**前提検証 (C4)**
- Round 3 指摘の主修正（`ValidationResult` 統一、`out_dir` 削除、`return_schema_version=True` 反映、`Path | None` 維持）は文書上で確認できました（[detailed-design.md:48](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-1912-todo-T058-schema-v2-contract/detailed-design.md:48), [detailed-design.md:49](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-1912-todo-T058-schema-v2-contract/detailed-design.md:49), [detailed-design.md:51](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-1912-todo-T058-schema-v2-contract/detailed-design.md:51), [detailed-design.md:52](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-1912-todo-T058-schema-v2-contract/detailed-design.md:52), [detailed-design.md:53](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-1912-todo-T058-schema-v2-contract/detailed-design.md:53)）。

[Critical]
1. API 契約マトリクスが文書内で二重化され、互いに矛盾しています。  
Fact: 新マトリクスは正しい方向（[detailed-design.md:59](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-1912-todo-T058-schema-v2-contract/detailed-design.md:59)）ですが、旧マトリクスが残存し `build_sidecar_table(collector)` / `_atomic_write_parquet(df, path)` など古い契約を再掲しています（[detailed-design.md:90](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-1912-todo-T058-schema-v2-contract/detailed-design.md:90), [detailed-design.md:101](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-1912-todo-T058-schema-v2-contract/detailed-design.md:101), [detailed-design.md:104](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-1912-todo-T058-schema-v2-contract/detailed-design.md:104)）。  
修正案: 旧マトリクスを削除するか「履歴（無効）」と明示し、実装指示としては新マトリクス1つに統一。

2. `load_calibrated_threshold` の戻り値契約が現行実装/マトリクスと不一致です。  
Fact: 施策6擬似コードは `-> tuple[float, str] | None`（[detailed-design.md:1046](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-1912-todo-T058-schema-v2-contract/detailed-design.md:1046)）ですが、現行は `float | None`（[calibrate_state.py:193](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/calibrate_state.py:193)）で、マトリクスも戻り値変更を明示していません（[detailed-design.md:69](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-1912-todo-T058-schema-v2-contract/detailed-design.md:69)）。  
修正案: `float | None` 維持なら擬似コードを修正。`run_id` も返したいなら別関数追加に分離して契約明記。

3. `flush` 既存契約維持方針と施策4擬似コードがずれています。  
Fact: 擬似コードが `def flush(self, output_dir: Path)` 必須化（[detailed-design.md:710](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-1912-todo-T058-schema-v2-contract/detailed-design.md:710)）。現行は `output_dir: Path | None = None`（[archive.py:581](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/archive.py:581)）。  
修正案: `flush(output_dir: Path | None = None)` のままにして、既存 no-arg 呼び出し互換を明示維持。

[Warning]
1. `run_alpha_sieve` の loader 契約説明で import 経路が現行とずれています。  
Fact: 擬似コードは `from src.alpha_factory.archive import load as load_archive`（[detailed-design.md:1379](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-1912-todo-T058-schema-v2-contract/detailed-design.md:1379)）ですが、現行は `GenomeArchive.load` 使用（[run_alpha_sieve.py:222](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_alpha_sieve.py:222), [archive.py:612](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/archive.py:612)）。  
修正案: module-level `load` を導入するなら `GenomeArchive.load` ラッパを併記。導入しないなら擬似コードを `GenomeArchive.load(..., return_schema_version=True)` に合わせる。

2. 施策8のテスト名が実契約と噛み合っていません。  
Fact: `_read_archive_with_fsp_compat` は df 単独返却維持（[detailed-design.md:1219](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-1912-todo-T058-schema-v2-contract/detailed-design.md:1219)）なのに、テスト名は「returns_none_schema_version」（[detailed-design.md:1272](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-1912-todo-T058-schema-v2-contract/detailed-design.md:1272)）。  
修正案: helper `_detect_archive_schema_version` を直接検証する命名に変更。

3. Round 3 反映表で「row_template default も同値」とある一方、`HistoryRecord.dataset_epoch_id` は空文字 default のままです。  
Fact: 反映表（[detailed-design.md:56](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-1912-todo-T058-schema-v2-contract/detailed-design.md:56)）と `HistoryRecord` 定義（[detailed-design.md:896](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-1912-todo-T058-schema-v2-contract/detailed-design.md:896)）に差。  
修正案: 反映表の文言を「row/template/fallback を epoch_legacy 統一。HistoryRecord は __post_init__ で拒否するため空文字 default 維持」など正確化。

[Suggestion]
1. 「有効な契約定義は新マトリクスのみ」という注記を見出し直下に追加すると、実装時の誤読を防げます。

---

**施策別判定**
1. 施策1: **APPROVE**  
2. 施策2: **APPROVE**  
3. 施策3: **APPROVE**  
4. 施策4: **REQUEST_CHANGES**  
5. 施策5: **APPROVE**  
6. 施策6: **REQUEST_CHANGES**  
7. 施策7: **APPROVE**  
8. 施策8: **REQUEST_CHANGES**  
9. 施策9: **APPROVE**  
10. 施策10: **REQUEST_CHANGES**  
11. 施策11: **APPROVE**  
12. 施策12: **INCONCLUSIVE**

**全体判定**
- **CHANGES_REQUESTED**

**判定理由（要約）**
- Round 3 指摘の主要論点は概ね解消されていますが、施策間シグネチャ整合を求める今回観点では、`calibrate_state` 戻り値契約、`flush` 互換契約、マトリクス二重化による矛盾が残っています。これらを潰せば APPROVED に到達可能です。