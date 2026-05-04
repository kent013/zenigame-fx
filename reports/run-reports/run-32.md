# Run 32 — run_20260504_123921

**Generated**: 2026-05-04T12:39:21.470046+00:00
**dataset_epoch_id**: `epoch_20251001_20260401`
**Dataset**: EUR_JPY `2025-10-01T00:00:00+00:00` → `2026-04-01T00:00:00+00:00` (bars=183403)
  - bars_stage_a: 86400
  - bars_stage_b: 183403
  - bars_holdout: 20457

## 使命判定

未達

- ❌ **sharpe**: 0.12914332497546277 / threshold 1.0
- ❌ **total_pnl**: 0.0 / threshold 50000.0
- ✅ **max_drawdown_pct**: 0.0 / threshold 20.0
- ✅ **trade_count**: 53 (range 50〜5000)

## GA 設定

- population_size: 40
- generations: 15
- mutation_rate: 0.5
- crossover_rate: 0.7
- tournament_size: 3
- elite_count: 2
- max_depth: 4
- fitness_metric: sharpe
- seed: 23

## Best 個体

- name: `g15_i7`
- generation: 15
- fitness: **0.10964332497546277**
- fitness_finite: ✅
- stage_a_pass: ✅
- stage_b_pass: ❌
- stage_c_pass: ❌
- trade_count: 53
- total_pnl: 0.0
- sharpe: 0.12914332497546277
- sortino: —
- calmar: —
- max_drawdown_pct: 0.0

**Archive 補足情報**:
- lane_id: tier1_EUR_JPY
- instrument: EUR_JPY
- fold_sign_ratio: 0.1250
- dsr: —
- ii_lite_pass: —
- n_nodes: 4
- active_clause: 1

## Stage 通過数

- 全 archive 行数: 640
- Stage A pass: 99
- Stage B pass: 2
- Stage C pass: 0

## Lane 別落下分布

| lane_id | total | A | B | C |
|---------|-------|---|---|---|
| tier1_EUR_JPY | 640 | 99 | 2 | 0 |

## Pair 別落下分布

| instrument | total | A | B | C |
|------------|-------|---|---|---|
| EUR_JPY | 640 | 99 | 2 | 0 |

## active_clause / n_nodes 分布

- active_clause: n=640, mean=1, median=1.0000, std=0.0000, min=1, max=1
- n_nodes: n=640, mean=2.3062, median=2.0000, std=0.9937, min=1, max=4

## mission_score 分布 (T043 / observation only)

> live_criteria 4 軸 (sharpe/total_pnl/max_drawdown/trade_count) の soft 合算スコア (幾何平均、[0.1, 1.0])。GA fitness や stage_c.passed には 影響しない (詳細: docs/alpha_factory/mission-score.md)。

- mission_score=計測対象 0 件 (Stage C base 評価で Sharpe を出した 個体が無いため未計測)

## fold_sign_ratio / dsr 分布

- fold_sign_ratio: n=99, mean=0.3131, median=0.2500, std=0.2097, min=0.0000, max=0.8750
- dsr: n=0
- n_fold_effective (Stage A pass): n=99, mean=4.4444, median=4, std=1.9552, min=0, max=9
- positive_fold_ratio_effective (Stage A pass): n=97, mean=0.5125, median=0.5000, std=0.1538, min=0.0000, max=0.8333

## Stage B failure reason 集計

- Stage A pass = 99, Stage B pass = 2, failures = 97 (primary_sum = 97)

### Primary reason (先頭 reason、合計 = failures)

| reason | count |
|--------|------:|
| `no_folds` | 0 |
| `insufficient_folds` | 0 |
| `all_folds_unavailable` | 0 |
| `stage_b_window_underfilled` | 0 |
| `median_oos_sharpe<min` | 96 |
| `positive_fold_ratio<min` | 1 |
| `stage_b_pre_flight_underfilled` | 0 |
| `unknown_reason` | 0 |
| `other` | 0 |

