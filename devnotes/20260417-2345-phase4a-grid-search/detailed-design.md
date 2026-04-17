# Phase 4a 詳細設計 — 複数戦略 & グリッドサーチ

**作成**: 2026-04-17 23:45 JST
**前提**: [../20260417-2300-phase2-detailed-design/detailed-design.md](../20260417-2300-phase2-detailed-design/detailed-design.md)
**状態**: DRAFT

---

## 1. スコープ

Phase 4（改善ループ）を 3 段階に分割し、4a では「**複数戦略の比較と系統的パラメータ探索**」を実装する。

**含む**:
- Strategy Registry（文字列 → Strategy 構築）
- 追加の参考戦略: MA Crossover（順張り）、RSI（逆張り）、Donchian Breakout（順張り）
- グリッドサーチランナー（パラメータ組合せを列挙して並列バックテスト）
- 戦略横断の比較レポート（Markdown + JSON）
- CLI: `scripts/grid_search.py`

**含まない（Phase 4b 以降）**:
- GA による戦略自動探索（Alpha Factory 相当）
- DSL ベースのシグナル合成
- 経済指標カレンダー連携（Phase 4c）
- ウォークフォワード / クロスバリデーション（Phase 4d）

---

## 2. Strategy Registry

```python
# src/strategy/registry.py
_REGISTRY: dict[str, type[Strategy]] = {}

def register(name: str) -> Callable: ...
def build(name: str, **params) -> Strategy: ...
def list_strategies() -> list[str]: ...
```

各戦略クラスに `@register("bollinger")` デコレータを付けて登録。CLI から `--strategy bollinger`, `--strategy ma_crossover` 等で切替可能。

---

## 3. 追加戦略

### 3.1 MA Crossover（`src/strategy/ma_crossover.py`）

- `fast_window` / `slow_window` の 2 本の SMA を計算（mid close ベース）
- `fast > slow` 状態になった瞬間に long、`fast < slow` になったら short（反対サインで反転エントリーも可）
- MVP は「反対シグナルで一度閉じてから反対方向に入り直す」2 段階動作

### 3.2 RSI（`src/strategy/rsi.py`）

- N 期間の RSI（Wilder 平滑化）
- `RSI < oversold_level`（既定 30）→ 逆張り long
- `RSI > overbought_level`（既定 70）→ 逆張り short
- `RSI` が中央（50）を越えたら決済

### 3.3 Donchian Breakout（`src/strategy/donchian.py`）

- N 期間の最高値 / 最安値（bid.high / ask.low ベース）
- close が直近 N 期間最高値を超えたら long、最安値を下回ったら short
- ATR ベースの固定 pips 損切りは Phase 4b で追加（MVP は EOD クローズのみで割り切る）

---

## 4. グリッドサーチ

### 4.1 データモデル

```python
@dataclass(frozen=True)
class GridSearchConfig:
    instrument: str
    start: datetime
    end: datetime
    initial_cash: Decimal
    leverage: int
    strategy_name: str
    parameter_grid: dict[str, list[Any]]   # 例: {"window": [10, 20, 30], "k": [1.5, 2.0, 2.5]}
    parallel: int = 1                      # multiprocessing worker 数。1 = 逐次
```

### 4.2 実行フロー

```
expand parameter_grid into list of dicts (itertools.product)
for each combo:
    build strategy from registry(name, **combo)
    run_backtest(bars, strategy, MockBroker, BacktestConfig(...))
    compute_metrics -> (combo, metrics)
sort by total_pnl desc
write report
```

### 4.3 並列化

- `multiprocessing.Pool` でワーカー並列。各ワーカーは bars のリストとパラメータ dict を受け取り、独立の MockBroker を生成する
- bars は大きいので Pool 間で pickle する。MVP は bars が M1×1 年 ≈ 370,000 件、メモリ上では Decimal 8 本値 + datetime で 1〜2MB 程度。pickle コストは許容範囲
- `parallel=1` ならインプロセス sequential（デバッグ容易）

### 4.4 比較レポート（`src/backtest/comparison.py`）

`reports/grid-searches/grid-YYYYMMDD-HHMMSS/` 以下に:

- `result.md`: config サマリ + 全 run のメトリクス表（PnL 降順 Top 20）
- `result.json`: 全 run の詳細

Markdown テーブル列:
- rank / params / trade_count / win_rate / total_pnl / profit_factor / max_drawdown / max_drawdown_pct / final_equity

---

## 5. CLI（`scripts/grid_search.py`）

```
uv run python scripts/grid_search.py \
    --instrument USD_JPY \
    --from 2025-11-01 --to 2026-04-01 \
    --initial-cash 1000000 \
    --leverage 10 \
    --strategy bollinger \
    --param window=10,20,30 \
    --param k=1.5,2.0,2.5 \
    --param units=5000,10000 \
    --parallel 4
```

`--param name=v1,v2,v3` を複数回指定。値は int/float/str を自動判別（int に変換できるなら int、float に変換できるなら float、それ以外は str）。

---

## 6. ディレクトリ構成の追加

```
src/
├── strategy/
│   ├── registry.py             # ← 新規
│   ├── ma_crossover.py         # ← 新規
│   ├── rsi.py                  # ← 新規
│   └── donchian.py             # ← 新規
└── backtest/
    ├── grid_search.py          # ← 新規
    └── comparison.py           # ← 新規
scripts/
└── grid_search.py              # ← 新規
tests/
├── strategy/
│   ├── test_registry.py        # ← 新規
│   ├── test_ma_crossover.py    # ← 新規
│   ├── test_rsi.py             # ← 新規
│   └── test_donchian.py        # ← 新規
└── backtest/
    └── test_grid_search.py     # ← 新規
reports/grid-searches/          # 生成物（.gitignore）
```

---

## 7. テスト戦略

- 各戦略の単体テスト: warmup、クロス / ブレイク判定、決済ロジック
- Registry: 登録と取り出し、未知戦略のエラー
- GridSearch: 小さな parameter_grid（2×2）で並列 / 逐次両方が同じ結果を返す
- 比較レポート: Top 20 ソート順・Decimal フォーマット確認

---

## 8. 完了判定

1. `uv run pytest` が green（全テスト）
2. `uv run ruff check src/ tests/ scripts/` が green
3. `uv run python scripts/grid_search.py --instrument USD_JPY --from ... --to ... --strategy bollinger --param window=10,20 --param k=2.0 --parallel 1` でレポートが生成される（bars が DB にある前提）

---

## 9. 先送り（Phase 4b 以降）

- GA（NSGA-II）による戦略自動生成
- DSL ベースのシグナル合成
- ウォークフォワード / train-test split
- Sharpe / Sortino / Calmar
- 経済指標カレンダー連携
- 戦略アンサンブル評価
