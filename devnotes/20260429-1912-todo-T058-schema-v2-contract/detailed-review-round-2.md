**前提検証 (C4)**
- `archive` 現行は 43 列で、`GenomeArchive.load()` は `pa.Table` 単体返却です（[archive.py:54](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/archive.py:54), [archive.py:612](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/archive.py:612), [test_archive.py:169](/Users/ishitoya/repository/zenigame-fx/tests/alpha_factory/test_archive.py:169)）。
- `run_ga.py` 現行は `GenomeArchive(run_id, run_number)` で生成し、`out_dir` は `flush()` 側契約です（[run_ga.py:1159](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py:1159), [archive.py:581](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/archive.py:581)）。
- `append_record(record, path)` の positional 呼び出しは現行で使われています（[calibrate_gate.py:452](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/calibrate_gate.py:452), [test_calibrate_gate_history.py:59](/Users/ishitoya/repository/zenigame-fx/tests/alpha_factory/test_calibrate_gate_history.py:59)）。
- `history.json` は list 前提で `analyze_run.py` が読んでいます（[analyze_run.py:34](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/analyze_run.py:34)）。

**指摘**
1. [Critical] `archive.load` の戻り値契約が設計内で不整合です。  
Fact: 施策4は tuple 返却（[detailed-design.md:662](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-1912-todo-T058-schema-v2-contract/detailed-design.md:662)）ですが、施策10は table 前提記述（[detailed-design.md:1155](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-1912-todo-T058-schema-v2-contract/detailed-design.md:1155)）。現行 caller も table 前提です（[run_alpha_sieve.py:222](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_alpha_sieve.py:222), [test_archive.py:546](/Users/ishitoya/repository/zenigame-fx/tests/alpha_factory/test_archive.py:546)）。  
修正案: `load(path, *, mode, return_schema_version=False)` で後方互換を維持し、段階移行で tuple を使う path を増やしてください。

2. [Critical] `GenomeArchive` 既存シグネチャ維持方針と施策9擬似コードが矛盾しています。  
Fact: 維持方針を明記（[detailed-design.md:49](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-1912-todo-T058-schema-v2-contract/detailed-design.md:49)）しつつ、`out_dir=` を `__init__` に渡しています（[detailed-design.md:1089](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-1912-todo-T058-schema-v2-contract/detailed-design.md:1089)）。  
修正案: `GenomeArchive(run_id, run_number, run_context=..., enforcement_mode=...)` + `archive.flush(output_dir=...)` に統一してください。

3. [Critical] `diagnostics_sidecar` の関数契約変更が既存呼び出しを壊します。  
Fact: 設計は `write_stage_a_provenance(rows, ...)`（[detailed-design.md:979](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-1912-todo-T058-schema-v2-contract/detailed-design.md:979)）ですが、現行は `collector` を受ける契約です（[diagnostics_sidecar.py:67](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/diagnostics_sidecar.py:67), [run_ga.py:1446](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py:1446)）。  
修正案: 既存 signature を維持し、`run_context` と `mode` を optional kwarg 追加にしてください。

4. [Critical] LOG_ONLY 警告集約ロジックが実際には機能しません。  
Fact: validator は LOG_ONLY で raise せず warning のみ（[detailed-design.md:214](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-1912-todo-T058-schema-v2-contract/detailed-design.md:214)）なのに、`flush` は `except SchemaContractError` で counter 加算しています（[detailed-design.md:640](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-1912-todo-T058-schema-v2-contract/detailed-design.md:640)）。  
修正案: validator を `ValidationResult` 返却にして、warning 件数を明示的に集計してください。

5. [Critical] `fsp_updater` の API 変更範囲が未閉包です。  
Fact: 施策8は `_read_archive_with_fsp_compat` を tuple 返却化（[detailed-design.md:1015](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-1912-todo-T058-schema-v2-contract/detailed-design.md:1015)）し、`_atomic_write_parquet` signature も変更（[detailed-design.md:1026](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-1912-todo-T058-schema-v2-contract/detailed-design.md:1026)）していますが、現行は多数 caller が旧契約依存です（[fsp_updater.py:398](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/fsp_updater.py:398), [test_fsp_updater.py:265](/Users/ishitoya/repository/zenigame-fx/tests/alpha_factory/test_fsp_updater.py:265)）。  
修正案: 互換レイヤを先に導入し、全 caller/test の更新リストを施策8に明記してください。

6. [Warning] C4 列数記述がまだ一部古いです。  
Fact: 施策4に「33 columns」表現が残存（[detailed-design.md:565](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-1912-todo-T058-schema-v2-contract/detailed-design.md:565)）。  
修正案: 43→47 のみで統一し、古い記述を削除してください。

7. [Warning] `calibrate_state` の関数 rename 方針が波及未整理です。  
Fact: 設計は `find_latest_applicable` 前提（[detailed-design.md:889](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-1912-todo-T058-schema-v2-contract/detailed-design.md:889)）ですが、現行 API は `load_calibrated_threshold` でテスト網が既にあります（[calibrate_state.py:184](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/calibrate_state.py:184), [test_calibrate_state.py:15](/Users/ishitoya/repository/zenigame-fx/tests/alpha_factory/test_calibrate_state.py:15)）。  
修正案: rename ではなく alias 追加で移行し、既存テストを壊さない形にしてください。

8. [Warning] DoD のテストパスに誤りがあります。  
Fact: `tests/alpha_factory/test_calibrate_gate_drift.py` を参照（[detailed-design.md:1249](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-1912-todo-T058-schema-v2-contract/detailed-design.md:1249)）していますが実ファイルは `tests/scripts/...` です（[test_calibrate_gate_drift.py:1](/Users/ishitoya/repository/zenigame-fx/tests/scripts/test_calibrate_gate_drift.py:1)）。  
修正案: DoD パスを実在パスに修正してください。

9. [Suggestion] `archive.load` / `diagnostics_sidecar` / `fsp_updater` の「契約変更一覧 + caller全件」を設計末尾に1表で追加すると、C2/C4 の再発防止に有効です。

**施策別判定**
1. 施策1 `schema_contract.py`: **APPROVE**  
2. 施策2 `RunContext`: **APPROVE**  
3. 施策3 `SchemaContractConfig`: **APPROVE**  
4. 施策4 `archive.py`: **REQUEST_CHANGES**  
5. 施策5 `calibrate_gate_history.py`: **REQUEST_CHANGES**  
6. 施策6 `calibrate_state.py`: **APPROVE**  
7. 施策7 `diagnostics_sidecar.py`: **REQUEST_CHANGES**  
8. 施策8 `fsp_updater.py`: **REQUEST_CHANGES**  
9. 施策9 `run_ga.py`: **REQUEST_CHANGES**  
10. 施策10 `run_alpha_sieve.py`: **REQUEST_CHANGES**  
11. 施策11 Tier2 guard: **INCONCLUSIVE**  
12. 施策12 テスト総合: **REQUEST_CHANGES**

**Round 1 指摘の解消状況**
- 解消済み: Critical 3/4/6、Warning 7/8/10  
- 部分解消: Critical 1/2/5、Warning 9  
- 新規破壊点: API 契約の不整合（施策4/7/8/9/10の接続部）

**全体判定**
- **CHANGES_REQUESTED**