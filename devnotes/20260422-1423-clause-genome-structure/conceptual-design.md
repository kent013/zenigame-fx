# Conceptual Design: Clause ベース Genome 構造

**作成日時**: 2026-04-22 14:23 (JST)
**TODO**: T007（予定）
**テーマ**: ga-architecture
**Priority**: Critical
**Mode**: standalone

## 1. 目的 / 仮説

### 目的

FX GA のゲノム表現を、現行のフラット 4 式（`entry_long` / `entry_short` / `exit_long` / `exit_short`）
から **Clause ベース合成構造**へ再構築する。zenigame 日本株 Alpha Factory の Clause 設計
（Jacobs et al. 1991, Jordan & Jacobs 1994 Mixture of Experts）を踏襲する。

### 根拠（確定済み）

- `devnotes/20260421-1850-fx-skill-port/debate-synthesis.md` — Claude × Codex 3 ラウンド議論の最終仕様
- `devnotes/20260421-1850-fx-skill-port/ga-architecture.md` 軸 1-(b) Clause / 軸 2-(i) per-instrument
- `docs/alpha_factory/clause-architecture.md`, `docs/alpha_factory/concepts/clause-genome-structure.md`

### 仮説

Clause 合成構造（directional × local_gate × weight）に **directional / local_gate の型分離**、
**directional の重み和正規化**、**composite のヒステリシス閾値**、**time_stop / session close** を
組み込むことで、`max_clause=1` でも **フラット 4 式と等価ではない**ゲノム空間が形成される
（Codex Round 3 Q12 の論点）。

### 成功判定

1. `Genome` 新 dataclass 群（`SignalConfig` / `ClauseConfig` / `PositionConfig` / `RiskConfig` / `Genome`）が
   frozen かつ互いに整合する
2. `compute_composite` が手計算と tolerance 1e-9 で一致
3. `DslStrategy.on_bar` が θ_on / θ_off の境界で正しく遷移する（保有→exit、無保有→entry）
4. `time_stop_min` と session close（UTC 指定時刻）で強制クローズが発火
5. `enforce_consistency` が Phase 2C の各段階（ランダム生成・交叉・変異・後処理）で pure に適用可能
6. `genome_to_dict` / `genome_from_dict` が round-trip で完全一致

## 2. 設計方針

### 2.1 既存のフラット式は **置き換える**（`_legacy` リネームしない）

理由:
- 後続 TODO で旧構造を復活させる計画が無い（debate-synthesis.md で確定）
- `_legacy` を残すと `src/ga/` / `src/backtest/` の両経路が並存し整合困難
- 旧 Genome に依存するテスト（`tests/ga/`, `tests/backtest/` の一部、`tests/dsl/test_dsl_strategy.py` 等）は
  本 TODO で **skip** マーク（後続 TODO `clause-ga-operators` / `clause-backtest-integration` で復旧）

### 2.2 5 つの必須構造要素

Codex 議論で確定した「Clause=1 でもフラット同値にならない」ための必須要素:

| # | 要素 | 反映先 |
|---|------|-------|
| 1 | directional signal と local_gate の型分離（categorical） | `ClauseConfig.directional` / `.local_gate` |
| 2 | directional の重み和正規化 `Σ w_i × x_i / Σ\|w_i\|` | `composite.compute_dir_score` |
| 3 | composite にヒステリシス閾値（θ_on > θ_off） | `PositionConfig.entry_threshold` / `.exit_threshold` |
| 4 | session close / time_stop を genome 内に持つ | `PositionConfig.time_stop_min` + DslStrategy 側 session close |
| 5 | spread フィルタを backtest 入力に組み込む（明示） | genome 外だが backtest engine への明示依存として記録（受け渡し契約: `PriceBar.spread_close` が必須、`BacktestConfig` に将来 `max_spread_bps` / `swap_cost_per_day` を追加予定。本 TODO では依存を明示するのみで実装は `clause-backtest-integration` に委譲） |

### 2.3 スコープ境界

**本 TODO が扱うもの**:
- `src/dsl/genome.py` — Genome dataclass 群の再構築
- `src/dsl/composite.py` — composite score 計算 pure function
- `src/dsl/strategy.py` — DslStrategy を独立モジュール化（PrimitiveEvaluator Protocol 抽象化）
- `src/dsl/enforce.py` — enforce_consistency pure function
- `src/dsl/serialize.py` — Clause 構造 round-trip
- `tests/dsl/` — 上記 4 モジュールの単体テスト

**本 TODO が扱わないもの（後続 TODO に委譲）**:
- `src/ga/operators.py` / `src/ga/random_gen.py` の Clause 対応 → `clause-ga-operators`
- `src/backtest/engine.py` の新 DslStrategy 統合 → `clause-backtest-integration`
- `PrimitiveRegistry` の実装 → `primitives-registry` / `primitives-directional-generic` / `primitives-modulator-generic`
- `src/dsl/samples.py` の Clause 対応サンプル → `clause-ga-operators` で実装（テスト fixture から最低限用意）

### 2.4 PrimitiveEvaluator の扱い

