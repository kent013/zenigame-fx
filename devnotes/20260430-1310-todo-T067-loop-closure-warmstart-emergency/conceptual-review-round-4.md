[VERDICT] CHANGES_REQUESTED

[Critical]
1. **cooldown 判定の責務と API がまだ閉じていません。**  
`§7.2` では `select_warmstart_candidates` が `new_run_history_index` を使って cooldown 判定すると書かれていますが、`§11.2` の同関数シグネチャには `new_run_history_index` がありません。  
どちらかに統一が必要です。  
- 案A: `select_warmstart_candidates(..., new_run_history_index: int, ...)` を SSOT に追加  
- 案B: cooldown 判定を `build_warmstart_candidates` 側へ移し、`§7.2` の手順を修正

[Warning]
1. `§9.2` の docstring に「名称を `best_mission_signed_margin` に統一（`best_mission_signed_margin` は廃止）」という自己矛盾が残っています（廃止対象は `best_margin_inf` のはず）。
2. `§13 R5` がまだ `WarmstartCandidate.rank_score` 表現で、`ca_rank_score/da_rank_score` 分離方針とずれています。
3. `§7.4` は `epoch_age` 方針を掲げつつ `dataset_epoch_id` 比較中心の記述になっており、実装責務が読み取りづらいです（`prev_epoch_admitted_indices` という名称も `...genome_ids` と不一致）。

[Suggestion]
1. `§11.2` を唯一の実装契約として、`§7.2/§7.4/§13 R5` をその語彙に機械同期してください。  
2. `epoch filter` は「`epoch_age` を真実源にする」か「`dataset_epoch_id` を真実源にする」かを一行で固定すると、詳細設計の分岐が消えます。

主要な矛盾はかなり解消されており、残りは上記1点の SSOT 不整合が中心です。ここを揃えれば APPROVED にできます。