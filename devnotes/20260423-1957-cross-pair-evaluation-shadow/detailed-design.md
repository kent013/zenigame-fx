# 詳細設計: cross-pair (ii-lite) evaluation shadow 実装 (T016)

概念設計: `conceptual-design.md`

## 1. 実装ファイル一覧

| ファイル | 種類 | 行数目安 |
|----------|------|----------|
| `src/alpha_factory/cross_pair.py` | 新規 | ~280 |
| `src/alpha_factory/stage_gate.py` | 修正 (cross-pair hook 周辺のみ) | +20 / -10 |
| `tests/alpha_factory/test_cross_pair.py` | 新規 | ~450 |
| `tests/alpha_factory/test_stage_gate.py` | 追記 (新規 cross-pair hook 動作の test) | +120 |
| `config/alpha_factory/default.yaml` | 追記 (cross_pair セクション) | +20 |
| `docs/alpha_factory/cross-pair.md` | 詳細化 (実装に合わせて refresh) | 既存修正 |
| `docs/alpha_factory/concepts/cross-pair-evaluation-shadow.md` | 「Stage C 通過後」を Phase 4 以降に修正 | 数行修正 |
| `docs/alpha_factory/terminology.md` | 用語追加 (CrossPairConfig / StageCRunCrossPairEvaluator) | +2 セクション |

## 2. `src/alpha_factory/cross_pair.py`

### 2.1 import 構造

```python
from __future__ import annotations

import statistics as _stats
from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from datetime import datetime, timezone
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
```

注意: `math` / `Protocol` は未使用のため import しない。`Callable` は `collections.abc` 由来 (Python 3.9+ 推奨)。`timezone.utc` を `_make_skipped_result` の dummy datetime に使用 (naive datetime 回避)。

### 2.2 公開 API

```python
__all__ = [
    "ANCHOR_PAIRS",
    "CrossPairConfig",
    "StageCRunCrossPairEvaluator",
    "evaluate_cross_pair",
]
```

注意: `CrossPairResult` は **再エクスポートしない** (T014 `stage_gate.py` の SSOT を維持)。

### 2.3 `ANCHOR_PAIRS` 定数

```python
# debate-synthesis.md 由来の SSOT 定義 (6 ペア × アンカー 2 本)
# Phase 2 時点では MockBroker quote==JPY 制約があるため、非 JPY-quote
# anchor を持つ target (EUR_USD/USD_CAD/USD_ZAR) は実 backtest 経路で
# pair_failure になる可能性が高い。これは _run_pair_sharpe で
# "exception:NotImplementedError" を出して reason_codes に積み、
# pair_failures != [] により passed=False で fail-fast する設計
# (= shadow mode で archive ii_lite_pass=False が記録される)。
# Phase 4 hard 化前に MockBroker を非 JPY-quote 対応する別 TODO を切る。
ANCHOR_PAIRS: Mapping[str, tuple[str, str]] = MappingProxyType({
    "EUR_JPY": ("EUR_USD", "USD_JPY"),
    "USD_JPY": ("USD_CAD", "EUR_JPY"),
    "EUR_USD": ("EUR_JPY", "USD_CAD"),
    "AUD_JPY": ("USD_JPY", "EUR_USD"),
    "USD_CAD": ("USD_JPY", "EUR_USD"),
    "USD_ZAR": ("USD_CAD", "USD_JPY"),
})
```

**運用方針 (Phase 2 = 構造的 pair_failure が常態)**:

事実認識: 上記 6 target すべてが少なくとも 1 つの非 JPY-quote anchor (EUR_USD / USD_CAD のいずれか) を持つ。MockBroker は `quote != JPY` で `NotImplementedError` を投げる (`src/broker/mock.py:40`)。したがって **Phase 2 時点では全 target で実 backtest 経由の構造的 pair_failure が発生**する (= shadow archive の `ii_lite_pass` は常に `False`)。

これは **意図された Phase 2 状態** である。本 TODO は以下の 3 つを担保することに価値を絞る:

