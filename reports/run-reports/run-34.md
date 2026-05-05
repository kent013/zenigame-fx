# Run 34 — run_20260505_043320

**Generated**: 2026-05-05T04:34:11.429727+00:00
**dataset_epoch_id**: `epoch_20251001_20260401`
**Dataset**: EUR_JPY `2025-10-01T00:00:00+00:00` → `2026-04-01T00:00:00+00:00` (bars=183403)
  - bars_stage_a: 86400
  - bars_stage_b: 97003
  - bars_holdout: 20457
  - Stage B excludes Stage A window (stage_b: 2025-10-01T00:00:00+00:00 → 2026-01-06T18:25:00+00:00, stage_a: 2026-01-06T18:26:00+00:00 → 2026-03-31T23:59:00+00:00)

## 使命判定

未達

- ❌ **sharpe**: 0.18903318328930815 / threshold 1.0
- ❌ **total_pnl**: 40140.0 / threshold 50000.0
- ✅ **max_drawdown_pct**: 0.0 / threshold 20.0
- ✅ **trade_count**: 54 (range 50〜5000)

## GA 設定

- population_size: 96
- generations: 60
- mutation_rate: 0.5
- crossover_rate: 0.7
- tournament_size: 3
- elite_count: 2
- max_depth: 4
- fitness_metric: sharpe
- seed: 23

## Best 個体

- name: `g48_i70`
- generation: 48
- fitness: **0.17103318328930817**
- fitness_finite: ✅
- stage_a_pass: ✅
- stage_b_pass: ❌
- stage_c_pass: ❌
- trade_count: 54
- total_pnl: 40140.0
- sharpe: 0.18903318328930815
- sortino: —
- calmar: —
- max_drawdown_pct: 0.0

**Archive 補足情報**:
- lane_id: tier1_EUR_JPY
- instrument: EUR_JPY
- fold_sign_ratio: 0.0000
- dsr: —
- ii_lite_pass: —
- n_nodes: 4
- active_clause: 1

## Stage 通過数

- 全 archive 行数: 5856
- Stage A pass: 2929
- Stage B pass: 22
- Stage C pass: 0
- ⚠ Stage B verdict is **statistically inconclusive** (`n_fold_effective < 3`).

## Lane 別落下分布

| lane_id | total | A | B | C |
|---------|-------|---|---|---|
| tier1_EUR_JPY | 5856 | 2929 | 22 | 0 |

## Pair 別落下分布

| instrument | total | A | B | C |
|------------|-------|---|---|---|
| EUR_JPY | 5856 | 2929 | 22 | 0 |

## active_clause / n_nodes 分布

- active_clause: n=5856, mean=0.9995, median=1.0000, std=0.0226, min=0, max=1
- n_nodes: n=5856, mean=3.1436, median=3.0000, std=0.8784, min=1, max=4

## mission_score 分布 (T043 / observation only)

> live_criteria 4 軸 (sharpe/total_pnl/max_drawdown/trade_count) の soft 合算スコア (幾何平均、[0.1, 1.0])。GA fitness や stage_c.passed には 影響しない (詳細: docs/alpha_factory/mission-score.md)。

- mission_score=計測対象 0 件 (Stage C base 評価で Sharpe を出した 個体が無いため未計測)

## fold_sign_ratio / dsr 分布

- fold_sign_ratio: n=2929, mean=0.0072, median=0.0000, std=0.0844, min=0.0000, max=1.0000
- dsr: n=0
- n_fold_effective (Stage A pass): n=2929, mean=0.2523, median=0, std=0.4778, min=0, max=2
- positive_fold_ratio_effective (Stage A pass): n=681, mean=0.6806, median=1.0000, std=0.4579, min=0.0000, max=1.0000

## Stage B failure reason 集計

- Stage A pass = 2929, Stage B pass = 22, failures = 2907 (primary_sum = 2907)

### Primary reason (先頭 reason、合計 = failures)

| reason | count |
|--------|------:|
| `no_folds` | 0 |
| `insufficient_folds` | 0 |
| `all_folds_unavailable` | 0 |
| `stage_b_window_underfilled` | 0 |
| `median_oos_sharpe<min` | 2664 |
| `positive_fold_ratio<min` | 243 |
| `stage_b_pre_flight_underfilled` | 0 |
| `unknown_reason` | 0 |
| `other` | 0 |

### Any reason incidence (全 reason、合計 >= failures)

| reason | count |
|--------|------:|
| `no_folds` | 0 |
| `insufficient_folds` | 0 |
| `all_folds_unavailable` | 2248 |
| `stage_b_window_underfilled` | 0 |
| `median_oos_sharpe<min` | 2664 |
| `positive_fold_ratio<min` | 2905 |
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
- trade_count=0 個体比率: 5.8% (342/5856)
- best 個体 trade_count: 54
- best 個体 feasibility: ✅

