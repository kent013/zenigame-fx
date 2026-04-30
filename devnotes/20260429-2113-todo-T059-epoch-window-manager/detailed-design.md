# 詳細設計: T059 — Epoch / Window Manager

## 使命・制約 (絶対遵守)

### zenigame-fx Alpha Factory 使命
live_criteria 全指標同時充足 + (ii-lite) 通過で使命達成。 絶対制約: イントラデイ / ロング・ショート両方向 / スワップ・スプレッド反映。

### 禁止事項
1-7 (synthesis § 1.3 参照)
8. ゲノム archive スキーマ変更時の値伝搬漏れ ← T058 で対応済 (本 TODO は依存)

### コーディングルール
- バグ修正はテストファースト
- 全施策にテスト必須
- テスト命名: 振る舞いを説明する汎用的な名前
- テスト配置: 対象モジュールに対応するテストファイル
- uv 必須: `uv run pytest tests/alpha_factory/`
- ruff / mypy 通過: `uv run ruff check src/ tests/` / `uv run mypy src/`
- Python 3.13 + numpy + pandas

## 概念設計リファレンス

`devnotes/20260429-2113-todo-T059-epoch-window-manager/conceptual-design.md` (Round 5 で APPROVED)

## Round 1 review 反映 (Codex 詳細レビュー Round 1 → Round 2)

| Round 1 [Critical/Warning/Suggestion] | 修正対応 |
|---|---|
| [C1] mark_run_status 全 epoch 走査と「異 epoch で同 run_id 許容」 テストが矛盾 | run_id を全 epoch で一意必須化 (reserve_run_slot で全 epoch 走査の重複 check)、 mark_run_status は run_id 単独で対象一意特定可能に。 テスト名を `test_run_id_uniqueness_enforced_globally_across_epochs` に修正 |
| [C2] reset() が破損 state で `_load_state_no_init` 呼び自身が失敗 | reset 内で `EpochStateCorruptError` 捕捉、 previous_state_snapshot に `{"corrupt": True, "error": ...}` 記録、 削除続行 |
| [W1] reset() lock 無し競合 | `with self._file_lock():` で全体保護 |
| [W2] _compute_fingerprint dataset_cfg 未使用 | 引数削除、 _verify_compatibility / _init_state で `dataset_cfg.instrument != self.instrument` を guard 追加 |
| [W3] make_epoch_id 時刻付き window 衝突余地 | 「window.start/end は 00:00 UTC 固定」 の契約を docstring に明記 |
| [W4] 破損 reset / 同 run_id 複数 epoch テスト不足 | `test_reset_recovers_even_when_state_json_is_corrupt`、 `test_reserve_raises_duplicate_run_id_error_when_same_id_in_other_epoch` 追加 |
| [W5] gitignore lock 名衝突 + 冗長 | 施策 3 を削除 (既存 `.cache/` 全体無視で対応済、 lock file 名も `.with_suffix(".lock")` で適切) |
| [S1] make_epoch_id 時刻固定明記 | docstring に「00:00 UTC 固定契約」 |
| [S2] flaky test 制御 | `pytest-timeout` + `pytest.mark.flaky(reruns=2)` を test 案に明記 |

## 施策一覧 (Phase 1: T059 PR、 Phase 2 は別 PR)

| # | 施策名 | 変更ファイル | 優先度 |
|---|--------|------------|--------|
| 1 | `epoch_manager.py` 新規作成 (EpochWindow + EpochManager + 6 種例外) | `src/alpha_factory/epoch_manager.py` (新規) | Critical |
| 2 | `tests/alpha_factory/test_epoch_manager.py` 新規作成 (単体テスト) | (新規) | Critical |

**Phase 1 (T059 PR) スコープは上記 2 施策のみ** (Round 1 [Warning] 5 反映で施策 3 削除)。 `run_ga.py` 組込・`default.yaml` 24m 切替・`config.py` 拡張 は **Phase 2 (別 PR、 別 TODO)** で実施。 これにより T059 PR 単独で merge しても runtime に影響なし。

---

## 施策 1: `epoch_manager.py` 新規作成

### 変更箇所
- ファイル: `src/alpha_factory/epoch_manager.py` (新規)

