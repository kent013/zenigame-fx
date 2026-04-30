# 概念設計: T060 — Partition + fold generator

## 背景・課題

T058 (Schema v2 contract) と T059 (EpochManager) で `dataset_epoch_id` の schema 受け皿と値生成は確立。 T060 は **EpochWindow (24m=104w) を canonical な partition と Stage B fold に分割するロジック** を実装する。

synthesis § 4.3-4.4 確定値:

```
Partition 時系列順 (24m=104w):
[B 62w] → [A 8w] → [emb 1w] → [C-lite 6w] → [emb 1w] → [C-lite 6w] → [emb 1w] → [C-lite 6w] → [emb 1w] → [C 12w]
合計 = 62 + 8 + 1 + 6 + 1 + 6 + 1 + 6 + 1 + 12 = 104w ✓

Stage B fold (rolling-origin、 B 62w 内):
- train 36w + embargo 1w + test 5w + step 5w → 5 folds
- fold 1: train [0-36w] / emb [36-37w] / test [37-42w]
- fold 2: train [5-41w] / emb [41-42w] / test [42-47w]
- fold 3: train [10-46w] / emb [46-47w] / test [47-52w]
- fold 4: train [15-51w] / emb [51-52w] / test [52-57w]
- fold 5: train [20-56w] / emb [56-57w] / test [57-62w]
```

**Stage A の時間軸位置に注意**: Stage A は時間軸では Stage B より**後** (recent proxy)、 cascade 順 (A→B→C-lite→C) は維持。 これは synthesis § 5.2 で「個体 genome のみ stage 横断、 評価値は stage ごとに独立」 と明記済み。

## 前提検証 (C4) — current HEAD `main@ea56484` 基準

| 前提 | verified | 出典 |
|---|---|---|
| 24m partition (B 62w + A 8w + emb 1w + C-lite 6w×3 + emb 1w + C 12w) = 104w | ✓ | synthesis § 4.3 |
| Stage B fold = train 36w + emb 1w + test 5w + step 5w → 5 folds | ✓ | synthesis § 4.4 |
| Stage A は時間軸で B より後 (recent proxy) | ✓ | synthesis § 5.2 |
| 5 fold pooled が主判定、 fold fail-fast 補助 | ✓ | synthesis § 4.4 |
| EpochWindow (start, end) は T059 で deterministic 生成 | ✓ | T059 詳細設計 APPROVED |
| 既存 `src/alpha_factory/walk_forward.py:make_wf_folds` は **observed-day index ベースの WF helper、 Stage B 18m 契約 (`stage_b_window_months=18`) と preflight (`compute_max_folds` / `wf_min_unique_dates`) で使用中** | ✓ | `stage_gate.py:134, 562` + `swim_lane.py:465` + `run_ga.py:1260` 確認 (Round 1 [Warning] 1) |

## 改善アイデア

### 設計方針

1. **Partition dataclass**: 10 領域 (B / A / emb / C-lite × 3 / emb × 3 / C) を frozen dataclass で表現
2. **PartitionGenerator**: EpochWindow から canonical Partition を生成
3. **Fold dataclass**: Stage B 1 fold の (train, embargo, test) 区間を表現
4. **FoldGenerator**: B 領域から rolling-origin で 5 folds を生成
5. **境界の inclusive/exclusive 規約**: `[start, end)` 半開区間 (synthesis 内の慣例維持)
6. **bar 単位の boundary 計算**: M1 24/7 fill 前提で `start + N weeks` を bar count に変換可能 (engine 側で消費)

### Partition dataclass

