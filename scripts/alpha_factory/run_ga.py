"""Alpha Factory GA Run エントリポイント (Phase 2 完全統合、T018).

Phase 2 基盤 (Clause Genome + Stage A/B/C gates + GenomeArchive +
cross-pair shadow + swim-lane manager) を統合した run-ga orchestrator。

フロー:
    1. ``config/alpha_factory/default.yaml`` + CLI overrides → ``AlphaFactoryConfig``
    2. DB から Stage A / Stage B / Stage C holdout の 3 区間 bars を取得
    3. ``LaneManager`` / ``Tier1Lane`` / ``GraduationLane`` 構築
    4. 世代 loop: random/breed → ``lane_manager.run_generation`` (Stage A/B/C +
       archive 4 段伝搬 + graduation 判定) → archive から cache 更新
    5. ``archive.flush()`` で Parquet、``summary.json`` / ``history.json`` /
       ``best_genome.json`` を ``reports/run-reports/run-{N}/`` に書き出し

出力契約 (既存 ``analyze_run.py`` / ``generate_run_report.py`` と互換):
    - summary.json の top-level キー: ``run_id`` / ``run_number`` /
      ``generated_at`` / ``dataset.instrument,start,end,bars`` / ``ga_config`` /
      ``backtest_config`` / ``best.name,fitness,metrics`` / ``live_criteria`` /
      ``population_size`` は **従来通り保持**、新情報は追加キーのみ。
    - ``best.fitness`` / ``history[*].best_fitness`` は有限 Decimal 文字列
      (非有限値は ``"0"`` にフォールバック + ``best.fitness_finite=false``)。

設計根拠:
    - devnotes/20260423-2324-run-ga-full-rewrite/conceptual-design.md
    - devnotes/20260423-2324-run-ga-full-rewrite/conceptual-design-r2.md
    - devnotes/20260423-2324-run-ga-full-rewrite/detailed-design.md
    - devnotes/20260423-2324-run-ga-full-rewrite/detailed-design-r2.md
"""

from __future__ import annotations

import argparse
import json
import math
import random
import sys
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import structlog
from sqlalchemy import select

from scripts.alpha_factory.get_latest_run_number import get_latest_run_number
from src.alpha_factory._registry_bridge import build_random_gen_registry
from src.alpha_factory.archive import GenomeArchive
from src.alpha_factory.config import (
    AlphaFactoryConfig,
    BacktestSectionConfig,
    DatasetConfig,
    GAFeasibilityConfig,
    StageWindowsConfig,
    load_config,
)
from src.alpha_factory.diagnostics_collector import DiagnosticsCollector
from src.alpha_factory.diagnostics_sidecar import (
    sidecar_relative_path,
    write_stage_a_provenance,
)
from src.alpha_factory.primitives import RegistryEvaluator, ensure_registered
from src.alpha_factory.swim_lane import (
    GRADUATION_LANE_ID,
    GraduationLane,
    LaneManager,
    Tier1Lane,
)
from src.backtest.engine import BacktestConfig
from src.broker import InstrumentMeta
from src.db.connection import SessionLocal
from src.db.models import CurrencyPair, PriceBarM1
from src.domain.price import Ohlc, PriceBar
from src.dsl import genome_to_dict
from src.dsl.genome import Genome
from src.ga.operators import crossover, mutate
from src.ga.random_gen import PrimitiveSpec as RandomGenSpec
from src.ga.random_gen import random_genome

logger = structlog.get_logger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = REPO_ROOT / "config" / "alpha_factory" / "default.yaml"
RUN_REPORTS_DIR = REPO_ROOT / "reports" / "run-reports"
RUN_CACHE_DIR = REPO_ROOT / ".cache" / "alpha_factory" / "runs"

_BARS_PER_DAY = 24 * 60  # M1 bars


# ---------------------------------------------------------------------------
# Internal dataclass / helpers
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LaneBarsBundle:
    """Stage A / B / C の 3 区間 bars + meta."""

    meta: InstrumentMeta
    bars_stage_a: list[PriceBar]
    bars_stage_b: list[PriceBar]
    bars_holdout: list[PriceBar]


