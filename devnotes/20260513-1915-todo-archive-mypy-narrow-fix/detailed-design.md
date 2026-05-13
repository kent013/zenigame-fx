# archive.py:335 mypy fix 詳細設計

## 実装方針

`assert` または明示的 `if x is None` 後 narrow:

```python
def _compute_persistence_score_shadow(
    positive_fold_ratio: float | None,
    fold_sign_ratio: float | None,
) -> float | None:
    if positive_fold_ratio is None and fold_sign_ratio is None:
        return None
    if positive_fold_ratio is None:
        assert fold_sign_ratio is not None  # type narrowing
        return max(0.0, min(1.0, float(fold_sign_ratio)))
    if fold_sign_ratio is None:
        return max(0.0, min(1.0, float(positive_fold_ratio)))
    composite = 0.7 * float(positive_fold_ratio) + 0.3 * float(fold_sign_ratio)
    return max(0.0, min(1.0, composite))
```

## 受入基準

- [ ] `uv run mypy src/alpha_factory/archive.py` clean
- [ ] 既存 `test_archive.py` 全 pass (= 動作不変)
- [ ] ruff clean

## ロールバック条件

- assert 追加で test 失敗
- 動作変更検出

## コミット計画

- 1 コミット: `fix(archive): mypy narrowing assert 追加 (PR2 由来 1 件解消)`
