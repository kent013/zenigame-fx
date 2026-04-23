"""Cross-pair (ii-lite) shadow evaluation 実装 (T016).

target ペア + アンカー 2 ペアで同一ゲノムを評価し、集約 Sharpe で
通過判定する軽量 cross-pair 検証。Phase 2 では shadow mode (記録のみ)、
Phase 4 で hard gate 化予定。

主な公開 API:
    - :data:`ANCHOR_PAIRS` — target → (anchor1, anchor2) マッピング
    - :class:`CrossPairConfig` — 通過基準と mode (shadow/hard)
    - :func:`evaluate_cross_pair` — pure function: 3 backtest + 集約
    - :class:`StageCRunCrossPairEvaluator` — T014 Protocol 実装 adapter

仕様:
    - docs/alpha_factory/cross-pair.md
    - docs/alpha_factory/concepts/cross-pair-evaluation-shadow.md
    - devnotes/20260423-1957-cross-pair-evaluation-shadow/{conceptual,detailed}-design.md
    - devnotes/20260421-1850-fx-skill-port/debate-synthesis.md (anchor SSOT)

戻り値の型 :class:`CrossPairResult` は T014
``src/alpha_factory/stage_gate.py`` で定義済の dataclass を再利用 (本実装で
新規定義しない)。詳細フィールドは ``CrossPairResult.metrics`` 辞書に
canonical key 集合で格納する (詳細設計 §6 / §2.6 参照)。
"""

from __future__ import annotations

import statistics as _stats
from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from types import MappingProxyType
from typing import Literal

import structlog

from src.alpha_factory.stage_gate import CrossPairResult
from src.backtest.engine import BacktestConfig, run_backtest
from src.backtest.metrics import compute_metrics
from src.broker.mock import InstrumentMeta, MockBroker
from src.domain.price import PriceBar
from src.dsl.genome import Genome
from src.dsl.strategy import DslStrategy, PrimitiveEvaluator

logger = structlog.get_logger(__name__)

__all__ = [
    "ANCHOR_PAIRS",
    "CrossPairConfig",
    "StageCRunCrossPairEvaluator",
    "evaluate_cross_pair",
]


# ---------------------------------------------------------------------------
# Anchor mapping (debate-synthesis.md SSOT)
# ---------------------------------------------------------------------------

