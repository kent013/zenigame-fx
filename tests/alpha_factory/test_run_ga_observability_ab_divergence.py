"""T081 step 1: ABDivergenceMetric 実値配線の run_ga.py 集約 helper test.

詳細設計: devnotes/20260502-2206-todo-T081-observability-real-values/detailed-design.md § 3.4.3

run_ga 全体の integration test は重い (= bars / aux / DB 必要) ため、 集約 helper
``_aggregate_ab_summary`` を直接 test する。 swim_lane 経路の score 収集は
``test_swim_lane.py`` の AB pair test (test 12-15 + nan/inf/numeric ガード) で担保済。
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from scripts.alpha_factory.run_ga import _aggregate_ab_summary
from src.alpha_factory.observability import (
    AB_MIN_ACTIONABLE_PAIRS,
    compute_ab_divergence_on_b_evaluated,
)

PHASE1_SOURCE = "fitness_pen+median_oos_sharpe_phase1"


def _summary(
    *,
    pairs: list[tuple[float, float]],
    source: str = PHASE1_SOURCE,
    b_evaluated: int = 0,
    excluded: int = 0,
) -> dict:
    """test 用 summary_out dict (= lane_manager.run_generation の戻りを模倣)."""
    return {
        "ab_score_pairs": pairs,
        "ab_score_source": source,
        "ab_b_evaluated_count": b_evaluated,
        "ab_excluded_preflight_count": excluded,
    }


# ---------------------------------------------------------------------------
# Test 1-11: run_ga 経路 (集約 helper を介して)
# ---------------------------------------------------------------------------


class TestAggregateAbSummary:
    """``_aggregate_ab_summary`` helper の集約挙動 (詳細設計 § 3.4.3)."""

    def test_1_pairs_aggregate_into_external_list(self) -> None:
        """test 1: pairs が外部 list に extend される (= n>=10 で status='ok' へ)."""
        pairs: list[tuple[float, float]] = []
        # 10 ペアを 1 世代 summary で append
        gen_pairs = [(float(i), float(2 * i)) for i in range(10)]
        b_eval, excluded, source = _aggregate_ab_summary(
            summary_out=_summary(pairs=gen_pairs, b_evaluated=10),
            all_ab_score_pairs=pairs,
            b_evaluated_count=0,
            excluded_preflight_count=0,
            current_score_source=None,
        )
        assert pairs == gen_pairs
        assert b_eval == 10
        assert excluded == 0
        assert source == PHASE1_SOURCE

    def test_2_n_below_min_returns_insufficient_data(self) -> None:
        """test 2: n=5 で compute_ab_divergence は insufficient_data."""
        pairs: list[tuple[float, float]] = []
        gen_pairs = [(float(i), float(2 * i)) for i in range(5)]
        _aggregate_ab_summary(
            summary_out=_summary(pairs=gen_pairs, b_evaluated=5),
            all_ab_score_pairs=pairs,
            b_evaluated_count=0,
            excluded_preflight_count=0,
            current_score_source=None,
        )
        a_scores = [Decimal(repr(a)) for a, _ in pairs]
        b_scores = [Decimal(repr(b)) for _, b in pairs]
        result = compute_ab_divergence_on_b_evaluated(a_scores, b_scores)
        assert result.status == "insufficient_data"
        assert result.n_pairs == 5

    def test_3_zero_variance_when_all_a_constant(self) -> None:
        """test 3: 全 a が同値 → status='zero_variance' (Codex Round 1 [Warning] 5)."""
        pairs: list[tuple[float, float]] = []
        gen_pairs = [(1.0, float(i)) for i in range(10)]  # a 定数
        _aggregate_ab_summary(
            summary_out=_summary(pairs=gen_pairs, b_evaluated=10),
            all_ab_score_pairs=pairs,
            b_evaluated_count=0,
            excluded_preflight_count=0,
            current_score_source=None,
        )
        a_scores = [Decimal(repr(a)) for a, _ in pairs]
        b_scores = [Decimal(repr(b)) for _, b in pairs]
        result = compute_ab_divergence_on_b_evaluated(a_scores, b_scores)
        assert result.status == "zero_variance"

    def test_4_excludes_invalid_pair_types(self) -> None:
        """test 4: 不正型 (= str / list / bool) の pair は append されない (defensive)
        (impl-review Round 1 [Suggestion] 取込: consumer 側 bool 除外も担保)."""
        pairs: list[tuple[float, float]] = []
        # valid + invalid str + invalid bool (= consumer defense in depth)
        bad_summary = {
            "ab_score_pairs": [
                (1.0, 2.0),
                ("not", "tuple"),
                (True, False),  # bool は numbers.Real subclass だが consumer 側でも除外
            ],
            "ab_score_source": PHASE1_SOURCE,
            "ab_b_evaluated_count": 1,
            "ab_excluded_preflight_count": 0,
        }
        _aggregate_ab_summary(
            summary_out=bad_summary,
            all_ab_score_pairs=pairs,
            b_evaluated_count=0,
            excluded_preflight_count=0,
            current_score_source=None,
        )
        assert pairs == [(1.0, 2.0)]

    def test_4b_includes_numpy_scalar_pairs(self) -> None:
        """test 4b: numpy.float32 / numpy.int64 等の数値型は include
        (impl-review Round 1 [Warning] 取込)."""
        import numpy as np

        pairs: list[tuple[float, float]] = []
        np_summary = {
            "ab_score_pairs": [
                (np.float32(0.42), np.int64(1)),
                (np.float64(0.5), 2.0),
            ],
            "ab_score_source": PHASE1_SOURCE,
            "ab_b_evaluated_count": 2,
            "ab_excluded_preflight_count": 0,
        }
        _aggregate_ab_summary(
            summary_out=np_summary,
            all_ab_score_pairs=pairs,
            b_evaluated_count=0,
            excluded_preflight_count=0,
            current_score_source=None,
        )
        assert len(pairs) == 2
        # float() conversion 後の値は numeric
        assert all(isinstance(a, float) and isinstance(b, float) for a, b in pairs)
        assert pairs[0][0] == pytest.approx(0.42, abs=1e-6)
        assert pairs[0][1] == 1.0

    def test_5_preflight_excluded_count_propagates(self) -> None:
        """test 5: preflight 除外個体 counter が累積される."""
        pairs: list[tuple[float, float]] = []
        _, excluded, _ = _aggregate_ab_summary(
            summary_out=_summary(pairs=[], b_evaluated=0, excluded=5),
            all_ab_score_pairs=pairs,
            b_evaluated_count=0,
            excluded_preflight_count=0,
            current_score_source=None,
        )
        assert excluded == 5
        assert pairs == []

    def test_6_aggregated_across_generations(self) -> None:
        """test 6: 複数世代の summary を順次 aggregate (cfg.ga.generations=2 → 3 世代分)."""
        pairs: list[tuple[float, float]] = []
        b_eval = 0
        excluded = 0
        source: str | None = None
        for _gen in range(3):  # 3 世代 (= gen 0..2)
            gen_pairs = [(float(i), float(2 * i)) for i in range(10)]
            b_eval, excluded, source = _aggregate_ab_summary(
                summary_out=_summary(pairs=gen_pairs, b_evaluated=10),
                all_ab_score_pairs=pairs,
                b_evaluated_count=b_eval,
                excluded_preflight_count=excluded,
                current_score_source=source,
            )
        assert len(pairs) == 30  # 3 世代 × 10
        assert b_eval == 30
        assert source == PHASE1_SOURCE

    def test_7_ok_status_returned_when_n_above_min(self) -> None:
        """test 7: n>=10 + 線形相関で status='ok' / corr finite."""
        pairs: list[tuple[float, float]] = []
        gen_pairs = [(float(i), float(2 * i + 0.1)) for i in range(15)]
        _aggregate_ab_summary(
            summary_out=_summary(pairs=gen_pairs, b_evaluated=15),
            all_ab_score_pairs=pairs,
            b_evaluated_count=0,
            excluded_preflight_count=0,
            current_score_source=None,
        )
        a_scores = [Decimal(repr(a)) for a, _ in pairs]
        b_scores = [Decimal(repr(b)) for _, b in pairs]
        result = compute_ab_divergence_on_b_evaluated(a_scores, b_scores)
        assert result.status == "ok"
        assert result.n_pairs == 15
        assert Decimal(-1) <= result.corr <= Decimal(1)

    def test_8_other_metrics_independent_from_ab_aggregation(self) -> None:
        """test 8: AB pair 集約は他 metric (q_force / archive_churn 等) と独立。
        helper の責務が ab_* 4 キーに限定されることを確認."""
        pairs: list[tuple[float, float]] = []
        sum_with_extra_keys = {
            **_summary(pairs=[(1.0, 2.0)], b_evaluated=1),
            "stage_a_pass": 99,  # 他 metric (helper は読まない)
            "graduation_count": 7,
        }
        b_eval, _, source = _aggregate_ab_summary(
            summary_out=sum_with_extra_keys,
            all_ab_score_pairs=pairs,
            b_evaluated_count=0,
            excluded_preflight_count=0,
            current_score_source=None,
        )
        assert pairs == [(1.0, 2.0)]
        # helper は他 metric を touch しない (= 戻り値は ab_* のみ)
        assert b_eval == 1
        assert source == PHASE1_SOURCE

    def test_9_score_source_mixing_raises_runtime_error(self) -> None:
        """test 9: 異なる source が混入したら RuntimeError (Codex Round 1 [Critical] 1)."""
        pairs: list[tuple[float, float]] = []
        # 1 世代目: phase1 source
        _, _, source = _aggregate_ab_summary(
            summary_out=_summary(pairs=[(1.0, 2.0)], source=PHASE1_SOURCE),
            all_ab_score_pairs=pairs,
            b_evaluated_count=0,
            excluded_preflight_count=0,
            current_score_source=None,
        )
        # 2 世代目: 別 source (= 仮想の SSOT 統一後)
        with pytest.raises(RuntimeError, match="ab_score_source mixing"):
            _aggregate_ab_summary(
                summary_out=_summary(
                    pairs=[(2.0, 4.0)],
                    source="canonical_five_source_score_v2",
                ),
                all_ab_score_pairs=pairs,
                b_evaluated_count=0,
                excluded_preflight_count=0,
                current_score_source=source,
            )

    def test_10_excluded_preflight_count_visible_in_returned_state(self) -> None:
        """test 10: excluded_preflight_count が累積されて log/diagnose 可能 (Codex [Warning] 4)."""
        pairs: list[tuple[float, float]] = []
        # 2 世代で 累計 excluded=8
        b_eval, excluded, _ = _aggregate_ab_summary(
            summary_out=_summary(pairs=[], excluded=3),
            all_ab_score_pairs=pairs,
            b_evaluated_count=0,
            excluded_preflight_count=0,
            current_score_source=None,
        )
        b_eval, excluded, _ = _aggregate_ab_summary(
            summary_out=_summary(pairs=[], excluded=5),
            all_ab_score_pairs=pairs,
            b_evaluated_count=b_eval,
            excluded_preflight_count=excluded,
            current_score_source=None,
        )
        assert excluded == 8

    def test_11_no_key_collision_with_list_aggregation(self) -> None:
        """test 11: list 集約 (= dict ではない) で key 衝突 (= 上書きロス) が発生しない
        (Codex Round 1 [Critical] 2)."""
        pairs: list[tuple[float, float]] = []
        # 同じ pair を 2 世代で 2 回 append → 全 2 件保持される (上書きロスなし)
        same_pair = [(0.5, 1.0)]
        _aggregate_ab_summary(
            summary_out=_summary(pairs=same_pair, b_evaluated=1),
            all_ab_score_pairs=pairs,
            b_evaluated_count=0,
            excluded_preflight_count=0,
            current_score_source=None,
        )
        _aggregate_ab_summary(
            summary_out=_summary(pairs=same_pair, b_evaluated=1),
            all_ab_score_pairs=pairs,
            b_evaluated_count=1,
            excluded_preflight_count=0,
            current_score_source=PHASE1_SOURCE,
        )
        assert pairs == [(0.5, 1.0), (0.5, 1.0)]


# ---------------------------------------------------------------------------
# Test 17: all-inactive run (= 全 lane noop) (Codex Round 2 [Suggestion] 3)
# ---------------------------------------------------------------------------


class TestAllInactiveRunObservability:
    """test 17: 全 lane が state != "active" (= noop summary) で
    ab_score_source = None (= "noop" log)、 n_pairs=0 → status='insufficient_data'."""

    def test_17_all_inactive_run_returns_insufficient_data(self) -> None:
        """全 lane noop で集約結果が空 list / source=None / n_pairs=0."""
        pairs: list[tuple[float, float]] = []
        b_eval, excluded, source = _aggregate_ab_summary(
            summary_out=_summary(pairs=[], source="noop", b_evaluated=0),
            all_ab_score_pairs=pairs,
            b_evaluated_count=0,
            excluded_preflight_count=0,
            current_score_source=None,
        )
        assert pairs == []
        assert b_eval == 0
        assert excluded == 0
        assert source is None  # noop は source 確定させない

        # compute_ab_divergence は insufficient_data
        a_scores = [Decimal(repr(a)) for a, _ in pairs]
        b_scores = [Decimal(repr(b)) for _, b in pairs]
        result = compute_ab_divergence_on_b_evaluated(a_scores, b_scores)
        assert result.status == "insufficient_data"
        assert result.n_pairs == 0
        # log 経路で source は "noop" として記録される (= run_ga.py side、
        # ここでは helper の戻り source=None だが、 caller が `source or "noop"` で log 出力)
        assert (source or "noop") == "noop"

    def test_min_actionable_threshold_constant(self) -> None:
        """AB_MIN_ACTIONABLE_PAIRS=10 が status 切替境界 (= n=9 で insufficient、 n=10 で ok)."""
        assert AB_MIN_ACTIONABLE_PAIRS == 10
