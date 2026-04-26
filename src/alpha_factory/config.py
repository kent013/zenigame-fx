"""Alpha Factory run-time config loader (T018)。

``config/alpha_factory/default.yaml`` を frozen dataclass の階層に変換する。
CLI override (dict) を deep-merge して最終値を決定する。

SSOT:
    - ``live_criteria`` は :class:`StageGateConfig` に一元化する
      (``AlphaFactoryConfig.live_criteria`` は alias property)。
    - ``cross_pair`` / ``stage_gate`` dataclass は既存 SSOT (src/alpha_factory)
      をそのまま再利用する (re-export)。

設計根拠:
    - devnotes/20260423-2324-run-ga-full-rewrite/detailed-design.md §2
    - devnotes/20260423-2324-run-ga-full-rewrite/detailed-design-r2.md
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal

import yaml  # type: ignore[import-untyped]

from src.alpha_factory.cross_pair import CrossPairConfig
from src.alpha_factory.stage_gate import StageGateConfig
from src.utils.time import to_utc

__all__ = [
    "AlphaFactoryConfig",
    "BacktestSectionConfig",
    "CrossPairConfig",
    "DatasetConfig",
    "GAConfig",
    "GAFeasibilityConfig",
    "StageGateConfig",
    "StageWindowsConfig",
    "load_config",
]


# ---------------------------------------------------------------------------
# dataclass 階層
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DatasetConfig:
    """Dataset 範囲 (instrument / start / end). 既存 summary 互換を維持。"""

    instrument: str
    start: datetime
    end: datetime

    def __post_init__(self) -> None:
        if not self.instrument:
            raise ValueError("dataset.instrument must be non-empty")
        if self.end <= self.start:
            raise ValueError(
                f"dataset.end ({self.end}) must be > dataset.start "
                f"({self.start})"
            )


@dataclass(frozen=True)
class BacktestSectionConfig:
    """Backtest 設定。``BacktestConfig`` (engine) へ渡す際は instrument を
    factory 側で付与する。"""

    initial_cash: Decimal
    leverage: int
    units: int
    max_spread_bps: Decimal | None = None
    holding_cost_per_day_bps: Decimal = Decimal("0")
    session_close_utc_hours: tuple[int, ...] = (23,)

    def __post_init__(self) -> None:
        if self.leverage < 1:
            raise ValueError(f"backtest.leverage must be >= 1: {self.leverage}")
        if self.units < 1:
            raise ValueError(f"backtest.units must be >= 1: {self.units}")
        if self.holding_cost_per_day_bps < 0:
            raise ValueError(
                f"backtest.holding_cost_per_day_bps must be >= 0: "
                f"{self.holding_cost_per_day_bps}"
            )
        if self.max_spread_bps is not None and self.max_spread_bps < 0:
            raise ValueError(
                f"backtest.max_spread_bps must be >= 0 when set: "
                f"{self.max_spread_bps}"
            )
        for h in self.session_close_utc_hours:
            if not 0 <= h <= 23:
                raise ValueError(
                    f"backtest.session_close_utc_hours out of range: {h}"
                )


@dataclass(frozen=True)
class GAFeasibilityConfig:
    """GA selection 用 feasibility 制約 (T031 Phase 1: trade_count=0 淘汰のみ)."""

    entry_count_min: int = 1
    apply_from_generation: int = 0
    enable_fallback_when_all_infeasible: bool = True
    entry_count_min_hard_cap: int = 10000

    def __post_init__(self) -> None:
        if self.entry_count_min < 0:
            raise ValueError("ga.feasibility.entry_count_min must be >= 0")
        if self.entry_count_min > self.entry_count_min_hard_cap:
            raise ValueError(
                f"ga.feasibility.entry_count_min ({self.entry_count_min}) "
                f"exceeds hard cap ({self.entry_count_min_hard_cap})"
            )
        if self.apply_from_generation < 0:
            raise ValueError("ga.feasibility.apply_from_generation must be >= 0")


@dataclass(frozen=True)
class GAConfig:
    """GA hyper-parameters. Stage A の fitness_pen (sharpe - α·size_norm) を
    内部選択の基底指標とする (R2: fitness_metric != sharpe は warning 出して
    sharpe として処理)。"""

    population_size: int
    generations: int
    crossover_rate: float
    mutation_rate: float
    tournament_size: int
    elite_count: int
    max_depth: int
    max_clause: int = 1
    fitness_metric: Literal["total_pnl", "sharpe", "calmar"] = "sharpe"
    seed: int | None = None
    complexity_alpha: float = 0.03
    complexity_size_ref: float = 10.0
    n_edit_max: int = 3
    feasibility: GAFeasibilityConfig = field(default_factory=GAFeasibilityConfig)

    def __post_init__(self) -> None:
        if self.population_size < 1:
            raise ValueError("ga.population_size must be >= 1")
        if self.generations < 0:
            raise ValueError("ga.generations must be >= 0")
        if self.elite_count < 0:
            raise ValueError("ga.elite_count must be >= 0")
        if self.elite_count > self.population_size:
            raise ValueError("ga.elite_count must be <= population_size")
        if not 0.0 <= self.crossover_rate <= 1.0:
            raise ValueError("ga.crossover_rate must be in [0, 1]")
        if not 0.0 <= self.mutation_rate <= 1.0:
            raise ValueError("ga.mutation_rate must be in [0, 1]")
        if self.tournament_size < 1:
            raise ValueError("ga.tournament_size must be >= 1")
        if self.max_clause < 1:
            raise ValueError("ga.max_clause must be >= 1")
        if self.max_depth < 1:
            raise ValueError("ga.max_depth must be >= 1")
        if self.n_edit_max < 0:
            raise ValueError("ga.n_edit_max must be >= 0")
        if self.complexity_size_ref <= 0.0:
            raise ValueError("ga.complexity_size_ref must be > 0")
        if self.feasibility.apply_from_generation > self.generations:
            raise ValueError(
                f"ga.feasibility.apply_from_generation "
                f"({self.feasibility.apply_from_generation}) must be "
                f"<= ga.generations ({self.generations})"
            )


@dataclass(frozen=True)
class StageWindowsConfig:
    """Stage A/B/C bars の切り出しルール。

    - Stage B bars = ``[dataset.start, dataset.end)``
    - Stage A bars = Stage B 末尾 ``stage_a_window_days`` 営業日相当
    - Stage C holdout bars = ``[dataset.end, dataset.end + stage_c_holdout_days)``
      を DB から別途取得。取得できない場合、
      ``allow_stage_c_fallback_slice=True`` で Stage B 末尾 holdout_days 分の
      slice へフォールバック (**test fixture 専用**; production では常に False)。
    """

    stage_a_window_days: int = 60
    stage_c_holdout_days: int = 60
    allow_stage_c_fallback_slice: bool = False

    def __post_init__(self) -> None:
        if self.stage_a_window_days < 1:
            raise ValueError("stage_windows.stage_a_window_days must be >= 1")
        if self.stage_c_holdout_days < 1:
            raise ValueError("stage_windows.stage_c_holdout_days must be >= 1")


@dataclass(frozen=True)
class AlphaFactoryConfig:
    """Alpha Factory 全体 config。loader から返される SSOT 構造。

    ``live_criteria`` は ``stage_gate.live_criteria`` に一元化され、property
    として expose される (R1 #5 対応)。
    """

    dataset: DatasetConfig
    backtest: BacktestSectionConfig
    ga: GAConfig
    stage_gate: StageGateConfig
    cross_pair: CrossPairConfig
    stage_windows: StageWindowsConfig

    @property
    def live_criteria(self) -> Mapping[str, float | int]:
        """``stage_gate.live_criteria`` への alias (SSOT 参照)."""
        return self.stage_gate.live_criteria


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------


def _parse_dt(value: object) -> datetime:
    if not value:
        raise ValueError("datetime string must be non-empty")
    s = str(value)
    return to_utc(datetime.fromisoformat(s.replace("Z", "+00:00")))


def _deep_merge(
    base: Mapping[str, Any], overrides: Mapping[str, Any]
) -> dict[str, Any]:
    """dict を recursively merge する。override 側の ``None`` は skip。"""
    out: dict[str, Any] = dict(base)
    for k, v in overrides.items():
        if v is None:
            continue
        if isinstance(v, Mapping) and isinstance(out.get(k), Mapping):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def _build_dataset(raw: Mapping[str, Any]) -> DatasetConfig:
    return DatasetConfig(
        instrument=str(raw.get("instrument", "")),
        start=_parse_dt(raw.get("start")),
        end=_parse_dt(raw.get("end")),
    )


def _build_backtest(raw: Mapping[str, Any]) -> BacktestSectionConfig:
    max_spread_raw = raw.get("max_spread_bps")
    return BacktestSectionConfig(
        initial_cash=Decimal(str(raw.get("initial_cash", "1000000"))),
        leverage=int(raw.get("leverage", 25)),
        units=int(raw.get("units", 10000)),
        max_spread_bps=(
            Decimal(str(max_spread_raw)) if max_spread_raw is not None else None
        ),
        holding_cost_per_day_bps=Decimal(
            str(raw.get("holding_cost_per_day_bps", "0"))
        ),
        session_close_utc_hours=tuple(
            int(h) for h in raw.get("session_close_utc_hours", (23,))
        ),
    )


def _strict_bool(value: Any, default: bool) -> bool:
    """文字列 'false'/'no'/'0' を True 扱いする ``bool(...)`` の罠を回避."""
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        v = value.strip().lower()
        if v in ("true", "yes", "1", "on"):
            return True
        if v in ("false", "no", "0", "off"):
            return False
        raise ValueError(f"invalid bool string: {value!r}")
    if isinstance(value, (int, float)):
        return bool(value)
    raise ValueError(f"unsupported bool type: {type(value).__name__}")


def _build_feasibility(raw: Mapping[str, Any] | None) -> GAFeasibilityConfig:
    feas_raw: Mapping[str, Any] = raw or {}
    return GAFeasibilityConfig(
        entry_count_min=int(feas_raw.get("entry_count_min", 1)),
        apply_from_generation=int(feas_raw.get("apply_from_generation", 0)),
        enable_fallback_when_all_infeasible=_strict_bool(
            feas_raw.get("enable_fallback_when_all_infeasible"), default=True
        ),
    )


def _build_ga(raw: Mapping[str, Any]) -> GAConfig:
    return GAConfig(
        population_size=int(raw.get("population_size", 40)),
        generations=int(raw.get("generations", 15)),
        crossover_rate=float(raw.get("crossover_rate", 0.7)),
        mutation_rate=float(raw.get("mutation_rate", 0.3)),
        tournament_size=int(raw.get("tournament_size", 3)),
        elite_count=int(raw.get("elite_count", 2)),
        max_depth=int(raw.get("max_depth", 4)),
        max_clause=int(raw.get("max_clause", 1)),
        fitness_metric=raw.get("fitness_metric", "sharpe"),
        seed=raw.get("seed"),
        complexity_alpha=float(raw.get("complexity_alpha", 0.03)),
        complexity_size_ref=float(raw.get("complexity_size_ref", 10.0)),
        n_edit_max=int(raw.get("n_edit_max", 3)),
        feasibility=_build_feasibility(raw.get("feasibility")),
    )


def _build_stage_gate(
    stage_gate_raw: Mapping[str, Any],
    live_criteria_raw: Mapping[str, Any],
) -> StageGateConfig:
    a_raw = stage_gate_raw.get("stage_a") or {}
    b_raw = stage_gate_raw.get("stage_b") or {}
    c_raw = stage_gate_raw.get("stage_c") or {}
    kwargs: dict[str, Any] = {
        "stage_a_window_days": int(a_raw.get("window_days", 60)),
        "stage_a_alpha": float(a_raw.get("alpha", 0.03)),
        "stage_a_threshold": float(a_raw.get("threshold", 0.0)),
        "stage_b_window_months": int(b_raw.get("window_months", 18)),
        "wf_train_days": int(b_raw.get("wf_train_days", 120)),
        "wf_test_days": int(b_raw.get("wf_test_days", 20)),
        "wf_step_days": int(b_raw.get("wf_step_days", 20)),
        "wf_embargo_days": int(b_raw.get("wf_embargo_days", 1)),
        "stage_b_median_oos_sharpe_min": float(
            b_raw.get("median_oos_sharpe_min", 0.20)
        ),
        "stage_b_positive_fold_min": float(
            b_raw.get("positive_fold_min", 0.60)
        ),
        "stage_b_dsr_min": float(b_raw.get("dsr_min", 0.0)),
        "wf_min_folds_required": int(b_raw.get("wf_min_folds_required", 2)),
        "stage_c_holdout_days": int(c_raw.get("holdout_days", 60)),
        "spread_stress_multiplier": float(
            c_raw.get("spread_stress_multiplier", 1.5)
        ),
        "spread_stress_min_total_pnl": float(
            c_raw.get("spread_stress_min_total_pnl", 0.0)
        ),
        "spread_stress_min_sharpe": float(
            c_raw.get("spread_stress_min_sharpe", 0.0)
        ),
    }
    if live_criteria_raw:
        kwargs["live_criteria"] = dict(live_criteria_raw)
    return StageGateConfig(**kwargs)


def _build_cross_pair(raw: Mapping[str, Any]) -> CrossPairConfig:
    pass_raw = raw.get("pass_criteria") or {}
    return CrossPairConfig(
        sharpe_target_cross_ratio_min=float(
            pass_raw.get("sharpe_target_cross_ratio_min", 0.8)
        ),
        mean_sharpe_cross_min=float(
            pass_raw.get("mean_sharpe_cross_min", 0.15)
        ),
        min_sharpe_cross_min=float(
            pass_raw.get("min_sharpe_cross_min", -0.20)
        ),
        aggregator_lambda=float(raw.get("aggregator_lambda", 0.5)),
        mode=raw.get("mode", "shadow"),
    )


def _build_stage_windows(
    raw: Mapping[str, Any], stage_gate: StageGateConfig
) -> StageWindowsConfig:
    return StageWindowsConfig(
        stage_a_window_days=int(
            raw.get("stage_a_window_days", stage_gate.stage_a_window_days)
        ),
        stage_c_holdout_days=int(
            raw.get("stage_c_holdout_days", stage_gate.stage_c_holdout_days)
        ),
        allow_stage_c_fallback_slice=bool(
            raw.get("allow_stage_c_fallback_slice", False)
        ),
    )


def load_config(
    path: Path, overrides: Mapping[str, Any] | None = None
) -> AlphaFactoryConfig:
    """YAML + CLI overrides を merge して :class:`AlphaFactoryConfig` を返す。

    Args:
        path: YAML config path。
        overrides: CLI 由来の dict (nested)。``None`` value は skip される。

    Raises:
        FileNotFoundError: path が存在しない場合。
        ValueError: dataclass validation 失敗。
    """
    with path.open("r", encoding="utf-8") as f:
        raw: dict[str, Any] = yaml.safe_load(f) or {}
    if overrides:
        raw = _deep_merge(raw, overrides)

    stage_gate = _build_stage_gate(
        raw.get("stage_gate") or {}, raw.get("live_criteria") or {}
    )
    return AlphaFactoryConfig(
        dataset=_build_dataset(raw.get("dataset") or {}),
        backtest=_build_backtest(raw.get("backtest") or {}),
        ga=_build_ga(raw.get("ga") or {}),
        stage_gate=stage_gate,
        cross_pair=_build_cross_pair(raw.get("cross_pair") or {}),
        stage_windows=_build_stage_windows(
            raw.get("stage_windows") or {}, stage_gate
        ),
    )
