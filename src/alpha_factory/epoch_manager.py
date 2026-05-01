"""T059: Epoch / Window Manager — 24m rolling, stride=4w, max_runs/epoch=6.

詳細:
- 概念設計: devnotes/20260429-2113-todo-T059-epoch-window-manager/conceptual-design.md
- 詳細設計: devnotes/20260429-2113-todo-T059-epoch-window-manager/detailed-design.md
- synthesis: devnotes/20260428-2300-cascade-port-debate/synthesis.md § 4.2
- T058 依存: dataset_epoch_id grammar、 RunContext 受け皿

T059 PR 1 (本 TODO):
- ``EpochWindow`` (frozen dataclass、 identity = (start, end))
- ``make_epoch_id(window)`` (deterministic、 module-level 関数、 grammar 適合)
- ``EpochManager`` (rolling window 生成 + atomic reservation + state compatibility check)
- ``run_ga.py`` で stub 置換 (= make_epoch_id 経由 deterministic、 fallback で互換維持)

Phase 2 follow-up (別 PR): ``default.yaml`` の 24m 切替 + ``EpochManager.reserve_run_slot``
の runtime 組込 + RSS gate 計測。
"""

from __future__ import annotations

import fcntl
import json
import os
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, ClassVar, Protocol, runtime_checkable

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
    "make_epoch_id",
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
    """rolling 24m window. identity is (start, end) only.

    契約: ``start`` / ``end`` は **00:00 UTC 固定**。
    日付以下の time component は ``make_epoch_id`` の出力に反映されないため、
    時刻を持つと canonical な (start, end) と衝突する余地が出てしまう。
    ``EpochManager._compute_window`` は ``anchor_origin`` (UTC midnight 想定) +
    日単位 stride で window を生成するためこの契約は自然に成立する。
    """

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


@runtime_checkable
class DatasetConfigLike(Protocol):
    """``cfg.dataset`` から必要な属性を duck-type で受ける Protocol.

    Note: 実 ``DatasetConfig`` import を回避 (T058 と独立に T059 単体動作可能)。
    """

    instrument: str
    start: datetime
    end: datetime


# ---------------------------------------------------------------------------
# make_epoch_id (module-level deterministic function)
# ---------------------------------------------------------------------------


def make_epoch_id(window: EpochWindow) -> str:
    """canonical (start, end) から deterministic epoch_id 生成.

    出力 grammar: ``[a-z0-9_]+`` (T058 ``DATASET_EPOCH_ID_PATTERN`` 適合)。

    契約: window.start/end は **00:00 UTC 固定**。 ``EpochManager._compute_window``
    が ``anchor_origin`` (UTC midnight) + 日単位 stride で window を生成するため
    この契約は自然に成立する (Round 1 [Suggestion] 1 反映)。

    Args:
        window: identity が (start, end) の ``EpochWindow``.

    Returns:
        ``f"epoch_{YYYYMMDD}_{YYYYMMDD}"`` 形式の deterministic 識別子.
    """
    start_str = window.start.strftime("%Y%m%d")
    end_str = window.end.strftime("%Y%m%d")
    return f"epoch_{start_str}_{end_str}"


# ---------------------------------------------------------------------------
# EpochManager
# ---------------------------------------------------------------------------


