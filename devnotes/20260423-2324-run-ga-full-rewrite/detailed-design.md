# Detailed Design — run-ga-full-rewrite (T018)

**親**: `conceptual-design.md` + `conceptual-design-r2.md` (R1 Codex review 6 件対応済)

## 1. 目的と scope

`scripts/alpha_factory/run_ga.py` を Phase 2 で揃った基盤 (Clause Genome + Stage A/B/C + GenomeArchive + cross-pair shadow + SwimLane) に完全統合する。既存の縮小版 (T008/T009 時代の `src.ga.run_ga` 直接呼び出し) を全面置換する。

本 TODO の最終目標 = **pop=5, gen=2 の small run がコード path 完走し、archive Parquet + summary.json が生成されること**。

## 2. 新規モジュール: `src/alpha_factory/config.py`

### 2.1 責務

YAML (`config/alpha_factory/default.yaml`) と CLI override dict を merge して frozen dataclass の階層を構築する。validation は各 dataclass の `__post_init__` に任せる (StageGateConfig は既存で豊富なチェック有)。

### 2.2 dataclass 階層

```python
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from types import MappingProxyType
from typing import Any, Literal

import yaml

from src.alpha_factory.cross_pair import CrossPairConfig
from src.alpha_factory.stage_gate import StageGateConfig
from src.utils.time import to_utc


@dataclass(frozen=True)
class DatasetConfig:
    instrument: str
    start: datetime  # from_iso, UTC
    end: datetime    # from_iso, UTC

    def __post_init__(self) -> None:
        if not self.instrument:
            raise ValueError("dataset.instrument must be non-empty")
        if self.end <= self.start:
            raise ValueError(
                f"dataset.end ({self.end}) must be > dataset.start ({self.start})"
            )


@dataclass(frozen=True)
class BacktestSectionConfig:
    initial_cash: Decimal
    leverage: int
    units: int
    max_spread_bps: Decimal | None = None
    holding_cost_per_day_bps: Decimal = Decimal("0")
    session_close_utc_hours: tuple[int, ...] = (23,)

    def __post_init__(self) -> None:
        if self.leverage < 1:
            raise ValueError(f"backtest.leverage must be >= 1: {self.leverage}")
        if self.units < 1:
            raise ValueError(f"backtest.units must be >= 1: {self.units}")
        for h in self.session_close_utc_hours:
            if not 0 <= h <= 23:
                raise ValueError(f"session_close_utc_hours out of range: {h}")


@dataclass(frozen=True)
class GAConfig:
    population_size: int
    generations: int
    crossover_rate: float
    mutation_rate: float
    tournament_size: int
    elite_count: int
    max_depth: int
    max_clause: int = 1
    fitness_metric: Literal["total_pnl", "sharpe", "calmar"] = "sharpe"
    seed: int | None = None
    complexity_alpha: float = 0.03
    complexity_size_ref: float = 10.0
    n_edit_max: int = 3

    def __post_init__(self) -> None:
        if self.population_size < 1:
            raise ValueError("ga.population_size must be >= 1")
        if self.generations < 0:
            raise ValueError("ga.generations must be >= 0")
        if self.elite_count > self.population_size:
            raise ValueError("ga.elite_count must be <= population_size")
        if not 0.0 <= self.crossover_rate <= 1.0:
            raise ValueError("ga.crossover_rate must be in [0, 1]")
        if not 0.0 <= self.mutation_rate <= 1.0:
            raise ValueError("ga.mutation_rate must be in [0, 1]")
        if self.tournament_size < 1:
            raise ValueError("ga.tournament_size must be >= 1")
        if self.max_clause < 1:
            raise ValueError("ga.max_clause must be >= 1")
        if self.max_depth < 1:
            raise ValueError("ga.max_depth must be >= 1")


@dataclass(frozen=True)
class StageWindowsConfig:
    """Stage A/B/C bars の切り出しルール (R1 #3 対応で新設)."""
    stage_a_window_days: int = 60   # dataset.end 末尾から遡る営業日数
    stage_c_holdout_days: int = 60  # dataset.end 以降から取得
    allow_stage_c_fallback_slice: bool = False  # R1 #4: test fixture only

    def __post_init__(self) -> None:
        if self.stage_a_window_days < 1:
            raise ValueError("stage_a_window_days must be >= 1")
        if self.stage_c_holdout_days < 1:
            raise ValueError("stage_c_holdout_days must be >= 1")


@dataclass(frozen=True)
class CrossPairIntegrationConfig:
    """run_ga.py 側の cross-pair 取り扱い設定 (R1 #1 対応)."""
    strict_for_graduation: bool = False
    """False (default) なら単一 instrument mode で cross_pair=skipped でも
    graduation 判定に cross-pair pass 要件を課さない (自動 True 扱い)。True なら
    cross-pair 通過必須。multi-pair bars が提供された時は本 flag に関わらず通常の
    shadow/hard mode 動作を行う。"""


@dataclass(frozen=True)
class AlphaFactoryConfig:
    dataset: DatasetConfig
    backtest: BacktestSectionConfig
    ga: GAConfig
    stage_gate: StageGateConfig
    cross_pair: CrossPairConfig
    stage_windows: StageWindowsConfig
    cross_pair_integration: CrossPairIntegrationConfig

    @property
    def live_criteria(self) -> Mapping[str, float | int]:
        """alias to stage_gate.live_criteria (R1 #5 対応: SSOT は StageGateConfig)."""
        return self.stage_gate.live_criteria
```

### 2.3 loader API

