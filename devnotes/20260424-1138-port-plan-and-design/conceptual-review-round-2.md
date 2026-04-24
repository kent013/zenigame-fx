**全体判定**

APPROVED

Round 1 の 3 つの承認ラインと、そこで挙がっていた主要 Critical はいずれも今回の改訂で実質的に解消されています。確認根拠は主に [conceptual-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260424-1138-port-plan-and-design/conceptual-design.md)、[conceptual-review-round-1.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260424-1138-port-plan-and-design/conceptual-review-round-1.md)、[zenigame-fx-codex-review/SKILL.md](/Users/ishitoya/repository/zenigame-fx/.claude/skills/zenigame-fx-codex-review/SKILL.md)、[zenigame-fx-improve-cycle/SKILL.md](/Users/ishitoya/repository/zenigame-fx/.claude/skills/zenigame-fx-improve-cycle/SKILL.md)、[zenigame-fx-analyze-run/SKILL.md](/Users/ishitoya/repository/zenigame-fx/.claude/skills/zenigame-fx-analyze-run/SKILL.md)、[scripts/codex](/Users/ishitoya/repository/zenigame-fx/scripts/codex)、[todo_manager.py](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/todo_manager.py)、[TODO.md](/Users/ishitoya/repository/zenigame-fx/docs/alpha_factory/TODO.md) です。

**Round 1 指摘の逐次評価**

1. [Critical] TODO 選定を `live_criteria` 未達要因に直結させる  
対応充足。`target_metric / failure_mode / causal_path / falsification / success_criterion` の必須化で、mission-facing に接続されています。

2. [Warning] 期待効果を mission KPI に寄せる  
対応充足。Stage C 通過率、ii-lite pass 率、コスト控除後 PnL 要因特定に言い換えられています。

3. [Suggestion] FX 固有制約を各 Phase 判断基準に再登場させる  
概ね充足。継承依存のままではなく、Phase B プロンプト改修側にも再掲されています。

4. [Warning] Phase A/B プロンプトに禁止事項 rejection rule を明記する  
対応充足。禁止事項 1/2/4/6/7 を rejection rule 化しています。

5. [Suggestion] 「ショート追加で見かけだけ改善」点検を入れる  
対応充足。明記されています。

6. [Critical] `scripts/codex` / `todo_manager.py` / `focus-theme` / `state file` の存在・I/F 未検証  
対応充足。前提表で Verified 化されており、実体も確認できました。`scripts/codex exec` / `exec resume` / `--json` / `-o` も現物で成立しています。

7. [Warning] 未移植 hook 不在時の improve-cycle/autopilot 側期待が未定義  
対応充足。`no-op`、成果物要求なし、unblock が固定されています。

8. [Warning] `815 passed baseline` の具体値が曖昧  
概ね充足。Assumed に降格され、`md only` の非機能変更として扱われています。blocking ではありません。

9. [Warning] 導入後に観測したい中間指標を追加する  
対応充足。棄却率、差し戻し率、同一論点再発率などが追加されています。

10. [Suggestion] 改善対象を「仮説の重複・矛盾の減少」と明確化する  
概ね充足。分析マージの役割が前より具体化されています。

11. [Critical] 合議ループ長文化リスク  
対応充足。通常 3 / repeat 5、かつ「1 つの反証可能仮説 + 1 つの最小変更」への収束条件が入っています。

12. [Warning] `codex-review` 依存で暗黙挙動変更のリスク  
対応充足。継承先必須節名が固定されています。

13. [Suggestion] focus-theme fallback を明文化する  
対応充足。`general` / `null` / 選定基準 0 skip が固定されています。

14. [Warning] state file を読むだけか更新もするのか曖昧  
対応充足。読み書き境界と key 単位の責務が明示されました。

15. [Suggestion] `run` 実行しない / TODO 実装しない を明記  
対応充足。スコープ外に明記されています。

16. [Critical] 前提を `Verified / Assumed / To verify` で出す  
対応充足。設計冒頭に追加済みです。

17. [Warning] focus-theme 不在時のテーマ集合を固定文言で書く  
対応充足。固定文言になっています。

18. [Critical] docs / devnotes / git log を参照済みという証拠がない  
対応充足。参照一覧が追加されています。

19. [Warning] `grep 0 件` だけでは不足、T020/T021 と同等契約を示すべき  
対応充足。章立て・契約・受け入れ基準に明記されています。

**残課題**

[Warning] P12 の表現は少し不正確です。現状の [analyze_run.py](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/analyze_run.py) が直接出すのは `analysis-claude.md` で、`analysis-codex.md` は [zenigame-fx-analyze-run/SKILL.md](/Users/ishitoya/repository/zenigame-fx/.claude/skills/zenigame-fx-analyze-run/SKILL.md) 側の成果物です。前提文は「analyze-run skill が両方を成果物として扱う」に寄せた方が誤読を防げます。

[Warning] `focus-theme.json` の SSOT は今後 1 行だけ補っておくとさらに堅いです。[docs/alpha_factory/README.md](/Users/ishitoya/repository/zenigame-fx/docs/alpha_factory/README.md) は `config/alpha_factory/` を示し、既存の非 FX `set-focus` は `.cache/alpha_factory/` を使っています。今回の設計は `config/alpha_factory/focus-theme.json` を採用しているので、「将来の `zenigame-fx-set-focus` もこのパスに従う」を 1 文固定すると再分岐を防げます。

[Suggestion] テスト baseline は数値固定より「現行 baseline 非悪化」に寄せると、将来のレビューでも使い回しやすいです。

**承認ライン評価**

1. TODO 選定を `live_criteria` 未達要因に直結させる  
PASS

2. 前提を `Verified / Assumed / To verify` で明示する  
PASS

3. 未移植 hook / state file / focus-theme 不在時の契約を固定する  
PASS

承認してよい改訂です。上の Warning 2 件は実装前に文言補正しておくとさらに事故率が下がりますが、今回の概念設計の承認可否を左右する水準ではありません。