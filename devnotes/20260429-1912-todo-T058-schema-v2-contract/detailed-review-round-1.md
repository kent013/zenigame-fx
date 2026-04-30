**主要指摘（Severity順）**
1. **[Critical] RunContext と enforcement mode の接続が設計内で破綻しています。**  
Fact: `RunContext` 定義には `schema_contract_mode` が存在しませんが、`flush()` 擬似コードでは `self._run_context_or_none.schema_contract_mode` を参照しています（[detailed-design.md:361](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-1912-todo-T058-schema-v2-contract/detailed-design.md:361), [detailed-design.md:591](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-1912-todo-T058-schema-v2-contract/detailed-design.md:591)）。  
Interpretation: このまま実装すると属性参照エラーになります。  
修正案: `SchemaEnforcementMode` は `RunContext` ではなく `AlphaFactoryConfig.schema_contract` から渡すか、`RunContext` に明示追加して生成箇所を固定してください。

2. **[Critical] `GenomeArchive.__init__` の提案シグネチャは既存呼び出しを広範囲で壊します。**  
Fact: 設計案は `out_dir` 必須引数化しています（[detailed-design.md:605](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-1912-todo-T058-schema-v2-contract/detailed-design.md:605)）。現行は `GenomeArchive(run_id, run_number)` 前提で多数利用されています（[run_ga.py:1159](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py:1159), [test_archive.py:161](/Users/ishitoya/repository/zenigame-fx/tests/alpha_factory/test_archive.py:161)）。  
Interpretation: 互換性を崩す破壊的変更です。  
修正案: `out_dir` は必須化せず `flush(output_dir=...)` 契約を維持し、`run_context` だけ optional 追加してください。

3. **[Critical] `HistoryRecord` v2 の後方互換ハンドリングが不十分です。**  
Fact: 設計では `__post_init__` で `dataset_epoch_id` を必須検証し `ValueError` 系を投げます（[detailed-design.md:703](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-1912-todo-T058-schema-v2-contract/detailed-design.md:703)）。現行 `read_history()` は `TypeError` しか握りつぶしていません（[calibrate_gate_history.py:109](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/calibrate_gate_history.py:109)）。  
Interpretation: 旧 record 読み込みで `read_history()` 自体が落ちる可能性があります。  
修正案: `read_history()` で `ValueError` も skip 対象にするか、v1 読み込み時の明示変換層を追加してください。

4. **[Critical] `append_record` の提案シグネチャは既存呼び出しと衝突します。**  
Fact: 設計案は `path` を keyword-only にしています（[detailed-design.md:709](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-1912-todo-T058-schema-v2-contract/detailed-design.md:709)）。現行は位置引数で呼んでいます（[calibrate_gate.py:452](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/calibrate_gate.py:452), [test_calibrate_gate_history.py:59](/Users/ishitoya/repository/zenigame-fx/tests/alpha_factory/test_calibrate_gate_history.py:59)）。  
Interpretation: 即時 `TypeError` リスクです。  
修正案: `append_record(record, path=..., *, mode=...)` にしてください。

5. **[Critical] T058 LOG_ONLY 方針と read/write 挙動が矛盾しています。**  
Fact: 概念設計は「T058 は read/write 両方 LOG_ONLY 統一、v1 は warning+skip」と定義しています（[conceptual-design.md:159](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-1912-todo-T058-schema-v2-contract/conceptual-design.md:159), [conceptual-design.md:247](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-1912-todo-T058-schema-v2-contract/conceptual-design.md:247)）。一方、詳細設計では `archive.load()` が v1 を `return table` し（skipしない）、`fsp` 書き込みは v2列欠落で即 raise です（[detailed-design.md:622](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-1912-todo-T058-schema-v2-contract/detailed-design.md:622), [detailed-design.md:861](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-1912-todo-T058-schema-v2-contract/detailed-design.md:861)）。  
Interpretation: 「LOG_ONLYで壊さない」という主張を満たせていません。  
修正案: v1検出時の返却契約を明確化（`None`/empty table/flag付き返却）し、`mode` ごとに一貫した分岐を定義してください。

6. **[Critical] `dataset_epoch_id` を stub 固定値にしたまま scope 置換すると cross-run contamination が再導入されます。**  
Fact: 設計は T058 で `epoch_legacy` stub を返し（[detailed-design.md:934](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-1912-todo-T058-schema-v2-contract/detailed-design.md:934)）、同時に `dataset_span` ガードを `dataset_epoch_id` に置換しています（[detailed-design.md:760](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-1912-todo-T058-schema-v2-contract/detailed-design.md:760)）。現行ガードは `dataset_span` を見ています（[calibrate_state.py:154](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/calibrate_state.py:154)）。  
Interpretation: epoch生成が未完成の段階で安全性が下がります。  
修正案: T058は `dataset_span` を残しつつ `dataset_epoch_id` を追加条件化し、完全置換はT059完了後に実施してください。