```python
def load_config(
    path: Path, overrides: Mapping[str, Any] | None = None
) -> AlphaFactoryConfig:
    """YAML → overrides deep-merge → AlphaFactoryConfig を返す."""
    with path.open("r", encoding="utf-8") as f:
        raw: dict[str, Any] = yaml.safe_load(f) or {}
    if overrides:
        raw = _deep_merge(raw, overrides)
    return _build_config(raw)


def _deep_merge(
    base: Mapping[str, Any], overrides: Mapping[str, Any]
) -> dict[str, Any]:
    """None value は skip, dict は recursive merge, それ以外は override."""
    out: dict[str, Any] = dict(base)
    for k, v in overrides.items():
        if v is None:
            continue
        if isinstance(v, Mapping) and isinstance(out.get(k), Mapping):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def _build_config(raw: Mapping[str, Any]) -> AlphaFactoryConfig:
    dataset_raw = raw.get("dataset") or {}
    dataset = DatasetConfig(
        instrument=str(dataset_raw.get("instrument", "")),
        start=_parse_dt(dataset_raw.get("start", "")),
        end=_parse_dt(dataset_raw.get("end", "")),
    )

    bt_raw = raw.get("backtest") or {}
    backtest = BacktestSectionConfig(
        initial_cash=Decimal(str(bt_raw.get("initial_cash", "1000000"))),
        leverage=int(bt_raw.get("leverage", 25)),
        units=int(bt_raw.get("units", 10000)),
        max_spread_bps=(
            Decimal(str(bt_raw["max_spread_bps"]))
            if bt_raw.get("max_spread_bps") is not None else None
        ),
        holding_cost_per_day_bps=Decimal(
            str(bt_raw.get("holding_cost_per_day_bps", "0"))
        ),
        session_close_utc_hours=tuple(
            int(h) for h in bt_raw.get("session_close_utc_hours", (23,))
        ),
    )

    ga_raw = raw.get("ga") or {}
    ga = GAConfig(
        population_size=int(ga_raw.get("population_size", 40)),
        generations=int(ga_raw.get("generations", 15)),
        crossover_rate=float(ga_raw.get("crossover_rate", 0.7)),
        mutation_rate=float(ga_raw.get("mutation_rate", 0.3)),
        tournament_size=int(ga_raw.get("tournament_size", 3)),
        elite_count=int(ga_raw.get("elite_count", 2)),
        max_depth=int(ga_raw.get("max_depth", 4)),
        max_clause=int(ga_raw.get("max_clause", 1)),
        fitness_metric=ga_raw.get("fitness_metric", "sharpe"),
        seed=ga_raw.get("seed"),
        complexity_alpha=float(ga_raw.get("complexity_alpha", 0.03)),
        complexity_size_ref=float(ga_raw.get("complexity_size_ref", 10.0)),
        n_edit_max=int(ga_raw.get("n_edit_max", 3)),
    )

    stage_gate_raw = raw.get("stage_gate") or {}
    live_criteria_raw = raw.get("live_criteria") or {}  # R1 #5: top-level から注入
    stage_gate = _build_stage_gate(stage_gate_raw, live_criteria_raw)

    cp_raw = raw.get("cross_pair") or {}
    cp_pass_raw = cp_raw.get("pass_criteria") or {}
    cross_pair = CrossPairConfig(
        sharpe_target_cross_ratio_min=float(
            cp_pass_raw.get("sharpe_target_cross_ratio_min", 0.8)
        ),
        mean_sharpe_cross_min=float(
            cp_pass_raw.get("mean_sharpe_cross_min", 0.15)
        ),
        min_sharpe_cross_min=float(
            cp_pass_raw.get("min_sharpe_cross_min", -0.20)
        ),
        aggregator_lambda=float(cp_raw.get("aggregator_lambda", 0.5)),
        mode=cp_raw.get("mode", "shadow"),
    )

    sw_raw = raw.get("stage_windows") or {}
    stage_windows = StageWindowsConfig(
        stage_a_window_days=int(
            sw_raw.get("stage_a_window_days",
                       stage_gate.stage_a_window_days)
        ),
        stage_c_holdout_days=int(
            sw_raw.get("stage_c_holdout_days",
                       stage_gate.stage_c_holdout_days)
        ),
        allow_stage_c_fallback_slice=bool(
            sw_raw.get("allow_stage_c_fallback_slice", False)
        ),
    )

    cpi_raw = raw.get("cross_pair_integration") or {}
    cross_pair_integration = CrossPairIntegrationConfig(
        strict_for_graduation=bool(
            cpi_raw.get("strict_for_graduation", False)
        ),
    )

    return AlphaFactoryConfig(
        dataset=dataset,
        backtest=backtest,
        ga=ga,
        stage_gate=stage_gate,
        cross_pair=cross_pair,
        stage_windows=stage_windows,
        cross_pair_integration=cross_pair_integration,
    )


def _build_stage_gate(
    stage_gate_raw: Mapping[str, Any],
    live_criteria_raw: Mapping[str, Any],
) -> StageGateConfig:
    a_raw = stage_gate_raw.get("stage_a") or {}
    b_raw = stage_gate_raw.get("stage_b") or {}
    c_raw = stage_gate_raw.get("stage_c") or {}
    live_criteria: dict[str, float | int] = dict(live_criteria_raw) if live_criteria_raw else {}
    return StageGateConfig(
        stage_a_window_days=int(a_raw.get("window_days", 60)),
        stage_a_alpha=float(a_raw.get("alpha", 0.03)),
        stage_a_threshold=float(a_raw.get("threshold", 0.0)),
        stage_b_window_months=int(b_raw.get("window_months", 18)),
        wf_train_days=int(b_raw.get("wf_train_days", 120)),
        wf_test_days=int(b_raw.get("wf_test_days", 20)),
        wf_step_days=int(b_raw.get("wf_step_days", 20)),
        wf_embargo_days=int(b_raw.get("wf_embargo_days", 1)),
        stage_b_median_oos_sharpe_min=float(
            b_raw.get("median_oos_sharpe_min", 0.20)
        ),
        stage_b_positive_fold_min=float(b_raw.get("positive_fold_min", 0.60)),
        stage_b_dsr_min=float(b_raw.get("dsr_min", 0.0)),
        stage_c_holdout_days=int(c_raw.get("holdout_days", 60)),
        spread_stress_multiplier=float(c_raw.get("spread_stress_multiplier", 1.5)),
        spread_stress_min_total_pnl=float(
            c_raw.get("spread_stress_min_total_pnl", 0.0)
        ),
        spread_stress_min_sharpe=float(c_raw.get("spread_stress_min_sharpe", 0.0)),
        live_criteria=live_criteria if live_criteria else None,  # None → default
    ) if live_criteria else StageGateConfig(
        # live_criteria 未指定時は StageGateConfig default を使う
        stage_a_window_days=int(a_raw.get("window_days", 60)),
        stage_a_alpha=float(a_raw.get("alpha", 0.03)),
        stage_a_threshold=float(a_raw.get("threshold", 0.0)),
        stage_b_window_months=int(b_raw.get("window_months", 18)),
        wf_train_days=int(b_raw.get("wf_train_days", 120)),
        wf_test_days=int(b_raw.get("wf_test_days", 20)),
        wf_step_days=int(b_raw.get("wf_step_days", 20)),
        wf_embargo_days=int(b_raw.get("wf_embargo_days", 1)),
        stage_b_median_oos_sharpe_min=float(
            b_raw.get("median_oos_sharpe_min", 0.20)
        ),
        stage_b_positive_fold_min=float(b_raw.get("positive_fold_min", 0.60)),
        stage_b_dsr_min=float(b_raw.get("dsr_min", 0.0)),
        stage_c_holdout_days=int(c_raw.get("holdout_days", 60)),
        spread_stress_multiplier=float(c_raw.get("spread_stress_multiplier", 1.5)),
        spread_stress_min_total_pnl=float(
            c_raw.get("spread_stress_min_total_pnl", 0.0)
        ),
        spread_stress_min_sharpe=float(c_raw.get("spread_stress_min_sharpe", 0.0)),
    )
```

