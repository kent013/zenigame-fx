"""T065: NSGA-II core + 主選抜 (B-pooled) — synthesis § 7.1 / § 6.5 確定式の単一実装.

詳細:

- 概念設計: ``devnotes/20260430-1100-todo-T065-nsga2-core-and-main-selection/conceptual-design.md``
- 詳細設計: ``devnotes/20260430-1100-todo-T065-nsga2-core-and-main-selection/detailed-design.md``
- synthesis § 7.1 (NSGA-II + 純 CPPS)、 § 6.5 (Pareto 3 軸)、 § 7.5 (operators)、
  § 7.7 (failure handling)
- T063 依存: ``stage_a_pass`` (a_pass_indices)、 default-deny 契約
- T064 依存: :class:`~src.alpha_factory.stage_bc_evaluator.BCEvaluationResult`
  (``b_pooled_cf``, ``pareto_axis_usable``, ``b_result.pooled_dd_per_fold_max``)
- T062 依存: :class:`~src.alpha_factory.mission_inf_gap.MissionGapResult`
  (``mission_inf_gap``, ``constraint_violation``, ``is_feasible``)
- T061 依存: :class:`~src.alpha_factory.canonical_metrics.InvariantFlags`
  (``session_close_drop_count``, ``negative_equity_drop_open_count``, ``is_feasible``)

Phase 1 (本 TODO = T065 PR 1): 単体実装 + テストのみ、 GA loop / archive / cross_pair /
swim_lane / run_ga.py 未配線. T065 PR 1 単独 merge で runtime に影響なし (既存 GA loop は
新規 module を import しないため).

Phase 2 (T066 / T067 / T070 / T071 と同時、 別 PR): 詳細設計 § Phase 2 申し送り 9 箇所参照.

References:

- Deb, K. (2000). An efficient constraint handling method for genetic algorithms.
  Computer Methods in Applied Mechanics and Engineering, 186(2-4), 311-338.
  https://doi.org/10.1016/S0045-7825(99)00389-8
- Deb, K., Pratap, A., Agarwal, S., & Meyarivan, T. (2002). A fast and elitist
  multiobjective genetic algorithm: NSGA-II. IEEE Transactions on Evolutionary
  Computation, 6(2), 182-197. https://doi.org/10.1109/4235.996017
"""

from __future__ import annotations

import hashlib
import json
import math
import random
import types
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

from src.alpha_factory.canonical_metrics import InvariantFlags
from src.alpha_factory.mission_inf_gap import MissionGapResult
from src.alpha_factory.stage_bc_evaluator import BCEvaluationResult

__all__ = [
    "INVARIANT_VIOLATION_PENALTY",
    "GenerationSelectionResult",
    "IndividualEvaluation",
    "ParetoAxis",
    "binary_tournament",
    "compute_effective_constraint_violation",
    "constrained_dominates",
    "crowding_distance",
    "extract_pareto_axis",
    "make_selection_seed",
    "non_dominated_sort",
    "run_generation_selection",
    "select_parent_pair",
    "select_survivors",
]


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


INVARIANT_VIOLATION_PENALTY: float = 1.0e6
"""invariant 1 件で slack 由来 violation を支配する大値 (synthesis § 6.6 / 概念設計 § 5.2).

事前上界根拠 (詳細設計 Round 1 [S1] 反映):

- T062 ``constraint_violation`` 実データ上界 = 4 slack 由来 ``max(0, -slack_*)`` の sum、
  typical 値域 [0, 数十]、 上界目安 1.0e2.
- 1.0e6 ≫ 1.0e2 のため invariant 1 件が slack 由来 violation の任意組合せを支配.
- invariant 件数が万単位になることは intraday FX で実用上想定外 (1 個体 backtest で
  session_close_drop が万件発生 = データ pipeline 異常 → upstream fail-fast).

INCONCLUSIVE (smoke 後再校正候補、 詳細設計 § 残論点 R1):

- invariant violation 個体が rank 末尾に確実に行く (mass 配分検証).
- all-infeasible front でも数値安定 (oscillation / overflow なし).
- finite violation 域で penalty による monotone ordering が崩れない (slack 1 / invariant 1 比較等).
"""


