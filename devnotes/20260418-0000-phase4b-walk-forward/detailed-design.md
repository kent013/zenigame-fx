# Phase 4b 詳細設計 — ウォークフォワード検証

**作成**: 2026-04-18 00:00 JST
**前提**: [../20260417-2345-phase4a-grid-search/detailed-design.md](../20260417-2345-phase4a-grid-search/detailed-design.md)
**状態**: DRAFT

---

## 1. 背景と目的

Phase 4a のグリッドサーチは「期間全体で最も良いパラメータ」を見つける。これは**カーブフィッティングの結果**になりやすく、実運用では再現しない。

**ウォークフォワード検証**は:
1. 期間を train / test に分割
2. train でグリッドサーチして最適パラメータを選定
3. test で最適パラメータを評価
4. train→test のスライド窓を繰り返し、アウトオブサンプル性能を集計

これで「過去最適化」ではなく「変化する市場への汎化性」を検証できる。

---

## 2. スコープ

**含む**:
- `WalkForwardConfig`（train_days / test_days / step_days / top_k）
- `run_walk_forward` — fold 分割とgrid search反復の実装
- Fold ごとに train で best-params を選び、test で評価する基本モード（Anchored / Rolling は選択可）
- アグリゲート指標: train vs test の prof_factor / max_dd / win_rate
- Markdown + JSON レポート
- CLI: `scripts/walk_forward.py`

**含まない**:
- 複数戦略同時比較（各 fold で戦略が入れ替わるモード）— Phase 4d 以降
- best-params 選定基準のカスタマイズ（MVP は total_pnl のみ）
- Monte Carlo の bootstrap 区間推定

---

## 3. データモデル

```python
@dataclass(frozen=True)
class WalkForwardConfig:
    instrument: str
    start: datetime
    end: datetime
    initial_cash: Decimal
    leverage: int
    strategy_name: str
    parameter_grid: dict[str, Sequence[Any]]
    train_days: int
    test_days: int
    step_days: int                       # fold 開始の刻み幅。test_days と同じなら重複なし
    mode: Literal["rolling", "anchored"] = "rolling"
    parallel: int = 1
    top_k: int = 1                       # train で上位 K を test で評価（MVP=1）

@dataclass
class FoldOutcome:
    fold_index: int
    train_start: datetime
    train_end: datetime
    test_start: datetime
    test_end: datetime
    best_params: dict[str, Any]
    train_metrics: BacktestMetrics
    test_metrics: BacktestMetrics

@dataclass
class WalkForwardResult:
    config: WalkForwardConfig
    folds: list[FoldOutcome]
```

---

## 4. 実行フロー

```
1. expand_grid(parameter_grid) → combos
2. folds = slice_folds(start, end, train_days, test_days, step_days, mode)
3. for each fold:
     train_bars = bars[fold.train_start:fold.train_end]
     test_bars  = bars[fold.test_start:fold.test_end]
     train_runs = run_grid_search(train_bars, combos) → sorted by total_pnl
     best = train_runs[0]
     test_strategy = build(strategy_name, **best.params)
     test_metrics  = run_backtest(test_bars, test_strategy, fresh MockBroker)
     append FoldOutcome(...)
4. aggregate metrics
5. write report
```

### 4.1 Fold 分割

- **Rolling**: train window がスライドする（昔の train データを捨てる）
- **Anchored**: train window が start から固定で、test window だけスライド（train データは増え続ける）
- MVP は両方対応、デフォルト rolling

### 4.2 `step_days`

- `step_days == test_days` なら test 区間に重複なし（標準）
- `step_days < test_days` なら重複あり（サンプル数を稼ぐ）
- `step_days > test_days` なら test 区間に隙間（非推奨、警告ログ）

### 4.3 最後の fold で test が端に到達できない場合

- test 期間が `test_days` に満たなくなったら、その fold をスキップ
- 警告ログを出す

---

## 5. アグリゲート指標

| 項目 | 集計方法 |
|------|----------|
| train_total_pnl / test_total_pnl | fold 合計 |
| train_profit_factor / test_profit_factor | fold 平均（None は除外） |
| train_win_rate / test_win_rate | fold 平均 |
| train_max_drawdown_pct / test_max_drawdown_pct | fold 最大 |
| overfit_score | (train_pnl - test_pnl) / |train_pnl|（train が正のとき） |

overfit_score > 0.5 で警告、> 1.0 で厳重警告レベル。

---

## 6. レポート（`src/backtest/walk_forward_report.py`）

`reports/walk-forwards/wf-YYYYMMDD-HHMMSS/`:
- `result.md`: config サマリ + fold ごとの train vs test + アグリゲート
- `result.json`: 全情報

Markdown 列:
- fold / train_period / test_period / best_params / train_pnl / test_pnl / train_win_rate / test_win_rate / train_dd / test_dd

---

## 7. CLI（`scripts/walk_forward.py`）

```
uv run python scripts/walk_forward.py \
    --instrument USD_JPY \
    --from 2025-01-01 --to 2026-04-01 \
    --initial-cash 1000000 \
    --leverage 10 \
    --strategy bollinger \
    --param window=10,20,30 \
    --param k=1.5,2.0,2.5 \
    --train-days 60 --test-days 14 --step-days 14 \
    --mode rolling \
    --parallel 4
```

---

## 8. ディレクトリ構成の追加

```
src/backtest/
├── walk_forward.py              # ← 新規
└── walk_forward_report.py       # ← 新規
scripts/
└── walk_forward.py              # ← 新規
tests/backtest/
└── test_walk_forward.py         # ← 新規
reports/walk-forwards/           # 生成物（.gitignore）
```

---

## 9. テスト戦略

- fold 分割関数の単体テスト（境界条件: start=end、train_days > 期間、step_days のバリエーション、anchored vs rolling）
- 小さなパラメータグリッド + 小さな bar リストで walk-forward が期待通り実行されること
- overfit_score の計算

---

## 10. 完了判定

1. `uv run pytest` が green（全テスト）
2. `uv run ruff check src/ tests/ scripts/` が green
3. CLI 実行で `reports/walk-forwards/wf-*/result.md` が生成される（bars が DB にある前提）

---

## 11. 先送り（Phase 4c 以降）

- 複数戦略を並列に比較するモード
- Monte Carlo bootstrap で区間推定
- best-params 選定基準のカスタマイズ（Sharpe, Calmar 等で選ぶ）
- 経済指標カレンダー連携
- DSL + GA（Alpha Factory 相当）