Note: `StageGateConfig(live_criteria=None)` ではなく、`default_factory` に委ねる方が望ましい。実装では `if live_criteria:` で branch する代わりに、**kwargs を一度 dict で組み立てて conditionally `live_criteria` key を含めない**方式を採る:

```python
def _build_stage_gate(stage_gate_raw, live_criteria_raw):
    kwargs: dict[str, Any] = {
        "stage_a_window_days": int(...),
        # ... 他の stage 引数 ...
    }
    if live_criteria_raw:
        kwargs["live_criteria"] = dict(live_criteria_raw)
    return StageGateConfig(**kwargs)
```

### 2.4 `_parse_dt` helper

```python
def _parse_dt(value: str) -> datetime:
    """ISO 8601 or 'YYYY-MM-DDTHH:MM:SSZ' 形式を UTC datetime に変換."""
    if not value:
        raise ValueError("datetime string must be non-empty")
    return to_utc(datetime.fromisoformat(str(value).replace("Z", "+00:00")))
```

## 3. 新規モジュール: `src/alpha_factory/_registry_bridge.py`

### 3.1 責務

`src/alpha_factory/primitives/_base.PrimitiveSpec` (ComputeFn 付きの完全版) を
`src/ga/random_gen.PrimitiveSpec` (simpler, category+domain+param_schema) に変換し、
`PrimitiveRegistry = Mapping[str, PrimitiveSpec]` を返す。

### 3.2 API

```python
def build_random_gen_registry() -> dict[str, RandomGenSpec]:
    """ensure_registered 後の primitives registry から
    src.ga.random_gen 用の Registry を構築する."""
    ensure_registered()
    specs = list_all()  # from _registry
    out: dict[str, RandomGenSpec] = {}
    for spec in specs:
        cat = _category_to_random_gen(spec.category)  # TREND_FOLLOW/MEAN_REVERT/NEUTRAL → directional, MODULATOR → modulator
        param_ranges = {
            p.name: _spec_to_range(p)
            for p in spec.param_schema
        }
        out[spec.id] = RandomGenSpec(
            id=spec.id,
            category=cat,
            domain=spec.domain,
            param_schema=param_ranges,
        )
    return out


def _category_to_random_gen(
    cat: Literal["TREND_FOLLOW", "MEAN_REVERT", "NEUTRAL", "MODULATOR"],
) -> Literal["directional", "modulator"]:
    if cat == "MODULATOR":
        return "modulator"
    return "directional"


def _spec_to_range(p: ParamSpec) -> tuple[float, float] | tuple[int, int]:
    if p.is_int:
        return (int(p.low), int(p.high))
    return (float(p.low), float(p.high))
```

ParamSpec の int / float は spec 側 flag で判定する。`src.ga.random_gen` 側の `random_params` が int か float かを `isinstance(lo, int) and isinstance(hi, int)` で決めているため、bridge も同じ規約で返す。

## 4. `scripts/alpha_factory/run_ga.py` 全面改修

### 4.1 全体フロー

```
main(argv)
├── _parse_args(argv) -> Namespace
├── _load_config_with_overrides(args) -> AlphaFactoryConfig
├── run_id / run_number 採番
├── ensure_registered()  # primitives 32
├── registry = build_random_gen_registry()  # random_gen 用
├── _load_lane_bars(instrument, dataset, stage_windows, allow_fallback)
│     → (bars_stage_a, bars_stage_b, bars_holdout, meta)
├── LaneManager / Tier1Lane / GraduationLane 構築
│     - Tier1Lane.provenance: dict[str, tuple[str|None, str|None]] = {}
│     - GraduationLane.pair_bars = {instrument: bars_stage_b} only when
│       multi-pair support activated; in single-instrument mode → empty
│       (cross-pair skipped by design)
├── archive = GenomeArchive(run_id, run_number)
├── primitive_evaluator = RegistryEvaluator(pair=instrument)
├── bt_factory = _make_bt_factory(dataset, backtest_cfg)
├── lane_manager = LaneManager(
│       tier1={lane_id: tier1_lane},
│       graduation=graduation_lane,
│       stage_gate_config=cfg.stage_gate,
│       cross_pair_config=cfg.cross_pair,
│       primitive_evaluator=primitive_evaluator,
│       archive=archive,
│       backtest_config_factory=bt_factory,
│   )
├── individuals_cache: dict[str, IndividualCacheEntry] = {}
│     - key: genome.name, value: (fitness_pen, stage_a_pass, stage_b_pass, stage_c_pass)
├── per_generation: list[dict] = []
├── for gen in range(cfg.ga.generations + 1):
│   ├── if gen == 0:
│   │     population = [random_genome(rng, f"g0_i{i}", units, ...) for i in range(pop)]
│   │     provenance = {g.name: (None, None) for g in population}
│   ├── else:
│   │     population, provenance = _breed_next_gen(
│   │         prev_population, individuals_cache, ga_cfg, registry, rng, gen
│   │     )
│   ├── tier1_lane.population = population
│   ├── tier1_lane.provenance = provenance
│   ├── summary = lane_manager.run_generation(lane_id)
│   ├── _update_cache(individuals_cache, tier1_lane.population, archive)
│   │     - archive から stage pass flag / fitness_pen を取得して cache 更新
│   ├── per_generation.append({
│   │       generation, n_evaluated, stage_a_pass, stage_b_pass,
│   │       stage_c_pass, graduation_count, best_fitness_pen
│   │     })
│   └── prev_population = population
├── archive_path = archive.flush()
├── best_entry = _select_best(individuals_cache)
├── _write_reports(run_dir, cfg, run_id, run_number, bars, per_generation,
│                  best_entry, archive_path, lane_manager)
└── return 0
```

### 4.2 Tier1Lane の provenance 拡張 (R1 #6 対応)

`src/alpha_factory/swim_lane.py::Tier1Lane` に以下フィールドを追加:

```python
provenance: dict[str, tuple[str | None, str | None]] = field(default_factory=dict)
"""genome.name -> (parent_a, parent_b). run_ga が populate し、LaneManager
が collect_stage_a 時に archive に transfer する (T018 で追加)."""
```

そして `LaneManager._run_tier1_generation` の `collect_stage_a` 呼び出しを以下に変更:

```python
parents = lane.provenance.get(genome.name, (None, None))
self._archive.collect_stage_a(
    genome,
    lane.lane_id,
    lane.generation_count,
    a_result,
    instrument=lane.instrument,
    parent_a=parents[0],
    parent_b=parents[1],
)
```

既存 swim_lane.py の変更は上記 1 箇所のみ。後方互換 (provenance 未設定 = default 空 dict → parent_a/parent_b = None) を保つ。

### 4.3 `_breed_next_gen` (lexicographic tournament)

```python
@dataclass(frozen=True)
class IndividualCacheEntry:
    fitness_pen: float
    stage_a_pass: bool
    stage_b_pass: bool
    stage_c_pass: bool

    @property
    def selection_score(self) -> tuple[int, int, int, float]:
        """Tournament / elitism 用の lexicographic tuple.

        (stage_c_pass, stage_b_pass, stage_a_pass, fitness_pen) で比較。
        """
        return (
            int(self.stage_c_pass),
            int(self.stage_b_pass),
            int(self.stage_a_pass),
            float(self.fitness_pen),
        )


def _tournament(
    pop: list[Genome],
    cache: dict[str, IndividualCacheEntry],
    rng: random.Random,
    k: int,
) -> Genome:
    sample = rng.sample(pop, k=min(k, len(pop)))
    return max(
        sample, key=lambda g: cache[g.name].selection_score
    )


def _breed_next_gen(
    prev_pop: list[Genome],
    cache: dict[str, IndividualCacheEntry],
    ga_cfg: GAConfig,
    registry: dict[str, RandomGenSpec],
    rng: random.Random,
    gen: int,
) -> tuple[list[Genome], dict[str, tuple[str | None, str | None]]]:
    # elitism: top elite_count (selection_score 降順)
    sorted_pop = sorted(
        prev_pop,
        key=lambda g: cache[g.name].selection_score,
        reverse=True,
    )
    elites = sorted_pop[: ga_cfg.elite_count]
    next_genomes: list[Genome] = []
    provenance: dict[str, tuple[str | None, str | None]] = {}
    for e in elites:
        # elite は rename 不要 (name 維持すると archive で同世代衝突するため rename する)
        renamed = replace(e, name=f"g{gen}_i{len(next_genomes)}")
        next_genomes.append(renamed)
        provenance[renamed.name] = (e.name, None)
    while len(next_genomes) < ga_cfg.population_size:
        p1 = _tournament(prev_pop, cache, rng, ga_cfg.tournament_size)
        p2 = _tournament(prev_pop, cache, rng, ga_cfg.tournament_size)
        if rng.random() < ga_cfg.crossover_rate:
            c1, c2 = crossover(
                p1, p2, rng, max_depth=ga_cfg.max_depth
            )
        else:
            c1, c2 = p1, p2
        c1 = mutate(
            c1, rng, ga_cfg.mutation_rate,
            max_clause=ga_cfg.max_clause,
            max_depth=ga_cfg.max_depth,
            registry=registry,
            n_edit_max=ga_cfg.n_edit_max,
        )
        c2 = mutate(
            c2, rng, ga_cfg.mutation_rate,
            max_clause=ga_cfg.max_clause,
            max_depth=ga_cfg.max_depth,
            registry=registry,
            n_edit_max=ga_cfg.n_edit_max,
        )
        name1 = f"g{gen}_i{len(next_genomes)}"
        r1 = replace(c1, name=name1)
        next_genomes.append(r1)
        provenance[name1] = (p1.name, p2.name)
        if len(next_genomes) < ga_cfg.population_size:
            name2 = f"g{gen}_i{len(next_genomes)}"
            r2 = replace(c2, name=name2)
            next_genomes.append(r2)
            provenance[name2] = (p1.name, p2.name)
    return next_genomes, provenance
```

### 4.4 Archive からの fitness_pen 抽出 (`_update_cache`)

`lane_manager.run_generation` が archive に書き込んだ後、archive の内部 dict
から fitness_pen / stage pass flag を取り出して cache を更新する。public API
として archive を直接参照しない方針を維持するため、**archive の internal
`_rows` を直接読むことはしない**。代わりに以下の API 追加提案:

オプション A: archive に `public` 参照 method を追加 (今回採用):

```python
# archive.py に追加
def get_row_snapshot(
    self, lane_id: str, generation: int, individual_name: str
) -> Mapping[str, Any] | None:
    """specific row の snapshot dict (copy) を返す。未知 key は None."""
    key = (lane_id, generation, individual_name)
    row = self._rows.get(key)
    if row is None:
        return None
    # _MAX_STAGE_KEY は internal なので除外
    return {k: v for k, v in row.items() if k != _MAX_STAGE_KEY}
```

これで `run_ga.py` は archive.get_row_snapshot で情報を取り出せる。T015 archive 実装への追加は public API 拡張 (破壊的変更なし)。

オプション B: archive API に依存せず、run_ga.py 側で stage_a_pass などを個別計算...は重複なので却下。オプション A を採用。

```python
def _update_cache(
    cache: dict[str, IndividualCacheEntry],
    population: list[Genome],
    archive: GenomeArchive,
    lane_id: str,
    generation: int,
) -> None:
    for g in population:
        row = archive.get_row_snapshot(lane_id, generation, g.name)
        if row is None:
            # Stage A が no-trades 等で row が作られていない可能性は低いが、
            # 万一の場合は -inf fitness で登録
            cache[g.name] = IndividualCacheEntry(
                fitness_pen=-math.inf,
                stage_a_pass=False,
                stage_b_pass=False,
                stage_c_pass=False,
            )
            continue
        fp = row.get("fitness_pen")
        cache[g.name] = IndividualCacheEntry(
            fitness_pen=float(fp) if fp is not None else -math.inf,
            stage_a_pass=bool(row.get("stage_a_pass", False)),
            stage_b_pass=bool(row.get("stage_b_pass", False)),
            stage_c_pass=bool(row.get("stage_c_pass", False)),
        )
```

### 4.5 bars ロード (`_load_lane_bars`)