1. **コードパス完全実装**: `evaluate_cross_pair` / Stage C hook / archive `ii_lite_pass` 連動の 3 段が動く状態を整える (Phase 4 で MockBroker 拡張すれば即時 hard 化可能)
2. **構造的失敗と閾値不達の区別**: archive consumer が「全 target で構造的 fail なのか / 閾値不達なのか」を判別できるよう、`reason_codes` に `pair_failure:<pair>:<error>` を残す。これは `CrossPairResult.reason_codes` を archive に書くカラムを追加する別 TODO で実用化される
3. **テストでロジック検証**: 実 backtest を直接走らせる test ではなく monkeypatch ベースで、集約・通過判定・skipped・fail-fast を担保

archive `ii_lite_pass` カラムだけでは「pair_failure か閾値不達か」を判別できないため、本 TODO では:
- **archive 列追加は別 TODO** (`cross_pair_error_type` / `pair_failure_count` 等の追加。GENOMES_SCHEMA 変更を伴うため独立 TODO 推奨)
- 本 TODO では Stage C `cross_pair_payload` に `error_type` を残し、`CrossPairResult.reason_codes` に詳細を残す。実行時ログ (`structlog`) からも追跡可能

**Phase 2 で意味のある shadow 統計**:
- `evaluate_cross_pair` の **monkeypatch test** で集約・通過判定が仕様通りであることを検証 → ロジック妥当性は担保
- swim-lane / run-ga 統合 TODO で **MockBroker 拡張 (非 JPY-quote 対応)** がある場合、本 TODO の実装をそのまま使って実データの shadow 統計を集める段階に進める
- それまでは「実 backtest 経由の archive `ii_lite_pass` は False (構造的)」を前提に、後段分析でこの行は除外する

**MockBroker 拡張 TODO** (本 TODO 範囲外、別 TODO):
- `_run_pair_sharpe` の冒頭で `MockBroker(meta)` 呼び出し時に `quote != JPY` を検出したら multi-currency conversion broker に切替、または home_currency を pair の quote に合わせる
- 実装範囲が大きい (notional / margin 計算が home currency 依存) ため独立 TODO

### 2.4 `CrossPairConfig`

```python
@dataclass(frozen=True)
class CrossPairConfig:
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
                f"sharpe_target_cross_ratio_min must be in [0,1]: "
                f"{self.sharpe_target_cross_ratio_min}"
            )
        if self.mode not in ("shadow", "hard"):
            raise ValueError(f"mode must be 'shadow' or 'hard': {self.mode}")
```

### 2.5 `_run_pair_sharpe` 内部 helper

```python
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
        (sharpe, failure_reason). failure_reason is None on success.
        - 例外: (0.0, "exception:<type>")
        - sharpe is None (no trades): (0.0, "metric_unavailable")
        - 成功: (sharpe, None)
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
```

### 2.6 `evaluate_cross_pair`

