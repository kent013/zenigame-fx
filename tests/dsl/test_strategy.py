"""T007: DslStrategy (Clause 版) のヒステリシス / time_stop / session close テスト。

PrimitiveEvaluator は Stub（ScriptedEvaluator）で composite を直接制御する。
idx に対して返すスカラー値を事前に仕込み、境界条件を直接検証する。
"""

from __future__ import annotations

from datetime import UTC, datetime, time
from decimal import Decimal

from src.broker.orders import OrderSignal, PortfolioSnapshot, Position
from src.domain.price import PriceBar
from src.dsl.genome import (
    ClauseConfig,
    Genome,
    PositionConfig,
    RiskConfig,
    SignalConfig,
)
from src.dsl.strategy import DslStrategy
from tests._helpers import make_bar


class ScriptedEvaluator:
    """bar index ごとに signal 値を返す stub evaluator。

    `script[idx][signal_name] = value` の形で事前に仕込む。
    """

    def __init__(self, script: dict[int, dict[str, float]]):
        self._script = script

    def evaluate(
        self, bars: list[PriceBar], idx: int, signal: SignalConfig
    ) -> float:
        return self._script[idx][signal.name]


def _mk_genome(
    entry_threshold: float = 0.3,
    exit_threshold: float = 0.1,
    time_stop_min: int = 0,
) -> Genome:
    return Genome(
        name="g",
        units=1000,
        clauses=(
            ClauseConfig(
                directional=(SignalConfig(name="F1", weight=1.0),),
                local_gate=(),
                weight=1.0,
            ),
        ),
        position=PositionConfig(
            entry_threshold=entry_threshold,
            exit_threshold=exit_threshold,
            max_pos=1,
            time_stop_min=time_stop_min,
        ),
        risk=RiskConfig(stop_atr=2.0, take_atr=3.0),
    )


def _empty_snapshot() -> PortfolioSnapshot:
    return PortfolioSnapshot(
        cash=Decimal("1000000"),
        equity=Decimal("1000000"),
        margin_used=Decimal(0),
        margin_level_pct=None,
    )


def _long_snapshot(entry_time: datetime) -> PortfolioSnapshot:
    pos = Position(
        id=1,
        instrument="USD_JPY",
        side="long",
        units=1000,
        entry_price=Decimal("154.0"),
        entry_time=entry_time,
        entry_margin=Decimal("6000"),
        leverage=25,
    )
    return PortfolioSnapshot(
        cash=Decimal("994000"),
        equity=Decimal("1000000"),
        margin_used=Decimal("6000"),
        margin_level_pct=None,
        positions=(pos,),
    )


def _short_snapshot(entry_time: datetime) -> PortfolioSnapshot:
    pos = Position(
        id=2,
        instrument="USD_JPY",
        side="short",
        units=1000,
        entry_price=Decimal("154.0"),
        entry_time=entry_time,
        entry_margin=Decimal("6000"),
        leverage=25,
    )
    return PortfolioSnapshot(
        cash=Decimal("994000"),
        equity=Decimal("1000000"),
        margin_used=Decimal("6000"),
        margin_level_pct=None,
        positions=(pos,),
    )


def _bar(minute: int) -> PriceBar:
    return make_bar(minute, bid_close="154.0", ask_close="154.01")


# ---- warmup ----


def test_warmup_no_signals() -> None:
    g = _mk_genome()
    # composite = 1.0 (entry 成立するはず) を仕込んでも warmup 中なので空
    evaluator = ScriptedEvaluator({i: {"F1": 1.0} for i in range(10)})
    strat = DslStrategy(g, evaluator, warmup_bars=3)
    assert strat.on_bar(_bar(0), _empty_snapshot()) == []
    assert strat.on_bar(_bar(1), _empty_snapshot()) == []
    # 3 本目で warmup を満たす
    result = strat.on_bar(_bar(2), _empty_snapshot())
    assert result == [OrderSignal(kind="open_long", units=1000)]


# ---- entry boundary ----


