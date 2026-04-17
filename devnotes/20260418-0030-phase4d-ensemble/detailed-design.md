# Phase 4d 詳細設計 — ストラテジーアンサンブル評価

**作成**: 2026-04-18 00:30 JST
**前提**: Phase 4a〜4c 済
**状態**: DRAFT

---

## 1. 目的

複数戦略を同一期間・同一 instrument に対して並行運用し、以下を評価する:

- 各戦略の個別 PnL
- 戦略間の PnL 相関（低相関の組合せはアンサンブル効果あり）
- 合成 PnL（等配分 or カスタム重み）と合成指標（Sharpe、MaxDD 等）

同じ戦略でも異なるパラメータで複数インスタンスを並行走らせることで、「設定のアンサンブル」も検証できる。

---

## 2. スコープ

**含む**:
- `EnsembleConfig` / `run_ensemble` / `EnsembleResult`
- 各戦略の単独バックテストを集約して合成 equity curve を計算
- Pearson 相関行列（戦略間 PnL 変化率）
- 合成 equity curve に対する拡張指標（compute_metrics を流用）
- Markdown + JSON レポート
- CLI: `scripts/ensemble.py`

**含まない**:
- 動的リバランス / レジーム検知（Phase 5+）
- 戦略ごとに異なる instrument / 異なる期間
- 戦略間の通信（フィルター、ベト機能など）

---

## 3. データモデル

```python
@dataclass(frozen=True)
class EnsembleSpec:
    name: str                 # ラベル（レポート上の識別名）
    strategy: str             # registry 名
    params: dict[str, Any]

@dataclass(frozen=True)
class EnsembleConfig:
    instrument: str
    start: datetime
    end: datetime
    initial_cash: Decimal     # ensemble 全体の初期資金
    leverage: int
    specs: list[EnsembleSpec]
    weights: list[Decimal] | None = None  # None なら等配分

@dataclass
class StrategyRun:
    spec: EnsembleSpec
    metrics: BacktestMetrics
    equity_curve: list[tuple[datetime, Decimal]]
    trades: list[Trade]
    capital_allocated: Decimal

@dataclass
class EnsembleResult:
    config: EnsembleConfig
    per_strategy: list[StrategyRun]
    combined_equity: list[tuple[datetime, Decimal]]
    combined_metrics: BacktestMetrics
    correlation: dict[tuple[str, str], float]
```

---

## 4. 実行フロー

```
total = config.initial_cash
weights = config.weights or [1/N]*N
for spec, w in zip(specs, weights):
    alloc = total * w
    strategy = build(spec.strategy, **spec.params)
    broker = MockBroker(meta)
    bconfig = BacktestConfig(..., initial_cash=alloc, leverage=config.leverage)
    result = run_backtest(bars, strategy, broker, bconfig)
    append StrategyRun(spec, compute_metrics(...), result.equity_curve, ...)

# 合成 equity: 各 bar 時刻で per-strategy equity を合算
combined = [(t, sum(strategy_runs[i].equity_curve[t] for i)) for t in timestamps]
# 合成 trades: 全 strategy の trades を時刻順にマージ
combined_metrics = compute_metrics(all_trades, combined)

# 相関: 各戦略の equity 変化率の Pearson
```

---

## 5. 相関計算

- 各戦略の equity curve を returns 系列に変換（`(equity_t - equity_{t-1}) / equity_{t-1}`）
- 各ペアで Pearson 相関係数を計算
- 対称なので上三角のみ保存（dict のキーは `(name_i, name_j)` で i<j）
- サンプル < 2 or 分散 0 の場合は `None`

---

## 6. CLI

```
uv run python scripts/ensemble.py \
    --instrument USD_JPY \
    --from 2025-11-01 --to 2026-04-01 \
    --initial-cash 1000000 \
    --leverage 10 \
    --strategy boll20:bollinger:window=20,k=2.0,units=5000 \
    --strategy boll30:bollinger:window=30,k=2.0,units=5000 \
    --strategy mac520:ma_crossover:fast_window=5,slow_window=20,units=5000
```

`--strategy LABEL:NAME:k1=v1,k2=v2,...` 形式で複数指定。

---

## 7. ディレクトリ構成追加

```
src/backtest/
├── ensemble.py              # ← 新規
└── ensemble_report.py       # ← 新規
scripts/
└── ensemble.py              # ← 新規
tests/backtest/
└── test_ensemble.py         # ← 新規
reports/ensembles/           # 生成物（.gitignore）
```

---

## 8. 完了判定

1. `uv run pytest` が green
2. `uv run ruff check` が green
3. CLI でレポートが生成される（bars が DB 前提）