primitive の本実装は後続 TODO。本 TODO では `PrimitiveEvaluator` を **Protocol として定義**し、
テストでは `StubEvaluator`（`dict[str, float]` 直接返し）で境界条件を確認する。

```python
class PrimitiveEvaluator(Protocol):
    def evaluate(self, bars: list[PriceBar], idx: int, signal: SignalConfig) -> float: ...
```

## 3. データ構造

### 3.1 SignalConfig / ClauseConfig / PositionConfig / RiskConfig / Genome

```python
@dataclass(frozen=True)
class SignalConfig:
    name: str         # primitive ID (例: "F1", "M1")
    weight: float     # directional: [0.1, 2.0] / local_gate: [-2.0, 2.0]
    params: dict[str, float | int]  # primitive 固有

@dataclass(frozen=True)
class ClauseConfig:
    directional: tuple[SignalConfig, ...]  # TREND_FOLLOW / MEAN_REVERT / NEUTRAL
    local_gate: tuple[SignalConfig, ...]   # MODULATOR
    weight: float    # clause_weight

@dataclass(frozen=True)
class PositionConfig:
    entry_threshold: float   # θ_on
    exit_threshold: float    # θ_off（entry > exit、違反時 enforce で swap）
    max_pos: int
    time_stop_min: int       # 0 = 無効

@dataclass(frozen=True)
class RiskConfig:
    stop_atr: float
    take_atr: float

@dataclass(frozen=True)
class Genome:
    name: str
    units: int
    clauses: tuple[ClauseConfig, ...]  # 1-3 clause
    position: PositionConfig
    risk: RiskConfig
```

`params: dict` は frozen dataclass 内の可変フィールドになるため、
dict を mutable のまま保持する（hashability は必要なし、比較も不要）。
テストでは `dataclasses.replace` でコピーを作る運用を前提。

### 3.2 composite.py

```python
def compute_dir_score(signals, values) -> float:
    """Σ(w_i × x_i) / Σ|w_i|"""

def compute_gate(signals, values) -> float:
    """Π gate_fn(gate_j) — 本 TODO では primitive 側で sigmoid 済み [0,1] 前提"""

def compute_composite(clauses, values_per_clause) -> float:
    """Σ(cw_k × (dir_k × gate_k)) / Σ|cw_k|"""
```

境界条件:
- `Σ|w_i| = 0` → 0.0 を返す（NaN 抑止）
- `signals = []` → dir_score は 0.0、gate は 1.0（空積）

### 3.3 strategy.py

ヒステリシス遷移の状態マシン:

| 保有状態 | composite 条件 | アクション |
|----------|----------------|-----------|
| なし | `composite >= θ_on` | `open_long` |
| なし | `-composite >= θ_on` | `open_short` |
| long | `composite < θ_off` | `close_position` |
| short | `-composite < θ_off` | `close_position` |
| long / short | 保有時間 >= `time_stop_min` | `close_position`（time_stop） |
| long / short | bar_time が session close 時刻 | `close_position`（session_close） |

session close は `DslStrategy` 引数 `session_close_utc: time | None` で受け取る。
本 TODO では `None` なら無効として扱う（後続 TODO で FX 主要セッション close を default 化）。

**イントラデイ絶対制約の不変条件（必須）**:
`session_close_utc is not None` **または** backtest engine 側の EOD 強制クローズ
（`src/backtest/engine.py` が `is_eod → close_all(reason="eod")` で実装済み）のどちらかが
必ず有効であること。両方 None/無効の設計は禁止する。
本 TODO では後者に依存し、DslStrategy 側 session_close は Phase 3 で常時有効化する。

### 3.4 enforce.py

```python
def enforce_consistency(genome: Genome) -> Genome:
    # Clause ごと:
    #   - directional の weight: abs + clip [0.1, 2.0]（0 未満は abs、上下 clip）
    #   - modulator の weight: clip [-2.0, 2.0]（符号は維持）
    #   - 同一 name の signal 排除（directional と local_gate それぞれで dedupe、後勝ち）
    #   - local_gate は最大 1 つ（超えた場合、|weight| 最大のみ残す）
    #   - directional が空になった場合: その Clause を除去（ダミー挿入はしない）
    #     ※ 全 Clause が directional 空になった場合は ValueError（ランダム生成の前提違反として
    #        explicit に失敗させる。GA operators は enforce 前に最低 1 つの directional を
    #        確保する責務を持つ。本 TODO では境界条件としてテストのみ）
    # Position:
    #   - entry_threshold > exit_threshold（違反時 swap）
    #   - max_pos >= 1
    #   - time_stop_min >= 0
    # Risk:
    #   - stop_atr > 0, take_atr > 0
    # Clause 全体:
    #   - 1 <= len(clauses) <= 3（len > 3 は |weight| 最大の 3 つを残す、len = 0 は ValueError）
```

`enforce_consistency` は pure function として実装し、GA の random_gen / crossover / mutate の直後に
呼ぶ運用を想定（後続 TODO で組み込む）。本 TODO ではテストで境界値のみ確認。

### 3.5 serialize.py

新構造に合わせて `genome_to_dict` / `genome_from_dict` を書き換える。