# ---------------------------------------------------------------------------
# DataClasses (frozen で immutable)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ParetoAxis:
    """Pareto 3 軸 (synthesis § 6.5)、 finite domain 必須.

    Field 規約:

    - ``net_pnl``: f1 (max)、 ``BCEvaluationResult.b_pooled_cf.net_pnl_after_cost`` 由来.
    - ``max_dd``: f2 (min)、 ``BCEvaluationResult.b_result.pooled_dd_per_fold_max`` 由来
      (synthesis § 5.2 準拠、 concat DD でない).
    - ``mission_inf_gap``: f3 (min)、 ``MissionGapResult.mission_inf_gap`` 由来 (T062 確定式).

    全 field finite (math.isfinite=True) を契約 (Round 1 [C3] 反映、
    :func:`extract_pareto_axis` 入口で検証).
    """

    net_pnl: float
    max_dd: float
    mission_inf_gap: float


@dataclass(frozen=True)
class IndividualEvaluation:
    """T063 / T064 / T062 / T061 の per-individual 結果統合.

    Field 規約:

    - ``index``: 個体 index、 population dict の key と一致 (caller 責務、 詳細 Round 2 [W3]).
    - ``genome_hash``: deterministic tie-break 用 (SHA-256 hex32 等、 caller 責務で生成).
    - ``stage_a_pass``: T063 ``a_pass_indices`` に含まれるか (default-deny 契約).
    - ``bc_result``: T064 ``evaluate_bc_for_a_pass`` の出力. a_pass のみ非 None、 a_fail は
      None 必須 (T064 contract、 違反は :func:`run_generation_selection` 入口で ValueError).
    - ``mission_gap``: T062 ``evaluate_mission_inf_gap`` の出力 (全個体).
    - ``invariant_flags``: T061 :class:`InvariantFlags` (全個体).

    index 一意性契約 (詳細 Round 2 [W3] 反映):

    - ``index`` は population dict の key と一致 (``population[idx].index == idx``).
    - 同一 generation 内で一意 (caller 責務)、 重複時は upstream pipeline 異常.
    - sort_keys 4-tuple の最終 tie-break 鍵として使用 (詳細 Round 1 [C2]). 重複は禁止.
    """

    index: int
    genome_hash: str
    stage_a_pass: bool
    bc_result: BCEvaluationResult | None
    mission_gap: MissionGapResult
    invariant_flags: InvariantFlags


@dataclass(frozen=True)
class GenerationSelectionResult:
    """per-generation 主選抜結果.

    Field 規約:

    - ``front_assignments``: eligible のみ ``{idx: front_no (1-origin)}``、
      :class:`~types.MappingProxyType` で immutable (詳細設計 D2).
    - ``crowding_distances``: eligible のみ ``{idx: float (+inf at front size <= 2 or endpoints)}``、
      :class:`~types.MappingProxyType` で immutable.
    - ``survivor_indices``: 長さ <= ``pop_size``、 ``rank → -crowding → genome_hash → index`` の
      lex 昇順 (Round 1 [C2] 4-tuple).
    - ``parent_pairs``: 長さ ``pop_size`` 固定 (Round 1 [W2] / 詳細設計 R5)、
      offspring ``pop_size`` 体生成想定。 ``(idx, idx)`` は self-mating fallback (mutation only).
    - ``excluded_indices``: A-fail (``stage_a_pass=False``) or B-invariant-fail
      (``pareto_axis_usable=False``).
    - ``sample_size_warnings``: 操作上の warning 列 (``eligible_set_empty`` 等、 詳細設計 § 10).
    """

    front_assignments: types.MappingProxyType[int, int]
    crowding_distances: types.MappingProxyType[int, float]
    survivor_indices: tuple[int, ...]
    parent_pairs: tuple[tuple[int, int], ...]
    excluded_indices: frozenset[int]
    sample_size_warnings: tuple[str, ...]


# ---------------------------------------------------------------------------
# RNG seed helper (Round 1 [C1] / Round 2 [Suggestion 1])
# ---------------------------------------------------------------------------