## Stage A provenance 分布 (T033 / sidecar)

> Stage A 落ち個体の `total_pnl_stage_a` 分布を可視化 (`reports/run-reports/run-{N}/diagnostics/stage_a_provenance.parquet`)。archive `total_pnl=0.0` が「Stage A 落ち = 投影仕様」「実 PnL=0」「コスト過大」のいずれかを切り分けるための観測指標 (詳細: docs/alpha_factory/diagnostics-sidecar.md)。

- sidecar 行数: 5856
- metric_stage 分布: stage_a_evaluated=2907, stage_a_only=2927, stage_b_evaluated=22
- (1) Stage A 落ち全体 `total_pnl_stage_a` 分布: n=2927, mean=-252704.4585, median=-50710.0000, std=390219.6617, min=-1008720.0000, max=24660.0000
- (2) Stage A 落ち かつ trade_count>0 の `total_pnl_stage_a` 分布 (n=2585): n=2585, mean=-286137.6983, median=-63730.0000, std=403547.5726, min=-1008720.0000, max=24660.0000
  - うち PnL=0 個体: 0 件 (取引したのに PnL=0 = Run 9 監査の対象観測)
- (3) Stage A 通過個体 `total_pnl_stage_a` 分布 (n=2929): n=2929, mean=17171.5568, median=16280.0000, std=9475.2423, min=-2770.0000, max=40440.0000

## Archive Top-5 個体一覧

> Best とは別物です。`fitness_pen` 単独降順。Best は (feasible, -violation, stage_b_pass, stage_c_feasible, stage_c_pass, stage_b_pass, stage_a_pass, fitness_pen) の辞書式 (v3.1_stage_b_priority, T046)。

| rank | name | gen | lane | instrument | fitness_pen | fitness_raw | A | B | C | trade_count | sharpe |
|-----:|------|----:|------|------------|------------:|------------:|---|---|---|----:|-------:|
| 1 | `g48_i70` | 48 | tier1_EUR_JPY | EUR_JPY | 0.1710 | 0.1890 | ✅ | ❌ | ❌ | 54 | — |
| 2 | `g49_i0` | 49 | tier1_EUR_JPY | EUR_JPY | 0.1710 | 0.1890 | ✅ | ❌ | ❌ | 54 | — |
| 3 | `g49_i53` | 49 | tier1_EUR_JPY | EUR_JPY | 0.1710 | 0.1890 | ✅ | ❌ | ❌ | 54 | — |
| 4 | `g50_i0` | 50 | tier1_EUR_JPY | EUR_JPY | 0.1710 | 0.1890 | ✅ | ❌ | ❌ | 54 | — |
| 5 | `g50_i1` | 50 | tier1_EUR_JPY | EUR_JPY | 0.1710 | 0.1890 | ✅ | ❌ | ❌ | 54 | — |

## 収束履歴

| gen | best_fitness |
|-----|--------------|
| 0 | 0.015449238780145872 |
| 1 | 0.057629647229293826 |
| 2 | -0.01870806106892877 |
| 3 | 0.004991631214854068 |
| 4 | 0.03966416734082372 |
| 5 | 0.03281773210728471 |
| 6 | 0.04662818476215118 |
| 7 | 0.05526726608135049 |
| 8 | 0.06385130737967791 |
| 9 | 0.08122974524132975 |
| 10 | 0.08245604226944779 |
| 11 | 0.08942142536564317 |
| 12 | 0.0826203448059969 |
| 13 | 0.08477084958105334 |
| 14 | 0.09233559177630961 |
| 15 | 0.09233559177630961 |
| 16 | 0.1001637694760704 |
| 17 | 0.10577079320629787 |
| 18 | 0.1001637694760704 |
| 19 | 0.1001637694760704 |
| 20 | 0.1001637694760704 |
| 21 | 0.1001637694760704 |
| 22 | 0.1001637694760704 |
| 23 | 0.1001637694760704 |
| 24 | 0.1001637694760704 |
| 25 | 0.1041657241335192 |
| 26 | 0.1041657241335192 |
| 27 | 0.1041657241335192 |
| 28 | 0.1041657241335192 |
| 29 | 0.1041657241335192 |
| 30 | 0.1041657241335192 |
| 31 | 0.14973464456089794 |
| 32 | 0.12510022672239893 |
| 33 | 0.12510022672239893 |
| 34 | 0.12510022672239893 |
| 35 | 0.12510022672239893 |
| 36 | 0.14666087306507564 |
| 37 | 0.14666087306507564 |
| 38 | 0.14666087306507564 |
| 39 | 0.14666087306507564 |
| 40 | 0.14666087306507564 |
| 41 | 0.15086251811356777 |
| 42 | 0.15086251811356777 |
| 43 | 0.1685018234692245 |
| 44 | 0.1685018234692245 |
| 45 | 0.1685018234692245 |
| 46 | 0.1685018234692245 |
| 47 | 0.1685018234692245 |
| 48 | 0.17103318328930817 |
| 49 | 0.17103318328930817 |
| 50 | 0.17103318328930817 |
| 51 | 0.17103318328930817 |
| 52 | 0.17103318328930817 |
| 53 | 0.17103318328930817 |
| 54 | 0.17103318328930817 |
| 55 | 0.17103318328930817 |
| 56 | 0.17103318328930817 |
| 57 | 0.17103318328930817 |
| 58 | 0.17103318328930817 |
| 59 | 0.17103318328930817 |
| 60 | 0.17103318328930817 |

