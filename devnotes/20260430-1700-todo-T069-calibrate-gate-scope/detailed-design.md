# 詳細設計: T069 — Calibrate-gate scope (epoch key + 3 Run freeze + Δ ≤ 0.03)

**作成日時**: 2026-04-30 17:30 JST (Round 2 改訂: 17:50 JST)
**設計者**: Claude
**前提**: 概念設計 `conceptual-design.md` Round 3 APPROVED 済 (`conceptual-review-round-3.md`)
**SSOT 規約 (§ 11.2)**: 本詳細設計 §3 (データモデル) / §4 (アルゴリズム) の擬似コードは概念設計 §5 (API シグネチャ) と同期。 不一致時は概念設計を正本として優先。
**main 基準**: `c4119b6` (改訂後 commit)
**改訂履歴**: Round 1 [C1-C5] / [W1-W3] / [S1-S3] 全反映 (`detailed-review-round-1.md` 参照)

## 0. 詳細設計の責務

概念設計で確定した API / アルゴリズム / 不変条件を **コード単位** に展開し、 Phase 1 PR で書ける状態まで詳細化:
- API シグネチャの完全展開 (引数 / 戻り値 / 例外 / docstring)
- 擬似コード (= Python に近いがフォーマットは設計書)
- edge case 完全列挙 (concept-level の F1-F15 を行 / 関数単位に対応付け)
- caller 影響 (現存 caller の signature 完全形 / 必要 patch のリストアップ)
- テスト名 + 期待挙動 + assertion
- LOC / DoD / Phase 1 / Phase 2 切り分け

## 1. ファイル / 関数 / クラス 完全リスト

### 1.1 新規ファイル

| Path | 主シンボル | LOC 概算 |
|---|---|---|
| `src/alpha_factory/calibrate_freeze.py` | `FreezeStatus`, `evaluate_freeze_status`, `decide_with_freeze`, `_FROZEN_DECISION_LABEL` | +130 |
| `tests/alpha_factory/test_calibrate_freeze.py` | F1-F13 + F15 + happy path | +220 |

### 1.2 既存ファイル変更

| Path | 関数 / 行 | 変更内容 | LOC 増減 |
|---|---|---|---|
| `src/alpha_factory/calibrate_gate.py:69-77` | `DecisionLabel` | `"skip_frozen"` 追加 | +1 |
| `src/alpha_factory/calibrate_gate.py:173-207` | `CalibrateConfig.__post_init__` | `threshold_delta_abs_max <= 0.03` contract 追加 | +5 |
| `src/alpha_factory/calibrate_gate_history.py:137-147` | `DriftAnalysis` dataclass | `n_skip_frozen: int` field 追加 | +1 |
| `src/alpha_factory/calibrate_gate_history.py:150-194` | `compute_drift` | `n_skip_frozen` 集計 + `DriftAnalysis` 構築に渡す | +3 |
| `tests/alpha_factory/test_calibrate_gate.py` | `CalibrateConfig` test | contract 強化 test 追加 | +25 |
| `tests/alpha_factory/test_calibrate_gate_history.py` | `compute_drift` test | n_skip_frozen test 追加 | +15 |
| `config/alpha_factory/default.yaml` | `stage_gate.stage_a.calibrate.threshold_delta_abs_max` | 0.03 SSOT 化 (現値が異なる場合のみ書き換え) | ±1 |
| `docs/alpha_factory/stage-gates.md` | T069 セクション | 仕様追記 | +30 |

### 1.3 Phase 2 申し送り (T069 PR では touch しない)

- `scripts/alpha_factory/calibrate_gate.py` (CLI 配線)
- `scripts/alpha_factory/calibrate_gate_drift.py` (n_skip_frozen 表示)
- `scripts/alpha_factory/run_ga.py` (任意 log)
- T058 detailed-design 改訂依頼: `HistoryRecord.applied_from_run_id: str` を v2 必須化

## 2. 既存 caller signature 完全展開 + Consumer Inventory (Round 1 [C5] / [S1] 反映)

T069 PR は library 層のみ追加、 既存 signature の **破壊変更なし**。 ただし以下の caller への影響を完全列挙:

### 2.1 Caller signature 列挙

| Caller | 既存 signature | T069 PR 影響 | Phase 2 影響 |
|---|---|---|---|
| `scripts/alpha_factory/calibrate_gate.py:311` | `decide(sample, config)` | 影響なし (decide() 不変) | `decide_with_freeze(sample, config, freeze_status=fs)` に置換 |
| `tests/scripts/test_calibrate_gate.py` 系 | `decide()` 直接 test | 影響なし | (任意) freeze test 追加 |
| `scripts/alpha_factory/run_ga.py:1078` | `load_calibrated_threshold(history_path=, base_config_hash=, dataset_span=, instrument=, stage_gate_version=, threshold_floor=-100.0, threshold_ceiling=100.0)` | T058 で `dataset_epoch_id` 必須引数追加済 / 影響なし | 影響なし (既存挙動継承) |
| `src/alpha_factory/calibrate_gate_history.py::compute_drift` 既存 caller | `compute_drift(records, *, monotone_threshold=4, clamp_threshold=3, band_multiplier=2.0)` | 影響なし (signature 不変、 戻り値の DriftAnalysis に field 追加のみ) | `n_skip_frozen` を表示する場合のみ touch |

`compute_drift` の戻り値 `DriftAnalysis` への field 追加 backward-compat (Round 1 [W3] 反映、 INCONCLUSIVE 修正版):
- `frozen=True` の dataclass で field 追加すると、 既存の **位置引数 / 全 field 指定の構築コード**は壊れる可能性 (positional 構築なら新 field 位置で型不一致)
- 内部 `compute_drift` 改変では keyword-only で field 列挙するので問題なし
- 既存 test fixture / production code に **直接 `DriftAnalysis(...)` を構築する箇所がある場合**は同 PR で更新必須
- T069 PR 実装時に `grep -rn "DriftAnalysis(" src/ tests/ scripts/` で全 construction 箇所を確認、 必要なら同 PR で更新

### 2.2 skip_frozen consumer inventory (4 段接続表、 Round 1 [C5] / [S1] 反映)

`DecisionLabel = "skip_frozen"` が config → model → writer → reader → report の 5 段で正しく流れることを確認:

