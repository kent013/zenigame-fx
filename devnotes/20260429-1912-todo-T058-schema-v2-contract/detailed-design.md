# 詳細設計: T058 — Schema v2 contract (dataset_epoch_id 全経路必須化)

## 使命・制約 (絶対遵守)

### zenigame-fx Alpha Factory 使命
live_criteria 全指標同時充足 + (ii-lite) 通過で使命達成。 絶対制約: イントラデイ / ロング・ショート両方向 / スワップ・スプレッド反映。

### 禁止事項
1-7 (synthesis § 1.3 参照)
8. ゲノム archive スキーマ変更時の値伝搬漏れ ← **本 TODO の最重要遵守項目**

### コーディングルール
- バグ修正はテストファースト
- 全施策にテスト必須
- テスト命名: 振る舞いを説明する汎用的な名前
- テスト配置: 対象モジュールに対応するテストファイル
- uv 必須: `uv run pytest tests/alpha_factory/`
- ruff / mypy 通過: `uv run ruff check src/ tests/` / `uv run mypy src/`
- Python 3.13 + numpy + pandas 環境

## 概念設計リファレンス

`devnotes/20260429-1912-todo-T058-schema-v2-contract/conceptual-design.md` (Round 4 で APPROVED)

## 施策一覧

| # | 施策名 | 変更ファイル | 優先度 |
|---|--------|------------|--------|
| 1 | `schema_contract.py` 新規作成 (contract / enum / lint / 例外) | `src/alpha_factory/schema_contract.py` (新規) | Critical |
| 2 | `RunContext` dataclass 新規作成 | `src/alpha_factory/run_context.py` (新規) | Critical |
| 3 | `SchemaContractConfig` を `AlphaFactoryConfig` に追加 | `src/alpha_factory/config.py`, `config/alpha_factory/default.yaml` | Critical |
| 4 | `GENOMES_SCHEMA` に 4 field 追加 + lint 連動 | `src/alpha_factory/archive.py` | Critical |
| 5 | `HistoryRecord` 拡張 + lint 連動 | `src/alpha_factory/calibrate_gate_history.py` | High |
| 6 | `calibrate_state` の scope key 拡張 | `src/alpha_factory/calibrate_state.py` | High |
| 7 | `diagnostics_sidecar` 拡張 + lint 連動 | `src/alpha_factory/diagnostics_sidecar.py` | High |
| 8 | `fsp_updater` で v2 propagate | `src/alpha_factory/fsp_updater.py` | Medium |
| 9 | `run_ga.py` で `RunContext` 生成 + 全 artifact propagate | `scripts/alpha_factory/run_ga.py` | Critical |
| 10 | `run_alpha_sieve` loader を mode 連動 | `scripts/alpha_factory/run_alpha_sieve.py` | Medium |
| 11 | Tier 2 軽量ガード | `extract_batch_metrics.py`, `generate_run_report.py`, `compare_batch_runs.py`, `analyze_run.py` | Low |
| 12 | テスト: schema_contract, run_context, archive v2, history v2, type-fix | 各 `tests/alpha_factory/`, `tests/scripts/` | Critical |

---

## Round 6 review 反映 (Codex 詳細レビュー Round 6 → Round 7)

| Round 6 [Critical/Warning] | 修正対応 |
|---|---|
| [C1] `load_calibrated_threshold` で `threshold_floor`/`threshold_ceiling` の default が消失、 run_ga 側が cfg 参照で参照エラー | 関数定義を `threshold_floor: float = -100.0`, `threshold_ceiling: float = 100.0` の default 維持、 run_ga 側は既存 caller pattern 通り threshold_* 明示渡しなし |
| [W1] マトリクスの load_calibrated_threshold 行が完全記述になっていない | 旧/新 signature を完全展開で明記 (history_path, dataset_span: tuple[str,str], threshold_floor/ceiling default 含む) |
| [W2] 施策 4 擬似コードの `def load(...)` 単体表記 | `class GenomeArchive: ... @staticmethod def load(...)` で明示化 |

## Round 5 review 反映 (Codex 詳細レビュー Round 5 → Round 6)

| Round 5 [Critical/Warning/Suggestion] | 修正対応 |
|---|---|
| [C1] `load_calibrated_threshold` 既存シグネチャ違反 (history_path, dataset_span tuple, threshold_floor/ceiling) | T058 で `dataset_epoch_id` のみ追加、 既存全引数 (history_path 明示、 dataset_span tuple、 threshold_floor/ceiling) 完全維持 |
| [W1] `archive.load` 表記不一致 | 全文 `GenomeArchive.load` (staticmethod) に統一 |
| [W2] tuple 受取 caller 一本化 | `tuple 受取は run_alpha_sieve のみ`、 fsp_updater は df 単独返却 + helper `_detect_archive_schema_version` 経路 |
| [W3] FSP caller 全更新リスト不存在経路 | run_ga.py の FSP 呼出は現行不存在のため削除、 fsp_updater 内部の同 module caller (`fsp_updater.py:398, 412, 443, 465, 497`) のみ列挙 |
| [S1] flush 行明記 | マトリクスの flush 行を `flush(output_dir: Path | None = None) -> Path` に詳細化 |

## Round 4 review 反映 (Codex 詳細レビュー Round 4 → Round 5)

> **注: 有効な契約定義は本セクション末尾の「API 契約変更マトリクス (Round 3 反映、 現行実装シグネチャ参照行追加)」 のみ**。 文書中に「Round 2 マトリクス」 の見出しがあるが履歴目的で残置されているだけで実装指示としては無効。 (Codex Round 4 [Suggestion] 1)

| Round 4 [Critical/Warning/Suggestion] | 修正対応 |
|---|---|
| [C1] API 契約マトリクス二重化矛盾 | Round 2 版マトリクスを「~~無効~~」 として履歴扱い、 実装指示は Round 3 マトリクスのみ |
| [C2] `load_calibrated_threshold` 戻り値 `tuple` 不整合 | 現行 `float | None` を維持 (擬似コードを `return rec.new_threshold` に修正、 run_id 同時返却は別 helper で T058 外) |
| [C3] `flush` 既存 `output_dir: Path | None = None` 維持違反 | `flush(output_dir: Path | None = None) -> Path` に修正 |
| [W1] run_alpha_sieve loader import 経路 | `GenomeArchive.load(..., return_schema_version=True)` (現行 caller 互換) |
| [W2] fsp_updater テスト名と契約噛み合わない | helper `_detect_archive_schema_version` 直接検証する命名に変更、 read 側は warning ログ assert に |
| [W3] HistoryRecord 空文字 default の整合 | row/template/fallback は `epoch_legacy` 統一、 HistoryRecord は __post_init__ で reject する sentinel として空文字 default 維持と文言修正 |
| [S1] 「有効な契約は新マトリクスのみ」 注記 | 本セクション冒頭に注記追加 |

## Round 3 review 反映 (Codex 詳細レビュー Round 3 → Round 4)

| Round 3 [Critical/Warning/Suggestion] | 修正対応 |
|---|---|
| [C1] ValidationResult 契約未統一 (施策 1 が `-> None` のまま) | 施策 1 の全 4 validator を `ValidationResult` 返却に統一、 `_check_required` も含めて整合 |
| [C2] 施策 9 で `out_dir=archive_dir` 残存 | 施策 9 の擬似コードから `out_dir=` 削除、 `archive.flush(output_dir=archive_dir)` で渡す形に統一 |
| [C3] `load_calibrated_threshold` と `find_latest_applicable` 混在 | `find_latest_applicable` を全文置換で `load_calibrated_threshold` に統一 (施策 6 + テスト名) |
| [C4] `archive.load(return_schema_version=True)` が施策 10 未反映 | 施策 10 の擬似コードを `table, sv = load_archive(..., return_schema_version=True)` + `if sv is None: skip` に修正 |
| [C5] diagnostics_sidecar `build_sidecar_table(rows)` (現行 rows 受取) と `write_stage_a_provenance(...) -> Path \| None` (現行返り値) を厳守 | 施策 7 を rows 受取 + `Path \| None` 返却の現行契約に完全合致させる、 `run_context` / `mode` を optional kwargs として追加のみ |
| [C6] `_atomic_write_parquet` に `schema` 引数必須 (現行) | 施策 8 を `_atomic_write_parquet(df, target_path, schema, *, mode=...)` に修正 |
| [W1] 33 col 表現残存 | 「既存 28+5 = 33 columns」 を「既存 43 columns」 に置換 |
| [W2] 施策 6 テスト名が旧 `test_find_latest_applicable_*` のまま | `test_load_calibrated_threshold_*` に変更 (全文置換で適用済み) |
| [W3] 空文字 `""` fallback | row/template/fallback (archive `_create_row_template` / sidecar / fsp_updater) は `epoch_legacy` に統一。 ただし `HistoryRecord.dataset_epoch_id` は `__post_init__` で空文字を reject する sentinel default として **空文字維持** (caller が必ず値設定する、 caller 不在で永続化することは不可) |
| [S1] API 契約変更マトリクスに「現行実装シグネチャ参照行」追加 | 既存マトリクスに行追加 (Round 4 で反映) |

### API 契約変更マトリクス (Round 3 [Suggestion] 1 反映、 現行実装シグネチャ参照行追加)

