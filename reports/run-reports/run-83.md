# Run 83 — run_20260520_152204

**Generated**: 2026-05-20T15:23:24.911304+00:00
**dataset_epoch_id**: `epoch_20250401_20260219`
**Dataset**: EUR_JPY `2025-04-01T00:00:00+00:00` → `2026-02-19T00:00:00+00:00` (bars=328883)
  - bars_stage_a: 86400
  - bars_stage_b: 242483
  - bars_holdout: 60232
  - Stage B excludes Stage A window (stage_b: 2025-04-01T00:00:00+00:00 → 2025-11-24T15:52:00+00:00, stage_a: 2025-11-24T15:53:00+00:00 → 2026-02-18T23:59:00+00:00)

## 使命判定

🎯 **使命達成**

- ✅ **sharpe**: 4.240848212862226 / threshold 1.0
- ✅ **total_pnl**: 65210.0 / threshold 50000.0
- ✅ **max_drawdown_pct**: 1.4908469793175152 / threshold 20.0
- ✅ **trade_count**: 51 (range 50〜5000)

## KPI 分離 (cycle 23 C2)

- **graduation_count**: 0 (仕様: Stage C pass AND cross_pair pass。 single-instrument では構造的に 0 となる)
- **stage_c_pass_count**: 43 (= Stage C 単独通過数)
- **mission_candidate_count**: 43 (= live_criteria.all_pass 個体数、 cycle 23 C1 単位修正後の真値)

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

- name: `g51_i71`
- generation: 51
- fitness: **0.045408075289406075**
- fitness_finite: ✅
- stage_a_pass: ✅
- stage_b_pass: ✅
- stage_c_pass: ✅
- trade_count: 51
- total_pnl: 65210.0
- sharpe: 0.06490807528940608
- sortino: —
- calmar: —
- max_drawdown_pct: 1.4908469793175152

**Archive 補足情報**:
- lane_id: tier1_EUR_JPY
- instrument: EUR_JPY
- fold_sign_ratio: 0.3030
- dsr: —
- ii_lite_pass: —
- n_nodes: 4
- active_clause: 1

## Stage 通過数

- 全 archive 行数: 5856
- Stage A pass: 717
- Stage B pass: 436
- Stage C pass: 43

## trade_count 境界張り付き分析 (cycle 23 C4)

- Stage C 通過群: 43 件
- live_criteria.trade_count_min = 50

### trade_count 分布

| trade_count | count | pct |
|-------------|-------|-----|
| 51 | 21 | 48.8% |
| 54 | 1 | 2.3% |
| 55 | 5 | 11.6% |
| 56 | 7 | 16.3% |
| 58 | 5 | 11.6% |
| 70 | 4 | 9.3% |

### 境界張り付き (==min) vs 非張り付き (>min) 比較

| 指標 | 境界張り付き (==min) | 非張り付き (>min) |
|------|---------------------|------------------|
| count | 0 | 43 |
| median total_pnl | — | 51920.0000 |
| median trade_sharpe_stage_c | — | 0.2117 |
| median max_drawdown_pct | — | 2.4625 |

## Lane 別落下分布

| lane_id | total | A | B | C |
|---------|-------|---|---|---|
| tier1_EUR_JPY | 5856 | 717 | 436 | 43 |

## Pair 別落下分布

| instrument | total | A | B | C |
|------------|-------|---|---|---|
| EUR_JPY | 5856 | 717 | 436 | 43 |

## active_clause / n_nodes 分布

- active_clause: n=5856, mean=1.4998, median=2.0000, std=0.5007, min=0, max=2
- n_nodes: n=5856, mean=3.5495, median=3.0000, std=2.0037, min=1, max=8

## mission_score 分布 (T043 / observation only)

> live_criteria 4 軸 (sharpe/total_pnl/max_drawdown/trade_count) の soft 合算スコア (幾何平均、[0.1, 1.0])。GA fitness や stage_c.passed には 影響しない (詳細: docs/alpha_factory/mission-score.md)。

- mission_score: n=392, mean=0.8588, median=0.8890, std=0.1239, min=0.2801, max=0.9828
- best mission_score: **0.9828** (`g51_i71`, gen=51, instrument=EUR_JPY)

## fold_sign_ratio / dsr 分布