| 段階 | ファイル | 関数 / line | T069 PR で何をするか |
|---|---|---|---|
| **1. Label 定義 (config 相当)** | `src/alpha_factory/calibrate_gate.py:69-77` | `DecisionLabel` Literal | `"skip_frozen"` 追加 (T069 必須) |
| **2. Model 構築** | `src/alpha_factory/calibrate_freeze.py` (新規) | `decide_with_freeze` | `Decision(decision="skip_frozen", ...)` を構築 (T069 必須) |
| **3. Writer (record append)** | `scripts/alpha_factory/calibrate_gate.py:422-450` | `HistoryRecord(decision=decision.decision, ...)` | T069 PR は touch しない、 Phase 2 で配線 (= 既存の `decision` 文字列をそのまま append、 専用 branch 不要) |
| **4. Reader (history load 経路)** | `src/alpha_factory/calibrate_state.py:178` | `_record_matches` で `decision in {"tighten", "loosen"}` filter | T069 PR は touch しない (= skip_frozen は filter で自然除外、 既存挙動で SSOT 統一) |
| **5. Reader (drift 監視経路)** | `src/alpha_factory/calibrate_gate_history.py:166-168` | `compute_drift` で 3 decision count | T069 PR で `n_skip_frozen` 集計を追加 (T069 必須) |
| **6. Report 表示** | (検証時点では calibrate-gate decision を読む report 経路の grep 結果ヒットなし、 = 現状未配線) | — | T069 PR は touch しない。 Phase 2 で run report (例えば `scripts/alpha_factory/run_report.py` 系) が calibrate decision を表示する場合、 `compute_drift.n_skip_frozen` を直接読み出して Markdown 表に追加する。 検証コマンド: `grep -rn "decision" scripts/alpha_factory/ src/alpha_factory/ --include='*.py' | grep -i 'report\|summary\|run_report'` |

転記漏れチェック (zenigame で頻出した 4 段接続パターン):
- `Decision.decision` field は既存、 新規 field 追加なし → 段 1-2 完結
- `HistoryRecord.decision` field は既存、 文字列値が拡張されるだけ → 段 3 は「既存経路で吸収」
- `compute_drift` の `n_skip_frozen` は **T069 PR で同時更新必須** (= 段 5 の漏れがあると drift 監視が skip_frozen を可視化できない)
- Phase 2 で scripts/run_ga / scripts/calibrate_gate / drift CLI / report の 4 経路を **同期**して更新する旨を §12 で明示

## 3. データモデル詳細

### 3.1 FreezeStatus (新設)

```python
# src/alpha_factory/calibrate_freeze.py

from __future__ import annotations
from dataclasses import dataclass

__all__ = [
    "FreezeStatus",
    "evaluate_freeze_status",
    "decide_with_freeze",
]


@dataclass(frozen=True)
class FreezeStatus:
    """epoch 内 calibrate-gate freeze 判定結果 (immutable, pure data).

    SSOT: 概念設計 §4.1.

    属性:
        is_frozen: epoch 内 distinct run count が freeze_window 未満なら True.
        epoch_distinct_run_count: 現 dataset_epoch_id にマッチした
            distinct applied_from_run_id 数 (None record は除外).
        freeze_window: 凍結窓サイズ (synthesis § 8.6 で 3 確定).
        next_run_index_in_epoch: 現 Run が epoch 内で何 Run 目になるか
            (1-indexed, = epoch_distinct_run_count + 1).

    不変条件 (__post_init__ で assert):
        is_frozen ⇔ (epoch_distinct_run_count < freeze_window)
        next_run_index_in_epoch == epoch_distinct_run_count + 1
        freeze_window >= 1
        epoch_distinct_run_count >= 0
    """

    is_frozen: bool
    epoch_distinct_run_count: int
    freeze_window: int
    next_run_index_in_epoch: int

    def __post_init__(self) -> None:
        if self.freeze_window < 1:
            raise ValueError(
                f"freeze_window must be >= 1, got {self.freeze_window}"
            )
        if self.epoch_distinct_run_count < 0:
            raise ValueError(
                f"epoch_distinct_run_count must be >= 0, "
                f"got {self.epoch_distinct_run_count}"
            )
        expected_is_frozen = self.epoch_distinct_run_count < self.freeze_window
        if self.is_frozen != expected_is_frozen:
            raise ValueError(
                f"is_frozen ({self.is_frozen}) inconsistent with "
                f"epoch_distinct_run_count ({self.epoch_distinct_run_count}) "
                f"and freeze_window ({self.freeze_window})"
            )
        expected_next = self.epoch_distinct_run_count + 1
        if self.next_run_index_in_epoch != expected_next:
            raise ValueError(
                f"next_run_index_in_epoch ({self.next_run_index_in_epoch}) "
                f"must equal epoch_distinct_run_count + 1 ({expected_next})"
            )
```

### 3.2 _FROZEN_DECISION_LABEL (新設、 module 内 const)

```python
_FROZEN_DECISION_LABEL: Final[Literal["skip_frozen"]] = "skip_frozen"
```

### 3.3 DecisionLabel 拡張

```python
# src/alpha_factory/calibrate_gate.py: 69-77 (既存)

DecisionLabel = Literal[
    "tighten",
    "loosen",
    "in_band",
    "skip_disabled",
    "skip_sample_size",
    "skip_zero_variance",
    "skip_frozen",          # ← T069 追加
]
```

### 3.4 CalibrateConfig.__post_init__ 強化

```python
# src/alpha_factory/calibrate_gate.py: 173-207 (既存) → 修正

def __post_init__(self) -> None:
    # ... (既存 check 群はそのまま)
    if self.threshold_delta_abs_max <= 0:
        raise ConfigError(
            f"threshold_delta_abs_max must be > 0, "
            f"got {self.threshold_delta_abs_max}"
        )
    # ↓ T069 追加 (synthesis § 8.6 SSOT)
    if self.threshold_delta_abs_max > 0.03:
        raise ConfigError(
            f"threshold_delta_abs_max must be <= 0.03 "
            f"(synthesis § 8.6 SSOT), got {self.threshold_delta_abs_max}"
        )
    # ... (既存 check 群はそのまま)
```

### 3.5 DriftAnalysis 拡張

