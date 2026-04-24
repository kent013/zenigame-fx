# 詳細設計: calibrate-gate port + Stage A threshold 動的調整

- 作成日時: 2026-04-24 18:55 JST
- 親概念設計: `conceptual-design.md`（rev1, APPROVED 2026-04-24）
- 関連 TODO: T027

## 1. 全体構成

```
.claude/skills/zenigame-fx-calibrate-gate/SKILL.md  ← user-facing wrapper
            │ 呼び出し
            v
scripts/alpha_factory/calibrate_gate.py            ← CLI entry
            │ import
            v
src/alpha_factory/calibrate_gate.py                ← pure logic (testable)
            │
            ├─ aggregator: pass_rate / fitness_pen pool 集計 (§3)
            ├─ controller: quantile-snap + hysteresis + delta clamp (§4)
            ├─ yaml_io: ruamel.yaml round-trip + atomic write (§5)
            └─ models: dataclass (CalibrateInput / Decision / Outcome)
```

**設計判断**: pure logic を `src/alpha_factory/calibrate_gate.py` に出し、
`scripts/alpha_factory/calibrate_gate.py` は CLI 配線のみ。これにより
`tests/scripts/test_calibrate_gate.py` ではなく `tests/alpha_factory/test_calibrate_gate.py`
で大半をテストする（pure function を直接テスト）。CLI は smoke test のみ。

## 2. モジュール責務

### 2.1 `src/alpha_factory/calibrate_gate.py` (pure logic)

公開 API:

```python
@dataclass(frozen=True)
class CalibrateConfig:
    enabled: bool
    aggregation_mode: Literal["last_k_generations", "all_generations", "generation_weighted_mean"]
    aggregation_window: int
    pass_rate_tolerance_abs: float
    threshold_delta_abs_max: float
    threshold_floor: float
    threshold_ceiling: float
    min_sample_size: int
    eps_var: float
    target_pass_rate: float       # SSOT: stage_gate.stage_a.target_pass_rate
    prev_threshold: float         # SSOT: stage_gate.stage_a.threshold


@dataclass(frozen=True)
class AggregatedSample:
    n_rows_total: int
    n_rows_used: int
    pass_count_used: int
    actual_pass_rate: float
    fitness_pen_pool: tuple[float, ...]   # 集計後の fitness_pen 列（quantile 用）
    mode: str
    window: int


@dataclass(frozen=True)
class MonitoringMetrics:
    """変更には使わないが、ログ・後段判断に残す従属監視指標。"""
    stage_b_pass_count: int
    stage_c_pass_count: int
    best_sharpe: float | None
    best_total_pnl: float | None
    best_max_drawdown_pct: float | None
    best_trade_count: int | None
    live_criteria_gap: dict[str, float]   # キー: sharpe / total_pnl / max_dd / trade_count_min / trade_count_max


@dataclass(frozen=True)
class Decision:
    decision: Literal[
        "in_band", "tighten", "loosen",
        "skip_disabled", "skip_no_archive", "skip_sample_size",
        "skip_zero_variance", "skip_schema_mismatch",
    ]
    new_threshold: float
    delta: float
    q_target: float | None
    var_fitness_pen: float | None
    raw_target_threshold: float | None    # clamp 前
    clamped_by_delta: bool
    clamped_by_floor_or_ceiling: bool
    effective_sample_size: int            # n_rows_used (C7 監査支援、Codex review 推奨)


def aggregate_sample(
    rows: Iterable[Mapping[str, object]],
    *,
    mode: str,
    window: int,
) -> AggregatedSample: ...


def compute_monitoring(
    rows: Iterable[Mapping[str, object]],
    *,
    live_criteria: Mapping[str, float],
) -> MonitoringMetrics: ...


def decide(
    sample: AggregatedSample,
    config: CalibrateConfig,
) -> Decision: ...
```

`aggregate_sample` の動作 (§3):

- `last_k_generations`: `max(generation) - window + 1` 以降の行のみ使用
- `all_generations`: 全行
- `generation_weighted_mean`: 各 generation の pass rate を計算 →
  generation_index に対する **線形重み** `w_g = (g - g_min + 1)`
  で加重平均。`fitness_pen_pool` は **全世代を同範囲で採用**
  （pass_rate と fitness_pen 集計範囲を一致させる integrity 制約。詳細 §3.3）

`decide` の動作:

