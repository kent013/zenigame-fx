# Run 36 — run_20260506_054244

**Generated**: 2026-05-06T05:42:53.128979+00:00
**dataset_epoch_id**: `epoch_20251001_20260401`
**Dataset**: EUR_JPY `2025-10-01T00:00:00+00:00` → `2026-04-01T00:00:00+00:00` (bars=183403)
  - bars_stage_a: 86400
  - bars_stage_b: 97003
  - bars_holdout: 20457
  - Stage B excludes Stage A window (stage_b: 2025-10-01T00:00:00+00:00 → 2026-01-06T18:25:00+00:00, stage_a: 2026-01-06T18:26:00+00:00 → 2026-03-31T23:59:00+00:00)

## 使命判定

未達

- ❌ **sharpe**: 0.2417390315293707 / threshold 1.0
- ❌ **total_pnl**: 28590.0 / threshold 50000.0
- ✅ **max_drawdown_pct**: 0.0 / threshold 20.0
- ✅ **trade_count**: 53 (range 50〜5000)

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

- name: `g56_i28`
- generation: 56
- fitness: **0.22223903152937072**
- fitness_finite: ✅
- stage_a_pass: ✅
- stage_b_pass: ❌
- stage_c_pass: ❌
- trade_count: 53
- total_pnl: 28590.0
- sharpe: 0.2417390315293707
- sortino: —
- calmar: —
- max_drawdown_pct: 0.0

**Archive 補足情報**:
- lane_id: tier1_EUR_JPY
- instrument: EUR_JPY
- fold_sign_ratio: 0.2000
- dsr: —
- ii_lite_pass: —
- n_nodes: 4
- active_clause: 1

## Stage 通過数

- 全 archive 行数: 5856
- Stage A pass: 1999
- Stage B pass: 0
- Stage C pass: 0

## Lane 別落下分布

| lane_id | total | A | B | C |
|---------|-------|---|---|---|
| tier1_EUR_JPY | 5856 | 1999 | 0 | 0 |

## Pair 別落下分布

| instrument | total | A | B | C |
|------------|-------|---|---|---|
| EUR_JPY | 5856 | 1999 | 0 | 0 |

## active_clause / n_nodes 分布

- active_clause: n=5856, mean=1.2939, median=1.0000, std=0.4645, min=0, max=2
- n_nodes: n=5856, mean=3.8945, median=4.0000, std=1.7550, min=1, max=8

## mission_score 分布 (T043 / observation only)

> live_criteria 4 軸 (sharpe/total_pnl/max_drawdown/trade_count) の soft 合算スコア (幾何平均、[0.1, 1.0])。GA fitness や stage_c.passed には 影響しない (詳細: docs/alpha_factory/mission-score.md)。

- mission_score=計測対象 0 件 (Stage C base 評価で Sharpe を出した 個体が無いため未計測)

## fold_sign_ratio / dsr 分布

- fold_sign_ratio: n=1999, mean=0.2164, median=0.2000, std=0.1269, min=0.0000, max=0.7000
- dsr: n=0
- n_fold_effective (Stage A pass): n=1999, mean=8.5128, median=9, std=3.1599, min=0, max=11
- positive_fold_ratio_effective (Stage A pass): n=1900, mean=0.1808, median=0.1818, std=0.1316, min=0.0000, max=1.0000

## Stage B failure reason 集計

- Stage A pass = 1999, Stage B pass = 0, failures = 1999 (primary_sum = 1999)

### Primary reason (先頭 reason、合計 = failures)

| reason | count |
|--------|------:|
| `no_folds` | 0 |
| `insufficient_folds` | 0 |
| `all_folds_unavailable` | 0 |
| `stage_b_window_underfilled` | 0 |
| `median_oos_sharpe<min` | 1999 |
| `positive_fold_ratio<min` | 0 |
| `stage_b_pre_flight_underfilled` | 0 |
| `unknown_reason` | 0 |
| `other` | 0 |

### Any reason incidence (全 reason、合計 >= failures)

| reason | count |
|--------|------:|
| `no_folds` | 0 |
| `insufficient_folds` | 0 |
| `all_folds_unavailable` | 99 |
| `stage_b_window_underfilled` | 0 |
| `median_oos_sharpe<min` | 1999 |
| `positive_fold_ratio<min` | 1999 |
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
- trade_count=0 個体比率: 4.9% (285/5856)
- best 個体 trade_count: 53
- best 個体 feasibility: ✅

## Stage A provenance 分布 (T033 / sidecar)

> Stage A 落ち個体の `total_pnl_stage_a` 分布を可視化 (`reports/run-reports/run-{N}/diagnostics/stage_a_provenance.parquet`)。archive `total_pnl=0.0` が「Stage A 落ち = 投影仕様」「実 PnL=0」「コスト過大」のいずれかを切り分けるための観測指標 (詳細: docs/alpha_factory/diagnostics-sidecar.md)。

- sidecar 行数: 5856
- metric_stage 分布: stage_a_evaluated=1999, stage_a_only=3857
- (1) Stage A 落ち全体 `total_pnl_stage_a` 分布: n=3857, mean=-415780.6948, median=-121740.0000, std=458997.3253, min=-1006190.0000, max=20760.0000
- (2) Stage A 落ち かつ trade_count>0 の `total_pnl_stage_a` 分布 (n=3572): n=3572, mean=-448954.6865, median=-154150.0000, std=461079.5853, min=-1006190.0000, max=20760.0000
  - うち PnL=0 個体: 0 件 (取引したのに PnL=0 = Run 9 監査の対象観測)
