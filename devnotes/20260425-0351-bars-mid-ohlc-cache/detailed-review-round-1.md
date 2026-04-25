[Critical] 施策1の型契約が現行型定義と不整合です（`mypy` 失敗リスク）。  
Fact: 新API案は `bars_to_mid_ohlc(bars: list[PriceBar])` ですが、`EvaluationContext.bars` は `Sequence[PriceBar]` です（[detailed-design.md:126](/Users/ishitoya/repository/zenigame-fx/devnotes/20260425-0351-bars-mid-ohlc-cache/detailed-design.md:126), [_base.py:236](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/primitives/_base.py:236)）。  
Interpretation: `_compute_all` から `ctx.bars` を渡す呼び出しで `arg-type` が出る可能性が高く、設計の必須条件 `uv run mypy src/` 合格と衝突します。`bars` 引数は `Sequence[PriceBar]` に揃えるべきです。

[Warning] 施策3の `id` 再利用テストが実質ノーオペです。  
Fact: `assert ("_REFS" in ... or True)` は常に True です（[detailed-design.md:359](/Users/ishitoya/repository/zenigame-fx/devnotes/20260425-0351-bars-mid-ohlc-cache/detailed-design.md:359)）。  
Interpretation: 「identity guard が効く」ことの反証テストになっておらず、Round 1 指示（id再利用シナリオ検証）を満たせていません。

[Suggestion] `clear_cache()` の race は現状契約下では回避できるが、将来拡張時は未閉鎖です。  
Fact: lock なし実装で、単一thread前提を明示しています（[detailed-design.md:62](/Users/ishitoya/repository/zenigame-fx/devnotes/20260425-0351-bars-mid-ohlc-cache/detailed-design.md:62), [detailed-design.md:156](/Users/ishitoya/repository/zenigame-fx/devnotes/20260425-0351-bars-mid-ohlc-cache/detailed-design.md:156)）。  
Interpretation: 現行 `run_ga` は `ensure_registered()` 後に逐次評価で回るため直近は許容（[run_ga.py:742](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py:742)）ですが、thread導入時は即破綻候補です。

**反証6点の判定**
1. LRU eviction 時の `_REFS` cleanup 漏れ: `APPROVE`（`popitem` 後に `_REFS.pop` 実装あり）  
2. `move_to_end` を `_CACHE` のみ実施する分岐: `APPROVE`（hit分岐で両方更新）  
3. `clear_cache()` race condition: `INCONCLUSIVE`（現状契約では問題化しないが、並列化時は未対策）  
4. `id` 再利用の現実シナリオ: `INCONCLUSIVE`（設計は妥当だが、テストが検証になっていない）  
5. 3モジュール alias rename 漏れ: `APPROVE`（方針は妥当、既存呼び出し維持）  
6. `_compute_all` からの import タイミング: `APPROVE`（登録フロー上、実行時解決で成立）

**施策ごとの判定**
1. 施策1 `_bars_cache.py`: `REQUEST_CHANGES` [Critical]  
2. 施策2 3モジュール重複削除: `APPROVE` [Suggestion]  
3. 施策3 cache invarianceテスト: `REQUEST_CHANGES` [Warning]

**全体判定**: `REQUEST_CHANGES`  
（主因: 施策1の型契約不整合と、施策3の id再利用テスト不成立）