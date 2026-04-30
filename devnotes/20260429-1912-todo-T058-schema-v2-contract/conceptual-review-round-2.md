全体判定: **CHANGES_REQUESTED**

[Critical] `passive validation` 方針と `read時 fail` の適用タイミングが矛盾しています。  
Fact: 改訂案は「T058 は passive validation (log_only)」と定義しています（[conceptual-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-1912-todo-T058-schema-v2-contract/conceptual-design.md#L36), [conceptual-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-1912-todo-T058-schema-v2-contract/conceptual-design.md#L152), [conceptual-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-1912-todo-T058-schema-v2-contract/conceptual-design.md#L215)）。  
Fact: 同時に「sieve loader で fail_closed」「read 時 v1 fail」を T058 実施項目に入れています（[conceptual-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-1912-todo-T058-schema-v2-contract/conceptual-design.md#L195), [conceptual-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-1912-todo-T058-schema-v2-contract/conceptual-design.md#L204)）。  
Interpretation: incremental 移行の前提と衝突し、T058 単独で読取系が先に壊れるリスクがあります。  
修正提案: T058 では read/write とも `enforcement_mode=log_only` で統一し、`fail_closed` は T067 の一斉切替時に有効化してください。`run_alpha_sieve` も `enforcement_mode` 連動にしてください。

[Warning] artifact inventory の定義品質に不整合があります。  
Fact: 見出しは「全9経路」ですが表は 10 行です（[conceptual-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-1912-todo-T058-schema-v2-contract/conceptual-design.md#L38), [conceptual-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-1912-todo-T058-schema-v2-contract/conceptual-design.md#L42)）。  
Fact: `diagnostics sidecar` と `stage_a_provenance.parquet` は同一実体です（[conceptual-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-1912-todo-T058-schema-v2-contract/conceptual-design.md#L47), [conceptual-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-1912-todo-T058-schema-v2-contract/conceptual-design.md#L48), [diagnostics_sidecar.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/diagnostics_sidecar.py#L50)）。  
Interpretation: full coverage 主張の監査性が落ちます。  
修正提案: 4/5 を統合し、件数表記を一致させてください。

[Warning] 「全経路 coverage」にはまだ抜けがあります。  
Fact: 現行実装は `history.json` / `best_genome.json` も永続化しています（[run_ga.py](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py#L998), [run_ga.py](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py#L1003)）。  
Fact: `run-{N}.md`、`batch_summary.json`、`comparison_report.md`、`analysis-claude.md` も生成されます（[generate_run_report.py](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/generate_run_report.py#L800), [compare_batch_runs.py](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/compare_batch_runs.py#L252), [compare_batch_runs.py](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/compare_batch_runs.py#L256), [analyze_run.py](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/analyze_run.py#L168)）。  
Interpretation: 「dataset_epoch_id 全 artifact 追跡」を厳密にやるなら inventory 追加が必要です。  
修正提案: 「contract必須 artifact」と「派生表示 artifact」を分けた 2 層 inventory にしてください。派生側は `summary.json` 参照で許容する方針を明記してください。

[Warning] `enforcement_mode` の実装着地点が未定義です。  
Fact: config で切替と書かれていますが、どの config 構造に置くかは未記載です（[conceptual-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-1912-todo-T058-schema-v2-contract/conceptual-design.md#L152)）。  
Interpretation: 実装時に分岐点がぶれます。  
修正提案: `config/alpha_factory/default.yaml` と `AlphaFactoryConfig` に `schema_contract.enforcement_mode` を明示追加してください。

[Suggestion] `RunContext` は方向性が妥当です。  
Fact: 最上流 source を `RunContext.dataset_epoch_id` に統一する設計は定義されています（[conceptual-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-1912-todo-T058-schema-v2-contract/conceptual-design.md#L107)）。  
Interpretation: 4 段伝搬を満たすために有効です。  
提案: 各コンポーネント API に `run_context` 必須注入を明記すると、横流れ実装を防げます。

[Suggestion] `cascade_contract_version` 追加方針は妥当です。  
Fact: `summary.json` の既存 `schema_version: "1.1"` は現行テストが前提にしています（[run_ga.py](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py#L875), [test_run_ga_parallel.py](/Users/ishitoya/repository/zenigame-fx/tests/scripts/test_run_ga_parallel.py#L172)）。  
Interpretation: 別キー追加は非破壊です。  
提案: `cascade_contract_version` は int 固定、`schema_version` は string 維持を契約文に明記してください。

[Suggestion] `dataset_epoch_id` 決定論制約は T058 文書化、T059 実装で正しいです。  
Fact: grammar と deterministic 要件はすでに文書化されています（[conceptual-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-1912-todo-T058-schema-v2-contract/conceptual-design.md#L130)）。  
Interpretation: contract と実装責務の分離は適切です。  
提案: T059 DoD に「同一 window で同一 ID」「window が違えば ID 変化」のテストを明記してください。

**残検証ポイントへの回答**
1. artifact 別 contract 分割: 方向性は妥当。上記 Warning の inventory 整理が必要。  
2. RunContext 最上流性: 満たせます。`run_context` 必須注入を API 契約に追加してください。  
3. passive→fail_closed 戦略: 方針は妥当。ただし現状記述は read 側だけ先行 fail が混在しており要修正。  
4. activation timing: T067 一斉切替は妥当。T058 の read fail 記述は T067 側へ移してください。  
5. `cascade_contract_version` 追加: 正しい。既存 `schema_version` テストには影響しません。  
6. 決定論制約: T058 に契約として残し、T059 で実装・検証するのが適切です。  
7. 見落とし経路: `history.json` / `best_genome.json` / `run-*.md` / `batch_summary.json` / `comparison_report.md` / `analysis-claude.md` を inventory 方針上どう扱うか明示が必要です。