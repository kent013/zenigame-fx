# Detailed Design: Genome Archive Schema (T015)

参照: [conceptual-design.md](./conceptual-design.md)

## 1. モジュール構成

### 1.1 新規ファイル

```
src/alpha_factory/archive.py             # GenomeArchive + GENOMES_SCHEMA
tests/alpha_factory/test_archive.py      # ユニットテスト
```

### 1.2 import 構成

```python
# src/alpha_factory/archive.py
from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, ClassVar, Literal, cast

import pyarrow as pa
import pyarrow.parquet as pq
import structlog

from src.alpha_factory.statistics import fold_sign_ratio
from src.alpha_factory.stage_gate import StageResult, CrossPairResult
from src.dsl.genome import Genome
from src.dsl.serialize import genome_to_dict
```

## 2. GENOMES_SCHEMA 定義

```python
GENOMES_SCHEMA: pa.Schema = pa.schema([
    pa.field("run_id", pa.string(), nullable=False),
    pa.field("run_number", pa.int32(), nullable=False),
    pa.field("generation", pa.int32(), nullable=False),
    pa.field("individual_name", pa.string(), nullable=False),
    pa.field("instrument", pa.string(), nullable=False),
    pa.field("lane_id", pa.string(), nullable=False),
    pa.field("parent_a", pa.string(), nullable=True),
    pa.field("parent_b", pa.string(), nullable=True),
    pa.field("genome_json", pa.string(), nullable=False),
    pa.field("fitness_raw", pa.float64(), nullable=False),
    pa.field("fitness_pen", pa.float64(), nullable=False),
    pa.field("stage_a_pass", pa.bool_(), nullable=False),
    pa.field("stage_b_pass", pa.bool_(), nullable=False),
    pa.field("stage_c_pass", pa.bool_(), nullable=False),
    pa.field("trade_count", pa.int32(), nullable=False),
    pa.field("total_pnl", pa.float64(), nullable=False),
    pa.field("sharpe", pa.float64(), nullable=True),
    pa.field("sortino", pa.float64(), nullable=True),
    pa.field("calmar", pa.float64(), nullable=True),
    pa.field("max_drawdown_pct", pa.float64(), nullable=False),
    pa.field("active_clause", pa.int32(), nullable=False),
    pa.field("n_nodes", pa.int32(), nullable=False),
    pa.field("bootstrap_ci_lower", pa.float64(), nullable=True),
    pa.field("bootstrap_ci_upper", pa.float64(), nullable=True),
    pa.field("fold_sign_ratio", pa.float64(), nullable=True),
    pa.field("dsr", pa.float64(), nullable=True),
    pa.field("ii_lite_pass", pa.bool_(), nullable=True),
    pa.field("graduated", pa.bool_(), nullable=False),
])

assert len(GENOMES_SCHEMA.names) == 28
```

## 3. _create_row_template

```python
def _create_row_template() -> dict[str, Any]:
    """GENOMES_SCHEMA 全カラムを default 値で初期化した dict を返す。

    nullable -> None、non-null bool -> False、non-null int -> 0、
    non-null float -> 0.0、non-null string -> "" を入れる。

    呼び出し元（collect_stage_X）が必須カラム（run_id / generation /
    individual_name / instrument / lane_id / genome_json）を上書きする。
    """
    return {
        "run_id": "",
        "run_number": 0,
        "generation": 0,
        "individual_name": "",
        "instrument": "",
        "lane_id": "",
        "parent_a": None,
        "parent_b": None,
        "genome_json": "",
        "fitness_raw": 0.0,
        "fitness_pen": 0.0,
        "stage_a_pass": False,
        "stage_b_pass": False,
        "stage_c_pass": False,
        "trade_count": 0,
        "total_pnl": 0.0,
        "sharpe": None,
        "sortino": None,
        "calmar": None,
        "max_drawdown_pct": 0.0,
        "active_clause": 0,
        "n_nodes": 0,
        "bootstrap_ci_lower": None,
        "bootstrap_ci_upper": None,
        "fold_sign_ratio": None,
        "dsr": None,
        "ii_lite_pass": None,
        "graduated": False,
    }
```

