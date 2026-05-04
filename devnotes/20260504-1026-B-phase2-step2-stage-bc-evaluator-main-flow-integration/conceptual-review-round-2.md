**全体判定**  
`CHANGES_REQUESTED`

Round 2 は Round 1 の主要論点をかなり正しく反映しています。特に `案B` 採用、`step 2.1` scope 化、`Phase 2 切替コミット` 呼称の分離、identifier 契約、default off、専用検証 run 化は妥当です。ただし、`BCEvaluationInput` を「追加 full backtest 禁止」で構築する前提が、stage_bc_evaluator 新 API の意味論と衝突する可能性が残っています。ここは採用前に修正が必要です。

**C9 反証**
**Fact**
- 新 API は per-fold rolling-origin pooled OOS、Stage C-lite、stress、cross-pair shadow を含む評価設計です。
- Round 2 では builder 制約として「既存成果物再利用のみ」「追加 full backtest 禁止」「shadow_pairs 参照共有 / lazy materialization」を置いています。
- 旧 API の `StageResult` は新 API の `BCEvaluationInput` と同じ情報構造ではありません。
- step 1.8 の sanitize 経路では `_shadow_sidecar_inputs` を空にする設計が維持されています。

**Interpretation**
- 旧 API の集計済み `StageResult` から、新 API が必要とする per-fold / per-window / per-pair の意味論的に正しい `PairBacktestBundle` を復元できる保証がありません。
- 「追加 full backtest 禁止」を絶対制約にすると、構築できる `BCEvaluationInput` が形式的には正しくても、stage_bc_evaluator の確定式を観測しているとは言えないリスクがあります。
- よって、Round 2 の最大欠陥は scope ではなく、`shadow 観測の意味論的妥当性` です。

**Critical**
- [Critical] `BCEvaluationInput` の構築方針が、stage_bc_evaluator 新 API の評価意味論を満たすか未証明です。修正提案: `2.1` の前半に `2.1a input feasibility` を明示し、各 input field について `既存成果物から意味論を保って構築可能 / 不可能 / skip` を判定してください。
- [Critical] 「追加 full backtest 禁止」はメモリ対策として妥当ですが、絶対化すると shadow 結果が偽観測になる可能性があります。修正提案: 禁止対象を `uncontrolled full backtest` に限定し、必要なら専用検証 run 内で `bounded recomputation` を許可する設計にしてください。
- [Critical] builder skip が多発した場合、`n>=30` を満たしても有効観測数が不足します。修正提案: `shadow_skipped=False の有効観測 n>=30`、かつ `skip_rate` 上限を `2.2 exit criteria` に追加してください。
- [Critical] `stage_c_lite_periods / stage_c_period` を既存 `stage_c_holdout_days` から derive する方針は、T064 の確定式と一致する根拠が不足しています。修正提案: derive rule を明文化し、T064 設計の window 定義と1対1対応することを acceptance に入れてください。

**Warning**
- [Warning] `mission_pass_diff` が旧 `c_passed` と新 `mission_pass` の単純比較なら、評価母集団と判定式が異なるため解釈が危険です。修正提案: diff は `descriptive_diff` と明記し、同等性ではなく乖離パターン分析に限定してください。
- [Warning] `peak_rss_delta` / `wall_clock_delta` は per-genome event schema に入れるより run-level metric です。修正提案: `stage_bc_evaluator.shadow` は genome-level、RSS/wall-clock は `stage_bc_evaluator.shadow_run_summary` に分離してください。
- [Warning] `shadow_enabled=True でも main flow 経路は不変` は fitness 不変を保証しても、wall-clock timeout や log I/O による間接影響は残ります。修正提案: 専用検証 run のみで有効化し、通常 run への有効化は 2.2 以降に限定してください。
- [Warning] `genome_hash` の SSOT が「既存 digest」とだけ書かれており、どの digest か曖昧です。修正提案: genome serialization source と hash algorithm を schema v1 に固定してください。

**Suggestion**
- `2.1 success criteria` と `2.2 exit criteria` の分離は良いです。さらに `2.1a feasibility`、`2.1b shadow logging` に分けると実装レビューしやすくなります。
- `BCEvaluationInput` の各 field について、`source`, `copy/reference`, `semantic validity`, `skip reason` の対応表を追加してください。
- `failure_handling.evaluate_bc_safe` 再利用は妥当ですが、degraded result を通常の shadow success と混同しないよう `bc_summary.status = ok/degraded/failed/skipped` を追加してください。

**方向性判断**
採用案は引き続き `案B` で妥当です。ただし Round 2 のまま `APPROVED` にはできません。`step 2.1 shadow integration` の前に、または内部の最初の小ステップとして、`BCEvaluationInput` が新 API の意味論を壊さず構築できることを明示検証する必要があります。

結論: `CHANGES_REQUESTED`。修正範囲は限定的で、設計全体の方向性は維持できます。