## 分析

### analysis-claude.md

# RUN run_20260504_132300 (run-34) 分析（Claude 自己分析）

cycle 1/10 — improve-cycle 自走ループ起点。前 cycle (cycle 20) で停止していた状態を新規 10 cycle として再起動した最初の analyze。

## 前提差分

なし。

- archive Parquet 存在: `.cache/alpha_factory/runs/genomes_run_20260504_132300.parquet` (1.05 MB, 5856 rows)
- summary.json 存在: `reports/run-reports/run-34/summary.json` (run_id=run_20260504_132300, run_number=34)
- run-34.md は **未生成**（前 cycle Phase 5 中断）— 本サイクルでは触らない
- run_alpha_factory_state.json は zombie だったため stale 化済 (pid 38613 dead since 2026-04-26)
- cycle 1 の analyze 対象として run-34 archive を使用、Phase 4 で run-35 を新規生成予定

## 観察事実（Facts）

### Stage 通過数

| Stage | Pass 件数 | 全体比 |
|---|---|---|
| Stage A | 3096 / 5856 | 52.9% |
| Stage B | 26 / 5856 | 0.4% |
| Stage C | 0 / 5856 | **0.0%** |
| graduated | 0 | 0% |

過去 history (backup file 参照):
- cycle 1 (run-27): Stage A pass = 142 件、 best=0.0981 (calibrate loosen)
- cycle 3 (run-29): Stage A pass = 241 件、 best=0.0984 (calibrate disable)
- cycle 20 (run-32): best=0.110, Stage B pass = 2 件

run-34 は Stage A pass 3096 件と過去比で 13-22 倍多い。これは `population_size=96 × generations=61 = 5856` の試行に対する pass であり、過去 (population=48 × generations=20 = 960 程度) より絶対数は試行倍率で増えている。 pass **率** で比較すべきだが、ここでは触れず Fact として留める。

### Best fitness

| | name | gen | fitness_pen | fitness_raw | sharpe | trade_count | active_clause | n_nodes | total_pnl |
|---|---|---|---|---|---|---|---|---|---|
| run-34 best (Stage A only) | g54_i35 | 54 | 0.2265 | 0.2400 | 0.2400 | 67 | 1 | 3 | **0.0** |
| run-34 second | g22_i76 | 22 | 0.2665 | 0.2815 | NaN | 30 | 1 | 3 | — |

注: top-fitness は g22_i76 (0.267) だが、`best` SoT (summary.json) は g54_i35 (0.227)。これは `selection_score_schema=v3_1_stage_b_priority` で Stage B 優先選定をしているため、 fitness_pen 単独 ranking とは異なる。

**total_pnl = 0.0** が異常。trade_count=67、 trade-level Sharpe=0.24 で PnL が 0 は内部記録欠陥の疑い (trade Sharpe は trade ごとの正規化値で計算され、絶対 PnL は別経路で記録されている可能性)。

### Lane / instrument 分布

- instrument: **EUR_JPY 単一** (5856 / 5856)
- lane_id: **tier1_EUR_JPY 単一**
- cross_pair_runtime_mode: `skipped_single_instrument`

multi-instrument 化されていない。default.yaml に `instruments`/`lanes`/`tiers` キーは未設定 (CLI 引数で都度指定される設計)。

### Stage B 落下要因 (`stage_b_reason_codes`)

| reason code | 件数 |
|---|---|
| `median_oos_sharpe<min;positive_fold_ratio<min` | 2823 (48%) |
| `median_oos_sharpe<min;positive_fold_ratio<min;all_folds_unavailable` | 216 (3.7%) |
| `positive_fold_ratio<min` | 29 |
| `median_oos_sharpe<min` | 2 |

