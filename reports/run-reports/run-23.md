# Run 23 — run_20260426_224524

**Generated**: 2026-04-26T22:45:24.440596+00:00
**Dataset**: EUR_JPY `2025-10-01T00:00:00+00:00` → `2026-04-01T00:00:00+00:00` (bars=183403)
  - bars_stage_a: 86400
  - bars_stage_b: 183403
  - bars_holdout: 20457

## 使命判定

未達

- ❌ **sharpe**: 0.3349342097796607 / threshold 1.0
- ❌ **total_pnl**: 27360.0 / threshold 50000.0
- ✅ **max_drawdown_pct**: 0.0 / threshold 20.0
- ❌ **trade_count**: 45 (range 50〜5000)

## GA 設定

- population_size: 96
- generations: 60
- mutation_rate: 0.3
- crossover_rate: 0.7
- tournament_size: 3
- elite_count: 2
- max_depth: 4
- fitness_metric: sharpe
- seed: None

## Best 個体

- name: `g55_i49`
- generation: 55
- fitness: **0.31432109199207137**
- fitness_finite: ✅
- stage_a_pass: ✅
- stage_b_pass: ❌
- stage_c_pass: ❌
- trade_count: 45
- total_pnl: 27360.0
- sharpe: 0.3349342097796607
- sortino: —
- calmar: —
- max_drawdown_pct: 0.0

**Archive 補足情報**:
- lane_id: tier1_EUR_JPY
- instrument: EUR_JPY
- fold_sign_ratio: 0.0000
- dsr: —
- ii_lite_pass: —
- n_nodes: 2
- active_clause: 1

## Stage 通過数

- 全 archive 行数: 5856
- Stage A pass: 2238
- Stage B pass: 0
- Stage C pass: 0

## Lane 別落下分布

| lane_id | total | A | B | C |
|---------|-------|---|---|---|
| tier1_EUR_JPY | 5856 | 2238 | 0 | 0 |

## Pair 別落下分布

| instrument | total | A | B | C |
|------------|-------|---|---|---|
| EUR_JPY | 5856 | 2238 | 0 | 0 |

## active_clause / n_nodes 分布

- active_clause: n=5856, mean=0.9582, median=1.0000, std=0.2002, min=0, max=1
- n_nodes: n=5856, mean=2.1335, median=2.0000, std=0.7245, min=1, max=4

## mission_score 分布 (T043 / observation only)

> live_criteria 4 軸 (sharpe/total_pnl/max_drawdown/trade_count) の soft 合算スコア (幾何平均、[0.1, 1.0])。GA fitness や stage_c.passed には 影響しない (詳細: docs/alpha_factory/mission-score.md)。

- mission_score=計測対象 0 件 (Stage C base 評価で Sharpe を出した 個体が無いため未計測)

## fold_sign_ratio / dsr 分布

- fold_sign_ratio: n=2238, mean=0.0000, median=0.0000, std=0.0000, min=0.0000, max=0.0000
- dsr: n=0
- n_fold_effective (Stage A pass): n=2238, mean=0.0080, median=0.0000, std=0.2689, min=0, max=9
- positive_fold_ratio_effective (Stage A pass): n=2, mean=0.0000, median=0.0000, std=0.0000, min=0.0000, max=0.0000

## Stage B failure reason 集計

- Stage A pass = 2238, Stage B pass = 0, failures = 2238 (primary_sum = 2238)

### Primary reason (先頭 reason、合計 = failures)

| reason | count |
|--------|------:|
| `no_folds` | 0 |
| `insufficient_folds` | 0 |
| `all_folds_unavailable` | 0 |
| `stage_b_window_underfilled` | 0 |
| `median_oos_sharpe<min` | 2238 |
| `positive_fold_ratio<min` | 0 |
| `stage_b_pre_flight_underfilled` | 0 |
| `unknown_reason` | 0 |
| `other` | 0 |

### Any reason incidence (全 reason、合計 >= failures)

| reason | count |
|--------|------:|
| `no_folds` | 0 |
| `insufficient_folds` | 0 |
| `all_folds_unavailable` | 2236 |
| `stage_b_window_underfilled` | 0 |
| `median_oos_sharpe<min` | 2238 |
| `positive_fold_ratio<min` | 2238 |
| `stage_b_pre_flight_underfilled` | 0 |
| `other` | 0 |

## Cross-pair shadow 集計

- runtime mode: skipped_single_instrument
- ii_lite_pass: True=0, False=0, None=5856

## Graduation

