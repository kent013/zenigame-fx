# Detailed Design: Clause ベース Genome 構造 (T007)

**作成日時**: 2026-04-22 14:35 (JST)
**概念設計**: `conceptual-design.md`（APPROVED_WITH_COMMENTS, Round 2）
**TODO**: T007

## 0. 設計目標の明確化（Round 2 レビュー反映）

### 0.1 「max_clause=1 でもフラット式と非等価」の正確な意味

Codex Round 2 falsification で `max_clause=1` + 1 directional + 空 gate + clause.weight=1 の構成が
`composite = dir_score` と還元可能であることが指摘された。これは正しい。

本設計の目標は **「composite スカラー式が数学的にフラット式と異なる」** ことではなく、
**「ゲノム空間全体としての戦略挙動がフラット 4 式と非等価である」** こと。具体的には:

- 旧フラット 4 式: `entry_long` / `entry_short` / `exit_long` / `exit_short` は独立した bool 式。
  exit が「別の bool ルール」であり、entry と exit の論理関係が独立。
- 新 Clause 構造: `composite` 1 本の連続スカラーで判定、ヒステリシス（θ_on > θ_off）で
  entry と exit が **同じ内部状態から派生**。さらに time_stop / session close は genome レベルで
  必ず存在する。

したがって `max_clause=1` + 単純構成でも以下の構造的差分が残る:

| 要素 | 旧フラット | 新 Clause（max_clause=1） |
|------|----------|--------------------------|
| 判定式 | 4 個（bool） | 1 個（float → 閾値） |
| entry / exit の連関 | 独立 bool | composite 共有 + ヒステリシス |
| time_stop | なし | 必ず持つ（0 なら無効、非 0 なら強制クローズ） |
| session close | 実装依存 | DslStrategy 引数 or engine EOD |

この「挙動面での非等価」は保証される。数学的 composite 式の reduction を禁止する意図ではない。
**本設計では max_clause=1 を禁止しない**（Phase 2 MVP の段階解放計画通り）。

### 0.2 残すべき制約（新規追加）

- `enforce_consistency` で **非有限値 (NaN/inf)** を検出した場合 `ValueError` で明示 raise
  （clip ではない: 下流の composite で NaN 伝搬するのを防ぐ）
- `entry_threshold` / `exit_threshold` は正値に強制しない（0 や負値は合法、ただし NaN/inf は禁止）
  - 理由: 実戦略では `entry_threshold=0.1, exit_threshold=0` のような設計もあり得る
- `params` は `SignalConfig` 生成時に **defensive copy** する（shared reference 混入を構造的に遮断）

### 0.3 spread / swap 受け渡し契約（詳細化）

本 TODO のスコープは I/F 宣言まで。実装は `clause-backtest-integration`。

```python
@dataclass(frozen=True)
class BacktestConfig:  # 既存
    instrument: str
    start: datetime
    end: datetime
    initial_cash: Decimal
    leverage: int
    # ↓ clause-backtest-integration で追加予定（本 TODO では宣言のみ）
    # max_spread_bps: Decimal | None = None      # 約定前フィルタ（None で無効）
    # swap_cost_per_day_bps: Decimal = Decimal(0)  # fitness 控除用日次コスト（bps）
```

契約:
- **単位**: 両方 bps（basis point、1/10000）
- **適用時点**:
  - `max_spread_bps`: `MockBroker.submit` 時点で spread_bps を計算、超過なら reject（約定前フィルタ）
  - `swap_cost_per_day_bps`: `mark_to_market` ごとに日次按分で equity 控除（fitness 反映）
- **欠落時挙動**: 本 TODO 時点では未設定 = 無効。`clause-backtest-integration` で **必須化**
  し、default を設定する前に live_criteria 整合性チェック付きでバリデーション
- **4 段伝搬契約**（config → GaConfig → meta → consumer）:
  1. `config/alpha_factory/default.yaml` — `backtest.max_spread_bps` / `backtest.swap_cost_per_day_bps`
  2. `GaConfig` dataclass — 同名フィールド
  3. `BacktestConfig` に渡される
  4. `MockBroker.submit` / `mark_to_market` で参照

上記 4 段は `clause-backtest-integration` TODO で **値伝搬漏れ禁止事項** として再確認。

## 1. モジュール一覧

