# T092 fold guard fixture 修正 (= test_t058_integration + test_run_ga_parallel 14 件 まとめ修正)

## 背景

T092 Stage B fold guard が `compute_max_folds=4 < wf_min_safe_folds=5` で fail-closed する設計。 既存 fixture (= `n_unique_dates_b=6`、 `wf_train=2d` / `wf_test=1d` / `wf_step=1d`) では新 guard を通過できず以下 15 件のテストが main 上で失敗:

- `tests/alpha_factory/test_t058_integration.py::test_end_to_end_writes_v2_summary_json` (1 件)
- `tests/scripts/test_run_ga_parallel.py::*` (14 件)

## 目的

fixture 側を新 guard 閾値に合致するよう拡張 (= `n_unique_dates_b ≥ 7` または `wf_min_safe_folds` を fixture-only で 2-3 に lower) で 15 件まとめ修正。 production 動作は変更しない (= fixture only)。

## 期待効果

- pytest 全件 pass (= --deselect 不要化)
- CI/test 健全性向上

## スコープ

- fixture 側のみ修正 (= production code touch なし)
- 2 option を検討:
  - Option A: `n_unique_dates_b` を 7 以上に拡張 (= dataset 期間を 6 日 → 7 日以上に)
  - Option B: fixture only で `wf_min_safe_folds=2 or 3` を pass し、 デフォルト 5 は維持

## 非目的

- T092 guard ロジックそのものの変更 (= guard は正しい動作、 fixture が古いだけ)
- 他テストの fixture 更新

## リスク

- Option A で dataset 期間延長すると別 fixture も影響受ける可能性 → grep で連動箇所確認
- Option B で fixture-only override が漏れて production 影響する → 必ず fixture scope に限定

## 参考

- `devnotes/20260513-1402-handoff-pr1-pr2-postdebate/handoff.md` § 既存問題
- `devnotes/20260512-1216-stage-b-nfold-safe-guard/` (T092 設計)