```python
# src/alpha_factory/calibrate_gate_history.py: 137-147 (既存) → 修正

@dataclass(frozen=True)
class DriftAnalysis:
    """直近 N Run の drift 分析結果."""

    records: tuple[HistoryRecord, ...]
    alerts: DriftAlerts
    n_tighten: int
    n_loosen: int
    n_in_band: int
    n_skip_frozen: int   # ← T069 追加
    n_clamped_floor_ceiling: int
    max_abs_gap: float
```

`compute_drift`:
```python
# src/alpha_factory/calibrate_gate_history.py: 150-194 (既存) → 修正部分のみ

def compute_drift(
    records: Iterable[HistoryRecord],
    *,
    monotone_threshold: int = 4,
    clamp_threshold: int = 3,
    band_multiplier: float = 2.0,
) -> DriftAnalysis:
    """直近 N record から drift 判定を出す."""
    rec_tuple = tuple(records)
    n_tighten = sum(1 for r in rec_tuple if r.decision == "tighten")
    n_loosen = sum(1 for r in rec_tuple if r.decision == "loosen")
    n_in_band = sum(1 for r in rec_tuple if r.decision == "in_band")
    n_skip_frozen = sum(1 for r in rec_tuple if r.decision == "skip_frozen")  # ← T069 追加
    n_clamped = sum(1 for r in rec_tuple if r.clamped_by_floor_or_ceiling)
    # ... (既存 alerts 計算、 max_abs_gap 計算はそのまま)
    return DriftAnalysis(
        records=rec_tuple,
        alerts=alerts,
        n_tighten=n_tighten,
        n_loosen=n_loosen,
        n_in_band=n_in_band,
        n_skip_frozen=n_skip_frozen,   # ← T069 追加
        n_clamped_floor_ceiling=n_clamped,
        max_abs_gap=max_abs_gap,
    )
```

## 4. アルゴリズム詳細

### 4.1 evaluate_freeze_status

```python
# src/alpha_factory/calibrate_freeze.py

from collections.abc import Sequence
from typing import Final

import structlog

from src.alpha_factory.calibrate_gate_history import HistoryRecord

logger = structlog.get_logger("calibrate_freeze")

DEFAULT_FREEZE_WINDOW: Final[int] = 3  # synthesis § 8.6 SSOT


def evaluate_freeze_status(
    records: Sequence[HistoryRecord],
    *,
    dataset_epoch_id: str,
    freeze_window: int = DEFAULT_FREEZE_WINDOW,
) -> FreezeStatus:
    """epoch 内 calibrate-gate freeze 判定 (pure function, no I/O).

    SSOT: 概念設計 §5.1 / §3.3 / §3.3.1.

    Args:
        records: 全 history record (caller で read_history 済 list).
                 read_history で v1 record は skip 済前提 (T058 SSOT).
        dataset_epoch_id: 現 RUN の epoch 識別子 (T058 / T059 担当の値).
                          空文字 / None は ValueError raise (caller 運用契約:
                          dataset_epoch_id 空なら calibrate-gate 自体を起動しない).
        freeze_window: 凍結窓サイズ (synthesis § 8.6 で 3 確定).

    Returns:
        FreezeStatus.

    Raises:
        ValueError: dataset_epoch_id が None or 空文字、 freeze_window < 1.
    """
    # 入力 validation
    if dataset_epoch_id is None or not isinstance(dataset_epoch_id, str):
        raise ValueError(
            f"dataset_epoch_id must be non-empty str, "
            f"got {type(dataset_epoch_id).__name__}: {dataset_epoch_id!r}"
        )
    if not dataset_epoch_id:
        raise ValueError(
            "dataset_epoch_id must be non-empty (caller contract: "
            "do not start calibrate-gate when dataset_epoch_id is empty)"
        )
    if freeze_window < 1:
        raise ValueError(
            f"freeze_window must be >= 1, got {freeze_window}"
        )

    # scope match (synthesis § 8.6 1 軸 SSOT)
    matching_records = [
        r for r in records if r.dataset_epoch_id == dataset_epoch_id
    ]

    # distinct Run count (Round 1 [C2] 反映、 detailed Round 1 [W2] で空文字 run_id も除外)
    # Round 2 [W1] 反映: null と empty を別カウンタに分離して運用時の異常分類を明確化
    null_run_id_count = 0
    empty_run_id_count = 0
    distinct_run_ids: set[str] = set()
    for r in matching_records:
        if r.applied_from_run_id is None:
            null_run_id_count += 1
            continue
        if not r.applied_from_run_id:  # 空文字 (anomalous)
            empty_run_id_count += 1
            continue
        distinct_run_ids.add(r.applied_from_run_id)

    epoch_distinct_run_count = len(distinct_run_ids)

    # Round 2 [W1] 反映: v2 record で applied_from_run_id=None / 空文字は異常
    # (T058 v2 schema で必須化を申し送り済、 ただし defense-in-depth で log)
    # null と empty を別 field に分離して運用時の異常分類を明確化
    if null_run_id_count > 0 or empty_run_id_count > 0:
        logger.warning(
            "calibrate_freeze.invalid_run_id",
            dataset_epoch_id=dataset_epoch_id,
            n_records_with_null_run_id=null_run_id_count,
            n_records_with_empty_run_id=empty_run_id_count,
        )

    is_frozen = epoch_distinct_run_count < freeze_window

    return FreezeStatus(
        is_frozen=is_frozen,
        epoch_distinct_run_count=epoch_distinct_run_count,
        freeze_window=freeze_window,
        next_run_index_in_epoch=epoch_distinct_run_count + 1,
    )
```

### 4.2 decide_with_freeze

```python
# src/alpha_factory/calibrate_freeze.py (続き)

from src.alpha_factory.calibrate_gate import (
    AggregatedSample,
    CalibrateConfig,
    Decision,
    decide,
)


def decide_with_freeze(
    sample: AggregatedSample,
    config: CalibrateConfig,
    *,
    freeze_status: FreezeStatus,
) -> Decision:
    """freeze 判定込みで decide() を呼ぶ wrapper.

    SSOT: 概念設計 §5.2 / §4.2.

    freeze_status.is_frozen=True の場合、 sample / config 内容にかかわらず
    decision="skip_frozen" + new_threshold=config.prev_threshold で即時返却.
    False の場合、 既存 decide(sample, config) に委譲.

    Args:
        sample: 集計結果.
        config: calibrate 設定 (config.prev_threshold が freeze 中の new_threshold ソース).
        freeze_status: evaluate_freeze_status の戻り値.

    Returns:
        Decision. freeze 中は:
            decision="skip_frozen"
            new_threshold=config.prev_threshold
            delta=0.0
            q_target=None
            var_fitness_pen=None
            raw_target_threshold=None
            clamped_by_delta=False
            clamped_by_floor_or_ceiling=False
            effective_sample_size=sample.n_rows_used
    """
    if freeze_status.is_frozen:
        return Decision(
            decision=_FROZEN_DECISION_LABEL,
            new_threshold=config.prev_threshold,
            delta=0.0,
            q_target=None,
            var_fitness_pen=None,
            raw_target_threshold=None,
            clamped_by_delta=False,
            clamped_by_floor_or_ceiling=False,
            effective_sample_size=sample.n_rows_used,
        )
    return decide(sample, config)
```

