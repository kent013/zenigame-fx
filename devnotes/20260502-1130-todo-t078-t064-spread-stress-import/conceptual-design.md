# 概念設計 (skeleton): T078 — T064 apply_spread_stress 重複定義解消 + TradeRecord schema 拡張

**作成日時**: 2026-05-02 11:30 JST
**起源**: cascade port v2 Phase 2 配線 handoff § 6 残作業 6 (T064 follow-up 申し送り)
**性質**: schema 変更 (= TradeRecord に spread_cost field 追加) + 重複定義解消 + adapter 設計
**位置付け**: cascade port v2 follow-up (= Stage C spread stress 評価の正式実装)
**status**: **skeleton (= 後続セッションで zenigame-fx-alpha-design による Codex review で詳細化)**

---

## 背景・課題

### 現状

`src/alpha_factory/stage_bc_evaluator.py` L1029-1049 に `apply_spread_stress` 関数の **skeleton (= NotImplementedError raise)** が定義:

```python
def apply_spread_stress(
    trades: tuple[TradeRecord, ...],
    multiplier: float,
) -> tuple[TradeRecord, ...]:
    raise NotImplementedError(
        "apply_spread_stress requires TradeRecord.spread_cost field "
        "(T070 Phase 2 申し送り)"
    )
```

一方、 `src/backtest/session_block.py` L502-538 に **正式実装** が存在:

```python
def apply_spread_stress(
    trades: Sequence[Trade],
    multiplier: Decimal,
) -> tuple[Trade, ...]:
    # 正式実装、 spread_cost を multiplier 倍にして pnl 再計算
```

### 型不整合

- `TradeRecord` (`src/alpha_factory/canonical_metrics.py` L227): `pnl_net / session_bucket / business_day_index` 等、 alpha_factory 専用、 **`spread_cost` field なし**
- `Trade` (`src/broker/orders` 経由): `pnl / spread_cost / holding_cost` 等、 broker / backtest 共通

= 単純な import 置換不可。 TradeRecord に spread_cost field を追加するか、 adapter で TradeRecord ↔ Trade 変換が必要。

### Stage C 評価への影響

`stage_bc_evaluator.py` L937-944 で `spread_stress_supported=True` の経路で `apply_spread_stress` 呼び出し → 現状は NotImplementedError。 Stage C で spread stress 評価が必須なら、 本 follow-up が **smoke 通過の前提**。 ただし `spread_stress_supported=False` で gate されているため、 Phase 1 では未到達経路。

---

## 改善アイデア

### 改訂 1: TradeRecord に spread_cost / holding_cost field 追加

```python
@dataclass(frozen=True)
class TradeRecord:
    entry_time_utc: datetime
    exit_time_utc: datetime
    pnl_net: float
    session_bucket: SessionBucket
    business_day_index: int
    is_session_close_drop: bool
    is_negative_equity_drop_open: bool
    # 新規追加
    spread_cost: float = 0.0      # T078: spread stress 用
    holding_cost: float = 0.0     # T078: 整合性のため (= holding_cost_total への接続)
```

= default 0.0 で既存 caller 互換性維持。

### 改訂 2: stage_bc_evaluator.py の skeleton を session_block.apply_spread_stress 経由に置換

option 1 (= 直接 import + adapter):
```python
from src.backtest.session_block import apply_spread_stress as _apply_spread_stress_broker

def apply_spread_stress(
    trades: tuple[TradeRecord, ...],
    multiplier: float,
) -> tuple[TradeRecord, ...]:
    # TradeRecord → Trade adapter (省略)
    # _apply_spread_stress_broker 呼出
    # Trade → TradeRecord 逆 adapter
    ...
```