- fold_sign_ratio: n=717, mean=0.2202, median=0.2424, std=0.1146, min=0.0000, max=0.4242
- dsr: n=0
- n_fold_effective (Stage A pass): n=717, mean=27.7392, median=34, std=9.6746, min=0, max=34
- positive_fold_ratio_effective (Stage A pass): n=713, mean=0.4670, median=0.5588, std=0.2166, min=0.0000, max=1.0000

## Stage B failure reason 集計

- Stage A pass = 717, Stage B pass = 436, failures = 281 (primary_sum = 281)

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
| `positive_fold_ratio_effective<min` | 202 |
| `median_oos_total_pnl<min` | 47 |
| `sum_oos_total_pnl<min` | 6 |
| `n_fold_effective_below_profit_safe_min` | 26 |
| `oos_total_pnl_unavailable` | 0 |
| `unknown_reason` | 0 |
| `other` | 0 |

### Any reason incidence (全 reason、合計 >= failures)

| reason | count |
|--------|------:|
| `no_folds` | 0 |
| `insufficient_folds` | 0 |
| `all_folds_unavailable` | 4 |
| `stage_b_window_underfilled` | 0 |
| `median_oos_sharpe<min` | 0 |
| `positive_fold_ratio<min` | 0 |
| `stage_b_pre_flight_underfilled` | 0 |
| `positive_fold_ratio_effective<min` | 202 |
| `median_oos_total_pnl<min` | 249 |
| `sum_oos_total_pnl<min` | 229 |
| `n_fold_effective_below_profit_safe_min` | 178 |
| `oos_total_pnl_unavailable` | 0 |
| `other` | 16 |

## Cross-pair shadow 集計

- runtime mode: skipped_single_instrument
- ii_lite_pass: True=0, False=0, None=5856

## Graduation

- archive graduated: 0
- summary.graduation_count: 0

## Feasibility 集計

- selection_score schema: `v3_3_stage_b_feasible_priority`
- trade_count=0 個体比率: 1.9% (111/5856)
- best 個体 trade_count: 51
- best 個体 feasibility: ✅

## Stage A provenance 分布 (T033 / sidecar)

> Stage A 落ち個体の `total_pnl_stage_a` 分布を可視化 (`reports/run-reports/run-{N}/diagnostics/stage_a_provenance.parquet`)。archive `total_pnl=0.0` が「Stage A 落ち = 投影仕様」「実 PnL=0」「コスト過大」のいずれかを切り分けるための観測指標 (詳細: docs/alpha_factory/diagnostics-sidecar.md)。

- sidecar 行数: 5856
- metric_stage 分布: stage_a_evaluated=281, stage_a_only=5139, stage_b_evaluated=393, stage_c_evaluated=43
- (1) Stage A 落ち全体 `total_pnl_stage_a` 分布: n=5139, mean=-615789.3520, median=-1000050.0000, std=463603.0421, min=-1006180.0000, max=50980.0000
- (2) Stage A 落ち かつ trade_count>0 の `total_pnl_stage_a` 分布 (n=5028): n=5028, mean=-629383.7470, median=-1000050.0000, std=459474.1724, min=-1006180.0000, max=50980.0000
  - うち PnL=0 個体: 0 件 (取引したのに PnL=0 = Run 9 監査の対象観測)
- (3) Stage A 通過個体 `total_pnl_stage_a` 分布 (n=717): n=717, mean=860.9066, median=18790.0000, std=136850.9946, min=-1000890.0000, max=75770.0000

## Archive Top-5 個体一覧

> Best とは別物です。`fitness_pen` 単独降順。Best は (feasible, -violation, stage_b_pass_and_feasible, stage_b_pass, stage_c_feasible, stage_c_pass, stage_b_pass, stage_a_pass, fold_robust, fitness_pen) の辞書式 (v3.3_stage_b_feasible_priority, cycle 5 improve-cycle)。stage_b_pass_and_feasible = (Stage B 通過 ∧ entry_count_min 達成) を最優先要素 3 に昇格し、 cycle 4 で観測された「Stage B pass だがtrade_count<50 で feasible=0」 個体支配を解消。

