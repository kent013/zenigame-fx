# Run 28 — run_20260504_055856

**Generated**: 2026-05-04T05:58:56.865282+00:00
**dataset_epoch_id**: `epoch_20251001_20260401`
**Dataset**: EUR_JPY `2025-10-01T00:00:00+00:00` → `2026-04-01T00:00:00+00:00` (bars=183403)
  - bars_stage_a: 86400
  - bars_stage_b: 183403
  - bars_holdout: 20457

## 使命判定

未達

- ❌ **sharpe**: 0.005658488726607911 / threshold 1.0
- ❌ **total_pnl**: 0.0 / threshold 50000.0
- ✅ **max_drawdown_pct**: 0.0 / threshold 20.0
- ✅ **trade_count**: 3412 (range 50〜5000)

## GA 設定

- population_size: 40
- generations: 15
- mutation_rate: 0.3
- crossover_rate: 0.7
- tournament_size: 3
- elite_count: 2
- max_depth: 4
- fitness_metric: sharpe
- seed: None

## Best 個体

- name: `g5_i10`
- generation: 5
- fitness: **-0.0033415112733920886**
- fitness_finite: ✅
- stage_a_pass: ❌
- stage_b_pass: ❌
- stage_c_pass: ❌
- trade_count: 3412
- total_pnl: 0.0
- sharpe: 0.005658488726607911
- sortino: —
- calmar: —
- max_drawdown_pct: 0.0

**Archive 補足情報**:
- lane_id: tier1_EUR_JPY
- instrument: EUR_JPY
- fold_sign_ratio: —
- dsr: —
- ii_lite_pass: —
- n_nodes: 2
- active_clause: 1

## Stage 通過数

- 全 archive 行数: 640
- Stage A pass: 0
- Stage B pass: 0
- Stage C pass: 0

## Lane 別落下分布

| lane_id | total | A | B | C |
|---------|-------|---|---|---|
| tier1_EUR_JPY | 640 | 0 | 0 | 0 |

## Pair 別落下分布

| instrument | total | A | B | C |
|------------|-------|---|---|---|
| EUR_JPY | 640 | 0 | 0 | 0 |

## active_clause / n_nodes 分布

- active_clause: n=640, mean=0.9984, median=1.0000, std=0.0395, min=0, max=1
- n_nodes: n=640, mean=1.8016, median=2.0000, std=0.8531, min=1, max=4

## mission_score 分布 (T043 / observation only)

> live_criteria 4 軸 (sharpe/total_pnl/max_drawdown/trade_count) の soft 合算スコア (幾何平均、[0.1, 1.0])。GA fitness や stage_c.passed には 影響しない (詳細: docs/alpha_factory/mission-score.md)。

- mission_score=計測対象 0 件 (Stage C base 評価で Sharpe を出した 個体が無いため未計測)

## fold_sign_ratio / dsr 分布

- fold_sign_ratio: n=0
- dsr: n=0
- n_fold_effective (Stage A pass): n=0
- positive_fold_ratio_effective (Stage A pass): n=0

## Stage B failure reason 集計

- Stage A pass = 0, Stage B pass = 0, failures = 0 (primary_sum = 0)

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
| `unknown_reason` | 0 |
| `other` | 0 |

### Any reason incidence (全 reason、合計 >= failures)

| reason | count |
|--------|------:|
| `no_folds` | 0 |
| `insufficient_folds` | 0 |
| `all_folds_unavailable` | 0 |
| `stage_b_window_underfilled` | 0 |
| `median_oos_sharpe<min` | 0 |
| `positive_fold_ratio<min` | 0 |
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
- trade_count=0 個体比率: 1.2% (8/640)
- best 個体 trade_count: 3412
- best 個体 feasibility: ✅

## Stage A provenance 分布 (T033 / sidecar)

> Stage A 落ち個体の `total_pnl_stage_a` 分布を可視化 (`reports/run-reports/run-{N}/diagnostics/stage_a_provenance.parquet`)。archive `total_pnl=0.0` が「Stage A 落ち = 投影仕様」「実 PnL=0」「コスト過大」のいずれかを切り分けるための観測指標 (詳細: docs/alpha_factory/diagnostics-sidecar.md)。