**整合性ガード**: モジュール直下で

```python
_TEMPLATE_KEYS = set(_create_row_template().keys())
_SCHEMA_NAMES = set(GENOMES_SCHEMA.names)
assert _TEMPLATE_KEYS == _SCHEMA_NAMES, (
    f"template missing {_SCHEMA_NAMES - _TEMPLATE_KEYS} / "
    f"extra {_TEMPLATE_KEYS - _SCHEMA_NAMES}"
)
```

import 時に乖離があれば即落ちる（4 段伝搬の dev-time guard）。

## 4. ステージ順序

```python
_STAGE_ORDER: dict[str, int] = {"": 0, "A": 1, "B": 2, "C": 3}
_MAX_STAGE_KEY = "_max_stage_seen"  # row dict 内の private field
```

`flush()` 直前に各 row から `pop(_MAX_STAGE_KEY, None)` で除去。

## 5. 構造指標

```python
def _compute_n_nodes(genome: Genome) -> int:
    """directional + local_gate の signal 合計数。"""
    return sum(len(c.directional) + len(c.local_gate) for c in genome.clauses)


def _compute_active_clause_placeholder() -> int:
    """**Phase 2 placeholder**: runtime 発火数取得経路が未整備のため 0 を返す。

    別 TODO で DslStrategy / engine から発火カウンタを取得する仕組みが
    実装されたら、collect_stage_a の引数に追加して上書きする。
    """
    return 0
```

`active_clause` の取得経路は **(b) placeholder 0** を選択
（理由: Stage A backtest を再実行する (a) 案はコスト過大。発火カウンタ
拡張は別 TODO に切り出す）。

## 6. payload 取り出しヘルパ (mypy 安全)

`StageResult.metrics` は `Mapping[str, object]` 型なので、`object` から
直接 `.get` を呼ぶと mypy エラーになる。次のヘルパ群で安全に narrow する:

```python
def _extract_payload(stage_result: StageResult) -> Mapping[str, object]:
    """StageResult.metrics["payload"] を Mapping[str, object] として返す。

    payload キーが無い・Mapping でない場合は空 dict を返す（defensive）。
    """
    payload_obj = stage_result.metrics.get("payload")
    if isinstance(payload_obj, Mapping):
        return cast(Mapping[str, object], payload_obj)
    return {}


def _opt_float(payload: Mapping[str, object], key: str) -> float | None:
    v = payload.get(key)
    if v is None:
        return None
    if isinstance(v, int | float):
        return float(v)
    return None  # 型不正は None 扱い (defensive)


def _opt_int(payload: Mapping[str, object], key: str) -> int | None:
    v = payload.get(key)
    if v is None:
        return None
    if isinstance(v, bool):
        return None  # bool は int サブクラスだが弾く
    if isinstance(v, int):
        return int(v)
    if isinstance(v, float):
        return int(v)
    return None


def _required_float(payload: Mapping[str, object], key: str, default: float = 0.0) -> float:
    v = _opt_float(payload, key)
    return v if v is not None else default


def _required_int(payload: Mapping[str, object], key: str, default: int = 0) -> int:
    v = _opt_int(payload, key)
    return v if v is not None else default


def _extract_oos_sharpes(payload: Mapping[str, object]) -> list[float] | None:
    """payload["oos_sharpes"] を list[float] として取り出す."""
    v = payload.get("oos_sharpes")
    if v is None:
        return None
    if not isinstance(v, list | tuple):
        return None
    out: list[float] = []
    for x in v:
        if isinstance(x, int | float):
            out.append(float(x))
        else:
            return None
    return out


def _extract_cross_pair(
    payload: Mapping[str, object],
) -> tuple[bool, CrossPairResult | None]:
    """payload["cross_pair"] から (skipped, result) を取り出す."""
    cp_obj = payload.get("cross_pair")
    if not isinstance(cp_obj, Mapping):
        return True, None
    cp = cast(Mapping[str, object], cp_obj)
    skipped = bool(cp.get("skipped", True))
    result_obj = cp.get("result")
    if isinstance(result_obj, CrossPairResult):
        return skipped, result_obj
    return skipped, None
```