def test_entry_long_at_theta_on_equal() -> None:
    # composite == entry_threshold (=0.3) → >= なので open_long
    g = _mk_genome(entry_threshold=0.3)
    evaluator = ScriptedEvaluator({0: {"F1": 0.3}})
    strat = DslStrategy(g, evaluator)
    result = strat.on_bar(_bar(0), _empty_snapshot())
    assert result == [OrderSignal(kind="open_long", units=1000)]


def test_entry_short_at_theta_on_equal() -> None:
    # composite = -0.3, -composite = 0.3 == entry_threshold → open_short
    g = _mk_genome(entry_threshold=0.3)
    evaluator = ScriptedEvaluator({0: {"F1": -0.3}})
    strat = DslStrategy(g, evaluator)
    result = strat.on_bar(_bar(0), _empty_snapshot())
    assert result == [OrderSignal(kind="open_short", units=1000)]


def test_no_entry_just_below_theta_on() -> None:
    g = _mk_genome(entry_threshold=0.3)
    evaluator = ScriptedEvaluator({0: {"F1": 0.29}})
    strat = DslStrategy(g, evaluator)
    assert strat.on_bar(_bar(0), _empty_snapshot()) == []


# ---- hysteresis hold region ----


def test_hold_between_theta_off_and_theta_on_long() -> None:
    # long 保有中、θ_off (=0.1) <= composite < θ_on (=0.3): 何もしない
    g = _mk_genome(entry_threshold=0.3, exit_threshold=0.1)
    evaluator = ScriptedEvaluator({0: {"F1": 0.2}})
    strat = DslStrategy(g, evaluator)
    entry_time = datetime(2026, 4, 1, 0, 0, 0, tzinfo=UTC)
    result = strat.on_bar(_bar(5), _long_snapshot(entry_time))
    assert result == []


def test_hold_between_theta_off_and_theta_on_short() -> None:
    # short 保有中、θ_off (=0.1) <= -composite < θ_on (=0.3): 何もしない
    # composite = -0.2 なので -composite = 0.2
    g = _mk_genome(entry_threshold=0.3, exit_threshold=0.1)
    evaluator = ScriptedEvaluator({0: {"F1": -0.2}})
    strat = DslStrategy(g, evaluator)
    entry_time = datetime(2026, 4, 1, 0, 0, 0, tzinfo=UTC)
    result = strat.on_bar(_bar(5), _short_snapshot(entry_time))
    assert result == []


# ---- exit boundary ----


def test_exit_long_below_theta_off() -> None:
    g = _mk_genome(entry_threshold=0.3, exit_threshold=0.1)
    evaluator = ScriptedEvaluator({0: {"F1": 0.05}})
    strat = DslStrategy(g, evaluator)
    entry_time = datetime(2026, 4, 1, 0, 0, 0, tzinfo=UTC)
    result = strat.on_bar(_bar(5), _long_snapshot(entry_time))
    assert len(result) == 1
    assert result[0].kind == "close_position"


def test_exit_at_theta_off_equal_long_no_close() -> None:
    # long 保有 + composite == θ_off: < 厳密なので close しない
    g = _mk_genome(entry_threshold=0.3, exit_threshold=0.1)
    evaluator = ScriptedEvaluator({0: {"F1": 0.1}})
    strat = DslStrategy(g, evaluator)
    entry_time = datetime(2026, 4, 1, 0, 0, 0, tzinfo=UTC)
    assert strat.on_bar(_bar(5), _long_snapshot(entry_time)) == []


def test_exit_short_above_neg_theta_off() -> None:
    # short 保有 + -composite < θ_off → close
    # composite = 0.0 だと -composite = 0.0 < 0.1 → close
    g = _mk_genome(entry_threshold=0.3, exit_threshold=0.1)
    evaluator = ScriptedEvaluator({0: {"F1": 0.0}})
    strat = DslStrategy(g, evaluator)
    entry_time = datetime(2026, 4, 1, 0, 0, 0, tzinfo=UTC)
    result = strat.on_bar(_bar(5), _short_snapshot(entry_time))
    assert len(result) == 1
    assert result[0].kind == "close_position"


