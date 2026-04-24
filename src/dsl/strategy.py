"""Clause ベース DslStrategy。

Cycle 2 (T029) で prepared signal flattening を導入:
  - `PreparedSignals` NamedTuple で prepare state を単一化
  - per-clause flat list で on_bar hot path から sorted() / dict lookup を排除
  - genome identity 検証で lifecycle contract violation を fail-fast

Genome の Clause を primitive 評価 → composite 化 → ヒステリシス判定 → 発注 の順で処理する。
primitive 評価は PrimitiveEvaluator Protocol 経由で行い、本 TODO では実装を提供しない
（後続 TODO `primitives-registry` で RegistryEvaluator が実装される）。
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from typing import NamedTuple, Protocol

import numpy as np

from src.broker.orders import OrderSignal, PortfolioSnapshot
from src.domain.price import PriceBar
from src.dsl.composite import compute_composite
from src.dsl.genome import Genome, SignalConfig

# SignalCacheKey: (primitive_id, sorted params tuple)
SignalCacheKey = tuple[str, tuple[tuple[str, float | int], ...]]


def _signal_cache_key(sig: SignalConfig) -> SignalCacheKey:
    """(name, sorted params tuple) で決定論的な cache key を作る.

    prepare() 内でのみ呼ばれる (Cycle 2 以降、on_bar hot path からは排除)。
    Cycle 1 時点では per-bar per-sig で呼ばれていたが、Cycle 2 (T029) で
    prepare-time precompute に移行した。
    """
    return (sig.name, tuple(sorted(sig.params.items())))


class PreparedSignals(NamedTuple):
    """prepare() で構築される precompute state (Cycle 2 / T029 で導入).

    単一オブジェクトにまとめることで、Cycle 1 の `_precomputed` + bar loop 内
    `_signal_cache_key` 再計算による 2 重管理と hot path コストを排除する。

    Attributes:
        arrays: (sig.name, sorted(params.items()) tuple) → ndarray。
                duplicate signal の共有用 lookup cache (同一 genome 内で同一
                (name, params) を持つ signal が複数 clause にあれば 1 度のみ
                compute_all_bars を呼ぶ invariant は Cycle 1 から不変)。
        clauses: clause_idx → (directional_entries, gate_entries)。
                各 entries は (sig.name, arr) の tuple を clause.directional /
                local_gate の index 順に保持。on_bar では index 直接 iterate
                で O(1) per-sig lookup。
        genome: prepare() 呼び出し時の genome reference。on_bar 冒頭で
                `prepared.genome is self._genome` の O(1) identity 比較で
                genome 差し替え等の lifecycle contract violation を fail-fast
                検出する (Design Review Round 1 Critical #2 対応: fingerprint
                毎バー再構築の O(clause×sig) コストを回避)。

                **Deep immutability の保証 (Design Review Round 2 Critical #1
                対応)**: Genome / ClauseConfig / SignalConfig / PositionConfig
                / RiskConfig は全て `@dataclass(frozen=True)`、`Genome.clauses`
                等の tuple field は structurally immutable、施策 0 で
                `SignalConfig.params` を `MappingProxyType` 化することで
                dict 値の in-place mutation も禁止される。よって `is` が True
                なら内容完全一致が構造的に保証される (identity → content
                equality の upgrade)。
    """

    arrays: dict[SignalCacheKey, np.ndarray]
    clauses: tuple[
        tuple[
            tuple[tuple[str, np.ndarray], ...],  # directional entries
            tuple[tuple[str, np.ndarray], ...],  # gate entries
        ],
        ...,
    ]
    genome: Genome


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


def _assert_unique_name(
    name: str, seen: set[str], clause_idx: int
) -> None:
    """同一 clause 内で signal.name 重複を fail-fast で拒否する.

    重複すると values_per_clause[i][name] の後勝ち上書きで silent bug 化
    するため、prepare() 時に禁止する (Round 1 Critical #3 対応)。
    """
    if name in seen:
        raise ValueError(
            f"duplicate signal.name {name!r} in clause index {clause_idx}; "
            f"signal names must be unique within a clause"
        )
    seen.add(name)


def _validate_unique_names_in_clauses(genome: Genome) -> None:
    """全 clause で signal.name 一意性を fail-fast 検証する.

    重複すると values_per_clause[i][name] が後勝ち上書きで silent bug 化する。
    Design Review Round 1 Warning #3 対応: unprepared (live feed) path も
    含めて同じ契約を強制するため、`__init__` から呼ぶ (prepare() 限定では
    paper trading で抜け漏れ)。
    """
    for clause_idx, clause in enumerate(genome.clauses):
        seen: set[str] = set()
        for sig in (*clause.directional, *clause.local_gate):
            _assert_unique_name(sig.name, seen, clause_idx)


class DslStrategy:
    """Clause ベース Genome を評価する Strategy (Cycle 2 / T029)。

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
        # 全 clause で signal.name 一意性を検証 (Design Review Round 1
        # Warning #3 対応: prepared / unprepared 両 path で同じ契約を強制)。
        # prepare() 内の重複検出では paper trading で抜け漏れる。
        _validate_unique_names_in_clauses(genome)
        self._genome = genome
        self._evaluator = evaluator
        self._warmup = warmup_bars
        self._session_close = session_close_utc
        self._bars: list[PriceBar] = []
        # 単一 prepared state (Cycle 2 / T029)。prepare() 未呼出時は None、
        # paper trading / live feed では常に None のまま (P8 Verified)。
        self._prepared: PreparedSignals | None = None
        self._bar_count = 0

    @property
    def genome(self) -> Genome:
        return self._genome

    def warmup_bars(self) -> int:
        return self._warmup

    def prepare(self, bars: list[PriceBar]) -> None:
        """backtest 全バーを事前計算して flat list に展開する.

        O(N²) → O(N) 最適化 (Cycle 1 から継承) + per-bar sorted() 排除
        (Cycle 2 / T029)。primitive が look-ahead bias-free である前提:
          compute_all_bars(bars)[idx] == compute_all_bars(bars[:idx+1])[idx]

        evaluator が evaluate_all_bars を持たない場合は NoOp
        (self._prepared を None のまま)、従来 path にフォールバック。

        Round 2 対応:
          - Round 1 Critical #2: _precomputed + _precomputed_clauses の
            2 重管理を単一 PreparedSignals に統合
          - Round 1 Critical #3: 同一 clause 内 signal.name 重複を fail-fast
          - Round 2 Warning 2: genome reference を prepare() 時点で保存
        """
        # 再 prepare() 時の stale state 除去 (Round 1 Warning 対応)
        self._prepared = None
        self._bar_count = 0

        if not hasattr(self._evaluator, "evaluate_all_bars"):
            return

        arrays: dict[SignalCacheKey, np.ndarray] = {}
        clause_entries: list[
            tuple[
                tuple[tuple[str, np.ndarray], ...],
                tuple[tuple[str, np.ndarray], ...],
            ]
        ] = []

        # name 一意性は __init__ で検証済み (Round 1 Warning #3 対応)。
        # ここでは arrays 共有 cache のみ意識すればよい。
        for clause in self._genome.clauses:
            dir_entries: list[tuple[str, np.ndarray]] = []
            for sig in clause.directional:
                key = _signal_cache_key(sig)
                if key not in arrays:
                    arrays[key] = self._evaluator.evaluate_all_bars(bars, sig)
                dir_entries.append((sig.name, arrays[key]))

            gate_entries: list[tuple[str, np.ndarray]] = []
            for sig in clause.local_gate:
                key = _signal_cache_key(sig)
                if key not in arrays:
                    arrays[key] = self._evaluator.evaluate_all_bars(bars, sig)
                gate_entries.append((sig.name, arrays[key]))

            clause_entries.append((tuple(dir_entries), tuple(gate_entries)))

        self._prepared = PreparedSignals(
            arrays=arrays,
            clauses=tuple(clause_entries),
            genome=self._genome,  # identity 比較用 (O(1))
        )

    def on_bar(
        self, bar: PriceBar, snapshot: PortfolioSnapshot
    ) -> list[OrderSignal]:
        prepared = self._prepared  # single snapshot read (atomicity)

        if prepared is not None:
            # O(1) identity check: prepare() 時点の genome と同一 reference か
            # (Design Review Round 1 Critical #2 対応: fingerprint 毎バー
            # 再構築の O(clause×sig) コストを回避)。Genome は frozen (P7) で
            # tuple fields も immutable のため、identity == は内容 == と
            # 同値 (`is` → `==` の upgrade は構造的に保証)。
            assert prepared.genome is self._genome, (
                "DslStrategy.prepared state is inconsistent with current "
                "genome; genome was swapped after prepare()? (lifecycle "
                "contract violation)"
            )
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
        if prepared is not None:
            # fast path: flat list iteration (Cycle 2 / T029)
            for dir_entries, gate_entries in prepared.clauses:
                vals: dict[str, float] = {}
                for name, arr in dir_entries:
                    v = arr[idx] if 0 <= idx < len(arr) else 0.0
                    vals[name] = 0.0 if not math.isfinite(v) else float(v)
                for name, arr in gate_entries:
                    v = arr[idx] if 0 <= idx < len(arr) else 0.0
                    vals[name] = 0.0 if not math.isfinite(v) else float(v)
                values_per_clause.append(vals)
        else:
            # unprepared path (live feed / paper trading)
            for clause in self._genome.clauses:
                vals = {}
                for sig in clause.directional:
                    vals[sig.name] = self._evaluator.evaluate(
                        self._bars, idx, sig
                    )
                for sig in clause.local_gate:
                    vals[sig.name] = self._evaluator.evaluate(
                        self._bars, idx, sig
                    )
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
