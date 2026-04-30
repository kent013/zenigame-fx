# T069 詳細設計レビュー Round 2

## 0. 本レビューの前提 (C4)
- 反証起点 (C9): 「Round 1 指摘が全解消されていない経路」を先に探索した。
- Verified: レビュー対象は提示された Round 2 改訂本文のみ。
- Verified: 判定軸は「この設計だけで Phase 1 PR を安全に実装できるか」。
- INCONCLUSIVE: 実コード・実ファイル未照合のため、呼び出し網羅性の最終確証は設計本文記載に依存。

## 1. 結論
**NEEDS_REVISION**

## 2. Critical (PR レベルで修正必須)
- [C1] 「F1-F15 を test_id と 1:1 対応」の要件が未達。  
  Fact: §9 で F1/F3 が同一 `test_other_epoch_records_excluded` を共有、F13 は test_id なし。  
  Interpretation: 監査要件として宣言した「1:1 対応」を満たしておらず、トレーサビリティ基準が崩れる。
- [C2] T058 依存条件が実装分岐として残っている。  
  Fact: §5.1 `_make_record` docstring に「T058未先行なら schema_version=1 一時対応も可」とある。  
  Interpretation: PR cut 条件が単一化されておらず、再現性のある実装方針として未確定。

## 3. Warning (修正推奨)
- [W1] `invalid_run_id` ログの項目名と実態が不一致。  
  Fact: `n_v2_records_with_null_run_id` に空文字も含めてカウント。  
  Interpretation: 運用時の異常分類が曖昧になる。
- [W2] consumer inventory の report 段が抽象的。  
  Fact: §2.2 段6で具体ファイル/関数が未特定。  
  Interpretation: Phase 2 での転記漏れ監査が弱い。
- [W3] `_make_sample` の `mode="last_k_generations"` が既存 `AggregatedSample` 契約と一致する保証が本文上で不足。  
  Interpretation: 実装時に型/バリデーション不整合のリスクが残る。

## 4. Suggestion (詳細で考慮)
- [S1] §9 を厳密 1:1 に修正し、F13 も `Phase1-PR-CHECK-F13` など監査IDを付与する。
- [S2] §5.1 の T058 依存は「必須前提」に固定し、代替分岐文言を削除して PR 条件を一本化する。
- [S3] §2.2 段6に report 経路の具体ファイル/関数名を追記して 6 段接続を完全固定化する。

## 5. 強み (継続すべき設計判断)
- Round 1 の主要 Critical（`_make_sample` 未完、ログ契約不整合、12項目欠落、consumer inventory不足）は実質的に大きく改善。
- `decide_with_freeze` で `decide()` 非破壊を維持した責務分離は妥当。
- `threshold_delta_abs_max <= 0.03` の fail-closed 化と yaml 同時更新方針は一貫している。
- `skip_frozen` を load 対象外に据えた設計判断は概念方針と整合的。

## 6. 次 Round への申し送り (NEEDS_REVISION 時のみ)
- §9 の F1-F15 を厳密 1:1 監査IDへ修正（共有IDと未割当を解消）。
- §5.1 の T058 依存を単一方針に固定（「一時的にv1可」文言を削除）。
- §2.2 段6 report 経路を具体ファイル/関数まで明記。
- ログ項目名を `null_or_empty_run_id` 相当へ改名するか、空文字を別カウンタに分離。