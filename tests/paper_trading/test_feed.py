from __future__ import annotations

import threading
import time

from src.paper_trading.feed import ReplayBarFeed
from tests._helpers import make_bar


def test_replay_bar_feed_yields_bars_in_order() -> None:
    bars = [make_bar(i, bid_close="154.100", ask_close="154.110") for i in range(3)]
    feed = ReplayBarFeed(bars, speedup=0)
    out = list(feed)
    assert [b.bar_time for b in out] == [b.bar_time for b in bars]


def test_replay_bar_feed_stops_on_request() -> None:
    bars = [make_bar(i, bid_close="154.100", ask_close="154.110") for i in range(100)]
    # speedup を非常に小さくして各 bar 間で待機する状況を作る
    feed = ReplayBarFeed(bars, speedup=10.0, bar_interval_seconds=60.0)  # 6s/bar

    received: list = []

    def consume() -> None:
        for bar in feed:
            received.append(bar)
            if len(received) >= 2:
                feed.stop()

    t = threading.Thread(target=consume)
    start = time.time()
    t.start()
    t.join(timeout=15)
    elapsed = time.time() - start

    assert not t.is_alive(), "feed did not stop within timeout"
    # 2 本受信後に stop できるはず。全 100 本を待つと 600s 近くかかるので 15s 以下で抜けていれば OK
    assert elapsed < 15
    assert len(received) >= 2
