**Section A: 全体判定**

`REQUEST_CHANGES`

主因は 1 点です。Phase 4 成功後に「次サイクルで何を分析するか」の SoT が未定義で、`--repeat` 時に同じ Run を再分析し続ける、または別 Run の `run_number` を誤参照する反証が成立します。[conceptual-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260424-1326-rewrite-improve-cycle-full/conceptual-design.md#L61) [conceptual-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260424-1326-rewrite-improve-cycle-full/conceptual-design.md#L102) [SKILL.md](/Users/ishitoya/repository/zenigame-fx/.claude/skills/zenigame-fx-run-alpha-factory/SKILL.md#L52)

イントラデイ逸脱、取引回数削減による見かけ改善、`live_criteria` 緩和を直接促す記述は本文上は見当たりません。この点は現状維持でよいです。[conceptual-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260424-1326-rewrite-improve-cycle-full/conceptual-design.md#L17)

**Section B: 指摘**

- [Critical] `run_id` / `run_number` のライフサイクルが壊れています。概念設計では Phase 1 が `{run_id}` を分析し、Phase 5 が `{next_run_number}` でレポート生成しますが、Phase 4 の `zenigame-fx-run-alpha-factory` は `current_cycle_state.json` を一切書かず、実際の SoT を `run_alpha_factory_state.json` と `summary.json.run_number` に置いています。したがって improve-cycle 側で成功 Run の `run_id` / `run_number` を取り込み直す規約がない限り、`--repeat` で旧 Run を再分析する反証が成立します。[conceptual-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260424-1326-rewrite-improve-cycle-full/conceptual-design.md#L61) [conceptual-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260424-1326-rewrite-improve-cycle-full/conceptual-design.md#L112) [conceptual-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260424-1326-rewrite-improve-cycle-full/conceptual-design.md#L225) [SKILL.md](/Users/ishitoya/repository/zenigame-fx/.claude/skills/zenigame-fx-run-alpha-factory/SKILL.md#L56) [SKILL.md](/Users/ishitoya/repository/zenigame-fx/.claude/skills/zenigame-fx-run-alpha-factory/SKILL.md#L105) [SKILL.md](/Users/ishitoya/repository/zenigame-fx/.claude/skills/zenigame-fx-run-report/SKILL.md#L15)

- [Warning] Emergency Fix は fail-soft としては妥当ですが、現状は producer がありません。概念設計は `analyze-run` が `emergency_fix.detected` を立てる前提を継承していますが、実際の `zenigame-fx-analyze-run` には state 書き込み契約がありません。つまり「壊れはしないが、発火も検証できない」状態です。[conceptual-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260424-1326-rewrite-improve-cycle-full/conceptual-design.md#L179) [SKILL.md](/Users/ishitoya/repository/zenigame-fx/.claude/skills/zenigame-fx-analyze-run/SKILL.md#L22) [SKILL.md](/Users/ishitoya/repository/zenigame-fx/.claude/skills/zenigame-fx-analyze-run/SKILL.md#L53)

- [Warning] Phase 2.5 をコメント化する判断自体は妥当ですが、「現状は plan-and-design 内 GA パラメータ調整に依拠」は実契約と一致していません。`plan-and-design` は `overrides` を読む側で、書く契約がありません。したがって GA-only 改善や `--observe-only` 時のパラメータ介入経路は未定義です。[conceptual-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260424-1326-rewrite-improve-cycle-full/conceptual-design.md#L55) [conceptual-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260424-1326-rewrite-improve-cycle-full/conceptual-design.md#L166) [SKILL.md](/Users/ishitoya/repository/zenigame-fx/.claude/skills/zenigame-fx-plan-and-design/SKILL.md#L90)

- [Warning] 残課題は 6 件で整理できていますが、検証クライテリアだけ「未移植 hook 4 件」と古い数を残しています。レビュー基準として自己矛盾です。[conceptual-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260424-1326-rewrite-improve-cycle-full/conceptual-design.md#L258) [conceptual-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260424-1326-rewrite-improve-cycle-full/conceptual-design.md#L305)

**Section C: 推奨修正**

最小変更は 1 つで足ります。

- Phase 4 完了直後に improve-cycle が `run_alpha_factory_state.json` → `summary.json` を読み、`current_cycle_state.json` を原子的に更新する規約を追加してください。更新対象は少なくとも `run_id`、`run_number`、`next_run_number`、`history`、`phase`、`completed_phases` です。Phase 5 は事前計算の `next_run_number` ではなく、`summary.json.run_number` を使って `/zenigame-fx-run-report` を呼ぶ、と明記すれば今回の Critical は解消します。

この 1 点が入れば、今回のラウンドでは APPROVE に寄せられます。