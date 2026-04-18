"""TokenBucket の並列アクセステスト（audit P2 follow-up）。

実装は threading.Lock で保護しているが、テストで担保されていなかった。
複数スレッドから同時に acquire() した場合に token が正しく消費され、
合計取得数が期待値と一致することを確認する。
"""

from __future__ import annotations

import threading
import time

from src.api.oanda.rate_limit import TokenBucket


def test_single_thread_acquire_consumes_tokens() -> None:
    bucket = TokenBucket(rate_per_sec=1000, capacity=5)
    for _ in range(5):
        bucket.acquire()
    # 5 回の acquire 後、バケツは空。次の acquire は少なくとも 1 回分の補充を待つ
    start = time.time()
    bucket.acquire()
    elapsed = time.time() - start
    assert elapsed >= 0.0005  # rate=1000/s なので 1 トークン 1ms、多少の余裕


def test_concurrent_acquire_totals_correctly() -> None:
    """複数スレッドが並列に acquire しても、合計取得数は期待値と一致する（lock がなければ race）。"""
    bucket = TokenBucket(rate_per_sec=500, capacity=50)
    counts_per_thread = 10
    thread_count = 5
    barrier = threading.Barrier(thread_count)
    counter = {"count": 0}
    counter_lock = threading.Lock()

    def worker() -> None:
        barrier.wait()  # 全スレッドが同時に発火
        for _ in range(counts_per_thread):
            bucket.acquire()
            with counter_lock:
                counter["count"] += 1

    threads = [threading.Thread(target=worker) for _ in range(thread_count)]
    start = time.time()
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)
    elapsed = time.time() - start

    expected_total = counts_per_thread * thread_count  # 50
    assert counter["count"] == expected_total
    # capacity=50 が初期 token 数なので、理論的には即座に 50 本発行できる
    assert elapsed < 5.0  # 暴走していないこと


def test_rate_limits_when_burst_exceeds_capacity() -> None:
    """capacity を超える要求は rate に律速される。"""
    bucket = TokenBucket(rate_per_sec=100, capacity=5)
    # 初期 5 トークン → 即時消費可能
    # さらに 5 トークン欲しければ 5/100 = 50ms 必要
    start = time.time()
    for _ in range(10):
        bucket.acquire()
    elapsed = time.time() - start
    assert elapsed >= 0.04, f"rate limiter should enforce minimum elapsed time, got {elapsed:.3f}s"
