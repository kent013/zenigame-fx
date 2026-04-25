**前提検証 (C4)**
- Verified: 現行実装で該当関数名は `_update_cache` です（`_update_cache_from_archive` ではない）。参照: [run_ga.py](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py:437), [detailed-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260425-0939-signal-eval-consistency-fix/detailed-design.md:35)
- Verified: `selection_score` の実利用経路は tournament / elite sort / best 選出 / summary 出力です。参照: [run_ga.py](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py:370), [run_ga.py](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py:384), [run_ga.py](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py:475), [run_ga.py](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py:653)
- Verified: 既存テストは `selection_score` 長さ 4 を固定で見ています。参照: [test_alpha_factory_run_ga.py](/Users/ishitoya/repository/zenigame-fx/tests/scripts/test_alpha_factory_run_ga.py:394)
- INCONCLUSIVE (C8): リポジトリ外の運用スクリプト/Notebook が `selection_score` 4要素固定かは確認不能。

**指摘**
- [Critical] 施策6の新規回帰テストが `...` のままで、テストファースト要件を満たしません。参照: [detailed-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260425-0939-signal-eval-consistency-fix/detailed-design.md:265)  
  修正案: `_update_cache` を直接呼ぶ具体テストにし、`trade_count=5/0/None`・`row=None` の各ケースで `feasible_trade` を明示アサートしてください。
- [Critical] 施策7で `generate_run_report.py` を変更対象に含めつつ「テスト不要」は、同ドキュメント内の「全施策にテスト必須」と矛盾します。参照: [detailed-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260425-0939-signal-eval-consistency-fix/detailed-design.md:20), [detailed-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260425-0939-signal-eval-consistency-fix/detailed-design.md:351), [generate_run_report.py](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/generate_run_report.py:451)  
  修正案: `tests/scripts/test_generate_run_report.py` を追加し、Best説明文が新tuple表記になることを検証してください。
- [Warning] 設計書の関数名が実コードと不一致です（`_update_cache_from_archive` vs `_update_cache`）。参照: [detailed-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260425-0939-signal-eval-consistency-fix/detailed-design.md:49), [run_ga.py](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py:437)  
  修正案: 設計書・テスト名を `_update_cache` に統一するか、実装側で意図的リネームするなら呼び出し元含め明記してください。
- [Warning] `clause-architecture.md` の更新対象として「tuple記述置換」を挙げていますが、現時点で該当文字列が見当たりません。参照: [detailed-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260425-0939-signal-eval-consistency-fix/detailed-design.md:337), [clause-architecture.md](/Users/ishitoya/repository/zenigame-fx/docs/alpha_factory/clause-architecture.md)  
  修正案: 実際に追記する節を明示するか、変更対象から外してください。
- [Warning] `fitness_pen` の NaN/inf は `selection_score` 比較に残留し得ます（現行でも潜在リスク）。参照: [run_ga.py](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py:456), [run_ga.py](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py:111)  
  修正案: `_update_cache` で `math.isfinite(fp)` を確認し、非有限は `-math.inf` に正規化するテストを追加してください。
- [Suggestion] `summary.best.selection_score` の仕様変更はスキーマ版本（例: `selection_score_schema`）を持たせると下流互換監視が容易です。

**施策別判定**
- 施策1 `IndividualCacheEntry` に `feasible_trade` 追加: **APPROVE**
- 施策2 `_update_cache...` で `trade_count` から導出: **REQUEST_CHANGES**
- 施策3 `selection_score` 5要素化: **APPROVE**
- 施策4 summary `selection_score` 5要素化: **APPROVE**
- 施策5 既存テスト 4→5 更新: **APPROVE**
- 施策6 新規回帰テスト: **REQUEST_CHANGES**
- 施策7 docs / report 更新: **REQUEST_CHANGES**

**全体判定**
- **CHANGES_REQUESTED**