1. `enabled=False` → `Decision("skip_disabled", prev, 0, None, None, None, False, False)`
2. `n_rows_used < min_sample_size` → `skip_sample_size`
3. `pass_rate ∈ [target-tol, target+tol]` → `in_band`, threshold 不変
4. `var(fitness_pen_pool) <= eps_var` → `skip_zero_variance`
5. それ以外 → `q_target = quantile_p(fitness_pen_pool, 1 - target)`,
   delta clamp + floor/ceiling clamp 適用 (`tighten` / `loosen`)

`quantile_p`: `numpy.quantile` ではなく **`statistics.quantiles(method="inclusive")` 相当**
を `numpy.quantile(method="linear")` で実装（NaN 排除済み）。

### 2.2 `scripts/alpha_factory/calibrate_gate.py` (CLI)

責務:
- argparse (`--run-id` / `--config-path` / `--dry-run` / `--archive-dir`)
- run_id 解決（`--run-id` 指定 / 最新 Parquet 自動検出）
- archive Parquet 読み込み (pyarrow → list of dict)
- 0 件 / schema mismatch のガード
- yaml 読み込み (ruamel.yaml round-trip)
- `CalibrateConfig` 構築
- `aggregate_sample` → `compute_monitoring` → `decide` 呼び出し
- 構造化 JSONL ログ出力 (`structlog`)
- 表形式の human-readable 報告（stdout）
- `--dry-run=False` かつ `decision in {tighten, loosen}` のみ yaml 書換 (§5)
- exit code mapping

最新 Parquet 検出:

```python
parquet_files = sorted(
    archive_dir.glob("genomes_run_*.parquet"),
    key=lambda p: p.stat().st_mtime,
    reverse=True,
)
```

`--run-id RUN_ID` 指定時は `archive_dir / f"genomes_{run_id}.parquet"` を直接参照。

### 2.3 `.claude/skills/zenigame-fx-calibrate-gate/SKILL.md`

frontmatter:

```yaml
---
name: zenigame-fx-calibrate-gate
description: 前 Run の archive Parquet から Stage A 実 pass rate を集計し、stage_gate.stage_a.threshold を deterministic に動的調整する
argument-hint: "[run_id] [--dry-run]"
---
```

手順（zenigame 版を踏襲しつつ deterministic 化）:

1. `run_id` 引数解決（省略時は最新検出）
2. `uv run python scripts/alpha_factory/calibrate_gate.py [--run-id ...] [--dry-run]`
3. exit code とログから decision 抽出
4. 表形式で報告（前 threshold / 新 threshold / actual / target / decision / 理由）

## 3. aggregation 詳細

### 3.1 last_k_generations（既定）

```python
generations = sorted({r["generation"] for r in rows})
g_max = max(generations)
threshold_g = g_max - window + 1
used = [r for r in rows if r["generation"] >= threshold_g]
n_rows_used = len(used)
pass_count_used = sum(1 for r in used if r["stage_a_pass"])
actual_pass_rate = pass_count_used / n_rows_used if n_rows_used > 0 else 0.0
fitness_pen_pool = tuple(float(r["fitness_pen"]) for r in used if r["fitness_pen"] is not None)
```

### 3.2 all_generations

```python
used = list(rows)
# 同様の計算
```

### 3.3 generation_weighted_mean

**集計範囲統一の制約**: pass_rate 集計と `fitness_pen_pool` は **同一の generation 集合** を使う。
本 mode では「重み付き平均で pass_rate を出すが、その評価範囲は **全世代**」とし、
`fitness_pen_pool` も **全世代** を採用する（last_k と混在させない）。

```python
gen_to_rows: dict[int, list[Mapping]] = defaultdict(list)
for r in rows:
    gen_to_rows[r["generation"]].append(r)
gens = sorted(gen_to_rows.keys())
g_min = gens[0]
weights = {g: (g - g_min + 1) for g in gens}      # 線形重み
total_w = sum(weights.values())
weighted_pass_rate = sum(
    weights[g] * (sum(1 for r in gen_to_rows[g] if r["stage_a_pass"]) / max(len(gen_to_rows[g]), 1))
    for g in gens
) / total_w if total_w > 0 else 0.0

# fitness_pen_pool は **全世代** を使用（pass_rate と同じ generation 集合 = 全世代）
fitness_pen_pool = tuple(float(r["fitness_pen"]) for r in rows if r["fitness_pen"] is not None)

# n_rows_used / pass_count_used の解釈 (informational のみ; decision には weighted_pass_rate を使う):
#   n_rows_used = len(rows)  # 全行
#   pass_count_used = round(weighted_pass_rate * n_rows_used)  # 重み付き換算した「実効通過数」
```