```python
def _load_lane_bars(
    instrument: str,
    dataset: DatasetConfig,
    stage_windows: StageWindowsConfig,
) -> LaneBarsBundle:
    """DB から Stage A/B/C の 3 区間 bars + meta を取得する."""
    with SessionLocal() as session:
        pair = _get_currency_pair(session, instrument)
        meta = _meta_from_pair(pair)
        # Stage B = dataset.start .. dataset.end (全体)
        bars_stage_b = _fetch_bars(session, pair.id, dataset.start, dataset.end)
        if not bars_stage_b:
            raise RuntimeError(
                f"no bars for {instrument} in [{dataset.start}, {dataset.end})"
            )
        # Stage A = bars_stage_b の末尾から N 営業日 相当
        # (営業日計算は複雑なので M1 bars 数ベースで近似)
        # 1 営業日 = 24*60 = 1440 bars (M1)
        bars_per_day = 24 * 60
        stage_a_n_bars = stage_windows.stage_a_window_days * bars_per_day
        bars_stage_a = bars_stage_b[-stage_a_n_bars:] if stage_a_n_bars <= len(bars_stage_b) else bars_stage_b
        # Stage C = dataset.end .. dataset.end + holdout_days (DB から別途取得)
        holdout_end = dataset.end + timedelta(days=stage_windows.stage_c_holdout_days)
        bars_holdout = _fetch_bars(session, pair.id, dataset.end, holdout_end)
        if not bars_holdout:
            if stage_windows.allow_stage_c_fallback_slice:
                logger.warning(
                    "run_ga.holdout_fallback_slice",
                    instrument=instrument,
                    note="using Stage B tail as Stage C (test/fixture mode)",
                )
                bars_holdout = bars_stage_b[-stage_a_n_bars:]
            else:
                raise RuntimeError(
                    f"no holdout bars for {instrument} in "
                    f"[{dataset.end}, {holdout_end}); "
                    f"set stage_windows.allow_stage_c_fallback_slice=true "
                    f"ONLY for tests"
                )
    return LaneBarsBundle(
        meta=meta,
        bars_stage_a=bars_stage_a,
        bars_stage_b=bars_stage_b,
        bars_holdout=bars_holdout,
    )
```

### 4.6 `_make_bt_factory`

```python
def _make_bt_factory(
    dataset: DatasetConfig, backtest: BacktestSectionConfig
) -> Callable[[str], BacktestConfig]:
    def factory(instrument: str) -> BacktestConfig:
        return BacktestConfig(
            instrument=instrument,
            start=dataset.start,
            end=dataset.end,
            initial_cash=backtest.initial_cash,
            leverage=backtest.leverage,
            max_spread_bps=backtest.max_spread_bps,
            holding_cost_per_day_bps=backtest.holding_cost_per_day_bps,
            session_close_utc_hours=frozenset(backtest.session_close_utc_hours),
            bar_minutes=1,
        )
    return factory
```

### 4.7 best 選択 (`_select_best`)

```python
def _select_best(
    cache: dict[str, IndividualCacheEntry]
) -> tuple[str, IndividualCacheEntry]:
    if not cache:
        raise RuntimeError("no individuals evaluated")
    return max(cache.items(), key=lambda kv: kv[1].selection_score)
```

### 4.8 `_write_reports`

```python
def _write_reports(
    run_dir: Path,
    cfg: AlphaFactoryConfig,
    run_id: str,
    run_number: int,
    bundle: LaneBarsBundle,
    per_generation: list[dict[str, Any]],
    best_name: str,
    best_entry: IndividualCacheEntry,
    best_genome: Genome,
    best_row: Mapping[str, Any] | None,
    archive_path: Path,
    lane_manager: LaneManager,
    cross_pair_mode: str,  # "skipped_single_instrument" or "enabled"
    now: datetime,
) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)

    best_metrics = _row_to_metrics_dict(best_row)  # subset of BacktestMetrics fields
    live_check = _check_live_criteria(best_row, cfg.live_criteria)

    summary: dict[str, Any] = {
        "run_id": run_id,
        "run_number": run_number,
        "generated_at": now.isoformat(),
        "dataset": {
            "instrument": cfg.dataset.instrument,
            "start": cfg.dataset.start.isoformat(),
            "end": cfg.dataset.end.isoformat(),
            "bars": len(bundle.bars_stage_b),  # 既存互換
            "bars_stage_a": len(bundle.bars_stage_a),
            "bars_stage_b": len(bundle.bars_stage_b),
            "bars_holdout": len(bundle.bars_holdout),
        },
        "ga_config": {
            "population_size": cfg.ga.population_size,
            "generations": cfg.ga.generations,
            "crossover_rate": cfg.ga.crossover_rate,
            "mutation_rate": cfg.ga.mutation_rate,
            "tournament_size": cfg.ga.tournament_size,
            "elite_count": cfg.ga.elite_count,
            "max_depth": cfg.ga.max_depth,
            "units": cfg.backtest.units,
            "fitness_metric": cfg.ga.fitness_metric,
            "seed": cfg.ga.seed,
        },
        "backtest_config": {
            "initial_cash": str(cfg.backtest.initial_cash),
            "leverage": cfg.backtest.leverage,
            "units": cfg.backtest.units,
        },
        "stage_gate_config": {
            "stage_a_window_days": cfg.stage_gate.stage_a_window_days,
            "stage_a_alpha": cfg.stage_gate.stage_a_alpha,
            "stage_b_window_months": cfg.stage_gate.stage_b_window_months,
            "stage_c_holdout_days": cfg.stage_gate.stage_c_holdout_days,
        },
        "cross_pair_config": {
            "mode": cfg.cross_pair.mode,
            "aggregator_lambda": cfg.cross_pair.aggregator_lambda,
            "strict_for_graduation": cfg.cross_pair_integration.strict_for_graduation,
        },
        "cross_pair_runtime_mode": cross_pair_mode,  # "skipped_single_instrument" | "enabled"
        "per_generation": per_generation,
        "best": {
            "name": best_name,
            "fitness": str(best_entry.fitness_pen),  # R1 #2: fitness_pen のみ
            "stage_a_pass": best_entry.stage_a_pass,
            "stage_b_pass": best_entry.stage_b_pass,
            "stage_c_pass": best_entry.stage_c_pass,
            "selection_score": [  # R1 #2: lexicographic 可視化
                int(best_entry.stage_c_pass),
                int(best_entry.stage_b_pass),
                int(best_entry.stage_a_pass),
                float(best_entry.fitness_pen),
            ],
            "metrics": best_metrics,
        },
        "live_criteria": live_check,
        "graduation_count": lane_manager.promote_graduates(),
        "archive_parquet": str(archive_path),
    }
    (run_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, default=_json_default),
        encoding="utf-8",
    )

    history = [
        {
            "generation": pg["generation"],
            "best_fitness": str(pg["best_fitness_pen"]),  # 既存互換: Decimal str
            "stage_a_pass": pg["stage_a_pass"],
            "stage_b_pass": pg["stage_b_pass"],
            "stage_c_pass": pg["stage_c_pass"],
            "graduation_count": pg["graduation_count"],
        }
        for pg in per_generation
    ]
    (run_dir / "history.json").write_text(
        json.dumps(history, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # best genome serialized
    (run_dir / "best_genome.json").write_text(
        json.dumps(genome_to_dict(best_genome), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # population.jsonl (lightweight, 最終世代のみ)
    last_gen_entries: list[dict[str, Any]] = []
    last_gen = per_generation[-1]["generation"] if per_generation else 0
    # archive から最終世代の row を抜き出す (get_row_snapshot を loop)
    # run_ga.py に population 現物 list を持たせているので簡易化:
    # 本 TODO では population.jsonl は (name, fitness_pen) のみ維持。
    # 詳細は実装時に最小限で。


def _row_to_metrics_dict(row: Mapping[str, Any] | None) -> dict[str, Any]:
    if row is None:
        return {}
    return {
        "total_pnl": str(row.get("total_pnl", "0")),
        "sharpe": (
            str(row["sharpe"]) if row.get("sharpe") is not None else None
        ),
        "sortino": (
            str(row["sortino"]) if row.get("sortino") is not None else None
        ),
        "calmar": (
            str(row["calmar"]) if row.get("calmar") is not None else None
        ),
        "max_drawdown_pct": str(row.get("max_drawdown_pct", "0")),
        "trade_count": int(row.get("trade_count", 0)),
    }


def _check_live_criteria(
    row: Mapping[str, Any] | None,
    criteria: Mapping[str, float | int],
) -> dict[str, Any]:
    """archive row の数値から live_criteria をチェック."""
    if row is None:
        return {"checks": {}, "all_pass": False}
    checks: dict[str, dict[str, Any]] = {}

    sharpe_val = row.get("sharpe")
    sharpe_min = float(criteria.get("sharpe_min", 0.0))
    checks["sharpe"] = {
        "value": (str(sharpe_val) if sharpe_val is not None else None),
        "threshold": str(sharpe_min),
        "pass": sharpe_val is not None and float(sharpe_val) >= sharpe_min,
    }
    pnl_val = float(row.get("total_pnl", 0.0))
    pnl_min = float(criteria.get("total_pnl_min", 0.0))
    checks["total_pnl"] = {
        "value": str(pnl_val),
        "threshold": str(pnl_min),
        "pass": pnl_val >= pnl_min,
    }
    # max_drawdown_max は fraction (0-1), row は percent。row/100 で比較
    dd_frac = float(row.get("max_drawdown_pct", 0.0)) / 100.0
    dd_max = float(criteria.get("max_drawdown_max", 1.0))
    checks["max_drawdown_pct"] = {
        "value": str(dd_frac * 100.0),
        "threshold": str(dd_max * 100.0),
        "pass": dd_frac <= dd_max,
    }
    tc = int(row.get("trade_count", 0))
    tc_min = int(criteria.get("trade_count_min", 0))
    tc_max = int(criteria.get("trade_count_max", 10**9))
    checks["trade_count"] = {
        "value": tc,
        "threshold_min": tc_min,
        "threshold_max": tc_max,
        "pass": tc_min <= tc <= tc_max,
    }
    all_pass = all(c["pass"] for c in checks.values())
    return {"checks": checks, "all_pass": all_pass}
```

