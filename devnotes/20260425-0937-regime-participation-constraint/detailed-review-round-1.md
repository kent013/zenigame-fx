**全体判定: CHANGES_REQUESTED**

**C4 前提検証（main 突合）**
- 設計書の「default 既存値変更なし」と、現行 `main` の値が不一致です。設計書は `population_size: 20 / generations: 5`、現行は `40 / 15` です。参照: [detailed-design.md:113](/Users/ishitoya/repository/zenigame-fx/devnotes/20260425-0937-regime-participation-constraint/detailed-design.md:113), [default.yaml:20](/Users/ishitoya/repository/zenigame-fx/config/alpha_factory/default.yaml:20)
- `trade_count` 列は現行スキーマに存在します（`genome_archive.py` ではなく `archive.py`）。参照: [archive.py:70](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/archive.py:70)
- 現行の `selection_score` は 4 要素で、テストも 4 要素前提です。参照: [run_ga.py:111](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py:111), [test_alpha_factory_run_ga.py:395](/Users/ishitoya/repository/zenigame-fx/tests/scripts/test_alpha_factory_run_ga.py:395)

1. 施策1 `GAFeasibilityConfig` 追加  
判定: REQUEST_CHANGES  
- [Warning] `entry_count_min` の上限・世代整合バリデーション不足。`極端値` で `violation` が `inf` 化し得ます。  
修正案: `entry_count_min <= live_criteria.trade_count_max`（または安全上限）と `apply_from_generation <= ga.generations` を `load_config` で検証。
- [Warning] `bool(...)` 変換は `"false"` 文字列を `True` 扱いします。  
修正案: 厳格 bool パーサを導入（`True/False` 以外は `ValueError`）。
- [Suggestion] `GAConfig` に `field(...)` を足すなら import 追記が必要です。参照: [config.py:20](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/config.py:20)

2. 施策2 `default.yaml` 追加  
判定: REQUEST_CHANGES  
- [Critical] 施策説明は「追記のみ」ですが、抜粋に既存 GA 値変更が混入しています。  
修正案: 既存値 (`40/15`) を維持し、`ga.feasibility` ブロックのみ追加。参照: [detailed-design.md:113](/Users/ishitoya/repository/zenigame-fx/devnotes/20260425-0937-regime-participation-constraint/detailed-design.md:113), [default.yaml:20](/Users/ishitoya/repository/zenigame-fx/config/alpha_factory/default.yaml:20)

3. 施策3 `IndividualCacheEntry` 6 要素化  
判定: REQUEST_CHANGES  
- [Warning] `-violation_magnitude` に `NaN` が混入すると順序比較が壊れます（Python では `nan` 比較が常に偽）。  
修正案: `selection_score` 生成時に `math.isfinite` で正規化（非有限は `+inf` 扱い等）。
- [Suggestion] `fitness_pen` 側の非有限も選抜用に正規化しておくと頑健です。

4. 施策4 `_update_cache` + Fallback  
判定: REQUEST_CHANGES  
- [Warning] fallback を `_tournament` / `_select_best` だけに入れると、エリート選抜（`_breed_next_gen` の `sorted_pop`）と規則不整合になります。参照: [run_ga.py:382](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py:382)  
修正案: 共通 score 関数を作り、`_tournament` / `_breed_next_gen` / `_select_best` で同一ロジックを使用。
- [Warning] 設計書の参照ファイル名が古い（`genome_archive.py`）。  
修正案: `src/alpha_factory/archive.py` に修正。参照: [detailed-design.md:289](/Users/ishitoya/repository/zenigame-fx/devnotes/20260425-0937-regime-participation-constraint/detailed-design.md:289)

5. 施策5 `summary.json` v2  
判定: REQUEST_CHANGES  
- [Critical] `per_generation.feasible_count` を追加しても、現行は `sanitized_per_generation` でキーを絞っており落ちます。参照: [run_ga.py:583](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py:583)  
修正案: sanitize 時に `feasible_count`（必要なら `no_trade_ratio` も）を明示コピー。
- [Warning] `selection_score` に生値 `float(best_entry.fitness_pen)` を使うと非有限が再流入します。  
修正案: 現行同様 `best_fitness_val` の有限化済み値を使用。参照: [run_ga.py:657](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py:657)

6. 施策6 run-report 更新  
判定: REQUEST_CHANGES  
- [Critical] 提示 snippet は `best_row` / `best_entry` が `generate_run_report.py` スコープに存在せず、そのままでは実装不能です。  
修正案: `summary["best"]` と `archive_rows` から算出（`feasible` は `selection_score_schema=="v2_feasibility"` かつ `selection_score[0]==1` で判定）。
- [Warning] スキル文書側に旧 4 要素記述が残っています。参照: [zenigame-fx-run-report/SKILL.md:120](/Users/ishitoya/repository/zenigame-fx/.claude/skills/zenigame-fx-run-report/SKILL.md:120), [generate_run_report.py:453](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/generate_run_report.py:453)  
修正案: スクリプトと skill 記述を同時更新。

7. 施策7 テスト計画  
判定: REQUEST_CHANGES  
- [Warning] `_breed_next_gen` の fallback 一貫性テストが不足。  
修正案: 「全 infeasible 時の elite 選抜」と「tournament sample 全 infeasible」の両方を個別テスト化。
- [Warning] run-report 用テストファイルは現状未存在です。  
修正案: `tests/scripts/test_generate_run_report.py` を新規作成し、`selection_score_schema` v1/v2 互換を検証。

**重点問合せ (a)-(g)**
- (a) 条件付きで整合。`row=None` を `feasible=False` 扱いする方針は妥当。  
- (b) `-violation` の NaN/inf 伝播リスクあり（要 finite guard）。  
- (c) fallback は `_tournament` だけでなく elite 選抜にも揃えるべき。  
- (d) `trade_count` 列は現行スキーマに存在（OK）。  
- (e) `selection_score_schema="v2_feasibility"` 自体は妥当。下流コード破壊は小さいが skill/doc 更新は必要。  
- (f) `entry_count_min` 極端値など validation は不足。  
- (g) `frozen dataclass + field(default_factory=...)` は Python 3.13 で問題ありません。