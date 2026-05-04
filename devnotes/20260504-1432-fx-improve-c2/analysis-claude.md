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