**重み式の明示** (Codex round 2 の補足):
- 線形重み `w_g = g - g_min + 1`
- `g_min = 0` のとき `w_0 = 1, w_1 = 2, ..., w_max = max+1`
- 後半世代を重く（survivor bias を活用）

**3 mode の集計範囲整合表**:

| mode | pass_rate の集計範囲 | fitness_pen_pool の集計範囲 |
|------|---------------------|--------------------------|
| `last_k_generations` | 終盤 K 世代 | 同左 |
| `all_generations` | 全世代 | 同左 |
| `generation_weighted_mean` | 全世代（重み付き） | 全世代（重みなし） |

## 4. controller 詳細

### 4.1 quantile-snap

```python
import numpy as np
def quantile_p(pool: tuple[float, ...], p: float) -> float:
    return float(np.quantile(np.array(pool, dtype=np.float64), p, method="linear"))

q_target = quantile_p(fitness_pen_pool, 1 - target)
```

- `np.quantile` の `method="linear"` (デフォルト) を採用（pandas / scipy 互換）
- `pool` 空 / 全 NaN は呼び出し前にガード

### 4.2 delta clamp

```python
delta_raw = q_target - prev_threshold
delta = max(-max_delta, min(max_delta, delta_raw))
clamped_by_delta = (delta != delta_raw)
new_after_delta = prev_threshold + delta
```

### 4.3 floor/ceiling clamp

```python
new_clamped = max(threshold_floor, min(threshold_ceiling, new_after_delta))
clamped_by_floor_or_ceiling = (new_clamped != new_after_delta)
new_threshold = round(new_clamped, 4)
```

### 4.4 decision string 確定

```python
if abs(actual - target) <= tol:
    decision_str = "in_band"
elif actual > target + tol:
    decision_str = "tighten"
else:
    decision_str = "loosen"
```

## 4.5 schema check と null/NaN 方針 (Codex review #2 対応)

### 4.5.1 必須カラムと null 許容

archive Parquet 読み込み直後に **schema mismatch ガード** を実施する。
許容しない null:

| カラム | null 許容 | 違反時の挙動 |
|-------|---------|------------|
| `generation` | NO (schema = int32 not null) | exit 8 + ERROR |
| `stage_a_pass` | NO (schema = bool not null) | exit 8 + ERROR |
| `fitness_pen` | NO (schema = float64 not null) | exit 8 + ERROR |
| `stage_b_pass` / `stage_c_pass` | NO | exit 8 + ERROR |
| `sharpe` / `sortino` / `calmar` | YES | None として monitoring から除外 |
| `dsr` / `bootstrap_ci_*` | YES | monitoring 範囲のみ参照 |

ガード実装:

```python
REQUIRED_NON_NULL_COLS = ("generation", "stage_a_pass", "fitness_pen", "stage_b_pass", "stage_c_pass")
REQUIRED_COLS = REQUIRED_NON_NULL_COLS + ("sharpe", "total_pnl", "max_drawdown_pct", "trade_count")

def validate_schema(table: pa.Table) -> None:
    missing = [c for c in REQUIRED_COLS if c not in table.schema.names]
    if missing:
        raise SchemaMismatchError(f"missing columns: {missing}")
    for col in REQUIRED_NON_NULL_COLS:
        n_null = table[col].null_count
        if n_null > 0:
            raise SchemaMismatchError(f"unexpected nulls in {col}: {n_null}")
    # NaN check (float のみ)
    for col in ("fitness_pen",):
        arr = table[col].to_numpy(zero_copy_only=False)
        if np.isnan(arr).any():
            raise SchemaMismatchError(f"NaN found in {col}")
```

呼び出し側で `SchemaMismatchError` を catch → exit 8。

### 4.5.2 設定値バリデーション

`CalibrateConfig` 構築時に以下を assert:

```python
assert 0.0 <= target_pass_rate <= 1.0
assert 0.0 <= pass_rate_tolerance_abs <= 0.5
assert threshold_delta_abs_max > 0
assert threshold_floor <= threshold_ceiling
assert aggregation_window >= 1
assert min_sample_size >= 1
assert eps_var > 0
```

違反時は `ValueError` → exit 5。

