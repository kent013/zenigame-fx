[VERDICT] CHANGES_REQUESTED

[Critical]
1. **`§1.2` が SSOT と矛盾**しています。  
`MissionGapResult.mission_inf_gap` を `best_mission_signed_margin` の計算源と記載し、さらに `AdmissionReport` を emergency 判定入力と書いています。`§4.2`/`§5`/`§11.2`（Run全体集計 + `compute_best_mission_signed_margin`）と不一致です。

2. **`§7.2` の API 形が `§11.2` と不一致**です。  
`select_warmstart_candidates` が旧シグネチャ（`archive`, `warmstart_state` 受け取り）のままで、`§11.2` の「`build_warmstart_candidates` 後に `candidates` を渡す」構成と衝突しています。実装時に分岐が発生します。

3. **`§16` の完了判定が `§13` と矛盾**しています。  
`§13` で R1/R2/R4 を「概念で確定」とした一方、`§16` は「R1-R8 が Decision Pending」を要求しています。現状のままでは完了条件を満たせません。

[Warning]
1. `§9.2` と `§11.2` に「旧 `best_mission_signed_margin`」という自己矛盾の注記が残っています（旧名は `best_margin_inf` のはず）。
2. `§12.13` の `test_admit_warmstart_to_da_with_eviction_da_capacity_overflow_caller_responsibility` は、`§10.1` の「eviction まで 1 API で完結」と整合しません。
3. `§7.2` 本文の説明が `rank_score` 表現のままで、`ca_rank_score/da_rank_score` 分離方針とズレています。

[Suggestion]
1. `§1.2` を `§11.2` 基準で機械的に再同期（判定入力・計算源・用語）してください。  
2. `§7.2` は旧版を削除して `§11.2` の関数境界に一本化してください。  
3. `§16` は「Pending 項目の番号列挙」に変更し、R1/R2/R4 を除外した形に更新してください。

方向性はほぼ固まっていますが、上記3点の SSOT 不整合が残っているため、現時点では APPROVED にできません。