### 4.9 CLI

```python
def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Alpha Factory GA run (Phase 2 integration)")
    p.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    p.add_argument("--run-id", default=None)
    p.add_argument("--instrument", default=None)
    p.add_argument("--start", default=None)
    p.add_argument("--end", default=None)
    p.add_argument("--population-size", type=int, default=None)
    p.add_argument("--generations", type=int, default=None)
    p.add_argument("--mutation-rate", type=float, default=None)
    p.add_argument("--crossover-rate", type=float, default=None)
    p.add_argument("--tournament-size", type=int, default=None)
    p.add_argument("--elite-count", type=int, default=None)
    p.add_argument("--max-depth", type=int, default=None)
    p.add_argument("--fitness-metric", choices=["total_pnl", "sharpe", "calmar"], default=None)
    p.add_argument("--seed", type=int, default=None)
    return p.parse_args(argv)


def _args_to_overrides(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "dataset": {
            "instrument": args.instrument,
            "start": args.start,
            "end": args.end,
        },
        "ga": {
            "population_size": args.population_size,
            "generations": args.generations,
            "mutation_rate": args.mutation_rate,
            "crossover_rate": args.crossover_rate,
            "tournament_size": args.tournament_size,
            "elite_count": args.elite_count,
            "max_depth": args.max_depth,
            "fitness_metric": args.fitness_metric,
            "seed": args.seed,
        },
    }
```

### 4.10 `main` の骨格