| Path | 新規/更新/削除 | 行数目安 |
|------|---------------|---------|
| `src/dsl/genome.py` | 置き換え（旧フラット Genome → Clause 構造） | ~90 |
| `src/dsl/composite.py` | **新規** | ~60 |
| `src/dsl/strategy.py` | **新規**（DslStrategy を独立モジュール化） | ~130 |
| `src/dsl/enforce.py` | **新規** | ~110 |
| `src/dsl/serialize.py` | 更新（genome_to_dict/from_dict を Clause 対応） | ~90 |
| `src/dsl/samples.py` | **削除**（旧 Genome 前提） |  |
| `src/dsl/__init__.py` | 更新（export 刷新） | ~15 |
| `src/dsl/ast.py` | **変更なし**（primitive 実装で再利用） |  |
| `src/dsl/eval.py` | **変更なし**（primitive 実装で再利用） |  |
| `tests/dsl/test_genome_clause.py` | **新規** | ~110 |
| `tests/dsl/test_composite.py` | **新規** | ~120 |
| `tests/dsl/test_strategy.py` | **新規** | ~200 |
| `tests/dsl/test_enforce.py` | **新規** | ~160 |
| `tests/dsl/test_dsl_strategy.py` | 全 skip（後続 TODO） | |
| `tests/dsl/test_serialize.py` | 全 skip（後続 TODO） | |
| `tests/dsl/test_warmup_boundary.py` | 全 skip（後続 TODO） | |
| `tests/dsl/test_eval.py` | **変更なし** |  |
| `tests/dsl/test_nested_lookback.py` | **変更なし** |  |
| `tests/ga/test_operators.py` | 全 skip | |
| `tests/ga/test_random_gen.py` | 全 skip | |
| `tests/ga/test_runner.py` | 全 skip | |
| `src/ga/fitness.py` / `operators.py` / `random_gen.py` / `runner.py` | **本 TODO では変更しない**（import 先が無くなりインポート時エラーになるため、ファイル冒頭で `pytest.importorskip`相当の退避ではなく、旧 Genome 参照箇所を実装レベルで破壊しないよう以下対応） | |

### 1.1 `src/ga/` の取り扱い（重要）

`src/ga/` は旧 Genome（フラット 4 式）に強く依存している。完全な Clause 対応は後続 TODO
`clause-ga-operators` のスコープ。

本 TODO では:

- **`src/ga/` のコード本体は変更しない**（変更すると本 TODO のスコープが膨らむ）
- ただし `from src.dsl.genome import Genome` が新 Genome（Clause 版）を import するため、
  `src/ga/operators.py` / `random_gen.py` / `runner.py` / `fitness.py` は **import 時点で構造不整合**
  になる（attribute `.entry_long` 等が無い新 Genome を使おうとする）
- **解決方針**: `src/ga/` の import 自体は成功させる（Genome クラス名は維持されるため）が、
  `test_ga/` の test 関数全体に `@pytest.mark.skip(reason="T007 placeholder: awaiting clause-ga-operators")` を付与
  → 後続 TODO `clause-ga-operators` で `src/ga/*.py` を書き換えて skip を解除

`tests/backtest/*` は `src/dsl/samples.py` 経由の旧 Genome に依存しているものがあるため、
該当テストのみ skip する（全体 skip ではなくファイル単位で精査）。

## 2. `src/dsl/genome.py` 詳細

```python
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class SignalConfig:
    """単一 primitive の呼び出し定義。

    Attributes:
        name: primitive ID（例: "F1", "M1"）。後続 TODO で PrimitiveRegistry 登録値と一致必須。
        weight: directional の場合 [0.1, 2.0] の正、local_gate の場合 [-2.0, 2.0]。
        params: primitive 固有パラメータ（fast/slow 窓、閾値など）。
                生成時に defensive copy される（shared reference 遮断）。
    """

    name: str
    weight: float
    params: dict[str, float | int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # frozen dataclass でも object.__setattr__ で内部書き換え可能。
        # 外部 dict と reference を共有しないよう dict(...) でコピー。
        object.__setattr__(self, "params", dict(self.params))


@dataclass(frozen=True)
class ClauseConfig:
    """1 clause = directional 群 × local_gate 群 × clause weight."""

    directional: tuple[SignalConfig, ...]
    local_gate: tuple[SignalConfig, ...]
    weight: float


@dataclass(frozen=True)
class PositionConfig:
    """ポジション開閉パラメータ。

    entry_threshold > exit_threshold（ヒステリシス必須、enforce_consistency で保証）。
    """

    entry_threshold: float
    exit_threshold: float
    max_pos: int
    time_stop_min: int  # 0 は無効


@dataclass(frozen=True)
class RiskConfig:
    """リスク管理パラメータ（ATR 係数）。"""

    stop_atr: float
    take_atr: float


@dataclass(frozen=True)
class Genome:
    """Clause ベース合成ゲノム。

    1 ゲノム = 1 通貨ペア用の signal generator。Clause を 1-3 個持ち、
    composite score 化してヒステリシス判定で発注する。
    """

    name: str
    units: int
    clauses: tuple[ClauseConfig, ...]
    position: PositionConfig
    risk: RiskConfig
```

