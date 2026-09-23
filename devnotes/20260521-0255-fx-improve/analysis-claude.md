# RUN run_20260520_152204 (Run 83) 分析（Claude 自己分析）

## 前提差分
なし（archive Parquet / summary.json / analyze_run.py / codex 全て疎通確認済み）。本 Run は T109 (Stage B→C gap diagnostic v1) 適用後の最初の full run。

## 観察事実（Facts）

### Stage 通過数（vs Run 82）
| Stage | Run 83 | Run 82 | 差分 |
|-------|--------|--------|------|
| A pass | 717 | 2687 | -1970 |
| B pass | 436 | 941 | -505 |
| C pass | **43** | 0 | +43 ← Run 75 以来 2 度目の C>0 |
| graduated | 0 | 0 | ±0 |

- seed=68（Run82=67）。stage_b_gate_kind=profit_safe_pfr。Stage A/B が Run82 比で大幅減（seed variance、前ループでも確認済の現象）。

### ★ 使命達成（live_criteria all_pass=True）
best `g51_i71`（gen51, tier1_EUR_JPY, fitness_pen=0.0454）:
| 指標 | value | threshold | pass |
|------|-------|-----------|------|
| sharpe (annualized) | 4.24 | 1.0 | ✅ |
| total_pnl | 65210 | 50000 | ✅ |
| max_drawdown_pct | 1.49% | 20% | ✅ |
| trade_count | 51 | 50–5000 | ✅ |

→ **4/4 達成**。run-report も `🎯 使命達成` と判定。North Star（live_criteria 全達成個体の出現）に到達。

### Stage C 通過 43 個体の分布（mission-eligible 集団）
| 指標 | min | median | max |
|------|-----|--------|-----|
| total_pnl | 50260 | 51920 | 65210 |
| trade_count | 51 | 54 | 70 |
| trade_sharpe_stage_c (raw) | 0.167 | 0.212 | 0.290 |
| max_drawdown_pct | 1.49 | 2.46 | 2.86 |
| n_fold_effective | 34 | 34 | 34 |
| positive_fold_ratio_effective | 0.529 | 0.588 | 0.647 |
| mission_score | 0.966 | 0.971 | 0.983 |

→ **43 個体すべてが total_pnl≥50k かつ trade_count≥50**（best 1 体の lucky draw でなく、mission-eligible 集団）。

### Stage C 通過 43 個体の多様性（収束度）
- 世代分布: gen 43-60（18 世代に持続、単一世代の fluke ではない）
- **unique fitness_pen: 7 / 43**、**distinct primitive-set: 6 / 43** → 実質 ~6 種の genotype の複製。
- primitive 頻度: P7(43 全), P9(39), F4(39), P11(37) が支配的モチーフ。active_clause 1-2、n_nodes med 4（浅い）。
- → **1 戦略ファミリー（P7+P9+F4+P11 モチーフ）に収束**。内部的に持続するが genotype 多様性は低い。

### graduation=0 の構造的理由
- **ii_lite_pass が全 5856 個体で None**（cross-pair ii-lite は Phase 2 で shadow-only、gate 化されていない）。
- C-pass 43 個体の `canonical_gate_pass_c_shadow` は全件 False、persistence_score_shadow med 0.50。
- graduation = Stage C pass AND cross-pair pass の AND。cross-pair が None のため graduation は構造的に発火不能。

### ★ T109 diagnostic（Stage C 評価 436 個体の gap_class）
| gap_class | n | base_trade_count med | base_total_pnl med | stress_pnl_degradation |
|-----------|---|---------------------|--------------------|-----------------------|
| pnl_only | 162 | 58 (≥50 OK) | 36420 (全件 0<pnl<50k) | **0** |
| both_pnl_count | 176 | 38 (<50) | 27750 (-20640〜49470) | **0** |
| count_only | 35 | 44 (<50) | 59490 (≥50k profitable) | **0** |
| pass | 43 | 54 | 51920 | **0** |
| sharpe_involved | 20 | — | — | 0 |

## 解釈・推論（Interpretations）

### 1. mission 達成は「near-miss 群の山の頂上」であり、profit magnitude が binding
T109 診断が明快に示す: B→C gap の主因は **total_pnl の magnitude 不足**。
- pnl_only 162 個体は trade_count 十分（med 58）だが pnl が 18k-50k で **50k 閾値に僅差で未達**（near-miss、中央値 36k = 目標の 72%）。
- pass 43 と pnl_only 162 は連続体: 同じモチーフで pnl が 50k を超えたか僅かに届かなかったかの差。
- 反証可能性: もし pnl_only 群の primitive-set が pass 群と全く別系統なら「別の壁」。同系統なら「magnitude の連続的不足」。→ 次サイクルで pset 重なりを確認。

