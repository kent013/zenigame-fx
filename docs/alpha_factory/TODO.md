# Alpha Factory TODO

zenigame-fx Alpha Factory の改善タスク一覧。

## Open

| ID | タイトル | テーマ | 概要 | 優先度 | 実装モード | 設計 | 追加日時 |
|----|---------|-------|------|-------|----------|------|---------|
| T095 | T092 fold guard fixture 修正 (15件まとめ) | stage-gate | T092 fixture fail 15 件 fix | High | incremental | [設計](devnotes/20260513-1915-todo-t092-fixture-fix/) | 2026-05-13 19:15 |
| T096 | archive.py:335 mypy narrowing fix (PR2 由来) | general | mypy narrow assert 1 行 fix | Low | incremental | [設計](devnotes/20260513-1915-todo-archive-mypy-narrow-fix/) | 2026-05-13 19:15 |
| T097 | docs: progress_criteria 明文化 (Z-1 10k / Z-2 20k / Z-3 30k / Z-4 50k) | general | progress_criteria docs 新規 | Medium | incremental | [設計](devnotes/20260513-1915-todo-progress-criteria-docs/) | 2026-05-13 19:15 |
| T098 | scripts: out-of-cluster audit (PR3 shadow 活用) | general | cluster artifact 自動検出 script | Medium | incremental | [設計](devnotes/20260513-1915-todo-out-of-cluster-audit/) | 2026-05-13 19:15 |
| T100 | Stage C stratified allocation (PR3 shadow stratifier) | stage-gate | Stage C 評価集団 stratifier | Medium | standalone | [設計](devnotes/20260513-1915-todo-stage-c-stratified-allocation/) | 2026-05-13 19:15 |
| T101 | Run 71/63 系統 warmstart 検討 (= 再現性検証) | ga-architecture | warmstart pool 注入 | Low | standalone | [設計](devnotes/20260513-1915-todo-run71-63-warmstart/) | 2026-05-13 19:15 |
| T102 | Phase 2 統合 Step 3-7 (BCEvaluationResult / NSGA-II / CPPS / warmstart 配線) | ga-architecture | Phase 2 配線 5 sub-PR | Medium | standalone | [設計](devnotes/20260513-1915-todo-phase2-integration-step3-7/) | 2026-05-13 19:15 |
| T103 | primitive 拡張 (zenigame 82 primitive 相当の FX 用拡充、 撤退条件 trigger) | primitives | primitive 30-50 個移植 | Low | standalone | [設計](devnotes/20260513-1915-todo-primitive-expansion/) | 2026-05-13 19:15 |
| T105 | backtest hot path の Decimal churn 削減 | infrastructure | backtest の Decimal churn 削減 | Medium | standalone | [設計](devnotes/20260514-2045-ga-worker-memory/) | 2026-05-15 08:11 |

## Conditional

| ID | タイトル | テーマ | 概要 | トリガー条件 | 昇格時優先度 | 実装モード | 設計 | 追加日時 |
|----|---------|-------|------|------------|------------|----------|------|---------|
| T104 | PR6: F6/F10/F4/F7 grammar soft downweight opt-in | primitives | F6 grammar soft downweight | PR4 smoke で F6 含有率 top decile が baseline×1.5 超 | Low | standalone | [設計](devnotes/20260513-1915-todo-pr6-f6-grammar-downweight/) | 2026-05-13 19:15 |
