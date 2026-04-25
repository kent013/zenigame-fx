# 詳細設計: cost-pnl-ledger-eventsource (Stage A 記録整合性監査 — sidecar 版)

## 使命・制約 (絶対遵守)

### zenigame-fx Alpha Factory 使命
live_criteria 全指標同時充足 + (ii-lite) 通過で使命達成。
絶対制約: イントラデイ / ロング・ショート両方向 / スワップ・スプレッド反映。

### 禁止事項
1. A・B・C 評価期間を根拠なしに延長
2. 見た目の数値改善
3. GA ハック
4. live_criteria 緩和
5. 過度な複雑化
6. 取引回数削減で成績を見せる
7. オーバーナイト保有前提

### コーディングルール
- バグ修正はテストファースト
- 全施策にテスト必須
- テスト命名: 振る舞いを説明する汎用名
- uv 必須: `uv run pytest tests/alpha_factory/`
- ruff / mypy 通過: `uv run ruff check src/ tests/` / `uv run mypy src/`
- Python 3.13 + numpy + pandas

## 概念設計リファレンス

`devnotes/20260425-0937-cost-pnl-ledger-eventsource/conceptual-design.md` (Round 4 APPROVED)

## 施策一覧

| # | 施策名 | 変更ファイル | 優先度 |
|---|--------|------------|--------|
| 1 | DiagnosticsCollector 新設 | 新規 `src/alpha_factory/diagnostics_collector.py` | High |
| 2 | Stage A payload に total_pnl/sharpe 追加 | `src/alpha_factory/stage_gate.py` | High |
| 3 | swim_lane で collector に StageResult 投入 | `src/alpha_factory/swim_lane.py` | High |
| 4 | sidecar writer (Parquet) 新設 | 新規 `src/alpha_factory/diagnostics_sidecar.py` | High |
| 5 | run_ga.py で collector 生成 + flush | `scripts/alpha_factory/run_ga.py` | High |
| 6 | run-report skill に固定セクション追加 | `.claude/skills/zenigame-fx-run-report/SKILL.md` + `scripts/alpha_factory/generate_run_report.py` | Medium |
| 7 | テスト 2 件追加 | 新規 `tests/alpha_factory/test_diagnostics_collector.py`, `test_diagnostics_sidecar.py` | High |

---

## 施策 1: DiagnosticsCollector 新設

### 変更箇所
- 新規: `src/alpha_factory/diagnostics_collector.py`

### 波及変更
- `AGENTS.md`: なし (内部 API、外部インターフェース変更なし)
- skill: なし
- `config/alpha_factory/default.yaml`: なし
- `docs/alpha_factory/*.md`: 後追いで `concepts/diagnostics-sidecar.md` を新規作成 (本詳細設計の補足、運用後)

### import 規約注記 (Round 1 Critical 対応)
- 全 import は `from src.alpha_factory.*` 形式で統一する (`from alpha_factory.*` は使わない)
- これは本設計書の全コードサンプルで遵守済み (`from src.alpha_factory.stage_gate import StageResult` 等)

### 実装内容

