"""Calibrate-gate (T027) — Stage A threshold deterministic 動的調整。

GA Run 終了後に archive Parquet から Stage A の実通過率を集計し、
``stage_gate.stage_a.threshold`` を quantile-snap + hysteresis + delta clamp で
更新する pure logic 群。CLI 配線は ``scripts/alpha_factory/calibrate_gate.py``。

設計:
    - devnotes/20260424-1759-port-calibrate-gate/conceptual-design.md
    - devnotes/20260424-1759-port-calibrate-gate/detailed-design.md

主な公開 API:
    - :class:`CalibrateConfig`
    - :class:`AggregatedSample`
    - :class:`MonitoringMetrics`
    - :class:`Decision`
    - :func:`aggregate_sample`
    - :func:`compute_monitoring`
    - :func:`decide`
    - :class:`SchemaMismatchError`
    - :class:`ConfigError`
    - :func:`load_calibrate_config`
    - :func:`validate_schema`
"""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any, Final, Literal

import numpy as np
import pyarrow as pa
import structlog

from src.alpha_factory.stage_gate import STAGE_A_FITNESS_SENTINELS

__all__ = [
    "AGGREGATION_MODES",
    "REQUIRED_COLS",
    "REQUIRED_NON_NULL_COLS",
    "AggregatedSample",
    "CalibrateConfig",
    "ConfigError",
    "Decision",
    "MonitoringMetrics",
    "SchemaMismatchError",
    "aggregate_sample",
    "compute_monitoring",
    "decide",
    "load_calibrate_config",
    "validate_schema",
]

logger = structlog.get_logger(__name__)


AggregationMode = Literal[
    "last_k_generations", "all_generations", "generation_weighted_mean"
]

AGGREGATION_MODES: Final[tuple[str, ...]] = (
    "last_k_generations",
    "all_generations",
    "generation_weighted_mean",
)

DecisionLabel = Literal[
    "in_band",
    "tighten",
    "loosen",
    "skip_disabled",
    "skip_no_archive",
    "skip_sample_size",
    "skip_zero_variance",
    "skip_schema_mismatch",
]


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class SchemaMismatchError(Exception):
    """Parquet schema が想定外（必須列欠落 / 不正な null / NaN）。"""


class ConfigError(Exception):
    """yaml の calibrate セクション欠落 / 値域違反。"""


# ---------------------------------------------------------------------------
# Schema validation
# ---------------------------------------------------------------------------


REQUIRED_NON_NULL_COLS: Final[tuple[str, ...]] = (
    "generation",
    "stage_a_pass",
    "fitness_pen",
    "stage_b_pass",
    "stage_c_pass",
    # Codex impl-review #1 対応: monitoring 計算で float/int() を直接呼ぶ
    # これらの列も non-null を強制し、null 混入時は TypeError 経由で
    # exit 5/異常終了に逸脱せず exit 8 (schema_mismatch) に正規化する。
    "total_pnl",
    "max_drawdown_pct",
    "trade_count",
)

REQUIRED_COLS: Final[tuple[str, ...]] = (
    *REQUIRED_NON_NULL_COLS,
    "sharpe",  # nullable 許容 (monitoring 内で除外)
)

# 数値カラム全体で NaN/Inf 検査対象 (int 列も含めて防御的に検査する。
# 通常 pa.int32() は NaN を保持しないが、上流が float 経由で構築するケースや
# zero-copy 不可な dict input 経路では NaN/Inf が混入し得るため明示的に弾く。
# Codex impl-review round 2 #1 対応)
_NAN_CHECK_NUMERIC_COLS: Final[tuple[str, ...]] = (
    "fitness_pen",
    "total_pnl",
    "max_drawdown_pct",
    "trade_count",
)