### 2.1 `params` の可変性とハッシュ

`params: dict[...]` は mutable のため、`@dataclass(frozen=True)` でも dict 自体の変更は防げない。
しかし frozen によって `signal.params = {...}` のような再代入は防止される。
`__hash__` は自動生成されるが dict を含むため呼ぶと `TypeError` になる想定。
GA では `Genome` を `dict` の key に使わないため問題なし。
テストでは `replace(signal, params=new_dict)` でコピーを作る運用を徹底。

### 2.2 `field(default_factory=dict)` について

`SignalConfig(name="F1", weight=1.0)` のように params 省略を許容するため default を `dict` にする。
frozen dataclass + `default_factory` は Python 3.10+ で問題なく動く。

## 3. `src/dsl/composite.py` 詳細

```python
from __future__ import annotations

import math
from collections.abc import Mapping, Sequence

from src.dsl.genome import ClauseConfig, SignalConfig


def compute_dir_score(
    signals: Sequence[SignalConfig], values: Mapping[str, float]
) -> float:
    """directional 加重和の正規化: Σ(w_i × x_i) / Σ|w_i|。

    Args:
        signals: directional signal 群（空は 0.0 を返す）。
        values: signal name → primitive 評価値。本 TODO では tanh 等で [-1, 1] 範囲想定。

    Returns:
        正規化された方向性スコア。Σ|w_i| が 0 の場合は 0.0。
    """
    if not signals:
        return 0.0
    num = 0.0
    denom = 0.0
    for sig in signals:
        num += sig.weight * values[sig.name]
        denom += abs(sig.weight)
    if denom == 0.0:
        return 0.0
    return num / denom


def compute_gate(
    signals: Sequence[SignalConfig], values: Mapping[str, float]
) -> float:
    """local_gate の積: Π gate_fn(gate_j)。

    本 TODO では primitive 側で sigmoid 済み [0, 1] 前提（pre-bounded）。
    signals が空の場合は 1.0 を返す（no-gate = pass-through）。

    Args:
        signals: local_gate signal 群。
        values: signal name → [0, 1] 範囲の gate 値。

    Returns:
        gate 積（[0, 1] 範囲）。
    """
    g = 1.0
    for sig in signals:
        g *= values[sig.name]
    return g


def compute_clause_score(
    clause: ClauseConfig, values: Mapping[str, float]
) -> float:
    """単一 clause の合成: dir_score × gate。"""
    dir_s = compute_dir_score(clause.directional, values)
    gate = compute_gate(clause.local_gate, values)
    return dir_s * gate


def compute_composite(
    clauses: Sequence[ClauseConfig],
    values_per_clause: Sequence[Mapping[str, float]],
) -> float:
    """複数 clause の加重合成: Σ(cw_k × cs_k) / Σ|cw_k|。

    Args:
        clauses: 1-3 個の clause。
        values_per_clause: 各 clause の primitive 評価値辞書。len は clauses と一致必須。

    Returns:
        composite score。Σ|cw_k| が 0 の場合は 0.0。

    Raises:
        ValueError: clauses と values_per_clause の長さ不一致、または空。
    """
    if len(clauses) != len(values_per_clause):
        raise ValueError(
            f"clauses len={len(clauses)} != values_per_clause len={len(values_per_clause)}"
        )
    if not clauses:
        raise ValueError("clauses must not be empty")
    num = 0.0
    denom = 0.0
    for clause, values in zip(clauses, values_per_clause, strict=True):
        cs = compute_clause_score(clause, values)
        num += clause.weight * cs
        denom += abs(clause.weight)
    if denom == 0.0:
        return 0.0
    return num / denom


def is_close(a: float, b: float, *, abs_tol: float = 1e-9) -> bool:
    """テスト用 helper: math.isclose の tolerance wrapper."""
    return math.isclose(a, b, abs_tol=abs_tol)
```

### 3.1 `values` の型選択

`Mapping[str, float]` にする。本 TODO の境界: primitive 評価値は float スカラーのみ。
後続 TODO で Decimal への置き換えを検討するが、composite 計算が float 演算で閉じるなら
tolerance 1e-9 で十分（zenigame の実装も float）。

