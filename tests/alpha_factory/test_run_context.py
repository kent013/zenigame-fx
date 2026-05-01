"""T058: RunContext 単体テスト.

詳細設計: devnotes/20260429-1912-todo-T058-schema-v2-contract/detailed-design.md § 施策 2。
"""

from __future__ import annotations

import dataclasses

import pytest

from src.alpha_factory.run_context import RunContext
from src.alpha_factory.schema_contract import SchemaContractError


def test_run_context_constructs_with_valid_fields() -> None:
    """全 field 揃って grammar 合致なら正常構築."""
    ctx = RunContext(
        run_id="run_20260501_000000",
        run_number=27,
        dataset_epoch_id="epoch_legacy",
        base_config_hash="abcdef0123",
        instrument="EUR_JPY",
    )
    assert ctx.run_id == "run_20260501_000000"
    assert ctx.run_number == 27
    assert ctx.dataset_epoch_id == "epoch_legacy"
    assert ctx.base_config_hash == "abcdef0123"
    assert ctx.instrument == "EUR_JPY"


def test_run_context_rejects_empty_run_id() -> None:
    with pytest.raises(ValueError, match="run_id must be non-empty"):
        RunContext(
            run_id="",
            run_number=27,
            dataset_epoch_id="epoch_legacy",
            base_config_hash="abcdef0123",
            instrument="EUR_JPY",
        )


def test_run_context_rejects_negative_run_number() -> None:
    with pytest.raises(ValueError, match="run_number must be >= 0"):
        RunContext(
            run_id="run_20260501_000000",
            run_number=-1,
            dataset_epoch_id="epoch_legacy",
            base_config_hash="abcdef0123",
            instrument="EUR_JPY",
        )


def test_run_context_rejects_invalid_epoch_id_grammar() -> None:
    """grammar 違反 (大文字 / ハイフン) は SchemaContractError."""
    with pytest.raises(SchemaContractError, match="dataset_epoch_id"):
        RunContext(
            run_id="run_20260501_000000",
            run_number=27,
            dataset_epoch_id="Epoch-2026",  # 大文字 + ハイフン
            base_config_hash="abcdef0123",
            instrument="EUR_JPY",
        )


def test_run_context_rejects_empty_dataset_epoch_id() -> None:
    """空文字 dataset_epoch_id は SchemaContractError."""
    with pytest.raises(SchemaContractError, match="dataset_epoch_id"):
        RunContext(
            run_id="run_20260501_000000",
            run_number=27,
            dataset_epoch_id="",
            base_config_hash="abcdef0123",
            instrument="EUR_JPY",
        )


def test_run_context_rejects_empty_base_config_hash() -> None:
    with pytest.raises(ValueError, match="base_config_hash must be non-empty"):
        RunContext(
            run_id="run_20260501_000000",
            run_number=27,
            dataset_epoch_id="epoch_legacy",
            base_config_hash="",
            instrument="EUR_JPY",
        )


def test_run_context_rejects_empty_instrument() -> None:
    with pytest.raises(ValueError, match="instrument must be non-empty"):
        RunContext(
            run_id="run_20260501_000000",
            run_number=27,
            dataset_epoch_id="epoch_legacy",
            base_config_hash="abcdef0123",
            instrument="",
        )


def test_run_context_is_frozen_dataclass() -> None:
    """RunContext は frozen dataclass、 attribute 変更不可."""
    ctx = RunContext(
        run_id="run_20260501_000000",
        run_number=27,
        dataset_epoch_id="epoch_legacy",
        base_config_hash="abcdef0123",
        instrument="EUR_JPY",
    )
    assert dataclasses.is_dataclass(ctx)
    with pytest.raises(dataclasses.FrozenInstanceError):
        ctx.run_id = "mutated"  # type: ignore[misc]


def test_run_context_accepts_run_number_zero() -> None:
    """run_number=0 は受理 (>= 0)."""
    ctx = RunContext(
        run_id="run_20260501_000000",
        run_number=0,
        dataset_epoch_id="epoch_legacy",
        base_config_hash="abcdef0123",
        instrument="EUR_JPY",
    )
    assert ctx.run_number == 0