```python
"""Per-individual diagnostics collector for sidecar emission.

Stage A/B/C 評価結果を generation 中に蓄積し、GA 完了時に sidecar Parquet として
flush する。production GA 経路から fail-open で利用される。
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Optional

from src.alpha_factory.stage_gate import StageResult

# metric_stage の解釈: 「到達した最高通過段」を表す (pass-based)
# stage_a_only   = Stage A 不通過 (または Stage B/C 未評価)
# stage_a_evaluated = Stage A 通過 (Stage B 未評価)
# stage_b_evaluated = Stage B 通過 (Stage C 未評価)
# stage_c_evaluated = Stage C 通過
# Round 1 Warning 対応: 命名が「到達段=通過段」ベースであることを明記 (仕様として採用)
_VALID_METRIC_STAGES = {
    "stage_a_only",
    "stage_a_evaluated",
    "stage_b_evaluated",
    "stage_c_evaluated",
}


@dataclass
class IndividualDiagnostics:
    """Per-individual diagnostics record (mutable during a generation)."""

    lane_id: str
    generation: int
    individual_name: str
    trade_count: int = 0
    total_pnl_stage_a: float = 0.0
    sharpe_stage_a: Optional[float] = None
    stage_a_pass: bool = False
    stage_b_pass: Optional[bool] = None  # None = not evaluated
    stage_c_pass: Optional[bool] = None  # None = not evaluated


class DiagnosticsCollector:
    """In-memory collector for per-individual stage diagnostics.

    Lifecycle:
    - Created in run_ga.py with run-level scope
    - Updated by swim_lane after each StageResult is produced
    - Flushed to Parquet sidecar at GA completion
    """

    def __init__(self) -> None:
        self._records: dict[tuple[str, int, str], IndividualDiagnostics] = {}

    def _key(self, lane_id: str, generation: int, individual_name: str) -> tuple[str, int, str]:
        return (lane_id, generation, individual_name)

    def record_stage_a(
        self,
        lane_id: str,
        generation: int,
        individual_name: str,
        result: StageResult,
    ) -> None:
        """Record Stage A result. Idempotent on duplicate keys (last write wins)."""
        payload = result.metrics.get("payload", {}) if hasattr(result, "metrics") else {}
        # Defensive read: payload may lack new fields if older code path
        trade_count = int(payload.get("trade_count", 0))
        total_pnl = float(payload.get("total_pnl", 0.0))
        sharpe_raw = payload.get("sharpe_raw")
        sharpe_stage_a = (
            float(sharpe_raw) if sharpe_raw is not None and math.isfinite(float(sharpe_raw)) else None
        )
        if not math.isfinite(total_pnl):
            total_pnl = 0.0
        self._records[self._key(lane_id, generation, individual_name)] = IndividualDiagnostics(
            lane_id=lane_id,
            generation=generation,
            individual_name=individual_name,
            trade_count=trade_count,
            total_pnl_stage_a=total_pnl,
            sharpe_stage_a=sharpe_stage_a,
            stage_a_pass=bool(result.passed),
        )

    def record_stage_b(
        self, lane_id: str, generation: int, individual_name: str, passed: bool
    ) -> None:
        """Record Stage B pass/fail. No-op if Stage A wasn't recorded (defensive)."""
        rec = self._records.get(self._key(lane_id, generation, individual_name))
        if rec is None:
            return
        rec.stage_b_pass = bool(passed)

    def record_stage_c(
        self, lane_id: str, generation: int, individual_name: str, passed: bool
    ) -> None:
        """Record Stage C pass/fail. No-op if Stage A wasn't recorded (defensive)."""
        rec = self._records.get(self._key(lane_id, generation, individual_name))
        if rec is None:
            return
        rec.stage_c_pass = bool(passed)

    def derive_metric_stage(self, rec: IndividualDiagnostics) -> str:
        """Post-hoc metric_stage derivation."""
        if rec.stage_c_pass is True:
            return "stage_c_evaluated"
        if rec.stage_b_pass is True:
            return "stage_b_evaluated"
        if rec.stage_a_pass:
            return "stage_a_evaluated"
        return "stage_a_only"

    def to_rows(self) -> list[dict[str, Any]]:
        """Materialize records as plain dicts for Parquet writing."""
        rows: list[dict[str, Any]] = []
        for rec in self._records.values():
            metric_stage = self.derive_metric_stage(rec)
            assert metric_stage in _VALID_METRIC_STAGES  # CI invariant I2
            rows.append(
                {
                    "lane_id": rec.lane_id,
                    "generation": rec.generation,
                    "individual_name": rec.individual_name,
                    "metric_stage": metric_stage,
                    "trade_count": rec.trade_count,
                    "total_pnl_stage_a": rec.total_pnl_stage_a,
                    "sharpe_stage_a": rec.sharpe_stage_a,
                    "stage_a_pass": rec.stage_a_pass,
                    "stage_b_pass": rec.stage_b_pass,
                    "stage_c_pass": rec.stage_c_pass,
                }
            )
        return rows

    def __len__(self) -> int:
        return len(self._records)
```

