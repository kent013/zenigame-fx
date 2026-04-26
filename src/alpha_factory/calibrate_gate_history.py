"""T040: calibrate-gate decision history (JSONL append-only persistence).

`scripts/alpha_factory/calibrate_gate.py` が threshold 調整 decision を
``reports/calibrate-gate/history.jsonl`` に追記し、`calibrate_gate_drift.py`
CLI が直近 N Run を集計・drift 警告を出力する。

判断主体は人間。本機構は記録・集計のみ (C3 collider bias 回避、calibrate-gate
制御則は変更しない)。

詳細: devnotes/20260426-0024-calibrate-gate-drift-monitor/
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from pathlib import Path

__all__ = [
    "DEFAULT_HISTORY_PATH",
    "DriftAlerts",
    "DriftAnalysis",
    "HistoryRecord",
    "append_record",
    "compute_drift",
    "read_history",
]

DEFAULT_HISTORY_PATH: Path = Path("reports/calibrate-gate/history.jsonl")


@dataclass(frozen=True)
class HistoryRecord:
    """1 Run 1 record. JSONL の 1 行 = 1 dict (asdict で serialize)."""

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


def append_record(record: HistoryRecord, path: Path = DEFAULT_HISTORY_PATH) -> None:
    """JSONL 1 行を append-only で追記する (parent dir 自動作成)。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(asdict(record), ensure_ascii=False, default=str)
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
            try:
                records.append(HistoryRecord(**obj))
            except TypeError:
                # スキーマ不整合 (古い record / 新規 field 追加直後) は skip
                continue
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
    """直近 N Run の drift 分析結果 (records + alerts + summary stats)."""

    records: tuple[HistoryRecord, ...]
    alerts: DriftAlerts
    n_tighten: int
    n_loosen: int
    n_in_band: int
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
        n_clamped_floor_ceiling=n_clamped,
        max_abs_gap=max_abs_gap,
    )