def test_exit_at_theta_off_equal_short_no_close() -> None:
    # short 保有 + -composite == θ_off: < 厳密なので close しない
    # -composite = 0.1 なので composite = -0.1
    g = _mk_genome(entry_threshold=0.3, exit_threshold=0.1)
    evaluator = ScriptedEvaluator({0: {"F1": -0.1}})
    strat = DslStrategy(g, evaluator)
    entry_time = datetime(2026, 4, 1, 0, 0, 0, tzinfo=UTC)
    assert strat.on_bar(_bar(5), _short_snapshot(entry_time)) == []


# ---- time_stop ----


def test_time_stop_forces_close() -> None:
    # time_stop_min=60、entry_time から 60 分経過で close
    g = _mk_genome(entry_threshold=0.3, exit_threshold=0.1, time_stop_min=60)
    # composite=0.5 (普段なら hold) だが time_stop で close される
    evaluator = ScriptedEvaluator({0: {"F1": 0.5}})
    strat = DslStrategy(g, evaluator)
    entry_time = datetime(2026, 4, 1, 0, 0, 0, tzinfo=UTC)
    # _bar(60) は entry_time + 60 分
    result = strat.on_bar(_bar(60), _long_snapshot(entry_time))
    assert len(result) == 1
    assert result[0].kind == "close_position"


def test_time_stop_just_before_no_close() -> None:
    g = _mk_genome(entry_threshold=0.3, exit_threshold=0.1, time_stop_min=60)
    evaluator = ScriptedEvaluator({0: {"F1": 0.5}})
    strat = DslStrategy(g, evaluator)
    entry_time = datetime(2026, 4, 1, 0, 0, 0, tzinfo=UTC)
    # 59 分経過: time_stop 未発火
    result = strat.on_bar(_bar(59), _long_snapshot(entry_time))
    assert result == []


def test_time_stop_disabled_when_zero() -> None:
    # time_stop_min=0 なら経過時間で close しない
    g = _mk_genome(entry_threshold=0.3, exit_threshold=0.1, time_stop_min=0)
    evaluator = ScriptedEvaluator({0: {"F1": 0.5}})
    strat = DslStrategy(g, evaluator)
    entry_time = datetime(2026, 4, 1, 0, 0, 0, tzinfo=UTC)
    result = strat.on_bar(_bar(1000), _long_snapshot(entry_time))
    assert result == []


# ---- session close ----


def test_session_close_forces_close() -> None:
    g = _mk_genome(entry_threshold=0.3, exit_threshold=0.1)
    evaluator = ScriptedEvaluator({0: {"F1": 0.5}})
    strat = DslStrategy(g, evaluator, session_close_utc=time(21, 0))
    entry_time = datetime(2026, 4, 1, 0, 0, 0, tzinfo=UTC)
    # bar_time.time() が 21:00 以降になるよう minute=21*60
    bar = make_bar(21 * 60, bid_close="154.0", ask_close="154.01")
    result = strat.on_bar(bar, _long_snapshot(entry_time))
    assert len(result) == 1
    assert result[0].kind == "close_position"


def test_session_close_none_no_force() -> None:
    g = _mk_genome(entry_threshold=0.3, exit_threshold=0.1)
    evaluator = ScriptedEvaluator({0: {"F1": 0.5}})
    strat = DslStrategy(g, evaluator, session_close_utc=None)
    entry_time = datetime(2026, 4, 1, 0, 0, 0, tzinfo=UTC)
    bar = make_bar(21 * 60, bid_close="154.0", ask_close="154.01")
    # session_close=None なので自発 close しない（engine EOD に委譲）
    assert strat.on_bar(bar, _long_snapshot(entry_time)) == []


def test_session_close_before_time_no_force() -> None:
    g = _mk_genome(entry_threshold=0.3, exit_threshold=0.1)
    evaluator = ScriptedEvaluator({0: {"F1": 0.5}})
    strat = DslStrategy(g, evaluator, session_close_utc=time(21, 0))
    entry_time = datetime(2026, 4, 1, 0, 0, 0, tzinfo=UTC)
    # 20:59
    bar = make_bar(20 * 60 + 59, bid_close="154.0", ask_close="154.01")
    assert strat.on_bar(bar, _long_snapshot(entry_time)) == []


