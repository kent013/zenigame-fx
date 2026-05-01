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
    bars_18m: list[PriceBar],
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