## 4. `src/dsl/strategy.py` 詳細

```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta
from typing import Protocol

from src.broker.orders import OrderSignal, PortfolioSnapshot
from src.domain.price import PriceBar
from src.dsl.composite import compute_composite
from src.dsl.genome import Genome, SignalConfig


class PrimitiveEvaluator(Protocol):
    """primitive 評価関数の抽象。後続 TODO `primitives-registry` で実装される。

    Implementations must be stateless across bars (or manage their own cache).
    """

    def evaluate(
        self, bars: list[PriceBar], idx: int, signal: SignalConfig
    ) -> float:
        """bars[idx] 時点での signal の評価値を返す。

        Returns:
            float（directional は符号付き、local_gate は [0, 1] の想定）。
        """
        ...


@dataclass
class _OpenPosition:
    """DslStrategy 内部で保持するポジション状態（entry_time 追跡のみ）。"""

    position_id: int
    side: str  # "long" | "short"
    entry_time: datetime


class DslStrategy:
    """Clause ベース Genome を評価する Strategy。

    ヒステリシス:
        - 無保有: composite >= θ_on → long エントリー、-composite >= θ_on → short
        - long: composite < θ_off → close
        - short: -composite < θ_off → close
    time_stop:
        - 保有時間 >= time_stop_min 分 → 強制クローズ
    session close:
        - session_close_utc != None かつ bar.bar_time.time() >= session_close_utc → 強制クローズ

    Note:
        session_close_utc=None の場合、イントラデイ強制クローズは backtest engine 側の
        EOD 機能に依存する（conceptual-design.md §3.3 参照）。
    """

    def __init__(
        self,
        genome: Genome,
        evaluator: PrimitiveEvaluator,
        *,
        warmup_bars: int = 0,
        session_close_utc: time | None = None,
    ) -> None:
        self._genome = genome
        self._evaluator = evaluator
        self._warmup = warmup_bars
        self._session_close = session_close_utc
        self._bars: list[PriceBar] = []
        self._open_pos: _OpenPosition | None = None

    @property
    def genome(self) -> Genome:
        return self._genome

    def warmup_bars(self) -> int:
        return self._warmup

    def on_bar(
        self, bar: PriceBar, snapshot: PortfolioSnapshot
    ) -> list[OrderSignal]:
        self._bars.append(bar)
        if len(self._bars) < self._warmup:
            return []
        idx = len(self._bars) - 1

        # 保有状態を snapshot から同期（engine が force close した場合の追従）
        if not snapshot.positions:
            self._open_pos = None
        elif self._open_pos is None and snapshot.positions:
            p = snapshot.positions[0]
            self._open_pos = _OpenPosition(p.id, p.side, p.entry_time)

        # composite 評価
        values_per_clause: list[dict[str, float]] = []
        for clause in self._genome.clauses:
            vals: dict[str, float] = {}
            for sig in clause.directional:
                vals[sig.name] = self._evaluator.evaluate(self._bars, idx, sig)
            for sig in clause.local_gate:
                vals[sig.name] = self._evaluator.evaluate(self._bars, idx, sig)
            values_per_clause.append(vals)
        composite = compute_composite(self._genome.clauses, values_per_clause)

        pos_cfg = self._genome.position

        # 保有あり: exit 判定優先
        if snapshot.positions:
            pos = snapshot.positions[0]
            # session close
            if (
                self._session_close is not None
                and bar.bar_time.time() >= self._session_close
            ):
                return [OrderSignal(kind="close_position", position_id=pos.id)]
            # time stop
            if pos_cfg.time_stop_min > 0:
                elapsed = bar.bar_time - pos.entry_time
                if elapsed >= timedelta(minutes=pos_cfg.time_stop_min):
                    return [OrderSignal(kind="close_position", position_id=pos.id)]
            # hysteresis exit
            if pos.side == "long" and composite < pos_cfg.exit_threshold:
                return [OrderSignal(kind="close_position", position_id=pos.id)]
            if pos.side == "short" and -composite < pos_cfg.exit_threshold:
                return [OrderSignal(kind="close_position", position_id=pos.id)]
            return []

        # 無保有: entry 判定
        if composite >= pos_cfg.entry_threshold:
            return [OrderSignal(kind="open_long", units=self._genome.units)]
        if -composite >= pos_cfg.entry_threshold:
            return [OrderSignal(kind="open_short", units=self._genome.units)]
        return []
```

### 4.1 `warmup_bars` について