### 4.5.3 quantile 引数の境界

`p = 1 - target` は target ∈ [0, 1] から自動的に [0, 1] に収まる。
`np.quantile` は p=0.0 / p=1.0 を許容するので追加チェック不要。

## 5. yaml round-trip atomic write

### 5.1 ライブラリ選定

`ruamel.yaml` を使用。理由:
- コメント・順序・anchor を保持
- round-trip safe
- 既存依存 (pyproject.toml 確認後、未追加なら `uv add ruamel.yaml`)

`PyYAML` は順序保持しないため不採用。

### 5.2 atomic write 手順 (一意 tmp 名 + 同時実行排他)

**single-writer 前提**: improve-cycle Phase 2.5 が唯一の calibrate 呼び出し元。
他 skill が並行で yaml を書く想定はない。ただし誤実行・並行 cron 等の事故を
防ぐため、**一意 tmp 名 + advisory lock** で防御する。

```python
import os
import tempfile
import fcntl
from contextlib import contextmanager

@contextmanager
def yaml_writer_lock(yaml_path: Path):
    """advisory file lock (POSIX flock)。Linux/macOS で動作。Windows は対象外。"""
    lock_path = yaml_path.with_suffix(yaml_path.suffix + ".lock")
    with lock_path.open("w") as lock_fd:
        fcntl.flock(lock_fd.fileno(), fcntl.LOCK_EX)  # blocking
        try:
            yield
        finally:
            fcntl.flock(lock_fd.fileno(), fcntl.LOCK_UN)


def update_threshold_atomic(
    yaml_path: Path,
    new_threshold: float,
) -> None:
    with yaml_writer_lock(yaml_path):
        yaml = YAML()
        yaml.preserve_quotes = True
        with yaml_path.open("r", encoding="utf-8") as f:
            data = yaml.load(f)

        # 階層更新
        data["stage_gate"]["stage_a"]["threshold"] = float(new_threshold)

        # 一意 tmp 名 (PID + 乱数) で同時実行衝突を防ぐ
        tmp_fd, tmp_str = tempfile.mkstemp(
            prefix=f"{yaml_path.name}.",
            suffix=".tmp",
            dir=str(yaml_path.parent),
        )
        tmp_path = Path(tmp_str)
        try:
            with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
                yaml.dump(data, f)
            # 構造再検証
            with tmp_path.open("r", encoding="utf-8") as f:
                verify = yaml.load(f)
            v = verify["stage_gate"]["stage_a"]["threshold"]
            if not isinstance(v, float) or abs(v - new_threshold) > 1e-9:
                raise ValueError(f"verify failed: written={v} expected={new_threshold}")
            os.replace(tmp_path, yaml_path)  # POSIX atomic rename
        except Exception:
            if tmp_path.exists():
                tmp_path.unlink(missing_ok=True)
            raise
```

中断シナリオ:
- write 中断 → 一意 tmp が残るが original 不変、`*.tmp` は git ignore で対応
- replace 中断 → POSIX rename は atomic、original or new どちらか
- 並行 calibrate 起動 → flock で blocking、second は first 完了後に続行
- lock file の残骸 → flock は fd close 時に自動解除、stale lock にならない

### 5.2.1 git ignore 追記

`.gitignore` に以下を追加:

```
config/alpha_factory/*.tmp
config/alpha_factory/*.lock
```

### 5.3 dry-run

`--dry-run=True` の場合、`update_threshold_atomic` を呼ばず、stdout に
「次回更新内容のプレビュー」のみ表示する。

## 6. monitoring 集計（§5.3 ログ用）

```python
def compute_monitoring(rows, *, live_criteria):
    stage_b_pass = sum(1 for r in rows if r["stage_b_pass"])
    stage_c_pass = sum(1 for r in rows if r["stage_c_pass"])

    valid_sharpes = [r["sharpe"] for r in rows if r["sharpe"] is not None]
    best_sharpe = max(valid_sharpes) if valid_sharpes else None
    best_total_pnl = max((r["total_pnl"] for r in rows), default=None)
    best_max_dd = min((r["max_drawdown_pct"] for r in rows), default=None)
    best_tc = max((r["trade_count"] for r in rows), default=None)

    # gap: 正なら未達、0 なら達成、負なら超過 (sharpe / total_pnl / trade_count_min)
    # max_dd: best_max_dd > live_criteria.max_drawdown_max なら gap > 0
    gap = {
        "sharpe": max(0.0, live_criteria["sharpe_min"] - (best_sharpe or 0.0)),
        "total_pnl": max(0.0, live_criteria["total_pnl_min"] - (best_total_pnl or 0.0)),
        "max_dd": max(0.0, (best_max_dd or 0.0) / 100.0 - live_criteria["max_drawdown_max"]),
        "trade_count_min": max(0.0, live_criteria["trade_count_min"] - (best_tc or 0)),
        "trade_count_max": max(0.0, (best_tc or 0) - live_criteria["trade_count_max"]),
    }
    return MonitoringMetrics(...)
```

