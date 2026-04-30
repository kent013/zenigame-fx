[VERDICT] CHANGES_REQUESTED

[Critical]
1. **SSOT の内部不整合が残っています。**  
`§4.1/§4.2` がまだ旧フロー（`emergency_state.is_active`、`AdmissionReport` 起点、`compute_best_margin_inf`）のままで、`§5/§11.2` の新SSOT（`is_boost_applicable`、Run全体集計、`compute_best_mission_signed_margin`）と矛盾しています。  
この状態だと実装者がどちらを採用すべきか判断不能です。

2. **指標名の統一が文書全体で未完了です。**  
`§1`, `§1.2`, `§17` に `best_margin_inf` 記述が残り、`§9.2` の「`best_mission_signed_margin` に統一」と衝突しています。  
特に `§1.2` は `mission_inf_gap` を emergency 判定計算源と読めるため、Round 1 [C3] の再発リスクがあります。

3. **R7 方針と擬似コードが矛盾しています。**  
`§13 R7` で「緩和倍率は詳細設計で確定」としつつ、`§7.3` で `constraints[key] = constraints[key] * 2` を固定記述しています。  
概念設計段階で倍率を確定しないなら、擬似コードから固定値を外す必要があります。

4. **Decision Pending の扱いが自己矛盾です。**  
冒頭マトリクスでは R1/R2/R4 を「概念設計で吸収済み」としながら、`§13` では依然 Pending 扱いで「詳細設計で確定」と書かれています。  
このままだと APPROVED 条件（設計凍結）が満たせません。

[Warning]
1. `§11.1 dataclass 一覧` が旧説明のままです（`EmergencyState` の `boost_consumed_run_id`、`WarmstartCandidate` の `ca_rank_score/da_rank_score/epoch_age` が反映不足）。
2. `§12` のテスト名が旧命名を引きずっています（`best_margin_inf` 系、`admit_warmstart_to_da` 系）。SSOT テストとしては名称ドリフトが大きいです。
3. `§6.2 compute_warmstart_counts` の型注釈が `tuple[int, int]` になっており、実際の返却（`total, ca, da`）と不一致です。

[Suggestion]
1. **最終整合パス**として、「旧語彙禁止リスト」を作って全文置換してください。  
対象例: `best_margin_inf`, `compute_best_margin_inf`, `emergency_state.is_active`, `admit_warmstart_to_da`, `AdmissionReport` 起点判定。
2. `§4` を `§11.2` だけを参照元にして書き直し、「Run開始時/終了時の唯一の判定入力」を1本化してください。
3. R1/R2/R4 は「確定済み」か「Pending」かを一本化し、完了判定 `§16` と同じ状態にそろえてください。

Round 1 の主要指摘に対する設計方向は正しいです。  
ただし現時点は文書内SSOTが閉じていないため、**APPROVED にはまだ早い**です。