option 2 (= TradeRecord に直接適用するロジックを展開):
```python
def apply_spread_stress(
    trades: tuple[TradeRecord, ...],
    multiplier: float,
) -> tuple[TradeRecord, ...]:
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

option 2 が単純で type 整合的、 推奨。

### 改訂 3: session_block.py 側の実装は不変 (= broker 経路で使用継続)

session_block.apply_spread_stress は backtest engine 経路で使用、 stage_bc_evaluator はゲノム評価経路 (= TradeRecord 系) で使用、 と用途分離。

### 改訂 4: spread_cost 計算経路の確立

TradeRecord に spread_cost field を追加するだけでは値が入らない。 trade 生成経路 (= backtest engine) で `Trade.spread_cost → TradeRecord.spread_cost` の伝搬を確立する必要あり。

---

## 期待効果

- **Stage C spread stress 評価が正式に動作可能** (= live_criteria 達成判定の堅牢化)
- **設計と実装の乖離解消** (= NotImplementedError raise → 正式実装)
- **smoke 5 Run の `spread_stress_supported=True` 経路通過** (= cascade port v2 完全完了の前提条件)

---

## 実装方針 (概要)

### 変更ファイル

1. `src/alpha_factory/canonical_metrics.py`: TradeRecord に spread_cost / holding_cost field 追加
2. `src/alpha_factory/stage_bc_evaluator.py` L1029-1049: skeleton 削除 + option 2 実装に置換
3. trade 生成経路 (= 場所未確定、 要調査): TradeRecord 構築時に spread_cost / holding_cost 伝搬
4. `src/backtest/session_block.py`: touch なし
5. tests/: TradeRecord 構築箇所で spread_cost / holding_cost を渡すように更新

### 影響範囲

- TradeRecord caller 全件 (= grep 必要)、 default 0.0 で既存互換性は維持
- trade 生成経路 (= backtest engine → TradeRecord 構築) の詳細調査が必要

---

## 制約・前提

- TradeRecord field 追加で既存 caller を壊さない (= default 0.0)
- session_block.apply_spread_stress (= broker 経路) は touch しない
- Phase 2 切替前に完了させる (= smoke 5 Run で spread_stress_supported=True 経路通過のため)

---

## スコープ外

1. session_block.py 側の API 変更 (= broker 経路は不変)
2. Trade ↔ TradeRecord adapter の汎用化 (= 本 TODO は spread_stress に特化)
3. holding_cost stress (= 本 TODO は spread_stress のみ、 holding_cost stress は別 TODO)

---

## リスク

| リスク | 影響 | 緩和 |
|---|---|---|
| TradeRecord field 追加で既存 caller の dataclass 構築が壊れる | 中 | default 0.0 で互換性維持、 mypy で全件確認 |
| trade 生成経路で spread_cost が 0.0 のまま伝搬される (= stress 効果ゼロ) | 高 | 本 TODO で trade 生成経路を改造、 spread_cost 値を伝搬 |
| `replace(t, ...)` で frozen dataclass の immutability 違反検出 | 低 | dataclasses.replace は frozen 互換 |
| smoke 5 Run で spread_stress 経路を validate できない (= calibration data 不在) | 中 | 値計算の test を充実、 数値検証は smoke 後 |

---

## 参考資料

- handoff: `devnotes/20260502-0710-cascade-port-v2-phase2-complete-handoff/handoff.md` § 6 残作業 6
- T064 detailed-design: `devnotes/20260501-2235-cascade-port-T064-complete-handoff/handoff.md`
- T070 detailed-design: `devnotes/20260502-0247-cascade-port-T070-complete-handoff/handoff.md`
- 実装: `src/alpha_factory/stage_bc_evaluator.py` L1029-1049 (skeleton)
- 関連: `src/backtest/session_block.py` L502-538 (正式実装、 broker 経路)
- TradeRecord: `src/alpha_factory/canonical_metrics.py` L226-249

---

## skeleton から本格設計への昇格手順

1. `zenigame-fx-alpha-design` skill 起動 (= topic="t078-spread-stress-import")
2. trade 生成経路の詳細調査 (= backtest engine → TradeRecord 構築の path)
3. spread_cost 伝搬先の caller 全件マトリクス
4. Codex 概念 + 詳細設計レビュー → APPROVED まで
5. `zenigame-fx-implement` で実装 (worktree todo/T078)
