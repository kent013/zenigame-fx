# Phase 4f 詳細設計 — DSL 式評価 & DslStrategy

**作成**: 2026-04-18 01:30 JST
**状態**: DRAFT

---

## 1. 目的

戦略ロジックを **データ駆動の式木** として表現し、後続フェーズで GA による自動進化を可能にする。今段階（Phase 4f）ではまず DSL の定義・評価・Strategy ラッパーを作り、手書きの式で動くことを確認する。

---

## 2. スコープ

**含む**:
- 式木の AST（dataclass ベース + dict への双方向変換）
- 参照価格・テクニカル指標のプリミティブ（close, high, low, open, volume, spread, sma, ema, stddev, rsi）
- 二項演算・比較・論理演算・if-then-else
- 評価器（バー履歴を持つ `EvalContext`、indicator 計算キャッシュ）
- Genome（entry/exit のペア）と DslStrategy ラッパー
- Bollinger / MA Crossover 相当を DSL で書き直したサンプル
- テスト

**含まない（Phase 4g 以降）**:
- GA のランダム生成・交叉・突然変異
- 適応度評価 / 淘汰
- LLM-Guided Mutation
- アーカイブ / ローリング

---

## 3. AST 定義

```python
@dataclass(frozen=True)
class Const: value: Decimal
@dataclass(frozen=True)
class Var: name: str                       # "close" | "open" | "high" | "low" | "bid_close" | "ask_close" | "spread" | "volume"
@dataclass(frozen=True)
class Indicator: kind: str; window: int; of: Expr  # sma/ema/stddev/rsi
@dataclass(frozen=True)
class BinOp: op: str; lhs: Expr; rhs: Expr  # +, -, *, /
@dataclass(frozen=True)
class Compare: op: str; lhs: Expr; rhs: Expr  # <, <=, >, >=, ==
@dataclass(frozen=True)
class Logical: op: str; args: tuple[Expr, ...]  # and, or, not
@dataclass(frozen=True)
class IfThenElse: cond: Expr; then: Expr; otherwise: Expr

Expr = Const | Var | Indicator | BinOp | Compare | Logical | IfThenElse
```

`to_dict()` / `from_dict()` で dict ↔ AST 変換（JSON シリアライズ用。GA archive に保存する）。

---

## 4. 評価器

```python
class EvalContext:
    bars: list[PriceBar]      # 累積履歴
    i: int                    # 現在のバー index
    _cache: dict[Hashable, Decimal]  # (kind, window, of_key, i) でメモ化

def evaluate(expr: Expr, ctx: EvalContext) -> Decimal | bool: ...
```

- `Var`: 現在バーの属性を返す
- `Indicator`: `of` を各過去バーで評価し、`window` 本で集計。**`of` が `Var("close")` の場合だけ最適化経路あり**。他は素朴に再計算
- `BinOp`: 数値演算
- `Compare` / `Logical`: bool
- `IfThenElse`: cond が bool に評価され、true/false で then/otherwise

型チェックは弱く、式が正しい型で組まれていることを前提とする。誤った組合せは runtime で例外を投げる。

**warmup**: Genome の entry/exit を走査して使用された最大 window を返すヘルパ `max_lookback(expr) -> int` を提供。

---

## 5. Genome / DslStrategy

```python
@dataclass(frozen=True)
class Genome:
    name: str
    units: int
    entry_long: Expr
    entry_short: Expr
    exit_long: Expr
    exit_short: Expr

class DslStrategy:
    def __init__(self, genome: Genome) -> None: ...
    def warmup_bars(self) -> int: ...
    def on_bar(self, bar, snapshot) -> list[OrderSignal]: ...
```

ロジック（既存 Bollinger 実装と同じ契約）:
- ポジション無しなら entry_long / entry_short を評価（true なら open）
- 保有中なら exit_long/short を評価（true なら close）
- 1 ポジション制約（MVP）

---

## 6. サンプル Genome

既存戦略を DSL で書き直したサンプルを `src/dsl/samples.py` に置く:

- `bollinger_genome(window=20, k=2.0, units=10000)`: entry_long = close < sma(window)-k*stddev(window)、exit_long = close >= sma
- `ma_crossover_genome(fast=5, slow=20, units=10000)`: entry_long = sma(fast) > sma(slow)、exit_long = sma(fast) <= sma(slow)

---

## 7. ディレクトリ構成追加

```
src/dsl/
├── __init__.py
├── ast.py              # dataclass の Expr ノード
├── serialize.py        # to_dict / from_dict
├── eval.py             # EvalContext, evaluate, max_lookback
├── genome.py           # Genome, DslStrategy
└── samples.py          # bollinger_genome / ma_crossover_genome
tests/dsl/
├── __init__.py
├── test_eval.py
├── test_serialize.py
└── test_dsl_strategy.py
```

---

## 8. 完了判定

1. `uv run pytest` green
2. `uv run ruff check` green
3. DslStrategy で手書き戦略と**同じ振る舞い**ができる（Bollinger 相当の式を走らせ、純 Python 実装と同じ trade 件数になるサニティテスト）

---

## 9. 先送り（Phase 4g 以降）

- ランダム式生成（grammar-based / grow / full）
- 交叉（部分木交換）
- 突然変異（サブツリー置換、定数摂動）
- 淘汰と集団管理
- NSGA-II 多目的最適化
- 適応度計算と stage gate
- ゲノムアーカイブ（Parquet）
- LLM ガイド変異