**Stage B 落下の主因は median_oos_sharpe < 0.05 と positive_fold_ratio < 0.6 の同時不達**。`all_folds_unavailable` 216 件は fold 評価そのものが機能しなかった個体群。

### Stage B pass 群 (n=26) の特徴

- positive_fold_ratio_effective: mean=0.787 (>= 0.6 OK)
- n_fold_effective: mean=7.88, median=8 (10 fold 中 8 程度有効)
- fold_sign_ratio: mean=0.413 (集団 0.178 より高め)
- n_nodes: mean=3.88 (集団 3.40 より少し複雑)
- active_clause: mean=1.00 (全員 single clause)

→ Stage B 通過個体は「fold で 80% positive、 8 fold 有効、複雑さ 4 ノード」が典型像。 だが Stage C で全滅。

### Stage C 全滅の周辺

- `dsr` 全行 NaN (集団 mean / median 不能)
- `ii_lite_pass` 0 件 (cross_pair shadow 全 skip)
- `mission_score` Stage C pass 群が空のため計算不能
- `archive_role` / `source_stage` カラム空 (recording 欠陥の疑い、別経路で確認要)

### dataset 期間

| 区間 | bars | 推定日数 |
|---|---|---|
| Stage A (window=60) | 86,400 | ~60日 |
| Stage B | 183,403 | 全期間 |
| holdout (Stage C) | 20,457 | ~14日相当 (60日設定だが bars=20457 と乖離) |

dataset: 2025-10-01 〜 2026-04-01 (6ヶ月)、 EUR_JPY M1 bars 183,403 (約 6 ヶ月分の 1 分足)。 `stage_c.holdout_days=60` 設定だが、 holdout bars が 20,457 (=14日相当) と乖離している可能性 (T087 disjoint 化との兼ね合い未検証)。

### GA 設定の乖離

| param | default.yaml | 実 RUN (summary) |
|---|---|---|
| population_size | 40 | **96** |
| generations | 15 | **60** |
| mutation_rate | 0.3 | **0.5** |
| seed | null | **23** |
| max_clause | (未指定) | **1** |
| units | (未指定) | **10000** |

CLI で大幅 override されている。 history backup の note によれば cycle 11-15 batch で `mut=0.5, seed=23` が「cycle 13 deterministic 再現」のために使われた。 cycle 21 (run-34) は同じ設定の再現延長。

`max_clause=1` は **active_clause=1 全員一致** の説明。 GA が clause 1 個に固定されている。

### live_criteria

| 指標 | 閾値 | run-34 best | Pass? |
|---|---|---|---|
| sharpe_min | ≥1.0 | 0.24 | ✗ (24% 達成) |
| total_pnl_min | ≥50,000 | 0.0 | ✗ (0% 達成、 PnL 計算欠陥疑) |
| max_drawdown_max | ≤0.2 | 0.0 | ✓ (達成、 但し PnL=0 故の trivial 達成) |
| trade_count_min | ≥50 | 67 | ✓ |
| trade_count_max | ≤5,000 | 67 | ✓ |

graduation_count=0、 live_pass=False。

## 解釈・推論（Interpretations）

### 仮説 H1: Stage C 評価層が壊れているか、あるいは Stage B→C で個体が劇的に劣化する構造的問題がある

**根拠**: Stage B pass 26 件 → Stage C pass 0 件 (dropout 100%)。 `mission_score` 観測ゼロ、 `dsr` 全 NaN は Stage C / 評価機構が機能していない強い兆候。

**反証可能性**: Stage C を逐個評価し、 Stage B pass 26 件が「実際は spread_stress / holdout で全員 negative になる」ならば evaluator は機能している (構造的 dropout)。 一方、 Stage C 評価が単に skip されている (run failure / silent error) ならば evaluator 不全。 → run_ga.py の Stage C evaluator 経路を Codex に独立検証依頼。

### 仮説 H2: max_clause=1 / max_depth=4 が信号生成空間を強く制約し、 Stage B sharpe 0.05 を超える個体が稀

**根拠**: best n_nodes=3-4、 active_clause=1 で固定。 Stage B 通過個体ですら mean trade-level Sharpe は計測不能 (NaN) 多数。 単純な clause 1 個では robust signal を作れない。

**反証可能性**: max_clause を 2-3 に拡張した RUN で Stage B pass 数が顕著増、 median_oos_sharpe 分布が右シフトすれば確証。 不変なら別要因 (data / cost model / fold 設計) が支配。 ただし「やたらに複雑な案を提案する」禁止に抵触するため、 拡張は段階的かつ正当化付きで実施。

### 仮説 H3: total_pnl=0.0 は recording 欠陥で、 戦略は実際に PnL を生成しているが summary に反映されていない

