# 詳細設計: B Phase 2 切替コミット step 1 — canonical_metrics → main flow 統合

**作成日時**: 2026-05-03 10:35 JST、 **本格化**: 2026-05-03 11:00 JST (= 着手前調査結果反映)
**status**: **本格化済 Round 0 (= 着手前調査で skeleton § 9 の論点を解消、 Codex 設計 review 待ち)**

---

## 0. 着手前調査結果 (= skeleton § 9 の論点解消)

### 0.1 T070 calendar / session bucket 関数の実存確認

skeleton の 「`assign_session_bucket_and_business_day_index`」 「`compute_business_day_universe`」 は **存在しない**。 代わりに以下が利用可能:

- **`src/backtest/session_block.py:332` `compute_bucket_for_trade(trade: Trade) -> SessionBlockBucket`**
  内部で `compute_bucket_for_bar(trade.exit_time)` を呼出、 UTC 検証 + `BLOCK_BUCKET_RANGES_UTC` でバケット決定
- **`SessionBlockBucket = Literal["tokyo", "london", "ny"]`** (session_block.py:70)
- **`SessionBucket = StrEnum("tokyo"/"london"/"ny")`** (canonical_metrics.py:110) — Literal と値が一致するため変換可能 (`SessionBucket(literal_value)`)

→ **adapter 設計**: `compute_bucket_for_trade(broker.Trade)` で SessionBlockBucket 取得 → `SessionBucket(value)` で StrEnum 変換。

### 0.2 business_day_index 計算

skeleton で 「T070 既存実装」 と仮定したが、 **直接対応する関数は存在しない**。 ただし:

- TradeRecord.business_day_index は単に `int >= 0` (= 同一 business day をユニークに識別する整数)
- canonical_metrics.compute_session_blocks は `(business_day_index, session_bucket)` 単位で集約するだけで、 整数の意味は問わない
- test fixture では `business_day_index=0, 1, 2, ...` のような integer encoding が使われている

→ **adapter 設計**: business_day_index を **`(date - epoch_date).days`** として計算 (= UTC date を unix epoch からの日数で整数化)。 epoch は固定値 (= 1970-01-01) で、 評価期間内では monotone increasing。

```python
EPOCH_DATE = date(1970, 1, 1)  # 仮定 (= UTC date を ordinal 化)

def business_day_index_for(exit_time_utc: datetime) -> int:
    return (exit_time_utc.date() - EPOCH_DATE).days
```

### 0.3 evaluate_canonical_five signature

```python
def evaluate_canonical_five(
    trades: Iterable[TradeRecord],
    bars: BarEquitySeries,
    thresholds: CanonicalFiveThresholds,         # ← REQUIRED (= raw metrics 単独取得不可)
    business_day_universe: dict[SessionBucket, frozenset[int]],
    *,
    bucket_validator: SessionBucketBoundaryProvider | None = None,
    q_bartlett: int = HAC_BARTLETT_DEFAULT_Q,
) -> CanonicalFiveResult:
```

**重要発見**: `thresholds` 引数が **必須**。 step 1 で raw metrics 観測のみ行う場合でも thresholds を caller 側で構築する必要がある。

ただし `evaluate_canonical_five` は **no-raise 契約** で、 thresholds が不適合でも `InfeasibleReasonCode` で deterministic な戻り値を返す (= 安全に呼出可能)。

→ **設計**: step 1 では Stage A / B / C 各 stage の **既存 live_criteria を window scaling した dummy thresholds** を `derive_stage_a_thresholds` (= 既存) で構築して dual-path で呼出。 LOG_ONLY mode では結果の `gate_pass` / `gate_worst_gap` を log のみで使う。

### 0.4 broker.Trade の TZ awareness

`compute_bucket_for_bar(bar_time)` (session_block.py:304-329) は:
```python
if bar_time.tzinfo is None:
    raise ValueError("bar_time must be timezone-aware (UTC), got naive: ...")
offset = bar_time.utcoffset()
if offset != timedelta(0):
    raise ValueError("bar_time must be UTC offset, got offset=...: ...")
```

→ broker.Trade.exit_time は **既に UTC-aware で utcoffset=0 が保証されている前提** (= main flow で既に `compute_bucket_for_trade` 等で利用されているため)。 adapter 側で追加検証不要。