## 5. テスト計画詳細

### 5.1 `tests/alpha_factory/test_calibrate_freeze.py` (新規)

```python
import pytest

from src.alpha_factory.calibrate_freeze import (
    DEFAULT_FREEZE_WINDOW,
    FreezeStatus,
    decide_with_freeze,
    evaluate_freeze_status,
)
from src.alpha_factory.calibrate_gate import (
    AggregatedSample,
    CalibrateConfig,
    Decision,
)
from src.alpha_factory.calibrate_gate_history import HistoryRecord


# --- fixtures ----------------------------------------------------------------

def _make_record(
    *,
    epoch_id: str,
    run_id: str | None,
    decision: str = "tighten",
    **kwargs,
) -> HistoryRecord:
    """T058 v2 必須 field を埋める HistoryRecord 構築 helper.

    PR 条件 (Round 2 [C2] 反映で単一化): T058 PR が先行 merge されていることが前提.
    schema_version=2 + calibrate_history_schema_version=2 を固定で使用 (代替分岐なし).
    T058 が未 merge の段階で T069 PR を出すことは許容しない (cascade port 整合性のため).
    """
    defaults = dict(
        run_id=run_id or "run_unspecified",
        applied_at="2026-04-30T10:00:00+00:00",
        n_rows_total=100,
        n_rows_used=80,
        aggregation_mode="latest",
        aggregation_window=1,
        actual_pass_rate=0.18,
        target_pass_rate=0.20,
        tol=0.02,
        prev_threshold=0.50,
        new_threshold=0.48,
        delta=-0.02,
        decision=decision,
        var_fitness_pen=0.001,
        clamped_by_delta=False,
        clamped_by_floor_or_ceiling=False,
        stage_b_pass_count=0,
        stage_c_pass_count=0,
        live_criteria_gap={},
        # T054 cross-run guard
        schema_version=2,  # T058 後の v2 SCHEMA_VERSION (T058 で SCHEMA_VERSION=2 に bump 想定)
        base_config_hash="hash_a",
        full_config_hash="full_hash_a",
        dataset_span=["2024-01-01", "2026-04-21"],
        instrument="EUR_USD",
        stage_gate_version="v0.1.0",
        applied_from_run_id=run_id,
        # T058 で v2 必須化される field 群
        dataset_epoch_id=epoch_id,
        calibrate_history_schema_version=2,  # T058 で導入、 v2 必須
    )
    defaults.update(kwargs)
    return HistoryRecord(**defaults)


# --- evaluate_freeze_status: validation ----------------------------------------

class TestEvaluateFreezeStatusValidation:
    """evaluate_freeze_status の入力 validation 系."""

    def test_F10a_dataset_epoch_id_none_raises_value_error(self):
        with pytest.raises(ValueError, match="dataset_epoch_id must be"):
            evaluate_freeze_status(records=[], dataset_epoch_id=None)  # type: ignore[arg-type]

    def test_F10b_dataset_epoch_id_empty_raises_value_error(self):
        with pytest.raises(ValueError, match="non-empty"):
            evaluate_freeze_status(records=[], dataset_epoch_id="")

    def test_F9a_freeze_window_zero_raises_value_error(self):
        with pytest.raises(ValueError, match="freeze_window must be >= 1"):
            evaluate_freeze_status(
                records=[], dataset_epoch_id="ep1", freeze_window=0
            )

    def test_F9b_freeze_window_negative_raises_value_error(self):
        with pytest.raises(ValueError, match="freeze_window must be >= 1"):
            evaluate_freeze_status(
                records=[], dataset_epoch_id="ep1", freeze_window=-1
            )


# --- evaluate_freeze_status: counting -----------------------------------------

class TestEvaluateFreezeStatusCounting:
    """count ロジックの正当性."""

    def test_empty_history_is_frozen_count_zero(self):
        # Happy path: epoch 1 Run 目 (count=0 < 3) → frozen
        result = evaluate_freeze_status(records=[], dataset_epoch_id="ep1")
        assert result.is_frozen is True
        assert result.epoch_distinct_run_count == 0
        assert result.next_run_index_in_epoch == 1
        assert result.freeze_window == DEFAULT_FREEZE_WINDOW

    def test_two_runs_frozen(self):
        # F1 / F3 / Happy path: epoch 内 2 distinct Run → freeze
        records = [
            _make_record(epoch_id="ep1", run_id="run_001"),
            _make_record(epoch_id="ep1", run_id="run_002"),
        ]
        result = evaluate_freeze_status(records=records, dataset_epoch_id="ep1")
        assert result.is_frozen is True
        assert result.epoch_distinct_run_count == 2
        assert result.next_run_index_in_epoch == 3

    def test_three_runs_unfrozen(self):
        # Happy path: count=3 → unfrozen (4 Run 目から calibrate)
        records = [
            _make_record(epoch_id="ep1", run_id=f"run_{i:03d}")
            for i in range(1, 4)
        ]
        result = evaluate_freeze_status(records=records, dataset_epoch_id="ep1")
        assert result.is_frozen is False
        assert result.epoch_distinct_run_count == 3
        assert result.next_run_index_in_epoch == 4

    def test_F1_other_epoch_records_excluded(self):
        # F1: 異なる epoch_id record は filter で count 除外
        records = [
            _make_record(epoch_id="ep1", run_id="run_001"),
            _make_record(epoch_id="ep0", run_id="run_xx1"),
            _make_record(epoch_id="ep0", run_id="run_xx2"),
        ]
        result = evaluate_freeze_status(records=records, dataset_epoch_id="ep1")
        assert result.is_frozen is True
        assert result.epoch_distinct_run_count == 1

    def test_F3_epoch_id_change_resets_count(self):
        # F3: 旧 epoch (ep0) で 5 Run 進行済でも、 新 epoch (ep1) では count=0 から開始
        records = [
            _make_record(epoch_id="ep0", run_id=f"run_xx{i}") for i in range(5)
        ]
        result = evaluate_freeze_status(records=records, dataset_epoch_id="ep1")
        assert result.is_frozen is True
        assert result.epoch_distinct_run_count == 0
        assert result.next_run_index_in_epoch == 1

    def test_F5_duplicate_run_id_counted_once(self):
        # F5: 同 run_id 二重 append → count 増えない
        records = [
            _make_record(epoch_id="ep1", run_id="run_001", decision="tighten"),
            _make_record(epoch_id="ep1", run_id="run_001", decision="loosen"),  # 二重
            _make_record(epoch_id="ep1", run_id="run_002"),
        ]
        result = evaluate_freeze_status(records=records, dataset_epoch_id="ep1")
        assert result.epoch_distinct_run_count == 2
        assert result.is_frozen is True

    def test_F15a_null_run_id_record_excluded_with_warning(self, caplog):
        # F15a: applied_from_run_id None は count 除外、 warning 出力
        records = [
            _make_record(epoch_id="ep1", run_id="run_001"),
            _make_record(epoch_id="ep1", run_id=None),  # None
        ]
        result = evaluate_freeze_status(records=records, dataset_epoch_id="ep1")
        assert result.epoch_distinct_run_count == 1
        # warning log の存在確認 (structlog caplog 経由)
        assert any(
            "calibrate_freeze.invalid_run_id" in str(rec.msg)
            for rec in caplog.records
        )

    def test_F15b_empty_run_id_record_excluded_with_warning(self, caplog):
        # F15b (Round 1 [W2] 反映): 空文字 run_id も除外 + warning
        records = [
            _make_record(epoch_id="ep1", run_id="run_001"),
            _make_record(epoch_id="ep1", run_id=""),  # 空文字 (anomalous)
        ]
        result = evaluate_freeze_status(records=records, dataset_epoch_id="ep1")
        assert result.epoch_distinct_run_count == 1
        assert any(
            "calibrate_freeze.invalid_run_id" in str(rec.msg)
            for rec in caplog.records
        )

    def test_custom_freeze_window(self):
        # custom freeze_window=5
        records = [
            _make_record(epoch_id="ep1", run_id=f"run_{i}")
            for i in range(4)
        ]
        result = evaluate_freeze_status(
            records=records, dataset_epoch_id="ep1", freeze_window=5
        )
        assert result.is_frozen is True
        assert result.epoch_distinct_run_count == 4
        assert result.freeze_window == 5

    def test_F11_many_runs_unfrozen_no_upper_limit(self):
        # F11: count >> 3 でも freeze は False (= 通常 calibrate)
        records = [
            _make_record(epoch_id="ep1", run_id=f"run_{i:03d}")
            for i in range(10)
        ]
        result = evaluate_freeze_status(records=records, dataset_epoch_id="ep1")
        assert result.is_frozen is False
        assert result.epoch_distinct_run_count == 10


# --- decide_with_freeze ------------------------------------------------------

class TestDecideWithFreeze:
    """decide_with_freeze の挙動."""

    def _make_config(self, prev_threshold: float = 0.50) -> CalibrateConfig:
        return CalibrateConfig(
            enabled=True,
            aggregation_mode="latest",
            aggregation_window=1,
            pass_rate_tolerance_abs=0.02,
            threshold_delta_abs_max=0.03,
            threshold_floor=-100.0,
            threshold_ceiling=100.0,
            min_sample_size=5,
            eps_var=1.0e-9,
            target_pass_rate=0.20,
            prev_threshold=prev_threshold,
        )

    def _make_sample(
        self, n_rows_used: int = 80, actual_pass_rate: float = 0.18,
    ) -> AggregatedSample:
        """既存 AggregatedSample (calibrate_gate.py:273-283) を埋める helper.

        既存 dataclass field 7 つ全てを埋める:
            n_rows_total, n_rows_used, pass_count_used, actual_pass_rate,
            fitness_pen_pool (tuple[float, ...]), mode (AggregationMode), window

        Round 2 [W3] 反映: mode="last_k_generations" は AGGREGATION_MODES (= Literal[
        "last_k_generations", "all_generations", "latest"]) の valid 値。
        AggregationMode は Literal なので type check は静的に通る。
        """
        # variance を持たせて zero_variance を回避
        pool = tuple(0.10 + 0.01 * i for i in range(n_rows_used))
        return AggregatedSample(
            n_rows_total=n_rows_used + 20,
            n_rows_used=n_rows_used,
            pass_count_used=int(n_rows_used * actual_pass_rate),
            actual_pass_rate=actual_pass_rate,
            fitness_pen_pool=pool,
            mode="last_k_generations",
            window=5,
        )

    def test_decide_with_freeze_frozen_returns_skip_frozen(self):
        # Happy path (decide_with_freeze 委譲なし側): is_frozen=True → "skip_frozen"
        # 注: F4 は「history append」 の Phase 2 IT、 本 unit はそれと別の責務
        config = self._make_config(prev_threshold=0.50)
        sample = self._make_sample()
        fs = FreezeStatus(
            is_frozen=True,
            epoch_distinct_run_count=2,
            freeze_window=3,
            next_run_index_in_epoch=3,
        )
        result = decide_with_freeze(sample, config, freeze_status=fs)
        assert result.decision == "skip_frozen"
        assert result.new_threshold == 0.50
        assert result.delta == 0.0
        assert result.q_target is None
        assert result.var_fitness_pen is None
        assert result.raw_target_threshold is None
        assert result.clamped_by_delta is False
        assert result.clamped_by_floor_or_ceiling is False
        assert result.effective_sample_size == sample.n_rows_used

    def test_unfrozen_delegates_to_decide(self):
        # 完全委譲: count=3 で `decide()` 結果と同一
        from src.alpha_factory.calibrate_gate import decide
        config = self._make_config(prev_threshold=0.50)
        sample = self._make_sample()
        fs = FreezeStatus(
            is_frozen=False,
            epoch_distinct_run_count=3,
            freeze_window=3,
            next_run_index_in_epoch=4,
        )
        expected = decide(sample, config)
        result = decide_with_freeze(sample, config, freeze_status=fs)
        assert result == expected


# --- FreezeStatus invariants -------------------------------------------------

class TestFreezeStatusInvariants:
    def test_inconsistent_is_frozen_raises(self):
        with pytest.raises(ValueError, match="is_frozen"):
            FreezeStatus(
                is_frozen=True,
                epoch_distinct_run_count=5,  # >= 3 だが is_frozen=True
                freeze_window=3,
                next_run_index_in_epoch=6,
            )

    def test_inconsistent_next_index_raises(self):
        with pytest.raises(ValueError, match="next_run_index_in_epoch"):
            FreezeStatus(
                is_frozen=False,
                epoch_distinct_run_count=3,
                freeze_window=3,
                next_run_index_in_epoch=5,  # 4 が正
            )

    def test_negative_count_raises(self):
        with pytest.raises(ValueError, match="epoch_distinct_run_count must be >= 0"):
            FreezeStatus(
                is_frozen=True,
                epoch_distinct_run_count=-1,
                freeze_window=3,
                next_run_index_in_epoch=0,
            )
```

