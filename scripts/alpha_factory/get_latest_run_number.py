"""最新の Alpha Factory Run 番号を返す。

reports/run-reports/run-{N}.md を走査して最大 N を標準出力へ書く。
Run が 1 つも無ければ 0 を返す（`next = latest + 1` で 1 から採番される）。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

_RUN_REPORTS_DIR = Path(__file__).resolve().parents[2] / "reports" / "run-reports"
_PATTERN = re.compile(r"^run-(\d+)\.md$")


def get_latest_run_number(base_dir: Path = _RUN_REPORTS_DIR) -> int:
    if not base_dir.exists():
        return 0
    numbers: list[int] = []
    for entry in base_dir.rglob("run-*.md"):
        m = _PATTERN.match(entry.name)
        if m:
            numbers.append(int(m.group(1)))
    return max(numbers) if numbers else 0


def main() -> int:
    print(get_latest_run_number())
    return 0


if __name__ == "__main__":
    sys.exit(main())