@dataclass(frozen=True)
class IndividualCacheEntry:
    """GA selection 用の cache entry (archive 由来).

    T031 RPC Phase 1: ``feasible`` / ``violation_magnitude`` を追加し
    ``selection_score`` 6 要素化 (v2)。
    T045 Stage C Feasibility: ``stage_c_feasible`` (PnL>0 ∧ Sharpe>0) を
    ``feasible`` 直後に挿入し v3 7 要素化。
    """

    generation: int
    fitness_pen: float
    stage_a_pass: bool
    stage_b_pass: bool
    stage_c_pass: bool
    feasible: bool = True
    violation_magnitude: float = 0.0
    # T045
    stage_c_feasible: bool = True

    @property
    def selection_score(self) -> tuple[int, float, int, int, int, int, float]:
        """Lexicographic 7-tuple v3:
        ``(feasible, -violation, stage_c_feasible, C_pass, B_pass, A_pass, fitness_pen)``.

        T045: stage_c_feasible (PnL>0 ∧ Sharpe>0) を T031 feasible 直後に挿入し
        負 PnL/負 Sharpe 個体の GA 選抜を構造的に下位化する。

        非有限値 (NaN/inf) は順序比較を破壊するため finite guard で正規化:
        - violation: 非有限なら ``+inf`` 扱い (= ``-inf`` を要素 2 に置く → 最下位)
        - fitness_pen: 非有限は ``-inf`` として比較最下位扱い
        """
        v = self.violation_magnitude
        v_norm = math.inf if not math.isfinite(v) else float(v)
        fp = self.fitness_pen
        fp_norm = -math.inf if not math.isfinite(fp) else float(fp)
        return (
            int(self.feasible),
            -v_norm,
            int(self.stage_c_feasible),
            int(self.stage_c_pass),
            int(self.stage_b_pass),
            int(self.stage_a_pass),
            fp_norm,
        )

    @property
    def _legacy_selection_score(self) -> tuple[int, int, int, float]:
        """旧 4 要素 selection_score (fallback / v1 互換用)."""
        fp = self.fitness_pen if math.isfinite(self.fitness_pen) else -math.inf
        return (
            int(self.stage_c_pass),
            int(self.stage_b_pass),
            int(self.stage_a_pass),
            fp,
        )


def _selection_key(
    entry: IndividualCacheEntry,
    fallback_active: bool,
) -> tuple[Any, ...]:
    """selection 用 lexicographic key.

    ``fallback_active=True`` (cache 全体が infeasible) の場合は旧 4 要素に
    フォールバックする。
    """
    if fallback_active:
        return entry._legacy_selection_score
    return entry.selection_score


def _is_all_infeasible(
    entries: Iterable[IndividualCacheEntry],
    feasibility_cfg: GAFeasibilityConfig,
) -> bool:
    """cache 全体スコープで全個体 infeasible なら True (fallback 発動条件)."""
    if not feasibility_cfg.enable_fallback_when_all_infeasible:
        return False
    return not any(e.feasible for e in entries)


def _safe_finite(x: float) -> tuple[float, bool]:
    """非有限 (-inf / +inf / nan) を 0.0 に落とす (summary/history の Decimal
    互換保証)."""
    if math.isfinite(x):
        return x, True
    return 0.0, False


def _fitness_to_str(x: float) -> str:
    """fitness float → Decimal 互換文字列 (非有限値は '0' 固定).

    ``Decimal(str(val)).normalize()`` で trailing zero を落とす
    (e.g. "0.0" → "0", "1.50" → "1.5")。
    """
    val, finite = _safe_finite(x)
    if not finite:
        return "0"
    # -0.0 は 0.0 に正規化 (符号 flip で文字列の一貫性を保つ)
    if val == 0.0:
        val = 0.0
    d = Decimal(str(val)).normalize()
    # 指数表記 (E+N) を避けて固定小数点形式にする
    s = f"{d:f}" if "E" in f"{d}" else str(d)
    # trailing zero の残りを除去
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    # "-0" を "0" に
    if s in ("", "-0", "-"):
        return "0"
    return s


# ---------------------------------------------------------------------------
# CLI / config
# ---------------------------------------------------------------------------


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Alpha Factory GA run (Phase 2 integration)"
    )
    p.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    p.add_argument("--run-id", default=None)
    p.add_argument("--instrument", default=None)
    p.add_argument("--start", default=None)
    p.add_argument("--end", default=None)
    p.add_argument("--population-size", type=int, default=None)
    p.add_argument("--generations", type=int, default=None)
    p.add_argument("--mutation-rate", type=float, default=None)
    p.add_argument("--crossover-rate", type=float, default=None)
    p.add_argument("--tournament-size", type=int, default=None)
    p.add_argument("--elite-count", type=int, default=None)
    p.add_argument("--max-depth", type=int, default=None)
    p.add_argument(
        "--fitness-metric",
        choices=["total_pnl", "sharpe", "calmar"],
        default=None,
    )
    p.add_argument("--seed", type=int, default=None)
    p.add_argument(
        "--no-report",
        action="store_true",
        help=(
            "reports/run-reports/run-{N}/ への成果物書き出しを skip する。"
            "プロファイル RUN 等で report を汚したくない場合に指定。"
            "archive Parquet と RUN_CACHE_DIR state (.cache/) は常に書く。"
        ),
    )
    return p.parse_args(argv)


def _args_to_overrides(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "dataset": {
            "instrument": args.instrument,
            "start": args.start,
            "end": args.end,
        },
        "ga": {
            "population_size": args.population_size,
            "generations": args.generations,
            "mutation_rate": args.mutation_rate,
            "crossover_rate": args.crossover_rate,
            "tournament_size": args.tournament_size,
            "elite_count": args.elite_count,
            "max_depth": args.max_depth,
            "fitness_metric": args.fitness_metric,
            "seed": args.seed,
        },
    }


