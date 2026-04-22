**指摘事項（重要度順）**
1. **`directional_swap` が `max_depth` 上限を破る可能性があります（設計契約との不整合）**  
   事実: [detailed-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260422-1552-clause-ga-operators/detailed-design.md):406 で `ka`、:407 で `kb` を独立に取り、:408-409 で連結しているため、子の `directional` 長が親より増え得ます。`crossover` 側は `max_depth` を受け取らず（:467）、最終 `enforce_consistency` も幅上限を強制しません（[enforce.py](/Users/ishitoya/repository/zenigame-fx/src/dsl/enforce.py):109）。  
   解釈: 概念設計の `max_depth` 幅上限（[conceptual-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260422-1552-clause-ga-operators/conceptual-design.md):141）および hard cap 方針（:171）と齟齬があります。

2. **`alpha` 効果テストが契約を検証できていません**  
   事実: 概念設計は「`α=0` と `α>0` で挙動変化を確認」（[conceptual-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260422-1552-clause-ga-operators/conceptual-design.md):393）ですが、詳細設計の `test_alpha_affects_pen_but_not_raw` は履歴長の一致しか見ていません（[detailed-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260422-1552-clause-ga-operators/detailed-design.md):1486, :1495）。  
   解釈: テスト名・意図とアサーションが一致しておらず、退行検知力が不足しています。

3. **`ruff clean` 成功条件に対して、提示コードの未使用要素が多いです**  
   事実: 成功条件で `ruff check src/ga/ tests/ga/` クリーンを要求（[conceptual-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260422-1552-clause-ga-operators/conceptual-design.md):39）。一方で、例: [detailed-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260422-1552-clause-ga-operators/detailed-design.md):335, :337, :1028, :1037, :1127, :1133, :1137, :1255 に未使用 import/変数候補があります。  
   解釈: 実装をこのまま写経すると lint で止まる可能性が高いです。

4. **`params_perturb` 周りの条件式は可読性が低く、保守時の誤読リスクがあります**  
   事実: [detailed-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260422-1552-clause-ga-operators/detailed-design.md):518-531 と :582-596 で同種ロジックが重複し、三項式+辞書アクセスが長く連結されています。  
   解釈: ユーザー指摘どおり、`_signal_name(...)` / `_signal_spec(...)` ヘルパー抽出を推奨します。

**観点別コメント（要点）**
- 1) 概念設計整合: 上記 1,2 を除き、attempted-edits / 一様選択 / 候補非空の思想は整合。  
- 2) `random_gen`: DUMMY 分離、bounded retry、`_filter_by_category`、`n_gate=min(1, ...)` は妥当。  
- 3) `operators`: 前提条件テーブルは概ね一致。ただし幅上限の扱いが未解決。  
- 4) `runner`: `EvaluationResult`/`safe_fitness`/elitism/tournament/`_rename` の流れは自然。  
- 5) 型注釈: `Literal` 設計自体は妥当。  
- 6) `test_rate_one_attempts_k_times`: 現状のカウントは kernel 名集合で絞っており、他 `rng.choice` との混同は起きにくい（ただし class-level monkeypatch のため将来拡張には脆い）。  
- 7) `enforce_consistency` タイミング: 末尾 enforce 方針は明確。  
- 8) `params_perturb` 可読性: 要リファクタ（上記 4）。  
- 9) `__init__.py` API: [detailed-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260422-1552-clause-ga-operators/detailed-design.md):989, :991, :1016, :1018 の公開はやや広め（内部 helper の露出最小化を検討）。

REVISE