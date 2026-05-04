**前提検証**
- `verified`: Round 2 は Round 1 の主要論点を設計上は拾っています。特に `descriptive_diff` 統一、`attempted=0` summary 抑止、二重隔離方針は改善です。
- `verified`: 本件は primitive 変更ではないため、ルックアヘッド論点は主に `stage_c_period` 導出窓の意味論に限定されます。
- `unverified`: 6 worker pool 経路で run-level summary が正しく 1 回 emit されること、`shadow_pairs={}` が BC evaluator の観測として意味論的に有効であること、`context_missing` が識別子契約を満たすことは未成立です。

**施策 1**
判定: `REQUEST_CHANGES`

- [Critical] `_evaluate_stage_bc_shadow_inner` から `build_bc_evaluation_input_from_sidecar` を呼ぶ箇所で、必須引数 `bars_holdout` が渡されていません。現設計のままだと全件 `builder_exception:TypeError` になり、2.1a/2.1b の有効観測が成立しません。修正案: `bars_holdout=tuple(bars_holdout)` と `bounded_recompute_mode=shadow_context.bounded_recompute_mode` を必ず渡し、テスト #4/#30/#31 で実経路を通す。
- [Critical] `bounded_recompute_mode=False` で `shadow_pairs={}` にする設計は、メモリ対策としては理解できますが、BC evaluator の本来評価から cross-pair 情報を落としています。これは「lazy materialization」ではなく「通常 run では cross-pair shadow を観測しない」設計です。修正案: `bc_summary.observation_scope="anchor_only"` を明示し、`status=degraded` または `skipped` 扱いにするか、同等 semantics を保つ lazy proxy を実装する。
- [Critical] 9 fields 対応表では `shadow_pairs` が `OK` / reference とされている一方、実装案では通常 run で空 dict です。設計文書内の意味論が矛盾しています。修正案: mode 別に表を分け、`bounded_recompute_mode=False` の `semantic_validity` を再定義する。
- [Critical] `_emit_shadow_event` は `logger.info` 後に `event_collector.record_event` を呼ぶため、collector 例外時に「正常/skip event を emit 済み → outer except が failed event を追加 emit」になり、per genome 1 event 契約を破ります。修正案: collector 例外は `_emit_shadow_event` 内で握り、event emit 後の例外で二重 event を出さない。
- [Warning] `copy_or_reference=reference` と書かれていますが、`tuple(...)`、`equity_curve_to_bar_equity_series`、`compute_business_day_universe_from_bars(list(...))` は実質コピー/再構築です。修正案: 表記を copy/recompute に修正し、メモリ評価対象に含める。
- [Warning] `shadow_skip_reason` に failed 系理由を入れると skip reason 集計と failure 集計が混ざります。修正案: `failure_reason` と `skip_reason` を分離するか、collector 側で status 別に集計する。

**施策 2**
判定: `REQUEST_CHANGES`

- [Critical] 6 worker 前提の主経路で collector が `None` になり、`shadow_run_summary` を本体が emit できません。smoke script の grep 集計は検証補助であって、C6 の run-level event 契約の実装ではありません。修正案: worker が event payload を親へ返す、または親が構造化 log を正式入力として集計し、run 終端で必ず 1 回 `stage_bc_evaluator.shadow_run_summary` を emit する。
- [Critical] 「親プロセス集約」と「step 2.1 simple model では smoke script 集計」が混在しており、実装責務が曖昧です。修正案: step 2.1 の正式仕様として `in-process only summary` なのか `pool summary supported` なのかを明確化する。環境前提が 6 worker なので後者が必要です。
- [Warning] `record_event` は schema 不正時に silently skipped 扱いします。修正案: `schema_version`、`run_id`、`individual_index`、`bc_summary.status` を検証し、不正 payload は `invalid_event` として別集計する。

**施策 3**
判定: `APPROVE`

- [Suggestion] `StageGateConfig` の default false は妥当です。追加で、config load 時の未指定 default / 明示 true / 明示 false の round-trip test を入れると安全です。

**施策 4**
判定: `REQUEST_CHANGES`

