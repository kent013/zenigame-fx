全体判定: **CHANGES_REQUESTED**

[Critical] `LOG_ONLY` 統一方針と文書内の実施項目がまだ矛盾しています。  
Fact: `Validator 配置` では T058 は read/write とも `LOG_ONLY` と明記されています（[conceptual-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-1912-todo-T058-schema-v2-contract/conceptual-design.md#L154), [conceptual-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-1912-todo-T058-schema-v2-contract/conceptual-design.md#L171)）。  
Fact: 同じ文書の `T058で実施するもの` と `制約` には「read時 v1 fail」「既存 v1 は読まない」と残っています（[conceptual-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-1912-todo-T058-schema-v2-contract/conceptual-design.md#L231), [conceptual-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-1912-todo-T058-schema-v2-contract/conceptual-design.md#L243)）。  
Interpretation: 切替戦略の中心仕様が二重化しており、実装時の解釈ブレを起こします。  
修正提案: T058 文言を完全に `LOG_ONLY` 側へ統一し、`v1 fail` は T067 セクションにのみ残してください。

[Warning] Tier2 の coverage はまだ完全ではありません。  
Fact: `run_alpha_sieve` は派生レポート `sieve-R{N}.md` を書き出しますが inventory に未掲載です（[run_alpha_sieve.py](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_alpha_sieve.py#L699)）。  
Fact: `extract_batch_metrics` は JSON だけでなく任意 Markdown (`--report`) も出力しますが Tier2 に未掲載です（[extract_batch_metrics.py](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/extract_batch_metrics.py#L280)）。  
Interpretation: 「Tier1+Tier2 で full coverage」という主張には不足があります。  
修正提案: Tier2 に `sieve-R{N}.md` と `extract_batch_metrics --report` を追加してください。

[Warning] `enforcement_mode` 配置は妥当ですが、読み込みバリデーション要件が未定義です。  
Fact: `SchemaContractConfig` と YAML 配置は明記されています（[conceptual-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-1912-todo-T058-schema-v2-contract/conceptual-design.md#L211), [conceptual-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-1912-todo-T058-schema-v2-contract/conceptual-design.md#L212)）。  
Interpretation: `log_only/fail_closed` 以外の値、欠落時 fallback、unknown key の扱いを決めないと運用事故になります。  
修正提案: `SchemaContractConfig.__post_init__` の許容値検証、loader fallback、設定値不正時の fail-fast 方針を DoD に追加してください。

[Warning] `RunContext` 必須注入は正しいが、T058 単独での一括シグネチャ変更はリスクが高いです。  
Fact: 全 component API への必須注入を T058 で明記しています（[conceptual-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-1912-todo-T058-schema-v2-contract/conceptual-design.md#L210)）。  
Interpretation: 変更範囲が広く、T058 の主目的（contract 基盤）に対して破壊半径が大きいです。  
修正提案: 段階導入にしてください。`RunContext` 追加は T058 で行い、必須化は T059/T063 合流で段階的に締める方が安全です。

[Suggestion] Tier2 は「lintなし convention」のままでも成立しますが、軽量ガードは入れた方が良いです。  
Fact: Tier2 は実装規約のみで lint 対象外と定義されています（[conceptual-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-1912-todo-T058-schema-v2-contract/conceptual-design.md#L71)）。  
Interpretation: 引用漏れ防止には最低限の自動検証が有効です。  
提案: fail しない `assert_epoch_id_present_for_display()` 相当を Tier2 生成スクリプトに共通適用してください。

[Suggestion] `cascade_contract_version` 型分離は妥当です。  
Fact: int 固定の明記は適切です（[conceptual-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-1912-todo-T058-schema-v2-contract/conceptual-design.md#L218), [conceptual-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-1912-todo-T058-schema-v2-contract/conceptual-design.md#L291)）。  
Interpretation: 既存 `schema_version: "1.1"` との衝突回避として十分です。  
提案: JSON schema（または同等テスト）で `schema_version: str` と `cascade_contract_version: int` を固定してください。

残検証ポイントへの回答:
1. 2 層 inventory の設計自体は妥当です。現時点は Tier2 の 2 経路追加後に full coverage 判定が可能です。  
2. read-fail も `LOG_ONLY` 統一の意味論は妥当です。文書内の矛盾行を削れば T058 単独破綻は回避できます。  
3. `schema_contract.enforcement_mode` の YAML 配置は問題ありません。値検証と fallback 方針の明文化が追加で必要です。  
4. RunContext 注入は段階導入が筋です。一括必須化は T058 では広すぎます。  
5. Tier2 を convention のみで運用するなら、少なくとも軽量 non-blocking チェックを入れるべきです。  
6. 現状は `sieve-R{N}.md` と `extract_batch_metrics --report` が見落としです。これを追加すればほぼ最終形です。