判定: REQUEST_CHANGES

[Critical] 詳細設計で必須の「improve-cycle 側 launcher 接続」が未反映です。  
[improve-cycle SKILL.md#L21](/Users/ishitoya/repository/zenigame-fx/.claude/skills/zenigame-fx-improve-cycle/SKILL.md#L21), [#L265](/Users/ishitoya/repository/zenigame-fx/.claude/skills/zenigame-fx-improve-cycle/SKILL.md#L265), [#L543](/Users/ishitoya/repository/zenigame-fx/.claude/skills/zenigame-fx-improve-cycle/SKILL.md#L543) が依然 TODO のままで、設計書の接続済み要件（launcher + marker）と不整合です（設計: [detailed-design.md#L337](/Users/ishitoya/repository/zenigame-fx/devnotes/20260424-1628-port-post-run-review/detailed-design.md#L337) 以降）。

[Critical] analyze-run 側も「未移植」表記のままで、接続済み注記に更新されていません。  
[analyze-run SKILL.md#L29](/Users/ishitoya/repository/zenigame-fx/.claude/skills/zenigame-fx-analyze-run/SKILL.md#L29), [#L220](/Users/ishitoya/repository/zenigame-fx/.claude/skills/zenigame-fx-analyze-run/SKILL.md#L220), [#L242](/Users/ishitoya/repository/zenigame-fx/.claude/skills/zenigame-fx-analyze-run/SKILL.md#L242)。

[Warning] 波及変更 5/6（runbook）と 6/6（terminology）が未実装です。  
[runbook.md](/Users/ishitoya/repository/zenigame-fx/docs/alpha_factory/runbook.md), [terminology.md](/Users/ishitoya/repository/zenigame-fx/docs/alpha_factory/terminology.md) に post-run-review 関連節が未追加で、詳細設計の網羅要件と不一致です（設計: [detailed-design.md#L500](/Users/ishitoya/repository/zenigame-fx/devnotes/20260424-1628-port-post-run-review/detailed-design.md#L500), [#L541](/Users/ishitoya/repository/zenigame-fx/devnotes/20260424-1628-port-post-run-review/detailed-design.md#L541)）。

[Warning] エラーハンドリング方針に設計との差分があります。  
`todo-add` 失敗時、設計例は `exit`（[detailed-design.md#L236](/Users/ishitoya/repository/zenigame-fx/devnotes/20260424-1628-port-post-run-review/detailed-design.md#L236)）ですが、実装 skill は `continue`（[post-run-review SKILL.md#L398](/Users/ishitoya/repository/zenigame-fx/.claude/skills/zenigame-fx-post-run-review/SKILL.md#L398), [#L464](/Users/ishitoya/repository/zenigame-fx/.claude/skills/zenigame-fx-post-run-review/SKILL.md#L464)）。仕様確定が必要です。

[Warning] 「Closed TODO 直近 10 件との照合」要件に対し、入力収集が Open 中心で不足しています。  
要件記載は [post-run-review SKILL.md#L312](/Users/ishitoya/repository/zenigame-fx/.claude/skills/zenigame-fx-post-run-review/SKILL.md#L312) ですが、収集手順は Open TODO 取得のみ（[#L142](/Users/ishitoya/repository/zenigame-fx/.claude/skills/zenigame-fx-post-run-review/SKILL.md#L142) 付近）で、Closed の取得経路が明示されていません。

[Suggestion] `Phase 2` で「zenigame-fx-codex-review One-shot」と書きつつ、例が `scripts/codex exec` 直打ちなので、呼び出し責務を一文で明確化すると監査しやすくなります。  
[post-run-review SKILL.md#L156](/Users/ishitoya/repository/zenigame-fx/.claude/skills/zenigame-fx-post-run-review/SKILL.md#L156), [#L166](/Users/ishitoya/repository/zenigame-fx/.claude/skills/zenigame-fx-post-run-review/SKILL.md#L166)

補足（良い点）:
- review-theme → TODO theme マッピングは `todo_manager.py` の許容 theme と整合しています。  
[post-run-review SKILL.md#L33](/Users/ishitoya/repository/zenigame-fx/.claude/skills/zenigame-fx-post-run-review/SKILL.md#L33), [todo_manager.py#L21](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/todo_manager.py#L21)
- Phase 1-0 の `awk` 方針（Open セクション限定 + `index()`）は現行 `list` 出力形式に対して妥当です。  
[post-run-review SKILL.md#L112](/Users/ishitoya/repository/zenigame-fx/.claude/skills/zenigame-fx-post-run-review/SKILL.md#L112), [todo_manager.py#L284](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/todo_manager.py#L284)
- 株版固有依存（systemd/Dramatiq/旧 skill 名）の混入は post-run-review 本体には見当たりません。

全体判定: CHANGES_REQUESTED