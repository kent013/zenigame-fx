### Section A: 全体判定
**REQUEST_CHANGES**

### Section B: 指摘

#### [Critical]
- **反証可能仮説 H1**: 「`run_id` 自動検出で archive 0 件だった初回サイクルでも、草案どおり Phase 2（plan-and-design）へ進める」
- **Fact**:
  - 草案は「archive 0 件なら Phase 1 を skip して、`run_id=null`・analysis 空で Phase 2 へ進む」と定義。
  - しかし `plan-and-design` 現契約は analysis を入力前提で、欠損時は停止する定義になっています（[`SKILL.md:24`](/Users/ishitoya/repository/zenigame-fx/.claude/skills/zenigame-fx-plan-and-design/SKILL.md:24), [`SKILL.md:709`](/Users/ishitoya/repository/zenigame-fx/.claude/skills/zenigame-fx-plan-and-design/SKILL.md:709)）。
- **Interpretation**:
  - 初回（履歴なし）で improve-cycle が Phase 2 で止まり、ブートストラップ不能になるリスクが高い。
- **反証手順**:
  1. `.cache/alpha_factory/runs/genomes_*.parquet` が 0 件の状態で `/zenigame-fx-improve-cycle` 実行  
  2. Phase 2 が停止せず `improvement-plan.md` / `detailed-design.md` を生成できれば H1 は棄却  
  3. 現契約上は停止が自然なので、現時点では **H1 はほぼ反証される（=設計衝突）**

#### [Warning]
- なし（本ラウンドは収束ルールに従い 1 仮説に絞り込み）

#### [Suggestion]
- なし（最小変更 1 件に集中）

### Section C: 推奨修正（最小変更 1 件）
- **Step 0-2 の初回分岐だけ変更**してください。  
  - archive 0 件時は **Phase 2/3 も skip** して、**Phase 4 → Phase 5 で初回 SoT Run をまず作る**（実質 bootstrap cycle）。  
  - その後の次サイクルから通常の Phase 1→2→3 フローへ復帰。  

これで既存 sub-skill 契約を崩さず、初回停止リスクを解消できます。