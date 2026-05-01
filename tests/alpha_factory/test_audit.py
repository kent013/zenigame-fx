"""T073 audit layer (DSR + PBO/SPA scaffold + AuditNullModel SSOT +
stratification API guard) tests.

詳細設計 § 5 + DoD § 9.

命名規約 (詳細設計 § 5.0): Fxxx_<behavior> 形式で pytest 関数名と 1:1 対応.
"""

from __future__ import annotations

import logging
import math
from collections.abc import Sequence
from dataclasses import fields
from datetime import date
from decimal import Decimal

import pytest

from src.alpha_factory.audit import (
    AUDIT_DSR_CALC_VERSION,
    AUDIT_DSR_MIN_OBSERVATIONS,
    AUDIT_DSR_MIN_TRIALS,
    AUDIT_REPORT_SCHEMA_VERSION,
    AUDIT_SCAFFOLD_CALC_VERSION,
    DSR_VALUE_SENTINEL,
    MOMENT_SENTINEL,
    TRIAL_COUNTING_POLICY_VERSION,
    AuditDSRMetric,
    AuditDSRStatus,
    AuditGenomeRecord,
    AuditNullModel,
    AuditPBOMetric,
    AuditScaffoldStatus,
    AuditSPAMetric,
    GenomeAuditInput,
    RunAuditReport,
    _make_sentinel_metric,
    check_audit_record_schema_version,
    compute_audit_dsr_for_genome,
    compute_audit_pbo_scaffold,
    compute_audit_spa_scaffold,
    compute_dsr_strata_with_allowlist,
    compute_marginal_dsr_strata,
    compute_run_audit_report,
)
from src.alpha_factory.statistics import deflated_sharpe_ratio
from src.backtest.calendar import ObservabilityFlags
from src.backtest.session_block import SessionBlock

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_null_model(
    *,
    n_trials: int = 10,
    raw: int | None = None,
    raw_count_status: str = "measured",
) -> AuditNullModel:
    """test 用 AuditNullModel factory (= Phase 1 SSOT 値で固定)."""
    raw_value = n_trials if raw is None else raw
    return AuditNullModel(
        null_model_kind="standard_normal",
        sr_scale="session_block_non_annualized",
        mean_sr_trials=Decimal(0),
        std_sr_trials=Decimal(1),
        trial_source="run_evaluated_genomes_unique_canonical",
        trial_counting_policy_version=TRIAL_COUNTING_POLICY_VERSION,
        n_trials=n_trials,
        n_trial_candidates_raw=raw_value,
        n_trial_candidates_unique=n_trials,
        raw_count_status=raw_count_status,  # type: ignore[arg-type]
    )


def _make_block(
    *,
    pnl_net: Decimal,
    business_date: date | None = None,
    bucket: str = "tokyo",
    open_minutes: int = 480,
    holiday: frozenset[str] = frozenset(),
    bar_count: int = 480,
) -> SessionBlock:
    """test 用 SessionBlock factory.

    pnl_before_costs = pnl_net (= spread/holding 0) で会計契約 SSOT 不変条件を満たす.
    """
    return SessionBlock(
        business_date=business_date or date(2026, 1, 5),
        bucket=bucket,  # type: ignore[arg-type]
        bar_count=bar_count,
        trade_count=1,
        pnl_net=pnl_net,
        pnl_before_costs=pnl_net,
        spread_cost_total=Decimal(0),
        holding_cost_total=Decimal(0),
        open_minutes=open_minutes,
        granularity_seconds=60,
        observability_flags=ObservabilityFlags(
            dst_transition_markets=frozenset(),
            holiday_markets=holiday,  # type: ignore[arg-type]
        ),
    )


