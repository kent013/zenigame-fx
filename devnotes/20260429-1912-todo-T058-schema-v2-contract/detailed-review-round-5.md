1. [Critical] `load_calibrated_threshold` 契約が「現行実装合致」を外しています。  
Fact: 設計は `dataset_span: list[str]` + `history_path` default 化（[detailed-design.md:1040](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-1912-todo-T058-schema-v2-contract/detailed-design.md:1040), [detailed-design.md:1084](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-1912-todo-T058-schema-v2-contract/detailed-design.md:1084), [detailed-design.md:83](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-1912-todo-T058-schema-v2-contract/detailed-design.md:83))。現行は `history_path` 明示引数 + `dataset_span: tuple[str, str]`（[calibrate_state.py:184](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/calibrate_state.py:184), [run_ga.py:1078](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py:1078))。  
Interpretation: このまま実装すると既存呼出契約・型整合・相対パス依存の挙動が変わるリスクが高いです。  
修正案: T058では「既存シグネチャを維持し `dataset_epoch_id` だけ追加」に戻し、`history_path` 明示渡しと `dataset_span` tuple を維持してください（threshold_floor/ceiling も維持）。

2. [Warning] `archive.load` の表記が施策間で不一致です。  
Fact: マトリクスは `archive.load`（[detailed-design.md:79](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-1912-todo-T058-schema-v2-contract/detailed-design.md:79)）、施策10は `GenomeArchive.load`（[detailed-design.md:1390](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-1912-todo-T058-schema-v2-contract/detailed-design.md:1390)）、現行も `GenomeArchive.load` staticmethod（[archive.py:612](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/archive.py:612)）。  
Interpretation: 実装者が module 関数化すると既存 caller 破壊の再発点になります。  
修正案: 文書全体を `GenomeArchive.load` に統一してください。

3. [Warning] `load(..., return_schema_version=True)` の caller 記述が矛盾しています。  
Fact: 施策4で「run_alpha_sieve, fsp_updater が tuple 受取」と記載（[detailed-design.md:834](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-1912-todo-T058-schema-v2-contract/detailed-design.md:834)）だが、施策8は fsp_updater を df 単独返却 + helper 検出として設計（[detailed-design.md:1222](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-1912-todo-T058-schema-v2-contract/detailed-design.md:1222)）。  
Interpretation: Round 2 の修正方針が文書内で再分岐しています。  
修正案: `tuple 受取は run_alpha_sieve のみ` に一本化し、施策4の該当文を修正してください。

4. [Warning] FSP caller 全更新リストに現行不存在の経路が入っています。  
Fact: `run_ga.py` の FSP 呼出箇所更新と記載（[detailed-design.md:1271](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-1912-todo-T058-schema-v2-contract/detailed-design.md:1271)）だが、現行 `run_ga.py` に `run_fsp_updater` 呼出はありません（[run_ga.py](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py)）。  
Interpretation: C4 前提検証としては未整合です。  
修正案: この行を削除するか、「将来 TODO（ID付き）」として明示分離してください。

5. [Suggestion] 契約マトリクスの精度をもう一段上げると再レビュー負荷が減ります。  
Fact: `GenomeArchive.flush` が「不変」表記のみ（[detailed-design.md:78](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-1912-todo-T058-schema-v2-contract/detailed-design.md:78)）。  
Interpretation: 既存 `Path | None = None` の重要互換条件が読み取りづらいです。  
修正案: 行78を `flush(output_dir: Path | None = None) -> Path` と明記。

施策別判定:
1. 施策1: APPROVE  
2. 施策2: APPROVE  
3. 施策3: APPROVE  
4. 施策4: REQUEST_CHANGES  
5. 施策5: APPROVE  
6. 施策6: REQUEST_CHANGES  
7. 施策7: APPROVE  
8. 施策8: REQUEST_CHANGES  
9. 施策9: APPROVE  
10. 施策10: APPROVE  
11. 施策11: APPROVE  
12. 施策12: REQUEST_CHANGES（上記Critical/Warningを検知できる回帰テスト追加が必要）

全体判定: CHANGES_REQUESTED

補足（Round 1-4 Critical 20件の解消確認）: 大半は解消済みですが、上記 Critical 1件と整合性 Warning 3件が残っており「矛盾なし」には未達です。