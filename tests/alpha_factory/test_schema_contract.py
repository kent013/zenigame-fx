"""T058: schema_contract 単体テスト.

詳細設計: devnotes/20260429-1912-todo-T058-schema-v2-contract/detailed-design.md § 施策 1。
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from src.alpha_factory.schema_contract import (
    ArchiveRole,
    SchemaContractError,
    SchemaEnforcementMode,
    SourceStage,
    ValidationResult,
    assert_calibrate_history_v2,
    assert_diagnostics_v2,
    assert_epoch_id_present_for_display,
    assert_genome_entry_v2,
    assert_run_report_v2,
    validate_epoch_id,
)

# ---------------------------------------------------------------------------
# validate_epoch_id grammar
# ---------------------------------------------------------------------------


def test_validate_epoch_id_accepts_lowercase_alphanumeric_underscore() -> None:
    """``[a-z0-9_]+`` に合致する文字列は raise しない."""
    validate_epoch_id("epoch_2026_q1")
    validate_epoch_id("epoch_legacy")
    validate_epoch_id("a")
    validate_epoch_id("0")
    validate_epoch_id("_")


def test_validate_epoch_id_rejects_empty_string() -> None:
    """空文字は SchemaContractError."""
    with pytest.raises(SchemaContractError, match="must be non-empty"):
        validate_epoch_id("")


def test_validate_epoch_id_rejects_uppercase() -> None:
    """大文字を含む文字列は SchemaContractError."""
    with pytest.raises(SchemaContractError, match="violates grammar"):
        validate_epoch_id("Epoch_2026")


def test_validate_epoch_id_rejects_hyphen_or_space() -> None:
    """ハイフン / 空白は SchemaContractError."""
    with pytest.raises(SchemaContractError, match="violates grammar"):
        validate_epoch_id("epoch-2026")
    with pytest.raises(SchemaContractError, match="violates grammar"):
        validate_epoch_id("epoch 2026")


# ---------------------------------------------------------------------------
# assert_genome_entry_v2
# ---------------------------------------------------------------------------


def test_assert_genome_entry_v2_log_only_does_not_raise_on_missing_field() -> None:
    """LOG_ONLY mode は欠落 field で raise しない (warning のみ + ok=False)."""
    record = {
        "dataset_epoch_id": "epoch_legacy",
        # "genome_entry_schema_version" 欠落
        # "archive_role" 欠落
        # "source_stage" 欠落
    }
    result = assert_genome_entry_v2(record, mode=SchemaEnforcementMode.LOG_ONLY)
    assert isinstance(result, ValidationResult)
    assert result.ok is False
    assert "genome_entry_schema_version" in result.missing


def test_assert_genome_entry_v2_fail_closed_raises_on_missing_field() -> None:
    """FAIL_CLOSED mode で必須 field 欠落 → SchemaContractError."""
    record = {
        "dataset_epoch_id": "epoch_legacy",
    }
    with pytest.raises(SchemaContractError, match="genome_entry"):
        assert_genome_entry_v2(record, mode=SchemaEnforcementMode.FAIL_CLOSED)


def test_assert_genome_entry_v2_fail_closed_raises_on_invalid_epoch_id() -> None:
    """FAIL_CLOSED mode で grammar 違反 → SchemaContractError."""
    record = {
        "dataset_epoch_id": "Epoch-2026",  # 大文字 + ハイフン
        "genome_entry_schema_version": 2,
        "archive_role": "mission_pass",
        "source_stage": "a",
    }
    # validate_epoch_id 経由で raise されるので message は "violates grammar ..." 形式
    with pytest.raises(SchemaContractError, match="violates grammar"):
        assert_genome_entry_v2(record, mode=SchemaEnforcementMode.FAIL_CLOSED)


def test_assert_genome_entry_v2_log_only_invalid_epoch_id_returns_not_ok() -> None:
    """LOG_ONLY mode で grammar 違反 → ok=False、 invalid 含む."""
    record = {
        "dataset_epoch_id": "Epoch-2026",
        "genome_entry_schema_version": 2,
        "archive_role": "mission_pass",
        "source_stage": "a",
    }
    result = assert_genome_entry_v2(record, mode=SchemaEnforcementMode.LOG_ONLY)
    assert result.ok is False
    assert "dataset_epoch_id" in result.invalid


def test_assert_genome_entry_v2_log_only_invalid_epoch_id_fires_dedicated_log_event() -> None:
    """SSOT (詳細設計 行 335): grammar 違反は ``schema_contract.invalid_epoch_id``
    専用 event で発火する (LOG_ONLY mode)."""
    record = {
        "dataset_epoch_id": "Epoch-2026",
        "genome_entry_schema_version": 2,
        "archive_role": "mission_pass",
        "source_stage": "a",
    }
    with patch("src.alpha_factory.schema_contract.logger") as mock_logger:
        assert_genome_entry_v2(record, mode=SchemaEnforcementMode.LOG_ONLY)
        events = [c[0][0] for c in mock_logger.warning.call_args_list]
        assert "schema_contract.invalid_epoch_id" in events
        assert "schema_contract.passive_validation_failed" in events


def test_assert_genome_entry_v2_passes_on_complete_valid_record() -> None:
    """全 field 揃って grammar 合致なら ok=True."""
    record = {
        "dataset_epoch_id": "epoch_legacy",
        "genome_entry_schema_version": 2,
        "archive_role": "mission_pass",
        "source_stage": "a",
    }
    result = assert_genome_entry_v2(record, mode=SchemaEnforcementMode.FAIL_CLOSED)
    assert result.ok is True


# ---------------------------------------------------------------------------
# assert_calibrate_history_v2
# ---------------------------------------------------------------------------


def test_assert_calibrate_history_v2_log_only_returns_not_ok_on_missing() -> None:
    record: dict[str, object] = {}
    result = assert_calibrate_history_v2(
        record, mode=SchemaEnforcementMode.LOG_ONLY
    )
    assert result.ok is False
    assert "dataset_epoch_id" in result.missing
    assert "calibrate_history_schema_version" in result.missing


def test_assert_calibrate_history_v2_fail_closed_raises_on_missing() -> None:
    record: dict[str, object] = {}
    with pytest.raises(SchemaContractError, match="calibrate_history"):
        assert_calibrate_history_v2(
            record, mode=SchemaEnforcementMode.FAIL_CLOSED
        )


def test_assert_calibrate_history_v2_passes_on_complete_record() -> None:
    record = {
        "dataset_epoch_id": "epoch_legacy",
        "calibrate_history_schema_version": 2,
    }
    result = assert_calibrate_history_v2(
        record, mode=SchemaEnforcementMode.FAIL_CLOSED
    )
    assert result.ok is True


# ---------------------------------------------------------------------------
# assert_run_report_v2
# ---------------------------------------------------------------------------


def test_assert_run_report_v2_fail_closed_raises_on_string_cascade_contract_version() -> None:
    """``cascade_contract_version`` が int 以外なら FAIL_CLOSED で raise."""
    report = {
        "dataset_epoch_id": "epoch_legacy",
        "cascade_contract_version": "v2",  # str → 型違反
    }
    with pytest.raises(SchemaContractError, match="cascade_contract_version"):
        assert_run_report_v2(report, mode=SchemaEnforcementMode.FAIL_CLOSED)


def test_assert_run_report_v2_log_only_string_cascade_contract_version_returns_not_ok() -> None:
    report = {
        "dataset_epoch_id": "epoch_legacy",
        "cascade_contract_version": "v2",
    }
    result = assert_run_report_v2(report, mode=SchemaEnforcementMode.LOG_ONLY)
    assert result.ok is False
    assert "cascade_contract_version" in result.invalid


def test_assert_run_report_v2_passes_on_int_cascade_contract_version() -> None:
    report = {
        "dataset_epoch_id": "epoch_legacy",
        "cascade_contract_version": 2,
    }
    result = assert_run_report_v2(report, mode=SchemaEnforcementMode.FAIL_CLOSED)
    assert result.ok is True


# ---------------------------------------------------------------------------
# assert_diagnostics_v2
# ---------------------------------------------------------------------------


def test_assert_diagnostics_v2_passes_on_complete_record() -> None:
    record = {
        "dataset_epoch_id": "epoch_legacy",
        "diagnostics_schema_version": 2,
    }
    result = assert_diagnostics_v2(
        record, mode=SchemaEnforcementMode.FAIL_CLOSED
    )
    assert result.ok is True


def test_assert_diagnostics_v2_fail_closed_raises_on_missing() -> None:
    record: dict[str, object] = {}
    with pytest.raises(SchemaContractError, match="diagnostics"):
        assert_diagnostics_v2(record, mode=SchemaEnforcementMode.FAIL_CLOSED)


# ---------------------------------------------------------------------------
# Enum persisted values (lower_snake_case)
# ---------------------------------------------------------------------------


def test_archive_role_persisted_value_is_lower_snake_case() -> None:
    """ArchiveRole の永続値は lower_snake_case."""
    assert ArchiveRole.MISSION_PASS.value == "mission_pass"
    assert ArchiveRole.PROGRESS_PASS.value == "progress_pass"
    assert ArchiveRole.SCORE_BYPASS.value == "score_bypass"


def test_source_stage_c_lite_persisted_value() -> None:
    """SourceStage.C_LITE は ``c_lite`` で永続化される (Stage C-lite と整合)."""
    assert SourceStage.A.value == "a"
    assert SourceStage.B.value == "b"
    assert SourceStage.C_LITE.value == "c_lite"
    assert SourceStage.C.value == "c"


# ---------------------------------------------------------------------------
# Tier 2 (assert_epoch_id_present_for_display)
# ---------------------------------------------------------------------------


def test_assert_epoch_id_present_for_display_does_not_raise_when_missing() -> None:
    """Tier 2 ガードは fail させない (warning のみ)."""
    obj: dict[str, object] = {"foo": "bar"}
    # raise しないこと
    assert_epoch_id_present_for_display(obj, artifact="some_display_artifact")
    assert_epoch_id_present_for_display(None, artifact="some_display_artifact")


def test_assert_epoch_id_present_for_display_logs_warning_when_missing() -> None:
    """Tier 2 ガードは warning ログを出す (mock logger 検証)."""
    obj = {"foo": "bar"}
    with patch(
        "src.alpha_factory.schema_contract.logger"
    ) as mock_logger:
        assert_epoch_id_present_for_display(obj, artifact="alpha_sieve_display")
        mock_logger.warning.assert_called_once()
        call_args = mock_logger.warning.call_args
        assert call_args[0][0] == "schema_contract.tier2_epoch_id_missing"
        assert call_args[1]["artifact"] == "alpha_sieve_display"


def test_assert_epoch_id_present_for_display_silent_when_present() -> None:
    """``dataset_epoch_id`` がある場合は warning を出さない."""
    obj = {"dataset_epoch_id": "epoch_legacy"}
    with patch(
        "src.alpha_factory.schema_contract.logger"
    ) as mock_logger:
        assert_epoch_id_present_for_display(obj, artifact="alpha_sieve_display")
        mock_logger.warning.assert_not_called()


def test_assert_epoch_id_present_for_display_warns_on_empty_string() -> None:
    """T058 PR 6: ``dataset_epoch_id`` が空文字でも warning を発火する
    (詳細設計 行 1469-1470 fail-open、 但し empty value は missing 扱い)."""
    obj = {"dataset_epoch_id": ""}
    with patch(
        "src.alpha_factory.schema_contract.logger"
    ) as mock_logger:
        assert_epoch_id_present_for_display(obj, artifact="some_display_artifact")
        mock_logger.warning.assert_called_once()
        assert (
            mock_logger.warning.call_args[0][0]
            == "schema_contract.tier2_epoch_id_missing"
        )


def test_assert_epoch_id_present_for_display_warns_on_none_value() -> None:
    """T058 PR 6: ``dataset_epoch_id`` が None でも warning を発火する."""
    obj: dict[str, object] = {"dataset_epoch_id": None}
    with patch(
        "src.alpha_factory.schema_contract.logger"
    ) as mock_logger:
        assert_epoch_id_present_for_display(obj, artifact="some_display_artifact")
        mock_logger.warning.assert_called_once()


def test_assert_epoch_id_present_for_display_includes_artifact_name_in_log() -> None:
    """T058 PR 6: artifact 引数が log の kwarg `artifact` に渡されること."""
    obj: dict[str, object] = {"foo": "bar"}
    with patch(
        "src.alpha_factory.schema_contract.logger"
    ) as mock_logger:
        assert_epoch_id_present_for_display(
            obj, artifact="generate_run_report.run-7.md"
        )
        assert (
            mock_logger.warning.call_args[1]["artifact"]
            == "generate_run_report.run-7.md"
        )