- [Critical] `context_missing` event が `run_id="<unknown>"` しか持てず、`generation_no`、`genome_hash`、`individual_index` の identifier 契約 C3 を満たせません。これは偽観測排除ではなく join 不能な観測を増やします。修正案: `StageBCShadowIdentity` のような最小識別子を `evaluate_stage_c` に別引数で渡し、context 構築失敗時も schema v1 を満たす。
- [Critical] `_emit_context_missing_shadow_event` の責務・schema・collector 例外隔離が未定義です。修正案: `bc_evaluator_shadow.py` に共通 helper を置き、通常 event と同じ schema builder / no-raise collector guard を使う。
- [Warning] `evaluate_stage_c` 側 outer catch は WARN だけで、context_missing helper 自体が失敗した場合に per genome 1 event を保証できません。修正案: outer catch でも最小識別子つき failed event を emit するか、helper を no-raise 化する。

**施策 5**
判定: `REQUEST_CHANGES`

- [Critical] `build_shadow_context` が `evaluate_stage_c` 呼出前に失敗した場合、現設計では有効な `context_missing` event を出す識別子が残りません。修正案: context full object と識別子 object を分け、識別子は `_evaluate_genome_steps` の最初に作る。
- [Critical] pool 経路で `ctx.bc_shadow_collector=None` とするなら、`GenomeEvaluator.__exit__` の summary は `n_genomes_attempted=0` で emit されません。修正案: pool の評価結果戻り値に shadow event payload を含め、親で collector に record する。
- [Warning] `genome, list(ctx.bars_holdout)` は既存契約かもしれませんが、Round 2 で `bars_b` コピーを潰した一方で holdout 側コピーは残っています。修正案: 既存 API が list 必須なら許容、そうでなければ tuple 参照共有に揃える。

**施策 6**
判定: `REQUEST_CHANGES`

- [Critical] `swim_lane` 側も 6 worker / lane 並列時の summary 集約契約が未確定です。parallel_eval と同じ欠陥が再発します。修正案: lane worker も event payload を親へ戻す共通経路に統一する。
- [Warning] `build_shadow_context` 共通化は良いですが、context 構築失敗時の扱いまで共通化しないと経路間で `context_missing` の意味がズレます。修正案: `build_shadow_context_safe -> tuple[context|None, identity, error_reason|None]` にする。

**施策 7**
判定: `REQUEST_CHANGES`

- [Critical] 追加テスト #30/#31 は良いですが、現スニペットの実経路では `bounded_recompute_mode` が builder に渡っていないため、unit test だけ通って integration が壊れます。修正案: `evaluate_stage_bc_shadow_safe` 経由で mode true/false を検証する integration test を追加する。
- [Critical] collector 例外時の二重 event 防止テストがありません。修正案: `record_event` を raise させ、log event が 1 件だけで main flow 不変を assert する。
- [Critical] pool 経路で `shadow_run_summary` が 1 回 emit されるテストがありません。修正案: 2 worker 以上の最小 fixture で親集約と summary emit を検証する。
- [Warning] `stage_c_lite_periods` の `holdout < 180`、端数、bar 欠損は follow-up ではなく C4 acceptance の一部としてテスト計画に入れるべきです。
- [Warning] テーブル見出しと実装規模欄に `25 ケース` が残っており、Round 2 の `32 ケース` と不整合です。

**Fact / Interpretation**
- Fact: `build_bc_evaluation_input_from_sidecar` の signature と呼出が不一致です。Interpretation: 実装すると shadow 観測が全件 skip/failed に倒れる可能性が高いです。
- Fact: 通常 run では `shadow_pairs={}` になります。Interpretation: 2.2 の切替判断に使える BC evaluator 観測とは言い切れず、少なくとも `ok` 観測に混ぜるべきではありません。
- Fact: pool 経路では collector が直接 event を受けません。Interpretation: 6 worker 前提の本番形では C6 run summary が未実装です。
- Fact: `context_missing` は識別子が `<unknown>` になります。Interpretation: C3 の横断 join 不能で、偽観測排除の目的に反します。

**全体判定**
- `CHANGES_REQUESTED`

Round 2 は Round 1 の表面的な穴はかなり塞いでいますが、まだ採用不可です。ブロッカーは `builder 呼出不一致`、`shadow_pairs={}` の意味論、`context_missing` の識別子欠落、`pool 経路 run summary 未実装`、`collector 例外時の二重 event` の 5 点です。これらを直せば、step 2.1 の段階分割方針自体は維持可能です。