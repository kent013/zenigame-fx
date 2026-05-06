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
