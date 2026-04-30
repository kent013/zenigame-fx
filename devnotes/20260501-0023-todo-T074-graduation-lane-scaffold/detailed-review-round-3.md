## Verdict
NEEDS_REVISION

## 前提 (C4)
- レビュー対象は提示された Round 3 本文のみ。実ファイル確認はしていない。`Verified`
- `recent_mission_pass_epoch_ids` は実測 diagnostic field として扱う。`Verified`
- `GraduationTriggerEvaluation` は `_make_trigger` 経由だけでなく dataclass 直接構築でも invariant を守る方針。`Verified`
- AST grep DoD は production code の混入検出が目的で、docstring/comment は除外する。`Verified`

## Critical
- なし。Round D1 の `recent_epochs_required >= 1`、Round D2 の partial pass 保持はいずれも方向性 OK。

## Warning
- [W1] `recent_mission_pass_epoch_ids` と `n_distinct_epochs` の cross-field invariant がまだ不足しています。`ready` で `recent_epochs_required=5, n_distinct_epochs=3, len(ids)=5` が直接構築で通るなら不正です。少なくとも `len(set(recent_mission_pass_epoch_ids)) == len(recent_mission_pass_epoch_ids)` と `n_distinct_epochs >= len(recent_mission_pass_epoch_ids)`、`ready` では結果的に `n_distinct_epochs >= recent_epochs_required` を要求すべきです。
- [W2] `tier1_event` の扱い説明が現仕様とズレています。`tier1` / `tier_1` を exact name にしたなら `tier1_event` は reject されません。reject したいなら regex/substring、許容したいなら「exact のため許容」と明記してください。
- [W3] AST grep の ImportFrom 抜け道を塞ぐ記述が必要です。`from . import archive` は `node.module is None` で alias 側に `archive` が出るため、`ImportFrom` でも `alias.name` を検査対象にしてください。
- [W4] `DST` substring の case-sensitivity を明記してください。例の `dst_aware_xxx` は case-sensitive なら検出されず、case-insensitive なら検出されます。

## Suggestion
- [S1] Phase 2 adapter contract は 3案併記でよいですが、推奨順を `A snapshot DTO > B transaction wrapper > C caller完結` と明記すると Phase 2 PR の判断が安定します。案 C は production 推奨不可でよいです。
- [S2] `synthesis_schema_version >= 22` は妥当です。既存文書に field が無い場合に備え、「Round 22 改訂 PR は `synthesis_schema_version: 22` を明示追加する」を申し送りに入れてください。
- [S3] F22f は `len=0` と `len=required-1` の両端を parametrize で分けるのがよいです。F22g は `len=required` と可能なら `len>required` も含めると境界が閉じます。
- [S4] F22e の 16ケースは production constants 化不要です。test 内の valid baseline fixture + override matrix が一番読みやすいです。

## Round D1-D2 から残置の最終確認
- D1 `[C1]`: 解消。`recent_epochs_required >= 1` は dataclass 直接構築にも効く。
- D2 `[W1]`: 概ね解消。partial pass diagnostic 化は正しいが、epoch id の unique / distinct count 整合だけ追加が必要。
- D2 `[W2]`: 概ね解消。`ast.Constant(str)` 追加と docstring 除外は妥当。
- D2 `[W3]`: 部分残り。exact name 化の結果、`tier1_event` は reject されない点を仕様文に合わせる必要あり。
- D2 `[W4]`: 解消方向。Phase 2 で案 A/B/C の推奨順を固定すれば十分。

## test_id 1:1 ギャップ
- F22e に `ready + n_distinct_epochs < recent_epochs_required` の fail case を追加。
- F22e または F22h に `recent_mission_pass_epoch_ids` duplicate の fail case を追加。
- F22f に `no_recent_mission_pass + len=0` と `len=required-1` の正常系を追加。
- F27 に `from . import archive` alias 検出 case を追加。
- F27 に `tier1_event` が許容か reject か、設計選択に合わせた case を追加。

## 学術文献 (任意)
- なし。今回の論点は統計因果ではなく、設計 invariant と静的検査 contract です。

## 総評
Round 2 の主要論点はほぼ解消しています。特に `recent_mission_pass_epoch_ids` を実測 diagnostic field として partial pass を保持する判断は、T071 audit consumer にとっても自然です。

残る blocker は小さいですが、`ready` dataclass の cross-field 整合だけは実装前に塞ぐべきです。`n_distinct_epochs >= len(unique recent_mission_pass_epoch_ids)` と duplicate 禁止を追加すれば、詳細設計は APPROVED 相当にできます。