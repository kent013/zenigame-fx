"""Alpha Sieve: Stage C 通過個体を別期間 OOS で再検証する追加ゲート (T025)。

Stage C 通過個体は holdout 60 日で live_criteria を満たした状態に過ぎないため、
holdout 直後 5 日のエンバーゴ + 90 日 OOS で再 backtest し、
sharpe > 0.5 AND trade_count >= 30 AND total_pnl > 0 を要求して true positive を絞る。

入力:
- archive Parquet: .cache/alpha_factory/runs/genomes_{run_id}.parquet
- summary.json:    reports/run-reports/run-{N}/summary.json (backtest_config 整合チェック用)
- DB:              src.db.connection.SessionLocal (PostgreSQL)
- YAML:            config/alpha_factory/default.yaml (BacktestSectionConfig SSOT)

出力:
- reports/alpha-sieve/{yyyy-mm}/sieve-R{run_number}.md

設計根拠:
- docs/alpha_factory/concepts/alpha-sieve.md
- devnotes/20260424-1444-port-alpha-sieve/{conceptual,detailed}-design.md
- devnotes/20260421-1850-fx-skill-port/debate-synthesis.md §B / §E

学術引用:
- Bailey, D. H., Borwein, J. M., López de Prado, M., Zhu, Q. J. (2014).
  The Probability of Backtest Overfitting.
- López de Prado, M. (2018). Advances in Financial Machine Learning, Ch.7
  (Cross-Validation in Finance: purged/embargoed CV).
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal
from zoneinfo import ZoneInfo

import structlog
from sqlalchemy import select

from scripts.alpha_factory.run_ga import (
    _bar_row_to_price_bar,
    _meta_from_pair,
)
from src.alpha_factory.archive import GenomeArchive
from src.alpha_factory.config import (
    BacktestSectionConfig,
    load_config,
)
from src.alpha_factory.primitives import RegistryEvaluator, ensure_registered
from src.backtest.engine import BacktestConfig, run_backtest
from src.backtest.metrics import compute_metrics
from src.broker import InstrumentMeta
from src.broker.mock import MockBroker
from src.db.connection import SessionLocal
from src.db.models import CurrencyPair, PriceBarM1
from src.domain.price import PriceBar
from src.dsl.serialize import genome_from_dict
from src.dsl.strategy import DslStrategy, PrimitiveEvaluator

logger = structlog.get_logger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[2]
ARCHIVE_DIR = REPO_ROOT / ".cache" / "alpha_factory" / "runs"
RUN_REPORTS_DIR = REPO_ROOT / "reports" / "run-reports"
OUTPUT_DIR = REPO_ROOT / "reports" / "alpha-sieve"
DEFAULT_CONFIG = REPO_ROOT / "config" / "alpha_factory" / "default.yaml"

JST = ZoneInfo("Asia/Tokyo")


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SieveConfig:
    """Alpha Sieve 評価設定。

    通過基準は debate-synthesis.md §B / §E と Codex Round 1 review に基づき:
    sharpe > 0.5 AND trade_count >= 30 AND total_pnl > 0
    (sharpe / total_pnl は strict greater-than、trade_count は >=)
    """

    sieve_window_days: int = 90
    sieve_embargo_days: int = 5
    sharpe_min: float = 0.5  # strict gt
    trade_count_min: int = 30  # >=
    total_pnl_min: float = 0.0  # strict gt

    def __post_init__(self) -> None:
        if self.sieve_window_days < 1:
            raise ValueError(
                f"sieve_window_days must be >= 1: {self.sieve_window_days}"
            )
        if self.sieve_embargo_days < 0:
            raise ValueError(
                f"sieve_embargo_days must be >= 0: {self.sieve_embargo_days}"
            )
        if self.trade_count_min < 1:
            raise ValueError(
                f"trade_count_min must be >= 1: {self.trade_count_min}"
            )


@dataclass(frozen=True)
class CandidateRow:
    """archive Parquet から取り出した Stage C 通過個体 1 行。"""

    individual_name: str
    lane_id: str
    instrument: str
    generation: int
    genome_json: str
    stage_c_sharpe: float | None
    stage_c_total_pnl: float
    stage_c_trade_count: int


@dataclass(frozen=True)
class SieveEvalResult:
    """1 個体の Sieve 評価結果。

    `oos_dsr` は Phase 2 では恒常 None。Phase 4 で trial pool 統計量を入力に
    `src.alpha_factory.statistics.deflated_sharpe_ratio` 経由で計算する予定。
    """

    candidate: CandidateRow
    status: Literal["evaluated", "no_data", "system_failure"]
    oos_sharpe: float | None
    oos_total_pnl: float
    oos_trade_count: int
    oos_max_drawdown_pct: float
    oos_dsr: float | None
    passed: bool
    reason_codes: tuple[str, ...]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Alpha Sieve: Stage C 通過個体を OOS で再検証"
    )
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--run-id", default=None)
    g.add_argument("--run-number", type=int, default=None)
    p.add_argument("--sieve-window-days", type=int, default=90)
    p.add_argument("--sieve-embargo-days", type=int, default=5)
    p.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG,
        help="BacktestSectionConfig SSOT として再ロードする YAML パス",
    )
    return p.parse_args(argv)


# ---------------------------------------------------------------------------
# Run resolution
# ---------------------------------------------------------------------------


def _resolve_run(
    *,
    run_id: str | None,
    run_number: int | None,
) -> tuple[str, int, Path, Path]:
    """run_id / run_number から (run_id, run_number, archive_path, summary_path) を解決する。

    どちらか一方の指定で、もう一方を逆引きする。
    """
    if run_id is not None:
        archive_path = ARCHIVE_DIR / f"genomes_{run_id}.parquet"
        # run_number は summary.json から逆引き
        # reports/run-reports/run-N/summary.json を全探索して run_id 一致を探す
        for run_dir in sorted(RUN_REPORTS_DIR.glob("run-*")):
            summary_path = run_dir / "summary.json"
            if not summary_path.exists():
                continue
            try:
                summary = json.loads(summary_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if summary.get("run_id") == run_id:
                rn = int(summary.get("run_number", 0))
                return run_id, rn, archive_path, summary_path
        raise FileNotFoundError(
            f"summary.json with run_id={run_id} not found under {RUN_REPORTS_DIR}"
        )
    if run_number is not None:
        run_dir = RUN_REPORTS_DIR / f"run-{run_number}"
        summary_path = run_dir / "summary.json"
        if not summary_path.exists():
            raise FileNotFoundError(
                f"summary.json not found at {summary_path}"
            )
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        rid = str(summary.get("run_id", ""))
        if not rid:
            raise ValueError(f"summary.json at {summary_path} missing run_id")
        archive_path = ARCHIVE_DIR / f"genomes_{rid}.parquet"
        return rid, run_number, archive_path, summary_path
    raise ValueError("either run_id or run_number must be provided")


# ---------------------------------------------------------------------------
# Stage C passers loader
# ---------------------------------------------------------------------------


def _load_stage_c_passers(parquet_path: Path) -> list[CandidateRow]:
    """archive Parquet を読み、stage_c_pass=True 行を CandidateRow として返す。"""
    table = GenomeArchive.load(parquet_path)
    n_rows = table.num_rows
    if n_rows == 0:
        return []
    # pyarrow から row dict を取り出す（pandas 経由を回避し依存最小化）
    cols: dict[str, list[Any]] = {
        name: table.column(name).to_pylist() for name in table.schema.names
    }
    out: list[CandidateRow] = []
    for i in range(n_rows):
        if not bool(cols["stage_c_pass"][i]):
            continue
        sharpe_raw = cols["sharpe"][i]
        out.append(
            CandidateRow(
                individual_name=str(cols["individual_name"][i]),
                lane_id=str(cols["lane_id"][i]),
                instrument=str(cols["instrument"][i]),
                generation=int(cols["generation"][i]),
                genome_json=str(cols["genome_json"][i]),
                stage_c_sharpe=(
                    float(sharpe_raw) if sharpe_raw is not None else None
                ),
                stage_c_total_pnl=float(cols["total_pnl"][i] or 0.0),
                stage_c_trade_count=int(cols["trade_count"][i] or 0),
            )
        )
    return out


# ---------------------------------------------------------------------------
# OOS bars loader
# ---------------------------------------------------------------------------


def _load_oos_bars(
    instrument: str,
    sieve_start: datetime,
    sieve_end: datetime,
) -> tuple[list[PriceBar], InstrumentMeta | None]:
    """DB から OOS 期間 bars + meta を取得。bars 0 件なら ([], meta_or_None)。"""
    with SessionLocal() as session:
        pair = session.scalars(
            select(CurrencyPair).where(CurrencyPair.oanda_name == instrument)
        ).one_or_none()
        if pair is None:
            logger.warning(
                "alpha_sieve.no_pair", instrument=instrument
            )
            return [], None
        meta = _meta_from_pair(pair)
        rows = session.scalars(
            select(PriceBarM1)
            .where(PriceBarM1.pair_id == pair.id)
            .where(PriceBarM1.bar_time >= sieve_start)
            .where(PriceBarM1.bar_time < sieve_end)
            .order_by(PriceBarM1.bar_time.asc())
        ).all()
    if not rows:
        return [], meta
    bars = [_bar_row_to_price_bar(r, instrument) for r in rows]
    return bars, meta


# ---------------------------------------------------------------------------
# Backtest config builder (YAML SSOT)
# ---------------------------------------------------------------------------


def _build_oos_backtest_config(
    *,
    instrument: str,
    summary: dict[str, Any],
    sieve_start: datetime,
    sieve_end: datetime,
    config_path: Path,
) -> BacktestConfig:
    """OOS backtest 用 BacktestConfig を組み立てる。

    SSOT 戦略:
      1. config/alpha_factory/default.yaml から BacktestSectionConfig を再ロード
         (summary に含まれない max_spread_bps / holding_cost / session_close を取得)
      2. summary.json の backtest_config (initial_cash / leverage / units) と
         整合性チェック → 不一致なら logger.warning
      3. BacktestSectionConfig 値で BacktestConfig を構築
    """
    cfg = load_config(config_path, overrides={})
    bt_section: BacktestSectionConfig = cfg.backtest

    summary_bt = summary.get("backtest_config", {})
    if summary_bt:
        if summary_bt.get("initial_cash") is not None and Decimal(
            str(summary_bt["initial_cash"])
        ) != bt_section.initial_cash:
            logger.warning(
                "alpha_sieve.backtest_config_mismatch",
                field="initial_cash",
                summary=str(summary_bt["initial_cash"]),
                config=str(bt_section.initial_cash),
            )
        if (
            summary_bt.get("leverage") is not None
            and int(summary_bt["leverage"]) != bt_section.leverage
        ):
            logger.warning(
                "alpha_sieve.backtest_config_mismatch",
                field="leverage",
                summary=summary_bt["leverage"],
                config=bt_section.leverage,
            )
        if (
            summary_bt.get("units") is not None
            and int(summary_bt["units"]) != bt_section.units
        ):
            logger.warning(
                "alpha_sieve.backtest_config_mismatch",
                field="units",
                summary=summary_bt["units"],
                config=bt_section.units,
            )

    return BacktestConfig(
        instrument=instrument,
        start=sieve_start,
        end=sieve_end,
        initial_cash=bt_section.initial_cash,
        leverage=bt_section.leverage,
        max_spread_bps=bt_section.max_spread_bps,
        holding_cost_per_day_bps=bt_section.holding_cost_per_day_bps,
        session_close_utc_hours=frozenset(bt_section.session_close_utc_hours),
        bar_minutes=1,
    )


# ---------------------------------------------------------------------------
# DSR (Phase 2: stub returning None)
# ---------------------------------------------------------------------------


def _compute_dsr_safe(*, sharpe: float | None) -> float | None:
    """Phase 2: 常に None を返す (DSR の trial pool が単一個体評価では構成不能)。

    Phase 4 で Stage C 通過個体プール全体の SR 分布を入力に
    `src.alpha_factory.statistics.deflated_sharpe_ratio` を呼び出すヘルパへ置換する。
    `sharpe` 引数は Phase 4 接続準備のため signature 保持。
    """
    _ = sharpe
    return None


# ---------------------------------------------------------------------------
# Single-individual evaluation
# ---------------------------------------------------------------------------


def _evaluate_one(
    candidate: CandidateRow,
    bars: list[PriceBar],
    meta: InstrumentMeta,
    backtest_config: BacktestConfig,
    primitive_evaluator: PrimitiveEvaluator,
    sieve_config: SieveConfig,
) -> SieveEvalResult:
    """個体 1 体を OOS bars で評価する。"""
    if not bars:
        return SieveEvalResult(
            candidate=candidate,
            status="no_data",
            oos_sharpe=None,
            oos_total_pnl=0.0,
            oos_trade_count=0,
            oos_max_drawdown_pct=0.0,
            oos_dsr=None,
            passed=False,
            reason_codes=("no_data",),
        )
    try:
        genome = genome_from_dict(json.loads(candidate.genome_json))
        strategy = DslStrategy(genome, primitive_evaluator)
        broker = MockBroker(instrument_meta=meta)
        result = run_backtest(bars, strategy, broker, backtest_config)
        bt = compute_metrics(result.trades, result.equity_curve)
        sharpe = float(bt.sharpe) if bt.sharpe is not None else None
        total_pnl = float(bt.total_pnl)
        trade_count = bt.trade_count
        max_dd_pct = float(bt.max_drawdown_pct)
    except Exception as exc:
        logger.warning(
            "alpha_sieve.eval_failure",
            individual=candidate.individual_name,
            error=str(exc),
            error_type=type(exc).__name__,
        )
        return SieveEvalResult(
            candidate=candidate,
            status="system_failure",
            oos_sharpe=None,
            oos_total_pnl=0.0,
            oos_trade_count=0,
            oos_max_drawdown_pct=0.0,
            oos_dsr=None,
            passed=False,
            reason_codes=("system_failure",),
        )

    oos_dsr = _compute_dsr_safe(sharpe=sharpe)
    passed, reason_codes = _judge(sharpe, total_pnl, trade_count, sieve_config)

    return SieveEvalResult(
        candidate=candidate,
        status="evaluated",
        oos_sharpe=sharpe,
        oos_total_pnl=total_pnl,
        oos_trade_count=trade_count,
        oos_max_drawdown_pct=max_dd_pct,
        oos_dsr=oos_dsr,
        passed=passed,
        reason_codes=reason_codes,
    )


# ---------------------------------------------------------------------------
# Pass criteria
# ---------------------------------------------------------------------------


def _judge(
    sharpe: float | None,
    total_pnl: float,
    trade_count: int,
    sieve_config: SieveConfig,
) -> tuple[bool, tuple[str, ...]]:
    """通過判定。reason_codes は失敗理由 (空タプル = 通過)。

    - sharpe > sharpe_min  (strict gt)
    - trade_count >= trade_count_min
    - total_pnl > total_pnl_min  (strict gt)
    """
    reasons: list[str] = []
    if sharpe is None:
        reasons.append("sharpe_unavailable")
    elif sharpe <= sieve_config.sharpe_min:
        reasons.append(f"sharpe<={sieve_config.sharpe_min}")
    if trade_count < sieve_config.trade_count_min:
        reasons.append(f"trade_count<{sieve_config.trade_count_min}")
    if total_pnl <= sieve_config.total_pnl_min:
        reasons.append("total_pnl<=0")
    return (len(reasons) == 0), tuple(reasons)


# ---------------------------------------------------------------------------
# Report renderer
# ---------------------------------------------------------------------------


def _fmt_float(v: float | None, precision: int = 4) -> str:
    if v is None:
        return "--"
    return f"{v:.{precision}f}"


def _render_report(
    *,
    status: Literal["ok", "no_candidates", "no_data"],
    run_id: str,
    run_number: int,
    archive_path: Path,
    instrument: str,
    holdout_end: datetime,
    sieve_config: SieveConfig,
    sieve_start: datetime,
    sieve_end: datetime,
    bars_loaded: int,
    backtest_config: BacktestConfig,
    candidates: list[CandidateRow],
    eval_results: list[SieveEvalResult],
    generated_at: datetime,
) -> str:
    """Markdown レポートを文字列で返す。"""
    n_candidates = len(candidates)
    evaluated = [r for r in eval_results if r.status == "evaluated"]
    no_data_results = [r for r in eval_results if r.status == "no_data"]
    failed_results = [r for r in eval_results if r.status == "system_failure"]
    passers = [r for r in evaluated if r.passed]
    fails = [r for r in eval_results if not r.passed]
    n_evaluable = len(evaluated)
    n_pass = len(passers)
    pass_rate_str = (
        f"{(n_pass / n_evaluable):.2%}" if n_evaluable > 0 else "-- (n/a)"
    )

    def _mean(values: list[float | None]) -> str:
        nums = [v for v in values if v is not None]
        if not nums:
            return "--"
        return f"{sum(nums) / len(nums):.4f}"

    mean_pass_sharpe = _mean([r.oos_sharpe for r in passers])
    mean_all_sharpe = _mean([r.oos_sharpe for r in evaluated])

    lines: list[str] = []
    lines.append(
        f"# Alpha Sieve Report — {run_id} (Run #{run_number})"
    )
    lines.append("")
    lines.append(f"- status: {status}")
    lines.append(f"- generated_at: {generated_at.astimezone(JST).isoformat()}")
    lines.append(f"- run_id: {run_id}")
    lines.append(f"- archive_path: {archive_path}")
    lines.append(f"- instrument: {instrument}")
    lines.append(f"- holdout_end: {holdout_end.isoformat()}")
    lines.append(f"- sieve_embargo_days: {sieve_config.sieve_embargo_days}")
    lines.append(
        f"- sieve_window: [{sieve_start.isoformat()}, {sieve_end.isoformat()}) "
        f"— {sieve_config.sieve_window_days} days"
    )
    lines.append(f"- bars_loaded: {bars_loaded}")
    lines.append("")

    lines.append("## criteria_snapshot")
    lines.append("")
    lines.append(f"- sharpe_min: {sieve_config.sharpe_min} (strict gt)")
    lines.append(f"- trade_count_min: {sieve_config.trade_count_min} (>=)")
    lines.append(f"- total_pnl_min: {sieve_config.total_pnl_min} (strict gt)")
    lines.append("")

    lines.append("## cost_model")
    lines.append("")
    lines.append(f"- max_spread_bps: {backtest_config.max_spread_bps}")
    lines.append(
        f"- holding_cost_per_day_bps: {backtest_config.holding_cost_per_day_bps}"
    )
    lines.append(
        f"- session_close_utc_hours: {sorted(backtest_config.session_close_utc_hours)}"
    )
    lines.append("- intraday_force_close: ON (engine 既定)")
    lines.append(f"- bar_minutes: {backtest_config.bar_minutes}")
    lines.append("")

    lines.append("## 結果サマリー")
    lines.append("")
    lines.append(f"- Stage C 通過個体数: {n_candidates}")
    lines.append(
        f"- Sieve 評価可能個体数: {n_evaluable} "
        f"(no_data 等で除外された数: {len(no_data_results) + len(failed_results)})"
    )
    lines.append(f"- Sieve 通過個体数: {n_pass}")
    lines.append(f"- pass 率: {pass_rate_str}")
    lines.append(f"- mean OOS Sharpe (通過個体): {mean_pass_sharpe}")
    lines.append(f"- mean OOS Sharpe (全体): {mean_all_sharpe}")
    lines.append("")

    lines.append("## 通過個体一覧")
    lines.append("")
    lines.append(
        "| 個体名 | lane_id | OOS Sharpe | OOS PnL | OOS Trade | "
        "Stage C Sharpe | Stage C PnL | Stage C Trade | DSR (info) |"
    )
    lines.append(
        "|--------|---------|------------|---------|-----------|"
        "----------------|-------------|---------------|------------|"
    )
    if not passers:
        lines.append("| (該当なし) | | | | | | | | |")
    else:
        for r in passers:
            c = r.candidate
            lines.append(
                f"| {c.individual_name} | {c.lane_id} | "
                f"{_fmt_float(r.oos_sharpe)} | "
                f"{_fmt_float(r.oos_total_pnl, 2)} | "
                f"{r.oos_trade_count} | "
                f"{_fmt_float(c.stage_c_sharpe)} | "
                f"{_fmt_float(c.stage_c_total_pnl, 2)} | "
                f"{c.stage_c_trade_count} | "
                f"{_fmt_float(r.oos_dsr)} |"
            )
    lines.append("")

    lines.append("## 不通過個体（理由付き）")
    lines.append("")
    lines.append(
        "| 個体名 | lane_id | OOS Sharpe | OOS PnL | OOS Trade | 理由 |"
    )
    lines.append(
        "|--------|---------|------------|---------|-----------|------|"
    )
    if not fails:
        lines.append("| (該当なし) | | | | | |")
    else:
        for r in fails:
            c = r.candidate
            lines.append(
                f"| {c.individual_name} | {c.lane_id} | "
                f"{_fmt_float(r.oos_sharpe)} | "
                f"{_fmt_float(r.oos_total_pnl, 2)} | "
                f"{r.oos_trade_count} | "
                f"{';'.join(r.reason_codes)} |"
            )
    lines.append("")

    lines.append("## no_data 詳細")
    lines.append("")
    if status == "no_data":
        lines.append(
            f"- instrument={instrument} の OOS 期間 "
            f"[{sieve_start.isoformat()}, {sieve_end.isoformat()}) に "
            f"price_bars_m1 行が 0 件、または通貨ペアが未登録です。"
        )
    elif no_data_results:
        for r in no_data_results:
            lines.append(
                f"- {r.candidate.individual_name} "
                f"(lane={r.candidate.lane_id}): no_data"
            )
    else:
        lines.append("- (該当なし)")
    lines.append("")

    lines.append("## ノート")
    lines.append("")
    if status == "no_candidates":
        lines.append(
            "- Stage C 通過個体が 0 体のため Sieve 評価をスキップしました。"
        )
    if status == "no_data":
        lines.append(
            "- OOS 期間の bars が DB に存在しないため Sieve 評価をスキップしました。"
        )
    if status == "ok":
        lines.append(
            "- DSR は Phase 2 では trial pool が構成不能のため恒常 `--`。"
            " Phase 4 で正式接続予定。"
        )
        if failed_results:
            lines.append(
                f"- system_failure: {len(failed_results)} 件 "
                "(個別 logger.warning 'alpha_sieve.eval_failure' を確認)"
            )

    return "\n".join(lines) + "\n"


def _write_report(run_number: int, report: str, generated_at: datetime) -> Path:
    """JST yyyy-mm ブロックに書き出す。"""
    yyyy_mm = generated_at.astimezone(JST).strftime("%Y-%m")
    out_dir = OUTPUT_DIR / yyyy_mm
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"sieve-R{run_number}.md"
    path.write_text(report, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    sieve_config = SieveConfig(
        sieve_window_days=args.sieve_window_days,
        sieve_embargo_days=args.sieve_embargo_days,
    )

    try:
        run_id, run_number, archive_path, summary_path = _resolve_run(
            run_id=args.run_id, run_number=args.run_number
        )
    except (FileNotFoundError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if not archive_path.exists():
        print(f"ERROR: archive not found: {archive_path}", file=sys.stderr)
        return 1
    if not summary_path.exists():
        print(f"ERROR: summary.json not found: {summary_path}", file=sys.stderr)
        return 1

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    instrument = str(summary["dataset"]["instrument"])
    dataset_end = datetime.fromisoformat(summary["dataset"]["end"])
    if dataset_end.tzinfo is None:
        dataset_end = dataset_end.replace(tzinfo=UTC)
    stage_c_holdout_days = int(
        summary.get("stage_gate_config", {}).get("stage_c_holdout_days", 60)
    )
    holdout_end = dataset_end + timedelta(days=stage_c_holdout_days)
    sieve_start = holdout_end + timedelta(days=sieve_config.sieve_embargo_days)
    sieve_end = sieve_start + timedelta(days=sieve_config.sieve_window_days)

    backtest_config = _build_oos_backtest_config(
        instrument=instrument,
        summary=summary,
        sieve_start=sieve_start,
        sieve_end=sieve_end,
        config_path=args.config,
    )

    generated_at = datetime.now(UTC)

    candidates = _load_stage_c_passers(archive_path)
    if not candidates:
        report = _render_report(
            status="no_candidates",
            run_id=run_id,
            run_number=run_number,
            archive_path=archive_path,
            instrument=instrument,
            holdout_end=holdout_end,
            sieve_config=sieve_config,
            sieve_start=sieve_start,
            sieve_end=sieve_end,
            bars_loaded=0,
            backtest_config=backtest_config,
            candidates=[],
            eval_results=[],
            generated_at=generated_at,
        )
        out_path = _write_report(run_number, report, generated_at)
        print(f"sieve report written: {out_path} (status=no_candidates)")
        return 0

    bars, meta = _load_oos_bars(instrument, sieve_start, sieve_end)
    if not bars or meta is None:
        report = _render_report(
            status="no_data",
            run_id=run_id,
            run_number=run_number,
            archive_path=archive_path,
            instrument=instrument,
            holdout_end=holdout_end,
            sieve_config=sieve_config,
            sieve_start=sieve_start,
            sieve_end=sieve_end,
            bars_loaded=0,
            backtest_config=backtest_config,
            candidates=candidates,
            eval_results=[],
            generated_at=generated_at,
        )
        out_path = _write_report(run_number, report, generated_at)
        print(f"sieve report written: {out_path} (status=no_data)")
        return 0

    ensure_registered()
    primitive_evaluator: PrimitiveEvaluator = RegistryEvaluator(pair=instrument)
    eval_results = [
        _evaluate_one(
            candidate=c,
            bars=bars,
            meta=meta,
            backtest_config=backtest_config,
            primitive_evaluator=primitive_evaluator,
            sieve_config=sieve_config,
        )
        for c in candidates
    ]

    report = _render_report(
        status="ok",
        run_id=run_id,
        run_number=run_number,
        archive_path=archive_path,
        instrument=instrument,
        holdout_end=holdout_end,
        sieve_config=sieve_config,
        sieve_start=sieve_start,
        sieve_end=sieve_end,
        bars_loaded=len(bars),
        backtest_config=backtest_config,
        candidates=candidates,
        eval_results=eval_results,
        generated_at=generated_at,
    )
    out_path = _write_report(run_number, report, generated_at)
    print(
        f"sieve report written: {out_path} "
        f"(evaluated={len(eval_results)} pass={sum(1 for r in eval_results if r.passed)})"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
