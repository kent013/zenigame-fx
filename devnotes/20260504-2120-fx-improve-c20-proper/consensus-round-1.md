**判定**  
`P1: MODIFY` で採用が妥当です。方向性は正しく、最小変更は1点だけに絞ります。

**最小変更（1つだけ）**  
`stage_b_pass` の横に **`decision_trace`（判定根拠1行）** を必須出力してください。  
中身: `rule_version / thresholds / used_metrics_source(summary|archive) / unavailable_imputation_policy`  
理由: C2/C4/C6対策として、数値そのものだけでなく「どの規則・どの母集団で判定したか」を同時固定でき、再誤読を防げます。

---

**Q1**  
1. (a) 実装容易性と妥当性: **妥当**。Stage A 診断の拡張パターンで Structural 変更として適切。  
2. (b) `median_oos_sharpe` 列の有無: **INCONCLUSIVE**（このターンでは read-only かつコマンド禁止条件のため実確認不可）。設計上はあなたの fallback（archive→summary）が正しい。  
3. (c) 反証条件の十分性: **ほぼ十分**。上の `decision_trace` を足せば、反証時に「実装バグか、集計経路差か」を即切り分け可能。

---

**Q2（cycle 21 以降）**  
1. SSOT整合が確認できた場合: signal/GA dynamics 側へ進む判断は妥当。  
2. 実装バグが出た場合: 修正優先で妥当。  
3. 「B pass だが C trade_count_min 未達」が増える場合: 案B検討は妥当（ただし即導入せず、件数推移をまず監査）。

---

**Q3（メタ過学習ガード）**  
異論なし。P1は **Structural** であり、Reactive Parametric ではありません。

---

**Q4（stage_b_pass=True 追加発見方法）**  
同一 `seed=23, mut=0.5` 反復の意味は2つで分けるべきです。  
1. **同一 seed を再実行**: 追加発見ではなく再現性検証（determinism確認）。  
2. **同一設定で seed のみ変更**: 追加発見の本命（反証可能）。  

反証可能な判定:  
- 同一 seed 再実行で結果不一致なら非決定性要因あり。  
- seed を変えても `stage_b_pass=True` が増えなければ、「探索不足」仮説は弱まり、別軸（表現力/制約整合）へ進む根拠になります。