1. 結論は **(A) positive_fold_ratio_effective gate 追加** が最適です。  
理由は、mission整合（OOS一貫性を直接見る）、情報価値（R101で n=723 を即検証可能）、コスト効率（実装ほぼ不要）、in-loop安全性（段階的に閾値を置ける）の4点で最もバランスが良いからです。  
(B)は有望ですが今は NaN で「まず特徴量実装」が必要、(C)は安全だが学習価値が一段落ちます。

2. 4軸飽和後の「閾値引き上げ」の意味は、**同じ軸を締めることではなく、非hollowで直交的な品質軸を追加すること**です。  
- `positive_fold_ratio` は「真の品質向上」になり得る（holdout改善と連動すれば）。  
- `sortino` は現時点では未計算なので、今は品質軸ではなく feature backlog です。  
- 連動が出なければ `positive_fold_ratio` も「形式的追認」と判定して打ち切るべきです。

3. (A)採用時の初期値は **`positive_fold_ratio_effective >= 0.55`** を推奨します。  
`min=0.500, median=0.618` の中間で、低一貫性の裾を切りつつ全滅リスクを抑えられます。  
予測は **dd型（安全寄り）**。ただし「StageB指標だけ改善し holdout PnL が落ちる」なら 74k 型崩壊シグナルです。

4. R103 の反証可能な成功/失敗基準（5条件）
1. `live_criteria + pfr>=0.55` 達成数が **145以上**（R101=723の20%以上）。  
2. 達成群の holdout `median total_pnl` が **80,000以上**。  
3. 達成群の holdout `median annualized sharpe` が **5.3以上**。  
4. 74k崩壊検知: `StageB median`上昇と`holdout median pnl`大幅低下（-10%超）の乖離が**発生しない**。  
5. 別seed再現で、達成数 **100以上** かつ `median pnl >= 75,000`。

全体判定: **A（positive_fold_ratio_effective を 0.55 で追加し、R103で 74k型崩壊を反証する）**。