### Any reason incidence (全 reason、合計 >= failures)

| reason | count |
|--------|------:|
| `no_folds` | 0 |
| `insufficient_folds` | 0 |
| `all_folds_unavailable` | 2 |
| `stage_b_window_underfilled` | 0 |
| `median_oos_sharpe<min` | 96 |
| `positive_fold_ratio<min` | 97 |
| `stage_b_pre_flight_underfilled` | 0 |
| `other` | 0 |

## Cross-pair shadow 集計

- runtime mode: skipped_single_instrument
- ii_lite_pass: True=0, False=0, None=640

## Graduation

- archive graduated: 0
- summary.graduation_count: 0

## Feasibility 集計

- selection_score schema: `v3_1_stage_b_priority`
- trade_count=0 個体比率: 2.3% (15/640)
- best 個体 trade_count: 53
- best 個体 feasibility: ✅

## Stage A provenance 分布 (T033 / sidecar)

> Stage A 落ち個体の `total_pnl_stage_a` 分布を可視化 (`reports/run-reports/run-{N}/diagnostics/stage_a_provenance.parquet`)。archive `total_pnl=0.0` が「Stage A 落ち = 投影仕様」「実 PnL=0」「コスト過大」のいずれかを切り分けるための観測指標 (詳細: docs/alpha_factory/diagnostics-sidecar.md)。

- sidecar 行数: 640
- metric_stage 分布: stage_a_evaluated=97, stage_a_only=541, stage_b_evaluated=2
- (1) Stage A 落ち全体 `total_pnl_stage_a` 分布: n=541, mean=-664228.3734, median=-1000070.0000, std=444124.5534, min=-1003220.0000, max=4190.0000
- (2) Stage A 落ち かつ trade_count>0 の `total_pnl_stage_a` 分布 (n=526): n=526, mean=-683170.2471, median=-1000080.0000, std=435810.7364, min=-1003220.0000, max=4190.0000
  - うち PnL=0 個体: 0 件 (取引したのに PnL=0 = Run 9 監査の対象観測)
- (3) Stage A 通過個体 `total_pnl_stage_a` 分布 (n=99): n=99, mean=-8243.4343, median=14050.0000, std=142614.7885, min=-1000240.0000, max=26580.0000

## Archive Top-5 個体一覧

> Best とは別物です。`fitness_pen` 単独降順。Best は (feasible, -violation, stage_b_pass, stage_c_feasible, stage_c_pass, stage_b_pass, stage_a_pass, fitness_pen) の辞書式 (v3.1_stage_b_priority, T046)。

| rank | name | gen | lane | instrument | fitness_pen | fitness_raw | A | B | C | trade_count | sharpe |
|-----:|------|----:|------|------------|------------:|------------:|---|---|---|----:|-------:|
| 1 | `g15_i7` | 15 | tier1_EUR_JPY | EUR_JPY | 0.1096 | 0.1291 | ✅ | ❌ | ❌ | 53 | — |
| 2 | `g12_i23` | 12 | tier1_EUR_JPY | EUR_JPY | 0.0922 | 0.1012 | ✅ | ❌ | ❌ | 68 | — |
| 3 | `g13_i0` | 13 | tier1_EUR_JPY | EUR_JPY | 0.0922 | 0.1012 | ✅ | ❌ | ❌ | 68 | — |
| 4 | `g13_i39` | 13 | tier1_EUR_JPY | EUR_JPY | 0.0922 | 0.1012 | ✅ | ❌ | ❌ | 68 | — |
| 5 | `g14_i0` | 14 | tier1_EUR_JPY | EUR_JPY | 0.0922 | 0.1012 | ✅ | ❌ | ❌ | 68 | — |

## 収束履歴