def make_selection_seed(run_id: str, gen_no: int) -> int:
    """run 跨ぎ deterministic な seed を blake2b で生成.

    Python ``hash()`` は process salt で run 跨ぎ不安定なため不採用. ``blake2b`` 8-byte digest
    を ``int.from_bytes`` (big endian, unsigned) で 64-bit 整数化、 ``random.Random(seed)`` に
    渡す前提.

    payload は ``json.dumps([run_id, gen_no, "selection"], separators=(",", ":"))`` で構造化
    シリアライズし、 delimiter 衝突 (run_id 内 ``"|"`` 等) を回避 (Round 2 [Suggestion 1]).

    Args:
        run_id: Run 識別子 (T058 schema v2 で確定済).
        gen_no: 世代番号 (0-origin or 1-origin、 caller 規約に依拠).

    Returns:
        unsigned 64-bit 整数 seed (``random.Random`` に渡す).
    """
    payload_str = json.dumps([run_id, gen_no, "selection"], separators=(",", ":"))
    digest = hashlib.blake2b(payload_str.encode("utf-8"), digest_size=8).digest()
    return int.from_bytes(digest, byteorder="big", signed=False)


# ---------------------------------------------------------------------------
# Pareto axis 抽出 (Round 1 [C3] / [S3])
# ---------------------------------------------------------------------------


def extract_pareto_axis(
    bc_result: BCEvaluationResult,
    mission_gap: MissionGapResult,
) -> ParetoAxis:
    """T064 :class:`BCEvaluationResult` + T062 :class:`MissionGapResult` から Pareto 3 軸を抽出.

    軸対応 (synthesis § 5.2 / § 6.5):

    - f1 = ``bc_result.b_pooled_cf.net_pnl_after_cost`` (max)
    - f2 = ``bc_result.b_result.pooled_dd_per_fold_max`` (min、 concat DD でない、 T064 [C2])
    - f3 = ``mission_gap.mission_inf_gap`` (min、 T062 確定式)

    finite check (Round 1 [C3]): 3 軸全てに ``math.isfinite`` 検証、 non-finite で
    :class:`ValueError` raise.

    ``b_pooled_cf is None`` (= invariant_fail at any fold) は事前 caller 責務でフィルタすべき
    (:func:`run_generation_selection` が ``pareto_axis_usable=True`` のみ通す).
    ここで ``b_pooled_cf=None`` または ``b_result.pooled_dd_per_fold_max is None`` は
    contract 違反として :class:`ValueError` raise.

    Args:
        bc_result: T064 評価結果.
        mission_gap: T062 評価結果.

    Returns:
        :class:`ParetoAxis` (3 軸 finite).

    Raises:
        ValueError: ``bc_result.b_pooled_cf is None`` / ``b_result.pooled_dd_per_fold_max is None``
            または 3 軸のいずれかが non-finite.
    """
    if bc_result.b_pooled_cf is None:
        raise ValueError(
            "extract_pareto_axis requires bc_result.b_pooled_cf to be non-None. "
            "pareto_axis_usable=True 個体のみ T065 へ進入する契約 (T064)"
        )
    pooled_dd = bc_result.b_result.pooled_dd_per_fold_max
    if pooled_dd is None:
        raise ValueError(
            "extract_pareto_axis requires bc_result.b_result.pooled_dd_per_fold_max "
            "to be non-None. pareto_axis_usable=True と整合的な T064 contract"
        )
    net_pnl = bc_result.b_pooled_cf.net_pnl_after_cost
    max_dd = pooled_dd
    mig = mission_gap.mission_inf_gap
    if not math.isfinite(net_pnl):
        raise ValueError(f"net_pnl must be finite, got {net_pnl!r}")
    if not math.isfinite(max_dd):
        raise ValueError(f"max_dd must be finite, got {max_dd!r}")
    if not math.isfinite(mig):
        raise ValueError(f"mission_inf_gap must be finite, got {mig!r}")
    return ParetoAxis(net_pnl=net_pnl, max_dd=max_dd, mission_inf_gap=mig)


# ---------------------------------------------------------------------------
# effective constraint violation (Round 1 [C2])
# ---------------------------------------------------------------------------