```python
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
    """target + アンカー 2 ペアで backtest し、集約 Sharpe で通過判定。

    Args:
        genome: 評価対象 Genome
        target: target ペア名
        pair_bars: {pair_name: bars} マッピング (target + 2 anchors の bars 必須)
        pair_meta: {pair_name: InstrumentMeta} マッピング
        backtest_config: 共通 BacktestConfig (instrument は内部で各 pair に書換)
        primitive_evaluator: PrimitiveEvaluator (全 pair 共通)
        cross_pair_config: 通過基準と mode
        sharpe_target_single: target 単独 Sharpe (Stage C base evaluation 値)
            - None: ratio 判定 skip (Phase 2 default)
            - <= 0: 同上 (符号反転で意味なし)
            - > 0: ratio 計算
        anchor_pairs: anchor mapping (None → モジュール ANCHOR_PAIRS)

    Returns:
        CrossPairResult (T014 dataclass、metrics に詳細格納)
    """
    anchors_map = anchor_pairs if anchor_pairs is not None else ANCHOR_PAIRS

    # --- skipped check ---
    if target not in anchors_map:
        return _make_skipped_result(
            target, anchors_map, cross_pair_config, backtest_config,
            reason=f"target_not_in_anchors:{target}",
        )

    a1, a2 = anchors_map[target]
    required = (target, a1, a2)
    missing_bars = [p for p in required if p not in pair_bars or not pair_bars[p]]
    missing_meta = [p for p in required if p not in pair_meta]
    if missing_bars or missing_meta:
        reason = f"missing_bars={missing_bars};missing_meta={missing_meta}"
        return _make_skipped_result(
            target, anchors_map, cross_pair_config, backtest_config, reason=reason,
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

    # --- aggregation ---
    sharpes = list(sharpe_per_pair.values())
    mean_sharpe = float(_stats.fmean(sharpes))
    std_sharpe = float(_stats.pstdev(sharpes))  # ddof=0 (母標準偏差)
    min_sharpe = float(min(sharpes))
    aggregate_fitness = mean_sharpe - cross_pair_config.aggregator_lambda * std_sharpe

    # --- ratio (opt-in) ---
    sharpe_target_cross = sharpe_per_pair[target]
    sharpe_ratio: float | None
    if sharpe_target_single is None or sharpe_target_single <= 0:
        sharpe_ratio = None
    else:
        sharpe_ratio = sharpe_target_cross / sharpe_target_single

    # --- pass criteria ---
    pc: dict[str, bool | None] = {
        "sharpe_ratio": (
            None if sharpe_ratio is None
            else sharpe_ratio >= cross_pair_config.sharpe_target_cross_ratio_min
        ),
        "mean": mean_sharpe >= cross_pair_config.mean_sharpe_cross_min,
        "min": min_sharpe >= cross_pair_config.min_sharpe_cross_min,
    }
    # AND 計算: None を除外、全 None なら False (保守的)
    booleans = [v for v in pc.values() if v is not None]
    base_all = bool(booleans) and all(booleans)
    # **fail-fast on pair failure**: backtest 例外 / metric_unavailable があれば
    # 集約値が信頼できないため passed=False で fail-fast (concept §5 失敗モード)
    pc["all"] = base_all and not pair_failures

    # --- window ---
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


def _make_skipped_result(
    target: str,
    anchors_map: Mapping[str, tuple[str, str]],
    config: CrossPairConfig,
    backtest_config: BacktestConfig,
    *,
    reason: str,
) -> CrossPairResult:
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
        "liquidity_weighted_mean": None,
        "pass_criteria": {
            "sharpe_ratio": None, "mean": None, "min": None, "all": False,
        },
        "skipped": True,
        "skip_reason": reason,
        "mode": config.mode,
    }
    # window は dummy (epoch UTC). archive にも書かれない (skipped → ii_lite_pass=None)
    dummy_dt = datetime.fromtimestamp(0, tz=timezone.utc)
    return CrossPairResult(
        target_pair=target,
        anchor_pairs=(a1, a2),
        aggregator_name=f"mean_minus_{config.aggregator_lambda}_std",
        window=(dummy_dt, dummy_dt),
        passed=False,
        metrics=metrics,
        reason_codes=("skipped",),
    )
```

### 2.7 `StageCRunCrossPairEvaluator`

```python
class StageCRunCrossPairEvaluator:
    """T014 CrossPairEvaluator Protocol を満たす実装オブジェクト。

    Stage C `evaluate_stage_c(cross_pair_evaluator=...)` に注入する。
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
```

## 3. `src/alpha_factory/stage_gate.py` 修正 (cross-pair hook)

`evaluate_stage_c` 内 cross-pair hook 部分のみ書き換え。signature・他 stage は不変。

### 3.1 修正前

```python
cross_pair_payload: dict[str, object] = {"skipped": True, "result": None}
if cross_pair_evaluator is not None:
    if cross_pair_inputs is None:
        raise ValueError(...)
    validated = _validate_cross_pair_inputs(cross_pair_inputs)
    cp_result = cross_pair_evaluator.evaluate(...)
    cross_pair_payload["skipped"] = False
    cross_pair_payload["result"] = cp_result
    # Phase 2: shadow only — passed には影響させない
```

### 3.2 修正後

