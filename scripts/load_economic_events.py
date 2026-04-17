"""経済指標 CSV をロードして economic_event テーブルへ UPSERT する。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from src.db.connection import SessionLocal
from src.events import load_events_from_csv, upsert_events


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Load economic events from CSV")
    p.add_argument("--csv", required=True, help="path to CSV file")
    p.add_argument("--source", default="manual_csv")
    args = p.parse_args(argv)

    path = Path(args.csv)
    if not path.exists():
        print(f"[error] csv not found: {path}", file=sys.stderr)
        return 1

    events = load_events_from_csv(path)
    with SessionLocal() as session:
        count = upsert_events(session, events, source=args.source)
    print(f"[done] upserted={count} from {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
