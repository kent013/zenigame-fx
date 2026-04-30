# T071 詳細設計レビュー Round 3

## 0. 本レビューの前提 (C4)
- 提示された Round 3 詳細設計本文のみをレビュー対象とし、コマンド実行・実ファイル確認は行っていない。
- T065-T068 / T064 の実 dataclass 定義は未確認のため、本文内 contract と hard dependency 設計の整合性で判定した。
- Round 2 Critical 7件の解消可否を Falsification-first で確認した。

## 1. 結論
[APPROVED]

Round 2 の PR ブロッカーは実質的に解消されています。T071 詳細設計は **Phase 1 PR に落とせる粒度** に到達しています。

## 2. Critical (PR レベルで修正必須)
- なし。

## 3. Warning (修正推奨)
- [W1] Fact: §5 に `test_F10a_*` が2本残っており、§6 には片方のみ記載。 Interpretation: blocker ではないが、監査性のため片方を `test_F10d_*` などに rename するとよい。
- [W2] Fact: F14 は「連続乖離 Run カウント保持責務」だが、Phase 1 test は `RunObservabilityReport` invariant に寄っている。 Interpretation: Phase 2 IT で state file を検証する設計なら許容。ただし Phase 1 では `consecutive_divergent_runs` 負数 invariant test を足すとより強い。
- [W3] Fact: §3.1 に `field` / `FailureSummary` の未使用 import が残る。 Interpretation: 実装時は `ruff / pyright clean` のため削除が必要。
- [W4] Fact: §2 grep の `stage` は広くヒットしやすい。 Interpretation: PR review では grep だけでなく extract test と型 import 成功を併用する前提で運用するのが安全。

## 4. Suggestion (詳細で考慮)
- [S1] `QForceRecommendation` に `reason` / `delta` / `clamped_at_*` の整合 invariant を足すと、report の自己矛盾をさらに防げる。
- [S2] `BypassRatioMetric` と `InflowConsistencyMetric` に count 非負・合計整合 invariant を足すと、会計 metric としてより堅い。
- [S3] `SESSION_PATTERN_REGEX` は実装時に `re.compile(...).fullmatch()` にすると contract 意図が明確。
- [S4] F14 Phase 2 IT では「state file の連続乖離 count が run をまたいで増減すること」を明示テストにする。

## 5. 強み (継続すべき設計判断)
- 3 status metric に `else: raise` が入り、`Literal` 違反 / `None` status の runtime 経路が閉じた。
- `SessionEntropyMetric` の sentinel invariant が `relative_entropy` / `n_unique_patterns` まで拡張され、status 契約が明確になった。
- §2 grep DoD が §4 実参照 field に同期され、T065-T068 伝搬漏れの検出力が上がった。
- `session_pass_pattern` を hard dependency に昇格したことで、上流 contract 未確定のまま T071 が merge される経路を塞げている。
- Phase 1 / Phase 2 の切り分けは維持されており、`run_ga.py` を触らず library PR として実装可能。

## 6. 最終判定
T071 詳細設計 Round 3 は **APPROVED**。  
残る指摘は実装時 cleanup / test naming の改善レベルであり、PR ブロッカーではありません。