# Phase 2 時点では MockBroker quote==JPY 制約のため、非 JPY-quote anchor を
# 含む target は実 backtest 経由で構造的 pair_failure になる。本 TODO は
# コードパス完全実装と monkeypatch ロジック検証に価値を絞り、実 backtest
# による意味のある shadow 統計取得は MockBroker 拡張別 TODO に依存する。
ANCHOR_PAIRS: Mapping[str, tuple[str, str]] = MappingProxyType(
    {
        "EUR_JPY": ("EUR_USD", "USD_JPY"),
        "USD_JPY": ("USD_CAD", "EUR_JPY"),
        "EUR_USD": ("EUR_JPY", "USD_CAD"),
        "AUD_JPY": ("USD_JPY", "EUR_USD"),
        "USD_CAD": ("USD_JPY", "EUR_USD"),
        "USD_ZAR": ("USD_CAD", "USD_JPY"),
    }
)


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CrossPairConfig:
    """Cross-pair (ii-lite) 評価設定。

    Attributes:
        sharpe_target_cross_ratio_min: ``Sharpe_target_cross / Sharpe_target_single``
            の下限。Phase 2 では provider 注入時のみ評価される (default
            None なら ratio skip)。
        mean_sharpe_cross_min: ``mean(Sharpe_i)`` の下限。
        min_sharpe_cross_min: ``min(Sharpe_i)`` の下限。
        aggregator_lambda: 集約 fitness ``F = mean - λ × std`` の λ。
        mode: ``"shadow"`` (Phase 2 default) / ``"hard"`` (Phase 4)。
            shadow では Stage C ``passed`` への影響無し、hard では AND 合成。
    """

    sharpe_target_cross_ratio_min: float = 0.8
    mean_sharpe_cross_min: float = 0.15
    min_sharpe_cross_min: float = -0.20
    aggregator_lambda: float = 0.5
    mode: Literal["shadow", "hard"] = "shadow"

    def __post_init__(self) -> None:
        if self.aggregator_lambda < 0:
            raise ValueError(
                f"aggregator_lambda must be >= 0: {self.aggregator_lambda}"
            )
        if not 0.0 <= self.sharpe_target_cross_ratio_min <= 1.0:
            raise ValueError(
                "sharpe_target_cross_ratio_min must be in [0, 1]: "
                f"{self.sharpe_target_cross_ratio_min}"
            )
        if self.mode not in ("shadow", "hard"):
            raise ValueError(
                f"mode must be 'shadow' or 'hard': {self.mode!r}"
            )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _run_pair_sharpe(
    *,
    genome: Genome,
    pair: str,
    bars: list[PriceBar],
    meta: InstrumentMeta,
    backtest_config: BacktestConfig,
    primitive_evaluator: PrimitiveEvaluator,
) -> tuple[float, str | None]:
    """単一ペアで backtest 実行し、Sharpe を返す。

    Returns:
        ``(sharpe, failure_reason)``. 成功時 ``(sharpe, None)``、失敗時は
        ``(0.0, "<reason>")``。reason 例:

        - ``"metric_unavailable"`` — no trades 等で sharpe is None
        - ``"exception:<ExceptionType>"`` — backtest 内で例外
    """
    pair_config = replace(backtest_config, instrument=pair)
    try:
        strategy = DslStrategy(genome, primitive_evaluator)
        broker = MockBroker(instrument_meta=meta)
        result = run_backtest(bars, strategy, broker, pair_config)
        bt = compute_metrics(result.trades, result.equity_curve)
        if bt.sharpe is None:
            return 0.0, "metric_unavailable"
        return float(bt.sharpe), None
    except Exception as exc:
        logger.warning(
            "cross_pair.pair_failure",
            genome=genome.name,
            pair=pair,
            error=str(exc),
            error_type=type(exc).__name__,
        )
        return 0.0, f"exception:{type(exc).__name__}"


def _make_skipped_result(
    target: str,
    anchors_map: Mapping[str, tuple[str, str]],
    config: CrossPairConfig,
    *,
    reason: str,
) -> CrossPairResult:
    """skipped 状態の CrossPairResult を構築する。"""
    a1, a2 = anchors_map.get(target, ("", ""))
    metrics: dict[str, object] = {
        "sharpe_per_pair": {},
        "mean_sharpe": None,
        "std_sharpe": None,
        "min_sharpe": None,
        "aggregate_fitness": None,
        "aggregator_lambda": config.aggregator_lambda,
        "sharpe_target_single": None,
        "sharpe_target_cross": None,
        "sharpe_target_cross_ratio": None,
        "liquidity_weighted_mean": None,  # 予約 (本 TODO 範囲外)
        "pass_criteria": {
            "sharpe_ratio": None,
            "mean": None,
            "min": None,
            "all": False,
        },
        "skipped": True,
        "skip_reason": reason,
        "mode": config.mode,
    }
    dummy_dt = datetime.fromtimestamp(0, tz=UTC)
    return CrossPairResult(
        target_pair=target,
        anchor_pairs=(a1, a2),
        aggregator_name=f"mean_minus_{config.aggregator_lambda}_std",
        window=(dummy_dt, dummy_dt),
        passed=False,
        metrics=metrics,
        reason_codes=("skipped",),
    )


# ---------------------------------------------------------------------------
# Public evaluator
# ---------------------------------------------------------------------------


