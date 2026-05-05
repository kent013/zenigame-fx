# Round 2 Design Review

## P1-1 (改良) 判定
APPROVE - `bars_per_day` の独自式を廃止し、既存 `compute_max_folds(...)` を起動時 fail-closed 判定に流用しているため、Round 1 の Critical 1（SSOT 不整合）は解消されています。ログ順序も `evaluating -> (不足なら例外) / (充足ならpassed)` に修正方針が明確です。

## P1-2 (改良) 判定
- Principled Parametric 判定: APPROVE / SSOT 一致・事前反証条件（`compute_max_folds(actual_n_unique_dates, new_wf_*) >= 5`）・閾値不変が揃っており、「閾値緩和でステージ飛ばし」には該当しません。

## 設計の二重基準解消 評価
APPROVE - `wf_min_safe_folds=5` を「起動前の安全床」、`wf_min_folds_required=2` を「worker内部の短絡判定」として役割分離しており、同一目的の二重基準ではなく意図的分離として妥当です（ドキュメント明記前提）。

## P4 / P2 持ち越し評価
APPROVE - cycle 2 を「1仮説（有効fold不足）+ 最小変更（起動時guard + WF窓調整）」に限定できており整合的です。P4/P2を切り離した判断は適切です。

## 全体判定
APPROVED

## 主要指摘 / 推奨事項
- merge 前にテストで `compute_max_folds` guard の fail/pass 両ケースを固定化してください（回帰防止）。
- `stage-gates.md` に 2 つの fold 関連キーの責務境界を明文化してください（将来の誤用防止）。
- `actual_n_unique_dates` の実測条件（対象期間・instrument・timezone）を Run 記録に残してください（再現性確保）。