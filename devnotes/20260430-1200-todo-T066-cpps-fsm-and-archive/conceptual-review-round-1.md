[VERDICT] `CHANGES_REQUESTED`

[Critical]
- `archive_admit` の SSOT が崩れています。§3.1 では `candidates: Mapping[int, IndividualEvaluation]` + 補助 Mapping 群、§8.2 では `Mapping[int, ArchiveMember]`、§11.2 では `Mapping[str, ArchiveMember]` です。さらに `ArchiveMember.archive_role` 型は `"mission_pass" | "progress_pass" | "score_bypass"` なのに、§8.2 では `"score_bypass_candidate"` を入力として要求しています。  
  Fact: API 定義が 3 箇所で不一致です。  
  Interpretation: 詳細設計に進む前に入力モデルを 1 つに正規化しないと、T066 の public contract が確定しません。

- admission/eviction が現行 dataclass だけでは実装不能です。§8.2 の `progress` / `bypass` 並び替えは `gate_worst_gap` を使いますが、§8.1 `ArchiveMember` に当該 field がありません。§9.1/§9.2 は `run_id_index` を使いますが、これも dataclass にありません。`update_archive_per_run` は epoch 切替テストを持つのに、§11.2 の署名に `new_dataset_epoch_id` がありません。  
  Fact: 必須 field / 引数が SSOT に未定義です。  
  Interpretation: これは実装詳細ではなく概念設計の欠落で、現状のままでは pure function 境界を固定できません。

- CA/DA への流入責務が未定義です。§8.2 では「mission/progress/score_bypass は CA、DA 振り分けは別途、Phase 1 では archive_target を呼出側で確定」とありますが、T066 の使命は CA/DA archive admission/eviction 提供です。  
  Fact: T066 自身が archive target を決めない一方で、DA へ何をどの規則で入れるかが本文にありません。  
  Interpretation: Two-Archive の中核仕様が抜けています。これでは DA が caller 依存の箱になり、synthesis §8 系の port として不十分です。

- CPPS 強制遷移の規約が本文内で不整合です。§1.1 と §5.2 は「gen=64 で 44、gen=48 は再校正」と読めますが、§4.1 の例では `force_g=44 if pop_gen=64 else 30` です。  
  Fact: fallback generation の値が 48 系なのか 30 なのか一致していません。  
  Interpretation: Round 1 のレビュー観点 1 に対して、現状は synthesis 厳密準拠を主張できません。

- deterministic contract が不足しています。§9.1/§9.2 の lex key に最終 tie-break がなく、`archive_admit` は `Mapping.values()` 起点なので入力順に影響されえます。  
  Fact: 完全同値時の順序が `genome_id` 等で固定されていません。  
  Interpretation: 「同一入力で同一出力」の DoD を掲げるなら、lex 末尾に stable key を足す必要があります。

[Warning]
- `compute_ca_da_capacities()` は `pop_size >= 2` を許容しますが、`compute_archive_capacities()` と inflow は 192/256 のみです。Phase 1 を 192/256 限定にするなら、capacity 系 public API は全て同じ制約に揃えるべきです。
- `target_inflow=0.04*pop`, `per_run_max=0.06*pop` は 192/256 の固定値表と整合していますが、丸め規約が本文にありません。`round` / `ceil` / table 固定のどれかを明記しないと、将来の pop 追加時に再解釈が入ります。
- `partition_survivors_to_ca_da()` は `sort_keys` を受け取るのに使っていません。T065 の順序保証に全面依存するなら、引数を削るか、検証用に利用するかを決めた方がよいです。
- `recency_floor=12` は §9.3 だと「保証」と書かれていますが、直近 3 run 由来メンバーが 12 未満のときは満たせません。hard constraint ではなく `best effort` か、infeasible 時の扱いを明示すべきです。
- `apply_hard_constraints()` の `compute_inflow_targets(pop_size, ...)` は未確定のままです。特に `per_run_max` 超過時、同一階層内で何を残すかが未定義です。
- `quality_floor_margin` は DA eviction #5 としては理解できますが、§8.4 では margin_inf p70 threshold と混線しています。別概念なので名前と責務を分離した方が安全です。

[Suggestion]
- 入力を 2 層に分けると収まりが良いです。  
  1. `ArchiveCandidate`: admission 前の候補。`gate_worst_gap`, provisional role, novelty/diversity, margin_inf, pattern/family, epoch など全て持つ。  
  2. `ArchiveMember`: archive 登録後の不変メタデータ。`archive_role` は `"mission_pass" | "progress_pass" | "score_bypass"` のみ。
- `update_archive_per_run()` には少なくとも `new_dataset_epoch_id` を入れてください。epoch 切替 reset を top-level API で扱えないと、T058 の汚染防止契約が宙に浮きます。
- eviction key の末尾に `genome_id` を入れてください。`run_id_index` も caller 注入ではなく `run_history` から pure に解ける形に寄せた方がよいです。
- `not_score_bypass` は保存値ではなく導出値にした方が不整合を避けられます。
- `c_pass_depth` は `INCONCLUSIVE` です。T064 に無ければ、T066 詳細設計より先に T064 側 SSOT 改訂を入れるべきです。

総評として、設計の方向性自体は synthesis §7/§8 と整合する骨格になっていますが、現時点では「public API と入力モデルの不一致」「DA 流入責務の欠落」「determinism 不足」が大きく、APPROVED には上げられません。Round 2 ではまず `ArchiveCandidate / ArchiveMember / ArchiveState / update_archive_per_run` の SSOT を 1 枚に潰し込み、その後に CA/DA target ルールを固定するのが先です。