### 0.5 既存 aggregate_session_blocks との関係

`src/backtest/session_block.py:337 aggregate_session_blocks(bars, trades, *, mode, ...)` は SessionBlock の tuple を返す (= bucket × date 単位の集約済 dataclass)。 canonical_metrics.compute_session_blocks とは **出力構造が異なる**:

- aggregate_session_blocks → `tuple[SessionBlock, ...]` (= 各 block に open_minutes / observability_flags 含む)
- canonical_metrics.compute_session_blocks → `dict[SessionBucket, list[SessionBlockSummary]]` (= per-bucket list)

= 直接互換ではない。 adapter で trade-level 変換 (broker.Trade → TradeRecord) を行い、 canonical_metrics 経路で再集計する。

---

## 1. 使命・制約

### zenigame-fx Alpha Factory 使命
live_criteria 全指標同時充足 + (ii-lite) 通過で使命達成。
絶対制約: イントラデイ / ロング・ショート両方向 / スワップ・スプレッド反映。

### 禁止事項
1. A・B・C 評価期間を根拠なしに延長
2. 見た目の数値改善
3. GA ハック
4. live_criteria 緩和
5. **過度な複雑化** ← 本 step では特に重要 (= dual-path で 1 commit を抑制)
6. 取引回数削減
7. オーバーナイト保有前提

---

## 2. 概念設計リファレンス

`devnotes/20260503-1024-B-phase2-step1-canonical-metrics/conceptual-design.md`

---

## 3. 改訂対象一覧 (skeleton)

| # | 改訂名 | 変更箇所 | 性質 | 優先度 |
|---|---|---|---|---|
| 1 | broker.Trade → TradeRecord adapter | src/alpha_factory/canonical_adapter.py 新規 | 配線 helper | High |
| 2 | equity_curve → BarEquitySeries adapter | 同上 | 配線 helper | High |
| 3 | business_day_universe 計算 (T070 既存活用) | 同上 | 配線 helper | High |
| 4 | stage_gate.py に dual-path 計算追加 (LOG_ONLY mode) | src/alpha_factory/stage_gate.py | 配線追加 | High |
| 5 | phase2.canonical_metrics_mode config 追加 | config/alpha_factory/default.yaml + src/alpha_factory/config.py | 設定追加 | Medium |
| 6 | adapter unit test + dual-path integration test | tests/ | test 追加 | High |

---

## 4. 詳細実装方針 (= 後続詳細化、 各改訂につき concrete code を本格化)

### 4.1 改訂 1-3: canonical_adapter.py (新規) — 着手前調査反映版

