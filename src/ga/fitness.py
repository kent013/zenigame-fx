"""GA fitness 評価（暫定スタブ, T007）。

本 TODO でフラット Genome から Clause Genome へ切り替えたため、DslStrategy の
コンストラクタ引数が (genome) → (genome, evaluator, ...) に変わった。
完全な clause 対応は後続 TODO `clause-backtest-integration` のスコープ。

暫定挙動: evaluate_genome は呼ばれた時点で NotImplementedError を明示 raise し、
silent に全個体失敗 (-1e12) となる状態を防ぐ。tests/ga/* は本 TODO で skip 済み。
"""

from __future__ import annotations

from decimal import Decimal
from typing import Literal

import structlog

from src.backtest.engine import BacktestConfig
from src.broker.mock import InstrumentMeta
from src.domain.price import PriceBar
from src.dsl.genome import Genome

logger = structlog.get_logger(__name__)

FitnessMetric = Literal["total_pnl", "sharpe", "calmar"]

_FAILURE_FITNESS = Decimal("-1000000000000")  # -1e12 相当（後続 TODO で使用）


def evaluate_genome(
    genome: Genome,
    bars: list[PriceBar],
    meta: InstrumentMeta,
    backtest_config: BacktestConfig,
    metric: FitnessMetric = "total_pnl",
) -> Decimal:
    """Clause Genome を評価して fitness を返す（未実装、clause-backtest-integration 待ち）."""
    raise NotImplementedError(
        "evaluate_genome is awaiting clause-backtest-integration TODO "
        "to accept a PrimitiveEvaluator. See docs/alpha_factory/clause-architecture.md."
    )
