# 詳細設計: Sharpe Ratio 計算の根本修正 (Phase 1A)

## 使命・制約（絶対遵守）

### zenigame-fx Alpha Factory 使命
live_criteria 全指標同時充足 + (ii-lite) 通過で使命達成。
絶対制約: イントラデイ / ロング・ショート両方向 / スワップ・スプレッド反映。

### 禁止事項
1. A・B・C 評価期間を根拠なしに延長
2. 見た目の数値改善
3. GA ハック
4. live_criteria 緩和（Phase 1B は replay 根拠必須）
5. 過度な複雑化
6. 取引回数削減で成績を見せる
7. オーバーナイト保有前提

### コーディングルール
- **バグ修正はテストファースト**: 再現最小テスト → FAIL 確認 → 修正 → PASS
- **全施策にテスト必須**
- **テスト命名**: 振る舞いを説明する汎用的な名前
- **uv 必須**: `uv run pytest tests/`
- Python 3.13 + numpy + pandas 環境

## 概念設計リファレンス

[devnotes/20260425-1624-sharpe-calc-fix/conceptual-design.md](./conceptual-design.md)

## 施策一覧

| # | 施策名 | 変更ファイル | 優先度 |
|---|--------|------------|--------|
| S1 | Position/Trade に equity_at_entry 追加 | `src/broker/orders.py`, `src/broker/mock.py` | P0 |
| S2 | compute_metrics に trade_sharpe_raw 追加 | `src/backtest/metrics.py` | P0 |
| S3 | GA fitness を trade_sharpe_raw に切り替え | `src/ga/fitness.py` | P1 |
| S4 | Stage Gate を trade_sharpe_raw に切り替え | `src/alpha_factory/stage_gate.py` | P1 |
| S5 | cross_pair を trade_sharpe_raw に切り替え | `src/alpha_factory/cross_pair.py` | P1 |
| S6 | calibrate_gate を trade_sharpe_raw に切り替え | `src/alpha_factory/calibrate_gate.py` | P1 |
| S7 | Alpha Sieve を trade_sharpe_raw に切り替え | `scripts/alpha_factory/run_alpha_sieve.py` | P1 |
| S8 | run_ga の live_criteria 判定を trade_sharpe_raw に切り替え | `scripts/alpha_factory/run_ga.py` | P1 |
| S9 | archive schema に trade_sharpe_raw + sharpe_calc_version 追加 | `src/alpha_factory/archive.py` | P1 |
| S9 | GenomeArchive canonical accessor 実装 | `src/alpha_factory/archive.py` | P1 |
| S10 | DSR コメント追記（v1 Sharpe 前提の明記） | `src/alpha_factory/statistics.py` | P2 |
| S11 | config に trade_count_min_for_sharpe 追加 | `config/alpha_factory/default.yaml` | P1 |
| S12 | テスト更新 | `tests/backtest/test_metrics.py`, `tests/ga/test_fitness.py` | P0 |

---

## S1: Position / Trade に equity_at_entry 追加

### 変更箇所

- ファイル: `src/broker/orders.py` (Position, Trade dataclass)
- ファイル: `src/broker/mock.py` (MockBroker._open_position, _close_one)

### 現行コード

```python
# orders.py
@dataclass(frozen=True)
class Position:
    id: int
    instrument: str
    side: PositionSide
    units: int
    entry_price: Decimal
    entry_time: datetime
    entry_margin: Decimal
    leverage: int

@dataclass(frozen=True)
class Trade:
    position_id: int
    instrument: str
    side: PositionSide
    units: int
    entry_price: Decimal
    entry_time: datetime
    exit_price: Decimal
    exit_time: datetime
    pnl: Decimal
    exit_reason: ExitReason
```

```python
# mock.py _open_position
pos = Position(
    id=self._next_position_id,
    instrument=self._meta.oanda_name,
    side=side,
    units=units,
    entry_price=entry_price,
    entry_time=entry_time,
    entry_margin=margin,
    leverage=leverage,
)
```

```python
# mock.py _close_one
trade = Trade(
    position_id=pos.id,
    instrument=pos.instrument,
    side=pos.side,
    units=pos.units,
    entry_price=pos.entry_price,
    entry_time=pos.entry_time,
    exit_price=exit_price,
    exit_time=bar.bar_time,
    pnl=net_pnl,
    exit_reason=reason,
)
```

### 変更後コード