- sidecar 行数: 640
- metric_stage 分布: stage_a_only=640
- (1) Stage A 落ち全体 `total_pnl_stage_a` 分布: n=640, mean=-910340.6875, median=-1000215.0000, std=271390.5526, min=-1006370.0000, max=140.0000
- (2) Stage A 落ち かつ trade_count>0 の `total_pnl_stage_a` 分布 (n=632): n=632, mean=-921863.9873, median=-1000230.0000, std=252907.5547, min=-1006370.0000, max=140.0000
  - うち PnL=0 個体: 0 件 (取引したのに PnL=0 = Run 9 監査の対象観測)
- (3) Stage A 通過個体: 0 件 (比較対照なし)

## Archive Top-5 個体一覧

> Best とは別物です。`fitness_pen` 単独降順。Best は (feasible, -violation, stage_b_pass, stage_c_feasible, stage_c_pass, stage_b_pass, stage_a_pass, fitness_pen) の辞書式 (v3.1_stage_b_priority, T046)。

| rank | name | gen | lane | instrument | fitness_pen | fitness_raw | A | B | C | trade_count | sharpe |
|-----:|------|----:|------|------------|------------:|------------:|---|---|---|----:|-------:|
| 1 | `g5_i10` | 5 | tier1_EUR_JPY | EUR_JPY | -0.0033 | 0.0057 | ❌ | ❌ | ❌ | 3412 | — |
| 2 | `g6_i0` | 6 | tier1_EUR_JPY | EUR_JPY | -0.0033 | 0.0057 | ❌ | ❌ | ❌ | 3412 | — |
| 3 | `g6_i4` | 6 | tier1_EUR_JPY | EUR_JPY | -0.0033 | 0.0057 | ❌ | ❌ | ❌ | 3412 | — |
| 4 | `g6_i24` | 6 | tier1_EUR_JPY | EUR_JPY | -0.0033 | 0.0057 | ❌ | ❌ | ❌ | 3412 | — |
| 5 | `g7_i0` | 7 | tier1_EUR_JPY | EUR_JPY | -0.0033 | 0.0057 | ❌ | ❌ | ❌ | 3412 | — |

## 収束履歴

| gen | best_fitness |
|-----|--------------|
| 0 | -0.027143136460600265 |
| 1 | -0.02687108038030102 |
| 2 | -0.02656007005393541 |
| 3 | -0.02656007005393541 |
| 4 | -0.003732550461116855 |
| 5 | -0.0033415112733920886 |
| 6 | -0.0033415112733920886 |
| 7 | -0.0033415112733920886 |
| 8 | -0.0033415112733920886 |
| 9 | -0.0033415112733920886 |
| 10 | -0.0033415112733920886 |
| 11 | -0.0033415112733920886 |
| 12 | -0.0033415112733920886 |
| 13 | -0.0033415112733920886 |
| 14 | -0.0033415112733920886 |
| 15 | -0.0033415112733920886 |

## 分析

### analysis-claude.md

# RUN run_20260504_043138 (run-28、 上書きで run-27 表記) 分析（Claude 自己分析）

**作成日時**: 2026-05-04 14:32 JST
**run_id**: run_20260504_043138
**run_number**: 27 (= run-27.md 不在で get_latest_run_number=26 → next 27 で上書き、 副次 bug)
**前 cycle 1 から引き継ぎ**: best fitness_pen 0.098 (= Run-27 -0.008 から positive 化)、 stage_a_pass=142 ✨
**dataset**: EUR_JPY 2025-10-01 〜 2026-04-01 (183403 bars)
**ga_config**: pop=40 / gen=15 / max_clause=1 / max_depth=4 / max_workers=2
**stage_a_threshold**: -0.0172 (calibrate-gate cycle 1 適用)

## 前提差分
なし (= archive Parquet / summary.json / scripts/codex 全て確認済)

## 観察事実 (Facts)

### F1. Stage 通過数 (= Stage A 大幅改善、 Stage B が次の壁)

| Stage | pass=True | pass=False | 通過率 |
|---|---:|---:|---:|
| A | **142** | 498 | 22.2% (Run-27 0% から大改善) |
| B | 0 | 640 | 0.0% (= 次の壁) |
| C | 0 | 640 | 0.0% |
| graduation_count | — | — | 0 |

