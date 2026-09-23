1. 引き上げ先は **74000** を推奨します。  
理由は「弱seed律速」を守ったうえで、**両seedで mission_candidate≥10 を満たす最大値**だからです（R96=12）。`72000` は安全マージンが +2（14→12）増えるだけで、引き上げ圧を弱める効果の方が大きいと判断します。  
ただし 74000 は弱seed側の余裕が薄いので、R97で事前登録した成功条件を厳密適用する前提です。

2. 禁止事項との整合性は **抵触なし** です。  
`total_pnl_min` のみ引き上げるのは「閾値緩和禁止」と整合します。取引数操作・期間延長・overnight保有・default経路変更（アルゴリズム挙動変更）には当たりません。  
注意点はメタ過学習のみで、これは「R97条件の事前固定」と「次seedで再検証」をセットにすれば管理可能です。

3. 反証可能な R97 成功基準（5条件）
1. **Config固定**: 変更は `live_criteria.total_pnl_min=74000` のみ（他は `sharpe_min=1.5, max_dd=0.2, trade_count=50-5000, warmstart/config/pop96/gen60` 固定）。  
2. **Stage C有効性**: `stage_c_pass_count > 0`。  
3. **North Star実用性**: `mission_candidate_count >= 10`。  
4. **高取引数tail再出現**: Stage Bで `trade_count >= 100` 個体が `>=1`。  
5. **独立seed再現**: R97達成後、直近の別seed（R98）でも `mission_candidate_count > 0`（同一閾値74000で）。

全体判定: 条件付きOK