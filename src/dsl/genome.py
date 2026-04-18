from __future__ import annotations

from dataclasses import dataclass

from src.broker.orders import OrderSignal, PortfolioSnapshot
from src.domain.price import PriceBar
from src.dsl.ast import Expr
from src.dsl.eval import EvalContext, evaluate, max_lookback


@dataclass(frozen=True)
class Genome:
    name: str
    units: int
    entry_long: Expr
    entry_short: Expr
    exit_long: Expr
    exit_short: Expr


class DslStrategy:
    """Genome を評価しながらシグナルを出す Strategy。1 ポジション制約（MVP）。"""

    def __init__(self, genome: Genome) -> None:
        self._genome = genome
        self._bars: list[PriceBar] = []
        self._warmup = max(
            max_lookback(genome.entry_long),
            max_lookback(genome.entry_short),
            max_lookback(genome.exit_long),
            max_lookback(genome.exit_short),
        )

    @property
    def genome(self) -> Genome:
        return self._genome

    def warmup_bars(self) -> int:
        return self._warmup

    def on_bar(self, bar: PriceBar, snapshot: PortfolioSnapshot) -> list[OrderSignal]:
        self._bars.append(bar)
        # warmup_bars() が返す値と同じバー数が揃った時点から評価を開始する。
        # 修正前は `<=` により 1 本余計に待機していた（Phase 4f audit Bug #1）。
        if len(self._bars) < self._warmup:
            return []
        ctx = EvalContext(bars=self._bars, i=len(self._bars) - 1)

        if snapshot.positions:
            pos = snapshot.positions[0]
            exit_expr = self._genome.exit_long if pos.side == "long" else self._genome.exit_short
            if bool(evaluate(exit_expr, ctx)):
                return [OrderSignal(kind="close_position", position_id=pos.id)]
            return []

        if bool(evaluate(self._genome.entry_long, ctx)):
            return [OrderSignal(kind="open_long", units=self._genome.units)]
        if bool(evaluate(self._genome.entry_short, ctx)):
            return [OrderSignal(kind="open_short", units=self._genome.units)]
        return []
