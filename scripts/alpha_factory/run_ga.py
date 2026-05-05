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
import numbers
import os
import random
import sys
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal

import structlog
from sqlalchemy import select

from scripts.alpha_factory.get_latest_run_number import get_latest_run_number
from src.alpha_factory._registry_bridge import build_random_gen_registry
from src.alpha_factory.archive import GenomeArchive
from src.alpha_factory.aux_loader import AuxBundle, build_aux_bundle_from_db
from src.alpha_factory.aux_preflight import (
    HARD_REQUIRED_AUX,
    SOFT_REQUIRED_AUX,
    compute_extended_period,
    preflight_check_aux_data,
)
from src.alpha_factory.calibrate_gate_history import DEFAULT_HISTORY_PATH
from src.alpha_factory.calibrate_state import (
    compute_base_config_hash,
    compute_full_config_hash,
    load_calibrated_threshold,
)
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
from src.alpha_factory.epoch_manager import EpochWindow, make_epoch_id
from src.alpha_factory.observability import (
    build_default_archive_churn_metric,
    build_default_bypass_ratio_metric,
    build_default_failure_metric,
    build_default_feasible_ratio_metric,
    build_default_inflow_consistency_metric,
    build_default_q_force_recommendation,
    build_default_selection_metric,
    build_default_session_entropy_metric,
    build_run_observability_report,
    compute_ab_divergence_on_b_evaluated,
    serialize_run_observability_report,
)
from src.alpha_factory.parallel_eval import (
    GenomeEvaluator,
    LaneEvalContext,
    PreflightPayload,
    measure_peak_rss_mb,
)
from src.alpha_factory.primitives import RegistryEvaluator, ensure_registered
from src.alpha_factory.run_context import RunContext, generate_epoch_id_stub
from src.alpha_factory.schema_contract import (
    CASCADE_CONTRACT_VERSION,
    assert_run_report_v2,
)
from src.alpha_factory.stage_b_inconclusive import is_stage_b_inconclusive
from src.alpha_factory.stage_gate import STAGE_GATE_VERSION
from src.alpha_factory.stage_partition_guard import validate_stage_partition
from src.alpha_factory.swim_lane import (
    GRADUATION_LANE_ID,
    GraduationLane,
    LaneManager,
    Tier1Lane,
)
from src.alpha_factory.walk_forward import (
    compute_max_folds,
    n_unique_dates,
    wf_min_unique_dates,
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
    T046 v3.1: stage_b_pass を stage_c_feasible より前 (上位) に移動して
    Stage B 整合との両立を確保 (Run-20→21 で観測された B 退行 834→0 の解消)。
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
    def selection_score(self) -> tuple[int, float, int, int, int, int, int, float]:
        """Lexicographic 8-tuple v3.1:
        ``(feasible, -violation, stage_b_pass, stage_c_feasible, C_pass, B_pass, A_pass, fitness_pen)``.

        T046: stage_b_pass を stage_c_feasible より前に置き「Stage B 整合 + 単期間 PnL/Sharpe 正」
        の両立を構造的に保証。Run-21 で T045 単独 (v3) が Stage B passes を 834→0 に退行させた
        副作用を解消する。

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
            int(self.stage_b_pass),  # T046: Stage B 整合 priority
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
    # T052: GA 評価並列ワーカー数 (canonical: --max-workers, alias: --workers)
    p.add_argument(
        "--max-workers",
        type=int,
        default=None,
        help=(
            "GA 評価並列ワーカー数 (1 = sequential, 2 以上で multiprocessing.Pool)。"
            "未指定時は YAML config の値を使用 (default 1)。"
        ),
    )
    p.add_argument(
        "--workers",
        type=int,
        default=None,
        dest="workers_alias",
        help="--max-workers のエイリアス (zenigame との表記互換)",
    )
    p.add_argument(
        "--strict-memory-guard",
        action="store_true",
        help=(
            "max_workers が available_memory ベースの推奨値を超えたら "
            "起動時 fail-fast (autopilot 等で OOM を未然防止)。"
        ),
    )
    # T054: Stage A threshold CLI override (history より優先)
    p.add_argument(
        "--stage-a-threshold",
        type=float,
        default=None,
        help=(
            "Stage A threshold を CLI で明示指定 (history.jsonl override より優先)。"
            "未指定時は (1) history.jsonl の最新適用可能 record (2) config 値 の順で fallback。"
        ),
    )
    # T057 Phase 2 Gate C: aux preflight override (dev 用)
    p.add_argument(
        "--allow-aux-missing",
        action="store_true",
        help=(
            "preflight aux data check で hard_missing があっても fail-closed "
            "せず WARN log のみで継続する (dev / smoke test 用)。"
            "production では config strict_aux_required=true を維持し本 flag は外す。"
        ),
    )
    args = p.parse_args(argv)
    # alias 統合 (両方指定時は同値でなければエラー)
    if args.max_workers is None and args.workers_alias is not None:
        args.max_workers = args.workers_alias
    elif (
        args.max_workers is not None
        and args.workers_alias is not None
        and args.max_workers != args.workers_alias
    ):
        p.error(
            f"--max-workers ({args.max_workers}) と "
            f"--workers ({args.workers_alias}) が異なる値で指定されました"
        )
    return args


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
            "max_workers": args.max_workers,
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
    """DB から Stage A/B/C の 3 区間 bars + meta を取得する (T087)。

    - Stage A bars = ``[dataset.end - stage_a_window, dataset.end)``
    - Stage B bars = ``[dataset.start, dataset.end - stage_a_window)``
      (T087 で Stage A 期間を時系列上 disjoint に除外)
    - Stage C holdout = ``[dataset.end, dataset.end + holdout_days)``
      取得不能時は **fail-closed (RuntimeError)**。 fallback slice は廃止 (T087)。
    """
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
        bars_stage_b_full = [_bar_row_to_price_bar(r, instrument) for r in rows_b]

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
        # T087: fallback slice (Stage B 末尾を holdout に再利用) は廃止 (partition
        # guard の disjoint 検証と矛盾するため)。 test fixture は test-only helper で
        # LaneBarsBundle を直接構築する経路に切り替えること。
        raise RuntimeError(
            f"no holdout bars for {instrument} in "
            f"[{dataset.end}, {holdout_end}); "
            f"holdout fetch failed and fallback slice is no longer supported "
            f"(would violate stage partition disjoint contract; T087)"
        )

    # T087: Stage A 期間を bars_stage_b から時系列上 disjoint に除外する。
    # `>=` 判定で disjoint 後の bars_stage_b が空になるケースも同時に検出。
    if stage_a_n_bars >= len(bars_stage_b_full):
        raise RuntimeError(
            f"dataset too short for disjoint stage A/B: "
            f"stage_a_n_bars={stage_a_n_bars} >= "
            f"len(bars_stage_b_full)={len(bars_stage_b_full)} "
            f"(instrument={instrument}, dataset=[{dataset.start}, {dataset.end})). "
            f"Extend dataset or reduce stage_a_window_days."
        )
    bars_stage_a = bars_stage_b_full[-stage_a_n_bars:]
    bars_stage_b = bars_stage_b_full[:-stage_a_n_bars]

    logger.info(
        "run_ga.lane_bars_loaded",
        instrument=instrument,
        stage_a_bar_first=bars_stage_a[0].bar_time.isoformat(),
        stage_a_bar_last=bars_stage_a[-1].bar_time.isoformat(),
        stage_a_count=len(bars_stage_a),
        stage_b_bar_first=bars_stage_b[0].bar_time.isoformat(),
        stage_b_bar_last=bars_stage_b[-1].bar_time.isoformat(),
        stage_b_count=len(bars_stage_b),
        holdout_bar_first=bars_holdout[0].bar_time.isoformat(),
        holdout_bar_last=bars_holdout[-1].bar_time.isoformat(),
        holdout_count=len(bars_holdout),
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


def _coerce_n_fold_effective(value: object) -> int | None:
    """T087: archive row の n_fold_effective を summary 用に整数 or None へ正規化。

    is_stage_b_inconclusive と同じ型防御 (Integral 以外 / NaN / bool は None)
    で、 summary 生成時の ``int(...)`` 失敗による report 落下を防ぐ。
    """
    import math
    from numbers import Integral

    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    if not isinstance(value, Integral):
        return None
    return int(value)


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
    run_context: RunContext,
    diagnostics_sidecar_path: Path | None = None,
    peak_rss_per_generation: list[dict[str, float]] | None = None,
) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    # T058 PR 5: 全 artifact に同一 dataset_epoch_id を伝搬する SSOT (RunContext 経由)
    dataset_epoch_id = run_context.dataset_epoch_id

    best_fitness_val, best_finite = _safe_finite(best_entry.fitness_pen)
    best_fitness_str = _fitness_to_str(best_entry.fitness_pen)
    best_metrics = _row_to_metrics_dict(best_row)
    live_check = _check_live_criteria(best_row, cfg.live_criteria)

    # per_generation.best_fitness_pen を非有限値から保護する
    # (R1 impl-review B1: summary.json に -inf/nan が漏れる経路遮断)
    sanitized_per_generation: list[dict[str, Any]] = []
    for idx, pg in enumerate(per_generation):
        raw_fp = float(pg["best_fitness_pen"])
        finite_val, finite_flag = _safe_finite(raw_fp)
        # T052: 世代毎 RSS ピーク (測定された世代のみ追加 field として記録)
        # ga_worker_* (pool_pids 指定時) と all_children_* (fallback) のどちらか
        # 非ゼロ側を採用 (sequential or pool_pids fallback では all_children を使う)
        rss_for_gen: dict[str, float] = {}
        if peak_rss_per_generation is not None and idx < len(peak_rss_per_generation):
            rss = peak_rss_per_generation[idx]
            worker_max = float(rss.get("ga_worker_max_rss_mb", 0.0))
            worker_total = float(rss.get("ga_worker_total_rss_mb", 0.0))
            # fallback: all_children_* に集計されたケース
            if worker_max == 0.0 and worker_total == 0.0:
                worker_max = float(rss.get("all_children_max_rss_mb", 0.0))
                worker_total = float(rss.get("all_children_total_rss_mb", 0.0))
            rss_for_gen = {
                "peak_main_rss_mb": float(rss.get("main_rss_mb", 0.0)),
                "peak_rss_mb_per_worker": worker_max,
                "peak_total_rss_mb": float(
                    rss.get("main_rss_mb", 0.0) + worker_total
                ),
            }
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
                # T052: stage 別 timing (sum + max 併記、legacy path では 0.0)
                "stage_a_seconds_total": float(pg.get("stage_a_seconds_total", 0.0)),
                "stage_a_seconds_max": float(pg.get("stage_a_seconds_max", 0.0)),
                "stage_b_seconds_total": float(pg.get("stage_b_seconds_total", 0.0)),
                "stage_b_seconds_max": float(pg.get("stage_b_seconds_max", 0.0)),
                "stage_c_seconds_total": float(pg.get("stage_c_seconds_total", 0.0)),
                "stage_c_seconds_max": float(pg.get("stage_c_seconds_max", 0.0)),
                **rss_for_gen,
            }
        )

    # T052: schema_version bump (1.0 → 1.1)
    # 1.1 で追加: per_generation[*].stage_*_seconds_total/_max,
    #            per_generation[*].peak_*_rss_mb, top-level parallel_config,
    #            top-level max_rss_mb_per_worker
    # 後方互換: consumer は未知 field を無視する義務 (additionalProperties: true)
    #
    # T058 PR 5: ``cascade_contract_version`` (int=2) と ``dataset_epoch_id``
    # (string) を summary.json 先頭に追加 (詳細設計 行 1354-1362)。
    # ``schema_version`` は **string "1.1" のまま維持** (test 互換性、
    # 詳細設計 行 1404)。 cascade_contract_version は int で型分離。
    summary: dict[str, Any] = {
        "schema_version": "1.1",
        "cascade_contract_version": CASCADE_CONTRACT_VERSION,
        "dataset_epoch_id": dataset_epoch_id,
        "run_id": run_id,
        "run_number": run_number,
        "generated_at": now.isoformat(),
        "dataset": {
            "instrument": cfg.dataset.instrument,
            "start": cfg.dataset.start.isoformat(),
            "end": cfg.dataset.end.isoformat(),
            # T087: `bars` は disjoint 化前と同じ意味 (= dataset 全期間
            # = bars_stage_a + bars_stage_b の合計) を据え置き、 後方互換維持。
            "bars": len(bundle.bars_stage_a) + len(bundle.bars_stage_b),
            "bars_dataset_total": len(bundle.bars_stage_a)
            + len(bundle.bars_stage_b),
            "bars_stage_a": len(bundle.bars_stage_a),
            "bars_stage_b": len(bundle.bars_stage_b),
            "bars_holdout": len(bundle.bars_holdout),
            "bars_stage_b_excludes_stage_a": True,
            "stage_a_bar_first": bundle.bars_stage_a[0].bar_time.isoformat(),
            "stage_a_bar_last": bundle.bars_stage_a[-1].bar_time.isoformat(),
            "stage_b_bar_first": bundle.bars_stage_b[0].bar_time.isoformat(),
            "stage_b_bar_last": bundle.bars_stage_b[-1].bar_time.isoformat(),
            "holdout_bar_first": bundle.bars_holdout[0].bar_time.isoformat(),
            "holdout_bar_last": bundle.bars_holdout[-1].bar_time.isoformat(),
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
                int(best_entry.stage_b_pass),  # T046 v3.1
                int(best_entry.stage_c_feasible),
                int(best_entry.stage_c_pass),
                int(best_entry.stage_b_pass),
                int(best_entry.stage_a_pass),
                float(best_fitness_val),
            ],
            "selection_score_schema": "v3_1_stage_b_priority",
            "metrics": best_metrics,
        },
        "stage_b": {
            # T087: best 個体ぶんの n_fold_effective を summary level で参照可能に
            # (downstream consumer / report 側の inconclusive 判定 SSOT)。
            # is_stage_b_inconclusive と整合した型防御 (Integral 以外は None)。
            "n_fold_effective": _coerce_n_fold_effective(
                best_row.get("n_fold_effective") if best_row is not None else None
            ),
            "statistical_inconclusive": is_stage_b_inconclusive(
                best_row.get("n_fold_effective") if best_row is not None else None
            ),
        },
        "live_criteria": live_check,
        "population_size": len(final_population),
        "graduation_count": lane_manager.promote_graduates(),
        "archive_parquet": str(archive_path),
        # T052: 並列実行設定と RSS ピーク (RUN 全体最大)
        "parallel_config": {
            "max_workers": cfg.ga.max_workers,
            "mode": "parallel" if cfg.ga.max_workers > 1 else "sequential",
        },
        "max_rss_mb_per_worker": float(
            max(
                (
                    max(
                        rss.get("ga_worker_max_rss_mb", 0.0),
                        rss.get("all_children_max_rss_mb", 0.0),
                    )
                    for rss in (peak_rss_per_generation or [])
                ),
                default=0.0,
            )
        ),
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
    # T058 PR 5: passive validation (LOG_ONLY default で warning のみ、
    # FAIL_CLOSED で必須 field 欠落 raise)
    assert_run_report_v2(summary, mode=cfg.schema_contract.to_mode())
    (run_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    history: list[dict[str, Any]] = []
    for pg in per_generation:
        history.append(
            {
                # T058 PR 5: 各世代 entry にも dataset_epoch_id 付与 (詳細設計 行 1366-1370)
                "dataset_epoch_id": dataset_epoch_id,
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

    # T058 PR 5: best_genome.json に dataset_epoch_id を merge
    # (詳細設計 行 1372-1373、 既存 genome_to_dict 構造に同一 epoch_id を追加)
    best_genome_payload: dict[str, Any] = {"dataset_epoch_id": dataset_epoch_id}
    best_genome_payload.update(genome_to_dict(best_genome))
    (run_dir / "best_genome.json").write_text(
        json.dumps(best_genome_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    with (run_dir / "population.jsonl").open("w", encoding="utf-8") as f:
        for g in final_population:
            ent = final_population_cache.get(g.name)
            fit_val = ent.fitness_pen if ent is not None else 0.0
            # T058 PR 5: 各 line に dataset_epoch_id 付与 (詳細設計 行 1375-1377)
            f.write(
                json.dumps(
                    {
                        "dataset_epoch_id": dataset_epoch_id,
                        "name": g.name,
                        "fitness": _fitness_to_str(fit_val),
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


def _check_memory_budget(max_workers: int, strict: bool) -> None:
    """T052: max_workers が available memory budget を超えたら warning。

    `--strict-memory-guard` 指定時は SystemExit (autopilot 等で OOM 防止)。
    1 worker あたり 約 400MB (保守的試算) + main 400MB + OS マージン 4GB を仮定。
    """
    try:
        import psutil
    except ImportError:
        return  # psutil 不在ならスキップ
    available_mb = psutil.virtual_memory().available / 1024 / 1024
    worker_budget_mb = available_mb - 4096
    recommended_max = max(1, int(worker_budget_mb // 400))
    if max_workers > recommended_max:
        logger.warning(
            "run_ga.max_workers_exceeds_memory_budget",
            requested=max_workers,
            recommended=recommended_max,
            available_mb=int(available_mb),
        )
        if strict:
            raise SystemExit(
                f"strict-memory-guard: max_workers={max_workers} > "
                f"recommended {recommended_max} "
                f"(available_mb={int(available_mb)})"
            )


def _aggregate_ab_summary(
    *,
    summary_out: Mapping[str, Any],
    all_ab_score_pairs: list[tuple[float, float]],
    b_evaluated_count: int,
    excluded_preflight_count: int,
    current_score_source: str | None,
) -> tuple[int, int, str | None]:
    """T081 step 1: lane_manager.run_generation の summary_out から AB pair / counter
    / source 集約 (詳細設計 § 3.4.3)。

    破壊的更新: ``all_ab_score_pairs`` に extend する。

    Args:
        summary_out: lane_manager.run_generation の戻り dict (= ab_score_pairs /
            ab_score_source / ab_b_evaluated_count / ab_excluded_preflight_count
            の必須 4 キーを含む)。
        all_ab_score_pairs: Run loop 全世代の集約 list (in-place extend)。
        b_evaluated_count: 集約済 b_evaluated_count (= 累積)。
        excluded_preflight_count: 集約済 excluded_preflight_count (= 累積)。
        current_score_source: 現在までに観測した source (= None / "noop" / Phase 1 source)。

    Returns:
        ``(new_b_evaluated_count, new_excluded_preflight_count, new_score_source)``

    Raises:
        RuntimeError: ab_score_source が run 内で異なる値が観測された場合
            (= mixing 禁止、 Codex Round 1 [Critical] 1 取込)。
    """
    new_pairs = summary_out.get("ab_score_pairs", [])
    if new_pairs:
        for pair in new_pairs:
            # consumer 側 defensive: numbers.Real (= numpy 数値型 covered) +
            # bool 除外 (= producer 側でも弾いているが二重防御、 impl-review Round 1
            # [Suggestion] 取込)
            if (
                isinstance(pair, tuple)
                and len(pair) == 2
                and isinstance(pair[0], numbers.Real)
                and not isinstance(pair[0], bool)
                and isinstance(pair[1], numbers.Real)
                and not isinstance(pair[1], bool)
            ):
                all_ab_score_pairs.append(
                    (float(pair[0]), float(pair[1]))
                )
    new_b_evaluated = b_evaluated_count + int(
        summary_out.get("ab_b_evaluated_count", 0)
    )
    new_excluded = excluded_preflight_count + int(
        summary_out.get("ab_excluded_preflight_count", 0)
    )
    new_source_value = summary_out.get("ab_score_source", "noop")
    new_score_source: str | None = current_score_source
    if isinstance(new_source_value, str) and new_source_value != "noop":
        if new_score_source is None:
            new_score_source = new_source_value
        elif new_score_source != new_source_value:
            raise RuntimeError(
                f"ab_score_source mixing detected: "
                f"existing={new_score_source!r} new={new_source_value!r}"
            )
    return new_b_evaluated, new_excluded, new_score_source


def _resolve_stage_a_threshold(
    cfg: AlphaFactoryConfig,
    *,
    cli_override: float | None,
    history_path: Path,
    dataset_epoch_id: str,
) -> tuple[float, Literal["config", "history", "cli"]]:
    """T054: Stage A threshold の effective 値と source を確定する。

    優先順位:
        1. CLI override (--stage-a-threshold) があれば最優先 → source="cli"
        2. history.jsonl の最新適用可能 record (cross-run guard 通過) → source="history"
        3. config 値 (yaml load 値) → source="config"

    cross-run contamination guard (load_calibrated_threshold) で
    base_config_hash / dataset_span / instrument / stage_gate_version /
    dataset_epoch_id の AND 一致確認 + decision filter (tighten/loosen) を行う。

    T058 PR 5: ``dataset_epoch_id`` を caller (RunContext 経由) から受取り、
    PR 3 の literal "epoch_legacy" 直書きを置換 (詳細設計 行 1078-1085)。
    """
    # 1. CLI override 優先
    if cli_override is not None:
        return float(cli_override), "cli"

    # 2. history.jsonl から override 試行
    base_hash = compute_base_config_hash(cfg)
    dataset_span = (str(cfg.dataset.start), str(cfg.dataset.end))
    # T058 PR 5: dataset_epoch_id を RunContext 経由で受け取る (synthesis § 12.1)
    calibrated = load_calibrated_threshold(
        history_path=history_path,
        base_config_hash=base_hash,
        dataset_epoch_id=dataset_epoch_id,
        dataset_span=dataset_span,
        instrument=cfg.dataset.instrument,
        stage_gate_version=STAGE_GATE_VERSION,
    )
    if calibrated is not None:
        return calibrated, "history"

    # 3. config 値 fallback
    return cfg.stage_gate.stage_a_threshold, "config"


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    cfg = load_config(args.config, overrides=_args_to_overrides(args))

    # T059: dataset_epoch_id の deterministic 生成 (T058 stub からの卒業).
    # RunContext は run_id 確定後 (下方) に生成するが、 threshold 解決が
    # それより前にあるため、 epoch_id 値だけ先取りして両方に渡す SSOT。
    #
    # 戦略: ``make_epoch_id(EpochWindow(start, end))`` で deterministic 生成。
    # cfg.dataset の (start, end) を window として直接使う (Phase 2 で
    # ``EpochManager.reserve_run_slot`` 経由に切替予定)。
    # backward compat: ``EpochWindow.__post_init__`` の ``ValueError`` (= end<=start)
    # は cfg load 時点で既に弾かれている (config.py: ``DatasetConfig.__post_init__``)
    # が、 万一の防御として ``ValueError`` のみ捕捉して ``generate_epoch_id_stub``
    # に fallback する (= T058 PR 1-7 の規範、 silent regression を避けるため
    # warning log を必ず出力)。 broad ``except Exception`` は意図的に避け、
    # 真に想定された例外型のみ救済する (Codex impl-review-pr1 Round 1 NIT C1)。
    try:
        dataset_epoch_id = make_epoch_id(
            EpochWindow(start=cfg.dataset.start, end=cfg.dataset.end)
        )
    except ValueError as exc:
        logger.warning(
            "run_ga.epoch_id_deterministic_fallback",
            error=str(exc),
            fallback_to="generate_epoch_id_stub",
        )
        dataset_epoch_id = generate_epoch_id_stub(cfg.dataset)

    # T054: Stage A threshold の effective 値と source を確定し cfg に反映する。
    # source 単一値 ("config" | "history" | "cli") を必ず確定 (詳細設計 §0b)。
    repo_root = Path(__file__).resolve().parents[2]
    history_path = repo_root / DEFAULT_HISTORY_PATH
    effective_threshold, threshold_source = _resolve_stage_a_threshold(
        cfg,
        cli_override=args.stage_a_threshold,
        history_path=history_path,
        dataset_epoch_id=dataset_epoch_id,
    )
    if effective_threshold != cfg.stage_gate.stage_a_threshold:
        logger.info(
            "stage_gate.threshold_override",
            old=cfg.stage_gate.stage_a_threshold,
            new=effective_threshold,
            source=threshold_source,
        )
        # frozen dataclass なので replace で書き換え (cfg / cfg.stage_gate 両方 frozen)
        cfg = replace(
            cfg,
            stage_gate=replace(
                cfg.stage_gate, stage_a_threshold=effective_threshold
            ),
        )
    # 必ず effective threshold + source を log 出力 (V0-B、source 単一値で確定)
    logger.info(
        "stage_gate.effective_threshold",
        stage_a_threshold=cfg.stage_gate.stage_a_threshold,
        source=threshold_source,
        full_config_hash=compute_full_config_hash(cfg),
    )

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

    # T058 PR 5: RunContext 生成 (詳細設計 行 1334-1341)
    # 1 Run スコープで固定される runtime context。 archive / report 全
    # artifact が同じ source から dataset_epoch_id 等を読む SSOT。
    run_context = RunContext(
        run_id=run_id,
        run_number=run_number,
        dataset_epoch_id=dataset_epoch_id,
        base_config_hash=compute_base_config_hash(cfg),
        instrument=cfg.dataset.instrument,
    )

    logger.info(
        "ga.run.start",
        run_id=run_id,
        run_number=run_number,
        instrument=cfg.dataset.instrument,
        population_size=cfg.ga.population_size,
        generations=cfg.ga.generations,
        dataset_epoch_id=dataset_epoch_id,
    )

    ensure_registered()
    rg_registry = build_random_gen_registry()

    bundle = _load_lane_bars(
        cfg.dataset.instrument, cfg.dataset, cfg.stage_windows
    )

    # T087: Stage Partition Integrity Guard (fail-closed)。
    # aux_preflight より前に呼ぶ理由: bars 区間が壊れていれば aux 評価は意味がない。
    # 違反時は StagePartitionInputError / StagePartitionLeakError で起動停止。
    validate_stage_partition(
        bundle.bars_stage_a,
        bundle.bars_stage_b,
        bundle.bars_holdout,
    )
    logger.info(
        "run_ga.stage_partition_guard.passed",
        instrument=cfg.dataset.instrument,
        stage_gate_version=STAGE_GATE_VERSION,
    )

    # T058 PR 5: archive に RunContext + enforcement_mode を注入
    # (詳細設計 行 1344-1349)。 既存 backward compat (run_context=None) は
    # 維持されるが、 production 経路では必ず RunContext を渡す。
    archive = GenomeArchive(
        run_id=run_id,
        run_number=run_number,
        run_context=run_context,
        enforcement_mode=cfg.schema_contract.to_mode(),
    )
    lane_id = f"tier1_{cfg.dataset.instrument}"

    # T057 Phase 2 Gate B/C: aux preflight + AuxBundle 構築
    # CLI > config の優先順位: --allow-aux-missing が指定されたら strict 無効化
    effective_strict = cfg.stage_gate.strict_aux_required and not args.allow_aux_missing
    logger.info(
        "preflight.effective_strict_mode",
        strict=effective_strict,
        config_strict=cfg.stage_gate.strict_aux_required,
        cli_allow_aux_missing=args.allow_aux_missing,
        source=("cli_override" if args.allow_aux_missing else "config"),
    )
    aux_bundle: AuxBundle | None = None
    try:
        with SessionLocal() as aux_session:
            preflight_period = (cfg.dataset.start, cfg.dataset.end)
            preflight_result = preflight_check_aux_data(
                db_session=aux_session,
                period=preflight_period,
                stage_b_window_months=cfg.stage_gate.stage_b_window_months,
                stage_c_holdout_days=cfg.stage_gate.stage_c_holdout_days,
                allow_missing=not effective_strict,
            )
            logger.info(
                "preflight.aux_data_check",
                hard_satisfied=preflight_result.hard_satisfied,
                hard_missing=preflight_result.hard_missing,
                soft_satisfied=preflight_result.soft_satisfied,
                soft_missing=preflight_result.soft_missing,
                coverage_pct=preflight_result.coverage_pct_by_series,
            )
            # AuxBundle を 1 度だけ構築 (raw)
            # Codex impl-review-round-1 [Critical]: preflight と同じ拡張期間を
            # 使う必要がある (Stage B 18ヶ月 history + Stage C holdout)。
            # dataset 期間だけでは Stage B/holdout の bars に対応する aux 観測が
            # 0 埋め経路に落ちる ("preflight 通過したのに評価で safe default"
            # 値伝搬漏れリスク)。
            all_series = list(HARD_REQUIRED_AUX.keys()) + list(
                SOFT_REQUIRED_AUX.keys()
            )
            extended_period = compute_extended_period(
                preflight_period,
                stage_b_window_months=cfg.stage_gate.stage_b_window_months,
                stage_c_holdout_days=cfg.stage_gate.stage_c_holdout_days,
            )
            aux_bundle = build_aux_bundle_from_db(
                db_session=aux_session,
                period=extended_period,
                series_ids=all_series,
                aux_pairs=("EUR_USD", "USD_JPY"),
            )
            logger.info(
                "preflight.aux_bundle_built",
                daily_series_count=len(aux_bundle.daily_series),
                aux_pair_bars_count=sum(
                    len(v) for v in aux_bundle.aux_pair_bars_index.values()
                ),
                event_calendar_loaded=aux_bundle.event_calendar is not None,
                vix_snapshot_loaded=aux_bundle.vix_snapshot is not None,
            )
    except Exception as exc:
        # preflight が effective_strict=True で失敗 → re-raise (fail-closed)
        # それ以外は WARN log を残して aux_bundle=None で継続 (safe default 経路)
        if effective_strict:
            raise
        logger.warning(
            "preflight.aux_bundle_build_failed",
            error=str(exc),
            note="continuing with aux_bundle=None (safe default path)",
        )
        aux_bundle = None

    primitive_evaluator = RegistryEvaluator(pair=cfg.dataset.instrument)
    bt_factory = _make_bt_factory(cfg.dataset, cfg.backtest)

    # T033: Stage A/B/C diagnostics を蓄積する run-level collector。
    # GA 完了後 sidecar Parquet として flush する。
    diagnostics_collector = DiagnosticsCollector()

    tier1_lane = Tier1Lane(
        lane_id=lane_id,
        instrument=cfg.dataset.instrument,
        bars_60d=bundle.bars_stage_a,
        bars_stage_b=bundle.bars_stage_b,
        bars_holdout=bundle.bars_holdout,
        meta=bundle.meta,
    )
    graduation_lane = GraduationLane(
        lane_id=GRADUATION_LANE_ID,
        pair_bars={},
        pair_meta={},
    )
    cross_pair_mode = (
        "enabled" if graduation_lane.pair_bars
        else "skipped_single_instrument"
    )

    # T052: GenomeEvaluator を構築 (max_workers=1 で in-process / >1 で Pool)。
    # LaneEvalContext は RUN 中 immutable (Pool initializer で 1 度だけ broadcast)。
    #
    # preflight 値 (Stage B fold 不足判定) を RUN 開始時に計算して context に
    # 埋め込む。これにより worker 側 evaluate_genome が Stage A pass 後に Stage
    # B/C を短絡 skip でき、無駄計算を排除できる (Codex impl-review §1 Critical)。
    bars_b_list = list(bundle.bars_stage_b)
    lane_n_unique_dates = n_unique_dates(bars_b_list)
    wf_min_dates = wf_min_unique_dates(
        cfg.stage_gate.wf_train_days,
        cfg.stage_gate.wf_embargo_days,
        cfg.stage_gate.wf_test_days,
    )
    lane_max_folds = compute_max_folds(
        lane_n_unique_dates,
        cfg.stage_gate.wf_train_days,
        cfg.stage_gate.wf_embargo_days,
        cfg.stage_gate.wf_test_days,
        cfg.stage_gate.wf_step_days,
    )
    wf_min_folds = cfg.stage_gate.wf_min_folds_required
    preflight_underfilled = lane_max_folds < wf_min_folds
    preflight_payload = PreflightPayload(
        n_unique_dates=lane_n_unique_dates,
        wf_min_unique_dates=wf_min_dates,
        max_folds=lane_max_folds,
        wf_min_folds_required=wf_min_folds,
        n_bars=len(bars_b_list),
    )

    lane_ctx = LaneEvalContext(
        lane_id=lane_id,
        bars_a=tuple(bundle.bars_stage_a),
        bars_b=tuple(bundle.bars_stage_b),
        bars_holdout=tuple(bundle.bars_holdout),
        meta=bundle.meta,
        bt_cfg=bt_factory(cfg.dataset.instrument),
        cp_inputs=None,  # Phase 2: graduation.pair_bars が空のため None
        preflight_underfilled=preflight_underfilled,
        preflight_payload=preflight_payload,
        aux_bundle=aux_bundle,  # T057 Phase 2: stage 別 align 用 raw container
    )
    # T052: max_workers が available memory budget を超えたら warning
    # (--strict-memory-guard 指定時のみ fail-fast)
    _check_memory_budget(cfg.ga.max_workers, args.strict_memory_guard)
    if cfg.ga.max_workers > os.cpu_count() if os.cpu_count() else False:
        logger.warning(
            "run_ga.max_workers_exceeds_cpu_count",
            requested=cfg.ga.max_workers,
            cpu_count=os.cpu_count(),
        )
    logger.info(
        "run_ga.parallel_mode",
        max_workers=cfg.ga.max_workers,
        mode="parallel" if cfg.ga.max_workers > 1 else "sequential",
    )

    # GA loop は GenomeEvaluator の `with` 文内で実行 (close 漏れ防止)
    per_generation: list[dict[str, Any]] = []
    prev_population: list[Genome] = []
    genomes_by_name: dict[str, Genome] = {}
    cache: dict[str, IndividualCacheEntry] = {}
    rng = random.Random(cfg.ga.seed)
    peak_rss_per_generation: list[dict[str, float]] = []

    with GenomeEvaluator(
        max_workers=cfg.ga.max_workers,
        stage_gate_cfg=cfg.stage_gate,
        cross_pair_cfg=cfg.cross_pair,
        prim_evaluator=primitive_evaluator,
        lane_contexts={lane_id: lane_ctx},
    ) as genome_evaluator:
        lane_manager = LaneManager(
            tier1={lane_id: tier1_lane},
            graduation=graduation_lane,
            stage_gate_config=cfg.stage_gate,
            cross_pair_config=cfg.cross_pair,
            primitive_evaluator=primitive_evaluator,
            archive=archive,
            backtest_config_factory=bt_factory,
            diagnostics_collector=diagnostics_collector,
            genome_evaluator=genome_evaluator,
        )

        # T081 step 1: ABDivergenceMetric 実値配線用集約 (詳細設計 § 3.4.3)
        # 全世代の (a_score, b_score) ペアを list で集約 (= 衝突回避)。
        # ab_score_source は run 内で不変、 異なる source を検出したら fail-fast。
        all_ab_score_pairs: list[tuple[float, float]] = []
        all_ab_b_evaluated_count = 0
        all_ab_excluded_preflight_count = 0
        ab_score_source: str | None = None  # run 内 mixing 検出用 (= None / "noop" 以外で固定)

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
            # T081 step 1: AB pair 集約 (詳細設計 § 3.4.3、 helper 化で test 可能)
            (
                all_ab_b_evaluated_count,
                all_ab_excluded_preflight_count,
                ab_score_source,
            ) = _aggregate_ab_summary(
                summary_out=summary_out,
                all_ab_score_pairs=all_ab_score_pairs,
                b_evaluated_count=all_ab_b_evaluated_count,
                excluded_preflight_count=all_ab_excluded_preflight_count,
                current_score_source=ab_score_source,
            )
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
            # T052: stage 別 timing を per_generation に伝搬
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
                    # T052: stage 別 timing (legacy path で未提供時は 0.0)
                    "stage_a_seconds_total": float(
                        summary_out.get("stage_a_seconds_total", 0.0)
                    ),
                    "stage_a_seconds_max": float(
                        summary_out.get("stage_a_seconds_max", 0.0)
                    ),
                    "stage_b_seconds_total": float(
                        summary_out.get("stage_b_seconds_total", 0.0)
                    ),
                    "stage_b_seconds_max": float(
                        summary_out.get("stage_b_seconds_max", 0.0)
                    ),
                    "stage_c_seconds_total": float(
                        summary_out.get("stage_c_seconds_total", 0.0)
                    ),
                    "stage_c_seconds_max": float(
                        summary_out.get("stage_c_seconds_max", 0.0)
                    ),
                }
            )
            # T052: 世代終了時 RSS ピーク測定
            # pool_pids が空 (sequential or AttributeError fallback) なら
            # None を渡して all_children_* 経路で集計
            # (parallel_eval.measure_peak_rss_mb の契約に従う)
            _pids = genome_evaluator.pool_pids
            peak_rss_per_generation.append(
                measure_peak_rss_mb(pool_pids=_pids if _pids else None)
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
    # T058 PR 5: write_stage_a_provenance に run_context / mode を伝搬 (PR 4 で
    # optional 化された kwargs を production 経路で必ず渡す)。
    sidecar_path_written: Path | None = None
    if not args.no_report:
        sidecar_path = REPO_ROOT / sidecar_relative_path(run_number)
        sidecar_path_written = write_stage_a_provenance(
            diagnostics_collector,
            sidecar_path,
            run_context=run_context,
            mode=cfg.schema_contract.to_mode(),
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
            run_context=run_context,
            diagnostics_sidecar_path=sidecar_path_written,
            peak_rss_per_generation=peak_rss_per_generation,
        )
    else:
        logger.info(
            "run_ga.skip_report",
            run_id=run_id,
            reason="--no-report",
            note="reports/run-reports/ was not touched (archive + cache only)",
        )

    # T081 step 1: RunObservabilityReport を JSON 出力
    # ABDivergenceMetric のみ実値配線、 残り 8 metric は stub default (= 後続 step 2-6 で実値置換)。
    # 詳細設計: devnotes/20260502-2206-todo-T081-observability-real-values/detailed-design.md § 3.4.3
    # --no-report 時は reports/ ディレクトリを触らない契約と整合 (skip).
    if not args.no_report:
        # 診断 log (Codex Round 1 [Warning] 4 取込: preflight 除外可視化)
        logger.info(
            "ga.observability.ab_score_pairs_collected",
            run_id=run_id,
            n_pairs=len(all_ab_score_pairs),
            b_evaluated_count=all_ab_b_evaluated_count,
            excluded_preflight_count=all_ab_excluded_preflight_count,
            score_source=ab_score_source or "noop",
        )
        # ABDivergenceMetric 実値計算 (= list[tuple] → Sequence[Decimal] 2 本に分解)
        a_scores = [Decimal(repr(a)) for a, _ in all_ab_score_pairs]
        b_scores = [Decimal(repr(b)) for _, b in all_ab_score_pairs]
        ab_divergence_metric = compute_ab_divergence_on_b_evaluated(
            a_scores, b_scores
        )
        # 残り 8 metric は default constructor で stub default を取得 (= 後続 step で実値置換)
        observability_report = build_run_observability_report(
            run_id=run_id,
            dataset_epoch_id=run_context.dataset_epoch_id,
            generation_count=cfg.ga.generations,
            ab_divergence=ab_divergence_metric,  # ← step 1 で実値
            q_force_recommendation=build_default_q_force_recommendation(),
            archive_churn=build_default_archive_churn_metric(),
            bypass_ratio=build_default_bypass_ratio_metric(),
            session_entropy=build_default_session_entropy_metric(),
            feasible_ratio=build_default_feasible_ratio_metric(),
            selection=build_default_selection_metric(),
            inflow_consistency=build_default_inflow_consistency_metric(),
            failure=build_default_failure_metric(run_id),
        )
        observability_path = run_dir / "observability.json"
        observability_path.write_text(
            serialize_run_observability_report(observability_report),
            encoding="utf-8",
        )
        logger.info(
            "ga.observability.report_written",
            run_id=run_id,
            path=str(observability_path),
            ab_divergence_status=ab_divergence_metric.status,
            ab_divergence_n_pairs=ab_divergence_metric.n_pairs,
            note="T081 step 1: ABDivergenceMetric 実値、 残 8 metric は stub default",
        )

    # T058 PR 5: run cache JSON に dataset_epoch_id を伝搬 (詳細設計 行 1379-1381)
    RUN_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    (RUN_CACHE_DIR / f"{run_id}.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "run_number": run_number,
                "dataset_epoch_id": run_context.dataset_epoch_id,
            },
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
