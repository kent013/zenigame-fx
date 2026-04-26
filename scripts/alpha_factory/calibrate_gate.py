"""Stage A threshold deterministic 動的調整 CLI (T027)。

設計:
    - devnotes/20260424-1759-port-calibrate-gate/conceptual-design.md
    - devnotes/20260424-1759-port-calibrate-gate/detailed-design.md

使い方:
    uv run python scripts/alpha_factory/calibrate_gate.py \\
        [--run-id RUN_ID] \\
        [--config-path PATH] \\
        [--dry-run] \\
        [--archive-dir PATH]

exit code:
    0  成功 (in_band / tighten / loosen)
    2  invalid arg
    3  no archive (auto-detect も指定 run-id も無し)
    4  calibrate disabled
    5  io error
    6  sample size insufficient
    7  zero variance
    8  schema mismatch
"""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import sys
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq
import structlog
from ruamel.yaml import YAML

# repo root に load path を通す
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from datetime import UTC  # noqa: E402

from src.alpha_factory.calibrate_gate import (  # noqa: E402
    CalibrateConfig,
    ConfigError,
    Decision,
    SchemaMismatchError,
    aggregate_sample,
    compute_monitoring,
    decide,
    load_calibrate_config,
    validate_schema,
)
from src.alpha_factory.calibrate_gate_history import (  # noqa: E402
    DEFAULT_HISTORY_PATH,
    HistoryRecord,
    append_record,
)

logger = structlog.get_logger("calibrate_gate")

DEFAULT_ARCHIVE_DIR = REPO_ROOT / ".cache" / "alpha_factory" / "runs"
DEFAULT_CONFIG_PATH = REPO_ROOT / "config" / "alpha_factory" / "default.yaml"

EXIT_OK = 0
EXIT_INVALID_ARG = 2
EXIT_NO_ARCHIVE = 3
EXIT_DISABLED = 4
EXIT_IO_ERROR = 5
EXIT_SAMPLE_SIZE = 6
EXIT_ZERO_VARIANCE = 7
EXIT_SCHEMA_MISMATCH = 8


# ---------------------------------------------------------------------------
# Atomic yaml writer (一意 tmp 名 + flock)
# ---------------------------------------------------------------------------


@contextmanager
def yaml_writer_lock(yaml_path: Path) -> Iterator[None]:
    """advisory file lock (POSIX flock)。Linux/macOS で動作。"""
    lock_path = yaml_path.with_suffix(yaml_path.suffix + ".lock")
    with lock_path.open("w") as lock_fd:
        fcntl.flock(lock_fd.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock_fd.fileno(), fcntl.LOCK_UN)