| rank | name | gen | lane | instrument | fitness_pen | fitness_raw | A | B | C | trade_count | sharpe |
|-----:|------|----:|------|------------|------------:|------------:|---|---|---|----:|-------:|
| 1 | `g40_i44` | 40 | tier1_EUR_JPY | EUR_JPY | 0.2635 | 0.2900 | ✅ | ❌ | ❌ | 43 | — |
| 2 | `g55_i23` | 55 | tier1_EUR_JPY | EUR_JPY | 0.2069 | 0.2454 | ✅ | ✅ | ❌ | 46 | — |
| 3 | `g47_i56` | 47 | tier1_EUR_JPY | EUR_JPY | 0.1985 | 0.2195 | ✅ | ✅ | ❌ | 26 | — |
| 4 | `g41_i27` | 41 | tier1_EUR_JPY | EUR_JPY | 0.1908 | 0.2118 | ✅ | ✅ | ❌ | 29 | — |
| 5 | `g42_i0` | 42 | tier1_EUR_JPY | EUR_JPY | 0.1908 | 0.2118 | ✅ | ✅ | ❌ | 29 | — |

## 収束履歴

| gen | best_fitness |
|-----|--------------|
| 0 | -0.009480436887098855 |
| 1 | -0.009480436887098855 |
| 2 | -0.009480436887098855 |
| 3 | -0.009480436887098855 |
| 4 | -0.009480436887098855 |
| 5 | -0.0016654135561131739 |
| 6 | -0.0016654135561131739 |
| 7 | -0.0016654135561131739 |
| 8 | -0.0016654135561131739 |
| 9 | -0.0016654135561131739 |
| 10 | -0.0016654135561131739 |
| 11 | -0.0016654135561131739 |
| 12 | -0.0016654135561131739 |
| 13 | -0.0016654135561131739 |
| 14 | 0.0029785279227919556 |
| 15 | 0.10331061005740243 |
| 16 | 0.10331061005740243 |
| 17 | 0.10331061005740243 |
| 18 | 0.10331061005740243 |
| 19 | 0.10331061005740243 |
| 20 | 0.10331061005740243 |
| 21 | 0.10331061005740243 |
| 22 | 0.10331061005740243 |
| 23 | 0.10331061005740243 |
| 24 | 0.10331061005740243 |
| 25 | 0.10331061005740243 |
| 26 | 0.10331061005740243 |
| 27 | 0.12057176171400047 |
| 28 | 0.12057176171400047 |
| 29 | 0.12057176171400047 |
| 30 | 0.12057176171400047 |
| 31 | 0.12057176171400047 |
| 32 | 0.12057176171400047 |
| 33 | 0.12057176171400047 |
| 34 | 0.12057176171400047 |
| 35 | 0.12554177631018876 |
| 36 | 0.10995853311540048 |
| 37 | 0.10995853311540048 |
| 38 | 0.10395853311540049 |
| 39 | 0.15963963600129588 |
| 40 | 0.26349130422327605 |
| 41 | 0.190833380801071 |
| 42 | 0.190833380801071 |
| 43 | 0.190833380801071 |
| 44 | 0.190833380801071 |
| 45 | 0.190833380801071 |
| 46 | 0.190833380801071 |
| 47 | 0.19850303720288806 |
| 48 | 0.10995853311540048 |
| 49 | 0.190833380801071 |
| 50 | 0.190833380801071 |
| 51 | 0.18011071830155956 |
| 52 | 0.08865994100444337 |
| 53 | 0.17797349156881137 |
| 54 | 0.1612243785552176 |
| 55 | 0.20686563003877387 |
| 56 | 0.10995853311540048 |
| 57 | 0.16994947893068685 |
| 58 | 0.16994947893068685 |
| 59 | 0.06901340572603823 |
| 60 | 0.10860833824615959 |

## 分析

### analysis-claude.md

# RUN run_20260514_211202 (Run 82) 分析（Claude 自己分析）

## 前提差分
なし（archive Parquet / summary.json / analyze_run.py / codex 全て疎通確認済み）。

## 観察事実（Facts）

### Stage 通過数（vs Run 81）
| Stage | Run 82 | Run 81 | 差分 |
|-------|--------|--------|------|
| A pass | 2687 | 2293 | +394 (+17%) |
| B pass | **941** | 718 | +223 (+31%) ← ループ累積で最多 |
| C pass | **0** | 0 | ±0 |
| graduated | 0 | 0 | ±0 |
| rows | 5856 | 5856 | — |

- stage_b_gate_kind: 全個体 `profit_safe_pfr`（seed=67）。

### Best fitness_pen 個体
- `g53_i19` @ tier1_EUR_JPY, gen 53
- fitness_pen=0.489 / fitness_raw=0.528（ループ内でも高水準）
- **stage_b_pass=False**（best は Stage B すら通過していない＝高 fitness と gate 通過が乖離）
- trade_count=41, total_pnl=+43240, max_dd=0.0%, n_fold=19, positive_fold_ratio=0.526
- active_clause=2, n_nodes=6（浅い）

