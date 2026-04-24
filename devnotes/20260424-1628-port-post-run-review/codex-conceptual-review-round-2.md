全体判定: **CHANGES_REQUESTED**

**観察事実（Fact）**
- `todo_manager.py list` は Markdown行を標準出力する実装で、JSONを返しません。[todo_manager.py](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/todo_manager.py#L284)
- `todo_manager.py add` は既存ID重複チェックをしていません（`next-id` と `add` が分離）。[todo_manager.py](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/todo_manager.py#L145) [todo_manager.py](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/todo_manager.py#L171)
- `improve-cycle` 側に post-run-review の起動TODOコメントがあり、現時点で未接続です。[SKILL.md](/Users/ishitoya/repository/zenigame-fx/.claude/skills/zenigame-fx-improve-cycle/SKILL.md#L21)
- `analyze-run` 側は post-run-review 未接続として記載されています。[SKILL.md](/Users/ishitoya/repository/zenigame-fx/.claude/skills/zenigame-fx-analyze-run/SKILL.md#L29)

**解釈（Interpretation）**
1. review-theme → TODO theme マッピング  
[Warning] **大筋は妥当**です。C1の「語彙不一致」は解消方向です。  
修正提案: `risk-management -> stage-gate` は `max_pos/time_stop` を取りこぼしやすいので、`summary` に副分類タグ（例: `[risk-sub:execution-control]`）を追加して意味の取り違えを防いでください。  
[Critical] `has-open-theme` の例コマンド（`list | jq .open[]`）は現行実装と不整合です。  
修正提案: `todo_manager.py list` の出力を `grep/awk` で解釈するか、`list --json` を別TODOで先行追加してください。

2. micro-stagger + リトライで race 吸収  
[Critical] **未解消**です。現行 `add` は重複IDエラーを返さないため、`重複ID error でリトライ` は発火しません。  
修正提案: `todo_manager.py` 非改修で行くなら、`next-id -> add` 全体を `flock` 等で単一クリティカルセクション化してください。  
[Warning] 1秒staggerは衝突確率を下げるだけで、整合性保証にはなりません。  
修正提案: 「候補生成は並列、`todo-add` は親プロセス単一writerで直列化」に変えるのが最小安全策です。

3. launch owner 単一化（improve-cycleのみ）  
[Suggestion] **方向性は妥当**で、C3（二重起動リスク）は解消方向です。  
[Warning] `analyze-run` 単独実行時にレビューhookが走らない運用差分は残ります。  
修正提案: runbookに「単独分析時は手動で `/zenigame-fx-post-run-review-launch {run_id} --tmp_dir ...` を実行」と明記してください。

結論として、**C1/C3はほぼ収束、C2はまだCritical**です。特に race 対策は「確率低減」から「排他保証」に上げる必要があります。