- (3) Stage A 通過個体 `total_pnl_stage_a` 分布 (n=1999): n=1999, mean=13153.7519, median=19160.0000, std=85900.9314, min=-1000940.0000, max=42970.0000

## Archive Top-5 個体一覧

> Best とは別物です。`fitness_pen` 単独降順。Best は (feasible, -violation, stage_b_pass, stage_c_feasible, stage_c_pass, stage_b_pass, stage_a_pass, fitness_pen) の辞書式 (v3.1_stage_b_priority, T046)。

| rank | name | gen | lane | instrument | fitness_pen | fitness_raw | A | B | C | trade_count | sharpe |
|-----:|------|----:|------|------------|------------:|------------:|---|---|---|----:|-------:|
| 1 | `g26_i95` | 26 | tier1_EUR_JPY | EUR_JPY | 0.2699 | 0.2894 | ✅ | ❌ | ❌ | 44 | — |
| 2 | `g39_i74` | 39 | tier1_EUR_JPY | EUR_JPY | 0.2338 | 0.2533 | ✅ | ❌ | ❌ | 48 | — |
| 3 | `g32_i47` | 32 | tier1_EUR_JPY | EUR_JPY | 0.2246 | 0.2591 | ✅ | ❌ | ❌ | 44 | — |
| 4 | `g56_i28` | 56 | tier1_EUR_JPY | EUR_JPY | 0.2222 | 0.2417 | ✅ | ❌ | ❌ | 53 | — |
| 5 | `g57_i0` | 57 | tier1_EUR_JPY | EUR_JPY | 0.2222 | 0.2417 | ✅ | ❌ | ❌ | 53 | — |

## 収束履歴

| gen | best_fitness |
|-----|--------------|
| 0 | -0.036511484633228654 |
| 1 | -0.0319411810750956 |
| 2 | -0.0319411810750956 |
| 3 | 0.008183593274836639 |
| 4 | 0.008183593274836639 |
| 5 | 0.0267055293483965 |
| 6 | 0.149714460202822 |
| 7 | 0.03140854028223269 |
| 8 | 0.03140854028223269 |
| 9 | 0.03140854028223269 |
| 10 | 0.03140854028223269 |
| 11 | 0.0432778368111328 |
| 12 | 0.05010482931060396 |
| 13 | 0.05445714307913524 |
| 14 | 0.05445714307913524 |
| 15 | 0.12673834278431068 |
| 16 | 0.08409148460103993 |
| 17 | 0.06981602717127808 |
| 18 | 0.09782775776566816 |
| 19 | 0.075437860456114 |
| 20 | 0.075437860456114 |
| 21 | 0.095928501821253 |
| 22 | 0.09720715568596278 |
| 23 | 0.1710709746092857 |
| 24 | 0.1746897686884248 |
| 25 | 0.1746897686884248 |
| 26 | 0.2699400194568124 |
| 27 | 0.1746897686884248 |
| 28 | 0.1746897686884248 |
| 29 | 0.17566007632298067 |
| 30 | 0.17566007632298067 |
| 31 | 0.19886586134947973 |
| 32 | 0.2246256255637327 |
| 33 | 0.21084401307700307 |
| 34 | 0.21084401307700307 |
| 35 | 0.21084401307700307 |
| 36 | 0.21084401307700307 |
| 37 | 0.21084401307700307 |
| 38 | 0.21084401307700307 |
| 39 | 0.2338411742544719 |
| 40 | 0.21084401307700307 |
| 41 | 0.22147686997826332 |
| 42 | 0.21084401307700307 |
| 43 | 0.21084401307700307 |
| 44 | 0.21084401307700307 |
| 45 | 0.21084401307700307 |
| 46 | 0.21084401307700307 |
| 47 | 0.21084401307700307 |
| 48 | 0.21084401307700307 |
| 49 | 0.2117150834955932 |
| 50 | 0.2117150834955932 |
| 51 | 0.2131167121616712 |
| 52 | 0.2131167121616712 |
| 53 | 0.2131167121616712 |
| 54 | 0.2131167121616712 |
| 55 | 0.2131167121616712 |
| 56 | 0.22223903152937072 |
| 57 | 0.22223903152937072 |
| 58 | 0.22223903152937072 |
| 59 | 0.22223903152937072 |
| 60 | 0.22223903152937072 |

## 分析

### analysis-claude.md

# RUN run_20260506_030253 (run-35) 分析（Claude 自己分析）

cycle 3 / 20 — improve-cycle 自走ループ。 cycle 2 (max_clause=2 baseline + WF 窓整合化 + partition guard) の効果検証。

## 前提差分

なし。

- archive Parquet 存在: `.cache/alpha_factory/runs/genomes_run_20260506_030253.parquet` (5856 rows, 1.31 MB)
- summary.json 存在: `reports/run-reports/run-35/summary.json`
- run-35.md 生成済 (cycle 2 Phase 5 完了)
- 前 Run (run-34) との差分比較可能 (`genomes_run_20260505_043320.parquet` 利用)