### F2. Best fitness (= positive 領域に到達)

- **best fitness_pen = 0.150908** (= Run-27 -0.0079 から positive、 g11_i31 @ generation 11)
  - trade_count=48, trade_sharpe_raw=0.1599, n_nodes=2
- 同値 cluster top: g14_i29 / g15_i0 / g15_i2 / g13_i2 = fitness_pen=0.098 で安定

### F3. Stage A passed 個体 142 個 の特徴 (= F1 の内訳)

| metric | min | max | mean | median |
|---|---|---|---|---|
| fitness_pen | -0.0172 (= threshold ぎりぎり) | 0.151 | 0.023 | 0.016 |
| trade_sharpe_raw | (raw>0 個体多数) | 0.160 | 0.0325 | — |
| **trade_count** | (低 trade) | 2907 | **115** | **55** ⚠ |
| n_nodes | 1 | — | 2.06 | 2 |
| active_clause | 1 (固定) | 1 | 1 | 1 |

= **Stage A pass 個体の trade_count は median 55 = 低 trade 寄り**。 size_norm penalty を最小化する戦略学習。

### F4. Stage B 失敗理由 (= 142 通過個体の Stage B 内訳)

```
stage_b_reason_codes (a_pass 142 個体):
  median_oos_sharpe<min;positive_fold_ratio<min                          132 (93%)
  median_oos_sharpe<min;positive_fold_ratio<min;all_folds_unavailable     10 (7%)

stage_b_unavailable_reason_counts:
  trade_count_below_min: 7    125 個体
  trade_count_below_min: 9     10 個体
  trade_count_below_min: 8      4 個体
  trade_count_below_min: 0      3 個体 (= 全 fold 通過)
```

= **125/142 (88%) が fold 内 trade_count_below_min**: fold 内で trade が 10 (= `fold_trade_count_min: 10`) 未満で fold 評価不能。

### F5. Stage B fold metrics (a_pass のみ、 n=142)

| metric | mean | median | range |
|---|---|---|---|
| n_fold_effective | 1.98 | 2 | [0, 9] |
| positive_fold_ratio_effective | 0.473 | 0.5 | [0, 0.5] (max 0.5! 上限制約あり) |
| trade_sharpe_stage_b | 0.0034 | 0.0056 | [-0.055, 0.040] |

- **n_fold_effective mean=1.98** = 5 fold 中 2 fold しか成立しない (= 残 3 fold は trade_count_below_min)
- **positive_fold_ratio max=0.5** = 5 fold で 2/4 fold が positive sharpe = `positive_fold_min: 0.60` 未達
- **trade_sharpe_stage_b max=0.040** = `median_oos_sharpe_min: 0.05` 未達

= 2 つの hard gate (`positive_fold_min=0.60` / `median_oos_sharpe_min=0.05`) を **構造的に同時達成不能**。 fold 数不足 + sharpe 不足の AND condition で 142 全個体 fail。

### F6. Generation 別 Stage A pass 推移 (= 進化が機能している証拠)

| gen | n | a_pass | fitness_pen max | raw max |
|---|---|---|---|---|
| 0 | 40 | 0 | -0.0494 | -0.0359 |
| 1 | 40 | 0 | -0.0303 | -0.0235 |
| 2 | 40 | 1 | 0.0163 | 0.0253 |
| 5 | 40 | 5 | 0.0163 | 0.0253 |
| 10 | 40 | 16 | 0.0163 | 0.0253 |
| **11** | 40 | 17 | **0.1509** | **0.1599** (=best 出現) |
| 14 | 40 | **19** | 0.0981 | 0.1071 |
| 15 | 40 | **20** | 0.0981 | 0.1071 |

= GA 進化が **機能**。 generation 進行で a_pass 数が単調増加 (0 → 20 / 40 = 50% 通過率)。

### F7. cycle 1 で発見した副次 bug (= cycle 2 で扱う候補)

- run_number=27 で Run-28 が上書き (= `get_latest_run_number.py` が run-{N}.md を見るため、 N.md 不在で 26 を返却 → next=27)
- archive write vs summary write の run_id 不一致 (cycle 1 § 6.5 で記録)