### ルックアヘッドバイアスチェック
- N/A (primitive 変更ではない、純粋に diagnostics 蓄積)

### パフォーマンスチェック
- メモリ: 個体数 (典型 120) × dataclass 1 個 (約 100 bytes) ≪ 1MB、24GB / 6 worker 制約に十分収まる
- 計算: 各 record は O(1)、derive は flush 時のみ O(N)

### テスト計画
- 新規 `tests/alpha_factory/test_diagnostics_collector.py`:
  - `test_collector_records_stage_a_payload`: Stage A payload から正しく値が抽出される
  - `test_collector_metric_stage_derivation_order`: stage_c > stage_b > stage_a_evaluated > stage_a_only の順
  - `test_collector_handles_missing_payload_fields`: 旧 payload 形式でも crash しない
  - `test_collector_idempotent_on_duplicate_key`: 同一キー再記録で last-write-wins
  - `test_collector_handles_nonfinite_total_pnl`: NaN/Inf を 0.0 に正規化
  - `test_record_stage_b_noop_without_stage_a`: 防御的 no-op

### リスク
- collector は in-memory のみのため、worker 間 (multiprocessing) で共有できない場合は worker-local collector を main process に集約する経路が必要 → 施策 5 で対処

---

## 施策 2: Stage A payload に total_pnl/sharpe 追加

### 変更箇所
- `src/alpha_factory/stage_gate.py` (L325-333)

### 波及変更
- `AGENTS.md`: なし
- skill: なし
- 既存テスト: `tests/alpha_factory/test_stage_gate.py` の Stage A payload 確認テストに `total_pnl` 追加

### 現行コード (L320-334)

```python
metrics_envelope: dict[str, object] = {
    "stage": "A",
    "genome_name": genome.name,
    "n_bars": len(bars_60d),
    "wall_time_seconds": elapsed,
    "payload": {
        "fitness_raw": fitness_raw,
        "size_norm": size_norm_val,
        "fitness_pen": fitness_pen,
        "alpha_a": stage_config.stage_a_alpha,
        "threshold": stage_config.stage_a_threshold,
        "trade_count": trade_count,
        "sharpe_raw": sharpe_raw,
    },
}
```

### 変更後コード (Round 1 Warning 対応: backtest 例外と size_norm 例外を分離)

```python
# Stage A backtest 内で算出済みの total_pnl を payload に格納 (sidecar diagnostics 用)
# bt は backtest 例外経路では未定義のため、bt 取得成否を独立フラグで管理する
# (Round 1 Warning: exception_caught は size_norm 例外でも立つため、
#  backtest 成功時は size_norm 例外と関わらず total_pnl を保持)
total_pnl_a: float = 0.0
if bt is not None:  # bt = None は backtest 例外時のみ (size_norm 例外とは独立)
    try:
        total_pnl_a = float(bt.total_pnl)
    except Exception:
        total_pnl_a = 0.0

metrics_envelope: dict[str, object] = {
    "stage": "A",
    "genome_name": genome.name,
    "n_bars": len(bars_60d),
    "wall_time_seconds": elapsed,
    "payload": {
        "fitness_raw": fitness_raw,
        "size_norm": size_norm_val,
        "fitness_pen": fitness_pen,
        "alpha_a": stage_config.stage_a_alpha,
        "threshold": stage_config.stage_a_threshold,
        "trade_count": trade_count,
        "sharpe_raw": sharpe_raw,
        # Round 4 添加: sidecar diagnostics 用 (in-memory only、archive には書かない)
        "total_pnl": total_pnl_a,
    },
}
```

