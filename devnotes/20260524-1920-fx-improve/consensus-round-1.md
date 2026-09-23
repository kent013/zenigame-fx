1. **収束案は (E)** が最適です。  
理由は4軸で最もバランスが良いからです。  
- mission整合: 70kは3 seed再現で「到達可能 frontier」として実証済み。  
- 情報価値: 既存3軸の閾値上げは、`hollow` か `funnel崩壊` の二択になっており、新情報が薄い。  
- in-loop安全: 74k崩壊の再発リスクを避けられる。  
- コスト効率: 7h/runを「崩壊確認」に使わず、次フレーム（cross-pair別設計/探索効率）へ投資できる。  

2. **hollowな閾値引き上げの意味**  
結論: **North Star上では実質価値は低く、形式的追認に近い**です。  
- `sharpe 1.5→4.0`: R98 p10=4.70なので、達成済分布を下から追認するだけ。  
- `dd 20%→5%`: 現max 2.68%で同様に非binding。さらにddはin-loop軸なので、副作用だけ増える可能性がある。  
唯一の価値は「下振れ防止の明文化」だが、frontier拡張には直結しません。  

3. **(B)を選ぶなら（参考）**  
選ぶなら **5%** 先行、3%はまだ早いです（2.68%に近すぎてseed/相場変動耐性が薄い）。  
`post-hoc信仰`再発防止手順:  
1. 事前登録: 合格基準をrun前に固定（後出し禁止）。  
2. 同一条件ペア比較: baseline(20%) vs candidate(5%)を同一seed群で並走。  
3. in-loop指標で判定: Stage A/B/C通過数・mission数・分布劣化を比較（事後フィルタのみで判定しない）。  
4. 3 seedで全て非崩壊を必須化（1 seedでもStageC=0なら棄却）。  
5. 5%合格後にのみ3%を検証。  

4. **R99の反証可能な成功/失敗基準（E採用時、70k据え置き確認run）**  
以下を**5条件すべて**満たせば成功、1つでも未達で失敗。  
1. `StageC pass count >= 200`  
2. `mission_candidate_count >= 200`  
3. `StageC median total_pnl >= 78,000`  
4. `StageC p10 annualized sharpe >= 4.2`  
5. `StageC max max_drawdown_pct <= 3.5%`  

全体判定: **(E) 70k/1.5/20%をvalidated frontierとして確定し、閾値の形式的引き上げは行わず、次は探索効率とcross-pairを別フレームで改善する。**