### 波及変更
- `AGENTS.md`: なし (内部 module、 T059 PR では runtime 未組込)
- `.claude/skills/zenigame-fx-{skill}/SKILL.md`: なし
- `config/alpha_factory/default.yaml`: なし (Phase 2 で `dataset.start/end` を 24m 化、 epoch_manager セクションは class const + state fingerprint で固定するため追加しない)
- `docs/alpha_factory/*.md`: なし (Phase 2 完了後に runbook 更新を別 TODO で)

### 変更後コード

```python
"""T059: Epoch / Window Manager — 24m rolling, stride=4w, max_runs/epoch=6.

詳細:
- 概念設計: devnotes/20260429-2113-todo-T059-epoch-window-manager/conceptual-design.md
- synthesis: devnotes/20260428-2300-cascade-port-debate/synthesis.md § 4.2
- T058 依存: dataset_epoch_id grammar、 RunContext 受け皿

Phase 1 (本 TODO): EpochManager 単体実装 + テストのみ、 run_ga.py 未組込。
Phase 2 (別 PR): 24m 切替 + run_ga.py 組込。
"""

from __future__ import annotations

import fcntl
import json
import os
import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, ClassVar, Final

import structlog

logger = structlog.get_logger(__name__)

__all__ = [
    "DuplicateRunIdError",
    "EpochCapExceeded",
    "EpochDatasetMismatch",
    "EpochLockTimeout",
    "EpochManager",
    "EpochStateCorruptError",
    "EpochStateIncompatible",
    "EpochWindow",
]


# ---------------------------------------------------------------------------
# Exceptions (6 種、 reserve_run_slot から raise)
# ---------------------------------------------------------------------------


class EpochCapExceeded(RuntimeError):
    """max_runs/epoch 超過 + 次 epoch end が data horizon を超える."""


class EpochStateIncompatible(RuntimeError):
    """state file の compatibility fingerprint が現 config と不一致."""


class EpochStateCorruptError(RuntimeError):
    """state file が破損 (JSON 壊れ等)、 明示 reset 必須."""


class EpochDatasetMismatch(RuntimeError):
    """cfg.dataset が現 epoch window と不一致 (6m → 24m 移行時の安全弁)."""


class EpochLockTimeout(RuntimeError):
    """fcntl lock 取得 timeout (LOCK_TIMEOUT_SECONDS 超過)."""


class DuplicateRunIdError(ValueError):
    """run_id の一意性違反 (全 epoch で一意必須、 Round 1 [Critical] 1)."""


# ---------------------------------------------------------------------------
# datetime helpers (`Z` vs `+00:00` 偽不一致回避)
# ---------------------------------------------------------------------------


def _normalize_dt(value: str | datetime) -> datetime:
    """Normalize to UTC-aware datetime (Z / +00:00 を吸収)."""
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _normalize_dt_to_iso(dt: datetime) -> str:
    """常に `+00:00` 形式の ISO 文字列で出力."""
    return _normalize_dt(dt).astimezone(UTC).isoformat()


def _now_utc() -> datetime:
    return datetime.now(UTC)


# ---------------------------------------------------------------------------
# EpochWindow (frozen, identity = (start, end))
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EpochWindow:
    """rolling 24m window. identity is (start, end) only."""

    start: datetime
    end: datetime

    def __post_init__(self) -> None:
        if self.end <= self.start:
            raise ValueError(
                f"EpochWindow.end ({self.end}) must be > start ({self.start})"
            )


# ---------------------------------------------------------------------------
# DatasetConfigLike protocol (T058 DatasetConfig との独立性確保)
# ---------------------------------------------------------------------------


class DatasetConfigLike:
    """``cfg.dataset`` から必要な属性を duck-type で受ける.

    Note: 実 `DatasetConfig` import を回避 (T058 未マージでも T059 は単体動作可能).
    """

    instrument: str
    start: datetime
    end: datetime


# ---------------------------------------------------------------------------
# EpochManager
# ---------------------------------------------------------------------------


class EpochManager:
    """rolling 24m window + atomic reservation + state compatibility check."""

    WINDOW_LENGTH_WEEKS: ClassVar[int] = 104
    STRIDE_DAYS: ClassVar[int] = 28
    MAX_RUNS_PER_EPOCH: ClassVar[int] = 6
    MARGIN_DAYS: ClassVar[int] = 7
    LOCK_TIMEOUT_SECONDS: ClassVar[int] = 10
    LOCK_RETRY_INTERVAL_S: ClassVar[float] = 0.1
    EPOCH_ID_FORMAT_VERSION: ClassVar[int] = 1
    STATE_SCHEMA_VERSION: ClassVar[int] = 1

    DEFAULT_STATE_RELATIVE_PATH: ClassVar[Path] = Path(
        ".cache/alpha_factory/epoch_state.json"
    )

    def __init__(
        self,
        *,
        repo_root: Path,
        anchor_origin: datetime,
        instrument: str,
        latest_data_end_floor: datetime,
        state_path: Path | None = None,
    ) -> None:
        """
        Args:
            repo_root: repository root path (CWD 依存解消)
            anchor_origin: epoch 0 の window.end (state file に固定保存)
            instrument: anchor pair (e.g., "EUR_JPY")
            latest_data_end_floor: data horizon (DB 最新 - MARGIN_DAYS)
            state_path: state file path (default: repo_root / DEFAULT_STATE_RELATIVE_PATH)
        """
        self.repo_root = repo_root
        self.anchor_origin = _normalize_dt(anchor_origin)
        self.instrument = instrument
        self.latest_data_end_floor = _normalize_dt(latest_data_end_floor)
        self._state_path = state_path or (repo_root / self.DEFAULT_STATE_RELATIVE_PATH)
        self._state_path.parent.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def make_epoch_id(self, window: EpochWindow) -> str:
        """canonical (start, end) から deterministic epoch_id 生成.

        契約: window.start/end は **00:00 UTC 固定** (anchor_origin が UTC midnight、
        STRIDE_DAYS=28 が日単位なので window 境界は常に 00:00 UTC)。
        日付以下の time component に意味を持たせない (Round 1 [Suggestion] 1 反映)。
        """
        start_str = window.start.strftime("%Y%m%d")
        end_str = window.end.strftime("%Y%m%d")
        return f"epoch_{start_str}_{end_str}"

    def current_window(self) -> EpochWindow:
        """state file から現 epoch_index を読み window 計算."""
        state = self._load_state_no_init()
        if state is None:
            return self._compute_window(0)
        return self._compute_window(state["current_epoch_index"])

    def reserve_run_slot(
        self,
        run_id: str,
        *,
        dataset_cfg: DatasetConfigLike,
    ) -> EpochWindow:
        """file lock 付き atomic reservation.

        run_id は全 epoch で一意必須 (Round 1 [Critical] 1)。 同 run_id が他 epoch
        で既に予約されている場合 DuplicateRunIdError raise、 mark_run_status の
        対象一意性を保証する (全 epoch 走査時の先頭一致 ambiguity を排除)。

        Returns:
            予約成功時の EpochWindow。 caller は make_epoch_id(window) で
            dataset_epoch_id を取得し RunContext に注入する。

        Raises:
            EpochLockTimeout: fcntl lock 取得 timeout (10s 超)
            EpochStateCorruptError: state file 破損 (JSON 壊れ等)
            EpochStateIncompatible: compatibility fingerprint 不一致 / instrument 不一致
            EpochDatasetMismatch: cfg.dataset と現 epoch window が不一致
            EpochCapExceeded: max_runs/epoch 超 + 次 epoch end が data horizon 超
            DuplicateRunIdError: 全 epoch で run_id の一意性違反
        """
        """file lock 付き atomic reservation.

        Returns:
            予約成功時の EpochWindow。 caller は make_epoch_id(window) で
            dataset_epoch_id を取得し RunContext に注入する。

        Raises:
            EpochLockTimeout: fcntl lock 取得 timeout (10s 超)
            EpochStateCorruptError: state file 破損 (JSON 壊れ等)
            EpochStateIncompatible: compatibility fingerprint 不一致
            EpochDatasetMismatch: cfg.dataset と現 epoch window が不一致
            EpochCapExceeded: max_runs/epoch 超 + 次 epoch end が data horizon 超
            DuplicateRunIdError: 同 epoch 内で同 run_id の重複予約
        """
        with self._file_lock():
            state = self._load_state_or_init(dataset_cfg)
            self._verify_compatibility(state, dataset_cfg)
            current_window = self._compute_window(state["current_epoch_index"])
            self._verify_dataset_match(dataset_cfg, current_window)

            # epoch advance 判定 (slots_consumed_in_epoch 単調増加カウンタ)
            if state["slots_consumed_in_epoch"] >= self.MAX_RUNS_PER_EPOCH:
                next_window = self._compute_window(state["current_epoch_index"] + 1)
                if next_window.end > self.latest_data_end_floor:
                    raise EpochCapExceeded(
                        f"max_runs/epoch ({self.MAX_RUNS_PER_EPOCH}) reached and "
                        f"next epoch end ({next_window.end}) exceeds data horizon "
                        f"({self.latest_data_end_floor}). Wait for data update."
                    )
                state["current_epoch_index"] += 1
                state["slots_consumed_in_epoch"] = 0
                logger.info(
                    "epoch_manager.epoch_advanced",
                    new_epoch_index=state["current_epoch_index"],
                    new_window_start=str(next_window.start),
                    new_window_end=str(next_window.end),
                )

            # 全 epoch で run_id 一意 check (Round 1 [Critical] 1 反映)
            for past_epoch_key, past_records in state["run_records"].items():
                if run_id in past_records:
                    raise DuplicateRunIdError(
                        f"run_id {run_id!r} already reserved in epoch {past_epoch_key} "
                        f"(global uniqueness required across all epochs)."
                    )

            # slot 消費 (status と分離)
            epoch_key = str(state["current_epoch_index"])
            epoch_records = state["run_records"].setdefault(epoch_key, {})
            epoch_records[run_id] = {
                "status": "started",
                "reserved_at": _now_utc().isoformat(),
            }
            state["slots_consumed_in_epoch"] += 1
            state["last_updated"] = _now_utc().isoformat()
            self._save_state_atomic(state)

            window = self._compute_window(state["current_epoch_index"])
            logger.info(
                "epoch_manager.run_reserved",
                run_id=run_id,
                epoch_index=state["current_epoch_index"],
                slots_consumed=state["slots_consumed_in_epoch"],
                window_start=str(window.start),
                window_end=str(window.end),
            )
            return window

    def mark_run_status(
        self,
        run_id: str,
        status: str,
        *,
        error: str | None = None,
    ) -> None:
        """Run 終了時の status 更新 (`completed` / `failed` / `aborted`).

        旧 epoch の running run を後から terminal にする経路もここで動作。
        """
        if status not in {"completed", "failed", "aborted"}:
            raise ValueError(f"invalid status: {status!r}")
        with self._file_lock():
            state = self._load_state_no_init()
            if state is None:
                logger.warning("epoch_manager.mark_run_status_no_state", run_id=run_id)
                return
            # run_id を全 epoch の run_records から探す (旧 epoch 対応)
            for epoch_key, records in state["run_records"].items():
                if run_id in records:
                    records[run_id]["status"] = status
                    records[run_id][f"{status}_at"] = _now_utc().isoformat()
                    if error is not None:
                        records[run_id]["error"] = error
                    state["last_updated"] = _now_utc().isoformat()
                    self._save_state_atomic(state)
                    logger.info(
                        "epoch_manager.run_status_updated",
                        run_id=run_id,
                        status=status,
                        epoch_index=int(epoch_key),
                    )
                    return
            logger.warning("epoch_manager.mark_run_status_not_found", run_id=run_id)

    def reset(self, *, reason: str) -> None:
        """state file 削除 + 新規初期化 + audit log 追記.

        破損 state でも reset を完遂できる (Round 1 [Critical] 2 反映)。
        production では `--reset-epoch-state --yes-reset-epoch-state --reason "..."`
        の 3-flag 必須経路でしか呼ばれないこと。
        """
        if not reason or not reason.strip():
            raise ValueError("reset reason must be non-empty")
        with self._file_lock():  # Round 1 [Warning] 1 反映: lock で競合防止
            # 既存 state を audit_log に保存 (破損例外捕捉、 reset 自体は完遂)
            try:
                previous = self._load_state_no_init()
            except EpochStateCorruptError as exc:
                previous = {"corrupt": True, "error": str(exc)}
                logger.warning(
                    "epoch_manager.reset_with_corrupt_state",
                    error=str(exc),
                )
            audit_path = self.repo_root / "reports/audit/epoch_manager_audit_log.jsonl"
            audit_path.parent.mkdir(parents=True, exist_ok=True)
            with audit_path.open("a", encoding="utf-8") as f:
                json.dump(
                    {
                        "event": "reset_epoch_state",
                        "timestamp": _now_utc().isoformat(),
                        "reason": reason,
                        "previous_state_snapshot": previous,
                    },
                    f,
                    ensure_ascii=False,
                )
                f.write("\n")
            # state file 削除 (破損していても unlink で OK)
            if self._state_path.exists():
                self._state_path.unlink()
            logger.warning(
                "epoch_manager.state_reset",
                reason=reason,
                audit_path=str(audit_path),
                previous_was_corrupt=bool(isinstance(previous, dict) and previous.get("corrupt")),
            )

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    def _compute_window(self, epoch_index: int) -> EpochWindow:
        """epoch_index から canonical EpochWindow を計算."""
        if epoch_index < 0:
            raise ValueError(f"epoch_index must be >= 0: {epoch_index}")
        end = self.anchor_origin + timedelta(days=self.STRIDE_DAYS * epoch_index)
        start = end - timedelta(weeks=self.WINDOW_LENGTH_WEEKS)
        return EpochWindow(start=start, end=end)

    def _load_state_or_init(self, dataset_cfg: DatasetConfigLike) -> dict[str, Any]:
        """state file を読み、 不在なら dataset_cfg を fingerprint 初期値で新規初期化."""
        if not self._state_path.exists():
            return self._init_state(dataset_cfg)
        try:
            with self._state_path.open("r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as exc:
            raise EpochStateCorruptError(
                f"epoch state file corrupt at {self._state_path}: {exc}. "
                "Use `--reset-epoch-state --yes-reset-epoch-state --reason \"...\"` to reset."
            ) from exc

    def _load_state_no_init(self) -> dict[str, Any] | None:
        """state file 読込のみ、 不在なら None を返す (新規初期化しない)."""
        if not self._state_path.exists():
            return None
        try:
            with self._state_path.open("r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as exc:
            raise EpochStateCorruptError(
                f"epoch state file corrupt at {self._state_path}: {exc}"
            ) from exc

    def _init_state(self, dataset_cfg: DatasetConfigLike) -> dict[str, Any]:
        """state file 不在時の新規初期化.

        Round 1 [Warning] 4 反映: dataset_cfg.instrument を self.instrument と照合 guard.
        """
        if dataset_cfg.instrument != self.instrument:
            raise EpochStateIncompatible(
                f"dataset_cfg.instrument ({dataset_cfg.instrument!r}) does not match "
                f"EpochManager.instrument ({self.instrument!r})."
            )
        return {
            "state_schema_version": self.STATE_SCHEMA_VERSION,
            "compatibility_fingerprint": self._compute_fingerprint(),
            "current_epoch_index": 0,
            "slots_consumed_in_epoch": 0,
            "run_records": {"0": {}},
            "last_updated": _now_utc().isoformat(),
        }

    def _compute_fingerprint(self) -> dict[str, Any]:
        """fingerprint 生成 (Round 1 [Warning] 4: dataset_cfg 引数削除、 self.instrument 単独)."""
        return {
            "instrument": self.instrument,
            "window_length_weeks": self.WINDOW_LENGTH_WEEKS,
            "stride_days": self.STRIDE_DAYS,
            "max_runs_per_epoch": self.MAX_RUNS_PER_EPOCH,
            "anchor_origin": _normalize_dt_to_iso(self.anchor_origin),
            "epoch_id_format_version": self.EPOCH_ID_FORMAT_VERSION,
            "state_schema_version": self.STATE_SCHEMA_VERSION,
        }

    def _verify_compatibility(
        self,
        state: dict[str, Any],
        dataset_cfg: DatasetConfigLike,
    ) -> None:
        # dataset_cfg.instrument 照合 (Round 1 [Warning] 4)
        if dataset_cfg.instrument != self.instrument:
            raise EpochStateIncompatible(
                f"dataset_cfg.instrument ({dataset_cfg.instrument!r}) does not match "
                f"EpochManager.instrument ({self.instrument!r})."
            )
        fp = dict(state.get("compatibility_fingerprint", {}))
        # anchor_origin の `Z` vs `+00:00` 偽不一致回避
        if "anchor_origin" in fp:
            fp["anchor_origin"] = _normalize_dt_to_iso(_normalize_dt(fp["anchor_origin"]))
        expected = self._compute_fingerprint()
        if fp != expected:
            raise EpochStateIncompatible(
                f"epoch state fingerprint mismatch.\n"
                f"  expected={expected}\n  got={fp}\n"
                "config or instrument changed; "
                "use `--reset-epoch-state --yes-reset-epoch-state --reason \"...\"` to reset."
            )

    def _verify_dataset_match(
        self,
        dataset_cfg: DatasetConfigLike,
        window: EpochWindow,
    ) -> None:
        cfg_start = _normalize_dt(dataset_cfg.start)
        cfg_end = _normalize_dt(dataset_cfg.end)
        if cfg_start != window.start or cfg_end != window.end:
            raise EpochDatasetMismatch(
                f"cfg.dataset ({cfg_start}..{cfg_end}) does not match "
                f"current epoch window ({window.start}..{window.end}). "
                "Update default.yaml dataset.start/end or run "
                "`--reset-epoch-state --yes-reset-epoch-state --reason \"...\"` if intended."
            )

    def _save_state_atomic(self, state: dict[str, Any]) -> None:
        """tmp + fsync + rename + fsync(dir) で耐クラッシュ保存."""
        tmp_token = f".tmp.{os.getpid()}.{uuid.uuid4().hex}.json"
        tmp_path = self._state_path.with_suffix(tmp_token)
        try:
            with tmp_path.open("w", encoding="utf-8") as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())
            tmp_path.rename(self._state_path)
            parent_fd = os.open(str(self._state_path.parent), os.O_RDONLY)
            try:
                os.fsync(parent_fd)
            finally:
                os.close(parent_fd)
        except Exception:
            tmp_path.unlink(missing_ok=True)
            raise

    def _file_lock(self) -> "_FileLockContext":
        return _FileLockContext(
            lock_path=self._state_path.with_suffix(".lock"),
            timeout_s=self.LOCK_TIMEOUT_SECONDS,
            retry_interval_s=self.LOCK_RETRY_INTERVAL_S,
        )