```python
class PeriodLabel(StrEnum):
    """Period 命名 SSOT (Round 1 [Suggestion] 1 反映: string literal 依存回避)."""
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
    # Fold 用 (FoldGenerator が生成)
    FOLD_TRAIN = "fold_train"
    FOLD_EMBARGO = "fold_embargo"
    FOLD_TEST = "fold_test"


@dataclass(frozen=True)
class Period:
    """時系列上の半開区間 [start, end). UTC-aware datetime 限定."""
    start: datetime
    end: datetime
    label: str  # PeriodLabel の value (fold_* は fold_index suffix が付く: "fold_0_train" 等)

    def __post_init__(self) -> None:
        # Round 1 [Warning] 2 反映: 厳格な前提検証
        if self.start.tzinfo is None or self.end.tzinfo is None:
            raise ValueError(f"Period {self.label!r}: start/end must be UTC-aware datetime")
        if self.end <= self.start:
            raise ValueError(f"Period {self.label!r}: end ({self.end}) must be > start ({self.start})")


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
            self.stage_b, self.stage_a, self.embargo_after_a,
            self.c_lite_1, self.embargo_1,
            self.c_lite_2, self.embargo_2,
            self.c_lite_3, self.embargo_3,
            self.stage_c,
        ]

    @property
    def c_lite_periods(self) -> tuple[Period, Period, Period]:
        """3 disjoint C-lite windows."""
        return (self.c_lite_1, self.c_lite_2, self.c_lite_3)
```

### PartitionGenerator

```python
class PartitionGenerator:
    """EpochWindow から canonical Partition を生成.

    synthesis § 4.3 確定の 10 領域構造を deterministic に生成:
    [B 62w][A 8w][emb 1w][C-lite 6w][emb 1w][C-lite 6w][emb 1w][C-lite 6w][emb 1w][C 12w]
    """

    STAGE_B_WEEKS: ClassVar[int] = 62
    STAGE_A_WEEKS: ClassVar[int] = 8
    EMBARGO_WEEKS: ClassVar[int] = 1
    C_LITE_WEEKS: ClassVar[int] = 6
    STAGE_C_WEEKS: ClassVar[int] = 12

    @classmethod
    def generate(cls, window: EpochWindow) -> Partition:
        """window.start を起点に時系列順で 10 領域を切り出す.

        Round 1 [Warning] 2 反映: 厳格な timedelta 一致検証 (floor division 不使用)。
        """
        # 不変条件チェック (timedelta 厳密一致)
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
        def slice_(weeks: int, label: PeriodLabel) -> Period:
            nonlocal cursor
            end = cursor + timedelta(weeks=weeks)
            p = Period(start=cursor, end=end, label=label.value)
            cursor = end
            return p

        partition = Partition(
            epoch_window=window,
            stage_b=slice_(cls.STAGE_B_WEEKS, PeriodLabel.STAGE_B),
            stage_a=slice_(cls.STAGE_A_WEEKS, PeriodLabel.STAGE_A),
            embargo_after_a=slice_(cls.EMBARGO_WEEKS, PeriodLabel.EMBARGO_AFTER_A),
            c_lite_1=slice_(cls.C_LITE_WEEKS, PeriodLabel.STAGE_C_LITE_1),
            embargo_1=slice_(cls.EMBARGO_WEEKS, PeriodLabel.EMBARGO_AFTER_C_LITE_1),
            c_lite_2=slice_(cls.C_LITE_WEEKS, PeriodLabel.STAGE_C_LITE_2),
            embargo_2=slice_(cls.EMBARGO_WEEKS, PeriodLabel.EMBARGO_AFTER_C_LITE_2),
            c_lite_3=slice_(cls.C_LITE_WEEKS, PeriodLabel.STAGE_C_LITE_3),
            embargo_3=slice_(cls.EMBARGO_WEEKS, PeriodLabel.EMBARGO_AFTER_C_LITE_3),
            stage_c=slice_(cls.STAGE_C_WEEKS, PeriodLabel.STAGE_C),
        )
        # cursor が window.end と一致することを検証 (Round 2 [Suggestion] 1: assert → 例外化)
        if cursor != window.end:
            raise PartitionMismatchError(
                f"partition cursor {cursor} != window.end {window.end} (gap or overlap detected)"
            )
        return partition
```

### Fold dataclass