# ---------------------------------------------------------------------------
# Bars loader
# ---------------------------------------------------------------------------


def _bar_row_to_price_bar(row: PriceBarM1, pair_name: str) -> PriceBar:
    return PriceBar(
        pair_name=pair_name,
        bar_time=row.bar_time,
        bid=Ohlc(
            open=row.open_bid,
            high=row.high_bid,
            low=row.low_bid,
            close=row.close_bid,
        ),
        ask=Ohlc(
            open=row.open_ask,
            high=row.high_ask,
            low=row.low_ask,
            close=row.close_ask,
        ),
        volume=row.volume,
        complete=row.complete,
    )


def _meta_from_pair(pair: CurrencyPair) -> InstrumentMeta:
    return InstrumentMeta(
        oanda_name=pair.oanda_name,
        base_currency=pair.base_currency,
        quote_currency=pair.quote_currency,
        margin_rate=pair.margin_rate,
        pip_size=InstrumentMeta.default_pip_size_for_quote(pair.quote_currency),
        display_precision=InstrumentMeta.default_display_precision_for_quote(pair.quote_currency),
    )


def _load_lane_bars(
    instrument: str,
    dataset: DatasetConfig,
    stage_windows: StageWindowsConfig,
) -> LaneBarsBundle:
    """DB から Stage A/B/C の 3 区間 bars + meta を取得する。

    - Stage B bars = [dataset.start, dataset.end)
    - Stage A bars = Stage B 末尾 ``stage_a_window_days * 1440`` 本
    - Stage C holdout = [dataset.end, dataset.end + holdout_days)
      欠損時 ``allow_stage_c_fallback_slice`` ならば Stage B 末尾 holdout 本数
      で slice (test fixture 専用)。
    """
    holdout_n_bars = stage_windows.stage_c_holdout_days * _BARS_PER_DAY
    stage_a_n_bars = stage_windows.stage_a_window_days * _BARS_PER_DAY
    with SessionLocal() as session:
        pair = session.scalars(
            select(CurrencyPair).where(CurrencyPair.oanda_name == instrument)
        ).one_or_none()
        if pair is None:
            raise RuntimeError(f"currency_pair for {instrument} not found")
        meta = _meta_from_pair(pair)

        rows_b = session.scalars(
            select(PriceBarM1)
            .where(PriceBarM1.pair_id == pair.id)
            .where(PriceBarM1.bar_time >= dataset.start)
            .where(PriceBarM1.bar_time < dataset.end)
            .order_by(PriceBarM1.bar_time.asc())
        ).all()
        if not rows_b:
            raise RuntimeError(
                f"no bars for {instrument} in "
                f"[{dataset.start}, {dataset.end})"
            )
        bars_stage_b = [_bar_row_to_price_bar(r, instrument) for r in rows_b]

        holdout_end = dataset.end + timedelta(
            days=stage_windows.stage_c_holdout_days
        )
        rows_hold = session.scalars(
            select(PriceBarM1)
            .where(PriceBarM1.pair_id == pair.id)
            .where(PriceBarM1.bar_time >= dataset.end)
            .where(PriceBarM1.bar_time < holdout_end)
            .order_by(PriceBarM1.bar_time.asc())
        ).all()
        bars_holdout = [_bar_row_to_price_bar(r, instrument) for r in rows_hold]

    if not bars_holdout:
        if stage_windows.allow_stage_c_fallback_slice:
            slice_n = (
                holdout_n_bars
                if holdout_n_bars <= len(bars_stage_b)
                else len(bars_stage_b)
            )
            bars_holdout = bars_stage_b[-slice_n:]
            logger.warning(
                "run_ga.holdout_fallback_slice",
                instrument=instrument,
                n_bars=len(bars_holdout),
                note="using Stage B tail as Stage C (test/fixture mode)",
            )
        else:
            raise RuntimeError(
                f"no holdout bars for {instrument} in "
                f"[{dataset.end}, {holdout_end}); "
                f"set stage_windows.allow_stage_c_fallback_slice=true "
                f"ONLY for tests"
            )

    bars_stage_a = (
        bars_stage_b[-stage_a_n_bars:]
        if stage_a_n_bars <= len(bars_stage_b)
        else list(bars_stage_b)
    )
    return LaneBarsBundle(
        meta=meta,
        bars_stage_a=bars_stage_a,
        bars_stage_b=bars_stage_b,
        bars_holdout=bars_holdout,
    )


# ---------------------------------------------------------------------------
# Backtest config factory
# ---------------------------------------------------------------------------


