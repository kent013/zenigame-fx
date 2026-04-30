# T070 詳細設計レビュー Round 2

## 0. 本レビューの前提 (C4)
- 前提1（verified）: 判定対象は提示された Round 2 詳細設計本文。
- 前提2（未検証）: 実コード・git 履歴・概念設計本文との突合は本ターンでは未実施。
- 前提3（verified）: 判定軸は「Round 1 指摘の解消状況」と「PR に落とせる実装粒度」。

## 1. 結論
[APPROVED]

## 2. Critical (PR レベルで修正必須)
- なし。

## 3. Warning (修正推奨)
- [W1] bucket の SSOT がまだ二層です。Facts: `compute_bucket_for_bar` は `BLOCK_BUCKET_RANGES_UTC` 駆動になった一方、集計側の `_BUCKETS` は固定タプル。Interpretation: 将来 bucket 定義変更時に drift 余地が残るため、`_BUCKETS = tuple(BLOCK_BUCKET_RANGES_UTC.keys())` へ寄せるとより堅牢です。
- [W2] Trade(normal/stressed) 境界は仕様で明確化されたが、型で強制はしていません。Facts: 両者とも戻り値型は `Trade`。Interpretation: 下流 caller の誤用は理論上残るため、Phase 2 で wrapper/type alias/専用 DTO のいずれかを検討すると安全です。

## 4. Suggestion (詳細で考慮)
- [S1] §7 の F1/F3/F15 の test_id 表記を、failure 名と test 名が直感的に一致する命名へ寄せると監査時の追跡コストが下がります。
- [S2] `compute_bucket_for_bar` に partition 重複検出（overlap check）を起動時検証として追加すると defense-in-depth が完成します。

## 5. 強み (継続すべき設計判断)
- Round 1 の C1-C4 は実質解消されています（SSOT駆動化、契約境界明記、caller 展開、import 補完）。
- `apply_spread_stress` の会計契約を normal/stressed で分離明記した点は、下流誤読防止に有効です。
- caller 完全展開が具体的なファイル:行ベースになり、転記漏れ監査の実効性が上がっています。
- Phase 1/2 の 13 項目整合が取れ、PR スコープ管理が明確です。

## 6. 次 Round への申し送り (NEEDS_REVISION 時のみ)
- APPROVED のため必須申し送りはありません。PR 化可能です。