"""B step 1.8 smoke 計測の集計 helper (= acceptance B2 / B3 merge gate).

詳細設計 § 12.3 SSOT。 ``measure_step1.8_memory.sh`` が出力する以下を併合し、
acceptance B2 / B3 merge gate 判定を表示する:

入力:
    - ``run-N.log`` — ``/usr/bin/time -l`` 由来の参考 RSS / wall time (補助指標)
    - ``sample-N.jsonl`` — psutil sampler 由来の per-worker RSS (主指標 SSOT)

出力指標 (= 詳細設計 § 12.3):
    - ``sampled_max_worker_rss`` (主条件): per-worker peak RSS の max
    - ``sampled_process_tree_rss_max`` (補助): process tree 合計 RSS の max
    - ``reference_peak_rss_max`` (補助、 macOS 依存): /usr/bin/time -l の RSS
    - ``wall_time_mean_per_run`` (B3): elapsed time の mean

merge gate:
    - B2 主条件: ``sampled_max_worker_rss < 3 GB``
    - B2 補助条件: ``sampled_process_tree_rss_max < 18 GB``
    - B3: ``wall_time_mean_per_run`` が step 1.7 比 ±20% 以内
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# psutil sampling 失敗時、 SSOT が verify できないため B2 INCONCLUSIVE.
B2_PRIMARY_GATE_BYTES = 3 * 1024 ** 3  # 3 GB / worker
B2_AUXILIARY_GATE_BYTES = 18 * 1024 ** 3  # 18 GB / process tree (= 6 worker × 3 GB)

# /usr/bin/time -l は macOS では bytes 単位で `maximum resident set size` を出す
_RE_MAX_RSS = re.compile(r"^\s*(\d+)\s+maximum resident set size", re.MULTILINE)
_RE_ELAPSED = re.compile(r"^\s*([\d.]+)\s+real", re.MULTILINE)


def _parse_time_log(log_path: Path) -> tuple[int | None, float | None]:
    """``/usr/bin/time -l`` 出力を parse して (peak_rss_bytes, elapsed_seconds)."""
    text = log_path.read_text(encoding="utf-8", errors="replace")
    rss_m = _RE_MAX_RSS.search(text)
    elapsed_m = _RE_ELAPSED.search(text)
    rss = int(rss_m.group(1)) if rss_m else None
    elapsed = float(elapsed_m.group(1)) if elapsed_m else None
    return rss, elapsed


def _parse_sampler_jsonl(
    jsonl_path: Path,
    *,
    expected_run_index: int | None = None,
) -> tuple[int | None, int | None, str | None]:
    """sample_worker_rss.py 出力 JSONL から (max_worker_rss, max_tree_rss, error) を集計.

    Codex impl-review Round 4 [Critical 2] + [Warning 2] 反映:
        - 1 行目の header (= ``_header=True``) で `run_index` を検証 (= stale file
          contamination guard、 過去 run の同名 sample-N.jsonl が残っていても
          現在の run-N.log と紐付けられない)
        - JSONDecodeError があれば failed 扱い (= SSOT 計測なら malformed line を
          見逃さない)

    Returns:
        (max_worker_rss, max_tree_rss, error_reason). 成功時は error_reason=None。
        失敗時 (header mismatch / JSONDecodeError / 0 sample / header 不在) は
        (None, None, "<reason>") を返す。
    """
    if not jsonl_path.exists():
        return None, None, "file_not_found"
    max_worker = 0
    max_tree = 0
    n_entries = 0
    header_seen = False
    with jsonl_path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                # malformed JSON は SSOT 違反 → failed (= Round 4 [Warning 2] 反映)
                return None, None, "json_decode_error"
            if entry.get("_header") is True:
                header_seen = True
                if expected_run_index is not None:
                    actual = entry.get("run_index")
                    if actual != expected_run_index:
                        return None, None, (
                            f"run_index_mismatch (expected={expected_run_index}, "
                            f"actual={actual})"
                        )
                continue
            n_entries += 1
            tree_max = int(entry.get("tree_max_rss_bytes", 0))
            tree_total = int(entry.get("tree_total_rss_bytes", 0))
            max_worker = max(max_worker, tree_max)
            max_tree = max(max_tree, tree_total)
    if not header_seen:
        # header 不在 = 古い形式 / sampler crash (= Round 4 [Critical 2] 反映、
        # stale file の可能性あり、 SSOT 違反として failed 扱い)
        return None, None, "header_missing"
    if n_entries == 0:
        return None, None, "no_data_samples"
    return max_worker, max_tree, None


def _format_gb(bytes_val: int | None) -> str:
    if bytes_val is None:
        return "N/A"
    return f"{bytes_val / 1024 ** 3:.3f} GB"


_RE_RUN_NUMBER = re.compile(r"run-(\d+)\.log$")
_RE_SAMPLE_NUMBER = re.compile(r"sample-(\d+)\.jsonl$")


def _extract_number(path: Path, pattern: re.Pattern[str]) -> str | None:
    match = pattern.search(path.name)
    if match is None:
        return None
    return match.group(1)


def aggregate(log_dir: Path) -> dict[str, object]:
    """N runs を併合する.

    Codex impl-review Round 3 [Critical] 反映: ``run-N.log`` と ``sample-N.jsonl`` の
    番号集合を突合し、 missing / parse 失敗の sample を全て ``sampler_failed_runs`` に
    含める (= 「一部 run だけ sampling 成功」 で B2 PASS させない SSOT 維持)。
    """
    run_logs = sorted(log_dir.glob("run-*.log"))
    sample_jsonls = sorted(log_dir.glob("sample-*.jsonl"))

    if not run_logs:
        raise FileNotFoundError(f"no run-*.log files in {log_dir}")

    run_numbers: set[str] = set()
    for log_path in run_logs:
        n = _extract_number(log_path, _RE_RUN_NUMBER)
        if n is not None:
            run_numbers.add(n)

    sample_numbers: set[str] = set()
    sample_path_by_number: dict[str, Path] = {}
    for sample_path in sample_jsonls:
        n = _extract_number(sample_path, _RE_SAMPLE_NUMBER)
        if n is not None:
            sample_numbers.add(n)
            sample_path_by_number[n] = sample_path

    reference_rss_list: list[int] = []
    elapsed_list: list[float] = []
    for log_path in run_logs:
        rss, elapsed = _parse_time_log(log_path)
        if rss is not None:
            reference_rss_list.append(rss)
        if elapsed is not None:
            elapsed_list.append(elapsed)

    sampled_worker_max_list: list[int] = []
    sampled_tree_max_list: list[int] = []
    sampler_failed_runs: list[str] = []
    expected_sample_files: list[str] = []
    missing_sample_files: list[str] = []

    # 全 run 番号に対応する sample が存在するか確認 (= 「一部 run だけ
    # sampling 成功」 を SSOT 違反として検出、 Round 3 [Critical] 反映)
    for run_n in sorted(run_numbers):
        expected_name = f"sample-{run_n}.jsonl"
        expected_sample_files.append(expected_name)
        sample_path_opt = sample_path_by_number.get(run_n)
        if sample_path_opt is None:
            missing_sample_files.append(expected_name)
            sampler_failed_runs.append(expected_name)
            continue
        # run_n は文字列なので int() で expected_run_index に渡す
        try:
            expected_idx: int | None = int(run_n)
        except ValueError:
            expected_idx = None
        worker_max, tree_max, error = _parse_sampler_jsonl(
            sample_path_opt, expected_run_index=expected_idx
        )
        if worker_max is None or tree_max is None:
            sampler_failed_runs.append(
                f"{sample_path_opt.name}:{error or 'unknown'}"
            )
            continue
        sampled_worker_max_list.append(worker_max)
        sampled_tree_max_list.append(tree_max)

    # run 番号と紐付かない余剰 sample (= sample-99.jsonl 等が偶発的にあるケース)
    for n in sorted(sample_numbers - run_numbers):
        sample_path = sample_path_by_number[n]
        sampler_failed_runs.append(f"unmatched:{sample_path.name}")

    summary: dict[str, object] = {
        "n_runs": len(run_logs),
        "n_samplers_succeeded": len(sampled_worker_max_list),
        "n_samplers_failed": len(sampler_failed_runs),
        "sampler_failed_files": sampler_failed_runs,
        "expected_sample_files": expected_sample_files,
        "missing_sample_files": missing_sample_files,
        "reference_peak_rss_max_bytes": max(reference_rss_list) if reference_rss_list else None,
        "reference_peak_rss_mean_bytes": (
            sum(reference_rss_list) // len(reference_rss_list)
            if reference_rss_list else None
        ),
        "sampled_max_worker_rss_bytes": (
            max(sampled_worker_max_list) if sampled_worker_max_list else None
        ),
        "sampled_process_tree_rss_max_bytes": (
            max(sampled_tree_max_list) if sampled_tree_max_list else None
        ),
        "wall_time_mean_seconds": (
            sum(elapsed_list) / len(elapsed_list) if elapsed_list else None
        ),
    }
    return summary


def _as_int(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    raise TypeError(f"_as_int: unexpected type {type(value).__name__}: {value!r}")


def _load_baseline_wall_time(baseline_dir: Path | None) -> float | None:
    """step 1.7 baseline directory から `wall_time_mean_seconds` を読む.

    詳細設計 § 12.3 / § 12.2 acceptance B3 の比較用 baseline。
    存在しない / parse 失敗時は None (= B3 INCONCLUSIVE)。
    """
    if baseline_dir is None or not baseline_dir.exists():
        return None
    try:
        baseline_summary = aggregate(baseline_dir)
    except (FileNotFoundError, ValueError):
        return None
    raw = baseline_summary.get("wall_time_mean_seconds")
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return float(raw)
    return None


def evaluate_gates(
    summary: dict[str, object],
    *,
    baseline_dir: Path | None = None,
    b3_tolerance: float = 0.20,
) -> dict[str, str]:
    """merge gate B2 / B3 を判定する.

    詳細設計 § 12.3 SSOT:
        - B2 主条件: ``sampled_max_worker_rss < 3 GB`` (= psutil sampling SSOT)
        - B2 補助条件: ``sampled_process_tree_rss_max < 18 GB``
        - B3: ``wall_time_mean_per_run`` が step 1.7 比 ±20% 以内

    Codex impl-review Round 2 [Critical] 反映:
        - sampling 欠損 (= sampled_tree is None) でも sampler 経路自体が失敗
          している場合は INCONCLUSIVE (= sampled_worker のみで PASS させない)
        - B3 実判定 (= baseline 不在時は INCONCLUSIVE で merge 失敗扱い)
    """
    gates: dict[str, str] = {}

    sampled_worker = _as_int(summary.get("sampled_max_worker_rss_bytes"))
    sampled_tree = _as_int(summary.get("sampled_process_tree_rss_max_bytes"))
    n_runs = _as_int(summary.get("n_runs")) or 0
    n_samplers_succeeded = _as_int(summary.get("n_samplers_succeeded")) or 0
    n_samplers_failed = _as_int(summary.get("n_samplers_failed")) or 0

    # sampling 経路の健全性 (= Round 2 [Critical 2] + Round 3 [Critical] 反映)
    # 全 run の sampling 成功 + 失敗 0 を要求する (= 「一部 run だけ sampling 成功」
    # で PASS させない SSOT 維持)
    sampling_healthy = (
        sampled_worker is not None
        and sampled_tree is not None
        and n_runs > 0
        and n_samplers_succeeded == n_runs
        and n_samplers_failed == 0
    )
    if not sampling_healthy:
        # sampling 欠損 → SSOT 未 verify → INCONCLUSIVE (= 暫定運用しない、
        # 全 run sampling 成功なしで PASS させない、 詳細設計 § 12.4 Case B)
        gates["B2"] = "INCONCLUSIVE"
    else:
        # 両指標が揃っているのみ PASS / FAIL を判定 (= sampled_worker / sampled_tree)
        assert sampled_worker is not None and sampled_tree is not None  # mypy guard
        if (
            sampled_worker < B2_PRIMARY_GATE_BYTES
            and sampled_tree < B2_AUXILIARY_GATE_BYTES
        ):
            gates["B2"] = "PASS"
        else:
            gates["B2"] = "FAIL"

    # B3 実判定 (= Round 2 [Critical 1] 反映)
    wall_time_raw = summary.get("wall_time_mean_seconds")
    wall_time = (
        float(wall_time_raw) if isinstance(wall_time_raw, (int, float)) else None
    )
    baseline_wall_time = _load_baseline_wall_time(baseline_dir)
    if wall_time is None or baseline_wall_time is None or baseline_wall_time <= 0:
        # baseline 不在 / 計測欠損 → SSOT 未 verify → INCONCLUSIVE (= merge 失敗扱い)
        gates["B3"] = "INCONCLUSIVE"
    else:
        ratio = wall_time / baseline_wall_time
        if abs(ratio - 1.0) <= b3_tolerance:
            gates["B3"] = "PASS"
        else:
            gates["B3"] = "FAIL"
    return gates


def main() -> int:
    parser = argparse.ArgumentParser(description="B step 1.8 smoke 計測集計")
    parser.add_argument("log_dir", type=Path, help="reports/smoke/step1.8/ 等")
    parser.add_argument(
        "--baseline-dir",
        type=Path,
        default=Path("reports/smoke/step1.7"),
        help="step 1.7 baseline directory (= acceptance B3 比較先、 default: reports/smoke/step1.7)",
    )
    parser.add_argument(
        "--b3-tolerance",
        type=float,
        default=0.20,
        help="acceptance B3 wall time 許容範囲 (default: 0.20 = ±20%%)",
    )
    args = parser.parse_args()

    summary = aggregate(args.log_dir)
    gates = evaluate_gates(
        summary, baseline_dir=args.baseline_dir, b3_tolerance=args.b3_tolerance
    )

    print("=== B step 1.8 smoke aggregate ===")
    print(f"n_runs: {summary['n_runs']}")
    print(f"sampler succeeded / failed: {summary['n_samplers_succeeded']} / {summary['n_samplers_failed']}")
    if summary.get("missing_sample_files"):
        print(f"  missing sample files: {summary['missing_sample_files']}")
    if summary["sampler_failed_files"]:
        print(f"  failed files: {summary['sampler_failed_files']}")
    print()
    print("--- main gate (B2 SSOT, psutil sampling) ---")
    print(f"sampled_max_worker_rss_max:        {_format_gb(summary['sampled_max_worker_rss_bytes'])}")  # type: ignore[arg-type]
    print(f"sampled_process_tree_rss_max:      {_format_gb(summary['sampled_process_tree_rss_max_bytes'])}")  # type: ignore[arg-type]
    print()
    print("--- auxiliary (time -l 由来、 macOS 依存挙動あり) ---")
    print(f"reference_peak_rss_max:            {_format_gb(summary['reference_peak_rss_max_bytes'])}")  # type: ignore[arg-type]
    print(f"reference_peak_rss_mean:           {_format_gb(summary['reference_peak_rss_mean_bytes'])}")  # type: ignore[arg-type]
    print(f"wall_time_mean (sec):              {summary['wall_time_mean_seconds']}")
    print(f"baseline_dir:                      {args.baseline_dir}")
    print()
    print("--- merge gates ---")
    print(f"B2 (sampled_max_worker_rss < 3 GB):           {gates['B2']}")
    print(f"B3 (wall_time vs step1.7 ±{int(args.b3_tolerance * 100)}%):              {gates['B3']}")

    print()
    print("--- summary JSON ---")
    print(json.dumps({"summary": summary, "gates": gates}, indent=2, default=str))

    # exit 0 のみ B2 / B3 両方 PASS のとき (= Round 2 [Critical 1] 反映、
    # B3 INCONCLUSIVE / FAIL は merge 失敗扱い)
    if gates["B2"] == "PASS" and gates["B3"] == "PASS":
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
