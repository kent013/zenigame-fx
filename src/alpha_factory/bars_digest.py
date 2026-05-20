"""bars の semantic equivalence 検証用 sha256 digest (T106).

DB ロード経路を server-side cursor streaming に置換 (T106) する際、 旧 ``.all()``
経路と新 streaming 経路で bars の内容・順序が完全一致することを確認するための
検証 utility。

canonical serialization:
    - TSV 1 行 1 bar
    - field 順: pair_name / bar_time / bid OHLC / ask OHLC / volume / complete
    - datetime は UTC ISO 8601 (tz-naive は UTC とみなす)
    - Decimal は ``str()`` でそのまま (正規化なし → trailing zero 差も検出する)
    - bool は "true" / "false"

production code には組み込まない (検証専用)。
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from datetime import UTC
from typing import Final

from src.domain.price import PriceBar

# canonical field 順序 (digest の安定性のため固定)。
_FIELD_ORDER: Final[tuple[str, ...]] = (
    "pair_name",
    "bar_time",
    "open_bid",
    "high_bid",
    "low_bid",
    "close_bid",
    "open_ask",
    "high_ask",
    "low_ask",
    "close_ask",
    "volume",
    "complete",
)


def _bar_to_tsv_line(bar: PriceBar) -> str:
    """1 bar を canonical TSV 1 行に直列化する."""
    bt = bar.bar_time
    bt = bt.replace(tzinfo=UTC) if bt.tzinfo is None else bt.astimezone(UTC)
    fields = (
        bar.pair_name,
        bt.isoformat(),
        str(bar.bid.open),
        str(bar.bid.high),
        str(bar.bid.low),
        str(bar.bid.close),
        str(bar.ask.open),
        str(bar.ask.high),
        str(bar.ask.low),
        str(bar.ask.close),
        str(bar.volume),
        "true" if bar.complete else "false",
    )
    return "\t".join(fields)


def bars_digest(bars: Iterable[PriceBar]) -> str:
    """bars の semantic equivalence sha256 digest を返す (hex).

    順序依存 (= L2 row order の検証にも使える)。 同一内容・同一順序の bars は
    同じ digest を返す。
    """
    hasher = hashlib.sha256()
    for bar in bars:
        hasher.update(_bar_to_tsv_line(bar).encode("utf-8"))
        hasher.update(b"\n")
    return hasher.hexdigest()