def compute_effective_constraint_violation(
    mission_gap: MissionGapResult,
    invariant_flags: InvariantFlags,
) -> float:
    """T062 ``constraint_violation`` + ``INVARIANT_VIOLATION_PENALTY × invariant_count``.

    Deb 2000 constrained-domination の single scalar violation を構築.

    finite domain 制約 (Round 1 [C2]):

    - ``constraint_violation`` が ``+inf`` で :class:`ValueError` raise (運用 bug indicator,
      T061 / T062 で fail-fast すべき).
    - ``invariant_count < 0`` で :class:`ValueError` raise.

    invariant_count = ``session_close_drop_count + negative_equity_drop_open_count``
    (synthesis § 6.6 invariant fail-fast 原因).

    Args:
        mission_gap: T062 評価結果.
        invariant_flags: T061 InvariantFlags.

    Returns:
        ``constraint_violation + INVARIANT_VIOLATION_PENALTY * invariant_count`` (finite).

    Raises:
        ValueError: ``constraint_violation`` が non-finite または ``invariant_count < 0``.
    """
    cv = mission_gap.constraint_violation
    if not math.isfinite(cv):
        raise ValueError(
            f"T062 constraint_violation must be finite, got {cv!r}. "
            f"+inf 由来 (slack=-inf) は upstream T061/T062 で fail-fast すべき。 "
            f"T065 は finite domain でのみ動作 (defense-in-depth)"
        )
    inv_count = (
        invariant_flags.session_close_drop_count
        + invariant_flags.negative_equity_drop_open_count
    )
    if inv_count < 0:
        raise ValueError(f"invariant_count must be non-negative, got {inv_count}")
    return cv + INVARIANT_VIOLATION_PENALTY * float(inv_count)


# ---------------------------------------------------------------------------
# constrained-domination (Deb 2000)
# ---------------------------------------------------------------------------


def _pareto_dominates(p: ParetoAxis, q: ParetoAxis) -> bool:
    """Pareto 3 軸 dominance (f1 max, f2 min, f3 min). feasible 同士のみ呼ぶ.

    Returns True iff ``p`` weakly dominates ``q`` on all axes AND strictly dominates on at
    least one axis.
    """
    not_worse = (
        p.net_pnl >= q.net_pnl
        and p.max_dd <= q.max_dd
        and p.mission_inf_gap <= q.mission_inf_gap
    )
    if not not_worse:
        return False
    strictly_better = (
        p.net_pnl > q.net_pnl
        or p.max_dd < q.max_dd
        or p.mission_inf_gap < q.mission_inf_gap
    )
    return strictly_better


def constrained_dominates(
    p_axis: ParetoAxis,
    q_axis: ParetoAxis,
    *,
    p_violation: float,
    q_violation: float,
    p_feasible: bool,
    q_feasible: bool,
) -> bool:
    """Deb 2000 constrained-domination.

    Step 1: feasible vs infeasible は feasible が unconditionally dominate.
    Step 2: both infeasible → ``p_violation < q_violation`` で dominate.
    Step 3: both feasible → Pareto 3 軸 dominance.

    Args:
        p_axis: 候補 p の Pareto 軸.
        q_axis: 候補 q の Pareto 軸.
        p_violation: p の effective_constraint_violation.
        q_violation: q の effective_constraint_violation.
        p_feasible: p の feasibility (mission_gap.is_feasible AND invariant_flags.is_feasible).
        q_feasible: q の feasibility.

    Returns:
        True iff p constrained-dominates q.
    """
    if p_feasible and not q_feasible:
        return True
    if not p_feasible and q_feasible:
        return False
    if not p_feasible:
        # both infeasible
        return p_violation < q_violation
    return _pareto_dominates(p_axis, q_axis)


# ---------------------------------------------------------------------------
# Non-dominated sort (Deb et al. 2002 fast non-dominated sort)
# ---------------------------------------------------------------------------


