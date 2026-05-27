前提を明示します（verified）  
- R101 control は frontier 達成が厚い（723, ann/pnl も高位）。  
- R106 は F15 実評価済みで、`A:76 -> B:41 -> C:0`。  
- cross-pair は長期で `ii_lite=0` 継続。  
- 既存レバーでは「A/Bで勝つがCで消える」失敗が再発。

1. F15失敗が(b)(c)(d)全体に与える示唆  
- 示唆は「高め」ですが一律ではありません。  
- 解釈: F15はMTF特有要因もある一方、今回の主失敗はより一般的な「表現力追加でA/B適合が先に立ち、C汎化が付いてこない」形です。  
- 推定: d（非線形トレンド）はF15に近い失敗再現リスクが高い。b/cはdよりは低いが、現状証拠からは「追加familyで自然に突破できる」確率は高くない。

2. (B') vs (C) vs (D) の収束  
- B' 新family: EV 中低。実装コストは中、失敗再発リスク高。  
- C cross-pair再挑戦: EV 低。負の履歴が厚く、直近の期待改善が最小。  
- D 総括+次軸: EV 高。コスト低中で、失敗モード（A/B→C乖離）に直接当てられる。  
- 収束: **D** を選ぶのが合理的。

3. Dを選ぶ場合の具体軸（北極星継続）  
- 軸: **過学習を減らす選択圧設計**。  
- 具体: Stage B fold-CVの「安定性」を連続値で selection key に追加する。  
- 例: `robust_score = median_oos_pnl - λ*IQR_oos_pnl - μ*downside_tail_penalty`（既存fold統計のみ、holdout情報は不使用）。  
- 理由: 新primitive追加より、今回の失敗原因である「A/B適合過多」を直接抑える方が、holdout汎化に因果的に近い。

4. 反証可能な次run成功基準  
- 2 seed で検証（同一条件）。  
- Gate 1 非退行: `pnl70k` 現行frontierで `stage_c_pass >= 650` かつ `median ann >= 5.4`。  
- Gate 2 崩壊耐性: 同軸を入れた `pnl74k in-loop` で `stage_c_pass > 0`（R97型の全滅を再発させない）。  
- Gate 3 再現性: 上記Gate2を2 seed中少なくとも1 seedで達成。未達なら軸を棄却。

全体判定: **D（過学習を減らす選択圧設計）**。次の一手は **Stage B安定性ペナルティを selection に連続値で組み込み、74k in-loop 崩壊の再現を止められるかを反証実験で判定**。