```python
# orders.py
@dataclass(frozen=True)
class Position:
    id: int
    instrument: str
    side: PositionSide
    units: int
    entry_price: Decimal
    entry_time: datetime
    entry_margin: Decimal
    leverage: int
    equity_at_entry: Decimal = Decimal(0)  # T-sharpe: bar 開始時 pre-fill equity (SSOT)

@dataclass(frozen=True)
class Trade:
    position_id: int
    instrument: str
    side: PositionSide
    units: int
    entry_price: Decimal
    entry_time: datetime
    exit_price: Decimal
    exit_time: datetime
    pnl: Decimal
    exit_reason: ExitReason
    equity_at_entry: Decimal = Decimal(0)  # T-sharpe: Position から伝搬
```

```python
# mock.py _open_position: equity パラメータ追加
def _open_position(
    self, side: PositionSide, units: int, entry_price: Decimal, entry_time, leverage: int,
    *, equity_at_entry: Decimal  # T-sharpe: bar 開始時 pre-fill equity
) -> Position:
    ...
    pos = Position(
        id=self._next_position_id,
        instrument=self._meta.oanda_name,
        side=side,
        units=units,
        entry_price=entry_price,
        entry_time=entry_time,
        entry_margin=margin,
        leverage=leverage,
        equity_at_entry=equity_at_entry,  # T-sharpe
    )
```

```python
# mock.py _close_one: pos.equity_at_entry を Trade に伝搬
trade = Trade(
    position_id=pos.id,
    instrument=pos.instrument,
    side=pos.side,
    units=pos.units,
    entry_price=pos.entry_price,
    entry_time=pos.entry_time,
    exit_price=exit_price,
    exit_time=bar.bar_time,
    pnl=net_pnl,
    exit_reason=reason,
    equity_at_entry=pos.equity_at_entry,  # T-sharpe: Position から伝搬
)
```

```python
# mock.py engine.py 等の _open_position 呼び出し箇所:
# bar 処理の冒頭で pre-fill equity を snapshot から取得し _open_position に渡す
# 例: engine.py の order execution ループ冒頭で
#   pre_fill_equity = broker.snapshot().equity
# を取得し、同 bar の全 _open_position に equity_at_entry=pre_fill_equity を渡す
```

### same-bar 複数 fill の扱い

同一 bar 内の全 `_open_position` 呼び出しに、**その bar 処理開始時点（全 fill 前）の equity** を共通で渡す。fill 順依存の equity は使わない。

### `equity_at_entry` デフォルト値の扱い

`Decimal(0)` をデフォルトにすることで、既存コードが引数を渡さなくても静かに動作する（伝搬漏れを隠す）リスクがある。

対策:
- `_trade_returns()` 内で `equity_at_entry <= 0` の trade を検知して `logger.warning("trade_return.invalid_equity_at_entry", ...)` を出す。その trade は計算からスキップ（ただし後述の S2 で Invalid 件数ゼロをテストで保証）
- テストで `Trade.equity_at_entry > 0` であることを明示的にアサートする
- `frozen=True` な dataclass でのフィールド順序制約により `None` デフォルトは採用しないが、`Decimal(0)` は「未設定（バグ）」として扱うことをドキュメントに明記する

**S4/S9 の原子的変更について**: payload key 変更（`"sharpe_raw"` → `"trade_sharpe_raw"`）は、`stage_gate.py` と `archive.py` の両ファイルを同一コミットで変更すること。片側先行は記録欠損を引き起こす。

### 波及変更

- `AGENTS.md`: なし
- `config/alpha_factory/default.yaml`: なし
- `docs/alpha_factory/*.md`: なし（概念は conceptual-design.md に記録済み）

### テスト計画

- `tests/backtest/test_metrics.py`: `Trade` に `equity_at_entry` が付いている場合の trade return 計算テスト
- `tests/broker/test_mock.py`: `Position.equity_at_entry` が bar 開始 equity で記録されることを確認
- same-bar 複数ポジションで全ての `Trade.equity_at_entry` が同じ（bar 開始時 equity）であることを確認

---

## S2: compute_metrics に trade_sharpe_raw 追加

### 変更箇所

- ファイル: `src/backtest/metrics.py`

### 変更後コード

