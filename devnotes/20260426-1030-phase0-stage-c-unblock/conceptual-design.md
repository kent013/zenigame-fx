# Phase 0 / T041 — Stage C max_spread_bps 設定（概念設計）

**起点監査**: [audit-claude.md](../20260426-1010-ga-audit-r16/audit-claude.md) / [audit-codex.md](../20260426-1010-ga-audit-r16/audit-codex.md) / [audit-codex-round-2.md](../20260426-1010-ga-audit-r16/audit-codex-round-2.md)

## 仮説

**Stage C は spread_stress_skipped 理由で常時 fail している**。Run 1〜16 で Stage C pass=0 はバグでなく仕様（gate 閉塞）。

## 検証済み事実

[stage_gate.py:630-632](../../src/alpha_factory/stage_gate.py#L630-L632):
```python
if backtest_config.max_spread_bps is None:
    stress_payload["skipped"] = True
    reasons.append("spread_stress_skipped")
```

[config.py:76](../../src/alpha_factory/config.py#L76): `max_spread_bps: Decimal | None = None`、yaml override なし。

## 北極星制約との接続

AGENTS.md 絶対制約「スワップ・スプレッドを fitness に反映（見かけの PnL ではなく純利益）」に対し、現状は spread/swap が一切反映されていない。**Stage C を開けることは緩和ではなく規約遵守**。

## 解決方針

`config/alpha_factory/default.yaml` の `backtest:` セクションに `max_spread_bps`（および明示的な `holding_cost_per_day_bps=0`）を追加し、Stage C stress を「論理的に通過可能」な状態にする。値は EUR_JPY tier1 broker (OANDA) の典型 spread 1.0-2.0 pips ≈ 6-12 bps の保守的中央値 **10 bps** を採用。

## 成功判定

- 既存 Stage C テスト全 pass
- 「max_spread_bps 設定済 + 軽量 genome」の場合に Stage C base が `spread_stress_skipped` 理由なしで評価される
- Run 14-16 archive の replay で `spread_stress_skipped` 以外の reason 分布が観測できる

## scope 外

- Sharpe 閾値再校正 (T042 別タスク)
- 通貨ペア別 max_spread_bps override（Phase 1 で検討）

## 詳細設計

[detailed-design.md](detailed-design.md) 参照。
