# Round 1 Detailed Design Review

## 施策 1 判定
APPROVE

[Warning]
- `cast順序完全同一` という記述は厳密には不一致です。現行は `bid 4項目 → ask 4項目`、提案は `openペア → highペア → ...` の順です（[detailed-design.md#L72](/Users/ishitoya/repository/zenigame-fx/devnotes/20260505-2121-bars_cache_compute_local_var/detailed-design.md#L72), [detailed-design.md#L101](/Users/ishitoya/repository/zenigame-fx/devnotes/20260505-2121-bars_cache_compute_local_var/detailed-design.md#L101)）。
- ただし `PriceBar/Ohlc` は frozen dataclass の通常属性で副作用経路がなく、数値同値性リスクは低いです（[price.py#L8](/Users/ishitoya/repository/zenigame-fx/src/domain/price.py#L8)）。

[Suggestion]
- 設計文言を「演算順序同一・cast回数同一（cast順序は変更）」に修正すると、主張の整合性が上がります。

## テスト計画 評価
- parityテスト方針は妥当です。既存の `_compute` 同値検証とも整合しています（[test_bars_cache.py#L72](/Users/ishitoya/repository/zenigame-fx/tests/alpha_factory/primitives/test_bars_cache.py#L72)）。
- `Decimal("NaN") -> float("nan")` ケースは妥当です。quiet NaN の同値確認として十分です。
- microbenchmark `軽量版 <= oracle * 1.10` は「非退行」用途として十分です。`必須gateではない` を守るため、perf test は通常CIから外す運用が安全です。
- C4前提（profileデータ・既存実装・既存テスト）は設計文書内で確認できています（[conceptual-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260505-2121-bars_cache_compute_local_var/conceptual-design.md), [detailed-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260505-2121-bars_cache_compute_local_var/detailed-design.md), [_bars_cache.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/primitives/_bars_cache.py), [test_bars_cache.py](/Users/ishitoya/repository/zenigame-fx/tests/alpha_factory/primitives/test_bars_cache.py)）。

## 全体判定
APPROVED

## 主要指摘 / 推奨事項
1. `bid/ask` local化の効果見積りは `5-15%` が妥当レンジです。`float(Decimal)` と ndarray 代入が支配項なので、`>15%` は楽観的です。  
2. NaNテストは妥当です。`Decimal("NaN")` を使う現設計で問題ありません。  
3. microbenchmark閾値は `<=1.10` で十分です。これ以上 strict にするとノイズで不安定化しやすいです。  
4. 残 blocker はありません（文言整合性の修正は推奨レベル）。