```python
@dataclass(frozen=True)
class Fold:
    """Stage B 1 fold の (train, embargo, test) 区間."""
    fold_index: int   # 0-origin
    train: Period
    embargo: Period
    test: Period

    def __post_init__(self) -> None:
        # 連続性 (gap なし)
        if self.train.end != self.embargo.start:
            raise ValueError(f"fold {self.fold_index}: train.end != embargo.start")
        if self.embargo.end != self.test.start:
            raise ValueError(f"fold {self.fold_index}: embargo.end != test.start")
```

### FoldGenerator

```python
class FoldGenerator:
    """Stage B (B 62w) から rolling-origin で 5 folds を生成.

    fold 構造: train 36w + embargo 1w + test 5w + step 5w → 5 folds
    fold k (k=0..4):
        train  = [k*5w, k*5w + 36w)
        embargo = [k*5w + 36w, k*5w + 37w)
        test   = [k*5w + 37w, k*5w + 42w)

    最終 fold (k=4) end = 4*5 + 42 = 62w → B 62w 末端と一致 (確認済)。
    """

    TRAIN_WEEKS: ClassVar[int] = 36
    EMBARGO_WEEKS: ClassVar[int] = 1
    TEST_WEEKS: ClassVar[int] = 5
    STEP_WEEKS: ClassVar[int] = 5
    NUM_FOLDS: ClassVar[int] = 5

    @classmethod
    def generate(cls, stage_b: Period) -> tuple[Fold, ...]:
        """Stage B period から 5 folds を時系列順で生成.

        Round 1 [Suggestion] 1: stage_b.label を PeriodLabel.STAGE_B value で照合
        Round 1 [Warning] 2: timedelta 厳密一致で検証
        """
        if stage_b.label != PeriodLabel.STAGE_B.value:
            raise ValueError(
                f"FoldGenerator expects {PeriodLabel.STAGE_B.value!r} period, got {stage_b.label!r}"
            )
        # 不変条件: B 62w で 5 folds が末端まで届く (timedelta 厳密一致)
        last_fold_end_weeks = (cls.NUM_FOLDS - 1) * cls.STEP_WEEKS \
                            + cls.TRAIN_WEEKS + cls.EMBARGO_WEEKS + cls.TEST_WEEKS
        expected_b_span = timedelta(weeks=last_fold_end_weeks)
        actual_b_span = stage_b.end - stage_b.start
        if actual_b_span != expected_b_span:
            raise FoldMismatchError(
                f"stage_b span {actual_b_span} != expected {expected_b_span} "
                f"(5-fold structure with {last_fold_end_weeks}w)"
            )

        folds: list[Fold] = []
        for k in range(cls.NUM_FOLDS):
            train_start = stage_b.start + timedelta(weeks=k * cls.STEP_WEEKS)
            train_end = train_start + timedelta(weeks=cls.TRAIN_WEEKS)
            embargo_end = train_end + timedelta(weeks=cls.EMBARGO_WEEKS)
            test_end = embargo_end + timedelta(weeks=cls.TEST_WEEKS)
            folds.append(Fold(
                fold_index=k,
                train=Period(start=train_start, end=train_end, label=f"fold_{k}_train"),
                embargo=Period(start=train_end, end=embargo_end, label=f"fold_{k}_embargo"),
                test=Period(start=embargo_end, end=test_end, label=f"fold_{k}_test"),
            ))
        # 最終 fold test.end が stage_b.end と一致 (Round 2 [Suggestion] 1: assert → 例外化)
        if folds[-1].test.end != stage_b.end:
            raise FoldMismatchError(
                f"last fold test.end {folds[-1].test.end} != stage_b.end {stage_b.end}"
            )
        return tuple(folds)
```

### 例外

```python
class PartitionMismatchError(ValueError):
    """24m EpochWindow と 10 領域合計の長さ不一致."""

class FoldMismatchError(ValueError):
    """B 62w と 5 folds の長さ不一致."""
```

### 半開区間 [start, end) 規約

すべての Period は **[start, end) 半開区間**:
- `period.start` 含む
- `period.end` 含まない
- 連続する Period の境界は `prev.end == next.start` で gap なし
- bar 単位での消費は engine 側で `start <= bar.timestamp < end` で判定

