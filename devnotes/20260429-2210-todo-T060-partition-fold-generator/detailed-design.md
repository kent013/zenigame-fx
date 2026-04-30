# 詳細設計: T060 — Partition + fold generator

## 使命・制約 (絶対遵守)

### zenigame-fx Alpha Factory 使命
live_criteria 全指標同時充足 + (ii-lite) 通過。 絶対制約: イントラデイ / ロング・ショート両方向 / スワップ・スプレッド反映。

### 禁止事項
1-7 (synthesis § 1.3)
8. archive スキーマ伝搬漏れ ← T058 対応済 (本 TODO は依存先)

### コーディングルール
- バグ修正テストファースト
- 全施策テスト必須、 振る舞いベース命名
- uv 必須、 ruff / mypy 通過、 Python 3.13

## 概念設計リファレンス

`devnotes/20260429-2210-todo-T060-partition-fold-generator/conceptual-design.md` (Round 2 で APPROVED)

## Round 1 review 反映 (Codex 詳細レビュー Round 1 → Round 2)

| Round 1 [Critical/Warning/Suggestion] | 修正対応 |
|---|---|
| [C1] Phase 2 申し送り 7 箇所では `calibrate_state.py:74` と `aux_preflight.py:52, 189` の `stage_b_window_months` 参照が漏れる | 申し送り DoD に 2 ファイル追加、 計 9 箇所同時更新 |
| [W1] UTC 厳密性が緩い (tzinfo あり だけだと JST `+09:00` 等が通る) | `Period.__post_init__` で `utcoffset() != timedelta(0)` を reject、 UTC のみ許可 |
| [S1] C2 parallel-path 明示強化 | Phase 1 DoD に「旧経路に新定数逆流禁止」「新経路 runtime 未配線 grep 確認」 を追加 |
| [S2] UTC 厳密性 test 追加 | `test_period_rejects_jst_aware_datetime`、 `test_period_rejects_pacific_aware_datetime` を追加 |

## 施策一覧 (Phase 1: T060 PR、 Phase 2 は別 PR)

| # | 施策名 | 変更ファイル | 優先度 |
|---|--------|------------|--------|
| 1 | `partition.py` 新規 (PeriodLabel + Period + Partition + PartitionGenerator + Fold + FoldGenerator + 例外) | `src/alpha_factory/partition.py` (新規) | Critical |
| 2 | `tests/alpha_factory/test_partition.py` 新規 (単体テスト) | (新規) | Critical |

**Phase 1 (T060 PR) スコープ = 上記 2 施策**。 `walk_forward.py` / `stage_gate.py` / `swim_lane.py` / `run_ga.py` / `default.yaml` / `config.py` / `docs/alpha_factory/stage-gates.md` + `calibrate_state.py` + `aux_preflight.py` の 9 箇所同時更新は **Phase 2 (別 PR、 T061-T064 と同時)** で実施。 T060 PR 単独 merge で runtime に影響なし。

---

## 施策 1: `partition.py` 新規作成

### 変更箇所
- ファイル: `src/alpha_factory/partition.py` (新規)

### 波及変更
- `AGENTS.md`: なし (内部 module、 T060 PR では runtime 未組込)
- `.claude/skills/zenigame-fx-{skill}/SKILL.md`: なし
- `config/alpha_factory/default.yaml`: なし (Phase 2 で旧 stage_b 関連 key 削除)
- `docs/alpha_factory/*.md`: なし (Phase 2 で stage-gates.md 更新)

### 変更後コード