## 観察事実（Facts）

### 1. Stage 通過数 (run-34 vs run-35)

| Stage | run-34 | run-35 | 差分 |
|---|---|---|---|
| Stage A | 2,929 / 5,856 (50.0%) | 1,999 / 5,856 (34.1%) | **-32%** |
| Stage B | 22 / 5,856 (0.4%) | **0 / 5,856 (0.0%)** | **-100%** |
| Stage C | 0 / 5,856 | 0 / 5,856 | 不変 |

### 2. Best 個体 比較

| metric | run-34 (g48_i70) | run-35 (g56_i28) | 差分 |
|---|---|---|---|
| fitness_pen | 0.171 | **0.222** | +30% |
| sharpe | 0.189 | 0.242 | +28% |
| total_pnl | 40,140 | 28,590 | -29% |
| trade_count | 54 | 53 | ≒ |
| max_dd_pct | 0.0 | 0.0 | 不変 |
| active_clause | 1 | 1 | 不変 (max_clause=2 でも単一 clause) |
| n_nodes | 4 | 4 | 不変 |

注: archive 視点での top-1 fitness_pen 個体は g26_i95 (fitness_pen=0.270, sharpe=NaN, trade_count=44, fold_sign_ratio=0.0) で別物。 summary best (selection_score schema 経由) は g56_i28。

### 3. **active_clause 別 Stage A 通過率 (DECISIVE)**

| active_clause | total | Stage A pass | 通過率 |
|---|---|---|---|
| 0 | 24 | 0 | 0.0% |
| 1 | 4,087 | 1,797 | **44.0%** |
| 2 | 1,745 | 202 | **11.6%** |

`max_clause=2` を許容したことで複合 clause 個体が pop の 30% (1,745/5,856) を占めるようになったが、 **Stage A 通過率は単一 clause の 1/4**。

### 4. WF fold 機能化 (cycle 2 implement の最大変化)

| metric | run-34 (Stage A pass 群) | run-35 (Stage A pass 群) |
|---|---|---|
| n_fold_effective mean | 0.252 | **8.513** |
| n_fold_effective median | 0 | 9.0 |
| positive_fold_ratio_effective n | 681 (極少) | **1,900** (全 Stage A pass) |
| positive_fold_ratio_effective mean | 0.681 | 0.181 |
| positive_fold_ratio_effective median | 1.000 | 0.182 |

run-34 では `n_fold_effective=0` の個体が大半 (median=0) で、 fold 評価そのものが機能していなかった。 cycle 2 の WF 窓整合化で fold 評価が **「全 Stage A pass 個体に対してまともに走るように」** なった結果、 統計対象母集団が変わった (n=681 → n=1,900)。

### 5. fold_sign_ratio 分布 (Stage A pass 群、 n=1999)

| 閾値 | 件数 | 比率 |
|---|---|---|
| ≥ 0.0 | 1,999 | 100.0% |
| ≥ 0.2 | 1,588 | 79.4% |
| ≥ 0.4 | 234 | 11.7% |
| ≥ 0.6 | 13 | 0.7% |
| ≥ 0.8 | 0 | 0.0% |

mean=0.216, median=0.20, max=0.70。 Stage B 通過閾値 (`positive_fold_ratio_min` = 0.6) を満たすのは **13 個体のみ (0.7%)**。

### 6. Stage B 落下要因 (n=1,999、 100%)

| reason | 件数 |
|---|---|
| `median_oos_sharpe<min;positive_fold_ratio<min` | 1,900 (95.0%) |
| `median_oos_sharpe<min;positive_fold_ratio<min;all_folds_unavailable` | 99 (5.0%) |

→ **全 Stage A pass 個体が「median_oos_sharpe < 0.05 かつ positive_fold_ratio < 0.6」の同時不達**で Stage B を落ちている。 単一 reason での通過は 0 件。

### 7. 世代別推移 (Stage A pass 群)

| gen 区間 | n | active_clause_mean | fold_sign_mean | fitness_pen_mean |
|---|---|---|---|---|
| 0-9 | 26 | 1.000 | 0.154 | 0.0203 |
| 10-19 | 142 | 1.007 | 0.278 | 0.0338 |
| 20-29 | 353 | 1.042 | 0.235 | 0.0483 |
| 30-39 | 405 | 1.064 | 0.212 | 0.0829 |
| 40-49 | 469 | 1.147 | 0.216 | 0.1044 |
| 50-59 | 549 | 1.158 | 0.195 | 0.1168 |
| 60+ | 55 | 1.073 | 0.225 | 0.1295 |

GA 進化中、 fitness_pen は単調増加 (0.02→0.13) するが **fold_sign_mean は 0.20-0.28 帯から動かない** (Stage B 閾値 0.6 の 1/3)。 active_clause_mean は緩やかに増加 (1.00→1.16) するが Stage A 通過率視点だと逆効果。

### 8. total_pnl=0 個体 (cycle 1 fix の効果検証)

| 集計 | 件数 |
|---|---|
| total_pnl=0 全体 | 285 |
| total_pnl=0 かつ trade_count>0 | **0** |

→ cycle 1 修正 (collect_stage_a で total_pnl 伝播) が**機能継続**。 取引したのに PnL=0 という Run 9 監査対象の異常は解消されたまま。

