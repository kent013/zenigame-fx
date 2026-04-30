[VERDICT] `CHANGES_REQUESTED`

[Critical]
- **`genome_id` 重複時に capacity が破綻します。**  
  `archive_admit` は `new_members = old + admitted` で重複を許容し、`archive_evict_ca/da` は `survivor_ids = {genome_id}` で残存判定しています。  
  この実装だと同一 `genome_id` が複数行ある場合、1件選んだだけで同ID全件が残り、`target_size` を超過し得ます。  
  参照: §8.2 step 7-8, §9.1 `survivor_ids`, §9.2 `survivor_ids`

- **lex 定義の SSOT が再度不一致です。**  
  §9.1/§9.2 は `genome_id` を最終 tie-break に追加した 9段/8段ですが、§1.2/§1.3 は 8段/7段のまま、§12.8 テスト名も `log_pf_clip_is_final_tiebreak` のままです。  
  どれを正とするかが文書内で一意ではありません。  
  参照: §1.2, §1.3, §9.1, §9.2, §12.8

[Warning]
- `n_mission / n_progress / n_bypass` は hard constraint 後の実 admission 数ではなく、候補選抜段階の件数を返しています。メトリクス解釈がズレる可能性があります。  
  参照: §8.2 step 9, §10 `AdmissionReport`
- §4.2 の処理説明は「run_history 先反映」修正と完全同期していません（本文の主実装は §8.6 が正）。  
  参照: §4.2, §8.6

[Suggestion]
- `ArchiveState.members` は **`genome_id` 一意制約**を明文化し、merge 時に upsert（既存置換）にしてください。  
  もしくは eviction 判定キーを `genome_id` 単体でなく member 一意キーに変更してください。
- §1.2/§1.3/§12.8 を §9.1/§9.2 に合わせて更新し、tie-break の最終段を完全一致させてください。
- `AdmissionReport` は `selected_*` と `admitted_*` を分けるか、現行カウント定義を明記してください。

修正後の方向性はかなり良いです。上記2点（重複ID容量破綻、lex SSOT不一致）が解消されれば APPROVED に上げられます。