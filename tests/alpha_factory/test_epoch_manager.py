"""T059: ``epoch_manager`` の振る舞いテスト.

詳細設計: ``devnotes/20260429-2113-todo-T059-epoch-window-manager/detailed-design.md``
施策 2 (行 621-695)。
"""

from __future__ import annotations

import json
import multiprocessing as mp
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from src.alpha_factory.epoch_manager import (
    DuplicateRunIdError,
    EpochCapExceeded,
    EpochDatasetMismatch,
    EpochLockTimeout,
    EpochManager,
    EpochStateCorruptError,
    EpochStateIncompatible,
    EpochWindow,
    make_epoch_id,
)
from src.alpha_factory.schema_contract import DATASET_EPOCH_ID_PATTERN

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


@dataclass
class _DatasetCfg:
    """``DatasetConfigLike`` を満たす lightweight stub."""

    instrument: str
    start: datetime
    end: datetime


def _anchor() -> datetime:
    """Canonical anchor_origin (UTC midnight)."""
    return datetime(2026, 4, 1, tzinfo=UTC)


def _make_manager(
    tmp_path: Path,
    *,
    instrument: str = "EUR_JPY",
    anchor_origin: datetime | None = None,
    latest_data_end_floor: datetime | None = None,
) -> EpochManager:
    """Test 用の ``EpochManager`` インスタンス生成.

    state file は ``tmp_path / .cache / alpha_factory / epoch_state.json``。
    """
    repo_root = tmp_path
    return EpochManager(
        repo_root=repo_root,
        anchor_origin=anchor_origin or _anchor(),
        instrument=instrument,
        # Default: 6 epoch advance (= +28d * 6 = 168d) を許容する horizon。
        latest_data_end_floor=latest_data_end_floor
        or (anchor_origin or _anchor()) + timedelta(days=365 * 5),
    )


def _matching_dataset_cfg(
    manager: EpochManager,
    *,
    epoch_index: int = 0,
) -> _DatasetCfg:
    window = manager._compute_window(epoch_index)
    return _DatasetCfg(
        instrument=manager.instrument,
        start=window.start,
        end=window.end,
    )


# ---------------------------------------------------------------------------
# Window identity / make_epoch_id
# ---------------------------------------------------------------------------


def test_make_epoch_id_returns_canonical_format_for_canonical_window() -> None:
    window = EpochWindow(
        start=datetime(2024, 4, 1, tzinfo=UTC),
        end=datetime(2026, 4, 1, tzinfo=UTC),
    )
    assert make_epoch_id(window) == "epoch_20240401_20260401"


def test_make_epoch_id_is_deterministic_for_same_start_end() -> None:
    a = EpochWindow(
        start=datetime(2024, 4, 1, tzinfo=UTC),
        end=datetime(2026, 4, 1, tzinfo=UTC),
    )
    b = EpochWindow(
        start=datetime(2024, 4, 1, tzinfo=UTC),
        end=datetime(2026, 4, 1, tzinfo=UTC),
    )
    assert make_epoch_id(a) == make_epoch_id(b)


def test_make_epoch_id_differs_when_start_or_end_differs() -> None:
    base = EpochWindow(
        start=datetime(2024, 4, 1, tzinfo=UTC),
        end=datetime(2026, 4, 1, tzinfo=UTC),
    )
    different_end = EpochWindow(
        start=datetime(2024, 4, 1, tzinfo=UTC),
        end=datetime(2026, 4, 29, tzinfo=UTC),
    )
    different_start = EpochWindow(
        start=datetime(2024, 4, 29, tzinfo=UTC),
        end=datetime(2026, 4, 1, tzinfo=UTC),
    )
    assert make_epoch_id(base) != make_epoch_id(different_end)
    assert make_epoch_id(base) != make_epoch_id(different_start)