def validate_schema(table: pa.Table) -> None:
    """archive Parquet の schema 検証。

    Raises:
        SchemaMismatchError: 必須カラム欠落 / 不正 null / NaN / Inf を検知した場合。
    """
    schema_names = set(table.schema.names)
    missing = [c for c in REQUIRED_COLS if c not in schema_names]
    if missing:
        raise SchemaMismatchError(f"missing columns: {missing}")
    for col in REQUIRED_NON_NULL_COLS:
        n_null = table[col].null_count
        if n_null > 0:
            raise SchemaMismatchError(f"unexpected nulls in {col}: {n_null}")
    for col in _NAN_CHECK_NUMERIC_COLS:
        arr = np.asarray(
            table[col].to_numpy(zero_copy_only=False), dtype=np.float64
        )
        if not np.isfinite(arr).all():
            raise SchemaMismatchError(f"NaN or Inf found in {col}")


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CalibrateConfig:
    """calibrate-gate の動作設定（yaml SSOT を materialize したもの）。"""

    enabled: bool
    aggregation_mode: AggregationMode
    aggregation_window: int
    pass_rate_tolerance_abs: float
    threshold_delta_abs_max: float
    threshold_floor: float
    threshold_ceiling: float
    min_sample_size: int
    eps_var: float
    target_pass_rate: float
    prev_threshold: float

    def __post_init__(self) -> None:
        if self.aggregation_mode not in AGGREGATION_MODES:
            raise ConfigError(
                f"aggregation_mode must be one of {AGGREGATION_MODES}, "
                f"got {self.aggregation_mode!r}"
            )
        if self.aggregation_window < 1:
            raise ConfigError(
                f"aggregation_window must be >= 1, got {self.aggregation_window}"
            )
        if not (0.0 <= self.target_pass_rate <= 1.0):
            raise ConfigError(
                f"target_pass_rate must be in [0, 1], got {self.target_pass_rate}"
            )
        if not (0.0 <= self.pass_rate_tolerance_abs <= 0.5):
            raise ConfigError(
                f"pass_rate_tolerance_abs must be in [0, 0.5], "
                f"got {self.pass_rate_tolerance_abs}"
            )
        if self.threshold_delta_abs_max <= 0:
            raise ConfigError(
                f"threshold_delta_abs_max must be > 0, "
                f"got {self.threshold_delta_abs_max}"
            )
        if self.threshold_floor > self.threshold_ceiling:
            raise ConfigError(
                f"threshold_floor ({self.threshold_floor}) must be "
                f"<= threshold_ceiling ({self.threshold_ceiling})"
            )
        if self.min_sample_size < 1:
            raise ConfigError(
                f"min_sample_size must be >= 1, got {self.min_sample_size}"
            )
        if self.eps_var <= 0:
            raise ConfigError(f"eps_var must be > 0, got {self.eps_var}")


_REQUIRED_CALIBRATE_KEYS: Final[frozenset[str]] = frozenset(
    {
        "enabled",
        "aggregation_mode",
        "aggregation_window",
        "pass_rate_tolerance_abs",
        "threshold_delta_abs_max",
        "threshold_floor",
        "threshold_ceiling",
        "min_sample_size",
        "eps_var",
    }
)


def load_calibrate_config(yaml_data: Mapping[str, Any]) -> CalibrateConfig:
    """yaml dict (ruamel parsed) から CalibrateConfig を構築する。

    Raises:
        ConfigError: 必須キー欠落 / 値域違反。
    """
    try:
        stage_a = yaml_data["stage_gate"]["stage_a"]
    except KeyError as e:
        raise ConfigError(f"missing key path: stage_gate.stage_a ({e})") from e
    section = stage_a.get("calibrate")
    if section is None:
        raise ConfigError("missing key path: stage_gate.stage_a.calibrate")

    missing = _REQUIRED_CALIBRATE_KEYS - set(section.keys())
    if missing:
        raise ConfigError(f"missing calibrate keys: {sorted(missing)}")
    extra = set(section.keys()) - _REQUIRED_CALIBRATE_KEYS
    if extra:
        # WARN のみ。前方互換のため raise しない（typo 検出ヒント）
        logger.warning("calibrate.unknown_keys", keys=sorted(extra))

    enabled_raw = section["enabled"]
    if not isinstance(enabled_raw, bool):
        raise ConfigError(
            f"calibrate.enabled must be bool, got {type(enabled_raw).__name__}: "
            f"{enabled_raw!r}"
        )
    return CalibrateConfig(
        enabled=enabled_raw,
        aggregation_mode=str(section["aggregation_mode"]),  # type: ignore[arg-type]
        aggregation_window=int(section["aggregation_window"]),
        pass_rate_tolerance_abs=float(section["pass_rate_tolerance_abs"]),
        threshold_delta_abs_max=float(section["threshold_delta_abs_max"]),
        threshold_floor=float(section["threshold_floor"]),
        threshold_ceiling=float(section["threshold_ceiling"]),
        min_sample_size=int(section["min_sample_size"]),
        eps_var=float(section["eps_var"]),
        target_pass_rate=float(stage_a["target_pass_rate"]),
        prev_threshold=float(stage_a["threshold"]),
    )