class EpochManager:
    """rolling 24m window + atomic reservation + state compatibility check.

    Phase 1 (T059 PR) では単体実装 + テスト + ``run_ga.py`` の deterministic
    epoch_id 生成 (= ``make_epoch_id(window)``) のみ。 ``reserve_run_slot`` を
    runtime で呼ぶ Phase 2 は別 PR (24m 切替 + RSS gate 計測 後)。
    """

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
            repo_root: repository root path (CWD 依存解消).
            anchor_origin: epoch 0 の window.end (state file に固定保存).
            instrument: anchor pair (e.g., ``"EUR_JPY"``).
            latest_data_end_floor: data horizon (DB 最新 - MARGIN_DAYS).
            state_path: state file path (default: ``repo_root / DEFAULT_STATE_RELATIVE_PATH``).
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
        """``make_epoch_id(window)`` の thin wrapper (instance API として提供).

        詳細: module-level :func:`make_epoch_id` 参照.
        """
        return make_epoch_id(window)

    def current_window(self) -> EpochWindow:
        """state file から現 epoch_index を読み window 計算.

        state file 不在時は epoch_index=0 の window を返す (init はしない、
        新規予約時に :meth:`reserve_run_slot` 経由で初期化される)。
        """
        state = self._load_state_no_init()
        if state is None:
            return self._compute_window(0)
        return self._compute_window(int(state["current_epoch_index"]))

    def reserve_run_slot(
        self,
        run_id: str,
        *,
        dataset_cfg: DatasetConfigLike,
    ) -> EpochWindow:
        """file lock 付き atomic reservation.

        run_id は全 epoch で一意必須 (Round 1 [Critical] 1)。 同 run_id が他 epoch
        で既に予約されている場合 ``DuplicateRunIdError`` raise、
        :meth:`mark_run_status` の対象一意性を保証する (全 epoch 走査時の先頭一致
        ambiguity を排除)。

        Returns:
            予約成功時の ``EpochWindow``。 caller は ``make_epoch_id(window)`` で
            ``dataset_epoch_id`` を取得し ``RunContext`` に注入する。

        Raises:
            EpochLockTimeout: fcntl lock 取得 timeout (10s 超).
            EpochStateCorruptError: state file 破損 (JSON 壊れ等).
            EpochStateIncompatible: compatibility fingerprint 不一致 / instrument 不一致.
            EpochDatasetMismatch: cfg.dataset と現 epoch window が不一致.
            EpochCapExceeded: max_runs/epoch 超 + 次 epoch end が data horizon 超.
            DuplicateRunIdError: 全 epoch で run_id の一意性違反.
        """
        with self._file_lock():
            state = self._load_state_or_init(dataset_cfg)
            self._verify_compatibility(state, dataset_cfg)

            # epoch advance 判定 (slots_consumed_in_epoch 単調増加カウンタ)。
            # advance 自体は dataset_cfg 検証に**先立って**行う (Codex
            # impl-review-pr1 Round 1 [Blocker] H4 反映): caller は post-advance
            # の新 window に合わせた cfg を渡す責務を負い、 mismatch なら
            # ``EpochDatasetMismatch`` で raise される。
            if int(state["slots_consumed_in_epoch"]) >= self.MAX_RUNS_PER_EPOCH:
                next_window = self._compute_window(
                    int(state["current_epoch_index"]) + 1
                )
                if next_window.end > self.latest_data_end_floor:
                    raise EpochCapExceeded(
                        f"max_runs/epoch ({self.MAX_RUNS_PER_EPOCH}) reached and "
                        f"next epoch end ({next_window.end}) exceeds data horizon "
                        f"({self.latest_data_end_floor}). Wait for data update."
                    )
                state["current_epoch_index"] = int(state["current_epoch_index"]) + 1
                state["slots_consumed_in_epoch"] = 0
                logger.info(
                    "epoch_manager.epoch_advanced",
                    new_epoch_index=state["current_epoch_index"],
                    new_window_start=str(next_window.start),
                    new_window_end=str(next_window.end),
                )

            # 現 epoch (advance 後なら新 epoch) の window と cfg.dataset を照合。
            current_window = self._compute_window(int(state["current_epoch_index"]))
            self._verify_dataset_match(dataset_cfg, current_window)

            # 全 epoch で run_id 一意 check (Round 1 [Critical] 1 反映)
            for past_epoch_key, past_records in state["run_records"].items():
                if run_id in past_records:
                    raise DuplicateRunIdError(
                        f"run_id {run_id!r} already reserved in epoch "
                        f"{past_epoch_key} (global uniqueness required across all "
                        "epochs)."
                    )

            # slot 消費 (status と分離)
            epoch_key = str(state["current_epoch_index"])
            epoch_records = state["run_records"].setdefault(epoch_key, {})
            epoch_records[run_id] = {
                "status": "started",
                "reserved_at": _now_utc().isoformat(),
            }
            state["slots_consumed_in_epoch"] = (
                int(state["slots_consumed_in_epoch"]) + 1
            )
            state["last_updated"] = _now_utc().isoformat()
            self._save_state_atomic(state)

            window = self._compute_window(int(state["current_epoch_index"]))
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
        """Run 終了時の status 更新 (``completed`` / ``failed`` / ``aborted``).

        旧 epoch の running run を後から terminal にする経路もここで動作。
        run_id は全 epoch で一意なので最初の一致で更新を確定する。
        """
        if status not in {"completed", "failed", "aborted"}:
            raise ValueError(f"invalid status: {status!r}")
        with self._file_lock():
            state = self._load_state_no_init()
            if state is None:
                logger.warning("epoch_manager.mark_run_status_no_state", run_id=run_id)
                return
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
        production では ``--reset-epoch-state --yes-reset-epoch-state --reason "..."``
        の 3-flag 必須経路でしか呼ばれないこと (Phase 2 で実装)。
        """
        if not reason or not reason.strip():
            raise ValueError("reset reason must be non-empty")
        with self._file_lock():  # Round 1 [Warning] 1 反映: lock で競合防止
            previous: dict[str, Any] | None
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
            if self._state_path.exists():
                self._state_path.unlink()
            logger.warning(
                "epoch_manager.state_reset",
                reason=reason,
                audit_path=str(audit_path),
                previous_was_corrupt=bool(
                    isinstance(previous, dict) and previous.get("corrupt")
                ),
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

    def _load_state_or_init(
        self, dataset_cfg: DatasetConfigLike
    ) -> dict[str, Any]:
        """state file を読み、 不在なら ``dataset_cfg`` を fingerprint 初期値で新規初期化."""
        if not self._state_path.exists():
            return self._init_state(dataset_cfg)
        try:
            with self._state_path.open("r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as exc:
            raise EpochStateCorruptError(
                f"epoch state file corrupt at {self._state_path}: {exc}. "
                "Use `--reset-epoch-state --yes-reset-epoch-state --reason \"...\"` "
                "to reset."
            ) from exc

    def _load_state_no_init(self) -> dict[str, Any] | None:
        """state file 読込のみ、 不在なら ``None`` を返す (新規初期化しない)."""
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

        Round 1 [Warning] 4 反映: ``dataset_cfg.instrument`` を ``self.instrument``
        と照合 guard。
        """
        if dataset_cfg.instrument != self.instrument:
            raise EpochStateIncompatible(
                f"dataset_cfg.instrument ({dataset_cfg.instrument!r}) does not "
                f"match EpochManager.instrument ({self.instrument!r})."
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
        if dataset_cfg.instrument != self.instrument:
            raise EpochStateIncompatible(
                f"dataset_cfg.instrument ({dataset_cfg.instrument!r}) does not "
                f"match EpochManager.instrument ({self.instrument!r})."
            )
        fp = dict(state.get("compatibility_fingerprint", {}))
        # anchor_origin の `Z` vs `+00:00` 偽不一致回避
        if "anchor_origin" in fp:
            fp["anchor_origin"] = _normalize_dt_to_iso(
                _normalize_dt(fp["anchor_origin"])
            )
        expected = self._compute_fingerprint()
        if fp != expected:
            raise EpochStateIncompatible(
                f"epoch state fingerprint mismatch.\n"
                f"  expected={expected}\n  got={fp}\n"
                "config or instrument changed; "
                "use `--reset-epoch-state --yes-reset-epoch-state --reason \"...\"` "
                "to reset."
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
                "`--reset-epoch-state --yes-reset-epoch-state --reason \"...\"` "
                "if intended."
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

    def _file_lock(self) -> _FileLockContext:
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
        self._lock_file: Any = None

    def __enter__(self) -> _FileLockContext:
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
                        f"Failed to acquire epoch state lock within "
                        f"{self.timeout_s}s: {self.lock_path}"
                    ) from None
                time.sleep(self.retry_interval_s)

    def __exit__(self, *args: Any) -> None:
        if self._lock_file is not None:
            fcntl.flock(self._lock_file.fileno(), fcntl.LOCK_UN)
            self._lock_file.close()
            self._lock_file = None
            logger.info("epoch_manager.lock_released", path=str(self.lock_path))
