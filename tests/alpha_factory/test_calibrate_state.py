"""T054: calibrate_state (state file load + cross-run contamination guard) tests."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest

from src.alpha_factory.calibrate_state import (
    SCHEMA_VERSION,
    compute_base_config_hash,
    compute_full_config_hash,
    load_calibrated_threshold,
)
from src.alpha_factory.config import load_config


@pytest.fixture
def af_cfg(tmp_path: Path):
    """default.yaml ベースで AlphaFactoryConfig を構築."""
    config_path = (
        Path(__file__).resolve().parents[2]
        / "config"
        / "alpha_factory"
        / "default.yaml"
    )
    return load_config(config_path)


def _make_record(
    *,
    run_id: str = "run_test",
    new_threshold: float = 0.123,
    decision: str = "tighten",
    base_hash: str,
    dataset_span: list[str],
    instrument: str,
    stage_gate_version: str,
    schema_version: int = SCHEMA_VERSION,
    applied_at: str | None = None,
) -> dict:
    return {
        "run_id": run_id,
        "applied_at": applied_at or datetime.now().isoformat(),
        "n_rows_total": 100,
        "n_rows_used": 100,
        "aggregation_mode": "all_generations",
        "aggregation_window": 5,
        "actual_pass_rate": 0.5,
        "target_pass_rate": 0.15,
        "tol": 0.05,
        "prev_threshold": 0.0,
        "new_threshold": new_threshold,
        "delta": 0.123,
        "decision": decision,
        "var_fitness_pen": 0.5,
        "clamped_by_delta": False,
        "clamped_by_floor_or_ceiling": False,
        "stage_b_pass_count": 100,
        "stage_c_pass_count": 0,
        "live_criteria_gap": {},
        "schema_version": schema_version,
        "base_config_hash": base_hash,
        "full_config_hash": "f" * 64,
        "dataset_span": dataset_span,
        "instrument": instrument,
        "stage_gate_version": stage_gate_version,
        "applied_from_run_id": run_id,
    }


def _write_history(records: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, default=str) + "\n")


class TestLoadCalibratedThreshold:
    def test_returns_none_when_history_path_missing(self, tmp_path: Path) -> None:
        """history.jsonl が存在しない → None."""
        result = load_calibrated_threshold(
            history_path=tmp_path / "missing.jsonl",
            base_config_hash="abc123",
            dataset_span=("2026-01-01", "2026-12-31"),
            instrument="USD_JPY",
            stage_gate_version="v3",
        )
        assert result is None

    def test_returns_none_when_history_empty(self, tmp_path: Path) -> None:
        """history.jsonl が空 → None."""
        history = tmp_path / "history.jsonl"
        history.write_text("", encoding="utf-8")
        result = load_calibrated_threshold(
            history_path=history,
            base_config_hash="abc",
            dataset_span=("2026-01-01", "2026-12-31"),
            instrument="USD_JPY",
            stage_gate_version="v3",
        )
        assert result is None

    def test_returns_threshold_when_record_matches(self, tmp_path: Path) -> None:
        """全 metadata 一致 + decision=tighten → new_threshold 返却."""
        history = tmp_path / "history.jsonl"
        rec = _make_record(
            new_threshold=0.0778,
            base_hash="myhash",
            dataset_span=["2026-01-01", "2026-12-31"],
            instrument="USD_JPY",
            stage_gate_version="v3",
        )
        _write_history([rec], history)
        result = load_calibrated_threshold(
            history_path=history,
            base_config_hash="myhash",
            dataset_span=("2026-01-01", "2026-12-31"),
            instrument="USD_JPY",
            stage_gate_version="v3",
        )
        assert result == 0.0778

    def test_skip_when_base_config_hash_mismatch(self, tmp_path: Path) -> None:
        """base_config_hash 不一致 → None (cross-run contamination guard)."""
        history = tmp_path / "history.jsonl"
        rec = _make_record(
            new_threshold=0.5,
            base_hash="old_hash",
            dataset_span=["2026-01-01", "2026-12-31"],
            instrument="USD_JPY",
            stage_gate_version="v3",
        )
        _write_history([rec], history)
        result = load_calibrated_threshold(
            history_path=history,
            base_config_hash="new_hash",  # 不一致
            dataset_span=("2026-01-01", "2026-12-31"),
            instrument="USD_JPY",
            stage_gate_version="v3",
        )
        assert result is None

    def test_skip_when_dataset_span_mismatch(self, tmp_path: Path) -> None:
        history = tmp_path / "history.jsonl"
        rec = _make_record(
            base_hash="h",
            dataset_span=["2025-01-01", "2025-12-31"],  # 異なる span
            instrument="USD_JPY",
            stage_gate_version="v3",
        )
        _write_history([rec], history)
        result = load_calibrated_threshold(
            history_path=history,
            base_config_hash="h",
            dataset_span=("2026-01-01", "2026-12-31"),
            instrument="USD_JPY",
            stage_gate_version="v3",
        )
        assert result is None

    def test_skip_when_instrument_mismatch(self, tmp_path: Path) -> None:
        history = tmp_path / "history.jsonl"
        rec = _make_record(
            base_hash="h",
            dataset_span=["2026-01-01", "2026-12-31"],
            instrument="EUR_USD",  # 異なる instrument
            stage_gate_version="v3",
        )
        _write_history([rec], history)
        result = load_calibrated_threshold(
            history_path=history,
            base_config_hash="h",
            dataset_span=("2026-01-01", "2026-12-31"),
            instrument="USD_JPY",
            stage_gate_version="v3",
        )
        assert result is None

    def test_skip_when_stage_gate_version_mismatch(self, tmp_path: Path) -> None:
        history = tmp_path / "history.jsonl"
        rec = _make_record(
            base_hash="h",
            dataset_span=["2026-01-01", "2026-12-31"],
            instrument="USD_JPY",
            stage_gate_version="v_old",  # 異なる version
        )
        _write_history([rec], history)
        result = load_calibrated_threshold(
            history_path=history,
            base_config_hash="h",
            dataset_span=("2026-01-01", "2026-12-31"),
            instrument="USD_JPY",
            stage_gate_version="v3",
        )
        assert result is None

    def test_decision_filter_in_band_skipped(self, tmp_path: Path) -> None:
        """decision='in_band' は適用対象外."""
        history = tmp_path / "history.jsonl"
        rec = _make_record(
            base_hash="h",
            dataset_span=["2026-01-01", "2026-12-31"],
            instrument="USD_JPY",
            stage_gate_version="v3",
            decision="in_band",  # 適用対象外
        )
        _write_history([rec], history)
        result = load_calibrated_threshold(
            history_path=history,
            base_config_hash="h",
            dataset_span=("2026-01-01", "2026-12-31"),
            instrument="USD_JPY",
            stage_gate_version="v3",
        )
        assert result is None

    def test_decision_filter_skip_sample_size_skipped(
        self, tmp_path: Path
    ) -> None:
        """decision='skip_sample_size' は適用対象外."""
        history = tmp_path / "history.jsonl"
        rec = _make_record(
            base_hash="h",
            dataset_span=["2026-01-01", "2026-12-31"],
            instrument="USD_JPY",
            stage_gate_version="v3",
            decision="skip_sample_size",
        )
        _write_history([rec], history)
        result = load_calibrated_threshold(
            history_path=history,
            base_config_hash="h",
            dataset_span=("2026-01-01", "2026-12-31"),
            instrument="USD_JPY",
            stage_gate_version="v3",
        )
        assert result is None

    def test_decision_loosen_applied(self, tmp_path: Path) -> None:
        """decision='loosen' は適用される."""
        history = tmp_path / "history.jsonl"
        rec = _make_record(
            new_threshold=-0.05,
            base_hash="h",
            dataset_span=["2026-01-01", "2026-12-31"],
            instrument="USD_JPY",
            stage_gate_version="v3",
            decision="loosen",
        )
        _write_history([rec], history)
        result = load_calibrated_threshold(
            history_path=history,
            base_config_hash="h",
            dataset_span=("2026-01-01", "2026-12-31"),
            instrument="USD_JPY",
            stage_gate_version="v3",
        )
        assert result == -0.05

    def test_skip_when_schema_version_missing(self, tmp_path: Path) -> None:
        """旧 record (schema_version 欄なし) は適用対象外 (fail-closed)."""
        history = tmp_path / "history.jsonl"
        rec = _make_record(
            base_hash="h",
            dataset_span=["2026-01-01", "2026-12-31"],
            instrument="USD_JPY",
            stage_gate_version="v3",
        )
        del rec["schema_version"]
        _write_history([rec], history)
        result = load_calibrated_threshold(
            history_path=history,
            base_config_hash="h",
            dataset_span=("2026-01-01", "2026-12-31"),
            instrument="USD_JPY",
            stage_gate_version="v3",
        )
        assert result is None

    def test_skip_when_threshold_non_finite(self, tmp_path: Path) -> None:
        """new_threshold が NaN/inf → skip (manually-crafted record で検証)."""
        history = tmp_path / "history.jsonl"
        # NaN を含む raw record を直書き (json.dumps では encode 不能)
        history.parent.mkdir(parents=True, exist_ok=True)
        line = (
            '{"run_id": "x", "applied_at": "2026-04-27T00:00:00", '
            '"new_threshold": NaN, "schema_version": '
            + str(SCHEMA_VERSION)
            + ', "base_config_hash": "h", '
            '"full_config_hash": "fff", '
            '"dataset_span": ["2026-01-01", "2026-12-31"], '
            '"instrument": "USD_JPY", "stage_gate_version": "v3", '
            '"decision": "tighten", "applied_from_run_id": "x"}\n'
        )
        history.write_text(line, encoding="utf-8")
        # Note: NaN は json.loads では parse 不可 (RFC 7159 違反) なので
        # _iter_history_records が JSONDecodeError で skip する。
        # → 結果として None が返ることが期待値。
        result = load_calibrated_threshold(
            history_path=history,
            base_config_hash="h",
            dataset_span=("2026-01-01", "2026-12-31"),
            instrument="USD_JPY",
            stage_gate_version="v3",
        )
        assert result is None

    def test_skip_when_threshold_out_of_range(self, tmp_path: Path) -> None:
        """new_threshold が floor/ceiling 外 → skip."""
        history = tmp_path / "history.jsonl"
        rec = _make_record(
            new_threshold=200.0,  # > default ceiling 100
            base_hash="h",
            dataset_span=["2026-01-01", "2026-12-31"],
            instrument="USD_JPY",
            stage_gate_version="v3",
        )
        _write_history([rec], history)
        result = load_calibrated_threshold(
            history_path=history,
            base_config_hash="h",
            dataset_span=("2026-01-01", "2026-12-31"),
            instrument="USD_JPY",
            stage_gate_version="v3",
        )
        assert result is None

    def test_returns_latest_record_when_multiple_match(
        self, tmp_path: Path
    ) -> None:
        """複数 record が match → 最新 (applied_at で降順) を採用."""
        history = tmp_path / "history.jsonl"
        rec_old = _make_record(
            new_threshold=0.10,
            base_hash="h",
            dataset_span=["2026-01-01", "2026-12-31"],
            instrument="USD_JPY",
            stage_gate_version="v3",
            applied_at="2026-04-26T17:45:00+00:00",
        )
        rec_new = _make_record(
            new_threshold=0.20,
            base_hash="h",
            dataset_span=["2026-01-01", "2026-12-31"],
            instrument="USD_JPY",
            stage_gate_version="v3",
            applied_at="2026-04-26T20:42:00+00:00",
        )
        _write_history([rec_old, rec_new], history)
        result = load_calibrated_threshold(
            history_path=history,
            base_config_hash="h",
            dataset_span=("2026-01-01", "2026-12-31"),
            instrument="USD_JPY",
            stage_gate_version="v3",
        )
        assert result == 0.20

    def test_skip_when_applied_at_invalid(self, tmp_path: Path) -> None:
        """applied_at が ISO 8601 形式でない → skip."""
        history = tmp_path / "history.jsonl"
        rec = _make_record(
            base_hash="h",
            dataset_span=["2026-01-01", "2026-12-31"],
            instrument="USD_JPY",
            stage_gate_version="v3",
            applied_at="not-a-date",
        )
        _write_history([rec], history)
        result = load_calibrated_threshold(
            history_path=history,
            base_config_hash="h",
            dataset_span=("2026-01-01", "2026-12-31"),
            instrument="USD_JPY",
            stage_gate_version="v3",
        )
        assert result is None


class TestComputeConfigHash:
    def test_base_hash_is_deterministic(self, af_cfg) -> None:
        """同 cfg を 2 回 hash → 同値."""
        h1 = compute_base_config_hash(af_cfg)
        h2 = compute_base_config_hash(af_cfg)
        assert h1 == h2
        assert isinstance(h1, str)
        assert len(h1) == 64  # sha256 hex

    def test_full_hash_differs_from_base(self, af_cfg) -> None:
        """full_config_hash と base_config_hash は異なる (stage_a_threshold 含むか否か)."""
        base = compute_base_config_hash(af_cfg)
        full = compute_full_config_hash(af_cfg)
        assert base != full

    def test_base_hash_excludes_stage_a_threshold(self, af_cfg) -> None:
        """stage_a_threshold が変わっても base_config_hash は不変 (適応値除外)."""
        from dataclasses import replace

        h1 = compute_base_config_hash(af_cfg)
        cfg2 = replace(
            af_cfg,
            stage_gate=replace(af_cfg.stage_gate, stage_a_threshold=0.5),
        )
        h2 = compute_base_config_hash(cfg2)
        assert h1 == h2  # 適応値除外で不変

    def test_full_hash_changes_with_stage_a_threshold(self, af_cfg) -> None:
        """stage_a_threshold が変わると full_config_hash は変わる (監査用)."""
        from dataclasses import replace

        h1 = compute_full_config_hash(af_cfg)
        cfg2 = replace(
            af_cfg,
            stage_gate=replace(af_cfg.stage_gate, stage_a_threshold=0.5),
        )
        h2 = compute_full_config_hash(cfg2)
        assert h1 != h2

    def test_base_hash_changes_with_dataset(self, af_cfg) -> None:
        """dataset 変更で base_config_hash は変わる (cross-run guard が機能)."""
        from dataclasses import replace

        h1 = compute_base_config_hash(af_cfg)
        cfg2 = replace(
            af_cfg,
            dataset=replace(af_cfg.dataset, instrument="EUR_USD"),
        )
        h2 = compute_base_config_hash(cfg2)
        assert h1 != h2


class TestThresholdSourceCliOverridesHistory:
    """T054 詳細設計 §A: CLI override が history より優先 (test_threshold_source_cli_overrides_history)."""

    def test_threshold_source_cli_overrides_history(
        self, tmp_path: Path, af_cfg
    ) -> None:
        """history.jsonl に適用可能 record + CLI override → CLI 値が採用."""
        # imports inside test to avoid circular issues
        from scripts.alpha_factory.run_ga import _resolve_stage_a_threshold

        history = tmp_path / "history.jsonl"
        base_hash = compute_base_config_hash(af_cfg)
        rec = _make_record(
            new_threshold=0.0778,
            base_hash=base_hash,
            dataset_span=[str(af_cfg.dataset.start), str(af_cfg.dataset.end)],
            instrument=af_cfg.dataset.instrument,
            stage_gate_version="v3_stage_b_fold_min_trade_count",
        )
        _write_history([rec], history)
        # CLI override = 0.99 で history 値 0.0778 より優先される
        threshold, source = _resolve_stage_a_threshold(
            af_cfg,
            cli_override=0.99,
            history_path=history,
        )
        assert threshold == 0.99
        assert source == "cli"

    def test_history_used_when_no_cli_override(
        self, tmp_path: Path, af_cfg
    ) -> None:
        """CLI 未指定 + history 適用可能 → history 値."""
        from scripts.alpha_factory.run_ga import _resolve_stage_a_threshold

        history = tmp_path / "history.jsonl"
        base_hash = compute_base_config_hash(af_cfg)
        rec = _make_record(
            new_threshold=0.0778,
            base_hash=base_hash,
            dataset_span=[str(af_cfg.dataset.start), str(af_cfg.dataset.end)],
            instrument=af_cfg.dataset.instrument,
            stage_gate_version="v3_stage_b_fold_min_trade_count",
        )
        _write_history([rec], history)
        threshold, source = _resolve_stage_a_threshold(
            af_cfg,
            cli_override=None,
            history_path=history,
        )
        assert threshold == 0.0778
        assert source == "history"

    def test_config_used_when_no_cli_no_history(
        self, tmp_path: Path, af_cfg
    ) -> None:
        """CLI 未指定 + history 適用不可 → config 値."""
        from scripts.alpha_factory.run_ga import _resolve_stage_a_threshold

        history = tmp_path / "missing_history.jsonl"
        threshold, source = _resolve_stage_a_threshold(
            af_cfg,
            cli_override=None,
            history_path=history,
        )
        assert threshold == af_cfg.stage_gate.stage_a_threshold
        assert source == "config"