# ---------------------------------------------------------------------------
# AggregatedSample
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AggregatedSample:
    """archive 集計結果 (decide の入力)。"""

    n_rows_total: int
    n_rows_used: int
    pass_count_used: int
    actual_pass_rate: float
    fitness_pen_pool: tuple[float, ...]
    mode: AggregationMode
    window: int


def _pool_excluding_sentinels(rows: Iterable[Mapping[str, Any]]) -> tuple[float, ...]:
    """T034: fitness_pen pool から Stage A failure sentinel 値を除外する。

    sentinel (SYSTEM_FAILURE / NO_EXPOSURE / METRIC_UNAVAILABLE) を quantile 計算
    に混ぜると threshold が不当に低く出る (探索圧崩壊) ため、値一致 (set
    membership) で明示除外する。閾値分離 (例: < -100) は fitness_pen 通常実値域
    と被る可能性があり安全でない (sharpe 下限 clamp が無いため)。
    """
    return tuple(
        float(r["fitness_pen"])
        for r in rows
        if float(r["fitness_pen"]) not in STAGE_A_FITNESS_SENTINELS
    )


def aggregate_sample(
    rows: Iterable[Mapping[str, Any]],
    *,
    mode: AggregationMode,
    window: int,
) -> AggregatedSample:
    """archive 行群を mode に従って集計する。

    Args:
        rows: archive 行 (dict) の iterable。各行に少なくとも
            ``generation`` / ``stage_a_pass`` / ``fitness_pen`` を含むこと。
        mode: 集計方式。
        window: ``last_k_generations`` の K。他 mode では未使用。

    Returns:
        :class:`AggregatedSample`。
    """
    if mode not in AGGREGATION_MODES:
        raise ValueError(f"unknown mode: {mode!r}")

    rows_list = [dict(r) for r in rows]
    n_rows_total = len(rows_list)

    if n_rows_total == 0:
        return AggregatedSample(
            n_rows_total=0,
            n_rows_used=0,
            pass_count_used=0,
            actual_pass_rate=0.0,
            fitness_pen_pool=(),
            mode=mode,
            window=window,
        )

    if mode == "last_k_generations":
        gens = sorted({int(r["generation"]) for r in rows_list})
        g_max = gens[-1]
        threshold_g = g_max - window + 1
        used = [r for r in rows_list if int(r["generation"]) >= threshold_g]
        n_used = len(used)
        pass_count = sum(1 for r in used if bool(r["stage_a_pass"]))
        actual = (pass_count / n_used) if n_used > 0 else 0.0
        pool = _pool_excluding_sentinels(used)

    elif mode == "all_generations":
        used = rows_list
        n_used = len(used)
        pass_count = sum(1 for r in used if bool(r["stage_a_pass"]))
        actual = (pass_count / n_used) if n_used > 0 else 0.0
        pool = _pool_excluding_sentinels(used)

    else:  # generation_weighted_mean
        gen_to_rows: dict[int, list[Mapping[str, Any]]] = defaultdict(list)
        for r in rows_list:
            gen_to_rows[int(r["generation"])].append(r)
        gens = sorted(gen_to_rows.keys())
        g_min = gens[0]
        weights = {g: float(g - g_min + 1) for g in gens}
        total_w = sum(weights.values())
        weighted_sum = 0.0
        for g in gens:
            gen_rows = gen_to_rows[g]
            gen_pass_rate = sum(1 for r in gen_rows if bool(r["stage_a_pass"])) / max(
                len(gen_rows), 1
            )
            weighted_sum += weights[g] * gen_pass_rate
        actual = (weighted_sum / total_w) if total_w > 0 else 0.0
        # 全世代統一: pool は全行 (sentinel 除外)
        pool = _pool_excluding_sentinels(rows_list)
        n_used = len(rows_list)
        pass_count = round(actual * n_used)

    return AggregatedSample(
        n_rows_total=n_rows_total,
        n_rows_used=n_used,
        pass_count_used=pass_count,
        actual_pass_rate=actual,
        fitness_pen_pool=pool,
        mode=mode,
        window=window,
    )