primitive ごとに必要な lookback が異なるため、正確な warmup は
`PrimitiveEvaluator.warmup_bars(signal)` を追加実装すべきだが、本 TODO では簡略化し
DslStrategy コンストラクタ引数で明示的に受け取る。後続 TODO で Registry が確定した時に
`sum(max(...) for clause in clauses)` 的に自動算出する。

### 4.2 entry/exit の境界条件

- `composite == θ_on`: 境界 **含む**（`>=`）→ エントリー
- `composite == θ_off`: 境界 **含む**（`<` なので含まない）→ exit しない
- `short` 側は `-composite >= θ_on` で対称

## 5. `src/dsl/enforce.py` 詳細

```python
from __future__ import annotations

import math
from dataclasses import replace

from src.dsl.genome import ClauseConfig, Genome, PositionConfig, SignalConfig

_DIR_WEIGHT_MIN = 0.1
_DIR_WEIGHT_MAX = 2.0
_GATE_WEIGHT_MIN = -2.0
_GATE_WEIGHT_MAX = 2.0
_MAX_CLAUSES = 3


def _clip(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def _check_finite(value: float, field_name: str) -> float:
    """NaN / inf を検出して ValueError。clip 前に呼ぶ。"""
    if not math.isfinite(value):
        raise ValueError(f"enforce_consistency: non-finite value in {field_name}: {value!r}")
    return value


def _enforce_directional(signals: tuple[SignalConfig, ...]) -> tuple[SignalConfig, ...]:
    """directional: abs + clip [0.1, 2.0]、同一 name は後勝ちで dedupe。非有限値は raise."""
    seen: dict[str, SignalConfig] = {}
    for sig in signals:
        _check_finite(sig.weight, f"SignalConfig({sig.name}).weight")
        w = _clip(abs(sig.weight), _DIR_WEIGHT_MIN, _DIR_WEIGHT_MAX)
        seen[sig.name] = replace(sig, weight=w)
    return tuple(seen.values())


def _enforce_gate(signals: tuple[SignalConfig, ...]) -> tuple[SignalConfig, ...]:
    """local_gate: clip [-2.0, 2.0]、同一 name 後勝ち dedupe、最大 1 本（|weight| 最大）。非有限値は raise."""
    seen: dict[str, SignalConfig] = {}
    for sig in signals:
        _check_finite(sig.weight, f"SignalConfig({sig.name}).weight")
        w = _clip(sig.weight, _GATE_WEIGHT_MIN, _GATE_WEIGHT_MAX)
        seen[sig.name] = replace(sig, weight=w)
    if len(seen) <= 1:
        return tuple(seen.values())
    # 最大 |weight| 1 本のみ残す
    best = max(seen.values(), key=lambda s: abs(s.weight))
    return (best,)


def _enforce_clause(clause: ClauseConfig) -> ClauseConfig | None:
    """directional が空になった場合は None を返し、呼び出し側で除去する。非有限値は raise."""
    _check_finite(clause.weight, "ClauseConfig.weight")
    dirs = _enforce_directional(clause.directional)
    if not dirs:
        return None
    gates = _enforce_gate(clause.local_gate)
    return ClauseConfig(directional=dirs, local_gate=gates, weight=clause.weight)


def _enforce_position(pos: PositionConfig) -> PositionConfig:
    _check_finite(pos.entry_threshold, "PositionConfig.entry_threshold")
    _check_finite(pos.exit_threshold, "PositionConfig.exit_threshold")
    entry = pos.entry_threshold
    exit_ = pos.exit_threshold
    if entry <= exit_:
        # swap（entry の方が大きいのが正しい状態）
        entry, exit_ = exit_, entry
        if entry == exit_:
            # 厳密に > にするため epsilon 分離（exit を下げる）
            exit_ = entry - 1e-6
    return replace(
        pos,
        entry_threshold=entry,
        exit_threshold=exit_,
        max_pos=max(1, pos.max_pos),
        time_stop_min=max(0, pos.time_stop_min),
    )


def enforce_consistency(genome: Genome) -> Genome:
    """Genome 全体に整合性ルールを適用する pure function。

    Raises:
        ValueError: 全 Clause が directional 空、または clauses が空。
    """
    new_clauses: list[ClauseConfig] = []
    for c in genome.clauses:
        fixed = _enforce_clause(c)
        if fixed is not None:
            new_clauses.append(fixed)
    if not new_clauses:
        raise ValueError(
            "enforce_consistency: all clauses lost their directional signals"
        )
    # clause 数上限
    if len(new_clauses) > _MAX_CLAUSES:
        new_clauses.sort(key=lambda c: abs(c.weight), reverse=True)
        new_clauses = new_clauses[:_MAX_CLAUSES]
    new_position = _enforce_position(genome.position)
    _check_finite(genome.risk.stop_atr, "RiskConfig.stop_atr")
    _check_finite(genome.risk.take_atr, "RiskConfig.take_atr")
    new_risk = replace(
        genome.risk,
        stop_atr=max(1e-6, genome.risk.stop_atr),
        take_atr=max(1e-6, genome.risk.take_atr),
    )
    return replace(
        genome,
        clauses=tuple(new_clauses),
        position=new_position,
        risk=new_risk,
    )
```

