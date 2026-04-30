# 概念設計: T059 — Epoch / Window Manager (Round 3 修正反映版)

**最終更新**: 2026-04-29、 Round 1+2+3 修正反映済 (Codex CHANGES_REQUESTED → 改訂)
**verified against**: `main@ea56484` (Round 1 で確認)。 **T058 は詳細設計 APPROVED 済 (Round 7) だが実装はまだ存在しない**。 T059 は **T058 merge 後**前提で進む

## 背景・課題

T058 (Schema v2 contract) で `dataset_epoch_id` の **schema 受け皿**は設計済み (詳細設計 APPROVED) だが、 **値生成ロジック**は T058 stub (`epoch_legacy` 固定文字列)。 T059 で:

1. **dataset window の決定論的生成**: 24m rolling window
2. **`dataset_epoch_id` の canonical 生成**: window identity (start, end) のみから deterministic 生成
3. **max_runs/epoch=6 の atomic enforcement**: file lock 付き reservation で cap を強制
4. **stride=4w の epoch 切替**: data horizon ガード付き

synthesis § 4.2 (Epoch-rolling) 確定値:

| 項目 | 値 |
|---|---|
| dataset window length | 24 months ≈ 104w |
| epoch stride | 4w (= 28 日固定、 「月次相当」 ではない) |
| max_runs/epoch | 6 |
| primary dataset | EUR_JPY anchor 単一 |

## 前提検証 (C4) — current HEAD `main@ea56484` 基準

| 前提 | verified | 出典 |
|---|---|---|
| DB に約 3 年分 M1 データあり (2023-04-23〜2026-04-21、 全 6 通貨ペア) | ✓ | `synthesis.md` § 4.5 + DB query |
| dataset 24m primary、 35m は graduation audit のみ | ✓ | synthesis § 4.1 |
| `dataset_epoch_id` grammar = `^[a-z0-9_]+$` | (T058 詳細設計 APPROVED で確定、 **実装はまだ**) | T058 詳細設計 § 施策 1 |
| `RunContext.dataset_epoch_id` の受け皿 | (T058 詳細設計 APPROVED で確定、 **実装はまだ**) | T058 詳細設計 § 施策 2 |
| `schema_contract.py`, `run_context.py` 実体 | **✗ 未実装** (current HEAD `src/alpha_factory/` に存在しない) | grep 確認、 `TODO.md:9` で T058 は Open |
| `run_ga.py:1078` で `load_calibrated_threshold` が `dataset_epoch_id` 不使用 | ✓ | current HEAD |
| `default.yaml` `dataset.start=2025-10-01, end=2026-04-01` (6m) | ✓ | current HEAD |
| 既存 DB 上限 `2026-04-21` < 24m 化時の dataset.end 候補 | ✓ | synthesis § 4.5 |

**依存関係**: T059 は **T058 merge 後**を前提とする。 T058 が main にマージされていない時点では T059 のコード実装は不可 (= 別 PR を待つ)。 概念設計は T058 詳細設計を信頼して進めて良い。

## 改善アイデア

### 設計方針 (Round 1 修正反映)

1. **EpochWindow dataclass**: `(start, end)` のみで identity を持つ frozen dataclass。 `epoch_index` は metadata
2. **EpochManager**: rolling window 生成 + atomic reservation + state compatibility check
3. **`dataset_epoch_id` の canonical 生成**: `f"epoch_{start.strftime('%Y%m%d')}_{end.strftime('%Y%m%d')}"` (start/end 両方を encode、 衝突なし)
4. **state file**: `epoch_state.json` + file lock 付き reservation、 compatibility fingerprint で abort 判定
5. **data horizon gate**: epoch advance 時に `next_window.end <= latest_data_end_floor` を強制
6. **state 破損は fail-closed**: 明示 `--reset-epoch-state` flag のみ許可

### EpochWindow

```python
@dataclass(frozen=True)
class EpochWindow:
    """rolling 24m window の不変表現. identity は (start, end) のみ."""
    start: datetime  # UTC、 24m window の開始
    end: datetime    # UTC、 24m window の終了 (start + 104w)
```

`epoch_index` は **削除** (metadata 化、 state file の補助情報のみ)。 同一 `(start, end)` なら必ず同一 ID。

### dataset_epoch_id 生成式 (Round 1 [Critical] 4 反映)

```python
def make_epoch_id(window: EpochWindow) -> str:
    """canonical window identity から deterministic 生成.

    同一 (start, end) → 同一 ID (anchor 変更や epoch_index に依存しない)。
    grammar 適合: ^epoch_[0-9]+_[0-9]+$ ⊂ ^[a-z0-9_]+$
    """
    start_str = window.start.strftime("%Y%m%d")
    end_str = window.end.strftime("%Y%m%d")
    return f"epoch_{start_str}_{end_str}"
```

