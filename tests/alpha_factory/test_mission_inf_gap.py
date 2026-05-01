"""T062: mission_inf_gap engine — 振る舞いベース test.

詳細設計: ``devnotes/20260430-0030-todo-T062-mission-inf-gap-engine/detailed-design.md``

Test 計画 (詳細設計 § 施策 2):

- Constants
- compute_mission_inf_gap_from_slacks
- compute_mission_margin
- compute_mission_signed_margin
- compute_constraint_violation
- extract_per_metric_shortfalls
- evaluate_mission_inf_gap (4 代表ケース + invariant 連鎖 + sentinel 比較)
- per_metric_shortfall immutability
- T065 constrained-domination 契約 (xfail)
- MissionGapResult 不変条件
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import FrozenInstanceError
from types import MappingProxyType

import pytest

from src.alpha_factory.canonical_metrics import (
    CanonicalFiveResult,
    InfeasibleReasonCode,
    InvariantFlags,
    SessionBucket,
)
from src.alpha_factory.mission_inf_gap import (
    MISSION_INF_GAP_METRIC_KEYS,
    MISSION_SIGNED_MARGIN_INFEASIBLE_SENTINEL,
    MissionGapResult,
    compute_constraint_violation,
    compute_mission_inf_gap_from_slacks,
    compute_mission_margin,
    compute_mission_signed_margin,
    evaluate_mission_inf_gap,
    extract_per_metric_shortfalls,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_canonical_five_result(
    *,
    slack_sharpe: float = 0.5,
    slack_pnl: float = 0.5,
    slack_dd: float = 0.5,
    slack_tc: float = 0.5,
    slack_wr: float = 0.5,
    is_feasible: bool = True,
    invariant_codes: frozenset[InfeasibleReasonCode] | None = None,
    session_close_drop_count: int = 0,
    negative_equity_drop_open_count: int = 0,
) -> CanonicalFiveResult:
    """Test 用 CanonicalFiveResult fixture.

    is_feasible=False を強制する場合は invariant_codes / *_count を非 0 にする.
    """
    if invariant_codes is None:
        if is_feasible:
            codes: frozenset[InfeasibleReasonCode] = frozenset()
        else:
            # 既定の infeasible 経路 (input 系)
            codes = frozenset({InfeasibleReasonCode.INPUT_EMPTY_TRADE_LIST})
    else:
        codes = invariant_codes

    invariants = InvariantFlags(
        session_close_drop_count=session_close_drop_count,
        negative_equity_drop_open_count=negative_equity_drop_open_count,
        infeasible_reason_codes=codes,
    )
    # 観測経路: invariants.is_feasible は 3 条件全て 0/empty で True.
    # caller 指定の is_feasible と invariants が整合しない場合は invariants 優先になる.
    return CanonicalFiveResult(
        sr_session_worst_block_scale=0.1,
        sr_session_worst_annual_estimate=2.5,
        net_pnl_after_cost=100000.0,
        max_dd=0.1,
        trade_count=500,
        session_block_win_rate_worst=0.5,
        per_bucket_sr={b: 0.1 for b in SessionBucket},
        per_bucket_wr={b: 0.5 for b in SessionBucket},
        low_sample_buckets=frozenset(),
        slack_sharpe=slack_sharpe,
        slack_pnl=slack_pnl,
        slack_dd=slack_dd,
        slack_tc=slack_tc,
        slack_wr=slack_wr,
        gate_worst_gap=0.0,
        gate_pass=True,
        log_pf_clip=0.0,
        bucket_validator_version="unvalidated",
        invariants=invariants,
    )


def _slacks_dict(
    sharpe: float = 0.5,
    pnl: float = 0.5,
    dd: float = 0.5,
    tc: float = 0.5,
) -> dict[str, float]:
    return {"sharpe": sharpe, "pnl": pnl, "dd": dd, "tc": tc}


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


class TestConstants:
    def test_mission_inf_gap_has_no_sentinel_returns_finite_value_for_all_inputs(
        self,
    ) -> None:
        """詳細 Round 1 [C1] 反映: sentinel +inf 撤廃確認.

        compute_mission_inf_gap_from_slacks は純粋に max(0, -slack) の最大値を返すのみ.
        +inf を返すのは upstream slack=-inf のみで、 is_feasible 経路では sentinel injection しない.
        """
        # feasible でも infeasible でも、 関数自体は slack を見るだけ.
        slacks = _slacks_dict(sharpe=1.0, pnl=1.0, dd=1.0, tc=1.0)
        assert compute_mission_inf_gap_from_slacks(slacks) == 0.0

    def test_mission_signed_margin_infeasible_sentinel_is_negative_infinity(
        self,
    ) -> None:
        assert math.isinf(MISSION_SIGNED_MARGIN_INFEASIBLE_SENTINEL)
        assert MISSION_SIGNED_MARGIN_INFEASIBLE_SENTINEL < 0.0
        assert MISSION_SIGNED_MARGIN_INFEASIBLE_SENTINEL == float("-inf")  # noqa: SIM300

    def test_mission_inf_gap_metric_keys_are_synthesis_six_four_strict_four(
        self,
    ) -> None:
        # win_rate を含まない 4 指標固定 (synthesis § 6.4 確定値)
        assert MISSION_INF_GAP_METRIC_KEYS == ("sharpe", "pnl", "dd", "tc")
        assert "wr" not in MISSION_INF_GAP_METRIC_KEYS
        assert "win_rate" not in MISSION_INF_GAP_METRIC_KEYS


# ---------------------------------------------------------------------------
# compute_mission_inf_gap_from_slacks
# ---------------------------------------------------------------------------


class TestComputeMissionInfGapFromSlacks:
    def test_compute_mission_inf_gap_zero_when_all_four_slacks_positive_or_zero(
        self,
    ) -> None:
        slacks = _slacks_dict(sharpe=0.0, pnl=0.5, dd=1.0, tc=2.0)
        assert compute_mission_inf_gap_from_slacks(slacks) == 0.0

    def test_compute_mission_inf_gap_returns_max_negative_slack_magnitude(self) -> None:
        # 1 指標未達: max(max(0, -slack)) = 0.3
        slacks = _slacks_dict(sharpe=-0.3, pnl=0.5, dd=0.5, tc=0.5)
        assert compute_mission_inf_gap_from_slacks(slacks) == pytest.approx(0.3)

        # 複数指標未達: max(0.7, 0.2) = 0.7
        slacks2 = _slacks_dict(sharpe=-0.7, pnl=-0.2, dd=0.5, tc=0.5)
        assert compute_mission_inf_gap_from_slacks(slacks2) == pytest.approx(0.7)

    def test_compute_mission_inf_gap_ignores_slack_wr_in_input(self) -> None:
        # slack_wr が dict に入っていても、 mission_inf_gap には影響しない.
        slacks: dict[str, float] = {
            "sharpe": 0.5,
            "pnl": 0.5,
            "dd": 0.5,
            "tc": 0.5,
            "wr": -100.0,  # 大きな負値だが、 結果に影響しないこと
        }
        assert compute_mission_inf_gap_from_slacks(slacks) == 0.0

    def test_compute_mission_inf_gap_raises_on_missing_required_key(self) -> None:
        # tc 欠損
        slacks = {"sharpe": 0.5, "pnl": 0.5, "dd": 0.5}
        with pytest.raises(ValueError, match="missing required keys"):
            compute_mission_inf_gap_from_slacks(slacks)

    def test_compute_mission_inf_gap_raises_on_nan_value(self) -> None:
        slacks = _slacks_dict(sharpe=float("nan"))
        with pytest.raises(ValueError, match="is NaN"):
            compute_mission_inf_gap_from_slacks(slacks)

    def test_compute_mission_inf_gap_negative_inf_slack_yields_positive_inf_gap(
        self,
    ) -> None:
        slacks = _slacks_dict(sharpe=float("-inf"))
        assert compute_mission_inf_gap_from_slacks(slacks) == float("inf")


# ---------------------------------------------------------------------------
# compute_mission_margin
# ---------------------------------------------------------------------------


class TestComputeMissionMargin:
    def test_compute_mission_margin_negates_mission_inf_gap(self) -> None:
        assert compute_mission_margin(0.3) == pytest.approx(-0.3)
        assert compute_mission_margin(1.5) == pytest.approx(-1.5)

    def test_compute_mission_margin_zero_when_all_achieved(self) -> None:
        assert compute_mission_margin(0.0) == 0.0

    def test_compute_mission_margin_returns_negative_inf_when_input_is_positive_inf(
        self,
    ) -> None:
        assert compute_mission_margin(float("inf")) == float("-inf")


# ---------------------------------------------------------------------------
# compute_mission_signed_margin
# ---------------------------------------------------------------------------


class TestComputeMissionSignedMargin:
    def test_compute_mission_signed_margin_returns_min_of_four_slacks(self) -> None:
        slacks = _slacks_dict(sharpe=0.5, pnl=0.2, dd=1.0, tc=0.8)
        assert compute_mission_signed_margin(slacks) == pytest.approx(0.2)

    def test_compute_mission_signed_margin_positive_when_all_four_slacks_positive(
        self,
    ) -> None:
        slacks = _slacks_dict(sharpe=0.1, pnl=0.2, dd=0.3, tc=0.4)
        assert compute_mission_signed_margin(slacks) == pytest.approx(0.1)

    def test_compute_mission_signed_margin_negative_when_any_slack_negative(
        self,
    ) -> None:
        slacks = _slacks_dict(sharpe=0.5, pnl=-0.3, dd=0.5, tc=0.5)
        assert compute_mission_signed_margin(slacks) == pytest.approx(-0.3)

    def test_compute_mission_signed_margin_handles_positive_infinity_slacks(
        self,
    ) -> None:
        # 極端な余裕 (+inf) は寄与せず、 他の有限値で min が確定
        slacks = _slacks_dict(
            sharpe=float("inf"), pnl=0.5, dd=0.3, tc=float("inf")
        )
        assert compute_mission_signed_margin(slacks) == pytest.approx(0.3)

    def test_compute_mission_signed_margin_returns_negative_inf_when_any_slack_is_negative_inf(
        self,
    ) -> None:
        slacks = _slacks_dict(sharpe=float("-inf"))
        assert compute_mission_signed_margin(slacks) == float("-inf")

    def test_compute_mission_signed_margin_raises_on_nan(self) -> None:
        slacks = _slacks_dict(dd=float("nan"))
        with pytest.raises(ValueError, match="is NaN"):
            compute_mission_signed_margin(slacks)


# ---------------------------------------------------------------------------
# compute_constraint_violation
# ---------------------------------------------------------------------------


class TestComputeConstraintViolation:
    def test_compute_constraint_violation_returns_zero_when_feasible(self) -> None:
        # feasible なら slack の値に関わらず 0.0
        slacks = _slacks_dict(sharpe=-0.5, pnl=-0.5, dd=-0.5, tc=-0.5)
        assert compute_constraint_violation(slacks, is_feasible=True) == 0.0

    def test_compute_constraint_violation_returns_finite_positive_when_infeasible(
        self,
    ) -> None:
        # 詳細 Round 1 [C1]: sentinel ではなく有限値で序列化可能
        slacks = _slacks_dict(sharpe=-0.3, pnl=0.5, dd=0.5, tc=0.5)
        v = compute_constraint_violation(slacks, is_feasible=False)
        assert v == pytest.approx(0.3)
        assert math.isfinite(v)

    def test_compute_constraint_violation_matches_mission_inf_gap_when_infeasible(
        self,
    ) -> None:
        # 現案: 同値 (将来 invariant violation count 加算で乖離可能)
        slacks = _slacks_dict(sharpe=-0.3, pnl=-0.7, dd=0.5, tc=0.5)
        mig = compute_mission_inf_gap_from_slacks(slacks)
        cv = compute_constraint_violation(slacks, is_feasible=False)
        assert cv == pytest.approx(mig)

    def test_compute_constraint_violation_raises_on_nan(self) -> None:
        slacks = _slacks_dict(tc=float("nan"))
        with pytest.raises(ValueError, match="is NaN"):
            compute_constraint_violation(slacks, is_feasible=False)


# ---------------------------------------------------------------------------
# extract_per_metric_shortfalls
# ---------------------------------------------------------------------------


class TestExtractPerMetricShortfalls:
    def test_per_metric_shortfall_returns_dict_with_four_keys(self) -> None:
        slacks = _slacks_dict()
        out = extract_per_metric_shortfalls(slacks)
        assert set(out.keys()) == set(MISSION_INF_GAP_METRIC_KEYS)
        assert len(out) == 4

    def test_per_metric_shortfall_zero_for_achieved_metric(self) -> None:
        slacks = _slacks_dict(sharpe=0.5, pnl=0.0, dd=2.0, tc=0.5)
        out = extract_per_metric_shortfalls(slacks)
        assert out["sharpe"] == 0.0
        assert out["pnl"] == 0.0
        assert out["dd"] == 0.0
        assert out["tc"] == 0.0

    def test_per_metric_shortfall_positive_for_unachieved_metric(self) -> None:
        slacks = _slacks_dict(sharpe=-0.3, pnl=0.5, dd=-0.7, tc=0.5)
        out = extract_per_metric_shortfalls(slacks)
        assert out["sharpe"] == pytest.approx(0.3)
        assert out["dd"] == pytest.approx(0.7)
        assert out["pnl"] == 0.0
        assert out["tc"] == 0.0

    def test_per_metric_shortfall_raises_on_nan(self) -> None:
        slacks = _slacks_dict(pnl=float("nan"))
        with pytest.raises(ValueError, match="is NaN"):
            extract_per_metric_shortfalls(slacks)


# ---------------------------------------------------------------------------
# evaluate_mission_inf_gap (top-level、 4 代表ケース)
# ---------------------------------------------------------------------------


class TestEvaluateMissionInfGap:
    def test_evaluate_mission_inf_gap_perfect_run_yields_zero_gap_and_signed_margin_positive(
        self,
    ) -> None:
        """代表ケース 1: feasible 全達成"""
        cfr = _make_canonical_five_result(
            slack_sharpe=0.5,
            slack_pnl=0.5,
            slack_dd=0.5,
            slack_tc=0.5,
        )
        result = evaluate_mission_inf_gap(cfr)
        assert result.is_feasible is True
        assert result.mission_inf_gap == 0.0
        assert result.constraint_violation == 0.0
        assert result.mission_signed_margin == pytest.approx(0.5)
        assert result.mission_signed_margin > 0
        assert result.mission_margin == 0.0

    def test_evaluate_mission_inf_gap_one_metric_short_yields_positive_gap_and_signed_margin_negative(
        self,
    ) -> None:
        """代表ケース 2: feasible 1 指標不足 (invariants は OK だが slack は negative)"""
        cfr = _make_canonical_five_result(
            slack_sharpe=-0.3,
            slack_pnl=0.5,
            slack_dd=0.5,
            slack_tc=0.5,
        )
        result = evaluate_mission_inf_gap(cfr)
        assert result.is_feasible is True
        assert result.mission_inf_gap == pytest.approx(0.3)
        # feasible なら constraint_violation は 0.0
        assert result.constraint_violation == 0.0
        assert result.mission_signed_margin == pytest.approx(-0.3)
        assert result.mission_signed_margin < 0
        assert result.mission_margin == pytest.approx(-0.3)

    def test_evaluate_mission_inf_gap_infeasible_yields_finite_gap_finite_violation_and_neg_inf_signed_margin(
        self,
    ) -> None:
        """代表ケース 3: infeasible (詳細 Round 1 [C1]、 sentinel +inf 撤廃)"""
        cfr = _make_canonical_five_result(
            slack_sharpe=-0.4,
            slack_pnl=0.5,
            slack_dd=0.5,
            slack_tc=0.5,
            is_feasible=False,
        )
        result = evaluate_mission_inf_gap(cfr)
        assert result.is_feasible is False
        # mission_inf_gap は有限値 (sentinel +inf 撤廃)
        assert result.mission_inf_gap == pytest.approx(0.4)
        assert math.isfinite(result.mission_inf_gap)
        # constraint_violation も有限値
        assert result.constraint_violation == pytest.approx(0.4)
        assert math.isfinite(result.constraint_violation)
        # mission_signed_margin のみ -inf sentinel
        assert result.mission_signed_margin == float("-inf")

    def test_evaluate_mission_inf_gap_propagates_value_error_on_nan_slack_in_all_paths(
        self,
    ) -> None:
        """代表ケース 4: NaN は全経路 (feasible / infeasible 両方) で fail-fast"""
        # feasible 経路で NaN
        cfr_feas = _make_canonical_five_result(
            slack_sharpe=float("nan"),
            is_feasible=True,
        )
        with pytest.raises(ValueError, match="is NaN"):
            evaluate_mission_inf_gap(cfr_feas)

        # infeasible 経路でも NaN は判定**前**に検出されること (詳細 Round 1 [C2])
        cfr_infeas = _make_canonical_five_result(
            slack_sharpe=float("nan"),
            is_feasible=False,
        )
        with pytest.raises(ValueError, match="is NaN"):
            evaluate_mission_inf_gap(cfr_infeas)

    # ------------------------------------------------------------------
    # invariant 連鎖
    # ------------------------------------------------------------------

    def test_evaluate_mission_inf_gap_propagates_t061_is_feasible_flag(self) -> None:
        cfr_feas = _make_canonical_five_result(is_feasible=True)
        cfr_infeas = _make_canonical_five_result(is_feasible=False)
        assert evaluate_mission_inf_gap(cfr_feas).is_feasible is True
        assert evaluate_mission_inf_gap(cfr_infeas).is_feasible is False

    def test_evaluate_mission_inf_gap_returns_frozen_dataclass(self) -> None:
        cfr = _make_canonical_five_result()
        r = evaluate_mission_inf_gap(cfr)
        assert isinstance(r, MissionGapResult)
        # frozen dataclass の immutability
        with pytest.raises(FrozenInstanceError):
            r.mission_inf_gap = 999.0  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Sentinel Comparison Convention (Round 2 [S3] 反映)
# ---------------------------------------------------------------------------


class TestSentinelComparisonConvention:
    def test_mission_inf_gap_finite_value_sorts_normally_in_minimize(self) -> None:
        # sorted by mission_inf_gap (minimize) で値順 (sentinel +inf なし)
        results = [
            evaluate_mission_inf_gap(
                _make_canonical_five_result(slack_sharpe=-0.2)
            ),
            evaluate_mission_inf_gap(
                _make_canonical_five_result(slack_sharpe=-0.5)
            ),
            evaluate_mission_inf_gap(
                _make_canonical_five_result(slack_sharpe=0.5)
            ),
        ]
        sorted_results = sorted(results, key=lambda x: x.mission_inf_gap)
        # 0.0 (perfect) → 0.2 → 0.5 の順
        assert sorted_results[0].mission_inf_gap == 0.0
        assert sorted_results[1].mission_inf_gap == pytest.approx(0.2)
        assert sorted_results[2].mission_inf_gap == pytest.approx(0.5)

    def test_constraint_violation_orders_infeasible_individuals_finite_scalar(
        self,
    ) -> None:
        # 詳細 Round 1 [C1]: infeasible 同士で violation 小さい方が前 (Deb 2000 準拠)
        r_small = evaluate_mission_inf_gap(
            _make_canonical_five_result(
                slack_sharpe=-0.1, is_feasible=False
            )
        )
        r_large = evaluate_mission_inf_gap(
            _make_canonical_five_result(
                slack_sharpe=-0.9, is_feasible=False
            )
        )
        assert r_small.constraint_violation < r_large.constraint_violation
        assert math.isfinite(r_small.constraint_violation)
        assert math.isfinite(r_large.constraint_violation)

    def test_mission_signed_margin_negative_infinity_sorts_to_end_in_archive_eviction(
        self,
    ) -> None:
        # archive eviction lex 順序 (descending mission_signed_margin、 上位ほど残す):
        # -inf は末尾 (= 真っ先に追い出される)
        items = [
            evaluate_mission_inf_gap(_make_canonical_five_result(is_feasible=False)),
            evaluate_mission_inf_gap(
                _make_canonical_five_result(slack_sharpe=0.5, is_feasible=True)
            ),
            evaluate_mission_inf_gap(
                _make_canonical_five_result(slack_sharpe=0.1, is_feasible=True)
            ),
        ]
        # 上位ほど残す = mission_signed_margin 降順
        sorted_items = sorted(items, key=lambda x: -x.mission_signed_margin)
        # 一番大きい (0.5) が先頭、 -inf (infeasible) が末尾
        assert sorted_items[0].mission_signed_margin == pytest.approx(0.5)
        assert sorted_items[-1].mission_signed_margin == float("-inf")


# ---------------------------------------------------------------------------
# per_metric_shortfall immutability (詳細 Round 1 [W2])
# ---------------------------------------------------------------------------


class TestPerMetricShortfallImmutability:
    def test_per_metric_shortfall_is_mapping_proxy_type_immutable(self) -> None:
        cfr = _make_canonical_five_result()
        r = evaluate_mission_inf_gap(cfr)
        # MappingProxyType は __setitem__ で TypeError
        assert isinstance(r.per_metric_shortfall, MappingProxyType)
        # Mapping 抽象とも互換
        assert isinstance(r.per_metric_shortfall, Mapping)
        with pytest.raises(TypeError):
            r.per_metric_shortfall["sharpe"] = 999.0  # type: ignore[index]


# ---------------------------------------------------------------------------
# T065 constrained-domination 契約テスト (xfail、 詳細 Round 1 [S3])
# ---------------------------------------------------------------------------


@pytest.mark.xfail(reason="T065 で constrained-domination 実装後に解除")
def test_infeasible_constraint_violation_ordering_contract_for_t065() -> None:
    """T065 (NSGA-II + constrained-domination) PR がマージされたら xfail decorator を外す.

    契約: infeasible 同士の比較で constraint_violation 小さい方が dominate.
    本契約は T065 の constrained_dominates 実装が import 可能になった時点で
    実検証可能になる.
    """
    from src.alpha_factory.ga.constrained_domination import (  # type: ignore[import-not-found]
        constrained_dominates,
    )

    r_small = evaluate_mission_inf_gap(
        _make_canonical_five_result(slack_sharpe=-0.1, is_feasible=False)
    )
    r_large = evaluate_mission_inf_gap(
        _make_canonical_five_result(slack_sharpe=-0.9, is_feasible=False)
    )
    # 両方 infeasible: small constraint_violation が dominate
    assert constrained_dominates(r_small, r_large) is True
    assert constrained_dominates(r_large, r_small) is False


# ---------------------------------------------------------------------------
# MissionGapResult 不変条件 (詳細 Round 2 [S2])
# ---------------------------------------------------------------------------


class TestMissionGapResultInvariants:
    def test_invariant_infeasible_implies_signed_margin_is_negative_infinity(
        self,
    ) -> None:
        cfr = _make_canonical_five_result(is_feasible=False)
        r = evaluate_mission_inf_gap(cfr)
        assert r.is_feasible is False
        assert r.mission_signed_margin == float("-inf")

    def test_invariant_feasible_implies_constraint_violation_is_zero(self) -> None:
        cfr = _make_canonical_five_result(
            slack_sharpe=-0.5, is_feasible=True
        )
        r = evaluate_mission_inf_gap(cfr)
        assert r.is_feasible is True
        assert r.constraint_violation == 0.0

    def test_invariant_mission_margin_equals_negative_mission_inf_gap(self) -> None:
        cfr = _make_canonical_five_result(slack_sharpe=-0.4)
        r = evaluate_mission_inf_gap(cfr)
        assert r.mission_margin == pytest.approx(-r.mission_inf_gap)
