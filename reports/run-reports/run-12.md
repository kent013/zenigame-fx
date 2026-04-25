# Run 12 — run_20260425_145811

**Generated**: 2026-04-25T14:58:11.122929+00:00
**Dataset**: EUR_JPY `2025-10-01T00:00:00+00:00` → `2026-04-01T00:00:00+00:00` (bars=183403)
  - bars_stage_a: 86400
  - bars_stage_b: 183403
  - bars_holdout: 20457

## 使命判定

未達

- ❌ **sharpe**: 0.05214504993538521 / threshold 1.0
- ❌ **total_pnl**: 7610.0 / threshold 50000.0
- ✅ **max_drawdown_pct**: 0.0 / threshold 20.0
- ✅ **trade_count**: 72 (range 50〜5000)

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

- name: `g58_i71`
- generation: 58
- fitness: **0.2744026322560356**
- fitness_finite: ✅
- stage_a_pass: ✅
- stage_b_pass: ❌
- stage_c_pass: ❌
- trade_count: 72
- total_pnl: 7610.0
- sharpe: 0.05214504993538521
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
- active_clause: 0

## Stage 通過数

- 全 archive 行数: 5856
- Stage A pass: 2349
- Stage B pass: 0
- Stage C pass: 0

## Lane 別落下分布

| lane_id | total | A | B | C |
|---------|-------|---|---|---|
| tier1_EUR_JPY | 5856 | 2349 | 0 | 0 |

## Pair 別落下分布

| instrument | total | A | B | C |
|------------|-------|---|---|---|
| EUR_JPY | 5856 | 2349 | 0 | 0 |

## active_clause / n_nodes 分布

- active_clause: n=5856, mean=0, median=0.0000, std=0.0000, min=0, max=0
- n_nodes: n=5856, mean=1.9740, median=2.0000, std=0.7579, min=1, max=4

## fold_sign_ratio / dsr 分布

- fold_sign_ratio: n=2349, mean=0.0000, median=0.0000, std=0.0000, min=0.0000, max=0.0000
- dsr: n=0

## Cross-pair shadow 集計

- runtime mode: skipped_single_instrument
- ii_lite_pass: True=0, False=0, None=5856

## Graduation

- archive graduated: 0
- summary.graduation_count: 0

## Feasibility 集計

- selection_score schema: `v2_feasibility`
- trade_count=0 個体比率: 4.9% (289/5856)
- best 個体 trade_count: 72
- best 個体 feasibility: ✅

## Archive Top-5 個体一覧

> Best とは別物です。`fitness_pen` 単独降順。Best は (feasible, -violation, stage_c_pass, stage_b_pass, stage_a_pass, fitness_pen) の辞書式 (v2_feasibility)。

| rank | name | gen | lane | instrument | fitness_pen | fitness_raw | A | B | C | trade_count | sharpe |
|-----:|------|----:|------|------------|------------:|------------:|---|---|---|----:|-------:|
| 1 | `g58_i71` | 58 | tier1_EUR_JPY | EUR_JPY | 0.2744 | 0.2849 | ✅ | ❌ | ❌ | 72 | — |
| 2 | `g59_i0` | 59 | tier1_EUR_JPY | EUR_JPY | 0.2744 | 0.2849 | ✅ | ❌ | ❌ | 72 | — |
| 3 | `g60_i0` | 60 | tier1_EUR_JPY | EUR_JPY | 0.2744 | 0.2849 | ✅ | ❌ | ❌ | 72 | — |
| 4 | `g60_i78` | 60 | tier1_EUR_JPY | EUR_JPY | 0.2744 | 0.2849 | ✅ | ❌ | ❌ | 72 | — |
| 5 | `g40_i42` | 40 | tier1_EUR_JPY | EUR_JPY | 0.2022 | 0.2127 | ✅ | ❌ | ❌ | 79 | — |

## 収束履歴

