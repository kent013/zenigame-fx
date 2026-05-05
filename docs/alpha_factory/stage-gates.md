# Stage Gates

## 目的

Stage A / B / C ゲートの構造・期間・通過条件・ペナルティ運用を一箇所に集約する。実装詳細は `concepts/stage-gate-implementation.md` および後続 TODO で扱う。

## スコープ

- 各 Stage の役割と通過条件の構造
- Stage B での Walk-Forward (WF) パラメータ構造
- 期間延長禁止（禁止事項 #1）の構造的明示
- live_criteria への接続点

数値（窓長・通過率・閾値）は SSOT 参照。期間延長は強い根拠なしに行わない（禁止事項 #1）。

**backtest 前提 (T009 以降)**: Stage A / B / C の全 評価フローは `src/backtest/engine.py`
の Clause DslStrategy + `BacktestConfig` (max_spread_bps / holding_cost_per_day_bps /
session_close_utc_hours / bar_minutes) を前提とする。spread フィルタ / holding cost /
session close は engine 不変条件として fitness に反映される。
詳細は [clause-architecture.md](clause-architecture.md#backtest-統合-t009-完了時点) を参照。

## 用語リンク

本ドキュメントで使用する用語: [Stage A](terminology.md#stage-a), [Stage B](terminology.md#stage-b), [Stage C](terminology.md#stage-c), [Walk-Forward](terminology.md#walk-forward), [IS / OOS](terminology.md#is-oos), [DSR](terminology.md#dsr), [(ii-lite)](terminology.md#ii-lite), [TC](terminology.md#tc), [StageResult](terminology.md#stage-result), [WF Fold](terminology.md#wf-fold), [Embargo](terminology.md#embargo), [Reason Code](terminology.md#reason-code), [CrossPairResult](terminology.md#cross-pair-result)

**重要 (T042)**: `live_criteria.sharpe_min` は **annualized Sharpe** スケール、Stage A/B threshold は **trade-level Sharpe** スケール。Stage C 内部で `_annualize_trade_sharpe` により換算してから比較する。詳細: [sharpe-rescale.md](sharpe-rescale.md)

## 主要定義

### Stage A — Fast Screen

- 短期窓で低コストにスクリーニング
- 複雑度ペナルティ α_A を fitness から控除
- 通過率目標を持ち、過剰通過 / 過少通過を `calibrate-gate` で調整
- 失敗個体は Stage B に進めない

### Stage B — Full IS + Walk-Forward OOS

- 完全 IS 期間でのフィット + WF-OOS 評価の二段
- WF パラメータ構造: `train_days / test_days / step_days / embargo_days`
- 通過条件は **複合 AND**:
  1. median OOS Sharpe ≥ 閾値
  2. 正 fold 比率 ≥ 閾値
  3. DSR ≥ 閾値（Phase 2 では monitor、Phase 3+ で hard）

#### Stage A/B disjoint 契約 (T087)

`bars_stage_b` は dataset から Stage A 期間（末尾 `stage_a_window_days` 営業日相当）を**時系列上 disjoint に除外**したもの。Stage B fold + IS monitor は `[dataset.start, dataset.end - stage_a_window)`、Stage A は `[dataset.end - stage_a_window, dataset.end)`、Stage C holdout は `[dataset.end, dataset.end + holdout_days)`。

これにより Stage A IS（GA fitness の評価対象）と Stage B fold OOS（gate 検証対象）は時系列上一切重ならず、選択汚染（IS と OOS の重複）を構造的に排除する。

`Stage Partition Integrity Guard`（[stage_partition_guard.py](../../src/alpha_factory/stage_partition_guard.py)）が起動時に以下を fail-closed で検証:

- **B-0 入力健全性**: 各 stage の non_empty / UTC tz / not null / monotonic / unique-within-stage
- **B-1 partition 整合性**:
  - 境界条件 1-3: `max(stage_b) < min(stage_a) < min(holdout)` 等の chronological order
  - 集合条件 4-6: `set(stage_a) ∩ set(stage_b) == ∅` 等の exact timestamp disjoint

違反時は `StagePartitionInputError` (B-0) / `StagePartitionLeakError` (B-1) が raise され、escape hatch なしで起動停止する。

`stage_b_statistical_inconclusive`（`n_fold_effective < 3`）は summary 経由で伝搬し、archive consumer は archive 列の `n_fold_effective` から `is_stage_b_inconclusive()` で同等判定可能。archive parquet schema metadata に `stage_gate_version` および `bars_stage_b_excludes_stage_a=true` が記録される。

### Stage C — Live Criteria + Stress + (ii-lite)

- holdout 期間で live_criteria 全条件を AND 評価
- spread × N stress test（コスト悪化耐性）
- trade_count が `[trade_count_min, trade_count_max]` 範囲内
- (ii-lite) 評価（Phase 2 shadow / Phase 6 hard）

### 期間延長禁止

A / B / C いずれの評価期間も「強い根拠なしに延長しない」。延長を提案する場合は概念設計に**反証を含む議論**を要する（禁止事項 #1）。

## 実装 (T014 完了時点)

`src/alpha_factory/stage_gate.py` および `src/alpha_factory/walk_forward.py` に
pure function として実装。GA runner / archive との配線は別 TODO（本 TODO の
責務外）。

### 公開関数 signature

```python
def evaluate_stage_a(
    genome: Genome,
    bars_60d: list[PriceBar],
    meta: InstrumentMeta,
    backtest_config: BacktestConfig,
    primitive_evaluator: PrimitiveEvaluator,
    stage_config: StageGateConfig,
) -> StageResult: ...

def evaluate_stage_b(
    genome: Genome,
    bars_stage_b: list[PriceBar],  # T087: bars_18m から rename。 Stage A 期間を除外した bars
    meta: InstrumentMeta,
    backtest_config: BacktestConfig,
    primitive_evaluator: PrimitiveEvaluator,
    stage_config: StageGateConfig,
) -> StageResult: ...

def evaluate_stage_c(
    genome: Genome,
    bars_holdout: list[PriceBar],
    meta: InstrumentMeta,
    backtest_config: BacktestConfig,
    primitive_evaluator: PrimitiveEvaluator,
    stage_config: StageGateConfig,
    *,
    cross_pair_evaluator: CrossPairEvaluator | None = None,
    cross_pair_inputs: Mapping[str, object] | None = None,
) -> StageResult: ...

def make_wf_folds(
    bars: list[PriceBar],
    train_days: int,
    test_days: int,
    step_days: int,
    embargo_days: int,
) -> list[tuple[list[PriceBar], list[PriceBar]]]: ...
```

### StageResult 構造

`StageResult(stage, passed, metrics, reason_codes)` の frozen dataclass。
`metrics` は共通 envelope (`stage` / `genome_name` / `n_bars` /
`wall_time_seconds` / `payload`) を必ず持つ。`payload` 内が Stage 固有。
`reason_codes` は `tuple[str, ...]` で空タプル = 通過、非空 = 失敗。
display 用に `reason_if_failed` property (`";".join(reason_codes)`) を提供。

### Reason Code 語彙 (canonical)

| Stage | Reason Code | 意味 |
|-------|-------------|------|
| A | `system_failure` | backtest / size_norm 計算で例外。payload `fitness_pen` に `SYSTEM_FAILURE_FITNESS=-1e12` (T034) |
| A | `no_exposure` | trade_count < `min_exposure_trade_count` (default 1)。旧 `no_trades` を置き換え。payload `fitness_pen` に `NO_EXPOSURE_FITNESS=-1e9` (T034) |
| A | `metric_unavailable` | sharpe が計算不可 (returns 不足など)。payload `fitness_pen` に `METRIC_UNAVAILABLE_FITNESS=-1e6` (T034) |
| A | `below_threshold` | fitness_pen ≤ stage_a_threshold |

**T034 sentinel 序列** (selection_score tie-break で「無取引優位」を解消):
```
system_failure (-1e12) < no_exposure (-1e9) < metric_unavailable (-1e6) < below_threshold (実値) < 通常
```
calibrate_gate は `STAGE_A_FITNESS_SENTINELS` 集合一致で sentinel を quantile pool から除外する (混入による threshold 不当緩和を防ぐ)。詳細: [stage_gate.py](../../src/alpha_factory/stage_gate.py) / [calibrate_gate.py](../../src/alpha_factory/calibrate_gate.py)。

**`min_exposure_trade_count` 不変条件**: `1 <= min_exposure_trade_count < live_criteria.trade_count_min` (live_criteria 緩和回避、禁止事項 #4 ガード)。`live_criteria.trade_count_min == 0` (緩和テスト用) では validation skip。
| B | `no_folds` | bars が train+embargo+test 未満で fold が出ない |
| B | `insufficient_folds` | fold が 1 のみ (n_fold < 2) |
| B | `median_oos_sharpe<min` | median OOS Sharpe < 閾値 |
| B | `positive_fold_ratio<min` | 正 fold 比率 < 閾値 |
| B | `all_folds_unavailable` | 全 fold で sharpe 計算不可 |
| C | `system_failure` | base backtest で例外 |
| C | `live_criteria.sharpe<min` | sharpe < live_criteria.sharpe_min |
| C | `live_criteria.total_pnl<min` | total_pnl < live_criteria.total_pnl_min |
| C | `live_criteria.max_drawdown>max` | max_drawdown_frac > max_drawdown_max |
| C | `live_criteria.trade_count<min` | trade_count < trade_count_min |
| C | `live_criteria.trade_count>max` | trade_count > trade_count_max |
| C | `intraday_constraint_violation` | 日跨ぎ trade が存在 |
| C | `spread_stress_skipped` | max_spread_bps=None で stress 評価不能 (fail-closed)。**T041 (Phase 0) で `config/alpha_factory/default.yaml::backtest.max_spread_bps=10` を設定し、production パスで本 reason は出ない状態に解消済**。Run 1〜16 で本 reason が常時付与され Stage C pass=0 だった構造的原因。 |
| C | `spread_stress.sharpe<min` | stress 後 sharpe < spread_stress_min_sharpe |
| C | `spread_stress.total_pnl<min` | stress 後 total_pnl < spread_stress_min_total_pnl |
| C | `spread_stress.trade_count<min` | stress 後 trade_count < live_criteria.trade_count_min |

### WF Fold 構造 (`make_wf_folds`)

observed-day index ベースで `(train_bars, test_bars)` tuple のリストを返す。
暦日加算は使わず、実際に観測された UTC date のインデックスで切る（祝日 / 週末 /
休場 gap に robust）。

```
fold k:
  train_start_idx = step_days * k
  train_end_idx_exclusive = train_start_idx + train_days
  test_start_idx = train_end_idx_exclusive + embargo_days
  test_end_idx_exclusive = test_start_idx + test_days
```

embargo 区間の bars は train / test どちらにも含めない（leak 防止、
López de Prado 2018 Ch.7）。`test_end_idx_exclusive > n_unique_dates` で fold
生成停止。`bars` 空 / `train+embargo+test > n_unique_dates` の場合は
ValueError ではなく **空 list** を返す（呼び出し側で `no_folds` reason に変換）。

### Drawdown unit canonicalization

Stage C 内の比較は **fraction (0-1)** に統一。
`BacktestMetrics.max_drawdown_pct` は percent (0-100) のため、Stage C 内で
`/ 100` 換算してから `live_criteria.max_drawdown_max` (fraction) と比較する。
metrics の `max_drawdown_frac` も fraction で出力する。

### Cross-pair (ii-lite) Hook

Phase 2 では `cross_pair_evaluator` 引数を **shadow only** で受ける。
- `cross_pair_evaluator=None` (default) → `payload.cross_pair.skipped=True`
- `cross_pair_evaluator` 指定時は `cross_pair_inputs` (TypedDict
  `CrossPairInputs`: `target_pair` / `pair_bars_map` / `meta_map`) も必須
- 戻り値の `CrossPairResult.passed` は **Phase 2 では Stage C.passed に影響させない**
  （Phase 4 で hard gate 化予定、その際に AND 合成）

## SSOT 参照

| 項目 | 参照キーパス（config/alpha_factory/default.yaml） |
|------|--------------------------------------------------|
| live_criteria.sharpe_min | `live_criteria.sharpe_min` |
| live_criteria.total_pnl_min | `live_criteria.total_pnl_min` |
| live_criteria.max_drawdown_max | `live_criteria.max_drawdown_max` |
| live_criteria.trade_count_min | `live_criteria.trade_count_min` |
| live_criteria.trade_count_max | `live_criteria.trade_count_max` |
| Stage A 窓長 / 通過率目標 | `stage_gate.stage_a.window_days` / `stage_gate.stage_a.target_pass_rate` |
| Stage A α / 閾値 | `stage_gate.stage_a.alpha` / `stage_gate.stage_a.threshold` |
| Stage B 窓 | `stage_gate.stage_b.window_months` |
| Stage B WF パラメータ | `stage_gate.stage_b.wf_train_days/wf_test_days/wf_step_days/wf_embargo_days` |
| Stage B 通過条件 | `stage_gate.stage_b.median_oos_sharpe_min/positive_fold_min/dsr_min` |
| Stage C 窓 / stress 倍率 | `stage_gate.stage_c.holdout_days` / `stage_gate.stage_c.spread_stress_multiplier` |
| Stage C stress 下限 | `stage_gate.stage_c.spread_stress_min_total_pnl/spread_stress_min_sharpe` |

注: `StageGateConfig` (`src/alpha_factory/stage_gate.py`) を yaml から構築する
loader は **GA runner 統合 TODO** で実装予定。現状は dataclass を直接構築する
形でテスト・利用する。

## 関連ドキュメント

- [clause-architecture.md](clause-architecture.md) — composite score / max_clause
- [statistics.md](statistics.md) — DSR / 正 fold 比率の計算
- [cross-pair.md](cross-pair.md) — Stage C 内 (ii-lite)
- [migration-triggers.md](migration-triggers.md) — Stage 通過率の崩壊検知
- [concepts/stage-gate-implementation.md](concepts/stage-gate-implementation.md)
- [terminology.md](terminology.md) — StageResult / WF Fold / Embargo /
  Reason Code / CrossPairResult

## Stage A threshold 動的調整 (T027 calibrate-gate)

`stage_gate.stage_a.threshold` は **calibrate-gate** (T027) により Run 終了後に
自動更新される。実装は `scripts/alpha_factory/calibrate_gate.py` + pure logic
`src/alpha_factory/calibrate_gate.py`。

### 制御則

bounded quantile tracking with hysteresis (dead-band) + delta clamp。

1. `actual = aggregate_pass_rate(rows, mode, window)` (既定 mode=`last_k_generations`, window=5)
2. `actual ∈ [target - tol, target + tol]` → `in_band` (変更なし)
3. それ以外 → `q_target = quantile(fitness_pen_pool, 1 - target)` を仮想 threshold へスナップ
4. 変更幅は `threshold_delta_abs_max` で clamp（暴走防止）
5. 結果は `[threshold_floor, threshold_ceiling]` で clamp

### SSOT

`config/alpha_factory/default.yaml` の `stage_gate.stage_a.calibrate.*`:

| キー | 既定 | 意味 |
|------|------|------|
| `enabled` | `true` | false で全 no-op |
| `aggregation_mode` | `last_k_generations` | `last_k_generations` / `all_generations` / `generation_weighted_mean` |
| `aggregation_window` | 5 | last_k_generations の K |
| `pass_rate_tolerance_abs` | 0.05 | dead-band 半幅 |
| `threshold_delta_abs_max` | 0.5 | 1 Run の変更幅上限 |
| `threshold_floor` / `threshold_ceiling` | -100.0 / 100.0 | 絶対値クランプ |
| `min_sample_size` | 30 | この未満は skip + WARN |
| `eps_var` | 1e-9 | quantile-snap skip 判定 |

### improve-cycle 接続

`improve-cycle` Phase 2.5 (calibrate-gate hook) で実行される。skill wrapper:
`.claude/skills/zenigame-fx-calibrate-gate/SKILL.md`。

詳細: [concepts/calibrate-gate.md](concepts/calibrate-gate.md) /
`devnotes/20260424-1759-port-calibrate-gate/`。

### T054: state file 経由の自動適用 (cross-run contamination guard 付)

`run_ga.py` 起動時、`reports/calibrate-gate/history.jsonl` の最新 record から
effective threshold を自動適用する経路を追加 (T054):

優先順位:
1. CLI override (`--stage-a-threshold X`) があれば最優先 → `source="cli"`
2. history.jsonl の最新適用可能 record → `source="history"`
3. config 値 (yaml load 値) → `source="config"`

cross-run contamination guard (`src/alpha_factory/calibrate_state.py`):
- `calibrate_history_schema_version == 2` (T058 で v2 に bump、 record format 互換)
- `base_config_hash` (適応値除外) 一致 — `compute_base_config_hash` が `stage_a_threshold` を除く全 stage_gate / dataset 値で hash
- `dataset_span` / `instrument` / `stage_gate_version` 一致
- **`dataset_epoch_id` 一致** (T058 追加: epoch-rolling 識別子の AND 結合、 dataset の epoch
  境界をまたいだ contamination を遮断)
- `decision in (tighten, loosen)` のみ適用 (`in_band` / `skip_sample_size` は除外)
- `applied_at` が ISO 8601 形式
- `new_threshold` が isfinite かつ [floor, ceiling] 内

不一致時は **fail-closed** (None → config 値を使用)。

startup 時に必ず log 出力:
```
stage_gate.effective_threshold stage_a_threshold=0.0778 source=history full_config_hash=...
```

#### T058 v2 schema 移行ノート (2026-04-30)

T058 (cascade port v2 contract) で `calibrate_history` の record schema は v1 → v2 に
bump された (`calibrate_history_schema_version=2`)。 v2 で必須化された field:

- `calibrate_history_schema_version` (int, default 2、 `__post_init__` で値固定検証)
- `dataset_epoch_id` (string, grammar `[a-z0-9_]+`、 epoch-rolling 識別子)

`read_history` は v1 record (= 上記 2 field を欠く record) を **skip + warning log**
(`calibrate_history.v1_or_invalid_record_skipped`) で扱い、 後段の filter 処理に
渡らないようにする (詳細設計 行 1027-1080)。

**T058 段階の scope key**: T054 の `dataset_span` 一致条件は **撤廃せず維持** したまま
`dataset_epoch_id` 一致条件を **AND 結合で追加** する (= scope key を「より厳しく」
する追加変更、 backward compat を保つ)。 T058 段階では `dataset_epoch_id` は
`generate_epoch_id_stub` (= `"epoch_legacy"` 固定) なので実質的に従来挙動のまま。

**T067 (将来) の完全置換予定**: T067 で T058 の transitional 設計から定常設計に
切り替える際、 移行 3 点セットを実施する:

1. `schema_contract.enforcement_mode` を `log_only` → `fail_closed` に切替え
2. cross-run scope key から `dataset_span` を **完全撤廃**
3. cross-run scope key を `dataset_epoch_id` **単独化** (T059 deterministic
   epoch_id 生成と組合せ)

T059 の deterministic epoch_id 生成と合わせて、 v1 archive / v1 history record も
全て排除する。

## 関連 TODO

- T014 完了 — `src/alpha_factory/stage_gate.py` / `src/alpha_factory/walk_forward.py`
  実装。
- T027 完了 — calibrate-gate (`stage_a.threshold` 動的調整)
- 後続:
  - GA runner 統合 (yaml → `StageGateConfig`、Stage 実行配線)
  - DSR hard gate 化 (Stage B `dsr_min`)
  - cross-pair-evaluation-shadow (Stage C `CrossPairEvaluator` 実装)
  - cross-pair の hard gate 化 (Phase 4)
  - calibrate-gate v2: per-lane / LLM 判断 / distribution shift detector (別 TODO)

## T054: Stage B fold-trade-count-min 独立化

### 背景

旧実装では Stage A も Stage B fold も `trade_count_min_for_sharpe = 30` を
共有していたが、Stage A は 60-day window、Stage B fold は wf_test_days=10
と評価期間が異なる。同じ 30 trade を 10-day fold に要求すると trade rate
3 trades/day を満たす個体しか fold 評価可能にならず、
`run_20260427_015804` では Stage A pass 全 3745 個体が
`all_folds_unavailable` 一色で reject された。

### 修正

`StageGateConfig.stage_b_fold_trade_count_min` (default=10) を追加し、
Stage B fold 評価では `trade_count_min_for_sharpe` の代わりにこれを使う。

統計要件 (Lo 2002 SE 上限):
- trade-level Sharpe SE ≈ √((1+0.5×SR²)/N)
- 目標 SR ≈ stage_b_median_oos_sharpe_min=0.05、SE 上限 0.32 から逆算 N≈10
- median + positive_fold_ratio の 2 段集約で fold 単位 noise を吸収

**緩和ではなく「機能していた当時 (run_20260426_145502 median 167) の
挙動を意図的に再現する設計判断」** (詳細設計 仮説 B-X 案 3、禁止事項 4 抵触なし)。

### 排他的 reason 別 fold count

`evaluate_stage_b` payload に `unavailable_reason_counts` を追加:

```python
class FoldUnavailableReason(StrEnum):
    FOLD_EXCEPTION = "fold_exception"      # 例外発生 (最優先)
    NO_TRADES = "no_trades"                # trade_count = 0
    TRADE_COUNT_BELOW_MIN = "trade_count_below_min"  # 0 < tc < min
    ZERO_VARIANCE = "zero_variance"        # tc >= min かつ std=0
    OTHER = "other"                        # 上記以外 (要 follow-up)
```

不変条件 (test_stage_gate.py 検証): `sum(reason_counts.values()) == n_fold_unavailable`

archive Parquet schema に `stage_b_unavailable_reason_counts` (JSON 文字列、
既存 `stage_b_reason_codes` との後方互換は追加のみで保持) を追加。

## T035: Stage B 観察可能性ハード契約 (Metric Completeness Gate)

`evaluate_stage_b` の payload に以下メトリクスを追加 (monitor only、`passed` 判定への影響なし):

- `n_fold_effective`: `n_fold - n_fold_unavailable` (実評価できた fold 数)
- `positive_fold_ratio_effective`: 有効 fold のみで再計算した positive ratio
- `n_unique_dates` / `wf_min_unique_dates`: skip-path 時 (LaneManager) に観測日数充足の根拠を残す

### Reason Code 語彙 (Stage B)

| reason_code | 発火条件 |
|-------------|---------|
| `no_folds` | `make_wf_folds` が空 list (本来 LaneManager skip-path で先回り防止) |
| `insufficient_folds` | `n_fold == 1` |
| `median_oos_sharpe<min` | median_oos_sharpe < `stage_b_median_oos_sharpe_min` |
| `positive_fold_ratio<min` | positive_ratio < `stage_b_positive_fold_min` |
| `all_folds_unavailable` | 全 fold で no-trade による sharpe=None |
| `stage_b_window_underfilled` | LaneManager が Stage B 評価前に observed_dates < (train+embargo+test) を検出し skip-path 適用 |

### archive 列追加 (T035)
- `n_fold_effective` (int64, nullable)
- `positive_fold_ratio_effective` (float64, nullable)
- `stage_b_reason_codes` (string, nullable; ";" 区切りで複数 reason 永続化)

## T069: epoch key + 3 Run freeze + Δ ≤ 0.03 (synthesis § 8.6)

### 凍結窓 3 Run

`dataset_epoch_id` を scope key として、 同 epoch 内の最初 3 distinct Run は
calibrate-gate を **freeze** (= threshold 適用なし、 `decision="skip_frozen"`)。
4 Run 目以降から通常の `tighten` / `loosen` 判定が有効化される。

count は `HistoryRecord.applied_from_run_id` の distinct set で測る (= 同 run_id
二重 append / retry に耐性)。 `applied_from_run_id` が `None` / 空文字の v2
record は count から除外し、 `calibrate_freeze.invalid_run_id` warning で可視
化する (defense-in-depth)。

### |Δ| ≤ 0.03

`stage_gate.stage_a.calibrate.threshold_delta_abs_max` を `0.03` に SSOT 固定
(`config/alpha_factory/default.yaml`)。 config 違反 (`> 0.03`) は起動時に
`CalibrateConfig.__post_init__` で `ConfigError` を raise し fail-closed。

### scope key

freeze 判定は `dataset_epoch_id` 単独で行う (synthesis § 8.6 1 軸 SSOT)。
cross-run contamination guard は T058 `load_calibrated_threshold` の 4 軸
verify (`base_config_hash` + `dataset_epoch_id` + `instrument` +
`stage_gate_version`) が別 layer で担保 (多層防御)。

### epoch 跨ぎ再利用遮断

T069 (Phase 1) では yaml への threshold 書き戻し経路は新設しない (= 既存
`scripts/alpha_factory/calibrate_gate.py` 経路を継承)。 Phase 2 (cascade port
切替) で以下のいずれかを確定:
- 案 A: yaml = immutable seed、 calibrate は history JSONL 専用 (推奨)
- 案 B: epoch 切替時に yaml reset
- 案 C: `stage_a_threshold` 自体を削除 (synthesis § 12.3 厳密準拠)

### library API (T069 PR1 scope)

| シンボル | 場所 | 役割 |
|---|---|---|
| `FreezeStatus` | `src/alpha_factory/calibrate_freeze.py` | epoch 内 freeze 判定結果 (immutable, pure data) |
| `evaluate_freeze_status` | 同上 | history record + dataset_epoch_id から `FreezeStatus` を計算 (pure function) |
| `decide_with_freeze` | 同上 | freeze 中は `skip_frozen` 即返、 そうでなければ `decide()` に委譲 |
| `DecisionLabel` | `src/alpha_factory/calibrate_gate.py` | `"skip_frozen"` を追加 |
| `DriftAnalysis.n_skip_frozen` | `src/alpha_factory/calibrate_gate_history.py` | drift 監視で `skip_frozen` record 数を可視化 |

### Phase 2 申し送り (T069 detailed-design § 12.2 連動)

- `scripts/alpha_factory/calibrate_gate.py` で `evaluate_freeze_status` +
  `decide_with_freeze` を配線 + skip_frozen record を history append + yaml
  書き戻し方式 (案 A 推奨) 確定
- `scripts/alpha_factory/calibrate_gate_drift.py` で `n_skip_frozen` を出力
- `scripts/alpha_factory/run_ga.py` で freeze 中の log (任意)
- 運用契約 preflight check: `dataset_epoch_id` 空なら calibrate 起動しない
- T058 詳細設計改訂依頼: `HistoryRecord.applied_from_run_id: str` を v2 必須化

## T070: SessionBlock 集計 + spread_cost / holding_cost field (synthesis § 4.4 / § 6.2 / § 6.3)

### 8h covering partition (BLOCK_BUCKET_RANGES_UTC)

UTC 24h を 3 covering partition (8h × 3、 重複なし) に分割し、 1 営業日 (UTC date)
× 1 bucket = 1 SessionBlock として集計する (synthesis § 4.4 SSOT):

| Bucket | UTC 時間範囲 | 想定マーケット |
|---|---|---|
| `tokyo` | `[0, 8)` | Tokyo session |
| `london` | `[8, 16)` | London session |
| `ny` | `[16, 24)` | NY session 後半 |

`src/alpha_factory/primitives/_indicators.py:51-55` の `_SESSION_RANGES_UTC`
(9h overlap windows、 indicator 用) とは **別責務** で並列管理する (= F18 防御).
DST / holiday は T072 (T914) で別 layer 例外として扱い、 T070 SSOT は UTC 単純基準
で固定.

### 会計契約 SSOT (Trade.spread_cost / holding_cost)

T070 で `Trade` dataclass に 2 field を追加 (default=Decimal(0)):

| field | 意味 | Trade.pnl への反映 |
|---|---|---|
| `spread_cost` | entry/exit spread 推定値 (Roll 1984 で `exit_spread × 2 × abs(units)`) | **未反映** (= 監査・stress 用記録) |
| `holding_cost` | `MockBroker._holding_cost_by_position[pos.id]` の転記 | **既反映** (= Trade.pnl は raw_pnl - holding_cost) |

**不変条件** (詳細設計 §3.5):

```
Trade.pnl + Trade.holding_cost == raw_pnl    (price-diff pnl)
Trade.spread_cost は raw_pnl と独立に記録
```

二重計上防御 (F19): `apply_bar_holding_cost` で既に `_cash` から控除済のため、
`_close_one` は cash 操作を変更しない (= broker.cash 動きの破壊変更なし).

### SessionBlock 集計式 (概念設計 §3.4.0)

```
pnl_net          = sum(t.pnl - t.spread_cost   for t in trades_in_block)
pnl_before_costs = sum(t.pnl + t.holding_cost  for t in trades_in_block)
spread_cost_total  = sum(t.spread_cost  for t in trades_in_block)
holding_cost_total = sum(t.holding_cost for t in trades_in_block)
```

**block invariant** (`SessionBlock.__post_init__` で検証):

```
pnl_before_costs == pnl_net + spread_cost_total + holding_cost_total
spread_cost_total >= 0
holding_cost_total >= 0
bar_count >= 0
trade_count >= 0
```

集計の **date universe** は bars が触れた UTC date set ∪ trades.exit_time が触れた
UTC date set × 3 bucket. `trade_count == 0` の empty block も生成する
(synthesis § 6.3 0.5 neutral 対象を機械判定可能化、 `is_empty_trade_block` /
`is_partial_bar_block` property 提供).

trade の 帰属 bucket は **`trade.exit_time` 一括帰属** (= entry/exit が異なる
bucket でも exit bucket に全 cost を寄せる、 詳細設計 §3.4.1 SSOT).

### apply_spread_stress (T064 申し送り解消、 T078 で alpha_factory 経路も完成)

T064 で `NotImplementedError` で skeleton 化されていた `apply_spread_stress` を
T070 で broker 経路 (Decimal、 `src/backtest/session_block.py`)、 T078 で
alpha_factory 経路 (float、 `src/alpha_factory/stage_bc_evaluator.py`) として
両方正式実装. 用途分離 (= 型差を維持しつつ代数的に等価):

#### broker 経路 (Decimal、 session_block.py)

```
delta_spread     = trade.spread_cost * (multiplier - Decimal(1))
new_pnl          = trade.pnl - delta_spread
new_spread_cost  = trade.spread_cost * multiplier
new_holding_cost = trade.holding_cost   # 不変 (stress は spread 専用)
```

#### alpha_factory 経路 (float、 stage_bc_evaluator.py、 T078 で skeleton 削除)

```
delta_factor     = multiplier - 1.0
new_pnl_net      = pnl_net - spread_cost * delta_factor
new_spread_cost  = spread_cost * multiplier
# holding_cost   不変 (stress は spread 専用)
```

両経路とも multiplier=1 で no-op、 multiplier < 1.0 / NaN / Infinite で `ValueError`.
overflow 時は TradeRecord invariant (= finite + >= 0) で `TradeRecordInvalidError` raise.
test 経路で代数的等価性を相対誤差 1e-9 以内で検証 (T078 [Suggestion] 2 反映).

**Caller 配線注意 (T078 [Warning] 1 反映)**: spread_cost が全 trade で 0.0
(= default、 trade 生成経路で伝搬未配線) の状態では multiplier > 1.0 でも stress
効果ゼロ (silent no-op). caller (= run_ga.py / Stage C 評価) 側で trade 生成経路
の spread_cost 伝搬を確立する責任あり (= 後続別 TODO).

**契約境界** (詳細設計 §4.3): stress 出力 `Trade(stressed)` は `Trade.pnl +
Trade.holding_cost = raw_pnl - delta_spread` の擬似 pnl となり、 通常会計の F13
invariant は適用しない. 下流 (T064 stress evaluator) は「stress 済 trade は
集計・SR 計算用、 broker.cash には反映されない」 を前提として扱う.

### transport SSOT (BacktestResult.session_blocks)

`BacktestResult.session_blocks: tuple[SessionBlock, ...]` field を追加し、
`run_backtest` 末尾で `aggregate_session_blocks(bars_list, broker.trades)` を
**1 回のみ計算** して同梱する. caller (T061 / T064 / Phase 2 配線) は
`result.session_blocks` を読むのみで **再計算は禁止** (= F14/F21 防御、
詳細設計 §4.6 SSOT).

backward-compat: `default_factory=tuple` のため既存 caller (= session_blocks を
読まない `BacktestResult(config=, trades=, equity_curve=)`) は影響なし.

### library API (T070 PR1 scope)

| シンボル | 場所 | 役割 |
|---|---|---|
| `SessionBlockBucket` | `src/backtest/session_block.py` | `Literal["tokyo", "london", "ny"]` |
| `BLOCK_BUCKET_RANGES_UTC` | 同上 | 8h covering partition SSOT (Final) |
| `SessionBlock` | 同上 | 1 営業日 × 1 bucket の集計 dataclass (frozen) |
| `compute_bucket_for_bar` | 同上 | `bar_time` UTC hour → bucket (pure function) |
| `compute_bucket_for_trade` | 同上 | `trade.exit_time` → bucket (pure function) |
| `aggregate_session_blocks` | 同上 | bars + trades → `tuple[SessionBlock, ...]` |
| `apply_spread_stress` | 同上 | spread cost multiplier で `Trade` 列を再計算 |
| `Trade.spread_cost` | `src/broker/orders.py` | entry/exit spread 推定値 (記録のみ) |
| `Trade.holding_cost` | 同上 | `_holding_cost_by_position[pos.id]` 転記 (既存 pnl 反映済) |
| `BacktestResult.session_blocks` | `src/backtest/engine.py` | run_backtest 末尾で同梱、 caller 再計算禁止 |

### Phase 2 申し送り (T070 detailed-design § 1.3 / § 10.2 連動)

- T064 `stage_bc_evaluator`: `apply_spread_stress` を T070 import に置換 +
  `TradeRecord` 表記 → `Trade` 統一
- T061 `canonical_metrics`: `BacktestResult.session_blocks` を入力に
  `SR_session_worst` / `WR_worst` 計算
- T072: `BLOCK_BUCKET_RANGES_UTC` への DST 例外、 holiday 時 block の特別扱い
- `scripts/alpha_factory/run_ga.py` / 既存 `backtest_runner`: `session_blocks`
  caller 配線 (= 再計算禁止 lint)
- run report / archive 露出: `Trade.spread_cost` / `holding_cost` /
  `SessionBlock.pnl_before_costs` などを log / report / archive に出す
  (F17 / F20 解消)
- broker `entry_spread` 保持改造: `spread_cost` を「entry_spread + exit_spread」
  で正確化 (現状 `exit × 2` 近似、 Roll 1984 で代用)

## T071: Observability hub (RunObservabilityReport / A→B 乖離 / archive churn / front1 / FailureSummary 消費)

### 責務

1 Run 全体の observability metric を **集約 dataclass** に集めるライブラリ層
(`src/alpha_factory/observability/run_metrics.py`)。 caller (Phase 2 で
`scripts/alpha_factory/run_ga.py`) は本層が公開する pure function を呼び、
`RunObservabilityReport` を構築して log / report / Phase 2 audit (T073) へ
受け渡す。

### 11 dataclass + 9 関数 (Phase 1 範囲)

| dataclass | 役割 |
|---|---|
| `ABDivergenceMetric` | A→B 乖離 Pearson corr (B 評価対象に conditioning、 status field で None 排除) |
| `QForceRecommendation` | A→B 乖離に応じた q_force 補正推奨 (raise/hold/restore + clamp) |
| `ArchiveChurnMetric` | 直近 N Run (max 3) の eviction 率 |
| `BypassRatioMetric` | archive 流入のうち score_bypass 割合 |
| `SessionEntropyMetric` | archive 内 session_pass_pattern Shannon entropy (3 bit、 weekly window) |
| `FeasibleRatioMetric` | Push/Pull FSM 切替指標 (T063 既存値の観測) |
| `SelectionMetric` | T065 GenerationSelectionResult からの抽出 (front1 cardinality 等) |
| `InflowConsistencyMetric` | warmstart + admission の inflow 整合性 |
| `FailureMetricStage` / `FailureMetric` | T068 RunFailureSummary からの per-stage / Run 横断抽出 |
| `RunObservabilityReport` | 上記 9 metric の集約 hub |

| 関数 | 役割 |
|---|---|
| `compute_ab_divergence_on_b_evaluated` | Pearson corr 計算 (n<10 で insufficient_data、 zero variance 検出) |
| `recommend_q_force_adjust` | hysteresis (0.30 / 0.50) + delta 0.02 + min/max clamp |
| `compute_archive_churn` | 直近 3 Run eviction 率 |
| `compute_bypass_ratio` | role 別 admission count から bypass 比率 |
| `compute_session_entropy` | 3 bit pattern の Shannon entropy (weekly window) |
| `extract_selection_metrics` | T065 result + caller 注入 (feasible_ratio 等) |
| `extract_inflow_consistency` | T067 share + T066 admission + caller 注入 (target share) |
| `extract_failure_metrics` | T068 summary + caller 注入 (fingerprint top-N) |
| `build_run_observability_report` | 集約 pure function |
| `build_stub_run_observability_report` (T080a) | Phase 2 配線 first step、 9 metric を valid status / default 値で構築 (= 経路確立、 実値配線は T080b-g) |
| `serialize_run_observability_report` (T080a) | RunObservabilityReport → JSON 文字列 (Decimal str 化、 Mapping/tuple/frozenset 変換) |

### 主要定数

| 定数 | 値 | 出処 |
|---|---|---|
| `DELTA_PER_RUN` | `Decimal("0.02")` | synthesis § 8.7 |
| `Q_FORCE_MAX` | `Decimal("0.40")` | synthesis § 8.7 |
| `RESTORE_THRESHOLD` | `Decimal("0.50")` | synthesis § 8.7 |
| `Q_FORCE_MIN` | `Decimal("0.15")` | T071 仮説値 (Phase 2 で再校正) |
| `DIVERGENCE_THRESHOLD` | `Decimal("0.30")` | T071 仮説値 (Phase 2 で再校正) |
| `AB_MIN_ACTIONABLE_PAIRS` | `10` | C7 規範 (n<10 相関 claim 禁止) |
| `WEEKLY_WINDOW_SIZE` | `7` | weekly entropy 集計窓 |
| `WARMSTART_SHARE_TOLERANCE` | `Decimal("0.01")` | inflow drift 許容範囲 |

### main 実装 SSOT 規範 (T058-T070 で確立)

詳細設計の前提と main 実装の field 名 / 存在に乖離がある場合、 main 実装を SSOT
として T071 側を調整する (= caller 注入式に変更)。 主要乖離点:

- T065 `GenerationSelectionResult`: `pareto_front1_size` / `feasible_ratio` /
  `mean_constraint_violation` / `generation` 不在 → T071 は `front_assignments`
  から front1 を再計算 + 残り 3 field は caller 注入
- T066 `AdmissionReport`: `n_admitted_ca/da` / `n_evicted_ca/da` / `n_admitted_by_role`
  不在 → role 別 (mission/progress/bypass) を str key dict に集約、
  eviction は `len(evicted_genome_ids)`
- T066 `ArchiveRole` enum 不在 → str key (`"mission_pass"` / `"progress_pass"`
  / `"score_bypass"`)
- T066 `ArchiveMember.session_pass_pattern` 不在 → caller (Phase 2) が
  事前計算した 3 bit string list を引数注入
- T067 `WarmstartConfig` / `warmstart_share_target` / `warmstart_share_actual`
  / `per_source_run_violations` 不在 → caller 注入 (target / violations)、
  `WarmstartReport.share` を actual 扱い
- T068 `RunFailureSummary.run_aborted` 不在 → `any_stage_all_failed` を抽出
- T068 `FailureSummary.fingerprint_dedup_top_n` 不在 → caller 注入 (per-stage
  fingerprint top-N dict、 default 空)

### F1-F15 失敗モード対応 (Phase 1 unit test)

| failure | 対応 | test prefix |
|---|---|---|
| F1 n<10 actionable 抑止 | `status="insufficient_data"` | `test_F1` |
| F2 var=0 で nan | `status="zero_variance"` sentinel | `test_F2` |
| F3 数値誤差 [-1, 1] 越境 | post compute clamp | `test_F3` |
| F4 q_force max/min 越境 | clamp + `clamped_at_*` field | `test_F4` |
| F5 hysteresis 振動 | `divergence_threshold (0.30) < restore_threshold (0.50)` | `test_F5` |
| F6 archive_churn denom 0 / 不足 | zero check + status 判定 | `test_F6` |
| F7 bypass_ratio denom 0 | zero check | `test_F7` |
| F8 session_entropy archive 空 / window 不足 | `empty_archive` / `insufficient_window` | `test_F8` |
| F9 InflowConsistency tolerance | `WARMSTART_SHARE_TOLERANCE = 0.01` | `test_F9` |
| F10 status 不整合 | `__post_init__` 完全強制 | `test_F10` |
| F11 T065-T068 field rename | extract function fixture テスト | `test_F11` |
| F12 a/b 個体対応ずれ | length 一致 check | `test_F12` |
| F13 divergence_threshold 仮説値 | T071 仮説 + Phase 2 再校正申し送り | (Phase 2-IT) |
| F14 連続乖離 Run カウント | caller 保持 + `RunObservabilityReport` invariant | `test_F14` |
| F15 q_force delta 適用順序 | delta → max/min clamp の順 | `test_F15` |

### Phase 2 申し送り

- `scripts/alpha_factory/run_ga.py`: `build_run_observability_report` 呼び出し
  + 連続乖離 Run state file 保持 + log / report 出力
  - **T080a (本 PR) 完了**: stub builder 経由で run 終了時に
    `reports/run-reports/{run_id}/observability.json` 出力経路を確立。
    9 metric は全て stub 値 (= valid status / default、 経路確認専用)。
  - **T080b-g (後続別 TODO)**: 各 metric の実値配線:
    - T080b: ABDivergenceMetric (cross-run history、 caller 計算)
    - T080c: ArchiveChurnMetric / BypassRatioMetric (AdmissionReport 経路)
    - T080d: SessionEntropyMetric / FeasibleRatioMetric (archive + StageAControllerState)
    - T080e: SelectionMetric (GenerationSelectionResult 経路)
    - T080f: InflowConsistencyMetric / FailureMetric (WarmstartReport / RunFailureSummary)
    - T080g: QForceRecommendation (recommend_q_force_adjust + state file)
- `src/alpha_factory/stage_a_evaluator.py` (T063): `q_force_recommendation` を
  `StageAControllerState` 更新に配線 (= T080g スコープ)
- `docs/alpha_factory/observability.md` 新設: RunObservabilityReport の
  Markdown 表現 + 監視運用ガイド (= 後続別 TODO)
- run report Markdown 化: `RunObservabilityReport` を report.md に整形
- T073 audit layer: DSR/PBO/SPA + `ab_divergence` を audit input
- pop promotion (192→256) trigger: `front1_cardinality < 20` 連続 2 Run 検出 →
  promotion 実行
- `divergence_threshold` 再校正: 実測 corr 分布から T071 仮説値 (0.30) を
  Phase 2 smoke 後に更新検討

## T072: DST/holiday session boundary contract

cascade port v2 Phase 2 配線 15 番目 TODO。 broker 配信 schedule
(`BrokerTradingSchedule`) と市場 holiday 観測 (`MarketHolidayCalendar`) を
**完全分離** し、 DST table + date_overrides + 半開区間 [start, end) で
SessionBlock を駆動する。 holiday を expected_bar_count に混ぜないことが
SSOT (= collider bias 規範)。

### 主要 dataclass / 関数 (Phase 1)

| Symbol | 責務 |
|---|---|
| `BrokerSeasonalCloseSpec` | DST season 別 close/reopen spec (= region_start/end inclusive、 disjoint、 連続 cover) |
| `BrokerTradingSchedule` | broker 配信 schedule SSOT (= dst_aware_close_table + broker_full_close_holidays + date_overrides) |
| `MarketHolidayCalendar` | 単一市場の取引所公式 holiday (観測情報のみ、 expected_bar_count に touch しない) |
| `ObservabilityFlags` | `dst_transition_markets` (≤2) + `holiday_markets` (≤3) の audit/log 用 mark |
| `BrokerSchedulingProvenance` | YAML schema 出典の provenance (source / verified_at / confidence / notes) |
| `is_dst_transition(market, d)` | zoneinfo (IANA tz) 経由 DST transition 判定 (London / NY、 Tokyo は常に False) |
| `is_market_holiday(market, d, calendar)` | 検証済 calendar の raw lookup |
| `compute_observability_flags(d, calendars)` | business_date 単位の flags 集計 |
| `compute_bucket_open_minutes(d, bucket, schedule)` | bucket UTC ∩ broker open window (半開区間 overlap) |
| `compute_expected_bar_count(open_minutes, granularity_seconds)` | floor 演算 (= H4 で 120 min → 0) |
| `validate_calendar_coverage(calendars, schedule, span)` | 全 3 市場 + broker schedule の period が dataset_span を覆うか集約検証 |
| `load_market_holiday_calendar(market, yaml_path)` / `load_broker_trading_schedule(yaml_path)` | YAML loader (= `_DuplicateKeyRejectLoader` 経由 duplicate / merge key reject) |
| `aggregate_session_blocks(...)` | mode 必須 (Round D1 [C4])。 production caller は wrapper 経由 |
| `aggregate_session_blocks_production(...)` | production-only wrapper (Round D2 [C3])、 mode="production" を構造的強制 |

### SessionBlock 改造

T070 既存 8 field に **3 field 追加**:
- `open_minutes` (primary、 0..480、 default 480)
- `granularity_seconds` (M1_PLUS_GRANULARITIES、 default 60)
- `observability_flags`

derived (property):
- `expected_bar_count = open_minutes * 60 // granularity_seconds`
- `schedule_status` ∈ {regular, closed_full, closed_partial}
- `is_partial_bar_block`

`to_record(include_derived: bool)` で audit/export schema を固定
(= `SESSION_BLOCK_STORAGE_FIELDS` 12 path / `SESSION_BLOCK_DERIVED_FIELD_PATHS`
4 path、 `RECORD_SCHEMA_VERSION="1.0.0"`)。

### YAML schema (config/calendars/)

- `broker_trading_schedule.yaml`: 2022-2027 の DST season 完全列挙 (= 13 region) +
  `broker_full_close_holidays` (= クリスマス / 新年) + `date_overrides` (= 早閉まり)
- `tokyo_market_holidays.yaml`: 国民の祝日 + TSE close 日 110 件
- `london_market_holidays.yaml`: UK bank holidays 51 件
- `ny_market_holidays.yaml`: NYSE / Federal Reserve holidays 60 件

すべて `_DuplicateKeyRejectLoader` で duplicate key + merge key (`<<`) を YAML
段階で reject する。

### collider bias 規範 (T071/T064/T066 詳細設計改訂申し送り)

`holiday_markets` 単独で session_pass_pattern / SR 計算分母を drop / filter
してはならない。 必ず stratified audit (= holiday_markets 値別の集計) を行い、
conditioning set を明示する。 holiday を expected_bar_count に混ぜることは
T072 SSOT で禁止。

### Phase 2 申し送り

- `scripts/alpha_factory/run_ga.py`: `aggregate_session_blocks_production` wrapper
  に切替 + broker_schedule / calendars を load 経由で渡す + `validate_calendar_coverage`
  を caller が一回呼ぶ
- `src/backtest/engine.py`: 同様に Phase 2 で wrapper 化
  (= 現状は `mode="test"` で T070 互換)
- T070 BLOCK_BUCKET_RANGES_UTC への DST 例外連携 caller (= T070 follow-up)
- T061 canonical_metrics: `expected_bar_count` 駆動の HAC SR / WR 計算
- T064 stage_bc_evaluator: fold 境界の closed_partial / closed_full 扱い
  (pnl=0 重みづけ or 除外、 holiday_markets は別軸 audit)
- T066 cpps_archive: archive admission 時の `session_pass_pattern` 生成で
  `expected_bar_count > 0` を分母条件、 holiday_markets を condition として
  stratified
- T071 SessionEntropyMetric: 同 semantic で `session_pass_pattern` 入力
- run report / archive: `to_record(include_derived=True)` 経由で
  observability_flags / schedule_status / expected_bar_count を log / report 露出
- OANDA Developer Portal 公式 spec 確認後に Phase 2 で
  `broker_full_close_holidays` / `date_overrides` を production 反映 (Phase 1 は
  単体テスト範囲、 confidence=medium)

---

## B Phase 2 切替コミット dual-path log SSOT (= step 1-1.8)

### § 4.7 ログ命名規約 SSOT

`stage_gate.canonical_five.dual_path` event の `stage` field と識別子契約は以下:

| stage_label | 評価対象 | step | fold_index | pair_label |
|---|---|---|---|---|
| `A` | Stage A 評価窓 (60d) | step 1 (= main commit 9bc6a02) | None | None |
| `B_IS` | Stage B 18m 全体 IS | step 1.5 (= 6276d58) | None | None |
| `B_fold` | Stage B per-fold OOS | step 1.6 (= 1dadc8b) | **必須 (0..n_fold-1)** | None |
| `C_base` | Stage C base evaluation (holdout 60d) | step 1.5 (= 6276d58) | None | None |
| `C_stress` | Stage C spread stress backtest (holdout 60d × spread_multiplier) | step 1.7 (= e3a428b) | None | None |
| **`C_cross_pair`** | Stage C cross-pair (ii-lite) shadow per-pair | **step 1.8 (本 commit)** | None | **必須 (実 pair 名 = "EUR_USD" 等)** |

### 識別子契約 (= `_log_canonical_dual_path` fail-fast)

`src/alpha_factory/stage_gate.py:_log_canonical_dual_path` は識別子契約違反を `ValueError` で fail-fast:

- `stage_label="B_fold"` で `fold_index is None` → ValueError
- `stage_label="C_cross_pair"` で `pair_label` が `None` / 空文字 / 空白文字列 / 前後空白付き文字列 → ValueError
- `stage_label != "B_fold"` で `fold_index is not None` → ValueError (= ログ名前空間汚染防止、 step 1.8 で対称化)
- `stage_label != "C_cross_pair"` で `pair_label is not None` → ValueError (= ログ名前空間汚染防止)

`pair_label` には **実 pair 名のみ許可** (= `"EUR_USD"` / `"USD_JPY"` 等)。 役割識別 (= target / anchor1 / anchor2) は dual-path log に出さない (= SSOT 簡潔化)。 将来 role 分析時は Stage C payload の `target_pair` / `anchor_pairs` と `(genome, pair)` で join する設計。

### dual-path skip SSOT (= step 1.8 で確立)

cross_pair dual-path 経路の skip 条件は **`sidecar_inputs is None`** (= exception pair のみ skip)。

- **exception pair** (= `_run_pair_sharpe` 内で `run_backtest` / `compute_metrics` raise) → `sidecar_inputs is None` → dual-path skip
- **metric_unavailable pair** (= bt 計算成功 + `trade_sharpe_raw is None`) → `sidecar_inputs` 保持 → dual-path で `_try_evaluate_canonical_five_safe` 呼出 → 内部 fallback で None 返り → `canonical_skipped=True` event emit

`pair_failures` リストは **既存 cross_pair gate** (= aggregate_fitness / pass_criteria) 用で、 dual-path 配線とは **独立**。

### sanitize 経路 (= step 1.8 で確立)

`evaluate_stage_c` の cross_pair 区画は dual-path 経路を `try ... finally` で囲み、 finally 句で **常時** sanitize:

```python
try:
    # dual-path: per-pair iterate + canonical 計算 + log emit
    ...
finally:
    # sidecar が payload / IPC / archive に絶対漏れない契約
    cross_pair_payload["result"] = replace(cp_result, _shadow_sidecar_inputs={})
```

dual-path 経路の **例外有無 / disabled mode / sidecar 空 / cp_result is None / pair_failure 全分岐** で sanitize は常時実行される。 sanitize 後の `CrossPairResult._shadow_sidecar_inputs` は空 dict、 multiprocessing pickle (= `parallel_eval._pool.map`) 経路でも IPC に sidecar が漏れない。

### `CrossPairResult._shadow_sidecar_inputs` field 契約

- `field(default_factory=dict, repr=False, compare=False)` (= step 1.8)
- `default_factory=dict`: multiprocessing pickle 互換 (= `MappingProxyType` 不可、 `pickle.dumps` で TypeError 防止)
- `repr=False`: snapshot 比較ノイズ排除
- `compare=False`: dataclass equality から除外 (= sidecar 内容のみ異なる 2 個の `CrossPairResult` は等価扱い)
- leading underscore で **public API ではない ephemeral 属性** を明示

### smoke merge gate (= acceptance B2 / B3、 step 1.8 で導入)

`scripts/smoke/measure_step1.8_memory.sh` + `scripts/smoke/aggregate_step1.8_memory.py` (= psutil sampling SSOT) で merge 条件を実測:

- **B2 主条件**: `sampled_max_worker_rss < 3 GB` (= psutil sampling、 元制約「6 worker / 1 worker 約 3 GB」 を直接検証)
- **B2 補助条件**: `sampled_process_tree_rss_max < 18 GB` (= 6 worker × 3 GB の総量上限、 暫定)
- **B3**: `wall_time_mean_per_run` が **step 1.7 baseline 比 ±20% 以内** (= `reports/smoke/step1.7/` を `--baseline-dir` で参照、 baseline 不在 / 計測欠損時は B3 INCONCLUSIVE で **merge 失敗** 扱い)

aggregate helper (= `aggregate_step1.8_memory.py`) の exit code:

- `0`: B2 PASS かつ B3 PASS
- `1`: それ以外 (= B2 FAIL / B3 FAIL / B2 INCONCLUSIVE / B3 INCONCLUSIVE のいずれか)

sampling 失敗時 (= 以下いずれか) は **B2 INCONCLUSIVE で merge 不可** (= SSOT を崩さない、 暫定運用しない、 詳細設計 § 12.4 Case B):

- `sampled_worker_rss` / `sampled_process_tree_rss` いずれか欠損
- `n_samplers_succeeded != n_runs` (= 一部 run の sample-N.jsonl が存在しない / 0 sample) — Codex impl-review Round 3 [Critical] 反映で導入
- `n_samplers_failed > 0` (= sample-N.jsonl 存在するが parse 失敗 / 空 / header 不在 / run_index mismatch)

stale file contamination guard (= Codex impl-review Round 4 [Critical] 反映):

- `measure_step1.8_memory.sh` 開始時に `rm -f reports/smoke/step1.8/{run-*.log,sample-*.jsonl}` で前回 run の残骸を初期化
- sampler は出力 JSONL の **1 行目に header** (= `run_index` / `started_at` / `root_pid` / `target_cmdline`) を書き込む
- aggregate は header の `run_index` と `run-N.log` の番号を pair 検証 (= mismatch なら sampler_failed)
- aggregate は JSONDecodeError も failed 扱い (= SSOT 計測で malformed line を見逃さない)

fallback は `ps -o rss= -p <pid>` 等の手動計測で SSOT を再 verify してから merge。

sampler の cross-run contamination guard:

- `--target-cmdline` で対象 root process を cmdline 部分一致で特定
- **sampler 起動時刻以後に起動した process だけを対象** (= 既存の別 run_ga が残っていても捕捉しない、 詳細設計 Round 5 [Suggestion 施策 6] + 実装 Round 2 [Warning] 反映)
- 任意で `--extra-marker` を渡せば run-specific cmdline marker でさらに絞り込み可能 (= 並列 smoke の future improvement)

詳細: `devnotes/20260504-0010-B-phase2-step1.8-stage-c-cross-pair-dual-path/{conceptual,detailed}-design.md`