例:
- `EpochWindow(start=2024-04-01, end=2026-04-01)` → `epoch_20240401_20260401`
- 同 anchor の次 epoch (4w 進む): `EpochWindow(start=2024-04-29, end=2026-04-29)` → `epoch_20240429_20260429`
- 異 anchor で偶然同 (start, end) なら同 ID で OK (window identity が同じ = 同 epoch を意味)

### EpochManager (Round 1 [Critical] 3, 5, 6 反映)

```python
class EpochManager:
    """rolling 24m window + atomic reservation + state compatibility check."""

    WINDOW_LENGTH_WEEKS: ClassVar[int] = 104  # 24m
    STRIDE_DAYS: ClassVar[int] = 28           # 4w (28日固定、 「月次相当」 ではない)
    MAX_RUNS_PER_EPOCH: ClassVar[int] = 6
    MARGIN_DAYS: ClassVar[int] = 7            # data horizon safety margin (Round 2 [Warning] 4)
    LOCK_TIMEOUT_SECONDS: ClassVar[int] = 10  # fcntl 排他取得 timeout
    EPOCH_ID_FORMAT_VERSION: ClassVar[int] = 1
    STATE_SCHEMA_VERSION: ClassVar[int] = 1

    def __init__(
        self,
        *,
        repo_root: Path,                # CWD 依存解消 (Round 1 [Warning] 9)
        anchor_origin: datetime,        # epoch 0 の window.end (state に固定保存)
        instrument: str,                # state compatibility fingerprint
        latest_data_end_floor: datetime,  # data horizon (Round 1 [Critical] 1)
        state_path: Path | None = None,  # default: repo_root / .cache/alpha_factory/epoch_state.json
    ) -> None: ...

    def current_window(self) -> EpochWindow:
        """state file から現 epoch_index を読み EpochWindow 計算 + data horizon check."""

    def reserve_run_slot(self, run_id: str, *, dataset_cfg: DatasetConfig) -> RunContext:
        """file lock 付き atomic reservation (Round 1+2+3 反映、 短時間クリティカルセクションのみ排他).

        - state file を file lock で排他取得 (取得後 reservation 完了するまで保持、 GA 実行中は lock 解放)
        - dataset_cfg が epoch window と一致するか hard guard
        - max_runs/epoch (slots_consumed_in_epoch) 超過なら epoch advance を試行
        - data horizon を超えるなら EpochCapExceeded raise
        - state compatibility fingerprint 不一致なら fail-closed
        - reservation 成功で run_records に追加、 slots_consumed_in_epoch increment、 lock 解放
        """

    def make_epoch_id(self, window: EpochWindow) -> str:
        """canonical (start, end) から ID 生成 (上記関数)."""
```

### state file format (Round 1 [Warning] 8 + Round 2 [Critical] 5 + Round 2 [Warning] 3 反映)

`{repo_root}/.cache/alpha_factory/epoch_state.json`:

```json
{
    "state_schema_version": 1,
    "compatibility_fingerprint": {
        "instrument": "EUR_JPY",
        "window_length_weeks": 104,
        "stride_days": 28,
        "max_runs_per_epoch": 6,
        "anchor_origin": "2026-04-01T00:00:00+00:00",
        "epoch_id_format_version": 1,
        "state_schema_version": 1
    },
    "current_epoch_index": 0,
    "slots_consumed_in_epoch": 3,
    "run_records": {
        "0": {
            "run_20260429_211200": {"status": "completed", "reserved_at": "2026-04-29T21:12:00+00:00", "completed_at": "2026-04-29T21:32:00+00:00"},
            "run_20260429_213400": {"status": "failed", "reserved_at": "2026-04-29T21:34:00+00:00", "failed_at": "2026-04-29T21:50:00+00:00", "error": "..."},
            "run_20260429_220000": {"status": "started", "reserved_at": "2026-04-29T22:00:00+00:00"}
        }
    },
    "last_updated": "2026-04-29T22:00:00+00:00"
}
```