def non_dominated_sort(
    eligible_indices: Iterable[int],
    axes: Mapping[int, ParetoAxis],
    violations: Mapping[int, float],
    feasibility: Mapping[int, bool],
) -> dict[int, int]:
    """Fast non-dominated sort (Deb et al. 2002) with Deb 2000 constrained-domination.

    O(M*N(N-1)/2) where M = number of objectives (3) and N = |eligible|.
    詳細 Round 1 [W2]: ``i < j`` のみ比較、 dominate 関係に応じて両側更新で冗長を半減.

    Args:
        eligible_indices: Pareto 候補 index iterable.
        axes: ``{idx: ParetoAxis}``.
        violations: ``{idx: effective_constraint_violation}``.
        feasibility: ``{idx: bool}``.

    Returns:
        ``{idx: front_no (1-origin)}``. front_no=1 は最優、 大きいほど劣後.
        空入力 (``eligible_indices`` が空) なら空 dict を返す.
    """
    eligible = list(eligible_indices)
    n = len(eligible)
    if n == 0:
        return {}

    fronts: list[list[int]] = [[]]
    domination_count: dict[int, int] = {idx: 0 for idx in eligible}
    dominated_set: dict[int, list[int]] = {idx: [] for idx in eligible}

    # i < j で 1 回比較し、 dominate 関係に応じて両側更新 (Round 1 [W2] 反映で半減)
    for i in range(n):
        p = eligible[i]
        for j in range(i + 1, n):
            q = eligible[j]
            p_dominates_q = constrained_dominates(
                axes[p],
                axes[q],
                p_violation=violations[p],
                q_violation=violations[q],
                p_feasible=feasibility[p],
                q_feasible=feasibility[q],
            )
            if p_dominates_q:
                dominated_set[p].append(q)
                domination_count[q] += 1
                continue
            q_dominates_p = constrained_dominates(
                axes[q],
                axes[p],
                p_violation=violations[q],
                q_violation=violations[p],
                p_feasible=feasibility[q],
                q_feasible=feasibility[p],
            )
            if q_dominates_p:
                dominated_set[q].append(p)
                domination_count[p] += 1

    for p in eligible:
        if domination_count[p] == 0:
            fronts[0].append(p)

    front_no: dict[int, int] = {}
    current_front = 0
    while fronts[current_front]:
        next_front: list[int] = []
        for p in fronts[current_front]:
            front_no[p] = current_front + 1
            for q in dominated_set[p]:
                domination_count[q] -= 1
                if domination_count[q] == 0:
                    next_front.append(q)
        current_front += 1
        fronts.append(next_front)

    return front_no


# ---------------------------------------------------------------------------
# Crowding distance (NSGA-II 標準、 Round 1 [W5] / [C3])
# ---------------------------------------------------------------------------


def crowding_distance(
    front_indices: Iterable[int],
    axes: Mapping[int, ParetoAxis],
) -> dict[int, float]:
    """Standard NSGA-II crowding distance, 3 軸正規化.

    Round 1 [W5]: ``front_size <= 2`` なら全員 ``+inf``.
    軸範囲 0 (max == min) なら当該軸の crowding 寄与 0 (zenigame ``sorting.py:97-104`` 同等).
    finite 軸保証下で ``inf - inf`` の経路を断つ (Round 1 [C3]、
    :func:`extract_pareto_axis` が finite 保証).

    Args:
        front_indices: 同一 front 内の index iterable.
        axes: ``{idx: ParetoAxis}`` (finite 保証済).

    Returns:
        ``{idx: crowding_distance}`` (大きいほど多様性高、 端は ``+inf``).
    """
    front_list = list(front_indices)
    crowding: dict[int, float] = dict.fromkeys(front_list, 0.0)

    if len(front_list) <= 2:
        for idx in front_list:
            crowding[idx] = math.inf
        return crowding

    for axis_name in ("net_pnl", "max_dd", "mission_inf_gap"):
        def _axis_key(i: int, _a: str = axis_name) -> float:
            return float(getattr(axes[i], _a))
        sorted_front = sorted(front_list, key=_axis_key)
        crowding[sorted_front[0]] = math.inf
        crowding[sorted_front[-1]] = math.inf

        a_min = getattr(axes[sorted_front[0]], axis_name)
        a_max = getattr(axes[sorted_front[-1]], axis_name)
        a_range = a_max - a_min
        if a_range == 0:
            # 軸範囲 0 寄与は 0 (zenigame sorting.py:97-104 同等)
            continue

        for k in range(1, len(sorted_front) - 1):
            prev_v = getattr(axes[sorted_front[k - 1]], axis_name)
            next_v = getattr(axes[sorted_front[k + 1]], axis_name)
            crowding[sorted_front[k]] += (next_v - prev_v) / a_range

    return crowding


# ---------------------------------------------------------------------------
# Private helpers (DRY、 詳細 Round 1 [W3] 反映)
# ---------------------------------------------------------------------------