## 7. GenomeArchive クラス本体

```python
logger = structlog.get_logger(__name__)


@dataclass
class GenomeArchive:
    """1 Run 分の Genome 評価結果を buffering して Parquet に flush する。

    主キー: (generation, individual_name)
    重複 collect ポリシー: monotonic enrich (詳細は conceptual-design §D)
    """

    run_id: str
    run_number: int

    # 主キー: (lane_id, generation, individual_name)
    # - lane_id を含めることで multi-lane (Tier 1 各 instrument + Graduation) で
    #   個体名が衝突しても別 row として記録される
    _rows: dict[tuple[str, int, str], dict[str, Any]] = field(
        default_factory=dict, init=False, repr=False
    )

    DEFAULT_OUTPUT_DIR: ClassVar[Path] = Path(".cache/alpha_factory/runs")

    # ---- public API ----

    def collect_stage_a(
        self,
        genome: Genome,
        lane_id: str,
        generation: int,
        stage_result: StageResult,
        *,
        instrument: str,
        parent_a: str | None = None,
        parent_b: str | None = None,
    ) -> None:
        if stage_result.stage != "A":
            raise ValueError(
                f"collect_stage_a expected stage='A', got {stage_result.stage!r}"
            )
        key = (lane_id, generation, genome.name)
        if not self._allow_collect(key, "A"):
            return  # regression ignored

        row = self._rows.setdefault(key, self._new_row(
            generation, genome, instrument, lane_id, parent_a, parent_b,
        ))
        # setdefault 直後の row は新規時のみ反映、既存時は維持
        payload = _extract_payload(stage_result)
        row["fitness_raw"] = _required_float(payload, "fitness_raw")
        row["fitness_pen"] = _required_float(payload, "fitness_pen")
        row["stage_a_pass"] = bool(stage_result.passed)
        row["trade_count"] = _required_int(payload, "trade_count")
        row["sharpe"] = _opt_float(payload, "sharpe_raw")
        row["n_nodes"] = _compute_n_nodes(genome)
        row["active_clause"] = _compute_active_clause_placeholder()
        row["genome_json"] = json.dumps(genome_to_dict(genome), sort_keys=True)
        self._mark_stage(row, "A", key)

    def collect_stage_b(
        self,
        genome: Genome,
        lane_id: str,
        generation: int,
        stage_result: StageResult,
        *,
        instrument: str | None = None,
    ) -> None:
        if stage_result.stage != "B":
            raise ValueError(
                f"collect_stage_b expected stage='B', got {stage_result.stage!r}"
            )
        key = (lane_id, generation, genome.name)
        if not self._allow_collect(key, "B"):
            return

        if key not in self._rows:
            # Stage B が初回 collect の場合は instrument 必須
            if not instrument:
                raise ValueError(
                    f"instrument is required for new row at {key} (Stage B first)"
                )
        row = self._rows.setdefault(key, self._new_row(
            generation, genome,
            instrument=instrument or "", lane_id=lane_id,
        ))
        payload = _extract_payload(stage_result)
        row["stage_b_pass"] = bool(stage_result.passed)

        oos = _extract_oos_sharpes(payload)
        if oos is None or len(oos) == 0:
            row["fold_sign_ratio"] = None
        else:
            row["fold_sign_ratio"] = float(fold_sign_ratio(oos))

        row["dsr"] = _opt_float(payload, "dsr")
        is_sharpe = _opt_float(payload, "is_full_sharpe")
        if is_sharpe is not None:
            row["sharpe"] = is_sharpe
        is_pnl = _opt_float(payload, "is_full_total_pnl")
        if is_pnl is not None:
            row["total_pnl"] = is_pnl
        is_tc = _opt_int(payload, "is_full_trade_count")
        if is_tc is not None:
            row["trade_count"] = is_tc
        # bootstrap_ci_lower/upper は本 TODO スコープ外 → None のまま
        self._mark_stage(row, "B", key)

    def collect_stage_c(
        self,
        genome: Genome,
        lane_id: str,
        generation: int,
        stage_result: StageResult,
        *,
        instrument: str | None = None,
    ) -> None:
        if stage_result.stage != "C":
            raise ValueError(
                f"collect_stage_c expected stage='C', got {stage_result.stage!r}"
            )
        key = (lane_id, generation, genome.name)
        if not self._allow_collect(key, "C"):
            return

        if key not in self._rows:
            if not instrument:
                raise ValueError(
                    f"instrument is required for new row at {key} (Stage C first)"
                )
        row = self._rows.setdefault(key, self._new_row(
            generation, genome,
            instrument=instrument or "", lane_id=lane_id,
        ))
        payload = _extract_payload(stage_result)
        row["stage_c_pass"] = bool(stage_result.passed)

        sharpe = _opt_float(payload, "sharpe")
        if sharpe is not None:
            row["sharpe"] = sharpe
        total_pnl = _opt_float(payload, "total_pnl")
        if total_pnl is not None:
            row["total_pnl"] = total_pnl
        max_dd_frac = _opt_float(payload, "max_drawdown_frac")
        if max_dd_frac is not None:
            row["max_drawdown_pct"] = max_dd_frac * 100.0
        tc = _opt_int(payload, "trade_count")
        if tc is not None:
            row["trade_count"] = tc

        # ii_lite_pass は cross_pair payload から導出
        skipped, cp_result = _extract_cross_pair(payload)
        if skipped or cp_result is None:
            row["ii_lite_pass"] = None
        else:
            row["ii_lite_pass"] = bool(cp_result.passed)
        self._mark_stage(row, "C", key)

    def mark_graduated(
        self, lane_id: str, generation: int, individual_name: str
    ) -> None:
        key = (lane_id, generation, individual_name)
        if key not in self._rows:
            raise KeyError(
                f"individual not in archive: lane_id={lane_id!r}, "
                f"generation={generation}, name={individual_name!r}"
            )
        self._rows[key]["graduated"] = True

    def flush(self, output_dir: Path | None = None) -> Path:
        out_dir = Path(output_dir) if output_dir is not None else self.DEFAULT_OUTPUT_DIR
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f"genomes_{self.run_id}.parquet"

        # _max_stage_seen を除外して flat row を生成 + last-mile guard
        schema_names = set(GENOMES_SCHEMA.names)
        clean_rows: list[dict[str, Any]] = []
        for key, row in self._rows.items():
            cr = {k: v for k, v in row.items() if k != _MAX_STAGE_KEY}
            cr_keys = set(cr.keys())
            if cr_keys != schema_names:
                missing = schema_names - cr_keys
                extra = cr_keys - schema_names
                raise ValueError(
                    f"row keys mismatch for key={key}: "
                    f"missing={sorted(missing)} extra={sorted(extra)}"
                )
            clean_rows.append(cr)

        table = pa.Table.from_pylist(clean_rows, schema=GENOMES_SCHEMA)
        pq.write_table(table, path)
        return path

    @staticmethod
    def load(parquet_path: Path) -> pa.Table:
        return pq.read_table(parquet_path)

    # ---- internals ----

    def _new_row(
        self,
        generation: int,
        genome: Genome,
        instrument: str,
        lane_id: str,
        parent_a: str | None = None,
        parent_b: str | None = None,
    ) -> dict[str, Any]:
        row = _create_row_template()
        row["run_id"] = self.run_id
        row["run_number"] = int(self.run_number)
        row["generation"] = int(generation)
        row["individual_name"] = genome.name
        row["instrument"] = instrument
        row["lane_id"] = lane_id
        row["parent_a"] = parent_a
        row["parent_b"] = parent_b
        row[_MAX_STAGE_KEY] = ""  # 未着手
        return row

    def _allow_collect(
        self, key: tuple[str, int, str], incoming: str
    ) -> bool:
        """monotonic enrich 判定。前段への逆流は warn + no-op."""
        existing = self._rows.get(key)
        if existing is None:
            return True
        prev = existing.get(_MAX_STAGE_KEY, "")
        if _STAGE_ORDER[incoming] < _STAGE_ORDER[prev]:
            logger.warning(
                "archive.stage_regression_ignored",
                lane_id=key[0],
                generation=key[1],
                individual_name=key[2],
                incoming=incoming,
                prev=prev,
            )
            return False
        if _STAGE_ORDER[incoming] == _STAGE_ORDER[prev]:
            logger.warning(
                "archive.same_stage_recollect",
                lane_id=key[0],
                generation=key[1],
                individual_name=key[2],
                stage=incoming,
            )
        return True

    def _mark_stage(
        self, row: dict[str, Any], incoming: str, key: tuple[str, int, str]
    ) -> None:
        prev = row.get(_MAX_STAGE_KEY, "")
        if _STAGE_ORDER[incoming] > _STAGE_ORDER[prev]:
            row[_MAX_STAGE_KEY] = incoming
```

