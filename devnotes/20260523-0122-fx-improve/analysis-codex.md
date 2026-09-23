1. Facts要約  
- Run 90（T117, `aggregate=min`）は Stage A/B/C が **0/0/0**、`stage_a_pass` 全個体 False で、Run 89（single-pair 2606/2142/892）から構造的に崩壊しています。  
- 世代進行で `fitness_pen` は改善（-0.058→-0.028）した一方、Stage A閾値 -0.0172 を一度も超えず、`fitness_raw(max)=0.0` で target 側改善も報酬化されていません。  
- anchor 側 `metric_unavailable=0` なので、主因はデータ欠損ではなく選抜設計側です。  

2. 解釈（反証可能性）  
- (a) `min-collapse` 診断は妥当です。`min(target,anchor)` は常に弱い側（初期は anchor）で決まり、target 改善の選抜圧を消します。  
反証条件: 「minの決定因子が大半の個体でanchorではない」または「target上位個体が実際に親選抜で優遇されている」が観測されればこの診断は棄却。  
- (b) mean集約の見込みは妥当です。`(target+anchor)/2` なら target 改善が即時に fitness へ寄与し、探索が停止しにくい。  
リスク: anchor が極端に悪いと mean も閾値未達になり得る（過剰淘汰）。ただし min よりは「target高性能で救済」される余地が明確に増えます。  
- (c) 優先順位は **mean先行 > weighted blend > NSGA2多目的** が低リスクです。NSGA2（集約せず両立）は理論的に本質解に近いですが、pair別目的の配線追加が大きく、いまの0/0/0ドリフトを止める即効性では mean が最善です。  

3. 次サイクル候補  
- Critical（1個）: **R91で `aggregate=mean` を同条件再実行**（最小実装: `--multi-pair-aggregate {min,mean}` 追加）。  
判定基準（反証可能）: Stage A pass が 0→正へ回復し、target 指標が世代で単調改善するか。回復しなければ「min-collapse単独原因」は棄却。  
- Warning（1）: weighted blend（target主, anchor従）は R91失敗時の次善策としてのみ実施（自由度増で過学習リスク）。  
- Warning（2）: NSGA2 pair別多目的は設計タスク化して後段へ（即時run投入は変更半径が大きい）。  

4. 全体判定  
**CRITICAL_DRIFT**