| gen | best_fitness |
|-----|--------------|
| 0 | 0.015449238780145872 |
| 1 | 0.015449238780145872 |
| 2 | -0.01870806106892877 |
| 3 | -0.01870806106892877 |
| 4 | -0.01870806106892877 |
| 5 | -0.01870806106892877 |
| 6 | -0.01870806106892877 |
| 7 | 0.0053274223193534725 |
| 8 | 0.06057645179905452 |
| 9 | 0.01745470245593319 |
| 10 | 0.053333119479138075 |
| 11 | 0.061198222260088 |
| 12 | 0.0921672280645699 |
| 13 | 0.0921672280645699 |
| 14 | 0.0921672280645699 |
| 15 | 0.10964332497546277 |

## 分析

### analysis-claude.md

# cycle 20 Phase 1 analyze-run (Run-46 + cycle 6-19 cross-run)

**作成日時**: 2026-05-04 21:25 JST
**前提**: cycle 1-5 正規 improve-cycle、 cycle 6-19 batch RUN (Codex 合議省略)
**主目的**: cycle 20 から正規 improve-cycle 復帰、 batch RUN の累積成果を活用

## 観察事実 (Facts、 cycle 6-19 全 14 RUN)

### F1. **Stage B 突破個体既に出現** (= cycle 13 で 2 個)

| cycle | run_id | seed | stage_b_pass | best_fp |
|---|---|---|---|---|
| 13 | run_20260504_111153 | 23 (mut=0.5) | **2** | 0.110 |
| 全他 | — | — | 0 | — |

**stage_b_pass=True 個体詳細** (cycle 13):
- g8_i33: trade_count=**16**, fitness_pen=0.061, sb=0.036, pos_fr=0.667
- g12_i17: trade_count=**17**, fitness_pen=0.002, sb=-0.006, pos_fr=0.667
- = trade_count <<< live_criteria.trade_count_min=50 (= mission 基準未達)
- ただし Stage B 判定 (median_oos_sharpe>=0.05 AND positive_fold_ratio>=0.60) は通過

### F2. archive 列 vs 判定 logic 不一致の疑い

cycle 7 (seed=7) AND 突破個体集計:
- 27 個体が `trade_sharpe_stage_b >= 0.05 AND positive_fold_ratio_effective >= 0.60` 満たす
- うち stage_b_pass=True: **0 個体**

= archive 列 `trade_sharpe_stage_b` と Stage B 判定で使う `median_oos_sharpe` が **異なる量** の可能性。 SSOT 監査必要。

### F3. archive fitness_pen max (= 視点違い) で global best 更新

- cycle 14 archive 内 fitness_pen max=**0.3934** (g14_i36, gen 14, trade_count=32) ← cycle 8 0.293 を超え
- ただし selection_score 由来 best (= summary.json) は fitness_pen=0.099 (g14_i32, trade_count=52)
- = archive 視点の高 fitness 個体は infeasible (= trade_count<50) で selection 下位

### F4. cycle 6-19 全体集計

- 累計 a_pass: 1849 個体
- AND 突破 (analytical = sb>=0.05 ∧ pos_fr>=0.60): 168 個体
- stage_b_pass=True (= 実判定): **2 個体のみ** (cycle 13)
- = analytical AND と stage_b_pass の **判定基準が異なる**

### F5. mut=0.5 vs mut=0.3 比較 (selection_score best fitness_pen 視点)

- mut=0.3 (10 RUN): best max=0.293 (cycle 8), positive 6/10
- mut=0.5 (5 RUN): best max=0.110 (cycle 13), positive 2/5
- = mut=0.5 で selection best は劣る、 ただし stage_b_pass 出現は mut=0.5 のみ

## 解釈 (Interpretations)

### I1 (Critical, 反証可能性 高): Stage B 判定 SSOT 監査が必須

archive `trade_sharpe_stage_b` (max=0.10-0.21) と Stage B 判定 `median_oos_sharpe>=0.05` の **対応関係が不明確**:
- 168 個体 analytical AND を満たすのに stage_b_pass=False
- 別経路 cycle 13 の 2 個体は stage_b_pass=True だが trade_count<<50

