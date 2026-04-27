**Findings**

[Warning] `hard_required / soft_required` が固定集合のままだと、「悪用解消」の達成判定が過大評価になる余地があります。  
Fact: 提示案は `HARD_REQUIRED_AUX` / `SOFT_REQUIRED_AUX` の静的分離で、`strict_aux_required=true` は hard のみに適用。  
Interpretation: soft 側 primitive（gold/wti/copper/spx/events）を実際に使う run でも safe default へ落ちうるため、目的を「完全解消」とは言い切れません。  
修正提案: Gate C 判定に「実際に選択・評価された primitive の required_data 充足率」を追加してください。

[Warning] 月次 series の `lag=35日` は安全側ですが、有効データ被覆率が低下する可能性があります。  
Fact: `policy_conservative` で月次を一律 35 日遅延にする設計。  
Interpretation: look-ahead 回避には有効ですが、特に短い評価窓で stale/default 比率が上がり、signal 有効性を落とすリスクがあります。  
修正提案: Gate B/C に「series ごとの finite coverage / stale rate」監視を入れて、閾値未達は WARN ではなく判定失敗にしてください。

**確認依頼への回答**

1. Round 2 の Critical 1 + Warning 2 への対応は妥当です。特に `policy_conservative` 既定化と Gate 分割は有効です。  
2. 新規 Critical はありません。新規 Warning は上記 2 件です（非ブロッカー）。  
3. 全体判定は **APPROVED（条件付きでなく実行可）**。  
残課題は実装時の受け入れ基準に組み込める運用リスクで、設計差し戻しレベルではありません。