```python
SHARPE_CALC_VERSION_V1 = "v1_bar_annualized"
SHARPE_CALC_VERSION_V2 = "v2_trade_level"
DEFAULT_TRADE_COUNT_MIN_FOR_SHARPE = 30  # config 経由で上書き可能


def _trade_returns(
    trades: list[Trade], logger_ctx: structlog.BoundLogger | None = None
) -> list[float]:
    """各クローズドトレードの return を計算する。

    return = net_pnl / equity_at_entry (bar 開始時 pre-fill equity)
    equity_at_entry が 0 以下のトレードは「未設定（バグ）」として警告ログを出しスキップ。
    スキップは trade 単位で行い、残りのトレードで計算を続行する。

    NOTE (C7): equity_at_entry <= 0 のトレードは「未設定（バグ）」として警告ログを出しスキップ。
    invalid_count は本関数内でログ集計して完結させる（caller は件数を受け取らない）。
    """
    rets: list[float] = []
    invalid_count = 0
    for t in trades:
        if t.equity_at_entry <= 0:
            invalid_count += 1
            logger.warning(
                "trade_return.invalid_equity_at_entry",
                trade_position_id=t.position_id,
                equity_at_entry=str(t.equity_at_entry),
            )
        else:
            rets.append(float(t.pnl / t.equity_at_entry))
    if invalid_count > 0:
        logger.warning(
            "trade_return.invalid_equity_at_entry_total",
            invalid_count=invalid_count,
            total_trades=len(trades),
        )
    return rets


def _trade_sharpe_raw(
    returns: list[float],
    trade_count_min: int = DEFAULT_TRADE_COUNT_MIN_FOR_SHARPE,
) -> float | None:
    """trade-level raw Sharpe (annualize なし)。

    - len(returns) < trade_count_min → None (sample-size guard)
    - len(returns) < 2 → None (分散計算の前提として必ず 2 以上が必要)
    - std == 0 または非有限値 → None (識別不能)
    - else: mean / std

    Note: trade_count_min は 2 以上である必要がある。1 の場合でも len < max(2, trade_count_min)
    で防御する。
    """
    if len(returns) < max(2, trade_count_min):  # ゼロ除算防止: len-1 が 0 にならないよう
        return None
    mean = sum(returns) / len(returns)
    var = sum((r - mean) ** 2 for r in returns) / (len(returns) - 1)
    std = math.sqrt(var)
    if std <= 1e-15:  # std == 0 に加えて浮動小数点 epsilon ガード
        return None
    result = mean / std
    if not math.isfinite(result):  # NaN / Inf ガード
        return None
    return result


@dataclass(frozen=True)
class BacktestMetrics:
    trade_count: int
    win_count: int
    loss_count: int
    win_rate: Decimal
    total_pnl: Decimal
    avg_win: Decimal
    avg_loss: Decimal
    profit_factor: Decimal | None
    max_drawdown: Decimal
    max_drawdown_pct: Decimal
    final_equity: Decimal
    sharpe: Decimal | None  # v1 bar-level annualized。非 AF consumer 後方互換のため Phase 2 まで維持
    sortino: Decimal | None
    calmar: Decimal | None
    avg_trade_duration: timedelta | None
    max_trade_duration: timedelta | None
    # T-sharpe: Phase 1A 追加フィールド
    trade_sharpe_raw: Decimal | None = None  # v2 trade-level raw Sharpe (AF consumer 用)
    sharpe_calc_version: str = SHARPE_CALC_VERSION_V2  # "v2_trade_level"


def compute_metrics(
    trades: list[Trade],
    equity_curve: list[tuple[datetime, Decimal]],
    *,
    trade_count_min_for_sharpe: int = DEFAULT_TRADE_COUNT_MIN_FOR_SHARPE,
) -> BacktestMetrics:
    ...
    # 既存 sharpe 計算（Phase 2 まで維持）
    rets = _bar_returns(equity_curve)
    sharpe_f = _sharpe(rets)
    sortino_f = _sortino(rets)
    sharpe = Decimal(str(sharpe_f)) if sharpe_f is not None else None
    sortino = Decimal(str(sortino_f)) if sortino_f is not None else None

    # T-sharpe: trade-level Sharpe 追加計算
    trade_rets = _trade_returns(trades)
    trade_sharpe_f = _trade_sharpe_raw(trade_rets, trade_count_min=trade_count_min_for_sharpe)
    trade_sharpe_raw = Decimal(str(trade_sharpe_f)) if trade_sharpe_f is not None else None

    return BacktestMetrics(
        ...
        sharpe=sharpe,  # v1 維持
        ...
        trade_sharpe_raw=trade_sharpe_raw,  # v2 新規追加
        sharpe_calc_version=SHARPE_CALC_VERSION_V2,
    )
```