**根拠**: trade_count=67、 sharpe=0.24 (positive)、 max_drawdown=0.0。 Sharpe positive で trade あるのに PnL=0 は数学的に矛盾 (ただし `total_pnl` がここでは「未集計」or「単位変換」かもしれない)。

**反証可能性**: 個体 g54_i35 を local reproduce で評価し、 trade-by-trade PnL を実数で取れれば確証。 計算経路を確認すれば trade-level sharpe → 集計 PnL 変換の bug 有無が判明。

### 仮説 H4: cross_pair shadow 全 skip (single_instrument) が学習信号を弱めている

**根拠**: `ii_lite_pass=0`、 `cross_pair_runtime_mode=skipped_single_instrument`。 anchors 設計はあるが multi-instrument RUN でないと機能しない。

**反証可能性**: instruments=[EUR_JPY, USD_JPY, EUR_USD] でマルチ instrument RUN を実行し、 cross_pair shadow が pass 数を変えるか観察。 shadow がただ「無効化」されているだけなら全体構造的に問題なし、 弱い信号を補強する経路として機能していたなら multi 化で Stage B/C 通過数が改善するはず。

### 仮説 H5: Stage A 通過閾値 -0.0172 が緩く、 fitness 最大化と Stage B sharpe_min=0.05 の間に乖離がある

**根拠**: Stage A 52.9% 通過、 Stage B 0.4% 通過。 Stage A 通過後 Stage B 落下率 99.2% は「Stage A pass 個体の大半は Stage B robust ではない」を意味する。 calibrate disabled でこの乖離を放置している。

**反証可能性**: Stage A threshold を -0.05 (より厳しく) に上げて RUN し、 Stage A→B drop 率が改善するか観察。 改善するなら Stage A の selectivity 不足、 不変なら Stage B 自体が selectivity の要点。 ただし「閾値をいたずらに緩和してステージを飛ばす」「数値をよくしようとする改善」禁止に抵触しないよう、 Stage B 不変の場合は次の hypothesis に進む。

### 禁止事項違反の兆候 (C4 検知)

| 禁止事項 | 兆候の有無 | 注 |
|---|---|---|
| A/B/C 評価期間延長 | なし | dataset window が伸びていない |
| 見た目数値改善 | **疑い** | best fitness=0.227 は過去 cycle 13 (0.293) を下回る、 だが PnL=0 が見かけ Sharpe を作っている恐れ |
| GA ハック | **疑い** | seed=23 deterministic 再現で「成績が良い設定」を再演している可能性、 これは improve でなく観測 |
| 閾値緩和でステージ飛ばし | **疑い** | calibrate disable, threshold=-0.0172 緩い |
| 複雑案 | なし | max_clause=1 固定で逆に単純すぎる |
| 取引回数削減で見かけ改善 | **要確認** | trade_count=67 で min=50 ぎりぎり、 削減方向の圧力が働いていないか |
| オーバーナイト保有 | 未測定 | 保有時間分布を archive から取得できていない (要 trade-level 集計) |

→ 「PnL=0 で sharpe positive」「seed 固定 deterministic 再現で改善でなく観測になっている」「Stage A threshold が緩い」が同時発生。 これらは個別には説明可能だが、 同時発生は注意 signal。

## 次サイクル候補

cycle 1 (本サイクル) では以下を優先候補として plan-and-design に渡す:

1. **[Critical] Stage C 評価機構の健全性検証** — Stage B pass 26 → Stage C pass 0 の dropout 100% が「真に厳しい」のか「evaluator silent failure」のかを Codex 独立検証で切り分ける。 `dsr` 全 NaN / `mission_score` 不在も同じ調査範囲。
2. **[Critical] total_pnl=0.0 の recording 経路調査** — trade Sharpe positive / drawdown=0 で PnL=0 は矛盾。 `total_pnl` の集計経路 (trade-level → summary 集約) に bug の疑い。 確証されれば live_criteria の `total_pnl_min` 判定が常に false になる構造問題。
3. **[Warning] Stage A threshold -0.0172 の妥当性再評価** — Stage A→B drop 99.2% は Stage A 効果薄を示唆。 calibrate enabled に戻すか、 alpha 引き上げ (0.03→0.05) か、 ハイブリッド (Stage A 動的 + Stage B 固定) を検討。 ただし「閾値緩和でステージ飛ばし」禁止に抵触しないよう、 厳しくする方向のみ。
4. **[Warning] max_clause=1 / max_depth=4 制約の段階的緩和** — 単純な single clause で Stage B sharpe ≥0.05 が稀。 max_clause=2 で Stage B pass 数が増えるか実験 (1 cycle のみの A/B)。 「複雑案禁止」を遵守するため、 拡大は 2 まで限定し、 効果不明なら即 revert。
5. **[Warning] multi-instrument RUN へ復帰** — single_instrument で cross_pair shadow が完全 skip。 過去 cycle で `--instrument USD_JPY` 等で multi にしていた形跡あり。 anchors 設計を活かすには 2-3 instruments RUN が前提。 RUN cost が倍増するため elective。

