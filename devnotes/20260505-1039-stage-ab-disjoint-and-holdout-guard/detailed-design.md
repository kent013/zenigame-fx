# 詳細設計: Stage A/B fold disjoint 化 + Stage Partition fail-closed guard

## 使命・制約（絶対遵守）

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
- **バグ修正はテストファースト**: 再現最小テスト → FAIL 確認 → 修正 → PASS
- **全施策にテスト必須**（テストなしは実装完了としない）
- **テスト命名**: 振る舞いを説明する汎用的な名前（Run 名・日付・セッション固有の識別子 NG）
- **テスト配置**: 対象モジュールに対応するテストファイル
- **uv 必須**: `uv run pytest tests/alpha_factory/`
- **ruff / mypy 通過**: `uv run ruff check src/ tests/` / `uv run mypy src/`
- Python 3.13 + numpy + pandas 環境

## 概念設計リファレンス

[devnotes/20260505-1039-stage-ab-disjoint-and-holdout-guard/conceptual-design.md](./conceptual-design.md)（Codex APPROVED Round 4）

## C1 Design-first チェックリスト（実装着手前必須）

実装着手時に以下を順番に verify し、結果を `devnotes/20260505-1039-stage-ab-disjoint-and-holdout-guard/c1-checklist.md` に残す（監査可能性のため `tmp/` ではなく devnotes 配下に配置 / Round 1 [Suggestion] 反映）:

1. `docs/alpha_factory/stage-gates.md` を Read し、Stage A/B/C の bars 区間契約・WF fold 規範を確認
2. `docs/alpha_factory/runbook.md` を Read し、起動シーケンス・aux preflight との順序関係を確認
3. `git log --all -S "bars_stage_b" --oneline -- scripts/alpha_factory/run_ga.py` で bars_stage_b の意味変更履歴を辿る
4. `git log --all -S "bars_18m" --oneline -- src/alpha_factory/stage_gate.py` で bars_18m の出自を辿る
5. `git grep -n "bars_18m" -- 'src/' 'tests/' 'scripts/alpha_factory/'` で全 31 件の出現箇所を確認、本詳細設計の rename スコープ表と照合
6. `ls devnotes/ | grep -E "(stage_b|partition|holdout)"` で関連 devnotes を確認

## 施策一覧

| # | 施策名 | 主要変更ファイル | 優先度 |
|---|---|---|---|
| 1 | `_load_lane_bars` で Stage A/B disjoint 化 | `scripts/alpha_factory/run_ga.py` | High |
| 2 | `stage_partition_guard.py` 新規モジュール | `src/alpha_factory/stage_partition_guard.py` (新規) | High |
| 3 | 起動時 partition guard 呼び出し + Stage C fallback 廃止 | `scripts/alpha_factory/run_ga.py`, `src/alpha_factory/config.py` | High |
| 4 | `evaluate_stage_b` 引数名 `bars_18m → bars_stage_b` rename | `src/alpha_factory/stage_gate.py` ほか限定スコープ | Medium |
| 5 | summary.json `bars_stage_b_excludes_stage_a` / `stage_b_statistical_inconclusive` フラグ追加（archive 非保持を明文化） | `scripts/alpha_factory/run_ga.py` | High |
| 6 | archive parquet schema metadata に `stage_gate_version` / `bars_stage_b_excludes_stage_a` 追加（既存 metadata と merge） | `src/alpha_factory/archive.py` | High |
| 7 | `STAGE_GATE_VERSION` を `v4_stage_b_disjoint` に bump | `src/alpha_factory/stage_gate.py` | High |
| 8 | run report に Stage B excludes 注記 + inconclusive 表示 | `scripts/alpha_factory/generate_run_report.py` | Medium |
| 9 | bundle 構築時 structured log キー整備 | `scripts/alpha_factory/run_ga.py` | Low |

---

## 施策 1: `_load_lane_bars` で Stage A/B disjoint 化

