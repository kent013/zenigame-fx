"""T069: calibrate_freeze (epoch 内 3 Run freeze 判定) unit tests.

F1-F13 + F15 + happy path を網羅 (詳細設計 §5.1 / §9 SSOT)。
"""

from __future__ import annotations

from typing import Any

import pytest

from src.alpha_factory.calibrate_freeze import (
    DEFAULT_FREEZE_WINDOW,
    FreezeStatus,
    decide_with_freeze,
    evaluate_freeze_status,
)
from src.alpha_factory.calibrate_gate import (
    AggregatedSample,
    CalibrateConfig,
    decide,
)
from src.alpha_factory.calibrate_gate_history import HistoryRecord

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_record(
    *,
    epoch_id: str,
    run_id: str | None,
    decision: str = "tighten",
    **kwargs: Any,
) -> HistoryRecord:
    """T058 v2 必須 field を埋める HistoryRecord 構築 helper.

    PR 条件: T058 PR が先行 merge されていることが前提
    (schema_version=2 + calibrate_history_schema_version=2 を固定で使用)。
    """
    # T077: applied_from_run_id 必須化対応. run_id None / "" でも HistoryRecord
    # の applied_from_run_id は非空文字 str に default で埋める (= helper の
    # 既存 caller を壊さない). null / empty を test したい時は kwargs で
    # 明示的に applied_from_run_id=None / "" を override する.
    run_id_resolved = run_id or "run_unspecified"
    defaults: dict[str, Any] = dict(
        run_id=run_id_resolved,
        applied_at="2026-04-30T10:00:00+00:00",
        n_rows_total=100,
        n_rows_used=80,
        aggregation_mode="last_k_generations",
        aggregation_window=5,
        actual_pass_rate=0.18,
        target_pass_rate=0.20,
        tol=0.02,
        prev_threshold=0.50,
        new_threshold=0.48,
        delta=-0.02,
        decision=decision,
        var_fitness_pen=0.001,
        clamped_by_delta=False,
        clamped_by_floor_or_ceiling=False,
        stage_b_pass_count=0,
        stage_c_pass_count=0,
        live_criteria_gap={},
        # T054 cross-run guard
        schema_version=2,
        base_config_hash="hash_a",
        full_config_hash="full_hash_a",
        dataset_span=["2024-01-01", "2026-04-21"],
        instrument="eur_usd",
        stage_gate_version="v0.1.0",
        # T077: 必須化、 run_id 同等 (helper 簡素化、 test override は kwargs)
        applied_from_run_id=run_id_resolved,
        # T058 で v2 必須化される field 群
        dataset_epoch_id=epoch_id,
        # calibrate_history_schema_version は HistoryRecord default で v2 固定
    )
    defaults.update(kwargs)
    return HistoryRecord(**defaults)


def _make_config(
    *,
    prev_threshold: float = 0.50,
    threshold_delta_abs_max: float = 0.03,
    target_pass_rate: float = 0.20,
    pass_rate_tolerance_abs: float = 0.02,
) -> CalibrateConfig:
    """既存 CalibrateConfig (T069 contract: ≤0.03)."""
    return CalibrateConfig(
        enabled=True,
        aggregation_mode="last_k_generations",
        aggregation_window=5,
        pass_rate_tolerance_abs=pass_rate_tolerance_abs,
        threshold_delta_abs_max=threshold_delta_abs_max,
        threshold_floor=-100.0,
        threshold_ceiling=100.0,
        min_sample_size=5,
        eps_var=1.0e-9,
        target_pass_rate=target_pass_rate,
        prev_threshold=prev_threshold,
    )


def _make_sample(
    *,
    n_rows_used: int = 80,
    actual_pass_rate: float = 0.18,
) -> AggregatedSample:
    """既存 AggregatedSample fixture (variance を持たせて zero_variance 回避)."""
    pool = tuple(0.10 + 0.01 * i for i in range(n_rows_used))
    return AggregatedSample(
        n_rows_total=n_rows_used + 20,
        n_rows_used=n_rows_used,
        pass_count_used=int(n_rows_used * actual_pass_rate),
        actual_pass_rate=actual_pass_rate,
        fitness_pen_pool=pool,
        mode="last_k_generations",
        window=5,
    )


# ---------------------------------------------------------------------------
# evaluate_freeze_status: validation
# ---------------------------------------------------------------------------


