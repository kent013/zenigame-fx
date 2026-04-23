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

    def scalars(self, stmt: Any) -> _ScalarsResult:
        stmt_str = str(stmt).lower()
        if "currency_pair" in stmt_str and "price_bar_m1" not in stmt_str:
            return _ScalarsResult("pair", [], self._pair)
        if "price_bar_m1" in stmt_str:
            # whereclause から bar_time の境界を compile して取得
            try:
                compiled = stmt.compile(
                    compile_kwargs={"literal_binds": True}
                )
                compiled_str = str(compiled).lower()
            except Exception:  # pragma: no cover - fallback
                compiled_str = stmt_str
            end_iso = self._dataset_end.isoformat(sep=" ").lower()
            # Stage B クエリは bar_time < dataset.end を含む
            # holdout クエリは bar_time >= dataset.end を含む
            # literal_binds で "bar_time >= '2026-01-08 00:00:00+00:00'" 形式
            if f">= '{end_iso}'" in compiled_str or (
                f">='{end_iso}'" in compiled_str
            ):
                kind = "holdout"
                rows = self._holdout_rows
            else:
                kind = "stage_b"
                rows = self._stage_b_rows
            self.bars_calls.append(kind)
            return _ScalarsResult("bars", list(rows), None)
        return _ScalarsResult("unknown", [], None)


def _install_mock_session(
    monkeypatch: pytest.MonkeyPatch,
    pair: Any,
    stage_b_rows: list[Any],
    holdout_rows: list[Any],
    dataset_end: datetime,
) -> list[_MockSession]:
    """run_ga.SessionLocal を差し替えて MockSession を返す."""
    created: list[_MockSession] = []

    def _factory() -> _MockSession:
        sess = _MockSession(pair, stage_b_rows, holdout_rows, dataset_end)
        created.append(sess)
        return sess

    monkeypatch.setattr(run_ga_module, "SessionLocal", _factory)
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
    assert cfg.stage_windows.allow_stage_c_fallback_slice is True


def test_load_config_default_yaml_loads() -> None:
    """production default.yaml が loader を通ること."""
    cfg = load_config(DEFAULT_CONFIG_PATH)
    assert cfg.dataset.instrument == "EUR_JPY"
    assert cfg.ga.population_size == 40
    # live_criteria は yaml top-level から injected
    assert float(cfg.live_criteria["sharpe_min"]) == 1.0


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
    assert len(created) == 1, "SessionLocal が呼ばれていること"
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
    # best.fitness は Decimal 互換 (有限値)
    Decimal(summary["best"]["fitness"])
    assert isinstance(summary["best"]["fitness_finite"], bool)
    # selection_score の 4 要素
    assert len(summary["best"]["selection_score"]) == 4
    # cross_pair_runtime_mode は単一 instrument なので skipped
    assert summary["cross_pair_runtime_mode"] == "skipped_single_instrument"
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


def test_smoke_run_holdout_fallback_slice(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """holdout bars が DB で空 + allow_stage_c_fallback_slice=True.

    fixture yaml は既に fallback=True なのでそのまま使う。
    """
    pair, stage_b_rows, holdout_rows = _prepare_smoke_inputs(
        fallback_holdout=True
    )
    assert holdout_rows == []
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
    from src.alpha_factory.archive import GenomeArchive as _Archive

    monkeypatch.setattr(
        _Archive, "DEFAULT_OUTPUT_DIR", tmp_path / "archive"
    )

    rc = run_ga_module.main(
        [
            "--config",
            str(CONFIG_PATH),
            "--run-id",
            "run_test_fallback",
            "--population-size",
            "3",
            "--generations",
            "0",
            "--seed",
            "1",
        ]
    )
    assert rc == 0
    run_dir = tmp_path / "reports" / "run-1"
    summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    # fallback でも bars_holdout > 0
    assert summary["dataset"]["bars_holdout"] > 0


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


def test_smoke_run_holdout_missing_without_fallback_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """fallback flag なしで holdout が取れない → RuntimeError."""
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
    # fixture fallback=True を override=False で無効化
    overrides = {"stage_windows": {"allow_stage_c_fallback_slice": False}}
    # load_config を経由するように argparse は通さず直接叩く
    from src.alpha_factory.config import load_config as _load

    cfg = _load(CONFIG_PATH, overrides=overrides)
    with pytest.raises(RuntimeError, match="no holdout bars"):
        run_ga_module._load_lane_bars(
            cfg.dataset.instrument, cfg.dataset, cfg.stage_windows
        )