```python
"""T060: Partition + Fold generator — 24m EpochWindow を canonical 10 領域 + 5 folds に分割.

詳細:
- 概念設計: devnotes/20260429-2210-todo-T060-partition-fold-generator/conceptual-design.md
- synthesis § 4.3 (Partition) + § 4.4 (Stage B fold)
- T059 依存: EpochWindow (start, end は 00:00 UTC 固定)

Phase 1 (本 TODO): 単体実装 + テストのみ、 walk_forward.py / stage_gate.py 未変更。
Phase 2 (別 PR): 9 箇所同時更新 (Phase 2 申し送り参照)。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from typing import ClassVar

# T059 EpochWindow を import (T059 merge 後前提)
from src.alpha_factory.epoch_manager import EpochWindow

__all__ = [
    "Fold",
    "FoldGenerator",
    "FoldMismatchError",
    "Partition",
    "PartitionGenerator",
    "PartitionMismatchError",
    "Period",
    "PeriodLabel",
]


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class PartitionMismatchError(ValueError):
    """24m EpochWindow と 10 領域合計の長さ不一致 / cursor != window.end."""


class FoldMismatchError(ValueError):
    """B 62w と 5 folds の長さ不一致 / 末端 fold test.end != stage_b.end."""


# ---------------------------------------------------------------------------
# PeriodLabel — Period 命名 SSOT
# ---------------------------------------------------------------------------


class PeriodLabel(StrEnum):
    """Period 命名 SSOT (string literal 依存回避)."""

    STAGE_B = "stage_b"
    STAGE_A = "stage_a"
    EMBARGO_AFTER_A = "embargo_after_a"
    STAGE_C_LITE_1 = "stage_c_lite_1"
    EMBARGO_AFTER_C_LITE_1 = "embargo_after_c_lite_1"
    STAGE_C_LITE_2 = "stage_c_lite_2"
    EMBARGO_AFTER_C_LITE_2 = "embargo_after_c_lite_2"
    STAGE_C_LITE_3 = "stage_c_lite_3"
    EMBARGO_AFTER_C_LITE_3 = "embargo_after_c_lite_3"
    STAGE_C = "stage_c"
    # Fold 用 (FoldGenerator が "fold_{k}_{train|embargo|test}" suffix で生成)
    FOLD_TRAIN = "fold_train"
    FOLD_EMBARGO = "fold_embargo"
    FOLD_TEST = "fold_test"


# ---------------------------------------------------------------------------
# Period — 半開区間 [start, end)、 UTC-aware
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Period:
    """時系列上の半開区間 [start, end). UTC-aware datetime 限定."""

    start: datetime
    end: datetime
    label: str  # PeriodLabel.value or fold_{k}_{train|embargo|test}

    def __post_init__(self) -> None:
        # UTC 厳密性 (Round 1 [Warning] 反映: tzinfo あり + utcoffset==0)
        for name, dt in (("start", self.start), ("end", self.end)):
            if dt.tzinfo is None:
                raise ValueError(
                    f"Period {self.label!r}: {name} must be timezone-aware datetime"
                )
            offset = dt.utcoffset()
            if offset is None or offset != timedelta(0):
                raise ValueError(
                    f"Period {self.label!r}: {name} must be UTC (utcoffset=0), got offset={offset}"
                )
        if self.end <= self.start:
            raise ValueError(
                f"Period {self.label!r}: end ({self.end}) must be > start ({self.start})"
            )


# ---------------------------------------------------------------------------
# Partition — 24m EpochWindow の 10 領域
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Partition:
    """24m epoch window の canonical partition (10 領域)."""

    epoch_window: EpochWindow
    stage_b: Period       # 62w
    stage_a: Period       # 8w
    embargo_after_a: Period  # 1w
    c_lite_1: Period      # 6w
    embargo_1: Period     # 1w
    c_lite_2: Period      # 6w
    embargo_2: Period     # 1w
    c_lite_3: Period      # 6w
    embargo_3: Period     # 1w
    stage_c: Period       # 12w

    @property
    def all_periods(self) -> list[Period]:
        """時系列順の全 10 領域 (overlap なし、 隙間なし)."""
        return [
            self.stage_b,
            self.stage_a,
            self.embargo_after_a,
            self.c_lite_1,
            self.embargo_1,
            self.c_lite_2,
            self.embargo_2,
            self.c_lite_3,
            self.embargo_3,
            self.stage_c,
        ]

    @property
    def c_lite_periods(self) -> tuple[Period, Period, Period]:
        """3 disjoint C-lite windows."""
        return (self.c_lite_1, self.c_lite_2, self.c_lite_3)


# ---------------------------------------------------------------------------
# PartitionGenerator
# ---------------------------------------------------------------------------


class PartitionGenerator:
    """EpochWindow から canonical Partition を生成.

    synthesis § 4.3 確定の 10 領域構造を deterministic に生成:
    [B 62w][A 8w][emb 1w][C-lite 6w][emb 1w][C-lite 6w][emb 1w][C-lite 6w][emb 1w][C 12w]
    合計 = 104w
    """

    STAGE_B_WEEKS: ClassVar[int] = 62
    STAGE_A_WEEKS: ClassVar[int] = 8
    EMBARGO_WEEKS: ClassVar[int] = 1
    C_LITE_WEEKS: ClassVar[int] = 6
    STAGE_C_WEEKS: ClassVar[int] = 12

    @classmethod
    def generate(cls, window: EpochWindow) -> Partition:
        """window.start を起点に時系列順で 10 領域を切り出す.

        Raises:
            PartitionMismatchError: window 長と 10 領域合計が不一致、
                または cursor != window.end (gap / overlap)
        """
        # 不変条件: 10 領域合計 == window 長 (timedelta 厳密一致)
        total_weeks = (
            cls.STAGE_B_WEEKS + cls.STAGE_A_WEEKS + cls.EMBARGO_WEEKS
            + cls.C_LITE_WEEKS + cls.EMBARGO_WEEKS
            + cls.C_LITE_WEEKS + cls.EMBARGO_WEEKS
            + cls.C_LITE_WEEKS + cls.EMBARGO_WEEKS
            + cls.STAGE_C_WEEKS
        )
        expected_span = timedelta(weeks=total_weeks)
        actual_span = window.end - window.start
        if actual_span != expected_span:
            raise PartitionMismatchError(
                f"window span {actual_span} != expected {expected_span} ({total_weeks}w)"
            )

        cursor = window.start

        def _slice(weeks: int, label: PeriodLabel) -> Period:
            nonlocal cursor
            end = cursor + timedelta(weeks=weeks)
            p = Period(start=cursor, end=end, label=label.value)
            cursor = end
            return p

        partition = Partition(
            epoch_window=window,
            stage_b=_slice(cls.STAGE_B_WEEKS, PeriodLabel.STAGE_B),
            stage_a=_slice(cls.STAGE_A_WEEKS, PeriodLabel.STAGE_A),
            embargo_after_a=_slice(cls.EMBARGO_WEEKS, PeriodLabel.EMBARGO_AFTER_A),
            c_lite_1=_slice(cls.C_LITE_WEEKS, PeriodLabel.STAGE_C_LITE_1),
            embargo_1=_slice(cls.EMBARGO_WEEKS, PeriodLabel.EMBARGO_AFTER_C_LITE_1),
            c_lite_2=_slice(cls.C_LITE_WEEKS, PeriodLabel.STAGE_C_LITE_2),
            embargo_2=_slice(cls.EMBARGO_WEEKS, PeriodLabel.EMBARGO_AFTER_C_LITE_2),
            c_lite_3=_slice(cls.C_LITE_WEEKS, PeriodLabel.STAGE_C_LITE_3),
            embargo_3=_slice(cls.EMBARGO_WEEKS, PeriodLabel.EMBARGO_AFTER_C_LITE_3),
            stage_c=_slice(cls.STAGE_C_WEEKS, PeriodLabel.STAGE_C),
        )
        if cursor != window.end:
            raise PartitionMismatchError(
                f"partition cursor {cursor} != window.end {window.end} (gap or overlap)"
            )
        return partition


# ---------------------------------------------------------------------------
# Fold — Stage B 1 fold (train, embargo, test)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Fold:
    """Stage B 1 fold の (train, embargo, test) 区間."""

    fold_index: int
    train: Period
    embargo: Period
    test: Period

    def __post_init__(self) -> None:
        if self.fold_index < 0:
            raise ValueError(f"fold_index must be >= 0: {self.fold_index}")
        # 連続性 (gap なし): train.end == embargo.start, embargo.end == test.start
        if self.train.end != self.embargo.start:
            raise ValueError(
                f"fold {self.fold_index}: train.end ({self.train.end}) "
                f"!= embargo.start ({self.embargo.start})"
            )
        if self.embargo.end != self.test.start:
            raise ValueError(
                f"fold {self.fold_index}: embargo.end ({self.embargo.end}) "
                f"!= test.start ({self.test.start})"
            )


# ---------------------------------------------------------------------------
# FoldGenerator
# ---------------------------------------------------------------------------


class FoldGenerator:
    """Stage B 62w から rolling-origin で 5 folds を生成.

    fold 構造: train 36w + embargo 1w + test 5w + step 5w → 5 folds
    fold k (k=0..4):
        train  = [k*5w, k*5w + 36w)
        embargo = [k*5w + 36w, k*5w + 37w)
        test   = [k*5w + 37w, k*5w + 42w)

    最終 fold (k=4) test.end = 4*5 + 42 = 62w → stage_b.end と一致。
    """

    TRAIN_WEEKS: ClassVar[int] = 36
    EMBARGO_WEEKS: ClassVar[int] = 1
    TEST_WEEKS: ClassVar[int] = 5
    STEP_WEEKS: ClassVar[int] = 5
    NUM_FOLDS: ClassVar[int] = 5

    @classmethod
    def generate(cls, stage_b: Period) -> tuple[Fold, ...]:
        """Stage B period から 5 folds を時系列順で生成.

        Raises:
            ValueError: stage_b.label が "stage_b" 以外
            FoldMismatchError: stage_b 長が期待値と不一致、
                または末端 fold test.end != stage_b.end
        """
        if stage_b.label != PeriodLabel.STAGE_B.value:
            raise ValueError(
                f"FoldGenerator expects {PeriodLabel.STAGE_B.value!r} period, "
                f"got {stage_b.label!r}"
            )
        # 不変条件: 5 fold 合計 = 62w (timedelta 厳密一致)
        last_fold_end_weeks = (cls.NUM_FOLDS - 1) * cls.STEP_WEEKS \
                            + cls.TRAIN_WEEKS + cls.EMBARGO_WEEKS + cls.TEST_WEEKS
        expected_b_span = timedelta(weeks=last_fold_end_weeks)
        actual_b_span = stage_b.end - stage_b.start
        if actual_b_span != expected_b_span:
            raise FoldMismatchError(
                f"stage_b span {actual_b_span} != expected {expected_b_span} "
                f"(5-fold structure spans {last_fold_end_weeks}w)"
            )

        folds: list[Fold] = []
        for k in range(cls.NUM_FOLDS):
            train_start = stage_b.start + timedelta(weeks=k * cls.STEP_WEEKS)
            train_end = train_start + timedelta(weeks=cls.TRAIN_WEEKS)
            embargo_end = train_end + timedelta(weeks=cls.EMBARGO_WEEKS)
            test_end = embargo_end + timedelta(weeks=cls.TEST_WEEKS)
            folds.append(
                Fold(
                    fold_index=k,
                    train=Period(
                        start=train_start, end=train_end, label=f"fold_{k}_train"
                    ),
                    embargo=Period(
                        start=train_end, end=embargo_end, label=f"fold_{k}_embargo"
                    ),
                    test=Period(
                        start=embargo_end, end=test_end, label=f"fold_{k}_test"
                    ),
                )
            )
        if folds[-1].test.end != stage_b.end:
            raise FoldMismatchError(
                f"last fold test.end {folds[-1].test.end} != stage_b.end {stage_b.end}"
            )
        return tuple(folds)
```