設計要点:
- **`run_records` は `{epoch_index: {run_id: record}}` の入れ子辞書** (Round 2 [Critical] 5): epoch advance 時も旧 epoch の running run を消さず terminal まで保持。 `mark_run_status` が後から status 更新可能
- **`slots_consumed_in_epoch`** (Round 3 [Critical] 1 反映): 現 epoch での予約済 slot の単調増加カウンタ。 status とは分離 (completed/failed でも slot は消費済として count、 max=6 cap で実質的に「現 epoch で何回予約したか」 を制御)。 これで完了 run が cap から除外されて実質無制限になる問題を回避
- **`compatibility_fingerprint` に `epoch_id_format_version` と `state_schema_version` 追加** (Round 2 [Warning] 3): 不一致なら fail-closed
- **datetime は `+00:00` 形式 (`isoformat()` 出力) で統一**、 文字列比較前に `_normalize_dt(s) -> datetime` で parse して datetime 比較 (Round 2 追加 Critical: anchor_origin の `Z` vs `+00:00` 偽不一致回避)

不変条件:
- `state_schema_version == 1` (互換破壊時は bump + fail-closed + reset 必須)
- `compatibility_fingerprint` の全 field が一致しない → **fail-closed**
- `0 <= slots_consumed_in_epoch <= 6`
- `slots_consumed_in_epoch == len(run_records[str(current_epoch_index)])` (現 epoch の全予約済 slot)

### file lock 付き reservation (Round 1 [Critical] 3 + Round 2 [Suggestion] 9)

`fcntl.flock` を直接使用 (`scripts/alpha_factory/calibrate_gate.py:28` で既存実用)、 抽象 `FileLock` ラッパは作らない。

定数:
- `LOCK_TIMEOUT_SECONDS: ClassVar[int] = 10` (Round 2 [Suggestion] 10、 定数化 + ログ出力)

```python
def reserve_run_slot(self, run_id: str, *, dataset_cfg: DatasetConfig) -> RunContext:
    """Round 2 [Critical] 4 反映: dataset_cfg を引数で受け、 epoch window 契約と一致するか hard guard."""
    lock_path = self._state_path.with_suffix(".lock")
    logger.info("epoch_manager.lock_acquire_start", path=str(lock_path), timeout_s=self.LOCK_TIMEOUT_SECONDS)
    deadline = time.monotonic() + self.LOCK_TIMEOUT_SECONDS
    retry_interval_s = 0.1  # 100ms ごとに再試行
    with open(lock_path, "w") as lock_file:
        # fcntl.flock 明示 (Round 4 [Warning] 2 反映: timeout 仕様確定)
        while True:
            try:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                logger.info("epoch_manager.lock_acquired", path=str(lock_path))
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    logger.error("epoch_manager.lock_timeout", path=str(lock_path), timeout_s=self.LOCK_TIMEOUT_SECONDS)
                    raise EpochLockTimeout(
                        f"Failed to acquire epoch state lock within {self.LOCK_TIMEOUT_SECONDS}s: {lock_path}"
                    )
                time.sleep(retry_interval_s)
        state = self._load_state_or_init(dataset_cfg)
        self._verify_compatibility(state, dataset_cfg)  # Round 2 [Critical] 4: dataset 契約 hard guard
        current_window = self._compute_window(state["current_epoch_index"])
        # Round 2 [Critical] 4: cfg.dataset が epoch window と一致しない → abort
        if (cfg_start_norm := _normalize_dt(dataset_cfg.start)) != current_window.start \
           or (cfg_end_norm := _normalize_dt(dataset_cfg.end)) != current_window.end:
            raise EpochDatasetMismatch(
                f"cfg.dataset ({cfg_start_norm}..{cfg_end_norm}) does not match "
                f"current epoch window ({current_window.start}..{current_window.end}). "
                "Update default.yaml or use --reset-epoch-state if intended."
            )
        # epoch advance 判定 (Round 3 [Critical] 1 反映: slots_consumed_in_epoch 単調増加)
        if state["slots_consumed_in_epoch"] >= self.MAX_RUNS_PER_EPOCH:
            next_window = self._compute_window(state["current_epoch_index"] + 1)
            if next_window.end > self.latest_data_end_floor:
                raise EpochCapExceeded(...)
            state["current_epoch_index"] += 1
            state["slots_consumed_in_epoch"] = 0
            # 旧 epoch の run_records は維持 (終了まで status 更新可、 Round 2 [Critical] 5)
            state["run_records"][str(state["current_epoch_index"])] = {}
        # Round 2 [Critical] 5 + Round 3 [Critical] 1: slot 消費 (status と分離)
        epoch_key = str(state["current_epoch_index"])
        epoch_records = state["run_records"].setdefault(epoch_key, {})
        # Round 4 [Suggestion]: 重複 run_id ガード
        if run_id in epoch_records:
            raise DuplicateRunIdError(
                f"run_id {run_id} already reserved in epoch {epoch_key}. "
                "Use a unique run_id per reservation."
            )
        epoch_records[run_id] = {
            "status": "started",
            "reserved_at": now_utc().isoformat(),
        }
        state["slots_consumed_in_epoch"] += 1  # 単調増加カウンタ (status 不問、 cap 強制)
        state["last_updated"] = now_utc().isoformat()
        self._save_state_atomic(state)  # tmp + fsync + rename
    window = self._compute_window(state["current_epoch_index"])
    return RunContext(
        run_id=run_id,
        run_number=...,
        dataset_epoch_id=self.make_epoch_id(window),
        base_config_hash=...,
        instrument=self.instrument,
    )
```