# ---- T037: active_clause_indices (runtime fired clause counter) -------------


def _mk_two_clause_genome() -> Genome:
    """2 clause × 1 directional の genome (T037 active_clause テスト用)."""
    return Genome(
        name="g_two",
        units=1000,
        clauses=(
            ClauseConfig(
                directional=(SignalConfig(name="F1", weight=1.0),),
                local_gate=(),
                weight=1.0,
            ),
            ClauseConfig(
                directional=(SignalConfig(name="F2", weight=1.0),),
                local_gate=(),
                weight=1.0,
            ),
        ),
        position=PositionConfig(
            entry_threshold=0.3,
            exit_threshold=0.1,
            max_pos=1,
            time_stop_min=0,
        ),
        risk=RiskConfig(stop_atr=2.0, take_atr=3.0),
    )


def test_active_clause_indices_initially_empty() -> None:
    """T037: backtest 開始前は空集合."""
    g = _mk_two_clause_genome()
    evaluator = ScriptedEvaluator({0: {"F1": 0.5, "F2": 0.0}})
    strat = DslStrategy(g, evaluator)
    assert strat.active_clause_indices == frozenset()


def test_active_clause_indices_records_fired_clause_idx() -> None:
    """T037: clause_score != 0.0 だった clause idx が集合に入る.

    clause0 は F1=0.5 で score 0.5 (発火)、clause1 は F2=0.0 で score 0.0 (不発)。
    """
    g = _mk_two_clause_genome()
    evaluator = ScriptedEvaluator({0: {"F1": 0.5, "F2": 0.0}})
    strat = DslStrategy(g, evaluator)
    strat.on_bar(_bar(0), _empty_snapshot())
    assert strat.active_clause_indices == frozenset({0})


def test_active_clause_indices_excludes_never_fired_clause() -> None:
    """T037: 全期間で clause_score=0 だった clause は集合に入らない."""
    g = _mk_two_clause_genome()
    evaluator = ScriptedEvaluator(
        {
            0: {"F1": 0.5, "F2": 0.0},
            1: {"F1": -0.4, "F2": 0.0},  # clause1 は連続不発
        }
    )
    strat = DslStrategy(g, evaluator)
    strat.on_bar(_bar(0), _empty_snapshot())
    strat.on_bar(_bar(1), _empty_snapshot())
    assert strat.active_clause_indices == frozenset({0})


def test_active_clause_indices_accumulates_across_bars() -> None:
    """T037: 異なる bar で異なる clause が発火した場合は両方記録される."""
    g = _mk_two_clause_genome()
    evaluator = ScriptedEvaluator(
        {
            0: {"F1": 0.5, "F2": 0.0},  # clause0 のみ
            1: {"F1": 0.0, "F2": 0.4},  # clause1 のみ
        }
    )
    strat = DslStrategy(g, evaluator)
    strat.on_bar(_bar(0), _empty_snapshot())
    strat.on_bar(_bar(1), _empty_snapshot())
    assert strat.active_clause_indices == frozenset({0, 1})


def test_active_clause_indices_returns_frozenset_immutable() -> None:
    """T037: 返り値は frozenset (外部から mutate 不能)."""
    g = _mk_two_clause_genome()
    evaluator = ScriptedEvaluator({0: {"F1": 0.5, "F2": 0.0}})
    strat = DslStrategy(g, evaluator)
    strat.on_bar(_bar(0), _empty_snapshot())
    s = strat.active_clause_indices
    assert isinstance(s, frozenset)
    # 外部参照からは mutate 不能 (frozenset は add/remove なし)
    assert not hasattr(s, "add")


# ---------------------------------------------------------------------------
# T053: prepare() の事前検証 + Numba kernel 用 PreparedSignals 拡張
# devnotes/20260427-1723-composite-numba-jit/detailed-design.md 施策 3
# ---------------------------------------------------------------------------


