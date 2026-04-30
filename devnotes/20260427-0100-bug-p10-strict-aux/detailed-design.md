# 詳細設計: P10 strict_aux 標準化

親: [conceptual-design.md](conceptual-design.md)

## 変更箇所

| ファイル | 変更 |
|---------|------|
| `src/alpha_factory/primitives/evaluator.py` | `RegistryEvaluator.__init__` の `strict_aux_required` default を True 化 (production)、test fixture は明示 False |
| `scripts/alpha_factory/run_ga.py` | RegistryEvaluator 生成箇所で event_snapshot を渡す経路を整備 (loader が無ければ skip) |
| `tests/alpha_factory/primitives/test_evaluator.py` | strict default True の挙動を verify、既存テストは明示 strict=False に修正 |
| `docs/alpha_factory/primitives.md` | strict_aux_required の production default 切替を追記 |

## 連動 TODO

本 TODO は **aux loader 整備 TODO** との連動が必須。loader 完成前に default true 化すると Stage A no_exposure / system_failure が増えるため:

- 順序 1: aux loader 整備 (#bug-pair-specific-aux-loader)
- 順序 2: 本 TODO の strict default true 化

または順序 1 のスコープに本 TODO を merge する選択肢もあり。

## DoD

- [ ] strict_aux default true で aux 不在時 Stage A が fail-fast
- [ ] 既存テスト全 pass (明示 strict=False で safe default 経路保持)
- [ ] aux loader 整備済み or 連動 TODO 完了済みの確認
- [ ] Codex impl-review APPROVED
