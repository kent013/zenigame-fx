"""T054: calibrate-gate state file 読込（cross-run contamination guard 付き）。

`scripts/alpha_factory/calibrate_gate.py` が `reports/calibrate-gate/history.jsonl`
に追記する decision record から、次 RUN 開始時に effective threshold を読み出す。

設計根拠:
    - devnotes/20260427-1856-stage-pipeline-health-fix/conceptual-design.md
    - devnotes/20260427-1856-stage-pipeline-health-fix/detailed-design.md §施策 A

cross-run contamination 防止:
    - SCHEMA_VERSION による record format 互換チェック
    - base_config_hash (適応値除外) による config 一致確認
    - dataset_span / instrument / stage_gate_version の一致確認
    - decision in (tighten, loosen) のみ適用 (in_band / skip_sample_size 除外)
    - record.applied_at の ISO 8601 形式検証
    - record.new_threshold の isfinite + range チェック

不一致時 / 不正値時は **fail-closed** (None を返す → config 値を使用)。
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Iterable, Mapping
from datetime import datetime
from pathlib import Path
from typing import Final

import structlog

from src.alpha_factory.config import AlphaFactoryConfig

__all__ = [
    "SCHEMA_VERSION",
    "compute_base_config_hash",
    "compute_full_config_hash",
    "load_calibrated_threshold",
]

logger = structlog.get_logger(__name__)

# state file format version. record.schema_version との比較に使う。
# 既存 record (schema_version 欄なし) は **後方互換読み取り対象外**
# (= 新 record のみ適用判定対象)。
# T058 (PR 3): dataset_epoch_id 追加に伴い v2 へ更新。 既存 v1 record は
# schema_version 不一致で自動排除される (再校正必要、 big-bang 前提)。
SCHEMA_VERSION: Final[int] = 2

# 既存 history record の互換読み取りで「decision filter のみ適用」とする
# decision 値集合 (tighten / loosen)。
_APPLY_DECISIONS: Final[frozenset[str]] = frozenset({"tighten", "loosen"})


def compute_base_config_hash(cfg: AlphaFactoryConfig) -> str:
    """適応値（calibrate-gate 変更対象）を **除外** した config hash。

    適応値除外は self-consistency 確保のため必須。

    除外対象 (calibrate-gate が変更しうる適応値):
        - cfg.stage_gate.stage_a_threshold

    Returns:
        sha256 hex digest。
    """
    payload: dict[str, object] = {
        "instrument": cfg.dataset.instrument,
        "start": str(cfg.dataset.start),
        "end": str(cfg.dataset.end),
        "stage_gate": {
            "stage_a_window_days": cfg.stage_gate.stage_a_window_days,
            "stage_a_alpha": cfg.stage_gate.stage_a_alpha,
            # stage_a_threshold は **意図的に除外** (適応値)
            "min_exposure_trade_count": cfg.stage_gate.min_exposure_trade_count,
            "stage_b_window_months": cfg.stage_gate.stage_b_window_months,
            "wf_train_days": cfg.stage_gate.wf_train_days,
            "wf_test_days": cfg.stage_gate.wf_test_days,
            "wf_step_days": cfg.stage_gate.wf_step_days,
            "wf_embargo_days": cfg.stage_gate.wf_embargo_days,
            "stage_b_median_oos_sharpe_min": (
                cfg.stage_gate.stage_b_median_oos_sharpe_min
            ),
            "stage_b_positive_fold_min": cfg.stage_gate.stage_b_positive_fold_min,
            "stage_b_dsr_min": cfg.stage_gate.stage_b_dsr_min,
            "wf_min_folds_required": cfg.stage_gate.wf_min_folds_required,
            "stage_b_fold_trade_count_min": (
                cfg.stage_gate.stage_b_fold_trade_count_min
            ),
            "stage_c_holdout_days": cfg.stage_gate.stage_c_holdout_days,
            "spread_stress_multiplier": cfg.stage_gate.spread_stress_multiplier,
            "trade_count_min_for_sharpe": cfg.stage_gate.trade_count_min_for_sharpe,
        },
    }
    blob = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def compute_full_config_hash(cfg: AlphaFactoryConfig) -> str:
    """完全 config hash（監査記録専用、適用判定には使わない）。

    base_config_hash と異なり、stage_a_threshold を含む全 stage_gate 値を含む。
    """
    payload: dict[str, object] = {
        "instrument": cfg.dataset.instrument,
        "start": str(cfg.dataset.start),
        "end": str(cfg.dataset.end),
        "stage_a_threshold": cfg.stage_gate.stage_a_threshold,
        "base_config_hash": compute_base_config_hash(cfg),
    }
    blob = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def _is_iso8601(value: str) -> bool:
    """ISO 8601 形式の datetime 文字列か判定 (datetime.fromisoformat 互換)。"""
    try:
        datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return False
    return True


def _iter_history_records(history_path: Path) -> Iterable[Mapping[str, object]]:
    """JSONL の各行を dict として yield (空行 / 不正 JSON は skip)。"""
    if not history_path.exists():
        return
    try:
        with history_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    logger.warning(
                        "calibrate_state.skip_invalid_json",
                        path=str(history_path),
                    )
                    continue
                if isinstance(rec, dict):
                    yield rec
    except OSError as exc:
        logger.warning(
            "calibrate_state.read_failure",
            path=str(history_path),
            error=str(exc),
        )


def _record_matches(
    record: Mapping[str, object],
    *,
    base_config_hash: str,
    dataset_epoch_id: str,
    dataset_span: tuple[str, str],
    instrument: str,
    stage_gate_version: str,
) -> bool:
    """record が現 RUN context にマッチするか判定 (cross-run contamination guard).

    T058 (PR 3): ``dataset_epoch_id`` を **追加条件** (AND 結合) として導入。
    既存 ``dataset_span`` ガードは T067 までは残す (synthesis § 12.1)。
    """
    rec_schema = record.get("schema_version")
    if not isinstance(rec_schema, int) or rec_schema != SCHEMA_VERSION:
        return False
    rec_base = record.get("base_config_hash")
    if not isinstance(rec_base, str) or rec_base != base_config_hash:
        return False
    # T058 (PR 3) → T067 移行手順: 下記 dataset_span ブロック (この 5 行) を
    # T067 切替コミットで削除すれば、 epoch_id 単独 scope への移行完了。
    # 具体的に削除するのは、 ``rec_span_obj`` 取得 + len/contents check + 比較の
    # 3 行 (= dataset_span ブロックの全体)。 直後の dataset_epoch_id ガードは
    # 残す (= moveable guard)。 詳細設計 行 1100-1102。
    rec_span_obj = record.get("dataset_span")
    if not isinstance(rec_span_obj, list) or len(rec_span_obj) != 2:
        return False
    rec_span = (str(rec_span_obj[0]), str(rec_span_obj[1]))
    if rec_span != dataset_span:
        return False
    # T058 (PR 3): dataset_epoch_id 追加条件 (AND)、 T067 で dataset_span 廃止後も
    # 残る moveable guard。 上の dataset_span ブロック削除に対して non-移動。
    rec_epoch_id = record.get("dataset_epoch_id")
    if not isinstance(rec_epoch_id, str) or rec_epoch_id != dataset_epoch_id:
        return False
    rec_inst = record.get("instrument")
    if not isinstance(rec_inst, str) or rec_inst != instrument:
        return False
    rec_sgv = record.get("stage_gate_version")
    if not isinstance(rec_sgv, str) or rec_sgv != stage_gate_version:
        return False
    rec_decision = record.get("decision")
    if not isinstance(rec_decision, str) or rec_decision not in _APPLY_DECISIONS:
        return False
    rec_applied_at = record.get("applied_at")
    return isinstance(rec_applied_at, str) and _is_iso8601(rec_applied_at)


def load_calibrated_threshold(
    *,
    history_path: Path,
    base_config_hash: str,
    dataset_epoch_id: str,
    dataset_span: tuple[str, str],
    instrument: str,
    stage_gate_version: str,
    threshold_floor: float = -100.0,
    threshold_ceiling: float = 100.0,
) -> float | None:
    """history.jsonl の最新適用可能 record から effective threshold を読み出す。

    cross-run contamination 防止のため、以下を全て verify (fail-closed):
        - record.schema_version == SCHEMA_VERSION
        - record.base_config_hash == 引数 base_config_hash (適応値除外の hash)
        - record.dataset_span == 引数 dataset_span (T067 で廃止予定)
        - record.dataset_epoch_id == 引数 dataset_epoch_id (T058 新設、 AND 結合)
        - record.instrument == 引数 instrument
        - record.stage_gate_version == 引数 stage_gate_version
        - record.decision in (tighten, loosen)
        - record.applied_at が ISO 8601 形式
        - record.new_threshold が isfinite かつ [floor, ceiling] 内

    Args:
        history_path: history.jsonl path
        base_config_hash: 適応値除外の現 RUN config hash
        dataset_span: (start, end) の string tuple (T067 で廃止予定)
        instrument: 通貨ペア
        stage_gate_version: Stage gate 識別子
        dataset_epoch_id: T058 新設の epoch-rolling 識別子 (RunContext から渡す)
        threshold_floor: 適用 threshold の下限 (default -100.0)
        threshold_ceiling: 適用 threshold の上限 (default 100.0)

    Returns:
        最新 verify record の new_threshold (float)、または None。
        None の場合は呼び出し側が config 値を使う。
    """
    candidates: list[tuple[str, float]] = []  # (applied_at, new_threshold)
    for record in _iter_history_records(history_path):
        if not _record_matches(
            record,
            base_config_hash=base_config_hash,
            dataset_epoch_id=dataset_epoch_id,
            dataset_span=dataset_span,
            instrument=instrument,
            stage_gate_version=stage_gate_version,
        ):
            continue
        rec_thr_obj = record.get("new_threshold")
        if not isinstance(rec_thr_obj, (int, float)):
            continue
        rec_thr = float(rec_thr_obj)
        if not math.isfinite(rec_thr):
            logger.warning(
                "calibrate_state.skip_non_finite_threshold",
                value=rec_thr_obj,
            )
            continue
        if not (threshold_floor <= rec_thr <= threshold_ceiling):
            logger.warning(
                "calibrate_state.skip_out_of_range",
                value=rec_thr,
                floor=threshold_floor,
                ceiling=threshold_ceiling,
            )
            continue
        rec_applied_at = record["applied_at"]
        assert isinstance(rec_applied_at, str)  # _record_matches で検証済み
        candidates.append((rec_applied_at, rec_thr))

    if not candidates:
        return None
    # applied_at で降順ソート → 最新を採用
    candidates.sort(key=lambda x: x[0], reverse=True)
    return candidates[0][1]
