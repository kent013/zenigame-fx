## 指摘事項

1. [Critical] `manage-sessions` への置換先が、現状の repo では実行不能です。概念設計は `scripts/cleanup_claude_sessions.py` を `zenigame-fx-manage-sessions cleanup` へ置換するとしていますが、`zenigame-fx-manage-sessions` 自体がそのスクリプトを必須前提にしており、不在時はアボートすると明記しています。しかも実ファイルは現 repo に存在しません。したがってこの置換は「skill 名を明記した」だけで、実行可能契約にはなっていません。[conceptual-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260424-0711-port-analyze-run/conceptual-design.md#L84) [SKILL.md](/Users/ishitoya/repository/zenigame-fx/.claude/skills/zenigame-fx-manage-sessions/SKILL.md#L16) [SKILL.md](/Users/ishitoya/repository/zenigame-fx/.claude/skills/zenigame-fx-manage-sessions/SKILL.md#L25)

2. [Critical] 出力成果物名の契約がまだ揺れています。概念設計は `analyze-claude.md` を将来 hook の固定フォーマットとして書いていますが、現行実装の出力名は `analysis-claude.md` です。さらに `zenigame-fx-improve-cycle` も出力説明は `analysis-claude.md` なのに、plateau 判定だけ `analyze-claude.md` を grep しています。Round 1 で skill 名揺れを直した一方、artifact 名の揺れが同じ種類の接続不良として残っています。[conceptual-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260424-0711-port-analyze-run/conceptual-design.md#L30) [analyze_run.py](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/analyze_run.py#L7) [analyze_run.py](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/analyze_run.py#L168) [SKILL.md](/Users/ishitoya/repository/zenigame-fx/.claude/skills/zenigame-fx-improve-cycle/SKILL.md#L101) [SKILL.md](/Users/ishitoya/repository/zenigame-fx/.claude/skills/zenigame-fx-improve-cycle/SKILL.md#L113)

3. [Warning] 呼び出し契約表は追加されましたが、現状の実装系とはまだ接続されていません。設計は `/zenigame-fx-improve-cycle -> /zenigame-fx-analyze-run` を固定契約として書いていますが、実在する `zenigame-fx-improve-cycle` は依然として `scripts/alpha_factory/analyze_run.py` を直接呼んでいます。今回の TODO が text port のみなら、その契約は「将来状態」であり、別 TODO で improve-cycle 側を切り替える前提を明記しないと、新 skill が孤立します。[conceptual-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260424-0711-port-analyze-run/conceptual-design.md#L34) [SKILL.md](/Users/ishitoya/repository/zenigame-fx/.claude/skills/zenigame-fx-improve-cycle/SKILL.md#L88)

## 判定

`NEEDS_REVISION` です。  
Round 1 の Critical 3 件は確かに解消されていますが、今回の版では「session 管理の実行可能性」と「artifact 名の契約固定」に新しい Critical が残っています。この 2 点を潰せば APPROVED に近いです。

## 修正要求

- `zenigame-fx-manage-sessions` を本 TODO の依存に置くなら、`scripts/cleanup_claude_sessions.py` の不在を `To verify before merge` ではなく明示的 blocker として扱うか、今回の analyze-run 移植からその統合を外してください。
- `analyze-claude.md` / `analysis-claude.md` を全設計・既存 skill・将来 hook 契約で 1 つに統一してください。
- `/zenigame-fx-improve-cycle` からの接続は「現契約」ではなく「follow-up TODO で切替予定」と書くか、切替 TODO を同時に起票してください。