`_save_state_atomic` は zenigame `fsp_updater.py:_atomic_write_parquet` の pattern (tmp → fsync → rename → fsync(dir)) を踏襲。

### state 破損時の挙動 (Round 1 [Critical] 5 反映)

```python
def _load_state_or_init(self, dataset_cfg: DatasetConfig) -> dict:
    """state file を読込、 不在なら dataset_cfg を fingerprint 初期値として新規初期化.

    dataset_cfg は新規初期化時の fingerprint (instrument 等) 生成に使用、
    既存 state load 時は使わない (Round 5 [Suggestion] 1 反映)。
    """
    if not self._state_path.exists():
        return self._init_state()
    try:
        with self._state_path.open() as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        # Round 1 [Critical] 5: warning + 新規初期化は禁止 → fail-closed
        raise EpochStateCorruptError(
            f"epoch state file corrupt: {exc}. "
            "Use --reset-epoch-state CLI flag to explicit reset (last resort, "
            "destroys archive scope integrity)."
        )
```

CLI flag `--reset-epoch-state` (run_ga.py 側で実装) で唯一の reset 経路、 通常 production では使用禁止。

### epoch advance の data horizon (Round 1 [Critical] 1 反映)

`latest_data_end_floor` は run_ga.py 側で計算して EpochManager に渡す:

```python
# run_ga.py 内
import pyarrow.parquet as pq
def _compute_latest_data_end_floor(repo_root: Path, instrument: str) -> datetime:
    """DB 最新 bar_time から safety margin (1 week) を引いた値."""
    # PriceBarM1 から MAX(bar_time) を取得 (e.g., 2026-04-21)
    latest = query_max_bar_time(instrument)  # DB から
    # Round 2 [Warning] 4 + Round 3 [Warning] 2 反映: 定数化 + ログ
    return latest - timedelta(days=EpochManager.MARGIN_DAYS)  # safety margin
```

`next_window.end > latest_data_end_floor` なら `EpochCapExceeded` raise、 Run 全体 abort。

### state compatibility fingerprint (Round 1 [Warning] 8 + Round 2 [Warning] 3 反映)

`_verify_compatibility(state, dataset_cfg)`:

```python
EPOCH_ID_FORMAT_VERSION: ClassVar[int] = 1  # epoch_{start_yyyymmdd}_{end_yyyymmdd} 形式
STATE_SCHEMA_VERSION: ClassVar[int] = 1

def _verify_compatibility(self, state: dict, dataset_cfg: DatasetConfig) -> None:
    fp = state.get("compatibility_fingerprint", {})
    expected = {
        "instrument": self.instrument,
        "window_length_weeks": self.WINDOW_LENGTH_WEEKS,
        "stride_days": self.STRIDE_DAYS,
        "max_runs_per_epoch": self.MAX_RUNS_PER_EPOCH,
        "anchor_origin": _normalize_dt_to_iso(self.anchor_origin),  # `+00:00` 形式
        "epoch_id_format_version": self.EPOCH_ID_FORMAT_VERSION,
        "state_schema_version": self.STATE_SCHEMA_VERSION,
    }
    # Round 2 追加 Critical: anchor_origin の `Z` vs `+00:00` 偽不一致回避
    fp_normalized = dict(fp)
    if "anchor_origin" in fp_normalized:
        fp_normalized["anchor_origin"] = _normalize_dt_to_iso(_normalize_dt(fp_normalized["anchor_origin"]))
    if fp_normalized != expected:
        raise EpochStateIncompatible(
            f"epoch state fingerprint mismatch. expected={expected}, got={fp_normalized}. "
            "config or instrument changed; use --reset-epoch-state --yes-reset-epoch-state --reason \"...\" to reset."
        )
```

helper:

```python
def _normalize_dt(value: str | datetime) -> datetime:
    """`Z` / `+00:00` の差を吸収して datetime 化."""
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _normalize_dt_to_iso(dt: datetime) -> str:
    """常に `+00:00` 形式で出力 (state file の datetime 統一)."""
    return _normalize_dt(dt).astimezone(UTC).isoformat()
```

