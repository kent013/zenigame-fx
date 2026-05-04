前提を固定して結論を出します。今回は提示データのみで判定し、未検証は `INCONCLUSIVE` とします。

**前提検証（C4）**
- `g8_i33/g12_i17` はともに `stage_b_pass=True`, `n_fold_effective=9`, `positive_fold_ratio_effective=6/9=0.667`。
- `fold_trade_count_min=10`、`trade_count=16/17`、`stage_b_unavailable_reason_counts=全0` は確認済み。
- `live_criteria.trade_count_min=50` は確認済み。

**Fact（C6）**
1. Q1: `5 folds` 規範との乖離  
- もし `wf_*_days` が「営業日」実装なら、6か月（約120営業日）で9foldは出にくい。  
- ただし「実データ期間の認識違い」または「fold単位が日でない」可能性があり、現時点で bug 断定不可（C1/C2, `INCONCLUSIVE`）。

2. Q1補足: `positive_fold_min=0.60` の厳しさ  
- 9foldだと閾値は実質 `ceil(0.60*9)=6` なので `6/9=0.667` 必要。  
- 5foldだと `3/5=0.60`。  
- よって「9foldだから緩い」は成立しません。離散化の都合でむしろ厳しめです。

3. Q2: `fold_trade_count_min` 整合性  
- 全fold成立なら foldごと最低10件が必要な解釈では総計90件以上が必要。  
- 実測16/17とは論理矛盾。  
- したがって「`fold_trade_count_min` は per-fold gate として効いていない」か「`trade_count` の計測スコープが別」のどちらか（高確度）。

4. Q3: North Star整合性  
- Stage B通過個体が `trade_count<50` で Stage C落ちし続ける構造は現実に起きている。  
- これは禁止事項 #6（見栄え改善方向）と逆で、むしろ評価段の接続不整合の問題。

**結論（1 round 収束）**
- cycle 21 の最小変更は **案Aを一点集中**：  
  **Stage Bの fold有効性判定（特に `fold_trade_count_min`）を SSOT で明文化し、decision_trace に foldごとの `oos_trade_count / available判定理由` を必須出力**。  
- live_criteriaを即Stage BへAND注入（案B/C）は、まず gate実装実態を確定する前だと C1/C9違反リスクが高い。

**反証可能仮説（Q5）**
- 仮説H:  
  「low-trade個体のStage B通過は、`fold_trade_count_min` の per-fold適用欠落（または等価のスコープ不整合）が主因である。」

**1 cycleでの最小実験**
1. 判定ログを fold単位で固定出力（`oos_trade_count`, `is_available`, `unavailable_reason`）。  
2. `fold_trade_count_min` を per-fold availability に強制適用（値は変更しない）。  
3. 同一設定で cycle 21 実行。  
4. 反証条件:  
- もし g8_i33/g12_i17 がなお `stage_b_pass=True` なら仮説Hは棄却。  
- `stage_b_pass=False` へ反転し、通過群の trade_count 分布が上がれば仮説H支持。

この順なら「数値操作なし」「仕組み先行」「1サイクル検証可能」を満たします。