def _make_bt_factory(
    dataset: DatasetConfig, backtest: BacktestSectionConfig
) -> Callable[[str], BacktestConfig]:
    def factory(instrument: str) -> BacktestConfig:
        return BacktestConfig(
            instrument=instrument,
            start=dataset.start,
            end=dataset.end,
            initial_cash=backtest.initial_cash,
            leverage=backtest.leverage,
            max_spread_bps=backtest.max_spread_bps,
            holding_cost_per_day_bps=backtest.holding_cost_per_day_bps,
            session_close_utc_hours=frozenset(backtest.session_close_utc_hours),
            bar_minutes=1,
        )

    return factory


# ---------------------------------------------------------------------------
# Breeding
# ---------------------------------------------------------------------------


def _tournament(
    pop: list[Genome],
    cache: dict[str, IndividualCacheEntry],
    rng: random.Random,
    k: int,
    feasibility_cfg: GAFeasibilityConfig,
) -> Genome:
    """``feasibility_cfg`` を見て fallback (cache 全体 infeasible) 判定後に max."""
    sample = rng.sample(pop, k=min(k, len(pop)))
    fallback = _is_all_infeasible(cache.values(), feasibility_cfg)
    return max(sample, key=lambda g: _selection_key(cache[g.name], fallback))


def _breed_next_gen(
    prev_pop: list[Genome],
    cache: dict[str, IndividualCacheEntry],
    ga_cfg: Any,  # GAConfig (from config.py)
    registry: dict[str, RandomGenSpec],
    rng: random.Random,
    gen: int,
) -> tuple[list[Genome], dict[str, tuple[str | None, str | None]]]:
    """次世代 genomes を生成。elite → crossover/mutate で埋める。

    elite 選抜 / tournament いずれも cache 全体スコープで一度だけ fallback 判定し、
    同一規則で sort / max するため、elite と tournament の規則不整合を回避する。
    """
    feasibility_cfg = ga_cfg.feasibility
    fallback = _is_all_infeasible(cache.values(), feasibility_cfg)
    sorted_pop = sorted(
        prev_pop,
        key=lambda g: _selection_key(cache[g.name], fallback),
        reverse=True,
    )
    elites = sorted_pop[: ga_cfg.elite_count]
    next_genomes: list[Genome] = []
    provenance: dict[str, tuple[str | None, str | None]] = {}
    for e in elites:
        new_name = f"g{gen}_i{len(next_genomes)}"
        renamed = replace(e, name=new_name)
        next_genomes.append(renamed)
        provenance[new_name] = (e.name, None)
    while len(next_genomes) < ga_cfg.population_size:
        p1 = _tournament(
            prev_pop, cache, rng, ga_cfg.tournament_size, feasibility_cfg
        )
        p2 = _tournament(
            prev_pop, cache, rng, ga_cfg.tournament_size, feasibility_cfg
        )
        if rng.random() < ga_cfg.crossover_rate:
            c1, c2 = crossover(p1, p2, rng, max_depth=ga_cfg.max_depth)
        else:
            c1, c2 = p1, p2
        c1 = mutate(
            c1,
            rng,
            ga_cfg.mutation_rate,
            max_clause=ga_cfg.max_clause,
            max_depth=ga_cfg.max_depth,
            registry=registry,
            n_edit_max=ga_cfg.n_edit_max,
        )
        c2 = mutate(
            c2,
            rng,
            ga_cfg.mutation_rate,
            max_clause=ga_cfg.max_clause,
            max_depth=ga_cfg.max_depth,
            registry=registry,
            n_edit_max=ga_cfg.n_edit_max,
        )
        name1 = f"g{gen}_i{len(next_genomes)}"
        r1 = replace(c1, name=name1)
        next_genomes.append(r1)
        provenance[name1] = (p1.name, p2.name)
        if len(next_genomes) < ga_cfg.population_size:
            name2 = f"g{gen}_i{len(next_genomes)}"
            r2 = replace(c2, name=name2)
            next_genomes.append(r2)
            provenance[name2] = (p1.name, p2.name)
    return next_genomes, provenance


# ---------------------------------------------------------------------------
# Cache update
# ---------------------------------------------------------------------------