## 解釈・推論 (Interpretations)

### I1 (Critical, 反証可能性 高): Stage A 通過個体の trade_count が低すぎ → Stage B fold-level で trade 不足

- F3: Stage A pass の trade_count median=55, mean=115
- F4: 88% (125/142) が `trade_count_below_min: 7` (= fold 内 7 trade で fold_trade_count_min=10 未満)
- F5: n_fold_effective mean=1.98 (= 5 fold 中 約 3 fold が trade 不足で skip)
- = **「Stage A は low-trade を許容、 Stage B は 1 trade/日以上要求」 の構造的不整合**

config 確認:
- `ga.feasibility.entry_count_min: 50` = GA selection_score の feasibility bit (Stage A 判定とは別経路)
- `stage_gate.stage_a.min_exposure_trade_count: 1` = Stage A の no_exposure 判定 (= 1 trade 未満で fail)
- `stage_gate.stage_b.fold_trade_count_min: 10` = Stage B fold 単位の sharpe 計算最低 trade 数

= **Stage A min_exposure_trade_count=1 が事実上 no-trade のみを除外 = ほぼ無効**。 Stage A 設計の「fast screen」 として trade 数の最低要求がない。

**反証**: もし fold-level trade 数が十分 (= a_pass median trade_count >= 100) でも Stage B が fail (= trade_sharpe < 0.05) なら、 root cause は trade 数不足ではなく primitive 表現力 / Stage B 判定基準の問題。

### I2 (Warning, 反証可能性 高): live_criteria 整合性 (= 北極星)

- `live_criteria.trade_count_min: 50` (= config) = mission 達成個体は最低 50 trade 必要
- Run-28 best (g11_i31): trade_count=**48** ← live_criteria.trade_count_min=50 **未達**
- = best 個体ですら mission 達成基準を構造的に満たさない
- **反証**: 仮に trade_count >= 50 + sharpe >= 1.0 (annualized) を満たす個体が出現しても、 そこから cross-pair 評価で再選別される (= 中期)

### I3 (Concern, 反証可能性 中): Stage B median_oos_sharpe_min=0.05 / positive_fold_min=0.60 の 2 段 hard AND

- Stage B trade_sharpe max=0.040 (config 0.05 未達) かつ positive_fold max=0.5 (config 0.60 未達)
- 2 個別の閾値を同時に超える必要 = 2 段 AND の確率 = 個別確率の積 (= 統計的に厳しい)
- ただし synthesis § 5 で「fold pooled が主判定、 fold 単位は fail-fast 補助」 とある = 設計上は AND ではない可能性
- **反証**: Stage B 判定式を Read で確認、 OR / pooled / AND の正解を SSOT 確認

### I4 (Concern, 反証可能性 中): Stage A pass 個体に「low-trade な best 戦略」 が固定 (= elite による)

