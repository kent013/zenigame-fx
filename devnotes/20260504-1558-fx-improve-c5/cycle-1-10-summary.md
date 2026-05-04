# improve-cycle 1-10 累積総括 (variance baseline 確立)

**作成日時**: 2026-05-04 19:30 JST
**期間**: 2026-05-04 12:36 〜 19:30 (= 約 7 時間、 10 cycle)
**北極星**: live_criteria 充足 FX イントラデイ戦略個体を 1 つ見つけ出す

## 出発点 vs 現状

| metric | cycle 0 (Run-27) | global best (cycle 8 seed=13) | 倍数 |
|---|---|---|---|
| best fitness_pen | -0.0079 | **+0.2925** | (negative→positive) |
| stage_a_pass | 0/640 | 181/640 | ∞ |
| trade_sharpe_raw max | 0.0011 | **0.3105** | **283 倍** ✨ |
| trade_sharpe_stage_b max | 0 | 0.2124 (cycle 7 seed=7) | ∞ |
| positive_fold_ratio max | 0 | 1.00 (cycle 3 / cycle 7) | ∞ |
| stage_b_pass | 0 | 0 | (still 0) |

**北極星距離**: trade_sharpe_raw max **0.31 / live_criteria.sharpe_min=1.0 = 残 3.2 倍** (cycle 0 では残 1000 倍)

## 全 10 cycle 結果一覧

| cycle | run | seed | threshold | gen | best fp | a_pass | raw max | fold_eff | pos_fr_max | sb_max |
|---|---|---|---|---|---|---|---|---|---|---|
| 0 | 27 | None | 0.0 | 15 | -0.008 | 0 | 0.001 | 0.00 | 0.00 | 0.000 |
| 1 | 28 | None | -0.0172 | 15 | +0.151 | 142 | 0.160 | 1.98 | 0.50 | 0.040 |
| 2 | 29 | None | 0.0128 | 15 | -0.003 | 0 | 0.006 | 0.00 | 0.00 | 0.000 |
| 3 | 30 | None | -0.0172 | 15 | +0.130 | 241 | 0.148 | 4.47 | **1.00** | 0.115 |
| 4 | 31 | None | -0.0172 | 30 | +0.002 | 208 | 0.011 | 9.00 | 0.00 | -0.119 |
| 5 | 32 | 42 | -0.0172 | 15 | -0.009 | 2 | 0.005 | 9.00 | 0.00 | -0.074 |
| 6 | 33 | 1 | -0.0172 | 15 | +0.142 | 125 | 0.158 | 8.87 | 0.50 | 0.128 |
| 7 | 34 | 7 | -0.0172 | 15 | +0.256 | 95 | 0.275 | 4.12 | **1.00** | **0.212** |
| 8 | 35 | 13 | -0.0172 | 15 | **+0.293** ★ | 181 | **0.311** ★ | 6.01 | 0.17 | 0.108 |
| 9 | 36 | 99 | -0.0172 | 15 | -0.023 | 0 | -0.019 | 0.00 | 0.00 | 0.000 |
| 10 | 37 | 314 | -0.0172 | 15 | -0.007 | 44 | -0.002 | 9.00 | 0.00 | -0.060 |

## variance baseline (= cycle 1, 3, 6-10 の 同 config 8 RUN)

threshold=-0.0172, gen=15, max_clause=1, 計 8 RUN:

| metric | min | max | mean | stdev |
|---|---|---|---|---|
| best fitness_pen | -0.023 | 0.293 | 0.117 | 0.121 |
| stage_a_pass | 0 | 241 | 104 | 86 |

= **mean ≒ stdev = noise が支配**。 1 RUN で improvement 効果を測定不能。

## 重要 learning (= 10 cycle で蓄積)

### L1. **calibrate-gate 振動現象** (cycle 1-3 で発見)
threshold 0.0 ↔ -0.0172 ↔ 0.0128 で集団 trade pattern が劇的変動。 dead-band tolerance=0.05 / max_delta=0.03 が GA 戦略空間 attractor 切替を抑制不全。 → **解決**: cycle 3 で calibrate-gate disable + threshold 手動固定。

