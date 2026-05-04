**全体判定**
- `APPROVE_WITH_CHANGES`
- 構造方向は Round 3 より明確に改善しています。特に `WorkerEvaluationResult` による archive 対象外 envelope 化、`StageBCShadowIdentity`、`anchor_plus_shadow` のみを 2.2 有効母集団にする判断は妥当です。
- ただし Round 4 のまま実装着手は不可です。`evaluate_stage_c` 内で得た payload を `_evaluate_genome_steps` の `WorkerEvaluationResult` まで運ぶ中間経路が未定義で、ここが最後の構造的穴です。

**前提検証**
- `verified`: `GenomeStageResult` を完全不変に戻した判断は E1/E2 の観点で正しいです。
- `verified`: smoke grep を正式経路から外し、worker return payload による parent 集約へ寄せた判断は正しいです。
- `unverified`: `evaluate_stage_c` の戻り値を変えずに `shadow_event_payload` を親へ渡す方法がまだ成立していません。
- `unverified`: `anchor_plus_shadow` 母集団だけで n>=30 と invalid rate をどう計算するかの summary schema がまだ不足しています。

**施策 1**
判定: `REQUEST_CHANGES`

- [Critical] `evaluate_stage_bc_shadow_safe` を `dict | None` return にする方針は正しいですが、本文コードはまだ `None` return のままです。修正案: 全 event emit helper が必ず `event_payload` を返し、例外時も failed payload を返す no-raise contract に統一する。
- [Critical] `StageBCShadowContext.identity` を導入したのに、本文コードはまだ `shadow_context.run_id` 等を参照しています。修正案: `identity = shadow_context.identity` を先頭で束縛し、全 event schema を identity 由来に統一する。
- [Critical] `build_bc_evaluation_input_from_sidecar` 呼出がまだ `bars_holdout` / `bounded_recompute_mode` を渡していません。修正案: Round 5 で本文コードを完全更新し、test #33 を wrapper 経由にする。
- [Warning] `WorkerEvaluationResult` を `bc_evaluator_shadow.py` に置くと worker orchestration 型が shadow module に混ざります。修正案: `parallel_eval.py` か `src/alpha_factory/evaluation_result.py` のような中立 module に置く。

**施策 2**
判定: `APPROVE_WITH_CHANGES`

- [Critical] parent 集約モデルは妥当ですが、collector 本文がまだ `n_invalid_events` / `n_anchor_only` / `n_anchor_plus_shadow` を持っていません。修正案: summary schema に scope 別 attempted/ok/degraded/failed/skipped を追加する。
- [Warning] `anchor_only` を degraded に混ぜると `degraded_rate` が「評価失敗」と「観測範囲不足」を同時に表します。修正案: `degraded_reason` または `observation_scope` 別 rate を必須にする。
- [Warning] 2.2 exit criteria は `anchor_plus_shadow` 母集団のみと決めたので、`n_genomes_attempted` 全体分母とは別に `n_anchor_plus_shadow_attempted` を持つべきです。

**施策 3**
判定: `APPROVE`

- [Suggestion] config round-trip test #39 を追加する方針で十分です。

**施策 4**
判定: `REQUEST_CHANGES`

- [Critical] `evaluate_stage_c` は `StageResult` を返す既存 API のままなので、wrapper return payload を caller に戻す経路がありません。修正案: 戻り値を変えず、`bc_shadow_event_capture: list[dict] | None` または `BCShadowEventSink` を optional 引数で渡して、`_evaluate_genome_steps` が後で取り出す方式にする。
- [Critical] `bc_shadow_identity` 追加方針は正しいですが、本文 signature はまだ未反映です。修正案: `bc_shadow_identity: StageBCShadowIdentity | None = None` を追加し、context missing 時は共通 helper に渡す。
- [Warning] `evaluate_stage_c` 内で event を logger emit し、さらに payload を返すなら、emit と return の順序・失敗時挙動を固定してください。推奨は「payload build → logger no-raise → capture no-raise → return payload」です。

**施策 5**
判定: `APPROVE_WITH_CHANGES`

- [Critical] `WorkerEvaluationResult` 分離は正しいですが、`_evaluate_genome_steps` が `evaluate_stage_c` から payload を受け取る方法が未定義です。修正案: worker 内に local capture を作り、`evaluate_stage_c(..., bc_shadow_event_capture=capture)` 後に `WorkerEvaluationResult(c_result, capture.last())` を返す。
- [Warning] `_evaluate_genome_steps` の return type 変更は全 caller に波及します。修正案: parent 側で `worker_result.c_result` のみを既存経路へ流すことを deep equality test #36 で固定する。
- [Warning] worker が例外で return 不能な場合、attempted 分母から漏れる可能性があります。修正案: parent 側で submitted futures 数と received payload 数を別集計する。

**施策 6**
判定: `APPROVE_WITH_CHANGES`

- [Warning] swim_lane も `WorkerEvaluationResult` envelope に統一する方針は妥当です。parallel_eval と別実装にせず、payload extraction / collector record を共通 helper にしてください。
- [Warning] lane ごとの summary emit 重複に注意が必要です。修正案: run-level summary は LaneManager 親で 1 回だけ emit と明記する。

**施策 7**
判定: `REQUEST_CHANGES`

- [Critical] test 表がまだ #1-32 のままです。Round 5 では #1-40 を本文に反映してください。
- [Critical] 追加必須テスト: `evaluate_stage_c` payload capture、`WorkerEvaluationResult` archive 非混入、pool 2 workers parent 集約、`anchor_plus_shadow` のみ 2.2 母集団、collector scope 別 rate。
- [Warning] C4 の holdout edge cases は follow-up ではなく acceptance test 本体に移してください。

**C3 / C7 / C8**
- `anchor_only` と `anchor_plus_shadow` は conditioning set が違うため、同じ母集団として descriptive diff を解釈してはいけません。Round 4 の母集団分離方針は collider bias 防止として妥当です。
- `anchor_only` の観測は 2.2 切替判断には `INCONCLUSIVE` と扱うべきです。degraded として記録し、valid n には入れない方針でよいです。
- `anchor_plus_shadow` の n<30 では切替判断禁止を維持してください。

**Round 5 必須条件**
- `evaluate_stage_c` から `_evaluate_genome_steps` へ payload を渡す方式を SSOT 化する。
- 本文コードを `identity` 参照、`dict | None` return、`bars_holdout` / `bounded_recompute_mode` 渡し込みに完全更新する。
- collector schema を `n_invalid_events` と scope 別集計込みに更新する。
- test 表を #1-40 に更新し、archive 非混入と pool 集約 E2E を必須化する。