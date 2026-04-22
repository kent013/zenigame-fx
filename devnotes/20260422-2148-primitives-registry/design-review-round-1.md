VERDICT: NEEDS_REVISION
REASONS:
- `required_data` 契約に自己矛盾があります。規約は `cross_pair.<pair>` ですが、実装・テストは `"cross_pair."` を `True` 扱いしており、無効キーを通してしまいます。
- docs 更新案が現実装と不整合です。T010 骨格は `registry` 空 + `ensure_registered()` no-op なのに、「全32プリミティブを管理」と書くと事実とずれます。
- `mypy/ruff/pytest clean` 前提に対して、提示テストコードの `Mapping` / `Sequence` が未使用で `ruff` (`F401`) リスクがあります。
- `DslStrategy Protocol` 互換は文章説明のみで、主要リスクに対する契約テストが不足しています（差し替え時のシグネチャ/ import 回帰を検知できない）。
- `slot_from_category()` が未知カテゴリを暗黙に `"directional"` へ落とすため、型境界外入力をサイレント受理します。fail-fast 方針に反します。

REVISION_ITEMS (NEEDS_REVISION の場合のみ):
- [R1] `is_valid_required_data()` を `cross_pair.<non-empty>` のみ許可に修正し、`"cross_pair."` は `False` に変更する（対応テストも更新）。
- [R2] `docs/alpha_factory/primitives.md` の記述を骨格段階に合わせる（「将来32個を管理予定、現時点は骨格のみ」など）。
- [R3] `tests/alpha_factory/test_primitives_registry.py` の未使用 import を削除し、`ruff check` 通過前提を担保する。
- [R4] `DslStrategy` に `RegistryEvaluator` を注入して実行する最小契約テストを追加する。
- [R5] `slot_from_category()` に未知値 `ValueError` を追加し、型境界外入力を早期に検知する。

NOTES:
- `_base` / `_registry` / `evaluator` の分割は循環 import 回避の観点で妥当です。
- `_dummy_registry` / GA / Protocol 既存資産に触れない方針自体は適切です。