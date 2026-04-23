1. **[High] `aux_series` の長さ不一致を `MISALIGNMENT` ではなく `MISSING_KEY` 扱いしており、設計仕様と不整合です。**  
事実: [pair_specific.py:512](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T013/src/alpha_factory/primitives/pair_specific.py:512), [pair_specific.py:597](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T013/src/alpha_factory/primitives/pair_specific.py:597), [pair_specific.py:653](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T013/src/alpha_factory/primitives/pair_specific.py:653), [pair_specific.py:780](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T013/src/alpha_factory/primitives/pair_specific.py:780), [pair_specific.py:867](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T013/src/alpha_factory/primitives/pair_specific.py:867) で `len(series) != len(bars)` が warning + safe default（または strict 時 RuntimeError）に流れています。  
解釈: 設計（[conceptual-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260423-1423-primitives-pair-specific/conceptual-design.md), [detailed-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260423-1423-primitives-pair-specific/detailed-design.md)）の `MISALIGNMENT = ValueError fail-fast` と一致せず、データ整合性バグをサイレントに隠すリスクがあります。特に `strict_aux_required` は key 存在しか見ないため、運用時に検出漏れが残ります。

2. **[Medium] `MISALIGNMENT` のテストが `aux_pair_bars` 側に偏っており、`aux_series` 長さ不一致の回帰を防げません。**  
事実: [test_pair_specific.py:635](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T013/tests/alpha_factory/primitives/test_pair_specific.py:635) と [test_pair_specific.py:647](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T013/tests/alpha_factory/primitives/test_pair_specific.py:647) は P5 のみ `ValueError` を検証していますが、P7/P8/P9/P11/P12 の `aux_series` 長さ不一致ケースは未検証です。  
解釈: 3状態監査要件（MISSING_KEY / STALE_VALUE / MISALIGNMENT）のうち、`aux_series` 系 MISALIGNMENT が実質未カバーです。

**確認事項 / 前提**  
`aux_series` の長さ不一致を意図的に「欠損扱い」にした設計変更であれば、設計書と docs の `MISALIGNMENT` 定義を更新して整合を取る必要があります。現状の文書・実装の組み合わせでは不整合です。

**判定: NEEDS_REVISION**