def _generate_pnl_blocks(
    pnls: Sequence[float], *, open_minutes: int = 480
) -> list[SessionBlock]:
    """deterministic な日付 sequence で SessionBlock list を作る."""
    blocks: list[SessionBlock] = []
    base = date(2026, 1, 5)
    for i, raw in enumerate(pnls):
        d = date.fromordinal(base.toordinal() + i // 3)
        bucket = ("tokyo", "london", "ny")[i % 3]
        blocks.append(
            _make_block(
                pnl_net=Decimal(str(raw)),
                business_date=d,
                bucket=bucket,
                open_minutes=open_minutes,
            )
        )
    return blocks


# ---------------------------------------------------------------------------
# F1-F4: 定数 / Literal tests
# ---------------------------------------------------------------------------


def test_audit_constants_match_ssot() -> None:
    """F1: 定数 SSOT 値 (詳細設計 § 3.1)."""
    assert AUDIT_DSR_MIN_OBSERVATIONS == 30
    assert AUDIT_DSR_MIN_TRIALS == 2
    assert AUDIT_REPORT_SCHEMA_VERSION == "1.0.0"
    assert AUDIT_DSR_CALC_VERSION == "v2"
    assert AUDIT_SCAFFOLD_CALC_VERSION == "scaffold-v1"
    assert TRIAL_COUNTING_POLICY_VERSION == "canonical-genome-v1"
    assert Decimal("-1") == DSR_VALUE_SENTINEL
    assert Decimal("0") == MOMENT_SENTINEL


def test_audit_dsr_status_excludes_not_implemented() -> None:
    """F2: AuditDSRStatus は 5 値で not_implemented を含まない."""
    expected = {
        "ok",
        "insufficient_data",
        "insufficient_trials",
        "degenerate_variance",
        "input_non_finite",
    }
    # typing.get_args は Python 3.11+ で Literal の値を取得.
    from typing import get_args

    assert set(get_args(AuditDSRStatus)) == expected
    assert "not_implemented" not in expected


def test_audit_scaffold_status_only_not_implemented() -> None:
    """F3: AuditScaffoldStatus は not_implemented 1 値."""
    from typing import get_args

    assert set(get_args(AuditScaffoldStatus)) == {"not_implemented"}


def test_audit_null_model_kind_phase1_standard_normal_only() -> None:
    """F4: AuditNullModelKind Phase 1 = standard_normal のみ."""
    from typing import get_args

    from src.alpha_factory.audit import AuditNullModelKind

    assert set(get_args(AuditNullModelKind)) == {"standard_normal"}


# ---------------------------------------------------------------------------
# F5-F12: AuditNullModel tests
# ---------------------------------------------------------------------------


def test_null_model_invariant_order_priority() -> None:
    """F5: invariant 順序 (= I-1 が I-2 / I-4 より先に raise)."""
    # null_model_kind="standard_normal" + mean=1 (I-1 violate)
    # かつ sr_scale="annualized" (I-2 violate)
    # → I-1 が先に raise
    with pytest.raises(ValueError, match="standard_normal null requires mean"):
        AuditNullModel(
            null_model_kind="standard_normal",
            sr_scale="annualized",  # type: ignore[arg-type]
            mean_sr_trials=Decimal(1),
            std_sr_trials=Decimal(1),
            trial_source="run_evaluated_genomes_unique_canonical",
            trial_counting_policy_version=TRIAL_COUNTING_POLICY_VERSION,
            n_trials=5,
            n_trial_candidates_raw=5,
            n_trial_candidates_unique=5,
            raw_count_status="measured",
        )


def test_null_model_standard_normal_requires_mean_zero() -> None:
    """F5b: standard_normal + mean=1 → ValueError."""
    with pytest.raises(ValueError, match="mean_sr_trials == 0"):
        AuditNullModel(
            null_model_kind="standard_normal",
            sr_scale="session_block_non_annualized",
            mean_sr_trials=Decimal(1),
            std_sr_trials=Decimal(1),
            trial_source="run_evaluated_genomes_unique_canonical",
            trial_counting_policy_version=TRIAL_COUNTING_POLICY_VERSION,
            n_trials=5,
            n_trial_candidates_raw=5,
            n_trial_candidates_unique=5,
            raw_count_status="measured",
        )


def test_null_model_standard_normal_requires_std_one() -> None:
    """F6: standard_normal + std=2 → ValueError."""
    with pytest.raises(ValueError, match="std_sr_trials == 1"):
        AuditNullModel(
            null_model_kind="standard_normal",
            sr_scale="session_block_non_annualized",
            mean_sr_trials=Decimal(0),
            std_sr_trials=Decimal(2),
            trial_source="run_evaluated_genomes_unique_canonical",
            trial_counting_policy_version=TRIAL_COUNTING_POLICY_VERSION,
            n_trials=5,
            n_trial_candidates_raw=5,
            n_trial_candidates_unique=5,
            raw_count_status="measured",
        )


def test_null_model_sr_scale_phase1_invariant() -> None:
    """F7: sr_scale="annualized" → ValueError (Phase 1 SSOT 違反)."""
    with pytest.raises(ValueError, match="sr_scale must be"):
        AuditNullModel(
            null_model_kind="standard_normal",
            sr_scale="annualized",  # type: ignore[arg-type]
            mean_sr_trials=Decimal(0),
            std_sr_trials=Decimal(1),
            trial_source="run_evaluated_genomes_unique_canonical",
            trial_counting_policy_version=TRIAL_COUNTING_POLICY_VERSION,
            n_trials=5,
            n_trial_candidates_raw=5,
            n_trial_candidates_unique=5,
            raw_count_status="measured",
        )


def test_null_model_trial_source_invariant() -> None:
    """F8: trial_source="archive_cardinality" → ValueError."""
    with pytest.raises(ValueError, match="trial_source must be"):
        AuditNullModel(
            null_model_kind="standard_normal",
            sr_scale="session_block_non_annualized",
            mean_sr_trials=Decimal(0),
            std_sr_trials=Decimal(1),
            trial_source="archive_cardinality",  # type: ignore[arg-type]
            trial_counting_policy_version=TRIAL_COUNTING_POLICY_VERSION,
            n_trials=5,
            n_trial_candidates_raw=5,
            n_trial_candidates_unique=5,
            raw_count_status="measured",
        )


def test_null_model_trial_counting_policy_version_invariant() -> None:
    """F9: trial_counting_policy_version="canonical-genome-v2" → ValueError."""
    with pytest.raises(ValueError, match="trial_counting_policy_version"):
        AuditNullModel(
            null_model_kind="standard_normal",
            sr_scale="session_block_non_annualized",
            mean_sr_trials=Decimal(0),
            std_sr_trials=Decimal(1),
            trial_source="run_evaluated_genomes_unique_canonical",
            trial_counting_policy_version="canonical-genome-v2",
            n_trials=5,
            n_trial_candidates_raw=5,
            n_trial_candidates_unique=5,
            raw_count_status="measured",
        )


def test_null_model_n_trials_equals_unique() -> None:
    """F10: n_trials != n_trial_candidates_unique → ValueError."""
    with pytest.raises(ValueError, match="must equal n_trial_candidates_unique"):
        AuditNullModel(
            null_model_kind="standard_normal",
            sr_scale="session_block_non_annualized",
            mean_sr_trials=Decimal(0),
            std_sr_trials=Decimal(1),
            trial_source="run_evaluated_genomes_unique_canonical",
            trial_counting_policy_version=TRIAL_COUNTING_POLICY_VERSION,
            n_trials=5,
            n_trial_candidates_raw=10,
            n_trial_candidates_unique=6,
            raw_count_status="measured",
        )


def test_null_model_raw_count_measured_lower_bound() -> None:
    """F11: raw_count_status="measured" + raw < unique → ValueError."""
    with pytest.raises(ValueError, match="raw_count_status='measured'"):
        AuditNullModel(
            null_model_kind="standard_normal",
            sr_scale="session_block_non_annualized",
            mean_sr_trials=Decimal(0),
            std_sr_trials=Decimal(1),
            trial_source="run_evaluated_genomes_unique_canonical",
            trial_counting_policy_version=TRIAL_COUNTING_POLICY_VERSION,
            n_trials=5,
            n_trial_candidates_raw=3,
            n_trial_candidates_unique=5,
            raw_count_status="measured",
        )


def test_null_model_raw_count_unknown_conservative() -> None:
    """F12: raw_count_status="unknown" + raw != unique → ValueError、 raw==unique → pass."""
    # raw != unique → raise
    with pytest.raises(ValueError, match="raw_count_status='unknown'"):
        AuditNullModel(
            null_model_kind="standard_normal",
            sr_scale="session_block_non_annualized",
            mean_sr_trials=Decimal(0),
            std_sr_trials=Decimal(1),
            trial_source="run_evaluated_genomes_unique_canonical",
            trial_counting_policy_version=TRIAL_COUNTING_POLICY_VERSION,
            n_trials=5,
            n_trial_candidates_raw=10,
            n_trial_candidates_unique=5,
            raw_count_status="unknown",
        )
    # raw == unique → pass
    null = AuditNullModel(
        null_model_kind="standard_normal",
        sr_scale="session_block_non_annualized",
        mean_sr_trials=Decimal(0),
        std_sr_trials=Decimal(1),
        trial_source="run_evaluated_genomes_unique_canonical",
        trial_counting_policy_version=TRIAL_COUNTING_POLICY_VERSION,
        n_trials=5,
        n_trial_candidates_raw=5,
        n_trial_candidates_unique=5,
        raw_count_status="unknown",
    )
    assert null.n_trial_candidates_raw == 5


# ---------------------------------------------------------------------------
# F13-F22: AuditDSRMetric tests
# ---------------------------------------------------------------------------


def test_audit_dsr_metric_ok_dsr_in_zero_one_range() -> None:
    """F13: status="ok" + dsr_value=1.5 → ValueError."""
    null = _make_null_model()
    with pytest.raises(ValueError, match="dsr_value in"):
        AuditDSRMetric(
            status="ok",
            dsr_value=Decimal("1.5"),
            n_observations=100,
            sharpe_ratio=Decimal("0.5"),
            skew=Decimal("0.0"),
            kurtosis=Decimal("3.0"),
            null_model=null,
            audit_calc_version=AUDIT_DSR_CALC_VERSION,
        )


def test_audit_dsr_metric_ok_requires_finite_moments() -> None:
    """F14: status="ok" + sharpe=NaN → ValueError."""
    null = _make_null_model()
    with pytest.raises(ValueError, match="sharpe_ratio finite"):
        AuditDSRMetric(
            status="ok",
            dsr_value=Decimal("0.5"),
            n_observations=100,
            sharpe_ratio=Decimal("NaN"),
            skew=Decimal("0.0"),
            kurtosis=Decimal("3.0"),
            null_model=null,
            audit_calc_version=AUDIT_DSR_CALC_VERSION,
        )


def test_audit_dsr_metric_status_non_ok_dsr_sentinel() -> None:
    """F15: status="insufficient_data" + dsr_value=0.5 → ValueError (sentinel 違反)."""
    null = _make_null_model()
    with pytest.raises(ValueError, match="DSR_VALUE_SENTINEL"):
        AuditDSRMetric(
            status="insufficient_data",
            dsr_value=Decimal("0.5"),
            n_observations=10,
            sharpe_ratio=MOMENT_SENTINEL,
            skew=MOMENT_SENTINEL,
            kurtosis=MOMENT_SENTINEL,
            null_model=null,
            audit_calc_version=AUDIT_DSR_CALC_VERSION,
        )


def test_audit_dsr_metric_status_non_ok_moment_sentinel() -> None:
    """F16: status="insufficient_data" + sharpe=0.1 → ValueError (sentinel 違反)."""
    null = _make_null_model()
    with pytest.raises(ValueError, match="sharpe_ratio == MOMENT_SENTINEL"):
        AuditDSRMetric(
            status="insufficient_data",
            dsr_value=DSR_VALUE_SENTINEL,
            n_observations=10,
            sharpe_ratio=Decimal("0.1"),
            skew=MOMENT_SENTINEL,
            kurtosis=MOMENT_SENTINEL,
            null_model=null,
            audit_calc_version=AUDIT_DSR_CALC_VERSION,
        )


def test_audit_dsr_metric_calc_version_invariant() -> None:
    """F17: audit_calc_version="v1" → ValueError."""
    null = _make_null_model()
    with pytest.raises(ValueError, match="audit_calc_version"):
        AuditDSRMetric(
            status="ok",
            dsr_value=Decimal("0.5"),
            n_observations=100,
            sharpe_ratio=Decimal("0.5"),
            skew=Decimal("0.0"),
            kurtosis=Decimal("3.0"),
            null_model=null,
            audit_calc_version="v1",
        )


def test_audit_dsr_metric_n_observations_non_negative() -> None:
    """F18: n_observations=-1 → ValueError."""
    null = _make_null_model()
    with pytest.raises(ValueError, match="n_observations must be >= 0"):
        AuditDSRMetric(
            status="ok",
            dsr_value=Decimal("0.5"),
            n_observations=-1,
            sharpe_ratio=Decimal("0.5"),
            skew=Decimal("0.0"),
            kurtosis=Decimal("3.0"),
            null_model=null,
            audit_calc_version=AUDIT_DSR_CALC_VERSION,
        )


def test_audit_dsr_metric_unknown_status_raises() -> None:
    """F19: unknown status → ValueError."""
    null = _make_null_model()
    with pytest.raises(ValueError, match="unknown AuditDSRStatus"):
        AuditDSRMetric(
            status="bad_status",  # type: ignore[arg-type]
            dsr_value=DSR_VALUE_SENTINEL,
            n_observations=10,
            sharpe_ratio=MOMENT_SENTINEL,
            skew=MOMENT_SENTINEL,
            kurtosis=MOMENT_SENTINEL,
            null_model=null,
            audit_calc_version=AUDIT_DSR_CALC_VERSION,
        )


def test_audit_dsr_metric_rejects_not_implemented_status() -> None:
    """F19b: AuditDSRMetric(status="not_implemented", ...) → ValueError (Round D1 [W2])."""
    null = _make_null_model()
    with pytest.raises(ValueError, match="unknown AuditDSRStatus"):
        AuditDSRMetric(
            status="not_implemented",  # type: ignore[arg-type]
            dsr_value=DSR_VALUE_SENTINEL,
            n_observations=10,
            sharpe_ratio=MOMENT_SENTINEL,
            skew=MOMENT_SENTINEL,
            kurtosis=MOMENT_SENTINEL,
            null_model=null,
            audit_calc_version=AUDIT_DSR_CALC_VERSION,
        )


def test_make_sentinel_metric_rejects_ok_status() -> None:
    """F19c: _make_sentinel_metric(status="ok", ...) → ValueError (Round D1 [W2])."""
    null = _make_null_model()
    with pytest.raises(ValueError, match="must be one of"):
        _make_sentinel_metric(
            status="ok",  # type: ignore[arg-type]
            null_model=null,
            n_observations=10,
        )


def test_make_sentinel_metric_requires_keyword_args() -> None:
    """F19d: _make_sentinel_metric を位置引数で呼出 → TypeError (Round D1 [C1])."""
    null = _make_null_model()
    with pytest.raises(TypeError):
        _make_sentinel_metric("insufficient_data", null, 10)  # type: ignore[misc]


def test_compute_audit_dsr_for_genome_happy_path() -> None:
    """F20: n=100、 deterministic returns、 status="ok"、 dsr_value ∈ [0, 1]."""
    null = _make_null_model(n_trials=10)
    # 100 個の deterministic な戻り (= cos / sin で variance を作る)
    pnls = [math.cos(i * 0.1) * 0.01 + 0.001 for i in range(100)]
    blocks = _generate_pnl_blocks(pnls)
    metric = compute_audit_dsr_for_genome(blocks, null_model=null)
    assert metric.status == "ok"
    assert Decimal(0) <= metric.dsr_value <= Decimal(1)
    assert metric.n_observations == 100
    assert math.isfinite(float(metric.sharpe_ratio))


def test_compute_audit_dsr_for_genome_insufficient_trials() -> None:
    """F21: n_trials=1 → status="insufficient_trials"."""
    null = _make_null_model(n_trials=1)
    pnls = [math.cos(i * 0.1) * 0.01 + 0.001 for i in range(100)]
    blocks = _generate_pnl_blocks(pnls)
    metric = compute_audit_dsr_for_genome(blocks, null_model=null)
    assert metric.status == "insufficient_trials"
    assert metric.dsr_value == DSR_VALUE_SENTINEL
    assert metric.sharpe_ratio == MOMENT_SENTINEL


def test_compute_audit_dsr_insufficient_trials_preserves_n_observations() -> None:
    """F21b: insufficient_trials 時に n_observations は filter 後の実測値 (Round D1 [C2])."""
    null = _make_null_model(n_trials=1)
    blocks = _generate_pnl_blocks([0.001] * 5)
    metric = compute_audit_dsr_for_genome(blocks, null_model=null)
    assert metric.status == "insufficient_trials"
    assert metric.n_observations == 5  # 0 固定でない


def test_compute_audit_dsr_for_genome_insufficient_data() -> None:
    """F22: open_minutes>0 が 5 個のみ → status="insufficient_data"."""
    null = _make_null_model(n_trials=10)
    blocks = _generate_pnl_blocks([0.001 * (i + 1) for i in range(5)])
    metric = compute_audit_dsr_for_genome(blocks, null_model=null)
    assert metric.status == "insufficient_data"
    assert metric.n_observations == 5


def test_compute_audit_dsr_for_genome_degenerate_variance() -> None:
    """F22b: 全 pnl_net=0 → status="degenerate_variance"."""
    null = _make_null_model(n_trials=10)
    blocks = _generate_pnl_blocks([0.0] * 100)
    metric = compute_audit_dsr_for_genome(blocks, null_model=null)
    assert metric.status == "degenerate_variance"
    assert metric.dsr_value == DSR_VALUE_SENTINEL


def test_compute_audit_dsr_for_genome_input_non_finite() -> None:
    """F22c: pnl_net に Infinity → status="input_non_finite".

    NaN は SessionBlock の pnl_before_costs == pnl_net + ... invariant を
    満たせない (= NaN != NaN) ため、 Decimal Infinity で finite check failure
    経路を発動させる.
    """
    null = _make_null_model(n_trials=10)
    pnls = [math.cos(i * 0.1) * 0.01 + 0.001 for i in range(100)]
    blocks = _generate_pnl_blocks(pnls)
    # 1 block を Infinity で置換 (= pnl_before_costs invariant も満たす)
    inf_block = SessionBlock(
        business_date=blocks[0].business_date,
        bucket=blocks[0].bucket,
        bar_count=480,
        trade_count=1,
        pnl_net=Decimal("Infinity"),
        pnl_before_costs=Decimal("Infinity"),
        spread_cost_total=Decimal(0),
        holding_cost_total=Decimal(0),
        open_minutes=480,
        granularity_seconds=60,
        observability_flags=ObservabilityFlags(
            dst_transition_markets=frozenset(),
            holiday_markets=frozenset(),
        ),
    )
    blocks[0] = inf_block
    metric = compute_audit_dsr_for_genome(blocks, null_model=null)
    assert metric.status == "input_non_finite"
    assert metric.dsr_value == DSR_VALUE_SENTINEL


def test_compute_audit_dsr_includes_holiday_blocks_for_collider_bias_avoidance() -> None:
    """F22d: holiday_markets だけで block を drop しない (T072 collider bias 規範継承)."""
    null = _make_null_model(n_trials=10)
    pnls = [math.cos(i * 0.1) * 0.01 + 0.001 for i in range(100)]
    blocks = _generate_pnl_blocks(pnls)
    # 半分の block に Tokyo holiday flag を付ける (= open_minutes>0 を維持)
    blocks[:50] = [
        SessionBlock(
            business_date=b.business_date,
            bucket=b.bucket,
            bar_count=b.bar_count,
            trade_count=b.trade_count,
            pnl_net=b.pnl_net,
            pnl_before_costs=b.pnl_before_costs,
            spread_cost_total=b.spread_cost_total,
            holding_cost_total=b.holding_cost_total,
            open_minutes=b.open_minutes,
            granularity_seconds=b.granularity_seconds,
            observability_flags=ObservabilityFlags(
                dst_transition_markets=frozenset(),
                holiday_markets=frozenset({"tokyo"}),
            ),
        )
        for b in blocks[:50]
    ]
    metric = compute_audit_dsr_for_genome(blocks, null_model=null)
    assert metric.n_observations == 100  # holiday flag block も含む


# ---------------------------------------------------------------------------
# F23-F26: PBO/SPA scaffold tests
# ---------------------------------------------------------------------------


def test_compute_audit_pbo_scaffold_factory() -> None:
    """F23: factory 出力 status="not_implemented"、 audit_calc_version="scaffold-v1"."""
    pbo = compute_audit_pbo_scaffold()
    assert pbo.status == "not_implemented"
    assert pbo.audit_calc_version == "scaffold-v1"


def test_audit_pbo_metric_has_no_numeric_fields() -> None:
    """F24: AuditPBOMetric の field 列に pbo_value 等の数値 field なし."""
    field_names = {f.name for f in fields(AuditPBOMetric)}
    assert field_names == {"status", "audit_calc_version"}


def test_compute_audit_spa_scaffold_factory() -> None:
    """F25: 同 (SPA)."""
    spa = compute_audit_spa_scaffold()
    assert spa.status == "not_implemented"
    assert spa.audit_calc_version == "scaffold-v1"
    field_names = {f.name for f in fields(AuditSPAMetric)}
    assert field_names == {"status", "audit_calc_version"}


def test_audit_scaffold_does_not_raise() -> None:
    """F26: scaffold 関数は NotImplementedError raise しない."""
    # 例外を raise しない (= status return SSOT)
    pbo = compute_audit_pbo_scaffold()
    spa = compute_audit_spa_scaffold()
    assert pbo.status == "not_implemented"
    assert spa.status == "not_implemented"


def test_audit_pbo_metric_rejects_other_status() -> None:
    """scaffold dataclass: status != "not_implemented" → ValueError."""
    with pytest.raises(ValueError, match="not_implemented"):
        AuditPBOMetric(
            status="ok",  # type: ignore[arg-type]
            audit_calc_version=AUDIT_SCAFFOLD_CALC_VERSION,
        )


def test_audit_pbo_metric_rejects_wrong_calc_version() -> None:
    with pytest.raises(ValueError, match="audit_calc_version"):
        AuditPBOMetric(status="not_implemented", audit_calc_version="v2")


def test_audit_spa_metric_rejects_other_status() -> None:
    with pytest.raises(ValueError, match="not_implemented"):
        AuditSPAMetric(
            status="ok",  # type: ignore[arg-type]
            audit_calc_version=AUDIT_SCAFFOLD_CALC_VERSION,
        )


def test_audit_spa_metric_rejects_wrong_calc_version() -> None:
    with pytest.raises(ValueError, match="audit_calc_version"):
        AuditSPAMetric(status="not_implemented", audit_calc_version="v2")


# ---------------------------------------------------------------------------
# F27-F30: AuditGenomeRecord / GenomeAuditInput / RunAuditReport tests
# ---------------------------------------------------------------------------


def test_audit_genome_record_id_non_empty() -> None:
    """F27: genome_id="" → ValueError."""
    null = _make_null_model()
    metric = _make_sentinel_metric(
        status="insufficient_data", null_model=null, n_observations=0
    )
    with pytest.raises(ValueError, match="genome_id"):
        AuditGenomeRecord(
            genome_id="",
            archive_role="winner",
            source_stage="stage_c",
            dsr_metric=metric,
        )


def test_run_audit_report_schema_version_invariant() -> None:
    """F28: audit_report_schema_version="9.9.9" → ValueError."""
    null = _make_null_model()
    metric = _make_sentinel_metric(
        status="insufficient_data", null_model=null, n_observations=0
    )
    record = AuditGenomeRecord(
        genome_id="g1",
        archive_role="winner",
        source_stage="stage_c",
        dsr_metric=metric,
    )
    with pytest.raises(ValueError, match="audit_report_schema_version"):
        RunAuditReport(
            run_id="run-1",
            dataset_epoch_id="ep-1",
            n_genomes=1,
            per_genome=(record,),
            pbo=compute_audit_pbo_scaffold(),
            spa=compute_audit_spa_scaffold(),
            audit_report_schema_version="9.9.9",
        )


def test_run_audit_report_n_genomes_match() -> None:
    """F29: len(per_genome) != n_genomes → ValueError."""
    null = _make_null_model()
    metric = _make_sentinel_metric(
        status="insufficient_data", null_model=null, n_observations=0
    )
    record = AuditGenomeRecord(
        genome_id="g1",
        archive_role="winner",
        source_stage="stage_c",
        dsr_metric=metric,
    )
    with pytest.raises(ValueError, match="n_genomes"):
        RunAuditReport(
            run_id="run-1",
            dataset_epoch_id="ep-1",
            n_genomes=2,
            per_genome=(record,),
            pbo=compute_audit_pbo_scaffold(),
            spa=compute_audit_spa_scaffold(),
            audit_report_schema_version=AUDIT_REPORT_SCHEMA_VERSION,
        )


def test_run_audit_report_uniform_null_model_invariant() -> None:
    """F30: per_genome[0].null_model != per_genome[1].null_model → ValueError."""
    null_a = _make_null_model(n_trials=10)
    null_b = _make_null_model(n_trials=20)
    metric_a = _make_sentinel_metric(
        status="insufficient_data", null_model=null_a, n_observations=0
    )
    metric_b = _make_sentinel_metric(
        status="insufficient_data", null_model=null_b, n_observations=0
    )
    rec_a = AuditGenomeRecord(
        genome_id="g1",
        archive_role="winner",
        source_stage="stage_c",
        dsr_metric=metric_a,
    )
    rec_b = AuditGenomeRecord(
        genome_id="g2",
        archive_role="winner",
        source_stage="stage_c",
        dsr_metric=metric_b,
    )
    with pytest.raises(ValueError, match="null_model differs"):
        RunAuditReport(
            run_id="run-1",
            dataset_epoch_id="ep-1",
            n_genomes=2,
            per_genome=(rec_a, rec_b),
            pbo=compute_audit_pbo_scaffold(),
            spa=compute_audit_spa_scaffold(),
            audit_report_schema_version=AUDIT_REPORT_SCHEMA_VERSION,
        )


def test_run_audit_report_pbo_calc_version_invariant() -> None:
    """RunAuditReport.pbo.audit_calc_version != scaffold-v1 は AuditPBOMetric の
    __post_init__ で先に reject されるため、 RunAuditReport 自体の guard は
    scaffold dataclass の __post_init__ がない場合にのみ発火する仕掛け。
    ここでは scaffold dataclass 経由で reject されることを確認."""
    with pytest.raises(ValueError, match="audit_calc_version"):
        AuditPBOMetric(status="not_implemented", audit_calc_version="bad")


def test_compute_run_audit_report_happy_path() -> None:
    """compute_run_audit_report happy path (= 2 genome、 deterministic order)."""
    null = _make_null_model(n_trials=10)
    pnls = [math.cos(i * 0.1) * 0.01 + 0.001 for i in range(100)]
    blocks = _generate_pnl_blocks(pnls)
    inputs = {
        "g2": GenomeAuditInput(
            genome_id="g2",
            archive_role="winner",
            source_stage="stage_c",
            session_blocks=blocks,
        ),
        "g1": GenomeAuditInput(
            genome_id="g1",
            archive_role="winner",
            source_stage="stage_c",
            session_blocks=blocks,
        ),
    }
    report = compute_run_audit_report(
        run_id="run-1",
        dataset_epoch_id="ep-1",
        per_genome=inputs,
        null_model=null,
    )
    assert report.n_genomes == 2
    # deterministic str sort: g1 < g2
    assert report.per_genome[0].genome_id == "g1"
    assert report.per_genome[1].genome_id == "g2"
    assert report.pbo.status == "not_implemented"
    assert report.spa.status == "not_implemented"


# ---------------------------------------------------------------------------
# F31-F35: canonical genome dedup tests (Round 3 [W2])
#
# 注: F31-F35 は caller (= GA runner) 側 dedup の SSOT を mock で検証.
# T073 の AuditNullModel は受け取った n_trials / raw / unique を invariant 検証
# するのみ.
# ---------------------------------------------------------------------------


def test_canonical_genome_dedup_retry_counted_once() -> None:
    """F31: 同 canonical genome_id の retry を raw=2 / unique=1 で dedup."""
    # 同一 genome を 2 回 evaluation attempt (= retry)、 caller dedup 後の SSOT
    null = _make_null_model(
        n_trials=1, raw=2, raw_count_status="measured"
    )
    # n_trials=1 でも n_trial_candidates_unique=1 必要
    # invariant: n_trials == unique
    assert null.n_trial_candidates_raw == 2
    assert null.n_trial_candidates_unique == 1
    assert null.n_trials == 1


def test_canonical_genome_dedup_cache_hit_excluded_from_raw_and_unique() -> None:
    """F32: cache hit は raw にも含めない (Round D1 [W4]).

    SSOT: 一度評価済 genome の cache replay は raw=1 / unique=1.
    caller dedup の SSOT を invariant で固定.
    """
    null = _make_null_model(n_trials=1, raw=1, raw_count_status="measured")
    assert null.n_trial_candidates_raw == 1
    assert null.n_trial_candidates_unique == 1


def test_canonical_genome_dedup_fold_evaluation_counts_raw() -> None:
    """F33: 同 canonical genome_id の fold 別評価は unique=1 / raw=fold 数."""
    null = _make_null_model(n_trials=1, raw=5, raw_count_status="measured")
    assert null.n_trial_candidates_raw == 5
    assert null.n_trial_candidates_unique == 1
    assert null.n_trials == 1


def test_canonical_genome_dedup_seed_variation_unique() -> None:
    """F34: 同 canonical genome_id (= seed 違いだが genome hash 同) を unique=1."""
    null = _make_null_model(n_trials=1, raw=3, raw_count_status="measured")
    assert null.n_trial_candidates_unique == 1


def test_canonical_genome_dedup_distinct_canonical_ids() -> None:
    """F35: 異 canonical genome_id (= 異 hash) を unique=2."""
    null = _make_null_model(n_trials=2, raw=2, raw_count_status="measured")
    assert null.n_trial_candidates_unique == 2
    assert null.n_trials == 2


# ---------------------------------------------------------------------------
# F36-F38: schema_version helper tests
# ---------------------------------------------------------------------------


def test_check_audit_record_schema_version_match() -> None:
    """F36: 一致 → 正常 (= log emit なし)."""
    # 例外なし
    check_audit_record_schema_version("1.0.0")


def test_check_audit_record_schema_version_minor_newer_warns(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """F37: 受信 record が consumer より新しい (= 1.1.0 vs expected 1.0.0) → warning."""
    with caplog.at_level(logging.WARNING, logger="src.alpha_factory.audit"):
        check_audit_record_schema_version("1.1.0")
    assert any("record newer" in r.message for r in caplog.records)


def test_check_audit_record_schema_version_minor_older_when_major_differs_raises() -> None:
    """F37b: expected="1.0.0" で received="0.5.0" → ValueError MAJOR mismatch (Round D1 [W3])."""
    with pytest.raises(ValueError, match="MAJOR mismatch"):
        check_audit_record_schema_version("0.5.0")


def test_check_audit_record_schema_version_minor_older_same_major_warns(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """F37c: expected="1.5.0" / received="1.0.0" → warning (= record older)、 raise しない."""
    with caplog.at_level(logging.WARNING, logger="src.alpha_factory.audit"):
        check_audit_record_schema_version("1.0.0", expected="1.5.0")
    assert any("record older" in r.message for r in caplog.records)


def test_check_audit_record_schema_version_major_mismatch_raises() -> None:
    """F38: MAJOR mismatch → ValueError."""
    with pytest.raises(ValueError, match="MAJOR mismatch"):
        check_audit_record_schema_version("2.0.0")


def test_check_audit_record_schema_version_invalid_format_raises() -> None:
    """F38b: "1" / "1.a" / "1.0.0.1" / "" → ValueError."""
    for bad in ["1", "1.a", "1.0.0.1", ""]:
        with pytest.raises(ValueError):
            check_audit_record_schema_version(bad)


def test_check_audit_record_schema_version_patch_diff_silent(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """PATCH 差 (= 1.0.5 vs 1.0.0) は silent (= warning emit なし)."""
    with caplog.at_level(logging.WARNING, logger="src.alpha_factory.audit"):
        check_audit_record_schema_version("1.0.5")
    assert not caplog.records


# ---------------------------------------------------------------------------
# F39-F40: stratification API tests
# ---------------------------------------------------------------------------


def _make_record_with_genome_id(
    genome_id: str, *, null_model: AuditNullModel
) -> AuditGenomeRecord:
    metric = _make_sentinel_metric(
        status="insufficient_data", null_model=null_model, n_observations=0
    )
    return AuditGenomeRecord(
        genome_id=genome_id,
        archive_role="winner",
        source_stage="stage_c",
        dsr_metric=metric,
    )


def test_compute_marginal_dsr_strata_no_interaction() -> None:
    """F39: marginal 集計のみ、 interaction 計算しない."""
    null = _make_null_model(n_trials=2)
    rec_a = _make_record_with_genome_id("g1", null_model=null)
    rec_b = _make_record_with_genome_id("g2", null_model=null)
    report = RunAuditReport(
        run_id="run-1",
        dataset_epoch_id="ep-1",
        n_genomes=2,
        per_genome=(rec_a, rec_b),
        pbo=compute_audit_pbo_scaffold(),
        spa=compute_audit_spa_scaffold(),
        audit_report_schema_version=AUDIT_REPORT_SCHEMA_VERSION,
    )
    flag_lookup = {
        "g1": ObservabilityFlags(
            dst_transition_markets=frozenset(),
            holiday_markets=frozenset({"tokyo"}),
        ),
        "g2": ObservabilityFlags(
            dst_transition_markets=frozenset({"london"}),
            holiday_markets=frozenset(),
        ),
    }
    strata = compute_marginal_dsr_strata(report, flag_lookup=flag_lookup)
    # marginal 軸のみ (interaction なし)
    assert set(strata.keys()) == {"by_holiday_markets", "by_dst_transition_markets"}
    # by_holiday_markets: {tokyo}: [g1], frozenset(): [g2]
    holiday_strata = strata["by_holiday_markets"]
    assert frozenset({"tokyo"}) in holiday_strata
    assert frozenset() in holiday_strata
    assert holiday_strata[frozenset({"tokyo"})][0].genome_id == "g1"
    assert holiday_strata[frozenset()][0].genome_id == "g2"


def test_compute_dsr_strata_with_allowlist_only_listed() -> None:
    """F40: allowlist 内の 2 軸 cross product のみ集計."""
    null = _make_null_model(n_trials=2)
    rec = _make_record_with_genome_id("g1", null_model=null)
    report = RunAuditReport(
        run_id="run-1",
        dataset_epoch_id="ep-1",
        n_genomes=1,
        per_genome=(rec,),
        pbo=compute_audit_pbo_scaffold(),
        spa=compute_audit_spa_scaffold(),
        audit_report_schema_version=AUDIT_REPORT_SCHEMA_VERSION,
    )
    flag_lookup = {
        "g1": ObservabilityFlags(
            dst_transition_markets=frozenset({"london"}),
            holiday_markets=frozenset({"tokyo"}),
        ),
    }
    allowlist: list[tuple[str, ...]] = [
        ("holiday_markets", "dst_transition_markets")
    ]
    result = compute_dsr_strata_with_allowlist(
        report, flag_lookup=flag_lookup, allowlist=allowlist
    )
    keys = ("holiday_markets", "dst_transition_markets")
    assert keys in result
    # cross product key の value tuple
    expected_value = (frozenset({"tokyo"}), frozenset({"london"}))
    assert expected_value in result[keys]


def test_compute_dsr_strata_with_allowlist_empty_returns_empty() -> None:
    """F40b: allowlist=() → interaction 計算なし、 result も空."""
    null = _make_null_model(n_trials=2)
    rec = _make_record_with_genome_id("g1", null_model=null)
    report = RunAuditReport(
        run_id="run-1",
        dataset_epoch_id="ep-1",
        n_genomes=1,
        per_genome=(rec,),
        pbo=compute_audit_pbo_scaffold(),
        spa=compute_audit_spa_scaffold(),
        audit_report_schema_version=AUDIT_REPORT_SCHEMA_VERSION,
    )
    result = compute_dsr_strata_with_allowlist(
        report,
        flag_lookup={
            "g1": ObservabilityFlags(
                dst_transition_markets=frozenset(),
                holiday_markets=frozenset(),
            )
        },
        allowlist=[],
    )
    assert result == {}


def test_compute_dsr_strata_with_allowlist_warns_on_small_stratum(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """F40c: n<30 の stratum で warning log emit (= C7 規範)."""
    null = _make_null_model(n_trials=2)
    rec = _make_record_with_genome_id("g1", null_model=null)
    report = RunAuditReport(
        run_id="run-1",
        dataset_epoch_id="ep-1",
        n_genomes=1,
        per_genome=(rec,),
        pbo=compute_audit_pbo_scaffold(),
        spa=compute_audit_spa_scaffold(),
        audit_report_schema_version=AUDIT_REPORT_SCHEMA_VERSION,
    )
    flag_lookup = {
        "g1": ObservabilityFlags(
            dst_transition_markets=frozenset(),
            holiday_markets=frozenset(),
        )
    }
    with caplog.at_level(logging.WARNING, logger="src.alpha_factory.audit"):
        compute_dsr_strata_with_allowlist(
            report,
            flag_lookup=flag_lookup,
            allowlist=[("holiday_markets", "dst_transition_markets")],
        )
    assert any("stratum_insufficient_n" in r.message for r in caplog.records)


def test_compute_dsr_strata_schema_version_invariant() -> None:
    """F40d: schema_version="2.0.0" → ValueError."""
    null = _make_null_model(n_trials=2)
    rec = _make_record_with_genome_id("g1", null_model=null)
    report = RunAuditReport(
        run_id="run-1",
        dataset_epoch_id="ep-1",
        n_genomes=1,
        per_genome=(rec,),
        pbo=compute_audit_pbo_scaffold(),
        spa=compute_audit_spa_scaffold(),
        audit_report_schema_version=AUDIT_REPORT_SCHEMA_VERSION,
    )
    with pytest.raises(ValueError, match="schema_version"):
        compute_dsr_strata_with_allowlist(
            report,
            flag_lookup={
                "g1": ObservabilityFlags(
                    dst_transition_markets=frozenset(),
                    holiday_markets=frozenset(),
                )
            },
            allowlist=[("holiday_markets",)],
            schema_version="2.0.0",
        )


def test_compute_dsr_strata_flag_namespace_invariant() -> None:
    """F40e: flag_namespace="t074" → ValueError."""
    null = _make_null_model(n_trials=2)
    rec = _make_record_with_genome_id("g1", null_model=null)
    report = RunAuditReport(
        run_id="run-1",
        dataset_epoch_id="ep-1",
        n_genomes=1,
        per_genome=(rec,),
        pbo=compute_audit_pbo_scaffold(),
        spa=compute_audit_spa_scaffold(),
        audit_report_schema_version=AUDIT_REPORT_SCHEMA_VERSION,
    )
    with pytest.raises(ValueError, match="flag_namespace"):
        compute_dsr_strata_with_allowlist(
            report,
            flag_lookup={
                "g1": ObservabilityFlags(
                    dst_transition_markets=frozenset(),
                    holiday_markets=frozenset(),
                )
            },
            allowlist=[("holiday_markets",)],
            flag_namespace="t074",
        )


def test_compute_dsr_strata_unsupported_key_raises() -> None:
    """allowlist に未対応 key → ValueError."""
    null = _make_null_model(n_trials=2)
    rec = _make_record_with_genome_id("g1", null_model=null)
    report = RunAuditReport(
        run_id="run-1",
        dataset_epoch_id="ep-1",
        n_genomes=1,
        per_genome=(rec,),
        pbo=compute_audit_pbo_scaffold(),
        spa=compute_audit_spa_scaffold(),
        audit_report_schema_version=AUDIT_REPORT_SCHEMA_VERSION,
    )
    with pytest.raises(ValueError, match="unsupported key"):
        compute_dsr_strata_with_allowlist(
            report,
            flag_lookup={
                "g1": ObservabilityFlags(
                    dst_transition_markets=frozenset(),
                    holiday_markets=frozenset(),
                )
            },
            allowlist=[("schedule_status",)],  # 未対応 key
        )


def test_compute_dsr_strata_empty_tuple_raises() -> None:
    """allowlist に空 tuple → ValueError."""
    null = _make_null_model(n_trials=2)
    rec = _make_record_with_genome_id("g1", null_model=null)
    report = RunAuditReport(
        run_id="run-1",
        dataset_epoch_id="ep-1",
        n_genomes=1,
        per_genome=(rec,),
        pbo=compute_audit_pbo_scaffold(),
        spa=compute_audit_spa_scaffold(),
        audit_report_schema_version=AUDIT_REPORT_SCHEMA_VERSION,
    )
    with pytest.raises(ValueError, match=">= 1 key"):
        compute_dsr_strata_with_allowlist(
            report,
            flag_lookup={
                "g1": ObservabilityFlags(
                    dst_transition_markets=frozenset(),
                    holiday_markets=frozenset(),
                )
            },
            allowlist=[()],
        )


def test_compute_dsr_strata_duplicate_key_raises() -> None:
    """allowlist に重複 key を含む tuple → ValueError."""
    null = _make_null_model(n_trials=2)
    rec = _make_record_with_genome_id("g1", null_model=null)
    report = RunAuditReport(
        run_id="run-1",
        dataset_epoch_id="ep-1",
        n_genomes=1,
        per_genome=(rec,),
        pbo=compute_audit_pbo_scaffold(),
        spa=compute_audit_spa_scaffold(),
        audit_report_schema_version=AUDIT_REPORT_SCHEMA_VERSION,
    )
    with pytest.raises(ValueError, match="duplicate keys"):
        compute_dsr_strata_with_allowlist(
            report,
            flag_lookup={
                "g1": ObservabilityFlags(
                    dst_transition_markets=frozenset(),
                    holiday_markets=frozenset(),
                )
            },
            allowlist=[("holiday_markets", "holiday_markets")],
        )


def test_compute_marginal_strata_missing_genome_raises() -> None:
    """flag_lookup に genome_id が無い → ValueError."""
    null = _make_null_model(n_trials=2)
    rec = _make_record_with_genome_id("g1", null_model=null)
    report = RunAuditReport(
        run_id="run-1",
        dataset_epoch_id="ep-1",
        n_genomes=1,
        per_genome=(rec,),
        pbo=compute_audit_pbo_scaffold(),
        spa=compute_audit_spa_scaffold(),
        audit_report_schema_version=AUDIT_REPORT_SCHEMA_VERSION,
    )
    with pytest.raises(ValueError, match="missing genome_id"):
        compute_marginal_dsr_strata(report, flag_lookup={})


# ---------------------------------------------------------------------------
# F41-F42: 既存 statistics.py との整合 tests
# ---------------------------------------------------------------------------


def test_compute_audit_dsr_matches_statistics_direct_call() -> None:
    """F41: compute_audit_dsr_for_genome の dsr_value が deflated_sharpe_ratio
    直呼出と一致する (= 既存数式 wrap、 数式不変)."""
    null = _make_null_model(n_trials=10)
    pnls = [math.cos(i * 0.1) * 0.01 + 0.001 for i in range(100)]
    blocks = _generate_pnl_blocks(pnls)
    metric = compute_audit_dsr_for_genome(blocks, null_model=null)
    assert metric.status == "ok"

    # 直接 deflated_sharpe_ratio 呼出 (= 同 input で同値が出ることを確認)
    relevant_pnls = [float(b.pnl_net) for b in blocks if b.open_minutes > 0]
    n = len(relevant_pnls)
    import statistics as _stats_mod

    mean = _stats_mod.fmean(relevant_pnls)
    variance = _stats_mod.variance(relevant_pnls)
    stdev = math.sqrt(variance)
    sharpe = mean / stdev
    skew_val = sum((r - mean) ** 3 for r in relevant_pnls) / (n * stdev**3)
    kurt_val = sum((r - mean) ** 4 for r in relevant_pnls) / (n * stdev**4)
    direct_dsr = deflated_sharpe_ratio(
        sharpe_ratio=sharpe,
        n_trials=null.n_trials,
        n_observations=n,
        skew=skew_val,
        kurtosis=kurt_val,
        mean_sr_trials=float(null.mean_sr_trials),
        std_sr_trials=float(null.std_sr_trials),
    )
    assert metric.dsr_value == Decimal(str(direct_dsr))


def test_archive_dsr_field_untouched_by_t073() -> None:
    """F42: T073 PR で archive.py:81 の `dsr` field 計算経路が変更されていない.

    grep DoD: T073 の audit.py module は src/alpha_factory/archive.py を
    参照しない (= 既存 archive `dsr` field 経路は touch しない).
    """
    # audit.py の source code に "src.alpha_factory.archive" 参照が無いこと
    import inspect

    import src.alpha_factory.audit as audit_mod

    source = inspect.getsource(audit_mod)
    assert "src.alpha_factory.archive" not in source, (
        "T073 audit.py must not reference archive module "
        "(= Phase 2 で sharpe_calc_version 同期時に切替)"
    )