```python
cross_pair_payload: dict[str, object] = {
    "skipped": True,
    "result": None,
    "error_type": None,   # 例外時の audit info
}
if cross_pair_evaluator is not None:
    if cross_pair_inputs is None:
        raise ValueError(
            "cross_pair_inputs required when cross_pair_evaluator is set"
        )
    validated = _validate_cross_pair_inputs(cross_pair_inputs)
    cp_result: CrossPairResult | None
    try:
        cp_result = cross_pair_evaluator.evaluate(
            genome=genome,
            target_pair=validated["target_pair"],
            pair_bars_map=validated["pair_bars_map"],
            meta_map=validated["meta_map"],
            backtest_config=backtest_config,
        )
    except Exception as exc:
        logger.warning(
            "stage_c.cross_pair_failure",
            genome=genome.name,
            error=str(exc),
            error_type=type(exc).__name__,
        )
        cp_result = None
        cross_pair_payload["error_type"] = type(exc).__name__
    if cp_result is None:
        # 例外 fallback: skipped 扱いで記録 (audit 用に error_type は残す)
        cross_pair_payload["skipped"] = True
        cross_pair_payload["result"] = None
    else:
        # CrossPairResult.metrics["skipped"] を Stage C payload に伝搬
        cp_metrics = cp_result.metrics
        cp_skipped = (
            bool(cp_metrics.get("skipped", False))
            if isinstance(cp_metrics, Mapping)
            else False
        )
        cross_pair_payload["skipped"] = cp_skipped
        # archive consumer は skipped=True なら ii_lite_pass=None 扱いだが、
        # metrics 詳細を保持するため cp_result は常に格納する
        cross_pair_payload["result"] = cp_result
    # Phase 2: shadow only — passed には影響させない (mode='hard' は別 TODO)
```

archive 側 `_extract_cross_pair` は既に `skipped=True or result is None` で `ii_lite_pass=None` を返す実装のため、上記修正で skipped が正しく伝搬する。

`error_type` フィールドは新規だが、archive `_extract_cross_pair` は `cp.get("skipped")` と `cp.get("result")` の 2 キーのみ参照する実装 (`src/alpha_factory/archive.py:247-259`) のため、後方互換が保たれる (新キー追加で既存 archive consumer は壊れない)。後段で error_type を archive 列に足したい場合は別 TODO。

## 4. `tests/alpha_factory/test_cross_pair.py`

### 4.1 fixtures (test_stage_gate.py から流用)

```python
from tests._helpers import usd_jpy_meta
# 他 anchor 用に eur_jpy_meta, eur_usd_meta, usd_cad_meta を helpers に追加
```

`tests/_helpers.py` に anchor 用 InstrumentMeta factory を追加 (既存 `usd_jpy_meta` を generic 化):

```python
def make_pair_meta(pair: str, *, base: str | None = None, quote: str = "JPY") -> InstrumentMeta:
    base_ = base or pair.split("_")[0]
    return InstrumentMeta(
        oanda_name=pair,
        base_currency=base_,
        quote_currency=quote,
        margin_rate=Decimal("0.04"),
    )
```

ただし MockBroker は `quote == home (JPY)` を要求するため、tests では JPY-quote pairs (USD_JPY, EUR_JPY 等) のみを cross-pair 評価する。EUR_USD などの USD-quote pair は MockBroker で動かないため、**現状は MockBroker 制約の都合で EUR_JPY, USD_JPY, AUD_JPY を中心に test を書く**。EUR_USD / USD_CAD などは synthetic backtest stub (PrimitiveEvaluator stub 経由で Sharpe 固定値を返す) で代替する。

### 4.2 戦略: backtest を stub する

実 backtest を 3 回走らせる test は時間コストが高い。`evaluate_cross_pair` の集約・判定ロジックは pure な数値計算なので、`_run_pair_sharpe` を monkeypatch して固定 Sharpe を返すパターンを基本にする:

```python
def test_aggregate_fitness_correct(monkeypatch):
    sharpes_table = {"EUR_JPY": 0.8, "EUR_USD": 0.6, "USD_JPY": 0.4}

    def fake_run(*, genome, pair, bars, meta, backtest_config, primitive_evaluator):
        return sharpes_table[pair], None

    monkeypatch.setattr("src.alpha_factory.cross_pair._run_pair_sharpe", fake_run)
    result = evaluate_cross_pair(
        genome=_dummy_genome(),
        target="EUR_JPY",
        pair_bars={p: [_dummy_bar(p)] for p in sharpes_table},
        pair_meta={p: _dummy_meta(p) for p in sharpes_table},
        backtest_config=_dummy_backtest_config(),
        primitive_evaluator=ConstantPrimitiveEvaluator(0.0),
        cross_pair_config=CrossPairConfig(),
    )
    assert math.isclose(result.metrics["mean_sharpe"], 0.6, abs_tol=1e-9)
    assert math.isclose(result.metrics["std_sharpe"], 0.16329932, abs_tol=1e-6)
    assert math.isclose(result.metrics["aggregate_fitness"], 0.6 - 0.5*0.16329932, abs_tol=1e-6)
```