### RunContext との接続 (Phase 2 PR、 T059 完了後の別 PR で組込)

以下の擬似コードは **Phase 2 (24m 切替 + runtime 組込 PR) のスコープ**で、 T059 単独 PR では `run_ga.py` には反映しない。 T059 PR では EpochManager 単体テストのみ。

`run_ga.py` の startup で:

```python
# T058 stub `epoch_legacy` を T059 で置換 (T058 merge 後)
epoch_manager = EpochManager(
    repo_root=repo_root,
    anchor_origin=cfg.dataset.end,  # state に固定保存後は変更不可
    instrument=cfg.dataset.instrument,
    latest_data_end_floor=_compute_latest_data_end_floor(repo_root, cfg.dataset.instrument),
)

# atomic reservation (Round 1 [Critical] 3)
try:
    run_context = epoch_manager.reserve_run_slot(run_id, dataset_cfg=cfg.dataset)
except (
    EpochCapExceeded,
    EpochStateIncompatible,
    EpochStateCorruptError,
    EpochDatasetMismatch,  # Round 4 [Warning] 3 反映
    EpochLockTimeout,       # Round 4 [Warning] 2 反映
    DuplicateRunIdError,    # Round 4 [Suggestion] 反映
) as exc:
    logger.error("epoch_manager.reserve_failed", error=str(exc), exc_type=type(exc).__name__)
    raise

# Run 完了時の status update
try:
    # ... GA 実行 ...
    epoch_manager.mark_run_status(run_id, "completed")
except Exception:
    # Round 5 [Suggestion] 2 反映: mark_run_status 失敗時に元例外を潰さない。
    # status 更新失敗は log-only で握り、 元例外を re-raise (運用事故耐性)
    try:
        epoch_manager.mark_run_status(run_id, "failed")
    except Exception as mark_exc:
        logger.warning("epoch_manager.mark_run_status_failed", run_id=run_id, mark_error=str(mark_exc))
    raise
```

## 期待効果 (Round 1 [Warning] 2 反映: 効果量主張を抑制)

### live_criteria 達成への構造的貢献

- **epoch スコープの正当化**: T058 で受け皿、 T059 で値生成、 これで calibrate-gate scope / warmstart filter / archive admission の epoch 識別が**機能する**。 T058 単独では `epoch_legacy` 固定で実質汚染防止が効かない
- **再利用範囲の構造的制限**: 同 window で max 6 Run cap で同一履歴 over-selection を構造的に防ぐ (Bailey PBO/SPA 系警告対応、 効果量は run analysis で別途検証)
- **graduation lane 起動条件の機能化**: synthesis § 11.1「graduates >= 24 + 3 epoch にまたがって蓄積」 が functional に判定可能

### Round 1 [Warning] 期待効果文言下方修正

「epoch 跨ぎ汚染防止 (構造的)」 「selection inflation 抑制」 → **構造的に再利用範囲を制限する** に表現を下げる。 効果量主張は後段 run analysis で分離。

## 実装方針 (概要)

### コンポーネント変更 (Round 4 [Warning] 1 反映: Phase 1 / Phase 2 分離)

#### Phase 1: T059 PR (本 TODO のスコープ)

| ファイル | 変更内容 |
|---|---|
| `src/alpha_factory/epoch_manager.py` | **新規作成**。 `EpochWindow` (start, end のみ) + `EpochManager` (`reserve_run_slot`, `mark_run_status`, `make_epoch_id`, `current_window`) + 例外 (`EpochCapExceeded` / `EpochStateIncompatible` / `EpochStateCorruptError` / `EpochDatasetMismatch` / `EpochLockTimeout` / `DuplicateRunIdError`)。 file lock + state compatibility + data horizon 全部含む |
| `tests/alpha_factory/test_epoch_manager.py` | **新規**。 単体テスト全項目 (window identity / atomic reservation / 各例外 / state fingerprint / data horizon / `--reset-epoch-state` 経路) |
| `.gitignore` | `.cache/alpha_factory/epoch_state.json` と `*.lock` を ignore |

**Phase 1 では `run_ga.py` を変更しない**。 EpochManager を import せず、 runtime に影響なし。 単体テストのみで動作検証。

#### Phase 2: 24m 切替 + runtime 組込 PR (別 TODO、 T059 完了後)

