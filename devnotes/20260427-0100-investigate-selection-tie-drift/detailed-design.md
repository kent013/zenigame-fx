# 詳細設計: selection_score tie drift 調査

親: [conceptual-design.md](conceptual-design.md)

## 変更箇所

| ファイル | 変更 |
|---------|------|
| `scripts/alpha_factory/inspect_selection_tie.py` | 新規 CLI (Run + 世代別の tie ratio / HHI) |
| `tests/scripts/test_inspect_selection_tie.py` | 新規 |

## 調査出力

```
| gen | n_unique_fitness_pen | tie_ratio | top_genome_hhi |
|----:|---------------------:|----------:|---------------:|
| 0   | 96                   | 0.00      | 0.04           |
| 5   | 80                   | 0.17      | 0.08           |
| 15  | 35                   | 0.65      | 0.31           |
```

## DoD

- [ ] tie drift の有無を Run 22 で定量化
- [ ] 必要なら多様性圧導入の別 TODO 起票
