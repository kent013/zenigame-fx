# archive.py:335 mypy narrowing fix (PR2 由来)

## 背景

`src/alpha_factory/archive.py:335` の `_compute_persistence_score_shadow` で:

```python
if positive_fold_ratio is None and fold_sign_ratio is None:
    return None
if positive_fold_ratio is None:
    return max(0.0, min(1.0, float(fold_sign_ratio)))  # <-- mypy error: fold_sign_ratio is float | None
```

`fold_sign_ratio is None` の and 条件後、 mypy が `float | None` を `float` に narrow できない。 main 上で 1 件失敗。 PR3 で line shift しただけで内容は PR2 由来。

## 目的

mypy clean 化 (= alpha_factory module の 1 件 mypy error 解消)。

## 期待効果

- mypy strict pass (= `uv run mypy src/alpha_factory/` clean)
- CI/lint 健全性向上

## スコープ

- `_compute_persistence_score_shadow` 関数のみ修正
- 動作不変 (= 同じロジック、 narrowing assertion 追加のみ)

## 非目的

- 他 mypy エラーの解消 (= 別 TODO)
- 関数ロジック変更

## リスク

- ほぼなし (= type-only fix、 1 行)
