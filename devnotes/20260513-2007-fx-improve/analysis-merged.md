# マージ分析: Run 74 → Run 75

## 合意事項（Claude + Codex 両者一致）

1. **全体判定: CRITICAL_DRIFT** — Stage B 閾値が設計上の不整合を抱える
2. **Stage B 通過 96 個体が全例赤字** (-6940 〜 -16670) — sign-based 検査で magnitude を見ない設計が原因
3. **active_clause 1.01 で clause collapse** — max_clause=2 設定が機能していない
4. **unique fitness_pen 6.2%** で Stage B 通過群の多様性崩壊
5. **selection_score_schema v3_3 の歪み** — feasible 優先が収益性より上位、archive 最大 fitness_pen (黒字) は Stage B fail、selection_score best (赤字) は Stage B pass
6. **DSR proxy 27 倍離れ** — M=5856 trials の Bonferroni-like 補正で全個体 fail
7. **トレード回数依存疑い** — best trade_count=41 は live_criteria 下限 50 を下回り「取引回数最適化への寄り」が疑わしい

## Claude 独自の発見

- archive 内 fitness_pen 最大個体 (g41_i78, 0.255 黒字) と selection_score best (g60_i45, 0.106 赤字) が異なる構造（v3_3 が Stage B pass を強く preference するため）
- Stage B fail 主因の 95.6% が `median_oos_sharpe<min;positive_fold_ratio<min` 同時 trigger
- 18 RUN 累積 Stage C pass = 0 (Run 57-74 全て)

## Codex 独自の発見

- イントラデイ逸脱・ショート偏重・live_criteria 緩和は **INCONCLUSIVE** (保有時間 / side 内訳 / 閾値変更履歴が未提示) — **FX 制約の監査指標を必須出力化すべき** (overnight_hold_ratio / long_short_pnl / spread_cost / swap_cost / net_pnl_after_cost)
- clause 2 個強制は探索空間を不自然に歪めるので段階導入推奨 (clause 使用率ペナルティ / 下限制約)

## 矛盾・要議論

なし。両者の判定・提案は同方向（CRITICAL_DRIFT、Stage B gate magnitude 強化）。

## 統合改善提案（優先度順）

| # | 提案 | 優先度 | 出所 | target_metric | failure_mode | 期待効果 |
|---|------|--------|------|--------------|-------------|---------|
| 1 | **T099 MODIFY (profit-safe pfr)**: Stage B gate を `pfr >= 0.4 AND median_oos_total_pnl >= 0 AND trade_sharpe_stage_b > 0` に opt-in (default OFF) | **Critical** | T099 + C22-1 統合 (Codex todo-selection APPROVED) | Stage B 通過群 median_oos_total_pnl ≥ 0 達成率 / Stage C trade_sharpe median / Stage C pass count | Stage B 通過 96 個体全例赤字、median_oos_sharpe → trade_sharpe_stage_c が ρ=-0.361 で逆予測 | curve-fit 個体除外 + 赤字許容構造の解消 → Stage C pass 出現 |
| 2 | (保留) clause 使用率ペナルティ段階導入 (active_clause 1.01 対策) | Warning | Codex 独立分析 + Claude I2 | active_clause / unique fitness_pen ratio | clause 1 collapse (96/96 が 1 clause)、多様性崩壊 | clause 2 個探索を強制せず、選好で誘導 |
| 3 | (保留) FX 制約監査指標の必須出力化 (overnight_hold / long_short_pnl / spread_cost / swap_cost / net_pnl_after_cost) | Warning | Codex 独立分析独自 | INCONCLUSIVE 解消 (禁止事項違反検知) | FX 固有制約逸脱検知が監査経路なしで INCONCLUSIVE | 検知体制整備、以降の deceit-vs-real 判定基準確立 |
| 4 | (保留) cross-pair lane 復活 / multi-instrument (EUR_JPY 単独 18 RUN regime 擦り懸念) | Warning | Claude C22-4 | cross_pair_runtime_mode の skipped → shadow 統計生成 | 同 regime 擦り続け、汎化欠如懸念 | regime shift 観察、shadow 評価復活 |

## 次フェーズへの申し送り

- **#1 を cycle 22 で実装** (Phase B/C/3 で確定 → Run 75 smoke)
- **#2-#4 は保留事項** として improvement-plan.md に記録、次サイクル以降の TODO 候補
- 30 RUN ループ (cycle 22-51) を考慮し、cycle 22 で #1 のみに集中し、cycle 23 以降の seed sweep で #1 効果を検証 (大規模設計変更は避ける)