### ルックアヘッドバイアスチェック
- N/A (datetime 境界生成のみ、 primitive 変更ではない)

### C3 / C7 適用
- N/A (相関 / sample size claim を新規導入しない)

### パフォーマンスチェック
- N/A (10 領域 + 5 folds 生成は軽量、 timedelta 演算のみ)

### テスト計画 (施策 2 で詳述)

### リスク
- T059 未マージ時、 EpochWindow import 失敗 → T059 マージ後に T060 PR 作成
- 既存 walk_forward.py に touch しないため Phase 1 単体では runtime に影響なし

---

## 施策 2: `tests/alpha_factory/test_partition.py` 新規作成

### 変更箇所
- ファイル: `tests/alpha_factory/test_partition.py` (新規)

### テスト計画

振る舞いベース test 名:

#### Period
- `test_period_rejects_naive_datetime_for_start_or_end`
- `test_period_rejects_end_le_start`
- `test_period_accepts_utc_aware_datetime`
- `test_period_rejects_jst_aware_datetime` (Round 1 [Suggestion] 2: UTC 厳密性、 JST/+09:00 は拒否)
- `test_period_rejects_pacific_aware_datetime` (例: -08:00 等の他 timezone も拒否)
- `test_period_label_string_value_is_period_label_value`

#### PeriodLabel
- `test_period_label_values_are_lowercase_alphanumeric_underscore`
- `test_all_partition_labels_distinct`