def update_threshold_atomic(yaml_path: Path, new_threshold: float) -> None:
    """``stage_gate.stage_a.threshold`` を atomic に更新する。

    一意 tmp 名 + flock + os.replace で同時実行衝突 / 中断耐性を確保する。
    """
    with yaml_writer_lock(yaml_path):
        yaml = YAML()
        yaml.preserve_quotes = True
        with yaml_path.open("r", encoding="utf-8") as f:
            data = yaml.load(f)

        data["stage_gate"]["stage_a"]["threshold"] = float(new_threshold)

        tmp_fd, tmp_str = tempfile.mkstemp(
            prefix=f"{yaml_path.name}.",
            suffix=".tmp",
            dir=str(yaml_path.parent),
        )
        tmp_path = Path(tmp_str)
        try:
            with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
                yaml.dump(data, f)
            with tmp_path.open("r", encoding="utf-8") as f:
                verify = yaml.load(f)
            v = verify["stage_gate"]["stage_a"]["threshold"]
            if not isinstance(v, float) or abs(v - new_threshold) > 1e-9:
                raise ValueError(
                    f"verify failed: written={v} expected={new_threshold}"
                )
            os.replace(tmp_path, yaml_path)
        except Exception:
            if tmp_path.exists():
                tmp_path.unlink(missing_ok=True)
            raise


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _resolve_parquet_path(archive_dir: Path, run_id: str | None) -> Path | None:
    """``--run-id`` 指定 / 省略 (latest auto-detect) で Parquet path を解決。

    Returns:
        Path or None (no archive)。
    """
    if run_id is not None:
        candidate = archive_dir / f"genomes_{run_id}.parquet"
        return candidate if candidate.exists() else None
    files = sorted(
        archive_dir.glob("genomes_run_*.parquet"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return files[0] if files else None


def _emit(event: str, **fields: Any) -> None:
    """JSONL ログを stderr に出力。"""
    payload = {"event": event, **fields}
    print(json.dumps(payload, ensure_ascii=False, default=str), file=sys.stderr)


def _format_report(
    run_id: str,
    config: CalibrateConfig,
    sample: Any,
    decision: Decision,
    monitoring: Any,
    dry_run: bool,
) -> str:
    """human-readable 報告を組み立てる。"""
    rep = []
    rep.append("## Stage A Gate Calibration\n")
    rep.append("| 項目 | 値 |")
    rep.append("|------|----|")
    rep.append(f"| Run ID | {run_id} |")
    rep.append(
        f"| Aggregation | {config.aggregation_mode} / "
        f"window={config.aggregation_window} |"
    )
    rep.append(
        f"| 集計対象行 | {sample.n_rows_used} / {sample.n_rows_total} |"
    )
    rep.append(f"| Stage A pass | {sample.pass_count_used} |")
    rep.append(f"| 実 pass rate | {sample.actual_pass_rate:.3f} |")
    rep.append(
        f"| Target pass rate | {config.target_pass_rate:.3f} ± "
        f"{config.pass_rate_tolerance_abs:.3f} |"
    )
    rep.append(f"| 前 threshold | {config.prev_threshold} |")
    if decision.q_target is not None:
        rep.append(f"| 提案 q_target | {decision.q_target:.4f} |")
    rep.append(
        f"| delta | {decision.delta:+.4f} "
        f"(clamped_by_delta={decision.clamped_by_delta}, "
        f"clamped_by_floor_or_ceiling={decision.clamped_by_floor_or_ceiling}) |"
    )
    rep.append(f"| **新 threshold** | **{decision.new_threshold}** |")
    rep.append(f"| 決定 | {decision.decision} |")
    rep.append(f"| dry-run | {dry_run} |")
    rep.append("")
    rep.append("### Monitoring (informational, 因果解釈禁止)")
    rep.append(f"- Stage B pass: {monitoring.stage_b_pass_count}")
    rep.append(f"- Stage C pass: {monitoring.stage_c_pass_count}")
    rep.append(f"- best sharpe: {monitoring.best_sharpe}")
    rep.append(f"- best total_pnl: {monitoring.best_total_pnl}")
    rep.append(f"- best max_dd_pct: {monitoring.best_max_drawdown_pct}")
    rep.append(f"- best trade_count: {monitoring.best_trade_count}")
    rep.append(f"- live_criteria_gap: {monitoring.live_criteria_gap}")
    return "\n".join(rep)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Stage A threshold deterministic 動的調整 (T027)"
    )
    parser.add_argument(
        "--run-id",
        type=str,
        default=None,
        help="archive run_id (省略時は最新 Parquet を自動選択)",
    )
    parser.add_argument(
        "--config-path",
        type=Path,
        default=DEFAULT_CONFIG_PATH,
        help=f"yaml path (default: {DEFAULT_CONFIG_PATH})",
    )
    parser.add_argument(
        "--archive-dir",
        type=Path,
        default=DEFAULT_ARCHIVE_DIR,
        help=f"archive Parquet dir (default: {DEFAULT_ARCHIVE_DIR})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="提案出力のみで yaml を更新しない",
    )
    args = parser.parse_args(argv)

    # ---- yaml load + config 構築 ----
    try:
        yaml_loader = YAML()
        yaml_loader.preserve_quotes = True
        with args.config_path.open("r", encoding="utf-8") as f:
            yaml_data = yaml_loader.load(f)
        live_criteria = yaml_data.get("live_criteria", {})
        config = load_calibrate_config(yaml_data)
    except FileNotFoundError as e:
        print(f"[error] config file not found: {args.config_path} ({e})", file=sys.stderr)
        return EXIT_IO_ERROR
    except ConfigError as e:
        print(f"[error] config error: {e}", file=sys.stderr)
        return EXIT_IO_ERROR
    except Exception as e:
        print(f"[error] yaml load error: {e}", file=sys.stderr)
        return EXIT_IO_ERROR

    if not config.enabled:
        _emit("calibrate_gate.disabled", config_path=str(args.config_path))
        print("calibrate.enabled=false, skipping", file=sys.stderr)
        return EXIT_DISABLED

    # ---- Parquet path 解決 ----
    parquet_path = _resolve_parquet_path(args.archive_dir, args.run_id)
    if parquet_path is None:
        if args.run_id is not None:
            print(
                f"run-id specified but file not found: "
                f"{args.archive_dir / f'genomes_{args.run_id}.parquet'}",
                file=sys.stderr,
            )
        else:
            print(f"no parquet found in {args.archive_dir}", file=sys.stderr)
        return EXIT_NO_ARCHIVE

    run_id_resolved = parquet_path.stem.replace("genomes_", "")

    # ---- Parquet load + schema check ----
    try:
        table = pq.read_table(parquet_path)
        validate_schema(table)
    except SchemaMismatchError as e:
        print(f"[error] schema mismatch: {e}", file=sys.stderr)
        _emit(
            "calibrate_gate.schema_mismatch",
            run_id=run_id_resolved,
            error=str(e),
        )
        return EXIT_SCHEMA_MISMATCH
    except Exception as e:
        print(f"[error] parquet read error: {e}", file=sys.stderr)
        return EXIT_IO_ERROR

    rows = table.to_pylist()

    # ---- aggregate / monitoring / decide ----
    sample = aggregate_sample(
        rows,
        mode=config.aggregation_mode,
        window=config.aggregation_window,
    )
    monitoring = compute_monitoring(rows, live_criteria=live_criteria)
    decision = decide(sample, config)

    _emit(
        "calibrate_gate.input",
        run_id=run_id_resolved,
        n_rows_total=sample.n_rows_total,
        n_rows_used=sample.n_rows_used,
        aggregation_mode=sample.mode,
        aggregation_window=sample.window,
        stage_a_pass_used=sample.pass_count_used,
        actual=sample.actual_pass_rate,
        target=config.target_pass_rate,
        tol=config.pass_rate_tolerance_abs,
        prev_threshold=config.prev_threshold,
    )
    _emit(
        "calibrate_gate.monitoring",
        stage_b_pass_count=monitoring.stage_b_pass_count,
        stage_c_pass_count=monitoring.stage_c_pass_count,
        best_sharpe=monitoring.best_sharpe,
        best_total_pnl=monitoring.best_total_pnl,
        best_max_drawdown_pct=monitoring.best_max_drawdown_pct,
        best_trade_count=monitoring.best_trade_count,
        live_criteria_gap=monitoring.live_criteria_gap,
    )
    _emit(
        "calibrate_gate.decision",
        decision=decision.decision,
        new_threshold=decision.new_threshold,
        delta=decision.delta,
        q_target=decision.q_target,
        var_fitness_pen=decision.var_fitness_pen,
        clamped_by_delta=decision.clamped_by_delta,
        clamped_by_floor_or_ceiling=decision.clamped_by_floor_or_ceiling,
        effective_sample_size=decision.effective_sample_size,
    )

    # ---- yaml 更新（必要時のみ） ----
    needs_write = decision.decision in {"tighten", "loosen"} and not args.dry_run
    if needs_write:
        try:
            update_threshold_atomic(args.config_path, decision.new_threshold)
        except Exception as e:
            print(f"[error] yaml write error: {e}", file=sys.stderr)
            _emit(
                "calibrate_gate.applied",
                yaml_path=str(args.config_path),
                applied=False,
                reason="io_error",
                dry_run=args.dry_run,
                new_threshold=decision.new_threshold,
            )
            return EXIT_IO_ERROR
        _emit(
            "calibrate_gate.applied",
            yaml_path=str(args.config_path),
            applied=True,
            reason="written",
            dry_run=False,
            new_threshold=decision.new_threshold,
        )
    else:
        # 監視・集計側が常に 4 イベント (input/monitoring/decision/applied) を
        # 期待できるように、書き込みなし経路でも applied=False を必ず emit する。
        if args.dry_run:
            reason = "dry_run"
        elif decision.decision == "in_band":
            reason = "in_band"
        elif decision.decision.startswith("skip_"):
            reason = decision.decision
        else:
            reason = "no_change"
        _emit(
            "calibrate_gate.applied",
            yaml_path=str(args.config_path),
            applied=False,
            reason=reason,
            dry_run=args.dry_run,
            new_threshold=decision.new_threshold,
        )

    # ---- T040: drift 監視用 JSONL 履歴に append (fail-open) ----
    # dry_run でも観察記録は残す (制御則は変えない、観察のみ)。
    try:
        from datetime import datetime
        record = HistoryRecord(
            run_id=run_id_resolved,
            applied_at=datetime.now(UTC).isoformat(),
            n_rows_total=sample.n_rows_total,
            n_rows_used=sample.n_rows_used,
            aggregation_mode=sample.mode,
            aggregation_window=sample.window,
            actual_pass_rate=sample.actual_pass_rate,
            target_pass_rate=config.target_pass_rate,
            tol=config.pass_rate_tolerance_abs,
            prev_threshold=config.prev_threshold,
            new_threshold=decision.new_threshold,
            delta=decision.delta,
            decision=decision.decision,
            var_fitness_pen=decision.var_fitness_pen,
            clamped_by_delta=decision.clamped_by_delta,
            clamped_by_floor_or_ceiling=decision.clamped_by_floor_or_ceiling,
            stage_b_pass_count=monitoring.stage_b_pass_count,
            stage_c_pass_count=monitoring.stage_c_pass_count,
            live_criteria_gap=monitoring.live_criteria_gap,
        )
        history_path = REPO_ROOT / DEFAULT_HISTORY_PATH
        append_record(record, history_path)
    except Exception as e:
        # fail-open: history 永続化エラーは calibrate-gate を止めない
        print(
            f"[warn] calibrate_gate.history append failed: {e}",
            file=sys.stderr,
        )

    # ---- human-readable report ----
    report = _format_report(
        run_id=run_id_resolved,
        config=config,
        sample=sample,
        decision=decision,
        monitoring=monitoring,
        dry_run=args.dry_run,
    )
    print(report)

    # ---- exit code mapping ----
    if decision.decision == "skip_sample_size":
        return EXIT_SAMPLE_SIZE
    if decision.decision == "skip_zero_variance":
        return EXIT_ZERO_VARIANCE
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
