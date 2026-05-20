"""B-1 memory attribution 診断 (T-worker-rss / step B-1).

worker per-worker RSS 9.5GB の「retained (蓄積) vs transient churn (断片化)」を
切り分けるため、 単一プロセスで real Stage A bars に対し N backtest を逐次実行し、
各区間で RSS / tracemalloc / gc object census を計測する。

判定:
  - RSS が iteration とともに単調増加 → retained leak (churn 削減では下がらない)
  - RSS が plateau だが高止まり + tracemalloc current が低い → churn 断片化支配
  - live Decimal/Trade/PriceBar 数が増え続ける → 真の retention

実行: uv run python devnotes/20260520-1358-backtest-decimal-churn-broker/b1_memory_attribution.py
"""

from __future__ import annotations

import gc
import sys
import tracemalloc
from collections import Counter
from decimal import Decimal
from pathlib import Path

import psutil

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from scripts.alpha_factory.run_ga import _load_lane_bars  # noqa: E402
from src.alpha_factory._registry_bridge import build_random_gen_registry  # noqa: E402
from src.alpha_factory.config import load_config  # noqa: E402
from src.alpha_factory.primitives import (  # noqa: E402
    RegistryEvaluator,
    ensure_registered,
)
from src.backtest.engine import BacktestConfig, run_backtest  # noqa: E402
from src.broker.mock import MockBroker  # noqa: E402
from src.broker.orders import Trade  # noqa: E402
from src.domain.price import Ohlc, PriceBar  # noqa: E402
from src.dsl.strategy import DslStrategy  # noqa: E402
from src.ga.random_gen import random_genome  # noqa: E402
import random  # noqa: E402

N_BACKTESTS = 200  # ~ 1 recycle 窓相当 (mt=12 想定の十数倍で趨勢を見る)
CENSUS_EVERY = 20
CONFIG = REPO_ROOT / "config" / "alpha_factory" / "default.yaml"


def _rss_mb() -> float:
    return psutil.Process().memory_info().rss / 1024 / 1024


def _census() -> dict[str, int]:
    c: Counter[str] = Counter()
    for obj in gc.get_objects():
        t = type(obj)
        if t is Decimal:
            c["Decimal"] += 1
        elif t is Trade:
            c["Trade"] += 1
        elif t is PriceBar:
            c["PriceBar"] += 1
        elif t is Ohlc:
            c["Ohlc"] += 1
    return dict(c)


def main() -> None:
    ensure_registered()
    cfg = load_config(CONFIG)
    rng = random.Random(9999)
    rg_registry = build_random_gen_registry()
    bundle = _load_lane_bars(cfg.dataset.instrument, cfg.dataset, cfg.stage_windows)
    bars = bundle.bars_stage_a  # Stage A (~86k bars)
    meta = bundle.meta
    print(f"loaded Stage A bars={len(bars)} instrument={cfg.dataset.instrument}")

    primitive_evaluator = RegistryEvaluator(pair=cfg.dataset.instrument)
    bt_cfg = BacktestConfig(
        instrument=cfg.dataset.instrument,
        start=cfg.dataset.start,
        end=cfg.dataset.end,
        initial_cash=cfg.backtest.initial_cash,
        leverage=cfg.backtest.leverage,
        max_spread_bps=cfg.backtest.max_spread_bps,
        holding_cost_per_day_bps=cfg.backtest.holding_cost_per_day_bps,
        session_close_utc_hours=frozenset(cfg.backtest.session_close_utc_hours),
        bar_minutes=1,
    )

    genomes = [
        random_genome(
            rng, name=f"b1_{i}", units=cfg.backtest.units,
            max_clause=cfg.ga.max_clause, max_depth=cfg.ga.max_depth,
            registry=rg_registry,
        )
        for i in range(N_BACKTESTS)
    ]

    tracemalloc.start()
    gc.collect()
    rss0 = _rss_mb()
    cen0 = _census()
    cur0, peak0 = tracemalloc.get_traced_memory()
    print(f"baseline rss={rss0:.0f}MB tracemalloc_cur={cur0/1e6:.0f}MB census={cen0}")
    print(f"{'iter':>5} {'rss_mb':>9} {'tm_cur_mb':>10} {'tm_peak_mb':>10} {'gap_mb':>9} {'census'}")

    for i, g in enumerate(genomes):
        try:
            strat = DslStrategy(g, primitive_evaluator)
            broker = MockBroker(instrument_meta=meta)
            run_backtest(bars, strat, broker, bt_cfg)
        except Exception as exc:  # noqa: BLE001
            # 一部 genome は backtest 内で raise しうる (本診断では無視)
            _ = exc
        del strat, broker
        if (i + 1) % CENSUS_EVERY == 0:
            gc.collect()
            rss = _rss_mb()
            cur, peak = tracemalloc.get_traced_memory()
            cen = _census()
            gap = rss - cur / 1e6  # RSS と Python 追跡分の差 ≈ 断片化+非Python
            print(
                f"{i+1:>5} {rss:>9.0f} {cur/1e6:>10.0f} {peak/1e6:>10.0f} "
                f"{gap:>9.0f} {cen}"
            )

    # tracemalloc top (retained allocation の出所)
    snap = tracemalloc.take_snapshot()
    print("\n--- tracemalloc top 10 (retained by line) ---")
    for stat in snap.statistics("lineno")[:10]:
        print(f"  {stat.size/1e6:8.1f}MB  {stat.count:>9} blocks  {stat.traceback}")

    gc.collect()
    rss_end = _rss_mb()
    print(f"\nsummary: rss baseline={rss0:.0f}MB end={rss_end:.0f}MB "
          f"growth={rss_end-rss0:.0f}MB over {N_BACKTESTS} backtests")
    print(f"final census={_census()}")


if __name__ == "__main__":
    main()