def _validate_t064_contract(population: Mapping[int, IndividualEvaluation]) -> None:
    """T064 contract 違反 2 ケース + index 一致違反で :class:`ValueError`.

    Round 1 [W1] (a_pass=True なら bc_result is not None) +
    Round 2 [W2] (a_fail なら bc_result is None) +
    詳細 Round 2 [W3] (population[idx].index == idx 一致契約) を fail-fast.
    """
    for idx, ev in population.items():
        if ev.index != idx:
            raise ValueError(
                f"IndividualEvaluation.index ({ev.index}) must match population dict key ({idx}). "
                f"index 一意性契約 (詳細 Round 2 [W3]) 違反"
            )
        if ev.stage_a_pass and ev.bc_result is None:
            raise ValueError(
                f"T064 contract violation at idx={idx}: a_pass=True but bc_result is None"
            )
        if (not ev.stage_a_pass) and ev.bc_result is not None:
            raise ValueError(
                f"T064 contract violation at idx={idx}: a_fail but bc_result is not None"
            )


def _compute_eligible_axes_violations_feasibility(
    population: Mapping[int, IndividualEvaluation],
) -> tuple[
    list[int],                        # eligible_indices (sorted で安定順)
    dict[int, ParetoAxis],            # axes
    dict[int, float],                 # violations
    dict[int, bool],                  # feasibility
    set[int],                         # excluded_indices
]:
    """eligible 抽出 + axes/violations/feasibility 計算 (詳細 Round 1 [C2] / [W3]).

    eligible は ``sorted(population.keys())`` で安定順固定 (Round 1 [C2] determinism).
    """
    eligible: list[int] = []
    axes: dict[int, ParetoAxis] = {}
    violations: dict[int, float] = {}
    feasibility: dict[int, bool] = {}
    excluded_indices_set: set[int] = set()
    # sorted で安定順 (Round 1 [C2])
    for idx in sorted(population.keys()):
        ev = population[idx]
        if (
            ev.stage_a_pass
            and ev.bc_result is not None
            and ev.bc_result.pareto_axis_usable
        ):
            eligible.append(idx)
            axes[idx] = extract_pareto_axis(ev.bc_result, ev.mission_gap)
            violations[idx] = compute_effective_constraint_violation(
                ev.mission_gap, ev.invariant_flags,
            )
            feasibility[idx] = (
                ev.mission_gap.is_feasible
                and ev.invariant_flags.is_feasible
            )
        else:
            excluded_indices_set.add(idx)
    return eligible, axes, violations, feasibility, excluded_indices_set


def _compute_front_assignments_and_crowding(
    eligible: Sequence[int],
    axes: Mapping[int, ParetoAxis],
    violations: Mapping[int, float],
    feasibility: Mapping[int, bool],
) -> tuple[dict[int, int], dict[int, float]]:
    """non_dominated_sort + crowding distance の連鎖 (詳細 Round 1 [W3] DRY).

    Returns:
        (front_no, crowding) tuple, both ``{idx: value}``.
    """
    front_no = non_dominated_sort(eligible, axes, violations, feasibility)
    crowding: dict[int, float] = {}
    fronts_grouped: dict[int, list[int]] = {}
    for idx, fn in front_no.items():
        fronts_grouped.setdefault(fn, []).append(idx)
    for _fn, members in fronts_grouped.items():
        crowding.update(crowding_distance(members, axes))
    return front_no, crowding


def _build_sort_keys(
    eligible: Iterable[int],
    front_no: Mapping[int, int],
    crowding: Mapping[int, float],
    population: Mapping[int, IndividualEvaluation],
) -> dict[int, tuple[int, float, str, int]]:
    """sort_keys 4-tuple ``(front_no, -crowding, genome_hash, index)`` の事前計算 (Round 1 [C2])."""
    return {
        idx: (
            front_no[idx],
            -crowding[idx],
            population[idx].genome_hash,
            population[idx].index,
        )
        for idx in eligible
    }


# ---------------------------------------------------------------------------
# Survivor selection (deterministic、 DRY helper 経由)
# ---------------------------------------------------------------------------


