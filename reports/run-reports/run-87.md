# Run 87 — run_20260521_061439

**Generated**: 2026-05-21T06:14:39.986464+00:00
**dataset_epoch_id**: `epoch_20250401_20260219`
**Dataset**: EUR_JPY `2025-04-01T00:00:00+00:00` → `2026-02-19T00:00:00+00:00` (bars=328883)
  - bars_stage_a: 86400
  - bars_stage_b: 242483
  - bars_holdout: 60232
  - Stage B excludes Stage A window (stage_b: 2025-04-01T00:00:00+00:00 → 2025-11-24T15:52:00+00:00, stage_a: 2025-11-24T15:53:00+00:00 → 2026-02-18T23:59:00+00:00)

## 使命判定

🎯 **使命達成**

- ✅ **sharpe**: 3.9239233973063143 / threshold 1.0
- ✅ **total_pnl**: 60570.0 / threshold 50000.0
- ✅ **max_drawdown_pct**: 1.807316576284669 / threshold 20.0
- ✅ **trade_count**: 50 (range 50〜5000)

## KPI 分離 (cycle 23 C2)

- **graduation_count**: 0 (仕様: Stage C pass AND cross_pair pass。 single-instrument では構造的に 0 となる)
- **stage_c_pass_count**: 599 (= Stage C 単独通過数)
- **mission_candidate_count**: 599 (= live_criteria.all_pass 個体数、 cycle 23 C1 単位修正後の真値)

## GA 設定

- population_size: 96
- generations: 60
- mutation_rate: 0.5
- crossover_rate: 0.7
- tournament_size: 3
- elite_count: 2
- max_depth: 4
- fitness_metric: sharpe
- seed: 68

## Best 個体

- name: `g55_i41`
- generation: 55
- fitness: **0.13700883799714314**
- fitness_finite: ✅
- stage_a_pass: ✅
- stage_b_pass: ✅
- stage_c_pass: ✅
- trade_count: 50
- total_pnl: 60570.0
- sharpe: 0.15050883799714315
- sortino: —
- calmar: —
- max_drawdown_pct: 1.807316576284669

**Archive 補足情報**:
- lane_id: tier1_EUR_JPY
- instrument: EUR_JPY
- fold_sign_ratio: 0.3030
- dsr: —
- ii_lite_pass: ❌
- n_nodes: 3
- active_clause: 1

## Stage 通過数

- 全 archive 行数: 5856
- Stage A pass: 2495
- Stage B pass: 1970
- Stage C pass: 599

## trade_count 境界張り付き分析 (cycle 23 C4)

- Stage C 通過群: 599 件
- live_criteria.trade_count_min = 50

### trade_count 分布

| trade_count | count | pct |
|-------------|-------|-----|
| 50 ← min | 198 | 33.1% |
| 51 | 133 | 22.2% |
| 52 | 84 | 14.0% |
| 53 | 57 | 9.5% |
| 54 | 41 | 6.8% |
| 55 | 28 | 4.7% |
| 56 | 20 | 3.3% |
| 57 | 8 | 1.3% |
| 58 | 5 | 0.8% |
| 59 | 13 | 2.2% |
| 60 | 2 | 0.3% |
| 61 | 3 | 0.5% |
| 62 | 2 | 0.3% |
| 69 | 5 | 0.8% |

### 境界張り付き (==min) vs 非張り付き (>min) 比較

| 指標 | 境界張り付き (==min) | 非張り付き (>min) |
|------|---------------------|------------------|
| count | 198 | 401 |
| median total_pnl | 59840.0000 | 58690.0000 |
| median trade_sharpe_stage_c | 0.2706 | 0.2526 |
| median max_drawdown_pct | 1.8018 | 1.8090 |

## Lane 別落下分布

| lane_id | total | A | B | C |
|---------|-------|---|---|---|
| tier1_EUR_JPY | 5856 | 2495 | 1970 | 599 |

## Pair 別落下分布

| instrument | total | A | B | C |
|------------|-------|---|---|---|
| EUR_JPY | 5856 | 2495 | 1970 | 599 |

## active_clause / n_nodes 分布

- active_clause: n=5856, mean=1.3050, median=1.0000, std=0.4604, min=1, max=2
- n_nodes: n=5856, mean=3.9722, median=4.0000, std=1.6439, min=1, max=8

## mission_score 分布 (T043 / observation only)

> live_criteria 4 軸 (sharpe/total_pnl/max_drawdown/trade_count) の soft 合算スコア (幾何平均、[0.1, 1.0])。GA fitness や stage_c.passed には 影響しない (詳細: docs/alpha_factory/mission-score.md)。