### 5.2 `tests/alpha_factory/test_calibrate_gate.py` 拡張

```python
class TestCalibrateConfigContract:
    def test_F8_threshold_delta_abs_max_at_synthesis_limit_ok(self):
        # F8 (boundary): 0.03 ちょうどは OK
        CalibrateConfig(..., threshold_delta_abs_max=0.03, ...)

    def test_F8_threshold_delta_abs_max_above_synthesis_limit_raises(self):
        # F8 main: 0.03 超は ConfigError (synthesis § 8.6 SSOT)
        with pytest.raises(ConfigError, match="must be <= 0.03"):
            CalibrateConfig(..., threshold_delta_abs_max=0.05, ...)

    def test_threshold_delta_abs_max_zero_raises(self):
        # 既存挙動 (T069 で変更なし、 既存 contract > 0)
        with pytest.raises(ConfigError, match="must be > 0"):
            CalibrateConfig(..., threshold_delta_abs_max=0.0, ...)
```

### 5.3 `tests/alpha_factory/test_calibrate_gate_history.py` 拡張

```python
def test_F12_compute_drift_counts_skip_frozen():
    records = [
        HistoryRecord(..., decision="skip_frozen", ...),
        HistoryRecord(..., decision="tighten", ...),
        HistoryRecord(..., decision="skip_frozen", ...),
    ]
    result = compute_drift(records)
    assert result.n_skip_frozen == 2
    assert result.n_tighten == 1
    # alert は skip_frozen で発火しない
    assert result.alerts.monotone_tighten is False
```