実 backtest 経由は **1 ケースだけ** (E2E sanity) 用意する。

### 4.3 テスト一覧 (categories 別、計 ~30 関数)

| カテゴリ | 件数 | 主目的 |
|----------|-----:|--------|
| anchor & config 整合性 | 7 | ANCHOR_PAIRS shape, CrossPairConfig invariants |
| 集約計算 | 2 | mean/pstdev/aggregate_fitness の数値正確性 |
| 通過基準境界 | 3 | mean/min/ratio 各境界の ±epsilon |
| pass_criteria.all | 3 | Phase 2 (2条件) / provider あり (3条件) / 1条件 fail |
| ratio skip pattern | 3 | single sharpe = None / 0 / 負 |
| skipped | 4 | target 未登録 / bars欠落 / meta欠落 / metrics shape |
| pair_failure | 3 | 0.0 imputation / reason_codes / **fail-fast on passed** |
| Stage C 統合 | 5 | Protocol duck-typing / skipped伝搬 / 例外隔離 / 通常 / passed 無影響 |
| archive 連動 | 2 | skipped→None / 通常→bool |
| E2E sanity (実 backtest) | 1 | JPY-quote 3 pairs |

完全な関数名一覧:

```
# anchor & config 整合性 (7)
test_anchor_pairs_has_six_targets()
test_anchor_pairs_each_has_two()
test_anchor_pairs_no_self_reference()
test_cross_pair_config_default_values()
test_cross_pair_config_invalid_lambda_raises()
test_cross_pair_config_invalid_ratio_raises()
test_cross_pair_config_invalid_mode_raises()

# 集約計算 (2)
test_aggregate_fitness_correct(monkeypatch)
test_pstdev_used_not_stdev(monkeypatch)

# 通過基準境界 (3)
test_pass_criteria_mean_boundary(monkeypatch)
test_pass_criteria_min_boundary(monkeypatch)
test_pass_criteria_ratio_boundary_with_provider(monkeypatch)

# pass_criteria.all (3)
test_pass_criteria_all_two_conditions_phase2(monkeypatch)
test_pass_criteria_all_three_conditions_with_provider(monkeypatch)
test_pass_criteria_all_one_failure(monkeypatch)

# ratio skip pattern (3)
test_sharpe_target_single_none_means_ratio_skip(monkeypatch)
test_sharpe_target_single_zero_means_ratio_skip(monkeypatch)
test_sharpe_target_single_negative_means_ratio_skip(monkeypatch)

# skipped (4)
test_skipped_target_not_in_anchors()
test_skipped_anchor_bars_missing()
test_skipped_anchor_meta_missing()
test_skipped_metrics_shape()

# pair_failure (3)
test_pair_backtest_failure_imputed_zero(monkeypatch)
test_pair_backtest_failure_in_reason_codes(monkeypatch)
test_pair_failure_forces_passed_false_even_if_thresholds_met(monkeypatch)  # ★ fail-fast 検証

# Stage C 統合 (5) - test_stage_gate.py に追加
test_stage_c_run_evaluator_protocol_duck_typing()
test_stage_c_skipped_propagates_to_payload()
test_stage_c_exception_isolated_records_error_type()  # ★ payload.error_type 検証も含む
test_stage_c_normal_completion_payload_shape()
test_stage_c_passed_unaffected_by_cross_pair()

# archive 連動 (2) - test_archive.py に追加 or test_cross_pair.py 内
test_archive_ii_lite_pass_skipped_yields_none()
test_archive_ii_lite_pass_normal_completion_yields_bool()

# E2E sanity (1)
test_e2e_real_backtest_three_jpy_quote_pairs()
```

### 4.4 主要 helper

```python
def _dummy_genome(name="g_test") -> Genome:
    sig = SignalConfig(name="ConstSignal", weight=1.0, params={})
    clause = ClauseConfig(directional=(sig,), local_gate=(), weight=1.0)
    pos = PositionConfig(entry_threshold=0.5, exit_threshold=0.1, max_pos=1, time_stop_min=0)
    risk = RiskConfig(stop_atr=2.0, take_atr=2.0)
    return Genome(name=name, units=10000, clauses=(clause,), position=pos, risk=risk)
```

monkeypatch ベースの test では genome の中身は relevant でない (`_run_pair_sharpe` を stub するため)。