**全体判定 (preliminary)**: **CONCERN** — Stage C dropout 100% と total_pnl=0.0 の 2 件は構造的問題の疑いがあり、 数値チューニングではなく原因解明が先。

### analysis-codex.md

# RUN run_20260504_132300 (run-34) 分析（Codex 独立分析）

## 前提差分（C4）
- 前提1（verified）: 本分析の定量根拠は、ユーザー提示の事実集計のみを使用。
- 前提2（verified）: 現行設計（T087）は Stage A/B/C の時系列 disjoint を要求。
- 前提3（差分）: 入力事実では `stage_b=183,403 (全期間)` かつ `stage_a=86,400` で、T087 契約と整合しない可能性がある。
- 前提4（差分）: `stage_c.holdout_days=60` に対し `holdout=20,457 bars` は量的乖離がある。

## 観察事実（Facts、 C6 Fact/Interpretation 分離遵守）
- Archive は `5856 (=96 × 61)` 行で、実行試行数は設定と整合。
- Stage 通過率: A `52.9%`、B `0.4%`、C `0.0%`、graduated `0`。
- Stage A 目標通過率 `0.15` に対し実績 `0.529`、`calibrate.enabled=False`。
- Stage B fail 主因は `median_oos_sharpe<min` と `positive_fold_ratio<min` の同時不達（2823件、+同 reason で all_folds_unavailable 216件）。
- Stage B pass 群は `n=26`、`positive_fold_ratio_effective mean=0.787`、`n_fold_effective median=8`。
- Best 個体は `sharpe=0.24`、`trade_count=67`、`total_pnl=0.0`、Stage B/C 不通過。
- top fitness_pen には `sharpe=NaN` 個体が含まれる。
- live_criteria は緩和されていない（`sharpe_min=1.0`, `total_pnl_min=50000` など）。
- `dsr` 全 NaN、`mission_score` 未計測、`archive_role/source_stage/fsp_*` は空。
- `cross_pair_runtime_mode=skipped_single_instrument`（single instrument 実行）。

## 解釈・推論（Interpretations、 C9 反証可能性付き）
### 仮説H1: 主ボトルネックは「Stage A の選別力不足」→「Stage B で大量脱落」
- 根拠: A通過率 52.9%（目標15%）に対し B通過率 0.4%、A通過後のB通過は約0.84%。
- 反証条件: 同一データ・同一seedで Stage A しきい値を厳格化し A通過率を目標帯へ寄せても、B通過“率/絶対数”が改善しなければ本仮説は棄却。

### 仮説H2: Stage B の fail は「閾値が厳しすぎる」より「候補品質不足」が主因
- 根拠: B fail reason が二重不達に集中。B pass 群では fold 有効数は確保されている。
- 反証条件: Stage A 通過群の `median_oos_sharpe`/`positive_fold_ratio` 分布が閾値近傍に密集していれば「閾値感度」が主因、遠く下方に偏るなら品質主因が支持。

### 仮説H3: `total_pnl=0.0` は計測/記録経路の異常シグナル
- 根拠: trade_count>0 かつ sharpe>0 と `total_pnl=0.0` の同時発生。
- 反証条件: 該当個体の取引明細再集計で実PNLが0に一致すれば異常ではない。不一致なら計測経路不整合が確定。

### 仮説H4: primitive 多様性は「退化」より「探索空間制約（max_clause=1）」の影響が大きい
- 根拠: `active_clause=1.00`（全員）で、構造上の多様性が限定。
- 反証条件: `max_clause` を 2 にした対照RUNで B通過の質/量が不変なら、多様性不足原因説は棄却。
- 注記（C7）: `n=26` のため因果断定は避ける。

### 仮説H5: cross-pair shadow skip は Phase2 設計上は妥当だが、頑健性監視の盲点を残す
- 根拠: single instrument 時 `skipped_single_instrument` は fail-close ではなく shadow非実施。
- 反証条件: multi-instrument で shadow を有効化しても指標差が実質ゼロなら、現運用の skip は実務上妥当。差が大きければ監視欠落。