### 2. cost stress は B→C gap の要因では「ない」（stress_pnl_degradation=0）
全 436 個体で stress_pnl_degradation=0（spread×1.5 が PnL を 1 円も変えていない）。
- 解釈 A: これらの戦略の entry/exit は spread が binding しない時間帯/頻度 → cost robust。
- 解釈 B: stress 機構が実質 toothless（spread cost モデルが multiplier に非感応、または max_spread_bps が効いていない）。
- いずれにせよ **cycle 1 の H83 が想定した「cost 二次要因」は棄却**。cost は要因ですらない。
- 反証可能性: 解釈 B が真なら、spread_stress_multiplier を上げても degradation は 0 のまま。解釈 A が真なら、極端な multiplier では degradation>0 に転じる。→ 要検証（cycle 2 で stress 機構の健全性監査）。

### 3. graduation=0 は品質問題でなく「cross-pair が shadow-only」の構造
ii_lite_pass が常に None のため graduation は発火不能。**mission（live_criteria）は達成済だが、graduation という別ゲートが未配線**。
- これは「次の水準」の自然な候補: cross-pair ii-lite を shadow → hard gate に昇格すれば、graduation が真の汎化（複数ペアで通用）を要求する高い壁になる。
- 反証可能性: cross-pair を hard 化して graduation>0 が出れば真の多ペア汎化個体。0 のままなら EUR_JPY 特化の過学習。

### 4. 達成の頑健性は「未確定」（seed variance + 低 genotype 多様性 + 単一ペア）
- 43 個体は 18 世代持続するが ~6 genotype の複製（P7+P9+F4+P11 モチーフ 1 ファミリー）。
- 前ループ知見: profit_safe_pfr は seed variance 極端（Run 75 lucky の前例）。本 Run は seed=68 単発。
- cross-pair shadow は全 False、cross-seed 検証なし。
- → **単一 seed・単一ペア・単一モチーフの達成**。durable victory と断定するには cross-seed / cross-pair / OOS 検証が必要。**閾値の即時引き上げは時期尚早**。

### 5. 禁止事項違反の兆候
- 取引回数削減で見かけ改善（禁止 6）: C-pass の trade_count は 51-70 で live 下限 50 を実質満たす。near-miss 群も count med 58。回数削減の兆候なし。
- live_criteria 緩和: なし（閾値不変、達成は正味）。
- イントラデイ逸脱: max_dd 1.5-2.9% と健全、暴走なし。

## 次サイクル候補

- **[Critical] mission 達成の頑健性検証（cross-seed / cross-pair）を最優先**。単一 seed=68・単一ペア・~6 genotype の達成。次 Run を別 seed で回す or cross-pair ii-lite を shadow→hard 昇格して「複数ペア通用」を要求する。これが North Star の「達成後に水準を引き上げる」の正攻法（閾値緩和でなく gate 追加 = Structural）。
- **[Warning] cross-pair ii-lite の gate 化検討**: graduation=0 は ii_lite_pass=None の構造。shadow→hard 昇格で graduation を真の汎化ゲートにする（ただし全滅リスクは smoke で確認）。
- **[Warning] stress 機構の健全性監査**: stress_pnl_degradation が全個体 0。spread×1.5 stress が toothless でないか（cost robust なのか機構不全なのか）を切り分ける。toothless なら cost gate は形骸化。
- **[Warning] profit magnitude の押し上げ（pnl_only 162 near-miss 群）**: 多くが 36k 前後で 50k に僅差未達。同モチーフの pnl scaling（position sizing 等）を検討。ただし mission は既に達成済のため優先度は robustness より下。

## 全体判定
**OK（mission 達成、ただし要追検証）** — live_criteria 全達成個体が 43 出現（North Star 到達）。cost は B→C gap の要因でないと判明（stress=0）。残課題は (1) 達成の頑健性（seed/pair/motif 集中）、(2) graduation gap（cross-pair shadow-only）。閾値引き上げは robustness 確認後。T109 diagnostic は設計通り機能し、profit magnitude が binding constraint と特定した（cycle 1 の最大の成果）。
