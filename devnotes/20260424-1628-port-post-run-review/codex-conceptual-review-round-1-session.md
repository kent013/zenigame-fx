全体判定: **CHANGES_REQUESTED**

**観察事実（Facts）**
- 使命の SSOT は `live_criteria` 全条件達成であり、README でも config でもその形で固定されています。[docs/alpha_factory/README.md:5](/Users/ishitoya/repository/zenigame-fx/docs/alpha_factory/README.md#L5) [config/alpha_factory/default.yaml:30](/Users/ishitoya/repository/zenigame-fx/config/alpha_factory/default.yaml#L30)
- Stage C は Phase 2 では `(ii-lite)` を shadow only として扱います。[docs/alpha_factory/stage-gates.md:44](/Users/ishitoya/repository/zenigame-fx/docs/alpha_factory/stage-gates.md#L44) [docs/alpha_factory/stage-gates.md:162](/Users/ishitoya/repository/zenigame-fx/docs/alpha_factory/stage-gates.md#L162)
- `improve-cycle` には `post-run-review-port` の未接続コメントが残っています。[.claude/skills/zenigame-fx-improve-cycle/SKILL.md:19](/Users/ishitoya/repository/zenigame-fx/.claude/skills/zenigame-fx-improve-cycle/SKILL.md#L19) [.claude/skills/zenigame-fx-improve-cycle/SKILL.md:265](/Users/ishitoya/repository/zenigame-fx/.claude/skills/zenigame-fx-improve-cycle/SKILL.md#L265)
- `analyze-run` は `post-run-review` 未移植を明記しつつ、`improve-cycle -> analyze-run` は「将来契約」、現状は `scripts/alpha_factory/analyze_run.py` 直呼びと記載しています。[.claude/skills/zenigame-fx-analyze-run/SKILL.md:24](/Users/ishitoya/repository/zenigame-fx/.claude/skills/zenigame-fx-analyze-run/SKILL.md#L24) [.claude/skills/zenigame-fx-analyze-run/SKILL.md:33](/Users/ishitoya/repository/zenigame-fx/.claude/skills/zenigame-fx-analyze-run/SKILL.md#L33)
- 既存 `post-run-review` 概念文書は `run_in_background: true` 前提の 5 並列 Agent を記述しています。[docs/alpha_factory/concepts/post-run-review.md:27](/Users/ishitoya/repository/zenigame-fx/docs/alpha_factory/concepts/post-run-review.md#L27)
- TODO 管理の `theme` 語彙は `ga-architecture` / `primitives` / `stage-gate` などで、提案された 5 review theme とは一致しません。[scripts/alpha_factory/todo_manager.py:21](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/todo_manager.py#L21)
- `todo_manager.py` の `next-id` と `add` は分離されており、排他制御はありません。`list` コマンドはあります。[scripts/alpha_factory/todo_manager.py:145](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/todo_manager.py#L145) [scripts/alpha_factory/todo_manager.py:171](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/todo_manager.py#L171) [scripts/alpha_factory/todo_manager.py:284](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/todo_manager.py#L284)
- Open TODO は現状 1 件だけです。[docs/alpha_factory/TODO.md:5](/Users/ishitoya/repository/zenigame-fx/docs/alpha_factory/TODO.md#L5)
- `git log` の先頭では T024/T025 のマージは確認できました。T001-T023 の一括確認や `834 tests passing / 1 skip` は今回の確認範囲では独立検証していません。

**観点別レビュー（Interpretations）**

1. 使命との整合性  
[Warning] 方向性自体は使命に沿っています。  
修正提案: 各 theme に「主に改善したい `live_criteria` 指標」か「Stage A/B/C のどのボトルネックを改善するか」を 1-2 個で固定してください。現状は `risk-management` 以外が広く、改善スループットがそのまま使命達成に結びつく設計になっていません。

2. 禁止事項違反  
[Warning] 5 theme × 各 0-3 件は 1 Run あたり最大 15 件の TODO を生み得ます。  
修正提案: 「採択は全体で 2-3 件まで」「1 theme あたり採択は最大 1 件まで」にしてください。現状のままだと「やたらに複雑な案」「見た目の改善案」の流入圧が強すぎます。  
[Suggestion] ショート禁止条項の削除自体は FX 方針と整合しています。

3. 実現可能性  
[Critical] hook の所有者が未確定です。`improve-cycle` 側は Phase 1 に hook 追加予定で、`analyze-run` 側は improve-cycle からの呼び出し自体を「将来契約」としています。ここで improve-cycle と analyze-run の両方から発火すると、将来の契約統一後に二重起動します。  
修正提案: `post-run-review` の dispatch owner を 1 箇所に固定してください。推奨は orchestrator である `improve-cycle` のみです。`analyze-run` は manual 単独呼び出し時だけ発火、という分岐を明文化すべきです。  
[Warning] `run_in_background: true` 前提は概念文書にありますが、起動成功・失敗・再実行の観測契約がありません。  
修正提案: Agent 起動時に「accepted artifact」を `.cache` に書く、失敗時は deferred queue に戻す、という最小の耐障害契約を追加してください。

4. 期待効果の妥当性  
[Warning] 「スループット 5 倍化」「各 theme で 0-3 件生成」は仮説です。  
修正提案: 効果主張は「仮説生成の throughput 向上」に留め、検証は `n>=30` Run 以降にしてください。直近 3 Run ベースでは C7 上、因果主張はできません。  
[Warning] `robustness` や `risk-management` の有効性を Stage 通過群だけで評価すると、C3 の collider bias が入ります。  
修正提案: 効果検証は「Run 全体」を母集団にし、conditioning set を設計書に明記してください。

5. リスク  
[Critical] early-skip のキーに使う 5 review theme は、現行 TODO schema の `theme` 語彙と一致しません。現状の `todo_manager.py` だけでは「同テーマ Open TODO があるので skip」は安全に実装できません。  
修正提案: TODO に `review_theme` メタデータを追加するか、`.cache/alpha_factory/post-run-review-index.json` のような別 SSOT を作って、review theme と TODO ID の対応を管理してください。  
[Critical] 並列 TODO 追加は race に弱いです。`next-id` と `add` が分離され、ロックもないため、5 Agent が同時に `T026` を取る設計事故が起こり得ます。  
修正提案: `reserve-and-add` の原子的コマンドを追加するか、`todo-add` だけは単一 writer に直列化してください。  
[Warning] `alpha-design` と `todo-add` まで各 Agent が進むと、失敗時に中途半端な設計・TODO が増えます。  
修正提案: 並列化は「案出し」までに留め、設計化と TODO 登録は親側で直列採択する形の方が安全です。

6. スコープの適切さ  
[Warning] 「hook コメントを書き換えるだけ」は過小スコープです。  
修正提案: 最低でも「dispatch owner 固定」「review_theme の SSOT」「TODO 追加の排他」の 3 点を同一 TODO に含めるか、前提 TODO を先に切ってください。これがないと port 完了と言えません。

7. メモリ制約  
[Warning] 確認した SSOT には background review Agent の並列上限や RAM 予算の設定項目がありません。  
修正提案: `max_parallel_reviews` を 1-2 に制限し、重い段階は `Codex議論までは並列、alpha-design/todo-add は直列` に分けてください。24GB × 6 worker 制約下で 5 本の長文 Agent を常時投げる設計は、安全側に倒れていません。

8. 前提検証（C4）  
[Warning] `834 tests passing / 1 skip` と `T001-T025 merged` は今回のレビューで独立検証できていません。  
修正提案: 概念設計の前提欄に、`pytest` 実行日時・コマンド・commit hash を明記してください。少なくとも「どの commit で確認した前提か」は固定すべきです。

9. Design-first（C1）  
[Suggestion] このレビューでは `docs/alpha_factory/`、`devnotes/.../debate-synthesis.md`、現行 `SKILL.md`、`todo_manager.py`、`git log` を参照しました。  
[Suggestion] 設計書本体にも「Reviewed sources」節を追加し、参照した doc/devnote/commit を列挙してください。C1/C4 の再監査がしやすくなります。

結論として、**テーマ別 post-run-review 自体の方向性は妥当**ですが、現状案は「発火主体」「重複抑止キー」「TODO 追加の原子性」が未確定です。ここを固めずに進めると、改善スループットではなく重複作業のスループットが上がります。