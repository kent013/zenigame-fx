# 最終改善計画: Run 74 → Run 75 (cycle 22)

## 合議ステータス: CONSENSUS REACHED (Round 1, with minor MODIFY adopted)

Codex consensus Round 1 で全項目 APPROVE / MODIFY (REJECT) が明示。Claude は MODIFY を反映して改善計画を確定。

## 確定施策一覧

| # | 施策名 | 内容 | 変更対象 | 優先度 | 変更分類 | target_metric | failure_mode | causal_path | falsification | success_criterion | 合議結果 |
|---|--------|------|---------|--------|---------|--------------|-------------|------------|---------------|-------------------|---------|
| **C1** | **T099 MODIFY = profit_safe_pfr opt-in** | Stage B gate に opt-in mode `profit_safe_pfr` 追加: `positive_fold_ratio_effective >= 0.4 AND median_oos_total_pnl >= 0 AND (trade_sharpe_stage_b > 0 AND n_fold_effective >= 20)`。default は `legacy` 不変。median_oos_total_pnl は新規集計 (fold-level total_pnl の median)。 | `src/zenigame_fx/alpha_factory/stage_gate.py` / `src/zenigame_fx/alpha_factory/config.py` (Phase5Config or StageGateConfig 拡張) / archive schema (`median_oos_total_pnl` 列追加) / CLI (`--stage-b-gate-kind`) / tests | **Critical** | **Structural** (新 gate kind + 新メトリクス追加) | Stage B 通過群 median_oos_total_pnl ≥ 0 達成率 / Stage C trade_sharpe_stage_c median / Stage C pass count / **min_stage_b_pass ≥ 10** | Run 74 で Stage B 通過 96 個体全例赤字、ρ(median_oos_sharpe→stage_c_sharpe)=-0.361、18 RUN 累積 Stage C pass=0 | median sign 検査 → curve-fit 選好 → 赤字許容 → Stage C で剥落 | profit_safe_pfr mode で Run 75 において (a) Stage B pass 数 が 10 未満に崩壊、(b) Stage B 通過群 median total_pnl が依然 negative、(c) Stage C trade_sharpe median が legacy より悪化 → いずれか発生で仮説否定 | profit_safe_pfr mode Run 75 で Stage B 通過群 **median_oos_total_pnl ≥ 0** ∧ **Stage C trade_sharpe median ≥ legacy 18 RUN 平均** ∧ **Stage B pass ≥ 10** を全て満たせば cycle 23-24 で再現確認、3 RUN 比較で default 化判断 | **APPROVED (with minor MODIFY)** |

## 却下された提案

| # | 提案 | 却下理由 |
|---|------|---------|
| #2 | clause 使用率ペナルティ段階導入 (active_clause 1.01 対策) | cycle 22 では交絡要因が増え、#1 (profit_safe_pfr) の因果検証を汚す (Codex)。保留 TODO 化は妥当 |
| #4 | cross-pair lane 復活 / multi-instrument 検討 | 守備範囲超過かつ変更規模大、#1 反証前に進めるべきでない (Codex) |

## 保留事項（合議収束ルールにより次 Run 検証申し送り）

| # | 仮説 | 最小変更案 | 検証条件 |
|---|------|----------|---------|
| H-clause | active_clause 1.01 collapse は GA selection dynamics 由来 (clause 2 個探索を妨害) | `clause_usage_penalty` を complexity 軸に追加 (active_clause が 1 の個体に小 penalty) | cycle 22 (profit_safe_pfr) で Stage B 通過群の active_clause 分布変化を観測。1 collapse 維持なら H-clause 仮説支持 → 次サイクル TODO 化 |
| H-monitor | FX 制約 (overnight_hold / long_short / spread_cost / swap_cost / net_pnl_after_cost) が監査経路なしで INCONCLUSIVE | TradeRecord / archive schema に 5 列を追加して必須出力化 | **設計定義のみを improvement-plan に固定 (下記 §H-monitor 設計仮固定)**。実装は次サイクル以降 |
| H-cross-pair | EUR_JPY 単独 18 RUN で regime 擦り続け、汎化欠如 | `--instrument-list "EUR_JPY,USD_JPY"` で multi-instrument mode | #1 反証 (Run 75) 結果次第。profit_safe_pfr 効果不発なら cross-pair で別仮説検証 |

## H-monitor 設計仮固定 (Codex MODIFY 反映: 設計のみ並走)

