# 詳細設計: max_drawdown=0 多発調査

親: [conceptual-design.md](conceptual-design.md)

## 変更箇所

| ファイル | 変更 |
|---------|------|
| `scripts/alpha_factory/inspect_equity_curve.py` | 新規 CLI (Run + 個体名指定で equity dump) |
| `tests/backtest/test_metrics.py` | 再現テスト追加 (bug 検出時のみ) |

## 調査手順

1. Run 22 best 個体の trades + equity_curve を再生成
2. equity_curve の min/max/peak-to-trough を可視化
3. compute_metrics の dd 計算 logic を line-by-line で trace
4. dd=0 が物理的に成立した条件を documentation

## DoD

- [ ] dd=0 多発の根本原因を特定 (bug or 設計通り)
- [ ] bug の場合は test 追加 + 修正
- [ ] 設計通りの場合は docs/alpha_factory/clause-architecture.md に明記