### 実装上の注意
- `bt` は `compute_metrics(result.trades, result.equity_curve)` の戻り値で、`total_pnl` 属性を持つ (`src/backtest/metrics.py#L85-L89` 参照)
- **`bt is not None` で判定する** (backtest 例外時は `bt = None` 初期化される実装を前提)。`exception_caught` ではなく `bt` の有無で判定することで、size_norm 例外時でも backtest が成功していれば total_pnl を保持できる (Round 1 Warning 対応)
- 既存判定ロジック (`fitness_pen <= threshold`) は完全に不変

### ルックアヘッドバイアスチェック
- N/A (Stage A backtest 結果の集計値を payload にコピーするだけ)

### テスト計画
- 既存 Stage A テストの payload assert に `total_pnl` キーが存在することを追加 (値は固定でも fixture 不要)
- 新規 `test_stage_a_payload_includes_total_pnl_on_success`
- 新規 `test_stage_a_payload_total_pnl_zero_on_exception`

### リスク
- `bt.total_pnl` の dtype が float32 などの場合 `float()` 変換で精度落ち → 既存 metrics 経路で float64 想定なので影響なし

---

## 施策 3: swim_lane で collector に StageResult 投入

### 変更箇所
- `src/alpha_factory/swim_lane.py` の Tier1 lane `_run_tier1_generation` (L308-) と Stage A/B/C evaluate 呼び出し直後

### 波及変更
- `AGENTS.md`: なし (内部実装)
- skill: なし

### generation_count 属性注記 (Round 1 Critical 対応)
- `lane.generation_count` を使用する (`self._generation_count` は swim_lane に存在しない)
- 実装者は `swim_lane.py` の `_run_tier1_generation` スコープ内の `lane` オブジェクトの属性を使用すること
- 本設計書のコードサンプルはすでに `lane.generation_count` を正しく使用している

### 呼び出し元・テスト更新対象 (Round 1 Warning 対応)

`run_generation` に `diagnostics_collector` 引数を追加するため、以下のファイルが影響を受ける:

| ファイル | 変更内容 |
|----------|---------|
| `src/alpha_factory/swim_lane.py` | `run_generation` シグネチャに `diagnostics_collector: DiagnosticsCollector | None = None` を追加 |
| `tests/alpha_factory/test_swim_lane.py` | 既存テストに `diagnostics_collector=None` の後方互換確認を追加 |
| `tests/scripts/test_alpha_factory_run_ga.py` | `run_generation` を呼ぶ経路で collector 引数が渡ることをモック確認 |

### 設計

`run_generation(lane_id)` メソッドに optional 引数 `diagnostics_collector: DiagnosticsCollector | None = None` を追加 (後方互換)。

`evaluate_stage_a/b/c` の関数シグネチャは変更しない (Round 4 review の指摘に従う)。
swim_lane 内の Stage A/B/C 呼び出し直後で `collector` が None でなければ各 record メソッドを呼ぶ:

```python
# Stage A 後
a_result = evaluate_stage_a(genome, bars_60d, meta, backtest_config, primitive_evaluator, stage_config)
if diagnostics_collector is not None:
    diagnostics_collector.record_stage_a(
        lane_id=lane.lane_id,
        generation=lane.generation_count,  # 現行 swim_lane の正規属性 (self._generation_count は不存在)
        individual_name=genome.name,
        result=a_result,
    )

# Stage B 後 (該当した場合)
b_result = evaluate_stage_b(...)
if diagnostics_collector is not None:
    diagnostics_collector.record_stage_b(
        lane_id=lane.lane_id,
        generation=lane.generation_count,
        individual_name=genome.name,
        passed=b_result.passed,
    )

# Stage C 後 (該当した場合)
c_result = evaluate_stage_c(...)
if diagnostics_collector is not None:
    diagnostics_collector.record_stage_c(
        lane_id=lane.lane_id,
        generation=lane.generation_count,
        individual_name=genome.name,
        passed=c_result.passed,
    )
```

### ルックアヘッドバイアスチェック
- N/A

### テスト計画
- 既存 `tests/alpha_factory/test_swim_lane.py` に collector 引数 None default の後方互換テスト追加
- 新規 `test_swim_lane_records_collector_on_stage_a_only_path`
- 新規 `test_swim_lane_records_collector_on_full_path`