### live_criteria（graduation 候補評価、summary.json）
| 指標 | value | threshold | pass |
|------|-------|-----------|------|
| sharpe (annualized) | 2.276 | 1.0 | ✅ |
| total_pnl | 4670 | 50000 | ❌ |
| max_drawdown_pct | 1.23% | 20% | ✅ |
| trade_count | 23 | 50–5000 | ❌ |

→ **2/4 pass**（sharpe・max_dd 達成、total_pnl・trade_count 未達）。cycle 23 の sharpe annualize 修正以降、sharpe は安定して pass するようになった。trade-level sharpe は 0.23。

### Stage B pass 群（n=941）の分布
| 指標 | min | median | max | mean | nan |
|------|-----|--------|-----|------|-----|
| trade_count | 11 | 34 | 112 | 39.8 | 0 |
| total_pnl | -33910 | **-1950** | 13080 | -1905 | 0 |
| trade_sharpe_stage_c | -0.361 | **-0.038** | 0.179 | -0.032 | 290 |
| trade_sharpe_stage_b | -0.056 | 0.045 | 0.114 | 0.042 | 0 |
| max_drawdown_pct | 1.04 | 1.69 | 4.50 | 1.75 | 0 |
| positive_fold_ratio_eff | 0.50 | 0.59 | 0.69 | 0.59 | 0 |
| n_fold_effective | 20 | 25 | 34 | 24.7 | 0 |
| mission_score | 0.273 | 0.310 | 0.690 | 0.352 | 290 |

- **Stage B 通過群の total_pnl 中央値が負（-1950）**。trade_sharpe_stage_c 中央値も負（-0.038）。
- B 通過群で trade_sharpe_stage_c 最大でも 0.179（top: g54_i8 / g56_i11, pnl ~13000, tc 32-34, pfr 0.61-0.68）。

### Stage C を阻む reason codes（全集団 fail 理由 top）
| reason | count |
|--------|-------|
| median_oos_total_pnl<min ; sum_oos_total_pnl<min | 621 |
| positive_fold_ratio<min ; median_oos_total_pnl<min ; sum_oos_total_pnl<min | 509 |
| sum_oos_total_pnl<min | 265 |
| n_fold_effective_below_profit_safe_min | 105 |

→ Stage C 不通過の支配的理由は **OOS total_pnl が負/不足**（median・sum とも min 割れ）。

### 構造分布
- active_clause（A pass）: 1→1570, 2→1117（3 以上ゼロ）。
- n_nodes（A pass）: min2 / median3 / max8（**全体に浅い**）。
- primitive 頻度（A pass sample 500）: P7=586・P2=585（ほぼ全個体が使用）、F4=107（最頻 signal）、M5/M3/F6… と tail に多様性あり。

### 未計測（C4 明示）
- 保有時間分布・セッション跨ぎ比率・ロング/ショート方向比率: archive に trade-level 情報なし → **not measured**（深掘りは analyze-genome-archive 整備後）。

## 解釈・推論（Interpretations）

### 1. 壁は「sharpe」から「total_pnl × trade_count」へ移動した
cycle 23 の sharpe annualize 修正が効き、Run 82 の best は sharpe 2.28 で楽々 pass。残る未達は **total_pnl=4670（目標 50000 の 9%）と trade_count=23（最低 50 の 46%）**。best 個体は「少数・高品質取引で高 sharpe だが、取引が少なすぎて絶対利益も足りない」過選択状態。
- 反証可能性: もし trade_count を増やした個体が total_pnl も比例増させるなら、両者はトレードオフでなく単に「取引機会の取り逃し」。逆に trade_count 増で sharpe/pnl が劣化するなら本質的トレードオフ。→ 次サイクルで trade_count と pnl の散布を確認すべき。

### 2. profit_safe_pfr は「fold 一貫性」を選ぶが「利益の大きさ」を選んでいない疑い
Stage B 通過 941 個体の **total_pnl 中央値が負（-1950）、trade_sharpe_stage_c 中央値も負**。つまり gate は positive_fold_ratio（≈0.59）と n_fold を満たす個体を通すが、OOS の絶対利益がマイナスの個体を大量に通過させている。これが Stage C（OOS pnl 正を要求）で全滅する直接原因。
- 反証可能性: もし B 通過群の pnl 負が「holdout 期間の regime 固有」なら別期間で正に転じるはず（Alpha Sieve OOS で検証可能）。gate 設計の問題なら期間に依らず負。

