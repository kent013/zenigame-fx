[VERDICT] `CHANGES_REQUESTED`

[Critical]
- **recency が実装順序上で壊れています**。`archive_admit` 内で eviction を実行した後に `update_archive_per_run` で `run_history` を追加しており、当 run 新規流入個体は eviction 時に `run_history` 未登録扱いになります。結果として「最新なのに最古扱い」で不当に落ちます。  
  参照: §8.2 step 8-9, §8.6, §9.1-§9.2

- **ArchiveMember 定義と eviction key が不整合です**。`_ca_eviction_sort_key` / `_da_eviction_sort_key` は `m.mission_pass`, `m.progress_pass` を参照していますが、§8.1.2 の `ArchiveMember` には当該 field がありません（`archive_role` のみ）。このままでは成立しません。  
  参照: §8.1.2, §9.1, §9.2

- **SSOT がまだ分裂しています**。Round 2 で統一と記載されていますが、§3.1 と §7 は旧 API（`sort_keys` あり、`Mapping[int, IndividualEvaluation]`）のまま残っています。  
  参照: §3.1, §7, §11.2（相互不一致）

- **AdmissionReport の契約が不整合です**。本文では `recency_floor_unmet`, `dataset_epoch_reset` を必須報告項目として使っていますが、§10 dataclass 定義にその field がありません。  
  参照: §4.2, §8.2, §8.6, §10

- **W1 解消が未完了です**。`compute_ca_da_capacities` が依然 `pop_size < 2` 判定で、192/256 限定契約と矛盾します。  
  参照: §5.3, §11.2

[Warning]
- `evicted_genome_ids` の算出が「旧 archive から消えたもののみ」になっており、同 run で admit された後に即 evict された個体は報告漏れします。観測と監査の一貫性が落ちます。  
  参照: §8.2 step 9

- epoch reset 時に `candidates[*].dataset_epoch_id` と `new_dataset_epoch_id` の一致検証がなく、入力汚染を通す余地があります。  
  参照: §8.1.1, §8.6

[Suggestion]
- `update_archive_per_run` で先に `new_run_id` を `run_history` へ反映した state を作り、その state を `archive_admit`/evict に渡してください（recency 評価の一貫化）。
- `ArchiveMember` に `mission_pass: bool` / `progress_pass: bool` を保持するか、eviction key 側を `archive_role` から完全導出に統一してください。
- §3.1/§7 を §11.2 SSOT に合わせて削除・修正し、旧シグネチャを文書上から完全消去してください。
- `compute_ca_da_capacities` も 192/256 のみ `ValueError` に統一してください。

Round 1 での主要改善は確かに進んでいますが、上記 5 点は実装段階で破綻するため、現時点では APPROVED に上げられません。