VERDICT: APPROVED
REASONS:
- R1-R2 は `EvaluationContext` 導入と `pair` 必須化で実質解消されており、`required_data` 宣言と実行時入力契約が分離されずに接続されました。
- R3 は `slot_from_category()` を骨格段階で凍結し、GA 側 slot 語彙との橋渡しを「後続で考える」状態から脱却できています。
- R4 は `RequiredDataKey` の canonical 化と `cross_pair.*` 規約で、語彙ゆれを抑えつつ拡張余地を残すバランスになっています。
- R5 は受入基準が局所化され、当該 TODO 単体で判定可能な verifiable 条件に改善されています。
- R6 は bootstrap 方針（`ensure_registered()`）が明示され、登録責務の置き場所が設計として固定されました。
- スコープは骨格に閉じており、禁止事項（数値操作・閾値緩和・期間延長・GA ハック）に抵触する要素は見当たりません。North Star への間接寄与として妥当です。

NOTES:
- `RequiredDataKey` に `swap` が未定義のため、将来 primitive 側でコスト系列参照を行う可能性があるなら `spread` と同じ層で早期に語彙固定しておくと後戻りをさらに減らせます。
- `slot_from_category()` の戻り値 `local_gate` は、現行 GA 実装の実スロット名と完全一致することを実装着手前に 1 回だけ確認してください（命名不一致は移行時の主要リスク）。