def evaluate_cross_pair(
    genome: Genome,
    target: str,
    pair_bars: Mapping[str, list[PriceBar]],
    pair_meta: Mapping[str, InstrumentMeta],
    backtest_config: BacktestConfig,
    primitive_evaluator: PrimitiveEvaluator,
    cross_pair_config: CrossPairConfig,
    *,
    sharpe_target_single: float | None = None,
    anchor_pairs: Mapping[str, tuple[str, str]] | None = None,
) -> CrossPairResult:
    """target + アンカー 2 ペアで backtest し、集約 Sharpe で通過判定する。

    Phase 2 では shadow mode で記録のみ、Stage C ``passed`` への影響なし。

    Args:
        genome: 評価対象 Genome。
        target: target ペア名 (``ANCHOR_PAIRS`` のキー)。
        pair_bars: ``{pair: bars}`` マッピング。target + 2 anchors の bars 必須。
        pair_meta: ``{pair: InstrumentMeta}`` マッピング。
        backtest_config: 共通 BacktestConfig (instrument は内部で各 pair に書換)。
        primitive_evaluator: 全 pair 共通の PrimitiveEvaluator。
        cross_pair_config: 通過基準と mode。
        sharpe_target_single: target 単独 Sharpe (Stage C base evaluation 値)。
            None / <= 0 では ratio 判定 skip (Phase 2 default は None)。
        anchor_pairs: anchor mapping override (None → モジュール ``ANCHOR_PAIRS``)。

    Returns:
        :class:`CrossPairResult` (T014 dataclass)。詳細は ``metrics`` 辞書に
        canonical key 集合 (詳細設計 §6) で格納される。
        ``passed`` は ``pass_criteria.all`` から決まり、pair_failure があれば
        fail-fast で False。
    """
    anchors_map = anchor_pairs if anchor_pairs is not None else ANCHOR_PAIRS

    # --- skipped checks ---
    if target not in anchors_map:
        return _make_skipped_result(
            target, anchors_map, cross_pair_config,
            reason=f"target_not_in_anchors:{target}",
        )

    a1, a2 = anchors_map[target]
    required = (target, a1, a2)
    missing_bars = [
        p for p in required if p not in pair_bars or not pair_bars[p]
    ]
    missing_meta = [p for p in required if p not in pair_meta]
    if missing_bars or missing_meta:
        reason = f"missing_bars={missing_bars};missing_meta={missing_meta}"
        return _make_skipped_result(
            target, anchors_map, cross_pair_config, reason=reason,
        )

    # --- run 3 backtests ---
    sharpe_per_pair: dict[str, float] = {}
    pair_failures: list[str] = []
    for pair in required:
        sh, fail = _run_pair_sharpe(
            genome=genome,
            pair=pair,
            bars=list(pair_bars[pair]),
            meta=pair_meta[pair],
            backtest_config=backtest_config,
            primitive_evaluator=primitive_evaluator,
        )
        sharpe_per_pair[pair] = sh
        if fail is not None:
            pair_failures.append(f"pair_failure:{pair}:{fail}")

    # --- aggregation (pstdev = ddof=0 母標準偏差) ---
    sharpes = list(sharpe_per_pair.values())
    mean_sharpe = float(_stats.fmean(sharpes))
    std_sharpe = float(_stats.pstdev(sharpes))
    min_sharpe = float(min(sharpes))
    aggregate_fitness = (
        mean_sharpe - cross_pair_config.aggregator_lambda * std_sharpe
    )

    # --- ratio (opt-in via sharpe_target_single) ---
    sharpe_target_cross = sharpe_per_pair[target]
    sharpe_ratio: float | None
    if sharpe_target_single is None or sharpe_target_single <= 0:
        sharpe_ratio = None
    else:
        sharpe_ratio = sharpe_target_cross / sharpe_target_single

    # --- pass criteria (None 除外 AND, fail-fast on pair_failure) ---
    pc: dict[str, bool | None] = {
        "sharpe_ratio": (
            None
            if sharpe_ratio is None
            else sharpe_ratio >= cross_pair_config.sharpe_target_cross_ratio_min
        ),
        "mean": mean_sharpe >= cross_pair_config.mean_sharpe_cross_min,
        "min": min_sharpe >= cross_pair_config.min_sharpe_cross_min,
    }
    booleans = [v for v in pc.values() if v is not None]
    base_all = bool(booleans) and all(booleans)
    # fail-fast: pair_failure があれば集約値が信頼できないため passed=False
    pc["all"] = base_all and not pair_failures

    # --- window (target bars の最初と最後) ---
    bars_target = pair_bars[target]
    window = (bars_target[0].bar_time, bars_target[-1].bar_time)

    # --- reason_codes ---
    reasons: list[str] = []
    if pc["sharpe_ratio"] is False:
        reasons.append("sharpe_ratio<min")
    if pc["mean"] is False:
        reasons.append("mean_sharpe<min")
    if pc["min"] is False:
        reasons.append("min_sharpe<min")
    reasons.extend(pair_failures)

    metrics: dict[str, object] = {
        "sharpe_per_pair": sharpe_per_pair,
        "mean_sharpe": mean_sharpe,
        "std_sharpe": std_sharpe,
        "min_sharpe": min_sharpe,
        "aggregate_fitness": aggregate_fitness,
        "aggregator_lambda": cross_pair_config.aggregator_lambda,
        "sharpe_target_single": sharpe_target_single,
        "sharpe_target_cross": sharpe_target_cross,
        "sharpe_target_cross_ratio": sharpe_ratio,
        "liquidity_weighted_mean": None,  # 予約 (本 TODO 範囲外)
        "pass_criteria": pc,
        "skipped": False,
        "skip_reason": "",
        "mode": cross_pair_config.mode,
    }

    return CrossPairResult(
        target_pair=target,
        anchor_pairs=(a1, a2),
        aggregator_name=f"mean_minus_{cross_pair_config.aggregator_lambda}_std",
        window=window,
        passed=bool(pc["all"]),
        metrics=metrics,
        reason_codes=tuple(reasons),
    )