cycle 22 では実装しないが、FX 監査指標出力化の設計定義を以下に固定する。次サイクル以降の TODO 化で本設計を流用。

### 列定義

| 列名 | 型 | 算出点 | 計算式 / 説明 | fail 条件 (= 禁止事項違反兆候) |
|------|-----|--------|---------------|--------------------------------|
| `overnight_hold_ratio` | float [0, 1] | trade レベル集計 → 個体レベル | `count(trade.holding_duration >= 1 day) / count(trade)` | `>= 0.20` で禁止事項 7 (オーバーナイト保有前提) 兆候 → warn / Critical flag |
| `long_pnl` | float | trade direction='long' のみで集計 | `sum(trade.net_pnl WHERE direction='long')` | `long_pnl < 0 AND short_pnl > 0 AND short_pnl >= 1.5 * abs(long_pnl)` で「ショートで見かけ改善」兆候 |
| `short_pnl` | float | trade direction='short' のみで集計 | `sum(trade.net_pnl WHERE direction='short')` | 同上 (ロング側を併せて判定) |
| `spread_cost` | float | trade レベル集計 → 個体レベル | `sum(trade.spread_cost)` (broker spread モデル由来) | `total_pnl > 0 AND spread_cost == 0` で「コスト未反映」兆候 → Critical |
| `swap_cost` | float | overnight 保有時のみ | `sum(trade.swap_cost)` (broker swap モデル由来) | `overnight_hold_ratio > 0 AND swap_cost == 0` で「スワップ未反映」兆候 → Critical |
| `net_pnl_after_cost` | float | trade レベル集計 → 個体レベル | `sum(trade.gross_pnl - trade.spread_cost - trade.swap_cost - trade.commission)` | `net_pnl_after_cost < 0 AND fitness_pen > 0` で「見かけの数値最適化」兆候 → Critical |

### 算出点

- TradeRecord 型 (既存 `src/zenigame_fx/.../trade.py`) に上記 5 フィールドを追加 (or 算出 method)
- `stage_bc_evaluator` で個体集計時に metadata payload へ書き込み
- archive Parquet 書き出し時 (`genome_entry_schema_version` bump) に上記列追加

### fail 条件 (= 禁止事項違反検知ルール)

- `overnight_hold_ratio >= 0.20` → 禁止事項 7 違反 candidate → log warning + Stage B 通過 disqualify (opt-in flag)
- `spread_cost == 0 AND total_pnl > 0` → コスト未反映 → Critical (即 fail)
- `swap_cost == 0 AND overnight_hold_ratio > 0` → スワップ未反映 → Critical (即 fail)
- `net_pnl_after_cost < 0 AND fitness_pen > 0` → 見かけ最適化 → Critical (即 fail)

## 次フェーズへの申し送り

- **Phase C-1**: T099 既存詳細設計 (devnotes/20260513-1915-todo-pr5-stage-b-pfr-only/detailed-design.md) を改変して `profit_safe_pfr` mode を実装する詳細設計を作成
  - Phase5Config + StageGateConfig 拡張
  - `evaluate_stage_b` で `profit_safe_pfr` 分岐を追加 (条件: pfr >= 0.4 ∧ median_oos_total_pnl >= 0 ∧ (trade_sharpe_stage_b > 0 ∧ n_fold_effective >= 20))
  - `median_oos_total_pnl` 新規集計 (fold loop で total_pnl 集計 → median 計算)
  - archive schema bump (`genome_entry_schema_version` += 1) → `median_oos_total_pnl` 列追加
  - CLI `--stage-b-gate-kind {legacy, profit_safe_pfr}`
  - tests: helper / integration / config (~20 件)

- **Phase 3 (実装)**: T099 worktree で実装 → tests → Codex impl-review → commit → main merge → TODO close

- **Phase 4 (Run 75)**: `--stage-b-gate-kind profit_safe_pfr --instrument EUR_JPY --population-size 96 --generations 60 --mutation-rate 0.5 --seed 60 --max-workers 2`

- **cycle 23 Run 76**: seed=61 で **legacy** 再現確認 (`--stage-b-gate-kind legacy`)、Run 75 効果が profit_safe_pfr に起因するか seed 効果か判別
- **cycle 24 Run 77**: seed=62 で **profit_safe_pfr** 再現確認
- **cycle 25 以降**: cycle 22-24 の 3 RUN 比較で default 化判断、以降 seed sweep