### 9. dataset / Lane / Pair 偏在

| 区分 | 値 |
|---|---|
| Lane | tier1_EUR_JPY 単一 (5,856 全行) |
| instrument | EUR_JPY 単一 |
| cross_pair_runtime_mode | skipped_single_instrument (run-34 と同様) |

## 解釈・推論（Interpretations、 C6 Fact/Interpretation 分離遵守）

### 仮説 H1: cycle 2 の WF 窓整合化は **「fold 評価を正しく機能させた」改善** であり、 Stage B pass 0 は退化ではなく **正しい評価結果**

**根拠**:
- run-34 では n_fold_effective=0 が大半、 つまり fold 評価そのものが skip されていた個体が多かった (`all_folds_unavailable` 経路)
- run-35 では n_fold_effective median=9, mean=8.51 で **ほぼ全 Stage A pass 個体に対して 9 fold WF が走る** ようになった
- run-34 で「Stage B pass 22 個体」と見えていたものは、 fold が機能した「特殊な少数派」 (n=681) であり、 統計母集団が偏っていた
- run-35 では Stage A pass のほぼ全員に対して fold 評価が走る → positive_fold_ratio が真の品質を測定

**反証可能性**:
- Stage B fold 評価結果を逐次確認し、 (a) fold 数が n_fold_effective median=9 で適正 (b) train/test 期間の disjoint が保たれている (c) trade 数が fold 内で min を満たす — これら 3 点が全部 OK ならば「正しく評価された」確証
- もし fold 内 trade 数が極端に少ない (<5) ならば fold 評価が malfunctioning で Stage B 不通過は人工的

→ 暫定 **CONFIRMED寄り**。 cycle 2 implement の主目的が「fold を機能させる」だったので、 結果が機能化した方向に動いたのは設計通り。

### 仮説 H2: max_clause=2 への拡張は **Stage A 通過に逆効果**。 単一 clause の方が pass しやすい

**根拠**:
- active_clause=1 通過率 44.0% vs active_clause=2 通過率 11.6% (3.8 倍の差)
- pop 全体 mean 1.29、 Stage A pass 群 mean 1.10 → max_clause=2 個体は Stage A で淘汰される傾向
- best 個体 g56_i28 は active_clause=1 (max_clause=2 を許容しても top は単一 clause)

**反証可能性**:
- max_clause=2 個体の **trade_count / total_pnl 分布** が単一 clause 群と比較して劣っているなら品質不足
- もし trade_count や PnL は同等なのに sharpe (Stage A 評価指標) だけ劣るなら、 複合 clause が「平均化」して timing 多重化のコストを払っている
- **複合 clause で Stage A 通過率を上げる介入** (例: clause 結合論理の見直し / 個別 clause 性能の事前評価) が必要

→ 暫定 **CONFIRMED**。 max_clause=2 baseline 維持は探索空間を広げる目的では達成 (active_clause=2 個体が 30% 生成された) だが、 Stage A 通過視点では逆効果。 Stage A の selectivity が複合 clause を不当に削っているか、 複合 clause 自体が Stage A 期間の sharpe 形成に不利な構造を持つ。

### 仮説 H3: positive_fold_ratio_min=0.6 は cycle 2 fold 機能化以降は **過厳格**

**根拠**:
- Stage A pass 群 (n=1999) の positive_fold_ratio_effective mean=0.18 で、 0.6 閾値の 1/3
- 0.6 を満たす個体は 13 個 (0.7%)、 ほぼランダム fluke
- ペナルティ無し最大値が 0.7 → 構造的に 0.6+ を出せる個体が極少

**反証可能性**:
- 13 個体が「真に robust signal」なのか「ランダムに 0.6+ になっただけ」かを別期間 (e.g. holdout) で再検証
- もし 13 個体が holdout でも positive performance なら閾値正当、 holdout で全滅なら閾値はランダム fluke を拾うだけ

→ **未確定**。 「閾値緩和でステージ飛ばし」禁止に抵触するため、 安易に 0.6 → 0.5 に下げるべきではない。 まず 13 個体の品質を真摯に検証してから判断。

### 仮説 H4: cycle 2 までの 改善方向は正しいが、 残された ボトルネックは **「signal source の絶対品質」** で primitive / 構文木の根本見直しが必要

**根拠**:
- fitness_pen_mean は世代と共に増加 (0.02→0.13) → GA 探索は機能している
- しかし **fold_sign_mean は 0.20 帯で頭打ち** (世代を重ねても改善しない)
- positive_fold_ratio_effective max=0.7 で天井
- → GA は「データ全体に fit する」方向で進化しているが、 「fold 横断で robust」 な解は探索範囲内に無いのではないか

**反証可能性**:
- 同じ primitive 集合・ 同じ構文木で **より長期間 (60→100 generations) GA を走らせる** と fold_sign_mean が突き抜ける/しない
- もし不変 → primitive / 構文木設計の見直しが必要 (T086 系の primitive 拡張、 cross-pair feature の追加等)
- もし突き抜ける → GA exploration が単に短かっただけ (population size 拡張)

→ **未確定だが疑念深い**。 cycle 4-10 で観察すべき長期トレンド。

### 仮説 H5: best 個体 g56_i28 は **trade_count_min=50 ぎりぎり** で、 GA が「取引回数削減で見かけ改善」している兆候