def test_epoch_window_rejects_end_le_start() -> None:
    with pytest.raises(ValueError, match=r"EpochWindow\.end"):
        EpochWindow(
            start=datetime(2026, 4, 1, tzinfo=UTC),
            end=datetime(2026, 4, 1, tzinfo=UTC),
        )
    with pytest.raises(ValueError, match=r"EpochWindow\.end"):
        EpochWindow(
            start=datetime(2026, 4, 2, tzinfo=UTC),
            end=datetime(2026, 4, 1, tzinfo=UTC),
        )


def test_compute_window_at_index_zero_returns_anchor_window(tmp_path: Path) -> None:
    manager = _make_manager(tmp_path)
    window = manager._compute_window(0)
    assert window.end == _anchor()
    assert window.start == _anchor() - timedelta(weeks=104)


def test_compute_window_at_index_one_advances_by_28_days(tmp_path: Path) -> None:
    manager = _make_manager(tmp_path)
    window_0 = manager._compute_window(0)
    window_1 = manager._compute_window(1)
    assert window_1.end - window_0.end == timedelta(days=28)
    assert window_1.start - window_0.start == timedelta(days=28)


# ---------------------------------------------------------------------------
# dataset_epoch_id 生成 (T058 grammar 整合)
# ---------------------------------------------------------------------------


def test_dataset_epoch_id_matches_pattern_lowercase_alphanumeric_underscore(
    tmp_path: Path,
) -> None:
    manager = _make_manager(tmp_path)
    epoch_id = make_epoch_id(manager.current_window())
    assert DATASET_EPOCH_ID_PATTERN.fullmatch(epoch_id) is not None


# ---------------------------------------------------------------------------
# Atomic reservation
# ---------------------------------------------------------------------------


def test_reserve_run_slot_creates_state_file_when_absent(tmp_path: Path) -> None:
    manager = _make_manager(tmp_path)
    cfg = _matching_dataset_cfg(manager)
    assert not manager._state_path.exists()
    manager.reserve_run_slot("run_a", dataset_cfg=cfg)
    assert manager._state_path.exists()


def test_reserve_run_slot_increments_slots_consumed_in_epoch(tmp_path: Path) -> None:
    manager = _make_manager(tmp_path)
    cfg = _matching_dataset_cfg(manager)
    manager.reserve_run_slot("run_a", dataset_cfg=cfg)
    manager.reserve_run_slot("run_b", dataset_cfg=cfg)
    state = json.loads(manager._state_path.read_text(encoding="utf-8"))
    assert state["slots_consumed_in_epoch"] == 2


def test_reserve_run_slot_persists_run_record_with_started_status(
    tmp_path: Path,
) -> None:
    manager = _make_manager(tmp_path)
    cfg = _matching_dataset_cfg(manager)
    manager.reserve_run_slot("run_a", dataset_cfg=cfg)
    state = json.loads(manager._state_path.read_text(encoding="utf-8"))
    record = state["run_records"]["0"]["run_a"]
    assert record["status"] == "started"
    assert "reserved_at" in record


def test_reserve_run_slot_returns_current_window(tmp_path: Path) -> None:
    manager = _make_manager(tmp_path)
    cfg = _matching_dataset_cfg(manager)
    window = manager.reserve_run_slot("run_a", dataset_cfg=cfg)
    assert window == manager._compute_window(0)


# ---------------------------------------------------------------------------
# epoch advance + data horizon
# ---------------------------------------------------------------------------


def test_reserve_advances_to_next_epoch_when_max_runs_reached(
    tmp_path: Path,
) -> None:
    manager = _make_manager(tmp_path)
    cfg_e0 = _matching_dataset_cfg(manager, epoch_index=0)
    for i in range(EpochManager.MAX_RUNS_PER_EPOCH):
        manager.reserve_run_slot(f"run_e0_{i}", dataset_cfg=cfg_e0)
    # 7 個目: advance を起こす + 新 window との dataset_cfg 一致が必須
    # (impl-review-pr1 Round 1 [Blocker] H4 反映: advance 後 re-verify)。
    cfg_e1 = _matching_dataset_cfg(manager, epoch_index=1)
    manager.reserve_run_slot("run_e1_0", dataset_cfg=cfg_e1)
    state = json.loads(manager._state_path.read_text(encoding="utf-8"))
    assert state["current_epoch_index"] == 1
    assert state["slots_consumed_in_epoch"] == 1
    assert "run_e1_0" in state["run_records"]["1"]