| gen | best_fitness |
|-----|--------------|
| 0 | 0.0 |
| 1 | 0.0 |
| 2 | 0.0 |
| 3 | 0.0 |
| 4 | 0.0015133227246339406 |
| 5 | 0.0015133227246339406 |
| 6 | 0.0015133227246339406 |
| 7 | 0.0015133227246339406 |
| 8 | 0.015335540797077567 |
| 9 | 0.09882569345721137 |
| 10 | 0.09882569345721137 |
| 11 | 0.09928502397120535 |
| 12 | 0.09928502397120535 |
| 13 | 0.09928502397120535 |
| 14 | 0.1139405694946358 |
| 15 | 0.1139405694946358 |
| 16 | 0.1139405694946358 |
| 17 | 0.1139405694946358 |
| 18 | 0.1139405694946358 |
| 19 | 0.1139405694946358 |
| 20 | 0.15784979309937902 |
| 21 | 0.15784979309937902 |
| 22 | 0.15784979309937902 |
| 23 | 0.15784979309937902 |
| 24 | 0.15784979309937902 |
| 25 | 0.15784979309937902 |
| 26 | 0.15784979309937902 |
| 27 | 0.15784979309937902 |
| 28 | 0.15784979309937902 |
| 29 | 0.15784979309937902 |
| 30 | 0.15784979309937902 |
| 31 | 0.15784979309937902 |
| 32 | 0.15784979309937902 |
| 33 | 0.15784979309937902 |
| 34 | 0.15784979309937902 |
| 35 | 0.15784979309937902 |
| 36 | 0.1854296285362178 |
| 37 | 0.1854296285362178 |
| 38 | 0.1854296285362178 |
| 39 | 0.1854296285362178 |
| 40 | 0.20221663221397648 |
| 41 | 0.20221663221397648 |
| 42 | 0.20221663221397648 |
| 43 | 0.20221663221397648 |
| 44 | 0.20221663221397648 |
| 45 | 0.20221663221397648 |
| 46 | 0.20221663221397648 |
| 47 | 0.20221663221397648 |
| 48 | 0.20221663221397648 |
| 49 | 0.20221663221397648 |
| 50 | 0.20221663221397648 |
| 51 | 0.20221663221397648 |
| 52 | 0.20221663221397648 |
| 53 | 0.20221663221397648 |
| 54 | 0.20221663221397648 |
| 55 | 0.20221663221397648 |
| 56 | 0.20221663221397648 |
| 57 | 0.20221663221397648 |
| 58 | 0.2744026322560356 |
| 59 | 0.2744026322560356 |
| 60 | 0.2744026322560356 |

## 分析

### analysis-claude.md

# Run 10 分析

**run_id**: `run_20260425_004002`
**generated_at**: 2026-04-25T00:40:13.448688+00:00

## 観察事実

### 使命判定 (live_criteria)

- ✅ sharpe: 18.491182265575507 / 閾値 1.0
- ❌ total_pnl: 18860.0 / 閾値 50000.0
- ✅ max_drawdown_pct: 0.0 / 閾値 20.0
- ❌ trade_count: 3 (許容 50〜5000)

### Best 個体

- name: `g60_i21`
- fitness (sharpe): 18.480682265575506
- trade_count: 3
- total_pnl: 18860.0
- sharpe: 18.491182265575507
- max_drawdown_pct: 0.0
- win_rate: None

### 収束状況

- 世代数: 61
- 初世代 best_fitness: 8.11512761939894
- 最終世代 best_fitness: 18.480682265575506
- Δfitness: 10.365554646176566
- plateau: False

### 前回 Run との比較

- best_fitness: 0 ↑ 18.480682265575506 (Δ=18.480682265575506)
- trade_count: 0 → 3

## 解釈

- 未達: total_pnl, trade_count。これらが次サイクルの改善ターゲット。
- 前回より改善。方向性は正しい可能性。

### analysis-codex.md

**観察事実（Facts）**
- Run `run_20260425_004002` の最良個体は `trade_count=3`, `total_pnl=18860`, `sharpe=18.49`, `max_drawdown_pct=0.0`。
- `live_criteria` は `sharpe` と `max_drawdown_pct` は達成、`total_pnl` と `trade_count` は未達。
- アーカイブ 5856 行中、`Stage A pass=4291`、`Stage B pass=0`、`Stage C pass=0`。
- `Stage B/C pass=0` は 60 世代を通じて継続。
- 世代進行で `Stage A pass` は `gen0:8 → gen5:47` と増加し、最終 fitness は `18.48`。
- 最良個体の構造は `n_nodes=2`, `active_clause=0`（最小複雑度側）。
- holdout は `37832 bars` あるが、B/C に到達した個体はない。
- `cross_pair` は `runtime=skipped_single_instrument`。

**解釈・推論（Interpretations, C9 falsification-first）**
- 前提（verified）
- `n(trades)=3` は C7 の基準（n<10 の相関/性能主張禁止）に該当。
- B/C 通過個体がゼロなので、B/C での一般化性能は未観測。

- 反証対象H1: 「高Sharpe（18.49）は戦略品質の改善を示す」
- 反証: `trade_count=3`、`total_pnl` 未達、B/C到達ゼロ。
- 判断: H1は棄却。高Sharpeは「低頻度サンプルでの見かけ値」の可能性が高い。

- 反証対象H2: 「GA進化で実運用条件に近づいている」
- 反証: A-pass は増えている一方、B-pass が全世代ゼロで固定。
- 判断: 「A最適化のみ進行、使命（live_criteria同時達成）には非収束」。ゲート間ミスマッチが主因候補。