- F2: best cluster (g11_i31, g14_i29, g15_i0, g15_i2) は trade_count=48-51 で固定
- elite_count=2 + tournament_size=3 で「low-trade で fitness_pen 高い個体」 が dominant 化
- = GA selection が low-trade 戦略を増殖、 「取引回数削減で見かけ向上」 (= 禁止事項 #6) の構造的萌芽

**反証**: もし feasibility の entry_count_min=50 が selection_score で機能していれば、 trade_count<50 の個体は劣位選抜のはず。 しかし best=48 < 50 なので feasibility bit が active な状態だが、 まだ low-trade が増殖。

### I5 (Notable, 反証可能性 高): cycle 1 真の root cause = threshold 設計 = (Q) 仮説

- cycle 1 で「P1 primitive / P2 penalty / P3 探索 dynamics」 を仮説立てたが、 全部 root cause ではなかった
- 真の root cause は **threshold 0.0 が厳しすぎた** = (Q) threshold 設計
- = improvement loop の重要な学び: 仮説を 3 つに絞り込んで誤り、 4 つ目が正解

### 禁止事項違反検知

| # | 禁止事項 | 観察 | 判定 |
|---|---|---|---|
| 1 | 評価期間延長 | 不変 | OK |
| 2 | 数値操作 | trade_count<live_criteria.trade_count_min で「見かけ Sharpe 高」 = 警戒 | ⚠ Concern (I2) |
| 3 | GA ハック | なし | OK |
| 4 | live_criteria 緩和 | 不変 | OK |
| 5 | やたら複雑な案 | 不変 | OK |
| 6 | **取引回数削減で見かけ向上** | best=48 trade で fitness_pen=0.151 = high sharpe = 削減で見かけ向上の構造 | ⚠ **Critical** (I4) |
| 7 | オーバーナイト前提 | 不変 | OK |
| 8 | archive スキーマ伝搬漏れ | archive_role / source_stage 全 NaN (= cycle 1 と同じ、 dormant chain 待ち) | ⚠ Concern |

## 次サイクル候補

### [Critical] Stage A min_exposure_trade_count を 1 → live_criteria.trade_count_min と同期 (= 50 想定)

= **構造的整合性 (= Stage A → Stage B → live_criteria の 3 段階で trade_count 要求が monotone increasing)**:
- 現状: Stage A=1 / Stage B fold=10 / live_criteria=50 → Stage A は live_criteria の 1/50 で「low-trade を許容」 = 不整合
- 提案: Stage A `min_exposure_trade_count: 50` (= live_criteria.trade_count_min と同期) → low-trade を Stage A で fail = 禁止事項 #6 構造的解消

target_metric: Stage B pass>0 の前提条件確立 (= Stage A pass 個体の median trade_count が live_criteria.trade_count_min を超える)
failure_mode: Stage A 通過個体の median trade_count=55 / fold 内 trade=7 < fold_trade_count_min=10
causal_path: Stage A min_exposure=1 → low-trade individual 通過 → Stage B fold 内 trade 不足 → fail
falsification: もし Stage A min_exposure=50 で a_pass 数が劇減 (例: 142 → 5 未満) なら primitive 表現力不足の方が支配的 = 棄却して P1 へ
success_criterion: Stage A pass 個体の median trade_count >= 50 + Stage B fold 内 trade>=10 個体が増える
変更分類: **Structural** (= Stage 設計の整合性回復、 数値弄りではない)

### [Warning] Stage B 判定式 SSOT 確認

I3 で「median_oos_sharpe AND positive_fold AND fold_trade」 の AND condition が厳しすぎないか synthesis § 5 と実装 (`stage_gate.evaluate_stage_b`) を Read で確認。 設計通り AND なら受容、 OR / pooled が SSOT なら実装 bug。

### [Warning] cycle 1 副次 bug (= run_number 上書き / archive vs summary run_id ズレ) を別 TODO 化

cycle 2 主題ではないが、 後続 cycle で扱うため TODO 候補。

## 全体判定: **PROGRESSING** (= cycle 1 で Stage A 突破、 cycle 2 で Stage B が次の壁)

cycle 1 で「Stage A pass=0 = 北極星から構造的隔絶」 から脱出。 cycle 2 では Stage B 突破を狙うが、 root cause が「low-trade Stage A pass = fold-level trade 不足」 という構造的不整合と判明。 Stage A 設計の整合性回復で対処可能 (= Structural 変更、 数値弄りではない)。

北極星「live_criteria 充足」 への現在地: trade_sharpe_raw max 0.16 / live_criteria.sharpe_min=1.0 = **約 6 倍改善余地**。 Run-27 baseline 1000 倍 → Run-28 6 倍に短縮 = 大幅前進。

### analysis-codex.md

**前提（C4）**
- `verified`: Run-28でStage Aは`142/640`通過、Stage B/Cは`0`。
- `verified`: Stage A通過個体の`trade_count`は`median=55`、bestは`48`。
- `verified`: Stage Bで`fold_trade_count_min=10`未満が多数（`trade_count_below_min:7/8/9`中心）。
- `verified`: `live_criteria.trade_count_min=50`に対し、`stage_a.min_exposure_trade_count=1`。
- `inconclusive`: この乖離が「意図設計」か「不整合バグ」か（設計文書の明示根拠未提示）。
- `inconclusive`: primitive偏在・cross-pair差の定量（データ未提示）。

**Facts（C6）**
- Stage A改善の主因は閾値`0.0 -> -0.0172`（通過率が0%→22.2%）。
- Stage B失敗は実質2層:
  - 統計不足（fold成立不足、`all_folds_unavailable`含む）
  - 成立foldでも性能不足（`trade_sharpe_stage_b max=0.040 < 0.05`、`positive_fold_ratio max=0.5 < 0.6`）
- 低取引群（48-51）が上位に残る現象がある。

**Interpretations（C6）**
- I1は**有力だが単独根因ではない**。  
  理由: fold不足は説明できるが、fold成立後のSharpe/ratio不足は別問題。
- 禁止事項#6の兆候は**spuriousよりreal寄りの構造リスク**。  
  理由: 現行ゲートで低取引個体が生存しやすい。
- Stage B AND条件は厳しいが、現時点では「厳しすぎる」より「入力個体品質不足」の寄与が大きい。

**仮説ごとの反証可能性（C9）**
- H1: 「Stage Aの`min_exposure=1`がボトルネック」
  - 反証テスト: Run-29で`min_exposure=50`に同期（他固定）。
  - 予測: Stage A通過数は大幅減、`all_folds_unavailable`/`trade_count_below_min`は大きく減る。
  - 反証条件: それでもfold不足がほぼ同率ならH1棄却方向。
- H2: 「低取引bestは本物シグナル」
  - 反証テスト: 同戦略群のfold別Sharpe分布とpair別再現性を確認。
  - 反証条件: fold間・pair間で符号/順位が不安定なら偶然優位（spurious）寄り。
- H3: 「Stage B条件が主犯」
  - 反証テスト: まずH1実施後に失敗内訳再計測。
  - 反証条件: unavailable解消後も`median_oos_sharpe`不足が支配的なら、主犯は条件でなく信号品質。

**次サイクル候補**
- `Critical(1)`: `stage_a.min_exposure_trade_count`を`live_criteria.trade_count_min(=50)`へ同期（単一変更）。
- `Warning(2)`: Run-29でStage B失敗理由の再分解（unavailable由来か、Sharpe/ratio由来か）。
- `Warning(3)`: 低取引上位クラスター（48-51）のfold安定性監査（禁止事項#6の早期検知）。

**Q1-Q5への短答**
- Q1: 反証可能。上記H1テストで可能。予測は「A通過急減、fold不足減、ただし性能不足は残存可能」。
- Q2: 現状は**realな構造的萌芽**と判定（本物シグナル断定は不可、`INCONCLUSIVE`）。
- Q3: 1つに絞るなら**I1（min_exposure=50同期）**。
- Q4: 設計意図かバグかは**INCONCLUSIVE**。ただし運用上は不整合（実質バグ相当）として扱うのが妥当。
- Q5: cycle 2は「高情報量の単一変更」を事前登録し、反証条件を先に固定して評価する（今回ならI1）。

**全体判定**
- **CONCERN**（CRITICAL_DRIFTまでは未到達だが、#6の芽は明確に監視対象）。

### analysis-merged.md

# マージ分析: cycle 2 (Run-28 → Run-29)

**作成日時**: 2026-05-04 14:35 JST
**前提**: analysis-claude.md / analysis-codex.md
**全体判定**: Claude=PROGRESSING / Codex=CONCERN (= CRITICAL_DRIFT 未到達、 #6 監視)

## 合意事項 (両者一致)

| # | 合意点 |
|---|---|
| C1 | Run-27 → Run-28 で Stage A pass 0 → 142 (= calibrate-gate threshold 改善が支配的) |
| C2 | Run-28 best=g11_i31 trade_count=48 < live_criteria.trade_count_min=50 (= mission 基準未達) |
| C3 | Stage A pass 142 個体の median trade_count=55 = 低 trade 寄り |
| C4 | 142 個体中 88% (125/142) が fold_trade_count_min=10 未満で Stage B fail |
| C5 | Stage A min_exposure_trade_count=1 と live_criteria.trade_count_min=50 のスケール乖離 |
| C6 | 禁止事項 #6 (= 取引回数削減で見かけ向上) の構造的萌芽あり |
| C7 | cycle 1 真の root cause = (Q) threshold 設計、 仮説 P1/P2/P3 全部外れ |

## Codex 独自の重要指摘 (= Claude 修正)

| # | 指摘 | C ルール |
|---|---|---|
| Cx1 | **I1 は有力だが単独根因ではない**: fold 不足は説明できるが fold 成立後の Sharpe/ratio 不足は別問題 | C9 反証可能性 |
| Cx2 | 禁止事項 #6 兆候は real 寄り (= INCONCLUSIVE)、 本物 signal 断定不可 | C8 |
| Cx3 | Stage B AND 条件は厳しいが、 現時点では「入力個体品質不足」 が主寄与 | C9 |
| Cx4 | H1 (= I1) 反証テスト: min_exposure=50 同期 → 予測「Stage A pass 急減、 fold 不足減、 ただし性能不足残存可能」 | C9 |
| Cx5 | cycle 2 は「高情報量の単一変更」 + 反証条件先固定 (= I1) | C4 / C9 |

## 統合改善提案 (= 1 つに絞る、 Codex Cx5 推薦)

### P1 (Critical, 単一変更): Stage A min_exposure_trade_count を 1 → live_criteria.trade_count_min (= 50) と同期

- **target_metric**: Stage B pass>0 の前提条件確立
- **failure_mode**: Stage A 通過個体 median trade_count=55 / fold 内 trade=7 < fold_trade_count_min=10 / 88% Stage B fail with `trade_count_below_min`
- **causal_path**: Stage A min_exposure=1 → low-trade individual 通過 → Stage B fold 内 trade 不足 → fail
- **falsification (= H1 反証テスト、 Codex Cx4)**:
  - 予測 (a): Stage A pass 数大幅減 (= 142 → ?)
  - 予測 (b): `trade_count_below_min` 大幅減 (= 125 → ?)
  - 反証条件: Stage A pass 急減 + fold 不足解消後も `median_oos_sharpe<min` が支配的 → H1 棄却 = root cause は signal 品質
- **success_criterion**:
  - Stage A pass 個体の median trade_count >= 50
  - `trade_count_below_min` 件数 < 10 (= 大幅減)
  - Stage B fail 理由が `trade_count_below_min` から `median_oos_sharpe<min` 主体へシフト (= signal 品質問題が露出)
- **変更分類**: **Structural** (= 整合性回復、 Reactive Parametric ではない、 live_criteria SSOT との同期)
- **補助監視**: low-trade cluster (trade_count 48-51) の fold 安定性 = 禁止事項 #6 早期検知 (= Codex Cx5)

### 却下 / 保留

- **Stage B 判定式の閾値緩和**: 設計通り AND condition、 緩和は禁止事項 #4 (= live_criteria 緩和の派生)
- **fold_trade_count_min=10 緩和**: T054 で「機能していた当時の挙動を意図的に再現する設計判断」 と記載、 緩和は SSOT 違反
- **primitive 改革**: post-run-review 担当 (= 当 cycle 範囲外、 中期キュー)
- **cycle 1 副次 bug** (= run_number 上書き / archive vs summary run_id ズレ): 別 TODO 切り出し、 当 cycle 主題ではない

## 反証条件 (= cycle 2 事前登録、 Codex Cx5)

Run-29 後に以下を確認:
1. Stage A pass 数 ≈ 142 → 5-30 (= 大幅減を予測、 もし ≈ 142 のまま = entry_count_min と min_exposure_trade_count の経路独立性 bug)
2. Stage A pass median trade_count >= 50 (= must)
3. fold `trade_count_below_min` 件数 < 10 (= 大幅減)
4. Stage B fail 理由分布: `trade_count_below_min` < `median_oos_sharpe<min`

これらが満たされなければ H1 棄却、 別仮説 (= signal 品質 / Stage B 厳しさ等) へ進む。

## 次フェーズへの申し送り

- B-2 で「単一変更 + 反証条件先固定」 を Codex に APPROVE 確認
- Phase C 詳細設計: config 1 行修正 (= `stage_gate.stage_a.min_exposure_trade_count: 1` → `50`) + テスト追加
- Phase 4 RUN: 完全同条件で再走、 reverse condition 観察