## 6. default.yaml の同時更新方針

### 6.1 現状確認

`config/alpha_factory/default.yaml` の `stage_gate.stage_a.calibrate.threshold_delta_abs_max` の現値は実装時に確認:
```bash
grep -A 1 "threshold_delta_abs_max" config/alpha_factory/default.yaml
```

### 6.2 適用ルール

- 現値 ≤ 0.03: そのまま維持 (= 既存 yaml の更新不要)
- 現値 > 0.03: `0.03` に書き換え (= synthesis § 8.6 SSOT 適用)

### 6.3 実装手順

1. 現値読み取り
2. > 0.03 なら `ruamel.yaml` で読み込み → `0.03` に置換 → atomic write
3. PR description で「現値 X → 0.03 に SSOT 化 (synthesis § 8.6)」 を記録

## 7. docs/alpha_factory/stage-gates.md 更新方針

T054 セクション (state file 経由の自動適用) の延長として T069 セクションを追加:

```markdown
## T069: epoch key + 3 Run freeze + Δ ≤ 0.03 (synthesis § 8.6)

### 凍結窓 3 Run

`dataset_epoch_id` を scope key として、 同 epoch 内の最初 3 distinct Run は
calibrate-gate を **freeze** (= threshold 適用なし、 `decision="skip_frozen"`)。
4 Run 目以降から通常の `tighten` / `loosen` 判定が有効化される。

count は `HistoryRecord.applied_from_run_id` の distinct set で測る (= 同 run_id
二重 append / retry に耐性)。

### |Δ| ≤ 0.03

`stage_gate.stage_a.calibrate.threshold_delta_abs_max` を `0.03` に SSOT 固定。
config 違反 (> 0.03) は起動時に `ConfigError` で fail-closed。

### scope key

freeze 判定は `dataset_epoch_id` 単独で行う。 cross-run contamination guard
は T058 `load_calibrated_threshold` の 4 軸 verify (base_config_hash + 
dataset_epoch_id + instrument + stage_gate_version) が別途担保 (多層防御)。

### epoch 跨ぎ再利用遮断

T069 (Phase 1) では yaml への threshold 書き戻し経路は新設しない。
Phase 2 (cascade port 切替) で以下のいずれかを確定:
- 案 A: yaml=immutable seed、 calibrate は history JSONL 専用 (推奨)
- 案 B: epoch 切替時に yaml reset
- 案 C: stage_a_threshold 自体を削除 (synthesis § 12.3 厳密準拠)
```

## 8. ログ契約 (詳細、 概念設計 §7 を SSOT 化)

### 8.1 calibrate_freeze.invalid_run_id

```python
logger.warning(
    "calibrate_freeze.invalid_run_id",
    dataset_epoch_id=dataset_epoch_id,             # str
    n_records_with_null_run_id=null_count,         # int (None record 数)
    n_records_with_empty_run_id=empty_count,       # int (空文字 record 数)
)
```

タイミング: `evaluate_freeze_status` 内で `applied_from_run_id is None` または空文字の v2 record を 1 つでも検出。 null と empty を別カウンタで出力 (Round 2 [W1] 反映で異常分類を明確化)。

### 8.2 calibrate_freeze.status (Phase 2 で scripts/calibrate_gate.py が出力)

T069 PR では出力しない (= scripts/calibrate_gate.py 配線を Phase 2 で行うため)。 ただし docstring + § 7 で必須 fields を確定:

`FreezeStatus` (§3.1) に `dataset_epoch_id` field は持たない (= 入力引数として caller が知っているので redundant)。 caller (Phase 2 の scripts/calibrate_gate.py) で **caller 側の closure 変数** から `dataset_epoch_id` / `applied_from_run_id` を log に渡す形式 (Round 1 [C2] / [S3] 反映):