### 変更箇所
- ファイル: [scripts/alpha_factory/run_ga.py:426-507](../../scripts/alpha_factory/run_ga.py#L426-L507) `_load_lane_bars`

### 波及変更
- `AGENTS.md`: なし（コマンドインターフェース不変）
- `.claude/skills/zenigame-fx-*/SKILL.md`: なし
- `config/alpha_factory/default.yaml`: なし
- `docs/alpha_factory/stage-gates.md`: 「bars_stage_b は Stage A 期間を除外する」契約を 1 段落追記（C1 確認時に既存記述があれば update、なければ追加）

### 現行コード
```python
bars_stage_a = (
    bars_stage_b[-stage_a_n_bars:]
    if stage_a_n_bars <= len(bars_stage_b)
    else list(bars_stage_b)
)
return LaneBarsBundle(
    meta=meta,
    bars_stage_a=bars_stage_a,
    bars_stage_b=bars_stage_b,
    bars_holdout=bars_holdout,
)
```

### 変更後コード
```python
# Stage B fold 評価から Stage A 期間を時系列上 disjoint にする (T-XXX)。
# bars_stage_b_full は DB クエリ結果 = [dataset.start, dataset.end) の全 bar。
# Stage A = bars_stage_b_full の末尾 stage_a_n_bars 本 (末尾固定、本 TODO 前提)。
# Stage B (fold + IS monitor) = bars_stage_b_full の残り = [dataset.start, end - stage_a_window)。
bars_stage_b_full = bars_stage_b
# Round 2 [Warning] 反映: stage_a_n_bars >= len(full) を 1 箇所で fail-closed
# (`>=` 判定で disjoint 後の bars_stage_b が空になるケースも同時に検出)。
if stage_a_n_bars >= len(bars_stage_b_full):
    raise RuntimeError(
        f"dataset too short for disjoint stage A/B: "
        f"stage_a_n_bars={stage_a_n_bars} >= "
        f"len(bars_stage_b_full)={len(bars_stage_b_full)} "
        f"(instrument={instrument}, dataset=[{dataset.start}, {dataset.end})). "
        f"Extend dataset or reduce stage_a_window_days."
    )
bars_stage_a = bars_stage_b_full[-stage_a_n_bars:]
bars_stage_b = bars_stage_b_full[:-stage_a_n_bars]

logger.info(
    "run_ga.lane_bars_loaded",
    instrument=instrument,
    stage_a_bar_first=bars_stage_a[0].bar_time.isoformat(),
    stage_a_bar_last=bars_stage_a[-1].bar_time.isoformat(),
    stage_a_count=len(bars_stage_a),
    stage_b_bar_first=bars_stage_b[0].bar_time.isoformat(),
    stage_b_bar_last=bars_stage_b[-1].bar_time.isoformat(),
    stage_b_count=len(bars_stage_b),
    holdout_bar_first=bars_holdout[0].bar_time.isoformat() if bars_holdout else None,
    holdout_bar_last=bars_holdout[-1].bar_time.isoformat() if bars_holdout else None,
    holdout_count=len(bars_holdout),
)

return LaneBarsBundle(
    meta=meta,
    bars_stage_a=bars_stage_a,
    bars_stage_b=bars_stage_b,
    bars_holdout=bars_holdout,
)
```

### ルックアヘッドバイアスチェック
- [x] 未来バー参照なし（bars_stage_b は時系列順スライス）
- [x] 当日確定値の先取りなし
- [x] rolling window 方向が過去方向（影響なし）
- [x] 正規化にローカル window or rolling 関数を使用（影響なし）
- [x] バケット / グループ平均が因果的（影響なし）
- [x] cumsum/accumulate が因果的方向（影響なし）

### パフォーマンスチェック
- bars_stage_b の slice は O(N) コピーが入るが、bundle 構築は run 起動時 1 回のみで影響軽微
- log 出力は info で 1 回のみ、hot path なし

### テスト計画
- 新規テスト: `test_load_lane_bars_disjoint_stage_a_b` — bars_stage_a と bars_stage_b の bar_time 集合 intersection が空であることを assert
- 新規テスト: `test_load_lane_bars_raises_when_dataset_smaller_or_equal_to_stage_a` — `stage_a_n_bars >= len(full)` で RuntimeError（境界条件 == も含む）
- 新規テスト: `test_load_lane_bars_bars_stage_b_not_empty_when_dataset_sufficient` — disjoint 後の bars_stage_b が空でない

### リスク
- 既存テストのうち `bars_stage_b` 全期間前提のものが壊れる可能性 → C1 チェックリスト 5 で grep して洗い出し
- `inspect_stage_b_folds.py` の `bars_18m = bundle.bars_stage_b` は意味が変わる（disjoint 短縮版を見ることになる）→ 期待動作なので問題なし、出力ログでその旨を示す

---

## 施策 2: `stage_partition_guard.py` 新規モジュール

### 変更箇所
- 新規ファイル: `src/alpha_factory/stage_partition_guard.py`

### 波及変更
- `AGENTS.md`: なし
- `docs/alpha_factory/stage-gates.md`: Stage Partition Integrity Guard セクションを 1 段落追加

### 新規モジュールコード骨子

```python
"""Stage Partition Integrity Guard (T-XXX)。

zenigame ``src/trading/alpha_factory/runner/_holdout.py`` 相当だが、
zenigame-fx では holdout 単独ではなく Stage A↔B↔Holdout 三者の partition
integrity を扱うため命名を ``stage_partition_guard`` に統一する。

仕様根拠:
- 概念設計: ``devnotes/20260505-1039-stage-ab-disjoint-and-holdout-guard/conceptual-design.md``
- 詳細設計: 同 dir / detailed-design.md
- 学術根拠: López de Prado (2018) Ch.7 (purged k-fold + embargo)
"""
from __future__ import annotations

from datetime import datetime, timedelta

from src.domain.price import PriceBar

__all__ = [
    "StagePartitionError",
    "StagePartitionInputError",
    "StagePartitionLeakError",
    "validate_stage_partition",
]


class StagePartitionError(RuntimeError):
    """Stage Partition Guard が検出した違反の共通基底クラス (Round 3 [Suggestion])."""


class StagePartitionInputError(StagePartitionError):
    """B-0 入力健全性違反 (non_empty / timezone / not_null / monotonic / unique)."""


class StagePartitionLeakError(StagePartitionError):
    """B-1 partition 整合性違反 (chronological order / timestamp disjoint)."""


def _validate_inputs(
    bars_stage_a: list[PriceBar],
    bars_stage_b: list[PriceBar],
    bars_holdout: list[PriceBar],
) -> None:
    """B-0 入力健全性検査 (StagePartitionInputError raise)。"""
    for label, bars in (
        ("stage_a", bars_stage_a),
        ("stage_b", bars_stage_b),
        ("holdout", bars_holdout),
    ):
        if not bars:
            raise StagePartitionInputError(
                f"B-0 violation: {label} is empty (3 stages all required)"
            )
        prev: datetime | None = None
        seen: set[datetime] = set()
        for i, b in enumerate(bars):
            t = b.bar_time
            # B-0 not_null 契約: bar_time が None であってはならない
            if t is None:
                raise StagePartitionInputError(
                    f"B-0 violation: {label}[{i}].bar_time is None"
                )
            if t.tzinfo is None or t.utcoffset() != timedelta(0):
                raise StagePartitionInputError(
                    f"B-0 violation: {label}[{i}].bar_time not UTC: {t}"
                )
            if prev is not None and t < prev:
                raise StagePartitionInputError(
                    f"B-0 violation: {label}[{i}].bar_time not monotonic: "
                    f"{prev} -> {t}"
                )
            if t in seen:
                raise StagePartitionInputError(
                    f"B-0 violation: {label}[{i}].bar_time duplicate: {t}"
                )
            seen.add(t)
            prev = t


def _validate_chronological_partition(
    bars_stage_a: list[PriceBar],
    bars_stage_b: list[PriceBar],
    bars_holdout: list[PriceBar],
) -> None:
    """B-1 境界条件 1-3 (chronological partition)。

    本 TODO は Stage A 末尾固定を前提に B が A より前であることを検証する。
    将来 Stage A 位置を確率化する別 TODO 着手時には本関数を撤去し、
    ``_validate_timestamp_disjoint`` のみで disjoint 検証する設計に切り替える
    (concept B-3)。
    """
    a_min = bars_stage_a[0].bar_time
    a_max = bars_stage_a[-1].bar_time
    b_max = bars_stage_b[-1].bar_time
    h_min = bars_holdout[0].bar_time
    # 1: max(B) < min(A)
    if not (b_max < a_min):
        raise StagePartitionLeakError(
            f"B-1 cond.1 violated: max(stage_b)={b_max} >= min(stage_a)={a_min}"
        )
    # 2: max(A) < min(holdout)
    if not (a_max < h_min):
        raise StagePartitionLeakError(
            f"B-1 cond.2 violated: max(stage_a)={a_max} >= min(holdout)={h_min}"
        )
    # 3: max(B) < min(holdout) (1+2 から導出可だが冗長 fail-fast)
    if not (b_max < h_min):
        raise StagePartitionLeakError(
            f"B-1 cond.3 violated: max(stage_b)={b_max} >= min(holdout)={h_min}"
        )


def _validate_timestamp_disjoint(
    bars_stage_a: list[PriceBar],
    bars_stage_b: list[PriceBar],
    bars_holdout: list[PriceBar],
) -> None:
    """B-1 集合条件 4-6 (exact timestamp contamination)。"""
    a_set = {b.bar_time for b in bars_stage_a}
    b_set = {b.bar_time for b in bars_stage_b}
    h_set = {b.bar_time for b in bars_holdout}
    pairs = (
        (4, "stage_a", a_set, "stage_b", b_set),
        (5, "stage_a", a_set, "holdout", h_set),
        (6, "stage_b", b_set, "holdout", h_set),
    )
    for cond_no, l1, s1, l2, s2 in pairs:
        overlap = s1 & s2
        if overlap:
            sample = sorted(overlap)[:3]
            raise StagePartitionLeakError(
                f"B-1 cond.{cond_no} violated: |{l1} ∩ {l2}|={len(overlap)} "
                f"sample={sample}"
            )


def validate_stage_partition(
    bars_stage_a: list[PriceBar],
    bars_stage_b: list[PriceBar],
    bars_holdout: list[PriceBar],
) -> None:
    """Stage A↔B↔Holdout の partition integrity を起動時に検証する fail-closed guard.

    順序:
        1. ``_validate_inputs``      (B-0 input healthcheck)
        2. ``_validate_chronological_partition`` (B-1 cond. 1-3)
        3. ``_validate_timestamp_disjoint``      (B-1 cond. 4-6)

    違反時は対応する例外型を raise し escape hatch なしで起動を停止する。
    """
    _validate_inputs(bars_stage_a, bars_stage_b, bars_holdout)
    _validate_chronological_partition(bars_stage_a, bars_stage_b, bars_holdout)
    _validate_timestamp_disjoint(bars_stage_a, bars_stage_b, bars_holdout)
```

### ルックアヘッドバイアスチェック
- N/A（partition 構造のみ検証、価格データ計算なし）

### パフォーマンスチェック
- O(N_a + N_b + N_h) で起動時 1 回のみ実行
- 集合構築のメモリは bar_time の hash table のみ → 6m データセットで Stage B ~80k 件 → ピーク数 MB 程度、24GB 制約内
- hot path に入らないので JIT / numpy 化は不要

### テスト計画

新規テストファイル: `tests/alpha_factory/test_stage_partition_guard.py`

正常系:
- `test_validate_stage_partition_disjoint_passes` — A/B/Holdout が正しく時系列順かつ disjoint なら raise しない

B-0 異常系（`StagePartitionInputError`）:
- `test_input_error_when_stage_a_empty`
- `test_input_error_when_stage_b_empty`
- `test_input_error_when_holdout_empty`
- `test_input_error_when_bar_time_not_utc` (JST tzinfo を持つ bar が紛れ込んだケース)
- `test_input_error_when_bar_time_not_monotonic`
- `test_input_error_when_bar_time_duplicate_in_stage`

B-1 境界条件異常系（`StagePartitionLeakError`、cond.1-3）:
- `test_leak_error_when_stage_b_after_stage_a` — cond.1 違反
- `test_leak_error_when_stage_a_overlaps_holdout_chronologically` — cond.2 違反
- `test_leak_error_when_stage_b_after_holdout_start` — cond.3 違反

B-1 集合条件異常系（`StagePartitionLeakError`、cond.4-6）:
- `test_leak_error_when_stage_a_and_b_share_timestamp` — cond.4 違反
- `test_leak_error_when_stage_a_and_holdout_share_timestamp` — cond.5 違反
- `test_leak_error_when_stage_b_and_holdout_share_timestamp` — cond.6 違反

例外階層テスト:
- `test_input_error_is_partition_error` — `StagePartitionInputError` が `StagePartitionError` のサブクラス
- `test_leak_error_is_partition_error` — `StagePartitionLeakError` が `StagePartitionError` のサブクラス

### リスク
- 既存テストの fixture が partition 不整合な bars を渡している場合、起動時に raise → 詳細設計実装時に grep で洗い出し、fixture を修正
- swap 後 bars_18m / bars_stage_b の意味変化により試験データの境界が新条件を満たさないケース → 施策 4 の rename と合わせて修正

---

## 施策 3: 起動時 partition guard 呼び出し + Stage C fallback 廃止

### Round 1 [Critical] 反映: Stage C fallback と guard の矛盾解消

現状 [scripts/alpha_factory/run_ga.py:475-495](../../scripts/alpha_factory/run_ga.py#L475-L495) には `allow_stage_c_fallback_slice=true` で `bars_holdout = bars_stage_b[-slice_n:]`（Stage B 末尾を holdout として再利用）する fallback 経路がある。これは partition guard の disjoint 検証で**必ず違反する**ため、両者は両立しない。

**判断**: `allow_stage_c_fallback_slice` は test fixture 用と現コメントに明記されており、本番経路では使われない。本 TODO で**本番経路から完全に廃止**（config 設定値・コード分岐の削除）し、test 用に必要な経路は別ヘルパーで明示分離する:

- `src/alpha_factory/config.py` の `StageWindowsConfig.allow_stage_c_fallback_slice` フィールドを**廃止**
- `_load_lane_bars` 内の fallback 分岐を削除（holdout が DB に存在しなければ RuntimeError）
- 既存テストで fallback を使っていたものは `tests/_helpers/fake_lane_bundle.py`（仮）等の test-only ヘルパーで `LaneBarsBundle` を直接構築する経路に切り替える

### 変更箇所
- ファイル: [scripts/alpha_factory/run_ga.py](../../scripts/alpha_factory/run_ga.py) main 起動シーケンス + `_load_lane_bars` 内の fallback 分岐
- ファイル: [src/alpha_factory/config.py](../../src/alpha_factory/config.py) `StageWindowsConfig.allow_stage_c_fallback_slice` 削除
- ファイル: 既存 fallback 利用テスト全件（grep で洗い出し）

### 波及変更
- `docs/alpha_factory/runbook.md`: 起動シーケンス図に「Stage Partition Guard」ステップ追記、fallback 廃止を runbook に明記
- `config/alpha_factory/default.yaml`: `allow_stage_c_fallback_slice` キーがあれば削除

### `_load_lane_bars` fallback 廃止コード

```python
# 旧: allow_stage_c_fallback_slice 経路は廃止 (T-XXX, partition guard 矛盾)
if not bars_holdout:
    raise RuntimeError(
        f"no holdout bars for {instrument} in "
        f"[{dataset.end}, {holdout_end}); "
        f"holdout fetch failed and fallback slice is no longer supported "
        f"(would violate stage partition disjoint contract). "
        f"Tests requiring synthetic holdout must use test-only helpers."
    )
```

### main() 起動シーケンス追加

```python
from src.alpha_factory.stage_partition_guard import validate_stage_partition

# ... main() 内 _load_lane_bars 呼び出し後、aux_preflight より前 ...

bundle = _load_lane_bars(instrument, cfg.dataset, cfg.stage_windows)

# Stage Partition Integrity Guard (T-XXX): fail-closed escape hatch なし
# 違反時は StagePartitionInputError / StagePartitionLeakError で起動停止
# aux_preflight より前に置く理由: bars 区間が壊れていれば aux 評価は意味がない
validate_stage_partition(
    bundle.bars_stage_a,
    bundle.bars_stage_b,
    bundle.bars_holdout,
)
logger.info(
    "run_ga.stage_partition_guard.passed",
    instrument=instrument,
    stage_gate_version=STAGE_GATE_VERSION,
)
```

### テスト計画

- 新規テスト: `test_load_lane_bars_no_fallback_when_holdout_missing` — DB に holdout が無いとき RuntimeError raise（fallback 廃止確認）
- 新規テスト: `test_run_ga_main_invokes_partition_guard` — 起動シーケンスで guard が呼ばれ、違反時に raise される統合テスト（subprocess or main() 直接呼び出し）
- 既存 fallback 依存テストは test-only ヘルパー経由に書き換え or 廃止

### リスク
- 既存テストで fallback を使っているものが多数ある場合、テスト書き換えコストが膨らむ → 実装時に grep で件数確認（`git grep -n "allow_stage_c_fallback_slice" -- 'tests/'`）
- test-only ヘルパーが必要な範囲は実装時に確定（最小化を心がける）

---

## 施策 4: `evaluate_stage_b` 引数名 `bars_18m → bars_stage_b` rename

### 変更箇所（スコープ限定: `evaluate_stage_b` 周辺の semantic rename のみ）

- [src/alpha_factory/stage_gate.py](../../src/alpha_factory/stage_gate.py): `evaluate_stage_b(bars_18m, ...)` シグネチャ + 関数本体内の参照（lines 910, 933, 960, 973, 979, 1210）
- [scripts/alpha_factory/run_ga.py:1404](../../scripts/alpha_factory/run_ga.py#L1404): `evaluate_stage_b` 呼び出し側 keyword 引数
- [scripts/alpha_factory/inspect_stage_b_folds.py](../../scripts/alpha_factory/inspect_stage_b_folds.py): lines 64, 82, 204, 215（同関数を直接呼び出しているスクリプトのため対象）
- [src/alpha_factory/canonical_adapter.py:162](../../src/alpha_factory/canonical_adapter.py#L162): docstring コメントの "bars_18m" 言及を "bars_stage_b" に更新（コードシグネチャ変更なし、コメントのみ）
- [src/alpha_factory/swim_lane.py](../../src/alpha_factory/swim_lane.py): lines 150, 157, 483, 628, 637, 812, 824 — `LaneContext.bars_18m` field 名 → `bars_stage_b`、type alias と全参照を rename
- 関連テスト: [tests/alpha_factory/test_aux_loader_align.py](../../tests/alpha_factory/test_aux_loader_align.py), [tests/alpha_factory/test_swim_lane.py](../../tests/alpha_factory/test_swim_lane.py)

### スコープ外（別 TODO）

- 上記スコープ外で `bars_18m` を文字列マッチで持つコード（archive メモ等）の global cleanup
- `wf_train_days=60` などの "18m" 設計コメントの修正（"18m" は config の `window_months: 18` 由来であり、本 rename 対象外）

### 波及変更
- `AGENTS.md`: なし（CLI 不変）
- `docs/alpha_factory/stage-gates.md`: API 例の引数名を更新

### 現行コード（抜粋）
```python
# src/alpha_factory/stage_gate.py:910-933
def evaluate_stage_b(
    genome: Genome,
    bars_18m: list[PriceBar],
    meta: InstrumentMeta,
    backtest_config: BacktestConfig,
    primitive_evaluator: PrimitiveEvaluator,
    stage_config: StageGateConfig,
    *,
    aux_bundle: object | None = None,
) -> StageResult:
    ...
    folds = make_wf_folds(
        bars_18m,
        ...
    )
```

### 変更後コード（抜粋）
```python
def evaluate_stage_b(
    genome: Genome,
    bars_stage_b: list[PriceBar],
    meta: InstrumentMeta,
    backtest_config: BacktestConfig,
    primitive_evaluator: PrimitiveEvaluator,
    stage_config: StageGateConfig,
    *,
    aux_bundle: object | None = None,
) -> StageResult:
    """Stage B — Walk-Forward OOS gate + IS monitor.

    Note: ``bars_stage_b`` は Stage A 期間を除外した bars (T-XXX 以降)。
    bars_stage_b は Stage A と時系列上 disjoint であることを ``stage_partition_guard``
    が起動時に保証する。"""
    ...
    folds = make_wf_folds(
        bars_stage_b,
        ...
    )
```

### ルックアヘッドバイアスチェック
- N/A（rename のみ、ロジック不変）

### パフォーマンスチェック
- N/A（rename のみ）

### テスト計画
- 既存 `tests/alpha_factory/test_stage_gate.py` の `evaluate_stage_b` 呼び出し test 群が新名で通ることを確認
- swim_lane / aux_loader_align の関連テストが新 field 名で通ることを確認
- 新規テストは施策 1〜3 / 5〜7 のものを追加し、施策 4 単体での新規テストはなし

### リスク
- `LaneContext.bars_18m` field rename で外部参照（subscription / serialize 経路）に漏れ → C1 チェックリスト 5 で `git grep -n "bars_18m"` 全 31 件を二重チェック
- `inspect_stage_b_folds.py` がデバッグスクリプトのため修正漏れが致命的でない可能性 → 実装時に少なくとも import エラーが出ないことを確認

---

## 施策 5: summary.json フラグ追加

### 変更箇所
- [scripts/alpha_factory/run_ga.py:910-918](../../scripts/alpha_factory/run_ga.py#L910-L918) `summary["dataset"]` 構築箇所
- summary["per_generation"] とは別に Stage B 評価サマリーブロックがある場合はそこに `stage_b_statistical_inconclusive` を追加（実装時に summary 構造確認）

### 波及変更
- `docs/alpha_factory/run-summary.md`（存在すれば）: 新フラグの仕様追加
- `scripts/alpha_factory/generate_run_report.py`: 施策 8 でフラグ参照を追加

### Round 1 [Warning] 反映: `bars` 値の据え置き + `bars_dataset_total` 新設

`dataset["bars"]` の意味変更は consumer 後方互換リスクがあるため、**`bars` キーは disjoint 化前と同じ意味（= dataset 全期間 = bars_stage_b_full の長さ = bars_stage_a + bars_stage_b の長さ）に据え置く**。新規に `bars_dataset_total` を併設して、新規 consumer はそちらを参照する規約にする。

### Round 1 [Critical] 反映: `stage_b_statistical_inconclusive` を archive 非保持と明文化

`stage_b_statistical_inconclusive` は **summary 専用の事前計算 convenience フラグ**であり、archive parquet には保持しない。理由:

- archive consumer は既存の `n_fold_effective` 列から `n_fold_effective is None or n_fold_effective < 3` で同等判定可能
- 4 段接続（GENOMES_SCHEMA → row template → collect → flush）を増やすと将来の archive schema 変更コストが上がる
- summary の方が version up しやすく consumer 影響を限定できる

archive consumer 向けの inconclusive 判定契約は `docs/alpha_factory/archive-schema.md` に明記する（後述）。

### Round 1 [Warning] / Round 2 [Warning] 反映: `n_fold_effective` の None / NaN / np.integer 対応

`stage_b_statistical_inconclusive` の判定ロジック（`numbers.Integral` で `np.int64` も含む整数を許容、`bool` は除外）:

```python
import math
from numbers import Integral

def is_stage_b_inconclusive(n_fold_effective: object) -> bool:
    """n_fold_effective < 3 を inconclusive と判定。

    - None / 非整数 / NaN / 負値 / bool: 保守的に True (inconclusive)。
    - numpy.integer (np.int64 等) は Integral として正常に扱う。
    - bool は Integral サブクラスだが意図しないため明示除外。
    """
    if n_fold_effective is None:
        return True
    if isinstance(n_fold_effective, bool):
        return True
    if isinstance(n_fold_effective, float) and math.isnan(n_fold_effective):
        return True
    if not isinstance(n_fold_effective, Integral):
        return True
    return int(n_fold_effective) < 3
```

本 helper は `_load_lane_bars` 等とは別の utility モジュール（例: `src/alpha_factory/stage_b_inconclusive.py` または既存 `src/alpha_factory/stage_gate.py` の private helper）に配置し、summary 生成側 / report 側 / archive consumer 向け参照例として一箇所で管理する。

### 現行コード
```python
"dataset": {
    "instrument": cfg.dataset.instrument,
    "start": cfg.dataset.start.isoformat(),
    "end": cfg.dataset.end.isoformat(),
    "bars": len(bundle.bars_stage_b),
    "bars_stage_a": len(bundle.bars_stage_a),
    "bars_stage_b": len(bundle.bars_stage_b),
    "bars_holdout": len(bundle.bars_holdout),
},
```

### 変更後コード
```python
"dataset": {
    "instrument": cfg.dataset.instrument,
    "start": cfg.dataset.start.isoformat(),
    "end": cfg.dataset.end.isoformat(),
    # `bars`: disjoint 化前と同じ意味 (dataset 全期間) を据え置き、後方互換維持。
    # disjoint 化前は len(bars_stage_b)=全期間。disjoint 化後は両者の合計が全期間に等しい。
    "bars": len(bundle.bars_stage_a) + len(bundle.bars_stage_b),
    "bars_dataset_total": len(bundle.bars_stage_a) + len(bundle.bars_stage_b),  # 明示的な新 key
    "bars_stage_a": len(bundle.bars_stage_a),
    "bars_stage_b": len(bundle.bars_stage_b),
    "bars_holdout": len(bundle.bars_holdout),
    "bars_stage_b_excludes_stage_a": True,  # T-XXX: disjoint 化済み
    "stage_a_bar_first": bundle.bars_stage_a[0].bar_time.isoformat(),
    "stage_a_bar_last": bundle.bars_stage_a[-1].bar_time.isoformat(),
    "stage_b_bar_first": bundle.bars_stage_b[0].bar_time.isoformat(),
    "stage_b_bar_last": bundle.bars_stage_b[-1].bar_time.isoformat(),
    "holdout_bar_first": bundle.bars_holdout[0].bar_time.isoformat(),
    "holdout_bar_last": bundle.bars_holdout[-1].bar_time.isoformat(),
},
```

`stage_b_statistical_inconclusive` フラグ: summary.json の固定 path **`summary["stage_b"]["statistical_inconclusive"]`** に追加（archive parquet には**書き込まない、列を増やさない**）。同階層 `summary["stage_b"]` には併せて best 個体ぶんの `n_fold_effective` も持つ。判定ロジックは上記 `is_stage_b_inconclusive`（None / 非 int は True）。施策 8 の run report は同 key path を参照し、無ければ archive row の `n_fold_effective` から `is_stage_b_inconclusive()` で再導出する（Round 2 [Warning] 反映）。

### テスト計画
- 新規テスト: `test_run_summary_includes_partition_metadata` — summary.json に `bars_stage_b_excludes_stage_a` / `bars_dataset_total` / `stage_a_bar_first` / `stage_b_bar_last` 等が含まれる
- 新規テスト: `test_summary_bars_key_unchanged_after_disjoint` — `bars` キーは依然として全期間 bar 数（後方互換確認）
- 新規テスト: `test_stage_b_statistical_inconclusive_when_n_fold_below_3` — `n_fold_effective=2` で flag が True
- 新規テスト: `test_stage_b_statistical_inconclusive_when_n_fold_at_threshold` — `n_fold_effective=3` で flag が False
- 新規テスト: `test_stage_b_statistical_inconclusive_when_n_fold_none` — `n_fold_effective=None` で flag が True（保守的）
- 新規テスト: `test_stage_b_inconclusive_not_in_archive_columns` — archive parquet に `stage_b_statistical_inconclusive` 列が**ない**ことを assert（責務分離の負テスト）

### リスク
- `bars` キーを据え置いたため、disjoint 化前後で値は同じ（全期間） → 後方互換維持。 summary を読んでいる外部 monitoring 等への影響なし

---

## 施策 6: archive parquet metadata に `stage_gate_version` / `bars_stage_b_excludes_stage_a` 追加

### 変更箇所
- [src/alpha_factory/archive.py:698-699](../../src/alpha_factory/archive.py#L698-L699) `flush()` 内の `pa.Table.from_pylist` → `pq.write_table` 経路

### 波及変更
- `docs/alpha_factory/archive-schema.md`（存在すれば）: parquet schema metadata の仕様追記
- 既存 archive 読み込み consumer: 後方互換性維持（metadata が無い v1 archive は raw 値を None として扱える経路が必要、もしくは v2 archive のみ対応）

### 現行コード
```python
table = pa.Table.from_pylist(clean_rows, schema=GENOMES_SCHEMA)
pq.write_table(table, path)
return path
```

### 変更後コード（案、Round 1 / Round 3 反映）

```python
# Archive metadata に Stage Partition 文脈情報を埋め込む (T-XXX)。
# 循環 import 回避のため STAGE_GATE_VERSION は archive.py 直接 import せず、
# flush() の caller (run_ga.py 経由) から引数として渡す or
# 軽量定数 module ``src/alpha_factory/stage_gate_version.py`` に切り出す。
# Round 3 [Suggestion] 反映: archive.py が stage_gate.py を import すると
# stage_gate.py 側からも archive 関連を import している既存経路と循環する可能性。
# 詳細は実装時に `python -c "import src.alpha_factory.archive"` で確認し、
# 循環するなら定数 module 切り出し or DI 化に切り替える。

new_metadata = {
    b"stage_gate_version": _stage_gate_version().encode("utf-8"),
    b"bars_stage_b_excludes_stage_a": b"true",
    b"genome_entry_schema_version": str(GENOME_ENTRY_SCHEMA_VERSION).encode("utf-8"),
}
existing_metadata = dict(GENOMES_SCHEMA.metadata or {})
existing_metadata.update(new_metadata)
schema_with_metadata = GENOMES_SCHEMA.with_metadata(existing_metadata)

table = pa.Table.from_pylist(clean_rows, schema=schema_with_metadata)
# 念のため Table 側にも同じ metadata を再適用 (pa.from_pylist が schema metadata を
# 保持しないバージョンへの保険)。
table = table.replace_schema_metadata(existing_metadata)
pq.write_table(table, path)
return path
```

`_stage_gate_version()` は archive.py 内でローカル import（lazy）するか、constant module 経由にする。`STAGE_GATE_VERSION` は施策 7 で `v4_stage_b_disjoint` に bump 済み。`pa.Schema.with_metadata` は immutable な新 schema を返す。

### テスト計画
- 新規テスト: `test_archive_parquet_metadata_contains_stage_gate_version` — flush 後の parquet を pq.read_metadata で読み、schema metadata に `stage_gate_version=v4_stage_b_disjoint` が含まれる
- 新規テスト: `test_archive_parquet_metadata_contains_bars_stage_b_excludes_stage_a` — schema metadata に `bars_stage_b_excludes_stage_a=true` が含まれる
- 新規テスト: `test_archive_parquet_metadata_preserves_existing_keys` — 既存 metadata に他 key があれば消失しないこと

### リスク
- `pa.Table.from_pylist(rows, schema=...)` は schema metadata を保持しないバージョンが pyarrow にあり、保険として `replace_schema_metadata` を再適用
- archive 読み込み（fsp_updater 等）が schema metadata を参照していない場合、無視される（後方互換 OK）

---

## 施策 7: `STAGE_GATE_VERSION` を `v4_stage_b_disjoint` に bump

### 変更箇所
- [src/alpha_factory/stage_gate.py:344](../../src/alpha_factory/stage_gate.py#L344)

### 波及変更
- `reports/calibrate-gate/history.jsonl`: 既存 record は不変、新 run 以降 `stage_gate_version=v4_stage_b_disjoint` で記録 → 過去 history（v3）が新条件下で誤適用されない（cross-run guard が AND で stage_gate_version 一致を要求するため）
- `tests/alpha_factory/test_calibrate_state.py` で stage_gate_version リテラル値を検査しているテストがあれば更新

### 現行コード
```python
STAGE_GATE_VERSION: Final[str] = "v3_stage_b_fold_min_trade_count"
```

### 変更後コード
```python
# T-XXX: Stage B の bars 区間が Stage A と disjoint 化したため version bump。
# 過去 v3 history の threshold が新条件下で誤適用されないよう
# cross-run guard に明示伝搬する。
STAGE_GATE_VERSION: Final[str] = "v4_stage_b_disjoint"
```

### テスト計画
- 新規テスト: `test_stage_gate_version_is_v4_disjoint` — 文字列値の固定（version drift 検知）
- 既存 calibrate_state テストでリテラルマッチがあれば調整

### リスク
- v3 を仮定する production system（外部 monitoring 等）への影響 → 本リポジトリ内のみで完結することを C1 で確認

---

## 施策 8: run report に Stage B excludes 注記 + inconclusive 表示

### 変更箇所
- [scripts/alpha_factory/generate_run_report.py:345](../../scripts/alpha_factory/generate_run_report.py#L345) 周辺の dataset セクション + Stage B verdict セクション

### 波及変更
- 既存 run report テスト

### 変更内容（疑似コード、Round 2 [Warning] 反映: report は archive row から再導出）

```python
from src.alpha_factory.stage_b_inconclusive import is_stage_b_inconclusive

# dataset セクション
if summary["dataset"].get("bars_stage_b_excludes_stage_a", False):
    out.append(
        "  - Stage B excludes Stage A window "
        f"(stage_b: {summary['dataset']['stage_b_bar_first']} → "
        f"{summary['dataset']['stage_b_bar_last']}, "
        f"stage_a: {summary['dataset']['stage_a_bar_first']} → "
        f"{summary['dataset']['stage_a_bar_last']})"
    )

# best 個体の Stage B verdict
# 1) summary に flag があればそれを使う (新 run 経路)
# 2) 無ければ archive row の n_fold_effective から再導出 (旧 run / archive 単体経路)
flag_in_summary = summary.get("stage_b", {}).get("statistical_inconclusive")
if flag_in_summary is None:
    flag_in_summary = is_stage_b_inconclusive(best_row.get("n_fold_effective"))
if flag_in_summary:
    out.append("  - **statistical inconclusive** (n_fold_effective < 3)")
```

### テスト計画
- 既存 generate_run_report テストに対応注記が出力されることを assert する case を追加

### リスク
- 過去 run の summary に新 key が無い → `dict.get(..., default)` で吸収

---

## 施策 9: bundle 構築時 structured log キー整備

施策 1 でログ追加済み。本施策は施策 1 のログ key に対する unit test 追加のみ。

### テスト計画
- 新規テスト: `test_lane_bars_loaded_log_emits_disjoint_keys` — caplog で `stage_a_bar_first`, `stage_b_bar_last`, `holdout_bar_first` 等のキーが含まれる

---

## 実装モード

| 項目 | 内容 |
|---|---|
| 推奨モード | **incremental** |
| 判断根拠 | 施策 1〜9 は順序依存があるが、各施策単独でテスト可能。施策 1+2+3 を 1 commit、施策 4 を 1 commit、施策 5+6+7 を 1 commit、施策 8+9 を 1 commit のように段階的に進める。standalone（一括 PR）でも commit 履歴で読みづらくなるだけで結果は同等 |
| 競合リスク | 同時並行する別 TODO（特に Stage A 確率化、cross-pair 周り）と `LaneContext.bars_18m` field 名衝突 → 本 TODO は先行マージを推奨 |
| 想定実装時間 | 中（4-6 時間: コード変更 2-3 時間、テスト 1-2 時間、C1 チェックリスト 1 時間） |

## 実装順序（incremental 内訳、Round 2 [Warning] 反映: version bump 単独先行禁止）

**重要原則（Round 2 [Warning] 反映）**: `STAGE_GATE_VERSION` bump（施策 7）は disjoint 化 + guard 呼び出し（施策 1〜3）と**同一 commit、または disjoint 化 / guard 呼び出しが merge 済み main に入った後に commit** する。中間状態で v3 実態 + v4 metadata になることを防ぐ。

1. **Step 1**: 施策 2 (stage_partition_guard モジュール新規) + テスト追加 — 単独で完結、main 動作影響なし
2. **Step 2**: 施策 1 (`_load_lane_bars` disjoint 化) + 施策 3 (起動時 guard 呼び出し + Stage C fallback 廃止) + 施策 7 (STAGE_GATE_VERSION bump) + テスト追加 — **同一 commit**（v4 名 = disjoint 実態の同時導入）
3. **Step 3**: 施策 4 (`bars_18m → bars_stage_b` rename) — Step 2 後に既存テスト全体を update
4. **Step 4**: 施策 5 (summary.json フラグ + `is_stage_b_inconclusive` helper) + 施策 9 (log キー整備テスト)
5. **Step 5**: 施策 6 (archive parquet metadata) + テスト
6. **Step 6**: 施策 8 (run report 注記 + `is_stage_b_inconclusive` 経由の再導出) + テスト
7. **Step 7**: ruff / mypy / pytest 全件 pass を最終確認

各 Step ごとに `uv run pytest tests/alpha_factory/ -x` を回し、緑で次に進む。Step 3 のテスト更新範囲が広いため、commit を細かく分けることで debug を容易にする。

## 一次確認結果（C1, 実装時記録欄）

実装時に C1 チェックリスト 1〜6 を実行した結果を `devnotes/20260505-1039-stage-ab-disjoint-and-holdout-guard/c1-checklist.md` に記録する。本設計書本文には結果サマリーのみを後追記する:

- [ ] チェック 1: docs/alpha_factory/stage-gates.md の Stage A/B/C 契約 — 結果: ___
- [ ] チェック 2: docs/alpha_factory/runbook.md の起動シーケンス — 結果: ___
- [ ] チェック 3: git log -S "bars_stage_b" — 結果: ___
- [ ] チェック 4: git log -S "bars_18m" — 結果: ___
- [ ] チェック 5: git grep -n "bars_18m" — 結果: ___ 件
- [ ] チェック 6: ls devnotes/ 関連検索 — 結果: ___
- [ ] チェック 7（追加、Round 2 [Suggestion] 反映で grep 範囲を repo 全体に拡大）: `git grep -n "allow_stage_c_fallback_slice" -- .` — 結果: ___ 件（fallback 廃止に伴う `tests/` / `config/` / `docs/` / `.claude/skills/` / `devnotes/` 全箇所の修正対象）

これらが上記設計の前提を覆す場合、実装着手前に詳細設計を再評価する。