### 注意

- 既存の `_bar_returns` / `_sharpe` / `_sortino` 関数は**削除しない**（Phase 2 まで `sharpe` フィールドを埋め続けるため）
- `trade_sharpe_raw` は `BacktestMetrics` の末尾にデフォルト値付きフィールドとして追加（既存呼び出し元のシグネチャ破壊なし）

### テスト計画

- `trade_count < 30` のとき `trade_sharpe_raw=None`
- `trade_count >= 30` でかつ全 pnl が同じ（std=0）のとき `trade_sharpe_raw=None`
- 正常ケース: 期待値計算との照合
- `equity_at_entry=0` のトレードが存在する場合の防御的スキップ確認
- `sharpe_calc_version` フィールドが常に `"v2_trade_level"` であることを確認

---

## S3: GA fitness を trade_sharpe_raw に切り替え

### 変更箇所

- ファイル: `src/ga/fitness.py` (L78-87)

### 現行コード

```python
if metric == "sharpe":
    if metrics.sharpe is None:
        logger.info(
            "ga.fitness.metric_unavailable",
            genome=genome.name,
            metric=metric,
            reason="insufficient_trades_or_zero_std",
        )
        return _FAILURE_FITNESS
    return metrics.sharpe
```

### 変更後コード

```python
if metric == "sharpe":
    # T-sharpe: trade_sharpe_raw (v2 trade-level) を使用。bar-level sharpe (v1) は非 AF 後方互換のみ
    if metrics.trade_sharpe_raw is None:
        logger.info(
            "ga.fitness.metric_unavailable",
            genome=genome.name,
            metric=metric,
            reason="insufficient_trades_or_zero_std",
            sharpe_calc_version=metrics.sharpe_calc_version,
        )
        return _FAILURE_FITNESS
    return metrics.trade_sharpe_raw
```

### テスト計画

- `tests/ga/test_fitness.py`: `metric="sharpe"` のとき `metrics.trade_sharpe_raw` を使用することを確認
- `trade_sharpe_raw=None` のとき `_FAILURE_FITNESS` を返すことを確認

---

## S4: Stage Gate を trade_sharpe_raw に切り替え

### 変更箇所

- ファイル: `src/alpha_factory/stage_gate.py`

**evaluate_stage_a** (L281): `bt.sharpe` → `bt.trade_sharpe_raw`
**evaluate_stage_b** (L390, L410): `bt.sharpe` → `bt.trade_sharpe_raw`
**evaluate_stage_c** (L519): `bt.sharpe` → `bt.trade_sharpe_raw`

### 変更後コード（Stage A 例）

```python
# evaluate_stage_a (L279-281)
bt = compute_metrics(result.trades, result.equity_curve)
trade_count = bt.trade_count
# T-sharpe: trade_sharpe_raw (v2) を使用
sharpe_raw = float(bt.trade_sharpe_raw) if bt.trade_sharpe_raw is not None else None
```

### Stage B の `stage_b_median_oos_sharpe_min` 閾値注意

現行値 `0.20` は v1 bar-level Sharpe スケールの値。Phase 1A 完了後は `trade_sharpe_raw` (raw, annualize なし) に対する閾値として機能する。Phase 1B の replay で再校正が必要。Phase 1A では現行値のまま暫定運用とし、コメントに旧スケール前提であることを明記する。

```python
# stage_b_median_oos_sharpe_min: 0.20 は v1 bar-level Sharpe スケール前提。
# Phase 1B の replay で trade_sharpe_raw (v2) スケールに再校正する。
# (T-sharpe Phase 1B)
```

### Stage C の live_criteria.sharpe_min 注意

同様に Phase 1B で再校正。Phase 1A では現行値 `1.0` のまま暫定運用（実質的には `trade_sharpe_raw >= 1.0` が条件になるが、それが厳しすぎるかは Phase 1B replay で判断）。

### テスト計画

- Stage A: `bt.trade_sharpe_raw is None` のとき `metric_unavailable` reason になることを確認
- Stage A: `trade_sharpe_raw` が `stage_a_threshold` を超えた場合に `pass=True` になることを確認
- Stage B: fold の `trade_sharpe_raw` が `stage_b_median_oos_sharpe_min` と比較されることを確認
- Stage C: `trade_sharpe_raw` が `live_criteria.sharpe_min` と比較されることを確認

---

## S5: cross_pair を trade_sharpe_raw に切り替え

