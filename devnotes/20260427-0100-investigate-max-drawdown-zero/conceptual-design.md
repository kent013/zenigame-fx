# 概念設計: max_drawdown=0 多発調査

**起点監査**: [audit-codex.md §2 (6)](../20260427-0050-bug-hunt-audit/audit-codex.md) — INCONCLUSIVE

## 仮説

Run 22 best 個体: trade_count=68 / max_drawdown_pct=0.0。68 trade で完全に dd=0 は通常起こらない。equity_curve 計算 / dd 検出 logic に bug がある可能性。

## 検証済み事実

- compute_metrics ([backtest/metrics.py:133-144](../../src/backtest/metrics.py#L133-L144)) で max_drawdown_pct を計算
- Run 16 でも max_drawdown 0 が頻発、cycle 7 yaml 変更後も継続
- Run 20 では mission_score 計算用の max_drawdown_frac は 0.014-0.05 (小さい) だが positive

## 解決方針

調査スクリプトで Run 22 best 個体の equity_curve を再構築し、dd 計算の境界条件を確認:
- equity_curve が空 / 1 点しかない / position 開かれず終了 etc.
- max_drawdown 算出 path で early exit / divide by zero / nan 返却が起きていないか

## 成功判定

- equity_curve dump で「dd=0 が物理的に成立する条件」を特定
- bug の場合は `tests/backtest/test_metrics.py` に再現テスト追加 → fix
- 設計通りの場合は理由を docs に明記
