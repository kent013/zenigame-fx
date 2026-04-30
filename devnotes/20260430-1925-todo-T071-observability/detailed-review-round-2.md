# T071 詳細設計レビュー Round 2

## 0. 本レビューの前提 (C4)
- 提示された Round 2 詳細設計本文のみをレビュー対象とし、コマンド実行・実ファイル確認は行っていない。
- 概念設計 Round 2 APPROVED は前提として扱うが、T064-T068 の実 dataclass 定義は未提示のため field 妥当性は本文内整合で判定する。
- Falsification-first として、PR 化を阻害する未閉塞経路を優先して確認した。
- Fact / Interpretation を分離して記載する。

## 1. 結論
[NEEDS_REVISION]

Round 1 の主要論点はかなり改善されていますが、**PR ブロッカーがまだ残っています**。特に `status` の runtime invariant、Hard dependency field 契約、DoD の SSOT 不整合、F1-F15 の test_id 整合に未解消があります。

## 2. Critical (PR レベルで修正必須)
- [C1] Fact: §1.1 は `11 dataclass + 9 関数` に更新済みだが、§8.1 DoD はまだ `9 dataclass + 8 関数` のまま。 Interpretation: Round 1 [C1] は完全解消しておらず、PR checklist の達成判定が再び曖昧になる。
- [C2] Fact: `ABDivergenceMetric` / `ArchiveChurnMetric` / `SessionEntropyMetric` は `Literal` 型に依存しており、runtime で `status=None` や未知 status が渡された場合に `else: raise ValueError` がない。 Interpretation: 「None 経路完全排除」は Python 実行時には未達で、status field 方式の根幹がまだ閉じていない。
- [C3] Fact: `SessionEntropyMetric` の `insufficient_window` / `empty_archive` は `shannon_entropy=0` は強制するが、`relative_entropy=0` と `n_unique_patterns=0` を強制していない。 Interpretation: sentinel invariant が完全ではなく、caller が status を見ても値の意味を安全に解釈できない。
- [C4] Fact: §2 の T067 grep DoD は `n_filtered_by_epoch` を確認する一方、§4.6 実装擬似コードは `warmstart_report.per_source_run_violations` を読む。§2 の T068 grep DoD も `all_failed` を確認する一方、実装は `run_aborted` / `per_stage_summaries` / `fingerprint_dedup_top_n` を読む。 Interpretation: Hard dependency field 契約と実際の参照 field が同期しておらず、T065-T068 field 伝搬漏れを防げない。
- [C5] Fact: §11 open issues に `ArchiveMember.session_pass_pattern field の値 (= "111" / "1,1,0" / 8 値整数 等) を T064 / T066 で確認` が残っている。 Interpretation: §3.1 / §4.5 で 3 bit string 固定したはずの入力 contract が、open issue で未確定扱いに戻っているため Round 1 [C4] は完全解消していない。
- [C6] Fact: §6 に `test_F3c_clamp_on_numerical_overshoot` があるが、§5 のテスト本文に存在しない。§6 の F11 は `test_F11_extract_functions_use_expected_fields` と書くが、§5 は3本の個別テスト名。§5 では `test_F10a_*` が2つあり test_id が重複している。 Interpretation: F1-F15 の 1:1 対応はまだ監査可能な状態ではない。
- [C7] Fact: §5 の `test_F14_empty_run_id_raises` は `RunObservabilityReport` の `run_id` invariant テストであり、§6 の F14「連続乖離 Run カウント保持責務」と対応していない。 Interpretation: F14 の failure mode が unit / integration のどちらで検証されるのか不明で、Round 1 [C5] の残存。

## 3. Warning (修正推奨)
- [W1] Fact: `QForceRecommendation.__post_init__` は `reason` / `delta` / `clamped_at_max` / `clamped_at_min` の整合を検証しない。 Interpretation: pure function 経由なら安全だが、dataclass 直生成時に矛盾した report が作れる。
- [W2] Fact: `BypassRatioMetric` は `n_total_admissions == sum(n_admitted_by_role.values())`、負数 count、role count と ratio の整合を検証しない。 Interpretation: 会計 metric としては不正状態を保持できる。
- [W3] Fact: `FeasibleRatioMetric` は `n_feasible_individuals` / `n_total_individuals` の非負制約を持たない。 Interpretation: 観測 metric として負数 population を許容してしまう。
- [W4] Fact: pseudo import に `field` と `FailureSummary` があるが本文上は未使用。 Interpretation: DoD の `ruff / pyright clean` と衝突する可能性が高い。
- [W5] Fact: `SESSION_PATTERN_REGEX` は文字列定数で、`compute_session_entropy` 内で `import re` して `re.match` している。 Interpretation: 正規表現 contract としては動くが、PR 実装では module top-level `re.compile` + `fullmatch` の方が意図が明確。

## 4. Suggestion (詳細で考慮)
- [S1] status enum 系 dataclass は全て最後に `else: raise ValueError(f"unknown status: {self.status!r}")` を入れる。
- [S2] §2 Hard dependency は「grep 対象 field」と「§4 で実際に読む field」を完全一致させる。
- [S3] §5 と §6 の test_id は機械的に照合できる命名にする。例: F11 は `test_F11a_*` / `test_F11b_*` / `test_F11c_*` に統一。
- [S4] §11 から `session_pass_pattern` 未確定 issue を削除するか、T064/T066 側の contract 確認を T071 PR の hard dependency に昇格する。
- [S5] §8.1 DoD の dataclass / 関数数を §1.1 と同じ `11 dataclass + 9 関数` に修正する。

## 5. 強み (継続すべき設計判断)
- `AB_MIN_ACTIONABLE_PAIRS=10` により、少なくとも n<10 の相関 claim / q_force action 経路は閉じられている。
- `session_pass_pattern` を 3 bit string に固定する方向性は、entropy の 8 パターン前提と整合している。
- F15 を F5 から分離し、delta 適用順序と clamp 順序を別 failure mode として扱った点は改善。
- Phase 1 を `src/observability + tests + docs` に限定し、`run_ga.py` 配線を Phase 2 に送る切り分けは妥当。
- synthesis 確定値と T071 仮説値の定数分離は、後続の再校正で因果ループを切らない設計になっている。

## 6. 次 Round への申し送り
- §8.1 の `9 dataclass + 8 関数` を `11 dataclass + 9 関数` に修正する。
- 3 status metric に未知 status / `None` を拒否する `else raise` を追加する。
- `SessionEntropyMetric` の sentinel invariant に `relative_entropy=0` と `n_unique_patterns=0` を追加する。
- §2 の field grep DoD を §4.6 の実参照 field と完全同期する。
- §5 / §6 の F1-F15 test_id を再照合し、欠番・重複・別概念テストを解消する。
- `session_pass_pattern` の open issue を削除するか、T064/T066 確認を hard dependency に昇格する。

この Round 2 は **方向性は APPROVED 相当**ですが、本文のままでは **PR 化 APPROVED にはまだ届きません**。修正量は小さいため、上記 Critical を反映すれば次 Round で承認可能です。