```python
"""broker.Trade / backtest equity_curve から canonical_metrics 経路へ変換する adapter.

cascade port v2 Phase 2 切替コミット step 1 の SSOT (= dual-path の足場).

session_block.compute_bucket_for_trade (= 既存) を再利用、
business_day_index は UTC date を 1970-01-01 epoch からの日数で整数化.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Final

from src.alpha_factory.canonical_metrics import (
    BarEquityPoint, BarEquitySeries, SessionBucket, TradeRecord,
)
from src.backtest.session_block import (
    SessionBlockBucket, compute_bucket_for_trade,
)
from src.broker.orders import Trade as BrokerTrade

# business_day_index epoch (= UTC ordinal を整数化する基準日、 固定)
BUSINESS_DAY_EPOCH: Final[date] = date(1970, 1, 1)


def _convert_bucket(literal: SessionBlockBucket) -> SessionBucket:
    """SessionBlockBucket (Literal["tokyo"|"london"|"ny"]) → SessionBucket (StrEnum)."""
    return SessionBucket(literal)


def _business_day_index_for(exit_time_utc: datetime) -> int:
    """exit_time の UTC date を BUSINESS_DAY_EPOCH (1970-01-01) からの日数で整数化.

    canonical_metrics は business_day_index >= 0 の整数を要求するのみで、
    具体値は問わない (= 同一 universe / trades で consistent であれば OK)。
    """
    return (exit_time_utc.date() - BUSINESS_DAY_EPOCH).days


def trade_to_trade_record(broker_trade: BrokerTrade) -> TradeRecord:
    """broker.Trade を canonical TradeRecord に変換.

    - session_bucket: compute_bucket_for_trade (= 既存) で算出 (= exit_time UTC hour 駆動)
    - business_day_index: exit_time UTC date を BUSINESS_DAY_EPOCH からの日数で整数化
    - pnl_net / spread_cost / holding_cost: Decimal → float (T078 で broker 側追加済)
    - is_session_close_drop / is_negative_equity_drop_open: broker.Trade に対応 field なし
      → step 1 では default False (= synthesis § 6.6 戦略的 fail-fast の sentinel、
        broker engine で本物の値が伝搬される段階は別 step で対応)

    例外契約:
        broker_trade.exit_time が naive datetime / 非 UTC offset の場合、
        compute_bucket_for_trade が ValueError raise (= caller で catch)。
    """
    bucket_literal = compute_bucket_for_trade(broker_trade)
    return TradeRecord(
        entry_time_utc=broker_trade.entry_time,
        exit_time_utc=broker_trade.exit_time,
        pnl_net=float(broker_trade.pnl),
        session_bucket=_convert_bucket(bucket_literal),
        business_day_index=_business_day_index_for(broker_trade.exit_time),
        is_session_close_drop=False,  # step 1 では default、 別 step で broker 経路から伝搬
        is_negative_equity_drop_open=False,
        spread_cost=float(broker_trade.spread_cost),
        holding_cost=float(broker_trade.holding_cost),
    )


def equity_curve_to_bar_equity_series(
    equity_curve: list[tuple[datetime, Decimal]],
) -> BarEquitySeries:
    """backtest engine の equity_curve を canonical BarEquitySeries に変換.

    BarEquitySeries invariant (UTC-aware / strict monotone increasing) は
    backtest engine の出力契約で既に保証されている (= equity_curve は時系列順、
    重複 timestamp なし、 全 UTC-aware)。 違反検出時は BarEquitySeries.__post_init__
    で raise (= caller で catch)。
    """
    points = tuple(
        BarEquityPoint(timestamp_utc=ts, equity=float(eq))
        for ts, eq in equity_curve
    )
    return BarEquitySeries(points=points)


def compute_business_day_universe_from_trades(
    trades: Iterable[BrokerTrade],
) -> dict[SessionBucket, frozenset[int]]:
    """trades が触れた (bucket, business_day_index) ペア集合を universe として返す.

    canonical_metrics は trades 全件が universe に含まれている必要がある (=
    INPUT_BUSINESS_DAY_UNIVERSE_MISMATCH を防ぐ)。 step 1 では trades 自身から
    universe を構築する最小実装 (= 後続 step で「期間内全 (bucket, day) 集合」 に
    拡張可能、 これは T070 計算済の bars 経路で別途取得可能)。

    注意: 全 bucket key が必須 (= len(business_day_universe) == 3)、
    そうでないと INPUT_EMPTY_BUSINESS_DAY_UNIVERSE 判定。 trades が空 / 1 bucket
    のみの Run でも 3 bucket の dict を返す (= 不在 bucket は frozenset() で
    INPUT_EMPTY_BUSINESS_DAY_UNIVERSE 判定される、 これは expected behavior)。
    """
    universe: dict[SessionBucket, set[int]] = {
        SessionBucket.TOKYO: set(),
        SessionBucket.LONDON: set(),
        SessionBucket.NY: set(),
    }
    for t in trades:
        bucket = _convert_bucket(compute_bucket_for_trade(t))
        universe[bucket].add(_business_day_index_for(t.exit_time))
    return {k: frozenset(v) for k, v in universe.items()}
```

### 4.1.1 trades が空の場合の挙動

`evaluate_canonical_five` は trades 空 / universe 空のいずれでも `InfeasibleReasonCode.INPUT_EMPTY_TRADE_LIST` / `INPUT_EMPTY_BUSINESS_DAY_UNIVERSE` を reason に追加して deterministic な戻り値を返す (= no-raise)。 step 1 では LOG_ONLY mode のため、 reason がついた状態でも log のみで既存判定不変。

### 4.2 改訂 4: stage_gate.py dual-path 配線 — 着手前調査反映版

`derive_stage_a_thresholds` (= 既存、 stage_a_evaluator.py:267) を再利用して各 stage の CanonicalFiveThresholds を構築。