| ファイル | 変更内容 |
|---|---|
| `src/alpha_factory/run_context.py` | T058 で実装済 (本 TODO の依存先)。 T059/Phase 2 では touch しない |
| `scripts/alpha_factory/run_ga.py` | `EpochManager` を起動初期に instantiate、 `reserve_run_slot(run_id, dataset_cfg=cfg.dataset)` で RunContext 取得、 finally で `mark_run_status`、 `--reset-epoch-state` / `--yes-reset-epoch-state` / `--reason` CLI flag (3 flag 必須) |
| `config/alpha_factory/default.yaml` | `dataset.start/end` を 24m に変更 (例: `2024-04-01` / `2026-04-01`)。 epoch_manager セクションは追加しない (class const + state fingerprint で固定) |
| `audit_log.jsonl` 出力経路 | `--reset-epoch-state` 実行時の audit event 永続化 |

**Phase 2 は別 PR**として、 24m memory gate (RSS 実測) を pass してから merge。

### state 破損時の reset 経路 (Round 2 [Warning] 6 反映: 二重明示 + 監査)

```bash
uv run python scripts/alpha_factory/run_ga.py \
  --reset-epoch-state \
  --yes-reset-epoch-state \
  --reason "Epoch state corruption recovery from incident #N"
```

3 つすべて指定が必須 (誤操作防止):
- `--reset-epoch-state`: 意図表示
- `--yes-reset-epoch-state`: 二重確認 (省略すると abort)
- `--reason "..."`: 理由文字列 (省略 / 空文字 で abort)

実行内容:
- state file 削除
- 新規初期化 (epoch_index=0)
- **`audit_log.jsonl` に追記必須** (`reset_epoch_state` event、 timestamp、 reason、 削除前 state snapshot)
- warning ログ大量出力
- production 使用禁止 (dev/debug 限定)

audit_log.jsonl format:
```json
{"event": "reset_epoch_state", "timestamp": "2026-04-29T22:00:00+00:00", "reason": "...", "previous_state_snapshot": {...}}
```

### 24m memory gate (Round 1 [Suggestion] 8 + Round 2 [Warning] 7 反映: DoD 拘束化)

T059 DoD 拘束条件として:

> **24m dataset 有効化 PR の前提条件** (T059 完了後の別 PR で `default.yaml` の `dataset.start/end` を 24m に変更する際の必須前提):
>
> - 24m smoke 実行で `max_workers=1` または `=2` の RSS を実測
> - 1 worker あたり RSS が **3 GB を超えていない**ことを確認
> - 超過する場合は `max_workers` を下げるか、 SharedBarStore 相当の memory 最適化を別 TODO (T070 以降) で先に実施
> - 実測値を `devnotes/20260429-2113-todo-T059-epoch-window-manager/memory-gate-result.md` に記録

T059 自体 (EpochManager 実装) はこの gate を消費せず通過可能 (= EpochManager 単独で 24m 化を強制しない)。 ただし「24m 化を有効化する別 PR」 の DoD として本 gate を要求する。

### T059 実装と runtime 有効化の分離 (Round 3 [Warning] 3 反映)

`reserve_run_slot` の `dataset_cfg != current_window` hard guard は強力だが、 現行 6m config (`default.yaml: dataset.start=2025-10-01, end=2026-04-01`) のままでは abort して GA 実行不能になる。 これを回避する 3 段階アプローチ:

1. **T059 PR (本 TODO)**: `EpochManager` クラスを実装、 単体テストで動作確認、 ただし `run_ga.py` から呼び出さない (= runtime 有効化しない)
2. **T058 + T059 統合 PR**: `RunContext` 経路 + `EpochManager.reserve_run_slot` を `run_ga.py` に組み込む。 ただし `default.yaml` を 24m に切替え、 同時に runtime 有効化
3. **T067 PR**: enforcement_mode を LOG_ONLY → FAIL_CLOSED に切替

つまり「T059 実装 PR の merge」 と「24m 切替 + runtime 有効化 PR の merge」 を分離。 T059 単独 PR で merge しても runtime に影響なし。 これで概念設計の hard guard と 6m 現状の衝突を回避。

## 制約・前提

- **T058 merge 後前提**: T058 のコードが main に存在しないと EpochManager → RunContext 注入経路が確立しない。 T058 PR が先行 merge されること
- **anchor_origin は state に固定**: 1 度設定した anchor は state reset (`--reset-epoch-state`) なしに変更不可。 fingerprint 不一致で abort
- **stride=28 days 固定**: synthesis 確定値、 「4w 月次相当」 ではなく「28 日固定」 (Round 1 [Suggestion] 反映)
- **file lock は fcntl-based**: macOS / Linux 前提、 Windows 非対応 (zenigame-fx は macOS 開発前提)
- **複数 Run 同時起動**: file lock は **reservation 中の短時間クリティカルセクションのみ排他** (Round 3 [Warning] 1)。 reservation 完了で lock 解放、 GA 実行中は他 Run も並行 reservation 可能 (= max_runs/epoch=6 cap で順次予約)。 lock acquire timeout 10s 超で abort
- **24m 有効化は別判断**: T059 は EpochManager 実装まで、 dataset.start/end の更新は別

