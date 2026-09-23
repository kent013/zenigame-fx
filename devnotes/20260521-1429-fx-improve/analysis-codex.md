1. Facts要約  
- Run 86 は warmstart(T101) で探索量が大幅改善し、`live_criteria all_pass=True` 個体を実際に獲得（再現性の到達点は確認）。  
- ただし `graduation=0`、かつ 622 Stage C 通過個体の `ii_lite_pass` は未配線で実質 `None`、cross-pair shadow で有効なのは 4/622 のみ。  
- 反証優先で見ると、「同一dataset内の再現」は成立したが「多ペア汎化」は未成立。  

2. 解釈（反証可能性つき）  
- (a) warmstart成功と in-sample特化  
仮説: 「warmstartは探索再現性を上げたが、主効果は in-sample 強化」。  
反証条件: 別ペア/ii-liteで pass 率が有意に上がる、または shadow margin 分布が負側集中から脱する。現状データは反証できず、仮説は妥当。  
- (b) 残フロンティア=汎化  
仮説: 「ボトルネックは Stage C 到達数ではなく cross-pair 汎化」。  
反証条件: cross-pair を hard 化しても十分な通過母集団が残る。現状 4/622 なので、残課題を汎化とみなすのが合理的。  
- (c) P3 gate昇格の妥当性/全滅回避  
仮説: 「次の構造介入は P3（ii-lite配線昇格）が最小リスクで正しい」。  
反証条件: 配線後に探索が即ゼロ化し、改善信号が得られない。よって段階設計（shadow→部分hard→全面hard判定）が必須で、全面hard即時適用は不適。  

3. 次サイクル候補  
- Critical: `ii_lite_pass` を正式配線し、`graduation = Stage C pass AND ii_lite_pass` をまず「部分hard」で運用（例: 上位Kまたは次世代の一定割合に ii-lite pass 必須）。全滅回避しつつ汎化方向へ探索圧を移す。  
- Warning: warmstart アンカー依存の多様性低下を監視（系譜集中率・ユニーク遺伝子率）。集中が進むなら注入比率固定のまま派生多様化のみ追加。  
- Warning: `n=4` の cross-pair 良好群で因果解釈しない（C7）。ペア別 breakdown と再現 run を先に取り、閾値引き上げ判断はその後。  

4. 全体判定  
**CONCERN**（達成可能性・再現性は前進、ただし mission 定義上の汎化ゲート未接続が主要リスク）