```python
def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    cfg = load_config(args.config, overrides=_args_to_overrides(args))

    now = datetime.now(tz=UTC)
    run_id = args.run_id or f"run_{now.strftime('%Y%m%d_%H%M%S')}"
    run_number = get_latest_run_number() + 1
    run_dir = RUN_REPORTS_DIR / f"run-{run_number}"

    logger.info(
        "ga.run.start",
        run_id=run_id,
        run_number=run_number,
        instrument=cfg.dataset.instrument,
    )

    ensure_registered()
    rg_registry = build_random_gen_registry()

    bundle = _load_lane_bars(
        cfg.dataset.instrument, cfg.dataset, cfg.stage_windows
    )

    archive = GenomeArchive(run_id=run_id, run_number=run_number)
    lane_id = f"tier1_{cfg.dataset.instrument}"

    primitive_evaluator = RegistryEvaluator(pair=cfg.dataset.instrument)
    bt_factory = _make_bt_factory(cfg.dataset, cfg.backtest)

    tier1_lane = Tier1Lane(
        lane_id=lane_id,
        instrument=cfg.dataset.instrument,
        bars_60d=bundle.bars_stage_a,
        bars_18m=bundle.bars_stage_b,
        bars_holdout=bundle.bars_holdout,
        meta=bundle.meta,
    )
    graduation_lane = GraduationLane(
        lane_id=GRADUATION_LANE_ID,
        pair_bars={},  # 単一 instrument mode では空 (cross-pair skipped)
        pair_meta={},
    )
    lane_manager = LaneManager(
        tier1={lane_id: tier1_lane},
        graduation=graduation_lane,
        stage_gate_config=cfg.stage_gate,
        cross_pair_config=cfg.cross_pair,
        primitive_evaluator=primitive_evaluator,
        archive=archive,
        backtest_config_factory=bt_factory,
    )

    cross_pair_mode = (
        "enabled" if graduation_lane.pair_bars
        else "skipped_single_instrument"
    )

    rng = random.Random(cfg.ga.seed)
    cache: dict[str, IndividualCacheEntry] = {}
    per_generation: list[dict[str, Any]] = []
    prev_population: list[Genome] = []

    for gen in range(cfg.ga.generations + 1):
        if gen == 0:
            population = [
                random_genome(
                    rng, name=f"g0_i{i}", units=cfg.backtest.units,
                    max_clause=cfg.ga.max_clause,
                    max_depth=cfg.ga.max_depth, registry=rg_registry,
                )
                for i in range(cfg.ga.population_size)
            ]
            provenance = {g.name: (None, None) for g in population}
        else:
            population, provenance = _breed_next_gen(
                prev_population, cache, cfg.ga, rg_registry, rng, gen
            )

        tier1_lane.population = population
        tier1_lane.provenance = provenance
        summary = lane_manager.run_generation(lane_id)
        _update_cache(
            cache, population, archive, lane_id, tier1_lane.generation_count - 1
        )
        # graduation を strict_for_graduation=False で単一 instrument 時のみ
        # skipped fallback (lane manager 側は未変更、ここで上書きする)
        if cross_pair_mode == "skipped_single_instrument" and \
                not cfg.cross_pair_integration.strict_for_graduation:
            # 単一 instrument では cross-pair skipped により
            # lane_manager の graduation は 0。ここでは Stage C 通過のみを
            # ベースに graduation_count_effective を算出する:
            sc_pass_count = summary["stage_c_pass"]
            eff_graduation = sc_pass_count
        else:
            eff_graduation = summary["graduation_count"]

        best_fitness_pen = max(
            (cache[g.name].fitness_pen for g in population),
            default=float("-inf"),
        )

        per_generation.append({
            "generation": gen,
            "n_evaluated": summary["n_evaluated"],
            "stage_a_pass": summary["stage_a_pass"],
            "stage_b_pass": summary["stage_b_pass"],
            "stage_c_pass": summary["stage_c_pass"],
            "graduation_count": summary["graduation_count"],
            "effective_graduation_count": eff_graduation,
            "best_fitness_pen": best_fitness_pen,
        })
        prev_population = population

    archive_path = archive.flush()

    best_name, best_entry = _select_best(cache)
    best_row = archive.get_row_snapshot(lane_id, tier1_lane.generation_count - 1, best_name)
    best_genome = next(g for g in prev_population if g.name == best_name) if prev_population else _fallback_find_best(cache, lane_manager)

    _write_reports(
        run_dir=run_dir,
        cfg=cfg,
        run_id=run_id,
        run_number=run_number,
        bundle=bundle,
        per_generation=per_generation,
        best_name=best_name,
        best_entry=best_entry,
        best_genome=best_genome,
        best_row=best_row,
        archive_path=archive_path,
        lane_manager=lane_manager,
        cross_pair_mode=cross_pair_mode,
        now=now,
    )

    RUN_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    (RUN_CACHE_DIR / f"{run_id}.json").write_text(
        json.dumps({"run_id": run_id, "run_number": run_number}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    logger.info(
        "ga.run.done",
        run_id=run_id,
        run_number=run_number,
        best_fitness=str(best_entry.fitness_pen),
        stage_c_pass=best_entry.stage_c_pass,
    )
    print(
        f"[done] run_id={run_id} run_number={run_number} "
        f"best={best_name} fitness_pen={best_entry.fitness_pen} "
        f"stage_c={best_entry.stage_c_pass} report={run_dir}"
    )
    return 0
```

Note: `best_genome` lookup は "最新世代に best が存在する場合" に限る素朴な実装。過去世代が best を残しているケースは、elite が毎世代 renamed で持ち上がるので OK。ただし実装上、best_name に該当する Genome が prev_population に居ない ("first-gen best" でかつ elite_count=0 のケース) は考えにくいが防御的に、初代 population を別途保持しておくか、**run_ga.py 側で `genomes_by_name: dict[str, Genome]` に毎世代 accumulate** する方が安全。

**実装では `genomes_by_name: dict[str, Genome] = {}` を main 内部で保持**し、各世代 populate 時に `for g in population: genomes_by_name[g.name] = g` を実行する。`best_genome = genomes_by_name[best_name]`。

## 5. テスト: `tests/scripts/test_alpha_factory_run_ga.py`

### 5.1 テストケース

1. **`test_load_config_from_yaml`**: `config/alpha_factory/default.yaml` を読み込み、各 dataclass が期待値で構築されることを検証。`live_criteria` が `AlphaFactoryConfig.live_criteria` property 経由で読める、`stage_windows` default が適用される。
2. **`test_config_cli_overrides`**: CLI override dict が反映されるか (dataset.instrument, ga.population_size, ga.seed を override)。None は skip。
3. **`test_config_rejects_invalid`**: `dataset.end <= dataset.start` で ValueError、`ga.elite_count > population_size` で ValueError。
4. **`test_registry_bridge`**: `build_random_gen_registry` が `ensure_registered` 後に 32 個の spec を返し、 category が "directional"/"modulator" に分類される。
5. **`test_run_id_generation`**: `get_latest_run_number` + 1 で採番される (既存テストで担保済なら最小 assertion)。
6. **`test_smoke_run_with_mocked_db`**: `SessionLocal` を monkeypatch し、dummy bars (800 本程度) + dummy CurrencyPair を返させて `main(["--population-size", "5", "--generations", "2", ...])` を実行。archive parquet + summary.json が生成されることを assert。`allow_stage_c_fallback_slice=True` を config override で有効化。bars 生成は `_stub_bars_over_range(start, end, n)` helper。

### 5.2 DB mock のポイント

`SessionLocal` を class 単位で monkeypatch するのではなく、run_ga.py 側の `_load_lane_bars` が使う `SessionLocal` を差し替える。
または `_load_lane_bars` を上位から differently injectable にする案もあるが、本 TODO では `monkeypatch.setattr("scripts.alpha_factory.run_ga.SessionLocal", ...)` で十分。

```python
class _MockSession:
    def __init__(self, bars_by_range, pair_row):
        self._bars = bars_by_range
        self._pair = pair_row

    def __enter__(self): return self
    def __exit__(self, *a): pass

    def scalars(self, stmt): return self  # スタブ
    def one_or_none(self): return self._pair
    def all(self): return self._bars  # 単純化: 範囲無視で同じを返す
```

SQLAlchemy stmt の introspection はしない。`select(CurrencyPair)` と `select(PriceBarM1)` の分岐は **`stmt.column_descriptions[0]['type']` を見て振り分ける**、または **call 順** (1 回目 = pair, 2 回目以降 = bars) で単純化。本 TODO では call 順で十分 (pair → stage_b → holdout の順)。