# ---------------------------------------------------------------------------
# MonitoringMetrics
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MonitoringMetrics:
    """変更には使わないが、ログ・後段判断に残す従属監視指標。

    符号規約: live_criteria_gap は **未達量を非負で表現**。
    0 = 達成、正 = 未達。

    因果解釈禁止: stage_b_pass_count / stage_c_pass_count / live_criteria_gap は
    threshold 変更の決定には使わない。観察記録のみ（C3 collider bias 注意）。
    """

    stage_b_pass_count: int
    stage_c_pass_count: int
    best_sharpe: float | None
    best_total_pnl: float | None
    best_max_drawdown_pct: float | None
    best_trade_count: int | None
    live_criteria_gap: dict[str, float]


def compute_monitoring(
    rows: Iterable[Mapping[str, Any]],
    *,
    live_criteria: Mapping[str, float],
) -> MonitoringMetrics:
    """archive 全行から監視指標を計算する（threshold 決定に使わない情報指標）。

    Args:
        rows: archive 行 (dict) の iterable。
        live_criteria: ``sharpe_min`` / ``total_pnl_min`` / ``max_drawdown_max`` /
            ``trade_count_min`` / ``trade_count_max`` を含む dict。

    Returns:
        :class:`MonitoringMetrics`。
    """
    rows_list = list(rows)
    stage_b_pass = sum(1 for r in rows_list if bool(r.get("stage_b_pass", False)))
    stage_c_pass = sum(1 for r in rows_list if bool(r.get("stage_c_pass", False)))

    # T-sharpe Phase 1A: trade_sharpe_raw (v2) を使用。v2 行のみを集計し、
    # v1/未知バージョン行は除外する。None は v1 として扱う（後方互換）
    unknown_versions: set[str] = set()
    valid_sharpes: list[float] = []
    for r in rows_list:
        raw_version = r.get("sharpe_calc_version")
        version = "v1_bar_annualized" if raw_version is None else raw_version
        if version == "v2_trade_level":
            v = r.get("trade_sharpe_raw")
            if v is not None:
                fv = float(v)
                if math.isfinite(fv):  # NaN/Inf ガード
                    valid_sharpes.append(fv)
        elif version != "v1_bar_annualized":
            unknown_versions.add(version)
    if unknown_versions:
        logger.warning(
            "calibrate_gate.unknown_sharpe_calc_version",
            unknown_versions=sorted(unknown_versions),
            total_rows=len(rows_list),
        )
    best_sharpe = max(valid_sharpes) if valid_sharpes else None

    pnl_vals = [
        float(r["total_pnl"])
        for r in rows_list
        if r.get("total_pnl") is not None
    ]
    best_total_pnl = max(pnl_vals) if pnl_vals else None

    dd_vals = [
        float(r["max_drawdown_pct"])
        for r in rows_list
        if r.get("max_drawdown_pct") is not None
    ]
    # 最良 = 最小 drawdown
    best_max_dd = min(dd_vals) if dd_vals else None

    tc_vals = [
        int(r["trade_count"])
        for r in rows_list
        if r.get("trade_count") is not None
    ]
    best_tc = max(tc_vals) if tc_vals else None

    sharpe_min = float(live_criteria.get("sharpe_min", 0.0))
    pnl_min = float(live_criteria.get("total_pnl_min", 0.0))
    dd_max = float(live_criteria.get("max_drawdown_max", 1.0))
    tc_min = float(live_criteria.get("trade_count_min", 0))
    tc_max = float(live_criteria.get("trade_count_max", float("inf")))

    gap = {
        "sharpe": max(0.0, sharpe_min - (best_sharpe if best_sharpe is not None else 0.0)),
        "total_pnl": max(
            0.0, pnl_min - (best_total_pnl if best_total_pnl is not None else 0.0)
        ),
        "max_dd": max(
            0.0, ((best_max_dd if best_max_dd is not None else 0.0) / 100.0) - dd_max
        ),
        "trade_count_min": max(
            0.0, tc_min - (float(best_tc) if best_tc is not None else 0.0)
        ),
        "trade_count_max": max(
            0.0, (float(best_tc) if best_tc is not None else 0.0) - tc_max
        ),
    }

    return MonitoringMetrics(
        stage_b_pass_count=stage_b_pass,
        stage_c_pass_count=stage_c_pass,
        best_sharpe=best_sharpe,
        best_total_pnl=best_total_pnl,
        best_max_drawdown_pct=best_max_dd,
        best_trade_count=best_tc,
        live_criteria_gap=gap,
    )


