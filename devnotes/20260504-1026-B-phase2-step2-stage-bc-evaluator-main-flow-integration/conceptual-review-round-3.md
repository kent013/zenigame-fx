**全体判定**  
`CHANGES_REQUESTED`

方向性は `案B`、かつ `2.1a input feasibility → 2.1b shadow logging → 2.2 switch → 2.3 deprecation` で妥当です。Round 3 はかなり収束していますが、まだ `sidecar 利用可能性` と `skip 観測契約` に設計矛盾が残っています。この2点は step 2.1 の成立条件そのものなので、APPROVED にはできません。

**C9 反証**
**Fact**
- `anchor_bundle` / `shadow_pairs` の source は `step 1.8 _shadow_sidecar_inputs を再利用` とされています。
- 一方で §2.5 は、既存 `cross_pair_payload["result"]._shadow_sidecar_inputs` の sanitize 経路を完全不変とし、sidecar 漏洩防止を維持するとしています。
- wrapper 疑似コードでは `bc_input is None` の場合に `return` しており、`stage_bc_evaluator.shadow` event を emit しません。
- しかし schema / exit criteria では `shadow_skipped`, `shadow_skip_reason`, `skip_rate`, `bc_summary.status="skipped"` を切替判断に使う前提です。
- Round 3 では `bounded recomputation` を許可すると書かれている一方、後続の builder docstring / §5.2 には「追加 full backtest 禁止」「新規 backtest は絶対走らせない」が残っています。

**Interpretation**
- sidecar が sanitize 後に消えるなら、`anchor_bundle` / `shadow_pairs` を既存成果物から構築できない可能性があります。これは `BCEvaluationInput` 9 fields のうち最も重要な cross-pair 系 input の feasibility を崩します。
- skip を event として記録しない設計では、`skip_rate <= 30%` を信頼できません。失敗や構築不能が不可視になり、偽の有効観測になります。
- `bounded recomputation` と「絶対 backtest 禁止」が同居しており、実装者がどちらを優先すべきか不明です。

**Critical**
- [Critical] `_shadow_sidecar_inputs` 再利用と sanitize 完全不変が衝突しています。修正提案: `2.1a` で sidecar availability timing を明示し、`pre-sanitize window で参照して即破棄`、`sanitized result とは別の local-only bundle を生成`、`bounded recomputation に fallback` のいずれかを設計で固定してください。
- [Critical] builder skip が現在の疑似コードでは無観測になります。修正提案: `shadow_enabled=True` のときは `ok/degraded/failed/skipped` のいずれでも per genome 1 event を必ず emit し、`shadow_enabled=False` のときだけ 0 event にしてください。
- [Critical] `bounded recomputation` 許可と「新規 backtest 絶対禁止」の記述が矛盾しています。修正提案: 禁止事項を `uncontrolled full backtest 禁止` に全文統一し、`bounded recomputation` の発火条件、上限、metadata、専用検証 run 限定を明文化してください。

**Warning**
- [Warning] `stage_c_lite_periods` の「時系列均等分割」は T064 の 3 windows × 60d と一致しない可能性があります。修正提案: `stage_c_holdout_days < 180`、端数、営業日/暦日、bar 欠損時の derive rule を acceptance C4 に含めてください。
- [Warning] `evaluate_bc_safe` の `outcome.result` が `BCEvaluationResult` 単体なのか `dict[int, BCEvaluationResult]` なのかが曖昧です。修正提案: wrapper 仕様で `evaluate_bc_for_a_pass` の返却型を明記し、`individual_index` unwrap 契約を固定してください。
- [Warning] `skip_rate <= 30%` は妥当な初期ガードですが、skip が特定 pair / market regime / genome class に偏ると collider bias が残ります。修正提案: skip_rate を全体だけでなく `skip_reason` 別、pair 別、generation 別にも集計してください。
- [Warning] `genome_hash = sha256(canonical_serialization(genome))` は良いですが、canonical serialization の version がありません。修正提案: event に `genome_serialization_version` を追加してください。

**Suggestion**
- `2.1a` の完了条件に「有効な `anchor_bundle` / `shadow_pairs` を少なくとも1 fixtureで構築できる」を追加すると、最重要リスクを早期に潰せます。
- `shadow_run_summary` に `n_genomes_attempted` を追加し、`observed/skipped/failed/degraded/ok` の分母を固定してください。
- §8 の進捗表が Round 2 表記のままなので、Round 3 では `2.1a / 2.1b` に更新してください。

**結論**
設計の方向性は採用可能です。ただし `sidecar 利用可能性`、`skip event 必須化`、`bounded recomputation 記述統一` は実装前に修正必須です。この3点を直せば、次 round は `APPROVED` にかなり近いです。