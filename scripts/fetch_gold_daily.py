"""Yahoo Finance GC=F (Gold Futures) daily を取得して MacroIndexDaily に upsert.

T057 follow-up: FRED LBMA Gold spot series (GOLDPMGBD228NLBM / GOLDAMGBD228NLBM)
は 2024 年に discontinued されたため、Yahoo Finance Gold Futures (CME) を後継
データソースとして採用。`series_id="GC_F_YAHOO"` で MacroIndexDaily に保存し、
aux_loader 側で `macro.gold` aux_series key にマッピングする。

look-ahead bias: GC=F は CME 取引時間で 23:00 UTC まで稼働、Yahoo Finance への
配信もそれ以降。effective_from_utc は SERIES_POLICY_CONSERVATIVE で
observation_date + 24h (翌日 00:00 UTC) として保守側で扱う。

使用例:
    uv run python scripts/fetch_gold_daily.py --from 2024-04-01 --to 2026-04-30

依存: yfinance (pyproject.toml に追加済).
"""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, date, datetime
from decimal import Decimal

import structlog

from src.db.connection import SessionLocal
from src.ingest.effective_from import compute_effective_from_utc

logger = structlog.get_logger(__name__)

GOLD_SERIES_ID = "GC_F_YAHOO"
YAHOO_TICKER = "GC=F"


def fetch_gold_daily(
    *, start: date, end: date
) -> list[tuple[date, Decimal]]:
    """yfinance で GC=F daily close を取得.

    Returns:
        list of (observation_date, close_price). 取得失敗時は空 list.
    """
    import yfinance as yf

    ticker = yf.Ticker(YAHOO_TICKER)
    df = ticker.history(
        start=start.isoformat(),
        end=end.isoformat(),
        interval="1d",
        auto_adjust=False,
    )
    if df.empty:
        logger.warning(
            "fetch_gold_daily.empty",
            start=start.isoformat(),
            end=end.isoformat(),
        )
        return []
    out: list[tuple[date, Decimal]] = []
    for ts, row in df.iterrows():
        # ts は pandas.Timestamp (tz-aware America/New_York). UTC date へ変換
        obs_date = ts.tz_convert("UTC").date() if ts.tz else ts.date()
        close_val = row.get("Close")
        if close_val is None or close_val != close_val:  # NaN check
            continue
        out.append((obs_date, Decimal(str(round(float(close_val), 4)))))
    return out


def upsert_macro_index_daily(
    series_id: str, observations: list[tuple[date, Decimal]]
) -> int:
    """MacroIndexDaily へ ON CONFLICT DO UPDATE で upsert.

    既存 fetch_fred と同じ pattern: (series_id, date) unique key で衝突したら
    value / fetched_at / effective_from_utc / source を更新.
    """
    if not observations:
        return 0
    from sqlalchemy.dialects.postgresql import insert

    from src.db.models import MacroIndexDaily

    fetched_at = datetime.now(UTC)
    rows = []
    for obs_date, value in observations:
        eff = compute_effective_from_utc(series_id, obs_date)
        rows.append(
            {
                "series_id": series_id,
                "date": obs_date,
                "value": value,
                "fetched_at": fetched_at,
                "effective_from_utc": eff,
                "source": "policy_conservative",
            }
        )
    with SessionLocal() as session:
        stmt = insert(MacroIndexDaily).values(rows)
        stmt = stmt.on_conflict_do_update(
            index_elements=["series_id", "date"],
            set_={
                "value": stmt.excluded.value,
                "fetched_at": stmt.excluded.fetched_at,
                "effective_from_utc": stmt.excluded.effective_from_utc,
                "source": stmt.excluded.source,
            },
        )
        session.execute(stmt)
        session.commit()
    return len(rows)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Fetch Gold Futures daily from Yahoo Finance")
    p.add_argument("--from", dest="start", required=True, help="YYYY-MM-DD")
    p.add_argument("--to", dest="end", required=True, help="YYYY-MM-DD")
    args = p.parse_args(argv)

    start = date.fromisoformat(args.start)
    end = date.fromisoformat(args.end)
    try:
        observations = fetch_gold_daily(start=start, end=end)
    except Exception as exc:
        print(
            f"[error] series={GOLD_SERIES_ID} fetch_failed={exc!r}",
            file=sys.stderr,
        )
        return 1

    if not observations:
        print(f"[warn] series={GOLD_SERIES_ID} fetched=0 (range empty)")
        return 0

    upserted = upsert_macro_index_daily(GOLD_SERIES_ID, observations)
    print(
        f"[done] series={GOLD_SERIES_ID} fetched={len(observations)} "
        f"upserted={upserted} range=[{observations[0][0]} → {observations[-1][0]}]"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
