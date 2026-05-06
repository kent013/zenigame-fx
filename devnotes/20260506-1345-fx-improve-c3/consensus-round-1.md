**結論**
cycle 3 は「`P1` を唯一の structural 介入」「`P2` は調査ノートのみ」「`P3-P5` 保留」で収束して問題ありません。  
ただし `P1` は最小修正を入れて **MODIFY** にします。

1. **P1: MODIFY**  
`meta_guard`: Structural  
`target_metric`: Stage A上位群の世代別 fold robustness 可観測性（cycle 4で相関検証可能か）  
`failure_mode`: top20%集計だけだと分母・選抜基準不明で誤読、NaN混入時に解釈不能  
`causal_path`: 観測設計の曖昧さが「目的関数不整合」仮説の反証可能性を下げる  
`falsification`: cycle 4で「generationごとの StageA順位優位群ほど fold_sign が上がる/上がらない」を統計的に判定できれば仮説検証成立  
`success_criterion`: 各generationで top群と母集団の比較ができ、再計算不要で analyze-run から直接判定可能  
`修正案`: 既存案に最小追加で `run_id, population_n, top_n, top_selector(fitness_pen), fold_sign_positive_ratio, median_oos_sharpe_nan_ratio` を追加

2. **P2: APPROVE**  
`meta_guard`: Structural  
`target_metric`: live_criteria整合性（trade_count_min経路の設計妥当性）  
`failure_mode`: trade<50個体が stage_a_pass=True になる経路未同定のまま誤修正  
`causal_path`: 判定経路未把握で修正すると別ルートを壊す  
`falsification`: g26_i95の通過ログと判定関数経路を突合し、設計通り/bugを二択化  
`success_criterion`: cycle 4開始時点で「fix要否」と「修正ポイント候補」が1ページで判断可能

3. **P3: APPROVE（保留）**  
`meta_guard`: Structural（観測追加のみ）  
`target_metric`: best trade_countの世代/Run推移  
`failure_mode`: attractor仮説を単発Runで誤認  
`causal_path`: 連続Run観測不足で因果誤読  
`falsification`: 4-5run連続で50-55帯集中が再現しなければ棄却  
`success_criterion`: run横断時系列で集中度を定量化できる

4. **P4: APPROVE（保留）**  
`meta_guard`: Structural（判断延期）  
`target_metric`: cross-pair shadowの有効/無効判定可能性  
`failure_mode`: 単一instrument状態で誤判定  
`causal_path`: 観測条件不足  
`falsification`: multi-instrument復帰後にshadow通過率/寄与で評価  
`success_criterion`: 復帰後1cycleで採否判断可能な指標が揃う

5. **P5: APPROVE（保留）**  
`meta_guard`: Reactive Parametric（現時点で変更禁止）  
`target_metric`: Stage A通過率とStage B品質の同時改善可否  
`failure_mode`: 直近Run反応でmax_clauseを動かし過学習  
`causal_path`: パラメータ介入が真因探索を妨げる  
`falsification`: P1結果で「目的不整合が主因でない」と示された場合のみ再検討  
`success_criterion`: P1/P2後に原理的根拠付きでのみ変更議論

**Q1回答**  
可視化は「ほぼ可能」ですが、上記の最小追加がないと反証力が弱いです。`MODIFY`案を採用すれば十分です。

**Q2回答**  
妥当です。cycle 3で実コード非変更・調査ノートのみは、implementフェーズのoverflow防止に有効です。

**Q3回答**  
適切です。  
「仕組み未確立で値を弄らない」原則、メタ過学習ガード、1 cycle 1 介入の全てに整合します。  
本ラウンドは **P1（最小修正付き）を唯一実装して収束**で進めるのが最善です。