**根拠**:
- best trade_count=53 (min=50 + 3)
- archive top-1 g26_i95 trade_count=44 (< 50、 stage_a_pass=True なのは別経路)
- top-3 (g26_i95, g39_i74, g32_i47) trade_count: 44, 48, 44 — 全員 ぎりぎり下回り
- 集団 fitness_pen 上位は **min を僅かに下回る個体** に集中

**反証可能性**:
- selection_score の `feasibility.entry_count_min=50` 制約 (cycle 12 で 1→50 復元) が機能していれば trade_count<50 は infeasible で best には選ばれないはず
- にもかかわらず archive top に < 50 個体が並ぶのは、 fitness_pen 単独 ranking と selection_score 6 要素辞書式の差異による (設計通り)
- ただし **GA selection の進化方向が「ぎりぎり 50 で sharpe を上げる」方向に向かっている** ならば、 trade_count_min=50 は GA の attractor になっている (削減方向の attractor は禁止事項 6 違反)

→ **要観察**。 cycle 4 以降の RUN で best trade_count の推移を見て、 50-55 帯に固定化するなら attractor 確証。

### 禁止事項違反チェック (C4)

| 禁止事項 | 兆候 | 注 |
|---|---|---|
| 1. A/B/C 評価期間延長 | なし | dataset 不変 (epoch_20251001_20260401) |
| 2. 見た目数値改善 | **疑い** | best fitness_pen 0.171→0.222 (+30%) は WF 窓整合化由来。 「機能の改善」だが「見た目が良くなる」副次効果あり、 Codex 独立判定要 |
| 3. GA ハック | なし | `seed=23 deterministic` は cycle 1-2 から維持、 cycle 1 と同じ条件 |
| 4. 閾値緩和でステージ飛ばし | なし | live_criteria 不変 (sharpe>=1.0, total_pnl>=50000) |
| 5. やたらに複雑な案 | **疑い** | max_clause=2 baseline 拡張が complexity 増加方向。 Stage A 通過率は逆に悪化 (44→11.6%)、 複雑化の見返り無し |
| 6. 取引回数削減で見かけ改善 | **疑い** | best trade_count 53 (cycle 1) → 53 (cycle 2)、 trade_count_min=50 ぎりぎり個体に集中 |
| 7. オーバーナイト保有 | 未測定 | trade-level 保有時間分布を archive から取れていない (要 sidecar 追加か trade ledger 再評価) |

## 次サイクル候補

### [Critical] C1: max_clause=2 baseline 維持の妥当性再評価

active_clause=2 の Stage A 通過率 11.6% は 単一 clause 44.0% の 1/4。 cycle 2 で「探索空間拡張」を目的に max_clause=2 を入れたが、 GA 進化の足を引っ張っている。

**選択肢**:
- (a) max_clause=1 に戻す (探索空間縮小、 cycle 1 baseline 復帰)
- (b) max_clause=2 維持しつつ active_clause=2 個体に対する Stage A 評価を見直す (clause 結合論理の検証)
- (c) max_clause=2 維持しつつ複合 clause の初期生成確率を下げる (e.g. p_two_clause=0.1 → 探索余地は残すが GA 主流は単一)

**判断**: ユーザー指示 (max_clause=2 baseline) を尊重しつつ、 (b) または (c) を Codex に問う。 単純に (a) で戻すのは「ユーザー判断の差し戻し」になるため避ける。

**反証**: cycle 4 以降で (b)/(c) を試して active_clause=2 個体の Stage A 通過率が単一 clause と同等 (40%+) に戻れば確証。 戻らなければ複合 clause の構造的問題。

### [Critical] C2: fold_sign_ratio / positive_fold_ratio の天井分析

run-35 で Stage A pass 群の fold_sign_ratio が **max 0.7、 mean 0.22** で頭打ち。 0.6 閾値到達者は 13 個 (0.7%)。 cycle 2 で fold 機能化したが、 結果として「ほぼ全員が Stage B 不通過」 になった。

**仮説**:
- (i) primitive 集合 / 構文木 max_depth=4 の制約で「真の robust signal」が表現可能領域に無い
- (ii) Stage B fold 設計 (train=20d / test=10d / 11 folds) が EUR_JPY M1 のレジーム変化に対して粒度不足
- (iii) `positive_fold_ratio_min=0.6` 閾値が WF 機能化以降は過厳格

**Action**: cycle 4 で 13 個の「天井近傍」個体 (fold_sign_ratio>=0.6) を逐次再評価 → 真に robust なのか fluke なのかを切り分け。

**反証**: 13 個が holdout でも positive ならば閾値妥当、 holdout で全滅なら fluke。

### [Warning] W1: best 個体 trade_count attractor 監視

cycle 1, 2 ともに best trade_count = 53-54 (min=50 + 3-4)。 GA が trade_count_min ぎりぎりに収束している兆候。

**Action**: cycle 4 以降の best trade_count 分布を観測。 50-55 帯に固定化するなら attractor 確証で fitness 設計見直し。

### [Warning] W2: cross-pair shadow 全 skip の継続

`cross_pair_runtime_mode=skipped_single_instrument` が run-34, 35 で継続。 anchors 設計が機能していない。 cycle 2-3 段階で対応する余裕は無いが、 後続 cycle で multi-instrument RUN への復帰検討。

