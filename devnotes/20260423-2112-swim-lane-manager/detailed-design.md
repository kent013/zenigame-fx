# 詳細設計: swim-lane-manager (T017)

## 0. 参照

- 概念設計: `devnotes/20260423-2112-swim-lane-manager/conceptual-design.md`
- 概念レビュー: `devnotes/20260423-2112-swim-lane-manager/conceptual-review-r1.md` (APPROVED + 軽微修正対応済)
- 関連 SSOT:
  - `src/alpha_factory/stage_gate.py` (T014)
  - `src/alpha_factory/archive.py` (T015)
  - `src/alpha_factory/cross_pair.py` (T016)
  - `src/dsl/genome.py` (T007 Genome)
  - `src/dsl/strategy.py` (PrimitiveEvaluator)
  - `src/broker/mock.py` (InstrumentMeta, MockBroker)
  - `src/backtest/engine.py` (BacktestConfig)
  - `src/domain/price.py` (PriceBar)

## 1. ファイルレイアウト

### 1.1 新規ファイル

```
src/alpha_factory/swim_lane.py                  # 本実装
tests/alpha_factory/test_swim_lane.py           # テスト (28 ケース)
```

### 1.2 編集ファイル

```
config/alpha_factory/default.yaml               # swim_lane: セクション追加
docs/alpha_factory/swim-lane.md                 # 実装内容で詳細化
docs/alpha_factory/terminology.md               # 5 用語追加
```

### 1.3 触らないファイル (本 TODO 範囲外)

- `src/alpha_factory/stage_gate.py` / `archive.py` / `cross_pair.py` (interface 既定、本 TODO は consumer のみ)
- `scripts/alpha_factory/run_ga.py` (Run-GA TODO で書き換え)

## 2. 公開 API シグネチャ

### 2.1 Module-level

```python
# src/alpha_factory/swim_lane.py

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal

from src.alpha_factory.archive import GenomeArchive
from src.alpha_factory.cross_pair import (
    CrossPairConfig,
    StageCRunCrossPairEvaluator,
)
from src.alpha_factory.stage_gate import (
    CrossPairResult,
    StageGateConfig,
    StageResult,
    evaluate_stage_a,
    evaluate_stage_b,
    evaluate_stage_c,
)
from src.backtest.engine import BacktestConfig
from src.broker.mock import InstrumentMeta
from src.domain.price import PriceBar
from src.dsl.genome import Genome
from src.dsl.strategy import PrimitiveEvaluator

LaneStatus = Literal["active", "converged", "paused"]
GRADUATION_LANE_ID = "graduation"
GRADUATION_INSTRUMENT_SENTINEL = "multi"


@dataclass
class SwimLane:
    lane_id: str
    population: list[Genome]
    generation_count: int = 0
    state: LaneStatus = "active"


@dataclass
class Tier1Lane(SwimLane):
    instrument: str = ""
    bars_60d: list[PriceBar] = field(default_factory=list)
    bars_18m: list[PriceBar] = field(default_factory=list)
    bars_holdout: list[PriceBar] = field(default_factory=list)
    meta: InstrumentMeta | None = None


@dataclass
class GraduationLane(SwimLane):
    seed_graduates: list[Genome] = field(default_factory=list)
    pair_bars: dict[str, list[PriceBar]] = field(default_factory=dict)
    pair_meta: dict[str, InstrumentMeta] = field(default_factory=dict)


class LaneManager:
    def __init__(
        self,
        tier1: dict[str, Tier1Lane],
        graduation: GraduationLane,
        stage_gate_config: StageGateConfig,
        cross_pair_config: CrossPairConfig,
        primitive_evaluator: PrimitiveEvaluator,
        archive: GenomeArchive,
        backtest_config_factory: Callable[[str], BacktestConfig],
        *,
        deferred_promotion: bool = False,
    ) -> None: ...

    def get_all_lanes(self) -> list[SwimLane]: ...

    def run_generation(self, lane_id: str) -> dict[str, Any]: ...

    def graduation_criteria(
        self,
        individual: Genome,
        stage_c_result: StageResult,
        cross_pair_result: CrossPairResult | None,
    ) -> bool: ...

    def promote_graduates(self) -> int: ...
```

