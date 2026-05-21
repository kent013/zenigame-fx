**Fact**
- dedup 後に `breed_slots = pop_size - len(injected)` を再確定する設計になり、Round 4 の残 Warning は解消されています。
- `select_from_pareto_features(..., offspring_count=breed_slots)` / tournament が再確定後の値を使うため、P5a/P5b both 時も頭数 contract が閉じています。
- `test_dedup_recomputes_breed_slots_to_pop_size` で重複注入ケースも固定されています。

**判定**
- P3: `APPROVE`
- P5a: `APPROVE`
- P5b: `APPROVE`

**全体判定**
`APPROVED`

残る Critical / Warning はありません。実装時は `dedup_by_genome_hash` が各 source の上限数を超えて materialize しないこと、`effective_cpps_slots` が dedup 後の CPPS 実注入数を表すことだけ確認すれば十分です。