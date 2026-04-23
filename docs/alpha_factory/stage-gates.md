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
| A | `system_failure` | backtest / size_norm 計算で例外 |
| A | `no_trades` | trade_count == 0 |
| A | `metric_unavailable` | sharpe が計算不可 (returns 不足など) |
| A | `below_threshold` | fitness_pen ≤ stage_a_threshold |
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
| C | `spread_stress_skipped` | max_spread_bps=None で stress 評価不能 (fail-closed) |
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

## 関連 TODO

- T014 完了 — `src/alpha_factory/stage_gate.py` / `src/alpha_factory/walk_forward.py`
  実装。後続:
  - GA runner 統合 (yaml → `StageGateConfig`、Stage 実行配線)
  - calibrate-gate (`stage_a.threshold` 動的調整)
  - DSR hard gate 化 (Stage B `dsr_min`)
  - cross-pair-evaluation-shadow (Stage C `CrossPairEvaluator` 実装)
  - cross-pair の hard gate 化 (Phase 4)
