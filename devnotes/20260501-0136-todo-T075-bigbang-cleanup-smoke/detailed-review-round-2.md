## Verdict
NEEDS_REVISION

## 前提 (C4)
- 提示された Round 2 改訂本文のみをレビュー対象とした。
- T075 の SSOT は「Phase 1 は純ライブラリ `src/alpha_factory/smoke.py` + 単体テストのみ」と解釈した。
- Round 1 指摘の修正有無を優先し、Round 2 で新規に入ったスコープ逸脱を重点的に反証した。
- 統計・因果 claim は本レビュー範囲外のため、C7/C8 は該当なし。

## Critical
- [C1] Fact: Round D1 [W3]/[W4] 対応として `docs/runbook/big-bang-cleanup-smoke.md`、PR template、CI meta check が詳細設計に入っている。Interpretation: これは「Phase 1 library + 単体テストのみ」という Round 4 SSOT と衝突する。Phase 1 では runbook/PR template/CI ファイルを実装対象にせず、PR description 上の手動 merge 条件または Phase 2 タスクへ分離する必要がある。
- [C2] Fact: `F40b_pr_template_round22_blockers` は `tests/alpha_factory/test_smoke.py` の単体テストとしては現在の PR description を検証できない。Interpretation: unit test に置くと検証対象が fixture 化されて実運用を保証せず、CI meta check に置くと Phase 1 の純ライブラリ境界を越える。詳細設計上の test_id と検証レイヤを分離すべき。

## Warning
- [W1] Fact: `DUAL_PATH_ENFORCE_ALLOWLIST` の `/**/*` pattern は実装 API により直下ファイルを含むかが揺れる。Interpretation: `PurePosixPath` 正規化 + `docs/historical/**` / `devnotes/**` / `tests/**` のような pattern 仕様を固定しないと F38d が環境依存になる。
- [W2] Fact: `tests/** が allowlist、tests-prod/** が対象` という例は、現行 `DUAL_PATH_ENFORCE_TARGETS` では `tests-prod/**` がどの target glob にも入らない。Interpretation: ここは「対象」ではなく「allowlist されない」と書くか、全体スキャン仕様を別途定義する必要がある。
- [W3] Fact: `CleanupCategorySlug` 5値で synthesis §12.1/§12.2 の全 deletion target を分類できるかは、対応表が本文に無い限り検証不能。Interpretation: `target -> category -> change_group_id` の表を詳細設計に追加すれば閉じる。
- [W4] Fact: `F26c` を grep DoD とすると、docstring/comment/テスト名の `auto_proceed` 等で false positive になり得る。Interpretation: raw grep ではなく AST で `FunctionDef.name` / public method / call target のみを検査する仕様にすべき。
- [W5] Fact: conformance fixture の `ValueError message` 文言固定は、実装者に過剰な文字列結合制約を与える。Interpretation: 固定するなら error code または stable prefix に限定し、metric一覧 dump は補助情報に留める方が安全。

## Suggestion
- [S1] `docs/runbook` 追加は Phase 2 正式タスク、Phase 1 では `ReleaseActionRecommendation` docstring と PR description 記載に限定する。
- [S2] `F40b` は `tests/alpha_factory/test_smoke.py` から外し、将来の CI meta check 仕様として `DoD8` または Phase 2 に移す。
- [S3] `DUAL_PATH_ENFORCE_TARGETS` に path normalization rule を追加する: repository-root relative、POSIX separator、symlink follow なし。
- [S4] `InconclusiveReason.message` は動的値を含めない、または同一 `source/reason_code` 内で最大件数を cap する規約を入れると dedup が安定する。
- [S5] `F26b` は負ケースだけでなく、一致ケースで construct 可能な positive case も明示する。

## Round D1 から残置の最終確認
- Round D1 [C1]: `SmokeOutcomeClassification.__post_init__` invariant と F26b 追加で実質解消。
- Round D1 [C2]: 4経路表化で大枠解消。ただし glob semantics / path normalization / `tests-prod` 境界説明が未固定。
- Round D1 [W1]: `CleanupCategorySlug` + regex 二重化で方向性は解消。対象 inventory 対応表があれば完了。
- Round D1 [W2]/[S3]: dedup 3軸化で解消。message の安定性だけ補足推奨。
- Round D1 [W3]/[W4]/[S5]: 方針は良いが、Phase 1 純ライブラリ制約との衝突が残る。

## test_id 1:1 ギャップ
- `F26b`: positive/negative の両方を明記すると invariant test として完結する。
- `F26c`: raw grep ではなく AST 対象ノードを test 名に反映する必要あり。
- `F38d`: `tests/foo.py`、`tests-prod/foo.py`、`devnotes/a.md`、`docs/historical/a.md`、`docs/runbook/a.md` の境界 case を明示する必要あり。
- `F40b`: unit test ではなく PR/CI meta layer の検証。Phase 1 test plan からは外すべき。
- `F39-F40`: schema/runs count は OK だが、Phase 1 で runbook/CI ファイル存在を要求しないことを明記する必要あり。

## 学術文献 (任意)
- なし。

## 総評
Round D1 の技術的な穴はかなり閉じています。特に severity invariant、dual-path enforce の表化、category Literal 化、dedup 3軸化は Round 1 指摘に対して妥当な修正です。

ただし、Round 2 で runbook/PR template/CI meta check が Phase 1 実装範囲に混入しており、ここが Round 4 SSOT の「純ライブラリ + 単体テストのみ」と衝突しています。Phase 1 ではそれらを PR description 上の手動条件または Phase 2 予約に落とせば、次回は APPROVED 可能です。