| 関数 | **現行実装 (T058 前)** | **新 signature (T058 後)** | 後方互換 |
|---|---|---|---|
| `GenomeArchive.__init__` | `(run_id, run_number)` (`archive.py:330` 周辺) | `(run_id, run_number, *, run_context=None, enforcement_mode=LOG_ONLY)` | ✓ |
| `GenomeArchive.flush` | `flush(output_dir: Path | None = None) -> Path` (`archive.py:581`) | 不変 (`flush(output_dir: Path | None = None) -> Path`) | ✓ |
| `GenomeArchive.load` (staticmethod) | `(path) -> pa.Table` (`archive.py:612`) | `(path, *, mode=LOG_ONLY, return_schema_version=False) -> pa.Table | tuple` | ✓ |
| `assert_*_v2` validators | (新規) | `(record, *, mode) -> ValidationResult` | (新規) |
| `append_record` | `(record, path)` positional (`calibrate_gate_history.py:72`) | `(record, path=DEFAULT_HISTORY_PATH, *, mode=LOG_ONLY)` | ✓ |
| `read_history` | `(path, last_n=None) -> list[HistoryRecord]` (`calibrate_gate_history.py:81`) | 不変 (内部で v1 record skip) | ✓ |
| `load_calibrated_threshold` | `(*, history_path, base_config_hash, dataset_span: tuple[str,str], instrument, stage_gate_version, threshold_floor=-100.0, threshold_ceiling=100.0) -> float \| None` (`calibrate_state.py:184`) | 既存全引数 + default 完全維持 + `dataset_epoch_id: str` を追加: `(*, history_path, base_config_hash, dataset_epoch_id, dataset_span, instrument, stage_gate_version, threshold_floor=-100.0, threshold_ceiling=100.0) -> float \| None` | ✗ 新引数 `dataset_epoch_id` 必須 (caller `run_ga.py:1078` のみ更新) |
| `build_sidecar_table` | `(rows: Sequence[dict]) -> pa.Table` (`diagnostics_sidecar.py:62`) | `(rows, *, run_context=None, mode=LOG_ONLY) -> pa.Table` | ✓ |
| `write_stage_a_provenance` | `(collector, output_path) -> Path \| None` (`diagnostics_sidecar.py:67`) | `(collector, output_path, *, run_context=None, mode=LOG_ONLY) -> Path \| None` | ✓ |
| `_atomic_write_parquet` | `(df, target_path, schema)` (`fsp_updater.py:180`) | `(df, target_path, schema, *, mode=LOG_ONLY)` | ✓ |
| `_read_archive_with_fsp_compat` | `(path) -> pd.DataFrame` (`fsp_updater.py` 周辺) | `(path, *, mode=LOG_ONLY) -> pd.DataFrame` | ✓ |
| `_detect_archive_schema_version` (新規 helper) | (新規) | `(table) -> int | None` | (新規) |

## Round 2 review 反映 (Codex 詳細レビュー Round 2 → Round 3)

| Round 2 [Critical/Warning/Suggestion] | 修正対応 |
|---|---|
| [Critical 1] archive.load 戻り値契約不整合 (tuple vs table) | `load(path, *, mode, return_schema_version=False)` で後方互換 + 段階移行、 既存 caller (test_archive.py:546) は table 受取り維持、 新 caller (run_alpha_sieve, fsp_updater) は `return_schema_version=True` で tuple |
| [Critical 2] GenomeArchive __init__ で out_dir 渡す擬似コード残存 | `out_dir` を __init__ から削除、 `flush(output_dir=...)` 既存契約のみ |
| [Critical 3] diagnostics_sidecar 関数契約変更が既存呼出を壊す | 既存 signature `write_stage_a_provenance(collector, ...)` 維持、 `run_context` / `mode` を optional kwargs として追加のみ |
| [Critical 4] LOG_ONLY 警告集約ロジック非機能 (validator が raise しないのに except SchemaContractError) | validator を `ValidationResult` 返却に変更、 `result.ok` で集計 |
| [Critical 5] fsp_updater API 変更範囲未閉包 | `_read_archive_with_fsp_compat` は df 単独返却維持、 schema_version 検出は `_detect_archive_schema_version` helper で別経路提供。 caller 全更新リスト明記 |
| [Warning 6] C4 列数 33 col 表現残存 | 33 col 表現を完全削除、 47 col に統一 |
| [Warning 7] calibrate_state rename 波及 | 既存関数名 `load_calibrated_threshold` 維持 (rename しない)、 `dataset_epoch_id` 引数追加のみ |
| [Warning 8] DoD test path 誤参照 | `tests/scripts/test_calibrate_gate_drift.py` (実在 path) に修正 |
| [Suggestion 9] 契約変更一覧 + caller 全件 | 末尾に「API 契約変更マトリクス」 を追加 (本セクション) |

## ~~API 契約変更マトリクス (Round 2 版)~~ — **無効、 Round 3 マトリクスを参照**

