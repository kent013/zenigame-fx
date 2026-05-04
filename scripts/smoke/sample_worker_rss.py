"""B step 1.8 acceptance B2 用 per-worker RSS sampler (= psutil>=5.9 既存依存).

詳細設計 § 12.3 SSOT。 1 秒間隔 (デフォルト) で対象 root process + descendants の
RSS を JSONL として書き出す。 集計 helper (= aggregate_step1.8_memory.py) で
``sampled_max_worker_rss`` (= acceptance B2 主条件) を再計算する。

Usage:
    uv run python scripts/smoke/sample_worker_rss.py \
        --output reports/smoke/step1.8/sample-1.jsonl \
        --interval 1.0 \
        --target-cmdline "src.alpha_factory.run_ga"

Round 5 [Suggestion 施策 6] 反映:
    - sampler 自身の PID は ``os.getpid()`` で除外 (= --target-cmdline 文字列が
      sampler 自身の cmdline にも含まれるため)
    - 対象 root process は cmdline 一致の最も早く起動した process (= 最小 create_time)
      を採用、 その descendants を sample 対象に含める
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import psutil


def _find_root_process(
    target_cmdline: str,
    *,
    exclude_pid: int,
    sampler_start_time: float,
    extra_marker: str | None = None,
) -> psutil.Process | None:
    """``target_cmdline`` が cmdline に含まれる process を返す.

    Cross-run contamination guard (= Codex impl-review Round 2 [Warning] 反映):
    sampler 起動時刻 (= ``sampler_start_time``) 以後に起動した process だけを
    対象にする (= 既存の別 run_ga が残っていてもそちらを捕捉しない)。
    複数候補があれば最も早く起動した process (= 最小 create_time) を採用。

    Args:
        target_cmdline: 対象 root process の cmdline 部分一致文字列。
        exclude_pid: 自プロセス (= sampler 自身) の PID。
        sampler_start_time: sampler 起動時刻 (= UNIX time)。 これより前に
            起動した process は対象外 (= cross-run contamination guard)。
        extra_marker: 追加の cmdline marker (= 任意)。 指定時はこの文字列も
            cmdline に含まれる process だけを採用 (= run-specific guard)。
    """
    candidates: list[psutil.Process] = []
    for proc in psutil.process_iter(["pid", "cmdline", "create_time"]):
        if proc.info["pid"] == exclude_pid:
            continue
        create_time = proc.info.get("create_time") or 0.0
        # 1.0 秒の grace を置く (= Codex impl-review Round 4 [Warning] 反映、
        # OS/psutil の時刻解像度次第で sampler 起動と同秒丸めの run_ga が
        # 除外される false negative を防ぐ)
        if create_time < sampler_start_time - 1.0:
            # sampler 起動より明らかに前の process は cross-run contamination として除外
            continue
        cmdline = proc.info.get("cmdline") or []
        cmdline_joined = " ".join(cmdline)
        if target_cmdline not in cmdline_joined:
            continue
        if extra_marker is not None and extra_marker not in cmdline_joined:
            continue
        candidates.append(proc)
    if not candidates:
        return None
    candidates.sort(key=lambda p: p.info.get("create_time") or 0.0)
    return candidates[0]


def _sample_tree(root: psutil.Process) -> tuple[list[dict[str, object]], int]:
    """root + descendants の RSS を sample. (records, total_rss_bytes) を返す."""
    records: list[dict[str, object]] = []
    total_rss = 0
    try:
        descendants = [root, *root.children(recursive=True)]
    except psutil.NoSuchProcess:
        return records, 0
    for proc in descendants:
        try:
            mem = proc.memory_info()
            records.append(
                {
                    "pid": proc.pid,
                    "rss_bytes": mem.rss,
                    "cmdline": " ".join(proc.cmdline()[:3]),
                }
            )
            total_rss += mem.rss
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return records, total_rss


def main() -> int:
    parser = argparse.ArgumentParser(description="B step 1.8 per-worker RSS sampler")
    parser.add_argument("--output", required=True, help="JSONL 出力ファイル")
    parser.add_argument("--interval", type=float, default=1.0, help="sampling 間隔 (秒)")
    parser.add_argument("--target-cmdline", required=True, help="対象 root process の cmdline 部分一致")
    parser.add_argument("--max-duration", type=float, default=3600.0, help="最大計測時間 (秒)")
    parser.add_argument(
        "--extra-marker",
        default=None,
        help="追加 cmdline marker (= run-specific guard、 省略可)",
    )
    parser.add_argument(
        "--run-index",
        type=int,
        default=None,
        help="対応する run-N.log の index N (= aggregate での pair 検証用)",
    )
    args = parser.parse_args()

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    self_pid = os.getpid()

    sampler_start_time = time.time()
    start = sampler_start_time
    root: psutil.Process | None = None
    # root 検出 retry (= run_ga 起動を待つ余裕、 max 30 秒)
    for _ in range(30):
        root = _find_root_process(
            args.target_cmdline,
            exclude_pid=self_pid,
            sampler_start_time=sampler_start_time,
            extra_marker=args.extra_marker,
        )
        if root is not None:
            break
        time.sleep(1.0)
    if root is None:
        print("sampler: target process not found within 30s", file=sys.stderr)
        return 2

    print(f"sampler: tracking root pid={root.pid} (start_time={root.create_time()})", file=sys.stderr)

    # header 行を最初に出力 (= aggregate での pair 検証用、
    # Codex impl-review Round 4 [Critical 2] 反映、 stale file contamination guard)
    header = {
        "_header": True,
        "run_index": args.run_index,
        "started_at": sampler_start_time,
        "root_pid": root.pid,
        "root_create_time": root.create_time(),
        "target_cmdline": args.target_cmdline,
        "extra_marker": args.extra_marker,
    }

    with output_path.open("w", encoding="utf-8") as f:
        f.write(json.dumps(header) + "\n")
        f.flush()
        while time.time() - start < args.max_duration:
            try:
                records, total_rss = _sample_tree(root)
            except psutil.NoSuchProcess:
                break
            if not records:
                break
            entry = {
                "timestamp": time.time(),
                "elapsed_seconds": time.time() - start,
                "tree_total_rss_bytes": total_rss,
                "tree_max_rss_bytes": max(r["rss_bytes"] for r in records),  # type: ignore[type-var]
                "process_count": len(records),
                "records": records,
            }
            f.write(json.dumps(entry) + "\n")
            f.flush()
            time.sleep(args.interval)

    return 0


if __name__ == "__main__":
    sys.exit(main())
