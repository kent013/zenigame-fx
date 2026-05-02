"""T040: calibrate-gate decision history (JSONL append-only persistence).

`scripts/alpha_factory/calibrate_gate.py` が threshold 調整 decision を
``reports/calibrate-gate/history.jsonl`` に追記し、`calibrate_gate_drift.py`
CLI が直近 N Run を集計・drift 警告を出力する。

判断主体は人間。本機構は記録・集計のみ (C3 collider bias 回避、calibrate-gate
制御則は変更しない)。

詳細: devnotes/20260426-0024-calibrate-gate-drift-monitor/

T058 (PR 3): HistoryRecord を v2 schema に拡張。 ``calibrate_history_schema_version``
+ ``dataset_epoch_id`` を必須化し、 ``__post_init__`` で grammar 検証を行う。
``append_record`` は ``assert_calibrate_history_v2`` で passive lint。 v1 record は
``read_history`` で skip + warning。 詳細:
``devnotes/20260429-1912-todo-T058-schema-v2-contract/detailed-design.md`` 施策 5。
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import structlog

from src.alpha_factory.schema_contract import (
    CALIBRATE_HISTORY_SCHEMA_VERSION,
    SchemaContractError,
    SchemaEnforcementMode,
    assert_calibrate_history_v2,
    validate_epoch_id,
)

__all__ = [
    "DEFAULT_HISTORY_PATH",
    "DriftAlerts",
    "DriftAnalysis",
    "HistoryRecord",
    "append_record",
    "compute_drift",
    "read_history",
]

logger = structlog.get_logger(__name__)

DEFAULT_HISTORY_PATH: Path = Path("reports/calibrate-gate/history.jsonl")


@dataclass(frozen=True)
class HistoryRecord:
    """1 Run 1 record. JSONL の 1 行 = 1 dict (asdict で serialize).

    T058 v2: ``calibrate_history_schema_version`` (= 2) と ``dataset_epoch_id``
    を必須化。 ``__post_init__`` で grammar / version 検証を行う。
    既存 ``schema_version`` (T054) は別目的で維持 (state file load の互換性
    識別子)。
    """

    run_id: str
    applied_at: str  # ISO 8601 (JST or UTC、loader 側の責務)
    n_rows_total: int
    n_rows_used: int
    aggregation_mode: str
    aggregation_window: int
    actual_pass_rate: float
    target_pass_rate: float
    tol: float
    prev_threshold: float
    new_threshold: float
    delta: float
    decision: str
    var_fitness_pen: float | None
    clamped_by_delta: bool
    clamped_by_floor_or_ceiling: bool
    stage_b_pass_count: int
    stage_c_pass_count: int
    # Codex round-1 [Critical] 対応: MonitoringMetrics.live_criteria_gap は
    # dict[str, float] (未達量、live_criteria 各軸の非負 gap)。スカラーではなく
    # dict のまま JSONL に保存し、SSoT 矛盾を解消する。空 dict は「達成 (gap無し)」
    # を意味する。
    live_criteria_gap: dict[str, float]
    # T058 (PR 3): v2 必須 (default 値で keyword 互換、 __post_init__ で検証)。
    calibrate_history_schema_version: int = CALIBRATE_HISTORY_SCHEMA_VERSION
    dataset_epoch_id: str = ""
    # T054: cross-run contamination guard 用メタデータ (optional、後方互換)。
    # 既存 record (これらが None) は state file load 時に schema_version 不一致で
    # 適用 skip となる (fail-closed)。新規書き込みでは必ず set される。
    schema_version: int | None = None
    base_config_hash: str | None = None
    full_config_hash: str | None = None
    dataset_span: list[str] | None = None  # [start, end] の string 2-tuple
    instrument: str | None = None
    stage_gate_version: str | None = None
    # T077 (cascade port v2 follow-up): v2 必須 (None 不可、 空文字 不可).
    # Round 21 までは Optional だったが Round 22 → 実装で必須化に統一.
    # 既存 v1 record (= dataset_epoch_id 不在) は from_dict_or_none で早期 None
    # return されるため本 type 制約は v2 record のみに適用.
    applied_from_run_id: str = ""

    def __post_init__(self) -> None:
        """T058 v2 必須検証: schema_version 一致 + dataset_epoch_id grammar.

        T077 追加: applied_from_run_id 必須化 (= 空文字 / None 不可、 v2 record で
        cross-run contamination guard が機能するための前提条件).
        """
        if (
            self.calibrate_history_schema_version
            != CALIBRATE_HISTORY_SCHEMA_VERSION
        ):
            raise ValueError(
                "calibrate_history_schema_version must be "
                f"{CALIBRATE_HISTORY_SCHEMA_VERSION}, "
                f"got {self.calibrate_history_schema_version}"
            )
        # validate_epoch_id は SchemaContractError (= ValueError 派生) を raise
        validate_epoch_id(self.dataset_epoch_id)
        # T077: applied_from_run_id 必須化 (= None / 空文字 reject、
        # cross-run contamination guard 用メタデータ確実性確保).
        if not isinstance(self.applied_from_run_id, str):
            raise ValueError(
                "HistoryRecord.applied_from_run_id must be non-empty str "
                f"(T077 v2 必須化), got type {type(self.applied_from_run_id).__name__}"
            )
        if not self.applied_from_run_id:
            raise ValueError(
                "HistoryRecord.applied_from_run_id must be non-empty str "
                "(T077 v2 必須化、 空文字 / None reject)"
            )

    @classmethod
    def from_dict_or_none(cls, obj: Mapping[str, Any]) -> HistoryRecord | None:
        """v1 record (dataset_epoch_id 不在) は None を返す (skip 用).

        v2 record は ``cls(**obj)`` で構築。 不正 record (TypeError /
        ValueError / SchemaContractError) も None を返し、 caller 側で
        skip + warning。 ``SchemaContractError`` は ``ValueError`` 派生だが
        defensive に明示追記 (Codex impl-review-pr3 round 1 [Critical] 1)。
        """
        if "dataset_epoch_id" not in obj or not obj.get("dataset_epoch_id"):
            return None
        if obj.get("calibrate_history_schema_version") != (
            CALIBRATE_HISTORY_SCHEMA_VERSION
        ):
            return None
        try:
            return cls(**obj)
        except (TypeError, ValueError, SchemaContractError):
            return None


def append_record(
    record: HistoryRecord,
    path: Path = DEFAULT_HISTORY_PATH,
    *,
    mode: SchemaEnforcementMode = SchemaEnforcementMode.LOG_ONLY,
) -> None:
    """JSONL 1 行を append-only で追記する (parent dir 自動作成).

    T058 (PR 3): 書込前に ``assert_calibrate_history_v2`` で passive lint。
    LOG_ONLY mode (default) では warning + Counter のみ、 FAIL_CLOSED で
    必須 field 欠落時に SchemaContractError raise。
    """
    record_dict = asdict(record)
    assert_calibrate_history_v2(record_dict, mode=mode)
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record_dict, ensure_ascii=False, default=str)
    with path.open("a", encoding="utf-8") as f:
        f.write(line)
        f.write("\n")


def read_history(
    path: Path = DEFAULT_HISTORY_PATH,
    last_n: int | None = None,
) -> list[HistoryRecord]:
    """JSONL を読み HistoryRecord list を返す。

    Args:
        path: history.jsonl path (default: reports/calibrate-gate/history.jsonl)
        last_n: 末尾 N 行のみ取得 (None なら全行)。

    Returns:
        新しい順ではなく **追記順** (古い→新しい) の list。
        ファイル不在 / 空なら空 list。

    T058 (PR 3): v1 record (dataset_epoch_id 不在) と invalid record は
    ``HistoryRecord.from_dict_or_none`` 経由で skip + warning log を出力する。
    """
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
                # 破損行は skip (defensive、ログ出力は CLI 側の責務)
                continue
            if not isinstance(obj, dict):
                continue
            record = HistoryRecord.from_dict_or_none(obj)
            if record is None:
                logger.warning(
                    "calibrate_history.v1_or_invalid_record_skipped",
                    obj_keys=sorted(obj.keys()),
                )
                continue
            records.append(record)
    if last_n is not None and last_n >= 0:
        records = records[-last_n:]
    return records


@dataclass(frozen=True)
class DriftAlerts:
    """drift 判定結果 (3 ルール)。1 つでも True で warning レベル."""

    monotone_tighten: bool
    monotone_loosen: bool
    threshold_clamp: bool
    pass_rate_band_excess: bool

    @property
    def any_alert(self) -> bool:
        return (
            self.monotone_tighten
            or self.monotone_loosen
            or self.threshold_clamp
            or self.pass_rate_band_excess
        )


@dataclass(frozen=True)
class DriftAnalysis:
    """直近 N Run の drift 分析結果 (records + alerts + summary stats).

    T069: ``n_skip_frozen`` を追加 (epoch 内 freeze 判定で
    ``decision="skip_frozen"`` となった record 数)。 drift 監視で freeze 中は
    monotone alert に寄与しないことを可視化する。
    """

    records: tuple[HistoryRecord, ...]
    alerts: DriftAlerts
    n_tighten: int
    n_loosen: int
    n_in_band: int
    n_skip_frozen: int  # T069: epoch 内 3 Run freeze 集計
    n_clamped_floor_ceiling: int
    max_abs_gap: float


def compute_drift(
    records: Iterable[HistoryRecord],
    *,
    monotone_threshold: int = 4,
    clamp_threshold: int = 3,
    band_multiplier: float = 2.0,
) -> DriftAnalysis:
    """直近 N record から drift 判定を出す。

    judgement rules (Phase 1 conservative):
    - monotone_tighten: 直近 N で tighten が monotone_threshold 回以上
    - monotone_loosen: 同上 loosen
    - threshold_clamp: clamped_by_floor_or_ceiling が clamp_threshold 回以上
    - pass_rate_band_excess: いずれかの record で |actual - target| > band_multiplier * tol
    """
    rec_tuple = tuple(records)
    n_tighten = sum(1 for r in rec_tuple if r.decision == "tighten")
    n_loosen = sum(1 for r in rec_tuple if r.decision == "loosen")
    n_in_band = sum(1 for r in rec_tuple if r.decision == "in_band")
    # T069: epoch 内 freeze 判定 record の集計 (synthesis § 8.6)
    n_skip_frozen = sum(1 for r in rec_tuple if r.decision == "skip_frozen")
    n_clamped = sum(
        1 for r in rec_tuple if r.clamped_by_floor_or_ceiling
    )
    gaps = [r.actual_pass_rate - r.target_pass_rate for r in rec_tuple]
    abs_gaps = [abs(g) for g in gaps]
    max_abs_gap = max(abs_gaps) if abs_gaps else 0.0
    band_excess = any(
        abs(r.actual_pass_rate - r.target_pass_rate)
        > band_multiplier * r.tol
        for r in rec_tuple
    )
    alerts = DriftAlerts(
        monotone_tighten=n_tighten >= monotone_threshold,
        monotone_loosen=n_loosen >= monotone_threshold,
        threshold_clamp=n_clamped >= clamp_threshold,
        pass_rate_band_excess=band_excess,
    )
    return DriftAnalysis(
        records=rec_tuple,
        alerts=alerts,
        n_tighten=n_tighten,
        n_loosen=n_loosen,
        n_in_band=n_in_band,
        n_skip_frozen=n_skip_frozen,
        n_clamped_floor_ceiling=n_clamped,
        max_abs_gap=max_abs_gap,
    )
