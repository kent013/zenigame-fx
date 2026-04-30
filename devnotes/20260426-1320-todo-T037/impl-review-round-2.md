APPROVED  
- `compute_composite` の直接呼び出しに戻したことで、clauses 空・長さ不一致の ValueError 契約がそのまま復活しているのを確認しました（worktrees/todo-T037/src/dsl/strategy.py:319 → worktrees/todo-T037/src/dsl/composite.py:74-104）。  
- 併設した per-clause 集計ループは `compute_clause_score` を使った観測専用で、composite 数値や既存フローに影響しないことも確認しました（worktrees/todo-T037/src/dsl/strategy.py:320-324）。