## スコープ外

- T058: schema 受け皿 (本 TODO の依存先)
- T060: partition splitter / fold generator (本 TODO の `EpochWindow` を消費)
- T067: enforcement_mode 切替 (LOG_ONLY → FAIL_CLOSED)
- T070 以降: memory profile / RSS gate (24m 有効化前の必須前提だが本 TODO 範囲外)
- CLI override (`--override-epoch-id`) の本格実装
- `EpochManagerConfig` の yaml override (現状 class const + state fingerprint で固定が筋、 必要なら別 TODO)
- Windows 対応の file lock (現状 fcntl 前提)

## 学術引用 / 先行知見

- **Bailey, Borwein, López de Prado, Zhu (2015): "The Probability of Backtest Overfitting"**: rolling window + max_runs/epoch cap の根拠
- **Tashman (2000): "Out-of-sample tests of forecasting accuracy"**: rolling-origin 理論基盤
- **POSIX file locking (fcntl)**: file-based atomic reservation の基盤
- T058 詳細設計: `validate_epoch_id` grammar、 `RunContext` 受け皿
- zenigame `fsp_updater.py:_atomic_write_parquet`: tmp → fsync → rename pattern (state file save にも踏襲)

## Round 4 → Round 5 の改訂点

| Round 4 [Warning/Suggestion] | 修正対応 |
|---|---|
| [W1] Phase 1 / Phase 2 PR 境界混在 | 「コンポーネント変更」 セクションを Phase 1 (T059 PR) と Phase 2 (24m 切替 + runtime 組込 PR) に明示分離、 `run_ga.py` 変更は Phase 2 へ移動、 「RunContext との接続」 セクション冒頭に Phase 2 スコープと明記 |
| [W2] lock timeout 仕様未閉包 (`...` のまま) | `deadline = time.monotonic() + LOCK_TIMEOUT_SECONDS`、 `retry_interval_s = 0.1` で `BlockingIOError` 再試行ループ、 deadline 超で `EpochLockTimeout` raise。 acquire 開始/成功/timeout を log |
| [W3] `EpochDatasetMismatch` がハンドリング漏れ | reserve 失敗 except 節に `EpochDatasetMismatch` / `EpochLockTimeout` / `DuplicateRunIdError` 追加、 exc_type を log に含める |
| [Suggestion] run_id 重複予約ガード | `if run_id in epoch_records: raise DuplicateRunIdError` 追加 |

## Round 3 → Round 4 の改訂点

| Round 3 [Critical/Warning/Suggestion] | 修正対応 |
|---|---|
| [C1] max_runs/epoch=6 契約破壊 (started のみカウントだと無制限) | `runs_in_current_epoch` を撤廃、 `slots_consumed_in_epoch` 単調増加カウンタに変更 (status と分離) |
| [C2] reserve_run_slot / _load_state_or_init シグネチャ不整合 | `reserve_run_slot(self, run_id: str, *, dataset_cfg: DatasetConfig)` で統一、 `_load_state_or_init(self, dataset_cfg)` も統一、 caller `epoch_manager.reserve_run_slot(run_id, dataset_cfg=cfg.dataset)` に修正 |
| [W1] lock 仕様矛盾 (1 Run 終了まで lock 待ち vs reservation のみ排他) | 「reservation 中の短時間クリティカルセクションのみ排他」 と明示、 GA 実行中は lock 解放 |
| [W2] MARGIN_DAYS=7 本文未反映 | `EpochManager.MARGIN_DAYS: ClassVar[int] = 7` に追加、 `latest_data_end_floor` 計算を `timedelta(days=EpochManager.MARGIN_DAYS)` 参照に統一 |
| [W3] T059 24m なしで通せる記述が hard guard と衝突 | 「T059 実装 PR」 と「24m 切替 + runtime 有効化 PR」 を分離、 T059 PR は EpochManager 単体テストのみ、 runtime 組込 (run_ga.py) は別 PR |
| [Suggestion] Round 3 表記更新 | タイトル「Round 3 修正反映版」 + 最終更新「Round 1+2+3 反映」 |

## Round 2 → Round 3 の改訂点