# ---------------------------------------------------------------------------
# Decision
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Decision:
    """controller 出力。"""

    decision: DecisionLabel
    new_threshold: float
    delta: float
    q_target: float | None
    var_fitness_pen: float | None
    raw_target_threshold: float | None
    clamped_by_delta: bool
    clamped_by_floor_or_ceiling: bool
    effective_sample_size: int


def decide(sample: AggregatedSample, config: CalibrateConfig) -> Decision:
    """quantile-snap + hysteresis (dead-band) + delta clamp。

    Args:
        sample: 集計結果。
        config: calibrate 設定 + target / prev_threshold。

    Returns:
        :class:`Decision`。``decision == "in_band" / skip_*`` の場合は
        ``new_threshold == prev_threshold`` で返す。
    """
    prev = config.prev_threshold
    n_used = sample.n_rows_used

    if not config.enabled:
        return Decision(
            decision="skip_disabled",
            new_threshold=prev,
            delta=0.0,
            q_target=None,
            var_fitness_pen=None,
            raw_target_threshold=None,
            clamped_by_delta=False,
            clamped_by_floor_or_ceiling=False,
            effective_sample_size=n_used,
        )

    if n_used < config.min_sample_size:
        return Decision(
            decision="skip_sample_size",
            new_threshold=prev,
            delta=0.0,
            q_target=None,
            var_fitness_pen=None,
            raw_target_threshold=None,
            clamped_by_delta=False,
            clamped_by_floor_or_ceiling=False,
            effective_sample_size=n_used,
        )

    target = config.target_pass_rate
    tol = config.pass_rate_tolerance_abs
    actual = sample.actual_pass_rate

    if abs(actual - target) <= tol:
        return Decision(
            decision="in_band",
            new_threshold=prev,
            delta=0.0,
            q_target=None,
            var_fitness_pen=None,
            raw_target_threshold=None,
            clamped_by_delta=False,
            clamped_by_floor_or_ceiling=False,
            effective_sample_size=n_used,
        )

    pool = sample.fitness_pen_pool
    if not pool:
        # n_used >= min_sample_size を満たしていれば pool も埋まっているはずだが
        # 念のため defense
        return Decision(
            decision="skip_zero_variance",
            new_threshold=prev,
            delta=0.0,
            q_target=None,
            var_fitness_pen=0.0,
            raw_target_threshold=None,
            clamped_by_delta=False,
            clamped_by_floor_or_ceiling=False,
            effective_sample_size=n_used,
        )
    arr = np.array(pool, dtype=np.float64)
    var_fp = float(np.var(arr))
    if var_fp <= config.eps_var:
        return Decision(
            decision="skip_zero_variance",
            new_threshold=prev,
            delta=0.0,
            q_target=None,
            var_fitness_pen=var_fp,
            raw_target_threshold=None,
            clamped_by_delta=False,
            clamped_by_floor_or_ceiling=False,
            effective_sample_size=n_used,
        )

    q_target = float(np.quantile(arr, 1.0 - target, method="linear"))
    delta_raw = q_target - prev
    delta = max(-config.threshold_delta_abs_max, min(config.threshold_delta_abs_max, delta_raw))
    clamped_by_delta = delta != delta_raw
    new_after_delta = prev + delta
    new_clamped = max(
        config.threshold_floor, min(config.threshold_ceiling, new_after_delta)
    )
    clamped_by_floor_or_ceiling = new_clamped != new_after_delta
    new_threshold = round(new_clamped, 4)

    decision_label: DecisionLabel = "tighten" if actual > target + tol else "loosen"

    return Decision(
        decision=decision_label,
        new_threshold=new_threshold,
        delta=new_threshold - prev,
        q_target=q_target,
        var_fitness_pen=var_fp,
        raw_target_threshold=q_target,
        clamped_by_delta=clamped_by_delta,
        clamped_by_floor_or_ceiling=clamped_by_floor_or_ceiling,
        effective_sample_size=n_used,
    )
