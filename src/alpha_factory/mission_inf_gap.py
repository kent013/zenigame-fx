"""T062: mission_inf_gap engine — synthesis § 6.4 / § 6.5 / § 8.3 確定式の単一実装.

詳細:
- 概念設計: ``devnotes/20260430-0030-todo-T062-mission-inf-gap-engine/conceptual-design.md``
- 詳細設計: ``devnotes/20260430-0030-todo-T062-mission-inf-gap-engine/detailed-design.md``
- synthesis § 6.4 (mission_inf_gap)、 § 6.5 (Pareto 3 軸)、 § 8.3 (archive eviction)、 § 17 (用語)
- T061 依存: :class:`~src.alpha_factory.canonical_metrics.CanonicalFiveResult` の
  ``slack_sharpe`` / ``slack_pnl`` / ``slack_dd`` / ``slack_tc`` を消費

Phase 1 (本 TODO = T062 PR 1): 単体実装 + テストのみ、 GA / archive / cross_pair 未変更.
Phase 2 (別 PR): T065-T067 と同時、 7 箇所同時更新 (Phase 2 申し送り参照).

SSOT 宣言 (synthesis Round 21 改訂済、 2026-04-30):
- :attr:`MissionGapResult.mission_signed_margin` は archive CA #5 ordering の SSOT
  (synthesis § 8.3 と整合)。
- synthesis § 8.3 旧版 (``mission_margin = -mission_inf_gap``) は数式矛盾のため
  Round 21 改訂で ``mission_signed_margin = min(slack_*)`` に SSOT 昇格、
  ``mission_margin`` は BACKWARD COMPAT 整理。
- 本 module の :func:`compute_mission_signed_margin` が SSOT 実装.

学術引用:
- Deb, K. (2000). "An efficient constraint handling method for genetic algorithms."
  Computer Methods in Applied Mechanics and Engineering, 186(2-4), 311-338.
  https://doi.org/10.1016/S0045-7825(99)00389-8
- Deb, K., Pratap, A., Agarwal, S., & Meyarivan, T. (2002). "A fast and elitist
  multiobjective genetic algorithm: NSGA-II." IEEE Transactions on Evolutionary
  Computation, 6(2), 182-197. https://doi.org/10.1109/4235.996017
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Final

from src.alpha_factory.canonical_metrics import CanonicalFiveResult

__all__ = [
    # Constants
    "MISSION_INF_GAP_METRIC_KEYS",
    "MISSION_SIGNED_MARGIN_INFEASIBLE_SENTINEL",
    # DataClasses
    "MissionGapResult",
    # Helpers
    "compute_constraint_violation",
    "compute_mission_inf_gap_from_slacks",
    "compute_mission_margin",
    "compute_mission_signed_margin",
    "evaluate_mission_inf_gap",
    "extract_per_metric_shortfalls",
]


# ---------------------------------------------------------------------------
# Constants (synthesis § 6.4 / § 6.5 / § 8.3 厳密準拠)
# ---------------------------------------------------------------------------

# Note (詳細 Round 1 [C1] 反映): MISSION_GAP_INFEASIBLE_SENTINEL=+inf を撤廃.
# mission_inf_gap は純粋に synthesis § 6.4 式 (= max(max(0, -slack_m))) を返し、
# is_feasible=False 個体の序列化は新規 ``constraint_violation`` field で対応.
# 全個体に +inf を入れると Deb 2000 の infeasible 同士 violation 序列が成立しないため.

MISSION_SIGNED_MARGIN_INFEASIBLE_SENTINEL: Final[float] = float("-inf")
"""is_feasible=False 時の mission_signed_margin (archive CA #5 ordering 用 sentinel).

margin が -inf なら archive eviction で最低 priority (= 真っ先に追い出される).
Note: 全 infeasible 個体が -inf 同値になるため、 archive 内 infeasible 同士の優先順位は
``constraint_violation`` 等 secondary key で tie-break する責務 (T067 lex 順序参照).
"""

MISSION_INF_GAP_METRIC_KEYS: Final[tuple[str, ...]] = ("sharpe", "pnl", "dd", "tc")
"""synthesis § 6.4 確定値: mission_inf_gap は 4 指標のみ (win_rate 含まない).

canonical 5 worst gate は別 (T061 が担当)。 本 const は machine-readable な型強制で
``slack_wr`` の混入を防ぐ.
"""


# ---------------------------------------------------------------------------
# Output DataClass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MissionGapResult:
    """Pareto 3 軸 f3 + archive eviction 用 mission gap / margin 結果.

    実運用 ordering 規約 (詳細 Round 1 [C1] / [S1] / [S2] 反映):

    - **Pareto 3 軸 f3 (NSGA-II minimize)**: ``mission_inf_gap`` を使う
      (純粋 § 6.4 式、 sentinel なし)
    - **NSGA-II constrained-domination (T065 実装、 Deb 2000)**:

      - feasible vs infeasible: ``is_feasible`` flag で feasible が dominate
      - infeasible vs infeasible: ``constraint_violation`` 小さい方が dominate
      - feasible vs feasible: ``mission_inf_gap`` 等 Pareto 軸で通常比較

    - **archive CA #5 (eviction lex 順序、 上位ほど残す)**: ``mission_signed_margin``
      を使う (synthesis Round 21 改訂後 SSOT、 本 module が実装)
    - **観測 / 診断**: ``per_metric_shortfall`` を使う (always with ``is_feasible`` flag)

    Sentinel Comparison Convention (Round 2 [S3] / 詳細 Round 1 [C1] 反映):

    - mission_inf_gap: 値域 [0, +inf)、 sentinel なし。 Pareto front は他軸 (f1=net_pnl,
      f2=max_dd) と組合せた支配関係で決定。 infeasible 個体は constrained-domination
      (T065) で feasible 集団から確実に分離される.
    - constraint_violation: 値域 [0, +inf]、 sentinel なし、 finite scalar。 feasible
      個体は 0.0、 infeasible 個体は max(0, -slack_m) の値 (mission_inf_gap と同値だが、
      概念上は infeasible 序列化用のため別 field)。 NaN は ValueError raise (caller 責務).
    - mission_signed_margin = -inf: Python ``<`` 比較で常に最小、 archive eviction で
      最低 priority。 全 infeasible が -inf 同値、 secondary key (T067 lex 順序、 例:
      ``-constraint_violation``) で tie-break する責務.
    - per_metric_shortfall: MappingProxyType (frozen dataclass の immutable 性を保つため、
      詳細 Round 1 [W2] 反映)。 NaN は ValueError、 +inf 寄与は upstream slack=-inf 由来.

    Field 詳細:

    - **mission_inf_gap**: synthesis § 6.4 確定式 (Pareto f3 minimize 用、 純粋計算)

      - = ``max(max(0, -slack_sharpe), max(0, -slack_pnl), max(0, -slack_dd), max(0, -slack_tc))``
      - 値域: [0, +inf)
      - 4 指標全達成 → 0.0、 1 指標以上未達 → > 0、 slack=-inf → +inf
      - **is_feasible に依存しない有限値計算** (詳細 Round 1 [C1] 反映、 sentinel +inf 撤廃)

    - **constraint_violation**: NSGA-II constrained-domination (Deb 2000) 用 violation 量

      - = mission_inf_gap (現案では同値、 将来 invariant violation count を加算する余地あり)
      - 値域: [0, +inf] (詳細 Round 2 [W1] 反映: slack=-inf 由来で +inf を取り得る)
      - is_feasible=True → 0.0
      - is_feasible=False → > 0 (infeasible 個体間の序列化に使用、 T065 担当)
      - infeasible 個体間で比較可能なスカラー (詳細 Round 1 [C1] 反映)
      - **重要 (詳細 Round 2 [W2] 反映)**: 現仕様では 4 slack 由来のみ。 ``is_feasible=False``
        の原因が slack 外 (例: synthesis § 6.6 の ``session_close_drop_count > 0`` /
        ``negative_equity_drop_open_count > 0`` のみで slack は問題なし) の場合、
        ``constraint_violation`` は 4 slack 計算値 (potentially 0 or 小さい値) になる.
        T065 (constrained-domination) では「invariant violation の有無を Deb 2000 比較に
        どう組込むか」 を明文化する必要 (T065 申し送り、 例:
        ``constraint_violation + invariant_violation_penalty * Σ(strategic_* counts)`` 等).

    - **mission_margin** (DEPRECATED-COMPAT: synthesis § 8.3 命名通り、 数式と命名が乖離.
      **実運用 ordering は mission_signed_margin / constraint_violation を使うこと**):

      - = ``-mission_inf_gap``
      - 値域: (-inf, 0]、 達成超過余裕は表現できない (4 指標全達成個体は一律 0.0)
      - is_feasible=False → ``-mission_inf_gap`` (= negative finite or -inf)

    - **mission_signed_margin** (実運用 SSOT、 archive CA #5 ordering 用):

      - = ``min(slack_sharpe, slack_pnl, slack_dd, slack_tc)``
      - 値域: feasible なら任意実数、 正値=4 指標全余裕、 負値=1 指標以上不足
      - is_feasible=False → -inf (:data:`MISSION_SIGNED_MARGIN_INFEASIBLE_SENTINEL`)

    - **per_metric_shortfall**: 4 指標別 ``max(0, -slack_m)`` immutable mapping
      (diagnostic only)

      - keys: ``"sharpe"`` / ``"pnl"`` / ``"dd"`` / ``"tc"``
      - 型: ``MappingProxyType[str, float]`` (frozen dataclass 保護、 詳細 Round 1 [W2])
      - **always interpret with ``is_feasible`` flag** (Round 2 [W3] 反映): infeasible 時も
        raw 計算値を返す (詳細 Round 1 [W1])、 strategic_* 時は slack 意味損なわれ可能性

    - **is_feasible**: T061 :attr:`InvariantFlags.is_feasible` を継承 (engine 連鎖)
    """

    mission_inf_gap: float
    constraint_violation: float
    mission_margin: float
    mission_signed_margin: float
    per_metric_shortfall: Mapping[str, float]
    is_feasible: bool


# ---------------------------------------------------------------------------
# Helpers (pure functions)
# ---------------------------------------------------------------------------


def _validate_slacks_dict(slacks: Mapping[str, float]) -> None:
    """slacks dict が必須 4 key を持ち、 値が NaN でないことを検証.

    NaN 検出時は ValueError raise (caller 修正責務、 Round 2 [W2] fail-fast 方針).
    +inf / -inf は許容 (T061 の signed slack で +inf=極端な余裕、 -inf=極端な不足を
    表現可能).
    """
    missing_keys = set(MISSION_INF_GAP_METRIC_KEYS) - set(slacks.keys())
    if missing_keys:
        raise ValueError(
            f"slacks missing required keys: {sorted(missing_keys)}. "
            f"Required: {MISSION_INF_GAP_METRIC_KEYS}"
        )
    for key in MISSION_INF_GAP_METRIC_KEYS:
        value = slacks[key]
        if math.isnan(value):
            raise ValueError(
                f"slacks[{key!r}] is NaN; engine composition bug indicator. "
                f"caller must fix upstream (T061 signed slack 計算)."
            )


def compute_mission_inf_gap_from_slacks(slacks: Mapping[str, float]) -> float:
    """4 指標 signed slack から ``mission_inf_gap`` を計算 (synthesis § 6.4 厳密).

    式::

        mission_inf_gap = max(max(0, -slacks[m]) for m in MISSION_INF_GAP_METRIC_KEYS)

    Args:
        slacks: T061 signed slack dict (必須 4 key: sharpe / pnl / dd / tc).
            ``slack_wr`` は無視 (synthesis § 6.4 で win_rate を含まない).

    Returns:
        ``mission_inf_gap >= 0``

        - +inf: 1 指標以上が -inf (極端な不足)
        - 0.0: 4 指標全達成
        - 正値: 1 指標以上未達

    Raises:
        ValueError: slacks に必須 key 欠損 or NaN を検出した場合 (caller 修正責務).
    """
    _validate_slacks_dict(slacks)
    return max(max(0.0, -slacks[k]) for k in MISSION_INF_GAP_METRIC_KEYS)


def compute_mission_margin(mission_inf_gap: float) -> float:
    """synthesis § 8.3 命名通り ``mission_margin = -mission_inf_gap`` (BACKWARD COMPAT).

    実運用 ordering には :func:`compute_mission_signed_margin` を使うこと
    (本関数は backward compat 用).
    """
    return -mission_inf_gap


def compute_mission_signed_margin(slacks: Mapping[str, float]) -> float:
    """archive CA #5 ordering 用 signed margin (synthesis § 8.3 SSOT、 Round 21 改訂後).

    式::

        mission_signed_margin = min(slacks[m] for m in MISSION_INF_GAP_METRIC_KEYS)

    Args:
        slacks: T061 signed slack dict (必須 4 key).

    Returns:
        signed margin (任意実数)

        - 4 指標全達成かつ余裕大: large positive
        - 1 指標 marginal: small positive
        - 1 指標未達: negative
        - 1 指標以上 -inf: -inf

    Raises:
        ValueError: slacks に必須 key 欠損 or NaN を検出した場合 (caller 修正責務).
    """
    _validate_slacks_dict(slacks)
    return min(slacks[k] for k in MISSION_INF_GAP_METRIC_KEYS)


def extract_per_metric_shortfalls(slacks: Mapping[str, float]) -> dict[str, float]:
    """4 指標別 shortfall dict を返す (diagnostic only、 Round 2 [W3] 反映).

    各 key で ``max(0, -slacks[m])``。 表示時は always with ``is_feasible`` flag を
    使うこと.
    """
    _validate_slacks_dict(slacks)
    return {k: max(0.0, -slacks[k]) for k in MISSION_INF_GAP_METRIC_KEYS}


def compute_constraint_violation(
    slacks: Mapping[str, float], is_feasible: bool
) -> float:
    """NSGA-II constrained-domination (Deb 2000) 用 violation 量を計算.

    - ``is_feasible=True`` → 0.0
    - ``is_feasible=False`` → ``max(max(0, -slack_m) for m in 4 指標)``
      (有限値、 sentinel なし).

      現案では :func:`compute_mission_inf_gap_from_slacks` と同値だが、 概念上は
      infeasible 序列化用のため別関数。 将来 invariant violation count
      (e.g. ``session_close_drop_count``) を加算する余地あり.

    Raises:
        ValueError: slacks に必須 key 欠損 or NaN を検出した場合.
    """
    _validate_slacks_dict(slacks)
    if is_feasible:
        return 0.0
    return max(max(0.0, -slacks[k]) for k in MISSION_INF_GAP_METRIC_KEYS)


# ---------------------------------------------------------------------------
# Top-level entry
# ---------------------------------------------------------------------------


def evaluate_mission_inf_gap(result: CanonicalFiveResult) -> MissionGapResult:
    """T061 出力を mission_inf_gap engine で消費し、 :class:`MissionGapResult` を返す.

    依存方向: T062 → T061 (logical pipeline、 canonical 5 → mission_inf_gap).
    T061 の signed slack 4 指標 (sharpe / pnl / dd / tc) を直接消費、 ``slack_wr`` は無視.

    NaN fail-fast 全経路化 (詳細 Round 1 [C2] 反映):
        ``is_feasible`` に依存せず、 4 slack の NaN 検証を判定**前**に実施.
        NaN は engine 合成 bug indicator で全経路で fail-fast.

    sentinel 撤廃 (詳細 Round 1 [C1] 反映):
        ``is_feasible=False`` でも :attr:`MissionGapResult.mission_inf_gap` は純粋
        § 6.4 式の有限値を返す。 :attr:`MissionGapResult.constraint_violation` で
        infeasible 序列化を提供 (Deb 2000 用)。
        :attr:`MissionGapResult.mission_signed_margin` のみ -inf sentinel を維持
        (archive eviction lex 順序の最低 priority マーク用).

    Args:
        result: T061 評価結果 (:class:`CanonicalFiveResult`).

    Returns:
        :class:`MissionGapResult` (frozen dataclass、 immutable per_metric_shortfall).

    Raises:
        ValueError: T061 出力に NaN slack を検出した場合 (caller=T061 修正責務、
            fail-fast 方針: selection loop 例外は run abort).
    """
    # NaN fail-fast 全経路化 (詳細 Round 1 [C2] 反映).
    slacks: dict[str, float] = {
        "sharpe": result.slack_sharpe,
        "pnl": result.slack_pnl,
        "dd": result.slack_dd,
        "tc": result.slack_tc,
    }
    _validate_slacks_dict(slacks)  # 全経路で NaN check 実施

    is_feasible = result.invariants.is_feasible
    mig = compute_mission_inf_gap_from_slacks(slacks)
    constraint_violation = compute_constraint_violation(slacks, is_feasible=is_feasible)
    mission_margin = compute_mission_margin(mig)
    if is_feasible:
        mission_signed_margin = compute_mission_signed_margin(slacks)
    else:
        # archive eviction で最低 priority マーク (T067 で secondary tie-break key 必要).
        mission_signed_margin = MISSION_SIGNED_MARGIN_INFEASIBLE_SENTINEL

    per_metric = extract_per_metric_shortfalls(slacks)
    return MissionGapResult(
        mission_inf_gap=mig,
        constraint_violation=constraint_violation,
        mission_margin=mission_margin,
        mission_signed_margin=mission_signed_margin,
        per_metric_shortfall=MappingProxyType(per_metric),
        is_feasible=is_feasible,
    )