## 次サイクル候補
- [Critical] Stage partition/holdout 実測監査: `stage_b` が Stage A と truly disjoint か、`holdout_days=60` と実 bars 乖離の理由を境界timestampで検証（契約違反なら即修正）。
- [Warning] Stage A 選別力の再調整実験: 「閾値厳格化のみ」で A→B 変換効率が改善するかを 1-run A/B テストで検証（緩和は禁止）。
- [Warning] `total_pnl` 計測経路の健全性チェック: best 個体の trade ledger から summary 集約までを突合し、0固定化/単位不整合を切り分ける。
- [Warning] cross-pair shadow の最小有効化検証: 2-3 pair の小規模 run で shadow 統計の情報価値を確認し、single-only運用の妥当性を判断。

## 全体判定
CONCERN  
Stage C 0% 自体より、`stage_b disjoint/holdout` 契約乖離疑いと `total_pnl=0.0` 異常シグナルが同時に存在し、閾値調整より先に計測・境界整合の検証が必要。

## Claude 分析との差分（最後に確認した結果）
- 同意点
  - Stage A 高通過/Stage B 低通過のミスマッチが主要課題。
  - `total_pnl=0.0` は優先調査対象。
  - cross-pair が single instrument で skip されている点は監視上の弱点。
- 反対意見・補足
  - `max_clause=1` を主因と断定するのは早い。現時点では「探索空間制約の寄与仮説」に留めるべき。
  - Stage C evaluator 不全を第一仮説に置く前に、T087 契約乖離（stage_b/holdout量）を先に反証すべき。
- Claude が見落としている可能性のある観点
  - `stage_b=全期間` と T087 disjoint 契約の不整合自体が、統計解釈の前提破壊点になっている可能性。
  - `holdout_days=60` と `holdout bars=20,457` の乖離は Stage C 全滅の説明変数になり得るため、まずデータ境界監査が必要。

### analysis-merged.md

# マージ分析: Run 34 (run_id=run_20260504_132300)

cycle 1/10 — improve-cycle 自走ループ起点。 Claude / Codex 両分析の統合。

## 合意事項（両者一致）

| # | 観察 | 含意 |
|---|------|------|
| M1 | Stage A 高通過 (52.9%) / Stage B 低通過 (0.4%) のミスマッチが主要課題 | A→B 変換効率の構造的問題 |
| M2 | Best 個体で `total_pnl=0.0` だが Sharpe positive — 計測 / 記録経路に異常の疑い | live_criteria `total_pnl_min=50000` 判定が常に false 化する構造 bug の可能性 |
| M3 | cross-pair shadow が single_instrument で skip されているのは設計通り、 ただし監視欠落 | multi-instrument RUN への復帰検討 (elective) |
| M4 | live_criteria は緩和されていない (sharpe≥1.0 / pnl≥50000) | 禁止事項 4「閾値緩和でステージ飛ばし」は **未発生** |
| M5 | Stage B fail 主因は `median_oos_sharpe<min` と `positive_fold_ratio<min` の同時不達 (2823件) | Stage B 評価層の閾値はそのままで、 候補品質が不足 |

## Claude 独自の発見

| # | 観察 | Codex はなぜ取り上げなかったか |
|---|------|---------------------------|
| L1 | seed=23 deterministic 再現で「改善でなく観測」になっている可能性 (cycle 13 と完全同値) | Codex は提示事実から再現性を直接観察できず、 仮説保留 |
| L2 | per_generation の median_fitness_pen / stage_X_pass_count などほぼ全行 null — 観測経路欠陥 | Codex は per_generation 抜粋を 5 件のみ受領、 全期間欠陥は判別困難 |
| L3 | Stage A 通過後の Stage B 落下率 99.2% から Stage A の selectivity 不足を仮説化 | Codex H1 と概ね同じだが、 Codex は「閾値緩和禁止」を強調し慎重 |
| L4 | dsr 全 NaN を「計算機構不全」と仮説化 | Codex も観察したが、 Stage C dropout 100% との因果に踏み込まず |

## Codex 独自の発見

| # | 観察 | Claude が見落とした要因 |
|---|------|---------------------|
| C1 | **Stage partition/holdout 契約乖離**: `stage_b=183,403 (全期間)` と T087 disjoint 契約の不整合 | Claude は dataset.bars=stage_b を fact として観察したが、 T087 契約 (Stage B = Stage A 期間を除外) との比較を行わず |
| C2 | **`holdout_days=60` vs `holdout bars=20,457` の量的乖離** が Stage C 全滅の説明変数になり得る | Claude は holdout=20,457 を観察したが「~14日相当」と注記したのみで Stage C dropout との接続を仮説化せず |
| C3 | max_clause=1 主因断定は早い ―「探索空間制約の寄与仮説」に留めるべき | Claude H2 は確かに「段階的緩和」と書いたが Critical/Warning 分けで Critical 寄りにした |
| C4 | Stage A 実通過率 0.529 vs target_pass_rate 0.15 の乖離。 calibrate.enabled=False で放置 | Claude L3 も近い指摘だが、 target_pass_rate との比較は明示せず |