**符号規約** (Codex round 2 補足): すべて **「未達量を非負で表現」**。
0 = 達成、正 = 未達。これにより人間 / 後段 LLM が gap の意味を misread しない。

**因果解釈禁止注記** (C3 collider bias 対応): monitoring 指標 (stage_b_pass_count /
stage_c_pass_count / live_criteria_gap) は **threshold 変更の決定には使わない**。
ログ・後段判断の **観察記録** であり、threshold と Stage B/C 通過数の相関を
因果として読まないこと（Stage A pass を中間 collider とする条件付け bias の余地）。

## 7. CLI 出力フォーマット

### 7.1 JSONL ログ (stderr)

```jsonl
{"event":"calibrate_gate.input", ...}
{"event":"calibrate_gate.monitoring", ...}
{"event":"calibrate_gate.decision", ...}
{"event":"calibrate_gate.applied", ...}    # 書換時のみ
```

### 7.2 human-readable 報告 (stdout)

```
## Stage A Gate Calibration

| 項目 | 値 |
|------|----|
| Run ID | run_20260423_195917 |
| Aggregation | last_k_generations / window=5 |
| 集計対象行 | 12 / 12 (全行) |
| Stage A pass | 0 |
| 実 pass rate | 0.000 |
| Target pass rate | 0.150 ± 0.050 |
| 前 threshold | 0.0 |
| 提案 q_target | -55.42 |
| delta (clamp前/後) | -55.42 / -0.50 (clamp適用) |
| **新 threshold** | **-0.50** |
| 決定 | loosen |
| dry-run | False |

### Monitoring (informational)
- Stage B pass: 0
- Stage C pass: 0
- best sharpe: -47.0
- live_criteria gap: sharpe=48.0, total_pnl=50000.0, max_dd=0.0, trade_count_min=0, trade_count_max=0
```

## 8. エラー処理 / exit code 詳細

| 状況 | exit | stderr |
|-----|------|--------|
| 成功 (in_band / tighten / loosen) | 0 | JSONL のみ |
| invalid arg | 2 | argparse error |
| no archive (auto-detect も指定 run-id も無し) | 3 | "no parquet found in {dir}" / "run-id specified but file not found: {path}" |
| disabled | 4 | "calibrate.enabled=false, skipping" |
| io error (yaml read/write) | 5 | exception trace |
| sample size insufficient | 6 | "n_rows_used={n} < min_sample_size={k}" |
| zero variance | 7 | "var(fitness_pen)={v} <= eps_var={e}" |
| schema mismatch | 8 | "missing/extra columns: ... / unexpected nulls in {col}" |

## 9. テスト計画

### 9.1 `tests/alpha_factory/test_calibrate_gate.py` (pure logic, 主力)

- `test_aggregate_last_k_generations_uses_only_late_gens`
- `test_aggregate_all_generations_uses_all`
- `test_aggregate_generation_weighted_mean_weights_late_more`
- `test_decide_in_band_returns_no_change`
- `test_decide_tighten_when_pass_rate_above_target_plus_tol`
- `test_decide_loosen_when_pass_rate_below_target_minus_tol`
- `test_decide_clamps_delta`
- `test_decide_clamps_floor_ceiling`
- `test_decide_skips_when_disabled`
- `test_decide_skips_when_sample_size_below_min`
- `test_decide_skips_on_zero_variance`
- `test_compute_monitoring_gap_signs_are_non_negative`

### 9.2 `tests/scripts/test_calibrate_gate_cli.py` (CLI smoke + IO)