**反証**: src/alpha_factory/stage_gate.py:1140-1180 の Stage B 判定実装を Read で確認。 `oos_sharpes_imputed` と archive `trade_sharpe_stage_b` の関係を SSOT で確定。

### I2 (Warning): mut=0.5 で stage_b_pass 出現は偶然 or signal

cycle 13 の 2 個体は trade_count=16/17 = mut=0.5 で **小 genome / low-trade individual** が生まれやすい?
- mut=0.5 = 高 mutation = small / atypical genome 生成多
- low-trade で fold 内 trade も少 → 一部 fold で sharpe 高 (= median 押上げ) → stage_b_pass

= **「low-trade attractor で偶然 Stage B 突破」 = 禁止事項 #6 違反の構造**

### I3 (Notable): live_criteria 整合性

cycle 13 stage_b_pass=2 個体は trade_count=16/17 << live_criteria.trade_count_min=50:
- = Stage B 通過しても mission 達成不可
- = Stage C 評価で live_criteria.trade_count_min<50 で reject 想定

## 次サイクル候補 (cycle 20+)

### [Critical] Stage B 判定 SSOT 監査 (= I1 対応)

stage_gate.py:1140-1180 (= evaluate_stage_b) と archive 列 (`trade_sharpe_stage_b`, `median_oos_sharpe`, `positive_fold_ratio_effective`) の対応関係を Codex C1 で監査。

具体的に:
- `oos_sharpes_imputed` の median = archive `trade_sharpe_stage_b` か?
- `positive_ratio` の母数 (n_fold) = archive `positive_fold_ratio_effective` (effective fold のみ) か?
- 不一致なら archive 列の意味を明確化、 もし bug なら fix

### [Warning] cycle 13 stage_b_pass 個体の構造分析

trade_count=16/17 で stage_b_pass=True の構造的原因。 fold-level sharpe の median が 0.05 を超えた条件 (= fold 数効果?) を確認。

## 全体判定: **PROGRESSING**

cycle 6-19 batch RUN で:
- selection_score best fitness_pen 累計 max=0.293 (cycle 8)
- archive 視点 fitness_pen max=0.393 (cycle 14)
- AND 突破 (analytical) 168 個体
- stage_b_pass=True 2 個体 (= live_criteria 未達)

= 「Stage B AND 同時達成」 は構造的に到達可能、 ただし **Stage B 判定基準と archive 列の対応関係が不明瞭** = 監査が次の打ち手。

### analysis-codex.md

前提 (verified / inconclusive)
- Verified: Stage B 判定は `median_oos_sharpe` と `positive_fold_ratio`（全 fold 母数）で行われ、`trade_sharpe_stage_b` は判定 SSOT ではない。根拠: [stage_gate.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/stage_gate.py:1163), [stage_gate.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/stage_gate.py:1171), [archive.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/archive.py:527)
- Verified: `positive_fold_ratio_effective` は unavailable fold を除外した観測値で、判定に使う `positive_fold_ratio`（全 fold）とは別。根拠: [stage_gate.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/stage_gate.py:1164), [stage_gate.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/stage_gate.py:1166)
- Verified: cycle 13 相当 run (`run_20260504_111153`) は `analytical_AND=29` に対し `stage_b_pass=2` を再現。29個の失敗 reason は 28個が `median_oos_sharpe<min;positive_fold_ratio<min`、1個が `positive_fold_ratio<min`（実測）。
- Verified: stage_b_pass=2 個体 (`g8_i33`, `g12_i17`) は archive 上 `trade_count=16/17`, `stage_c_pass=False`, `trade_sharpe_stage_c=None` で live_criteria 未達。
- Inconclusive: cycle 6-19 の14 RUN全体をローカル生成物だけで再集計するための seed/run 対応メタが一部欠損（batch run の report 不在）。ただしユーザー提示集計と cycle13 実測は整合。
- Verified(ドリフト): `genome-archive-schema.md` の一部記述は現実装(T044)とズレあり（上書き説明が旧仕様）。根拠: [genome-archive-schema.md](/Users/ishitoya/repository/zenigame-fx/docs/alpha_factory/concepts/genome-archive-schema.md:35), [archive.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/archive.py:534)

