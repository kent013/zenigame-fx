"""T058 PR 7: end-to-end integration tests for cascade port v2 contract.

詳細設計: devnotes/20260429-1912-todo-T058-schema-v2-contract/detailed-design.md
§ 施策 12 (行 1474-1483、 統合テスト) + DoD (行 1509-1538)。

PR 1-6 で個別 component (schema_contract / RunContext / config / archive /
calibrate / diagnostics / fsp / run_ga / sieve / Tier 2) ごとに unit / smoke
test を整備済。 PR 7 では cascade を end-to-end で実行 (= GenomeArchive +
calibrate_history + run_ga summary 構築 + Tier 2 display 4 scripts) して
``dataset_epoch_id`` が SSOT 経路を通って漏れなく伝搬することを検証する。

検証対象 (詳細設計 行 1478-1482、 4 ケース):
    1. ``test_end_to_end_writes_v2_archive_with_all_required_fields``
       — RunContext を GenomeArchive に注入 + flush → Parquet 読み戻しで
         genome_entry_schema_version=2 / dataset_epoch_id non-null /
         archive_role / source_stage 列の存在を確認。
    2. ``test_end_to_end_writes_v2_calibrate_history_with_dataset_epoch_id``
       — append_record で v2 HistoryRecord を JSONL に書込 → read_history
         で復元 → dataset_epoch_id 一致を確認。
    3. ``test_end_to_end_writes_v2_summary_json``
       — run_ga.py の smoke run を実行して summary.json に
         schema_version="1.1" + cascade_contract_version=2 +
         dataset_epoch_id (non-empty) が並存することを確認。
    4. ``test_end_to_end_propagates_epoch_id_to_tier2_outputs``
       — summary.json を Tier 2 display 4 scripts (extract_batch_metrics /
         generate_run_report / compare_batch_runs / analyze_run) に流し、
         warning を出さずに dataset_epoch_id が伝搬することを確認。

加えて FAIL_CLOSED mode で v1 artifact が期待通り fail することを 1 ケース
追加し、 DoD Config / Smoke DoD 行 1534 を満たす。
"""

from __future__ import annotations

import importlib.util
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from structlog.testing import capture_logs