- mission_score: n=1933, mean=0.9233, median=0.9516, std=0.0806, min=0.2831, max=0.9830
- best mission_score: **0.9830** (`g42_i25`, gen=42, instrument=EUR_JPY)

## fold_sign_ratio / dsr 分布

- fold_sign_ratio: n=2495, mean=0.2518, median=0.2424, std=0.0697, min=0.0000, max=0.4848
- dsr: n=0
- n_fold_effective (Stage A pass): n=2495, mean=32.1479, median=34, std=5.2206, min=0, max=34
- positive_fold_ratio_effective (Stage A pass): n=2494, mean=0.5718, median=0.6061, std=0.1276, min=0.0000, max=1.0000

## Stage B failure reason 集計

- Stage A pass = 2495, Stage B pass = 1970, failures = 525 (primary_sum = 525)

### Primary reason (先頭 reason、合計 = failures)

| reason | count |
|--------|------:|
| `no_folds` | 0 |
| `insufficient_folds` | 0 |
| `all_folds_unavailable` | 0 |
| `stage_b_window_underfilled` | 0 |
| `median_oos_sharpe<min` | 0 |
| `positive_fold_ratio<min` | 0 |
| `stage_b_pre_flight_underfilled` | 0 |
| `positive_fold_ratio_effective<min` | 214 |
| `median_oos_total_pnl<min` | 175 |
| `sum_oos_total_pnl<min` | 91 |
| `n_fold_effective_below_profit_safe_min` | 45 |
| `oos_total_pnl_unavailable` | 0 |
| `unknown_reason` | 0 |
| `other` | 0 |

### Any reason incidence (全 reason、合計 >= failures)

| reason | count |
|--------|------:|
| `no_folds` | 0 |
| `insufficient_folds` | 0 |
| `all_folds_unavailable` | 1 |
| `stage_b_window_underfilled` | 0 |
| `median_oos_sharpe<min` | 0 |
| `positive_fold_ratio<min` | 0 |
| `stage_b_pre_flight_underfilled` | 0 |
| `positive_fold_ratio_effective<min` | 214 |
| `median_oos_total_pnl<min` | 389 |
| `sum_oos_total_pnl<min` | 439 |
| `n_fold_effective_below_profit_safe_min` | 116 |
| `oos_total_pnl_unavailable` | 0 |
| `other` | 7 |

## Cross-pair shadow 集計

- runtime mode: enabled
- ii_lite_pass: True=0, False=1970, None=3886

## Graduation

- archive graduated: 0
- summary.graduation_count: 0

## Feasibility 集計

- selection_score schema: `v3_3_stage_b_feasible_priority`
- trade_count=0 個体比率: 2.5% (147/5856)
- best 個体 trade_count: 50
- best 個体 feasibility: ✅

## Stage A provenance 分布 (T033 / sidecar)

> Stage A 落ち個体の `total_pnl_stage_a` 分布を可視化 (`reports/run-reports/run-{N}/diagnostics/stage_a_provenance.parquet`)。archive `total_pnl=0.0` が「Stage A 落ち = 投影仕様」「実 PnL=0」「コスト過大」のいずれかを切り分けるための観測指標 (詳細: docs/alpha_factory/diagnostics-sidecar.md)。

- sidecar 行数: 5856
- metric_stage 分布: stage_a_evaluated=525, stage_a_only=3361, stage_b_evaluated=1371, stage_c_evaluated=599
- (1) Stage A 落ち全体 `total_pnl_stage_a` 分布: n=3361, mean=-165013.0110, median=-18820.0000, std=331377.2593, min=-1003870.0000, max=60440.0000
- (2) Stage A 落ち かつ trade_count>0 の `total_pnl_stage_a` 分布 (n=3214): n=3214, mean=-172560.2769, median=-20445.0000, std=336943.6067, min=-1003870.0000, max=60440.0000
  - うち PnL=0 個体: 1 件 (取引したのに PnL=0 = Run 9 監査の対象観測)
- (3) Stage A 通過個体 `total_pnl_stage_a` 分布 (n=2495): n=2495, mean=24959.0661, median=23280.0000, std=25784.0372, min=-1000250.0000, max=77610.0000

## Archive Top-5 個体一覧

> Best とは別物です。`fitness_pen` 単独降順。Best は (feasible, -violation, stage_b_pass_and_feasible, stage_b_pass, stage_c_feasible, stage_c_pass, stage_b_pass, stage_a_pass, fold_robust, fitness_pen) の辞書式 (v3.3_stage_b_feasible_priority, cycle 5 improve-cycle)。stage_b_pass_and_feasible = (Stage B 通過 ∧ entry_count_min 達成) を最優先要素 3 に昇格し、 cycle 4 で観測された「Stage B pass だがtrade_count<50 で feasible=0」 個体支配を解消。