import numpy as np  # noqa: E402
import pytest  # noqa: E402


class _AllBarsEvaluator:
    """evaluate_all_bars を実装した stub. T053 の prepare() path 用.

    signal_returns: signal name -> ndarray (or list-like). prepare() からは
    name 単位で配列を返す。len は基本 bars と同長だが、length-mismatch テスト
    では意図的に bars 長と異なる長さにする。
    """

    def __init__(
        self,
        signal_returns: dict[str, np.ndarray],
        force_length: int | None = None,
    ) -> None:
        self._signal_returns = signal_returns
        self._force_length = force_length

    def evaluate(
        self, bars: list[PriceBar], idx: int, signal: SignalConfig
    ) -> float:
        return float(self._signal_returns[signal.name][idx])

    def evaluate_all_bars(
        self, bars: list[PriceBar], signal: SignalConfig
    ) -> np.ndarray:
        arr = self._signal_returns[signal.name]
        if self._force_length is not None:
            return np.asarray(arr[: self._force_length], dtype=np.float64)
        # bars 長で切り詰め (= 一致)
        return np.asarray(arr[: len(bars)], dtype=np.float64)


def _mk_genome_two_clauses_shared_signal() -> Genome:
    """同じ (name, params) の signal を 2 clause に出す Genome.

    unique_signal_matrix dedup の検証用。
    """
    return Genome(
        name="g_shared",
        units=1000,
        clauses=(
            ClauseConfig(
                directional=(
                    SignalConfig(name="F1", weight=1.0, params={"n": 5}),
                ),
                local_gate=(),
                weight=1.0,
            ),
            ClauseConfig(
                directional=(
                    # 同 (name, params) - 共有キャッシュ対象
                    SignalConfig(name="F1", weight=0.5, params={"n": 5}),
                    SignalConfig(name="F2", weight=1.0),
                ),
                local_gate=(),
                weight=1.0,
            ),
        ),
        position=PositionConfig(
            entry_threshold=0.3,
            exit_threshold=0.1,
            max_pos=1,
            time_stop_min=0,
        ),
        risk=RiskConfig(stop_atr=2.0, take_atr=3.0),
    )


def _mk_bars(n: int) -> list[PriceBar]:
    return [_bar(i) for i in range(n)]


def test_prepared_signals_unique_signal_matrix_dedupes_shared_primitives() -> None:
    """V (T053): 同 (name, params) を 2 clause に出すと unique_signal_matrix
    の行数が 2 ではなく 1 になる (arrays dict 共有キャッシュ不変条件)."""
    n_bars = 5
    g = _mk_genome_two_clauses_shared_signal()
    sig_returns = {
        "F1": np.linspace(0.1, 0.5, n_bars),
        "F2": np.linspace(0.2, 0.6, n_bars),
    }
    evaluator = _AllBarsEvaluator(sig_returns)
    strat = DslStrategy(g, evaluator)
    strat.prepare(_mk_bars(n_bars))
    prepared = strat._prepared
    assert prepared is not None
    # 2 clause に F1 が登場するが unique key は (F1, n=5) と F2 の 2 個のみ
    assert prepared.unique_signal_matrix.shape == (2, n_bars)
    # arrays dict も同 invariant
    assert len(prepared.arrays) == 2


def test_prepared_signals_dir_offsets_csr_form() -> None:
    """V (T053): dir_offsets が CSR 形式: offsets[ci+1] - offsets[ci] = 当該
    clause の dir signal 数."""
    n_bars = 5
    g = _mk_genome_two_clauses_shared_signal()
    sig_returns = {
        "F1": np.linspace(0.1, 0.5, n_bars),
        "F2": np.linspace(0.2, 0.6, n_bars),
    }
    evaluator = _AllBarsEvaluator(sig_returns)
    strat = DslStrategy(g, evaluator)
    strat.prepare(_mk_bars(n_bars))
    prepared = strat._prepared
    assert prepared is not None
    # clause 0: directional 1 個 (F1)
    # clause 1: directional 2 個 (F1, F2)
    assert prepared.dir_offsets.tolist() == [0, 1, 3]
    assert (
        prepared.dir_offsets[1] - prepared.dir_offsets[0]
        == len(g.clauses[0].directional)
    )
    assert (
        prepared.dir_offsets[2] - prepared.dir_offsets[1]
        == len(g.clauses[1].directional)
    )
    # gate 側はどちらも 0 個
    assert prepared.gate_offsets.tolist() == [0, 0, 0]