- archive graduated: 0
- summary.graduation_count: 0

## Feasibility 集計

- selection_score schema: `v3_1_stage_b_priority`
- trade_count=0 個体比率: 13.1% (765/5856)
- best 個体 trade_count: 45
- best 個体 feasibility: ✅

## Stage A provenance 分布 (T033 / sidecar)

> Stage A 落ち個体の `total_pnl_stage_a` 分布を可視化 (`reports/run-reports/run-{N}/diagnostics/stage_a_provenance.parquet`)。archive `total_pnl=0.0` が「Stage A 落ち = 投影仕様」「実 PnL=0」「コスト過大」のいずれかを切り分けるための観測指標 (詳細: docs/alpha_factory/diagnostics-sidecar.md)。

- sidecar 行数: 5856
- metric_stage 分布: stage_a_evaluated=2238, stage_a_only=3618
- (1) Stage A 落ち全体 `total_pnl_stage_a` 分布: n=3618, mean=-2560487.1918, median=-80790.0000, std=4743327.1874, min=-19282080.0000, max=22270.0000
- (2) Stage A 落ち かつ trade_count>0 の `total_pnl_stage_a` 分布 (n=2853): n=2853, mean=-3247053.1581, median=-384930.0000, std=5128618.9642, min=-19282080.0000, max=22270.0000
  - うち PnL=0 個体: 0 件 (取引したのに PnL=0 = Run 9 監査の対象観測)
- (3) Stage A 通過個体 `total_pnl_stage_a` 分布 (n=2238): n=2238, mean=10545.6568, median=20990.0000, std=317277.1787, min=-10596800.0000, max=34130.0000

## Archive Top-5 個体一覧

> Best とは別物です。`fitness_pen` 単独降順。Best は (feasible, -violation, stage_b_pass, stage_c_feasible, stage_c_pass, stage_b_pass, stage_a_pass, fitness_pen) の辞書式 (v3.1_stage_b_priority, T046)。

| rank | name | gen | lane | instrument | fitness_pen | fitness_raw | A | B | C | trade_count | sharpe |
|-----:|------|----:|------|------------|------------:|------------:|---|---|---|----:|-------:|
| 1 | `g55_i49` | 55 | tier1_EUR_JPY | EUR_JPY | 0.3143 | 0.3233 | ✅ | ❌ | ❌ | 45 | — |
| 2 | `g56_i0` | 56 | tier1_EUR_JPY | EUR_JPY | 0.3143 | 0.3233 | ✅ | ❌ | ❌ | 45 | — |
| 3 | `g56_i69` | 56 | tier1_EUR_JPY | EUR_JPY | 0.3143 | 0.3233 | ✅ | ❌ | ❌ | 45 | — |
| 4 | `g57_i0` | 57 | tier1_EUR_JPY | EUR_JPY | 0.3143 | 0.3233 | ✅ | ❌ | ❌ | 45 | — |
| 5 | `g57_i1` | 57 | tier1_EUR_JPY | EUR_JPY | 0.3143 | 0.3233 | ✅ | ❌ | ❌ | 45 | — |

## 収束履歴

| gen | best_fitness |
|-----|--------------|
| 0 | -0.031602918749649565 |
| 1 | 0.22641512644206302 |
| 2 | 0.22641512644206302 |
| 3 | 0.22641512644206302 |
| 4 | 0.22641512644206302 |
| 5 | 0.22641512644206302 |
| 6 | 0.22641512644206302 |
| 7 | 0.2404385111119331 |
| 8 | 0.2404385111119331 |
| 9 | 0.268708589365632 |
| 10 | 0.268708589365632 |
| 11 | 0.268708589365632 |
| 12 | 0.268708589365632 |
| 13 | 0.268708589365632 |
| 14 | 0.268708589365632 |
| 15 | 0.268708589365632 |
| 16 | 0.268708589365632 |
| 17 | 0.268708589365632 |
| 18 | 0.268708589365632 |
| 19 | 0.2736713503230536 |
| 20 | 0.2736713503230536 |
| 21 | 0.29137259541497046 |
| 22 | 0.29137259541497046 |
| 23 | 0.29137259541497046 |
| 24 | 0.29137259541497046 |
| 25 | 0.29137259541497046 |
| 26 | 0.29137259541497046 |
| 27 | 0.29137259541497046 |
| 28 | 0.29137259541497046 |
| 29 | 0.29137259541497046 |
| 30 | 0.29137259541497046 |
| 31 | 0.29137259541497046 |
| 32 | 0.29137259541497046 |
| 33 | 0.29137259541497046 |
| 34 | 0.29137259541497046 |
| 35 | 0.3064831790184034 |
| 36 | 0.3064831790184034 |
| 37 | 0.3137638913724729 |
| 38 | 0.3137638913724729 |
| 39 | 0.3137638913724729 |
| 40 | 0.3137638913724729 |
| 41 | 0.3137638913724729 |
| 42 | 0.3137638913724729 |
| 43 | 0.3137638913724729 |
| 44 | 0.3137638913724729 |
| 45 | 0.3137638913724729 |
| 46 | 0.3137638913724729 |
| 47 | 0.3137638913724729 |
| 48 | 0.3137638913724729 |
| 49 | 0.3137638913724729 |
| 50 | 0.3137638913724729 |
| 51 | 0.3137638913724729 |
| 52 | 0.3137638913724729 |
| 53 | 0.3137638913724729 |
| 54 | 0.3137638913724729 |
| 55 | 0.31432109199207137 |
| 56 | 0.31432109199207137 |
| 57 | 0.31432109199207137 |
| 58 | 0.31432109199207137 |
| 59 | 0.31432109199207137 |
| 60 | 0.31432109199207137 |