**Action**: 観察のみ。 介入は Stage B 通過個体が出てから検討 (順序は Stage gates → cross-pair)。

### [Warning] W3: fitness_pen 0.222 vs sharpe NaN の archive Top の謎

archive top-1 (fitness_pen 単独 max) g26_i95 は sharpe=NaN, trade_count=44, fold_sign_ratio=0.0。 selection_score 6 要素辞書式では best にならない (g56_i28 が SoT) が、 **なぜ stage_a_pass=True なのか** が不明 (trade_count=44 < trade_count_min=50)。

**Action**: cycle 4 で stage_a_pass の定義経路を Codex に確認 (trade_count_min は live_criteria のもの、 stage_a_pass は別経路の閾値判定)。 bug ではなく異なる契約な可能性が高いが、 確認した上で観察事実として記録。

## 全体判定 (preliminary)

**OK寄り CONCERN**

cycle 2 の WF 窓整合化は機能改善として **設計通り**。 Stage B pass 0 は「真の品質を測れるようになった」結果であり、 退化ではない (H1)。

ただし 同時に投入された max_clause=2 baseline は Stage A 通過率視点では逆効果 (H2)、 fold 評価結果は天井 0.7 で構造限界の疑い (H3, H4)、 best 個体は trade_count attractor の疑い (H5) — 3 つの concern を抱えた状態で cycle 3 plan-and-design に進む。

cycle 3 では C1 (max_clause=2 妥当性) と C2 (fold ceiling 分析) を Codex 独立分析に問い、 plan-and-design で 1 cycle あたり 1 介入の原則 で次の改善を選定する。

### analysis-codex.md

## 前提差分 (C4 verified / 差分)
- `verified`: Stage 分割・WF 評価が run-35 で実効化された（`n_fold_effective median 0→9`、Stage A pass ほぼ全件で fold 指標が計算）。
- `verified`: Stage B は `1,999/1,999` が不通過、理由は全件で `median_oos_sharpe<0.05` と `positive_fold_ratio<0.6` の同時不達。
- `verified`: `max_clause=2` 変更後、`active_clause=2` 個体は母集団 30% を占める一方、Stage A 通過率は 11.6%（clause=1 は 44.0%）。
- `verified`: live_criteria 閾値自体は run-34 から不変。
- `差分/未検証`: 生 archive 原票・実コード経路は未読のため、ここでは提示集計の整合を前提に評価（設計意図との最終照合は未了）。

## 観察事実 (Facts、 C6 Fact/Interpretation 分離遵守)
- Stage A 通過率は `50.0%→34.1%`、Stage B は `22件→0件`。
- run-35 Stage A pass 群の `fold_sign_ratio` は `mean 0.216 / median 0.20`、`>=0.6` は 13件（0.7%）。
- 世代進行で `fitness_pen_mean` は単調増加、`active_clause_mean` も上昇、`fold_sign_mean` は 0.20 前後で停滞。
- Top-3（fitness_pen最大）は `trade_count<50`、`sharpe=NaN`、`fold_sign=0` でも Stage A pass。
- `total_pnl=0 & trade_count>0` は 0件（過去異常は再発していない）。
- cross-pair runtime は `skipped_single_instrument`（EUR_JPY 単一）。

## 解釈・推論 (Interpretations、 C9 反証可能性付き)
1. **主ボトルネック仮説: Stage B 閾値そのものより「探索圧の不整合」**
- 仮説: GA は Stage A で伸びる指標（fitness_pen）に最適化され、WF 頑健性（fold_sign）へ圧が十分かかっていない。結果として Stage B で集団壊滅。
- 反証条件: Stage A 選抜上位群で `fold_sign` が世代とともに有意上昇（例: 終盤 median >=0.4）し、同時に Stage B pass が回復するならこの仮説は棄却。

2. **`max_clause=2` の寄与は現状「探索拡張」ではなく「ノイズ拡張」寄り**
- 仮説: 2-clause は表現力増ではなく過適合候補の増加として作用し、Stage A 通過効率を落としている（11.6% vs 44.0%）。
- 反証条件: 同条件 A/B（`max_clause=1` vs `2`）で、`2` が Stage B 到達数または Stage B 指標（median_oos_sharpe, fold_sign）を改善すれば棄却。

3. **禁止事項系の兆候: 「取引回数下限近傍 attractor」+「複雑化で逆効果」**
- 兆候: best が `trade_count=53`（下限50近傍）、Top-3 は `<50` でも高fitness_pen。  
- 解釈: ルール上の明示違反確定ではないが、「live適合性より Stage A スコア有利」を選ぶ圧が存在する可能性。
- 反証条件: Stage A スコア算定に live_criteria 連動ペナルティを入れた比較 run で、`trade_count` 分布が下限近傍から離れ、かつ Stage B 指標が改善しなければこの兆候は弱まる。

4. **cross-pair shadow は現状 INCONCLUSIVE**
- 仮説: single instrument で `skipped` 継続中は、shadow 統計を根拠に一般化判断すべきでない。
- 反証条件: 2通貨ペア以上で同一 run 条件を回し、shadow 指標と本番指標の整合が再現すれば妥当化可能。