def test_prepared_signals_dtypes_are_float64_int64() -> None:
    """V (T053): kernel と契約する dtype が明示 float64 / int64."""
    n_bars = 3
    g = _mk_genome_two_clauses_shared_signal()
    sig_returns = {
        "F1": np.array([0.1, 0.2, 0.3]),
        "F2": np.array([0.4, 0.5, 0.6]),
    }
    evaluator = _AllBarsEvaluator(sig_returns)
    strat = DslStrategy(g, evaluator)
    strat.prepare(_mk_bars(n_bars))
    prepared = strat._prepared
    assert prepared is not None
    assert prepared.clause_weights.dtype == np.float64
    assert prepared.dir_weights_flat.dtype == np.float64
    assert prepared.unique_signal_matrix.dtype == np.float64
    assert prepared.clause_score_buffer.dtype == np.float64
    assert prepared.dir_offsets.dtype == np.int64
    assert prepared.dir_signal_idx.dtype == np.int64
    assert prepared.gate_offsets.dtype == np.int64
    assert prepared.gate_signal_idx.dtype == np.int64


def test_prepare_on_evaluator_without_evaluate_all_bars_returns_no_op() -> None:
    """V (T053): evaluate_all_bars を持たない evaluator では prepare() が
    no-op になり _prepared は None のまま (既存挙動の保持)."""
    g = _mk_genome()
    # ScriptedEvaluator は evaluate_all_bars を実装しない
    evaluator = ScriptedEvaluator({0: {"F1": 0.5}})
    strat = DslStrategy(g, evaluator)
    strat.prepare(_mk_bars(3))
    assert strat._prepared is None


def test_prepare_raises_on_clauses_empty() -> None:
    """V10 (Round 1 Critical 1): Genome.clauses == () で prepare() が
    ValueError を raise する (compute_composite() の契約を prepared path
    でも維持する)."""
    g = Genome(
        name="g_empty",
        units=1000,
        clauses=(),
        position=PositionConfig(
            entry_threshold=0.3,
            exit_threshold=0.1,
            max_pos=1,
            time_stop_min=0,
        ),
        risk=RiskConfig(stop_atr=2.0, take_atr=3.0),
    )
    # evaluator は evaluate_all_bars を持つもの (= prepared path に入る)
    evaluator = _AllBarsEvaluator({})
    strat = DslStrategy(g, evaluator)
    with pytest.raises(ValueError, match="clauses must not be empty"):
        strat.prepare(_mk_bars(3))


def test_prepare_raises_on_evaluate_all_bars_length_mismatch() -> None:
    """V11 (Round 1 Critical 3): evaluate_all_bars が len(bars) と異なる
    長さを返すと prepare() が ValueError を raise (fail-fast)."""
    n_bars = 5
    g = _mk_genome()
    # 4 個 (短い) を返す
    evaluator_short = _AllBarsEvaluator(
        {"F1": np.array([0.1, 0.2, 0.3, 0.4, 0.5])},
        force_length=4,
    )
    strat = DslStrategy(g, evaluator_short)
    with pytest.raises(ValueError, match="evaluate_all_bars returned shape"):
        strat.prepare(_mk_bars(n_bars))

    # 6 個 (長い) を返す
    evaluator_long = _AllBarsEvaluator(
        {"F1": np.array([0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7])},
        force_length=6,
    )
    strat2 = DslStrategy(g, evaluator_long)
    with pytest.raises(ValueError, match="evaluate_all_bars returned shape"):
        strat2.prepare(_mk_bars(n_bars))