### 5.1 weight の符号（directional）

directional は符号反転ではなく **絶対値** を取る（Codex 議論で「directional は正のみ」と確定）。
符号による long/short 表現は primitive 値側（tanh 出力の符号）で担う設計。

### 5.2 local_gate の 0 許容

`weight=0` の gate は「clause 内に存在するが効かない」を意味するが、
本 TODO の compute_gate は符号を持たない積なので、0 を入れると clause_score が 0 に潰れる。
これは意図的な「この clause を無効化」シグナルとして解釈可能なため、enforce では 0 を許容する。

## 6. `src/dsl/serialize.py` 詳細

```python
from __future__ import annotations

from typing import Any

from src.dsl.genome import ClauseConfig, Genome, PositionConfig, RiskConfig, SignalConfig


def signal_to_dict(sig: SignalConfig) -> dict[str, Any]:
    return {"name": sig.name, "weight": sig.weight, "params": dict(sig.params)}


def signal_from_dict(d: dict[str, Any]) -> SignalConfig:
    return SignalConfig(
        name=str(d["name"]),
        weight=float(d["weight"]),
        params=dict(d.get("params", {})),
    )


def clause_to_dict(c: ClauseConfig) -> dict[str, Any]:
    return {
        "directional": [signal_to_dict(s) for s in c.directional],
        "local_gate": [signal_to_dict(s) for s in c.local_gate],
        "weight": c.weight,
    }


def clause_from_dict(d: dict[str, Any]) -> ClauseConfig:
    return ClauseConfig(
        directional=tuple(signal_from_dict(s) for s in d["directional"]),
        local_gate=tuple(signal_from_dict(s) for s in d["local_gate"]),
        weight=float(d["weight"]),
    )


def position_to_dict(p: PositionConfig) -> dict[str, Any]:
    return {
        "entry_threshold": p.entry_threshold,
        "exit_threshold": p.exit_threshold,
        "max_pos": p.max_pos,
        "time_stop_min": p.time_stop_min,
    }


def position_from_dict(d: dict[str, Any]) -> PositionConfig:
    return PositionConfig(
        entry_threshold=float(d["entry_threshold"]),
        exit_threshold=float(d["exit_threshold"]),
        max_pos=int(d["max_pos"]),
        time_stop_min=int(d["time_stop_min"]),
    )


def risk_to_dict(r: RiskConfig) -> dict[str, Any]:
    return {"stop_atr": r.stop_atr, "take_atr": r.take_atr}


def risk_from_dict(d: dict[str, Any]) -> RiskConfig:
    return RiskConfig(stop_atr=float(d["stop_atr"]), take_atr=float(d["take_atr"]))


def genome_to_dict(g: Genome) -> dict[str, Any]:
    return {
        "name": g.name,
        "units": g.units,
        "clauses": [clause_to_dict(c) for c in g.clauses],
        "position": position_to_dict(g.position),
        "risk": risk_to_dict(g.risk),
    }


def genome_from_dict(d: dict[str, Any]) -> Genome:
    return Genome(
        name=str(d["name"]),
        units=int(d["units"]),
        clauses=tuple(clause_from_dict(c) for c in d["clauses"]),
        position=position_from_dict(d["position"]),
        risk=risk_from_dict(d["risk"]),
    )
```

### 6.1 旧 Expr serialize の扱い

本 TODO では `expr_to_dict` / `expr_from_dict` は `src/dsl/serialize.py` から **削除**
（ast.py / eval.py 自体は残すが、シリアライズは新構造のみ）。
後続 TODO で primitive 側に Expr 依存が出た場合、その際に再導入を検討。

## 7. `src/dsl/__init__.py`