## 矛盾・要議論

| # | Claude の見解 | Codex の見解 | 議論 |
|---|------------|------------|------|
| D1 | Stage C 評価機構の健全性 (dsr NaN / mission_score 不在) を Critical 1 | T087 partition/holdout 契約乖離を Critical 1 (Stage C dropout 100% 自体より境界整合が先) | Codex 優位 — partition 整合性が破綻していたら Stage C 解釈そのものが無意味。 Claude H1 (evaluator 不全) は partition 検証後の二次仮説として残す |
| D2 | max_clause=1 は Stage B 制約の主因 (Warning) | max_clause=1 主因断定は早い、 寄与仮説に留めるべき | Codex 優位 (n=26 で因果断定不可)。 Warning 維持だが「主因」表現を「寄与仮説」に訂正 |

## 統合改善提案（優先度順）

| # | 提案 | 優先度 | 出所 | target_metric | failure_mode | causal_path | falsification | success_criterion |
|---|------|--------|------|--------------|-------------|-----------|--------------|------------------|
| **P1** | **Stage partition/holdout 実測監査** | **Critical** | Codex C1 + Claude H1 | データ境界の正当性 (live_criteria 共通基盤) | `stage_b=183403=全期間` で T087 disjoint 契約と矛盾、 holdout bars=20457 が holdout_days=60 と乖離 | partition guard が validate しているが、 summary 表示の `bars_stage_b` 集計が contract と異なる経路を通っている恐れ。 もしくは guard 自体に bug | partition 境界 timestamp で実測し disjoint なら partition guard 健全、 contract 通り。 重複していたら **構造 bug** 確定で即修正 | partition が disjoint で stage_b の timestamp range が `[dataset.start, dataset.end - stage_a_window)` ⊂ Stage A 期間外を満たす |
| **P2** | **`total_pnl=0.0` 計測経路の健全性チェック** | **Critical** | Claude H3 + Codex H3 | `total_pnl_min=50000` 判定の正当性 | best 個体で trade_count=67, sharpe=0.24 (positive) なのに total_pnl=0.0 | trade-level Sharpe → summary 集約経路で PnL 単位変換 / 集計欠陥の疑い | best 個体 g54_i35 を local 再評価し trade ledger を集計、 0 ではない値が出れば計測経路 bug | 集計後 PnL > 0 (or 数学的に 0) で recording / display 整合 |
| **P3** | Stage A 選別力の再調整実験 (厳格化のみ) | Warning | Codex C4 + Claude H5 | Sharpe / Stage B pass rate | Stage A 通過率 52.9% (target 0.15 の 3.5 倍) で selectivity 不足 | 緩い Stage A で「真に良くない個体」が Stage B に流れ込み median_oos_sharpe を引き下げ | Stage A threshold を厳格化した RUN で Stage A→B 変換率が改善せず Stage B 絶対数も増えなければ Stage A 不要 (棄却) | Stage A pass rate ≈ 0.15 (target 一致) で Stage B pass 数が増加 or 不変 |
| **P4** | max_clause=1 制約の探索空間寄与仮説の小規模 A/B (寄与仮説に留める) | Warning | Claude H2 + Codex H4 | Stage B pass count | active_clause=1 全員一致、 探索空間が clause 1 個に制約 | 単一 clause では robust signal を作れず median_oos_sharpe ≥ 0.05 を超える個体が稀 | max_clause=2 の対照 RUN で Stage B pass の質 / 量が不変なら多様性不足説は **棄却** | max_clause=2 で Stage B pass 数の有意増加 + median_oos_sharpe 分布の右シフト |
| **P5** | cross-pair shadow の最小有効化検証 (multi-instrument 2-3 pair) | Warning | 両者一致 | cross_pair sharpe target / 監視充実 | single_instrument で cross_pair 全 skip。 anchors 設計が機能していない | shadow 統計の情報価値を確認 | multi で shadow 有効化しても指標差が実質ゼロなら現運用 skip は妥当 (棄却) | shadow が pass/fail 判定に有意な情報を加える (差 > ノイズ閾値) |

## 全体判定

**CONCERN** — Stage C 0% 自体より、 `stage_b disjoke/holdout` 契約乖離疑いと `total_pnl=0.0` 異常シグナルが同時に存在し、 閾値調整より先に **計測経路と境界整合の検証** が必要。 cycle 1 は P1 / P2 を Critical として最優先、 P3-P5 は Warning として次以降に回せる。

## 滞留 TODO 判断

Open / Conditional 共に 0 件。 棚卸し対象なし。

## Conditional 昇格チェック

Conditional 0 件。 評価対象なし。