### 2.2 内部メソッド (ヘルパー)

```python
# 全て LaneManager 上のプライベートメソッド or module-level helper

def _validate_intraday_constraint(self, factory) -> None: ...
def _build_cross_pair_args(
    self, lane: SwimLane, genome: Genome,
) -> tuple[StageCRunCrossPairEvaluator | None, dict[str, Any] | None]: ...
def _extract_cross_pair_result(
    stage_c_result: StageResult,
) -> CrossPairResult | None: ...
def _mark_for_graduation(
    self, lane: Tier1Lane, genome: Genome,
) -> bool: ...
def _run_tier1_generation(
    self, lane: Tier1Lane,
) -> dict[str, Any]: ...
def _noop_summary(self, lane: SwimLane, elapsed: float) -> dict[str, Any]: ...
```

## 3. 実装詳細

### 3.1 dataclass 定義

```python
LaneStatus = Literal["active", "converged", "paused"]

GRADUATION_LANE_ID = "graduation"
GRADUATION_INSTRUMENT_SENTINEL = "multi"


@dataclass
class SwimLane:
    """全 lane の共通基底。"""
    lane_id: str
    population: list[Genome]
    generation_count: int = 0
    state: LaneStatus = "active"


@dataclass
class Tier1Lane(SwimLane):
    """1 通貨ペア固有 GA lane。

    Note:
        meta は dataclass デフォルト規約のため None 許容。`LaneManager` 構築時に
        non-None を assert する (詳細設計 §3.2.4)。
    """
    instrument: str = ""
    bars_60d: list[PriceBar] = field(default_factory=list)
    bars_18m: list[PriceBar] = field(default_factory=list)
    bars_holdout: list[PriceBar] = field(default_factory=list)
    meta: InstrumentMeta | None = None


@dataclass
class GraduationLane(SwimLane):
    """Universal alpha 探索 lane。Phase 2 では本 TODO 内で評価ロジック未実装。"""
    seed_graduates: list[Genome] = field(default_factory=list)
    pair_bars: dict[str, list[PriceBar]] = field(default_factory=dict)
    pair_meta: dict[str, InstrumentMeta] = field(default_factory=dict)
```

**型上の注意**:
- `SwimLane.population` は default_factory なし → 必須 positional arg。`Tier1Lane(population=[...])` のように明示生成を強制 (mutable default の罠を避ける目的、空 lane を作る場合は `population=[]` を明示)。
- ただし dataclass 継承で base に non-default、子に default を混ぜるとエラーになる。**逃げ手**: `population` も `field(default_factory=list)` にする (Python dataclass の MRO 制約)。実装は次のとおり:

```python
@dataclass
class SwimLane:
    lane_id: str
    population: list[Genome] = field(default_factory=list)
    generation_count: int = 0
    state: LaneStatus = "active"
```

これで `Tier1Lane` / `GraduationLane` の継承時に default-after-default で問題が出ない。

### 3.2 LaneManager 実装

#### 3.2.1 `__init__` バリデーション