def test_reserve_raises_epoch_dataset_mismatch_after_advance_when_cfg_matches_old_window(
    tmp_path: Path,
) -> None:
    """Codex impl-review-pr1 Round 1 [Blocker] H4 反映:
    advance 後に新 window と dataset_cfg を再検証する。 旧 window と一致する
    cfg のままでは advance 直後の予約は ``EpochDatasetMismatch``."""
    manager = _make_manager(tmp_path)
    cfg_e0 = _matching_dataset_cfg(manager, epoch_index=0)
    for i in range(EpochManager.MAX_RUNS_PER_EPOCH):
        manager.reserve_run_slot(f"run_{i}", dataset_cfg=cfg_e0)
    # 7 回目: cfg_e0 (= 旧 window 一致) は新 window と不一致 → mismatch raise
    with pytest.raises(EpochDatasetMismatch):
        manager.reserve_run_slot("run_overflow", dataset_cfg=cfg_e0)


def test_reserve_raises_epoch_cap_exceeded_when_next_end_beyond_data_horizon(
    tmp_path: Path,
) -> None:
    anchor = _anchor()
    # data horizon を anchor 直後に設定 → 次 epoch (anchor + 28d) で cap.
    manager = _make_manager(
        tmp_path,
        anchor_origin=anchor,
        latest_data_end_floor=anchor + timedelta(days=14),
    )
    cfg_e0 = _matching_dataset_cfg(manager, epoch_index=0)
    for i in range(EpochManager.MAX_RUNS_PER_EPOCH):
        manager.reserve_run_slot(f"run_{i}", dataset_cfg=cfg_e0)
    # cap 判定は dataset_match よりも前に行われるため、 cfg はどちらでも raise する
    with pytest.raises(EpochCapExceeded):
        manager.reserve_run_slot("run_overflow", dataset_cfg=cfg_e0)


# ---------------------------------------------------------------------------
# dataset mismatch hard guard
# ---------------------------------------------------------------------------


def test_reserve_raises_epoch_dataset_mismatch_when_cfg_dataset_differs_from_window(
    tmp_path: Path,
) -> None:
    manager = _make_manager(tmp_path)
    bad_cfg = _DatasetCfg(
        instrument="EUR_JPY",
        start=datetime(2025, 1, 1, tzinfo=UTC),  # window.start とは違う
        end=datetime(2026, 1, 1, tzinfo=UTC),
    )
    with pytest.raises(EpochDatasetMismatch):
        manager.reserve_run_slot("run_a", dataset_cfg=bad_cfg)


# ---------------------------------------------------------------------------
# compatibility fingerprint
# ---------------------------------------------------------------------------


def test_reserve_raises_epoch_state_incompatible_when_instrument_changes(
    tmp_path: Path,
) -> None:
    manager = _make_manager(tmp_path, instrument="EUR_JPY")
    cfg = _matching_dataset_cfg(manager)
    manager.reserve_run_slot("run_a", dataset_cfg=cfg)
    # instrument を切替えた新 manager で同 state を読み込む → 不一致
    other = _make_manager(tmp_path, instrument="USD_JPY")
    cfg_other = _matching_dataset_cfg(other)
    with pytest.raises(EpochStateIncompatible):
        other.reserve_run_slot("run_b", dataset_cfg=cfg_other)


def test_reserve_raises_epoch_state_incompatible_when_anchor_origin_changes(
    tmp_path: Path,
) -> None:
    manager = _make_manager(tmp_path, anchor_origin=_anchor())
    cfg = _matching_dataset_cfg(manager)
    manager.reserve_run_slot("run_a", dataset_cfg=cfg)
    # anchor を変更した新 manager → fingerprint mismatch
    new_anchor = _anchor() + timedelta(days=28)
    other = _make_manager(tmp_path, anchor_origin=new_anchor)
    cfg_other = _matching_dataset_cfg(other)
    with pytest.raises(EpochStateIncompatible):
        other.reserve_run_slot("run_b", dataset_cfg=cfg_other)


