**前提確認（C4）**
- Verified: 提示された `conceptual-design` と `detailed-design` の本文を突き合わせてレビューしました。
- INCONCLUSIVE: 実ファイル（4つの `SKILL.md` 実体）と移植元 `SKILL.md` 原文は未照合のため、行単位の最終一致は未検証です。

**共通テンプレート / 検証手順 セクション判定: 要修正**
- [Critical] Fact: 検証手順3が `grep -E "zenigame-(?!fx-)"` になっており、`-E` では負の先読みは使えません。  
- [Critical] Interpretation: 旧 namespace 残存の機械検証が成立せず、完了基準3の担保が崩れます。
- [Warning] Fact: 共通ルールでは「依存マトリクス一致」が必須だが、詳細設計の実行前提チェック記述は skill ごとに粒度が揃っていません。  
- [Warning] Interpretation: 実装時に「どこまで書けば合格か」の解釈ぶれが発生します。
- [Suggestion] `実行前提チェック` のテンプレートを統一し、全 skill で `script / artifact / related skill / 未充足時挙動` の4項目を必須化してください。

**`zenigame-fx-manage-sessions` セクション判定: 条件付き要修正**
- [Warning] Fact: 概念設計の依存マトリクスにある artifact（`.cache/alpha_factory/session-completed/`）が実行前提チェック節で明示されていません。  
- [Warning] Interpretation: 完了基準6（依存マトリクス一致）を厳密適用すると不一致です。
- [Suggestion] artifact は「チェック必須でない」場合でも、依存一覧には明記して責務境界を固定してください。

**`zenigame-fx-clear-cache` セクション判定: 条件付き要修正**
- [Warning] Fact: 概念設計の依存 artifact（`.cache/`）が実行前提チェックに未記載です。  
- [Warning] Interpretation: 依存マトリクス一致の要件に対して不足です。
- [Suggestion] 例示 namespace が仮例である固定文は妥当です。加えて「`status` 出力優先」の運用手順を1行で明文化すると実装時の誤解を減らせます。

**`zenigame-fx-snapshot` セクション判定: 概ね整合**
- [Suggestion] Fact: artifact 不足時責務を script 側に寄せる方針は概念設計と整合しています。  
- [Suggestion] Interpretation: ただし依存マトリクス一致を満たすため、artifact パス3点を「参照依存」として明示列挙した方が監査で通しやすいです。

**`zenigame-fx-batch-ga` セクション判定: 要修正**
- [Critical] Fact: 「related skill が `executable=executable` であることを起動時チェック」とある一方、その判定ソース（どこに executable 状態を持つか）が設計で未定義です。  
- [Critical] Interpretation: 実装可能性が不足し、実行前提チェックが仕様化されていません。
- [Critical] Fact: 概念設計の依存 artifact（`.cache/alpha_factory/runs/winners_latest.json` 等）が実行前提チェックに出てきません。  
- [Critical] Interpretation: 完了基準6との不一致です。
- [Warning] Fact: `/zenigame-fx-improve-cycle` を必須 related skill にしつつ、「batch中は呼び出さない」と記載されています。  
- [Warning] Interpretation: 依存定義と運用方針が衝突しており、不要な abort 条件になり得ます。

**frontmatter 正当性 判定: 概ね問題なし（ただし最終確認は未完）**
- [Suggestion] `name / description / argument-hint / user-invocable` の形式は妥当です。  
- [Suggestion] ただし「元ファイル踏襲」と書かれた項目は実ファイル照合が未実施のため INCONCLUSIVE です。

**監査チェック C1-C9**
- C1: 適合（概念設計→詳細設計の順で照合）
- C2: 適合（「Xが無い=バグ」型の断定は回避）
- C3: 該当なし（統計因果の議論なし）
- C4: 適合（前提を明示）
- C5: 該当なし（並列sub-agent不使用）
- C6: 適合（Fact / Interpretation を分離）
- C7: 該当なし（サンプル相関議論なし）
- C8: 適合（未検証点を INCONCLUSIVE 明示）
- C9: 適合（反証観点で矛盾点を先に確認）

**全体判定**
- **CHANGES_REQUESTED**