### 3. C=0 の根本は OOS profitability の欠如であり、fold robustness ではない
reason codes は `median_oos_total_pnl<min` / `sum_oos_total_pnl<min` が支配的。fold 数や正 fold 比率は満たせている（n_fold med 25, pfr med 0.59）。**「ばらつきは小さいが期待値が負」**の個体群。これは「分散を抑える」方向の改善（fold robustness 強化）では解決せず、「期待 PnL の符号と大きさ」を直接押し上げる構造介入が必要。

### 4. genome が浅い（n_nodes median 3, active_clause ≤2）
表現力が低く、イントラデイの「頻度高く・利益も出る」複合シグナルを捉えきれていない可能性。ただし複雑化は禁止事項 #5（やたら複雑な案）と緊張するため、深さペナルティの妥当性検証に留めるべき。

### 5. 禁止事項違反の兆候
- イントラデイ逸脱: 直接計測不可だが max_dd 1-4% と低く、保有暴走の兆候は薄い。
- 取引回数削減で見かけ改善（禁止 #6）: **むしろ逆方向の懸念**。best が trade_count 23 と少なく、これは「回数削減で sharpe を稼いでいる」可能性。live_criteria の trade_count 下限 50 がこれを正しく弾いている。
- live_criteria 緩和: 兆候なし。

## 次サイクル候補

- **[Critical] Stage B/C gate の「OOS profitability magnitude」要件強化**: profit_safe_pfr が median_oos_total_pnl 負の個体を 941 通過させている。Stage B 通過条件に「median OOS pnl > 正の下限」を課す（または fitness に OOS pnl 期待値の符号付き項を加える）ことで、Stage C で全滅する無益な探索を上流で削減し、選択圧を profitability に向ける。閾値緩和ではなく**正方向への要件追加**である点に注意（禁止 #4 非該当）。
- **[Warning] total_pnl × trade_count トレードオフの実証**: 次 Run で trade_count と total_pnl/sharpe の散布を確認し、「取引機会取り逃し」か「本質的トレードオフ」かを判定。前者なら entry 条件の緩和系 primitive を、後者なら fitness の pnl 項重み調整を検討。
- **[Warning] seed variance の低減**: 前ループ Run75-81 で Stage B pass が 827→0→0→458→175→718 と激しく変動。mission(Run75) は seed=60 lucky draw 依存。多seed 平均 or 評価の頑健化を検討（ただし評価コスト増に注意）。
- **[Warning] genome 深さペナルティの妥当性検証**: n_nodes median 3 と浅い。深さペナルティが過剰で表現力を削いでいないか確認（複雑化推奨ではなく、ペナルティ係数の健全性点検）。

## 全体判定
**CONCERN** — mission 未達（C=0）。Stage B は record 高（941）だが、その大半が OOS pnl 負であり gate が profitability を選べていない。sharpe の壁は越えたが total_pnl/trade_count が新たな壁。閾値緩和でなく gate/fitness の profitability 要件強化が次の打ち手。

---

## 【重要訂正】解釈 #2 の撤回 — gate は正しく動作している（Codex Critical 検証結果）

Codex の Critical 提言（B判定メトリクスと archive 集計メトリクスのスコープ一致監査）を実施した結果、**解釈 #2「profit_safe_pfr が OOS pnl 負の個体を通過させている」は誤りだったため撤回する**。

検証（Stage B pass n=941）:
| カラム | min | median | max | n<0 |
|--------|-----|--------|-----|-----|
| `total_pnl`（当初参照、誤）| -33910 | -1950 | 13080 | 581 |
| `median_oos_total_pnl`（gate 実使用）| 15 | 1280 | 3775 | **0** |
| `sum_oos_total_pnl`（gate 実使用）| 40 | 18250 | 74380 | **0** |

- profit_safe_pfr gate 定義（stage_gate.py:558-573）: ① positive_fold_ratio_effective>=0.4 ② median_oos_total_pnl>=0 ③ sum_oos_total_pnl>=0 ④ n_fold_effective>=20。
- **B 通過 941 個体で ②③ 違反はゼロ件**＝gate は設計通り「fold-CV OOS で黒字」の個体のみ通過させている。
- 当初参照した `total_pnl` は **Stage C holdout 窓（連続 60 日 + spread×1.5 stress, stage_c_holdout_days=60）の PnL** であり、スコープが異なる（Codex 仮説 B が正解）。