def _update_cache(
    cache: dict[str, IndividualCacheEntry],
    population: list[Genome],
    archive: GenomeArchive,
    lane_id: str,
    generation: int,
    feasibility_cfg: GAFeasibilityConfig,
    stage_c_feasibility_apply: bool = True,
) -> None:
    """archive の row から fitness_pen / stage pass / feasibility を取り出し cache 更新.

    T031: ``feasibility_cfg.apply_from_generation <= generation`` で feasibility を
    実評価。archive 不在 (評価失敗) は明確に infeasible として violation を最大化。
    T045: ``stage_c_feasibility_apply=True`` で archive 行の total_pnl>0 ∧ trade_sharpe_raw>0
    を満たす個体に ``stage_c_feasible=True`` をセット (selection_score v3)。
    """
    apply = generation >= feasibility_cfg.apply_from_generation
    entry_min = feasibility_cfg.entry_count_min
    for g in population:
        row = archive.get_row_snapshot(lane_id, generation, g.name)
        if row is None:
            cache[g.name] = IndividualCacheEntry(
                generation=generation,
                fitness_pen=-math.inf,
                stage_a_pass=False,
                stage_b_pass=False,
                stage_c_pass=False,
                feasible=(not apply),
                violation_magnitude=float(entry_min) if apply else 0.0,
                stage_c_feasible=(not stage_c_feasibility_apply),
            )
            continue
        fp_raw = row.get("fitness_pen")
        try:
            fp = float(fp_raw) if fp_raw is not None else -math.inf
        except (TypeError, ValueError):
            fp = -math.inf
        tc_raw = row.get("trade_count")
        try:
            trade_count = int(tc_raw) if tc_raw is not None else 0
        except (TypeError, ValueError):
            trade_count = 0
        if apply:
            feasible = trade_count >= entry_min
            violation = max(0.0, float(entry_min - trade_count))
        else:
            feasible = True
            violation = 0.0
        # T045: stage_c_feasible 計算
        if stage_c_feasibility_apply:
            try:
                pnl = float(row.get("total_pnl") or 0.0)
            except (TypeError, ValueError):
                pnl = 0.0
            sharpe_raw = row.get("trade_sharpe_raw")
            try:
                sharpe = (
                    float(sharpe_raw) if sharpe_raw is not None else 0.0
                )
            except (TypeError, ValueError):
                sharpe = 0.0
            stage_c_feasible = (
                math.isfinite(pnl)
                and math.isfinite(sharpe)
                and pnl > 0.0
                and sharpe > 0.0
            )
        else:
            stage_c_feasible = True
        cache[g.name] = IndividualCacheEntry(
            generation=generation,
            fitness_pen=fp,
            stage_a_pass=bool(row.get("stage_a_pass", False)),
            stage_b_pass=bool(row.get("stage_b_pass", False)),
            stage_c_pass=bool(row.get("stage_c_pass", False)),
            feasible=feasible,
            violation_magnitude=violation,
            stage_c_feasible=stage_c_feasible,
        )


def _select_best(
    cache: Mapping[str, IndividualCacheEntry],
    feasibility_cfg: GAFeasibilityConfig,
) -> tuple[str, IndividualCacheEntry]:
    if not cache:
        raise RuntimeError("no individuals evaluated")
    fallback = _is_all_infeasible(cache.values(), feasibility_cfg)
    return max(
        cache.items(),
        key=lambda kv: _selection_key(kv[1], fallback),
    )


# ---------------------------------------------------------------------------
# Report writer
# ---------------------------------------------------------------------------


def _row_to_metrics_dict(row: Mapping[str, Any] | None) -> dict[str, Any]:
    if row is None:
        return {}

    def _dec_or_none(v: Any) -> str | None:
        return str(v) if v is not None else None

    # T-sharpe Phase 1A: report 出力の "sharpe" 列は trade_sharpe_raw (v2) を採用
    return {
        "total_pnl": str(row.get("total_pnl", "0")),
        "sharpe": _dec_or_none(row.get("trade_sharpe_raw")),
        "sortino": _dec_or_none(row.get("sortino")),
        "calmar": _dec_or_none(row.get("calmar")),
        "max_drawdown_pct": str(row.get("max_drawdown_pct", "0")),
        "trade_count": int(row.get("trade_count", 0)),
        "sharpe_calc_version": str(
            row.get("sharpe_calc_version") or "v1_bar_annualized"
        ),
    }


def _check_live_criteria(
    row: Mapping[str, Any] | None,
    criteria: Mapping[str, float | int],
) -> dict[str, Any]:
    if row is None:
        return {"checks": {}, "all_pass": False}
    checks: dict[str, dict[str, Any]] = {}

    # T-sharpe Phase 1A: live_criteria.sharpe_min は trade_sharpe_raw (v2) と比較。
    # v1 archive 行は sharpe_calc_version で識別し検査時に None 扱い (比較禁止)。
    raw_version = row.get("sharpe_calc_version")
    version = "v1_bar_annualized" if raw_version is None else str(raw_version)
    # v1/未知 archive 行は v2 sharpe_min と比較しない
    if version not in ("v1_bar_annualized", "v2_trade_level"):
        logger.warning(
            "live_criteria.unknown_sharpe_calc_version",
            sharpe_calc_version=version,
        )
    sharpe_raw = (
        row.get("trade_sharpe_raw") if version == "v2_trade_level" else None
    )
    sharpe_min = float(criteria.get("sharpe_min", 0.0))
    if sharpe_raw is None:
        checks["sharpe"] = {
            "value": None,
            "threshold": str(sharpe_min),
            "pass": False,
            "sharpe_calc_version": version,
        }
    else:
        sharpe_val = float(sharpe_raw)
        checks["sharpe"] = {
            "value": str(sharpe_val),
            "threshold": str(sharpe_min),
            "pass": sharpe_val >= sharpe_min,
            "sharpe_calc_version": version,
        }

    pnl_val = float(row.get("total_pnl", 0.0) or 0.0)
    pnl_min = float(criteria.get("total_pnl_min", 0.0))
    checks["total_pnl"] = {
        "value": str(pnl_val),
        "threshold": str(pnl_min),
        "pass": pnl_val >= pnl_min,
    }

    dd_pct = float(row.get("max_drawdown_pct", 0.0) or 0.0)  # 既に percent
    dd_frac = dd_pct / 100.0
    dd_max = float(criteria.get("max_drawdown_max", 1.0))
    checks["max_drawdown_pct"] = {
        "value": str(dd_pct),
        "threshold": str(dd_max * 100.0),
        "pass": dd_frac <= dd_max,
    }

    tc = int(row.get("trade_count", 0))
    tc_min = int(criteria.get("trade_count_min", 0))
    tc_max = int(criteria.get("trade_count_max", 10**9))
    checks["trade_count"] = {
        "value": tc,
        "threshold_min": tc_min,
        "threshold_max": tc_max,
        "pass": tc_min <= tc <= tc_max,
    }

    all_pass = all(c["pass"] for c in checks.values())
    return {"checks": checks, "all_pass": all_pass}