### 変更箇所

- ファイル: `src/alpha_factory/cross_pair.py` (L145-148)

### 現行コード

```python
bt = compute_metrics(result.trades, result.equity_curve)
if bt.sharpe is None:
    return 0.0, "metric_unavailable"
return float(bt.sharpe), None
```

### 変更後コード

```python
bt = compute_metrics(result.trades, result.equity_curve)
# T-sharpe: trade_sharpe_raw (v2) を使用。None は fail-fast (skip 扱い禁止)
if bt.trade_sharpe_raw is None:
    return 0.0, "metric_unavailable"  # 0.0 は fail-fast: cross-pair 集計で None 混入を防ぐ
return float(bt.trade_sharpe_raw), None
```

**fail-fast の意味**: `return 0.0, "metric_unavailable"` のとき、呼び出し元の cross-pair 集計は failure_reason が `"metric_unavailable"` の場合を **0.0 として集計する**（既存実装を確認済み）。これが `mean_sharpe` / `min_sharpe` に 0.0 を混入させることで fail-fast として機能する。skip（除外集計）は行わない。

### テスト計画

- `bt.trade_sharpe_raw is None` のとき `failure_reason="metric_unavailable"` で `0.0` を返すことを確認

---

## S6: calibrate_gate を trade_sharpe_raw に切り替え

### 変更箇所

- ファイル: `src/alpha_factory/calibrate_gate.py` (L411)

### 現行コード

```python
valid_sharpes = [
    float(r["sharpe"]) for r in rows_list if r.get("sharpe") is not None
]
best_sharpe = max(valid_sharpes) if valid_sharpes else None
```

### 変更後コード

```python
# T-sharpe: trade_sharpe_raw (v2) を使用。v2 行のみフィルタ（v1/unknown 行を除外）
def _get_sharpe_version(r: Mapping[str, Any]) -> str:
    """archive 行の sharpe_calc_version を取得。None は v1 として扱う。"""
    return r.get("sharpe_calc_version") or "v1_bar_annualized"  # None も v1 とみなす

unknown_versions: set[str] = set()
valid_sharpes = []
for r in rows_list:
    version = _get_sharpe_version(r)
    if version == "v2_trade_level":
        v = r.get("trade_sharpe_raw")
        if v is not None:
            fv = float(v)
            if math.isfinite(fv):  # NaN/Inf ガード
                valid_sharpes.append(fv)
    elif version != "v1_bar_annualized":
        unknown_versions.add(version)  # 未知バージョンを収集

if unknown_versions:
    logger.warning(
        "calibrate_gate.unknown_sharpe_calc_version",
        unknown_versions=sorted(unknown_versions),
        total_rows=len(rows_list),
    )

best_sharpe = max(valid_sharpes) if valid_sharpes else None
```

### 注意

`calibrate_gate` は archive 行から sharpe を読んでいるため、`archive.get_trade_sharpe(row)` accessor 経由に変更するのが理想だが、rows は dict のため `r["trade_sharpe_raw"]` への直接参照でも同等。accessor は `pa.Table` の row に対して使う設計とする。

---

## S7: Alpha Sieve を trade_sharpe_raw に切り替え

### 変更箇所

- ファイル: `scripts/alpha_factory/run_alpha_sieve.py` (L401-402)

### 現行コード

```python
bt = compute_metrics(result.trades, result.equity_curve)
sharpe = float(bt.sharpe) if bt.sharpe is not None else None
```

### 変更後コード

```python
bt = compute_metrics(result.trades, result.equity_curve)
# T-sharpe: trade_sharpe_raw (v2) を使用
sharpe = float(bt.trade_sharpe_raw) if bt.trade_sharpe_raw is not None else None
```

---

## S8: run_ga の live_criteria 判定を trade_sharpe_raw に切り替え

### 変更箇所

- ファイル: `scripts/alpha_factory/run_ga.py` (L490-522)

### 現行コード

```python
# _row_to_metrics_dict
"sharpe": _dec_or_none(row.get("sharpe")),

# _check_live_criteria
sharpe_raw = row.get("sharpe")
```

### 変更後コード

```python
# _row_to_metrics_dict
"sharpe": _dec_or_none(row.get("trade_sharpe_raw")),  # T-sharpe: v2 を使用

# _check_live_criteria
# T-sharpe: archive 行の trade_sharpe_raw (v2) を参照
sharpe_raw = row.get("trade_sharpe_raw")
# sharpe_calc_version が "v1_bar_annualized" の行は比較禁止
if row.get("sharpe_calc_version") == "v1_bar_annualized":
    sharpe_raw = None  # v1 archive 行との比較を防ぐ
```