### 真のボトルネック（再定義）
**Stage B（dataset 全域の fold-CV OOS）では黒字・頑健なのに、Stage C（連続 60 日 holdout 窓 + spread×1.5 stress）では大半が赤字** という汎化ギャップ。

補強事実:
- B 通過群の trade_count: full_dataset 中央値 192 / stage_b 142 に対し、**Stage C holdout では 34**（短窓ゆえ取引機会が激減）。
- live 候補 best は holdout で trade_count=23（live 下限 50 未達）・total_pnl=4670（50000 未達）。
- これは「fold をまたいだ平均では黒字だが、特定の連続 60 日窓 + stress 下では負/低頻度」という、CV→holdout の典型的な汎化失敗。

→ 改善方向は「gate の profitability 要件強化」ではなく、**(a) Stage C 評価集団の質（lucky cluster 集中の緩和・novel cluster 機会確保）の改善、または (b) Stage B→C 汎化を予測する選択圧の付与**。

---

## TODO 由来の改善候補（standalone ルール適用）

Open テーブルに standalone タスクが存在（T100/T101/T102/T103）→ skill の standalone ルールにより最優先 standalone を **1 件のみ** 選定、incremental は混在させない。

候補比較:
| ID | タイトル | 優先度 | mode | ボトルネック関連性 | 実装リスク |
|----|---------|--------|------|------------------|-----------|
| **T100** | Stage C stratified allocation | Medium | standalone | **高**（Stage C 評価集団の lucky cluster 集中緩和＝今回の C ボトルネック直撃） | 低（config-gated opt-in、行動変更 1 RUN smoke） |
| T101 | Run71/63 warmstart | Low | standalone | 中（再現性検証） | 中 |
| T102 | Phase 2 統合 Step3-7 | Medium | standalone | 低（NSGA-II/CPPS 配線、大規模 5 sub-PR） | 高（loop 停止リスク） |
| T103 | primitive 拡張 30-50個 | Low | standalone | 中（探索空間拡大） | 高（大規模） |

選定: **T100**（Medium、Stage C ボトルネック直撃、既存詳細設計あり、config-gated で低リスク）。

| ID | target_metric | failure_mode | causal_path | falsification | success_criterion | 判定 |
|----|--------------|-------------|------------|---------------|-------------------|------|
| T100 | Total PnL / Trade Count（Stage C 通過個体の出現＝C>0） | Run82 で Stage B 941 通過も Stage C=0。Stage C 評価集団が fitness_pen 上位順で lucky cluster / 同型解に集中し、novel cluster が holdout 評価機会を得られていない疑い | Stage C 評価集団を persistence decile × primitive cluster で層別抽出 → 同型解集中を緩和 → novel cluster が holdout 評価を受ける → holdout で黒字・高頻度な個体が C を通過する確率上昇 | stratified 化後も Stage C pass=0 のまま、かつ評価集団の primitive cluster 多様性が legacy と有意差なし | 次 Run で Stage C 評価集団の cluster 多様性が向上し、かつ Stage C pass>0 または holdout total_pnl 分布の上方シフトが観測される | **REJECT（design-stale）** |

### T100 を design-stale として却下（競合チェック結果）
`swim_lane.py:665-694` を確認した結果、**Stage C 評価には top-N cap / 選定段階が存在せず、Stage B 通過個体は全件その場で `evaluate_stage_c` される**（Run82 では 941 件全件評価）。T100 の設計前提（「Stage C 評価集団は Stage B pass 順で集約され lucky 個体が混入」）は現行コードに対し成立しない。層別化すべき選定対象が無いため、T100 はそのままでは実装不能。

→ `skip_todos: [{id: T100, reason: "design stale: Stage C は全 B-pass を無 cap 評価。stratify する選定段階が現行コードに存在しない"}]`。
→ **cycle_focus を `ga_improvements` に切替**。core bottleneck（B fold-CV → C 60日holdout+stress の汎化ギャップ）に対する GA 構造改善を Codex 合議で 1 つに収束させる。

### analysis-codex.md