def test_state_anchor_origin_z_vs_plus_zero_zero_does_not_cause_false_mismatch(
    tmp_path: Path,
) -> None:
    manager = _make_manager(tmp_path)
    cfg = _matching_dataset_cfg(manager)
    manager.reserve_run_slot("run_a", dataset_cfg=cfg)
    # state file の anchor_origin を `Z` 形式に書き換える
    state = json.loads(manager._state_path.read_text(encoding="utf-8"))
    iso = state["compatibility_fingerprint"]["anchor_origin"]
    z_form = iso.replace("+00:00", "Z")
    state["compatibility_fingerprint"]["anchor_origin"] = z_form
    manager._state_path.write_text(json.dumps(state), encoding="utf-8")
    # 同 manager で reserve → false mismatch にならない
    manager.reserve_run_slot("run_b", dataset_cfg=cfg)


def test_init_state_raises_epoch_state_incompatible_when_dataset_cfg_instrument_differs(
    tmp_path: Path,
) -> None:
    manager = _make_manager(tmp_path, instrument="EUR_JPY")
    bad_cfg = _DatasetCfg(
        instrument="USD_JPY",
        start=manager._compute_window(0).start,
        end=manager._compute_window(0).end,
    )
    with pytest.raises(EpochStateIncompatible):
        manager.reserve_run_slot("run_a", dataset_cfg=bad_cfg)


# ---------------------------------------------------------------------------
# state corruption
# ---------------------------------------------------------------------------


def test_reserve_raises_epoch_state_corrupt_error_on_invalid_json(
    tmp_path: Path,
) -> None:
    manager = _make_manager(tmp_path)
    manager._state_path.parent.mkdir(parents=True, exist_ok=True)
    manager._state_path.write_text("{not valid json", encoding="utf-8")
    cfg = _matching_dataset_cfg(manager)
    with pytest.raises(EpochStateCorruptError):
        manager.reserve_run_slot("run_a", dataset_cfg=cfg)


def test_load_state_no_init_returns_none_when_file_absent(tmp_path: Path) -> None:
    manager = _make_manager(tmp_path)
    assert manager._load_state_no_init() is None


# ---------------------------------------------------------------------------
# Duplicate run_id (Round 1 [Critical] 1: 全 epoch で一意)
# ---------------------------------------------------------------------------


def test_reserve_raises_duplicate_run_id_error_when_same_id_in_same_epoch(
    tmp_path: Path,
) -> None:
    manager = _make_manager(tmp_path)
    cfg = _matching_dataset_cfg(manager)
    manager.reserve_run_slot("run_dup", dataset_cfg=cfg)
    with pytest.raises(DuplicateRunIdError):
        manager.reserve_run_slot("run_dup", dataset_cfg=cfg)


def test_reserve_raises_duplicate_run_id_error_when_same_id_in_other_epoch(
    tmp_path: Path,
) -> None:
    manager = _make_manager(tmp_path)
    cfg_e0 = _matching_dataset_cfg(manager, epoch_index=0)
    # epoch 0 を埋め切って、 advance 後に同 run_id を再利用しようとする。
    for i in range(EpochManager.MAX_RUNS_PER_EPOCH):
        manager.reserve_run_slot(f"run_{i}", dataset_cfg=cfg_e0)
    # advance 後の duplicate check に到達するため cfg_e1 (= 新 window 一致) で呼ぶ
    cfg_e1 = _matching_dataset_cfg(manager, epoch_index=1)
    with pytest.raises(DuplicateRunIdError):
        manager.reserve_run_slot("run_0", dataset_cfg=cfg_e1)