- 反証対象H3: 「禁止事項違反はない」
- 反証: 直接の閾値緩和証拠は提示なし（この点は INCONCLUSIVE）。ただし `trade_count=3` での高Sharpe追従は禁止事項7の兆候と整合。
- 判断: 明示違反は未確定だが、運用上は「違反予備軍」の挙動。

- Stage B全滅の原因仮説（反証可能性付き）
1. 仮説A: Aの評価軸が「低頻度・低分散個体」を通しすぎる  
   - テスト: A-pass個体の `trade_count` 分布を抽出し、B-failとの対応を確認。
2. 仮説B: B窓（18mo）で regime 非適応（期間依存）  
   - テスト: B窓を分割し、月別/期間別で gross・cost・hit率の崩れ位置を特定。
3. 仮説C: 構造多様性不足（`n_nodes=2`, `active_clause=0` への収束）  
   - テスト: 世代ごとの構文多様度（ユニーク式数、primitive使用エントロピー）と A/B pass の関係を計測。
4. 仮説D: 単一銘柄運用で交差検証圧が不足  
   - テスト: shadow cross-pair を有効化したときの A→B 遷移率変化を比較。

- primitive偏在/多様性について
- `active_clause=0` と最小ノード収束は、「探索が単純式に偏っている」または「複雑式が早期淘汰される選択圧」のサイン。
- 現状データだけでは「単純式が本質的に優位」か「探索空間設計の欠陥」かは未確定（INCONCLUSIVE）。

**次サイクル候補**
- Critical（最優先）
1. `Stage A` に最低取引密度制約を導入（例: A通過条件に `trade_count` 下限、または frequency-aware fitness）し、A→B遷移可能な個体だけを残す。

- Warning
1. B失敗理由を分解ログ化（Sharpe要因、cost要因、trade不足要因を個体単位で保存）し、B全滅の内訳を可視化。
2. 構文多様性維持策（初期集団のprimitiveバランス、淘汰圧の緩和、重複式ペナルティ）を小さく導入。
3. cross_pair の shadow を実行有効化し、単一銘柄過適合の早期検知を追加。

**全体判定**
- `CRITICAL_DRIFT`

### analysis-merged.md

# マージ分析: Run 10

## 合意事項（両者一致）

- **Run 10 は CRITICAL_DRIFT 状態**: best 個体 trade_count=3 / sharpe=18.49 / total_pnl=18860（live_criteria の total_pnl・trade_count 未達）。
- **Stage A overpass + Stage B 全滅**: archive 5856 行中 A=4291 (73%) / B=0 / C=0 を 60 世代維持。Stage A gate が低頻度・低分散個体を素通しさせている。
- **best 構造の極端な単純化**: n_nodes=2, active_clause=0、最小複雑度に収束。多様性枯渇の兆候。
- **禁止事項 6（取引回数削減で見かけ改善）の予備軍**: trade_count=3 で sharpe を稼ぐ挙動は典型的な逸脱パターン。直接違反は未確定だが運用上は危険信号。

## Claude 独自の発見

- 前回 Run との比較で best_fitness は急上昇（0 → 18.48）。これは「進化が機能している」のではなく「Stage A 通過個体が少数の高スループット低取引数戦略に偏った」結果。
- holdout 37832 bars が用意されているのに Stage B/C に届いていない。

## Codex 独自の発見

- **H1 (高 Sharpe = 戦略品質改善)** を明確に棄却。
- **H2 (GA 進化で実運用条件に近づく)** も棄却。「A 最適化のみ進行、使命非収束」。ゲート間ミスマッチが主因。
- **構文多様性の計測**（generation 別 unique 式数 / primitive 使用エントロピー）が次のヒントになる。

## 矛盾・要議論

なし（両者の方向性は一致）。

## 統合改善提案（優先度順）

| # | 提案 | 優先度 | 出所 | target_metric | failure_mode | 期待効果 |
|---|------|--------|------|--------------|-------------|---------|
| 1 | Stage A に最低取引密度制約を導入（feasibility constraint で trade_count=0 個体を selection_score で淘汰） | Critical | 両者一致 | trade_count, total_pnl | trade_count=3 に集中、A→B 遷移率ゼロ | A 通過個体が「実用的な取引頻度」を持つよう構造的に保証、B-pass 出現を期待 |
| 2 | B 全滅理由の reason_codes 集計（個体単位で sharpe/cost/trade 不足の内訳を保存） | Critical | Codex | 観測可能性 | B 失敗の内訳が見えない | 次サイクル以降の根本原因特定が容易になる |
| 3 | active-clause / clause 発火カウンタの runtime 計測 | High | Codex Warning | 多様性 | active_clause=0 への収束 | 単純式偏重の早期検知 |

提案 1 は **TODO T031 (regime-participation-constraint Phase 1)** に直接対応。提案 2 は T035、提案 3 は T037 に対応。