## 1. 観察事実（Facts）
- Run 82（seed=67, EUR_JPY, pop=96, gens=60, stage_b_gate=profit_safe_pfr）で `Stage A=2687`, `Stage B=941`, `Stage C=0`, `graduated=0`。
- Stage 通過数は Run81 比で `A +17%`, `B +31%`、ただし `C は 0 のまま`。
- best fitness_pen 個体 `g53_i19` は `fitness_pen=0.489`, `fitness_raw=0.528`, `stage_b_pass=False`, `trade_count=41`, `total_pnl=+43240`。
- graduation 候補評価では `sharpe=2.276(annualized)` と `max_drawdown=1.23%` は閾値通過、`total_pnl=4670<50000` と `trade_count=23<50` は未達（2/4）。
- Stage B 通過群（n=941）の分布は `trade_count median=34`, `total_pnl median=-1950`, `trade_sharpe_stage_c median=-0.038`（NaN 290件）。
- Stage C 不通過 reason の上位は `median_oos_total_pnl<min` と `sum_oos_total_pnl<min` 系が多数。
- A pass 構造分布は `active_clause=1 or 2` のみ、`n_nodes median=3`。
- primitive 出現（A pass sample500）で `P7=586`, `P2=585` と偏在が大きい。
- Run54-82 では mission 達成は Run75 のみ。全 RUN で `DSR proxy pass=0`。

## 2. 解釈・推論（Interpretations, falsification-first）
### 仮説A: ボトルネックは Stage B ではなく「Stage B→C の目的不整合」
- 反証可能性: Stage B 通過群から Stage C へ進んだ個体の `median/sum_oos_total_pnl` が正であれば、この仮説は棄却。
- 現状評価: Stage C 不通過 reason が pnl 系に集中し、C通過0。Bの通過増加がC改善に接続しておらず、仮説は暫定支持。

### 仮説B: `profit_safe_pfr` が「見かけ上」安全でも、実質 OOS 負群を通している
- 反証可能性: Stage B 判定時に使う `median_oos_total_pnl` と集計で見ている `total_pnl` が同一スコープ・同一定義で、かつ通過群で非負が確認できれば棄却。
- 現状評価: B通過群 `total_pnl median=-1950` は gate 名称（profit_safe）と緊張関係。まず「指標スコープ不一致（B判定値と集計値が別物）」の監査が必要。

### 仮説C: 現在の主壁は `total_pnl` と `trade_count`（live_criteria）
- 反証可能性: Stage C 通過個体で `trade_count>=50` かつ `total_pnl>=50000` が一定数出れば棄却。
- 現状評価: 候補例が `trade_count=23`, `total_pnl=4670`。sharpe は通るため、収益量と約定密度不足が主要制約。

### 仮説D: 禁止事項6（取引回数削減で sharpe 稼ぎ）の過選択兆候がある
- 反証可能性: `trade_count` と `sharpe` の関係で、低回数帯が優位でない（もしくは高回数帯でも同等以上）なら棄却。
- 現状評価: live候補が低取引で sharpe 通過・回数未達。過選択の疑いは高いが、因果確定には分位比較が必要。

### 仮説E: P7/P2 偏在 + genome浅さが探索空間を狭め、OOS収益構造を掴めていない
- 反証可能性: primitive 多様化後も Stage C pnl 分布が改善しなければ棄却。
- 現状評価: `active_clause<=2`, `n_nodes median=3`, primitive偏在は「同型解の大量生成」を示唆。探索の実効多様性不足が疑われる。

## 3. 次サイクル候補（閾値緩和なし）
### Critical（1）
1. **Stage B 判定メトリクスと archive 集計メトリクスのスコープ一致監査を最優先で実施**
- 目的: `profit_safe_pfr` が実際に何を通しているかを同一定義で検証。
- 介入: B判定で使った値（fold単位の median/sum pnl, n_fold_effective, pfr）を個体単位で永続化し、report 側で同値を再集計。
- 成功条件: 「B通過=非負OOS pnl」という設計意図の真偽を機械的に判定可能にする。

### Warning（2-3）
1. **低取引sharpe偏重の構造抑制（閾値変更ではなく目的関数の正則化）**
- 例: fitness に「取引密度不足ペナルティ」または「時間帯カバレッジ項」を追加し、23トレード型の過選択を抑える。

2. **探索多様性の構造介入**
- 例: primitive 使用エントロピー監視、同型ゲノム重複抑制、浅い木への集中を防ぐ変異オペレータ（深さ上限緩和ではなく“偏在抑制”）。

3. **Stage C 失敗 reason の反証バッチ**
- 例: reason code 上位（median/sum pnl不足）に対し、失敗個体群で「どの時間帯・方向・コスト控除で崩れているか」を固定フォーマットで分解し、次世代の生成バイアスに反映。

