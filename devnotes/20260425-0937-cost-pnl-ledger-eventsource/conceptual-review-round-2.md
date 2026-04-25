全体判定: **CHANGES_REQUESTED**

1. Round 1 Critical の解消
- [Suggestion] Round 1 で指摘された元の Critical は概ね解消しています。`total_pnl` 集計自体は現行実装で `sum(Trade.pnl)` になっており、`Trade.pnl` も `raw_pnl - holding_cost` の net です。[metrics.py](/Users/ishitoya/repository/zenigame-fx/src/backtest/metrics.py#L86) [metrics.py](/Users/ishitoya/repository/zenigame-fx/src/backtest/metrics.py#L89) [mock.py](/Users/ishitoya/repository/zenigame-fx/src/broker/mock.py#L327) [mock.py](/Users/ishitoya/repository/zenigame-fx/src/broker/mock.py#L333)
- [Suggestion] 「Stage A archive の投影仕様による未記録」という整理も、現行の Stage 別射影仕様と一致しています。[clause-architecture.md](/Users/ishitoya/repository/zenigame-fx/docs/alpha_factory/clause-architecture.md#L354) [stage_gate.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/stage_gate.py#L325) [archive.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/archive.py#L332)
- [Suggestion] 誤った invariant I1 を撤回し、projection provenance 側へ寄せたのも妥当です。

2. Design-first (C1)
- [Suggestion] C1 は反映されています。Round 1 で未読だった Stage 別射影仕様を明示的に前提化し、設計 SSOT と実装を両方読んだ形になっています。[clause-architecture.md](/Users/ishitoya/repository/zenigame-fx/docs/alpha_factory/clause-architecture.md#L354) [genome-archive-schema.md](/Users/ishitoya/repository/zenigame-fx/docs/alpha_factory/concepts/genome-archive-schema.md#L12) [archive.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/archive.py#L54)

3. 縮小スコープの妥当性
- [Warning] A/B/C に割った方向は正しいですが、文書としてはまだ A に絞り切れていません。特に Phase B は taxonomy 確立、再構成関数、archive 追記列まで含んでおり、A の「原因切り分け」とは別 TODO に分けるべきです。
- [Suggestion] Round 2 で通すなら、この概念設計は A 専用に縮め、B/C は将来 TODO として 1 段落に退避した方がよいです。
- [Suggestion] なお Phase B 自体は成立余地があります。`PriceBar` は bid/ask を持ち、MockBroker の fill ルールも決定論です。[price.py](/Users/ishitoya/repository/zenigame-fx/src/domain/price.py#L16) [mock.py](/Users/ishitoya/repository/zenigame-fx/src/broker/mock.py#L201) [mock.py](/Users/ishitoya/repository/zenigame-fx/src/broker/mock.py#L363) ただし exit が `open`/`close` のどちらかを `exit_reason` から復元する仕様を先に固定しないと、`spread_implicit` は監査値として不安定です。

4. fail-open / audit-only
- [Warning] fitness / 選抜へ影響させない方針は明確で、ここは良いです。
- [Warning] ただし `summary.diagnostics.invariant_violations` は現行 `summary.json` にない新契約です。現行 SoT はその器を持っていません。[run_ga.py](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py#L603) なので Phase C も実際には summary schema 変更を伴います。
- [Suggestion] Phase C の初回実装は `logger.warning` か sidecar diagnostics ファイルに限定した方が、fail-open を崩しません。

5. 後方互換
- [Critical] 「既存 archive 列を touch しないので後方互換完全維持」は現状では成立しません。`GENOMES_SCHEMA` は 28 カラム固定で、template と import-time assert が完全一致を要求し、テストと SSOT 文書も 28 カラム前提です。[archive.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/archive.py#L51) [archive.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/archive.py#L101) [archive.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/archive.py#L142) [test_archive.py](/Users/ishitoya/repository/zenigame-fx/tests/alpha_factory/test_archive.py#L165) [genome-archive-schema.md](/Users/ishitoya/repository/zenigame-fx/docs/alpha_factory/concepts/genome-archive-schema.md#L12)
- [Critical] したがって `metric_stage` / `total_pnl_stage_a` / cost 列の追加は、既存列非変更でも明確な schema change です。ここを直さない限り、観点 5 は満たしていません。
- [Suggestion] 厳密な後方互換が必要なら、Phase A は archive ではなく sidecar diagnostics に逃がすべきです。もし archive に入れるなら、「後方互換完全維持」ではなく「consumer は extra columns を無視できる前提の schema extension」と書き換え、versioning を明記してください。

6. TODO 分割案
- [Warning] A/B/C の分割自体は現実的です。ただし優先度付けは現行合意とズレています。Run 10 合意では audit は Warning で、Critical は no-trade penalty 側です。[improvement-plan.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260425-0931-fx-improve/improvement-plan.md#L7)
- [Suggestion] TODO は `A1: stage provenance を sidecar で記録` を短 TODO とし、B/C は A1 の観測後に再判定、が一番現実的です。
- [Suggestion] もし A を先に起票するなら、「Run 10 blocker ではない observability task」と明記してください。現状の `Critical` ラベルは強すぎます。

要するに、Round 1 由来の誤読は解消していますが、**「後方互換完全維持」と書きながら archive/summary の schema extension を入れている点**がまだ通りません。ここを sidecar 化するか、互換要件の定義を下げて schema change として正面から扱えば、再レビューで通せます。