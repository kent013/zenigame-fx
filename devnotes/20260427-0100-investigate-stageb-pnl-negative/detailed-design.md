# 詳細設計: Stage B 通過群 total_pnl 全 negative 調査

親: [conceptual-design.md](conceptual-design.md)

## 変更箇所

| ファイル | 変更 |
|---------|------|
| `scripts/alpha_factory/inspect_stage_b_folds.py` | 新規 CLI |
| `tests/scripts/test_inspect_stage_b_folds.py` | 新規 |
| `docs/alpha_factory/diagnostics-sidecar.md` または新規 docs | 調査結果記録テンプレート (run-{N} ごとに output) |

## CLI 仕様

```bash
uv run python scripts/alpha_factory/inspect_stage_b_folds.py \\
    --run-id run_20260426_145502 --top 5
```

- archive Parquet から Stage B 通過個体を pick (top N または ALL)
- 各個体について Stage B WF backtest を **再実行** し、fold ごとの (start, end, n_trade, sum_pnl, oos_sharpe) を tabulate
- 全 fold sum_pnl vs Stage A 60d total_pnl vs Stage B is_full total_pnl を比較
- 「fold 80% positive で total negative」の事例を可視化

## 出力

```
## Stage B fold inspection: g32_i12 (Run 20)

| fold | start      | end        | n_trade | sum_pnl  | oos_sharpe |
|-----:|------------|------------|--------:|---------:|-----------:|
| 0    | 2025-10-01 | 2025-10-10 | 8       | +12,000  | +0.45      |
| 1    | 2025-10-11 | 2025-10-20 | 6       | +8,000   | +0.30      |
| ...  |            |            |         |          |            |
| 7    | 2025-12-15 | 2025-12-25 | 12      | -56,000  | -1.20      |
|      |            |            |         |          |            |
| sum  |            |            | 80      | -16,500  | (mean +0.18) |

Stage A 60d total_pnl: -16,850 (整合)
Stage B is_full total_pnl: -41,200 (より長期で悪化)
```

## DoD

- [ ] CLI が任意 run_id の Stage B 通過個体について fold ごと metrics を出力
- [ ] サンプル 5 個体で「fold 80% positive で total negative」の物理現象を再現または bug 検出
- [ ] 結果に応じて次の TODO (修正 or 統計帰結受容) を別途起票

## 反証

- 反証仮説 1: 「fold 80% positive は数学的に total negative を許容するため bug ではない」 → 1 fold あたり trade 数が小さく標準誤差が大きい場合、8 fold median+0.18 でも total negative はあり得る (中央値と平均の差)
- 反証仮説 2: 「Stage A と Stage B の sign 計算は一致している」 → fold 個別 sharpe が positive かつ全期間 backtest sharpe も positive ならこの調査は不要 (現状未確認)
