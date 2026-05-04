**全体判定**  
`CHANGES_REQUESTED`

方向性はかなり良く、`stage_gate.evaluate_stage_c` 内の sanitize 直前に shadow を置く判断は、sidecar 利用可能性と sanitize SSOT の両立策として妥当です。ただし Round 4 では、配置変更によって新たに `Stage B artifacts をどう渡すか` という構造問題が発生しています。ここが未解決なので、まだ `APPROVED` にはできません。

**C9 反証**
**Fact**
- `BCEvaluationInput.trades / bars / folds` は `legacy_b_result` と `bars_b` を source にしています。
- Round 4 の wrapper は `stage_gate.evaluate_stage_c` 内に移動し、引数は `cp_result_with_sidecar / cross_pair_payload / bars_holdout / stage_config` 中心です。
- wrapper signature から `legacy_b_result` と `bars_b` が消えています。
- §4.1 にはまだ `parallel_eval.py` / `swim_lane.py` に wrapper 1行追加とあり、§2.2 の「caller 完全不変」と矛盾しています。
- schema には `genome_serialization_version`, `n_genomes_attempted`, `skip_rate_by_reason` が反映されていません。
- acceptance C2 は「builder skip / shadow_enabled=False で 0 件」と書いており、Round 4 の「skip でも 1 event emit」と矛盾しています。

**Interpretation**
- sanitize 直前配置は正しい方向ですが、`stage_gate.evaluate_stage_c` 単独では Stage B 側の input を構築できない可能性があります。
- caller 完全不変を維持すると、`BCEvaluationInput` の 9 fields を満たせないリスクがあります。
- skip 観測契約と schema がまだ古い記述を含むため、実装者が逆の挙動を実装する危険があります。

**Critical**
- [Critical] `stage_gate.evaluate_stage_c` 内配置では `legacy_b_result / bars_b / folds` の供給経路が消えています。修正提案: caller から `StageBCShadowContext` を `evaluate_stage_c` に渡す、または `stage_gate` 内で Stage B artifacts を持たない field は明示 skip にする、のどちらかを設計で固定してください。
- [Critical] 「caller 完全不変」と §4.1 の `parallel_eval.py` / `swim_lane.py` 変更候補が矛盾しています。修正提案: caller 不変を捨てて context 渡しにするか、変更ファイル候補から caller 変更を削除し、Stage B input 不足時の skip 契約に寄せてください。
- [Critical] skip event 契約が C2 と矛盾しています。修正提案: C2 を `shadow_enabled=True では ok/degraded/failed/skipped いずれも per genome 1 event、shadow_enabled=False のみ 0 event` に修正してください。
- [Critical] `shadow_run_summary` を run 終端で emit する場所がありません。`stage_gate.py` 内完結では run-level 集計を出せません。修正提案: run-level summary はログ後処理で生成するか、`run_ga` / evaluator 上位層に collector を置く設計にしてください。

**Warning**
- [Warning] `bounded recomputation` の文言統一がまだ未完了です。§2.1 の docstring と設計判断に「追加 full backtest 禁止」「新規 backtest は絶対走らせない」が残っています。修正提案: 全文を `uncontrolled full backtest 禁止` に統一してください。
- [Warning] schema v1 に `genome_serialization_version`, `n_genomes_attempted`, `skip_rate_by_reason` が未反映です。修正提案: 改訂対応マトリクスと §2.3 schema / acceptance を一致させてください。
- [Warning] `2.1a success criteria` に fixture での `anchor_bundle / shadow_pairs` 構築確認が本文側で十分に反映されていません。修正提案: §1.5 または acceptance に明示追加してください。
- [Warning] `bc_summary.status="failed"` と `shadow_skipped=False` の扱いは良いですが、`failed` を skip_rate 分子に入れるか failure_rate と分けるかが揺れています。修正提案: `skip_rate`, `failure_rate`, `degraded_rate` を分離してください。

**Suggestion**
- `StageBCShadowContext` を導入するなら、最小 field は `run_id`, `generation_no`, `individual_index`, `genome`, `legacy_b_result`, `bars_b`, `bounded_recompute_mode` です。
- `stage_gate.evaluate_stage_c` では sidecar 参照と shadow 実行だけを行い、run-level 集計は外部 aggregator に寄せる方が責務分離として自然です。
- §7 のリスク表も `追加 full backtest 禁止` の古い表現が残っているので更新してください。

**結論**
Round 4 の根本方針、特に sanitize 直前配置は採用できます。ただし `Stage B artifacts の供給経路` と `run-level summary の emit 位置` が未解決です。次 round でこの2点と schema/C2 の矛盾を直せば、概念設計としては `APPROVED` 可能です。