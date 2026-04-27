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

from dataclasses import dataclass
from datetime import datetime, time, timedelta
from typing import NamedTuple, Protocol

import numpy as np

from src.broker.orders import OrderSignal, PortfolioSnapshot
from src.domain.price import PriceBar
from src.dsl.composite import (
    compute_clause_score,
    compute_composite,
    compute_composite_at_bar_jit,
)
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

    # === T053: Numba JIT kernel 用 flat ndarray 群 ===
    # devnotes/20260427-1723-composite-numba-jit/detailed-design.md 施策 3。
    # arrays / clauses は維持しつつ並行で flat 表現を持つことで:
    #   - prepared path: kernel に直接渡せる contiguous ndarray
    #   - unprepared path: 既存 dict / tuple 表現がそのまま使える
    # の両立を実現する。同データを 2 重保持するが clause 当たり数十 B 程度の
    # offsets / weights + unique_signal_matrix のみ追加 (~9.4 MB / Stage A
    # genome 想定、24GB × 6worker 制約に対し許容内)。
    clause_weights: np.ndarray  # float64[n_clauses]
    dir_weights_flat: np.ndarray  # float64[total_dir_occurrences]
    dir_offsets: np.ndarray  # int64[n_clauses+1] CSR 形式
    dir_signal_idx: np.ndarray  # int64[total_dir_occurrences] - unique_signal_matrix 行 index
    gate_offsets: np.ndarray  # int64[n_clauses+1] CSR 形式
    gate_signal_idx: np.ndarray  # int64[total_gate_occurrences]
    unique_signal_matrix: np.ndarray  # float64[n_unique_signals, n_bars]
    clause_score_buffer: np.ndarray  # float64[n_clauses] - kernel out, per-bar overwrite


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
        # T037: runtime fired clause idx 集合 (compute_clause_score != 0.0 が
        # 1 度でも起きた clause)。observability only、entry/exit/composite には
        # 影響しない。詳細: devnotes/20260425-0958-signal-active-clause-metric/
        self._active_clause_indices: set[int] = set()

    @property
    def genome(self) -> Genome:
        return self._genome

    @property
    def active_clause_indices(self) -> frozenset[int]:
        """T037: backtest 中に compute_clause_score != 0.0 だった clause idx 集合。

        observability only、entry/exit/composite/fitness には影響しない。
        backtest 開始時 (`prepare()` または on_bar 初回) に空集合からスタート、
        各 bar で値を蓄積する。再 `prepare()` 時は集合をリセットする。
        """
        return frozenset(self._active_clause_indices)

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
        # T037: 再 prepare() で active clause counter もリセット
        # (新規 backtest 開始 = 集合空 が契約)。
        self._active_clause_indices.clear()

        if not hasattr(self._evaluator, "evaluate_all_bars"):
            return

        # T053 Round 1 Critical 1: clauses 空の ValueError 契約を prepared
        # path でも維持する (kernel 側は per-bar 検証しないため、ここで
        # fail-fast。unprepared path は compute_composite() が per-bar に
        # raise する既存挙動)。
        if not self._genome.clauses:
            raise ValueError(
                "Genome.clauses must not be empty (compute_composite contract)"
            )

        n_bars = len(bars)

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
                    # T053 Round 1 Critical 3: 配列長不一致を fail-fast。
                    # Round 2 Warning: list / Series も np.asarray で正規化
                    # してから shape 検証。
                    arr = np.asarray(
                        self._evaluator.evaluate_all_bars(bars, sig),
                        dtype=np.float64,
                    )
                    if arr.shape != (n_bars,):
                        raise ValueError(
                            f"evaluate_all_bars returned shape {arr.shape}, "
                            f"expected ({n_bars},) for signal {sig.name}"
                        )
                    arrays[key] = arr
                dir_entries.append((sig.name, arrays[key]))

            gate_entries: list[tuple[str, np.ndarray]] = []
            for sig in clause.local_gate:
                key = _signal_cache_key(sig)
                if key not in arrays:
                    arr = np.asarray(
                        self._evaluator.evaluate_all_bars(bars, sig),
                        dtype=np.float64,
                    )
                    if arr.shape != (n_bars,):
                        raise ValueError(
                            f"evaluate_all_bars returned shape {arr.shape}, "
                            f"expected ({n_bars},) for signal {sig.name}"
                        )
                    arrays[key] = arr
                gate_entries.append((sig.name, arrays[key]))

            clause_entries.append((tuple(dir_entries), tuple(gate_entries)))

        # === T053: flat ndarray 構築 (Numba kernel 用) ===
        n_clauses = len(self._genome.clauses)

        # unique signal matrix: arrays dict を行スタック。
        # 順序を deterministic にするため key 順でソート。
        unique_keys = sorted(arrays.keys())
        key_to_row = {k: i for i, k in enumerate(unique_keys)}
        n_unique = len(unique_keys)
        unique_signal_matrix = np.empty((n_unique, n_bars), dtype=np.float64)
        for k, row_idx in key_to_row.items():
            # arrays[k] は既に float64 + shape (n_bars,) (上で正規化済み)。
            # 念のため明示変換 (kernel との dtype 整合担保)。
            unique_signal_matrix[row_idx, :] = arrays[k]

        clause_weights = np.array(
            [c.weight for c in self._genome.clauses], dtype=np.float64
        )

        dir_offsets_list: list[int] = [0]
        dir_weights_list: list[float] = []
        dir_signal_idx_list: list[int] = []
        gate_offsets_list: list[int] = [0]
        gate_signal_idx_list: list[int] = []

        for clause in self._genome.clauses:
            for sig in clause.directional:
                dir_weights_list.append(sig.weight)
                dir_signal_idx_list.append(key_to_row[_signal_cache_key(sig)])
            dir_offsets_list.append(len(dir_weights_list))
            for sig in clause.local_gate:
                gate_signal_idx_list.append(key_to_row[_signal_cache_key(sig)])
            gate_offsets_list.append(len(gate_signal_idx_list))

        dir_weights_flat = np.array(dir_weights_list, dtype=np.float64)
        dir_offsets = np.array(dir_offsets_list, dtype=np.int64)
        dir_signal_idx = np.array(dir_signal_idx_list, dtype=np.int64)
        gate_offsets = np.array(gate_offsets_list, dtype=np.int64)
        gate_signal_idx = np.array(gate_signal_idx_list, dtype=np.int64)
        clause_score_buffer = np.empty(n_clauses, dtype=np.float64)

        self._prepared = PreparedSignals(
            arrays=arrays,
            clauses=tuple(clause_entries),
            genome=self._genome,  # identity 比較用 (O(1))
            clause_weights=clause_weights,
            dir_weights_flat=dir_weights_flat,
            dir_offsets=dir_offsets,
            dir_signal_idx=dir_signal_idx,
            gate_offsets=gate_offsets,
            gate_signal_idx=gate_signal_idx,
            unique_signal_matrix=unique_signal_matrix,
            clause_score_buffer=clause_score_buffer,
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

        # T053: prepared path は Numba JIT fused kernel に集約。
        # unprepared path (live feed / paper trading) は既存挙動を維持。
        if prepared is not None:
            # fast path: Numba njit fused kernel (composite + per-clause score
            # を 1 関数内で同時計算、dict 構築 / hashing / 二重 compute_clause_score
            # 呼び出しを排除)。
            composite = compute_composite_at_bar_jit(
                idx,
                prepared.clause_weights,
                prepared.dir_weights_flat,
                prepared.dir_offsets,
                prepared.dir_signal_idx,
                prepared.gate_offsets,
                prepared.gate_signal_idx,
                prepared.unique_signal_matrix,
                prepared.clause_score_buffer,
            )
            # T037: per-clause score buffer から exact `!= 0.0` で集計
            # (kernel が毎 bar 全 clause を上書きする契約)。
            buf = prepared.clause_score_buffer
            for ci in range(buf.shape[0]):
                if buf[ci] != 0.0:
                    self._active_clause_indices.add(ci)
        else:
            # unprepared path: 既存実装 (live feed / paper trading)。
            # Numba 化のリスクを後段に隔離するため pure Python のまま維持。
            values_per_clause: list[dict[str, float]] = []
            for clause in self._genome.clauses:
                vals: dict[str, float] = {}
                for sig in clause.directional:
                    vals[sig.name] = self._evaluator.evaluate(
                        self._bars, idx, sig
                    )
                for sig in clause.local_gate:
                    vals[sig.name] = self._evaluator.evaluate(
                        self._bars, idx, sig
                    )
                values_per_clause.append(vals)
            # T037: composite + active_clause を pure Python で計算。
            # 同 clause について compute_clause_score を 2 回計算するが
            # clause 数は 1-3 で重い処理ではない (既存挙動踏襲)。
            composite = compute_composite(
                self._genome.clauses, values_per_clause
            )
            for ci, (clause, vals) in enumerate(
                zip(self._genome.clauses, values_per_clause, strict=True)
            ):
                if compute_clause_score(clause, vals) != 0.0:
                    self._active_clause_indices.add(ci)

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
