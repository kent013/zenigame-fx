**全体判定**
- `CHANGES_REQUESTED`
- Round 3 の構造方向は Round 2 より明確に前進しています。特に `StageBCShadowIdentity`、`observation_scope`、worker→parent payload 集約の方向性は妥当です。
- ただし現設計書は「改訂マトリクス」と「本文コード」が矛盾しており、このまま実装に入ると compile 不整合・archive 混入・pool 集約不能が再発します。Round 4 で本文を SSOT 化してから実装すべきです。

**前提検証**
- `verified`: `context_missing` の識別子問題に対して `StageBCShadowIdentity` を導入する方針は妥当です。
- `verified`: `anchor_only` と `anchor_plus_shadow` を分離する方針は偽観測排除に有効です。
- `unverified`: `GenomeStageResult.shadow_event_payload` が archive / deep comparison / fitness 経路に漏れない保証は未成立です。
- `unverified`: `evaluate_stage_c` 内で生成された shadow event payload を worker return まで運ぶ経路が本文に定義されていません。

**施策 1**
判定: `REQUEST_CHANGES`

- [Critical] 本文コードが Round 3 構造に追従していません。`StageBCShadowContext` は `identity` field に変更されていますが、wrapper 内では `shadow_context.run_id` / `generation_no` / `individual_index` を参照しており compile 不能です。修正案: 全参照を `shadow_context.identity.run_id` 等に統一する。
- [Critical] マトリクスでは builder に `bars_holdout` / `bounded_recompute_mode` を渡すとありますが、本文コードではまだ渡していません。修正案: 本文コードを修正し、test #33 を wrapper 経由の integration test にする。
- [Critical] `evaluate_stage_bc_shadow_safe` は現状 `None` を返すため、`GenomeStageResult.shadow_event_payload` に載せる payload が取得できません。修正案: wrapper を `dict[str, Any] | None` return に変更するか、明示的な `ShadowEventCapture` を渡して payload を回収する。
- [Critical] `observation_scope="anchor_only"` を `status="degraded"` にする方針は妥当ですが、`_make_bc_summary_from_result` への伝搬仕様が未定義です。修正案: `bc_summary.status` と `bc_summary.observation_scope` の決定表を明記する。
- [Warning] `StageBCShadowIdentity` が `genome_hash` 必須だと、hash 計算失敗時に identity 自体が作れません。修正案: `build_shadow_identity_first_safe` で `genome_hash="<hash_failed>"` と `identity_error` を返せるようにする。

**施策 2**
判定: `REQUEST_CHANGES`

- [Critical] マトリクスでは `n_invalid_events` 追加・schema validation とありますが、本文の `BCShadowEventCollector` は Round 2 のままです。修正案: 必須 field validation、`n_invalid_events`、`invalid_event_rate`、invalid reason 集計を本文に反映する。
- [Critical] `pool summary supported` と明記した一方、本文 §5.3 はまだ「pool は smoke script で grep 集計」と書いています。これは SSOT 衝突です。修正案: smoke 集計記述を検証補助に降格し、正式経路を `shadow_event_payload` parent 集約に統一する。
- [Warning] `anchor_only` を degraded と数えるなら、`degraded_rate` は「失敗」ではなく「観測範囲不足」を含みます。修正案: `degraded_rate_by_reason` または `n_anchor_only` を追加し、2.2 判断で混同しない。

**施策 3**
判定: `APPROVE`

- [Suggestion] `phase2_bc_evaluator_shadow_enabled=False` default は妥当です。config load round-trip test は追加してください。

**施策 4**
判定: `REQUEST_CHANGES`

- [Critical] 本文の `evaluate_stage_c` signature に `bc_shadow_identity` が追加されておらず、`context_missing` はまだ `run_id="<unknown>"` です。Round 3 の中核修正が本文に反映されていません。修正案: `bc_shadow_identity: StageBCShadowIdentity | None` を新引数に追加する。
- [Critical] `evaluate_stage_c` が `StageResult` しか返さない場合、shadow event payload を `GenomeStageResult.shadow_event_payload` へどう渡すか未定義です。修正案: `StageResult` に載せず、`_evaluate_genome_steps` の worker return envelope で `c_result` と `shadow_event_payload` を分けて返す。
- [Warning] `context_missing` helper は `bc_evaluator_shadow.py` 共通 helper に寄せるべきです。`stage_gate.py` 内で独自 schema を組むと schema drift が起きます。

