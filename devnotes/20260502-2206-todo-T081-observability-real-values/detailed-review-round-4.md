**全体判定: APPROVED**

提供された Round 4 改訂内容に基づく限り、Round 1〜3 の Critical / Warning は解消されています。T081 Step 1 の詳細設計は実装着手可能です。

**ID別判定**
- R1-C1 SSOT 乖離: `APPROVE`
- R1-C2 `ab_score_pairs` key 衝突: `APPROVE`
- R1-C3 legacy / via_evaluator 契約未確認: `APPROVE`
- R1-W4 preflight 除外で `n_pairs<10` 常態化リスク: `APPROVE`
- R1-W5 テスト不足: `APPROVE`
- R2-C1 preflight early `continue` による既存処理破壊: `APPROVE`
- R2-W1 `ab_score_source` 永続化不足: `APPROVE`
- R2-W2 cross-run `RuntimeError` 過剰: `APPROVE`
- R2-W3 `AB_MIN_ACTIONABLE_PAIRS=10` と C7 discipline mismatch: `APPROVE`
- R3-W1 numpy 型ガード不足: `APPROVE`

**残課題**
- [Suggestion] Step 6 実装時は `q-force-state.json` に `ab_score_source` を必ず保存し、source 不一致の過去 record は skip + warn にしてください。
- [Suggestion] `numbers.Real` guard は妥当です。`bool` 明示除外も正しいです。
- [Suggestion] test 14 の `wraps=` spy、test 16 の JSON byte-for-byte equality、test 17 の all-inactive run は設計通り実装すれば十分です。

**最終コメント**
- Step 1 は「既存 GA 評価フローを変えず、B-evaluated 集合に限定して AB divergence を観測する」設計として整合しています。
- list 集約、source mixing guard、preflight count、noop handling、default constructor 互換性 test まで揃っており、incremental 実装モードも妥当です。