import scripts.alpha_factory.run_ga as run_ga_module
from src.alpha_factory.archive import GenomeArchive
from src.alpha_factory.calibrate_gate_history import (
    HistoryRecord,
    append_record,
    read_history,
)
from src.alpha_factory.run_context import RunContext
from src.alpha_factory.schema_contract import (
    CALIBRATE_HISTORY_SCHEMA_VERSION,
    CASCADE_CONTRACT_VERSION,
    GENOME_ENTRY_SCHEMA_VERSION,
    SchemaEnforcementMode,
    SchemaVersionError,
)
from src.alpha_factory.stage_gate import StageResult
from src.dsl.genome import (
    ClauseConfig,
    Genome,
    PositionConfig,
    RiskConfig,
    SignalConfig,
)
from tests.scripts.test_alpha_factory_run_ga import (
    CONFIG_PATH,
    _generate_bar_rows,
    _install_mock_session,
    _make_currency_pair,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
EXTRACT_PATH = REPO_ROOT / "scripts" / "alpha_factory" / "extract_batch_metrics.py"
COMPARE_PATH = REPO_ROOT / "scripts" / "alpha_factory" / "compare_batch_runs.py"
GENERATE_PATH = REPO_ROOT / "scripts" / "alpha_factory" / "generate_run_report.py"
ANALYZE_PATH = REPO_ROOT / "scripts" / "alpha_factory" / "analyze_run.py"


# ---------------------------------------------------------------------------
# Module loading helper for display scripts (importlib による直接 load)
# ---------------------------------------------------------------------------


def _load_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# Genome / StageResult fixtures (test_archive と同型、 self-contained)
# ---------------------------------------------------------------------------


def _stub_genome(name: str = "g0_i0") -> Genome:
    clauses = (
        ClauseConfig(
            directional=(SignalConfig(name="F1", weight=1.0, params={}),),
            local_gate=(SignalConfig(name="M1", weight=0.5, params={}),),
            weight=1.0,
        ),
    )
    return Genome(
        name=name,
        units=1,
        clauses=clauses,
        position=PositionConfig(
            entry_threshold=0.5, exit_threshold=0.2, max_pos=1, time_stop_min=0
        ),
        risk=RiskConfig(stop_atr=1.0, take_atr=2.0),
    )


def _stage_a_result() -> StageResult:
    payload: dict[str, Any] = {
        "fitness_raw": 0.3,
        "fitness_pen": 0.27,
        "size_norm": 0.1,
        "alpha_a": 0.03,
        "threshold": 0.0,
        "trade_count": 25,
        "trade_sharpe_raw": 0.3,
        "active_clause": 1,
    }
    return StageResult(
        stage="A",
        passed=True,
        metrics={
            "stage": "A",
            "genome_name": "g0_i0",
            "n_bars": 60,
            "wall_time_seconds": 0.1,
            "payload": payload,
        },
    )


# ---------------------------------------------------------------------------
# 1. archive end-to-end (RunContext 注入 + flush + Parquet 読み戻し)
# ---------------------------------------------------------------------------


def test_end_to_end_writes_v2_archive_with_all_required_fields(
    tmp_path: Path,
) -> None:
    """RunContext 注入 + flush → Parquet 読み戻しで v2 必須 4 field を確認.

    詳細設計 行 1478-1479 (= 統合テスト 1 件目)。 検証点:
    - genome_entry_schema_version=2
    - dataset_epoch_id 列が non-null かつ grammar [a-z0-9_]+ 適合
    - archive_role / source_stage 列が schema に存在 (T058 段階では None default、
      T063-T066 で書込)
    - row が空 string 入りでも RunContext.dataset_epoch_id で fallback 補完 (
      archive.py 行 679-680 の SSOT 経路)
    - DoD 行 1532「v2 contract lint が log warning なしで通過」: flush 中に
      ``schema_contract.passive_validation_failed`` /
      ``schema_contract.invalid_epoch_id`` /
      ``archive.flush.schema_lint_summary`` 等の lint warning が一切発火しない
    """
    run_context = RunContext(
        run_id="run_t058_pr7_integration",
        run_number=99,
        dataset_epoch_id="epoch_2026_q1",
        base_config_hash="cfg_hash_e2e",
        instrument="EUR_JPY",
    )
    archive = GenomeArchive(
        run_id=run_context.run_id,
        run_number=run_context.run_number,
        run_context=run_context,
    )
    archive.collect_stage_a(
        _stub_genome(),
        "tier1_EUR_JPY",
        0,
        _stage_a_result(),
        instrument="EUR_JPY",
    )
    # PR 5 (archive.py 行 679-680) の RunContext fallback を試すため、
    # template default ("epoch_legacy") を空 string に上書きしてから flush
    row_key = ("tier1_EUR_JPY", 0, "g0_i0")
    archive._rows[row_key]["dataset_epoch_id"] = ""

    with capture_logs() as logs:
        out_path = archive.flush(tmp_path)
    assert out_path.exists(), "Parquet must be written"

    # DoD 行 1532: v2 contract lint warning が一切発火していないこと (LOG_ONLY
    # mode で v2 必須 field が全て揃った状態を end-to-end で検証する)
    archive_lint_events = {
        "schema_contract.passive_validation_failed",
        "schema_contract.invalid_epoch_id",
        "archive.flush.schema_lint_summary",
    }
    fired = [log for log in logs if log.get("event") in archive_lint_events]
    assert fired == [], (
        f"archive flush must not fire schema lint warnings in LOG_ONLY mode "
        f"when v2 contract is satisfied, but got: {fired}"
    )

    table = pq.read_table(out_path)
    columns = set(table.column_names)
    # v2 必須 4 field が schema 上に存在すること
    assert {
        "genome_entry_schema_version",
        "dataset_epoch_id",
        "archive_role",
        "source_stage",
    }.issubset(columns), f"v2 required fields missing from schema: {columns}"

    # 値検証 (= RunContext 経由の伝搬経路)
    rows = table.to_pylist()
    assert len(rows) == 1
    row = rows[0]
    assert row["genome_entry_schema_version"] == GENOME_ENTRY_SCHEMA_VERSION == 2
    # 空 string fallback → RunContext.dataset_epoch_id で補完
    assert row["dataset_epoch_id"] == "epoch_2026_q1"
    # archive_role / source_stage は T058 段階で None default (T063-T066 で書込)
    assert row["archive_role"] is None
    assert row["source_stage"] is None


def test_end_to_end_writes_v2_archive_keeps_template_stub_when_set(
    tmp_path: Path,
) -> None:
    """row が template default ("epoch_legacy") のまま flush された場合は、
    RunContext.dataset_epoch_id 値とは独立に "epoch_legacy" stub が保持される.

    archive.py の fallback ロジック (空/None のみ補完、 詳細設計 行 1130-1140)
    の SSOT 検証。 production smoke run では generate_epoch_id_stub も
    "epoch_legacy" を返すため両者は一致するが、 fallback の発火条件はあくまで
    empty/None。
    """
    run_context = RunContext(
        run_id="run_t058_pr7_stub_path",
        run_number=100,
        dataset_epoch_id="epoch_other_value",
        base_config_hash="cfg_hash_stub",
        instrument="EUR_JPY",
    )
    archive = GenomeArchive(
        run_id=run_context.run_id,
        run_number=run_context.run_number,
        run_context=run_context,
    )
    archive.collect_stage_a(
        _stub_genome(),
        "tier1_EUR_JPY",
        0,
        _stage_a_result(),
        instrument="EUR_JPY",
    )
    out_path = archive.flush(tmp_path)
    table = pq.read_table(out_path)
    rows = table.to_pylist()
    assert len(rows) == 1
    # template default はそのまま保持される (空/None でないため fallback しない)
    assert rows[0]["dataset_epoch_id"] == "epoch_legacy"


def test_end_to_end_archive_fail_closed_rejects_v1_archive(
    tmp_path: Path,
) -> None:
    """FAIL_CLOSED mode で v1 archive (genome_entry_schema_version 列無し) を
    検出した際に :class:`SchemaVersionError` が raise されることを確認.

    詳細設計 DoD 行 1534 (= enforcement_mode=fail_closed で v1 artifact が
    fail することの確認)。
    """
    # genome_entry_schema_version 列が無い v1 互換 Parquet を直接作る
    legacy_table = pa.Table.from_pylist(
        [{"individual_name": "legacy_g", "lane_id": "L1"}],
        schema=pa.schema(
            [
                pa.field("individual_name", pa.string(), nullable=False),
                pa.field("lane_id", pa.string(), nullable=False),
            ]
        ),
    )
    v1_path = tmp_path / "legacy_v1.parquet"
    pq.write_table(legacy_table, v1_path)

    with pytest.raises(SchemaVersionError):
        GenomeArchive.load(
            v1_path,
            mode=SchemaEnforcementMode.FAIL_CLOSED,
            return_schema_version=True,
        )


# ---------------------------------------------------------------------------
# 2. calibrate_history end-to-end (append_record → read_history)
# ---------------------------------------------------------------------------


def test_end_to_end_writes_v2_calibrate_history_with_dataset_epoch_id(
    tmp_path: Path,
) -> None:
    """append_record で v2 HistoryRecord を JSONL に書込 → read_history で
    復元 → dataset_epoch_id 一致を確認.

    詳細設計 行 1480 (= 統合テスト 2 件目)。
    """
    history_path = tmp_path / "history.jsonl"
    record = HistoryRecord(
        run_id="run_t058_pr7_calibrate",
        applied_at="2026-04-30T12:34:56+09:00",
        n_rows_total=96,
        n_rows_used=80,
        aggregation_mode="last_k_generations",
        aggregation_window=5,
        actual_pass_rate=0.18,
        target_pass_rate=0.15,
        tol=0.05,
        prev_threshold=0.10,
        new_threshold=0.12,
        delta=0.02,
        decision="tighten",
        var_fitness_pen=0.01,
        clamped_by_delta=False,
        clamped_by_floor_or_ceiling=False,
        stage_b_pass_count=3,
        stage_c_pass_count=1,
        live_criteria_gap={"sharpe": 0.0, "total_pnl": 0.0},
        dataset_epoch_id="epoch_2026_q1",
    )

    append_record(record, history_path)
    assert history_path.exists()

    # JSONL の生 dict が v2 必須 field を含むこと (file 永続層の検証)
    raw_lines = history_path.read_text(encoding="utf-8").splitlines()
    assert len(raw_lines) == 1
    raw_obj = json.loads(raw_lines[0])
    assert (
        raw_obj["calibrate_history_schema_version"]
        == CALIBRATE_HISTORY_SCHEMA_VERSION
        == 2
    )
    assert raw_obj["dataset_epoch_id"] == "epoch_2026_q1"

    # read_history 経由で v2 record が復元できること
    loaded = read_history(history_path)
    assert len(loaded) == 1
    assert loaded[0].run_id == "run_t058_pr7_calibrate"
    assert loaded[0].dataset_epoch_id == "epoch_2026_q1"
    assert (
        loaded[0].calibrate_history_schema_version
        == CALIBRATE_HISTORY_SCHEMA_VERSION
    )

    # v1 record (dataset_epoch_id 不在) を後ろに付け加えて、 read_history が
    # warning + skip すること (詳細設計 § 施策 5)
    v1_obj = {
        "run_id": "run_v1_legacy",
        "applied_at": "2026-03-15T00:00:00+09:00",
        "n_rows_total": 96,
        "n_rows_used": 80,
        "aggregation_mode": "last_k_generations",
        "aggregation_window": 5,
        "actual_pass_rate": 0.20,
        "target_pass_rate": 0.15,
        "tol": 0.05,
        "prev_threshold": 0.10,
        "new_threshold": 0.10,
        "delta": 0.0,
        "decision": "in_band",
        "var_fitness_pen": 0.0,
        "clamped_by_delta": False,
        "clamped_by_floor_or_ceiling": False,
        "stage_b_pass_count": 0,
        "stage_c_pass_count": 0,
        "live_criteria_gap": {},
        # dataset_epoch_id / calibrate_history_schema_version 不在 (v1)
    }
    with history_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(v1_obj) + "\n")

    with capture_logs() as logs:
        loaded_with_v1 = read_history(history_path)
    assert len(loaded_with_v1) == 1, "v1 record must be skipped"
    assert any(
        log.get("event")
        == "calibrate_history.v1_or_invalid_record_skipped"
        for log in logs
    )


