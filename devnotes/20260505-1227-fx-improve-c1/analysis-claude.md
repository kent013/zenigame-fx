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