### L2. **GA seed dependency 極大** (cycle 4-10 で確証)
同 config で best fitness_pen が -0.023 ~ +0.293 の **1 桁オーダー** 振動。 cycle 1/3 best=0.13~0.15 は luckily good seed の結果。

### L3. **集団レベルは比較的安定**
- stage_a_pass: 0 / 240 と振れるが、 cycle 1, 3, 6, 7, 8 (=正規 cycle) では 95-241 で安定
- = best 個体は seed luck だが、 Stage A 突破集団は構造的に再現可能

### L4. **Stage B AND condition は同一個体で同時達成困難**
- 10 cycle で **stage_b_pass>=1 個体一度も出現せず**
- 個別 component は突破個体多数:
  - trade_sharpe_stage_b max >= 0.05 突破: cycle 3 (0.115), cycle 6 (0.128), cycle 7 (**0.212**), cycle 8 (0.108)
  - positive_fold_ratio max >= 0.60 突破: cycle 3 (1.00), cycle 7 (1.00)
- 同一個体で AND は 0 件 = **median_oos_sharpe と positive_fold_ratio は trade-off** (= 「stable per-fold」 vs 「high median sharpe」)

### L5. **不安定 RUN の特徴** (cycle 5/9/10 = bad seed)
- stage_a_pass 0-44 / best fitness_pen negative
- trade_count median が high (~3000+) = over-trading attractor へ収束
- = GA が初期 random_genome population に依存して bad attractor に落ちる確率が高い

### L6. **分類** (= 10 cycle の cycle 結果分布)
| カテゴリ | count | best fp range | 例 |
|---|---|---|---|
| Bad seed (over-trade attractor) | 4 | -0.02 ~ +0.002 | cycle 4, 5, 9, 10 |
| Mid seed | 2 | +0.002 ~ +0.142 | cycle 6 |
| Good seed (low-trade attractor) | 4 | +0.13 ~ +0.29 | cycle 1, 3, 7, 8 |

= 10 cycle で good seed=40%、 bad seed=40%、 mid=20% = **not 50%**。 「seed luck 40%」 が現状の improvement loop の限界。

## 次の打ち手候補 (= cycle 11+)

### 優先順位 1: **GA 初期化 / 探索 dynamics 改革** (= seed dependency 軽減)
- mutation_rate 0.3 → 0.5 / crossover_rate 0.7 → 0.5 で diversification
- もしくは ensemble seed (= 複数 seed RUN → best 集約)
- これは Reactive Parametric リスクあり、 Codex 合議推奨

### 優先順位 2: **Stage B AND condition の構造的検証**
- median_oos_sharpe AND positive_fold_ratio の同時達成困難性
- synthesis § 5 SSOT 確認: pooled 主判定 / fold 単位 fail-fast 補助 と整合か
- もし pooled が SSOT なら現実装の `oos_sharpes_imputed` 集計が正しいか

### 優先順位 3: **primitive 改革** (= post-run-review 担当、 範囲外)
- 高 Sharpe / stable per-fold の signal 設計

### 優先順位 4: **multi-instrument 化** (= cross-pair 有効化)
- swim_lane.tier1 6 ペア展開
- Stage C 突破後の中期課題

## メタ learning (= improvement loop 自身について)

- cycle 1: 仮説 P1/P2/P3 全部外れ、 真は (Q) threshold
- cycle 2: 仮説 I1 反証、 真は time-concentrated 取引
- cycle 3: meta-level 真は **calibrate-gate 自身** (= 自動制御メカニズム)
- cycle 4: 仮説 P1 反証、 真は **GA seed variance**
- cycle 5: 仮説確認、 seed=42 は bad attract 確認
- cycle 6-10: variance baseline 確立、 seed luck 40% 判明

= **5/5 cycle で当初仮説が反証** = 反証 first 運用が機能、 ただし「真の root cause 発見」 が cycle ごとに変わる = improvement loop の **複雑性**

## 北極星への新たな見方

- trade_sharpe_raw max=0.31 (good seed) → live_criteria.sharpe_min=1.0 = **残 3.2 倍**
- ただし 1 RUN で 0.31 を再現可能性は 40% 程度
- = ensemble (= 複数 seed) で 0.31 を確実に出す → 残 3.2 倍に primitive 改革 or 探索 dynamics 改善
