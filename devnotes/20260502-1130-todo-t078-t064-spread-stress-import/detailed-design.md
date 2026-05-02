# 詳細設計 (skeleton): T078 — T064 apply_spread_stress 重複解消 + TradeRecord schema 拡張

**作成日時**: 2026-05-02 11:30 JST
**status**: **skeleton (= 後続セッションで zenigame-fx-alpha-design による Codex review で詳細化)**
**改訂対象**: `src/alpha_factory/canonical_metrics.py` (TradeRecord schema 拡張) + `src/alpha_factory/stage_bc_evaluator.py` (skeleton 削除 + 正式実装) + trade 生成経路 (= 詳細調査要、 backtest engine 関連) + tests/

---

## 1. 使命・制約

cascade port v2 Stage C spread stress 評価の正式実装。 schema 拡張を伴うため、 TradeRecord caller 全件の整合性確認が必要。

## 2. 概念設計リファレンス

`/Users/ishitoya/repository/zenigame-fx/devnotes/20260502-1130-todo-t078-t064-spread-stress-import/conceptual-design.md`

## 3. 改訂対象一覧 (skeleton、 後続詳細化)

| # | 改訂名 | 変更箇所 | 性質 | 優先度 |
|---|---|---|---|---|
| 1 | TradeRecord に spread_cost / holding_cost field 追加 | `src/alpha_factory/canonical_metrics.py` L226-249 | schema 拡張 | 高 |
| 2 | stage_bc_evaluator.py skeleton 削除 + 正式実装 (option 2) | `src/alpha_factory/stage_bc_evaluator.py` L1029-1049 | 関数本体置換 | 高 |
| 3 | trade 生成経路で spread_cost / holding_cost 伝搬 | (= 詳細調査要、 backtest engine → TradeRecord 構築 path) | 配線追加 | 高 |
| 4 | TradeRecord caller 全件確認 | (= 全 caller、 default 0.0 で互換性維持) | 確認 | 中 |
| 5 | 既存 test 更新 | tests/ で TradeRecord 構築箇所 | test 修正 | 中 |

## 4. 詳細実装方針 (skeleton、 後続詳細化)

### 4.1 TradeRecord 拡張

```python
# Before
@dataclass(frozen=True)
class TradeRecord:
    entry_time_utc: datetime
    exit_time_utc: datetime
    pnl_net: float
    session_bucket: SessionBucket
    business_day_index: int
    is_session_close_drop: bool
    is_negative_equity_drop_open: bool

# After
@dataclass(frozen=True)
class TradeRecord:
    entry_time_utc: datetime
    exit_time_utc: datetime
    pnl_net: float
    session_bucket: SessionBucket
    business_day_index: int
    is_session_close_drop: bool
    is_negative_equity_drop_open: bool
    spread_cost: float = 0.0       # T078 追加
    holding_cost: float = 0.0      # T078 追加 (整合性確保)
```

### 4.2 apply_spread_stress 正式実装

```python
# Before (L1029-1049)
def apply_spread_stress(
    trades: tuple[TradeRecord, ...],
    multiplier: float,
) -> tuple[TradeRecord, ...]:
    raise NotImplementedError(...)

# After
def apply_spread_stress(
    trades: tuple[TradeRecord, ...],
    multiplier: float,
) -> tuple[TradeRecord, ...]:
    if multiplier < 1.0 or not math.isfinite(multiplier):
        raise ValueError(f"multiplier must be >= 1.0 and finite, got {multiplier}")
    delta_factor = multiplier - 1.0
    return tuple(
        replace(
            t,
            pnl_net=t.pnl_net - t.spread_cost * delta_factor,
            spread_cost=t.spread_cost * multiplier,
        )
        for t in trades
    )
```

### 4.3 trade 生成経路の調査と配線

**要詳細調査**: backtest engine → TradeRecord 構築の path を grep で特定し、 Trade.spread_cost / holding_cost を TradeRecord.spread_cost / holding_cost に伝搬する経路を確立。

## 5. 機械検証手順 (skeleton)

```bash
# TradeRecord schema 確認
grep -qE "spread_cost: float" src/alpha_factory/canonical_metrics.py \
  || { echo "FAIL: TradeRecord schema 拡張未完"; exit 1; }

# stage_bc_evaluator.py NotImplementedError 削除確認
! grep -qE "raise NotImplementedError.*spread_cost" src/alpha_factory/stage_bc_evaluator.py \
  || { echo "FAIL: skeleton 残存"; exit 1; }

# pytest + mypy
uv run pytest tests/ -x -k "spread_stress or canonical_metrics or stage_bc"
uv run mypy src/
```

## 6. テスト計画 (skeleton)

- 新規 test: `apply_spread_stress` の代数検証 (= multiplier=1 no-op、 multiplier=2 で spread_cost 倍、 pnl_net 減少)
- 新規 test: TradeRecord に spread_cost / holding_cost を渡す invariant 確認
- 既存 test 更新: TradeRecord 構築箇所で必要に応じて spread_cost / holding_cost を 0 渡し

## 7. リスク (= 概念設計と同じ)

## 8. 実装モード

**incremental** (= schema 変更を含むが backward compat 維持、 worktree todo/T078)

## 9. 後続セッションでの本格化手順

1. zenigame-fx-alpha-design skill 起動
2. trade 生成経路の詳細調査
3. spread_cost 伝搬先の全 caller マトリクス
4. Codex 概念 + 詳細レビュー → APPROVED
5. zenigame-fx-implement で実装