## 7. Parquet 書き出し詳細

- `pa.Table.from_pylist(rows, schema=GENOMES_SCHEMA)` で型強制
  - schema 不一致のキーが row dict にあれば pyarrow が `ArrowInvalid`
  - これにより 4 段伝搬の last-mile guard
- `pq.write_table(table, path)` — compression は default (`snappy`)
- 出力先 default: `Path(".cache/alpha_factory/runs/")` （CWD 相対）
  - テストは tmp_path で書き出すため副作用なし

## 8. テスト設計

### 8.1 fixtures

```python
import pytest
import pyarrow as pa
from src.alpha_factory.archive import (
    GENOMES_SCHEMA, GenomeArchive, _create_row_template,
)
from src.alpha_factory.stage_gate import StageResult


def _stub_genome(name: str = "g0_i0") -> Genome:
    """最小構造の Genome (1 clause × 1 directional × 0 gate)."""
    sig = SignalConfig(name="F1", weight=1.0, params={})
    clause = ClauseConfig(directional=(sig,), local_gate=(), weight=1.0)
    return Genome(
        name=name,
        units=1,
        clauses=(clause,),
        position=PositionConfig(
            entry_threshold=0.5, exit_threshold=0.2, max_pos=1, time_stop_min=0,
        ),
        risk=RiskConfig(stop_atr=1.0, take_atr=2.0),
    )


def _stage_a_result(passed: bool = True, **payload_overrides) -> StageResult:
    payload = {
        "fitness_raw": 0.3,
        "fitness_pen": 0.27,
        "size_norm": 0.1,
        "alpha_a": 0.03,
        "threshold": 0.0,
        "trade_count": 25,
        "sharpe_raw": 0.3,
    }
    payload.update(payload_overrides)
    return StageResult(
        stage="A", passed=passed,
        metrics={"stage": "A", "genome_name": "g0_i0", "n_bars": 60,
                 "wall_time_seconds": 0.1, "payload": payload},
    )


def _stage_b_result(passed: bool = True, **payload_overrides) -> StageResult:
    payload = {
        "n_fold": 5, "n_fold_unavailable": 0,
        "oos_sharpes": (0.1, -0.2, 0.3, -0.1, 0.4),
        "median_oos_sharpe": 0.1, "positive_fold_ratio": 0.6,
        "dsr": None, "is_full_sharpe": 0.5, "is_full_total_pnl": 12000.0,
        "is_full_trade_count": 200,
    }
    payload.update(payload_overrides)
    return StageResult(
        stage="B", passed=passed,
        metrics={"stage": "B", "genome_name": "g0_i0", "n_bars": 7000,
                 "wall_time_seconds": 1.2, "payload": payload},
    )


def _stage_c_result(passed: bool = True, cross_pair_skipped: bool = True,
                    cross_pair_passed: bool | None = None) -> StageResult:
    cp = {"skipped": True, "result": None}
    if not cross_pair_skipped:
        cp["skipped"] = False
        cp["result"] = CrossPairResult(
            target_pair="USD_JPY", anchor_pairs=("EUR_JPY", "AUD_JPY"),
            aggregator_name="median",
            window=(datetime(2026, 1, 1), datetime(2026, 2, 1)),
            passed=bool(cross_pair_passed), metrics={}, reason_codes=(),
        )
    payload = {
        "sharpe": 1.2, "total_pnl": 60000.0,
        "max_drawdown_frac": 0.15, "trade_count": 80,
        "live_criteria_pass": {}, "intraday_compliant": True,
        "overnight_violations": 0, "stress": {"skipped": False},
        "cross_pair": cp,
    }
    return StageResult(
        stage="C", passed=passed,
        metrics={"stage": "C", "genome_name": "g0_i0", "n_bars": 1500,
                 "wall_time_seconds": 0.8, "payload": payload},
    )
```