Facts / Interpretations
- Fact (Q1): `trade_sharpe_stage_b` は Stage B IS 全期間 Sharpe の観測列で、判定に使う `median_oos_sharpe` とは別定義。
- Interpretation (Q1): (a) 設計意図の可能性が高い。少なくとも実装・テストはその前提で一貫している。根拠: [test_archive.py](/Users/ishitoya/repository/zenigame-fx/tests/alpha_factory/test_archive.py:343)

- Fact (Q2): `n_fold_effective=9` は「imputed 異常」ではなく、unavailable=0 を意味する。
- Fact (Q2): `trade_count=16/17` は Stage C 側値（B pass 後に C 評価で更新）であり、Stage B fold 判定の母数を直接示さない。根拠: [archive.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/archive.py:597)
- Interpretation (Q2): 主因は (c) Other。  
  - `trade_sharpe_stage_b` と `median_oos_sharpe` の取り違え  
  - `positive_fold_ratio_effective` と `positive_fold_ratio` の取り違え  
  の二重ミスマッチが F1/F2 の核心。

- Fact (Q3): 低 trade 個体が B を抜ける芽はある（少なくとも C で即 reject）。  
- Interpretation (Q3): 禁止事項 #6 の本質リスクは「見栄え改善」そのものより、「誤った代理指標で意思決定すること」。まず SSOT 同期が先。

反証可能性 (C9)
- 仮説 H0: 「F2差分はバグではなく、比較指標の不一致で説明可能」  
- 反証テスト:
1. `trade_sharpe_stage_b>=0.05 && positive_fold_ratio_effective>=0.60` 集合を抽出  
2. その集合の `stage_b_reason_codes` を集計  
3. `median_oos_sharpe<min` / `positive_fold_ratio<min` が主因なら H0 支持、そうでなければ H0 棄却  
- 現時点結果(cycle13): H0 支持（29中29が reason で説明可能、pass は2のみ）

次サイクル候補 (Critical 1 / Warning 2)
- Critical 1: 案A（Stage B 判定 SSOT監査）  
  - 具体: report/analyze で `median_oos_sharpe` と `positive_fold_ratio` を直接可視化し、`trade_sharpe_stage_b` との混同を禁止。
- Warning 1: `inspect_stage_b_folds.py` は fold Sharpe 再計算で `trade_count_min_for_sharpe` を使っており、Stage B本体の `fold_trade_count_min` と不一致。診断結果の解釈に注意。根拠: [inspect_stage_b_folds.py](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/inspect_stage_b_folds.py:123), [stage_gate.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/stage_gate.py:1046)
- Warning 2: archive schema ドキュメントの旧記述を放置すると、今後も同型誤読が再発。

全体判定
- CONCERN

Q4（1つに絞る）: 案A  
- 理由: 現在の主要リスクは性能不足より「判定SSOTと分析列の乖離認知」。ここを閉じずに案Bへ進むと、禁止事項 #2/#4/#6 に接触しやすい。

Q5（Falsification-first next experiment）
1. 次 cycle で `stage_b_pass` 全個体について `median_oos_sharpe`, `positive_fold_ratio`, `positive_fold_ratio_effective`, `trade_sharpe_stage_b` を同時出力  
2. 「B pass だが C trade_count_min 未達」の件数を毎 run 監査  
3. 件数が増えるなら初めて B/C 接続設計（案B）を検討、増えないなら現状維持で signal 強化に戻る