#### 4.2.1 helper: `_try_evaluate_canonical_five_safe`

stage_gate.py 内に module-level helper を追加 (= 1 helper で stage A/B/C 全対応):

```python
from src.alpha_factory.canonical_adapter import (
    compute_business_day_universe_from_trades,
    equity_curve_to_bar_equity_series,
    trade_to_trade_record,
)
from src.alpha_factory.canonical_metrics import (
    CanonicalFiveResult,
    CanonicalFiveThresholds,
    evaluate_canonical_five,
)
from src.alpha_factory.stage_a_evaluator import derive_stage_a_thresholds


def _try_evaluate_canonical_five_safe(
    *,
    trades: list[Trade],
    equity_curve: list[tuple[datetime, Decimal]],
    thresholds: CanonicalFiveThresholds,
    stage_label: str,
    genome_name: str,
    enabled: bool,
) -> CanonicalFiveResult | None:
    """canonical_metrics 計算を例外 safe で実施 (= dual-path LOG_ONLY mode 用).

    Args:
        enabled: phase2.canonical_metrics_mode != "disabled" のとき True
            (= disabled mode は完全 skip で計算 overhead 0)。
        thresholds: caller が live_criteria + window scaling で構築済。

    例外時は WARN log のみで None 返り (= 既存判定経路は完全に不変)。
    no-raise 契約は evaluate_canonical_five 側にあるが、 adapter 経路で
    naive datetime / non-UTC が混入した場合は ValueError raise されるため、
    本 helper で catch する。

    Returns:
        CanonicalFiveResult (gate_pass / gate_worst_gap / 各 slack を含む)、
        または None (= disabled / 例外時)。
    """
    if not enabled:
        return None
    try:
        canonical_trades = tuple(trade_to_trade_record(t) for t in trades)
        canonical_bars = equity_curve_to_bar_equity_series(equity_curve)
        canonical_universe = compute_business_day_universe_from_trades(trades)
        result = evaluate_canonical_five(
            canonical_trades,
            canonical_bars,
            thresholds,
            canonical_universe,
        )
        return result
    except Exception as exc:
        logger.warning(
            "stage_gate.canonical_five.skipped",
            stage=stage_label,
            genome=genome_name,
            error=str(exc),
            error_type=type(exc).__name__,
        )
        return None


def _log_canonical_dual_path(
    *,
    stage_label: str,
    genome_name: str,
    legacy: BacktestMetrics,
    canonical: CanonicalFiveResult | None,
) -> None:
    """dual-path 結果 (legacy + canonical) を構造化 log に出力."""
    if canonical is None:
        logger.info(
            "stage_gate.canonical_five.dual_path",
            stage=stage_label,
            genome=genome_name,
            canonical_skipped=True,
        )
        return
    logger.info(
        "stage_gate.canonical_five.dual_path",
        stage=stage_label,
        genome=genome_name,
        # legacy
        legacy_total_pnl=str(legacy.total_pnl),
        legacy_trade_count=legacy.trade_count,
        legacy_max_dd_pct=str(legacy.max_drawdown_pct),
        legacy_sharpe=str(legacy.sharpe) if legacy.sharpe is not None else None,
        # canonical
        canonical_net_pnl=canonical.net_pnl_after_cost,
        canonical_trade_count=canonical.trade_count,
        canonical_max_dd=canonical.max_dd,
        canonical_sr_worst_block=canonical.sr_session_worst_block_scale,
        canonical_sr_worst_annual=canonical.sr_session_worst_annual_estimate,
        canonical_wr_worst=canonical.session_block_win_rate_worst,
        canonical_gate_pass=canonical.gate_pass,
        canonical_gate_worst_gap=canonical.gate_worst_gap,
        canonical_invariants_feasible=canonical.invariants.is_feasible,
        # diff
        pnl_diff=float(legacy.total_pnl) - canonical.net_pnl_after_cost,
        trade_count_diff=legacy.trade_count - canonical.trade_count,
    )
```

#### 4.2.2 evaluate_stage_a への配線 (例)

`stage_gate.py:431` 付近の `bt = compute_metrics(...)` の直後に追加:

