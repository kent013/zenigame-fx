# 改善計画: Run 85 → Run 86 (cycle 4, plan-and-design 進行中)

## 背景
cycle 3 で P2 (Stage C stress cost-robustness 化) 完遂・検証。seed=68 mission 個体 g51_i71 は真の cost stress 下でも Stage C 通過 = cost-robust 実証。残る最大課題は **seed variance**: R83=R85(seed68)→Stage C 43 だが R84(seed69)→0、Stage B も 15倍変動。GA は seed 固定で deterministic だが seed-locked。

## Critical 施策 (両分析 + Codex 合議で確定): T101 warmstart
既知 mission 個体 (R85 の Stage-C 通過 43 genome、特に g51_i71) を GA 初期集団に注入し、mission 個体を seed 非依存に保持 → 再現性を担保。評価関数・閾値・selection は不変 (低リスク)。
- 受入基準 (Codex): seed 67/68/69 各 run で live all_pass>=1。
- Codex Warning: 単一個体固定でなく top-N archive motif + mutation で多様性維持 (T101 設計の motif merge + mutate がこれを満たす)。

### T101 既存設計 (devnotes/20260513-1915-todo-run71-63-warmstart/detailed-design.md)
- archive から `stage_c_pass=True AND total_pnl>=20000` の genome を motif 抽出 (R85 の 43 個体が該当)。
- GA initialize_population (run_ga.py:2077 の random_genome 生成箇所) で warmstart_ratio 分を mutated motif で生成、残りは random。
- GAConfig: `warmstart_ratio` (default 0.0=完全不変), `warmstart_motif_archive`。CLI `--warmstart-ratio`。
- default 0.0 で baseline 完全一致 (既存 test 全 pass)。

## ★ 要調査・整合 (plan-and-design 次ステップで Codex 合議): 既存 warmstart インフラとの関係
コードベースに既に warmstart 機構が存在 (T066/T067):
- `src/alpha_factory/loop_closure.py`: build_warmstart_candidates / select_warmstart_candidates / admit_warmstart_to_da_with_eviction / compute_warmstart_counts / compute_warmstart_ramp_share。
- `src/alpha_factory/cpps_archive.py`: CPPS archive (CA/DA admission)。
→ **T101 の simpler 初期集団注入が既存 loop_closure/CPPS warmstart と重複/競合しないか、既存インフラを使うべきか** を Codex design-review で確認必須。重複実装は避け、既存機構で同目的を達成できるならそれを配線する。

## 次フェーズ手順 (fresh context で継続)
1. plan-and-design: 既存 warmstart インフラ (loop_closure/cpps_archive) を調査し、T101 の simpler 注入と整合。Codex consensus + design-review で「既存インフラ活用 vs T101 新規 warmstart.py」を1つに収束 (低リスク最優先)。
2. detailed-design 確定 (default OFF で挙動不変、g51_i71/R85 motif 注入)。
3. implement (worktree, TODO=T101 or 新規, テスト: default 0.0 baseline 一致 + warmstart 注入 unit/integration, Codex impl-review, merge)。
4. R86: warmstart 適用で seed=67 と seed=69 (R84 で mission=0 だった seed) を各 run 実行、live all_pass>=1 を確認 (受入基準)。背景監視。
5. report → cycle 5。

## 使命・禁止事項チェック
warmstart は初期集団への既知良個体注入 = 探索の足場 (評価/閾値/selection 不変、ルール改ざんでない)。閾値緩和・期間延長・取引回数操作なし。default OFF で挙動不変。✅