def select_survivors(
    population: Mapping[int, IndividualEvaluation],
    *,
    target_size: int,
) -> tuple[int, ...]:
    """``rank → -crowding → genome_hash → index`` の lex 昇順で deterministic survivor 抽出.

    ``rng`` 不要 (概念 Round 1 [W3])、 完全 deterministic.

    eligible の定義: ``stage_a_pass=True AND bc_result is not None AND pareto_axis_usable=True``.

    入口契約: T064 contract 違反 2 ケース + index 一致違反で :class:`ValueError`
    (概念 Round 1 [W1] / Round 2 [W2] / 詳細 Round 2 [W3]).

    Args:
        population: ``{idx: IndividualEvaluation}``.
        target_size: 抽出上限 (>= 1).

    Returns:
        ``tuple[int, ...]``、 長さ <= ``target_size``、 eligible が ``target_size`` 未満なら
        全 eligible 返却.

    Raises:
        ValueError: ``target_size < 1``、 T064 contract 違反、 index 一致違反、
            または extract_pareto_axis / compute_effective_constraint_violation の finite 違反.
    """
    if target_size < 1:
        raise ValueError(f"target_size must be >= 1, got {target_size}")

    _validate_t064_contract(population)
    eligible, axes, violations, feasibility, _excluded = (
        _compute_eligible_axes_violations_feasibility(population)
    )
    if not eligible:
        return ()

    front_no, crowding = _compute_front_assignments_and_crowding(
        eligible, axes, violations, feasibility,
    )
    sort_keys = _build_sort_keys(eligible, front_no, crowding, population)
    sorted_eligible = sorted(eligible, key=lambda i: sort_keys[i])
    return tuple(sorted_eligible[:target_size])


# ---------------------------------------------------------------------------
# Binary tournament (crowded-comparison operator only、 Round 1 [S1] / Round 2 [Critical])
# ---------------------------------------------------------------------------


def binary_tournament(
    survivors: Sequence[int],
    sort_keys: Mapping[int, tuple[int, float, str, int]],
    *,
    rng: random.Random,
) -> int:
    """survivor 抽出済集団から crowded-comparison operator で 1 体抽出.

    ``sort_keys`` は :func:`run_generation_selection` 内で 1 回事前計算した
    ``{idx: (rank, -crowding, genome_hash, index)}`` の 4-tuple を渡す
    (詳細 Round 1 [C2] 反映、 最終 tie-break として ``index`` を追加し deterministic 完全保証).

    tournament 内では tuple lex 比較のみ (constrained-domination の再評価はしない、
    概念 Round 2 [Critical]).

    入口契約 (詳細 Round 1 [C1] defense-in-depth): ``len(survivors) >= 2`` 必須
    (``rng.sample(k=2)`` のため、 :func:`select_parent_pair` で ``len==1`` ガード済).

    Args:
        survivors: survivor index sequence.
        sort_keys: ``{idx: (rank, -crowding, genome_hash, index)}``.
        rng: deterministic ``random.Random``.

    Returns:
        勝者 idx.

    Raises:
        ValueError: ``len(survivors) < 2``.
    """
    if len(survivors) < 2:
        raise ValueError(
            f"binary_tournament requires len(survivors) >= 2, got {len(survivors)}"
        )
    a, b = rng.sample(list(survivors), k=2)
    return a if sort_keys[a] < sort_keys[b] else b


def select_parent_pair(
    survivors: Sequence[int],
    evaluations: Mapping[int, IndividualEvaluation],
    sort_keys: Mapping[int, tuple[int, float, str, int]],
    *,
    rng: random.Random,
    max_retry: int = 3,
) -> tuple[int, int]:
    """自己交配回避リトライ込みの parent pair 抽出.

    survivor 数による分岐 (詳細 Round 1 [C1] 反映):

    - ``len(survivors) == 0``: 呼出元責務として :class:`ValueError` raise (空 survivor は
      :func:`run_generation_selection` の入口で検出され、 ここには到達しない契約).
    - ``len(survivors) == 1``: 早期 return ``(survivors[0], survivors[0])`` で self-mating fallback
      (binary_tournament の ``rng.sample(k=2)`` で :class:`ValueError` を回避).
    - ``len(survivors) >= 2``: p1 を 1 回 + p2 を最大 ``max_retry`` 回追加抽出
      (= 合計最大 ``max_retry+1`` 回 :func:`binary_tournament` 呼出、 詳細 Round 1 [W1] 反映).

    超過なら ``(p1, p1)`` で mutation only fallback (caller 責務、 Phase 2 breeding 経路、 D8).

    Args:
        survivors: survivor index sequence.
        evaluations: ``{idx: IndividualEvaluation}``.
        sort_keys: ``{idx: (rank, -crowding, genome_hash, index)}``.
        rng: deterministic ``random.Random``.
        max_retry: p2 の最大リトライ回数 (default 3).

    Returns:
        ``(p1, p2)`` parent pair. ``p1 == p2`` は self-mating fallback シグナル.

    Raises:
        ValueError: ``len(survivors) == 0``.
    """
    if len(survivors) == 0:
        raise ValueError("select_parent_pair requires non-empty survivors")
    if len(survivors) == 1:
        only_idx = survivors[0]
        return (only_idx, only_idx)

    p1 = binary_tournament(survivors, sort_keys, rng=rng)
    for _ in range(max_retry):
        p2 = binary_tournament(survivors, sort_keys, rng=rng)
        if evaluations[p2].genome_hash != evaluations[p1].genome_hash:
            return (p1, p2)
    return (p1, p1)