### リスク
- swim_lane が現状 single-process 評価か multiprocess かで実装経路が変わる → 既存実装が single process の場合は in-process collector で OK、multiprocess の場合は施策 5 で main process 集約

---

## 施策 4: sidecar writer (Parquet) 新設

### 変更箇所
- 新規: `src/alpha_factory/diagnostics_sidecar.py`

### 波及変更
- `AGENTS.md`: なし
- `pyproject.toml`: 変更なし (pandas を使わず pyarrow のみで実装。pyarrow は既存依存)

### pandas 不使用方針 (Round 1 Critical 対応)
- `pandas` は `pyproject.toml` に未登録のため、本モジュールでは `pandas` を使用しない
- `pyarrow` の `pa.array()` + `pa.table()` API を直接使用してスキーマ付き Table を構築する
- `generate_run_report.py` 側は既に pandas 依存があるため変更なし

### 実装内容

```python
"""Sidecar Parquet writer for DiagnosticsCollector output.

Output: reports/run-reports/run-{N}/diagnostics/stage_a_provenance.parquet

pandas に依存しない実装 (pyarrow のみ)。
pyproject.toml に未登録の外部依存を追加しない原則に従う。
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

logger = logging.getLogger(__name__)

# Sidecar Parquet schema (10 columns, no overlap with archive 28-col schema)
_SIDECAR_SCHEMA = pa.schema(
    [
        pa.field("lane_id", pa.string(), nullable=False),
        pa.field("generation", pa.int64(), nullable=False),
        pa.field("individual_name", pa.string(), nullable=False),
        pa.field("metric_stage", pa.string(), nullable=False),
        pa.field("trade_count", pa.int64(), nullable=False),
        pa.field("total_pnl_stage_a", pa.float64(), nullable=False),
        pa.field("sharpe_stage_a", pa.float64(), nullable=True),
        pa.field("stage_a_pass", pa.bool_(), nullable=False),
        pa.field("stage_b_pass", pa.bool_(), nullable=True),
        pa.field("stage_c_pass", pa.bool_(), nullable=True),
    ]
)

_COLUMN_NAMES = [f.name for f in _SIDECAR_SCHEMA]


def _build_table(rows: list[dict[str, Any]]) -> pa.Table:
    """Build a typed pyarrow Table from row dicts (no pandas dependency)."""
    if not rows:
        # Empty table with correct schema
        return pa.table(
            {name: pa.array([], type=_SIDECAR_SCHEMA.field(name).type) for name in _COLUMN_NAMES},
            schema=_SIDECAR_SCHEMA,
        )
    # Column-oriented construction
    columns = {name: [row[name] for row in rows] for name in _COLUMN_NAMES}
    arrays = {
        name: pa.array(columns[name], type=_SIDECAR_SCHEMA.field(name).type)
        for name in _COLUMN_NAMES
    }
    return pa.table(arrays, schema=_SIDECAR_SCHEMA)


def write_stage_a_provenance(
    rows: list[dict[str, Any]], out_path: Path
) -> bool:
    """Write rows to sidecar Parquet. Returns True on success, False on any error.

    Production GA must remain fail-open: caller swallows False and continues.
    """
    try:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        table = _build_table(rows)
        pq.write_table(table, out_path)
        return True
    except Exception as exc:
        logger.warning(
            "diagnostics_sidecar.write_failed",
            extra={"out_path": str(out_path), "error": str(exc)},
        )
        return False
```

### ルックアヘッドバイアスチェック
- N/A

### テスト計画
- 新規 `tests/alpha_factory/test_diagnostics_sidecar.py`:
  - `test_sidecar_writes_correct_schema`: schema 列・型が一致
  - `test_sidecar_writes_empty_rows_without_error`: 空 list でもファイル生成
  - `test_sidecar_returns_false_on_io_error`: `pq.write_table` を monkeypatch で例外注入 → False 返却・例外伝播なし (Round 1 Warning 対応: 権限エラー依存を排除)
  - `test_sidecar_roundtrip_preserves_values`: 書き込み → 読み込みで値完全一致