class TestEvaluateFreezeStatusValidation:
    """``evaluate_freeze_status`` の入力 validation 系."""

    def test_F10a_dataset_epoch_id_none_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="dataset_epoch_id must be"):
            evaluate_freeze_status(records=[], dataset_epoch_id=None)  # type: ignore[arg-type]

    def test_F10b_dataset_epoch_id_empty_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="non-empty"):
            evaluate_freeze_status(records=[], dataset_epoch_id="")

    def test_F10c_dataset_epoch_id_non_str_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="dataset_epoch_id must be"):
            evaluate_freeze_status(records=[], dataset_epoch_id=123)  # type: ignore[arg-type]

    def test_F9a_freeze_window_zero_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="freeze_window must be >= 1"):
            evaluate_freeze_status(
                records=[], dataset_epoch_id="ep1", freeze_window=0
            )

    def test_F9b_freeze_window_negative_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="freeze_window must be >= 1"):
            evaluate_freeze_status(
                records=[], dataset_epoch_id="ep1", freeze_window=-1
            )


# ---------------------------------------------------------------------------
# evaluate_freeze_status: counting
# ---------------------------------------------------------------------------


class TestEvaluateFreezeStatusCounting:
    """count ロジックの正当性."""

    def test_empty_history_is_frozen_count_zero(self) -> None:
        # Happy path: epoch 1 Run 目 (count=0 < 3) → frozen
        result = evaluate_freeze_status(records=[], dataset_epoch_id="ep1")
        assert result.is_frozen is True
        assert result.epoch_distinct_run_count == 0
        assert result.next_run_index_in_epoch == 1
        assert result.freeze_window == DEFAULT_FREEZE_WINDOW

    def test_two_runs_frozen(self) -> None:
        # Happy path: epoch 内 2 distinct Run → freeze (3 Run 目もまだ frozen)
        records = [
            _make_record(epoch_id="ep1", run_id="run_001"),
            _make_record(epoch_id="ep1", run_id="run_002"),
        ]
        result = evaluate_freeze_status(
            records=records, dataset_epoch_id="ep1"
        )
        assert result.is_frozen is True
        assert result.epoch_distinct_run_count == 2
        assert result.next_run_index_in_epoch == 3

    def test_three_runs_unfrozen(self) -> None:
        # Happy path: count=3 → unfrozen (4 Run 目から calibrate)
        records = [
            _make_record(epoch_id="ep1", run_id=f"run_{i:03d}")
            for i in range(1, 4)
        ]
        result = evaluate_freeze_status(
            records=records, dataset_epoch_id="ep1"
        )
        assert result.is_frozen is False
        assert result.epoch_distinct_run_count == 3
        assert result.next_run_index_in_epoch == 4

    def test_F1_other_epoch_records_excluded(self) -> None:
        # F1: 異なる epoch_id record は filter で count 除外
        records = [
            _make_record(epoch_id="ep1", run_id="run_001"),
            _make_record(epoch_id="ep0", run_id="run_xx1"),
            _make_record(epoch_id="ep0", run_id="run_xx2"),
        ]
        result = evaluate_freeze_status(
            records=records, dataset_epoch_id="ep1"
        )
        assert result.is_frozen is True
        assert result.epoch_distinct_run_count == 1

    def test_F3_epoch_id_change_resets_count(self) -> None:
        # F3: 旧 epoch (ep0) で 5 Run 進行済でも、 新 epoch (ep1) では count=0
        records = [
            _make_record(epoch_id="ep0", run_id=f"run_xx{i}")
            for i in range(5)
        ]
        result = evaluate_freeze_status(
            records=records, dataset_epoch_id="ep1"
        )
        assert result.is_frozen is True
        assert result.epoch_distinct_run_count == 0
        assert result.next_run_index_in_epoch == 1

    def test_F5_duplicate_run_id_counted_once(self) -> None:
        # F5: 同 run_id 二重 append → count 増えない (distinct set)
        records = [
            _make_record(
                epoch_id="ep1", run_id="run_001", decision="tighten"
            ),
            _make_record(
                epoch_id="ep1", run_id="run_001", decision="loosen"
            ),  # 二重
            _make_record(epoch_id="ep1", run_id="run_002"),
        ]
        result = evaluate_freeze_status(
            records=records, dataset_epoch_id="ep1"
        )
        assert result.epoch_distinct_run_count == 2
        assert result.is_frozen is True

    # T077: F15a / F15b は applied_from_run_id 必須化により不要 (= type level
    # で防がれる、 HistoryRecord 構築時に ValueError raise). hot-fix 経路削除に
    # 対応する新仕様 test に置換.
    def test_T077_null_applied_from_run_id_rejected_at_construction(self) -> None:
        """T077 必須化: HistoryRecord 構築時に applied_from_run_id None reject."""
        with pytest.raises(ValueError, match="applied_from_run_id"):
            _make_record(
                epoch_id="ep1",
                run_id="run_002",
                applied_from_run_id=None,  # type: ignore[arg-type]
            )

    def test_T077_empty_applied_from_run_id_rejected_at_construction(self) -> None:
        """T077 必須化: HistoryRecord 構築時に applied_from_run_id 空文字 reject."""
        with pytest.raises(ValueError, match="applied_from_run_id"):
            _make_record(
                epoch_id="ep1",
                run_id="run_002",
                applied_from_run_id="",
            )

    def test_T077_defense_in_depth_evaluate_freeze_rejects_bypass_object(
        self,
    ) -> None:
        """T077 Round 2 [Suggestion]: HistoryRecord.__post_init__ を bypass した
        不正オブジェクト (= dataclasses.replace + object.__setattr__ 等で
        applied_from_run_id を None / "" に書き換え) が evaluate_freeze_status
        に入った場合、 defense-in-depth で ValueError raise されることを検証.

        簡易再現: 通常 HistoryRecord 1 件 + 「applied_from_run_id が None」 を
        持つ模擬 record を namespace で構築 (= 不正混入 simulate). Round 1
        [Warning] hot-fix 削除後の silent miscount 防止経路を保証.
        """
        from types import SimpleNamespace

        valid_record = _make_record(epoch_id="ep1", run_id="run_001")
        # 不正混入 simulate (= HistoryRecord 構築を bypass、 applied_from_run_id が None)
        invalid_record = SimpleNamespace(
            applied_from_run_id=None,
            dataset_epoch_id="ep1",
        )
        with pytest.raises(ValueError, match="invalid applied_from_run_id"):
            evaluate_freeze_status(
                records=[valid_record, invalid_record],  # type: ignore[list-item]
                dataset_epoch_id="ep1",
            )

    def test_T077_defense_in_depth_evaluate_freeze_rejects_empty_string(
        self,
    ) -> None:
        """T077 Round 2 [Suggestion]: 空文字 applied_from_run_id も defense-in-depth
        で reject されることを検証 (= None と空文字の両方を fail-fast).
        """
        from types import SimpleNamespace

        valid_record = _make_record(epoch_id="ep1", run_id="run_001")
        invalid_empty = SimpleNamespace(
            applied_from_run_id="",
            dataset_epoch_id="ep1",
        )
        with pytest.raises(ValueError, match="invalid applied_from_run_id"):
            evaluate_freeze_status(
                records=[valid_record, invalid_empty],  # type: ignore[list-item]
                dataset_epoch_id="ep1",
            )

    def test_custom_freeze_window(self) -> None:
        # custom freeze_window=5
        records = [
            _make_record(epoch_id="ep1", run_id=f"run_{i}")
            for i in range(4)
        ]
        result = evaluate_freeze_status(
            records=records, dataset_epoch_id="ep1", freeze_window=5
        )
        assert result.is_frozen is True
        assert result.epoch_distinct_run_count == 4
        assert result.freeze_window == 5

    def test_F11_many_runs_unfrozen_no_upper_limit(self) -> None:
        # F11: count >> 3 でも freeze は False (= 通常 calibrate)
        records = [
            _make_record(epoch_id="ep1", run_id=f"run_{i:03d}")
            for i in range(10)
        ]
        result = evaluate_freeze_status(
            records=records, dataset_epoch_id="ep1"
        )
        assert result.is_frozen is False
        assert result.epoch_distinct_run_count == 10

    def test_default_freeze_window_is_3(self) -> None:
        """``DEFAULT_FREEZE_WINDOW`` SSOT 確認 (synthesis § 8.6)."""
        assert DEFAULT_FREEZE_WINDOW == 3


