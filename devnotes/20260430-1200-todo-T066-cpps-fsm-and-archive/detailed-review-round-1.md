[VERDICT] **CHANGES_REQUESTED**

[Critical]
1. **`archive_admit` の入力一意性契約が不足**
- 事実: `candidates: Mapping[str, ArchiveCandidate]` で `key != c.genome_id` や `c.genome_id` 重複を検証していません。
- 問題: `genome_id` 一意制約・deterministic 保証と衝突します（同一 `genome_id` が別 key で入ると、`admitted_genome_ids` 重複や暗黙上書きが起こり得る）。
- 要修正: `archive_admit` 冒頭で `key == c.genome_id` と `c.genome_id` 重複なしを `ValueError` で防御。

2. **`update_archive_per_run` で `run_id` 整合性を検証していない**
- 事実: `dataset_epoch_id` 一致は検証済みですが、`c.run_id == new_run_id` は未検証です。
- 問題: 別 run の candidate 混入時に recency 判定・eviction 優先度が歪み、cross-run contamination guard の意図を壊します。
- 要修正: epoch 検証ループで `run_id` 一致も必須化。

3. **Phase 0 依存 (`c_pass_depth`) が“運用前提”止まり**
- 事実: 文書では必須前提と明記されていますが、T066 側で不成立を早期検知する仕組みが設計にありません。
- 問題: T064 follow-up 未着地でも T066 単体が進み、統合時に遅延破綻するリスクがあります。
- 要修正: DoD に「型/契約テストで `BCEvaluationResult.c_pass_depth` 存在を必須化」を追加。

[Warning]
1. **`run_history` の重複 run_id**
- `new_run_id` の再投入時に重複が蓄積し、`run_id_index` にバイアスが乗ります。再実行/リトライ時の扱いを明文化した方が安全です。

2. **`determine_archive_role` の数値健全性**
- `b_pooled_cf is not None` のみで `NaN/inf` を弾いていません。score_bypass 候補判定に有限値チェックを入れる方が堅牢です。

3. **SSOT §11.2 完全一致は本レビューでは INCONCLUSIVE**
- inline本文のみでレビューしており、§11.2 原文との差分照合は未実施です（C8）。

[Suggestion]
1. **追加テスト**
- `archive_admit` に `key/genome_id 不一致`・`candidate内重複genome_id`・`run_id不一致` の ValueError テストを追加。
- `run_history` 再実行時の重複方針（許容/除去）をテストで固定。

2. **契約を関数docstringに明記**
- `archive_admit`: 「`candidates` は `genome_id` を key とし一意」を明文化。
- `update_archive_per_run`: 「全 candidate は `new_run_id` と一致」を明文化。

3. **レビュー観点への総括**
- それ以外（FSM 3段判定、192/256制約、CA/DA lex、immutability、Phase1/2分離、selected/admitted分離）は概ね整合しています。  