### リスク
- `pyarrow` schema mismatch (例: `bool` vs `int8`) → `_SIDECAR_SCHEMA` で nullable と dtype を明示固定、roundtrip テストで検証

---

## 施策 5: run_ga.py で collector 生成 + flush

### 変更箇所
- `scripts/alpha_factory/run_ga.py` の GA orchestration セクション (L812 付近 `swim_lane.run_generation()` 呼び出し箇所、L603 の summary 出力箇所)

### 波及変更
- `AGENTS.md`: なし (CLI オプション追加なし、内部のみ)
- skill: なし

### Round 1 Critical/Warning 対応

**[Critical] `--no-report` 契約遵守:**
- `run_ga.py` では `--no-report` 時に `reports/run-reports/` への書き込みを完全 skip する契約がある (L845-L868 の `if not args.no_report:` ブロック)
- sidecar も `reports/run-reports/run-{N}/diagnostics/` に書くため、`--no-report` 時は sidecar flush を skip する

**[Critical] fail-open の end-to-end 保証:**
- `collector.to_rows()` が例外を発生させる可能性がある (assertion 失敗等)
- `to_rows() + write_stage_a_provenance()` 全体を `try/except` で包み、例外時は False を返して GA を停止させない

**[Warning] パス構築:**
- `Path("reports/run-reports")` 直書きを避け、`run_dir / "diagnostics"` を使用する
- `run_dir` は L731 で `RUN_REPORTS_DIR / f"run-{run_number}"` として確定済みなので、この変数を再利用する

### 設計

```python
from src.alpha_factory.diagnostics_collector import DiagnosticsCollector
from src.alpha_factory.diagnostics_sidecar import write_stage_a_provenance

# GA 開始時に生成
collector = DiagnosticsCollector()

# 既存の generation loop で collector を渡す
for gen in range(generations):
    swim_lane.run_generation(lane_id, diagnostics_collector=collector)

# GA 完了後 flush (--no-report 時は skip, fail-open で全体 try/except)
if not args.no_report:
    sidecar_path = run_dir / "diagnostics" / "stage_a_provenance.parquet"
    try:
        sidecar_ok = write_stage_a_provenance(collector.to_rows(), sidecar_path)
    except Exception as exc:
        logger.warning(
            "diagnostics_sidecar.flush_failed",
            extra={"error": str(exc)},
        )
        sidecar_ok = False

    # summary.json への optional field (成功時のみ)
    if sidecar_ok:
        summary_dict["diagnostics_sidecar"] = str(sidecar_path)
    # 失敗時は field 自体を出さない (consumer は missing field を無視)
else:
    # --no-report 時は sidecar も skip
    logger.info(
        "diagnostics_sidecar.skip",
        reason="--no-report",
    )
```

### マルチプロセス対応 (現状確認後の判断)

`swim_lane.run_generation` が現状 single process なら上記でそのまま動く。
multiprocess の場合: collector を Manager().dict() で共有するか、worker から結果を返却して main で merge する。
**初回実装は single process 前提で進め、multiprocess 対応は実測後に追加 TODO**。

### テスト計画
- 新規 `tests/scripts/test_alpha_factory_run_ga.py` (または既存に追記):
  - `test_run_ga_diagnostics_sidecar_written_on_success`: 通常実行で sidecar が出力される
  - `test_run_ga_diagnostics_sidecar_skipped_on_no_report`: `--no-report` 時は sidecar ファイルが生成されない
  - `test_run_ga_diagnostics_sidecar_fail_open`: `write_stage_a_provenance` が False を返しても GA が正常終了する (mock 注入)

### リスク
- run_number の取得タイミングが summary.json 書き込みより後だと sidecar path が不定 → run_number は GA 開始時 L730-731 で確定しているため問題なし

---

## 施策 6: run-report skill に固定セクション追加