> **注: このマトリクスは Round 2 で書かれたものだが、 Round 3 で詳細化された [新マトリクス](#api-契約変更マトリクス-round-3-suggestion-1-反映-現行実装シグネチャ参照行追加) で完全に置換されている**。 実装指示としては Round 3 マトリクス (現行実装 file:line 引用付き) のみを参照すること。 旧マトリクスは履歴目的で残置。

## Round 1 review 反映 (Codex 詳細レビュー Round 1 → Round 2)

| Round 1 [Critical/Warning] | 修正対応 |
|---|---|
| [Critical] RunContext に schema_contract_mode 不在で flush 参照失敗 | enforcement_mode は **AlphaFactoryConfig.schema_contract から GenomeArchive に直接 inject** する。 RunContext には load しない (Codex Round 1 [Critical] 1) |
| [Critical] GenomeArchive.__init__ で out_dir 必須化は既存呼出 (`run_ga.py:1159`, `test_archive.py:161`) を壊す | **既存シグネチャ維持** (`GenomeArchive(run_id, run_number)`)、 `flush(output_dir=...)` 契約維持、 `run_context` と `enforcement_mode` を **optional kwargs として追加**のみ (Codex Round 1 [Critical] 2) |
| [Critical] HistoryRecord __post_init__ で ValueError raise → read_history は TypeError catch のみ → 旧 record で落ちる | read_history で **ValueError も skip 対象**に拡張、 v1 record (`calibrate_history_schema_version` 不在) は明示変換層で skip (Codex Round 1 [Critical] 3) |
| [Critical] append_record(path=) keyword-only 化は既存呼出 (`calibrate_gate.py:452`, `test_calibrate_gate_history.py:59`) と衝突 | `append_record(record, path=DEFAULT_HISTORY_PATH, *, mode=...)` に修正、 path は positional 互換維持 (Codex Round 1 [Critical] 4) |
| [Critical] LOG_ONLY と read/write 挙動矛盾 (archive.load v1 return / fsp 即 raise) | **v1 検出時の返却契約**を明確化: LOG_ONLY は (table, schema_version=v1) flag 付き返却、 caller 側で skip 判定。 fsp_updater._atomic_write_parquet は mode=LOG_ONLY なら warning + 最善努力書き込み (Codex Round 1 [Critical] 5) |
| [Critical] dataset_epoch_id stub `epoch_legacy` 固定で dataset_span 完全置換は contamination 再導入 | T058 では **dataset_span ガード残置**、 dataset_epoch_id を追加条件化 (AND 結合)、 完全置換は T067 (Codex Round 1 [Critical] 6) |
| [Warning] history.json 伝搬仕様非互換 (現行 list、 設計 dict) | history.json は **list 形式維持**、 各要素 (per-generation) に dataset_epoch_id 追加 (Codex Round 1 [Warning] 7) |
| [Warning] diagnostics sidecar schema 更新不明示 | STAGE_A_PROVENANCE_SCHEMA に **列を明示追加**、 read/write テスト更新 (Codex Round 1 [Warning] 8) |
| [Warning] C4 前提ズレ (33 col 前提、 実 43 col) | 列数を **43 col 前提**に再同期 (Codex Round 1 [Warning] 9) |
| [Warning] 波及変更不足 (docs/skill) | DoD に `docs/alpha_factory/stage-gates.md` § T054 と `.claude/skills/zenigame-fx-calibrate-gate/SKILL.md:99` 追加 (Codex Round 1 [Warning] 10) |
| [Suggestion] LOG_ONLY warning 大量化 | per-row warning を **run 単位 counter** + 末尾 summary log に集約 |
| [Suggestion] C3/C7 適用 | 本設計は schema/contract 変更で相関 claim なし、 **N/A 明記** |

## 施策 1: `schema_contract.py` 新規作成

### 変更箇所
- ファイル: `src/alpha_factory/schema_contract.py` (新規)

### 波及変更
- `AGENTS.md`: なし (内部 module)
- `.claude/skills/zenigame-fx-{skill}/SKILL.md`: なし
- `config/alpha_factory/default.yaml`: 施策 3 で追加
- `docs/alpha_factory/*.md`: なし (文書追加は T058 内では不要、 後段 T067 切替時に runbook 更新)

### 変更後コード

```python
"""T058: Schema v2 contract — dataset_epoch_id 全経路必須化.

zenigame-fx の selection cascade を big-bang baseline で再構築する際の
最先頭 contract。 詳細:
- 概念設計: devnotes/20260429-1912-todo-T058-schema-v2-contract/conceptual-design.md
- synthesis: devnotes/20260428-2300-cascade-port-debate/synthesis.md § 9
- 後段 TODO (T059-T075) は本 schema に依存。
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from enum import StrEnum
from typing import Any, Final

import structlog

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Schema versions (artifact 別)
# ---------------------------------------------------------------------------

GENOME_ENTRY_SCHEMA_VERSION: Final[int] = 2
CALIBRATE_HISTORY_SCHEMA_VERSION: Final[int] = 2
CASCADE_CONTRACT_VERSION: Final[int] = 2
DIAGNOSTICS_SCHEMA_VERSION: Final[int] = 2


# ---------------------------------------------------------------------------
# Enum (永続値 lower_snake_case)
# ---------------------------------------------------------------------------


class ArchiveRole(StrEnum):
    """Archive 流入 3 層の identifier (T066 で書込)."""

    MISSION_PASS = "mission_pass"
    PROGRESS_PASS = "progress_pass"
    SCORE_BYPASS = "score_bypass"


class SourceStage(StrEnum):
    """個体評価の最終 stage (T063-T064 で書込)."""

    A = "a"
    B = "b"
    C_LITE = "c_lite"
    C = "c"


class SchemaEnforcementMode(StrEnum):
    """Schema lint の enforcement mode.

    LOG_ONLY (T058 default): warning + Counter 計測、 fail させない。
    FAIL_CLOSED (T067 で切替): 必須 field 欠落で SchemaContractError raise。
    """

    LOG_ONLY = "log_only"
    FAIL_CLOSED = "fail_closed"


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class SchemaContractError(ValueError):
    """必須 field 欠落 (FAIL_CLOSED mode で raise)."""


class SchemaVersionError(ValueError):
    """schema_version 不一致 (T067 で v1 archive 検出時 raise)."""


# ---------------------------------------------------------------------------
# Grammar — dataset_epoch_id
# ---------------------------------------------------------------------------

DATASET_EPOCH_ID_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[a-z0-9_]+$")


def validate_epoch_id(value: str) -> None:
    """dataset_epoch_id の grammar 検証.

    Raises:
        SchemaContractError: 空文字 / pattern 不一致。
    """
    if not value:
        raise SchemaContractError("dataset_epoch_id must be non-empty")
    if not DATASET_EPOCH_ID_PATTERN.fullmatch(value):
        raise SchemaContractError(
            f"dataset_epoch_id violates grammar [a-z0-9_]+: {value!r}"
        )


# ---------------------------------------------------------------------------
# Required field sets (Tier 1: 9 経路)
# ---------------------------------------------------------------------------

COMMON_REQUIRED: Final[frozenset[str]] = frozenset({"dataset_epoch_id"})

GENOME_ENTRY_CONTRACT_V2: Final[frozenset[str]] = COMMON_REQUIRED | frozenset({
    "genome_entry_schema_version",
    "archive_role",
    "source_stage",
})

CALIBRATE_HISTORY_CONTRACT_V2: Final[frozenset[str]] = COMMON_REQUIRED | frozenset({
    "calibrate_history_schema_version",
})

RUN_REPORT_CONTRACT_V2: Final[frozenset[str]] = COMMON_REQUIRED | frozenset({
    "cascade_contract_version",
})

DIAGNOSTICS_CONTRACT_V2: Final[frozenset[str]] = COMMON_REQUIRED | frozenset({
    "diagnostics_schema_version",
})


# ---------------------------------------------------------------------------
# Validators (Tier 1: 4 関数、 ValidationResult 返却統一、 Round 3 [Critical] 1 反映)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ValidationResult:
    """Validator 返却型. LOG_ONLY mode で `result.ok` で集計に使う."""
    ok: bool
    missing: tuple[str, ...] = ()
    invalid: tuple[str, ...] = ()


def _check_required(
    record: Mapping[str, Any],
    required: frozenset[str],
    *,
    artifact: str,
    mode: SchemaEnforcementMode,
) -> ValidationResult:
    """必須 field 欠落を mode に従って handle、 ValidationResult を返す."""
    missing = tuple(sorted(required - record.keys()))
    if not missing:
        return ValidationResult(ok=True)
    if mode == SchemaEnforcementMode.FAIL_CLOSED:
        raise SchemaContractError(
            f"{artifact}: missing required fields {list(missing)}"
        )
    logger.warning(
        "schema_contract.passive_validation_failed",
        artifact=artifact,
        missing=list(missing),
        record_keys=sorted(record.keys()),
    )
    return ValidationResult(ok=False, missing=missing)


def assert_genome_entry_v2(
    record: Mapping[str, Any],
    *,
    mode: SchemaEnforcementMode,
) -> ValidationResult:
    """Tier 1: Parquet archive entry の v2 contract 検証."""
    base = _check_required(
        record, GENOME_ENTRY_CONTRACT_V2, artifact="genome_entry", mode=mode
    )
    invalid: list[str] = []
    epoch_id = record.get("dataset_epoch_id")
    if isinstance(epoch_id, str):
        try:
            validate_epoch_id(epoch_id)
        except SchemaContractError:
            if mode == SchemaEnforcementMode.FAIL_CLOSED:
                raise
            invalid.append("dataset_epoch_id")
            logger.warning(
                "schema_contract.invalid_epoch_id",
                artifact="genome_entry",
                value=epoch_id,
            )
    if invalid:
        return ValidationResult(ok=False, missing=base.missing, invalid=tuple(invalid))
    return base


def assert_calibrate_history_v2(
    record: Mapping[str, Any],
    *,
    mode: SchemaEnforcementMode,
) -> ValidationResult:
    """Tier 1: calibrate-gate history JSONL の v2 contract 検証."""
    return _check_required(
        record, CALIBRATE_HISTORY_CONTRACT_V2, artifact="calibrate_history", mode=mode
    )


def assert_run_report_v2(
    report: Mapping[str, Any],
    *,
    mode: SchemaEnforcementMode,
) -> ValidationResult:
    """Tier 1: summary.json の v2 contract 検証."""
    base = _check_required(
        report, RUN_REPORT_CONTRACT_V2, artifact="run_report", mode=mode
    )
    invalid: list[str] = []
    # 型分離: cascade_contract_version は int、 既存 schema_version は string
    ccv = report.get("cascade_contract_version")
    if ccv is not None and not isinstance(ccv, int):
        if mode == SchemaEnforcementMode.FAIL_CLOSED:
            raise SchemaContractError(
                f"cascade_contract_version must be int, got {type(ccv).__name__}"
            )
        invalid.append("cascade_contract_version")
        logger.warning(
            "schema_contract.type_violation",
            artifact="run_report",
            field="cascade_contract_version",
            type=type(ccv).__name__,
        )
    if invalid:
        return ValidationResult(ok=False, missing=base.missing, invalid=tuple(invalid))
    return base


def assert_diagnostics_v2(
    record: Mapping[str, Any],
    *,
    mode: SchemaEnforcementMode,
) -> ValidationResult:
    """Tier 1: diagnostics sidecar / stage_a_provenance の v2 contract 検証."""
    return _check_required(
        record, DIAGNOSTICS_CONTRACT_V2, artifact="diagnostics", mode=mode
    )


# ---------------------------------------------------------------------------
# Tier 2 軽量ガード (non-blocking)
# ---------------------------------------------------------------------------


def assert_epoch_id_present_for_display(
    obj: Mapping[str, Any] | None,
    *,
    artifact: str,
) -> None:
    """Tier 2 派生表示 artifact 用の軽量 non-blocking ガード.

    `dataset_epoch_id` 引用漏れを log warning + Counter 計測。 fail させない
    (Tier 2 は表示用なので運用事故化を避ける、 Codex Round 3 [Suggestion])。
    """
    if obj is None or "dataset_epoch_id" not in obj:
        logger.warning(
            "schema_contract.tier2_epoch_id_missing",
            artifact=artifact,
            keys=sorted((obj or {}).keys()),
        )
```

### ルックアヘッドバイアスチェック (primitive 変更時のみ必須、 本施策は schema なので非該当)
- N/A

### C3 / C7 適用 (Codex Round 1 [Suggestion] 12 反映)
- N/A — 本設計は schema/contract 変更で相関 claim や予測 claim なし、 sample size 系統計判定なし

### パフォーマンスチェック
- N/A (lint overhead は軽微、 Codex Round 1 確認済)
- LOG_ONLY 期間の per-row warning は run 単位 counter に集約、 末尾 summary log に出すため log 洪水を回避 (Codex Round 1 [Suggestion] 11)

### テスト計画
- 新規 test ファイル: `tests/alpha_factory/test_schema_contract.py`
- 振る舞いベースのテスト名 (Run 名・日付・セッション固有 NG):
  - `test_validate_epoch_id_accepts_lowercase_alphanumeric_underscore`
  - `test_validate_epoch_id_rejects_empty_string`
  - `test_validate_epoch_id_rejects_uppercase`
  - `test_validate_epoch_id_rejects_hyphen_or_space`
  - `test_assert_genome_entry_v2_log_only_does_not_raise_on_missing_field`
  - `test_assert_genome_entry_v2_fail_closed_raises_on_missing_field`
  - `test_assert_genome_entry_v2_fail_closed_raises_on_invalid_epoch_id`
  - `test_assert_run_report_v2_fail_closed_raises_on_string_cascade_contract_version`
  - `test_archive_role_persisted_value_is_lower_snake_case`
  - `test_source_stage_c_lite_persisted_value`
  - `test_assert_epoch_id_present_for_display_does_not_raise_when_missing`
  - `test_assert_epoch_id_present_for_display_logs_warning_when_missing` (mock logger 使用)

### リスク
- 単独施策では機能しない (他施策と同時着地が必要)
- LOG_ONLY mode で warning が大量発生する可能性 → counter で量を観測、 異常閾値で alert

---

## 施策 2: `RunContext` dataclass 新規作成

### 変更箇所
- ファイル: `src/alpha_factory/run_context.py` (新規)

### 波及変更
- `AGENTS.md`: なし
- `.claude/skills/zenigame-fx-{skill}/SKILL.md`: なし
- `config/alpha_factory/default.yaml`: なし
- `docs/alpha_factory/*.md`: なし

### 変更後コード

```python
"""T058: RunContext — 1 Run 全体で固定される runtime context.

`run_ga.py` の startup で生成、 全 component (GA loop, archive, calibrate,
diagnostics, FSP, sieve) が同じ source から `dataset_epoch_id` 等を読む。

T058 段階の必須注入は archive / calibrate / diagnostics の主要 3 component
のみ。 全 component 必須化は T059 / T063 合流時に段階的に締める。
"""

from __future__ import annotations

from dataclasses import dataclass

from src.alpha_factory.schema_contract import validate_epoch_id

__all__ = ["RunContext"]


@dataclass(frozen=True)
class RunContext:
    """1 Run スコープの runtime context.

    Attributes:
        run_id: ``run_YYYYMMDD_HHMMSS`` 形式の Run 識別子。
        run_number: Run の連番 (e.g., 26)。
        dataset_epoch_id: epoch-rolling 識別子 (T059 で生成)。
        base_config_hash: config hash (calibrate-gate scope 用)。
        instrument: anchor pair (e.g., ``EUR_JPY``)。
    """

    run_id: str
    run_number: int
    dataset_epoch_id: str
    base_config_hash: str
    instrument: str

    def __post_init__(self) -> None:
        if not self.run_id:
            raise ValueError("run_context.run_id must be non-empty")
        if self.run_number < 0:
            raise ValueError(f"run_context.run_number must be >= 0: {self.run_number}")
        # grammar 検証は schema_contract.validate_epoch_id 経由
        validate_epoch_id(self.dataset_epoch_id)
        if not self.base_config_hash:
            raise ValueError("run_context.base_config_hash must be non-empty")
        if not self.instrument:
            raise ValueError("run_context.instrument must be non-empty")
```

### テスト計画
- 新規: `tests/alpha_factory/test_run_context.py`
  - `test_run_context_constructs_with_valid_fields`
  - `test_run_context_rejects_empty_run_id`
  - `test_run_context_rejects_negative_run_number`
  - `test_run_context_rejects_invalid_epoch_id_grammar`
  - `test_run_context_is_frozen_dataclass`

### リスク
- 既存 component への注入は施策 4-10 で実施、 単独では機能しない

---

## 施策 3: `SchemaContractConfig` を `AlphaFactoryConfig` に追加

### 変更箇所
- ファイル: `src/alpha_factory/config.py` (L17-44 に dataclass 追加、 `AlphaFactoryConfig` に field 追加、 `load_config` 内で parse)
- ファイル: `config/alpha_factory/default.yaml` (新セクション追加)

### 波及変更
- `AGENTS.md`: なし
- `.claude/skills/zenigame-fx-{skill}/SKILL.md`: なし
- `docs/alpha_factory/*.md`: なし

### 現行コード (`config.py:32-42`)

```python
__all__ = [
    "AlphaFactoryConfig",
    "BacktestSectionConfig",
    "CrossPairConfig",
    "DatasetConfig",
    "FspConfig",
    "GAConfig",
    "GAFeasibilityConfig",
    "StageGateConfig",
    "StageWindowsConfig",
    "load_config",
]
```

### 変更後コード (`config.py` に追加)

```python
__all__ = [
    "AlphaFactoryConfig",
    "BacktestSectionConfig",
    "CrossPairConfig",
    "DatasetConfig",
    "FspConfig",
    "GAConfig",
    "GAFeasibilityConfig",
    "SchemaContractConfig",  # T058
    "StageGateConfig",
    "StageWindowsConfig",
    "load_config",
]


@dataclass(frozen=True)
class SchemaContractConfig:
    """T058: schema_contract enforcement settings.

    Attributes:
        enforcement_mode: ``log_only`` (T058 default) or ``fail_closed`` (T067).
    """

    enforcement_mode: str = "log_only"

    def __post_init__(self) -> None:
        from src.alpha_factory.schema_contract import SchemaEnforcementMode

        valid = {m.value for m in SchemaEnforcementMode}
        if self.enforcement_mode not in valid:
            raise ValueError(
                f"schema_contract.enforcement_mode must be one of {sorted(valid)}: "
                f"got {self.enforcement_mode!r}"
            )

    def to_mode(self) -> "SchemaEnforcementMode":
        from src.alpha_factory.schema_contract import SchemaEnforcementMode

        return SchemaEnforcementMode(self.enforcement_mode)


@dataclass(frozen=True)
class AlphaFactoryConfig:
    # 既存 field ...
    dataset: DatasetConfig
    backtest: BacktestSectionConfig
    ga: GAConfig
    stage_gate: StageGateConfig
    cross_pair: CrossPairConfig
    stage_windows: StageWindowsConfig
    fsp: FspConfig = field(default_factory=FspConfig)
    schema_contract: SchemaContractConfig = field(  # T058 新設
        default_factory=SchemaContractConfig
    )
```

### `config/alpha_factory/default.yaml` 追加

```yaml
# T058: schema_contract enforcement settings.
# T058 段階は log_only (passive validation)、 T067 切替時に fail_closed へ。
# 詳細: devnotes/20260429-1912-todo-T058-schema-v2-contract/conceptual-design.md
schema_contract:
  enforcement_mode: log_only
```

### `load_config` 内 parse 追加 (擬似 diff)

```python
sc_raw = (raw.get("schema_contract") or {})
unknown_keys = set(sc_raw.keys()) - {"enforcement_mode"}
if unknown_keys:
    raise ValueError(
        f"schema_contract: unknown keys {sorted(unknown_keys)} (Codex Round 3 提案: unknown key 拒否)"
    )
schema_contract = SchemaContractConfig(
    enforcement_mode=sc_raw.get("enforcement_mode", "log_only")
)
```

### テスト計画
- 既存 `tests/alpha_factory/test_config.py` に追加:
  - `test_load_config_default_yaml_parses_schema_contract_log_only`
  - `test_load_config_overrides_schema_contract_to_fail_closed`
  - `test_schema_contract_config_rejects_invalid_enforcement_mode`
  - `test_schema_contract_config_to_mode_returns_strenum_member`
  - `test_load_config_rejects_unknown_schema_contract_key`

### リスク
- yaml に既存 schema_contract セクションが無いため migration 影響なし

---

## 施策 4: `GENOMES_SCHEMA` に 4 field 追加 + lint 連動

### 変更箇所
- ファイル: `src/alpha_factory/archive.py` (L54-118: schema、 L142-200: template、 L590-610: flush)

### 波及変更
- `AGENTS.md`: なし (内部 schema)
- `docs/alpha_factory/runbook.md`: archive schema 説明があれば 4 field 追記

### 現行コード (`archive.py:54-118`)

```python
GENOMES_SCHEMA: pa.Schema = pa.schema(
    [
        pa.field("run_id", pa.string(), nullable=False),
        # ... 既存 43 columns
        pa.field("fsp_idio_ratio", pa.float64(), nullable=True),
    ]
)
```

### 変更後コード

```python
GENOMES_SCHEMA: pa.Schema = pa.schema(
    [
        # T058: schema v2 必須 4 field
        pa.field("genome_entry_schema_version", pa.int32(), nullable=False),
        pa.field("dataset_epoch_id", pa.string(), nullable=False),
        pa.field("archive_role", pa.string(), nullable=True),  # T066 で書込
        pa.field("source_stage", pa.string(), nullable=True),  # T063-T064 で書込
        # 既存 field
        pa.field("run_id", pa.string(), nullable=False),
        # ... (省略)
        pa.field("fsp_idio_ratio", pa.float64(), nullable=True),
    ]
)
```

### `_create_row_template` 拡張

```python
def _create_row_template() -> dict[str, Any]:
    return {
        # T058 新設
        "genome_entry_schema_version": 2,
        "dataset_epoch_id": "epoch_legacy",  # T058 stub fallback (T059 で deterministic 値に置換)、 grammar 適合 (Round 3 [Warning] 3)
        "archive_role": None,
        "source_stage": None,
        # 既存
        "run_id": "",
        # ... (省略)
    }
```

### `flush()` で lint 連動 (Round 1+2 [Critical] 反映)

GenomeArchive 既存シグネチャは維持。 `out_dir` は `__init__` でなく `flush(output_dir=...)` 既存契約を維持する。

```python
class GenomeArchive:
    def __init__(
        self,
        run_id: str,
        run_number: int,
        *,
        run_context: RunContext | None = None,
        enforcement_mode: SchemaEnforcementMode = SchemaEnforcementMode.LOG_ONLY,
    ) -> None:
        # 既存 init: out_dir は __init__ に渡らない (flush 時に渡る既存契約維持)
        self.run_id = run_id
        self.run_number = run_number
        self.rows: list[dict[str, Any]] = []
        # T058 追加 (optional)
        self._run_context = run_context
        self._enforcement_mode = enforcement_mode
        self._lint_warning_count = 0  # per-run counter

    def flush(self, output_dir: Path | None = None) -> Path:
        """既存契約 `output_dir: Path | None = None` 維持 (Round 4 [Critical] 3)."""
        # ... 既存処理 (None なら default 出力先) ...
        clean_rows = [...]

        # T058: 各 row に対して passive validation (mode 連動)
        # validator は ValidationResult 返却 (Round 2 [Critical] 4 反映)
        for row in clean_rows:
            if (row.get("dataset_epoch_id") in (None, "")) and self._run_context:
                row["dataset_epoch_id"] = self._run_context.dataset_epoch_id
            row.setdefault("genome_entry_schema_version", 2)
            result = assert_genome_entry_v2(row, mode=self._enforcement_mode)
            # FAIL_CLOSED は assert 内で raise 済み、 ここに来るのは LOG_ONLY のみ
            if not result.ok:
                self._lint_warning_count += 1

        # Codex Round 1 [Suggestion]: 末尾 summary log
        if self._lint_warning_count:
            logger.warning(
                "archive.flush.schema_lint_summary",
                warning_count=self._lint_warning_count,
                mode=self._enforcement_mode.value,
                run_id=self.run_id,
            )

        table = pa.Table.from_pylist(clean_rows, schema=GENOMES_SCHEMA)
        # ... 既存 write 処理 ...
```

### `validator` を `ValidationResult` 返却に修正 (Round 2 [Critical] 4 反映)

`schema_contract.py` 内の validator を以下に修正:

```python
@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    missing: tuple[str, ...] = ()
    invalid: tuple[str, ...] = ()  # field name list with invalid values

def assert_genome_entry_v2(
    record: Mapping[str, Any],
    *,
    mode: SchemaEnforcementMode,
) -> ValidationResult:
    missing = tuple(sorted(GENOME_ENTRY_CONTRACT_V2 - record.keys()))
    invalid: list[str] = []
    epoch_id = record.get("dataset_epoch_id")
    if isinstance(epoch_id, str):
        try:
            validate_epoch_id(epoch_id)
        except SchemaContractError:
            invalid.append("dataset_epoch_id")

    if missing or invalid:
        if mode == SchemaEnforcementMode.FAIL_CLOSED:
            raise SchemaContractError(
                f"genome_entry: missing={missing} invalid={tuple(invalid)}"
            )
        logger.warning(
            "schema_contract.passive_validation_failed",
            artifact="genome_entry",
            missing=list(missing),
            invalid=list(invalid),
        )
        return ValidationResult(ok=False, missing=missing, invalid=tuple(invalid))
    return ValidationResult(ok=True)
```

他の validator (`assert_calibrate_history_v2`, `assert_run_report_v2`, `assert_diagnostics_v2`) も同様に `ValidationResult` 返却。

### `load()` で v1 検出時 mode 連動 (Round 2 [Critical] 1 反映: 後方互換 flag)

`return_schema_version=False` (default) で既存 `pa.Table` 返却を維持、 `True` で tuple 返却に切替。 段階移行で caller 更新。

```python
from typing import overload

class GenomeArchive:
    # ... 既存 init / flush / collect_* ...

    @staticmethod
    @overload
    def load(
        path: Path,
        *,
        mode: SchemaEnforcementMode = ...,
        return_schema_version: Literal[False] = False,
    ) -> pa.Table: ...

    @staticmethod
    @overload
    def load(
        path: Path,
        *,
        mode: SchemaEnforcementMode = ...,
        return_schema_version: Literal[True],
    ) -> tuple[pa.Table, int | None]: ...

    @staticmethod
    def load(
        path: Path,
        *,
        mode: SchemaEnforcementMode = SchemaEnforcementMode.LOG_ONLY,
        return_schema_version: bool = False,
    ) -> pa.Table | tuple[pa.Table, int | None]:
    """Read archive Parquet (T058: schema_version 検出後方互換).

    Args:
        return_schema_version: True で (table, schema_version: int|None) tuple、
            False (default) で既存 pa.Table を返す。 caller 段階移行用。
    """
    table = pq.read_table(path)
    if "genome_entry_schema_version" not in table.column_names:
        if mode == SchemaEnforcementMode.FAIL_CLOSED:
            raise SchemaVersionError(
                f"v1 archive detected (no genome_entry_schema_version): {path}"
            )
        logger.warning("archive.load.v1_detected", path=str(path))
        if return_schema_version:
            return (table, None)
        return table  # 後方互換 (caller は schema_version 検出不可、 LOG_ONLY なので問題なし)
    versions = table.column("genome_entry_schema_version").to_pylist()
    detected = max(versions) if versions else 2
    if return_schema_version:
        return (table, detected)
    return table
```

新 caller (`run_alpha_sieve` のみ、 Round 5 [Warning] 3 反映) は `return_schema_version=True` で tuple 受け取り、 v1 detect → skip。 `fsp_updater` は **df 単独返却 + helper `_detect_archive_schema_version` 経路**で別 (施策 8 参照、 tuple 受取しない):

```python
# run_alpha_sieve.py 内
table, sv = load(path, mode=mode, return_schema_version=True)
if sv is None:
    logger.warning("alpha_sieve.v1_archive_skipped", path=str(path))
    return  # skip
```

既存 caller (test_archive.py:546 等) は `return_schema_version` 省略で `pa.Table` 受取り維持 (後方互換)。

### テスト計画
- 既存 `tests/alpha_factory/test_archive.py` に追加:
  - `test_genomes_schema_includes_v2_required_fields`
  - `test_create_row_template_initializes_v2_fields_with_defaults`
  - `test_flush_log_only_mode_does_not_raise_on_missing_dataset_epoch_id` (warning のみ、 raise しない確認)
  - `test_flush_fail_closed_mode_raises_on_missing_dataset_epoch_id`
  - `test_flush_injects_dataset_epoch_id_from_run_context`
  - `test_flush_summary_log_aggregates_lint_warnings_per_run` (Codex Round 1 [Suggestion])
  - `test_load_log_only_returns_none_schema_version_for_v1_archive`
  - `test_load_fail_closed_raises_on_v1_archive`
  - `test_load_returns_v2_when_genome_entry_schema_version_present`
  - `test_archive_role_persisted_string_value_in_parquet` (write→read 往復)
  - `test_source_stage_persisted_string_value_in_parquet`
  - `test_genome_archive_init_with_legacy_signature_works_without_run_context` (既存呼出 backward compat)

### リスク
- 既存 **43 col** + 4 col = **47 col** (Codex Round 1 [Warning] 9 + Round 2 [Warning] 6 反映、 33 col 表現は本詳細設計から完全削除)。 Parquet sizing 軽微増 (~5%)
- v1 archive を即時削除しない (T058 では LOG_ONLY skip)、 T067 で FAIL_CLOSED 本格排除

---

## 施策 5: `HistoryRecord` 拡張 + lint 連動

### 変更箇所
- ファイル: `src/alpha_factory/calibrate_gate_history.py` (L33-69: HistoryRecord, L72-78: append_record)

### 波及変更
- `AGENTS.md`: なし
- `scripts/alpha_factory/calibrate_gate.py`: append_record 呼出に dataset_epoch_id 渡し追加

### 現行コード (抜粋)

```python
@dataclass(frozen=True)
class HistoryRecord:
    run_id: str
    # ... 既存 field
    schema_version: int | None = None  # T054 既存
    base_config_hash: str | None = None
    # ... 既存 metadata
```

### 変更後コード

```python
@dataclass(frozen=True)
class HistoryRecord:
    run_id: str
    applied_at: str
    # ... 既存 field 維持 ...
    # T058: v2 必須 (schema_version は v2 = 2 を強制)
    calibrate_history_schema_version: int = 2  # 新規 (既存 schema_version は別目的で維持、 default 2)
    dataset_epoch_id: str = ""  # T058 新設、 必須 (default 空文字は __post_init__ で reject)
    # T054 既存 (維持、 schema_version は legacy だが int | None は引き続き)
    schema_version: int | None = None
    base_config_hash: str | None = None
    full_config_hash: str | None = None
    dataset_span: list[str] | None = None
    instrument: str | None = None
    stage_gate_version: str | None = None
    applied_from_run_id: str | None = None

    def __post_init__(self) -> None:
        # T058: v2 必須検証
        from src.alpha_factory.schema_contract import (
            CALIBRATE_HISTORY_SCHEMA_VERSION,
            validate_epoch_id,
        )
        if self.calibrate_history_schema_version != CALIBRATE_HISTORY_SCHEMA_VERSION:
            raise ValueError(
                f"calibrate_history_schema_version must be {CALIBRATE_HISTORY_SCHEMA_VERSION}, "
                f"got {self.calibrate_history_schema_version}"
            )
        validate_epoch_id(self.dataset_epoch_id)
```

### `append_record` lint (Codex Round 1 [Critical] 4 反映)

既存呼出 (`calibrate_gate.py:452`, `test_calibrate_gate_history.py:59`) は **path positional 引数**。 シグネチャ互換維持:

```python
def append_record(
    record: HistoryRecord,
    path: Path = DEFAULT_HISTORY_PATH,  # positional 互換 (Codex Round 1 [Critical] 4)
    *,
    mode: SchemaEnforcementMode = SchemaEnforcementMode.LOG_ONLY,
) -> None:
    """JSONL 1 行 append-only."""
    record_dict = asdict(record)
    assert_calibrate_history_v2(record_dict, mode=mode)
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record_dict, ensure_ascii=False, default=str)
    with path.open("a", encoding="utf-8") as f:
        f.write(line)
        f.write("\n")
```

### `read_history` で v1 record skip (Codex Round 1 [Critical] 3 反映)

```python
def read_history(
    path: Path = DEFAULT_HISTORY_PATH,
    last_n: int | None = None,
) -> list[HistoryRecord]:
    if not path.exists():
        return []
    records: list[HistoryRecord] = []
    with path.open(encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            try:
                records.append(HistoryRecord(**obj))
            except (TypeError, ValueError):  # T058: v1 record で ValueError raise 可能性
                # v1 record (dataset_epoch_id 不在) は skip + warning
                logger.warning("calibrate_history.v1_record_skipped", obj_keys=sorted(obj.keys()))
                continue
    if last_n is not None:
        records = records[-last_n:]
    return records
```

注: `__post_init__` の `validate_epoch_id` は frozen dataclass 構築時に必ず動く。 v1 record (dataset_epoch_id 不在 or 空) は ValueError raise → read_history で skip。 raw dict 経由 (将来不正な書込) を防ぐため `append_record` の lint も残す。

### HistoryRecord v2 後方互換 (Codex Round 1 [Critical] 3 完全対応)

v1 record の skip 経路を明確化するため、 `HistoryRecord.from_dict_or_none` classmethod を追加:

```python
@classmethod
def from_dict_or_none(cls, obj: Mapping[str, Any]) -> "HistoryRecord | None":
    """v1 record (dataset_epoch_id 不在) は None を返す (skip 用)."""
    if "dataset_epoch_id" not in obj or not obj.get("dataset_epoch_id"):
        return None
    if obj.get("calibrate_history_schema_version") != CALIBRATE_HISTORY_SCHEMA_VERSION:
        return None
    try:
        return cls(**obj)
    except (TypeError, ValueError):
        return None
```

read_history は `from_dict_or_none` を使って明示変換:

```python
record = HistoryRecord.from_dict_or_none(obj)
if record is None:
    logger.warning("calibrate_history.v1_or_invalid_record_skipped", obj_keys=sorted(obj.keys()))
    continue
records.append(record)
```

### テスト計画
- 既存 `tests/alpha_factory/test_calibrate_gate_history.py` に追加:
  - `test_history_record_v2_constructs_with_dataset_epoch_id`
  - `test_history_record_rejects_invalid_epoch_id_grammar`
  - `test_append_record_writes_v2_fields_to_jsonl`
  - `test_append_record_log_only_warns_on_missing_via_raw_dict_path` (lint テスト用、 dataclass バイパス)

### リスク
- 既存 history.jsonl は v1 record (calibrate_history_schema_version 不在) → T058 段階で読み込みは warning skip、 T067 で fail
- T054 既存の `schema_version` field との混同に注意 (本施策では別キー `calibrate_history_schema_version` を新設、 T054 既存は維持)

---

## 施策 6: `calibrate_state` の scope key 拡張

### 変更箇所
- ファイル: `src/alpha_factory/calibrate_state.py` (L44, L159, L194-220)

### 現行コード (`calibrate_state.py:44`)

```python
SCHEMA_VERSION = 1
```

### 変更後コード

```python
SCHEMA_VERSION = 2  # T058: dataset_epoch_id 追加対応
```

### `load_calibrated_threshold` の scope key 拡張 (Round 1+2 反映: 既存関数名維持)

現行 `calibrate_state.py:184` の関数名は `load_calibrated_threshold`。 既存 test 網 (`test_calibrate_state.py:15`) を壊さないため **rename せず**、 既存関数に `dataset_epoch_id` 引数を追加する (Round 2 [Warning] 7 反映)。

T058 では **dataset_span ガードを残しつつ** dataset_epoch_id を **追加条件** (AND 結合) にする。 完全置換は T067 で実施 (epoch_id stub `epoch_legacy` のままで dataset_span を捨てると contamination 再導入のため)。

```python
def load_calibrated_threshold(
    *,
    history_path: Path,  # 現行: 明示渡し維持
    base_config_hash: str,
    dataset_epoch_id: str,  # T058 新設 (追加条件、 唯一の新規引数)
    dataset_span: tuple[str, str],  # 現行型 tuple 維持
    instrument: str,
    stage_gate_version: str,
    threshold_floor: float = -100.0,  # 現行 default 維持 (Round 6 [Critical] 1)
    threshold_ceiling: float = 100.0,  # 現行 default 維持 (Round 6 [Critical] 1)
) -> float | None:
    """T058: T054 dataset_span ガードに dataset_epoch_id 追加条件 (AND 結合).

    既存全引数 (history_path 明示、 dataset_span tuple、 threshold_floor/ceiling default)
    を完全維持し、 dataset_epoch_id のみ追加 (Round 5+6 [Critical])。
    """
    records = read_history(path=history_path)
    for rec in reversed(records):
        if rec.schema_version != SCHEMA_VERSION:
            continue
        if rec.base_config_hash != base_config_hash:
            continue
        if rec.dataset_span != dataset_span:  # T054 既存 (T058 段階は維持)
            continue
        # T058: 新規 scope (epoch stub `epoch_legacy` でも match して安全)
        if rec.dataset_epoch_id != dataset_epoch_id:
            continue
        if rec.instrument != instrument:
            continue
        if rec.stage_gate_version != stage_gate_version:
            continue
        # ... 既存 isfinite / range check
        return rec.new_threshold  # 現行戻り値型 float | None 維持
    return None
```

T067 完了後 (T067 内で synthesis § 12 に従い実施):
- T067 切替コミットで `dataset_span` argument を削除、 dataset_epoch_id 単独 scope に
- 旧 v1 record は schema_version 不一致で自動排除

### 呼出元 `run_ga.py:1078` 修正 (Round 5+6 [Critical] 反映)

現行 (`run_ga.py:1078`) は `history_path` 明示 + `dataset_span` tuple、 `threshold_floor`/`threshold_ceiling` は関数 default に任せて caller では渡さない。 T058 では **`dataset_epoch_id` だけ追加**、 既存 caller pattern を完全維持:

```python
dataset_span = (str(cfg.dataset.start), str(cfg.dataset.end))  # 現行 tuple 維持
calibrated = load_calibrated_threshold(
    history_path=history_path,  # 現行: 明示渡し
    base_config_hash=base_config_hash,
    dataset_epoch_id=run_context.dataset_epoch_id,  # T058 新規 (唯一の追加)
    dataset_span=dataset_span,
    instrument=run_context.instrument,
    stage_gate_version=stage_gate_version,
    # threshold_floor / threshold_ceiling は関数 default (-100.0 / 100.0) を使用、 caller では渡さない (現行 pattern 維持)
)
```

### テスト計画
- `tests/alpha_factory/test_calibrate_state.py` に追加:
  - `test_load_calibrated_threshold_filters_by_dataset_epoch_id`
  - `test_load_calibrated_threshold_returns_none_for_v1_records`
  - `test_load_calibrated_threshold_skips_record_with_different_epoch_id`

### リスク
- 既存 history.jsonl の record は schema_version=1 → 自動排除で再校正必要 (big-bang 前提なので OK、 T067 で排除完成)

---

## 施策 7: `diagnostics_sidecar` 拡張 + lint 連動

### 変更箇所
- ファイル: `src/alpha_factory/diagnostics_sidecar.py` (L34: build_sidecar_table, L50: write_stage_a_provenance)

### 変更後コード (Round 3 [Critical] 5 反映: 既存 signature 完全維持 + 返り値 `Path | None` 維持)

現行 `diagnostics_sidecar.py:62, 67-70` の signature:
- `build_sidecar_table(rows: Sequence[dict]) -> pa.Table` ← **rows 受取** (collector ではない)
- `write_stage_a_provenance(collector: DiagnosticsCollector, output_path: Path) -> Path | None` ← 返り値 Path|None (None 時は書込失敗)

既存 caller (`run_ga.py:1446`) を壊さないため、 既存 signature を完全維持し `run_context` / `mode` を optional kwargs として追加するのみ。

```python
# diagnostics_sidecar.py: 既存 schema (10 列) に T058 列を明示追加
STAGE_A_PROVENANCE_SCHEMA: Final[pa.Schema] = pa.schema(
    [
        # T058 新規 (先頭)
        pa.field("diagnostics_schema_version", pa.int32(), nullable=False),
        pa.field("dataset_epoch_id", pa.string(), nullable=False),
        # 既存 10 列 (維持)
        pa.field("lane_id", pa.string(), nullable=False),
        pa.field("generation", pa.int32(), nullable=False),
        pa.field("individual_name", pa.string(), nullable=False),
        pa.field("metric_stage", pa.string(), nullable=False),
        pa.field("trade_count", pa.int32(), nullable=False),
        pa.field("total_pnl_stage_a", pa.float64(), nullable=False),
        pa.field("sharpe_stage_a", pa.float64(), nullable=True),
        pa.field("stage_a_pass", pa.bool_(), nullable=False),
        pa.field("stage_b_pass", pa.bool_(), nullable=True),
        pa.field("stage_c_pass", pa.bool_(), nullable=True),
    ]
)


def build_sidecar_table(
    rows: Sequence[dict[str, Any]],  # 既存契約維持: rows 受取 (collector ではない)
    *,
    run_context: RunContext | None = None,  # T058 optional 追加
    mode: SchemaEnforcementMode = SchemaEnforcementMode.LOG_ONLY,
) -> pa.Table:
    """既存契約維持 + T058 optional kwargs."""
    enriched = list(rows)  # mutate 防止
    for row in enriched:
        if "dataset_epoch_id" not in row or not row.get("dataset_epoch_id"):
            row["dataset_epoch_id"] = (
                run_context.dataset_epoch_id if run_context else "epoch_legacy"
            )
        row.setdefault("diagnostics_schema_version", DIAGNOSTICS_SCHEMA_VERSION)
        assert_diagnostics_v2(row, mode=mode)
    return pa.Table.from_pylist(enriched, schema=STAGE_A_PROVENANCE_SCHEMA)


def write_stage_a_provenance(
    collector: DiagnosticsCollector,  # 既存 signature 維持
    output_path: Path,
    *,
    run_context: RunContext | None = None,  # T058 optional 追加
    mode: SchemaEnforcementMode = SchemaEnforcementMode.LOG_ONLY,
) -> Path | None:  # 既存返り値型 Path | None 維持
    """既存契約維持 + T058 optional kwargs。 fail-open は既存通り."""
    rows = collector.to_rows()
    if not rows:
        logger.info("diagnostics_sidecar.empty", output_path=str(output_path))
        return None
    try:
        table = build_sidecar_table(rows, run_context=run_context, mode=mode)
        pq.write_table(table, output_path)
        return output_path
    except Exception as exc:  # 既存 fail-open 維持
        logger.warning("diagnostics_sidecar.write_failed", error=str(exc))
        return None
```

caller `run_ga.py:1446` 側は run_context が確定した時点で kwarg 追加するだけ:

```python
write_stage_a_provenance(
    collector,
    output_path,
    run_context=run_context,  # T058
    mode=cfg.schema_contract.to_mode(),  # T058
)
```

`run_context=None` のままの呼出は `epoch_legacy` を fallback として使用、 LOG_ONLY default で動作 (warning のみ、 fail させない)。

### テスト計画
- `tests/alpha_factory/test_diagnostics_sidecar.py` に追加:
  - `test_stage_a_provenance_schema_includes_v2_required_fields`
  - `test_build_sidecar_table_injects_dataset_epoch_id_from_run_context`
  - `test_write_stage_a_provenance_includes_v2_metadata`
  - `test_diagnostics_lint_log_only_warns_on_missing_field` (mock logger)
  - `test_diagnostics_lint_fail_closed_raises_on_missing_field`

### リスク
- 既存 sidecar Parquet は v1 (no dataset_epoch_id) → T058 段階で skip、 T067 排除

---

## 施策 8: `fsp_updater` で v2 propagate

### 変更箇所
- ファイル: `src/alpha_factory/fsp_updater.py` (L114: _read_archive_with_fsp_compat, _atomic_write_parquet)

### 変更後コード (Round 2 [Critical] 5 反映: 互換レイヤ + caller 全更新リスト)

既存 `_read_archive_with_fsp_compat` / `_atomic_write_parquet` の caller (`fsp_updater.py:398`、 `test_fsp_updater.py:265`) は旧契約 (df 単独返却 / mode kwarg なし) を前提にしている。 後方互換のため以下の戦略:

1. **新 caller 用に kwarg 追加** (default 引数で旧 caller 互換維持)
2. **戻り値は単独 df のままに維持** (schema_version 検出は新規 helper 関数 `_detect_archive_schema_version()` で別経路提供)

```python
def _detect_archive_schema_version(table: pa.Table) -> int | None:
    """T058: schema_version 検出 helper (FSP 読込後の判定用)."""
    if "genome_entry_schema_version" not in table.column_names:
        return None
    versions = table.column("genome_entry_schema_version").to_pylist()
    return max(versions) if versions else 2


def _read_archive_with_fsp_compat(
    path: Path,
    *,
    mode: SchemaEnforcementMode = SchemaEnforcementMode.LOG_ONLY,
) -> pd.DataFrame:
    """既存返却 (df 単独) 維持。 v1 検出は内部 _detect_archive_schema_version で."""
    table = pq.read_table(path)
    sv = _detect_archive_schema_version(table)
    if sv is None:
        if mode == SchemaEnforcementMode.FAIL_CLOSED:
            raise SchemaVersionError(f"FSP read: v1 archive: {path}")
        logger.warning("fsp_updater.v1_archive_detected", path=str(path))
        # LOG_ONLY: 既存挙動 (df 返却) 維持。 caller は schema_version=None を別経路で確認可
    return table.to_pandas()


def _atomic_write_parquet(
    df: pd.DataFrame,
    target_path: Path,
    schema: pa.Schema,  # 現行必須 (Round 3 [Critical] 6 反映)
    *,
    mode: SchemaEnforcementMode = SchemaEnforcementMode.LOG_ONLY,
) -> None:
    """T058 mode 連動 (kwarg は default で旧 caller 互換維持).

    既存 signature `(df, target_path, schema)` 維持、 mode のみ kwarg 追加。
    """
    required = {"genome_entry_schema_version", "dataset_epoch_id"}
    missing = required - set(df.columns)
    if missing:
        if mode == SchemaEnforcementMode.FAIL_CLOSED:
            raise SchemaContractError(f"FSP archive write missing v2 fields: {missing}")
        logger.warning(
            "fsp_updater.write.v2_fields_missing",
            missing=sorted(missing),
            path=str(target_path),
        )
        # LOG_ONLY: 最善努力で書込 (grammar 適合 fallback `epoch_legacy` を補完)
        for col in missing:
            df[col] = "epoch_legacy" if col == "dataset_epoch_id" else 2
    # ... existing atomic write (tmp → fsync → rename)
```

### Caller 全更新リスト (Round 2 [Critical] 5 + Round 5 [Warning] 4 反映)

| caller | 変更 |
|---|---|
| `fsp_updater.py:398, 412, 443, 465, 497` (内部 caller、 同 module 内の `_atomic_write_parquet` 呼出) | 新 kwarg `mode` を `cfg.schema_contract.to_mode()` から伝搬 (FSP updater entry point から layer down)。 既存 default で動作維持 |
| `test_fsp_updater.py:265` 等 | 既存 test は kwarg 省略で動作 (LOG_ONLY default)、 新 test (mode=FAIL_CLOSED + v1 archive) を追加 |

注: 現行 `run_ga.py` には FSP updater の直接呼出は無い (`scripts/alpha_factory/run_ga.py` 全体を grep 確認済、 Round 5 [Warning] 4 反映で削除)。 FSP は post-RUN updater として独立スクリプト経由で呼ばれる経路のみ更新対象。 将来 `run_ga.py` から FSP updater を呼ぶようになった場合は別 TODO で kwarg 伝搬を追加。

### テスト計画 (Round 4 [Warning] 2 反映: helper 直接検証)
- `tests/alpha_factory/test_fsp_updater.py` に追加:
  - `test_detect_archive_schema_version_returns_none_for_v1_table` (helper 直接検証)
  - `test_detect_archive_schema_version_returns_2_for_v2_table` (helper 直接検証)
  - `test_read_archive_log_only_warns_on_v1` (df 単独返却維持の確認、 warning ログ assert)
  - `test_read_archive_fail_closed_raises_on_v1`
  - `test_atomic_write_log_only_warns_and_fills_defaults_when_v2_fields_missing`
  - `test_atomic_write_fail_closed_raises_when_v2_fields_missing`

---

## 施策 9: `run_ga.py` で `RunContext` 生成 + 全 artifact propagate

### 変更箇所
- ファイル: `scripts/alpha_factory/run_ga.py`
  - L998-1010: history.json / best_genome.json / population.jsonl 生成
  - L875: summary.json 生成
  - L1075: calibrate-gate threshold 解決 (load_calibrated_threshold 呼出)
  - L1479: run cache JSON 生成
  - 新規: `RunContext` 生成箇所 (起動初期、 T059 完了後にここで dataset_epoch_id 確定)

### 変更後コード (擬似)

```python
def main():
    # ... config 読込

    # T058: RunContext 生成 (T059 で dataset_epoch_id 値生成、 ここでは仮置き)
    # 注: T059 完了前は固定 epoch_id "epoch_legacy" で動作 (LOG_ONLY mode で破綻しない)
    dataset_epoch_id = generate_epoch_id(cfg.dataset)  # T059 で実装、 T058 stub
    run_context = RunContext(
        run_id=run_id,
        run_number=run_number,
        dataset_epoch_id=dataset_epoch_id,
        base_config_hash=compute_base_config_hash(cfg),
        instrument=cfg.dataset.instrument,
    )

    # archive 生成時に注入 (out_dir は __init__ に渡さない、 flush(output_dir=...) で渡す)
    archive = GenomeArchive(
        run_id=run_id,
        run_number=run_number,
        run_context=run_context,
        enforcement_mode=cfg.schema_contract.to_mode(),
    )
    # ... GA 評価ループ ...
    # 末尾で flush
    archive.flush(output_dir=archive_dir)

    # summary.json (Tier 1)
    summary = {
        "schema_version": "1.1",  # 既存維持 (string)
        "cascade_contract_version": CASCADE_CONTRACT_VERSION,  # T058 新規 (int=2)
        "dataset_epoch_id": dataset_epoch_id,
        "run_id": run_id,
        # ... 既存 fields
    }
    assert_run_report_v2(summary, mode=cfg.schema_contract.to_mode())

    # population.jsonl, history.json (list), best_genome.json, run cache JSON にも propagate
    # Codex Round 1 [Warning] 7 反映: history.json は list 形式維持 (現行 run_ga.py:984, analyze_run.py:40)
    # 各 entry (per-generation) に dataset_epoch_id を含める
    history_json: list[dict] = []  # 既存: list of per-generation snapshots
    for snap in per_generation_snapshots:
        snap["dataset_epoch_id"] = dataset_epoch_id
        history_json.append(snap)

    # best_genome.json は既存 dict 形式
    best_genome_json["dataset_epoch_id"] = dataset_epoch_id

    # population.jsonl は per-line dict、 各行に dataset_epoch_id 追加
    for line_dict in population_lines:
        line_dict["dataset_epoch_id"] = dataset_epoch_id

    # run cache JSON (`.cache/alpha_factory/runs/{run_id}.json`)
    run_cache_json["dataset_epoch_id"] = dataset_epoch_id
```

### `generate_epoch_id` stub (T059 で本格実装)

T058 段階では仮 stub を `src/alpha_factory/run_context.py` に置き、 T059 が置き換える:

```python
# T058 stub: T059 で deterministic 生成に置換
def generate_epoch_id_stub(dataset_cfg: DatasetConfig) -> str:
    """Returns "epoch_legacy" until T059 implements deterministic generation."""
    return "epoch_legacy"
```

### テスト計画
- `tests/scripts/test_run_ga_parallel.py` に追加:
  - `test_summary_json_includes_cascade_contract_version_and_dataset_epoch_id`
  - `test_summary_json_schema_version_remains_string_one_one` (既存 test 補強)
  - `test_history_json_includes_dataset_epoch_id`
  - `test_best_genome_json_includes_dataset_epoch_id`
  - `test_run_cache_json_includes_dataset_epoch_id`
  - `test_cascade_contract_version_is_int_in_summary_json` (型固定テスト)

### リスク
- 既存 `summary.json` 構造維持 (`schema_version: "1.1"` string) は test 互換性のため重要

---

## 施策 10: `run_alpha_sieve` loader を mode 連動

### 変更箇所
- ファイル: `scripts/alpha_factory/run_alpha_sieve.py` (L220 付近: archive 読込)

### 変更後コード (Round 3 [Critical] 4 + Round 4 [Warning] 1 反映: `GenomeArchive.load(..., return_schema_version=True)` で tuple 受取)

現行 `run_alpha_sieve.py:222` は `GenomeArchive.load` を使用 (module-level `load` ではない)。 既存 import 経路を維持:

```python
from src.alpha_factory.archive import GenomeArchive
from src.alpha_factory.schema_contract import SchemaEnforcementMode

mode = cfg.schema_contract.to_mode()  # T058 段階は LOG_ONLY、 T067 で FAIL_CLOSED
table, sv = GenomeArchive.load(
    archive_path,
    mode=mode,
    return_schema_version=True,  # 新 caller は tuple 受取
)
if sv is None:
    # FAIL_CLOSED は load 内で SchemaVersionError raise 済 → 到達不可
    # LOG_ONLY のみここに到達 (warning は load 内で出力済)
    logger.warning("alpha_sieve.v1_archive_skipped", path=str(archive_path))
    return  # sieve 結果から除外
# v2 archive 処理 (table を sieve に流す)
```

### テスト計画
- `tests/scripts/test_run_alpha_sieve.py` に追加:
  - `test_run_alpha_sieve_log_only_skips_v1_archive_with_warning`
  - `test_run_alpha_sieve_fail_closed_raises_on_v1_archive`
  - `test_run_alpha_sieve_v2_archive_processed_normally`

---

## 施策 11: Tier 2 軽量ガード

### 変更箇所
- `scripts/alpha_factory/extract_batch_metrics.py:134, 280`
- `scripts/alpha_factory/generate_run_report.py:800`
- `scripts/alpha_factory/compare_batch_runs.py:252, 256, 262`
- `scripts/alpha_factory/analyze_run.py:168`

### 変更後コード (擬似、 各スクリプトで)

```python
from src.alpha_factory.schema_contract import assert_epoch_id_present_for_display

def write_summary_section(summary: dict, ...):
    assert_epoch_id_present_for_display(summary, artifact="run_report.md")
    # ... existing render logic
```

### テスト計画
- `tests/scripts/test_tier2_epoch_id_propagation.py` (新規)
  - `test_run_report_md_includes_dataset_epoch_id_in_header`
  - `test_batch_summary_json_preserves_per_run_dataset_epoch_id`
  - `test_comparison_report_md_references_dataset_epoch_id`
  - `test_analyze_run_md_references_dataset_epoch_id`
  - `test_extract_batch_metrics_report_md_includes_dataset_epoch_id`

### リスク
- 軽量ガードは fail させないので副作用なし、 warning のみ

---

## 施策 12: テスト総合 (重複説明省略)

各施策に test 追加。 加えて統合テスト:

- `tests/alpha_factory/test_t058_integration.py` (新規)
  - `test_end_to_end_writes_v2_archive_with_all_required_fields`
  - `test_end_to_end_writes_v2_calibrate_history_with_dataset_epoch_id`
  - `test_end_to_end_writes_v2_summary_json`
  - `test_end_to_end_propagates_epoch_id_to_tier2_outputs`

---

## 実装モード

| 項目 | 内容 |
|------|------|
| 推奨モード | **incremental** (12 施策を独立 PR で順次マージ可能、 ただし最低でも施策 1-3 + 4 を同時着地) |
| 判断根拠 | schema_contract.py / run_context.py / config.py は前提なので最初に。 archive.py 変更でテスト pass 必須。 calibrate / diagnostics / fsp / run_ga / sieve / Tier 2 は後段で incremental |
| 競合リスク | T059 (Epoch Manager) と並行実装する場合、 `generate_epoch_id_stub` の置換タイミングで小衝突 (逐次マージで解消) |
| 想定実装時間 | 中 (12 施策 × ~30-60 分/施策 = 6-12h、 テスト含む) |

---

## 実装順序 (incremental 推奨)

1. **施策 1 + 2 + 3** (schema_contract.py / run_context.py / config.py) を 1 PR で着地 (基盤確定)
2. **施策 4** (archive.py) を 1 PR (既存 test pass 確認、 v2 field 追加だけで CI green)
3. **施策 5 + 6** (calibrate_gate_history.py + calibrate_state.py) を 1 PR
4. **施策 7 + 8** (diagnostics + fsp_updater) を 1 PR
5. **施策 9 + 10** (run_ga.py + run_alpha_sieve.py) を 1 PR (RunContext 注入完成)
6. **施策 11** (Tier 2 軽量ガード) を 1 PR
7. **施策 12** (統合テスト) を最終 PR

---

## DoD (Definition of Done)

T058 完了の判定基準:

### コード DoD
- [ ] 12 施策全てのコード変更が main にマージ済
- [ ] `uv run pytest tests/alpha_factory/test_schema_contract.py` 全 pass
- [ ] `uv run pytest tests/alpha_factory/test_run_context.py` 全 pass
- [ ] `uv run pytest tests/alpha_factory/test_archive.py` 全 pass (v2 schema 追加 test 含む、 既存呼出 backward compat 含む)
- [ ] `uv run pytest tests/alpha_factory/test_calibrate_gate_history.py` 全 pass (v1 record skip テスト含む)
- [ ] `uv run pytest tests/scripts/test_calibrate_gate_drift.py` 全 pass (Codex Round 1+2 [REQUEST_CHANGES] 12: 波及更新、 path 修正済)
- [ ] `uv run pytest tests/alpha_factory/test_calibrate_state.py` 全 pass (dataset_span + dataset_epoch_id 両方の scope key 確認)
- [ ] `uv run pytest tests/alpha_factory/test_diagnostics_sidecar.py` 全 pass (STAGE_A_PROVENANCE_SCHEMA 列追加確認)
- [ ] `uv run pytest tests/alpha_factory/test_fsp_updater.py` 全 pass (mode 連動確認)
- [ ] `uv run pytest tests/alpha_factory/test_t058_integration.py` 全 pass
- [ ] `uv run pytest tests/scripts/test_run_ga_parallel.py` (cascade_contract_version + dataset_epoch_id 含む、 既存 schema_version: "1.1" 維持確認)
- [ ] `uv run pytest tests/scripts/test_run_alpha_sieve.py` 全 pass (LOG_ONLY skip / FAIL_CLOSED raise 両 path)
- [ ] `uv run pytest tests/scripts/test_tier2_epoch_id_propagation.py` 全 pass
- [ ] `uv run ruff check src/ tests/` clean
- [ ] `uv run mypy src/` clean

### Config / Smoke DoD
- [ ] `config/alpha_factory/default.yaml` に `schema_contract.enforcement_mode: log_only` 反映
- [ ] 1 Run smoke 実行で v2 archive が生成され、 v2 contract lint が log warning なしで通過 (T059 stub epoch_id `epoch_legacy` でも OK)
- [ ] `RunContext` が archive / calibrate / diagnostics の主要 3 component に注入されている
- [ ] T067 切替準備として `enforcement_mode=fail_closed` で smoke を試走し、 既存 v1 artifact があれば期待通り fail することを確認

### Docs / Skill DoD (Codex Round 1 [Warning] 10 反映)
- [ ] `docs/alpha_factory/stage-gates.md` § "T054: state file 経由の自動適用" を更新 (T058 で dataset_epoch_id 追加条件、 完全置換は T067 と明記)
- [ ] `.claude/skills/zenigame-fx-calibrate-gate/SKILL.md:99` 付近の現行契約 (schema_version=1, dataset_span guard) を T058 反映 (v2 + dataset_epoch_id 追加条件)

---

## 関連 / 後段 TODO

- T059: dataset_epoch_id 値生成 (本施策の `generate_epoch_id_stub` を置換)
- T063-T064: archive_role / source_stage の値書込
- T066: archive admission での archive_role 設定
- T067: enforcement_mode を log_only → fail_closed に切替、 RunContext 全 component 注入完成、 旧 v1 archive 排除
- T075: 旧 v1 archive Parquet 物理削除