### summary.json の混在状態対処

run_ga の summary 出力に `sharpe_calc_version` を追記する:

```python
# summary.json 出力箇所
{
    ...
    "sharpe_calc_version": row.get("sharpe_calc_version", "v1_bar_annualized"),
    ...
}
```

### live_criteria.sharpe_min の意味論変更への対処（Phase 1A 暫定）

Phase 1A では `live_criteria.sharpe_min=1.0` を `trade_sharpe_raw >= 1.0` として暫定運用する。これは非常に厳しい値である可能性があるが、Phase 1B replay まで判断できない。

Phase 1B では `live_criteria.trade_sharpe_raw_min` を新設し（別キー）、`sharpe_min` は v1 legacy ラベルとして無効化する。Phase 1A 時点でこの分離は行わない（スコープ）。

ただし `_check_live_criteria()` において、archive 行の `sharpe_calc_version == "v1_bar_annualized"` の場合は `trade_sharpe_raw` が None として扱われ `checks["sharpe"] = {pass: False}` になる（上記コードで対応済み）。

---

## S9: archive schema + canonical accessor

### 変更箇所

- ファイル: `src/alpha_factory/archive.py`

### GENOMES_SCHEMA への追加

```python
GENOMES_SCHEMA: pa.Schema = pa.schema(
    [
        # ... 既存 28 カラム ...
        pa.field("sharpe", pa.float64(), nullable=True),  # 既存: v1 bar-level（旧値、残存）
        # T-sharpe: Phase 1A 追加
        pa.field("trade_sharpe_raw", pa.float64(), nullable=True),  # v2 trade-level
        pa.field("sharpe_calc_version", pa.string(), nullable=True),  # nullable=True: 旧データ互換
        # ... 残りの既存カラム ...
    ]
)
```

**`sharpe_calc_version` を `nullable=True` にする理由**: `nullable=False` で追加すると既存の Parquet ファイルに空欄がある行でエラーになる可能性がある。読み込み時に `None` の場合はデフォルト `"v1_bar_annualized"` として補完する。accessor でデフォルト補完を実装済み（`row.get("sharpe_calc_version", "v1_bar_annualized")`）。

**4点セットの確認**: schema → template → collect → flush の全ての箇所で `trade_sharpe_raw` と `sharpe_calc_version` が扱われていることを import-time assert と flush の last-mile guard で検証する（既存の仕組みを流用）。

### _create_row_template への追加

```python
def _create_row_template() -> dict[str, Any]:
    return {
        ...
        "sharpe": None,  # 既存
        # T-sharpe
        "trade_sharpe_raw": None,
        "sharpe_calc_version": "v2_trade_level",
        ...
    }
```

### collect_stage_a (payload から trade_sharpe_raw を書き込む)

Stage A の `StageResult.metrics["payload"]` に `"trade_sharpe_raw"` を追加して archive に伝搬させる。S4 の Stage A コード変更で `sharpe_raw` → `trade_sharpe_raw` とリネームするか、payload の key を変更する。

```python
# stage_gate.py evaluate_stage_a の metrics_envelope["payload"] を変更
"payload": {
    "fitness_raw": fitness_raw,
    "size_norm": size_norm_val,
    "fitness_pen": fitness_pen,
    "alpha_a": stage_config.stage_a_alpha,
    "threshold": stage_config.stage_a_threshold,
    "trade_count": trade_count,
    "trade_sharpe_raw": sharpe_raw,  # T-sharpe: "sharpe_raw" → "trade_sharpe_raw" に改名
},

# archive.py collect_stage_a で payload から取得
row["trade_sharpe_raw"] = _opt_float(payload, "trade_sharpe_raw")
row["sharpe_calc_version"] = "v2_trade_level"
```

### canonical accessor

