# T069 詳細設計レビュー Round 1

## 0. 本レビューの前提 (C4)
- 反証起点 (C9): 「この設計はそのまま PR 化できない経路がある」という仮説から確認した。
- Verified: ユーザー制約に従い、提示テキストのみを対象にレビューした（実ファイル・git 履歴・追加 docs は未照合）。
- Verified: 判定軸は「Phase 1 を破壊的変更なしで実装可能な粒度か」。
- INCONCLUSIVE: 概念設計本文との完全一致は、概念設計ファイル実読がないため最終確証は未取得。

## 1. 結論
**NEEDS_REVISION**

## 2. Critical (PR レベルで修正必須)
- [C1] `test_calibrate_freeze.py` 擬似コードが未完了。Fact: §5.1 `TestDecideWithFreeze._make_sample` が `...` のまま。Interpretation: このままでは実装者が即 PR 化できず、テスト仕様が未確定。
- [C2] `FreezeStatus` とログ契約のフィールド不整合。Fact: §8.2 が `fs.dataset_epoch_id_used` を参照するが、§3.1 `FreezeStatus` に当該 field がない。Interpretation: Phase 2 配線時に実装ブレまたは実行時エラーを誘発する。
- [C3] schema version 記述が自己矛盾。Fact: §5.1 `_make_record` は `schema_version=1` 固定だが同ブロックで「T058 v2 必須 field」を前提化。Interpretation: F15 系の防御を誤って通してしまう false-negative テストになる。
- [C4] Phase 2 申し送りの監査可能性不足。Fact: DoD は「申し送り12項目」を要求する一方、§12 は #7-13 のみ。Interpretation: 受け渡し要件の欠落有無をレビュー不能。
- [C5] 「caller signature 完全展開」の根拠不足。Fact: §2 は主要 caller を列挙するが、`skip_frozen` consumer 全体（report 系含む）のファイル単位配線が明示されていない。Interpretation: 転記漏れ再発リスクが残る。

## 3. Warning (修正推奨)
- [W1] SSOT 参照節の表記揺れ。Fact: 冒頭で「API + 擬似コードは §5/§6」とあるが実体は §4。Interpretation: 設計レビュー時の参照ミスを誘発。
- [W2] `evaluate_freeze_status` の run_id validation が `None` のみ対象。Fact: 空文字 run_id の扱い未定義。Interpretation: 異常データ時に distinct count が歪む可能性。
- [W3] `DriftAnalysis` field 追加の backward-compat が「影響なし」と断定的。Fact: 直接コンストラクト箇所は「grep で確認予定」と未確定。Interpretation: 断定ではなく INCONCLUSIVE 扱いが妥当。

## 4. Suggestion (詳細で考慮)
- [S1] §2 に「consumer inventory」を追加し、`DecisionLabel=skip_frozen` の受理点を `config→model→writer→reader→report` で1行ずつ固定化する。
- [S2] F1-F15 を `test_id` と 1:1 対応させ、未実装は明示的に `Phase2-IT-*` と命名して追跡可能にする。
- [S3] `FreezeStatus` を拡張しない方針なら、§8.2 の `dataset_epoch_id` は「caller変数を使う」擬似コードに修正して型不整合を消す。

## 5. 強み (継続すべき設計判断)
- scope key を `dataset_epoch_id` 1軸に固定し、distinct run count を採用している点は妥当。
- `decide()` 非破壊で `decide_with_freeze()` を分離した責務設計は安全。
- F1-F15 を failure mode として明示し、F4/F7/F14 を Phase 2 integration に切り分けた方針はよい。
- `threshold_delta_abs_max <= 0.03` の fail-closed 契約を `CalibrateConfig` に置く判断は一貫している。

## 6. 次 Round への申し送り (NEEDS_REVISION 時のみ)
- `_make_sample` を具体実装し、`DecideWithFreeze` テストを実行可能な粒度へ確定する。
- §8.2 ログ契約を `FreezeStatus` 定義と整合させる（field 追加 or 参照修正）。
- `schema_version` と T058 v2 前提の整合を明文化し、fixture を v2 契約準拠に更新する。
- Phase 2 申し送り「12項目」を本文内で 1-12 完全列挙し、DoD と一致させる。
- `skip_frozen` の consumer 配線表を追加し、転記漏れ防止の 4 段接続を監査可能にする。