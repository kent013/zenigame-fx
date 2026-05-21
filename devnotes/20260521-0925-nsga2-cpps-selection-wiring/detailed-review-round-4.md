**Fact**
- Round 3 の Critical は解消されています。`offspring_count` 導入で P5a/P5b both 時の頭数 contract は成立します。
- `eligible==1` の `parent_pairs` 長、`warmstart_active`、P3 の 6 列 schema も今回の記述で整合しました。
- 残るのは CPPS/warmstart 注入の dedup 後 slot 再計算だけです。

**P3: ParetoFeaturesLite sidecar**
判定: `APPROVE`

Critical/Warning なし。builder 化、6 列 schema、finite precheck、`source_stage=="B"` invariant で設計として十分です。

**P5a: NSGA-II only selection**
判定: `APPROVE`

Critical/Warning なし。`offspring_count` contract、`eligible==1` self-mating、elite copy 不使用、all-mode population size test で前回懸念は閉じています。

**P5b: CPPS only injection**
判定: `REQUEST_CHANGES`

- [Warning] dedup 後の実注入数と `breed_slots` の再計算が明文化されていません。設計上は「重複・不足は breed 補充」とありますが、疑似コードでは `breed_slots = pop_size - (warmstart_total + cpps_slots)` を dedup 前に確定しています。dedup で注入数が減ると、`next_gen < pop_size` になり得ます。  
  修正案: `requested_inject_slots` と `actual_injected` を分け、注入 materialize + genome_hash dedup 後に `breed_slots = pop_size - len(injected)` を再確定してください。`select_from_pareto_features(..., offspring_count=breed_slots)` / tournament もこの再確定値を使う。`test_dedup_recomputes_breed_slots_to_pop_size` を追加してください。

**全体判定**
`REQUEST_CHANGES`

実装前に直すべき点はこの 1 件だけです。dedup 後 `breed_slots` 再確定を入れれば、P3/P5a/P5b 全体を `APPROVED` にできます。