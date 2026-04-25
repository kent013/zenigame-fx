# 詳細設計: strategy-signal-cache-flatten

## 使命・制約（絶対遵守）

### zenigame-fx Alpha Factory 使命
live_criteria 全指標同時充足 + (ii-lite) 通過で使命達成。
絶対制約: イントラデイ / ロング・ショート両方向 / スワップ・スプレッド反映。

### 禁止事項
7 項目（概念設計参照）

### コーディングルール
- **全施策にテスト必須**
- **テスト命名**: 振る舞いを説明する汎用的な名前
- **テスト配置**: `tests/dsl/test_dsl_strategy_flat_cache.py`（新規）
- **uv 必須**: `uv run pytest tests/broker/ tests/backtest/ tests/alpha_factory/ tests/dsl/ -x`
- **ruff / mypy 通過**
- Python 3.11

## 概念設計リファレンス

[devnotes/20260425-0256-strategy-signal-cache-flatten/conceptual-design.md](./conceptual-design.md) — APPROVED (Round 2)

## 前提 verify 完了

| # | 前提 | 状態 | verify |
|---|---|---|---|
| P1-P10 | (概念設計 §前提表) | **Verified** | 全 grep 確認済 |
| P11 | prepare() での name uniqueness assert | **To implement** | 施策 1 で実装 |

### Warning 対応（Round 2）

- **W1: P11 is To implement** → 施策 1 の必須要素として明示、test `test_prepare_rejects_duplicate_signal_names_in_clause` で CI gate 化
- **W2: genome identity 検証** → PreparedSignals に `genome: Genome` field を追加、on_bar で `prepared.genome is self._genome` の O(1) identity 比較で検出（Design Review Round 1 Critical #2 で fingerprint 毎バー再構築を避けるため identity 比較に変更、Round 2 Critical #1 で施策 0 の MappingProxyType 化により deep immutability を保証）

## 施策一覧

| # | 施策名 | 変更ファイル | 優先度 |
|---|--------|------------|--------|
| 0 | **`SignalConfig.params` を `MappingProxyType` 化**（deep immutability、Design Review Round 2 Critical #1 対応） | `src/dsl/genome.py` | High |
| 1 | DslStrategy に `PreparedSignals` NamedTuple を導入、`_signal_cache_key` hot path 排除、genome identity check | `src/dsl/strategy.py` | High |
| 2 | flat cache invariance / fail-fast tests (NaN fallback 強化版) | `tests/dsl/test_dsl_strategy_flat_cache.py` (新規) | High |
| 3 | 既存 `test_engine_prepare.py` の `_precomputed` 参照を `_prepared` に追従 | `tests/backtest/test_engine_prepare.py` | Medium |

## 施策 0: SignalConfig.params を MappingProxyType 化（Deep Immutability）

### 背景
Design Review Round 2 Critical #1: `SignalConfig` は `@dataclass(frozen=True)` だが `params: dict[str, float | int]` の dict 自体は mutable で、caller が `sig.params["k"] = v` で in-place mutation 可能。これにより `prepared.genome is self._genome` が True でも params 内容が変わる false negative の穴が残る。

### 変更箇所
`src/dsl/genome.py:25-43` の `SignalConfig`

### 事前調査（mutation 経路の完全列挙）
```bash
grep -rn "\.params\[" src/ tests/   # 代入経路
grep -rn "sig\.params\s*=\|signal\.params\s*=" src/ tests/   # field 代入
```
結果:
- `src/` では `.params[...]` への書き込みは**ゼロ件**
- `tests/dsl/test_genome_clause.py:45, 53` は **read only** (`assert sig.params == ...`)
- 現実には mutation 経路が存在しないが、防御的 immutability で将来変更・外部呼び出しからの保護を強化

### 現行コード
```python
# src/dsl/genome.py:25-43
@dataclass(frozen=True)
class SignalConfig:
    name: str
    weight: float
    params: dict[str, float | int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "params", dict(self.params))
```

### 変更後コード
```python
# src/dsl/genome.py:25-46
from types import MappingProxyType
from collections.abc import Mapping

@dataclass(frozen=True)
class SignalConfig:
    """単一 primitive の呼び出し定義。

    Attributes:
        name: primitive ID (例: "F1", "M1")。
        weight: directional の場合 [0.1, 2.0] の正、local_gate の場合 [-2.0, 2.0]。
        params: primitive 固有パラメータ。生成時に defensive copy + MappingProxyType
                で immutable 化される (Cycle 2 / T029 で deep immutability 保証)。
    """

    name: str
    weight: float
    params: Mapping[str, float | int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # Cycle 2 / T029: dict(self.params) で shared reference を遮断した上で
        # MappingProxyType で外部からの mutation を禁止 (deep immutability)。
        # DslStrategy の prepare-time identity check (`prepared.genome is
        # self._genome`) が安全に成立する前提を構成する。
        object.__setattr__(
            self, "params", MappingProxyType(dict(self.params))
        )