# ---------------------------------------------------------------------------
# decide_with_freeze
# ---------------------------------------------------------------------------


class TestDecideWithFreeze:
    """``decide_with_freeze`` の挙動."""

    def test_decide_with_freeze_frozen_returns_skip_frozen(self) -> None:
        # Happy path: is_frozen=True → "skip_frozen"
        # 注: F4 「history append」 は Phase 2 IT、 本 unit はそれと別の責務
        config = _make_config(prev_threshold=0.50)
        sample = _make_sample()
        fs = FreezeStatus(
            is_frozen=True,
            epoch_distinct_run_count=2,
            freeze_window=3,
            next_run_index_in_epoch=3,
        )
        result = decide_with_freeze(sample, config, freeze_status=fs)
        assert result.decision == "skip_frozen"
        assert result.new_threshold == 0.50
        assert result.delta == 0.0
        assert result.q_target is None
        assert result.var_fitness_pen is None
        assert result.raw_target_threshold is None
        assert result.clamped_by_delta is False
        assert result.clamped_by_floor_or_ceiling is False
        assert result.effective_sample_size == sample.n_rows_used

    def test_unfrozen_delegates_to_decide(self) -> None:
        # 完全委譲: count=3 で `decide()` 結果と同一
        config = _make_config(prev_threshold=0.50)
        sample = _make_sample()
        fs = FreezeStatus(
            is_frozen=False,
            epoch_distinct_run_count=3,
            freeze_window=3,
            next_run_index_in_epoch=4,
        )
        expected = decide(sample, config)
        result = decide_with_freeze(sample, config, freeze_status=fs)
        assert result == expected

    def test_frozen_skip_frozen_does_not_touch_disabled_branch(self) -> None:
        """freeze 中は ``enabled=False`` でも ``skip_frozen`` 優先 (= freeze の方が先).

        ``decide_with_freeze`` の責務は freeze 判定の優先実行。
        ``enabled=False`` は ``decide()`` 内の skip_disabled だが、 freeze 中は
        ``decide()`` を呼ばないため ``skip_frozen`` が固定で返る。
        """
        config = CalibrateConfig(
            enabled=False,  # 通常 decide なら "skip_disabled"
            aggregation_mode="last_k_generations",
            aggregation_window=5,
            pass_rate_tolerance_abs=0.02,
            threshold_delta_abs_max=0.03,
            threshold_floor=-100.0,
            threshold_ceiling=100.0,
            min_sample_size=5,
            eps_var=1.0e-9,
            target_pass_rate=0.20,
            prev_threshold=0.42,
        )
        sample = _make_sample()
        fs = FreezeStatus(
            is_frozen=True,
            epoch_distinct_run_count=0,
            freeze_window=3,
            next_run_index_in_epoch=1,
        )
        result = decide_with_freeze(sample, config, freeze_status=fs)
        assert result.decision == "skip_frozen"
        assert result.new_threshold == 0.42


