# 概念設計: Stage C stress の cost-robustness 化 (P2)

## 背景
R83 で mission 達成（live_criteria 全達成 43 個体）も R84（seed=69）で mission=0 = seed-lucky と判明。さらに整合性問題が確定: Stage C の「spread×1.5 stress」は `max_spread_bps`（spread フィルタ閾値、broker が spread>閾値 の trade を skip）を 1.5 倍に緩めるだけで per-trade コストを増やさず、stress_pnl_degradation が全個体 0。「stress」が名前通りの役割（高コスト環境での頑健性検証）を果たしていない。

## 目的
Stage C stress を「フィルタ緩和」から「実効スプレッド（約定コスト）の割増」に変え、cost robustness を実際に検証する。これにより mission 達成個体が真に cost-robust であることを保証する（思考原則: 機能の名前に立ち返れ）。

## スコープ
- broker / backtest に `spread_cost_multiplier`（default 1.0）を導入。
- stress backtest で realized fill（entry/exit 約定）の実効スプレッドを multiplier 倍に広げる（adverse 方向）。
- fill 経路は numba kernel（本番 engine=kernel）と MockBroker（fail-safe）の 2 系統 → 両方配線必須。
- MTM / margin 判定は両経路とも生価格（realized fill のみ stress、parity 維持）。
- Stage C stress 経路で multiplier を 1.5 に設定。

## 非目的
- 通常 backtest（Stage A/B/base-C）の挙動変更（default 1.0 で完全不変）。
- live_criteria 閾値変更（mission は seed 脆弱のため凍結）。
- seed variance 対処（別レーン）/ cross-pair gate 昇格（P3、将来）。

## 期待効果
- stress_pnl_degradation が非ゼロ化し、cost fragile な個体が Stage C stress で脱落。
- mission 達成個体が真に cost-robust になる。

## 使命・禁止事項整合
cost stress を名前通りに直す整合性修正。閾値緩和（禁止4）でなく cost 要件の厳格化方向。default 1.0 で通常経路不変。

## 詳細設計
`detailed-design.md` 参照（Codex design-review APPROVED, Round 2）。