#### Partition
- `test_all_periods_returns_ten_periods_in_chronological_order`
- `test_all_periods_have_no_gap_or_overlap`
- `test_c_lite_periods_returns_three_disjoint_windows`

#### PartitionGenerator
- `test_generate_24m_window_produces_canonical_10_region_partition`
- `test_generate_total_length_equals_window_span_104w`
- `test_generate_raises_partition_mismatch_when_window_too_short`
- `test_generate_raises_partition_mismatch_when_window_too_long`
- `test_generate_stage_b_is_first_62w_after_window_start`
- `test_generate_stage_a_follows_stage_b_with_no_gap`
- `test_generate_stage_c_is_final_12w_ending_at_window_end`
- `test_generate_three_c_lite_windows_separated_by_1w_embargo`

#### Fold
- `test_fold_rejects_negative_fold_index`
- `test_fold_rejects_train_end_not_equal_to_embargo_start`
- `test_fold_rejects_embargo_end_not_equal_to_test_start`

#### FoldGenerator
- `test_generate_produces_5_folds_for_62w_stage_b`
- `test_generate_raises_value_error_when_label_is_not_stage_b`
- `test_generate_raises_fold_mismatch_when_stage_b_too_short`
- `test_generate_raises_fold_mismatch_when_stage_b_too_long`
- `test_fold_train_length_is_36_weeks_for_each_fold`
- `test_fold_embargo_length_is_1_week_for_each_fold`
- `test_fold_test_length_is_5_weeks_for_each_fold`
- `test_fold_step_is_5_weeks_between_consecutive_folds`
- `test_first_fold_train_starts_at_stage_b_start`
- `test_last_fold_test_ends_at_stage_b_end`
- `test_consecutive_fold_test_periods_are_disjoint`

