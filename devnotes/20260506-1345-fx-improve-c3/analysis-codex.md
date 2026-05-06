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