| rank | name | gen | lane | instrument | fitness_pen | fitness_raw | A | B | C | trade_count | sharpe |
|-----:|------|----:|------|------------|------------:|------------:|---|---|---|----:|-------:|
| 1 | `g57_i36` | 57 | tier1_EUR_JPY | EUR_JPY | 0.2726 | 0.2856 | ✅ | ❌ | ❌ | 46 | — |
| 2 | `g48_i55` | 48 | tier1_EUR_JPY | EUR_JPY | 0.2455 | 0.2745 | ✅ | ❌ | ❌ | 39 | — |
| 3 | `g23_i20` | 23 | tier1_EUR_JPY | EUR_JPY | 0.2396 | 0.2691 | ✅ | ❌ | ❌ | 34 | — |
| 4 | `g47_i72` | 47 | tier1_EUR_JPY | EUR_JPY | 0.2394 | 0.2659 | ✅ | ❌ | ❌ | 43 | — |
| 5 | `g50_i81` | 50 | tier1_EUR_JPY | EUR_JPY | 0.2245 | 0.2590 | ✅ | ✅ | ❌ | 40 | — |

## 収束履歴

| gen | best_fitness |
|-----|--------------|
| 0 | 0.07391491636745944 |
| 1 | 0.07391491636745944 |
| 2 | 0.07391491636745944 |
| 3 | 0.1302730946292371 |
| 4 | 0.1302730946292371 |
| 5 | 0.14126771045037836 |
| 6 | 0.17080370960081656 |
| 7 | 0.12606712625715205 |
| 8 | 0.19953856821967528 |
| 9 | 0.12654553279760525 |
| 10 | 0.12852096528689758 |
| 11 | 0.10621879464572934 |
| 12 | 0.12051120676979955 |
| 13 | 0.12651120676979954 |
| 14 | 0.12313879336016702 |
| 15 | 0.09624150079552758 |
| 16 | 0.12649014267262654 |
| 17 | 0.1363744447285467 |
| 18 | 0.1328059170685459 |
| 19 | 0.12313879336016702 |
| 20 | 0.17436900205377437 |
| 21 | 0.14989716686026547 |
| 22 | 0.13401019164776765 |
| 23 | 0.2395914242915565 |
| 24 | 0.1598925640106723 |
| 25 | 0.2173553219030252 |
| 26 | 0.15971480686907638 |
| 27 | 0.15502551214075774 |
| 28 | 0.1528120457286967 |
| 29 | 0.15120255332911475 |
| 30 | 0.13459186350139227 |
| 31 | 0.15627016882715927 |
| 32 | 0.15120255332911475 |
| 33 | 0.13154028250196567 |
| 34 | 0.13154028250196567 |
| 35 | 0.20858015157807133 |
| 36 | 0.1704828167049769 |
| 37 | 0.19427524246205963 |
| 38 | 0.19780661781444622 |
| 39 | 0.15317597189460383 |
| 40 | 0.17829683101668434 |
| 41 | 0.17229683101668436 |
| 42 | 0.1504043417159948 |
| 43 | 0.13970255345314325 |
| 44 | 0.1367574547321876 |
| 45 | 0.17633943180745335 |
| 46 | 0.19878046089331777 |
| 47 | 0.23943008128108098 |
| 48 | 0.24545794131816262 |
| 49 | 0.2199541865708995 |
| 50 | 0.22446394816386214 |
| 51 | 0.18951683271236866 |
| 52 | 0.2236588222484299 |
| 53 | 0.18515100424422623 |
| 54 | 0.18515100424422623 |
| 55 | 0.191439697953859 |
| 56 | 0.18515100424422623 |
| 57 | 0.2726473946164336 |
| 58 | 0.1910272066744498 |
| 59 | 0.191394062380848 |
| 60 | 0.19405965589117688 |

## 分析

### analysis-claude.md

# RUN run_20260520_232522 (Run 86) 分析（Claude 自己分析）

## 前提差分
なし。R86 は T101 warmstart 適用 (seed=69, warmstart_ratio=0.1, motif=R85 archive) の検証 run。

## 観察事実（Facts）

