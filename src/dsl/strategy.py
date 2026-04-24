"""Clause ベース DslStrategy（T007）。

Genome の Clause を primitive 評価 → composite 化 → ヒステリシス判定 → 発注 の順で処理する。
primitive 評価は PrimitiveEvaluator Protocol 経由で行い、本 TODO では実装を提供しない
（後続 TODO `primitives-registry` で RegistryEvaluator が実装される）。
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from typing import Protocol

import numpy as np

from src.broker.orders import OrderSignal, PortfolioSnapshot
from src.domain.price import PriceBar
from src.dsl.composite import compute_composite
from src.dsl.genome import Genome, SignalConfig


def _signal_cache_key(
    sig: SignalConfig,
) -> tuple[str, tuple[tuple[str, float | int], ...]]:
    """prepare() の precompute cache で使う安定キー。

    params は dict（unordered）なので sorted(items) のタプル化で決定論化する。
    """
    return (sig.name, tuple(sorted(sig.params.items())))


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
        # prepare() で埋まる precompute cache。
        # key=(signal.name, sorted(params.items()) tuple) → full-length np.ndarray
        # 存在する場合 on_bar は arr[idx] で O(1) 参照し、evaluator.evaluate を
        # 経由しないため per-bar O(N) 計算が消える（backtest 全体 O(N²) → O(N)）。
        self._precomputed: dict[tuple[str, tuple[tuple[str, float | int], ...]], np.ndarray] | None = None
        self._bar_count = 0

    @property
    def genome(self) -> Genome:
        return self._genome

    def warmup_bars(self) -> int:
        return self._warmup

    def prepare(self, bars: list[PriceBar]) -> None:
        """backtest 全バーを事前計算して cache する（O(N²) → O(N) 最適化）。

        primitive が look-ahead bias-free である前提を利用:
        ``compute_all_bars(bars)[idx]`` == ``compute_all_bars(bars[:idx+1])[idx]``
        （rolling* は prefix-sum、ema/atr/rsi/adx は recurrence で過去のみ参照）。

        evaluator が ``evaluate_all_bars`` を提供しない場合は NoOp で、従来の
        per-bar ``evaluate()`` 経路にフォールバックする（live feed / paper trading
        互換）。
        """
        if not hasattr(self._evaluator, "evaluate_all_bars"):
            return
        cache: dict[
            tuple[str, tuple[tuple[str, float | int], ...]], np.ndarray
        ] = {}
        for clause in self._genome.clauses:
            for sig in (*clause.directional, *clause.local_gate):
                key = _signal_cache_key(sig)
                if key not in cache:
                    cache[key] = self._evaluator.evaluate_all_bars(bars, sig)
        self._precomputed = cache
        self._bar_count = 0

    def _lookup_signal(self, sig: SignalConfig, idx: int) -> float:
        """prepared 経路: cache から arr[idx] を安全に取り出す (nan → 0.0)。"""
        assert self._precomputed is not None
        key = _signal_cache_key(sig)
        arr = self._precomputed[key]
        if idx < 0 or idx >= len(arr):
            return 0.0
        v = float(arr[idx])
        return 0.0 if not math.isfinite(v) else v

    def on_bar(
        self, bar: PriceBar, snapshot: PortfolioSnapshot
    ) -> list[OrderSignal]:
        if self._precomputed is not None:
            # prepared 経路: self._bars の蓄積を省略、bar_count で idx 決定
            idx = self._bar_count
            self._bar_count += 1
            if idx < self._warmup:
                return []
        else:
            self._bars.append(bar)
            if len(self._bars) < self._warmup:
                return []
            idx = len(self._bars) - 1

        # 各 clause の primitive 値を評価
        values_per_clause: list[dict[str, float]] = []
        for clause in self._genome.clauses:
            vals: dict[str, float] = {}
            if self._precomputed is not None:
                for sig in clause.directional:
                    vals[sig.name] = self._lookup_signal(sig, idx)
                for sig in clause.local_gate:
                    vals[sig.name] = self._lookup_signal(sig, idx)
            else:
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
