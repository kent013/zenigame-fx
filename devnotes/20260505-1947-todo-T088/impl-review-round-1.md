前提: 提供された差分抜粋・設計抜粋・テストサマリのみを根拠にレビューしました（実ファイル本文は未参照）。

**ファイル別判定**

[`src/alpha_factory/primitives/_indicators.py`](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/primitives/_indicators.py): `CHANGES_REQUESTED`  
- [Critical] `_wilder_smooth` の early return 条件が `if not np.isfinite(seed): return out` になっており、設計要件の「seed=NaN のとき early return」より広すぎます。`seed=±inf` で旧実装と出力が変わるため、「numerically identical」契約を破る可能性があります。ここは `np.isnan(seed)` に限定すべきです。  
- [Warning] `rolling_min` 本体が提示抜粋では省略されているため、`>=` comparator・head/tail/size の対称実装を行単位で確証できません。  
- [Suggestion] `_wilder_smooth_recurrence_jit` は `v == v` 判定で `np.isnan(v)` と等価（float前提）なので問題ありませんが、意図を1行コメントで明示すると保守性が上がります。  

[`tests/alpha_factory/primitives/test_indicators.py`](/Users/ishitoya/repository/zenigame-fx/tests/alpha_factory/primitives/test_indicators.py): `概ね適合`  
- [Warning] 要件が「数値同一性」なら、`seed=±inf` 入力での parity ケースが未記載です（今回の Critical を再発防止できない）。  
- [Suggestion] `_wilder_smooth` parity に「先頭窓が inf を含む」ケースを1本追加してください。  

**レビュー観点への回答**

1. 設計一致性: ほぼ一致。ただし `_wilder_smooth` early return 条件が設計（NaN限定）から逸脱。  
2. 正確性: `rolling_max` の head/tail/size は提示コード上で off-by-one/wrap-around 問題は見当たりません（`n=1` も成立）。  
3. パフォーマンス: `@numba.njit(cache=True, fastmath=False)` と内側ループの NumPy 関数排除は満たしています。  
4. 一貫性: 命名規約は一致。  
5. テスト網羅: 提示サマリ上は設計要求に整合。ただし inf 系ケースが不足。  
6. ruff/mypy: 提示サマリ上は通過。  
7. 禁止事項違反: 目的が最適化で閾値いじりではない点は適合。ただし数値不変契約は上記 Critical で未達リスクあり。  

**全体判定**: `CHANGES_REQUESTED`