### bar 数換算 (engine 連携、 本 TODO 範囲外、 Round 1 [Suggestion] 3 反映)

bar count は **engine 側 (T070 backtest engine 拡張) の slice 結果に従う**。 T060 は datetime 境界のみ責任を持ち、 bar count を invariant に入れない (将来の欠損補修や feed 異常 / DST 等への対応を T060 が抱え込まない)。

参考値 (T070 申し送り、 不変条件ではない):
- M1 24/7 fill 想定で `1 week ≈ 10080 bars`、 ただし feed 実態に従う
- engine 側 slice は **比較を必ず UTC 正規化済 timestamp で実施**: `start <= bar.timestamp_utc < end` (Round 1 [Suggestion] 2 反映)

T060 テストでは datetime 境界のみ検証、 bar count assertion は入れない。

## 期待効果

### live_criteria 達成への構造的貢献

- **Partition 確定で全 stage 評価期間が canonical 化**: T061-T064 (Stage 評価器) が Period を消費して deterministic に動作
- **fold 構造の確定**: Stage B 5 fold pooled が synthesis § 4.4 通り deterministic に生成、 fold-median worst gap 計算の前提が満たされる
- **embargo 1w で leakage 防止**: stage 間および fold 内で 1w gap、 train→test の look-ahead 防止 (synthesis § 4.4)
- **Stage A を時間軸末尾近くに置くこと**で recent proxy として機能 (synthesis § 5.2)

### 副次効果

- **Partition は EpochWindow から deterministic に生成**: 同 EpochWindow → 同 Partition、 後段 audit / replay に有利

## 実装方針 (概要)

### コンポーネント変更 (Phase 1: T060 PR)

| ファイル | 変更内容 |
|---|---|
| `src/alpha_factory/partition.py` | **新規作成**。 `Period` + `Partition` + `PartitionGenerator` + `Fold` + `FoldGenerator` + `PartitionMismatchError` / `FoldMismatchError` |
| `tests/alpha_factory/test_partition.py` | **新規**。 partition 10 領域生成 / fold 5 生成 / 連続性 / 不変条件違反検出 |

**Phase 1 (T060 PR) スコープは上記 2 施策のみ**。 既存 `src/alpha_factory/walk_forward.py:make_wf_folds` (observed-day index ベース、 Stage B 18m 契約で使用中) との置換・整合は **Phase 2 (T061-T064 評価層実装と同時)** で実施。 T060 PR 単独では既存 walk_forward に touch しない。

### Phase 2 (別 TODO、 T061-T064 と同時) 申し送り (Round 1 [Critical] 1 反映: 拡張)

T060 完了後、 旧 observed-day index ベース fold 経路を**全面廃止 or 再定義**する必要がある。 単に `make_wf_folds` を置換するだけでは旧 preflight 契約が残り、 underfilled 判定や `wf_min_folds_required` が旧契約のまま走り**誤 reject の温床**になる。

**Phase 2 で同時更新が必要な箇所**:

| ファイル / 箇所 | 変更内容 |
|---|---|
| `src/alpha_factory/walk_forward.py` | `make_wf_folds` / `compute_max_folds` / `wf_min_unique_dates` を全廃 or 新 FoldGenerator に委譲する thin wrapper に再定義 |
| `src/alpha_factory/stage_gate.py` (`StageGateConfig` L133, `evaluate_stage_b` L560-L600) | `stage_b_window_months` / `wf_*_days` を削除、 新 Partition / Fold ベースに置換、 旧 `bars_18m` 引数廃止 |
| `src/alpha_factory/swim_lane.py:465` | `compute_max_folds` 呼出箇所を新 FoldGenerator に置換 |
| `scripts/alpha_factory/run_ga.py:1260` | preflight の `wf_min_unique_dates` 経路を新 FoldGenerator + 新 preflight 仕様に置換 |
| `config/alpha_factory/default.yaml` | `stage_gate.stage_b.{window_months, wf_train_days, wf_test_days, wf_step_days, wf_embargo_days, wf_min_folds_required, fold_trade_count_min}` を全廃、 新仕様 (固定 5 folds) を反映 |
| `src/alpha_factory/config.py` | `StageGateConfig` の Stage B 関連 field を新仕様に再定義 |
| `docs/alpha_factory/stage-gates.md` | Stage B 仕様を新 Partition / Fold ベースに書き換え |