```python
"""DSL package — Clause ベース Genome 構造。"""

from src.dsl.composite import (
    compute_clause_score,
    compute_composite,
    compute_dir_score,
    compute_gate,
)
from src.dsl.enforce import enforce_consistency
from src.dsl.genome import (
    ClauseConfig,
    Genome,
    PositionConfig,
    RiskConfig,
    SignalConfig,
)
from src.dsl.serialize import genome_from_dict, genome_to_dict
from src.dsl.strategy import DslStrategy, PrimitiveEvaluator

__all__ = [
    "ClauseConfig",
    "DslStrategy",
    "Genome",
    "PositionConfig",
    "PrimitiveEvaluator",
    "RiskConfig",
    "SignalConfig",
    "compute_clause_score",
    "compute_composite",
    "compute_dir_score",
    "compute_gate",
    "enforce_consistency",
    "genome_from_dict",
    "genome_to_dict",
]
```

## 8. テスト設計詳細

### 8.1 `tests/dsl/test_genome_clause.py`

- `test_signal_config_frozen` — `replace` 以外でフィールド変更できないこと
- `test_signal_config_default_params` — `params` 省略時空 dict
- `test_clause_config_tuple_signals` — directional / local_gate が tuple（不変）
- `test_genome_minimal_construct` — 1 clause / 1 directional で構築できること
- `test_genome_three_clauses` — 3 clause まで構築可

### 8.2 `tests/dsl/test_composite.py`

Stub 値辞書で手計算と一致を確認:

- `test_dir_score_single_signal` — `w=1.0, x=0.5` → `0.5`
- `test_dir_score_two_signals_normalized` — `w=(2,1), x=(0.5, -1)` → `(2*0.5 + 1*-1)/(2+1) = 0.0`
- `test_dir_score_empty` → `0.0`
- `test_dir_score_zero_weights_sum` → `0.0`（理論的には起きない、safety）
- `test_gate_empty` → `1.0`
- `test_gate_product` — `values=(0.8, 0.5)` → `0.4`
- `test_compute_clause_score` — `dir=0.3, gate=0.5` → `0.15`
- `test_composite_single_clause` — 1 clause のみ → `cs`
- `test_composite_multi_clause_normalized` — 2 clause の加重平均
- `test_composite_len_mismatch_raises` → `ValueError`
- `test_composite_empty_clauses_raises` → `ValueError`
- `test_composite_denom_zero` — 全 `clause.weight=0` → `0.0`

### 8.3 `tests/dsl/test_strategy.py`

Stub Evaluator で composite を注入し、ヒステリシス遷移を検証:

```python
class ScriptedEvaluator:
    """bar index ごとに返す値を事前設定する stub."""
    def __init__(self, script: dict[int, dict[str, float]]):
        self._script = script
    def evaluate(self, bars, idx, signal):
        return self._script[idx][signal.name]
```

- `test_warmup_no_signals` — warmup 期間中は空 list
- `test_entry_long_at_theta_on` — `composite == θ_on` → open_long
- `test_entry_short_at_theta_on` — `composite == -θ_on` → open_short
- `test_no_entry_below_theta_on` — `composite < θ_on` → 空
- `test_hold_between_theta_off_and_theta_on` — long 保有 + `θ_off <= composite < θ_on` → 何もしない（チャタリング防止）
- `test_exit_long_below_theta_off` — `composite < θ_off` → close_position
- `test_exit_short_above_neg_theta_off` — short 保有 + `-composite < θ_off` → close
- `test_time_stop_forces_close` — `time_stop_min=60` + 60 分経過 → close
- `test_session_close_forces_close` — `session_close_utc=time(21,0)` + bar_time.time() >= 21:00 → close
- `test_session_close_none_no_force` — `session_close_utc=None` → 境界越えても自発 close しない（engine EOD に委譲）
- `test_exit_at_theta_off_equal_long_no_close` — long 保有 + `composite == θ_off` → close しない（`<` 厳密）
- `test_exit_at_theta_off_equal_short_no_close` — short 保有 + `-composite == θ_off` → close しない（対称性）

Bar 生成: `_helpers.make_bar(bar_time, close, ...)` を作成しテストで使う。

### 8.4 `tests/dsl/test_enforce.py`

