"""Clause ベース DslStrategy（T007）。

Genome の Clause を primitive 評価 → composite 化 → ヒステリシス判定 → 発注 の順で処理する。
primitive 評価は PrimitiveEvaluator Protocol 経由で行い、本 TODO では実装を提供しない
（後続 TODO `primitives-registry` で RegistryEvaluator が実装される）。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta
from typing import Protocol

from src.broker.orders import OrderSignal, PortfolioSnapshot
from src.domain.price import PriceBar
from src.dsl.composite import compute_composite
from src.dsl.genome import Genome, SignalConfig


class PrimitiveEvaluator(Protocol):
    """primitive 評価関数の抽象。後続 TODO で実装される。

    Implementations should be deterministic for a given (bars, idx, signal) triple.
    State（キャッシュ等）は各 evaluator の内部で管理して良い。
    """

    def evaluate(
        self, bars: list[PriceBar], idx: int, signal: SignalConfig
    ) -> float:
        """bars[idx] 時点での signal の評価値を返す。

        Returns:
            float（directional は符号付き [-1, 1] 想定、local_gate は [0, 1] 想定）。
        """
        ...


@dataclass
class _OpenPosition:
    """DslStrategy 内部で保持するポジション状態（参考情報、snapshot で上書きされる）。"""

    position_id: int
    side: str
    entry_time: datetime


class DslStrategy:
    """Clause ベース Genome を評価する Strategy。

    ヒステリシス:
        - 無保有: composite >= θ_on → long、-composite >= θ_on → short（θ_on 等号含む）
        - long 保有: composite < θ_off → close（θ_off 等号は含まない）
        - short 保有: -composite < θ_off → close
    time_stop:
        - pos_cfg.time_stop_min > 0 かつ 経過時間 >= time_stop_min 分 → 強制クローズ
    session close:
        - session_close_utc != None かつ bar.bar_time.time() >= session_close_utc → 強制クローズ

    session_close_utc=None の場合、イントラデイ絶対制約は backtest engine 側の
    EOD 強制クローズ（src/backtest/engine.py 内の is_eod 判定）に依存する。
    両方が無効になる設計は禁止（conceptual-design.md §3.3 参照）。
    """

    def __init__(
        self,
        genome: Genome,
        evaluator: PrimitiveEvaluator,
        *,
        warmup_bars: int = 0,
        session_close_utc: time | None = None,
    ) -> None:
        self._genome = genome
        self._evaluator = evaluator
        self._warmup = warmup_bars
        self._session_close = session_close_utc
        self._bars: list[PriceBar] = []

    @property
    def genome(self) -> Genome:
        return self._genome

    def warmup_bars(self) -> int:
        return self._warmup

    def on_bar(
        self, bar: PriceBar, snapshot: PortfolioSnapshot
    ) -> list[OrderSignal]:
        self._bars.append(bar)
        if len(self._bars) < self._warmup:
            return []
        idx = len(self._bars) - 1

        # 各 clause の primitive 値を評価
        values_per_clause: list[dict[str, float]] = []
        for clause in self._genome.clauses:
            vals: dict[str, float] = {}
            for sig in clause.directional:
                vals[sig.name] = self._evaluator.evaluate(self._bars, idx, sig)
            for sig in clause.local_gate:
                vals[sig.name] = self._evaluator.evaluate(self._bars, idx, sig)
            values_per_clause.append(vals)
        composite = compute_composite(self._genome.clauses, values_per_clause)

        pos_cfg = self._genome.position

        # 保有あり: exit 判定のみ（無保有のみ entry を試みる = ドテン禁止）
        if snapshot.positions:
            pos = snapshot.positions[0]
            # session close
            if (
                self._session_close is not None
                and bar.bar_time.time() >= self._session_close
            ):
                return [OrderSignal(kind="close_position", position_id=pos.id)]
            # time stop
            if pos_cfg.time_stop_min > 0:
                elapsed = bar.bar_time - pos.entry_time
                if elapsed >= timedelta(minutes=pos_cfg.time_stop_min):
                    return [OrderSignal(kind="close_position", position_id=pos.id)]
            # hysteresis exit
            if pos.side == "long" and composite < pos_cfg.exit_threshold:
                return [OrderSignal(kind="close_position", position_id=pos.id)]
            if pos.side == "short" and -composite < pos_cfg.exit_threshold:
                return [OrderSignal(kind="close_position", position_id=pos.id)]
            return []

        # 無保有: entry 判定
        if composite >= pos_cfg.entry_threshold:
            return [OrderSignal(kind="open_long", units=self._genome.units)]
        if -composite >= pos_cfg.entry_threshold:
            return [OrderSignal(kind="open_short", units=self._genome.units)]
        return []
