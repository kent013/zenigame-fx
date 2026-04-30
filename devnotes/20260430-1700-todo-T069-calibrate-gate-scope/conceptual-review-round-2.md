# T069 概念設計レビュー Round 2

## 0. 本レビューの前提 (C4)
- 評価対象は、提示された Round 2 概念設計本文のみです（実コード・実ファイルは未照合）。
- Round 1 の [C1]-[C4] に対する「本文上の修正有無」と「修正後の整合性」を中心に判定しました。

## 1. 結論
NEEDS_REVISION

## 2. Critical (必須修正)
- [C5] `dataset_epoch_id` での再利用遮断目標と、`freeze中は load=None -> config値 fallback` の組み合わせが概念上衝突しています。  
  Facts: §1-3 は「epoch跨ぎ再利用を fail-closed で阻止」と定義し、§3.4 は「freeze中は config 値採用」と定義。  
  Interpretation: 既存運用（T054）では calibrate が `default.yaml` の threshold を更新するため、epoch 切替後も前epoch由来 threshold が config fallback 経由で再利用され得ます。これは「history経路の遮断」はできても「実効 threshold の跨ぎ再利用」は遮断できない経路です。  
  必要な概念確定: 「epoch先頭3 Runで使う threshold は何をSSOTにするか」を明示し、前epoch値が混入しない仕様を固定してください（例: immutable seed / epoch切替時リセット契約 / yaml非更新化のいずれか）。

## 3. Warning (修正推奨)
- [W1] `applied_from_run_id is None` を count除外する設計は妥当ですが、欠落が続くと freeze が永久継続します。`HistoryRecord(applied_from_run_id)` を v2必須にするか、連続欠落時の異常ログを必須化した方が安全です。
- [W2] §7 の `calibrate_freeze.status` に `applied_from_run_id` を含めると、F5（二重append）系の監査容易性が上がります。

## 4. Round 2 観点チェック結果
- 1. [C1]-[C4] は **Round 1 指摘そのもの**はほぼ解消。  
- 2. §3.2(1軸) と §3.3(distinct count) の局所整合は取れています。  
- 3. §3.4 の SSOT 統一（load対象外）は整っています。  
- 4. §3.5 atomic cut の形は改善されています。  
- 5. Consumer Inventory §2.2 は前回より十分具体化されています。  
- 6. ログ必須 fields は概ね妥当ですが、`applied_from_run_id` 追加余地あり。  
- 7. F1-F13 に対し、上記 [C5]（config fallback 経由のepoch跨ぎ再利用）が未封鎖です。

上記 [C5] を概念で塞げば、APPROVED 判定に進めます。