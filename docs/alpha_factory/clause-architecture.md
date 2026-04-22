# Clause Architecture

## 目的

ゲノム内部構造（Clause）の構造・式・合成ルールを一箇所に集約する。実装詳細は `concepts/clause-genome-structure.md` および後続 TODO で扱う。

## スコープ

- Clause の構成要素（directional / local_gate / weight）
- composite score の合成式とヒステリシス
- max_clause の段階解放方針
- long/short 対称制御 / セッション制御 / コスト反映の構造的要件

数値（α ペナルティ・閾値など）は SSOT 参照。

## 用語リンク

本ドキュメントで使用する用語: [Clause](terminology.md#clause), [Composite Score](terminology.md#composite-score), [Directional](terminology.md#directional), [Local Gate](terminology.md#local-gate), [Modulator](terminology.md#modulator), [TC](terminology.md#tc)

## 主要定義

### 1 Clause の構造

```
Clause = directional × local_gate × weight
dir_score  = Σ(w_i × signal_i) / Σ|w_i|          # directional の加重和（正規化）
gate       = Π gate_fn(gate_signal_j)             # local_gate の積（[0, 1] 有界）
clause_score = dir_score × gate
```

### 複数 Clause の合成

```
composite = Σ(cw_k × clause_score_k) / Σ|cw_k|
```

### ヒステリシス

- エントリー閾値 `θ_on`
- エグジット閾値 `θ_off`
- **必ず `θ_on > θ_off`**（チャタリング抑止）

### max_clause 段階解放

- 初期: 1（Phase 2 MVP）
- 標準: 2（Phase 3）
- 上限: 3（昇格試験合格時のみ、Phase 3 以降）

### 必須構造要件

- long/short 対称制御（パラメータは分離可）
- session close / time_stop による min/max 保有時間
- spread / slippage / swap を fitness に反映（絶対制約）

## 実装関数シグネチャ (T007 完了時点)

`src/dsl/` に以下の pure function / dataclass / Protocol を配置する。

### dataclass 群 (`src/dsl/genome.py`)

```python
@dataclass(frozen=True)
class SignalConfig:
    name: str                                       # primitive ID
    weight: float                                   # directional [0.1, 2.0] / gate [-2.0, 2.0]
    params: dict[str, float | int] = field(default_factory=dict)
    # __post_init__ で defensive copy

@dataclass(frozen=True)
class ClauseConfig:
    directional: tuple[SignalConfig, ...]
    local_gate: tuple[SignalConfig, ...]
    weight: float

@dataclass(frozen=True)
class PositionConfig:
    entry_threshold: float   # θ_on
    exit_threshold: float    # θ_off（θ_on > θ_off）
    max_pos: int
    time_stop_min: int       # 0 で無効

@dataclass(frozen=True)
class RiskConfig:
    stop_atr: float
    take_atr: float

@dataclass(frozen=True)
class Genome:
    name: str
    units: int
    clauses: tuple[ClauseConfig, ...]   # 1-3 clause
    position: PositionConfig
    risk: RiskConfig
```

### composite 関数 (`src/dsl/composite.py`)

```python
def compute_dir_score(signals, values) -> float        # Σ(w×x) / Σ|w|、空/denom=0 → 0.0
def compute_gate(signals, values) -> float             # Π gate、空 → 1.0
def compute_clause_score(clause, values) -> float      # dir_score × gate
def compute_composite(clauses, values_per_clause) -> float
    # Σ(cw × cs) / Σ|cw|、len 不一致・空 → ValueError、denom=0 → 0.0
```

### Strategy と PrimitiveEvaluator (`src/dsl/strategy.py`)

```python
class PrimitiveEvaluator(Protocol):
    def evaluate(self, bars: list[PriceBar], idx: int, signal: SignalConfig) -> float: ...

class DslStrategy:
    def __init__(
        self, genome: Genome, evaluator: PrimitiveEvaluator, *,
        warmup_bars: int = 0, session_close_utc: time | None = None,
    ) -> None: ...
    def warmup_bars(self) -> int: ...
    def on_bar(self, bar: PriceBar, snapshot: PortfolioSnapshot) -> list[OrderSignal]: ...
```

ヒステリシス動作:
- 無保有: `composite >= θ_on` → `open_long` / `-composite >= θ_on` → `open_short`
- long 保有: `composite < θ_off` → `close_position`
- short 保有: `-composite < θ_off` → `close_position`
- `time_stop_min > 0` かつ経過時間 ≥ `time_stop_min` → 強制 close
- `session_close_utc is not None` かつ `bar.bar_time.time() >= session_close_utc` → 強制 close

**イントラデイ絶対制約の不変条件**: `session_close_utc is not None` **または** backtest engine 側の
EOD 強制クローズ（`is_eod → close_all(reason="eod")`）のどちらかが必ず有効であること。

### enforce_consistency (`src/dsl/enforce.py`)

```python
def enforce_consistency(genome: Genome) -> Genome:
    # directional: abs + clip [0.1, 2.0]、同 name dedupe（後勝ち）
    # local_gate: clip [-2.0, 2.0]、同 name dedupe、最大 1 本（|weight| 最大）
    # directional 空 Clause は除去、全 Clause 消失で ValueError
    # len(clauses) > 3 → |weight| Top 3 に絞る
    # PositionConfig: entry > exit（違反時 swap、等号時 epsilon 分離）、max_pos ≥ 1、time_stop_min ≥ 0
    # RiskConfig: stop_atr / take_atr ≥ 1e-6
    # 全 weight / threshold / ATR に NaN/inf があれば ValueError
```

有限実数入力で冪等（`f(f(x)) == f(x)`）。

### serialize (`src/dsl/serialize.py`)

`genome_to_dict(g: Genome) -> dict[str, Any]` / `genome_from_dict(d) -> Genome`。JSON round-trip 保証。

## GA operators 実装シグネチャ (T008 完了時点)

Clause ベース Genome に対応した crossover / mutate / random_gen / runner を `src/ga/` に配置。

### crossover (`src/ga/operators.py`)

**実行可能 operator 集合から一様選択**（STGP 系譜、Montana 1995）。候補集合は空にならない
（`position_swap` / `risk_swap` / `clause_swap` が always）。

| operator | 前提条件 | 内容 |
|----------|---------|------|
| clause_point | `min(len(A.clauses), len(B.clauses)) >= 2` | 点交叉で clauses を分割・交換 |
| clause_swap | always | 各親から clause を 1 本選び丸ごと swap |
| directional_swap | 対応 clause に `len(directional) >= 2` が 1 組以上 | directional tuple の点交叉（max_depth を超えないよう trim 保護） |
| gate_swap | 対応 clause の local_gate が片方でも非空 | clause の local_gate を丸ごと swap（max_depth 保護付き） |
| position_swap | always | PositionConfig を親選択で swap |
| risk_swap | always | RiskConfig を親選択で swap |

各子は最後に `enforce_consistency` を通して最終正規化。

### mutate (`src/ga/operators.py`)

**attempted-edits 契約**: `n_attempts ~ Binomial(n_edit_max, mutation_rate)` で編集試行回数を
先引きし、各試行で実行可能 kernel を一様選択。

- `mutation_rate=0` → 0 attempts（完全 no-op）
- `mutation_rate=1` → `n_edit_max` attempts 確定（default K=3）
- effective-diffs 保証は提供しない（weight perturb で σ 正規分布から元値が引かれる等の no-op あり）

kernel 一覧: `weight_perturb / params_perturb / signal_add / signal_del / clause_add / clause_del
/ position_perturb / risk_perturb`。構造不変条件（directional>=1、clauses>=1、max_depth / max_clause
hard cap）は各 kernel が前提条件で守る。

### random_gen (`src/ga/random_gen.py`)

Clause 構造の初期個体生成。`PrimitiveSpec(id, category, domain, param_schema)` を受け取り
category で slot（directional / local_gate）を制約:

- directional slot → category=`directional` の primitive のみ
- local_gate slot → category=`modulator` の primitive のみ

生成後に `enforce_consistency` を通す（bounded retry 3 回）。

### complexity penalty (`src/ga/complexity.py`)

```
nodes       = Σ(len(c.directional) + len(c.local_gate))
max_width   = max(len(c.directional) + len(c.local_gate))  # 幅（深さではない）
n_clause    = len(clauses)
gate_nodes  = Σ len(c.local_gate)
size_norm   = (nodes + 0.5 × max_width + 2 × (n_clause - 1) + 0.5 × gate_nodes) / size_ref
fitness_pen = fitness_raw - α × size_norm
```

default: `α=0.03, size_ref=10.0`（暫定、後続 TODO で SSOT 化）。
Luke & Panait 2006 の parsimony pressure（hard cap + size 罰則の併用）に基づく。

### runner (`src/ga/runner.py`)

`run_ga(evaluator, config, *, registry)` で evaluator を外部注入。
`evaluator: Callable[[Genome], EvaluationResult]` で `EvaluationResult(fitness_raw, meta)`
を返す。NaN / inf は runner 側で `-math.inf` に置換。`Individual` は
`genome / fitness_raw / fitness_pen / meta` を保持。

T008 時点では `evaluate_genome` は NotImplementedError のまま（T009 clause-backtest-integration
で復活）。テスト用の dummy primitive registry は `src/ga/_dummy_registry.py`（T010 で置換）。

## backtest 統合 (T009 完了時点)

T009 `clause-backtest-integration` で `src/backtest/engine.py` / `src/broker/mock.py` /
`src/ga/fitness.py` を Clause 対応にした。以下が実装契約:

### BacktestConfig 新規フィールド

```python
@dataclass(frozen=True)
class BacktestConfig:
    instrument: str
    start: datetime
    end: datetime
    initial_cash: Decimal
    leverage: int
    max_spread_bps: Decimal | None = None           # T009 追加
    holding_cost_per_day_bps: Decimal = Decimal(0)  # T009 追加（旧名 swap_cost_per_day_bps 廃止）
    session_close_utc_hours: frozenset[int] = frozenset()  # T009 追加（hour 粒度）
    bar_minutes: int = 1                            # T009 追加（holding cost 按分）
```

### spread フィルタ（前バー close spread、no-lookahead）

- 判定値: 「前バー close spread_bps」= `(ask.close - bid.close) / mid_close × 10000`
- 適用タイミング: `MockBroker.fill_pending` 冒頭で `_last_close_spread_bps > max_spread_bps`
  ならその bar の pending open 系シグナルを drop（reject）
- 初期 bar（前バー未観測）は reject しない（defensive default）
- `max_spread_bps=None` で無効

### holding cost proxy（保有時間比例コスト）

- 本 TODO は「保有時間に比例する cost」を fitness に反映する proxy 実装。
  実 OANDA rollover swap（日付境界固定・水曜 3 倍・side 別）の精密再現は将来 TODO
- 単位: bps/day（正値のみ。負値は `__post_init__` で raise）
- 適用: 各 bar `mark_to_market` 直後で `MockBroker.apply_bar_holding_cost(bar, per_day_bps, bar_minutes)`
  - `per_bar_bps = per_day_bps × (bar_minutes / 1440)`
  - `cost_i = |notional_home_i| × per_bar_bps / 10000`（各 open position）
  - `cash -= Σ cost_i` に即時反映
  - 各 position の累計 holding cost を `MockBroker._holding_cost_by_position[pos.id]` に加算
- `_close_one` で `Trade.pnl = raw_pnl - cost_accum` として **Trade.pnl に cost 反映済みの
  net_pnl を記録**（cash は raw_pnl で加算、二重控除回避）
- 不変条件: `sum(Trade.pnl) == final_cash - initial_cash`

### session close（hour 粒度、engine 絶対制約）

- `session_close_utc_hours: frozenset[int]`（hour 粒度、HH:MM 粒度は将来 TODO）
- 発動タイミング（bar.bar_time.hour が集合に含まれる場合、順序を厳守）:
  1. pending の open 系シグナルを drop
  2. `fill_pending(bar)`（open 系は既に drop 済み）
  3. `mark_to_market(bar)` + holding cost
  4. margin call check
  5. 保有があれば `close_all(bar, reason="eod")`
  6. `strategy.on_bar` を呼ぶ（snapshot は全クローズ後）
  7. strategy から open 系シグナルが返っても submit せず drop
  8. close 系シグナルは submit
- strategy 内 `session_close_utc: time | None` は fail-safe（engine 側が primary）

### イントラデイ絶対制約（North Star）

`run_backtest` 冒頭で以下のいずれかが有効でないと `ValueError`:
- `session_close_utc_hours` が非空
- `bars` が複数 UTC date に跨る（既存 EOD 強制クローズ）

両方無効は「意図的ポリシー」として禁止。短時間単日 backtest も例外なく
イントラデイ強制クローズを担保する。

### `evaluate_genome` （`src/ga/fitness.py`、T009 復活）

```python
def evaluate_genome(
    genome: Genome,
    bars: list[PriceBar],
    meta: InstrumentMeta,
    backtest_config: BacktestConfig,
    primitive_evaluator: PrimitiveEvaluator,
    *,
    metric: FitnessMetric = "total_pnl",  # total_pnl / sharpe / calmar
    warmup_bars: int = 0,
    session_close_utc: time | None = None,
) -> Decimal: ...
```

- 例外発生時: `warning` ログ (`ga.fitness.system_failure`) + `_FAILURE_FITNESS` (-1e12)
- metric 不能時（sharpe None / calmar None）: `info` ログ (`ga.fitness.metric_unavailable`)
  + `_FAILURE_FITNESS`
- `total_pnl` は `Trade.pnl` 合計（holding cost 反映済み）を返す

### 4 段伝搬契約（Phase 2I で実配線予定）

本 TODO では `BacktestConfig` の新規フィールド宣言までを実装。`config/alpha_factory/
default.yaml` → `GaConfig` → `BacktestConfig` → `MockBroker` の 4 段伝搬は
`run-ga-full-rewrite` (Phase 2I) で実配線する。旧キー `swap_cost_per_day_bps` は
`holding_cost_per_day_bps` へ改名されており、Phase 2I の yaml loader で明示エラーまたは
互換読込ポリシーを決める必要がある。4 段すべての実配線テストを受け入れ条件に含める。

## SSOT 参照

| 項目 | 参照キーパス（config/alpha_factory/default.yaml） |
|------|--------------------------------------------------|
| max_depth | `ga.max_depth`（現行。Phase 2I で Clause 用 `ga.max_depth_per_clause` / `ga.max_clause` に再設計予定） |
| ペナルティ α | Phase 2I で `ga.complexity_penalty.alpha_stage_a` / `alpha_stage_bc` 追加予定（未定義） |
| ヒステリシス閾値 | Phase 2I で `ga.entry_threshold` / `exit_threshold` 追加予定（未定義） |

## 関連ドキュメント

- [stage-gates.md](stage-gates.md) — α ペナルティの Stage 別運用
- [swim-lane.md](swim-lane.md) — Tier / Lane との関係
- [primitives.md](primitives.md) — directional / modulator の候補
- [concepts/clause-genome-structure.md](concepts/clause-genome-structure.md)
- [concepts/clause-ga-operators.md](concepts/clause-ga-operators.md)
- [concepts/clause-backtest-integration.md](concepts/clause-backtest-integration.md)

## 関連 TODO

- **T007 (Closed)**: Clause ベース Genome 構造に再構築（本ドキュメントの実装関数シグネチャ節）
- **T008 (Closed)**: Clause-aware GA operators（crossover/mutate/random_gen/runner + complexity penalty）
- **T009 (Closed)**: backtest engine を Clause DslStrategy に対応 + spread/holding cost コスト反映 + fitness 復活
- 未着手: primitives-registry (T010), stage-gate-implementation (T011)