```python
# Phase 2 で scripts/alpha_factory/calibrate_gate.py 起動時に実行されるイメージ
fs = evaluate_freeze_status(records, dataset_epoch_id=current_epoch_id)
logger.info(
    "calibrate_freeze.status",
    dataset_epoch_id=current_epoch_id,         # caller closure (引数値)
    epoch_distinct_run_count=fs.epoch_distinct_run_count,
    freeze_window=fs.freeze_window,
    next_run_index_in_epoch=fs.next_run_index_in_epoch,
    is_frozen=fs.is_frozen,
    applied_from_run_id=current_run_id,         # caller closure (現 Run の id)
)
```

`FreezeStatus` 自身は dataset_epoch_id を保持しない (= immutable status のみ)、 caller がコンテキストを別途保持して log に乗せる責務分離。

## 9. F1-F15 失敗モード対応マトリクス (Round 1 [S2] / Round 2 [C1] 反映、 厳密 1:1 対応)

各 failure に **一意の test_id**を割当。 Phase 1 unit test で塞ぐもの / Phase 2 integration で塞ぐもの / PR review check で塞ぐもの を区別。

| failure | 概念設計 § | 詳細設計の対応 | test_id (Phase 1) | Phase 2 IT / PR check |
|---|---|---|---|---|
| F1 scope_key 不一致で count 過大 | concept §10 | `r.dataset_epoch_id == dataset_epoch_id` filter | `test_F1_other_epoch_records_excluded` | — |
| F2 v1 record が count に混入 | concept §10 | T058 read_history skip 前提 + applied_from_run_id None/空文字 除外 | (T058 範囲、 cross-PR 追跡 ID `T058-IT-v1-skip` で T058 側テストにマッピング) | — |
| F3 epoch 切替で count reset 失敗 | concept §10 | filter で別 epoch 除外 | `test_F3_epoch_id_change_resets_count` | — |
| F4 skip_frozen が history に append されない | concept §10 | docstring で固定、 caller 配線は Phase 2 | — | `Phase2-IT-F4` (scripts/calibrate_gate.py 経由 record append integration) |
| F5 同一 Run 二重 append で freeze 早期解除 | concept §10 | distinct set count | `test_F5_duplicate_run_id_counted_once` | — |
| F6 同 dataset_epoch_id で base_config_hash 変化 | concept §10 | T058 4 軸 verify で別 layer 除外 | (T058 範囲、 cross-PR 追跡 ID `T058-IT-cross-run-guard` で T058 側テストにマッピング) | — |
| F7 skip_frozen state 解決分裂 | concept §10 | SSOT 「load 対象外 → config 値」 | — | `Phase2-IT-F7` (run_ga.py 起動 → load_calibrated_threshold=None → config fallback の end-to-end) |
| F8 \|Δ\| > 0.03 config | concept §10 | `CalibrateConfig.__post_init__` で fail-closed | `test_F8_threshold_delta_abs_max_above_synthesis_limit_raises` | — |
| F9 freeze_window 0 / 負 | concept §10 | ValueError raise | `test_F9a_freeze_window_zero_raises_value_error` / `test_F9b_freeze_window_negative_raises_value_error` | — |
| F10 dataset_epoch_id None / 空文字 | concept §10 | ValueError raise | `test_F10a_dataset_epoch_id_none_raises_value_error` / `test_F10b_dataset_epoch_id_empty_raises_value_error` | — |
| F11 count >> 3 | concept §10 | 上限なし、 issue なし | `test_F11_many_runs_unfrozen_no_upper_limit` | — |
| F12 monitoring/report が skip_frozen を reject | concept §10 | Consumer Inventory で確認済 + n_skip_frozen 追加 | `test_F12_compute_drift_counts_skip_frozen` | — |
| F13 Phase 1 単独 merge で yaml 0.03 超 | concept §10 | atomic cut で吸収、 PR review checklist で確認 | — | `Phase1-PR-CHECK-F13` (PR description で「default.yaml 現値 X → 0.03 SSOT 化済」 を明記、 reviewer が confirm) |
| F14 epoch 跨ぎ yaml fallback 再利用 | concept §10 | T069 で yaml 書き戻し経路を作らない | — | `Phase2-IT-F14` (yaml 書き戻し方式案 A 確定後の epoch 跨ぎ E2E) |
| F15 applied_from_run_id None / 空文字 v2 record で永久 freeze | concept §10 | T058 v2 必須化申し送り + warning log emit | `test_F15a_null_run_id_record_excluded_with_warning` / `test_F15b_empty_run_id_record_excluded_with_warning` | — |

## 10. backward-compat 確認

### 10.1 既存 caller への影響

| caller | 影響 | mitigation |
|---|---|---|
| `decide()` direct call | 影響なし (signature 不変) | — |
| `compute_drift()` direct call | DriftAnalysis に field 追加 (frozen dataclass) → 既存 caller の attribute 読み出しは影響なし、 ただし内部 `compute_drift` 改変で **追加引数を渡す必要あり** | T069 PR 内で同時更新 |
| `CalibrateConfig.__post_init__` | `threshold_delta_abs_max > 0.03` で ConfigError | default.yaml 同時更新で吸収 (atomic cut) |
| `DecisionLabel` | `Literal` 拡張 (TypeError なし) | mypy / type check に再走 |

### 10.2 Test fixture 影響

既存 `tests/alpha_factory/test_calibrate_gate_history.py` の `compute_drift` test 群は `n_skip_frozen` を assert していないため影響なし。 ただし `DriftAnalysis` を直接構築する fixture があれば `n_skip_frozen=0` を渡す必要があり (= grep で抽出 → 詳細実装時に確認)。

## 11. DoD (Definition of Done)

### 11.1 Implementation
- [ ] `src/alpha_factory/calibrate_freeze.py` 新規実装 (FreezeStatus + 2 関数)
- [ ] `src/alpha_factory/calibrate_gate.py` DecisionLabel + CalibrateConfig contract 強化
- [ ] `src/alpha_factory/calibrate_gate_history.py` DriftAnalysis.n_skip_frozen + compute_drift 拡張
- [ ] `config/alpha_factory/default.yaml` threshold_delta_abs_max ≤ 0.03 確認 (>0.03 なら 0.03 に更新)
- [ ] `docs/alpha_factory/stage-gates.md` T069 セクション追加