# ---------------------------------------------------------------------------
# FreezeStatus invariants
# ---------------------------------------------------------------------------


class TestFreezeStatusInvariants:
    def test_inconsistent_is_frozen_raises(self) -> None:
        with pytest.raises(ValueError, match="is_frozen"):
            FreezeStatus(
                is_frozen=True,
                epoch_distinct_run_count=5,  # >= 3 だが is_frozen=True は矛盾
                freeze_window=3,
                next_run_index_in_epoch=6,
            )

    def test_inconsistent_next_index_raises(self) -> None:
        with pytest.raises(ValueError, match="next_run_index_in_epoch"):
            FreezeStatus(
                is_frozen=False,
                epoch_distinct_run_count=3,
                freeze_window=3,
                next_run_index_in_epoch=5,  # 4 が正
            )

    def test_negative_count_raises(self) -> None:
        with pytest.raises(
            ValueError, match="epoch_distinct_run_count must be >= 0"
        ):
            FreezeStatus(
                is_frozen=True,
                epoch_distinct_run_count=-1,
                freeze_window=3,
                next_run_index_in_epoch=0,
            )

    def test_freeze_window_zero_raises(self) -> None:
        with pytest.raises(ValueError, match="freeze_window must be >= 1"):
            FreezeStatus(
                is_frozen=False,
                epoch_distinct_run_count=0,
                freeze_window=0,
                next_run_index_in_epoch=1,
            )

    def test_valid_construction(self) -> None:
        # Happy path: 矛盾なき構築は通る
        fs = FreezeStatus(
            is_frozen=True,
            epoch_distinct_run_count=1,
            freeze_window=3,
            next_run_index_in_epoch=2,
        )
        assert fs.is_frozen is True
        assert fs.epoch_distinct_run_count == 1
        assert fs.freeze_window == 3
        assert fs.next_run_index_in_epoch == 2
