# 概念設計: selection_score tie drift 調査

**起点監査**: [audit-codex.md §2 (13)](../20260427-0050-bug-hunt-audit/audit-codex.md) — INCONCLUSIVE

## 仮説

Stage A pass 集中 + 同一 fitness_pen tie で tournament selection が決定論的 drift に陥り、多様性が世代を超えて消失する可能性。Run 22 で directional 14k 中 96% が 3 primitive に集中している winner-take-all 兆候は本仮説と整合。

## 検証済み事実

- selection_score = (feasible, -violation, stage_c, stage_b, stage_a, fitness_pen) の lexicographic 比較
- Run 22 で primitive 集中 (F6: 4916 / F10: 4375 / F1: 3589 で 96%)
- archive で同一 fitness_pen 個体の頻度未測定

## 解決方針

調査スクリプトで Run の世代ごとに:
- 同 fitness_pen 集団のサイズ分布
- elite として retain される個体の genome_hash 推移
- tournament 勝者の同質化推移 (Herfindahl-Hirschman Index)

bug ではなく構造的問題なら多様性 pressure 導入の別 TODO 起票。

## 成功判定

- tie drift の有無 / 規模を quantitative に定量化
- 必要なら多様性圧 (HHI penalty / island model) の修正 TODO へ繋げる