# ---------------------------------------------------------------------------
# Stage C adapter (CrossPairEvaluator Protocol 実装)
# ---------------------------------------------------------------------------


class StageCRunCrossPairEvaluator:
    """T014 ``CrossPairEvaluator`` Protocol を満たす実装オブジェクト。

    Stage C ``evaluate_stage_c(cross_pair_evaluator=...)`` に注入する thin
    adapter。``evaluate(...)`` 内で :func:`evaluate_cross_pair` を呼ぶ。

    ``sharpe_target_single_provider`` は opt-in (Phase 2 default は None)。
    swim-lane / run-ga 統合 TODO で provider が結束されると ratio 判定が
    有効化される (= 3 条件 AND に拡張)。
    """

    def __init__(
        self,
        primitive_evaluator: PrimitiveEvaluator,
        cross_pair_config: CrossPairConfig,
        *,
        anchor_pairs: Mapping[str, tuple[str, str]] | None = None,
        sharpe_target_single_provider: Callable[[], float | None] | None = None,
    ) -> None:
        self._primitive_evaluator = primitive_evaluator
        self._config = cross_pair_config
        self._anchor_pairs = anchor_pairs
        self._sharpe_provider = sharpe_target_single_provider

    def evaluate(
        self,
        genome: Genome,
        target_pair: str,
        pair_bars_map: Mapping[str, list[PriceBar]],
        meta_map: Mapping[str, InstrumentMeta],
        backtest_config: BacktestConfig,
    ) -> CrossPairResult:
        sharpe_single: float | None = None
        if self._sharpe_provider is not None:
            try:
                sharpe_single = self._sharpe_provider()
            except Exception as exc:
                logger.warning(
                    "cross_pair.provider_failure",
                    genome=genome.name,
                    error=str(exc),
                    error_type=type(exc).__name__,
                )
                sharpe_single = None
        return evaluate_cross_pair(
            genome=genome,
            target=target_pair,
            pair_bars=pair_bars_map,
            pair_meta=meta_map,
            backtest_config=backtest_config,
            primitive_evaluator=self._primitive_evaluator,
            cross_pair_config=self._config,
            sharpe_target_single=sharpe_single,
            anchor_pairs=self._anchor_pairs,
        )
