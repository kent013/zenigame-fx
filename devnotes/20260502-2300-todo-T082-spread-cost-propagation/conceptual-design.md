# 概念設計 (skeleton): T082 — TradeRecord.spread_cost / holding_cost 伝搬経路配線

**作成日時**: 2026-05-02 23:00 JST
**起源**: T078 (commit `857eb82`) スコープ外残作業 = trade 生成経路で spread_cost / holding_cost が default 0.0 のままで silent no-op risk
**性質**: 配線追加 (= backtest engine → TradeRecord 構築時の spread_cost / holding_cost 伝搬)
**位置付け**: T078 follow-up + spread stress 評価の運用効果確立
**status**: **skeleton (= 後続セッションで zenigame-fx-alpha-design による Codex review で詳細化)**

---

## 背景・課題

### T078 で確立した状態

T078 (`commit 857eb82`) で:
- TradeRecord に spread_cost / holding_cost field 追加 (= default 0.0)
- stage_bc_evaluator.apply_spread_stress 正式実装 (= broker 経路と代数等価)

= **schema は揃ったが、 値が default 0.0 のままで silent no-op**。

### 配線が必要な経路

`src/broker/orders.Trade` (= broker 経路、 Decimal 型、 spread_cost/holding_cost 値あり) から `src/alpha_factory/canonical_metrics.TradeRecord` (= alpha_factory 経路、 float 型、 spread_cost/holding_cost default 0.0) への **値伝搬** が必要。

つまり backtest engine 完了後、 `Trade(broker)` から `TradeRecord(alpha_factory)` を構築する箇所で:
```python
TradeRecord(
    ...
    spread_cost=float(broker_trade.spread_cost),   # 追加伝搬
    holding_cost=float(broker_trade.holding_cost), # 追加伝搬
)
```

### 影響

T078 で正式実装した apply_spread_stress が効果を発揮するには本配線が必須。 spread_cost が 0.0 では multiplier > 1.0 でも何も変わらない (= silent no-op)。

---

## 改善アイデア

### 改訂 1: Trade → TradeRecord 変換箇所の特定 + 伝搬配線

具体的には:
1. backtest engine が `Trade(broker)` を生成する箇所を grep
2. `Trade(broker)` から `TradeRecord(alpha_factory)` へ変換する adapter 関数 (= 既存 or 新規) を確認
3. adapter で spread_cost / holding_cost を float 化して伝搬

### 改訂 2: caller 側 WARN/FAIL ガード追加 (= T078 [Suggestion] 1 反映)

`apply_spread_stress(trades, multiplier)` の caller (= run_ga.py / Stage C 評価) で:
- multiplier > 1.0 かつ `sum(t.spread_cost for t in trades) == 0` の場合 → WARN log (= 設定不整合の検出)
- 必要なら fail-closed (= ValueError) も option (= smoke 後決定)

---

## 期待効果

- **spread stress 評価が実効的に機能** (= Stage C で multiplier=1.5 適用時に実際に pnl が下がる)
- **silent no-op 解消** (= 設定不整合の早期検出)
- **smoke 5 Run で spread stress 通過判定の calibration data 取得可能**

---

## 実装方針 (概要)

### 変更ファイル候補

1. backtest engine 系 (= 詳細調査要、 `src/backtest/engine.py` or 関連):
   - Trade(broker) → TradeRecord(alpha_factory) 変換箇所で spread_cost / holding_cost 伝搬
2. `src/alpha_factory/stage_bc_evaluator.py`:
   - apply_spread_stress caller 側で WARN/FAIL ガード追加 (= [Suggestion] 1 取込)
3. tests/:
   - 配線経路の test (= broker Trade に spread_cost を入れて TradeRecord に伝搬するか)
   - WARN/FAIL ガードの test

### 影響範囲

- backtest engine の Trade 変換経路 (= 詳細調査要)
- T078 の silent no-op 解消経路の確立

---

## 制約・前提

- T078 で確立した型差異 (= float vs Decimal) は維持
- 単純な float() 変換で誤差は許容範囲 (= relative 1e-9 以内、 T078 broker 等価性 test で確認済)
- 既存 backtest engine の output が `Trade(broker)` であることを前提

---

## スコープ外

1. broker 側 spread_cost 計算ロジックの改善 (= 別 TODO)
2. holding_cost 計算ロジックの改善 (= 別 TODO)
3. spread_cost / holding_cost に基づく fitness 関数の改造 (= 別 TODO)

---

## リスク

| リスク | 影響 | 緩和 |
|---|---|---|
| Trade → TradeRecord 変換箇所が複数あり、 一部漏れ | 中 | grep で全件特定、 mypy で型確認、 test で全パターン検証 |
| float() 変換で精度落ち | 低 | T078 で 1e-9 以内確認済、 通常 spread (= 1-10 程度) では実害なし |
| WARN/FAIL ガードで既存 test が壊れる | 中 | smoke 5 Run の calibration data で WARN レベル決定、 fail-closed は別 TODO |

---

## 参考資料

- T078 完了 commit: `857eb82` (= TradeRecord schema 拡張)
- T078 設計: `devnotes/20260502-1130-todo-t078-t064-spread-stress-import/`
- TradeRecord: `src/alpha_factory/canonical_metrics.py` L226-300
- broker Trade: `src/broker/orders.py` L33-56
- stress 関数 (alpha_factory): `src/alpha_factory/stage_bc_evaluator.py` L1029-

---

## skeleton から本格設計への昇格手順

1. zenigame-fx-alpha-design skill 起動 (= topic="t082-spread-cost-propagation")
2. backtest engine の Trade → TradeRecord 変換箇所を grep + Read で全件特定
3. 各変換箇所の field マトリクス作成 (= 既存 field + spread_cost / holding_cost 追加箇所)
4. WARN/FAIL ガードの level / threshold 検討
5. Codex 概念 + 詳細設計レビュー → APPROVED まで
6. zenigame-fx-implement で実装 (worktree todo/T082)
