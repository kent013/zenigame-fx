**全体判定**  
`APPROVED`

Round 5 は概念設計として採用可能です。Round 4 までの構造的な欠陥だった `Stage B artifacts 供給経路`、`run-level summary emit 位置`、`skip event 契約`、`bounded recomputation 文言矛盾` は、設計方針として解消されています。残っている論点は概念設計の否決理由ではなく、詳細設計前に直すべき記述整合・契約明確化です。

**C9 反証**
**Fact**
- `StageBCShadowContext` により `legacy_b_result / bars_b / run_id / generation_no / individual_index` を caller から `evaluate_stage_c` に渡す設計になりました。
- shadow は `stage_gate.evaluate_stage_c` 内の sanitize 直前で実行され、sidecar 利用可能性と sanitize 維持を両立する設計です。
- `BCShadowEventCollector` を上位層に置き、run 終端で `shadow_run_summary` を emit する責務分離になりました。
- `shadow_enabled=True` では `ok/degraded/failed/skipped` の per genome 1 event が acceptance C2 で固定されています。

**Interpretation**
- 主要な反証候補だった「必要 artifact が無い」「skip が不可視」「run summary を出す場所が無い」は概念上は潰れています。
- step 2.1 は live_criteria へ直接寄与しませんが、2.2 switch の前提観測を作る LOG_ONLY phase として North Star に間接寄与します。
- よって、段階分割された `案B / step 2.1a + 2.1b` は妥当です。

**Critical**
- [Critical] なし。

**Warning**
- [Warning] `StageBCShadowContext` の説明では `genome` を含めるとありますが、dataclass 定義には `genome: Genome` がありません。修正提案: `genome` を context field に追加し、`genome_hash` 生成と builder 入力の SSOT にしてください。
- [Warning] §2.1 に「新規 backtest は絶対走らせない」が残っており、`bounded recomputation` 許可と再び矛盾します。修正提案: `通常 run では uncontrolled full backtest 禁止、専用検証 run では bounded recomputation のみ許可` に全文統一してください。
- [Warning] §4.1 の `parallel_eval.py` / `swim_lane.py` 変更説明が「Stage C 後に共通 wrapper 1行追加」のままです。修正提案: `StageBCShadowContext 構築 + evaluate_stage_c へ bc_shadow_context / collector 追加` に更新してください。
- [Warning] `shadow_enabled=True` かつ `bc_shadow_context is None` の場合、現在の疑似コードでは wrapper が呼ばれず 0 event になり得ます。修正提案: context missing を `skipped/context_missing` として emit するか、caller 側で context 必須を assert する acceptance を追加してください。
- [Warning] `skip_rate / failure_rate / degraded_rate` を分離した一方、2.2 exit criteria は合算 <=30% のままです。修正提案: `invalid_observation_rate = skip_rate + failure_rate + degraded_rate <= 30%` と明示してください。

**Suggestion**
- `BCShadowEventCollector.record_event` は logger emit と同じ payload を受ける設計にすると、run summary と raw log の乖離を防げます。
- `StageBCShadowContext` は `frozen=True` のままで良いですが、`bars_b` は mutable list ではなく tuple 化すると参照安全性が上がります。
- 詳細設計では `bounded_recompute_mode=True` の発火条件と最大回数を acceptance に落としてください。

**結論**
Round 5 の概念設計は `APPROVED` です。実装・詳細設計に進めてよいです。上記 Warning は詳細設計に入る前のテキスト修正として処理してください。