```python
class GenomeArchive:
    ...
    @staticmethod
    def get_trade_sharpe(row: Mapping[str, Any]) -> float:
        """比較用 accessor。v2 archive の trade_sharpe_raw を返す。

        v1 archive（sharpe_calc_version が "v2_trade_level" でない）の場合は
        ValueError を送出。静かな v1/v2 混在を防ぐ。

        Args:
            row: archive 行 (dict or similar Mapping)。

        Raises:
            ValueError: v1 archive の行に対して呼び出された場合。
            KeyError: row に trade_sharpe_raw または sharpe_calc_version が存在しない場合。
        """
        # nullable=True 対応: None のみを "v1_bar_annualized" として補完（"" は別異常扱い）
        raw_version = row.get("sharpe_calc_version")
        version = "v1_bar_annualized" if raw_version is None else raw_version
        if version != "v2_trade_level":
            raise ValueError(
                f"get_trade_sharpe: sharpe_calc_version={version!r} は v2 専用 accessor では"
                f"読めません。v1 archive との比較は禁止されています。"
            )
        return row["trade_sharpe_raw"]

    @staticmethod
    def get_legacy_bar_sharpe(row: Mapping[str, Any]) -> float | None:
        """閲覧専用 accessor。比較・判定への使用禁止。H2 検証専用。

        v1 archive の bar-level annualized Sharpe を返す。
        v2 archive の場合は ValueError。
        """
        # nullable=True 対応: None のみを "v1_bar_annualized" として補完
        raw_version = row.get("sharpe_calc_version")
        version = "v1_bar_annualized" if raw_version is None else raw_version
        if version == "v2_trade_level":
            raise ValueError(
                f"get_legacy_bar_sharpe: v2 archive には v1 bar-level Sharpe は存在しません。"
            )
        v = row.get("sharpe")
        return float(v) if v is not None else None
```

### 波及変更

- `AGENTS.md`: なし（GENOMES_SCHEMA 変更は内部実装）
- `config/alpha_factory/default.yaml`: S11 で対応

### テスト計画

- archive schema に `trade_sharpe_raw` / `sharpe_calc_version` が追加されていることを確認
- `_create_row_template()` に新カラムのデフォルト値が存在することを確認
- `get_trade_sharpe()`: v1 行に対して ValueError が発生することを確認
- `get_trade_sharpe()`: v2 行に対して `trade_sharpe_raw` の値を返すことを確認
- `get_legacy_bar_sharpe()`: v1 行に対して `sharpe` 値を返すことを確認
- `get_legacy_bar_sharpe()`: v2 行に対して ValueError が発生することを確認
- import-time assert が `trade_sharpe_raw` / `sharpe_calc_version` を含む schema/template で通過することを確認

---

## S10: DSR コメント追記

### 変更箇所

- ファイル: `src/alpha_factory/statistics.py` (L148 付近, DSR 関数)

```python
def deflated_sharpe_ratio(...):
    """Deflated Sharpe Ratio (DSR) の計算。

    NOTE (T-sharpe Phase 1A): 現在この関数は v1 bar-level annualized Sharpe を
    入力として期待しています。Phase 1A で GA / Stage Gate の Sharpe が
    trade_sharpe_raw (v2, annualize なし) に切り替わったため、DSR の入力意味論が
    変わっています。Phase 2 (別 TODO) で DSR の入力定義を更新します。
    Phase 1A 時点では DSR は monitor only であり、gate 判定には使用されていません。
    """
```

---

## S11: config に trade_count_min_for_sharpe 追加

### 変更箇所

- ファイル: `config/alpha_factory/default.yaml`

```yaml
ga:
  ...
  fitness_metric: sharpe
  # T-sharpe: trade-level Sharpe のサンプルサイズ最小値 (Phase 1B で N=20/30/50 感度分析)
  trade_count_min_for_sharpe: 30
```

### 4 段接続（config → consumer）

| 段 | ファイル / 場所 | 内容 |
|---|---|---|
| 1. config 定義 | `config/alpha_factory/default.yaml` | `ga.trade_count_min_for_sharpe: 30` |
| 2. GaConfig / StageGateConfig 読み込み | `run_ga.py` の config 解析箇所 | `trade_count_min_for_sharpe = cfg["ga"]["trade_count_min_for_sharpe"]` |
| 3. compute_metrics 呼び出し | `stage_gate.py` / `fitness.py` / `cross_pair.py` / `run_alpha_sieve.py` の全 `compute_metrics(...)` 呼び出し | `compute_metrics(..., trade_count_min_for_sharpe=trade_count_min_for_sharpe)` を明示渡し |
| 4. archive への記録 | `run_ga.py` summary / archive meta | 起動時ログに `trade_count_min_for_sharpe` を含める |