## 4. 全体判定
**CRITICAL_DRIFT**  
- 理由: Stage B 通過の増加が Stage C/mission 達成に全く接続しておらず、目的整合性の崩れが示唆されるため。

### analysis-merged.md

# マージ分析: Run 82 (run_20260514_211202)

## 合意事項（両者一致）
- Stage A=2687 / B=941（record 高）/ C=0 / graduated=0。mission 未達。
- sharpe(annualized 2.276)は live 閾値を越えた（cycle 23 修正の効果）。**新たな壁は total_pnl(4670<50000) と trade_count(23<50)**。
- best fitness_pen 個体 g53_i19 は Stage B 不通過（高 fitness と gate 通過が乖離）。
- 禁止事項 6（取引回数削減で sharpe 稼ぎ）の過選択兆候: live 候補が trade_count 23 と低い。live_criteria の trade_count 下限 50 が正しく弾いている。

## 検証で確定した訂正（Codex Critical → Claude 撤回）
- **profit_safe_pfr gate は設計通り動作**。B 通過 941 個体の median_oos_total_pnl（中央値 1280）・sum_oos_total_pnl（中央値 18250）は全件 >=0。違反ゼロ。
- 当初 Claude が見た「total_pnl 中央値 -1950」は **Stage C holdout 窓（連続 60日 + spread×1.5 stress）の PnL** であり、Stage B 判定に使う fold-CV OOS 指標とはスコープが別物。Codex 仮説 B が正解。

## 真のボトルネック（合意・再定義）
**Stage B（dataset 全域の fold-CV OOS）では黒字・頑健なのに、Stage C（連続 60日 holdout 窓 + spread×1.5 stress）では全 941 件が赤字/低頻度で全滅。**

補強事実:
- B 通過群 trade_count: full_dataset 192 / stage_b 142 → **holdout 34**（短窓で取引機会激減）。
- holdout は dataset 末尾（直近）60日 → 「過去 fold で選抜 → 直近窓で失敗」= 温度差/regime drift + cost stress の複合。
- Stage C は全 B-pass を無 cap 評価（swim_lane.py:665-694）→ C=0 は「選抜の偏り」ではなく「誰も通らない」問題。

## Claude 独自の発見
- genome が浅い（n_nodes median 3、active_clause<=2）。primitive P7/P2 がほぼ全個体に出現（同型解大量生成の疑い）。
- T100（Stage C stratified allocation）は **design-stale**: Stage C に選定 cap が無いため層別化対象が存在しない。→ REJECT。

## Codex 独自の発見
- 仮説 D: 低取引 sharpe 偏重（過選択）の因果確定には trade_count×sharpe の分位比較が必要。
- 仮説 E: P7/P2 偏在 + genome 浅さ → 探索の実効多様性不足。
- 全体判定 CRITICAL_DRIFT（Stage B 増が C/mission に全く接続していない目的整合性の崩れ）。

## 矛盾・要議論
- 改善方向: (a) Stage C 評価集団の質改善（T100 系）は **無効と判明**。 (b) Stage B→C 汎化を予測する選択圧の付与 が残る主路線。
- どの構造レバーを引くか（cost stress の前倒し / recency-aware fold / holdout 整合の selection 項）は Codex 合議で 1 つに収束させる。

## 統合改善提案（優先度順、Codex 合議で確定）
| # | 提案 | 優先度 | 出所 | target_metric | failure_mode | 期待効果 |
|---|------|--------|------|--------------|-------------|---------|
| P1 | Stage B→C 汎化ギャップに対する **1 つの最小構造変更**（候補: ①Stage B に cost stress 前倒し ②直近期間整合の selection 項 ③holdout 整合 diagnostic）を Codex 合議で 1 つに収束 | Critical | Claude+Codex | Total PnL / Trade Count（C>0） | B 941 通過も C=0、holdout で全滅 | holdout で黒字・十分頻度の個体が Stage C を通過する |
| P2 | （保留）genome 浅さ・primitive 偏在の実効多様性監視 | Warning | Codex | 探索多様性 | P7/P2 偏在・n_nodes med3 | 同型解集中の緩和 |

## 次フェーズへの申し送り
- cycle_focus = `ga_improvements`（T100 は design-stale で REJECT、他 standalone は高リスク/低関連）。
- Codex 合議（B-2）で P1 を「1 つの反証可能仮説 + 1 つの最小変更」に収束させ、低リスク（loop 停止回避）を最優先する。