### 変更箇所
- `.claude/skills/zenigame-fx-run-report/SKILL.md`: 固定セクション追加 + 必須セクション検証コマンド更新
- `scripts/alpha_factory/generate_run_report.py`: sidecar 読み込み + 表示生成

### 波及変更
- `AGENTS.md`: なし (skill 内変更)

### SKILL.md 変更 1: 固定セクション追加 (テンプレート差分)

現行の「出力レポートのセクション構造」セクション (1-14 番) に 15 番として追加:

```markdown
15. **Stage A Provenance 分布** (`diagnostics/stage_a_provenance.parquet` 存在時のみ詳細表示、不在時は "not available" を出力)
```

内容仕様:
```markdown
## Stage A Provenance 分布

`reports/run-reports/run-{N}/diagnostics/stage_a_provenance.parquet` (sidecar) から:
- metric_stage 別個体数 (stage_a_only / stage_a_evaluated / stage_b_evaluated / stage_c_evaluated)
- Stage A 落ち個体 (`metric_stage="stage_a_only"`) の中で `trade_count > 0` の個体数とその `total_pnl_stage_a` 分布 (median, p25, p75)
- Stage A 通過個体の `total_pnl_stage_a` 分布

sidecar 不在時の表示:
> Stage A provenance: not available (sidecar file not produced; pre-Phase A run or fail-open path)
```

### SKILL.md 変更 2: 必須セクション検証コマンド更新 (Round 1 Warning 対応)

現行の「Step 2: 出力検証」grep コマンドに `## Stage A Provenance 分布` を追加:

```bash
for section in "## 使命判定" "## Best 個体" "## Stage 通過数" "## Lane 別落下分布" "## Pair 別落下分布" "## active_clause / n_nodes 分布" "## Cross-pair shadow 集計" "## Archive Top-5 個体一覧" "## 収束履歴" "## Stage A Provenance 分布"; do
  grep -q "^${section}" reports/run-reports/run-{N}.md || echo "MISSING: $section"
done
```

### generate_run_report.py 変更概要

```python
def _render_stage_a_provenance_section(run_dir: Path) -> str:
    sidecar = run_dir / "diagnostics" / "stage_a_provenance.parquet"
    if not sidecar.exists():
        return (
            "## Stage A Provenance 分布\n\n"
            "Stage A provenance: not available "
            "(sidecar file not produced; pre-Phase A run or fail-open path)\n"
        )
    df = pd.read_parquet(sidecar)
    # group by metric_stage
    counts = df["metric_stage"].value_counts().to_dict()
    only = df[df["metric_stage"] == "stage_a_only"]
    only_traded = only[only["trade_count"] > 0]
    # ... format markdown ...
```

### テスト計画 (Round 1 Warning 対応)

新規 `tests/scripts/test_alpha_factory_generate_run_report.py` を新設:
- `test_render_stage_a_provenance_section_with_sidecar`: sidecar parquet が存在する時に `## Stage A Provenance 分布` セクションが出力される
- `test_render_stage_a_provenance_section_without_sidecar`: sidecar 不在時に "not available" が出力される
- `test_generate_run_report_includes_provenance_section`: generate_run_report.py を実行した出力 md に `## Stage A Provenance 分布` が含まれる

### リスク
- 既存 run-9.md など過去レポートには sidecar がないため、後方互換のため "not available" 表示が必須 (実装済)

---

## 施策 7: テスト追加 (まとめ)

施策 1, 2, 3, 4, 5, 6 で各々テストを記載済。最終的な追加テストファイル:

