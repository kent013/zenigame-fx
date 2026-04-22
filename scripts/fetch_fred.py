"""FRED API からマクロ指標日足を取得して macro_index_daily テーブルに UPSERT する。

詳細設計: devnotes/20260422-1027-fred-ingest-implementation/
"""

from __future__ import annotations

import argparse
import sys
from datetime import date

from src.config import settings
from src.db.connection import SessionLocal
from src.ingest.fred import fetch_series, upsert_observations

DEFAULT_SERIES = ("VIXCLS", "DTWEXBGS", "DGS10", "DGS2", "T10YIE")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Fetch FRED daily macro indicators")
    p.add_argument(
        "--series",
        default=",".join(DEFAULT_SERIES),
        help="comma-separated FRED series ids (default: VIXCLS,DTWEXBGS,DGS10,DGS2,T10YIE)",
    )
    p.add_argument("--from", dest="start", required=True, help="YYYY-MM-DD")
    p.add_argument("--to", dest="end", required=True, help="YYYY-MM-DD")
    args = p.parse_args(argv)

    if not settings.fred_api_key:
        print("[error] FRED_API_KEY is empty in settings/.env", file=sys.stderr)
        return 2

    series_list = [s.strip() for s in args.series.split(",") if s.strip()]
    if not series_list:
        print("[error] --series is empty", file=sys.stderr)
        return 2

    try:
        start = date.fromisoformat(args.start)
        end = date.fromisoformat(args.end)
    except ValueError as exc:
        print(f"[error] invalid date format: {exc}", file=sys.stderr)
        return 2
    if start > end:
        print(f"[error] start ({start}) > end ({end})", file=sys.stderr)
        return 2

    total = 0
    empty_series: list[str] = []
    failed_series: list[tuple[str, str]] = []

    with SessionLocal() as session:
        for series_id in series_list:
            try:
                obs = fetch_series(series_id, start, end)
            except Exception as exc:  # CLI 境界で捕捉して他シリーズの処理を継続
                failed_series.append((series_id, repr(exc)))
                print(f"[error] series={series_id} fetch_failed={exc!r}", file=sys.stderr)
                continue
            written = upsert_observations(session, obs)
            print(f"[done] series={series_id} fetched={len(obs)} upserted={written}")
            total += written
            if len(obs) == 0:
                empty_series.append(series_id)

    print(
        f"[summary] series={len(series_list)} total_upserted={total} "
        f"empty={empty_series} failed={[s for s, _ in failed_series]}"
    )

    # 部分失敗（fetch error または 0 件）を見逃さない acceptance 要件のため非ゼロ終了
    if failed_series or empty_series:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