- `test_directional_weight_clip_lower` — `weight=0.05` → `0.1`
- `test_directional_weight_clip_upper` — `weight=2.5` → `2.0`
- `test_directional_weight_abs` — `weight=-0.5` → `0.5`
- `test_directional_dedupe` — 同 name 複数 → 1 つ（後勝ち）
- `test_gate_weight_clip` — `weight=2.5` → `2.0`, `-2.5` → `-2.0`
- `test_gate_max_one` — 2 つ以上 → `|weight|` 最大の 1 つ
- `test_gate_dedupe` — 同 name 複数 → 1 つ
- `test_position_swap_when_entry_lte_exit` — `entry=0.1, exit=0.3` → `entry=0.3, exit=0.1`
- `test_position_swap_equal_thresholds` — `entry=exit=0.2` → `entry=0.2, exit=0.2 - 1e-6`
- `test_position_max_pos_min_1` — `max_pos=0` → `1`
- `test_position_time_stop_non_negative` — `time_stop_min=-5` → `0`
- `test_risk_positive_epsilon` — `stop_atr=0` → `1e-6`
- `test_clause_all_directional_empty_raises` — clause 1 つで directional 空 → `ValueError`
- `test_clause_directional_empty_removed_when_others_exist` — 2 clause、1 つが空 → 残りの 1 つ
- `test_clauses_over_three_truncated` — 4 clause → 3 clause（|weight| Top 3）
- `test_enforce_idempotent` — `f(f(x)) == f(x)`（有限実数入力で冪等性を担保）
- `test_enforce_rejects_nan_weight` — SignalConfig.weight=`math.nan` → `ValueError`
- `test_enforce_rejects_inf_weight` — SignalConfig.weight=`math.inf` → `ValueError`
- `test_enforce_rejects_nan_threshold` — PositionConfig.entry_threshold=`math.nan` → `ValueError`
- `test_enforce_rejects_nan_atr` — RiskConfig.stop_atr=`math.nan` → `ValueError`
- `test_enforce_rejects_nan_clause_weight` — ClauseConfig.weight=`math.nan` → `ValueError`
- `test_enforce_rejects_inf_clause_weight` — ClauseConfig.weight=`math.inf` → `ValueError`
- `test_signal_config_defensive_copy` — 生成時に渡した外部 dict を後で変更しても SignalConfig.params が独立であること

## 9. 後続 TODO への受け渡し契約

### 9.1 `clause-ga-operators`

- `src/ga/random_gen.py` を Genome の新 API に書き換え
- `random_signal_config(rng, kind: Literal["directional", "local_gate"])` を新設
- crossover: signal 単位 or clause 単位の swap
- mutate: weight perturb, name swap, params perturb, clause add/remove
- 各 operator の直後に `enforce_consistency` を呼ぶ

### 9.2 `clause-backtest-integration`

- `src/backtest/engine.py` に `PrimitiveEvaluator` を受け渡すインターフェースを追加
  （`run_backtest(bars, strategy, broker, config, evaluator=...)`）
- `BacktestConfig` に `max_spread_bps` / `swap_cost_per_day` を追加（spread フィルタ実装）
- `src/ga/fitness.py` の `evaluate_genome` が `DslStrategy(genome, evaluator, ...)` を組み立てる

### 9.3 `primitives-registry`

- `PrimitiveEvaluator` の実装クラス `RegistryEvaluator` を作成
- primitive ID → 評価関数の mapping
- `warmup_bars(signal)` メソッドを追加

## 10. 実装順序

1. `src/dsl/genome.py` 置き換え → 構文確認のみで pytest は走らない
2. `src/dsl/composite.py` 新規
3. `src/dsl/enforce.py` 新規
4. `src/dsl/strategy.py` 新規
5. `src/dsl/serialize.py` 更新
6. `src/dsl/__init__.py` 更新
7. `src/dsl/samples.py` 削除（`git rm`）
8. 旧テスト skip 付与（`pytest.mark.skip` を `pytestmark` で module-level）
9. 新テスト 4 ファイル実装
10. `uv run pytest --collect-only` で pytest 収集が成功することを先に確認（import エラー検出）
11. `uv run pytest tests/dsl/ -x` で新テスト PASS、skip が期待どおり
12. `uv run pytest` 全体実行で他領域の破壊を確認、skip で回避できているか
13. mypy / ruff（設定があれば）

## 11. リスクと軽減策

| リスク | 軽減策 |
|--------|-------|
| `src/ga/` import 時エラーで pytest collection 失敗 | `src/ga/` 本体は変更せず、テストファイル module-level skip で collection 成功させる |
| `tests/backtest/` の引き込みエラー | `from src.dsl import ma_crossover_genome` 等を使うテストのみ module-level skip |
| `enforce_consistency` の `entry == exit` 時 `1e-6` 丸め | float tolerance で問題ない範囲。後続で調整 |
| params dict の shared reference 問題 | serialize で `dict(...)` コピー、テストで別 dict 経由も検証 |