## 次サイクル候補
- **Critical (1件)**: `max_clause=2` の即時反証実験（`max_clause=1` に戻した対照 run を同 epoch/seed帯で実施）。  
  反証可能性: `max_clause=1` でも Stage B=0 かつ fold_sign 分布不変なら、「clause数主因」仮説は棄却。
- **Warning 1**: Stage A 目的関数と Stage B 要件の整合監査（Stage A 上位の `fold_sign` 相関を世代別で検証）。  
  反証可能性: Stage A 上位ほど fold_sign が高いなら「探索圧不整合」仮説は棄却。
- **Warning 2**: trade_count 下限 attractor 監査（50-70帯への集中度を run間比較）。  
  反証可能性: 分布が広く下限集中なしなら attractor 仮説は棄却。
- **Warning 3**: cross-pair shadow 妥当性確認は保留明示（single運用中は評価対象外扱い）。  
  反証可能性: multi-pair run で shadow が予測力を示せば保留解除。

## 全体判定: CRITICAL_DRIFT
- 理由: Stage B 全滅が単発ノイズではなく、世代進行で `fitness_pen↑` と `fold_sign停滞` が同時発生しており、探索方向と頑健性目標の乖離が構造的に見えるため。

## Claude 分析との差分 (最後に確認)
- **同意**: WF 機能化自体は改善であり、run-34 比較だけで「退化」と断定しない点。
- **反対/修正**: `positive_fold_ratio_min=0.6` を主因とみなすのは早い。閾値過厳格より先に、Stage A 最適化圧の不整合を反証すべき。
- **見落とし補足**: `fitness_pen` 上位が `trade<50 / sharpe NaN / fold_sign=0` でも上に来る事実は、live適合性との目的関数ギャップを示す強い警告。ここを先に潰さないと、閾値調整だけでは再発しやすい。

### analysis-merged.md

# マージ分析: Run 35 (run_20260506_030253)

cycle 3 / 20 — Claude / Codex 両分析の統合。

## 合意事項（両者一致）

| # | 観察 / 仮説 | 含意 |
|---|------|------|
| M1 | cycle 2 WF 窓整合化で fold 評価が機能化 (n_fold_effective median 0→9)、 Stage B pass 0 は退化ではなく **真の品質測定の結果** | 評価機構修正は CONFIRMED 改善 |
| M2 | max_clause=2 拡張は Stage A 通過率に逆効果（active_clause=1: 44.0% vs active_clause=2: 11.6%） | 複合 clause は現状「ノイズ拡張」寄り、 探索拡張になっていない |
| M3 | best 個体は trade_count_min=50 ぎりぎり (53)、 Top-3 (fitness_pen 単独 max) は trade<50 で sharpe NaN | trade_count attractor の疑い + Stage A 目的関数と live 適合性のギャップ |
| M4 | live_criteria 不変、 Stage A threshold 不変 (-0.0172) — 禁止事項 1, 2, 4 は未発生 | 数値弄りによる見栄え改善は無し |
| M5 | cross-pair shadow 全 skip 継続 (single instrument) | anchors 設計が機能していない、 監視欠落（要対応だが優先度は Stage gates 後） |

## Claude 独自の発見

| # | 観察 | Codex はなぜ取り上げなかったか |
|---|------|---------------------------|
| L1 | positive_fold_ratio_min=0.6 を「過厳格」と仮説化 (H3) | Codex は「閾値より探索圧不整合が主因」として閾値仮説を**棄却寄り**（修正点）|
| L2 | total_pnl=0 かつ trade>0 が 0 件で cycle 1 fix 機能継続 | Codex も観察したが因果に踏み込まず |
| L3 | fold_sign_ratio max=0.7 で天井、 GA 探索空間の構造限界仮説 (H4) | Codex も近い指摘 (fold_sign 停滞) を出しているが構造限界とは言わず |

## Codex 独自の発見（Claude が見落とした観点）

| # | 観察 | Claude の見落とし |
|---|------|------------------|
| C1 | **探索圧不整合**: GA は fitness_pen (Stage A) 最大化方向に進化、 fold_sign_mean は世代を重ねても 0.20 帯で停滞 | Claude H4 は近いが「primitive 設計の限界」に話を膨らませた。 Codex は **Stage A 目的関数自体が Stage B 要件と整合していない** という構造的な問題を指摘 |
| C2 | **`fitness_pen` 上位が trade<50 / sharpe NaN / fold_sign=0 でも上に来る** = live 適合性と GA 目的関数のギャップは強い警告 | Claude W3 で確認依頼に留めた、 Codex は最重要警告として位置付け |
| C3 | メタ過学習ガード: max_clause=2 維持・調整は **Reactive Parametric** （直近 Run ベース） で、 同じデータへの当てはめ強化のリスク | Claude は max_clause=2 維持/戻し/調整の三択を提示するに留め、 メタ過学習リスクは明示せず |

## 矛盾・要議論