## 分析

### analysis-claude.md

# Run 22 分析

**run_id**: `run_20260426_204204`
**generated_at**: 2026-04-26T20:42:04.236776+00:00

## 観察事実

### 使命判定 (live_criteria)

- ❌ sharpe: 0.14488130397605056 / 閾値 1.0
- ❌ total_pnl: 17580.0 / 閾値 50000.0
- ✅ max_drawdown_pct: 0.0 / 閾値 20.0
- ✅ trade_count: 68 (許容 50〜5000)

### Best 個体

- name: `g44_i92`
- fitness (sharpe): 0.33656668015050756
- trade_count: 68
- total_pnl: 17580.0
- sharpe: 0.14488130397605056
- max_drawdown_pct: 0.0
- win_rate: None

### 収束状況

- 世代数: 61
- 初世代 best_fitness: 0.0004721925489815041
- 最終世代 best_fitness: 0.33656668015050756
- Δfitness: 0.3360944876015260559
- plateau: True

### 前回 Run との比較

- best_fitness: 0.39563308988865625 ↓ 0.33656668015050756 (Δ=-0.05906640973814869)
- trade_count: 72 → 68

## 解釈

- 未達: sharpe, total_pnl。これらが次サイクルの改善ターゲット。
- plateau 検出: 最終 3 世代で best_fitness が変化なし。mutation_rate 増加 or 初期集団多様化を検討。
- 前回より後退。seed のばらつきの可能性もあるので、即座に閾値を弄らず複数 Run の傾向で判断する。

### analysis-codex.md

**観察事実**
- Run-20（`gate=0, v2`）で `B pass=834` を確認。
- Run-21（`gate=0.0778, v3`）で `B pass=0`、Run-22（`gate=0.1778, v3.1`）でも `B pass=0` 継続。
- `best PnL / Sharpe` は Run-21,22 で正方向化している一方、`Stage B` は復旧していない。
- サンプルは Run-19〜22 の4点のみで、因果断定には不十分（C7）。

**解釈**
- `B=0` は gate ratchet だけでは説明しにくい（既に Run-21 時点で 0）。
- まず反証すべき主因は `T045/T046（v3系の選抜・制約変更）` 側。
- よって H1 単独より H2/H3 優先で検証するのが C9（falsification-first）に合う。

**推奨施策（1件）**
- **案C採用**: `T045/T046 を一時撤回し v2 + gate=0` で **1 run** 実行し、`Stage B復活可否` を先に判定する。  
  （最小変更で診断力が高く、1サイクル内で実行可能）

**反証可能仮説（1つ）**
- 仮説: 「`B=0` の主因は calibrate ratchet ではなく、`v3/v3.1（T045/T046）` の選抜・制約変更である」
- 反証条件: `v2 + gate=0` に戻しても `B pass=0` のままなら、この仮説は棄却寄り。

**success_criterion**
- 1 runで以下を同時に満たすこと:
  1. `B pass > 0`（最低復活ライン）
  2. できれば `B pass >= 200`（ノイズでない復活の目安）
  3. `A pass` が極端崩壊しない（Run-20比で -50%以内）

**全体判定**
- 現時点は **INCONCLUSIVE**。ただし優先順位は「H1後回し、H2/H3先に反証」。  
- Cycle 11 の一手は **案C** が最短で因果を切り分けられる。