7. **[Warning] `history.json` 伝搬仕様が現行 consumer と非互換になる可能性があります。**  
Fact: 擬似コードは `history_json["dataset_epoch_id"] = ...` と top-level dict 前提です（[detailed-design.md:923](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-1912-todo-T058-schema-v2-contract/detailed-design.md:923)）。現行は `history.json` が list で、consumer も list 前提です（[run_ga.py:984](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py:984), [analyze_run.py:40](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/analyze_run.py:40)）。  
Interpretation: 形式変更時に `analyze_run` 等が壊れます。  
修正案: list形式を維持して各要素に追加するか、`history.meta.json` を分離してください。

8. **[Warning] diagnostics sidecar の schema更新が設計上明示されていません。**  
Fact: sidecar schema は現行10列です（[diagnostics_sidecar.py:34](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/diagnostics_sidecar.py:34)）。設計では row に新キーを `setdefault` しています（[detailed-design.md:823](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-1912-todo-T058-schema-v2-contract/detailed-design.md:823)）。  
Interpretation: 列追加が抜けると契約の実効性がありません。  
修正案: `STAGE_A_PROVENANCE_SCHEMA` に列追加し、read/write テストも更新してください。

9. **[Warning] C4前提検証が最新 main とズレています。**  
Fact: 設計は archive を 33列前提で見積もっています（[detailed-design.md:544](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-1912-todo-T058-schema-v2-contract/detailed-design.md:544)）。現行は43列です（[archive.py:8](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/archive.py:8), [test_archive.py:169](/Users/ishitoya/repository/zenigame-fx/tests/alpha_factory/test_archive.py:169)）。  
Interpretation: 影響範囲/工数/テスト更新量の見積りが過小です。  
修正案: C4テーブルと設計本文の列数・契約を再同期してください。

10. **[Warning] 波及変更（docs/skill）が不足しています。**  
Fact: 設計は docs/skills 変更なしとしています（[detailed-design.md:51](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-1912-todo-T058-schema-v2-contract/detailed-design.md:51), [detailed-design.md:53](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-1912-todo-T058-schema-v2-contract/detailed-design.md:53)）。一方で運用文書は現行契約（schema_version=1, dataset_span guard）を明記しています（[stage-gates.md:262](/Users/ishitoya/repository/zenigame-fx/docs/alpha_factory/stage-gates.md:262), [zenigame-fx-calibrate-gate/SKILL.md:99](/Users/ishitoya/repository/zenigame-fx/.claude/skills/zenigame-fx-calibrate-gate/SKILL.md:99)）。  
Interpretation: 実装後に運用手順が誤情報になります。  
修正案: `docs/alpha_factory/stage-gates.md` と `.claude/skills/zenigame-fx-calibrate-gate/SKILL.md` をT058 DoDに追加してください。

11. **[Suggestion] LOG_ONLY期間は per-row warning を集約した方が安全です。**  
Fact: 設計でも warning多発リスクを認識しています（[detailed-design.md:325](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-1912-todo-T058-schema-v2-contract/detailed-design.md:325)）。  
Interpretation: 大規模runでログ洪水になり解析性を落とします。  
提案: run単位カウンタ集計 + 末尾サマリログにしてください。

12. **[Suggestion] C3/C7（collider bias / sample size）は本設計では実質非該当です。**  
Fact: 本件は schema/contract 変更中心で相関・予測 claim がありません。  
Interpretation: C3/C7 の判定は「N/A」明記で十分です。

---

**施策別判定**
1. `schema_contract.py`: **APPROVE**  
2. `RunContext`: **APPROVE**  
3. `SchemaContractConfig`: **APPROVE**  
4. `archive.py` 4 field + lint: **REQUEST_CHANGES**  
5. `calibrate_gate_history.py`: **REQUEST_CHANGES**  
6. `calibrate_state.py`: **REQUEST_CHANGES**  
7. `diagnostics_sidecar.py`: **REQUEST_CHANGES**  
8. `fsp_updater.py`: **REQUEST_CHANGES**  
9. `run_ga.py` propagate: **REQUEST_CHANGES**  
10. `run_alpha_sieve.py` mode連動: **INCONCLUSIVE**（`archive.load` の最終契約確定待ち）  
11. Tier 2 軽量ガード: **APPROVE**  
12. テスト総合: **REQUEST_CHANGES**（`test_calibrate_gate_drift.py` 等の波及更新が不足）

**全体判定: CHANGES_REQUESTED**

補足: このレビューは設計書・現行コード・既存テスト・関連skill/docsの読解ベースです。read-only 環境のためテスト実行は行っていません。