### 8.2 テストケース一覧

| # | テスト名 | 検証内容 |
|---|---------|---------|
| 1 | `test_schema_has_28_columns` | `len(GENOMES_SCHEMA.names) == 28` および全カラム名 |
| 2 | `test_template_matches_schema_keys` | `set(template.keys()) == set(SCHEMA.names)` |
| 3 | `test_template_default_values` | 各カラムの default 値（None / 0 / False / ""） |
| 4 | `test_collect_stage_a_partial_fill` | Stage A 適用後の row 内容 |
| 5 | `test_collect_stage_a_n_nodes_computed` | `_compute_n_nodes` の正しさ |
| 6 | `test_collect_stage_a_active_clause_placeholder` | 0 が入る |
| 7 | `test_collect_stage_a_genome_json_roundtrip` | json.loads で genome_to_dict() に戻る |
| 8 | `test_collect_stage_b_updates_overrides_sharpe_pnl_tc` | A→B で上書き |
| 9 | `test_collect_stage_b_fold_sign_ratio_from_oos_sharpes` | fold_sign_ratio() 実値 |
| 10 | `test_collect_stage_b_no_oos_sharpes_yields_none` | None |
| 11 | `test_collect_stage_c_max_drawdown_pct_x100` | 0.15 → 15.0 |
| 12 | `test_collect_stage_c_ii_lite_pass_skipped` | None |
| 13 | `test_collect_stage_c_ii_lite_pass_true` | True |
| 14 | `test_collect_stage_c_ii_lite_pass_false` | False |
| 15 | `test_mark_graduated_sets_flag` | True |
| 16 | `test_mark_graduated_unknown_individual_raises` | KeyError |
| 17 | `test_flush_creates_parquet_file` | tmp_path で path が返る |
| 18 | `test_flush_load_roundtrip` | load → 同一値 |
| 19 | `test_flush_excludes_max_stage_seen` | "_max_stage_seen" カラムが Parquet に無い |
| 20 | `test_same_stage_recollect_overwrites_with_warn` | A→A で warn + 上書き |
| 21 | `test_stage_regression_ignored_with_warn` | B→A で warn + B 値が保持される |
| 22 | `test_stage_enrich_progresses` | A→B→C 累積、最終状態が正しい |
| 23 | `test_composite_key_separates_generations` | 同 individual_name 異 generation は別 row |
| 23a | `test_composite_key_separates_lanes` | 同 individual_name × 同 generation でも lane_id 違いは別 row |
| 23b | `test_collect_stage_b_new_row_requires_instrument` | 既存行なし + instrument=None で ValueError |
| 23c | `test_collect_stage_c_new_row_requires_instrument` | 同上 |
| 23d | `test_mark_graduated_takes_lane_id` | mark_graduated(lane_id, gen, name) で対応行のみ True |
| 24 | `test_collect_stage_a_wrong_stage_raises` | stage='B' を渡すと ValueError |
| 25 | `test_collect_stage_b_wrong_stage_raises` | stage='A' / 'C' を渡すと ValueError |
| 26 | `test_collect_stage_c_wrong_stage_raises` | stage='A' / 'B' を渡すと ValueError |
| 27 | `test_payload_missing_keys_defensive_get` | payload={} で例外なく default 値が入る |
| 28 | `test_cross_pair_result_invalid_type_yields_none` | result が CrossPairResult でない型なら ii_lite_pass=None |
| 29 | `test_oos_sharpes_invalid_element_type_yields_none` | oos_sharpes に str が混ざると fold_sign_ratio=None |
| 30 | `test_flush_extra_key_in_row_raises` | row dict に schema 外キーがあると ValueError |

