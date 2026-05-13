# T092 fold guard fixture 修正 詳細設計

## 実装方針

### Option B (推奨): fixture-only override

各テスト fixture で `StageGateConfig(wf_min_safe_folds=2)` を明示指定。 production yaml の default 5 は維持。

修正対象:
- `tests/alpha_factory/test_t058_integration.py::test_end_to_end_writes_v2_summary_json`
- `tests/scripts/test_run_ga_parallel.py` の全 14 件

実装:
- 既存 fixture (= `_make_*_config()` 等) で `StageGateConfig(wf_min_safe_folds=2)` 引数追加
- production 影響なし (= fixture-only)

### Option A (alternative): dataset 期間拡張

`tests/scripts/test_run_ga_parallel.py` の dataset を 6 日 → 7 日に拡張。
ただし他テスト連動の可能性あり、 grep 確認必要。

## 受入基準

- [ ] `tests/alpha_factory/test_t058_integration.py` 全 pass (= 1 件 fix)
- [ ] `tests/scripts/test_run_ga_parallel.py` 全 pass (= 14 件 fix)
- [ ] `tests/` 全 pass、 `--deselect` 不要化
- [ ] production yaml の `wf_min_safe_folds=5` 維持
- [ ] ruff / mypy clean

## ロールバック条件

- production code 変更検出 (= fixture only 契約違反)
- 他テスト fixture が間接影響を受けて失敗

## コミット計画

- 1 コミット: `fix(tests): T092 fold guard fixture を新 guard 閾値に合致 (15 件まとめ修正)`
- 影響範囲:
  - `tests/alpha_factory/test_t058_integration.py` (= fixture 修正)
  - `tests/scripts/test_run_ga_parallel.py` (= fixture 修正)