### 5.3 テスト config fixture

`tests/fixtures/alpha_factory_min_config.yaml` を新設:

```yaml
dataset:
  instrument: EUR_JPY
  start: "2026-01-01T00:00:00Z"
  end: "2026-02-01T00:00:00Z"
backtest:
  initial_cash: "1000000"
  leverage: 25
  units: 10000
  max_spread_bps: "5"
ga:
  population_size: 5
  generations: 2
  crossover_rate: 0.7
  mutation_rate: 0.3
  tournament_size: 3
  elite_count: 1
  max_depth: 2
  max_clause: 1
  fitness_metric: sharpe
  seed: 42
live_criteria:
  sharpe_min: 1.0
  total_pnl_min: 0
  max_drawdown_max: 0.5
  trade_count_min: 0
  trade_count_max: 10000
stage_gate:
  stage_a:
    window_days: 1
  stage_b:
    wf_train_days: 5
    wf_test_days: 2
    wf_step_days: 2
    wf_embargo_days: 0
  stage_c:
    holdout_days: 1
stage_windows:
  stage_a_window_days: 1
  stage_c_holdout_days: 1
  allow_stage_c_fallback_slice: true
cross_pair:
  mode: shadow
  aggregator_lambda: 0.5
  pass_criteria:
    sharpe_target_cross_ratio_min: 0.8
    mean_sharpe_cross_min: 0.15
    min_sharpe_cross_min: -0.20
cross_pair_integration:
  strict_for_graduation: false
```

### 5.4 テスト実行時の registry

`build_random_gen_registry` で 32 個を使う。ただし smoke テストでは evaluator 実行時間が現実的でないため、`max_clause=1, max_depth=2, population_size=5, generations=2` で抑える。1 genome = Stage A (no-trades 濃厚) → Stage B / C は skipped が多く、コード path 確認に十分。

## 6. archive 拡張

`src/alpha_factory/archive.py::GenomeArchive` に以下 method を追加 (公開 API 拡張、破壊的変更なし):

```python
def get_row_snapshot(
    self, lane_id: str, generation: int, individual_name: str
) -> Mapping[str, Any] | None:
    """row の snapshot (mapping copy) を返す。未登録 key は None."""
    key = (lane_id, generation, individual_name)
    row = self._rows.get(key)
    if row is None:
        return None
    return {k: v for k, v in row.items() if k != _MAX_STAGE_KEY}
```

## 7. 既存コード変更サマリ

| File | Change | Risk |
| --- | --- | --- |
| `scripts/alpha_factory/run_ga.py` | 全面書換 | 中 (CLI 出力契約維持でレポート生成系に影響しない設計) |
| `src/alpha_factory/config.py` | 新規 | 低 |
| `src/alpha_factory/_registry_bridge.py` | 新規 | 低 |
| `src/alpha_factory/swim_lane.py::Tier1Lane` | field `provenance` 追加 + `_run_tier1_generation` の collect_stage_a 引数追加 | 低 (既存テストは後方互換 default で通る) |
| `src/alpha_factory/archive.py::GenomeArchive` | method `get_row_snapshot` 追加 | 低 |
| `tests/scripts/test_alpha_factory_run_ga.py` | 新規 (smoke + config) | 低 |
| `tests/fixtures/alpha_factory_min_config.yaml` | 新規 | 低 |

## 8. 出力仕様サマリ (既存契約維持 + 追加キー)

### summary.json (必須キー、**既存維持**)

- `run_id`, `run_number`, `generated_at`
- `dataset.instrument`, `dataset.start`, `dataset.end`, `dataset.bars`
- `ga_config.*` (現行のサブキーすべて)
- `backtest_config.initial_cash/leverage/units`
- `best.name`, `best.fitness` (Decimal 文字列: **fitness_pen のみ**), `best.metrics`
- `live_criteria.checks`, `live_criteria.all_pass`

### summary.json (**追加キー**)

- `dataset.bars_stage_a`, `dataset.bars_stage_b`, `dataset.bars_holdout`
- `stage_gate_config.*` (簡易)
- `cross_pair_config.mode/aggregator_lambda/strict_for_graduation`
- `cross_pair_runtime_mode` ("skipped_single_instrument" or "enabled")
- `per_generation[]` (世代ごとの集計)
- `best.stage_a_pass/stage_b_pass/stage_c_pass`
- `best.selection_score` (list[int, int, int, float])
- `graduation_count` (lane_manager.promote_graduates)
- `archive_parquet`

### history.json (**既存互換**)

```json
[{"generation": 0, "best_fitness": "0.12", "stage_a_pass": 2, "stage_b_pass": 0, "stage_c_pass": 0, "graduation_count": 0}, ...]
```

`best_fitness` は従来通り Decimal 文字列 (fitness_pen)。`stage_a_pass` 等は追加フィールド。

### best_genome.json (**既存互換**)

`src.dsl.serialize.genome_to_dict` の出力そのまま。

### population.jsonl (**既存互換**)

最終世代の `{"name", "fitness"}` 行。本 TODO では最終世代の `genomes_by_name[name]` から fitness_pen を引いて出力 (archive が SSOT だが、jsonl 互換のため duplicate 出力)。

## 9. 検証項目 (impl-review 準備)

- [ ] mypy クリーン (`src/`, `scripts/alpha_factory/run_ga.py`)
- [ ] ruff クリーン (`src/`, `tests/`, `scripts/alpha_factory/`)
- [ ] 既存テスト (baseline: 784 passed) から減らない
- [ ] 新規 6 テスト pass
- [ ] default.yaml + config fixture YAML でコード path が構築できる
- [ ] summary.json の `dataset.instrument/start/end/bars` が現行と bitwise 同型 (既存 generate_run_report.py が壊れない)
- [ ] `best.fitness` が Decimal 文字列

## 10. 実装順序

1. `src/alpha_factory/archive.py` に `get_row_snapshot` 追加 (+ テスト 1 件)
2. `src/alpha_factory/swim_lane.py::Tier1Lane` に `provenance` 追加 + `_run_tier1_generation` 修正 (+ 既存テスト run で regression 無し確認)
3. `src/alpha_factory/config.py` 新規 (+ テスト 3 件)
4. `src/alpha_factory/_registry_bridge.py` 新規 (+ テスト 1 件)
5. `scripts/alpha_factory/run_ga.py` 全面書換 (+ smoke テスト 1 件)
6. tests/fixtures/alpha_factory_min_config.yaml 新規
7. mypy / ruff / pytest 全 run
8. Codex impl-review
