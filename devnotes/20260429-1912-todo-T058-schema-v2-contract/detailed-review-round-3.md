[Critical]
1. `ValidationResult` 契約が文書内で未統一です。  
Fact: 施策1の validator は `-> None` のまま（[detailed-design.md:234](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-1912-todo-T058-schema-v2-contract/detailed-design.md:234), [detailed-design.md:257](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-1912-todo-T058-schema-v2-contract/detailed-design.md:257)）ですが、施策4 `flush` は `result.ok` 前提（[detailed-design.md:669](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-1912-todo-T058-schema-v2-contract/detailed-design.md:669)）。  
修正案: 施策1の4 validator 全てを `ValidationResult` 返却に統一し、施策5/7/8 の呼出側も同一契約に合わせて明記。

2. `GenomeArchive.__init__` から `out_dir` 削除方針が施策9擬似コードに反映されていません。  
Fact: Round 2 反映表では削除済みと記載（[detailed-design.md:49](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-1912-todo-T058-schema-v2-contract/detailed-design.md:49)）なのに、施策9で `out_dir=archive_dir` が残存（[detailed-design.md:1234](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-1912-todo-T058-schema-v2-contract/detailed-design.md:1234)）。  
修正案: `GenomeArchive(..., run_context=..., enforcement_mode=...)` のみ渡し、出力先は `flush(output_dir=...)` に統一。

3. `load_calibrated_threshold` 維持方針と呼出例が矛盾しています。  
Fact: 関数名維持を宣言（[detailed-design.md:980](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-1912-todo-T058-schema-v2-contract/detailed-design.md:980)）しつつ、呼出例は `find_latest_applicable`（[detailed-design.md:1027](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-1912-todo-T058-schema-v2-contract/detailed-design.md:1027)）。  
修正案: 呼出・テスト名を `load_calibrated_threshold` に統一。戻り値型も `float | None` か `tuple` かを1つに固定。

4. `archive.load(return_schema_version=True)` の新契約が施策10に未反映です。  
Fact: 施策4で新 caller は tuple 受取を規定（[detailed-design.md:781](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-1912-todo-T058-schema-v2-contract/detailed-design.md:781)）していますが、施策10は table 前提のまま（[detailed-design.md:1300](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-1912-todo-T058-schema-v2-contract/detailed-design.md:1300)）。  
修正案: `table, sv = GenomeArchive.load(..., return_schema_version=True)` に変更し、`sv is None` で skip。

5. `diagnostics_sidecar` は「既存契約維持」になっていません。  
Fact: `build_sidecar_table` が rows→collector に変更（[detailed-design.md:1069](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-1912-todo-T058-schema-v2-contract/detailed-design.md:1069)）し、`write_stage_a_provenance` 返り値も `None` 化（[detailed-design.md:1093](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-1912-todo-T058-schema-v2-contract/detailed-design.md:1093)）。現行は rows受取と `Path | None` 返却契約です（[diagnostics_sidecar.py:62](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/diagnostics_sidecar.py:62), [diagnostics_sidecar.py:70](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/diagnostics_sidecar.py:70)）。  
修正案: 既存署名を維持し optional kwarg のみ追加。返り値は `Path | None` 維持。

6. `fsp_updater` の互換説明が実シグネチャと不整合です。  
Fact: マトリクス/施策8で `_atomic_write_parquet(df, path, *, mode=...)` としていますが（[detailed-design.md:72](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-1912-todo-T058-schema-v2-contract/detailed-design.md:72), [detailed-design.md:1163](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-1912-todo-T058-schema-v2-contract/detailed-design.md:1163)）、現行は `schema` 引数必須（[fsp_updater.py:180](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/fsp_updater.py:180)）。  
修正案: `schema` を保持したまま `mode` を追加する形に修正し、caller/テスト更新表もそれに合わせる。

[Warning]
1. 「33 col 完全削除」宣言と本文が矛盾しています。  
Fact: 33 col 表記がまだ残っています（[detailed-design.md:596](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-1912-todo-T058-schema-v2-contract/detailed-design.md:596)）。  
修正案: 43→47 で統一。

2. 施策6テスト名が旧関数名のままです。  
Fact: 関数名維持と言いつつ `test_find_latest_applicable_*` が残存（[detailed-design.md:1038](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-1912-todo-T058-schema-v2-contract/detailed-design.md:1038)）。  
修正案: `load_calibrated_threshold` ベースの命名へ変更。

3. 空文字 `dataset_epoch_id` 補完が複数箇所で残っています。  
Fact: sidecar と fsp で `""` 補完（[detailed-design.md:1081](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-1912-todo-T058-schema-v2-contract/detailed-design.md:1081), [detailed-design.md:1182](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-1912-todo-T058-schema-v2-contract/detailed-design.md:1182)）。  
修正案: `epoch_legacy` など grammar を満たす fallback に統一。

[Suggestion]
1. API 契約変更マトリクスに「現行実装シグネチャ参照行」を列追加すると、次ラウンドの自己矛盾を減らせます。

---

**施策別判定**
1. 施策1: **REQUEST_CHANGES**  
2. 施策2: **APPROVE**  
3. 施策3: **APPROVE**  
4. 施策4: **REQUEST_CHANGES**  
5. 施策5: **APPROVE**  
6. 施策6: **REQUEST_CHANGES**  
7. 施策7: **REQUEST_CHANGES**  
8. 施策8: **REQUEST_CHANGES**  
9. 施策9: **REQUEST_CHANGES**  
10. 施策10: **REQUEST_CHANGES**  
11. 施策11: **INCONCLUSIVE**  
12. 施策12: **REQUEST_CHANGES**

---

**Round 1+2 Critical 11件の解消判定**
- 完全解消: C3, C4, W8  
- 部分解消: C1, C2, C5, W6, W7  
- 未解消/再発: 施策間シグネチャ整合（特に 1/4/6/7/8/9/10）

**全体判定**
- **CHANGES_REQUESTED**