def test_on_bar_prepared_path_matches_unprepared_path() -> None:
    """V2 / V3 (T053): prepared path (Numba kernel) と unprepared path
    (純 Python) が同 genome × 同 signal values で完全一致する.

    composite (allclose) と active_clause_indices (exact) の両方を検証。
    composite 同値は kernel 戻り値と純 Python `compute_composite` の戻り値を
    bar 毎に直接比較する (Codex round-1 [Warning] 反映: prepared/unprepared
    の発注 (open_long/open_short/close_position) が一致するだけでは composite
    の数値同値性を検出できない可能性があるため)。
    """
    from src.dsl.composite import (  # local import to avoid name shadowing
        compute_composite,
        compute_composite_at_bar_jit,
    )

    n_bars = 20
    rng = np.random.default_rng(20260427)
    g = _mk_two_clause_genome()
    sig_returns = {
        "F1": rng.uniform(-1.0, 1.0, n_bars),
        "F2": rng.uniform(-1.0, 1.0, n_bars),
    }

    # === prepared path (kernel): strategy 経由で active_clause を蓄積 ===
    eval_prepared = _AllBarsEvaluator(sig_returns)
    strat_prepared = DslStrategy(g, eval_prepared)
    strat_prepared.prepare(_mk_bars(n_bars))
    prepared = strat_prepared._prepared
    assert prepared is not None
    snapshot = _empty_snapshot()
    composites_jit: list[float] = []
    for i in range(n_bars):
        strat_prepared.on_bar(_bar(i), snapshot)
        # kernel を独立に呼び直して composite を直接観測 (on_bar 内部で
        # buffer は kernel の最新出力で上書きされるが、composite 戻り値は
        # 内部のローカル変数のため、ここで再度 kernel 直接呼び出しで取得)。
        c = compute_composite_at_bar_jit(
            i,
            prepared.clause_weights,
            prepared.dir_weights_flat,
            prepared.dir_offsets,
            prepared.dir_signal_idx,
            prepared.gate_offsets,
            prepared.gate_signal_idx,
            prepared.unique_signal_matrix,
            prepared.clause_score_buffer,
        )
        composites_jit.append(c)

    # === unprepared path (pure Python): 同 signal values を ScriptedEvaluator 経由 ===
    eval_unprepared = ScriptedEvaluator(
        {
            i: {
                "F1": float(sig_returns["F1"][i]),
                "F2": float(sig_returns["F2"][i]),
            }
            for i in range(n_bars)
        }
    )
    strat_unprepared = DslStrategy(g, eval_unprepared)
    # prepare() を呼ばない (= unprepared path)
    composites_py: list[float] = []
    for i in range(n_bars):
        strat_unprepared.on_bar(_bar(i), snapshot)
        # 純 Python 実装で同 idx の composite を観測 (kernel と独立 oracle)
        values_per_clause = [
            {
                sig.name: float(sig_returns[sig.name][i])
                for sig in (*clause.directional, *clause.local_gate)
            }
            for clause in g.clauses
        ]
        composites_py.append(compute_composite(g.clauses, values_per_clause))

    # composite 同値: V2 aggregate np.allclose(atol=1e-6, rtol=0)
    assert np.allclose(composites_jit, composites_py, atol=1e-6, rtol=0)

    # active_clause_indices が完全一致 (T037 V3 exact parity)
    assert (
        strat_prepared.active_clause_indices
        == strat_unprepared.active_clause_indices
    )


def test_on_bar_unprepared_path_unchanged() -> None:
    """V (T053): unprepared path (live feed) は既存挙動を維持 (Numba 経由なし)."""
    g = _mk_genome()
    evaluator = ScriptedEvaluator({0: {"F1": 0.5}, 1: {"F1": 0.0}})
    strat = DslStrategy(g, evaluator)
    # prepare() を呼ばない → _prepared is None
    assert strat._prepared is None
    orders_0 = strat.on_bar(_bar(0), _empty_snapshot())
    # composite = 1.0 * 0.5 / 1.0 = 0.5 >= 0.3 → open_long
    assert len(orders_0) == 1
    assert orders_0[0].kind == "open_long"
    # active clause が記録される
    assert 0 in strat.active_clause_indices