```json
{
  "name": "g0_i0",
  "units": 10000,
  "clauses": [
    {
      "directional": [{"name": "F1", "weight": 1.0, "params": {"fast": 8, "slow": 21}}],
      "local_gate":  [{"name": "M1", "weight": 0.5, "params": {"pct": 0.7}}],
      "weight": 1.0
    }
  ],
  "position": {
    "entry_threshold": 0.3, "exit_threshold": 0.1,
    "max_pos": 1, "time_stop_min": 240
  },
  "risk": {"stop_atr": 2.0, "take_atr": 3.0}
}
```

旧 Expr ツリー前提の `expr_to_dict` / `expr_from_dict` は残す（`src/dsl/ast.py` は後続 TODO まで保持）。
ただし `genome_to_dict` / `genome_from_dict` は新構造のみサポート。

## 4. テスト設計

| ファイル | テスト範囲 |
|---------|-----------|
| `tests/dsl/test_genome_clause.py` | dataclass frozen / 不正入力の型エラー / round-trip |
| `tests/dsl/test_composite.py` | dir_score 手計算（正規化）、gate 空積、composite 複数 clause、denom=0 |
| `tests/dsl/test_strategy.py` | θ_on 境界（`composite == θ_on`）/ θ_off 境界 / time_stop / session close / short 対称 |
| `tests/dsl/test_enforce.py` | weight clip / directional 空 / dup name / θ_on ≤ θ_off / clause 数違反 |

tolerance: `compute_composite` は float 演算なので `math.isclose(..., abs_tol=1e-9)` を使う。

## 5. 既存コードへの影響

| 影響先 | 本 TODO での扱い |
|-------|----------------|
| `src/dsl/samples.py` | 旧 Genome 前提なので内容を削除またはコメントアウト（後続で Clause 版を追加） |
| `src/dsl/__init__.py` | export を新構造に更新、旧 samples は削除 |
| `src/ga/fitness.py` / `operators.py` / `random_gen.py` / `runner.py` | 旧 Genome 前提なので **skip マーク**（後続 `clause-ga-operators`） |
| `src/backtest/engine.py` | 旧 `DslStrategy` に依存しないので無修正（Strategy Protocol 準拠） |
| `tests/ga/*` | 旧 GA 前提なので一時 `pytest.skip(reason="awaiting clause-ga-operators TODO")` |
| `tests/backtest/*` | `src/dsl/samples.py` 経由で旧 Genome を使っているものは同様に skip |
| `tests/dsl/test_dsl_strategy.py` / `test_serialize.py` / `test_eval.py` / `test_nested_lookback.py` / `test_warmup_boundary.py` | 旧 Expr / 旧 DslStrategy 前提。`test_eval.py` / `test_nested_lookback.py` は Expr 本体のテストなので温存（`ast.py` / `eval.py` は本 TODO で削除しない）、`test_dsl_strategy.py` / `test_serialize.py` / `test_warmup_boundary.py` は本 TODO で新構造に書き換えるか skip |

### 5.1 Expr AST の扱い

`src/dsl/ast.py` / `src/dsl/eval.py` は本 TODO では **削除しない**。
- 理由 1: primitive 実装時に indicator 演算（SMA / EMA / RSI）を再利用する可能性が高い
- 理由 2: 削除すると tests/dsl の広範囲が一気に壊れる
- 後続 TODO `primitives-*` で再利用される前提

## 6. マイグレーション方針

旧構造で作られた archive ファイル（存在すれば）の変換は **不要**（FX GA はまだ本格稼働前の段階）。
新 GA 開始時点で新構造のみサポート。

## 7. 学術引用

- Jacobs, R. A., Jordan, M. I., Nowlan, S. J., & Hinton, G. E. (1991). Adaptive mixtures of local experts. Neural Computation, 3(1), 79–87.
- Jordan, M. I., & Jacobs, R. A. (1994). Hierarchical mixtures of experts and the EM algorithm. Neural Computation, 6(2), 181–214.
- Koza, J. R. (1992). Genetic Programming: On the Programming of Computers by Means of Natural Selection. MIT Press.

## 8. オープンクエスチョン

1. **session close 時刻の default**: FX 週末クローズ（金 21:00 UTC）だけ genome 固定、日次 EOD は既存の backtest engine 側に残すか? → 本 TODO では DslStrategy 引数で受け取り、default は None
2. **params: dict の型安定性**: `dict[str, float | int]` は mypy 視点で緩い。本 TODO ではそのまま、後続の primitive-registry で primitive ごとに typed dataclass に格上げする計画
3. **`gate` の [0, 1] 保証**: 本 TODO では primitive 側で sigmoid 済み前提。後続で compute_gate 内でも clip するか検討

## 9. 依存関係

本 TODO 完了後に着手可能になる後続 TODO:
- `clause-ga-operators`: Clause 対応の crossover / mutate / random_gen
- `clause-backtest-integration`: backtest engine と新 DslStrategy の統合（PrimitiveEvaluator を実装版に差し替え）
- `primitives-registry` → `primitives-directional-generic` / `primitives-modulator-generic` / `primitives-pair-specific`