- `test_cli_dry_run_does_not_modify_yaml` (SHA256 check)
- `test_cli_writes_yaml_atomically_when_decision_is_loosen`
- `test_cli_exits_3_when_no_archive`
- `test_cli_exits_3_when_run_id_specified_but_missing`
- `test_cli_exits_4_when_disabled`
- `test_cli_exits_8_when_schema_has_unexpected_nulls`
- `test_cli_uses_latest_parquet_when_run_id_omitted`
- `test_cli_writes_with_unique_tmp_name_concurrent` (簡易: tmp glob で衝突しないこと確認)
- `test_cli_generation_weighted_mean_uses_all_generations` (integrity)

### 9.3 fixtures

```python
@pytest.fixture
def archive_rows_factory():
    """generation × pass の任意分布を作る。"""
    def _make(specs: list[tuple[int, list[bool], list[float]]]) -> list[dict]:
        ...
    return _make
```

```python
@pytest.fixture
def yaml_with_calibrate(tmp_path):
    """default.yaml の最小コピーを作る（calibrate セクション付き）。"""
    ...
```

## 10. ruamel.yaml 依存追加手順

`pyproject.toml` の `[project.dependencies]` に未追加なら追加:

```bash
uv add ruamel.yaml
uv sync
```

import 失敗時のフォールバック (PyYAML 限定モード) は **本 TODO では実装しない**
（テストで ruamel.yaml 必須を assert）。

### 10.1 lockfile / 既存テスト影響の検証手順

1. `uv add ruamel.yaml` 実行 → `uv.lock` の diff を確認
2. `uv sync` → 仮想環境再構築
3. `uv run pytest tests/ -v --tb=short -x` 全 834 テスト実行
4. `uv run mypy src/ scripts/` で型エラー有無確認
5. 既存テストが 1 件でも fail したら `uv remove ruamel.yaml` で revert + 別案検討

ruamel.yaml は単純な round-trip ライブラリで、他依存と衝突しにくい。
影響は新規 import のみと想定されるが、上記手順で確認する。

## 10.2 `calibrate.*` 転記経路チェック表 (Codex review #4 対応)

新規 yaml キー `stage_gate.stage_a.calibrate.*` の **4 段接続経路**:

| キー | 1. yaml 定義 | 2. loader | 3. consumer | 4. ログ出力 |
|------|------------|-----------|-------------|-----------|
| `enabled` | §5.1 | `scripts/alpha_factory/calibrate_gate.py::load_calibrate_config` | `decide` 内 (skip_disabled) | `calibrate_gate.decision.decision` |
| `aggregation_mode` | §5.1 | 同上 | `aggregate_sample` | `calibrate_gate.input.aggregation_mode` |
| `aggregation_window` | §5.1 | 同上 | `aggregate_sample` | `calibrate_gate.input.aggregation_window` |
| `pass_rate_tolerance_abs` | §5.1 | 同上 | `decide` (in_band 判定) | `calibrate_gate.input.tol` |
| `threshold_delta_abs_max` | §5.1 | 同上 | `decide` (delta clamp) | `calibrate_gate.decision.delta` |
| `threshold_floor` / `threshold_ceiling` | §5.1 | 同上 | `decide` (floor/ceiling clamp) | `calibrate_gate.decision.new_threshold` |
| `min_sample_size` | §5.1 | 同上 | `decide` (skip_sample_size) | `calibrate_gate.decision` |
| `eps_var` | §5.1 | 同上 | `decide` (skip_zero_variance) | `calibrate_gate.decision` |

**`genome.meta` への注入は不要**:
- 理由: calibrate-gate は **GA Run 終了後のオフライン処理** で、GA 実行中
  (genome 生成・mutation・crossover) では calibrate 設定を参照しない。
  Stage A 評価の閾値は `stage_gate.stage_a.threshold` を参照するが、これは
  既存の `StageGateConfig` 経路を使う（calibrate 設定とは独立）。
- 書込み対象は `stage_gate.stage_a.threshold` のみで、これは既存 GA loader
  経路で次 Run 起動時に自動的に reload される。

**転記漏れ防止 import-time guard** (任意推奨):

```python
# src/alpha_factory/calibrate_gate.py
_REQUIRED_CALIBRATE_KEYS = frozenset({
    "enabled", "aggregation_mode", "aggregation_window",
    "pass_rate_tolerance_abs", "threshold_delta_abs_max",
    "threshold_floor", "threshold_ceiling",
    "min_sample_size", "eps_var",
})


def load_calibrate_config(yaml_data: Mapping[str, Any]) -> CalibrateConfig:
    section = yaml_data["stage_gate"]["stage_a"].get("calibrate", {})
    missing = _REQUIRED_CALIBRATE_KEYS - section.keys()
    if missing:
        raise ConfigError(f"missing calibrate keys: {sorted(missing)}")
    extra = section.keys() - _REQUIRED_CALIBRATE_KEYS
    if extra:
        # extra キーは WARN（typo 検出のヒント）。raise はしない（前方互換）
        logger.warning("calibrate.unknown_keys", keys=sorted(extra))
    ...
```

