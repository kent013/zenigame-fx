[VERDICT] REVISE REQUIRED

[Critical]
1. **Stage C の tri-state 判定ロジックに FAIL 優先欠落があります。**  
   抜粋コードだと `stress_pass == PENDING` の場合に `live_criteria_pass=False` でも `mission_pass=PENDING` になり得ます。`live_criteria` か `cross_pair` が確定 FAIL のときは、`stress` が PENDING でも `mission_pass=FAIL` にすべきです（真理値表を固定してください）。

2. **cross-pair 要件が review 観点の「5/6 通貨」とズレる可能性が残っています。**  
   Round 2 で `anchor除外 + shadow 5/5` に固定したのは明確化として良いですが、今回のレビュー観点は明示的に `5/6` です。ここは synthesis 原文に対する厳密整合を再確認し、`5/6` か `5/5(shadow only)` かを仕様本文に根拠付きで確定してください。現状は仕様逸脱リスクがあります。

[Warning]
1. **`build_pooled_oos_input` の `running_max reset` は pooled 意味論を変える可能性があります。**  
   擬似DD回避意図は妥当ですが、全期間 pooled OOS の DD を過小評価するリスクがあるため、再構成規約を詳細設計で数式レベルに固定する必要があります。

2. **A→B 変換スコア `1/(1+gate_worst_gap)` の定義域ガードが未記載です。**  
   `gate_worst_gap` の下限（特に `<= -1`）が理論上あり得るなら非有界/特異点が出ます。入力制約またはクリップ規約を明記してください。

3. **forced_pass の「厳密順位仕様」は未確定のまま残っています。**  
   key は改善済みですが、Enum比較順・同点時の完全決定性・除外条件（invariant fail 個体）を詳細設計で必ず固定してください。

4. **`SampleSizeFlag` と pass 判定の結合規約がまだ弱いです。**  
   `INSUFFICIENT` のときに `mission_pass/progress_pass` を `PENDING` 強制にするかどうかが未定義です。C7 運用の一貫性のために明文化が必要です。

[Suggestion]
1. `StageC` について `live/cross/stress` の 3入力に対する **完全な truth table** を概念設計に追記すると、実装とテストがブレません。  
2. cross-pair は仕様本文に `denominator`（6全体かshadow5か）と `anchorの扱い` を1行で固定し、ログ項目にも同じ表現を使うと運用時の誤読を防げます。  
3. `compute_a_b_correlation_source_score()` に domain assert（または安全クリップ）を入れる前提を概念設計に書いておくと、T071 連携時の事故が減ります。  

Round 1 で挙げた大半の構造問題は解消されています。上記 2 Critical を閉じれば APPROVED 判定に進めます。