```

### 波及変更
- `AGENTS.md`: 不要
- `.claude/skills/*/SKILL.md`: 不要
- `config/alpha_factory/default.yaml`: 不要
- `docs/alpha_factory/*.md`: 不要
- `src/ga/random_gen.py` / `src/ga/operators.py`: random_gen が dict で params を生成するため、SignalConfig に渡す時点で defensive copy + MappingProxyType 変換される → mutate なければ影響なし。影響調査必須（Phase W で grep 再確認）
- `src/dsl/serialize.py`: genome の dump / load で params が dict 型でなくても動くか確認必須

### ルックアヘッドバイアスチェック
- N/A（データ型変更のみ）

### パフォーマンスチェック
- MappingProxyType は dict のラッパで read は同等速度
- `prepare()` 内の `tuple(sorted(sig.params.items()))` も引き続き動作（Mapping が items() を提供）

### テスト計画
- 既存 `tests/dsl/test_genome_clause.py` の `sig.params == {...}` 等の read 比較は引き続き合格
- 新規 test `test_signal_config_params_immutable` を追加（施策 2）: `sig.params["k"] = v` で `TypeError` が raise されること

### リスク
- 型注釈が `dict` → `Mapping` に変わるため、既存コードで `sig.params: dict` を期待する箇所があれば mypy error。影響範囲は `grep -rn "sig\.params:\|signal\.params:" src/` で確認（想定: ゼロ件）
- `dict(sig.params)` のような cast は引き続き動作（Mapping を dict() に渡せる）

## 施策 1: DslStrategy に PreparedSignals を導入

### 変更箇所
`src/dsl/strategy.py` 全体（既存コード書き換え）

### 波及変更
- `AGENTS.md`: 不要
- `.claude/skills/*/SKILL.md`: 不要
- `config/alpha_factory/default.yaml`: 不要
- `docs/alpha_factory/*.md`: 不要

### 現行コード

```python
# src/dsl/strategy.py:23-199 (抜粋)
def _signal_cache_key(sig):
    return (sig.name, tuple(sorted(sig.params.items())))


class DslStrategy:
    def __init__(self, genome, evaluator, *, warmup_bars=0, session_close_utc=None):
        # ...
        self._precomputed: dict[tuple[str, tuple[tuple[str, float | int], ...]], np.ndarray] | None = None
        self._bar_count = 0

    def prepare(self, bars):
        if not hasattr(self._evaluator, "evaluate_all_bars"):
            return
        cache: dict[...] = {}
        for clause in self._genome.clauses:
            for sig in (*clause.directional, *clause.local_gate):
                key = _signal_cache_key(sig)
                if key not in cache:
                    cache[key] = self._evaluator.evaluate_all_bars(bars, sig)
        self._precomputed = cache
        self._bar_count = 0

    def _lookup_signal(self, sig, idx):
        assert self._precomputed is not None
        key = _signal_cache_key(sig)
        arr = self._precomputed[key]
        if idx < 0 or idx >= len(arr):
            return 0.0
        v = float(arr[idx])
        return 0.0 if not math.isfinite(v) else v

    def on_bar(self, bar, snapshot):
        if self._precomputed is not None:
            idx = self._bar_count
            self._bar_count += 1
            if idx < self._warmup:
                return []
        else:
            self._bars.append(bar)
            if len(self._bars) < self._warmup:
                return []
            idx = len(self._bars) - 1

        values_per_clause = []
        for clause in self._genome.clauses:
            vals = {}
            if self._precomputed is not None:
                for sig in clause.directional:
                    vals[sig.name] = self._lookup_signal(sig, idx)
                for sig in clause.local_gate:
                    vals[sig.name] = self._lookup_signal(sig, idx)
            else:
                for sig in clause.directional:
                    vals[sig.name] = self._evaluator.evaluate(self._bars, idx, sig)
                for sig in clause.local_gate:
                    vals[sig.name] = self._evaluator.evaluate(self._bars, idx, sig)
            values_per_clause.append(vals)
        composite = compute_composite(self._genome.clauses, values_per_clause)
        # ... position logic ...
```

### 変更後コード

```python
"""Clause ベース DslStrategy。

Cycle 2 (T029) で prepared signal flattening を導入:
  - `PreparedSignals` NamedTuple で prepare state を単一化
  - per-clause flat list で on_bar hot path から sorted() / dict lookup を排除
  - genome identity 検証で lifecycle contract violation を fail-fast
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from typing import NamedTuple, Protocol

import numpy as np

from src.broker.orders import OrderSignal, PortfolioSnapshot
from src.domain.price import PriceBar
from src.dsl.composite import compute_composite
from src.dsl.genome import Genome, SignalConfig

# SignalCacheKey: (primitive_id, sorted params tuple)
SignalCacheKey = tuple[str, tuple[tuple[str, float | int], ...]]


def _signal_cache_key(sig: SignalConfig) -> SignalCacheKey:
    """(name, sorted params tuple) で決定論的な cache key を作る.

    prepare() 内でのみ呼ばれる (Cycle 2 以降、on_bar hot path からは排除)。
    Cycle 1 (commit e49c80a) 時点では per-bar per-sig で呼ばれていたが、
    Cycle 2 (T029) で prepare-time precompute に移行した。
    """
    return (sig.name, tuple(sorted(sig.params.items())))


class PreparedSignals(NamedTuple):
    """prepare() で構築される precompute state (Cycle 2 / T029 で導入).

    単一オブジェクトにまとめることで、Cycle 1 の `_precomputed` + bar loop 内
    `_signal_cache_key` 再計算による 2 重管理と hot path コストを排除する。

    Attributes:
        arrays: (sig.name, sorted(params.items()) tuple) → ndarray。
                duplicate signal の共有用 lookup cache (同一 genome 内で同一
                (name, params) を持つ signal が複数 clause にあれば 1 度のみ
                compute_all_bars を呼ぶ invariant は Cycle 1 から不変)。
        clauses: clause_idx → (directional_entries, gate_entries)。
                各 entries は (sig.name, arr) の tuple を clause.directional /
                local_gate の index 順に保持。on_bar では index 直接 iterate
                で O(1) per-sig lookup。
        genome: prepare() 呼び出し時の genome reference。on_bar 冒頭で
                `prepared.genome is self._genome` の O(1) identity 比較で
                genome 差し替え等の lifecycle contract violation を fail-fast
                検出する (Design Review Round 1 Critical #2 対応: fingerprint
                毎バー再構築の O(clause×sig) コストを回避)。

                **Deep immutability の保証 (Design Review Round 2 Critical #1
                対応)**: Genome / ClauseConfig / SignalConfig / PositionConfig
                / RiskConfig は全て `@dataclass(frozen=True)`、`Genome.clauses`
                等の tuple field は structurally immutable、施策 0 で
                `SignalConfig.params` を `MappingProxyType` 化することで
                dict 値の in-place mutation も禁止される。よって `is` が True
                なら内容完全一致が構造的に保証される (identity → content
                equality の upgrade)。
    """

    arrays: dict[SignalCacheKey, np.ndarray]
    clauses: tuple[tuple[
        tuple[tuple[str, np.ndarray], ...],  # directional entries
        tuple[tuple[str, np.ndarray], ...],  # gate entries
    ], ...]
    genome: Genome


class PrimitiveEvaluator(Protocol):
    """primitive 評価関数の抽象 (既存)."""

    def evaluate(
        self, bars: list[PriceBar], idx: int, signal: SignalConfig
    ) -> float:
        ...


@dataclass
class _OpenPosition:
    position_id: int
    side: str
    entry_time: datetime


def _assert_unique_name(
    name: str, seen: set[str], clause_idx: int
) -> None:
    """同一 clause 内で signal.name 重複を fail-fast で拒否する.

    重複すると values_per_clause[i][name] の後勝ち上書きで silent bug 化
    するため、prepare() 時に禁止する (Round 1 Critical #3 対応)。
    """
    if name in seen:
        raise ValueError(
            f"duplicate signal.name {name!r} in clause index {clause_idx}; "
            f"signal names must be unique within a clause"
        )
    seen.add(name)


def _validate_unique_names_in_clauses(genome: Genome) -> None:
    """全 clause で signal.name 一意性を fail-fast 検証する.

    重複すると values_per_clause[i][name] が後勝ち上書きで silent bug 化する。
    Design Review Round 1 Warning #3 対応: unprepared (live feed) path も
    含めて同じ契約を強制するため、`__init__` から呼ぶ (prepare() 限定では
    paper trading で抜け漏れ)。
    """
    for clause_idx, clause in enumerate(genome.clauses):
        seen: set[str] = set()
        for sig in (*clause.directional, *clause.local_gate):
            _assert_unique_name(sig.name, seen, clause_idx)


class DslStrategy:
    """Clause ベース Genome を評価する Strategy (Cycle 2 / T029)."""

    def __init__(
        self,
        genome: Genome,
        evaluator: PrimitiveEvaluator,
        *,
        warmup_bars: int = 0,
        session_close_utc: time | None = None,
    ) -> None:
        # 全 clause で signal.name 一意性を検証 (Design Review Round 1
        # Warning #3 対応: prepared / unprepared 両 path で同じ契約を強制)。
        # prepare() 内の重複検出では paper trading で抜け漏れる。
        _validate_unique_names_in_clauses(genome)
        self._genome = genome
        self._evaluator = evaluator
        self._warmup = warmup_bars
        self._session_close = session_close_utc
        self._bars: list[PriceBar] = []
        # 単一 prepared state (Cycle 2 / T029)。prepare() 未呼出時は None、
        # paper trading / live feed では常に None のまま (P8 Verified)。
        self._prepared: PreparedSignals | None = None
        self._bar_count = 0

    @property
    def genome(self) -> Genome:
        return self._genome

    def warmup_bars(self) -> int:
        return self._warmup

    def prepare(self, bars: list[PriceBar]) -> None:
        """backtest 全バーを事前計算して flat list に展開する.

        O(N²) → O(N) 最適化 (Cycle 1 から継承) + per-bar sorted() 排除
        (Cycle 2 / T029)。primitive が look-ahead bias-free である前提:
          compute_all_bars(bars)[idx] == compute_all_bars(bars[:idx+1])[idx]

        evaluator が evaluate_all_bars を持たない場合は NoOp
        (self._prepared を None のまま)、従来 path にフォールバック。

        Round 2 対応:
          - Round 1 Critical #2: _precomputed + _precomputed_clauses の
            2 重管理を単一 PreparedSignals に統合
          - Round 1 Critical #3: 同一 clause 内 signal.name 重複を fail-fast
          - Round 2 Warning 2: genome reference を prepare() 時点で保存
        """
        # 再 prepare() 時の stale state 除去 (Round 1 Warning 対応)
        self._prepared = None
        self._bar_count = 0

        if not hasattr(self._evaluator, "evaluate_all_bars"):
            return

        arrays: dict[SignalCacheKey, np.ndarray] = {}
        clause_entries: list[tuple[
            tuple[tuple[str, np.ndarray], ...],
            tuple[tuple[str, np.ndarray], ...],
        ]] = []

        # name 一意性は __init__ で検証済み (Round 1 Warning #3 対応)。
        # ここでは arrays 共有 cache のみ意識すればよい。
        for clause in self._genome.clauses:
            dir_entries: list[tuple[str, np.ndarray]] = []
            for sig in clause.directional:
                key = _signal_cache_key(sig)
                if key not in arrays:
                    arrays[key] = self._evaluator.evaluate_all_bars(bars, sig)
                dir_entries.append((sig.name, arrays[key]))

            gate_entries: list[tuple[str, np.ndarray]] = []
            for sig in clause.local_gate:
                key = _signal_cache_key(sig)
                if key not in arrays:
                    arrays[key] = self._evaluator.evaluate_all_bars(bars, sig)
                gate_entries.append((sig.name, arrays[key]))

            clause_entries.append((tuple(dir_entries), tuple(gate_entries)))

        self._prepared = PreparedSignals(
            arrays=arrays,
            clauses=tuple(clause_entries),
            genome=self._genome,  # identity 比較用 (O(1))
        )

    def on_bar(
        self, bar: PriceBar, snapshot: PortfolioSnapshot
    ) -> list[OrderSignal]:
        prepared = self._prepared  # single snapshot read (atomicity)

        if prepared is not None:
            # O(1) identity check: prepare() 時点の genome と同一 reference か
            # (Design Review Round 1 Critical #2 対応: fingerprint 毎バー
            # 再構築の O(clause×sig) コストを回避)。Genome は frozen (P7) で
            # tuple fields も immutable のため、identity == は内容 == と
            # 同値 (`is` → `==` の upgrade は構造的に保証)。
            assert prepared.genome is self._genome, (
                "DslStrategy.prepared state is inconsistent with current "
                "genome; genome was swapped after prepare()? (lifecycle "
                "contract violation)"
            )
            idx = self._bar_count
            self._bar_count += 1
            if idx < self._warmup:
                return []
        else:
            self._bars.append(bar)
            if len(self._bars) < self._warmup:
                return []
            idx = len(self._bars) - 1

        # 各 clause の primitive 値を評価
        values_per_clause: list[dict[str, float]] = []
        if prepared is not None:
            # fast path: flat list iteration (Cycle 2 / T029)
            for dir_entries, gate_entries in prepared.clauses:
                vals: dict[str, float] = {}
                for name, arr in dir_entries:
                    v = arr[idx] if 0 <= idx < len(arr) else 0.0
                    vals[name] = 0.0 if not math.isfinite(v) else float(v)
                for name, arr in gate_entries:
                    v = arr[idx] if 0 <= idx < len(arr) else 0.0
                    vals[name] = 0.0 if not math.isfinite(v) else float(v)
                values_per_clause.append(vals)
        else:
            # unprepared path (live feed / paper trading)
            for clause in self._genome.clauses:
                vals = {}
                for sig in clause.directional:
                    vals[sig.name] = self._evaluator.evaluate(
                        self._bars, idx, sig
                    )
                for sig in clause.local_gate:
                    vals[sig.name] = self._evaluator.evaluate(
                        self._bars, idx, sig
                    )
                values_per_clause.append(vals)

        composite = compute_composite(self._genome.clauses, values_per_clause)
        pos_cfg = self._genome.position

        # 保有あり: exit 判定のみ
        if snapshot.positions:
            pos = snapshot.positions[0]
            if (
                self._session_close is not None
                and bar.bar_time.time() >= self._session_close
            ):
                return [OrderSignal(kind="close_position", position_id=pos.id)]
            if pos_cfg.time_stop_min > 0:
                elapsed = bar.bar_time - pos.entry_time
                if elapsed >= timedelta(minutes=pos_cfg.time_stop_min):
                    return [OrderSignal(kind="close_position", position_id=pos.id)]
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

### 削除される要素
- `self._precomputed: dict[...] | None` フィールド → `self._prepared` に置換
- `self._lookup_signal(sig, idx)` メソッド → on_bar 内 inline 化で削除
- module-level `_signal_cache_key` は残存するが prepare() 内のみから呼ばれる

### ルックアヘッドバイアスチェック
- [x] 未来バー参照なし（arr は compute_all_bars で事前計算、look-ahead-free 保証）
- [x] 当日確定値の先取りなし
- [x] rolling window 方向（primitive 側で担保）
- [x] 正規化（primitive 側）
- [x] バケット平均（primitive 側）
- [x] cumsum/accumulate（primitive 側）

### パフォーマンスチェック
- [x] compute_all_bars 実装済み（primitive 側、Cycle 1 から変更なし）
- [x] 内側ループ内 NumPy なし（arr[idx] は C-level indexing）
- [x] SoA プロパティ使用（tuple of (name, arr) で参照共有）
- [x] 同一配列のキャッシュ（arrays dict で duplicate signal 共有）

### テスト計画
- [ ] 既存 `tests/backtest/test_engine_prepare.py` の 3 test を `_prepared` に追従（施策 3）
- [ ] 新規 `tests/dsl/test_dsl_strategy_flat_cache.py` を追加（施策 2）

### リスク
- **identity 検証コスト**: `prepared.genome is self._genome` は O(1) pointer compare でほぼゼロコスト。Python の C-level identity check。
- **assert 文の性能**: `assert` は `-O` optimization フラグで無効化される。default では実行される → 本番コストあり。production では `-O` でなく default 実行なので OK
- **stale bars 参照**: unprepared path で `self._bars.append(bar)` を呼ぶ。prepare() 経路では触らない。state machine unprepared → prepared の境界で片方のみ state を扱う invariant は保たれる

## 施策 2: flat cache invariance tests

### 変更箇所
`tests/dsl/test_dsl_strategy_flat_cache.py`（新規）

### 波及変更
- AGENTS.md / skills / config / docs: 不要

### テスト構造

```python
"""DslStrategy の flat cache / PreparedSignals invariance tests (Cycle 2 / T029).

Cycle 2 で prepare() の cache 構造を `PreparedSignals` NamedTuple に統合し、
on_bar hot path から `_signal_cache_key` を排除した。以下を検証:
  - `self._prepared` の単一 slot 化 (Round 1 Critical #2)
  - 同一 clause 内 signal.name 重複の __init__ fail-fast (Review R1 Warning #3)
  - genome identity 検証で mutation 検出 (Review R1 Critical #1/#2)
  - prepared / unprepared 経路が同じ vals を生成 (bit-identical)
  - NaN/inf 入力時の fallback (Review R1 Warning #4)
"""
from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import numpy as np
import pytest

from src.alpha_factory.primitives import (
    RegistryEvaluator,
    clear,
    ensure_registered,
)
from src.backtest.engine import BacktestConfig, run_backtest
from src.broker.mock import MockBroker
from src.domain.price import Ohlc, PriceBar
from src.dsl.genome import (
    ClauseConfig,
    Genome,
    PositionConfig,
    RiskConfig,
    SignalConfig,
)
from src.dsl.strategy import DslStrategy, PreparedSignals
from tests._helpers import usd_jpy_meta


# Review R1 Suggestion #6 + Review R2 Suggestion #4: registry isolation
@pytest.fixture(autouse=True)
def _registry_isolation():
    """各 test 前後で registry を clear + re-register し、global state の
    汚染を防ぐ (primitives-registry は global singleton なため)。

    teardown は `clear()` のみで後続テストに暗黙状態を注入しない。"""
    clear()
    ensure_registered()
    yield
    clear()


def _bar(i: int, base: Decimal = Decimal("154.00")) -> PriceBar:
    bt = datetime(2026, 4, 1, 0, 0, 0, tzinfo=UTC) + timedelta(minutes=i)
    offset = Decimal(str(round(math.sin(i / 30.0) * 0.5, 5)))
    mid = base + offset
    bid = mid - Decimal("0.005")
    ask = mid + Decimal("0.005")
    return PriceBar(
        pair_name="USD_JPY",
        bar_time=bt,
        bid=Ohlc(bid, bid + Decimal("0.001"), bid - Decimal("0.001"), bid),
        ask=Ohlc(ask, ask + Decimal("0.001"), ask - Decimal("0.001"), ask),
        volume=10,
        complete=True,
    )


def _genome_simple() -> Genome:
    return Genome(
        name="g_flat",
        units=10000,
        clauses=(
            ClauseConfig(
                directional=(
                    SignalConfig(
                        name="F1", weight=1.0,
                        params={"fast_n": 5, "slow_n": 20, "atr_n": 10},
                    ),
                ),
                local_gate=(),
                weight=1.0,
            ),
        ),
        position=PositionConfig(
            entry_threshold=0.1, exit_threshold=0.05,
            max_pos=1, time_stop_min=0,
        ),
        risk=RiskConfig(stop_atr=2.0, take_atr=3.0),
    )


def test_prepare_stores_single_slot_state() -> None:
    """Round 1 Critical #2: 2 重管理の排除を検証."""
    ev = RegistryEvaluator(pair="USD_JPY")
    strat = DslStrategy(_genome_simple(), ev)
    assert strat._prepared is None
    bars = [_bar(i) for i in range(200)]
    strat.prepare(bars)
    assert isinstance(strat._prepared, PreparedSignals)
    # _precomputed は削除されている (旧 API なし)
    assert not hasattr(strat, "_precomputed") or strat._precomputed is None


def test_prepared_clauses_are_tuples_of_tuples() -> None:
    """clauses が immutable tuple で書き換え不可であること."""
    ev = RegistryEvaluator(pair="USD_JPY")
    strat = DslStrategy(_genome_simple(), ev)
    strat.prepare([_bar(i) for i in range(200)])
    p = strat._prepared
    assert p is not None
    assert isinstance(p.clauses, tuple)
    for clause_entries in p.clauses:
        assert isinstance(clause_entries, tuple)
        assert len(clause_entries) == 2  # (directional, gate)
        dir_entries, gate_entries = clause_entries
        assert isinstance(dir_entries, tuple)
        assert isinstance(gate_entries, tuple)


def test_prepare_rejects_duplicate_signal_names_in_clause() -> None:
    """Round 1 Critical #3: 同一 clause 内 signal.name 重複を fail-fast."""
    ev = RegistryEvaluator(pair="USD_JPY")
    dup_sig_a = SignalConfig(
        name="F1", weight=1.0, params={"fast_n": 5, "slow_n": 20, "atr_n": 10}
    )
    dup_sig_b = SignalConfig(
        name="F1", weight=0.5, params={"fast_n": 3, "slow_n": 15, "atr_n": 7}
    )
    genome = Genome(
        name="g_dup",
        units=10000,
        clauses=(
            ClauseConfig(
                directional=(dup_sig_a, dup_sig_b),  # 同名重複
                local_gate=(),
                weight=1.0,
            ),
        ),
        position=PositionConfig(0.1, 0.05, 1, 0),
        risk=RiskConfig(2.0, 3.0),
    )
    strat = DslStrategy(genome, ev)
    with pytest.raises(ValueError, match="duplicate signal.name"):
        strat.prepare([_bar(i) for i in range(100)])


def test_prepare_shares_arrays_across_duplicate_signals_between_clauses() -> None:
    """同一 (name, params) の signal が別 clause にあれば arrays dict を共有."""
    ev = RegistryEvaluator(pair="USD_JPY")
    shared = SignalConfig(
        name="F1", weight=1.0, params={"fast_n": 5, "slow_n": 20, "atr_n": 10}
    )
    genome = Genome(
        name="g_share",
        units=10000,
        clauses=(
            ClauseConfig(directional=(shared,), local_gate=(), weight=1.0),
            ClauseConfig(directional=(shared,), local_gate=(), weight=1.0),
        ),
        position=PositionConfig(0.1, 0.05, 1, 0),
        risk=RiskConfig(2.0, 3.0),
    )
    strat = DslStrategy(genome, ev)
    strat.prepare([_bar(i) for i in range(100)])
    p = strat._prepared
    assert p is not None
    # arrays dict は 1 entry のみ (共有)
    assert len(p.arrays) == 1
    # 両 clause の directional entries は同じ arr object を参照
    arr_c0 = p.clauses[0][0][0][1]  # clause 0 directional[0] arr
    arr_c1 = p.clauses[1][0][0][1]  # clause 1 directional[0] arr
    assert arr_c0 is arr_c1


def test_on_bar_prepared_equivalent_to_unprepared() -> None:
    """Round 1: prepared / unprepared 経路が同じ trades / equity を生成."""
    bars = [_bar(i) for i in range(400)]
    cfg = BacktestConfig(
        instrument="USD_JPY",
        start=datetime(2026, 4, 1, tzinfo=UTC),
        end=datetime(2026, 4, 3, tzinfo=UTC),
        initial_cash=Decimal("1000000"),
        leverage=10,
        max_spread_bps=Decimal("10"),
        session_close_utc_hours=frozenset({21}),
        bar_minutes=1,
    )

    class _NoPrepareEvaluator:
        """evaluate_all_bars を持たないラッパ (prepared を抑制)."""

        def __init__(self, inner):
            self._inner = inner

        def evaluate(self, bars_, idx, sig):
            return self._inner.evaluate(bars_, idx, sig)

    ev_fast = RegistryEvaluator(pair="USD_JPY")
    strat_fast = DslStrategy(_genome_simple(), ev_fast)
    broker_fast = MockBroker(instrument_meta=usd_jpy_meta())
    result_fast = run_backtest(bars, strat_fast, broker_fast, cfg)

    ev_slow = _NoPrepareEvaluator(RegistryEvaluator(pair="USD_JPY"))
    strat_slow = DslStrategy(_genome_simple(), ev_slow)
    broker_slow = MockBroker(instrument_meta=usd_jpy_meta())
    result_slow = run_backtest(bars, strat_slow, broker_slow, cfg)

    assert strat_fast._prepared is not None
    assert strat_slow._prepared is None

    assert len(result_fast.trades) == len(result_slow.trades)
    assert broker_fast.snapshot().equity == broker_slow.snapshot().equity
    for tf, ts in zip(result_fast.trades, result_slow.trades, strict=True):
        assert tf.entry_time == ts.entry_time
        assert tf.exit_time == ts.exit_time
        assert tf.side == ts.side
        assert tf.entry_price == ts.entry_price
        assert tf.exit_price == ts.exit_price


def test_prepare_resets_stale_state_on_repeated_call() -> None:
    """Round 1 Warning: 再 prepare() で stale state を除去."""
    ev = RegistryEvaluator(pair="USD_JPY")
    strat = DslStrategy(_genome_simple(), ev)
    strat.prepare([_bar(i) for i in range(100)])
    first = strat._prepared
    assert first is not None
    # 再 prepare (別 bars)
    strat.prepare([_bar(i) for i in range(200)])
    second = strat._prepared
    assert second is not None
    assert second is not first  # 新規 state
    assert strat._bar_count == 0  # reset されている


def test_genome_identity_mismatch_raises_on_swap() -> None:
    """Round 2 Warning 2 + Review R1 Critical #2: prepare() 後に別 genome を
    self._genome にセットすると O(1) identity 検査で fail-fast。"""
    ev = RegistryEvaluator(pair="USD_JPY")
    g1 = _genome_simple()
    g2 = Genome(
        name="g_swap",
        units=10000,
        clauses=(
            ClauseConfig(
                directional=(
                    SignalConfig(
                        name="F2", weight=1.0,
                        params={"fast_n": 3, "slow_n": 10, "signal_n": 7},
                    ),
                ),
                local_gate=(),
                weight=1.0,
            ),
        ),
        position=PositionConfig(0.1, 0.05, 1, 0),
        risk=RiskConfig(2.0, 3.0),
    )
    strat = DslStrategy(g1, ev)
    strat.prepare([_bar(i) for i in range(100)])
    # lifecycle 違反: genome instance を差し替え
    strat._genome = g2  # type: ignore[assignment]
    with pytest.raises(AssertionError, match="inconsistent with current genome"):
        strat.on_bar(_bar(0), _empty_snapshot())


def test_clause_boundary_and_weight_change_detected() -> None:
    """Review R1 Critical #1 対応: directional/local_gate 境界変更や
    clause.weight / signal.weight 変更でも identity 比較で検出 (別 instance)。"""
    ev = RegistryEvaluator(pair="USD_JPY")
    g1 = _genome_simple()
    # 同じ signal name/params だが clause.weight が異なる
    g1_weight_changed = Genome(
        name=g1.name, units=g1.units,
        clauses=(
            ClauseConfig(
                directional=g1.clauses[0].directional,
                local_gate=g1.clauses[0].local_gate,
                weight=0.5,  # 変更
            ),
        ),
        position=g1.position, risk=g1.risk,
    )
    assert g1 is not g1_weight_changed
    strat = DslStrategy(g1, ev)
    strat.prepare([_bar(i) for i in range(100)])
    strat._genome = g1_weight_changed  # type: ignore[assignment]
    with pytest.raises(AssertionError):
        strat.on_bar(_bar(0), _empty_snapshot())


def test_duplicate_name_rejected_in_init_without_prepare() -> None:
    """Review R1 Warning #3: name uniqueness は __init__ で強制 (prepare 不要)。
    unprepared (paper trading) path も含めて守られる。"""
    ev = RegistryEvaluator(pair="USD_JPY")
    dup_sig_a = SignalConfig(
        name="F1", weight=1.0, params={"fast_n": 5, "slow_n": 20, "atr_n": 10}
    )
    dup_sig_b = SignalConfig(
        name="F1", weight=0.5, params={"fast_n": 3, "slow_n": 15, "atr_n": 7}
    )
    genome = Genome(
        name="g_dup_init",
        units=10000,
        clauses=(
            ClauseConfig(
                directional=(dup_sig_a, dup_sig_b),
                local_gate=(),
                weight=1.0,
            ),
        ),
        position=PositionConfig(0.1, 0.05, 1, 0),
        risk=RiskConfig(2.0, 3.0),
    )
    with pytest.raises(ValueError, match="duplicate signal.name"):
        DslStrategy(genome, ev)


def _genome_negative_entry() -> Genome:
    """entry_threshold が負 (-0.1) の genome。NaN fallback か NaN 伝播かを
    明確に識別するため使う (Review R2 Warning 対応)。

    composite=0.0 なら composite >= -0.1 が True → open_long 発生。
    composite=NaN なら NaN >= -0.1 は False → signal 空。
    """
    return Genome(
        name="g_neg_entry",
        units=10000,
        clauses=(
            ClauseConfig(
                directional=(
                    SignalConfig(
                        name="F1", weight=1.0,
                        params={"fast_n": 5, "slow_n": 20, "atr_n": 10},
                    ),
                ),
                local_gate=(),
                weight=1.0,
            ),
        ),
        position=PositionConfig(
            entry_threshold=-0.1, exit_threshold=-0.2,
            max_pos=1, time_stop_min=0,
        ),
        risk=RiskConfig(stop_atr=2.0, take_atr=3.0),
    )


def test_prepared_path_nan_falls_back_to_zero() -> None:
    """warmup 期 (NaN) で prepared path が 0.0 fallback (NaN 伝播ではない)
    を検証。NaN 伝播だと composite=NaN で `NaN >= -0.1` が False になり
    signal が発生しないが、0.0 fallback なら `0.0 >= -0.1` で open_long が
    発生する (Review R2 Warning 対応: 識別力を強化)。"""
    ev = RegistryEvaluator(pair="USD_JPY")
    strat = DslStrategy(_genome_negative_entry(), ev)
    bars = [_bar(i) for i in range(30)]
    strat.prepare(bars)
    p = strat._prepared
    assert p is not None
    arr = p.clauses[0][0][0][1]
    # warmup 領域は NaN
    assert np.isnan(arr[0])
    # on_bar は NaN を 0.0 に fallback するため、composite=0.0 で
    # open_long が発生する (entry_threshold=-0.1 < 0.0)
    signals = strat.on_bar(bars[0], _empty_snapshot())
    assert len(signals) == 1
    assert signals[0].kind == "open_long"


def test_signal_config_params_immutable() -> None:
    """施策 0: MappingProxyType で sig.params mutation が TypeError になる."""
    sig = SignalConfig(
        name="F1", weight=1.0, params={"fast_n": 5, "slow_n": 20, "atr_n": 10}
    )
    with pytest.raises(TypeError):
        sig.params["fast_n"] = 999  # type: ignore[index]


def _empty_snapshot():
    """空の PortfolioSnapshot fixture (cash / equity 1M、positions なし)。"""
    from src.broker.orders import PortfolioSnapshot
    return PortfolioSnapshot(
        cash=Decimal("1000000"),
        equity=Decimal("1000000"),
        margin_used=Decimal(0),
        margin_level_pct=None,
        positions=(),
    )


def test_prepare_noop_when_evaluator_lacks_evaluate_all_bars() -> None:
    """live feed evaluator は prepared state を作らない (paper trading 互換)."""

    class _LiveLikeEvaluator:
        def __init__(self):
            self._inner = RegistryEvaluator(pair="USD_JPY")

        def evaluate(self, bars_, idx, sig):
            return self._inner.evaluate(bars_, idx, sig)

    strat = DslStrategy(_genome_simple(), _LiveLikeEvaluator())
    strat.prepare([_bar(i) for i in range(100)])
    assert strat._prepared is None
```

### リスク
- 新規テスト fixture が既存 `_genome_simple` と重複する可能性。重複部分は conftest.py に吸収する選択肢もあるが、小規模なので本 TODO では local 定義

## 施策 3: 既存 test_engine_prepare.py の追従

### 変更箇所
`tests/backtest/test_engine_prepare.py`

### 波及変更
- AGENTS.md / skills / config / docs: 不要

### 現行コード（該当箇所）

```python
# tests/backtest/test_engine_prepare.py:115-131
    # prepare 経路が使われたことを確認
    assert strat_fast._precomputed is not None
    assert strat_slow._precomputed is None
```

### 変更後コード

```python
    # prepare 経路が使われたことを確認 (Cycle 2 / T029 で _prepared に移行)
    assert strat_fast._prepared is not None
    assert strat_slow._prepared is None
```

同様に `test_prepare_noop_when_evaluator_lacks_evaluate_all_bars` / `test_prepare_reuses_cache_across_duplicate_signals` 内の `_precomputed` 参照を `_prepared` に修正。重複共有の検証は `strat._prepared.arrays` の len を見る。

### リスク
- 低い（単純な attribute rename）

## 実装モード

| 項目 | 内容 |
|------|------|
| 推奨モード | incremental |
| 判断根拠 | `src/dsl/strategy.py` のみ本体変更、test 2 file の追加/修正。worktree で実装→review→merge の標準フロー |
| 競合リスク | 現在 main にアクティブな dsl/strategy 変更 TODO は無し。T028 (broker) が直前 merge だが領域独立 |
| 想定実装時間 | 短（本体 ~1h + test ~1.5h + Codex review ~30min = 合計 2-3h） |

## コミット計画

1. `feat(dsl): T029 flatten prepared signals cache (remove per-bar sorted)`
   - `src/dsl/strategy.py` 変更
   - `tests/dsl/test_dsl_strategy_flat_cache.py` 追加
   - `tests/backtest/test_engine_prepare.py` の attribute 追従

## Phase 7 検証手順

1. `profile-optimize` Phase 7 で EUR_JPY pop=8 gen=1 seed=42 14d の再プロファイル
2. `_signal_cache_key` + `_lookup_signal` 合計 tottime 削減率測定（target: `_signal_cache_key` 95%+ 削減）
3. RUN 全体時間の短縮率測定（target: 5%+）
4. `best_genome.fitness_pen` / Stage A/B/C pass counts が baseline (`profile_20260425_025427`) と bit-identical
5. INCONCLUSIVE ルール適用（n=1、target 達成なら PASS、未達なら Cycle 3 で複数 seed 再測）

## Round 1-2 Codex レビュー対応マップ

（conceptual-design.md §Round 1 Codex レビュー対応マップ + Round 2 Warning 対応を参照）
