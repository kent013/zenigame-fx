**観察事実**
- Stage B は 834 個体通過し、`trade_count` と `max_dd` は満たせている（取引実行フェーズには到達）。
- しかし Stage C は 0 通過、best 個体でも `sharpe=-0.19`・`total_pnl=-16850`。
- `positive_fold_ratio_effective` の中央値は 0.78 と高く、fold 単位の勝率は悪くない一方で、収益量/分散調整後成績が負けている。

**解釈（C9 falsification-first）**
- まず反証すべき仮説: 「Stage C不通過の主因は閾値が厳しすぎるだけ」  
  - 反証根拠: best 個体自体が Sharpe/PnL 負で、閾値緩和だけでは本質解決しない可能性が高い。
- より有力な仮説: 「GAの最適化目標が Stage C 要件（Sharpe/PnL正）と構造的にずれている」  
  - `mission_score` が soft 合算のため、負PnL個体が生き残れる。

**推奨施策（1件）**
- **fitness設計改善**: GA を「可行性優先の2段階最適化」に変更する。  
  - 第1段: `total_pnl>0` かつ `median_oos_sharpe>0` を満たす個体を優先（満たさない個体は強いペナルティ）。  
  - 第2段: 可行性を満たした母集団内で mission_score 4軸を最適化。  
- これが最も影響力が高い方向です。理由は、現状ボトルネックが signal の有無ではなく「選抜圧の向き」に見えるためです。

**新規TODO設計（提案）**
- `target_metric`: Stage C pass count（0→>0）、B-pass内の `PnL>0 & Sharpe>0` 個体比率、best `total_pnl`、best `median_oos_sharpe`  
- `failure_mode`: soft合算fitnessにより、負PnL/負Sharpe個体が上位選抜され、Stage C可行領域へ収束しない  
- `causal_path`: fitnessを可行性優先へ変更 → 世代ごとの親選抜が正PnL/正Sharpe側へ偏る → Stage C通過候補密度が上がる  
- `falsification`: 変更後2-3 runで「B-pass内の正PnL正Sharpe比率」が有意に増えない、または Stage C pass が依然0なら仮説棄却（signal品質側へピボット）  
- `success_criterion`: 連続2 runで Stage C pass > 0、かつ best 個体が `total_pnl>0`・`median_oos_sharpe>0` を同時達成

**全体判定**
- Stage B突破は完了、現ボトルネックは **探索空間不足より選抜目的のミスマッチ** である可能性が高い。次の1手は fitness の構造修正が妥当です。