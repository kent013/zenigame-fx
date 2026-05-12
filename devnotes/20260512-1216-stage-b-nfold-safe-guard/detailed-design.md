# 詳細設計: Stage B `n_fold_effective` safe floor guard

作成: 2026-05-12 12:16 JST
概念設計: [`conceptual-design.md`](./conceptual-design.md)

## 変更対象ファイル

### 1) `src/alpha_factory/stage_gate.py`

#### 1-A) `evaluate_stage_b()` 内 reason 判定への guard 追加

参考行: [stage_gate.py:1196-1232](../../src/alpha_factory/stage_gate.py#L1196-L1232)

**差分**:

```diff
     # 集計と判定
     n_fold_effective = n_fold - n_fold_unavailable
     median_oos: float | None = None
     positive_ratio: float | None = None
     positive_ratio_effective: float | None = None
     # effective fold (unavailable=False のもの) のみを抜き出した OOS Sharpe 列
     effective_oos: list[float] = [
         s for i, s in enumerate(oos_sharpes_imputed)
         if not fold_was_unavailable[i]
     ]
     if n_fold == 0:
         reasons.append("no_folds")
     elif n_fold == 1:
         reasons.append("insufficient_folds")
         median_oos = float(oos_sharpes_imputed[0])
         positive_ratio = 1.0 if oos_sharpes_imputed[0] > 0 else 0.0
         if effective_oos:
             positive_ratio_effective = (
                 sum(1 for s in effective_oos if s > 0) / len(effective_oos)
             )
     else:
         median_oos = float(_stats.median(oos_sharpes_imputed))
         positive_ratio = sum(1 for s in oos_sharpes_imputed if s > 0) / n_fold
         if effective_oos:
             positive_ratio_effective = (
                 sum(1 for s in effective_oos if s > 0) / len(effective_oos)
             )
         if median_oos < stage_config.stage_b_median_oos_sharpe_min:
             reasons.append("median_oos_sharpe<min")
         if positive_ratio < stage_config.stage_b_positive_fold_min:
             reasons.append("positive_fold_ratio<min")

+    # cycle 22 (Run 60 artifact 防止): 統計安全水域 (wf_min_safe_folds) 未満の
+    # n_fold_effective で Stage B 通過させない。`wf_min_folds_required` (worker 短絡判定)
+    # と独立の statistical safety floor。 stage_gate.py L414-417 の意図を個体評価層
+    # まで貫徹する。
+    if n_fold_effective < stage_config.wf_min_safe_folds:
+        reasons.append("n_fold_below_safe_floor")
+
     # 全 fold metric_unavailable のときは別 reason で監査性を上げる
     if n_fold > 0 and n_fold_unavailable == n_fold:
         reasons.append("all_folds_unavailable")
```

**配置理由**:
- `n_fold_effective` 計算 (L1197) の後、 各種 median/positive 判定 (L1216-1226) の後、 `all_folds_unavailable` 監査前 (L1228-1230)
- `n_fold == 0` (`no_folds`) や `n_fold == 1` (`insufficient_folds`) でも本 guard が併発で記録される (n_fold_effective=0 or ≤1 のため)。 reasons が複数並ぶこと自体は既存仕様で許容 (passed = `len(reasons)==0`)。
- `all_folds_unavailable` (n_fold>0 かつ全 unavailable) は別軸の監査 reason で本 guard と直交。

### 2) `src/alpha_factory/stage_gate.py` (test 追加用には不要、 既存配列ベースで伝搬)

#### 2-A) `StageBResult.reasons` の archive 伝搬確認

`StageBResult` dataclass の `reasons` フィールド経由で archive 書き出しまで伝搬する想定。 archive admit 経路の確認:

- [`src/alpha_factory/loop_closure.py`](../../src/alpha_factory/loop_closure.py) で `stage_b_result.reasons` → `stage_b_failure_reason` 列に書かれる経路を確認
- 文字列 reason 1 個 (`n_fold_below_safe_floor`) を追加するのみ。 schema 変更なし。 **禁止事項 8 抵触なし**

実装時に文字列定数を enum / Literal にしているか確認し、 enum なら追加要 (詳細は実装側で対応)。

## テスト計画

### 新規テスト: `tests/alpha_factory/test_stage_gate_n_fold_safe_floor.py`

```python
"""Stage B `n_fold_effective` safe floor guard tests.

cycle 22 (Run 60 artifact 防止): `n_fold_effective < wf_min_safe_folds` の hard guard 動作を検証する。
"""

import pytest
from src.alpha_factory.stage_gate import evaluate_stage_b, StageGateConfig, StageBResult
# ↑ 実 import パスはコード側に合わせる

# fixture: minimal な evaluate_stage_b 呼び出しに必要な scaffold は既存 conftest を参考に


def test_stage_b_fails_when_n_fold_effective_below_safe_floor(...):
    """n_fold_effective=4 (< wf_min_safe_folds=5) のとき Stage B failed で reason に記録される."""
    # Arrange: 4 fold 分のメトリックを与え、 wf_min_safe_folds=5
    # Act: evaluate_stage_b(...)
    # Assert:
    #   - result.passed is False
    #   - "n_fold_below_safe_floor" in result.reasons


def test_stage_b_passes_when_n_fold_effective_at_safe_floor(...):
    """n_fold_effective=5 == wf_min_safe_folds で他 metric 健全なら通過する."""
    # Arrange: 5 fold 健全、 median_oos / positive_ratio 充足
    # Act + Assert: result.passed is True; "n_fold_below_safe_floor" not in result.reasons


def test_safe_floor_reason_records_alongside_insufficient_folds(...):
    """n_fold==1 のときは既存 insufficient_folds と safe floor の両方記録 (passed=False)."""
    # Arrange: n_fold=1
    # Act: evaluate_stage_b
    # Assert: "insufficient_folds" in reasons AND "n_fold_below_safe_floor" in reasons


def test_safe_floor_reason_records_alongside_no_folds(...):
    """n_fold==0 のときは既存 no_folds と safe floor の両方記録 (passed=False)."""


@pytest.mark.parametrize("safe_floor", [2, 5, 8])
def test_safe_floor_threshold_respects_config(safe_floor: int, ...):
    """`wf_min_safe_folds` の値に従って guard 閾値が動的に変わる."""
```

### 回帰テスト

- 既存 `tests/alpha_factory/test_stage_gate_*` 系全件 → CI で通過確認
- 既存テストのうち n_fold_effective を 5 未満で「passed=True」 を前提にしているテストがあれば、 archive artifact だったケースなので test 側を訂正 (必要時のみ、 数件想定)

## ロールバック / safety

- 単一行追加のため revert は trivial
- archive parquet の `stage_b_failure_reason` に新文字列 `n_fold_below_safe_floor` が混入する。 後段 reporting / analytics で reason 集計しているコードがあれば、 未知 reason として skip される実装になっているか確認 (詳細は実装時)

## 実装手順

1. **branch**: `feat/stage-b-nfold-safe-floor` (worktree 推奨)
2. patch 1 行を [stage_gate.py:1228](../../src/alpha_factory/stage_gate.py#L1228) 直前に挿入
3. test 追加 (上記計画通り)
4. `uv run pytest tests/alpha_factory/test_stage_gate_n_fold_safe_floor.py -q` で新 test pass
5. `uv run pytest tests/alpha_factory -q` で既存 test 全 pass (壊れたら artifact ケースか確認)
6. archive 経路の reason 伝搬を 1 回 minimal RUN (gen=1, pop=8 など) で目視確認 → parquet に `stage_b_failure_reason="n_fold_below_safe_floor"` が出ること
7. commit / PR
8. zenigame-fx-codex-review (`scripts/codex exec`) で 1 round レビュー
9. main マージ → 次 Run (Run 76) で artifact 個体が落ちるか観測

## 実装複雑度評価

- 実コード変更: 4 行 (コメント含む)
- 新規テスト: ~80-120 行
- 既存 test 訂正: 0-数件想定
- 工数: 半日 (実装 + test + Codex review)

## 残課題 / 別途検討

- **archive 後段 reporting**: 過去 18 RUN を本 guard でフィルタした場合の best 個体一覧を再計算するか? (本 TODO の範囲外、 別途 analyze-run skill 経由で可能)
- **lane preflight 強化**: `wf_min_folds_required` (=2) を `wf_min_safe_folds` (=5) に揃える案は別 TODO 候補 (より aggressive、 lane 全 skip の副作用大きい)。 本 TODO では個体粒度 guard のみ。