```python
bt = compute_metrics(
    result.trades,
    result.equity_curve,
    trade_count_min_for_sharpe=stage_config.trade_count_min_for_sharpe,
)

# T-canonical step 1: dual-path canonical 5 metrics (LOG_ONLY)
# stage_config.phase2_canonical_metrics_mode は config.py の Phase2Config で設定
canonical_thresholds = derive_stage_a_thresholds(
    live_criteria=stage_config.live_criteria_dict,  # dict 化が必要、 既存実装と整合確認
    window_days=STAGE_A_WINDOW_DAYS,
    baseline_dataset_days=BASELINE_DATASET_DAYS,
)
canonical_sidecar = _try_evaluate_canonical_five_safe(
    trades=result.trades,
    equity_curve=result.equity_curve,
    thresholds=canonical_thresholds,
    stage_label="A",
    genome_name=genome.name,
    enabled=(stage_config.phase2_canonical_metrics_mode != "disabled"),
)
_log_canonical_dual_path(
    stage_label="A",
    genome_name=genome.name,
    legacy=bt,
    canonical=canonical_sidecar,
)
# canonical_sidecar は payload には添付しない (= step 1 では log のみ、
# archive Parquet schema に影響させない)
```

stage B / C も同型で `derive_stage_b_thresholds` / `derive_stage_c_thresholds` (= 既存 or 新規) で thresholds 構築 → 同じ helper で dual-path 評価。

#### 4.2.3 stage B / C の thresholds 構築

- Stage A: `derive_stage_a_thresholds(live_criteria, window_days=60, baseline_dataset_days=...)` (= 既存)
- Stage B / C: 同型関数 (= grep で既存 / 新規判断、 step 1 では Stage A と同じ window logic で構築可)

→ **要詳細化**: Stage B (= 18m WF folds) は per-fold thresholds、 Stage C (= holdout 全期間) は holdout window thresholds。 step 1 では Stage A だけ dual-path 配線して、 step B/C は次 step (= step 1.5 or step 2) で対応 という選択肢もある (= scope 縮小)。

**推奨 scope 限定**: step 1 では **Stage A のみ dual-path 配線**、 stage B/C は別 step に分割。 理由:
- Stage A は per-trade per-genome 単純評価で thresholds 構築も simple
- Stage B (5-fold WF rolling) は per-fold thresholds が必要で複雑度増
- 1 step 1 commit の原則を守るため (= 過度な複雑化禁止)

### 4.3 改訂 5: config 追加

`config/alpha_factory/default.yaml`:
```yaml
phase2:
  canonical_metrics_mode: log_only  # log_only / fail_closed / disabled
  # @why: B Phase 2 切替コミット step 1 で canonical_metrics 経路を dual-path 配線。
  # log_only = sidecar 計算 + log のみ (default)、 disabled = skip (regression 防止)、
  # fail_closed = canonical 判定切替 (= 後続別 TODO で導入)
```

`src/alpha_factory/config.py` に Phase2Config dataclass 追加:
```python
@dataclass(frozen=True)
class Phase2Config:
    canonical_metrics_mode: Literal["log_only", "fail_closed", "disabled"] = "log_only"

@dataclass(frozen=True)
class AlphaFactoryConfig:
    ...
    phase2: Phase2Config = field(default_factory=Phase2Config)
```

stage_gate.py の `_try_evaluate_canonical_five_safe` で mode 確認:
```python
if backtest_config.phase2_mode == "disabled":
    return None  # skip canonical 計算
```

### 4.4 改訂 6: テスト計画

新規 test ファイル:
1. `tests/alpha_factory/test_canonical_adapter.py`:
   - `test_trade_to_trade_record_basic`: broker Trade fixture → TradeRecord 変換、 session_bucket / business_day_index 正確
   - `test_trade_to_trade_record_preserves_spread_cost`: T078 broker.spread_cost が float 変換で伝搬 (= 1e-9 以内)
   - `test_equity_curve_to_bar_equity_series_basic`: timestamp / equity 変換、 strict monotone 維持
   - `test_business_day_universe_for_period`: 1 day / 1 week / 1 month で expected universe size