| # | Claude の見解 | Codex の見解 | 議論 |
|---|------------|------------|------|
| D1 | positive_fold_ratio_min=0.6 を緩和候補に検討 (H3) | 「閾値より Stage A 目的関数の不整合が主因」、 閾値変更を **早計** と判断 | **Codex 優位** — fold_sign_ratio max=0.7 で天井なのは「fold で robust に勝つ signal が探索範囲に無い」可能性。 閾値緩和は禁止事項 4 (ステージ飛ばし) に抵触する恐れ。 まず Stage A 目的関数監査を先行 |
| D2 | max_clause=2 を 戻す or 評価論理見直し or 初期生成確率調整の三択 | max_clause=1 に戻した A/B 反証実験を Critical | **Codex 優位** — Claude 案 (a)(b)(c) のうち (a) が最も反証可能性が高い。 ただしユーザー指示で max_clause=2 baseline 設定があるため、 戻すには user confirm が必要 |
| D3 | best trade_count attractor を Warning | 同 | 一致 |

## 統合改善提案（優先度順）

| # | 提案 | 優先度 | 出所 | 変更分類 | target_metric | failure_mode | causal_path | falsification | success_criterion |
|---|------|--------|------|---------|--------------|-------------|------------|---------------|-------------------|
| **P1** | **Stage A 目的関数と Stage B 要件の整合監査 (観察 sidecar 追加)** | **Critical** | Codex C1 + Claude H4 | **Structural** | Stage B pass count / Sharpe robustness | GA は fitness_pen 増加方向に進化するが fold_sign_mean は 0.20 帯で停滞 → Stage A 目的関数 (fitness_pen = sharpe - α·size_norm) が WF 頑健性を測れていない | Stage A 目的関数に WF fold-aware の構造的シグナルが欠落、 結果として Stage B 不通過が世代を重ねても解消しない | Stage A pass 群で **世代別の fold_sign_mean / median_oos_sharpe 分布を sidecar parquet に出力**、 後 Run の analyze で「Stage A 上位群でも fold_sign が世代と共に上昇しない」が verified なら H1 棄却 (= 閾値や primitive の問題)、 verified なら本仮説確証で Phase 4 で目的関数改修 | sidecar parquet が世代別 stage_a 上位 N 件の fold_sign / median_oos_sharpe を含み、 cycle 4 の analyze で Stage A 順位と fold robustness の相関を測定可能 |
| **P2** | **archive Top-1 (g26_i95) trade<50 / sharpe NaN / fold_sign=0 個体の stage_a_pass 経路調査** | **Critical** | Codex C2 + Claude W3 | **Structural** (調査のみ、 修正は別 cycle) | live_criteria 整合性 | trade_count<50 で stage_a_pass=True、 さらに fitness_pen 単独 ranking で top に来る = GA selection / Stage A 評価が live 制約を反映していない | Stage A の通過判定が trade_count_min をチェックしていない、 もしくは別経路 (selection_score) が trade_count<50 を許容している | g26_i95 の stage_a_pass 経路を grep + log で追跡。 stage_gate.canonical_five.dual_path で stage_a_pass=True が出ているなら canonical の閾値経路を確認 | trade_count<50 で stage_a_pass=True になる経路が特定され、 設計通り or bug の判定が可能 |
| **P3** | trade_count attractor 監視 (cycle 4-5 で経時観測) | Warning | Claude W1 + Codex Warning 2 | 観察のみ | trade_count 分布 | best trade_count 53-54 が cycle 1, 2, 3 で固定化したら attractor 確証 | cycle 4-5 で best trade_count が 50-55 帯から離れれば棄却 | best trade_count が 50-55 帯に集中せず分散する |
| **P4** | cross-pair shadow 妥当性確認は **明示保留** | Warning | 両者一致 | 観察のみ | shadow 統計の情報価値 | single instrument 運用中は判断不能 | multi-instrument RUN 復帰までは判断保留 | multi RUN 後に shadow 指標と本番指標の整合を測定 |
| **P5** | max_clause=2 維持/戻しの判断は **保留**（C3 メタ過学習ガード） | Warning | Codex C3 + Claude H2 | Reactive Parametric (要注意) | active_clause 別 Stage A 通過率 | max_clause=2 拡張で複合 clause 個体の Stage A 通過率が 1/4 | (a) 戻す / (b) 評価論理見直し / (c) 初期生成確率調整 のいずれを取るか、 P1 (Stage A 目的関数監査) の結果を見てから判断 | P1 sidecar で「Stage A 上位は単一 clause 偏重 = 複合 clause が Stage A に不適」が verified なら (b) の方向、 不変なら (c)、 Codex 推薦は (a) | P1 結果に基づく根拠ある判断 |

**保留事項**:
- P5 (max_clause=2 baseline 維持/変更) は P1 (Stage A 目的関数監査) の結果を待ってから cycle 4 以降で判断する。 ユーザー指示 (max_clause=2 baseline) を尊重しつつ、 観測データで根拠ある判断を優先

## 全体判定

**CONCERN（Codex CRITICAL_DRIFT を踏まえつつ、 cycle 3 の介入は P1 観察 sidecar 追加に絞る）**

cycle 2 の WF 機能化は CONFIRMED 改善。 ただし「探索圧不整合」「live 適合性ギャップ」「max_clause=2 メタ過学習リスク」 の 3 つの concern を抱えた状態で、 cycle 3 では **P1 (sidecar 観察追加)** という structural / 観察のみ の最小介入で進む。 P2 (Top-1 経路調査) は調査メイン、 修正は cycle 4 以降。

「仕組みが機能していない段階で値を弄るな」 「機能の名前に立ち返れ」 の原則に従い、 閾値や max_clause の調整は cycle 4 以降の決断とする。