**重要な契約変更 (design-review R1 #1 対応)**:

- `tier1: dict[str, Tier1Lane]` の **dict キーは `lane_id`（= `"tier1_{instrument}"`）** を使う。
- `Tier1Lane.instrument` は lane_id から prefix 剥離で自動決定可能だが、明示保持する。
- これにより `get_all_lanes()[i].lane_id` をそのまま `run_generation(lane_id)` に渡せる公開 API の一貫性が確保される。
- constructor 受け取り側 (Run-GA 統合 TODO) では `{f"tier1_{inst}": Tier1Lane(lane_id=f"tier1_{inst}", instrument=inst, ...)}` という形で dict を組み立てる。

```python
def __init__(
    self,
    tier1: dict[str, Tier1Lane],
    graduation: GraduationLane,
    stage_gate_config: StageGateConfig,
    cross_pair_config: CrossPairConfig,
    primitive_evaluator: PrimitiveEvaluator,
    archive: GenomeArchive,
    backtest_config_factory: Callable[[str], BacktestConfig],
    *,
    deferred_promotion: bool = False,
) -> None:
    if not tier1:
        raise ValueError("tier1 must be non-empty (at least one Tier1Lane)")
    for lane_id, lane in tier1.items():
        if not isinstance(lane, Tier1Lane):
            raise TypeError(
                f"tier1[{lane_id!r}] must be Tier1Lane: "
                f"got {type(lane).__name__}"
            )
        if lane.lane_id != lane_id:
            raise ValueError(
                f"tier1[{lane_id!r}].lane_id mismatch: "
                f"got {lane.lane_id!r}"
            )
        if not lane_id.startswith("tier1_"):
            raise ValueError(
                f"tier1 key must start with 'tier1_': got {lane_id!r}"
            )
        expected_instrument = lane_id.removeprefix("tier1_")
        if lane.instrument != expected_instrument:
            raise ValueError(
                f"tier1[{lane_id!r}].instrument must match suffix "
                f"(expected {expected_instrument!r}, got {lane.instrument!r})"
            )
        if lane.meta is None:
            raise ValueError(
                f"tier1[{lane_id!r}].meta must be non-None"
            )
    if not isinstance(graduation, GraduationLane):
        raise TypeError("graduation must be GraduationLane")
    if graduation.lane_id != GRADUATION_LANE_ID:
        raise ValueError(
            f"graduation.lane_id must be {GRADUATION_LANE_ID!r}: "
            f"got {graduation.lane_id!r}"
        )
    self._tier1 = tier1
    self._graduation = graduation
    self._stage_gate_config = stage_gate_config
    self._cross_pair_config = cross_pair_config
    self._primitive_evaluator = primitive_evaluator
    self._archive = archive
    self._bt_factory = backtest_config_factory
    self._deferred_promotion = deferred_promotion
    self._promoted_keys: set[tuple[str, int, str]] = set()  # 冪等性ガード
    # health-check: factory が intraday 制約を満たすか確認
    self._validate_intraday_constraint(backtest_config_factory)

# property exposure (read-only access)
@property
def tier1(self) -> dict[str, Tier1Lane]:
    return self._tier1

@property
def graduation(self) -> GraduationLane:
    return self._graduation
```

#### 3.2.2 `_validate_intraday_constraint`

```python
def _validate_intraday_constraint(
    self, factory: Callable[[str], BacktestConfig],
) -> None:
    """factory が返す BacktestConfig が絶対制約を満たすか試走する。

    1. 任意の instrument (= tier1 の最初のキー) を引数に factory を呼ぶ
    2. session_close_utc_hours が非空 OR engine 側 EOD 強制を期待できる前提を assert
       (engine の単日判定は run_backtest 実行時のため、ここでは
        session_close_utc_hours が空でないことを必要条件として check)
    3. holding_cost_per_day_bps / max_spread_bps の妥当性を assert
    """
    sample_lane_id = next(iter(self._tier1))
    sample_inst = sample_lane_id.removeprefix("tier1_")
    cfg = factory(sample_inst)
    if not isinstance(cfg, BacktestConfig):
        raise TypeError(
            f"backtest_config_factory must return BacktestConfig: "
            f"got {type(cfg).__name__}"
        )
    if not cfg.session_close_utc_hours:
        raise ValueError(
            "backtest_config_factory must return BacktestConfig with non-empty "
            "session_close_utc_hours (intraday absolute constraint)"
        )
    if cfg.holding_cost_per_day_bps < 0:
        raise ValueError(
            f"holding_cost_per_day_bps must be >= 0: "
            f"got {cfg.holding_cost_per_day_bps}"
        )
```

**判断**: engine 側で「session_close_utc_hours 空 + bars 単日」の場合に ValueError を raise する設計はあるが、本 TODO では **factory が常に session_close_utc_hours 非空を返す** ことを契約とする。これにより lane manager の health-check が単純化される (bars 内容に依存しない)。`factory(EUR_JPY)` の試走は副作用無し (BacktestConfig は frozen dataclass、生成のみ)。

#### 3.2.3 `get_all_lanes`

```python
def get_all_lanes(self) -> list[SwimLane]:
    """tier1 + graduation の全 lane を順序固定で返す。

    順序: tier1 dict の挿入順 → graduation。
    呼び出し側 (Run-GA) が決定論的に lane 巡回できることを保証。
    """
    return [*self._tier1.values(), self._graduation]
```

#### 3.2.4 `run_generation`

```python
def run_generation(self, lane_id: str) -> dict[str, Any]:
    """lane_id 指定の lane に対して 1 世代を回す。

    Returns:
        集計サマリー dict。NoOp の場合は §4.10 仕様の最小 dict。
    Raises:
        KeyError: lane_id 不在
        NotImplementedError: lane_id == GRADUATION_LANE_ID (Phase 2)
    """
    start = _time.perf_counter()
    if lane_id == GRADUATION_LANE_ID:
        # Phase 2: GraduationLane の評価は別 TODO
        raise NotImplementedError(
            "GraduationLane.run_generation is not implemented in Phase 2 "
            "(planned for run-ga-full-rewrite TODO)"
        )
    if lane_id not in self._tier1:
        raise KeyError(f"unknown lane_id: {lane_id!r}")
    lane = self._tier1[lane_id]
    if lane.state != "active":
        elapsed = _time.perf_counter() - start
        return self._noop_summary(lane, elapsed)
    summary = self._run_tier1_generation(lane)
    summary["wall_time_seconds"] = _time.perf_counter() - start
    return summary
```

#### 3.2.5 `_run_tier1_generation` (本処理)

```python
def _run_tier1_generation(self, lane: Tier1Lane) -> dict[str, Any]:
    assert lane.meta is not None  # constructor で validate 済み
    bt_cfg = self._bt_factory(lane.instrument)
    stage_a_pass = 0
    stage_b_pass = 0
    stage_c_pass = 0
    graduation_count = 0
    for genome in lane.population:
        # Stage A
        a_result = evaluate_stage_a(
            genome, lane.bars_60d, lane.meta, bt_cfg,
            self._primitive_evaluator, self._stage_gate_config,
        )
        self._archive.collect_stage_a(
            genome, lane.lane_id, lane.generation_count, a_result,
            instrument=lane.instrument,
        )
        if not a_result.passed:
            continue
        stage_a_pass += 1
        # Stage B
        b_result = evaluate_stage_b(
            genome, lane.bars_18m, lane.meta, bt_cfg,
            self._primitive_evaluator, self._stage_gate_config,
        )
        self._archive.collect_stage_b(
            genome, lane.lane_id, lane.generation_count, b_result,
        )
        if not b_result.passed:
            continue
        stage_b_pass += 1
        # Stage C (cross-pair shadow を含む)
        cp_evaluator, cp_inputs = self._build_cross_pair_args(lane, genome)
        c_result = evaluate_stage_c(
            genome, lane.bars_holdout, lane.meta, bt_cfg,
            self._primitive_evaluator, self._stage_gate_config,
            cross_pair_evaluator=cp_evaluator,
            cross_pair_inputs=cp_inputs,
        )
        self._archive.collect_stage_c(
            genome, lane.lane_id, lane.generation_count, c_result,
        )
        if c_result.passed:
            stage_c_pass += 1
        # Graduation 判定
        cp_result = self._extract_cross_pair_result(c_result)
        if self.graduation_criteria(genome, c_result, cp_result):
            promoted = self._mark_for_graduation(lane, genome)
            if promoted:
                graduation_count += 1
    lane.generation_count += 1
    return {
        "lane_id": lane.lane_id,
        "state": lane.state,
        "n_evaluated": len(lane.population),
        "stage_a_pass": stage_a_pass,
        "stage_b_pass": stage_b_pass,
        "stage_c_pass": stage_c_pass,
        "graduation_count": graduation_count,
    }
```

#### 3.2.6 `_build_cross_pair_args`

```python
def _build_cross_pair_args(
    self, lane: SwimLane, genome: Genome,
) -> tuple[StageCRunCrossPairEvaluator | None, dict[str, Any] | None]:
    """Tier1Lane 用に cross-pair adapter を構築する。

    Graduation Lane 呼び出しは Phase 2 で arrive しないが、防御的に (None, None)。
    Tier 1 でも graduation.pair_bars が空 / 当該 instrument 未含有なら (None, None)。
    """
    if not isinstance(lane, Tier1Lane):
        return None, None
    pair_bars = self._graduation.pair_bars
    pair_meta = self._graduation.pair_meta
    if not pair_bars or lane.instrument not in pair_bars:
        return None, None
    cp_evaluator = StageCRunCrossPairEvaluator(
        primitive_evaluator=self._primitive_evaluator,
        cross_pair_config=self._cross_pair_config,
    )
    cp_inputs: dict[str, Any] = {
        "target_pair": lane.instrument,
        "pair_bars_map": pair_bars,
        "meta_map": pair_meta,
    }
    return cp_evaluator, cp_inputs
```

#### 3.2.7 `_extract_cross_pair_result`

```python
@staticmethod
def _extract_cross_pair_result(
    stage_c_result: StageResult,
) -> CrossPairResult | None:
    """Stage C result の payload から CrossPairResult を取り出す。

    archive._extract_cross_pair と同じロジック (重複実装は許容、archive
    内部 helper の公開 API 化は別 TODO)。
    """
    payload_obj = stage_c_result.metrics.get("payload")
    if not isinstance(payload_obj, Mapping):
        return None
    cp_obj = payload_obj.get("cross_pair")
    if not isinstance(cp_obj, Mapping):
        return None
    if bool(cp_obj.get("skipped", True)):
        return None
    result_obj = cp_obj.get("result")
    if isinstance(result_obj, CrossPairResult):
        return result_obj
    return None
```

#### 3.2.8 `graduation_criteria`

```python
def graduation_criteria(
    self,
    individual: Genome,
    stage_c_result: StageResult,
    cross_pair_result: CrossPairResult | None,
) -> bool:
    """Stage C 通過 AND cross-pair 通過の AND 判定。

    cross_pair_result is None (skipped / 例外) は保守的に False。
    Phase 2 では cross-pair shadow が provider 未注入で 2 条件 AND
    (mean / min) 縮退となるが、本判定は cross_pair_result.passed の
    bool 値だけを参照するため Phase 4 で 3 条件に拡張時も変更不要。
    """
    if not stage_c_result.passed:
        return False
    if cross_pair_result is None:
        return False
    return bool(cross_pair_result.passed)
```

#### 3.2.9 `_mark_for_graduation` (冪等性ガード付き)

```python
def _mark_for_graduation(
    self, lane: Tier1Lane, genome: Genome,
) -> bool:
    """個体を graduation に昇格する。冪等性: 同一 key 二重呼び出しは skip。

    Returns:
        新規昇格なら True、既昇格 (skip) なら False。
    """
    key = (lane.lane_id, lane.generation_count, genome.name)
    if key in self._promoted_keys:
        logger.warning(
            "swim_lane.graduation_duplicate_skipped",
            lane_id=lane.lane_id,
            generation=lane.generation_count,
            individual_name=genome.name,
        )
        return False
    self._promoted_keys.add(key)
    self._graduation.seed_graduates.append(genome)
    self._archive.mark_graduated(
        lane.lane_id, lane.generation_count, genome.name,
    )
    return True
```

#### 3.2.10 `promote_graduates`

```python
def promote_graduates(self) -> int:
    """累積 graduation 件数を返す (Phase 2 default 実装は no-op + counter getter)。

    Phase 2: _mark_for_graduation が即時 append + archive.mark_graduated を行うため、
    本メソッドは累積件数の getter として動作する。

    deferred_promotion=True の場合 (Phase 4 拡張用予約): 本 TODO では未実装、
    NotImplementedError raise。
    """
    if self._deferred_promotion:
        raise NotImplementedError(
            "deferred_promotion mode is reserved for run-ga-full-rewrite TODO"
        )
    return len(self._graduation.seed_graduates)
```

#### 3.2.11 `_noop_summary`

```python
def _noop_summary(self, lane: SwimLane, elapsed: float) -> dict[str, Any]:
    return {
        "lane_id": lane.lane_id,
        "state": lane.state,
        "n_evaluated": 0,
        "stage_a_pass": 0,
        "stage_b_pass": 0,
        "stage_c_pass": 0,
        "graduation_count": 0,
        "wall_time_seconds": elapsed,
    }
```

## 4. config 統合

### 4.1 `config/alpha_factory/default.yaml` 追記

既存セクション末尾 (improve_cycle の後) に追加:

```yaml
# Swim lane manager (T017)
# - 実装: src/alpha_factory/swim_lane.py (LaneManager + Tier1Lane + GraduationLane)
# - 概念: docs/alpha_factory/swim-lane.md
# - YAML loader は別 TODO (run-ga-full-rewrite) で実装。本セクションは SSOT のみ。
swim_lane:
  tier1:
    population_size: 30
    generations: 15
    crossover_rate: 0.7
    mutation_rate: 0.3
    elite_count: 2
  graduation:
    population_size: 40
    seed_strategy: "union_of_tier1_graduates"
  graduation_criteria:
    require_stage_c_pass: true
    require_cross_pair_pass: true
```

`SwimLaneConfig` dataclass / loader は本 TODO では追加しない (StageGateConfig / CrossPairConfig と同じ方針)。

## 5. テスト設計

### 5.1 ファイル: `tests/alpha_factory/test_swim_lane.py`

### 5.2 fixtures / helpers

```python
# 主要 helper
def _stub_genome(name: str = "g0_i0") -> Genome: ...
def _stub_meta(pair: str = "EUR_JPY") -> InstrumentMeta: ...
def _stub_bars(pair: str = "EUR_JPY", n: int = 10) -> list[PriceBar]: ...
def _stub_bt_factory_intraday() -> Callable[[str], BacktestConfig]: ...
def _stub_bt_factory_violating() -> Callable[[str], BacktestConfig]: ...
def _make_tier1_lane(instrument: str, pop_size: int = 2) -> Tier1Lane: ...
def _make_graduation_lane(with_pair_data: bool = False) -> GraduationLane: ...
def _make_lane_manager(...) -> LaneManager: ...
```

`tests/dsl/conftest.py::ConstantPrimitiveEvaluator` を再利用 (cross_pair test と同様)。

### 5.3 テストケース一覧 (28 ケース)

#### dataclass / 型検証 (4)

1. **test_swim_lane_dataclass_fields**: `SwimLane(lane_id="x", population=[...])` で生成 OK、default 値検証
2. **test_tier1_lane_inheritance**: `Tier1Lane` が `SwimLane` を継承、`instrument` / `bars_*` / `meta` field 存在
3. **test_graduation_lane_inheritance**: `GraduationLane` が `SwimLane` を継承、`seed_graduates` / `pair_bars` / `pair_meta` field 存在
4. **test_lane_status_literal**: `LaneStatus` の値が `{"active", "converged", "paused"}` (実体は Literal なので set 比較は型上の確認、実装としては assert)

#### LaneManager 初期化 (5)

5. **test_lane_manager_init_basic**: 1 Tier1Lane + GraduationLane で初期化成功、`get_all_lanes()` が 2 lane 返す
6. **test_lane_manager_init_empty_tier1_raises**: tier1={} で `ValueError`
7. **test_lane_manager_init_instrument_key_mismatch**: `tier1["tier1_EUR_JPY"]` の内部 `instrument="USD_JPY"` で `ValueError`（lane_id suffix と instrument の不一致）
8. **test_lane_manager_init_graduation_lane_id_mismatch**: `graduation.lane_id="x"` で `ValueError`
9. **test_lane_manager_init_meta_none_raises**: `Tier1Lane.meta=None` で `ValueError`

#### get_all_lanes (1)

10. **test_get_all_lanes_order**: tier1 dict の挿入順 → graduation の順序が固定 (3 lane で確認)

#### run_generation - Tier1 lane (8)

11. **test_run_generation_unknown_lane_id_keyerror**: 不在 lane_id で `KeyError`
12. **test_run_generation_graduation_not_implemented**: `lane_id="graduation"` で `NotImplementedError`
13. **test_run_generation_stage_a_fail_short_circuit**: monkeypatch で Stage A 失敗、archive.collect_stage_a のみ呼ばれ、b/c は呼ばれない
14. **test_run_generation_stage_b_fail_short_circuit**: A 通過 / B 失敗、collect_stage_a/b は呼ばれ c は呼ばれない、graduation_count=0
15. **test_run_generation_stage_c_fail_no_graduation**: A/B 通過 / C 失敗、archive.collect a/b/c が呼ばれ mark_graduated は呼ばれない
16. **test_run_generation_stage_c_pass_with_cp_pass_graduates**: 全通過 + cross-pair 通過 → mark_graduated 呼ばれ、`graduation.seed_graduates` に append、`promoted_keys` 更新
17. **test_run_generation_stage_c_pass_with_cp_fail_no_graduation**: 全通過 + cross-pair 不通過 → mark_graduated 呼ばれない
18. **test_run_generation_stage_c_pass_with_cp_skipped_no_graduation**: 全通過 + cross-pair skipped → graduation 保守的 False

#### run_generation - state / 計数 (3)

19. **test_run_generation_increments_generation_count**: 3 回呼んで 0→1→2→3
20. **test_run_generation_converged_state_noop**: lane.state="converged" → NoOp summary、generation_count 不変、archive 未更新
21. **test_run_generation_paused_state_noop**: 同上 ("paused")

#### graduation_criteria (4)

22. **test_graduation_criteria_stage_c_fail**: passed=False → False
23. **test_graduation_criteria_cross_pair_none**: stage_c.passed=True / cp=None → False (保守)
24. **test_graduation_criteria_cross_pair_fail**: stage_c.passed=True / cp.passed=False → False
25. **test_graduation_criteria_both_pass**: True

#### promote_graduates / 冪等性 (2)

26. **test_promote_graduates_returns_count**: graduation 0/1/2 件で len 一致
27. **test_mark_for_graduation_idempotent**: 同一 (lane, gen, name) で 2 回 `_mark_for_graduation` を呼んでも seed_graduates は 1 件、archive.mark_graduated も 1 回のみ

#### cross-pair adapter / 健全性 (1)

28. **test_lane_manager_init_intraday_violation_raises**: factory が `session_close_utc_hours=frozenset()` を返す場合、`__init__` で `ValueError`

### 5.4 テスト戦略の詳細

#### 5.4.1 monkeypatch / stub 使用方針

- `evaluate_stage_a/b/c` は **module-level pure function** なので `monkeypatch.setattr("src.alpha_factory.swim_lane.evaluate_stage_a", fake_a)` で差し替え可能
- archive は `MagicMock(spec=GenomeArchive)` で全 collect_* / mark_graduated を mock 化
- cross_pair は `_build_cross_pair_args` を直接 patch する選択肢もあるが、Stage C の `cross_pair_evaluator` 引数経由で渡される設計を尊重し、stub Stage C 結果を作る方が安全

#### 5.4.2 stub Stage C result 構築

```python
def _stage_c_result_with_cross_pair(
    *, passed: bool, cp_skipped: bool, cp_passed: bool | None,
) -> StageResult:
    cp: dict[str, Any] = {"skipped": cp_skipped, "result": None}
    if not cp_skipped:
        cp["result"] = CrossPairResult(
            target_pair="EUR_JPY",
            anchor_pairs=("USD_JPY", "EUR_USD"),
            aggregator_name="median",
            window=(datetime(2026, 1, 1, tzinfo=UTC), datetime(2026, 2, 1, tzinfo=UTC)),
            passed=bool(cp_passed),
            metrics={"skipped": False},
            reason_codes=(),
        )
    payload = {
        "sharpe": 1.2, "total_pnl": 60000.0, "max_drawdown_frac": 0.15,
        "trade_count": 80, "live_criteria_pass": {}, "intraday_compliant": True,
        "overnight_violations": 0, "stress": {"skipped": False}, "cross_pair": cp,
    }
    return StageResult(
        stage="C", passed=passed,
        metrics={"stage": "C", "genome_name": "g0_i0", "n_bars": 100,
                 "wall_time_seconds": 0.1, "payload": payload},
    )
```

## 6. 失敗モード対応 (詳細)

| モード | 検出箇所 | 対処 | テスト |
|--------|----------|------|--------|
| Tier1Lane.meta = None | `__init__` | `ValueError` | 9 |
| graduation.lane_id != "graduation" | `__init__` | `ValueError` | 8 |
| tier1 lane_id/instrument suffix mismatch | `__init__` | `ValueError` | 7 |
| 空 tier1 dict | `__init__` | `ValueError` | 6 |
| factory 違反 | `__init__` | `ValueError` | 28 |
| run_generation 不在 lane_id | `run_generation` | `KeyError` | 11 |
| GraduationLane.run_generation | `run_generation` | `NotImplementedError` | 12 |
| Stage A 失敗 | `_run_tier1_generation` | 短絡、stage_a_pass not 増分 | 13 |
| Stage B 失敗 | 同上 | 同上 | 14 |
| Stage C 失敗 | 同上 | 同上、graduation 判定までは行く (passed False で graduation False) | 15 |
| cross-pair 例外 | T016 で例外隔離済 | payload.cross_pair.skipped=True → graduation False | 18 |
| 二重 graduation | `_mark_for_graduation` | skip + WARN ログ | 27 |
| state != "active" | `run_generation` | NoOp summary | 20, 21 |

## 7. 命名 / log key (canonical)

- structlog logger: `logger = structlog.get_logger(__name__)`
- canonical log keys:
  - `swim_lane.graduation_duplicate_skipped`: `(lane_id, generation, individual_name)`
  - (Stage A/B/C 内部例外は stage_gate.py 側で吸収済、本モジュールでは追加 log なし)

## 8. 依存と import 順序

```python
from __future__ import annotations

import time as _time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any, Literal

import structlog

from src.alpha_factory.archive import GenomeArchive
from src.alpha_factory.cross_pair import (
    CrossPairConfig,
    StageCRunCrossPairEvaluator,
)
from src.alpha_factory.stage_gate import (
    CrossPairResult,
    StageGateConfig,
    StageResult,
    evaluate_stage_a,
    evaluate_stage_b,
    evaluate_stage_c,
)
from src.backtest.engine import BacktestConfig
from src.broker.mock import InstrumentMeta
from src.domain.price import PriceBar
from src.dsl.genome import Genome
from src.dsl.strategy import PrimitiveEvaluator
```

## 9. ドキュメント更新

### 9.1 `docs/alpha_factory/swim-lane.md`

既存 skeleton を以下で詳細化:

- `## 主要定義` セクション直下に **「実装」** subsection 追加 (LaneManager / Tier1Lane / GraduationLane)
- LaneManager interface 表 (constructor 引数 / 主要メソッド)
- archive 4 段伝搬契約への参照
- cross-pair shadow との結合点
- `## SSOT 参照` テーブルに `swim_lane.tier1.population_size` 等を実装済みとして更新

### 9.2 `docs/alpha_factory/terminology.md`

末尾に追記 (anchor 形式は既存パターンに合わせる):

- SwimLane
- Tier1Lane
- GraduationLane
- LaneManager
- Graduation Criteria

各 entry に: クラス／用語の責務、定義ファイル `src/alpha_factory/swim_lane.py`、関連ドキュメントを記載。

## 10. 残課題 (本 TODO 範囲外)

(概念設計 §10 に同じ)

1. Run-GA 統合 (`run-ga-full-rewrite`)
2. Graduation Lane の Stage A/B/C 評価 evaluator (cross-pair 集約 fitness)
3. 多通貨 bars / meta のロード経路
4. lane state 遷移ロジック
5. 並列実行
6. YAML loader (`SwimLaneConfig` dataclass)
7. rollback ポリシー
8. lane 間 individual id 衝突防止 (lane_id prefix ルール強化)