class _FileLockContext:
    """fcntl-based exclusive lock with timeout."""

    def __init__(
        self,
        lock_path: Path,
        timeout_s: int,
        retry_interval_s: float,
    ) -> None:
        self.lock_path = lock_path
        self.timeout_s = timeout_s
        self.retry_interval_s = retry_interval_s
        self._lock_file = None

    def __enter__(self) -> "_FileLockContext":
        logger.info(
            "epoch_manager.lock_acquire_start",
            path=str(self.lock_path),
            timeout_s=self.timeout_s,
        )
        self._lock_file = open(self.lock_path, "w")
        deadline = time.monotonic() + self.timeout_s
        while True:
            try:
                fcntl.flock(self._lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                logger.info("epoch_manager.lock_acquired", path=str(self.lock_path))
                return self
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    self._lock_file.close()
                    self._lock_file = None
                    raise EpochLockTimeout(
                        f"Failed to acquire epoch state lock within {self.timeout_s}s: {self.lock_path}"
                    )
                time.sleep(self.retry_interval_s)

    def __exit__(self, *args: Any) -> None:
        if self._lock_file is not None:
            fcntl.flock(self._lock_file.fileno(), fcntl.LOCK_UN)
            self._lock_file.close()
            self._lock_file = None
            logger.info("epoch_manager.lock_released", path=str(self.lock_path))
```

### ルックアヘッドバイアスチェック
- N/A (本施策は infrastructure、 primitive 変更ではない)

### C3 / C7 適用
- N/A (相関 / 因果 claim なし、 schema/control logic のみ)

### パフォーマンスチェック
- N/A (state file I/O は軽微、 fcntl lock も短時間)

### テスト計画 (施策 2 で詳述)

### リスク
- T058 未マージ時、 `RunContext` import が無いため `dataset_epoch_id` 注入経路は Phase 2 まで stub 値で動作 (T059 単体ではこの問題は出ない)
- macOS / Linux 前提、 Windows 非対応 (`fcntl`)

---

## 施策 2: `tests/alpha_factory/test_epoch_manager.py` 新規作成

### 変更箇所
- ファイル: `tests/alpha_factory/test_epoch_manager.py` (新規)

### テスト計画

振る舞いベース test 名 (Run 名・日付・セッション固有 NG):

#### Window identity
- `test_make_epoch_id_returns_canonical_format_for_canonical_window`
- `test_make_epoch_id_is_deterministic_for_same_start_end`
- `test_make_epoch_id_differs_when_start_or_end_differs`
- `test_epoch_window_rejects_end_le_start`
- `test_compute_window_at_index_zero_returns_anchor_window`
- `test_compute_window_at_index_one_advances_by_28_days`

#### dataset_epoch_id 生成
- `test_dataset_epoch_id_matches_pattern_lowercase_alphanumeric_underscore` (T058 grammar 整合)

#### Atomic reservation
- `test_reserve_run_slot_creates_state_file_when_absent`
- `test_reserve_run_slot_increments_slots_consumed_in_epoch`
- `test_reserve_run_slot_persists_run_record_with_started_status`
- `test_reserve_run_slot_returns_current_window`

#### epoch advance + data horizon
- `test_reserve_advances_to_next_epoch_when_max_runs_reached`
- `test_reserve_raises_epoch_cap_exceeded_when_next_end_beyond_data_horizon`

#### dataset mismatch hard guard
- `test_reserve_raises_epoch_dataset_mismatch_when_cfg_dataset_differs_from_window`

#### compatibility fingerprint
- `test_reserve_raises_epoch_state_incompatible_when_instrument_changes`
- `test_reserve_raises_epoch_state_incompatible_when_anchor_origin_changes`
- `test_state_anchor_origin_z_vs_plus_zero_zero_does_not_cause_false_mismatch`
- `test_init_state_raises_epoch_state_incompatible_when_dataset_cfg_instrument_differs` (Round 2 [Suggestion]: state 不在時の init 経路で instrument guard 動作確認)

#### state corruption
- `test_reserve_raises_epoch_state_corrupt_error_on_invalid_json`
- `test_load_state_no_init_returns_none_when_file_absent`

#### Duplicate run_id (Round 1 [Critical] 1 反映: 全 epoch 一意)
- `test_reserve_raises_duplicate_run_id_error_when_same_id_in_same_epoch`
- `test_reserve_raises_duplicate_run_id_error_when_same_id_in_other_epoch` (Round 1 [Critical] 1 + [Warning] テスト不足)
- `test_run_id_uniqueness_enforced_globally_across_epochs`

#### Lock timeout (Round 1 [Suggestion] 2: flaky 制御明記)
- `test_reserve_raises_epoch_lock_timeout_when_lock_held_by_another_process` (multiprocess test、 `pytest-timeout` で wall-clock 制限、 必要なら `pytest.mark.flaky(reruns=2)` で CI 安定化)
- `test_lock_released_after_reservation_completes`

#### Status update
- `test_mark_run_status_updates_record_to_completed`
- `test_mark_run_status_updates_record_in_previous_epoch`
- `test_mark_run_status_no_op_when_run_id_not_found`
- `test_mark_run_status_rejects_invalid_status`

#### Reset
- `test_reset_writes_audit_log_with_previous_state_snapshot`
- `test_reset_deletes_state_file`
- `test_reset_rejects_empty_reason`
- `test_state_initialized_fresh_after_reset`
- `test_reset_recovers_even_when_state_json_is_corrupt` (Round 1 [Critical] 2 + [Warning] テスト不足)
- `test_reset_records_corrupt_flag_in_audit_log_when_state_was_corrupt`
- `test_reset_acquires_file_lock_to_prevent_concurrent_reservation` (Round 1 [Warning] 1)

#### Atomic save
- `test_save_state_atomic_creates_no_partial_file_on_simulated_crash`
- `test_save_state_uses_unique_tmp_file_per_call`

### リスク
- multiprocess lock test は CI で flaky になりやすい → `pytest-timeout` 設定 + multiprocessing で並行性確認

---

## 施策 3: ~~`.gitignore` 追加~~ — **削除** (Round 1 [Warning] 5 + [Suggestion] 2 反映)

既存 `.gitignore` で `.cache/` 全体が無視済 (`grep -n cache .gitignore` で `.cache/` 行確認可)。 epoch_state.json も自動的に ignore される。 冗長追記は不要。

加えて、 lock file 名は `.with_suffix(".lock")` で `epoch_state.lock` (= json suffix が lock に置換)、 元案の `epoch_state.json.lock` は誤りだった。 これも `.cache/` 全体無視で対応済。

→ **施策 3 は削除**。 Phase 1 (T059 PR) スコープは施策 1 + 2 のみ。

---

## 実装モード

| 項目 | 内容 |
|------|------|
| 推奨モード | **standalone** (T058 とは独立に EpochManager 単体実装可、 ただし Phase 2 の runtime 組込で T058 依存が顕在化) |
| 判断根拠 | T059 PR 自体は単体テストのみで T058 の RunContext 等を import しない。 ただし Phase 2 (24m 切替) で T058 マージ済が前提 |
| 競合リスク | T058 マージ時の `src/alpha_factory/` 変更との小衝突可能性 (新規ファイル追加なのでマージ衝突は起きにくい) |
| 想定実装時間 | 短〜中 (2 施策 × ~半日、 テスト含めて 1 日程度) |

## 実装順序

T059 PR では 2 施策を 1 PR で着地。 Phase 2 (24m 切替 + run_ga.py 組込) は別 PR (別 TODO) で T058 マージ後に実施。

---

## DoD (Definition of Done)

T059 PR 完了基準:

### コード DoD
- [ ] `src/alpha_factory/epoch_manager.py` 新規作成 (EpochWindow + EpochManager + 6 例外、 全 epoch run_id 一意 + reset 破損対応 + reset lock + instrument 照合)
- [ ] `tests/alpha_factory/test_epoch_manager.py` 新規作成 (Round 1 [W4] テスト追加含めて全 pass)
- [ ] `uv run pytest tests/alpha_factory/test_epoch_manager.py` 全 pass
- [ ] `uv run ruff check src/ tests/` clean
- [ ] `uv run mypy src/` clean
- [ ] `run_ga.py` を変更しない (Phase 1 スコープ厳守)

### Phase 2 (T059 完了後の別 PR) DoD (申し送り)
- [ ] `default.yaml` の `dataset.start/end` を 24m に変更 (例: `2024-04-01` / `2026-04-01`)
- [ ] `run_ga.py` で `EpochManager` instantiate + `reserve_run_slot(run_id, dataset_cfg=cfg.dataset)` 呼出 + finally で `mark_run_status`
- [ ] `--reset-epoch-state` / `--yes-reset-epoch-state` / `--reason` の 3-flag CLI 必須実装
- [ ] **24m memory gate**: smoke で `max_workers=1` または `=2` の RSS 実測、 3 GB/worker 超過なし確認 → 結果を `devnotes/.../memory-gate-result.md` に記録
- [ ] Phase 2 PR で T058 マージ済を確認

### Docs / Skill DoD (Phase 2 で実施、 T059 では不要)
- [ ] `docs/alpha_factory/runbook.md` に EpochManager 運用手順追記
- [ ] `.claude/skills/zenigame-fx-run-alpha-factory/SKILL.md` に `--reset-epoch-state` 経路追記

---

## 関連 / 後段 TODO

- T058: Schema v2 contract (本 TODO の依存先、 詳細設計 APPROVED 済)
- T060: Partition + fold generator (本 TODO の `EpochWindow` を消費)
- Phase 2 PR (別 TODO): 24m 切替 + run_ga.py 組込 + RSS gate
- T067: enforcement_mode 切替
- T075: 旧 v1 archive 物理削除