2. `tests/alpha_factory/test_stage_gate_canonical_dual_path.py`:
   - `test_dual_path_log_only_legacy_unchanged`: LOG_ONLY mode で StageResult.metrics["payload"] が legacy と同一 (= regression 0)
   - `test_dual_path_canonical_sidecar_logged`: log に canonical_five.dual_path event が出る、 net_pnl / trade_count / max_dd 含む
   - `test_dual_path_canonical_skipped_on_exception`: T070 calendar 関数が例外を raise したら canonical 計算 skip、 既存判定不変
   - `test_dual_path_disabled_mode_skips_canonical`: phase2.canonical_metrics_mode=disabled で canonical 計算 skip
   - `test_dual_path_diff_logged_when_legacy_differs`: legacy total_pnl と canonical net_pnl の diff が log される

---

## 5. 機械検証手順

```bash
# adapter import / 構文確認
uv run python -c "from src.alpha_factory.canonical_adapter import trade_to_trade_record"

# unit test
uv run pytest tests/alpha_factory/test_canonical_adapter.py -x

# dual-path integration test
uv run pytest tests/alpha_factory/test_stage_gate_canonical_dual_path.py -x

# regression
uv run pytest tests/alpha_factory/ -x  # 全 PASS 必須

# ruff / mypy
uv run ruff check src/ tests/
uv run mypy src/
```

---

## 6. 波及変更

| target | 影響 |
|---|---|
| `AGENTS.md` | phase2.canonical_metrics_mode 設定説明追記 |
| `config/alpha_factory/default.yaml` | phase2 section 追加 |
| `src/alpha_factory/config.py` | Phase2Config dataclass + load_config 経路 |
| `docs/alpha_factory/runbook.md` | dual-path log の解釈ガイド (= LOG_ONLY mode の運用説明) |
| `.claude/skills/zenigame-fx-*/SKILL.md` | なし (= スキル interface に影響しない) |

---

## 7. 実装モード

| 項目 | 内容 |
|---|---|
| 推奨モード | **standalone** (= dual-path で legacy と独立、 既存 test に影響しないため worktree 1 commit でまとめて) |
| 判断根拠 | LOG_ONLY mode で既存判定不変、 step 1 完了時点で regression 0 が test で保証可能 |
| 競合リスク | 後続 step 2 (= stage_bc_evaluator main flow 統合) と canonical_adapter で競合可能性 (= 別 step として分離設計) |
| 想定実装時間 | 中-長 (= adapter + dual-path + test、 数時間-1 日) |

---

## 8. リスク

| リスク | 影響 | 緩和 |
|---|---|---|
| `evaluate_canonical_five` が thresholds 必須で raw metrics 単独取得不可 | 中 | API 確認、 必要なら raw 計算 helper を新規追加 (= 別 step か?) |
| broker.Trade の `entry_time` / `exit_time` が naive datetime | 高 | adapter で `_validate_utc_aware` 呼出、 不適合時 WARN + skip canonical |
| `compute_business_day_universe` が T070 calendar.py に存在しない | 中 | grep 確認、 不在なら新規追加 (= 別 step 推奨) |
| dual-path 計算 overhead が 50% 超 | 中 | smoke 5 Run で profile、 worst-case `disabled` mode で fall back |

---

## 9. 後続セッションでの本格化手順

1. T070 calendar.py の関数 grep + 名称確認 (= `assign_session_bucket_and_business_day_index` / `compute_business_day_universe` の実存確認)
2. `evaluate_canonical_five` の signature 詳細確認 (= thresholds 必須か?)
3. `broker.Trade` の field 全件確認 (= entry_time / exit_time の TZ awareness)
4. `_try_evaluate_canonical_five_safe` の例外 fallback ロジック詳細化
5. `phase2.canonical_metrics_mode` config の loader 経路詳細化
6. Codex 概念 + 詳細設計レビュー (= zenigame-fx-codex-review、 gpt-5.3-codex / high) APPROVED
7. zenigame-fx-implement で worktree todo/B-step1 で実装
8. impl-review APPROVED → main マージ → step 2 へ

---

## 10. 7 step segmentation との関係

step 1 完了で確立されるもの:
- canonical_adapter.py module (= broker → canonical 変換 SSOT)
- TradeRecord 経路の存在 (= T082 obsolete 解除条件の 1 つ)
- canonical 5 metrics の sidecar 計算経路

step 2 (= stage_bc_evaluator main flow 統合) はこの adapter を再利用。