### warmstart 検証結果（cycle 4 の主眼、成功）
- R84 (seed=69, warmstart なし): Stage A/B/C = 391/62/**0**、mission=0。
- R86 (seed=69, warmstart=0.1): Stage A/B/C = 2198/1630/**622**、**622 個体すべて mission-eligible** (total_pnl>=50k & trade_count>=50)、best g42_i51 live all_pass=True (sharpe4.16/pnl64160/dd1.81%/tc50)。
- Stage C 通過に g0_ws0 (=注入アンカー g51_i71)・g0_ws7 が直接含まれ、子孫 (g1_i0, g2_i0…) も大量繁殖。
- → **seed-locked だった mission (seed=68 のみ) を warmstart で seed=69 でも 622 個体再現 = mission の seed 非依存化に成功**。

### ★ graduation gap / cross-pair 汎化（cycle 5 の核心）
R86 の Stage C 通過 622 個体の cross-pair shadow:
| 列 | 値 |
|----|-----|
| ii_lite_pass | **全 622 件 None** (cross-pair ii-lite は shadow-only、gate 未配線) |
| canonical_gate_pass_c_shadow | **False 618 / True 4** (cross-pair 評価は走るが gate 未接続) |
| mission_signed_margin_c_shadow | **中央値 -1.0** (大半が cross-pair で負マージン) |
| persistence_score_shadow | 中央値 0.53 |
| graduated | **0** |

## 解釈・推論（Interpretations）

### 1. mission は「達成可能 + cost-robust + 再現可能」に到達したが、個体は in-sample 特化
4 サイクルで mission を巡る 3 つの性質を確立:
- 達成可能 (R83): live_criteria 全達成個体が出る。
- cost-robust (R85/P2): 真の spread×1.5 cost stress 下でも通過。
- 再現可能 (R86/warmstart): seed 非依存に保持・繁殖。
しかし R86 の 622 個体は **cross-pair で負マージン (med -1.0)** = EUR_JPY 同一 dataset への in-sample 特化。warmstart は in-sample winner を増やすが汎化はしない (warmstart は再現性であり汎化でないと設計時に明記済)。

### 2. 残るフロンティアは「汎化 (generalization)」であり、graduation=0 がそれを定量化している
graduation = Stage C pass AND cross-pair pass。cross-pair ii-lite が shadow-only (ii_lite_pass=None) のため graduation は構造的に発火不能。**しかし cross-pair 評価自体は走っており (canonical shadow: 618 False/4 True)、その結果は「622 個体中 cross-pair でまともなのは 4 個体のみ」を示す**。つまり in-sample mission 個体の大半は多ペアで通用しない。
- 反証可能性: cross-pair を hard gate 化して graduation>0 が出れば真の多ペア汎化個体が存在。0 のままなら EUR_JPY 過学習が確定的。

### 3. cross-pair ii-lite gate 昇格 (P3) は「汎化の壁を可視化・要求する」次の自然な構造介入
cross-pair 評価は既に走り shadow 結果を出している。これを ii_lite_pass / graduation に配線 (shadow→部分hard) すれば、graduation が真の多ペア汎化ゲートになる。
- リスク: 全面 hard 化は graduation 全滅 (現状 cross-pair まともなのは 4/622) → 段階的 (shadow 計測の可視化強化 → 部分 hard) が安全。
- 代替: OOS 検証 (Alpha Sieve、未移植) / 複数ペア同時学習。

### 4. 禁止事項違反の兆候
なし。warmstart は探索の足場 (評価不変)。cross-pair gate 昇格は汎化要求の厳格化 (緩和でない)。

## 次サイクル候補
- **[Critical] cross-pair ii-lite gate 昇格 (P3)**: cross-pair shadow 結果を ii_lite_pass / graduation に配線。段階的 (まず shadow 計測の確実な記録・可視化 → graduation 判定への部分接続)。全面 hard 化は全滅リスクのため避ける。これにより「mission 個体が多ペア汎化するか」を graduation で定量化。
- **[Warning] 複数ペア同時学習 / OOS 検証**: in-sample 特化を根本緩和する学習側の対処 (大規模、将来)。
- **[Warning] live_criteria 閾値引き上げ**: mission は in-sample で再現可能になったが、汎化未確認のため閾値引き上げは時期尚早 (汎化フロンティアが先)。

## 全体判定
**OK (warmstart 成功、ただし汎化が次フロンティア)** — mission は達成可能+cost-robust+再現可能に到達。R86 が示す残課題は cross-pair 汎化 (622 個体中 cross-pair まとも 4、margin med -1.0 = in-sample 特化)。次は cross-pair ii-lite gate 昇格 (P3) で graduation を真の汎化ゲートにし、汎化の壁を定量化する。

---

## 【重要訂正】graduation=0 の真因 = 単一銘柄実行 (cross-pair 構造的スキップ)

cross-pair 評価経路を確認した結果、graduation=0 の真因は「ii-lite が shadow-only 配線」ではなく **run が単一銘柄 (EUR_JPY) で cross-pair が構造的にスキップされている** ことだった (cross_pair_runtime_mode=skipped_single_instrument)。

検証:
- `scripts/alpha_factory/run_ga.py:1934` で `GraduationLane(pair_bars={}, pair_meta={})` が **空 dict でハードコード**。
- `run_ga.py:1939-1942`: `cross_pair_mode = "enabled" if graduation_lane.pair_bars else "skipped_single_instrument"` → pair_bars 空なので常に skipped。
- cross-pair ii-lite は anchor ペア (複数銘柄) の bars を必要とするが、現状 run_ga は GraduationLane に複数ペアデータを読み込んでいない。
- ∴ ii_lite_pass=None、cross_pair_result=None → graduation_criteria が常に False (swim_lane.py:427)。
- CrossPairConfig には mode="hard" が既に存在 (cross_pair.py:99) し graduation_criteria も配線済 (swim_lane.py:402-429)。**機構は揃っているが、複数ペアデータが供給されていない**だけ。
- R86 の canonical_gate_pass_c_shadow=True 4 件は cross-pair でなく canonical-5 不変条件の shadow (単一銘柄でも計算) で別物。

### 修正された cycle 5 方針 (P3 再定義)
汎化 (graduation) には **multi-pair データを GraduationLane.pair_bars に読み込む配線** が必須。これは ii_lite 配線でなく **data-loading + multi-pair 評価の有効化** であり、規模が大きい (anchor ペアの M1 bars ロード、24GB/6worker メモリ制約、Phase 2 統合 T102 と関連)。
- 段階案: (a) まず anchor ペア 1-2 個 (例 USD_JPY) の holdout bars のみ GraduationLane に供給し cross-pair を **shadow で実際に走らせる** (ii_lite_pass が None でなく True/False を出すようにする) → 汎化の壁を定量化。(b) その後 mode=hard で graduation を要求。
- リスク: メモリ (複数ペア M1)、Phase 2 統合との重複。Codex 合議で scope (anchor 数 / shadow 先行 / メモリ) を確定する。
- これは cycle 1 で Codex が「実装面積大・loop 停止リスク」と REJECT した P3 の本体。段階導入で低リスク化する。

### analysis-codex.md

1. Facts要約  
- Run 86 は warmstart(T101) で探索量が大幅改善し、`live_criteria all_pass=True` 個体を実際に獲得（再現性の到達点は確認）。  
- ただし `graduation=0`、かつ 622 Stage C 通過個体の `ii_lite_pass` は未配線で実質 `None`、cross-pair shadow で有効なのは 4/622 のみ。  
- 反証優先で見ると、「同一dataset内の再現」は成立したが「多ペア汎化」は未成立。  

2. 解釈（反証可能性つき）  
- (a) warmstart成功と in-sample特化  
仮説: 「warmstartは探索再現性を上げたが、主効果は in-sample 強化」。  
反証条件: 別ペア/ii-liteで pass 率が有意に上がる、または shadow margin 分布が負側集中から脱する。現状データは反証できず、仮説は妥当。  
- (b) 残フロンティア=汎化  
仮説: 「ボトルネックは Stage C 到達数ではなく cross-pair 汎化」。  
反証条件: cross-pair を hard 化しても十分な通過母集団が残る。現状 4/622 なので、残課題を汎化とみなすのが合理的。  
- (c) P3 gate昇格の妥当性/全滅回避  
仮説: 「次の構造介入は P3（ii-lite配線昇格）が最小リスクで正しい」。  
反証条件: 配線後に探索が即ゼロ化し、改善信号が得られない。よって段階設計（shadow→部分hard→全面hard判定）が必須で、全面hard即時適用は不適。  

3. 次サイクル候補  
- Critical: `ii_lite_pass` を正式配線し、`graduation = Stage C pass AND ii_lite_pass` をまず「部分hard」で運用（例: 上位Kまたは次世代の一定割合に ii-lite pass 必須）。全滅回避しつつ汎化方向へ探索圧を移す。  
- Warning: warmstart アンカー依存の多様性低下を監視（系譜集中率・ユニーク遺伝子率）。集中が進むなら注入比率固定のまま派生多様化のみ追加。  
- Warning: `n=4` の cross-pair 良好群で因果解釈しない（C7）。ペア別 breakdown と再現 run を先に取り、閾値引き上げ判断はその後。  

4. 全体判定  
**CONCERN**（達成可能性・再現性は前進、ただし mission 定義上の汎化ゲート未接続が主要リスク）

