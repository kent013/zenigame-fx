# 詳細設計 (skeleton): B Phase 2 切替コミット step 1 — canonical_metrics → main flow 統合

**作成日時**: 2026-05-03 10:35 JST
**status**: **skeleton (= 後続セッションで本格化、 Codex 設計 review)**

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

### 4.1 改訂 1-3: canonical_adapter.py (新規)

```python
"""broker.Trade / backtest equity_curve から canonical_metrics 経路へ変換する adapter.

cascade port v2 Phase 2 切替コミット step 1 の SSOT (= dual-path の足場).

T070 calendar.py の session bucket / business day index 計算を信頼 (= 既存実装)。
"""

from __future__ import annotations
from datetime import datetime
from decimal import Decimal

from src.alpha_factory.canonical_metrics import (
    BarEquityPoint, BarEquitySeries, TradeRecord, SessionBucket,
)
from src.alpha_factory.calendar import (
    assign_session_bucket_and_business_day_index,  # 要 grep 確認
    compute_business_day_universe,                 # 要 grep 確認
)
from src.broker.orders import Trade as BrokerTrade


def trade_to_trade_record(broker_trade: BrokerTrade) -> TradeRecord:
    """broker.Trade を canonical TradeRecord に変換.

    session_bucket / business_day_index は exit_time の T070 attribution を使用。
    spread_cost / holding_cost は T078 で broker.Trade 側にも追加済 (Decimal → float)。
    """
    bucket, biz_day = assign_session_bucket_and_business_day_index(
        broker_trade.exit_time
    )
    return TradeRecord(
        entry_time_utc=broker_trade.entry_time,
        exit_time_utc=broker_trade.exit_time,
        pnl_net=float(broker_trade.pnl),
        session_bucket=bucket,
        business_day_index=biz_day,
        is_session_close_drop=False,  # 要 broker side flag 確認
        is_negative_equity_drop_open=False,  # 同上
        spread_cost=float(broker_trade.spread_cost),
        holding_cost=float(broker_trade.holding_cost),
    )


def equity_curve_to_bar_equity_series(
    equity_curve: list[tuple[datetime, Decimal]],
) -> BarEquitySeries:
    """backtest engine の equity_curve を canonical BarEquitySeries に変換.

    BarEquitySeries invariant (UTC-aware / strict monotone increasing) を満たす
    前提 = backtest engine 側で既に保証されている (要確認)。
    """
    points = tuple(
        BarEquityPoint(timestamp_utc=ts, equity=float(eq))
        for ts, eq in equity_curve
    )
    return BarEquitySeries(points=points)


def compute_business_day_universe_for_period(
    start: datetime,
    end: datetime,
) -> dict[SessionBucket, frozenset[int]]:
    """評価期間 [start, end) で発生し得た全 (bucket, business_day_index) ペア集合.

    T070 calendar.py の compute_business_day_universe を呼び出す。
    """
    return compute_business_day_universe(start, end)
```

### 4.2 改訂 4: stage_gate.py dual-path 配線

`evaluate_stage_a` 末尾近くの payload 構築前に追加:

```python
# T-canonical Phase 2 step 1: canonical 5 metrics を dual-path で計算 (LOG_ONLY mode)
canonical_sidecar = _try_evaluate_canonical_five_safe(
    trades=result.trades,
    equity_curve=result.equity_curve,
    bars_period=(bars_60d[0].bar_time, bars_60d[-1].bar_time),
    backtest_config=backtest_config,
    stage_label="A",
    genome_name=genome.name,
)
# canonical_sidecar は CanonicalFiveResult or None
# 失敗時は WARN log のみで legacy 経路は完全に不変
```

`_try_evaluate_canonical_five_safe` (新規 module-level helper):
```python
def _try_evaluate_canonical_five_safe(
    *,
    trades: list[Trade],
    equity_curve: list[tuple[datetime, Decimal]],
    bars_period: tuple[datetime, datetime],
    backtest_config: BacktestConfig,
    stage_label: str,
    genome_name: str,
) -> CanonicalFiveResult | None:
    """canonical_metrics 計算を例外 safe で実施.

    例外時は WARN log のみで None 返り (= 既存判定経路は不変)。
    """
    try:
        canonical_trades = tuple(
            trade_to_trade_record(t) for t in trades
        )
        canonical_bars = equity_curve_to_bar_equity_series(equity_curve)
        canonical_universe = compute_business_day_universe_for_period(
            bars_period[0], bars_period[1]
        )
        # CanonicalFiveThresholds は live_criteria + window scale から構築
        # (= step 2 で stage_bc_evaluator から流用予定、 step 1 では default = step 1 では不要?
        # 実は evaluate_canonical_five は thresholds なしで raw metrics 計算可能か要確認)
        # → 要設計詳細化
        ...
    except Exception as exc:
        logger.warning(
            "stage_gate.canonical_five.skipped",
            stage=stage_label,
            genome=genome_name,
            error=str(exc),
            error_type=type(exc).__name__,
        )
        return None
```

**未確定論点**: `evaluate_canonical_five` は thresholds 引数を必須としている可能性。 step 1 で raw metrics のみ取得する場合の API contract を要確認。 必要なら raw metrics 計算と slack 計算を分離する関数追加 (= 別 helper) または step 1 で thresholds を caller 側で構築。

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
