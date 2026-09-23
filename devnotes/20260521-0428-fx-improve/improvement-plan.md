# 最終改善計画: Run 84 → Run 85

## 合議ステータス: P2 方針は cycle 2 consensus + cycle 3 両分析で確定（CONSENSUS、design-review は cycle 3 Phase C で実施予定）

## 背景
- cycle 2 で H84 REJECTED: R83 の mission 達成（seed=68, 43個体）は seed-lucky で再現せず（R84 seed=69 で mission=0）。seed variance 極端（Stage B: R82=941/R83=436/R84=62）。
- 確定整合性問題: Stage C の「spread×1.5 stress」は max_spread_bps（spread フィルタ閾値、broker が spread>閾値 の trade を skip; src/broker/mock.py:165-208）を緩めるだけで per-trade コストを増やさず、stress_pnl_degradation が全個体 0。「stress」が名前通りの cost robustness 検証を果たしていない。
- fill は bid/ask 約定（long entry=ask.open, short entry=bid.open, long exit=bid, short exit=ask）で spread cost は自然発生するが、stress はこの実効スプレッドを広げていない。

## 確定施策（R85）
| # | 施策名 | 内容 | 変更対象 | 優先度 | 変更分類 | target_metric | failure_mode | causal_path | falsification | success_criterion |
|---|--------|------|---------|--------|---------|--------------|-------------|------------|---------------|-------------------|
| P2 | Stage C stress の cost-robustness 化 | broker に `spread_cost_multiplier`（default 1.0）を追加し、stress backtest で実効スプレッド（約定コスト）を `spread_stress_multiplier`(1.5) 倍に広げる。閾値緩和でなく per-trade コスト増分を PnL に直接反映 | `src/backtest/engine.py`(BacktestConfig), `src/broker/mock.py`(fill 価格), `src/alpha_factory/stage_gate.py`(stress 経路) | Critical | Structural（整合性修正） | 全 live_criteria の妥当性（cost robust な mission 個体のみ通過） | Stage C stress が cost を増やさず stress_pnl_degradation 全件 0 | broker fill 時に adverse 方向へ (m-1)×half_spread 上乗せ → 往復 spread cost が m 倍 → cost 増が PnL に反映 | P2 導入後も stress_pnl_degradation が 0 のまま（実装/配線不整合） | R85 で stress_pnl_degradation が多数個体で >0、stress 下の Stage C 通過が真の cost robust 個体に限定される |

## 設計詳細
`detailed-design.md` 参照（Codex design-review 未実施 → cycle 3 Phase C で実施）。

## 保留事項（将来サイクル）
| # | 仮説 | 最小変更案 | 検証条件 |
|---|------|----------|---------|
| seed variance | Stage A/B が seed で 7-15 倍変動 = GA 探索不安定 | multi-seed 評価 / population 安定化 | P2 と直交（別レーン）。mission 率の区間推定で「運か再現性か」を統計更新 |
| P3 cross-pair | graduation=0 は ii_lite shadow-only | ii-lite 計測可能化→段階 gate 昇格 | graduation 配線後に多ペア汎化を要求 |

## 使命・禁止事項チェック
P2 は cost stress を「名前通り」に直す整合性修正。閾値緩和（禁止4）ではなく cost 要件の厳格化方向。default 1.0 で通常経路（Stage A/B/base-C）は挙動不変。✅

## 次フェーズへの申し送り
- cycle_focus = `ga_improvements`。
- Phase C で P2 の detailed-design を Codex design-review → 実装（worktree）→ R85 で検証。
- **重要**: spread_cost_multiplier は default 1.0 必須（通常 backtest の挙動を変えない）。stress 経路のみ 1.5 を設定。fill 価格ロジックは PnL に直結するため Codex review で off-by-one / 符号 / long-short 対称性を重点確認。