# ---------------------------------------------------------------------------
# Top-level entry (per generation)
# ---------------------------------------------------------------------------


def run_generation_selection(
    population: Mapping[int, IndividualEvaluation],
    *,
    pop_size: int,
    rng: random.Random,
) -> GenerationSelectionResult:
    """per-generation 主選抜の top-level entry.

    入口契約検証:

    - ``pop_size >= 1`` (else :class:`ValueError`).
    - ``population`` 非空 (else :class:`ValueError`).
    - T064 contract: ``stage_a_pass=True`` なら ``bc_result is not None`` (else :class:`ValueError`).
    - T064 contract: ``stage_a_pass=False`` なら ``bc_result is None`` (else :class:`ValueError`).
    - index 一致: ``population[idx].index == idx`` (else :class:`ValueError`).

    eligible が空なら ``survivor_indices=()``、 ``parent_pairs=()``、
    ``excluded_indices = population.keys()``、 ``sample_size_warnings = ("eligible_set_empty",)``.

    Args:
        population: ``{idx: IndividualEvaluation}``.
        pop_size: target survivor / parent_pairs size.
        rng: deterministic ``random.Random`` (e.g. seeded via :func:`make_selection_seed`).

    Returns:
        :class:`GenerationSelectionResult`.

    Raises:
        ValueError: ``pop_size < 1``、 ``population`` 空、 T064 contract / index 違反、
            または finite domain 違反.
    """
    if pop_size < 1:
        raise ValueError(f"pop_size must be >= 1, got {pop_size}")
    if not population:
        raise ValueError("population must be non-empty")

    _validate_t064_contract(population)
    eligible, axes, violations, feasibility, excluded_indices_set = (
        _compute_eligible_axes_violations_feasibility(population)
    )

    sample_size_warnings: list[str] = []

    if not eligible:
        return GenerationSelectionResult(
            front_assignments=types.MappingProxyType({}),
            crowding_distances=types.MappingProxyType({}),
            survivor_indices=(),
            parent_pairs=(),
            excluded_indices=frozenset(excluded_indices_set),
            sample_size_warnings=("eligible_set_empty",),
        )

    front_no, crowding = _compute_front_assignments_and_crowding(
        eligible, axes, violations, feasibility,
    )
    sort_keys = _build_sort_keys(eligible, front_no, crowding, population)

    sorted_eligible = sorted(eligible, key=lambda i: sort_keys[i])
    survivor_indices = tuple(sorted_eligible[:pop_size])

    if len(eligible) < pop_size:
        sample_size_warnings.append(
            f"eligible_size_{len(eligible)}_below_pop_size_{pop_size}"
        )
    if len(eligible) < 30:
        sample_size_warnings.append("eligible_below_operational_threshold")
    if len(eligible) < 10:
        sample_size_warnings.append("eligible_critically_low")
    if len(eligible) == 1:
        sample_size_warnings.append("single_eligible_individual")
    if not any(feasibility.values()):
        sample_size_warnings.append("no_feasible_individuals")

    parent_pairs: list[tuple[int, int]] = []
    for _ in range(pop_size):
        pair = select_parent_pair(
            survivor_indices, population, sort_keys, rng=rng, max_retry=3,
        )
        parent_pairs.append(pair)

    return GenerationSelectionResult(
        front_assignments=types.MappingProxyType(dict(front_no)),
        crowding_distances=types.MappingProxyType(dict(crowding)),
        survivor_indices=survivor_indices,
        parent_pairs=tuple(parent_pairs),
        excluded_indices=frozenset(excluded_indices_set),
        sample_size_warnings=tuple(sample_size_warnings),
    )