**施策 5**
判定: `REQUEST_CHANGES`

- [Critical] `GenomeStageResult.shadow_event_payload` は E1/E2 の dormant 契約に対する新しい漏洩リスクです。archive writer や deep snapshot が dataclass field を丸ごと見る場合、BCEvaluation 系 payload が archive に混入します。修正案: `GenomeStageResult` ではなく `WorkerEvaluationResult` のような archive 対象外 envelope に載せる。
- [Critical] `shadow_event_payload` を `GenomeStageResult` に追加すると、`shadow_enabled=False` でも default `None` field が equality / serialization / schema に影響する可能性があります。修正案: archive/equality 対象外を明示するか、既存 result 型を変更しない。
- [Warning] parent 集約では worker log と parent summary の二重 counting を避ける必要があります。修正案: per-genome event は worker が 1 回 log、parent は payload を count するだけで per-genome re-log しない、と明記する。

**施策 6**
判定: `REQUEST_CHANGES`

- [Critical] `swim_lane` も `GenomeStageResult.shadow_event_payload` 方式にすると archive 漏洩リスクを共有します。修正案: parallel_eval と同じ archive 対象外 envelope を共通化する。
- [Warning] lane 経路と pool 経路で `run_id` / `generation_no` / `individual_index` の採番規則がズレると join 不能になります。修正案: `StageBCShadowIdentity` 生成 helper を完全共通化し、採番 source を明記する。

**施策 7**
判定: `REQUEST_CHANGES`

- [Critical] 本文のテスト一覧はまだ #1-32 で、Round 3 の #33-35 と C4 追加 5 ケースが反映されていません。修正案: テスト表を 35+5 ケースに更新する。
- [Critical] `GenomeStageResult.shadow_event_payload` が archive / deep comparison / fitness に漏れないテストが不足しています。修正案: `shadow_enabled=True` でも `GenomeStageResult` / archive schema / fitness snapshot に payload が入らないことを固定する。
- [Critical] payload return 経路のテストが不足しています。修正案: worker が `shadow_event_payload` を返し、parent が summary 1 件を emit する integration test を追加する。
- [Warning] `anchor_only` と `anchor_plus_shadow` を同じ母集団として diff 分析しないテストまたは集計仕様が必要です。これは collider bias 防止に関わります。

**Round 3 構造の個別評価**
- `StageBCShadowIdentity`: `APPROVE_WITH_CHANGES`。方向性は正しいですが、hash 失敗時の safe fallback と `evaluate_stage_c` signature 反映が必要です。
- `observation_scope`: `APPROVE_WITH_CHANGES`。`anchor_only` を `degraded` として 2.2 有効観測から除外するなら妥当です。
- `GenomeStageResult.shadow_event_payload`: `REQUEST_CHANGES`。既存 result 型に載せるのは archive / equality 漏洩リスクが高いです。archive 対象外 worker envelope に分離してください。
- `pool summary supported`: `APPROVE_WITH_CHANGES`。方向性は必須ですが、本文の smoke grep モデルを削除し、正式 parent 集約に統一してください。

**Fact / Interpretation**
- Fact: Round 3 マトリクスは構造修正を宣言していますが、本文コードは Round 2 のまま残っています。Interpretation: 現設計は SSOT として不成立です。
- Fact: `shadow_event_payload` を `GenomeStageResult` に追加する案は E1/E2 の漏洩面を増やします。Interpretation: このままでは dormant 契約の反証が成立します。
- Fact: 通常 run の `anchor_only` は全件 degraded になります。Interpretation: 2.2 exit criteria の `ok n>=30` には使えず、専用 `anchor_plus_shadow` run を正式な切替判断母集団として定義する必要があります。

**次の修正条件**
- Round 4 ではマトリクスではなく本文コード・9 fields 表・collector 仕様・test 表を完全更新してください。
- `GenomeStageResult` 変更案は撤回し、archive 対象外の worker return envelope に分離するのが安全です。
- `anchor_only` / `anchor_plus_shadow` のどちらを 2.2 exit criteria の母集団にするかを明文化してください。