#### 統合 (Partition → Fold)
- `test_partition_generator_then_fold_generator_chain_produces_104w_with_5_folds`

### リスク
- (テストのみ、 リスク軽微)

---

## 実装モード

| 項目 | 内容 |
|------|------|
| 推奨モード | **standalone** (T058 / T059 同様、 単体実装可、 Phase 2 で 9 箇所同時更新を別 PR) |
| 判断根拠 | T060 PR は単体テストのみで既存 walk_forward / stage_gate / preflight 経路に touch しない |
| 競合リスク | T059 マージ済前提、 T058 マージ済前提 (運用上 T058→T059→T060 順マージ) |
| 想定実装時間 | 短 (2 施策、 半日程度) |

## 実装順序

T060 PR で 2 施策を 1 PR で着地。 Phase 2 (9 箇所同時更新) は T061-T064 評価層実装と同時に別 PR (別 TODO)。

---

## DoD (Definition of Done)

T060 PR 完了基準:

### コード DoD
- [ ] `src/alpha_factory/partition.py` 新規作成 (PeriodLabel + Period + Partition + PartitionGenerator + Fold + FoldGenerator + 例外)
- [ ] `tests/alpha_factory/test_partition.py` 新規作成 (上記 test 全 pass)
- [ ] `uv run pytest tests/alpha_factory/test_partition.py` 全 pass
- [ ] `uv run ruff check src/ tests/` clean
- [ ] `uv run mypy src/` clean
- [ ] `walk_forward.py` / `stage_gate.py` / `swim_lane.py` / `run_ga.py` / `default.yaml` / `config.py` / `docs/alpha_factory/stage-gates.md` を変更しない (Phase 1 スコープ厳守)

