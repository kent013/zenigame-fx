"""run_backtest hot-path プロファイル (handoff §7 step 2).

real Stage A bars に対し N genome 分の run_backtest を cProfile し、
tottime / cumtime 上位関数を出力する。numba 化の優先順位付けが目的。

- prepare() を 1 回計上するため、各 genome で strat を作り直す (= production と同条件)。
- 最初の 1 本は numba JIT warmup として捨て、計測は warmup 後のみ。

実行: uv run python devnotes/20260520-1949-handoff-backtest-engine-numba/profile_run_backtest.py
"""

from __future__ import annotations

import cProfile
import pstats
import random
import sys
import time
from io import StringIO
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from scripts.alpha_factory.run_ga import _load_lane_bars  # noqa: E402
from src.alpha_factory._registry_bridge import build_random_gen_registry  # noqa: E402
from src.alpha_factory.config import load_config  # noqa: E402
from src.alpha_factory.primitives import RegistryEvaluator, ensure_registered  # noqa: E402
from src.backtest.engine import BacktestConfig, run_backtest  # noqa: E402
from src.broker.mock import MockBroker  # noqa: E402
from src.dsl.strategy import DslStrategy  # noqa: E402
from src.ga.random_gen import random_genome  # noqa: E402

N_WARMUP = 2
N_PROFILE = 30
CONFIG = REPO_ROOT / "config" / "alpha_factory" / "default.yaml"


def main() -> None:
    ensure_registered()
    cfg = load_config(CONFIG)
    rng = random.Random(9999)
    rg_registry = build_random_gen_registry()
    bundle = _load_lane_bars(cfg.dataset.instrument, cfg.dataset, cfg.stage_windows)
    bars = bundle.bars_stage_a
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
            rng, name=f"prof_{i}", units=cfg.backtest.units,
            max_clause=cfg.ga.max_clause, max_depth=cfg.ga.max_depth,
            registry=rg_registry,
        )
        for i in range(N_WARMUP + N_PROFILE)
    ]

    def _run_one(g) -> int:
        strat = DslStrategy(g, primitive_evaluator)
        broker = MockBroker(instrument_meta=meta)
        try:
            res = run_backtest(bars, strat, broker, bt_cfg)
            return len(res.trades)
        except Exception:  # noqa: BLE001
            return -1

    # warmup (JIT compile cache を温める)
    for g in genomes[:N_WARMUP]:
        _run_one(g)

    # wall-time 計測
    t0 = time.perf_counter()
    n_trades = 0
    for g in genomes[N_WARMUP:]:
        nt = _run_one(g)
        if nt > 0:
            n_trades += nt
    wall = time.perf_counter() - t0
    per_bt = wall / N_PROFILE
    per_bar_us = per_bt / len(bars) * 1e6
    print(f"\nwall={wall:.2f}s over {N_PROFILE} backtests "
          f"({per_bt*1000:.1f}ms/bt, {per_bar_us:.1f}us/bar, total_trades={n_trades})")

    # cProfile (関数別 tottime)
    pr = cProfile.Profile()
    pr.enable()
    for g in genomes[N_WARMUP:]:
        _run_one(g)
    pr.disable()

    s = StringIO()
    ps = pstats.Stats(pr, stream=s).sort_stats("tottime")
    ps.print_stats(30)
    print("\n--- cProfile top 30 by tottime ---")
    print(s.getvalue())


if __name__ == "__main__":
    main()