| ファイル | テスト数 | 内容 |
|----------|---------|------|
| `tests/alpha_factory/test_diagnostics_collector.py` (新規) | 6 | DiagnosticsCollector 単体 |
| `tests/alpha_factory/test_diagnostics_sidecar.py` (新規) | 4 | write_stage_a_provenance 単体 (monkeypatch 含む) |
| `tests/scripts/test_alpha_factory_generate_run_report.py` (新規) | 3 | generate_run_report.py 出力検証 (Round 1 Warning 対応) |
| `tests/scripts/test_alpha_factory_run_ga.py` (既存に追記 or 新規) | 3 | diagnostics_sidecar 成功/失敗/`--no-report` (Round 1 Warning 対応) |
| `tests/alpha_factory/test_stage_gate.py` (既存に追記) | 2 | Stage A payload に total_pnl が含まれることを確認 |
| `tests/alpha_factory/test_swim_lane.py` (既存に追記) | 3 | collector 引数付き run_generation の後方互換 + 記録確認 |

### `tests/scripts/test_alpha_factory_run_ga.py` 追加テスト詳細 (Round 1 Warning 対応)

```python
def test_run_ga_diagnostics_sidecar_written_on_success(...):
    """通常実行 (--no-report なし) で sidecar parquet が出力される"""

def test_run_ga_diagnostics_sidecar_skipped_on_no_report(...):
    """--no-report 指定時は sidecar ファイルが生成されない"""

def test_run_ga_diagnostics_sidecar_fail_open(...):
    """write_stage_a_provenance を monkeypatch して例外を注入しても GA が正常終了する"""
```

### テスト命名 (汎用名、Run/日付固有 NG)
- `test_collector_records_stage_a_payload`
- `test_sidecar_writes_correct_schema`
- `test_sidecar_returns_false_on_io_error` (pq.write_table monkeypatch)
- `test_swim_lane_records_collector_on_stage_a_only_path`
- 等

---

## 実装モード

| 項目 | 内容 |
|------|------|
| 推奨モード | **incremental** |
| 判断根拠 | archive schema を touch しない、fitness 経路を touch しない、既存テスト変更は assertion 追加のみ。後方互換・段階的 merge 可能。multiprocess 対応は次 TODO で扱う前提のため初回 PR は単機能で incremental |
| 競合リスク | swim_lane.py は現在 hot path だが、引数追加 (default None) のため他 PR との衝突は最小 |
| 想定実装時間 | 短〜中 (新規 2 ファイル + 4 ファイル軽微変更 + 6 テスト追加) |

## 全体リスクサマリ

| リスク | 緩和 |
|--------|------|
| multiprocess での collector 共有 | 初回は single-process 前提、対応は次 TODO |
| sidecar 書き込み失敗で GA 停止 | write_stage_a_provenance は always return bool、例外を呑む (fail-open) |
| pyarrow schema mismatch | nullable / dtype を `_SIDECAR_SCHEMA` で明示、roundtrip テスト |
| run-report 既存出力との衝突 | 固定セクションを追加、不在時は "not available" 明記 |
| Stage A bt 未定義経路 | `bt is not None` チェックで保護。backtest 例外時は total_pnl=0.0、size_norm 例外時でも backtest 成功なら total_pnl を保持 (Round 2 修正) |

## メモリ制約チェック

- collector: 個体数 (~120) × dataclass (約 100 bytes) ≈ 12KB / generation
- 5 generation × 1 lane = 60KB (per run)
- 24GB / 6 worker / 1 worker 3GB の制約に対し誤差レベル

## 前提検証 (C4)

- archive schema 28 カラム固定: `src/alpha_factory/archive.py#L51-L101` で確認
- Stage A payload 構造: `src/alpha_factory/stage_gate.py#L320-L334` で確認
- backtest metrics の total_pnl: `src/backtest/metrics.py#L85-L89` で確認
- swim_lane の Stage A 呼び出し: `src/alpha_factory/swim_lane.py#L463` で確認

## 確認済み既存ドキュメント

- `docs/alpha_factory/clause-architecture.md#L356-L365` (Stage 別射影仕様)
- `docs/alpha_factory/concepts/genome-archive-schema.md#L12-` (archive schema SSOT)
- `.claude/skills/zenigame-fx-run-report/SKILL.md#L40` (run-report 固定セクション契約)
- `devnotes/20260425-0931-fx-improve/improvement-plan.md#L7-L10` (Run 10 監査のみ合意)
