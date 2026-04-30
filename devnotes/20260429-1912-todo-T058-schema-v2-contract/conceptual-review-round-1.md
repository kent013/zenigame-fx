全体判定: **CHANGES_REQUESTED**

前提確認:
- `docs/alpha_factory/`、`devnotes/20260428-2300-cascade-port-debate/synthesis.md`、本 T058 設計ノート、関連コード、直近 `git log` は確認済みです。C1 / C4 / C9 のレビュー前提は満たしています。
- 現行コード上、`dataset_epoch_id` はまだ runtime config に存在せず、archive/history/report への伝搬経路も未実装です ([config.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/config.py#L51), [archive.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/archive.py#L698), [run_ga.py](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py#L875))。
- 現行 `summary.json` には別目的の top-level `schema_version: "1.1"` が既にあり、テストもそれを前提にしています ([run_ga.py](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py#L875), [test_run_ga_parallel.py](/Users/ishitoya/repository/zenigame-fx/tests/scripts/test_run_ga_parallel.py#L172))。

**1. 使命との整合性**
Fact:
- 上位文書は `dataset_epoch_id` を epoch 汚染防止の中核契約として要求しています ([synthesis.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260428-2300-cascade-port-debate/synthesis.md#L398))。
- T058 案は「4 field を全永続化経路で必須」と書く一方、実装表では `calibrate_gate_history.py` と `generate_run_report.py` には実質 `dataset_epoch_id` しか追加していません ([conceptual-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-1912-todo-T058-schema-v2-contract/conceptual-design.md#L18))。

Interpretation:
- live_criteria への本質的貢献は `dataset_epoch_id` による epoch 分離です。`archive_role` / `source_stage` まで「全経路必須」に広げる定義は、使命に必要な contract と artifact ごとの意味論を混同しています。

- [Critical] 「4 field 全経路必須」は contract の切り方が誤っています。`archive_role` と `source_stage` は genome-entry 系 artifact には意味がありますが、run-level の `summary.json` や calibrate history 1 行には単一値として定義できません。  
修正提案: contract を artifact class ごとに分割してください。`GenomeEntryContractV2`、`CalibrateHistoryContractV2`、`RunReportContractV2`、`DiagnosticsContractV2` を別定義にし、全 artifact 共通必須は `dataset_epoch_id` と artifact-local version のみに絞るべきです。
- [Suggestion] 期待効果の記述は「quality 低下を検出可能」ではなく「role/stage 別に分解観測可能」に留めた方が使命整合です。

**2. 禁止事項違反**
Fact:
- 禁止事項 8 は「archive スキーマ伝搬漏れ」の防止です。
- 現行 `DatasetConfig` に `dataset_epoch_id` は無く、`GenomeArchive._new_row()` も `run_id/run_number/generation/instrument/lane_id` しか受け取りません ([config.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/config.py#L51), [archive.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/archive.py#L698))。

Interpretation:
- 今の設計は「必須化」を宣言しているのに、供給元と 4 段伝搬の最上流が設計されていません。これは禁止事項 8 を防ぐ設計として未完成です。

- [Critical] `config → runtime context → meta → consumer` の最上流が欠けています。  
修正提案: T058 のスコープに `dataset_epoch_id` の受け皿を明示追加してください。少なくとも `AlphaFactoryConfig` か dedicated `RunContext` に載せ、`run_ga.py`、`GenomeArchive`、`calibrate_gate.py`、report writer が同じ source から読む設計にしてください。
- [Warning] T058 単独で fail-closed lint を有効化すると、T063/T066 前の現行 writer が全滅します。  
修正提案: `new_cascade` 名前空間で隔離するか、T058 で最低限の producer まで同時着地させてください。

**3. 実現可能性**
Fact:
- archive の read/write は `GenomeArchive.flush/load()` に集中していますが、FSP updater は `pq.read_table()` を直接呼び、diagnostics sidecar も独自 schema で Parquet を書いています ([archive.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/archive.py#L581), [fsp_updater.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/fsp_updater.py#L114), [diagnostics_sidecar.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/diagnostics_sidecar.py#L34))。

Interpretation:
- `assert_v2_schema()` を各 write/read 冒頭で呼ぶだけでは coverage 不足です。直 Parquet read/write や report 系 JSON writer が複数あります。

- [Warning] 質問 1 への回答は「No」です。full coverage ではありません。  
修正提案: validator 呼び出し対象を `GenomeArchive.flush/load`、`append_record/read_history` だけでなく、`run_ga._write_reports`、`diagnostics_sidecar.build_sidecar_table/write_stage_a_provenance`、`fsp_updater._read_archive_with_fsp_compat/_atomic_write_parquet`、`run_alpha_sieve` の loader にまで広げてください。
- [Suggestion] `schema_contract.py` は `assert_*` だけでなく、artifact ごとの `normalize_*` も持たせると後段 drift を減らせます。

**4. 期待効果の妥当性**
Fact:
- `dataset_epoch_id` による warmstart / calibrate scope 分離は構造的な汚染防止です。
- 一方、「bypass 比率上昇が archive 質低下を招く兆候を検出可能」は設計ノート上の期待効果で、まだ実データ検証はありません ([conceptual-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-1912-todo-T058-schema-v2-contract/conceptual-design.md#L47))。

Interpretation:
- 汚染防止効果は妥当です。quality 検出の主張はまだ観測可能化の段階で、因果主張に寄せると C3 に抵触しやすいです。C7 はこの TODO 自体には本質的には未適用ですが、後段 monitor 解釈では適用が必要です。

- [Warning] `archive_role` を持てば archive 品質低下を「検出できる」とまで言うのは強すぎます。  
修正提案: 文言を「role 別に層別観測できる。品質低下との関連は後段 run で検証」に下げてください。
- [Suggestion] `source_stage` の効果も「誤判定回避のための識別子追加」と書く方が妥当です。

**5. リスク**
Fact:
- `summary.json` の top-level `schema_version` は既に report schema version として使われています ([run_ga.py](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py#L875))。
- T058 案は `schema_version=2` を全経路共通 field として導入しようとしています ([conceptual-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-1912-todo-T058-schema-v2-contract/conceptual-design.md#L24))。

Interpretation:
- 同じ key 名で「report schema version」と「dataset contract version」を兼ねさせると、既存 consumer/test と意味論衝突を起こします。

- [Critical] `schema_version` の名前衝突は foundation 層の重大リスクです。  
修正提案: `summary.json` は既存の `schema_version` を維持し、T058 用には `dataset_contract_version` か `cascade_contract_version` を新設してください。Parquet/JSONL 側は artifact-local `schema_version` を使ってもよいですが、run report 系とは名前空間を分けるべきです。
- [Warning] `source_stage="C-lite"` のような mixed case + hyphen は downstream join/filter で揺れやすいです。  
修正提案: enum member は `C_LITE`、永続値は `"c_lite"` のように lower_snake_case に寄せてください。

**6. スコープの適切さ**
Fact:
- 上位文書は big-bang 移行でも `new_cascade` 名前空間で開発し、smoke 後に旧系削除としています。
- T058 案は foundational task ですが、現行系に直接 fail-closed を差し込む書き方です。

Interpretation:
- 基盤 contract の先行固定は正しいです。ですが、artifact class 分割と供給元追加まで含めないと「設計の先頭 task」としては狭すぎ、逆に lint 有効化まで含めると広すぎます。

- [Warning] 現スコープは「定義だけ先行」なのに「fail-closed まで有効化」で実装順序が噛み合っていません。  
修正提案: T058 を `contract 定義 + source 導入 + passive validation` に縮め、hard fail は T063/T066/T067 合流時に activate する設計へ分離してください。
- [Suggestion] `archive_role` / `source_stage` の enum 定義は T058、writer 実装は後段、hard-required 化は合流 TODO、の 3 段に切ると実装しやすいです。

**7. メモリ制約**
Fact:
- 現行 archive は PyArrow table 化して一括 write しています ([archive.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/archive.py#L592))。
- FSP updater は archive 全体を pandas に落として再書き込みします ([fsp_updater.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/fsp_updater.py#L114))。

Interpretation:
- 4 つの軽量 metadata 追加自体のメモリ負荷は小さく、24GB / worker 3GB 制約に対して本質的な問題ではありません。支配的なのは既存の backtest と pandas 変換です。

- [Suggestion] 質問 5 への回答は「概ね問題なし」です。lint overhead は軽微です。監視すべきは列追加ではなく FSP の pandas 化と GA 評価側 RSS です。
- [Suggestion] string 列は dictionary-encoded Parquet を前提にしておくと将来の archive 膨張にも安全です。

**8. 前提検証 (C4)**
Fact:
- 現行 codebase には `dataset_epoch_id` も epoch manager もまだ存在しません。
- `calibrate_state` は今も `base_config_hash + dataset_span + instrument + stage_gate_version` で scope を切っています ([calibrate_state.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/calibrate_state.py#L44), [run_ga.py](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py#L1075))。

Interpretation:
- 質問 4 の方向性自体は正しいです。v1 record の自動排除も big-bang 前提なら正しいです。ただし `dataset_epoch_id` が current context に確実に載る前提を満たしていません。

- [Warning] 質問 4 への回答は「方向性は正しいが、前提不足」です。  
修正提案: `find_latest_applicable(base_config_hash, dataset_epoch_id, ...)` に変える前に、`dataset_epoch_id` の current-source を明記し、history writer と loader が同じ値生成規約を使うことを契約化してください。
- [Warning] 質問 3 への回答は「string 型だけでは不足」です。  
修正提案: T058 で生成ロジックまでは持たなくてよいですが、最低限 `^[a-z0-9_]+$`、lowercase、空文字禁止、同一 epoch で決定論的一致、の grammar は固定してください。

**9. Design-first (C1)**
Fact:
- レビュー前に `synthesis.md` §9/§14、`docs/alpha_factory/stage-gates.md` の T054 節、関連 source、関連 tests、直近 `git log` を確認しました。
- 現行の追加 consumer として `extract_batch_metrics.py`、`run_alpha_sieve.py`、`population.jsonl`、run cache JSON、diagnostics sidecar、FSP updater を確認しました ([extract_batch_metrics.py](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/extract_batch_metrics.py#L134), [run_alpha_sieve.py](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_alpha_sieve.py#L220), [run_ga.py](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py#L1008), [run_ga.py](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py#L1479))。

Interpretation:
- C1 は満たしています。見落とし経路の観点では、設計ノートの 5 経路だけでは不足です。

- [Warning] 質問 6 への回答は「Yes、見落としあり」です。  
修正提案: 少なくとも `diagnostics/stage_a_provenance.parquet`、FSP archive rewrite、`population.jsonl`、`.cache/alpha_factory/runs/{run_id}.json`、`extract_batch_metrics.py` の派生 JSON を棚卸し対象に追加してください。
- [Suggestion] 設計書に「artifact inventory」表を先頭追加すると、禁止事項 8 の再発をかなり防げます。

補足回答:
- 質問 2: `StrEnum` 自体は big-bang 前提なら問題ありません。永続値は lower_snake_case を推奨します。
- 質問 5: lint の性能コストは軽微です。メモリ制約上の本丸ではありません。

要点は 3 つです。`dataset_epoch_id` の供給源を先に設計へ入れること、contract を artifact 別に分けること、`summary.json` の既存 `schema_version` と衝突させないことです。これが入れば APPROVED に近づきます。