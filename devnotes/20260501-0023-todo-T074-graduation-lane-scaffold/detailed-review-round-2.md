## Verdict
NEEDS_REVISION

## 前提 (C4)
- レビュー対象は提示された Round 2 差分本文のみ。リポジトリ実ファイルは読んでいない。`Verified`
- `GraduationTriggerEvaluation` は `evaluate_graduation_trigger` が返す正規化済み結果を表す前提。`Verified by design text`
- `recent_mission_pass_epoch_ids` は名前上「直近 window 内で mission_pass した epoch id」を表すと解釈。`Interpretation`
- AST grep DoD は production code の並列経路混入検出が目的で、docstring/comment 除外が目的。`Verified by design text`

## Critical
- なし。Round D1 `[C1]` の `recent_epochs_required >= 1` は `GraduationTriggerEvaluation.__post_init__` に入り、dataclass 直接構築経路も塞げています。

## Warning
- [W1] `no_recent_mission_pass` の `len(recent_mission_pass_epoch_ids) == 0` は過拘束です。条件は「直近 N epoch すべて pass ではない」なので、部分 pass 例 `required=3, pass_ids=("e3", "e2")` も failure です。field を実測値にするなら `0 <= len < required`、非 ready では空固定にするなら field 名を `ready_recent_mission_pass_epoch_ids` 等へ寄せるべきです。
- [W2] AST grep DoD は string literal 経由の動的参照を見逃します。`getattr(x, "observability_flags")` や dict key `"tier1"` を許す設計なら問題なしですが、C2 parallel-path 検出目的なら `ast.Constant(str)` も対象にし、module docstring と通常説明文だけ除外する方が安全です。
- [W3] `tier1` の substring check は false positive が出やすいです。`Tier1Lane` / `tier1` / `tier_1` など識別子 token 境界ベースにするか、違反語を exact name と substring に分けて明文化してください。
- [W4] Phase 2 adapter contract の「snapshot mutation 検出を caller 責務」は、既存 `archive.py` に transaction/snapshot API が無い場合に実装リスクが残ります。Phase 2 申し送りに「既存 API が無ければ snapshot DTO か transaction wrapper を追加する」と明記した方がよいです。

## Suggestion
- [S1] `insufficient_epochs` に `n_graduates >= 24` を要求するのは妥当です。これは priority 正規化済み status の invariant なので、`status="insufficient_epochs", n_graduates=0` は reject でよいです。
- [S2] robust 追加禁止は commit hash より `synthesis_schema_version >= 22` のような版 ID が安全です。複数 PR で Round 22 が完了する場合、単一 commit hash 基準は曖昧になります。
- [S3] F22e は parametrize 推奨です。4 status の valid baseline を作り、各 invariant を 1 field ずつ壊す matrix にすると test_id と失敗理由が対応しやすいです。
- [S4] `src.alpha_factory.graduation` import 確定なら、Phase 1 では `src/alpha_factory/__init__.py` re-export は不要です。公開 API として使う段階で判断すれば十分です。

## Round D1 から残置の最終確認
- `[C1]` 解消: `recent_epochs_required >= 1` が dataclass 直接構築にも効くため OK。
- `[W1]` 解消: `.issubset()` 統一は OK。
- `[W2]` 解消: `GraduationArchiveSummary` の I-1→I-4 raise 順序仕様化は OK。
- `[W3]` 部分残り: status 別 invariant は網羅されたが、`no_recent_mission_pass` の partial pass 表現だけ再検討が必要。
- `[W7]` 部分残り: AST 化は方向性 OK。ただし string literal 動的参照の扱いを仕様化すべきです。

## test_id 1:1 ギャップ
- F22e に `no_recent_mission_pass` partial pass case を追加してください。期待値は設計選択に依存します。
- F27 に `getattr(obj, "observability_flags")` / `{"tier1": x}` を検出対象にするか許容対象にするかの test を追加してください。
- F9-F14 の `n_graduates<0` / duplicate / not-in-distinct は、本文だけなら命名整合 OK。実 test list でも F9/F10/F11 に明示されていれば十分です。

## 学術文献 (任意)
- なし。今回は統計的因果主張ではなく、設計 invariant と test contract のレビューです。

## 総評
Round D1 の Critical は解消済みで、trigger の priority 正規化方針も概ね健全です。ただし `recent_mission_pass_epoch_ids` を「実測 diagnostic」として持つのか「ready 時だけ埋まる証跡」として持つのかが未確定で、ここを曖昧にしたまま実装すると F22e が設計意図を固定できません。

修正は小さいです。`no_recent_mission_pass` の partial pass 方針と F27 の string literal 方針を明文化すれば、詳細設計は APPROVED に近い状態です。