これらを同時更新しないと「FoldGenerator は新仕様で動くが preflight は旧 18m 契約で reject」 という不整合が発生する。

- run_ga.py で EpochManager → PartitionGenerator → FoldGenerator のチェーン構築
- backtest engine (T070) で Period を bar slice に変換

## C3 / C7 適用 (Round 2 [Suggestion] 2 反映)

- **N/A**: 本設計は 24m partition + 5 folds の deterministic 境界生成のみで、 相関 / 因果 / sample size の statistical claim を新規導入していない。 collider bias / sample size discipline は本 TODO の不変条件チェック対象外、 後段 T061-T064 (評価器) で別途適用。

## 制約・前提

- **24m epoch window 専用**: 6m / 35m 等への拡張は本 TODO 範囲外 (synthesis § 4.1 で 24m primary 確定)
- **partition 構造は固定**: 10 領域長の synthesis 確定値は class const、 yaml override 不要
- **Period は datetime ベース**: bar 数換算は engine 側 (本 TODO は datetime のみ)
- **半開区間 [start, end) 規約**: 全 Period 共通
- **embargo は 1w 固定**: synthesis 確定、 別値は別 TODO

## スコープ外

- T058: schema 受け皿 (依存先)
- T059: EpochWindow 生成 (依存先)
- T061-T064: Stage 評価器 (本 TODO の Partition / Fold を消費する側)
- T070: backtest engine の bar slice (Period → bar 範囲変換)
- 既存 `walk_forward.py:make_wf_folds` の置換 (Phase 2 で T061-T064 と同時)
- yaml override (partition 長を runtime で変えるユースケースは想定外)

## Round 1 → Round 2 の改訂点

| Round 1 [Critical/Warning/Suggestion] | 修正対応 |
|---|---|
| [C1] Phase 2 申し送りが `make_wf_folds` 置換だけでは不足 | Phase 2 で同時更新が必要な 7 箇所 (`walk_forward.py` / `stage_gate.py` / `swim_lane.py` / `run_ga.py` / `default.yaml` / `config.py` / `docs/alpha_factory/stage-gates.md`) を表で明示 |
| [W1] C4 前提誤記 (walk_forward.py を「6m 用」 と書いた) | 「observed-day index ベースの WF helper、 Stage B 18m 契約と preflight で使用中」 に修正 |
| [W2] floor division 依存で壊れた境界を見逃す可能性 | `timedelta(weeks=N)` で厳密一致検証、 `Period.__post_init__` で UTC-aware / end > start を assert、 `cursor == window.end` assert 追加、 fold 末端 assert 追加 |
| [S1] Period.label string literal 依存 | `PeriodLabel` StrEnum を導入、 `FoldGenerator` も `PeriodLabel.STAGE_B.value` で照合 |
| [S2] T070 handoff に UTC 正規化 1 行 | bar slice 節に「比較は UTC 正規化済 timestamp で」 追記 |
| [S3] bar 数換算 invariant 化を回避 | bar count は engine 側 slice 結果に従う、 T060 テストは datetime 境界のみ |

## 学術引用 / 先行知見

- **Tashman (2000): "Out-of-sample tests of forecasting accuracy"**: rolling-origin の理論基盤
- **Bailey et al. (2014): CSCV (Combinatorially Symmetric Cross-Validation)**: fold 集約の理論的根拠
- synthesis § 4.3-4.4: 24m partition + 5 folds 確定値
- 既存 `walk_forward.py:make_wf_folds`: 旧 fold ロジック (置換予定)