# ---------------------------------------------------------------------------
# 3. summary.json end-to-end (run_ga smoke + 全 v2 field 検証)
# ---------------------------------------------------------------------------


def _setup_smoke_env(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    sub_dir: str,
) -> Path:
    """smoke run の出力 root を返す."""
    from src.alpha_factory.archive import GenomeArchive as _Archive

    pair = _make_currency_pair("EUR_JPY")
    start = datetime(2026, 1, 1, tzinfo=UTC)
    end = datetime(2026, 1, 8, tzinfo=UTC)
    stage_b_rows = _generate_bar_rows(pair, start, end, step_minutes=60)
    holdout_rows = _generate_bar_rows(
        pair, end, end + timedelta(days=1), step_minutes=60,
    )
    _install_mock_session(
        monkeypatch, pair, stage_b_rows, holdout_rows,
        datetime(2026, 1, 8, tzinfo=UTC),
    )
    out_root = tmp_path / sub_dir
    monkeypatch.setattr(run_ga_module, "RUN_REPORTS_DIR", out_root / "reports")
    monkeypatch.setattr(run_ga_module, "RUN_CACHE_DIR", out_root / "cache")
    monkeypatch.setattr(run_ga_module, "get_latest_run_number", lambda: 0)
    monkeypatch.setattr(_Archive, "DEFAULT_OUTPUT_DIR", out_root / "archive")
    return out_root


