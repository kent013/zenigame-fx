**全体判定**
- `CHANGES_REQUESTED`
- capture sink、`WorkerEvaluationResult` 分離、`anchor_plus_shadow` 母集団分離という構造方向は妥当です。
- ただし Round 5 本文は「SSOT 完全更新」になっていません。改訂マトリクスと本文コードが依然として衝突しており、この状態では `APPROVED` は出せません。

**Critical**
- [Critical] `WorkerEvaluationResult` の配置が矛盾しています。マトリクスでは `parallel_eval.py` へ移動とありますが、本文 §4.3 ではまだ `bc_evaluator_shadow.py` に定義されています。修正案: 本文から削除し、`parallel_eval.py` 側の dataclass と import 方針を SSOT にする。
- [Critical] `evaluate_stage_bc_shadow_safe` はマトリクスでは `dict | None` return ですが、本文 signature は `-> None` のままです。`_emit_shadow_event` も `-> None` で payload を返していません。修正案: wrapper / inner / emit helper の return contract を本文コードに反映する。
- [Critical] `shadow_context.identity` 参照へ未統一です。本文ではまだ `shadow_context.run_id` / `individual_index` 等を参照しており、`StageBCShadowContext` 定義と compile 不整合です。修正案: `identity = shadow_context.identity` 由来に全置換する。
- [Critical] builder 呼出がまだ `bars_holdout` / `bounded_recompute_mode` を渡していません。Round 2 から残る実装不能点です。修正案: 本文 §4.3 の呼出をマトリクス通りに更新する。
- [Critical] `evaluate_stage_c` signature に `bc_shadow_identity` / `bc_shadow_event_capture` がありません。本文 §7.2 は Round 2 のままで、`run_id="<unknown>"` も残っています。修正案: context missing helper と capture sink の実配線を本文に反映する。
- [Critical] parent 集約の SSOT が衝突しています。§5.3 は `WorkerEvaluationResult` 経由と書く一方、§8.6 はまだ smoke grep / simple model と書いています。修正案: §8.6 を削除または parent 集約モデルに完全置換する。
- [Critical] capture sink と `event_collector` の二重 counting リスクが未解消です。worker 内で collector に record し、parent が capture payload を再 record すると summary が二重計上されます。修正案: worker/in-process 共通で `event_collector=None`、capture payload を parent でのみ `record_event` する方針に一本化する。
- [Critical] collector 本文が旧 schema のままです。`n_invalid_events`、`n_anchor_only`、`n_anchor_plus_shadow`、`n_genomes_submitted`、`degraded_rate_by_reason` が実装案にありません。修正案: §5.2 を更新する。
- [Critical] test 表が #1-32 のままで、#33-40 が本文にありません。修正案: archive 非混入、payload capture、pool 2 workers、scope 別母集団、config round-trip を本文表に追加する。

**施策別判定**
- 施策 1 `bc_evaluator_shadow.py`: `REQUEST_CHANGES`。return contract / identity / builder 呼出が本文未反映。
- 施策 2 collector: `REQUEST_CHANGES`。scope 別集計と invalid event schema が本文未反映。
- 施策 3 config field: `APPROVE`。default false 方針は妥当。
- 施策 4 `evaluate_stage_c`: `REQUEST_CHANGES`。capture sink と identity signature が本文未反映。
- 施策 5 `parallel_eval`: `REQUEST_CHANGES`。`WorkerEvaluationResult` 配置と parent 集約が本文未反映。
- 施策 6 `swim_lane`: `REQUEST_CHANGES`。parallel_eval と同型の parent 集約 SSOT が未確定。
- 施策 7 tests: `REQUEST_CHANGES`。本文表が旧 32 件のまま。

**Fact / Interpretation**
- Fact: Round 5 マトリクスには正しい修正方針が並んでいますが、本文コードは Round 2/3 の断片を多く残しています。
- Interpretation: 設計思想は採用可能ですが、詳細設計書としては SSOT 不成立です。
- Fact: capture sink と parent collector が併存しています。
- Interpretation: 二重 counting を防ぐ実装規約がないため、C6 summary の信頼性に反証が残ります。

**最小修正条件**
- 本文 §4.3、§5.2、§7.2、§8、§9.1 をマトリクス通りに実更新する。
- worker 側は capture のみ、parent 側だけが collector record する、と明文化する。
- `WorkerEvaluationResult` は `parallel_eval.py` に置き、`GenomeStageResult` は完全不変を維持する。
- `anchor_plus_shadow` のみを 2.2 valid n に算入する summary fields と tests を本文に入れる。

この 4 点が本文に反映されれば、構造面は `APPROVED` 可能です。