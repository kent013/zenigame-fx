"""T033: Per-individual diagnostics collector for sidecar emission.

Stage A/B/C 評価結果を generation 中に蓄積し、GA 完了時に sidecar Parquet として
flush する。production GA 経路から fail-open で利用される。

archive Parquet schema は touch しない。post-RUN で
``reports/run-reports/run-{N}/diagnostics/stage_a_provenance.parquet`` に出力する。

詳細: devnotes/20260425-0937-cost-pnl-ledger-eventsource/
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Final

from src.alpha_factory.pareto_features import ParetoFeaturesLite
from src.alpha_factory.stage_gate import StageResult

__all__ = [
    "VALID_METRIC_STAGES",
    "VALID_STAGE_C_GAP_CLASSES",
    "DiagnosticsCollector",
    "IndividualDiagnostics",
]

# metric_stage の解釈: 「到達した最高通過段」(pass-based)
# stage_a_only      = Stage A 不通過 (または Stage B/C 未評価)
# stage_a_evaluated = Stage A 通過 (Stage B 未評価 / 不通過)
# stage_b_evaluated = Stage B 通過 (Stage C 未評価 / 不通過)
# stage_c_evaluated = Stage C 通過
VALID_METRIC_STAGES: Final[frozenset[str]] = frozenset(
    {
        "stage_a_only",
        "stage_a_evaluated",
        "stage_b_evaluated",
        "stage_c_evaluated",
    }
)

# T109: Stage B→C gap diagnostic v1。Stage C 評価で base live_criteria 失敗の
# 組合せを固定コードで分類する enum (CI invariant 用)。観測専用、passed 判定や
# GA 探索には一切影響しない。
# - pass            : Stage C 通過
# - pnl_only        : base live_criteria で total_pnl のみ未達
# - count_only      : base live_criteria で trade_count のみ未達
# - both_pnl_count  : total_pnl ∧ trade_count 両方未達
# - sharpe_involved : sharpe を含む base live_criteria 未達 (上記以外)
# - mixed           : 上記以外の base live_criteria 未達組合せ
# - stress_or_other : base live_criteria 全通過だが stress/intraday 等で不通過
# - system_fail     : system_failure / worker_error (実行時障害)
# - unknown         : payload 不整合 (defensive)
VALID_STAGE_C_GAP_CLASSES: Final[frozenset[str]] = frozenset(
    {
        "pass",
        "pnl_only",
        "count_only",
        "both_pnl_count",
        "sharpe_involved",
        "mixed",
        "stress_or_other",
        "system_fail",
        "unknown",
    }
)


def _safe_float(value: Any) -> float | None:
    """None/NaN/Inf/型不正を None に潰す finite ガード。"""
    if value is None:
        return None
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def _safe_int(value: Any) -> int | None:
    """None/型不正/非有限を None に潰す int ガード。

    int(float("inf")) は OverflowError を送出するため捕捉する
    (Codex impl-review Round 1 [Suggestion]: 壊れた payload で診断全体が
    unknown に倒れるのを防ぐ)。
    """
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError, OverflowError):
        return None


def _derive_stage_c_gap(result: StageResult) -> dict[str, Any]:
    """Stage C StageResult から B→C gap 診断を抽出 (T109)。

    新規 backtest は行わず、evaluate_stage_c が既に計算済みの payload を
    defensive read するのみ。観測専用で、全例外を握り潰し fail-soft で
    安全な default を返す (診断欠損が GA 評価を絶対に止めない契約)。

    分類優先順位 (排他):
      1. system_fail        : reason に system_failure / worker_error
      2. pass               : result.passed
      3. base live_criteria 失敗組合せ (both_pnl_count / pnl_only /
                              count_only / sharpe_involved / mixed)
      4. stress_or_other    : base lc 全通過だが stress/intraday 等で fail
      5. unknown            : payload 不整合 (defensive)
    """
    out: dict[str, Any] = {
        "gap_class": "unknown",
        "base_total_pnl": None,
        "base_trade_count": None,
        "stress_pnl_degradation": None,
        "stress_trade_count": None,
    }
    try:
        # reason_codes を payload 型チェックより前に抽出。payload 自体が
        # 壊れた system_failure / worker_error も確実に system_fail へ寄せる
        # (Codex design-review Round 2 [Suggestion])。worker_error は並列
        # パスの代替 StageResult (swim_lane.py:864-879) で live_criteria_pass
        # を持たない実行時障害 (Round 1 [Critical])。
        reasons = tuple(getattr(result, "reason_codes", ()) or ())
        if ("system_failure" in reasons) or ("worker_error" in reasons):
            out["gap_class"] = "system_fail"
            return out
        payload_obj: Any = (
            result.metrics.get("payload", {})
            if hasattr(result, "metrics")
            else {}
        )
        if not isinstance(payload_obj, dict):
            return out
        payload = payload_obj
        # raw 値 (finite 化)
        out["base_total_pnl"] = _safe_float(payload.get("total_pnl"))
        out["base_trade_count"] = _safe_int(payload.get("trade_count"))
        stress = payload.get("stress")
        if isinstance(stress, dict) and not stress.get("skipped", False):
            out["stress_pnl_degradation"] = _safe_float(
                stress.get("pnl_degradation")
            )
            out["stress_trade_count"] = _safe_int(stress.get("trade_count"))
        if bool(result.passed):
            out["gap_class"] = "pass"
            return out
        lcp = payload.get("live_criteria_pass", {})
        if not isinstance(lcp, dict) or not lcp:
            # live_criteria_pass が欠落/空 → 基底 lc 失敗を判定できず unknown
            # (worker_error 等の payload は reason_codes で上流 system_fail 済)
            out["gap_class"] = "unknown"
            return out
        pnl_fail = lcp.get("total_pnl") is False
        count_fail = (lcp.get("trade_count_min") is False) or (
            lcp.get("trade_count_max") is False
        )
        sharpe_fail = lcp.get("sharpe") is False
        dd_fail = lcp.get("max_drawdown") is False
        if not (pnl_fail or count_fail or sharpe_fail or dd_fail):
            # base live_criteria は全通過 → stress / intraday 等で不通過
            out["gap_class"] = "stress_or_other"
            return out
        if pnl_fail and count_fail:
            out["gap_class"] = "both_pnl_count"
        elif pnl_fail and not (count_fail or sharpe_fail or dd_fail):
            out["gap_class"] = "pnl_only"
        elif count_fail and not (pnl_fail or sharpe_fail or dd_fail):
            out["gap_class"] = "count_only"
        elif sharpe_fail:
            out["gap_class"] = "sharpe_involved"
        else:
            out["gap_class"] = "mixed"
        return out
    except Exception:
        # fail-soft: 診断は観測専用、絶対に評価経路を壊さない
        return out


@dataclass
class IndividualDiagnostics:
    """Per-individual diagnostics record (mutable during a generation)."""

    lane_id: str
    generation: int
    individual_name: str
    trade_count: int = 0
    total_pnl_stage_a: float = 0.0
    sharpe_stage_a: float | None = None
    stage_a_pass: bool = False
    stage_b_pass: bool | None = None  # None = not evaluated
    stage_c_pass: bool | None = None  # None = not evaluated
    # T109: Stage B→C gap diagnostic v1 (Stage C 評価個体のみ非 None)
    stage_c_gap_class: str | None = None
    stage_c_base_total_pnl: float | None = None
    stage_c_base_trade_count: int | None = None
    stage_c_stress_pnl_degradation: float | None = None
    stage_c_stress_trade_count: int | None = None
    # T111: ParetoFeaturesLite (NSGA-II selection 用 Stage B 完結軸、観測専用)。
    # Stage B 評価個体のみ非 None。pareto_axis_usable=True ⇒ source_stage=="B"。
    pareto_net_pnl_after_cost: float | None = None
    pareto_pooled_dd_per_fold_max: float | None = None
    pareto_mission_inf_gap: float | None = None
    pareto_is_feasible_invariant: bool | None = None
    pareto_axis_usable: bool | None = None
    pareto_source_stage: str | None = None


class DiagnosticsCollector:
    """In-memory collector for per-individual stage diagnostics.

    Lifecycle:
    - Created in run_ga.py with run-level scope
    - Updated by stage_gate / swim_lane after each StageResult is produced
    - Flushed to Parquet sidecar at GA completion (writer は別モジュール)

    主キー: ``(lane_id, generation, individual_name)`` の複合キー
    (既存 archive と整合)。同一キーの再記録は last-write-wins。
    """

    def __init__(self) -> None:
        self._records: dict[tuple[str, int, str], IndividualDiagnostics] = {}

    def _key(
        self, lane_id: str, generation: int, individual_name: str
    ) -> tuple[str, int, str]:
        return (lane_id, generation, individual_name)

    def record_stage_a(
        self,
        lane_id: str,
        generation: int,
        individual_name: str,
        result: StageResult,
    ) -> None:
        """Stage A 結果を記録。同一キー再記録は last-write-wins (idempotent)."""
        payload_obj: Any = (
            result.metrics.get("payload", {})
            if hasattr(result, "metrics")
            else {}
        )
        if not isinstance(payload_obj, dict):
            payload: dict[str, Any] = {}
        else:
            payload = payload_obj
        # Defensive read: payload may lack new fields if older code path
        trade_count = int(payload.get("trade_count", 0) or 0)
        total_pnl_raw = payload.get("total_pnl", 0.0)
        try:
            total_pnl = float(total_pnl_raw) if total_pnl_raw is not None else 0.0
        except (TypeError, ValueError):
            total_pnl = 0.0
        if not math.isfinite(total_pnl):
            total_pnl = 0.0
        sharpe_raw = payload.get("trade_sharpe_raw")
        sharpe_stage_a: float | None = None
        if sharpe_raw is not None:
            try:
                v = float(sharpe_raw)
                if math.isfinite(v):
                    sharpe_stage_a = v
            except (TypeError, ValueError):
                sharpe_stage_a = None
        self._records[self._key(lane_id, generation, individual_name)] = (
            IndividualDiagnostics(
                lane_id=lane_id,
                generation=generation,
                individual_name=individual_name,
                trade_count=trade_count,
                total_pnl_stage_a=total_pnl,
                sharpe_stage_a=sharpe_stage_a,
                stage_a_pass=bool(result.passed),
            )
        )

    def record_stage_b(
        self,
        lane_id: str,
        generation: int,
        individual_name: str,
        passed: bool,
        pareto_lite: ParetoFeaturesLite | None = None,
    ) -> None:
        """Stage B pass/fail + ParetoFeaturesLite を記録。Stage A 未記録なら no-op.

        T111: ``pareto_lite`` は NSGA-II selection 用 Stage B 完結軸 (観測専用)。
        省略時 (後方互換) は Pareto 列を据え置く。
        """
        rec = self._records.get(
            self._key(lane_id, generation, individual_name)
        )
        if rec is None:
            return
        rec.stage_b_pass = bool(passed)
        if pareto_lite is not None:
            rec.pareto_net_pnl_after_cost = pareto_lite.net_pnl_after_cost
            rec.pareto_pooled_dd_per_fold_max = (
                pareto_lite.pooled_dd_per_fold_max
            )
            rec.pareto_mission_inf_gap = pareto_lite.mission_inf_gap
            rec.pareto_is_feasible_invariant = (
                pareto_lite.is_feasible_invariant
            )
            rec.pareto_axis_usable = pareto_lite.pareto_axis_usable
            rec.pareto_source_stage = pareto_lite.source_stage

    def record_stage_c(
        self,
        lane_id: str,
        generation: int,
        individual_name: str,
        result: StageResult,
    ) -> None:
        """Stage C 結果を記録。Stage A 未記録なら no-op (defensive).

        T109: B→C gap diagnostic v1。base live_criteria 失敗の組合せを固定
        コードで分類し、stress PnL 劣化量と base/stress trade_count を記録する
        (観測のみ、passed 判定や GA 探索には一切影響しない)。
        """
        rec = self._records.get(
            self._key(lane_id, generation, individual_name)
        )
        if rec is None:
            return
        rec.stage_c_pass = bool(result.passed)
        diag = _derive_stage_c_gap(result)
        rec.stage_c_gap_class = diag["gap_class"]
        rec.stage_c_base_total_pnl = diag["base_total_pnl"]
        rec.stage_c_base_trade_count = diag["base_trade_count"]
        rec.stage_c_stress_pnl_degradation = diag["stress_pnl_degradation"]
        rec.stage_c_stress_trade_count = diag["stress_trade_count"]

    def derive_metric_stage(self, rec: IndividualDiagnostics) -> str:
        """post-hoc metric_stage 確定 (collector 側で flush 時に決定)."""
        if rec.stage_c_pass is True:
            return "stage_c_evaluated"
        if rec.stage_b_pass is True:
            return "stage_b_evaluated"
        if rec.stage_a_pass:
            return "stage_a_evaluated"
        return "stage_a_only"

    def to_rows(self) -> list[dict[str, Any]]:
        """Materialize records as plain dicts for Parquet writing.

        sidecar 出力の SSOT。CI invariant I2 を assert で保護
        (metric_stage が enum 内であること)。
        """
        rows: list[dict[str, Any]] = []
        for rec in self._records.values():
            metric_stage = self.derive_metric_stage(rec)
            assert metric_stage in VALID_METRIC_STAGES, (
                f"metric_stage out of enum: {metric_stage!r} "
                f"(rec={rec})"
            )
            # T109: gap_class CI invariant (None または enum 内)
            assert (
                rec.stage_c_gap_class is None
                or rec.stage_c_gap_class in VALID_STAGE_C_GAP_CLASSES
            ), (
                f"stage_c_gap_class out of enum: {rec.stage_c_gap_class!r} "
                f"(rec={rec})"
            )
            # T111: ParetoFeaturesLite CI invariant
            # (pareto_axis_usable=True ⇒ source_stage=="B" かつ 3 scalar finite)。
            if rec.pareto_axis_usable is True:
                assert rec.pareto_source_stage == "B", (
                    f"pareto_axis_usable=True but source_stage="
                    f"{rec.pareto_source_stage!r} (rec={rec})"
                )
                _pareto_scalars = (
                    rec.pareto_net_pnl_after_cost,
                    rec.pareto_pooled_dd_per_fold_max,
                    rec.pareto_mission_inf_gap,
                )
                assert all(
                    v is not None and math.isfinite(v) for v in _pareto_scalars
                ), (
                    f"pareto_axis_usable=True but scalar is None/non-finite "
                    f"(rec={rec})"
                )
            rows.append(
                {
                    "lane_id": rec.lane_id,
                    "generation": rec.generation,
                    "individual_name": rec.individual_name,
                    "metric_stage": metric_stage,
                    "trade_count": rec.trade_count,
                    "total_pnl_stage_a": rec.total_pnl_stage_a,
                    "sharpe_stage_a": rec.sharpe_stage_a,
                    "stage_a_pass": rec.stage_a_pass,
                    "stage_b_pass": rec.stage_b_pass,
                    "stage_c_pass": rec.stage_c_pass,
                    # T109: Stage B→C gap diagnostic v1
                    "stage_c_gap_class": rec.stage_c_gap_class,
                    "stage_c_base_total_pnl": rec.stage_c_base_total_pnl,
                    "stage_c_base_trade_count": rec.stage_c_base_trade_count,
                    "stage_c_stress_pnl_degradation": (
                        rec.stage_c_stress_pnl_degradation
                    ),
                    "stage_c_stress_trade_count": rec.stage_c_stress_trade_count,
                    # T111: ParetoFeaturesLite (NSGA-II selection 用 Stage B 完結軸)
                    "pareto_net_pnl_after_cost": rec.pareto_net_pnl_after_cost,
                    "pareto_pooled_dd_per_fold_max": (
                        rec.pareto_pooled_dd_per_fold_max
                    ),
                    "pareto_mission_inf_gap": rec.pareto_mission_inf_gap,
                    "pareto_is_feasible_invariant": (
                        rec.pareto_is_feasible_invariant
                    ),
                    "pareto_axis_usable": rec.pareto_axis_usable,
                    "pareto_source_stage": rec.pareto_source_stage,
                }
            )
        return rows

    def __len__(self) -> int:
        return len(self._records)
