"""Tests for ``scripts/alpha_factory/run_ga.py`` (T018).

- Config loader (``src/alpha_factory/config.py``) の YAML → dataclass 変換
- Registry bridge (``src/alpha_factory/_registry_bridge.py``)
- smoke run (DB mock で pop=5, gen=1 完走 + archive/summary 生成)

DB mock は ``SessionLocal`` を monkeypatch し、``CurrencyPair`` / ``PriceBarM1``
の stmt を stmt 文字列で判別して振り分ける (R1 review §テスト妥当性)。
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from scripts.alpha_factory import run_ga as run_ga_module
from src.alpha_factory._registry_bridge import build_random_gen_registry
from src.alpha_factory.config import (
    AlphaFactoryConfig,
    GAConfig,
    load_config,
)
from src.alpha_factory.primitives import clear as _clear_registry

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = REPO_ROOT / "tests" / "fixtures" / "alpha_factory_min_config.yaml"
DEFAULT_CONFIG_PATH = REPO_ROOT / "config" / "alpha_factory" / "default.yaml"


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _make_currency_pair(instrument: str = "EUR_JPY") -> Any:
    """Fake CurrencyPair (SQLAlchemy instrumentation 回避のため SimpleNamespace)."""
    return SimpleNamespace(
        id=1,
        oanda_name=instrument,
        display_name=instrument,
        base_currency=instrument.split("_")[0],
        quote_currency=instrument.split("_")[1],
        pip_location=-2 if "JPY" in instrument else -4,
        display_precision=5,
        trade_units_precision=0,
        margin_rate=Decimal("0.04"),
        minimum_trade_size=1,
        maximum_order_units=100_000_000,
        instrument_type="CURRENCY",
        is_active=True,
    )


def _make_bar_row(
    *, pair_id: int, bar_time: datetime, mid: Decimal = Decimal("154.000")
) -> Any:
    spread = Decimal("0.005")
    bid = mid
    ask = mid + spread
    return SimpleNamespace(
        id=0,
        pair_id=pair_id,
        bar_time=bar_time,
        open_bid=bid,
        high_bid=bid,
        low_bid=bid,
        close_bid=bid,
        open_ask=ask,
        high_ask=ask,
        low_ask=ask,
        close_ask=ask,
        volume=10,
        complete=True,
    )


def _generate_bar_rows(
    pair: Any,
    start: datetime,
    end: datetime,
    step_minutes: int = 60,
) -> list[Any]:
    rows: list[Any] = []
    cur = start
    i = 0
    while cur < end:
        mid = Decimal("154.000") + Decimal(
            str((i % 10) * 0.001)
        )  # わずかに変動
        rows.append(_make_bar_row(pair_id=pair.id, bar_time=cur, mid=mid))
        cur = cur + timedelta(minutes=step_minutes)
        i += 1
    return rows


class _ScalarsResult:
    """SQLAlchemy ``session.scalars(stmt)`` の薄い mock."""

    def __init__(self, kind: str, rows: list[Any], pair: Any | None):
        self._kind = kind
        self._rows = rows
        self._pair = pair

    def one_or_none(self) -> Any:
        if self._kind == "pair":
            return self._pair
        return None

    def all(self) -> list[Any]:
        if self._kind == "bars":
            return list(self._rows)
        return []


class _ExecuteResult:
    """T106: SQLAlchemy ``session.execute(stmt)`` Result の薄い mock.

    `_stream_bars` は属性アクセスのみで row を消費する契約なので、 row は
    SimpleNamespace (bar_time / open_bid / ... 属性を持つ) をそのまま yield する。
    `__iter__` + `close()` を実装し、 try/finally の close 契約をテスト可能にする。
    """

    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows
        self.closed = False

    def __iter__(self) -> Any:
        return iter(self._rows)

    def close(self) -> None:
        self.closed = True


class _MockSession:
    """``SessionLocal`` 置換 mock。stmt の内容のみで分岐する (call-order 非依存)。

    判別ロジック (R1 impl-review B3 対応):
        - ``currency_pair`` を table として参照している stmt → pair
        - ``price_bar_m1`` を table として参照している stmt → bars 範囲から選別
          - DatetimeClause の whereclause をテキストで parse し、range が
            dataset.end 以降なら holdout、それ以前なら Stage B。
    """

    def __init__(
        self,
        pair: Any,
        stage_b_rows: list[Any],
        holdout_rows: list[Any],
        dataset_end: datetime,
    ) -> None:
        self._pair = pair
        self._stage_b_rows = stage_b_rows
        self._holdout_rows = holdout_rows
        self._dataset_end = dataset_end
        self.bars_calls: list[str] = []

    def __enter__(self) -> _MockSession:
        return self

    def __exit__(self, *a: Any) -> None:
        return None

    def _classify_bars_stmt(self, stmt: Any) -> tuple[str, list[Any]]:
        """price_bar_m1 stmt を holdout / stage_b に振り分ける (共通ロジック)."""
        try:
            compiled = stmt.compile(compile_kwargs={"literal_binds": True})
            compiled_str = str(compiled).lower()
        except Exception:  # pragma: no cover - fallback
            compiled_str = str(stmt).lower()
        end_iso = self._dataset_end.isoformat(sep=" ").lower()
        if f">= '{end_iso}'" in compiled_str or f">='{end_iso}'" in compiled_str:
            return "holdout", self._holdout_rows
        return "stage_b", self._stage_b_rows

    def scalars(self, stmt: Any) -> _ScalarsResult:
        stmt_str = str(stmt).lower()
        if "currency_pair" in stmt_str and "price_bar_m1" not in stmt_str:
            return _ScalarsResult("pair", [], self._pair)
        if "price_bar_m1" in stmt_str:
            kind, rows = self._classify_bars_stmt(stmt)
            self.bars_calls.append(kind)
            return _ScalarsResult("bars", list(rows), None)
        return _ScalarsResult("unknown", [], None)

    def execute(self, stmt: Any) -> _ExecuteResult:
        """T106: column-tuple streaming 経路 (``session.execute(stmt)``)。"""
        stmt_str = str(stmt).lower()
        if "price_bar_m1" in stmt_str:
            kind, rows = self._classify_bars_stmt(stmt)
            self.bars_calls.append(kind)
            return _ExecuteResult(list(rows))
        return _ExecuteResult([])


def _install_mock_session(
    monkeypatch: pytest.MonkeyPatch,
    pair: Any,
    stage_b_rows: list[Any],
    holdout_rows: list[Any],
    dataset_end: datetime,
) -> list[_MockSession]:
    """run_ga.SessionLocal を差し替えて MockSession を返す.

    T087: テスト fixture は step_minutes=60 で bar 行を生成するため、
    `_BARS_PER_DAY` を本番値 (1440 = M1) から 24 (= 60min × 24h) へ patch して
    stage_a_window_days と bar 数の換算が一致するようにする。
    """
    created: list[_MockSession] = []

    def _factory() -> _MockSession:
        sess = _MockSession(pair, stage_b_rows, holdout_rows, dataset_end)
        created.append(sess)
        return sess

    monkeypatch.setattr(run_ga_module, "SessionLocal", _factory)
    monkeypatch.setattr(run_ga_module, "_BARS_PER_DAY", 24)
    return created


# ---------------------------------------------------------------------------
# Config loader
# ---------------------------------------------------------------------------


def test_load_config_from_fixture_yaml() -> None:
    cfg = load_config(CONFIG_PATH)
    assert isinstance(cfg, AlphaFactoryConfig)
    assert cfg.dataset.instrument == "EUR_JPY"
    assert cfg.dataset.start == datetime(2026, 1, 1, tzinfo=UTC)
    assert cfg.dataset.end == datetime(2026, 1, 8, tzinfo=UTC)
    assert cfg.ga.population_size == 5
    assert cfg.ga.seed == 42
    assert cfg.backtest.initial_cash == Decimal("1000000")
    assert cfg.backtest.max_spread_bps == Decimal("5")
    # live_criteria は stage_gate.live_criteria に注入されて property で取れる
    assert cfg.live_criteria["sharpe_min"] == 1.0
    assert cfg.stage_gate.live_criteria["sharpe_min"] == 1.0
    # stage_windows
    assert cfg.stage_windows.stage_a_window_days == 1
    # T087: allow_stage_c_fallback_slice は廃止 (config attribute も削除)


def test_load_config_default_yaml_loads() -> None:
    """production default.yaml が loader を通ること."""
    cfg = load_config(DEFAULT_CONFIG_PATH)
    assert cfg.dataset.instrument == "EUR_JPY"
    assert cfg.ga.population_size == 40
    # live_criteria は yaml top-level から injected
    # cycle12-16 North Star: sharpe_min 1.0→1.5 (維持)、total_pnl_min 50000→70000→74000→(診断revert)70000。
    # trade_count_min は cycle12で100へ上げたが構造的到達不能(R94 Stage C0)で cycle13に50へ revert。
    # cycle15: 70000→74000 引き上げたが R97(seed70)で StageC=0 崩壊 (total_pnl_min は in-loop 作用)。
    # cycle16: 74000→70000 診断revert (70k+seed70 反実仮想で閾値因果切り分け。70kは R95/R96 2seed validated)。
    assert float(cfg.live_criteria["sharpe_min"]) == 1.5
    assert int(cfg.live_criteria["trade_count_min"]) == 50
    assert float(cfg.live_criteria["total_pnl_min"]) == 70000


def test_parse_args_max_workers_canonical_flag() -> None:
    """T052: --max-workers が args.max_workers に反映される。"""
    from scripts.alpha_factory.run_ga import _parse_args

    args = _parse_args(["--max-workers", "4"])
    assert args.max_workers == 4


def test_parse_args_workers_alias_flag() -> None:
    """T052: --workers エイリアスが args.max_workers に統合される。"""
    from scripts.alpha_factory.run_ga import _parse_args

    args = _parse_args(["--workers", "6"])
    assert args.max_workers == 6


def test_parse_args_workers_default_none() -> None:
    """T052: 未指定時は None (YAML config の値が使われる)。"""
    from scripts.alpha_factory.run_ga import _parse_args

    args = _parse_args([])
    assert args.max_workers is None


def test_parse_args_conflict_between_max_workers_and_workers_raises() -> None:
    """T052: --max-workers と --workers が異なる値だと SystemExit (argparse error)."""
    from scripts.alpha_factory.run_ga import _parse_args

    with pytest.raises(SystemExit):
        _parse_args(["--max-workers", "4", "--workers", "8"])


def test_parse_args_strict_memory_guard_flag() -> None:
    """T052: --strict-memory-guard で args.strict_memory_guard=True。"""
    from scripts.alpha_factory.run_ga import _parse_args

    args = _parse_args(["--strict-memory-guard"])
    assert args.strict_memory_guard is True


def test_args_to_overrides_propagates_max_workers() -> None:
    """T052: --max-workers が ga.max_workers override に伝搬。"""
    from scripts.alpha_factory.run_ga import _args_to_overrides, _parse_args

    args = _parse_args(["--max-workers", "4"])
    overrides = _args_to_overrides(args)
    assert overrides["ga"]["max_workers"] == 4


def test_main_constructs_lane_eval_context_with_preflight_payload(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """T052 Codex impl-review §1 Critical 反映: run_ga.main() が
    LaneEvalContext を構築する際に preflight 値を埋め込み、worker 側短絡が
    本番経路で発火することを保証する (LaneEvalContext.preflight_underfilled
    を後から外部から確認するため、GenomeEvaluator を spy する).

    Codex impl-review-round-2 Warning 反映: 固定 /tmp パス回避、tmp_path 使用。
    """
    from src.alpha_factory.parallel_eval import GenomeEvaluator as _OrigEvaluator

    captured: dict[str, Any] = {}

    class _SpyEvaluator(_OrigEvaluator):
        def __init__(
            self, max_workers, stage_gate_cfg, cross_pair_cfg,
            prim_evaluator, lane_contexts, **kwargs,
        ):
            captured["lane_contexts"] = dict(lane_contexts)
            # max_tasks_per_child 等の keyword-only 引数を透過
            super().__init__(
                max_workers, stage_gate_cfg, cross_pair_cfg,
                prim_evaluator, lane_contexts, **kwargs,
            )

    monkeypatch.setattr(run_ga_module, "GenomeEvaluator", _SpyEvaluator)
    pair, stage_b_rows, holdout_rows = _prepare_smoke_inputs(fallback_holdout=False)
    _install_mock_session(
        monkeypatch, pair, stage_b_rows, holdout_rows,
        datetime(2026, 1, 8, tzinfo=UTC),
    )
    monkeypatch.setattr(run_ga_module, "RUN_REPORTS_DIR", tmp_path / "reports")
    monkeypatch.setattr(run_ga_module, "RUN_CACHE_DIR", tmp_path / "cache")
    monkeypatch.setattr(run_ga_module, "get_latest_run_number", lambda: 0)
    from src.alpha_factory.archive import GenomeArchive as _Archive

    monkeypatch.setattr(_Archive, "DEFAULT_OUTPUT_DIR", tmp_path / "archive")
    rc = run_ga_module.main(
        [
            "--config", str(CONFIG_PATH),
            "--run-id", "preflight_test",
            "--population-size", "2",
            "--generations", "0",
            "--seed", "42",
            "--no-report",
        ]
    )
    assert rc == 0
    # captured lane_contexts に LaneEvalContext が入っており、preflight_payload が
    # non-None であることを確認 (preflight_underfilled は値次第だが payload は必ず生成)
    assert "lane_contexts" in captured
    lane_ctx = next(iter(captured["lane_contexts"].values()))
    assert lane_ctx.preflight_payload is not None, (
        "LaneEvalContext.preflight_payload must be set in main() "
        "(Codex impl-review §1 Critical)"
    )
    # T087: bars_stage_b は Stage A 期間 (末尾 stage_a_window_days=1 = 24 bars) を
    # 除外したもの。 7d × 24h = 168 bars 全体から末尾 24 bars を引いた 144 bars。
    assert lane_ctx.preflight_payload.n_bars == len(stage_b_rows) - 24


def test_load_config_with_cli_overrides() -> None:
    overrides = {
        "dataset": {"instrument": "USD_JPY"},
        "ga": {"population_size": 3, "seed": 999, "generations": None},
    }
    cfg = load_config(CONFIG_PATH, overrides=overrides)
    assert cfg.dataset.instrument == "USD_JPY"
    assert cfg.ga.population_size == 3
    assert cfg.ga.seed == 999
    # None override → skip (元の値保持)
    assert cfg.ga.generations == 1


def test_dataset_config_rejects_reversed_range() -> None:
    overrides = {
        "dataset": {
            "end": "2025-01-01T00:00:00Z"  # start より前
        }
    }
    with pytest.raises(ValueError, match=r"dataset\.end"):
        load_config(CONFIG_PATH, overrides=overrides)


def test_ga_config_rejects_invalid() -> None:
    with pytest.raises(ValueError, match="elite_count"):
        GAConfig(
            population_size=4,
            generations=1,
            crossover_rate=0.7,
            mutation_rate=0.3,
            tournament_size=3,
            elite_count=10,  # > population_size
            max_depth=2,
        )
    with pytest.raises(ValueError, match="elite_count"):
        GAConfig(
            population_size=4,
            generations=1,
            crossover_rate=0.7,
            mutation_rate=0.3,
            tournament_size=3,
            elite_count=-1,
            max_depth=2,
        )


# ---------------------------------------------------------------------------
# Registry bridge
# ---------------------------------------------------------------------------


@pytest.fixture
def registry_clean() -> Callable[[], None]:
    """primitives registry の isolation 用 fixture."""
    _clear_registry()
    yield
    # 後続テスト用に再登録 (次の test run では build_random_gen_registry が
    # ensure_registered 経由で再 populate する)


def test_registry_bridge_returns_32_specs(registry_clean: None) -> None:
    reg = build_random_gen_registry()
    assert len(reg) == 32
    # categoryは directional/modulator のみ
    for spec in reg.values():
        assert spec.category in ("directional", "modulator")
    # domain は generic/pair_specific のみ
    for spec in reg.values():
        assert spec.domain in ("generic", "pair_specific")


# ---------------------------------------------------------------------------
# Smoke run (DB mock)
# ---------------------------------------------------------------------------


def _prepare_smoke_inputs(
    fallback_holdout: bool,
) -> tuple[Any, list[Any], list[Any]]:
    pair = _make_currency_pair("EUR_JPY")
    start = datetime(2026, 1, 1, tzinfo=UTC)
    end = datetime(2026, 1, 8, tzinfo=UTC)
    stage_b_rows = _generate_bar_rows(pair, start, end, step_minutes=60)
    if fallback_holdout:
        holdout_rows: list[Any] = []
    else:
        holdout_rows = _generate_bar_rows(
            pair,
            end,
            end + timedelta(days=1),
            step_minutes=60,
        )
    return pair, stage_b_rows, holdout_rows


def test_load_lane_bars_disjoint_stage_a_b(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """T087: bars_stage_a と bars_stage_b の bar_time 集合が完全 disjoint."""
    pair, stage_b_rows, holdout_rows = _prepare_smoke_inputs(
        fallback_holdout=False
    )
    _install_mock_session(
        monkeypatch,
        pair,
        stage_b_rows,
        holdout_rows,
        datetime(2026, 1, 8, tzinfo=UTC),
    )
    from src.alpha_factory.config import load_config as _load

    cfg = _load(CONFIG_PATH)
    bundle = run_ga_module._load_lane_bars(
        cfg.dataset.instrument, cfg.dataset, cfg.stage_windows
    )
    a_set = {b.bar_time for b in bundle.bars_stage_a}
    b_set = {b.bar_time for b in bundle.bars_stage_b}
    assert a_set & b_set == set()
    # Stage A は末尾、 Stage B はそれ以前
    assert max(b.bar_time for b in bundle.bars_stage_b) < min(
        b.bar_time for b in bundle.bars_stage_a
    )


def test_load_lane_bars_can_skip_holdout_for_stage_a_only_anchor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """T117: multi-pair anchor は Stage A のみ使うため holdout 不在でもロード可能。"""
    pair, stage_b_rows, _holdout_rows = _prepare_smoke_inputs(
        fallback_holdout=True
    )
    sessions = _install_mock_session(
        monkeypatch,
        pair,
        stage_b_rows,
        [],
        datetime(2026, 1, 8, tzinfo=UTC),
    )
    from src.alpha_factory.config import load_config as _load

    cfg = _load(CONFIG_PATH)
    bundle = run_ga_module._load_lane_bars(
        cfg.dataset.instrument,
        cfg.dataset,
        cfg.stage_windows,
        require_holdout=False,
    )
    assert bundle.bars_stage_a
    assert bundle.bars_stage_b
    assert bundle.bars_holdout == []
    assert sessions[-1].bars_calls == ["stage_b"]


def test_load_lane_bars_raises_when_dataset_smaller_or_equal_to_stage_a(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """T087: stage_a_n_bars >= len(bars_stage_b_full) で RuntimeError (== 境界含む)."""
    pair = _make_currency_pair("EUR_JPY")
    start = datetime(2026, 1, 1, tzinfo=UTC)
    end = datetime(2026, 1, 2, tzinfo=UTC)
    # 1 day の dataset を 60-min step で生成 → 24 bars。
    # _install_mock_session で _BARS_PER_DAY=24 に patch されるため、
    # stage_a_window_days=1 → stage_a_n_bars=24 = len(stage_b_full) で `>=` 違反。
    stage_b_rows = _generate_bar_rows(pair, start, end, step_minutes=60)
    holdout_rows = _generate_bar_rows(
        pair, end, end + timedelta(days=1), step_minutes=60
    )
    _install_mock_session(
        monkeypatch, pair, stage_b_rows, holdout_rows, end
    )
    from src.alpha_factory.config import load_config as _load

    overrides = {
        "dataset": {
            "instrument": "EUR_JPY",
            "start": "2026-01-01T00:00:00Z",
            "end": "2026-01-02T00:00:00Z",
        },
        "stage_windows": {"stage_a_window_days": 1},
    }
    cfg = _load(CONFIG_PATH, overrides=overrides)
    with pytest.raises(RuntimeError, match="dataset too short"):
        run_ga_module._load_lane_bars(
            cfg.dataset.instrument, cfg.dataset, cfg.stage_windows
        )


# ---------------------------------------------------------------------------
# T106: server-side cursor streaming
# ---------------------------------------------------------------------------


class _SpyExecuteResult:
    """execute 結果 mock: rows を yield しつつ close 呼び出しを記録する."""

    def __init__(self, rows: list[Any], *, raise_after: int | None = None) -> None:
        self._rows = rows
        self._raise_after = raise_after
        self.closed = False

    def __iter__(self) -> Any:
        for i, row in enumerate(self._rows):
            if self._raise_after is not None and i >= self._raise_after:
                raise RuntimeError("simulated iteration error")
            yield row

    def close(self) -> None:
        self.closed = True


class _SpySession:
    """execute(stmt) を 1 度だけ受ける spy。 stmt と result を保持する."""

    def __init__(self, result: _SpyExecuteResult) -> None:
        self.result = result
        self.executed_stmt: Any = None

    def execute(self, stmt: Any) -> _SpyExecuteResult:
        self.executed_stmt = stmt
        return self.result


def test_load_lane_bars_streams_via_yield_per() -> None:
    """T106: _stream_bars の stmt に yield_per が乗り、 result.close() が呼ばれる."""
    pair = _make_currency_pair("EUR_JPY")
    rows = _generate_bar_rows(
        pair,
        datetime(2026, 1, 1, tzinfo=UTC),
        datetime(2026, 1, 1, 3, tzinfo=UTC),
        step_minutes=60,
    )
    result = _SpyExecuteResult(rows)
    session = _SpySession(result)

    bars = run_ga_module._stream_bars(
        session,  # type: ignore[arg-type]
        pair_id=pair.id,
        pair_name="EUR_JPY",
        start=datetime(2026, 1, 1, tzinfo=UTC),
        end=datetime(2026, 1, 1, 3, tzinfo=UTC),
        batch_size=2,
    )
    assert len(bars) == len(rows)
    # yield_per execution option が stmt に乗っていること
    exec_opts = session.executed_stmt.get_execution_options()
    assert exec_opts.get("yield_per") == 2
    # try/finally で close されること
    assert result.closed is True


def test_stream_bars_closes_result_on_exception() -> None:
    """T106 (Round 2 Suggestion): iteration 中の例外でも result.close() される."""
    pair = _make_currency_pair("EUR_JPY")
    rows = _generate_bar_rows(
        pair,
        datetime(2026, 1, 1, tzinfo=UTC),
        datetime(2026, 1, 1, 5, tzinfo=UTC),
        step_minutes=60,
    )
    result = _SpyExecuteResult(rows, raise_after=2)
    session = _SpySession(result)

    with pytest.raises(RuntimeError, match="simulated iteration error"):
        run_ga_module._stream_bars(
            session,  # type: ignore[arg-type]
            pair_id=pair.id,
            pair_name="EUR_JPY",
            start=datetime(2026, 1, 1, tzinfo=UTC),
            end=datetime(2026, 1, 1, 5, tzinfo=UTC),
        )
    assert result.closed is True


def test_stream_bars_uses_attribute_access_only() -> None:
    """T106: row は属性アクセスのみで消費する (row[0] / _mapping を使わない)."""

    class _AttrOnlyRow:
        def __init__(self, bar_time: datetime) -> None:
            self.bar_time = bar_time
            self.open_bid = Decimal("154.000")
            self.high_bid = Decimal("154.000")
            self.low_bid = Decimal("154.000")
            self.close_bid = Decimal("154.000")
            self.open_ask = Decimal("154.005")
            self.high_ask = Decimal("154.005")
            self.low_ask = Decimal("154.005")
            self.close_ask = Decimal("154.005")
            self.volume = 10
            self.complete = True

        def __getitem__(self, idx: Any) -> Any:  # index access は契約違反
            raise AssertionError("row[...] index access is forbidden by contract")

    rows = [_AttrOnlyRow(datetime(2026, 1, 1, tzinfo=UTC))]
    result = _SpyExecuteResult(rows)
    session = _SpySession(result)

    bars = run_ga_module._stream_bars(
        session,  # type: ignore[arg-type]
        pair_id=1,
        pair_name="EUR_JPY",
        start=datetime(2026, 1, 1, tzinfo=UTC),
        end=datetime(2026, 1, 2, tzinfo=UTC),
    )
    assert len(bars) == 1
    assert bars[0].bid.open == Decimal("154.000")
    assert result.closed is True


def test_load_lane_bars_equivalent_to_legacy_via_digest(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """T106: streaming 化後の bars が ORM row 変換 (legacy) と digest 一致する."""
    from src.alpha_factory.bars_digest import bars_digest

    pair, stage_b_rows, holdout_rows = _prepare_smoke_inputs(
        fallback_holdout=False
    )
    _install_mock_session(
        monkeypatch,
        pair,
        stage_b_rows,
        holdout_rows,
        datetime(2026, 1, 8, tzinfo=UTC),
    )
    from src.alpha_factory.config import load_config as _load

    cfg = _load(CONFIG_PATH)
    bundle = run_ga_module._load_lane_bars(
        cfg.dataset.instrument, cfg.dataset, cfg.stage_windows
    )
    # legacy 参照: 同じ rows を _bar_row_to_price_bar で変換した期待値
    legacy_stage_b_full = [
        run_ga_module._bar_row_to_price_bar(r, "EUR_JPY") for r in stage_b_rows
    ]
    legacy_holdout = [
        run_ga_module._bar_row_to_price_bar(r, "EUR_JPY") for r in holdout_rows
    ]
    streamed_full = list(bundle.bars_stage_b) + list(bundle.bars_stage_a)
    assert bars_digest(streamed_full) == bars_digest(legacy_stage_b_full)
    assert bars_digest(bundle.bars_holdout) == bars_digest(legacy_holdout)


def test_phase_rss_marker_emits_main_rss_mb(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """T106: _log_phase_marker が phase + main_rss_mb を logger.info に出す."""
    events: list[tuple[str, dict[str, Any]]] = []
    monkeypatch.setattr(
        run_ga_module.logger,
        "info",
        lambda event, **kw: events.append((event, kw)),
    )
    run_ga_module._log_phase_marker("after_stage_b_full_load", bar_count=42)
    assert len(events) == 1
    event, kw = events[0]
    assert event == "run_ga.phase_rss_marker"
    assert kw["phase"] == "after_stage_b_full_load"
    assert kw["main_rss_mb"] >= 0.0
    assert kw["error_type"] is None
    assert kw["bar_count"] == 42


def test_phase_rss_marker_records_error_type_on_psutil_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """T106 (Round 2 Suggestion): psutil 例外時 main_rss_mb=-1.0 + error_type."""
    import psutil

    def _boom() -> Any:
        raise psutil.Error("simulated psutil failure")

    monkeypatch.setattr(psutil, "Process", _boom)
    events: list[tuple[str, dict[str, Any]]] = []
    monkeypatch.setattr(
        run_ga_module.logger,
        "info",
        lambda event, **kw: events.append((event, kw)),
    )
    run_ga_module._log_phase_marker("before_ga_loop")
    assert len(events) == 1
    _, kw = events[0]
    assert kw["main_rss_mb"] == -1.0
    assert kw["error_type"] == "Error"


def test_smoke_run_holdout_ok(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """holdout bars が DB から取得できる通常シナリオ."""
    pair, stage_b_rows, holdout_rows = _prepare_smoke_inputs(
        fallback_holdout=False
    )
    created = _install_mock_session(
        monkeypatch,
        pair,
        stage_b_rows,
        holdout_rows,
        datetime(2026, 1, 8, tzinfo=UTC),
    )
    # 出力先を tmp に
    monkeypatch.setattr(run_ga_module, "RUN_REPORTS_DIR", tmp_path / "reports")
    monkeypatch.setattr(
        run_ga_module, "RUN_CACHE_DIR", tmp_path / "cache"
    )
    # run_number を固定 (get_latest_run_number を monkeypatch)
    monkeypatch.setattr(
        run_ga_module, "get_latest_run_number", lambda: 0
    )
    # archive 出力 path を tmp に (flush は DEFAULT_OUTPUT_DIR を使う)
    from src.alpha_factory.archive import GenomeArchive as _Archive

    monkeypatch.setattr(
        _Archive, "DEFAULT_OUTPUT_DIR", tmp_path / "archive"
    )

    rc = run_ga_module.main(
        [
            "--config",
            str(CONFIG_PATH),
            "--run-id",
            "run_test_ok",
            "--population-size",
            "5",
            "--generations",
            "1",
            "--seed",
            "42",
        ]
    )
    assert rc == 0
    # T057 Phase 2 Gate B: aux preflight + AuxBundle build で SessionLocal が
    # 追加で 1 回呼ばれる (Codex impl-review-round-1 [Warning] 反映:
    # call count を厳密に固定して回帰検出を維持。1 = bars 取得, 2 = preflight + aux 取得).
    assert len(created) == 2, (
        "SessionLocal は本番 RUN で 2 回呼ばれる "
        "(1 回目: bars 取得, 2 回目: aux preflight + AuxBundle 構築)"
    )
    # stmt ベースでの bars 判別が動いていること (R1 impl-review B3)
    assert created[0].bars_calls == ["stage_b", "holdout"]

    run_dir = tmp_path / "reports" / "run-1"
    assert (run_dir / "summary.json").exists()
    assert (run_dir / "history.json").exists()
    assert (run_dir / "best_genome.json").exists()
    assert (run_dir / "population.jsonl").exists()

    summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    # 既存契約: top-level population_size 維持
    assert "population_size" in summary
    # 既存契約: dataset.instrument/start/end/bars 維持
    assert summary["dataset"]["instrument"] == "EUR_JPY"
    assert summary["dataset"]["bars"] > 0
    # 新規: bars_stage_a/bars_stage_b/bars_holdout
    assert summary["dataset"]["bars_stage_a"] > 0
    assert summary["dataset"]["bars_holdout"] > 0
    # T087: disjoint metadata
    assert summary["dataset"]["bars_stage_b_excludes_stage_a"] is True
    assert summary["dataset"]["bars_dataset_total"] == (
        summary["dataset"]["bars_stage_a"] + summary["dataset"]["bars_stage_b"]
    )
    # `bars` キーは disjoint 化前と同じ意味 (= 全期間) で据え置き
    assert summary["dataset"]["bars"] == summary["dataset"]["bars_dataset_total"]
    # 起動 log が引ける形で時刻情報が記録される
    assert "stage_a_bar_first" in summary["dataset"]
    assert "stage_b_bar_last" in summary["dataset"]
    assert "holdout_bar_first" in summary["dataset"]
    # T087: stage_b inconclusive flag
    assert "stage_b" in summary
    assert "statistical_inconclusive" in summary["stage_b"]
    assert isinstance(summary["stage_b"]["statistical_inconclusive"], bool)
    # best.fitness は Decimal 互換 (有限値)
    Decimal(summary["best"]["fitness"])
    assert isinstance(summary["best"]["fitness_finite"], bool)
    # cycle 5: selection_score_schema v3_3_stage_b_feasible_priority (10 要素)
    # 3 要素目 stage_b_pass_and_feasible_int (cycle 5 新規、 最優先要素 3 に昇格)
    # 9 要素目 fold_robust_int (cycle 4、 fitness_pen より上位)
    assert summary["best"]["selection_score_schema"] == "v3_3_stage_b_feasible_priority"
    assert len(summary["best"]["selection_score"]) == 10
    # 1 要素目 feasible_int, 3 要素目 stage_b_pass_and_feasible_int, 4 要素目 stage_b_pass_int
    assert summary["best"]["selection_score"][0] in (0, 1)
    assert summary["best"]["selection_score"][2] in (0, 1)  # stage_b_pass_and_feasible
    assert summary["best"]["selection_score"][3] in (0, 1)  # stage_b_pass
    # 9 要素目 fold_robust_int (cycle 4)
    assert summary["best"]["selection_score"][8] in (0, 1)
    # best.feasible / violation_magnitude / stage_c_feasible キーが存在
    assert isinstance(summary["best"]["feasible"], bool)
    assert isinstance(summary["best"]["violation_magnitude"], float)
    assert isinstance(summary["best"]["stage_c_feasible"], bool)
    # per_generation に feasible_count
    for pg in summary["per_generation"]:
        assert isinstance(pg["feasible_count"], int)
    # T114: cross_pair.enable default False → skipped_disabled (runtime_mode 細分化)。
    # (旧: skipped_single_instrument。anchor 未供給でなく enable=False が skip 理由)
    assert summary["cross_pair_runtime_mode"] == "skipped_disabled"
    # archive parquet が生成されている
    archive_path = Path(summary["archive_parquet"])
    assert archive_path.exists()

    history = json.loads((run_dir / "history.json").read_text(encoding="utf-8"))
    assert len(history) == 2  # gen=0, gen=1
    for h in history:
        # best_fitness は Decimal 互換
        Decimal(h["best_fitness"])
        assert "stage_a_pass" in h
        assert "graduation_count" in h


def test_load_config_rejects_deprecated_fallback_slice() -> None:
    """T087: stage_windows.allow_stage_c_fallback_slice は廃止 → load_config で fail-closed."""
    from src.alpha_factory.config import load_config as _load

    overrides = {"stage_windows": {"allow_stage_c_fallback_slice": True}}
    with pytest.raises(ValueError, match="allow_stage_c_fallback_slice is deprecated"):
        _load(CONFIG_PATH, overrides=overrides)


def test_fitness_to_str_handles_non_finite() -> None:
    """R1 impl-review B1/B2: 非有限 fitness が "0" に正規化されること."""
    import math

    assert run_ga_module._fitness_to_str(0.0) == "0"
    assert run_ga_module._fitness_to_str(-0.0) == "0"
    assert run_ga_module._fitness_to_str(1.5) == "1.5"
    assert run_ga_module._fitness_to_str(-0.25) == "-0.25"
    # 非有限は必ず "0" (NaN/-inf 経由で Decimal が落ちないこと)
    assert run_ga_module._fitness_to_str(float("nan")) == "0"
    assert run_ga_module._fitness_to_str(-math.inf) == "0"
    assert run_ga_module._fitness_to_str(math.inf) == "0"
    # Decimal() で parse できる (既存 consumer 互換)
    Decimal(run_ga_module._fitness_to_str(-math.inf))
    Decimal(run_ga_module._fitness_to_str(float("nan")))


def test_smoke_run_holdout_missing_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """T087: holdout が DB から取れなければ常に RuntimeError (fallback 廃止)."""
    pair, stage_b_rows, holdout_rows = _prepare_smoke_inputs(
        fallback_holdout=True
    )
    _install_mock_session(
        monkeypatch,
        pair,
        stage_b_rows,
        holdout_rows,
        datetime(2026, 1, 8, tzinfo=UTC),
    )
    monkeypatch.setattr(run_ga_module, "RUN_REPORTS_DIR", tmp_path / "reports")
    monkeypatch.setattr(
        run_ga_module, "RUN_CACHE_DIR", tmp_path / "cache"
    )
    monkeypatch.setattr(
        run_ga_module, "get_latest_run_number", lambda: 0
    )
    from src.alpha_factory.config import load_config as _load

    cfg = _load(CONFIG_PATH)
    with pytest.raises(RuntimeError, match="no holdout bars"):
        run_ga_module._load_lane_bars(
            cfg.dataset.instrument, cfg.dataset, cfg.stage_windows
        )