| Round 2 [Critical/Warning/Suggestion] | 修正対応 |
|---|---|
| [C-extra] anchor_origin の `Z` vs `+00:00` 偽不一致 | `_normalize_dt` / `_normalize_dt_to_iso` helper で datetime 正規化、 比較前に必ず datetime 化 |
| [C4] 6m 運用中に 24m 想定 epoch_id 発行で ID 再利用汚染 | `reserve_run_slot(run_id, *, dataset_cfg)` で `cfg.dataset` が epoch window と一致しないなら `EpochDatasetMismatch` raise |
| [C5] mark_run_status が epoch advance で消失 | state を `run_records: {epoch_index: {run_id: record}}` 入れ子辞書に変更、 epoch advance 時も旧 epoch の running run を terminal まで保持 |
| [W2] safety margin 1 week 根拠未計測 | `MARGIN_DAYS: ClassVar[int] = 7` 定数化、 `latest`/`margin_days`/`floor`/`next_window.end` を毎回ログ出力で実測再校正 |
| [W3] compatibility_fingerprint 項目不足 | `epoch_id_format_version` と `state_schema_version` を fingerprint に追加 |
| [W6] --reset-epoch-state 二重明示 + audit | `--reset-epoch-state --yes-reset-epoch-state --reason "..."` 3 つ必須、 `audit_log.jsonl` に reset event 追記 |
| [W7] 24m memory gate を DoD に含む | T059 完了 → 24m 有効化 PR の前提条件として `max_workers=1/2` で RSS 実測、 3 GB/worker 超で別 TODO 必須 |
| [W8a] schema_version bump policy | 互換破壊時は state_schema_version bump + fail-closed + reset 必須を明文化 |
| [S1] FileLock 抽象 → fcntl.flock 明示 | `fcntl.flock(lock_file.fileno(), LOCK_EX | LOCK_NB)` 直接使用、 抽象 wrapper は作らない |
| [S2] lock timeout 10s 定数化・ログ化 | `LOCK_TIMEOUT_SECONDS: ClassVar[int] = 10`、 acquire 開始/成功/失敗を log |
| [S3] epoch_index は metadata 限定 | metadata 限定方針を明記、 ID/判定キーには使わない |

## Round 1 → Round 2 の改訂点

| Round 1 [Critical/Warning/Suggestion] | 修正対応 |
|---|---|
| [C1] epoch advance が data horizon と切れている | `latest_data_end_floor` を引数に追加、 `next_window.end > floor` で `EpochCapExceeded` raise |
| [C2] T058 未着地、 verified 表が current HEAD と不一致 | C4 表を current HEAD `main@ea56484` 基準に修正、 「T058 merge 後前提」 明記、 verified を T058 詳細設計 APPROVED 段階に修正 |
| [C3] `can_start_new_run` + `register_run` 二段では cap 保証不可 (lost update / TOCTOU) | `reserve_run_slot(run_id)` で fcntl file lock 付き原子的 reservation に統合、 二段廃止 |
| [C4] `epoch_{end}_p{epoch_index}` deterministic 性弱い (anchor 変動で別 ID) | canonical `(start, end)` 両方を encode する `epoch_{start_yyyymmdd}_{end_yyyymmdd}` に変更、 epoch_index は state metadata 化 |
| [C5] state 破損時 warning + 新規初期化は危険 | fail-closed (`EpochStateCorruptError` raise)、 reset は明示 `--reset-epoch-state` CLI flag のみ許可 |
| [C6] anchor_date=cfg.dataset.end default 不適切 | `anchor_origin` を state file に固定保存 + compatibility fingerprint で照合、 不一致なら abort |
| [W7] file lock を out of scope に落とすのは不適切 | 本 TODO に含める (correctness の話で改善ではない) |
| [W8] state schema に compatibility fingerprint なし | `instrument/window_length_weeks/stride_days/max_runs_per_epoch/anchor_origin` を state fingerprint として保存 |
| [W9] state_path CWD 依存 | `repo_root` を引数に取る、 `repo_root / .cache/alpha_factory/epoch_state.json` で解決 |
| [W10] 24m 化のメモリ実測 gate | T059 approval 条件に「24m 有効化は別判断、 RSS 実測必須」 を明記 |
| [Suggestion] 28日固定 vs 月次相当 | 「28 日固定」 と表現、 「月次相当」 削除 |
| [Suggestion] run status (started/completed/failed) 永続化 | state file の `run_ids_in_current_epoch` を dict list 化 (`run_id`, `status`, `reserved_at`) |
| [Suggestion] 効果量主張下方修正 | 「epoch スコープの正当化」 「再利用範囲を構造的に制限」 に文言下げ |