def test_end_to_end_writes_v2_summary_json(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """run_ga の smoke run で summary.json が schema_version="1.1" +
    cascade_contract_version=2 + dataset_epoch_id (non-empty) を含むこと.

    詳細設計 行 1481 (= 統合テスト 3 件目)。
    """
    out_root = _setup_smoke_env(monkeypatch, tmp_path, sub_dir="summary_e2e")
    rc = run_ga_module.main(
        [
            "--config", str(CONFIG_PATH),
            "--run-id", "run_t058_pr7_summary_e2e",
            "--population-size", "4",
            "--generations", "1",
            "--seed", "42",
            "--max-workers", "1",
        ]
    )
    assert rc == 0

    run_dir = out_root / "reports" / "run-1"
    summary = json.loads(
        (run_dir / "summary.json").read_text(encoding="utf-8")
    )
    # v2 trio (schema_version は string "1.1" のまま、 cascade_contract_version
    # は int=2、 dataset_epoch_id は non-empty で grammar [a-z0-9_]+ に適合)
    assert summary["schema_version"] == "1.1"
    assert isinstance(summary["schema_version"], str)
    assert summary["cascade_contract_version"] == CASCADE_CONTRACT_VERSION == 2
    assert isinstance(summary["cascade_contract_version"], int)
    assert not isinstance(
        summary["cascade_contract_version"], bool
    ), "int subclass bool は除外する"
    epoch_id = summary["dataset_epoch_id"]
    assert isinstance(epoch_id, str) and epoch_id, (
        "dataset_epoch_id must be a non-empty string"
    )
    # T058 段階 stub なので "epoch_legacy" になることを確認 (T059 で
    # deterministic 値に置換される)
    assert epoch_id == "epoch_legacy"

    # 派生 artifact (history.json / best_genome.json) にも propagate していること
    history = json.loads((run_dir / "history.json").read_text(encoding="utf-8"))
    assert history, "history.json must be non-empty"
    for entry in history:
        assert entry["dataset_epoch_id"] == "epoch_legacy"

    best_genome = json.loads(
        (run_dir / "best_genome.json").read_text(encoding="utf-8")
    )
    assert best_genome["dataset_epoch_id"] == "epoch_legacy"


# ---------------------------------------------------------------------------
# 4. Tier 2 display 4 scripts への propagation
# ---------------------------------------------------------------------------


def _write_summary_for_display(
    run_dir: Path,
    *,
    run_id: str,
    run_number: int,
    dataset_epoch_id: str,
) -> None:
    """display 4 scripts に流すための summary.json を書き出す."""
    run_dir.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {
        "schema_version": "1.1",
        "cascade_contract_version": 2,
        "dataset_epoch_id": dataset_epoch_id,
        "run_id": run_id,
        "run_number": run_number,
        "generated_at": "2026-04-30T12:00:00+00:00",
        "dataset": {
            "instrument": "EUR_JPY",
            "start": "2026-03-01",
            "end": "2026-03-15",
            "bars": 14000,
        },
        "ga_config": {
            "population_size": 96,
            "generations": 60,
            "mutation_rate": 0.3,
            "crossover_rate": 0.7,
            "fitness_metric": "sharpe",
            "seed": 42,
        },
        "best": {
            "name": "g60_i00",
            "generation": 60,
            "fitness": "1.5",
            "fitness_finite": True,
            "stage_a_pass": True,
            "stage_b_pass": True,
            "stage_c_pass": True,
            "metrics": {
                "total_pnl": "1234.5",
                "sharpe": "2.0",
                "max_drawdown_pct": "0.1",
                "trade_count": 100,
                "win_rate": "0.55",
            },
        },
        "live_criteria": {
            "checks": {
                "sharpe": {"value": "2.0", "threshold": "1.0", "pass": True},
                "trade_count": {
                    "value": 100,
                    "threshold_min": 50,
                    "threshold_max": 5000,
                    "pass": True,
                },
            },
            "all_pass": True,
        },
        "graduation_count": 1,
    }
    (run_dir / "summary.json").write_text(
        json.dumps(payload), encoding="utf-8"
    )


def _write_history_for_display(run_dir: Path) -> None:
    history = [
        {"generation": 1, "best_fitness": "1.0"},
        {"generation": 2, "best_fitness": "1.5"},
    ]
    (run_dir / "history.json").write_text(
        json.dumps(history), encoding="utf-8"
    )


def test_end_to_end_propagates_epoch_id_to_tier2_outputs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """summary.json を Tier 2 display 4 scripts に流したとき、
    ``schema_contract.tier2_epoch_id_missing`` warning が出ずに
    ``dataset_epoch_id`` が出力 artifact に伝搬すること.

    詳細設計 行 1482 (= 統合テスト 4 件目)。
    """
    extract_mod = _load_module("_extract_t058_pr7", EXTRACT_PATH)
    compare_mod = _load_module("_compare_t058_pr7", COMPARE_PATH)
    generate_mod = _load_module("_generate_t058_pr7", GENERATE_PATH)
    analyze_mod = _load_module("_analyze_t058_pr7", ANALYZE_PATH)

    epoch_id = "epoch_2026_pr7_e2e"
    run_reports = tmp_path / "reports" / "run-reports"
    run_dir = run_reports / "run-5"
    _write_summary_for_display(
        run_dir,
        run_id="run_T058_PR7",
        run_number=5,
        dataset_epoch_id=epoch_id,
    )
    _write_history_for_display(run_dir)

    # 各 script の REPO_ROOT / RUN_REPORTS_DIR を tmp_path に向ける
    for mod in (extract_mod, compare_mod, generate_mod, analyze_mod):
        if hasattr(mod, "REPO_ROOT"):
            monkeypatch.setattr(mod, "REPO_ROOT", tmp_path)
        if hasattr(mod, "RUN_REPORTS_DIR"):
            monkeypatch.setattr(mod, "RUN_REPORTS_DIR", run_reports)

    # 4 scripts を順に実行し、 tier2 missing warning が出ないことを 1 回で確認
    with capture_logs() as logs:
        # generate_run_report
        rc = generate_mod.main(["--run-number", "5"])
        assert rc == 0
        run_report_md = (run_reports / "run-5.md").read_text(encoding="utf-8")
        assert epoch_id in run_report_md

        # analyze_run
        analyze_tmp = tmp_path / "tmp_analyze"
        rc = analyze_mod.main(["--run-number", "5", "--tmp-dir", str(analyze_tmp)])
        assert rc == 0
        analyze_md = (analyze_tmp / "analysis-claude.md").read_text(encoding="utf-8")
        assert epoch_id in analyze_md

        # extract_batch_metrics (JSON + report.md 両方)
        extract_json = tmp_path / "out" / "metrics.json"
        extract_md = tmp_path / "out" / "metrics.md"
        rc = extract_mod.main([
            "run_T058_PR7",
            "--output", str(extract_json),
            "--report", str(extract_md),
        ])
        assert rc == 0
        extract_data = json.loads(extract_json.read_text(encoding="utf-8"))
        assert extract_data["dataset_epoch_id"] == epoch_id
        extract_md_text = extract_md.read_text(encoding="utf-8")
        assert epoch_id in extract_md_text

        # compare_batch_runs は metrics 集合を batch_dir 配下に置いて実行
        batch_dir = tmp_path / "batch_001"
        metrics_dir = batch_dir / "metrics"
        metrics_dir.mkdir(parents=True)
        (metrics_dir / "r1.json").write_text(
            json.dumps({
                "run_id": "run_T058_PR7",
                "run_number": 5,
                "dataset_epoch_id": epoch_id,
                "best": {
                    "name": "g60_i00",
                    "generation": 60,
                    "fitness": 1.5,
                    "sharpe": 2.0,
                    "trade_count": 100,
                    "total_pnl": 1234.5,
                    "max_drawdown_pct": 0.1,
                    "win_rate": 0.55,
                    "profit_factor": 1.2,
                    "stage_a_pass": True,
                    "stage_b_pass": True,
                    "stage_c_pass": True,
                },
                "stage_pass": {
                    "stage_a_pass": 10,
                    "stage_b_pass": 5,
                    "stage_c_pass": 1,
                    "total": 16,
                },
                "best_b_sharpe": 2.0,
                "best_c_sharpe": 1.8,
                "live_criteria_all_pass": True,
                "live_criteria_failed": [],
                "graduation_count": 1,
            }),
            encoding="utf-8",
        )
        rc = compare_mod.main(["--batch-dir", str(batch_dir)])
        assert rc == 0
        batch_summary = json.loads(
            (batch_dir / "batch_summary.json").read_text(encoding="utf-8")
        )
        assert batch_summary["dataset_epoch_ids"] == [epoch_id]
        comparison_md = (batch_dir / "comparison_report.md").read_text(
            encoding="utf-8"
        )
        assert epoch_id in comparison_md

    # warning が一切発火していないこと (= upstream で SSOT 経由の伝搬が完了し、
    # Tier 2 軽量ガードが noop で抜けたことを示す)
    tier2_warnings = [
        log
        for log in logs
        if log.get("event") == "schema_contract.tier2_epoch_id_missing"
    ]
    assert tier2_warnings == [], (
        f"Tier 2 missing warning should not fire when summary has epoch_id, "
        f"but got: {tier2_warnings}"
    )


# ---------------------------------------------------------------------------
# Cross-cutting: T058 PR 7 で touch する Run-level 全 component が
# RunContext を共有することの一気通貫確認 (行 1533 補強)
# ---------------------------------------------------------------------------


def test_run_context_is_propagated_to_archive_and_diagnostics_components(
    tmp_path: Path,
) -> None:
    """RunContext が archive (collect/flush) と diagnostics_sidecar
    (build_sidecar_table) の双方で使われ、 同一 dataset_epoch_id が
    両 artifact に書き込まれることを確認.

    詳細設計 DoD 行 1533 (= RunContext が archive / calibrate / diagnostics
    の主要 3 component に注入されている) を 1 ケースで end-to-end 検証する。
    """
    from src.alpha_factory.diagnostics_collector import DiagnosticsCollector
    from src.alpha_factory.diagnostics_sidecar import (
        build_sidecar_table,
        write_stage_a_provenance,
    )

    epoch_id = "epoch_shared_v2"
    run_context = RunContext(
        run_id="run_t058_pr7_shared",
        run_number=42,
        dataset_epoch_id=epoch_id,
        base_config_hash="cfg_shared",
        instrument="EUR_JPY",
    )

    # archive に注入
    archive = GenomeArchive(
        run_id=run_context.run_id,
        run_number=run_context.run_number,
        run_context=run_context,
    )
    archive.collect_stage_a(
        _stub_genome(),
        "tier1_EUR_JPY",
        0,
        _stage_a_result(),
        instrument="EUR_JPY",
    )
    # template default ("epoch_legacy") を空 string に上書きして RunContext
    # fallback 経路を発火させる (archive.py 行 679-680)
    archive._rows[("tier1_EUR_JPY", 0, "g0_i0")]["dataset_epoch_id"] = ""
    archive_path = archive.flush(tmp_path)
    archive_table = pq.read_table(archive_path)
    assert archive_table.to_pylist()[0]["dataset_epoch_id"] == epoch_id

    # diagnostics_sidecar に注入 (collector は最低限 1 row 入れる)
    collector = DiagnosticsCollector()
    collector.record_stage_a(
        lane_id="tier1_EUR_JPY",
        generation=0,
        individual_name="g0_i0",
        result=_stage_a_result(),
    )
    sidecar_path = tmp_path / "diagnostics" / "stage_a_provenance.parquet"
    written = write_stage_a_provenance(
        collector, sidecar_path, run_context=run_context
    )
    assert written == sidecar_path
    sidecar_table = pq.read_table(sidecar_path)
    rows = sidecar_table.to_pylist()
    assert rows
    for row in rows:
        assert row["dataset_epoch_id"] == epoch_id

    # build_sidecar_table 直呼び (run_context propagate path 確認)
    direct_table = build_sidecar_table(
        collector.to_rows(), run_context=run_context
    )
    direct_rows = direct_table.to_pylist()
    assert direct_rows
    for row in direct_rows:
        assert row["dataset_epoch_id"] == epoch_id