### 11.2 Tests
- [ ] `tests/alpha_factory/test_calibrate_freeze.py` F1/F3/F5/F8/F9/F10/F11/F12/F15 unit test
- [ ] `tests/alpha_factory/test_calibrate_gate.py` CalibrateConfig contract test 追加
- [ ] `tests/alpha_factory/test_calibrate_gate_history.py` n_skip_frozen test 追加
- [ ] 全既存 test 通過 (破壊変更なし確認)
- [ ] ruff / pyright clean

### 11.3 Cross-PR / PR review checklist
- [ ] **T058 PR が先行 merge されていることを確認** (Round 3 [S2] 反映、 PR description に「T058 merge commit hash: <SHA>」 必須記載)
- [ ] PR description で「Phase 1 範囲 / Phase 2 申し送り 12 項目」 を明記
- [ ] PR description checklist に `Phase1-PR-CHECK-F13` 「default.yaml 現値 X → 0.03 SSOT 化済」 を含める
- [ ] T058 詳細設計に `HistoryRecord.applied_from_run_id` v2 必須化を追加要請 (= T058 設計改訂を別 PR)
- [ ] `tests/alpha_factory/test_calibrate_freeze.py` の structlog + caplog 互換性を実装時に確認 (Round 3 [W2] 反映、 既存 test fixture が structlog の caplog を有効化しているか実装時 verify、 必要なら structlog testing helpers を追加)

## 12. Phase 1 / Phase 2 申し送り (合計 12 項目、 Round 1 [C4] 反映で 1-12 完全列挙)

### 12.1 Phase 1 (T069 PR で同時更新、 big-bang atomic cut)

| # | 箇所 | 変更内容 |
|---|---|---|
| 1 | `src/alpha_factory/calibrate_freeze.py` | 新設 (FreezeStatus + 2 関数) |
| 2 | `src/alpha_factory/calibrate_gate.py` | DecisionLabel + CalibrateConfig contract 強化 |
| 3 | `src/alpha_factory/calibrate_gate_history.py` | DriftAnalysis.n_skip_frozen 追加 + compute_drift 集計 |
| 4 | `config/alpha_factory/default.yaml` | threshold_delta_abs_max 現値確認 + 必要なら 0.03 SSOT |
| 5 | `docs/alpha_factory/stage-gates.md` | T069 仕様追記 |
| 6 | `tests/alpha_factory/test_calibrate_freeze.py` + 既存 test 拡張 | F1-F13 + F15 unit test |

### 12.2 Phase 2 (cascade port 切替 commit、 synthesis § 12.4)

| # | 箇所 | 変更内容 | 担当 |
|---|---|---|---|
| 7 | `scripts/alpha_factory/calibrate_gate.py` | `evaluate_freeze_status` + `decide_with_freeze` 呼び替え + skip_frozen record append + yaml 書き戻し方式案 A 確定 | Phase 2 |
| 8 | `scripts/alpha_factory/calibrate_gate_drift.py` | `n_skip_frozen` を出力に追加 | Phase 2 |
| 9 | `scripts/alpha_factory/run_ga.py` | freeze 中の log (任意)、 _resolve_stage_a_threshold 不変 | Phase 2 |
| 10 | 運用契約 preflight check | `dataset_epoch_id` 空なら calibrate 起動しない | Phase 2 |
| 11 | T058 詳細設計改訂 | `HistoryRecord.applied_from_run_id: str` v2 必須化 | T058 詳細設計改訂 |
| 12 | yaml 書き戻し再利用遮断 | 案 A (immutable seed) 推奨確定 | Phase 2 |

### 12.3 Phase 2 integration test 申し送り (Round 1 [S2] 反映)

| test_id | シナリオ |
|---|---|
| `Phase2-IT-F4` | scripts/calibrate_gate.py 経由で skip_frozen record append が history に保存される |
| `Phase2-IT-F7` | run_ga.py 起動 → freeze 中 → load_calibrated_threshold=None → config 値 fallback の end-to-end |
| `Phase2-IT-F14` | yaml 書き戻し方式案 A 確定後の epoch 跨ぎ E2E (前 epoch threshold が次 epoch に流入しない) |

## 13. 実装順序 (PR 内)

1. `src/alpha_factory/calibrate_freeze.py` 新規 (FreezeStatus + 2 関数)
2. `src/alpha_factory/calibrate_gate.py` 拡張 (DecisionLabel + contract)
3. `src/alpha_factory/calibrate_gate_history.py` 拡張 (DriftAnalysis + compute_drift)
4. `config/alpha_factory/default.yaml` 同時更新 (現値確認後)
5. `tests/alpha_factory/test_calibrate_freeze.py` 新規
6. `tests/alpha_factory/test_calibrate_gate.py` 拡張
7. `tests/alpha_factory/test_calibrate_gate_history.py` 拡張
8. `docs/alpha_factory/stage-gates.md` T069 追記
9. PR description 整理 (Phase 2 申し送り 12 項目)

## 14. 重要な設計判断 SSOT (詳細設計内、 概念設計と同期)

1. **scope key 1 軸 (dataset_epoch_id) 厳密準拠** — concept §3.2 / detailed §4.1
2. **distinct Run count + applied_from_run_id 必須化申し送り** — concept §3.3 / §3.3.1 / detailed §4.1
3. **skip_frozen は load 対象外 (T058 既存挙動経由)** — concept §3.4 / detailed §4.2 (= caller 配線は Phase 2)
4. **|Δ| ≤ 0.03 contract 強化 + atomic cut** — concept §3.5 / detailed §3.4 / §6
5. **decide() 不変 + decide_with_freeze() 新設 (責務分離)** — concept §5 / detailed §4.2
6. **yaml 書き戻し経路は T069 で作らない (Phase 2 で案 A 確定)** — concept §3.4.1 / detailed §7
7. **applied_from_run_id None v2 record で warning log + T058 schema 申し送り** — concept §3.3.1 / detailed §4.1 / §8.1

## 15. open issues (詳細実装時に再確認、 Codex 詳細レビュー対象)

- AggregatedSample fixture の構築 (test_calibrate_freeze.py §5.1) は既存 test の helper を再利用するか単独定義するか — 詳細実装で確認
- T058 PR (HistoryRecord v2 必須化) と T069 PR の merge 順序 — T058 が先行必須 (= run_id None 永久 freeze を構造的に消す)
- structlog の caplog 設定が既存 test で動くか確認 (= structlog の test fixture 整備状況)
