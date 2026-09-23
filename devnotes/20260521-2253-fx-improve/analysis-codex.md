1. Facts要約  
- Run 87 は `cross_pair_runtime_mode=enabled` で実行され、`ii_lite_pass` は `None→bool` に正常化。  
- Stage C 599 個体の `ii_lite_pass` が **0/599**、`graduation=0`。  
- `mission_signed_margin_c_shadow` 中央値 `-1.367`（正は 4/599）で、「閾値近傍の失敗」ではなく大幅な負側集中。

2. 解釈（反証可能性つき）  
- (a) 診断妥当性: 「深い過学習 + GAの汎化選択圧ゼロ」は現時点で妥当。  
  反証条件は「実装/データ不整合で cross-pair が構造的に落ちている」ことだが、`enabled` で値が連続分布し一部正値もあるため“常時バグ落ち”仮説は弱い。  
- (b) 高コスト下の実行可能策: 最有力は **(b) in-loop selection pressure の疎評価導入**。  
  全個体3ペア評価は重すぎるため、`top-Nのみ` + `世代間キャッシュ` + `M世代ごと再評価` で圧を入れるのが現実的。  
- (c) 安価proxyの成立性: **限定的に成立**（過学習抑制の前段フィルタとして有効）。  
  ただし proxy 単独は「cross-pair汎化」の代理として不完全。反証は「proxy改善しても `ii_lite_pass` が増えない」場合で、その時点で棄却すべき。

3. 次サイクル候補  
- Critical（1個）: **opt-in の段階導入で (b) を実装**。`default不変(OFF)` のまま、Stage B上位候補にのみ cross-pair shadow を疎注入し、選抜キーに“弱く”反映（閾値緩和なし）。目的は loop 停止回避と汎化圧の最小注入。  
- Warning（1）: (c) の proxy（sub-period安定性/分散ペナルティ）は **prefilter専用** に限定し、最終判定へ直結させない（Reactive Parametric禁止）。  
- Warning（2）: 変更評価は固定 seed 複数本で A/B 比較し、`ii_lite_pass率` と `mission_signed_margin_c_shadow` の改善が無ければ即ロールバック（閾値は上げるのみ、緩和なし）。

4. 全体判定  
- **CRITICAL_DRIFT**（達成指標に対し探索圧がミスマッチのため）。