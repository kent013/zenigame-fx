# 詳細設計 (skeleton): T082 — TradeRecord.spread_cost / holding_cost 伝搬経路配線

**作成日時**: 2026-05-02 23:00 JST
**status**: **skeleton (= 後続セッションで本格化)**

---

## 1. 使命・制約

T078 で導入した TradeRecord.spread_cost / holding_cost field を実値で埋めるため、 backtest engine の Trade(broker) → TradeRecord(alpha_factory) 変換経路に配線追加。

## 2. 概念設計リファレンス

`/Users/ishitoya/repository/zenigame-fx/devnotes/20260502-2300-todo-T082-spread-cost-propagation/conceptual-design.md`

## 3. 改訂対象一覧 (skeleton、 後続詳細化)

| # | 改訂名 | 変更箇所 | 性質 | 優先度 |
|---|---|---|---|---|
| 1 | Trade → TradeRecord 変換箇所の特定 + spread_cost / holding_cost 伝搬 | (= 詳細調査要、 backtest engine 経路) | 配線追加 | High |
| 2 | apply_spread_stress caller 側 WARN/FAIL ガード | stage_bc_evaluator caller | コード追加 | Medium |
| 3 | tests/: 配線経路 + ガード | tests/ | test 追加 | Medium |

## 4. 実装方針 (skeleton)

### 4.1 変換箇所特定 (= 後続詳細化)

```bash
# Trade → TradeRecord 変換箇所を全件 grep
grep -rnE "TradeRecord\(.*entry_time_utc" src/ tests/ scripts/ | head -30
# Trade(broker) を入力に持つ関数を grep
grep -rnE "Trade.*spread_cost|broker_trade" src/ scripts/ | head -30
```

### 4.2 配線追加例

```python
# 変換 helper (新規 or 既存):
def trade_to_trade_record(broker_trade: Trade, ...) -> TradeRecord:
    return TradeRecord(
        ...
        spread_cost=float(broker_trade.spread_cost),
        holding_cost=float(broker_trade.holding_cost),
    )
```

### 4.3 WARN/FAIL ガード

```python
def apply_spread_stress_safe(trades, multiplier, *, on_zero_spread="warn"):
    if multiplier > 1.0 and sum(t.spread_cost for t in trades) == 0:
        if on_zero_spread == "warn":
            logger.warning("apply_spread_stress: all spread_cost==0, silent no-op")
        elif on_zero_spread == "fail":
            raise ValueError("...")
    return apply_spread_stress(trades, multiplier)
```

## 5. 機械検証手順 (skeleton)

```bash
# 配線確認
grep -qE "spread_cost=float" src/backtest/<該当 file>.py || exit 1

# pytest
uv run pytest tests/ -x
```

## 6. テスト計画 (skeleton)

- 配線 test: broker Trade に spread_cost=2.5 入れて、 TradeRecord に 2.5 伝搬されること
- WARN ガード test: spread_cost=0 で multiplier=1.5 → WARN log

## 7. 実装モード

**incremental**

## 8. 後続セッションでの本格化手順

1. backtest engine の Trade 変換箇所詳細調査
2. zenigame-fx-alpha-design で Codex review
3. zenigame-fx-implement で worktree todo/T082