WARN ログ確認は `caplog`（structlog 経由なら `structlog.testing.capture_logs`）。

### 8.3 caplog で structlog を捕捉

```python
from structlog.testing import capture_logs

def test_stage_regression_ignored_with_warn():
    arc = GenomeArchive(run_id="run_test", run_number=1)
    g = _stub_genome()
    arc.collect_stage_b(g, "tier1_USD_JPY", 0, _stage_b_result(),
                         instrument="USD_JPY")
    with capture_logs() as logs:
        arc.collect_stage_a(g, "tier1_USD_JPY", 0, _stage_a_result(),
                            instrument="USD_JPY")
    assert any(
        log["event"] == "archive.stage_regression_ignored" for log in logs
    )
    # B 値が保持されている
    row = arc._rows[(0, "g0_i0")]
    assert row["sharpe"] == pytest.approx(0.5)  # B の is_full_sharpe
```

## 9. pyproject.toml / uv.lock

```toml
# [project] dependencies に追加
"pyarrow>=15.0",
```

`uv add pyarrow` で `uv.lock` も更新（PR 内に含める）。

## 10. mypy / ruff 対応

- 型 import: `from typing import Any, ClassVar, Literal`
- pyarrow は `[tool.mypy] ignore_missing_imports = true` で stub 不在を許容済み
- `_create_row_template` は dict literal のため型推論問題なし
- `pa.Table.from_pylist` の戻り型は `Any` 扱い（mypy strict=False 設定）