def _write_reports(
    *,
    run_dir: Path,
    cfg: AlphaFactoryConfig,
    run_id: str,
    run_number: int,
    bundle: LaneBarsBundle,
    per_generation: list[dict[str, Any]],
    best_name: str,
    best_entry: IndividualCacheEntry,
    best_genome: Genome,
    best_row: Mapping[str, Any] | None,
    final_population: list[Genome],
    final_population_cache: dict[str, IndividualCacheEntry],
    archive_path: Path,
    lane_manager: LaneManager,
    cross_pair_mode: str,
    now: datetime,
    diagnostics_sidecar_path: Path | None = None,
) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)

    best_fitness_val, best_finite = _safe_finite(best_entry.fitness_pen)
    best_fitness_str = _fitness_to_str(best_entry.fitness_pen)
    best_metrics = _row_to_metrics_dict(best_row)
    live_check = _check_live_criteria(best_row, cfg.live_criteria)

    # per_generation.best_fitness_pen を非有限値から保護する
    # (R1 impl-review B1: summary.json に -inf/nan が漏れる経路遮断)
    sanitized_per_generation: list[dict[str, Any]] = []
    for pg in per_generation:
        raw_fp = float(pg["best_fitness_pen"])
        finite_val, finite_flag = _safe_finite(raw_fp)
        sanitized_per_generation.append(
            {
                "generation": pg["generation"],
                "n_evaluated": pg["n_evaluated"],
                "stage_a_pass": pg["stage_a_pass"],
                "stage_b_pass": pg["stage_b_pass"],
                "stage_c_pass": pg["stage_c_pass"],
                "graduation_count": pg["graduation_count"],
                "best_fitness_pen": finite_val,
                "best_fitness_pen_finite": bool(finite_flag),
                "feasible_count": int(pg.get("feasible_count", 0)),
            }
        )

    summary: dict[str, Any] = {
        "run_id": run_id,
        "run_number": run_number,
        "generated_at": now.isoformat(),
        "dataset": {
            "instrument": cfg.dataset.instrument,
            "start": cfg.dataset.start.isoformat(),
            "end": cfg.dataset.end.isoformat(),
            "bars": len(bundle.bars_stage_b),
            "bars_stage_a": len(bundle.bars_stage_a),
            "bars_stage_b": len(bundle.bars_stage_b),
            "bars_holdout": len(bundle.bars_holdout),
        },
        "ga_config": {
            "population_size": cfg.ga.population_size,
            "generations": cfg.ga.generations,
            "crossover_rate": cfg.ga.crossover_rate,
            "mutation_rate": cfg.ga.mutation_rate,
            "tournament_size": cfg.ga.tournament_size,
            "elite_count": cfg.ga.elite_count,
            "max_depth": cfg.ga.max_depth,
            "max_clause": cfg.ga.max_clause,
            "units": cfg.backtest.units,
            "fitness_metric": cfg.ga.fitness_metric,
            "seed": cfg.ga.seed,
        },
        "backtest_config": {
            "initial_cash": str(cfg.backtest.initial_cash),
            "leverage": cfg.backtest.leverage,
            "units": cfg.backtest.units,
        },
        "stage_gate_config": {
            "stage_a_window_days": cfg.stage_gate.stage_a_window_days,
            "stage_a_alpha": cfg.stage_gate.stage_a_alpha,
            "stage_a_threshold": cfg.stage_gate.stage_a_threshold,
            "stage_b_window_months": cfg.stage_gate.stage_b_window_months,
            "stage_c_holdout_days": cfg.stage_gate.stage_c_holdout_days,
            "spread_stress_multiplier": cfg.stage_gate.spread_stress_multiplier,
        },
        "cross_pair_config": {
            "mode": cfg.cross_pair.mode,
            "aggregator_lambda": cfg.cross_pair.aggregator_lambda,
        },
        "cross_pair_runtime_mode": cross_pair_mode,
        "per_generation": sanitized_per_generation,
        "best": {
            "name": best_name,
            "generation": best_entry.generation,
            "fitness": best_fitness_str,
            "fitness_finite": bool(best_finite),
            "stage_a_pass": bool(best_entry.stage_a_pass),
            "stage_b_pass": bool(best_entry.stage_b_pass),
            "stage_c_pass": bool(best_entry.stage_c_pass),
            "feasible": bool(best_entry.feasible),
            "violation_magnitude": float(
                _safe_finite(best_entry.violation_magnitude)[0]
            ),
            # T045
            "stage_c_feasible": bool(best_entry.stage_c_feasible),
            "selection_score": [
                int(best_entry.feasible),
                -float(_safe_finite(best_entry.violation_magnitude)[0]),
                int(best_entry.stage_c_feasible),
                int(best_entry.stage_c_pass),
                int(best_entry.stage_b_pass),
                int(best_entry.stage_a_pass),
                float(best_fitness_val),
            ],
            "selection_score_schema": "v3_stage_c_feasibility",
            "metrics": best_metrics,
        },
        "live_criteria": live_check,
        "population_size": len(final_population),
        "graduation_count": lane_manager.promote_graduates(),
        "archive_parquet": str(archive_path),
    }
    # T033: 書き込み成功時のみ summary に sidecar path を追加
    # (consumer は missing field を無視できる契約)
    if diagnostics_sidecar_path is not None:
        try:
            summary["diagnostics_sidecar"] = str(
                diagnostics_sidecar_path.relative_to(REPO_ROOT)
            )
        except ValueError:
            summary["diagnostics_sidecar"] = str(diagnostics_sidecar_path)
    (run_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    history: list[dict[str, Any]] = []
    for pg in per_generation:
        history.append(
            {
                "generation": pg["generation"],
                "best_fitness": _fitness_to_str(
                    float(pg["best_fitness_pen"])
                ),
                "stage_a_pass": pg["stage_a_pass"],
                "stage_b_pass": pg["stage_b_pass"],
                "stage_c_pass": pg["stage_c_pass"],
                "graduation_count": pg["graduation_count"],
            }
        )
    (run_dir / "history.json").write_text(
        json.dumps(history, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    (run_dir / "best_genome.json").write_text(
        json.dumps(genome_to_dict(best_genome), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    with (run_dir / "population.jsonl").open("w", encoding="utf-8") as f:
        for g in final_population:
            ent = final_population_cache.get(g.name)
            fit_val = ent.fitness_pen if ent is not None else 0.0
            f.write(
                json.dumps(
                    {"name": g.name, "fitness": _fitness_to_str(fit_val)},
                    ensure_ascii=False,
                )
                + "\n"
            )


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    cfg = load_config(args.config, overrides=_args_to_overrides(args))

    if cfg.ga.fitness_metric != "sharpe":
        logger.warning(
            "run_ga.fitness_metric_override",
            requested=cfg.ga.fitness_metric,
            note=(
                "Phase 2: Stage A fitness_pen (sharpe - alpha*size_norm) を "
                "唯一の内部選択指標として使用。CLI/config の fitness_metric "
                "値は summary への記録のみで効かない"
            ),
        )

    now = datetime.now(tz=UTC)
    run_id = args.run_id or f"run_{now.strftime('%Y%m%d_%H%M%S')}"
    run_number = get_latest_run_number() + 1
    run_dir = RUN_REPORTS_DIR / f"run-{run_number}"

    logger.info(
        "ga.run.start",
        run_id=run_id,
        run_number=run_number,
        instrument=cfg.dataset.instrument,
        population_size=cfg.ga.population_size,
        generations=cfg.ga.generations,
    )

    ensure_registered()
    rg_registry = build_random_gen_registry()

    bundle = _load_lane_bars(
        cfg.dataset.instrument, cfg.dataset, cfg.stage_windows
    )

    archive = GenomeArchive(run_id=run_id, run_number=run_number)
    lane_id = f"tier1_{cfg.dataset.instrument}"

    primitive_evaluator = RegistryEvaluator(pair=cfg.dataset.instrument)
    bt_factory = _make_bt_factory(cfg.dataset, cfg.backtest)

    # T033: Stage A/B/C diagnostics を蓄積する run-level collector。
    # GA 完了後 sidecar Parquet として flush する。
    diagnostics_collector = DiagnosticsCollector()

    tier1_lane = Tier1Lane(
        lane_id=lane_id,
        instrument=cfg.dataset.instrument,
        bars_60d=bundle.bars_stage_a,
        bars_18m=bundle.bars_stage_b,
        bars_holdout=bundle.bars_holdout,
        meta=bundle.meta,
    )
    graduation_lane = GraduationLane(
        lane_id=GRADUATION_LANE_ID,
        pair_bars={},
        pair_meta={},
    )
    lane_manager = LaneManager(
        tier1={lane_id: tier1_lane},
        graduation=graduation_lane,
        stage_gate_config=cfg.stage_gate,
        cross_pair_config=cfg.cross_pair,
        primitive_evaluator=primitive_evaluator,
        archive=archive,
        backtest_config_factory=bt_factory,
        diagnostics_collector=diagnostics_collector,
    )
    cross_pair_mode = (
        "enabled" if graduation_lane.pair_bars
        else "skipped_single_instrument"
    )

    rng = random.Random(cfg.ga.seed)
    cache: dict[str, IndividualCacheEntry] = {}
    per_generation: list[dict[str, Any]] = []
    prev_population: list[Genome] = []
    genomes_by_name: dict[str, Genome] = {}

    for gen in range(cfg.ga.generations + 1):
        if gen == 0:
            population = [
                random_genome(
                    rng,
                    name=f"g0_i{i}",
                    units=cfg.backtest.units,
                    max_clause=cfg.ga.max_clause,
                    max_depth=cfg.ga.max_depth,
                    registry=rg_registry,
                )
                for i in range(cfg.ga.population_size)
            ]
            provenance: dict[str, tuple[str | None, str | None]] = {
                g.name: (None, None) for g in population
            }
        else:
            population, provenance = _breed_next_gen(
                prev_population, cache, cfg.ga, rg_registry, rng, gen
            )

        for g in population:
            genomes_by_name[g.name] = g

        # lane.generation_count は run_generation で +1 される。ここで使う
        # "この世代 ID" は呼び出し前の generation_count をキャプチャする。
        current_generation = tier1_lane.generation_count
        tier1_lane.population = population
        tier1_lane.provenance = provenance
        summary_out = lane_manager.run_generation(lane_id)
        _update_cache(
            cache,
            population,
            archive,
            lane_id,
            current_generation,
            cfg.ga.feasibility,
            stage_c_feasibility_apply=cfg.stage_gate.stage_c_feasibility_apply,
        )

        best_fp = max(
            (cache[g.name].fitness_pen for g in population),
            default=-math.inf,
        )
        feasible_count = sum(
            1
            for g in population
            if g.name in cache and cache[g.name].feasible
        )
        per_generation.append(
            {
                "generation": gen,
                "n_evaluated": int(summary_out["n_evaluated"]),
                "stage_a_pass": int(summary_out["stage_a_pass"]),
                "stage_b_pass": int(summary_out["stage_b_pass"]),
                "stage_c_pass": int(summary_out["stage_c_pass"]),
                "graduation_count": int(summary_out["graduation_count"]),
                "best_fitness_pen": best_fp,
                "feasible_count": feasible_count,
            }
        )
        prev_population = population

    archive_path = archive.flush()

    best_name, best_entry = _select_best(cache, cfg.ga.feasibility)
    best_row = archive.get_row_snapshot(
        lane_id, best_entry.generation, best_name
    )
    best_genome = genomes_by_name[best_name]

    # T033: Stage A diagnostics sidecar を _write_reports の前に flush して、
    # 書き込み成功時のみ summary.json に diagnostics_sidecar field を追加する。
    # --no-report 時は sidecar も skip (reports/ ディレクトリを触らない契約と整合)。
    sidecar_path_written: Path | None = None
    if not args.no_report:
        sidecar_path = REPO_ROOT / sidecar_relative_path(run_number)
        sidecar_path_written = write_stage_a_provenance(
            diagnostics_collector, sidecar_path
        )

    if not args.no_report:
        _write_reports(
            run_dir=run_dir,
            cfg=cfg,
            run_id=run_id,
            run_number=run_number,
            bundle=bundle,
            per_generation=per_generation,
            best_name=best_name,
            best_entry=best_entry,
            best_genome=best_genome,
            best_row=best_row,
            final_population=prev_population,
            final_population_cache=cache,
            archive_path=archive_path,
            lane_manager=lane_manager,
            cross_pair_mode=cross_pair_mode,
            now=now,
            diagnostics_sidecar_path=sidecar_path_written,
        )
    else:
        logger.info(
            "run_ga.skip_report",
            run_id=run_id,
            reason="--no-report",
            note="reports/run-reports/ was not touched (archive + cache only)",
        )

    RUN_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    (RUN_CACHE_DIR / f"{run_id}.json").write_text(
        json.dumps(
            {"run_id": run_id, "run_number": run_number},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    logger.info(
        "ga.run.done",
        run_id=run_id,
        run_number=run_number,
        best_name=best_name,
        best_fitness=str(best_entry.fitness_pen),
        stage_c_pass=best_entry.stage_c_pass,
    )
    report_field = "skipped(--no-report)" if args.no_report else str(run_dir)
    print(
        f"[done] run_id={run_id} run_number={run_number} "
        f"best={best_name} fitness_pen={best_entry.fitness_pen} "
        f"stage_c={best_entry.stage_c_pass} report={report_field}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