### Phase 2 (T061-T064 と同時、 別 PR) DoD (申し送り、 Round 1 [Critical] 反映で 2 ファイル追加)
- [ ] `walk_forward.py` の `make_wf_folds` / `compute_max_folds` / `wf_min_unique_dates` を全廃 or 新 FoldGenerator 委譲 thin wrapper 化
- [ ] `stage_gate.py:StageGateConfig` から `stage_b_window_months` / `wf_*_days` 削除、 新 Partition / Fold ベースに置換
- [ ] `stage_gate.py:evaluate_stage_b` の `bars_18m` 引数廃止、 新仕様に置換
- [ ] `swim_lane.py:465` の `compute_max_folds` 呼出を新 FoldGenerator に置換
- [ ] `run_ga.py:1260` の preflight `wf_min_unique_dates` を新仕様に置換
- [ ] `default.yaml: stage_gate.stage_b.{window_months, wf_train_days, wf_test_days, wf_step_days, wf_embargo_days, wf_min_folds_required, fold_trade_count_min}` を全廃、 新 (固定 5 folds) 反映
- [ ] `config.py:StageGateConfig` の Stage B 関連 field 再定義
- [ ] `docs/alpha_factory/stage-gates.md` の Stage B 仕様を新 Partition / Fold ベースに書き換え
- [ ] **`calibrate_state.py:74`** の `stage_b_window_months` 参照を新 Partition (Period 集合) ベースに置換 (Round 1 [Critical] 1)
- [ ] **`aux_preflight.py:52, 189`** の `stage_b_window_months` 参照と `wf_*` 経路を新 Partition / Fold ベースに置換 (Round 1 [Critical] 1)
- [ ] **`scripts/alpha_factory/inspect_stage_b_folds.py:83`** の `wf_*` / fold logic を新 FoldGenerator に置換 (Round 2 [Suggestion]: 運用スクリプト移行)
- [ ] **`tests/alpha_factory/test_config.py:333`** の `wf_*_days` / `stage_b_window_months` 関連 test を新仕様に更新 (Round 2 [Suggestion]: 既存 test 移行)

### Phase 1 (T060 PR) C2 parallel-path 確認 DoD (Round 1 [Suggestion] 1 反映)
- [ ] **旧経路 `walk_forward.py` に新定数 (`PartitionGenerator.STAGE_B_WEEKS` 等) を逆流させない** (Phase 2 まで完全分離)
- [ ] **新経路 `partition.py` を runtime に配線しない** (T060 PR で `run_ga.py` / `evaluate_stage_b` から import されないこと)
- [ ] grep 確認: `grep -rn "from src.alpha_factory.partition" scripts/ src/` の結果が `src/alpha_factory/partition.py` (自身) と新 test 以外で hit しないこと

---

## 関連 / 後段 TODO

- T058: Schema v2 contract (依存先、 設計 APPROVED)
- T059: EpochManager (依存先、 設計 APPROVED、 EpochWindow を提供)
- T061-T064: Stage 評価器 (本 TODO の Partition / Fold を消費する側、 Phase 2 で同時更新)
- T070: backtest engine の bar slice (Period → bar 範囲変換、 UTC 正規化)
