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

## spread / swap 受け渡し契約 (後続 clause-backtest-integration TODO)

```python
@dataclass(frozen=True)
class BacktestConfig:  # 既存 + 追加予定フィールド
    instrument: str
    start: datetime
    end: datetime
    initial_cash: Decimal
    leverage: int
    # 以下は clause-backtest-integration TODO で追加
    # max_spread_bps: Decimal | None = None
    # swap_cost_per_day_bps: Decimal = Decimal(0)
```

- 単位: 両方 bps（basis point、1/10000）
- 適用時点:
  - `max_spread_bps`: `MockBroker.submit` 時点で spread_bps 計算、超過なら reject（約定前フィルタ）
  - `swap_cost_per_day_bps`: `mark_to_market` ごとに日次按分で equity 控除（fitness 反映）
- 4 段伝搬: `config/alpha_factory/default.yaml` → `GaConfig` → `BacktestConfig` → `MockBroker`

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
- 未着手: clause-ga-operators, clause-backtest-integration, primitives-registry