## 11. ドキュメント更新計画 (step G)

1. `docs/alpha_factory/concepts/genome-archive-schema.md`
   - `active_clause`: 「Phase 2 placeholder=0、別 TODO で発火カウンタ実装」を追記
   - `fold_sign_ratio`: 「`statistics.fold_sign_ratio(oos_sharpes)` 実値計算」を追記
   - 列意味論 SSOT 移管（本 docs を SSOT 化、devnotes は historical）

2. `docs/alpha_factory/clause-architecture.md` 末尾に
   「## Genome Archive (T015)」節を追加:
   - GENOMES_SCHEMA 概観、4 段伝搬契約、monotonic enrich
   - 詳細は archive.md（新規） or schema doc 参照

3. `docs/alpha_factory/terminology.md` に追加:
   - `GenomeArchive`
   - `GENOMES_SCHEMA`
   - `monotonic enrich`

## 12. 受け入れ条件再掲

- GENOMES_SCHEMA 28 カラム + nullable 設定
- `_create_row_template()` ↔ schema 完全一致 (assert + test)
- collect_stage_a/b/c 実装、StageResult.metrics["payload"] から正しく抽出
- 重複 collect monotonic enrich (regression ignored, recollect warn+override)
- mark_graduated, flush, load OK
- 全テスト pass、mypy / ruff クリーン
- pyarrow 依存追加、uv.lock 更新
- docs / terminology / schema doc 更新