**現状の実装上の注意**: `compute_metrics` の `trade_count_min_for_sharpe` はキーワード引数でデフォルト値 30 を持つ。config 未設定でも動作するが、config で 30 以外の値を設定した場合に全 consumer への明示渡しが必要。Phase 1A では config 値 30 がデフォルトと一致するため、実装初期は `DEFAULT_TRADE_COUNT_MIN_FOR_SHARPE` 定数に頼ることを許容する（Phase 1B で config 読み込み + 明示渡しに整備）。

---

## S12: テスト更新

### `tests/backtest/test_metrics.py`

追加テスト:
- `test_trade_sharpe_raw_returns_none_when_trade_count_below_minimum`
- `test_trade_sharpe_raw_returns_none_when_std_is_zero`
- `test_trade_sharpe_raw_calculates_correctly_with_sufficient_trades`
- `test_trade_sharpe_raw_skips_trades_with_zero_equity_at_entry`
- `test_compute_metrics_includes_trade_sharpe_raw_field`
- `test_compute_metrics_sharpe_calc_version_is_v2`
- `test_compute_metrics_legacy_sharpe_still_populated`（v1 sharpe フィールドが Phase 2 まで維持されていること）

### `tests/ga/test_fitness.py`

追加テスト:
- `test_evaluate_genome_uses_trade_sharpe_raw_when_metric_is_sharpe`
- `test_evaluate_genome_returns_failure_fitness_when_trade_sharpe_raw_is_none`

### `tests/alpha_factory/test_archive.py`

追加テスト:
- `test_genomes_schema_includes_trade_sharpe_raw_column`
- `test_genomes_schema_includes_sharpe_calc_version_column`
- `test_get_trade_sharpe_raises_for_v1_archive`
- `test_get_trade_sharpe_returns_value_for_v2_archive`
- `test_get_legacy_bar_sharpe_raises_for_v2_archive`
- `test_get_legacy_bar_sharpe_returns_value_for_v1_archive`

---

## 実装モード

| 項目 | 内容 |
|------|------|
| 推奨モード | incremental |
| 判断根拠 | S1（Trade schema）→ S2（metrics）→ S3-S8（consumer 切替）→ S9（archive）の順で段階的に実装可能。各ステップ後にテストが通ることを確認してから次へ進む |
| 競合リスク | archive schema は `import-time assert` があるため schema / template / collect / flush の 4 点を同時に変更する必要あり。S9 は一括変更が必要 |
| 想定実装時間 | 中（S1-S2 は比較的単純、S3-S8 は機械的な切り替え、S9 の archive accessor が最も注意が必要） |

---

## 値伝搬チェックリスト確認（Phase 1A）

| # | チェック点 | 確認 |
|---|---|---|
| 1 | config: `trade_count_min_for_sharpe=30` が `default.yaml` に追加 | S11 ✅ |
| 2 | metrics API: `compute_metrics()` が `trade_sharpe_raw` を返す | S2 ✅ |
| 3 | genome.meta: Stage A payload → archive collect で `trade_sharpe_raw` が伝搬 | S4+S9 ✅ |
| 4 | archive schema: `GENOMES_SCHEMA` に `trade_sharpe_raw` + `sharpe_calc_version` 定義 | S9 ✅ |
| 5 | row_template / collect / flush: 4 点セット完結 | S9 ✅ |
| 6 | accessor hard-fail: v1 で `get_trade_sharpe()` が例外、全 AF consumer が accessor 経由 | S9 + S6,S7,S8 ✅ |
| 7 | logger: 新値伝搬に対応するログ（fitness metric log に `sharpe_calc_version` 追加） | S3 ✅ |

---

## リスク

1. **archive schema 変更時の import-time assert**: `_create_row_template()` と `GENOMES_SCHEMA` を同時に変更しないと import 時 AssertionError。S9 は一括変更必須
2. **Stage B の fold Sharpe 比較**: `stage_b_median_oos_sharpe_min=0.20` は v1 スケール前提。Phase 1A 後は全個体が Stage B を通過できなくなる可能性あり。Phase 1B で即座に再校正する
3. **Phase 1A 後の live_criteria.sharpe_min=1.0**: `trade_sharpe_raw` (raw, annualize なし) に対して 1.0 という閾値は非常に厳しい（月次 Sharpe 1.0 相当）。Phase 1B replay まで Stage C 通過個体が激減する可能性を認識しておく
4. **`Trade.equity_at_entry` のデフォルト値**: `Decimal(0)` をデフォルトにすると既存テストが静かに 0 でパスしてしまう。テストに `equity_at_entry` の正設定を明示的に含めること