## 11. improve-cycle 接続

`SKILL.md` Phase 2.5 セクションを以下に書換:

```markdown
├─ Phase 2.5: /zenigame-fx-calibrate-gate {run_id}
│   → archive 由来 Stage A pass rate から stage_gate.stage_a.threshold を deterministic に更新
│   （`stage_gate.stage_a.calibrate.enabled=false` で無効化可）
```

`<!-- TODO(calibrate-gate-port) -->` コメントは削除。

## 12. ロールアウト・smoke test (2 段)

### 12.1 Stage 1: skip 経路の smoke (実 archive、production config)

```bash
uv run python scripts/alpha_factory/calibrate_gate.py \
  --run-id run_20260423_195917 --dry-run
```

期待:
- n_rows_used = 12 (last_k=5 だが generation は 0 だけなので全行)
- actual = 0.0 (全 fail)
- decision = `skip_sample_size` (n=12 < min_sample_size=30) → exit 6
- yaml 不変、JSONL に skip ログのみ

→ **目的**: 実 archive を読んで schema check / aggregation / skip 判定までの
経路が走ることを確認する。

### 12.2 Stage 2: 成功経路の smoke (合成 fixture, min_sample_size 緩和)

```bash
# 合成 archive (n=100, pass=10) を tmp に作る
uv run python -m tests.fixtures.calibrate_gate_smoke_fixture \
  --out /tmp/genomes_smoke.parquet --n 100 --pass-count 10

# 緩和 config (min_sample_size=10) を tmp に作る
cp config/alpha_factory/default.yaml /tmp/calibrate_smoke.yaml
sed -i.bak 's/min_sample_size: 30/min_sample_size: 10/' /tmp/calibrate_smoke.yaml

# 実行 (dry-run)
uv run python scripts/alpha_factory/calibrate_gate.py \
  --run-id smoke --archive-dir /tmp \
  --config-path /tmp/calibrate_smoke.yaml \
  --dry-run
```

期待:
- n_rows_used = 100, pass = 10, actual = 0.10
- target = 0.15, tol = 0.05 → actual ∈ [0.10, 0.20] → `in_band` → 不変
- exit 0

または `pass-count=2`（actual=0.02 < 0.10）で `loosen` パス確認。

→ **目的**: controller の成功経路（quantile-snap / clamp / yaml dry-run preview）
が動くことを確認する。

**Stage 1 と 2 で同時に「skip 経路」「成功経路」を共に検証** することで、
smoke の C8 INCONCLUSIVE を解消する。

### 12.2 段階的有効化

- Run 3 完了直後: `calibrate.enabled=false` でリリース → ログだけ確認
- Run 4 で `enabled=true` に切替 → threshold 動的更新を本格運用

**本 TODO のリリース時は `enabled=true` で投入**。disabled は緊急時の fallback。

## 13. 実装順序 (worktree 内)

1. `uv add ruamel.yaml`
2. `src/alpha_factory/calibrate_gate.py` 実装 + tests
3. `scripts/alpha_factory/calibrate_gate.py` 実装 + CLI tests
4. `config/alpha_factory/default.yaml` に `calibrate` セクション追加
5. `.claude/skills/zenigame-fx-calibrate-gate/SKILL.md` 新設
6. `docs/alpha_factory/concepts/calibrate-gate.md` 整備
7. `docs/alpha_factory/stage-gates.md` に節追加
8. `improve-cycle` SKILL.md Phase 2.5 hook 接続表記更新
9. mypy / ruff / pytest
10. cycle 21 run-3 で smoke test (`--dry-run`)
11. Codex impl-review

## 14. リスク再確認

- yaml 書換失敗 → atomic write で original 保護、5 種類の exit code で診断可能
- min_sample_size=30 が厳しすぎ → 別 TODO で empirical 化（5 Run 蓄積後）
- `last_k_generations` で全世代が同一 (run_3 のように generation=0 のみ)
  になる場合は `len(used) == n_rows_total` になるだけで logic は壊れない