def test_run_id_uniqueness_enforced_globally_across_epochs(tmp_path: Path) -> None:
    manager = _make_manager(tmp_path)
    cfg_e0 = _matching_dataset_cfg(manager, epoch_index=0)
    for i in range(EpochManager.MAX_RUNS_PER_EPOCH):
        manager.reserve_run_slot(f"run_e0_{i}", dataset_cfg=cfg_e0)
    # 7 回目: advance + 新 window との dataset 一致が必須
    cfg_e1 = _matching_dataset_cfg(manager, epoch_index=1)
    manager.reserve_run_slot("run_e1_0", dataset_cfg=cfg_e1)
    # 8 回目: 既に epoch_1 に居るので cfg_e1 を使う
    # 全 epoch で一意なので、 異 epoch から同 id 再利用は不可
    with pytest.raises(DuplicateRunIdError):
        manager.reserve_run_slot("run_e0_0", dataset_cfg=cfg_e1)


# ---------------------------------------------------------------------------
# Lock timeout
# ---------------------------------------------------------------------------


def _hold_lock_worker(state_path_str: str, hold_s: float, ready_path: str) -> None:
    """別 process で lock を保持し続けるワーカ.

    lock 取得後 ``ready_path`` を touch して親に通知、 ``hold_s`` 秒保持して exit。
    """
    import fcntl

    lock_path = Path(state_path_str).with_suffix(".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    f = open(lock_path, "w")  # noqa: SIM115 — lock を hold するため context manager 不可
    try:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        Path(ready_path).touch()
        time.sleep(hold_s)
        fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    finally:
        f.close()


def test_reserve_raises_epoch_lock_timeout_when_lock_held_by_another_process(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """別 process が lock を保持している間、 短縮 timeout で ``EpochLockTimeout``."""
    manager = _make_manager(tmp_path)
    # timeout を短縮 (CI 安定化、 Round 1 [Suggestion] 2 反映)
    monkeypatch.setattr(EpochManager, "LOCK_TIMEOUT_SECONDS", 1)
    monkeypatch.setattr(EpochManager, "LOCK_RETRY_INTERVAL_S", 0.05)
    ready = tmp_path / "lock_ready.flag"
    ctx = mp.get_context("spawn")
    proc = ctx.Process(
        target=_hold_lock_worker,
        args=(str(manager._state_path), 5.0, str(ready)),
    )
    proc.start()
    try:
        # lock 取得完了を待つ
        deadline = time.monotonic() + 10
        while not ready.exists():
            if time.monotonic() >= deadline:
                pytest.skip("lock holder did not start in time")
            time.sleep(0.05)
        cfg = _matching_dataset_cfg(manager)
        with pytest.raises(EpochLockTimeout):
            manager.reserve_run_slot("run_a", dataset_cfg=cfg)
    finally:
        proc.join(timeout=15)
        if proc.is_alive():
            proc.terminate()
            proc.join(timeout=5)


def test_lock_released_after_reservation_completes(tmp_path: Path) -> None:
    manager = _make_manager(tmp_path)
    cfg = _matching_dataset_cfg(manager)
    manager.reserve_run_slot("run_a", dataset_cfg=cfg)
    # 直後に再取得できる (lock が解放されている証拠)
    manager.reserve_run_slot("run_b", dataset_cfg=cfg)


# ---------------------------------------------------------------------------
# Status update
# ---------------------------------------------------------------------------


def test_mark_run_status_updates_record_to_completed(tmp_path: Path) -> None:
    manager = _make_manager(tmp_path)
    cfg = _matching_dataset_cfg(manager)
    manager.reserve_run_slot("run_a", dataset_cfg=cfg)
    manager.mark_run_status("run_a", "completed")
    state = json.loads(manager._state_path.read_text(encoding="utf-8"))
    record = state["run_records"]["0"]["run_a"]
    assert record["status"] == "completed"
    assert "completed_at" in record


def test_mark_run_status_updates_record_in_previous_epoch(tmp_path: Path) -> None:
    manager = _make_manager(tmp_path)
    cfg_e0 = _matching_dataset_cfg(manager, epoch_index=0)
    for i in range(EpochManager.MAX_RUNS_PER_EPOCH):
        manager.reserve_run_slot(f"run_e0_{i}", dataset_cfg=cfg_e0)
    cfg_e1 = _matching_dataset_cfg(manager, epoch_index=1)
    manager.reserve_run_slot("run_e1_0", dataset_cfg=cfg_e1)
    # 旧 epoch の record を後から terminal に
    manager.mark_run_status("run_e0_0", "completed")
    state = json.loads(manager._state_path.read_text(encoding="utf-8"))
    assert state["run_records"]["0"]["run_e0_0"]["status"] == "completed"


def test_mark_run_status_no_op_when_run_id_not_found(tmp_path: Path) -> None:
    manager = _make_manager(tmp_path)
    cfg = _matching_dataset_cfg(manager)
    manager.reserve_run_slot("run_a", dataset_cfg=cfg)
    # raise しない、 warn のみ
    manager.mark_run_status("run_unknown", "completed")
    state = json.loads(manager._state_path.read_text(encoding="utf-8"))
    assert state["run_records"]["0"]["run_a"]["status"] == "started"


def test_mark_run_status_rejects_invalid_status(tmp_path: Path) -> None:
    manager = _make_manager(tmp_path)
    with pytest.raises(ValueError, match=r"invalid status"):
        manager.mark_run_status("run_a", "running")


# ---------------------------------------------------------------------------
# Reset
# ---------------------------------------------------------------------------


def _audit_log_path(manager: EpochManager) -> Path:
    return manager.repo_root / "reports/audit/epoch_manager_audit_log.jsonl"


def test_reset_writes_audit_log_with_previous_state_snapshot(tmp_path: Path) -> None:
    manager = _make_manager(tmp_path)
    cfg = _matching_dataset_cfg(manager)
    manager.reserve_run_slot("run_a", dataset_cfg=cfg)
    manager.reset(reason="test reset")
    audit_path = _audit_log_path(manager)
    lines = audit_path.read_text(encoding="utf-8").strip().splitlines()
    assert lines
    last = json.loads(lines[-1])
    assert last["event"] == "reset_epoch_state"
    assert last["reason"] == "test reset"
    snap = last["previous_state_snapshot"]
    assert isinstance(snap, dict)
    assert "run_a" in snap["run_records"]["0"]


def test_reset_deletes_state_file(tmp_path: Path) -> None:
    manager = _make_manager(tmp_path)
    cfg = _matching_dataset_cfg(manager)
    manager.reserve_run_slot("run_a", dataset_cfg=cfg)
    assert manager._state_path.exists()
    manager.reset(reason="test")
    assert not manager._state_path.exists()


def test_reset_rejects_empty_reason(tmp_path: Path) -> None:
    manager = _make_manager(tmp_path)
    with pytest.raises(ValueError, match=r"reset reason"):
        manager.reset(reason="")
    with pytest.raises(ValueError, match=r"reset reason"):
        manager.reset(reason="   ")


def test_state_initialized_fresh_after_reset(tmp_path: Path) -> None:
    manager = _make_manager(tmp_path)
    cfg = _matching_dataset_cfg(manager)
    for i in range(3):
        manager.reserve_run_slot(f"run_a_{i}", dataset_cfg=cfg)
    manager.reset(reason="reset for fresh")
    # reset 後の reserve_run_slot は slots_consumed_in_epoch=1 から
    manager.reserve_run_slot("run_b_0", dataset_cfg=cfg)
    state = json.loads(manager._state_path.read_text(encoding="utf-8"))
    assert state["slots_consumed_in_epoch"] == 1
    assert state["current_epoch_index"] == 0
    assert "run_a_0" not in state["run_records"]["0"]


def test_reset_recovers_even_when_state_json_is_corrupt(tmp_path: Path) -> None:
    manager = _make_manager(tmp_path)
    manager._state_path.parent.mkdir(parents=True, exist_ok=True)
    manager._state_path.write_text("{corrupt", encoding="utf-8")
    # 破損 state でも reset は完遂できる
    manager.reset(reason="recover corrupt state")
    assert not manager._state_path.exists()


def test_reset_records_corrupt_flag_in_audit_log_when_state_was_corrupt(
    tmp_path: Path,
) -> None:
    manager = _make_manager(tmp_path)
    manager._state_path.parent.mkdir(parents=True, exist_ok=True)
    manager._state_path.write_text("{corrupt", encoding="utf-8")
    manager.reset(reason="recover corrupt state")
    lines = _audit_log_path(manager).read_text(encoding="utf-8").splitlines()
    last = json.loads(lines[-1])
    snap = last["previous_state_snapshot"]
    assert snap.get("corrupt") is True
    assert "error" in snap


def _reset_acquires_lock_worker(
    state_path_str: str, ready_path: str, hold_s: float
) -> None:
    """親 reset 中の lock 衝突確認用 worker."""
    import fcntl

    lock_path = Path(state_path_str).with_suffix(".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    f = open(lock_path, "w")  # noqa: SIM115 — lock を hold するため context manager 不可
    try:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        Path(ready_path).touch()
        time.sleep(hold_s)
        fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    finally:
        f.close()


def test_reset_acquires_file_lock_to_prevent_concurrent_reservation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """別 process が lock 保持中、 reset は lock 取得を試み timeout する."""
    manager = _make_manager(tmp_path)
    monkeypatch.setattr(EpochManager, "LOCK_TIMEOUT_SECONDS", 1)
    monkeypatch.setattr(EpochManager, "LOCK_RETRY_INTERVAL_S", 0.05)
    ready = tmp_path / "lock_ready.flag"
    ctx = mp.get_context("spawn")
    proc = ctx.Process(
        target=_reset_acquires_lock_worker,
        args=(str(manager._state_path), str(ready), 5.0),
    )
    proc.start()
    try:
        deadline = time.monotonic() + 10
        while not ready.exists():
            if time.monotonic() >= deadline:
                pytest.skip("lock holder did not start in time")
            time.sleep(0.05)
        with pytest.raises(EpochLockTimeout):
            manager.reset(reason="should fail to acquire lock")
    finally:
        proc.join(timeout=15)
        if proc.is_alive():
            proc.terminate()
            proc.join(timeout=5)


# ---------------------------------------------------------------------------
# Atomic save
# ---------------------------------------------------------------------------


def test_save_state_atomic_creates_no_partial_file_on_simulated_crash(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """tmp の rename 前に例外 → state file は不在のまま (partial file 残らない)."""
    manager = _make_manager(tmp_path)
    cfg = _matching_dataset_cfg(manager)

    real_rename = Path.rename

    def fail_rename(self: Path, target: Path) -> Path:  # type: ignore[no-untyped-def]
        raise OSError("simulated crash before rename")

    monkeypatch.setattr(Path, "rename", fail_rename)
    with pytest.raises(OSError, match=r"simulated crash"):
        manager.reserve_run_slot("run_a", dataset_cfg=cfg)
    monkeypatch.setattr(Path, "rename", real_rename)
    # state file は残っていない、 tmp file も残っていない
    assert not manager._state_path.exists()
    leftover = list(manager._state_path.parent.glob(".tmp.*.json"))
    assert leftover == []


def test_save_state_uses_unique_tmp_file_per_call(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """連続 _save_state_atomic 呼出で tmp 名が衝突しない (uuid 使用確認)."""
    manager = _make_manager(tmp_path)
    cfg = _matching_dataset_cfg(manager)
    manager.reserve_run_slot("run_a", dataset_cfg=cfg)

    seen: list[Path] = []
    real_with_suffix = Path.with_suffix

    def spy_with_suffix(self: Path, suffix: str) -> Path:  # type: ignore[no-untyped-def]
        result = real_with_suffix(self, suffix)
        if suffix.startswith(".tmp."):
            seen.append(result)
        return result

    monkeypatch.setattr(Path, "with_suffix", spy_with_suffix)
    manager.reserve_run_slot("run_b", dataset_cfg=cfg)
    manager.reserve_run_slot("run_c", dataset_cfg=cfg)
    # 2 回 reserve したので 2 個以上の異 tmp path が観測される
    assert len(seen) >= 2
    assert len(set(seen)) == len(seen)