## 5. `tests/alpha_factory/test_stage_gate.py` 追記

`evaluate_stage_c` の cross-pair hook 修正に対する独立 test:

```python
def test_stage_c_cross_pair_skipped_propagates_to_payload():
    """adapter が skipped Result を返したら payload.skipped=True"""

def test_stage_c_cross_pair_exception_isolated():
    """adapter が例外を投げたら stage_c.passed は影響受けず payload.skipped=True"""

def test_stage_c_cross_pair_normal_completion():
    """adapter が non-skipped Result を返したら payload.skipped=False, result=cp_result"""
```

stub `CrossPairEvaluator` を test 内で定義:

```python
class _StubCrossPairEvaluator:
    def __init__(self, behavior: str) -> None:
        self._behavior = behavior  # "skipped" / "exception" / "normal"
    def evaluate(self, **kwargs) -> CrossPairResult:
        if self._behavior == "exception":
            raise RuntimeError("stub failure")
        if self._behavior == "skipped":
            return CrossPairResult(
                target_pair=kwargs["target_pair"],
                anchor_pairs=("X", "Y"),
                aggregator_name="stub",
                window=(datetime.now(), datetime.now()),
                passed=False,
                metrics={"skipped": True, "skip_reason": "stub", ...},
                reason_codes=("skipped",),
            )
        # normal
        return CrossPairResult(
            ..., passed=True,
            metrics={"skipped": False, "pass_criteria": {"all": True}, ...},
            reason_codes=(),
        )
```

## 6. `config/alpha_factory/default.yaml` 追記

```yaml
# Cross-pair (ii-lite) evaluation 設定 (T016)
# - 実装: src/alpha_factory/cross_pair.py
# - 概念: docs/alpha_factory/cross-pair.md
# - mode='shadow' (Phase 2 default): Stage C passed には影響させず archive 記録のみ
# - mode='hard'   (Phase 4 で切替): 通過基準を Stage C の AND に組み込む (別 TODO)
cross_pair:
  mode: shadow
  aggregator_lambda: 0.5            # F = mean - λ × std
  pass_criteria:
    sharpe_target_cross_ratio_min: 0.8   # Phase 4 で有効化、Phase 2 は monitor only
    mean_sharpe_cross_min: 0.15
    min_sharpe_cross_min: -0.20
  anchors:
    EUR_JPY: [EUR_USD, USD_JPY]
    USD_JPY: [USD_CAD, EUR_JPY]
    EUR_USD: [EUR_JPY, USD_CAD]
    AUD_JPY: [USD_JPY, EUR_USD]
    USD_CAD: [USD_JPY, EUR_USD]
    USD_ZAR: [USD_CAD, USD_JPY]
```

YAML loader は別 TODO (run-ga 統合) で実装する。

## 7. ドキュメント修正

### 7.1 `docs/alpha_factory/cross-pair.md`

- 「実装詳細は `concepts/cross-pair-evaluation-shadow.md` および後続 TODO で扱う」→ 「実装は `src/alpha_factory/cross_pair.py` (T016 で実装済)」に更新
- SSOT 参照表で `ii_lite.*` → `cross_pair.*` に統一
- 「関連 TODO: 未着手 (Phase 2H)」→ 「T016 実装済」に更新
- Phase 2 = 2 条件 AND、Phase 4 = 3 条件 AND の段階導入を明記

### 7.2 `docs/alpha_factory/concepts/cross-pair-evaluation-shadow.md`

- 「Stage C 通過後に必ず実行」→ 「Phase 2 では Stage C 実行個体すべてを観測対象 / Phase 4 hard 化後は Stage C の AND 合成として動作」に修正
- config キー名を `ii_lite:` → `cross_pair:` に統一

### 7.3 `docs/alpha_factory/terminology.md`

追加用語:

```markdown
### CrossPairConfig

`<a id="cross-pair-config"></a>` CrossPairConfig — `src/alpha_factory/cross_pair.py` の frozen dataclass (T016)。`sharpe_target_cross_ratio_min` / `mean_sharpe_cross_min` / `min_sharpe_cross_min` / `aggregator_lambda` / `mode` の 5 フィールド。`__post_init__` で lambda >= 0、ratio_min ∈ [0,1]、mode ∈ {shadow, hard} を検証。

### StageCRunCrossPairEvaluator

`<a id="stage-c-run-cross-pair-evaluator"></a>` StageCRunCrossPairEvaluator — `src/alpha_factory/cross_pair.py` のクラス (T016)。T014 `CrossPairEvaluator` Protocol の実装。constructor で `(primitive_evaluator, cross_pair_config, anchor_pairs=None, sharpe_target_single_provider=None)` を受け取り、`evaluate(...)` 内で `evaluate_cross_pair(...)` を呼ぶ thin wrapper。`sharpe_target_single_provider` は opt-in (Phase 2 default では None)。
```

`(ii-lite)` 既存定義の末尾を「実装は cross_pair.py (T016)」に更新。

## 8. mypy / ruff 配慮

- `Mapping[str, list[PriceBar]]` 等の型 hint は `from collections.abc import Mapping` を使う (Python 3.9+ generic syntax)
- `dict[str, float | int]` 等は Python 3.10+ syntax
- `if TYPE_CHECKING` ブロックは不要 (循環 import 無し: cross_pair.py → stage_gate.py の単方向)
- ruff: `UP007` (`Optional[X]` → `X | None`)、`UP035` (`typing.List` 等 deprecated) を遵守
- structlog logger は `structlog.get_logger(__name__)`

## 9. 段階的実装順序

1. `src/alpha_factory/cross_pair.py` skeleton (ANCHOR_PAIRS / CrossPairConfig / `_make_skipped_result`)
2. `_run_pair_sharpe` + `evaluate_cross_pair` (集約・判定)
3. `StageCRunCrossPairEvaluator`
4. `tests/alpha_factory/test_cross_pair.py` (monkeypatch ベース 20+ tests)
5. `src/alpha_factory/stage_gate.py` cross-pair hook 修正 (例外隔離 + skipped 伝搬)
6. `tests/alpha_factory/test_stage_gate.py` 追記 (3 統合 test)
7. `tests/_helpers.py` に anchor pair meta factory 追加 (必要なら)
8. E2E sanity test (実 backtest 1 ケース)
9. archive 連動 test (test_archive.py への追加 or test_cross_pair.py 内)
10. `config/alpha_factory/default.yaml` 追記
11. ドキュメント更新 (cross-pair.md / concepts/cross-pair-evaluation-shadow.md / terminology.md)
12. `uv run pytest tests/ -v && uv run mypy src/alpha_factory/ && uv run ruff check src/ tests/`

## 10. リスク

| リスク | 対処 |
|--------|------|
| MockBroker quote==JPY 制約で EUR_USD などの実 backtest 不可 | テストは monkeypatch ベース中心、E2E は JPY-quote pair で 1 ケース |
| `sharpe_target_single_provider` が `evaluate_stage_c` 実行順序と整合しない (前回指摘 #2) | Phase 2 では provider 未使用 (default None)、ratio 判定は skip |
| Stage C hook 修正で既存 test_stage_gate.py が壊れる | 既存 test は cross_pair_evaluator=None で動作確認、修正は cross_pair_evaluator!=None 経路のみ |
| `_extract_cross_pair` が Mapping isinstance check しているため CrossPairResult 直接渡しは大丈夫 | 既存実装通り |

## 11. 完了条件

- `uv run pytest tests/` 全通過 (既存 717 tests + 新規 ~30 tests)
- `uv run mypy src/alpha_factory/` エラー無し
- `uv run ruff check src/ tests/` エラー無し
- Codex impl-review APPROVED

## 12. 残課題 (本 TODO 範囲外)

1. **MockBroker 非 JPY-quote 対応** (Phase 2 で構造的 pair_failure を解消する前提条件、優先度 High)
2. swim-lane / run-ga 統合 (多通貨 bars/meta ロード経路 + provider bind)
3. archive スキーマ拡張 (`cross_pair_error_type` / `pair_failure_count` 列追加、GENOMES_SCHEMA 変更)
4. `liquidity_weighted_mean` 実装 (流動性データソース確定後)
5. Phase 4 hard 化 (`mode='hard'` で Stage C `passed` への AND 合成 + reason 語彙追加)
6. config YAML loader (StageGateConfig と一括で実装)
7. migration-triggers.md の shadow → hard 切替条件具体化
8. archive `ii_lite_pass` カラム名を `cross_pair_pass` に rename (互換性のため別 TODO)
