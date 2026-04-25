# マージ分析: Run 10 (run_20260425_004002)

## 合意事項（Run 10 観察事実）

- **Stage A 通過率激増**: 4291/5856 = 73.3%（Run 9 の 0/120 から劇的改善）
- **Stage B 全滅**: 0/4291 → 次のボトルネックは Stage B
- **trade_count 改善**: 平均 34.94（Run 9 の極小から大幅改善）、ただし live_criteria.trade_count_min=50 に未到達
- **trade_count=0 比率**: 12.2%（Run 9 の 75% から大幅改善）
- **best fitness=18.48** (sharpe=18.49、live_criteria.sharpe_min=1.0 達成)
- **total_pnl 改善**: best=18,860 / max=27,130 / mean=10,319 — ただし live_criteria.total_pnl_min=50,000 に未到達
- **graduation/Stage C 通過**: 0 件（Stage B で全数止まる）

## Run 9 → Run 10 主要変化（pop/gen スケールアップによる）

| 指標 | Run 9 (pop=20,gen=5) | Run 10 (pop=96,gen=60) | 変化 |
|------|---------------------|-----------------------|------|
| Stage A pass | 0/120 (0%) | 4291/5856 (73%) | +73 pt |
| trade_count=0 比率 | 75% | 12% | -63 pt |
| best fitness | 0 | 18.48 | +18.48 |
| total_pnl best | 0 | 18,860 | +18,860 |
| sharpe (取引個体) | 全て負 | 平均 8.32 | 大幅改善 |

## 解釈

- Run 9 の崩壊は **pop=20×gen=5 が小さすぎ** て探索初期で多様性が枯渇した結果が大きい（cycle 1 Codex の「無取引優位」仮説は完全には反証されないが、第一の主因ではなかった可能性）
- Run 10 規模なら Stage A は通過するが **Stage B walkforward** で全滅 → wf_train_days=120 / wf_test_days=20 が窓 14 日に対して大きすぎる可能性
- trade_count 平均 34.94 は live_criteria 50 にあと一歩

## 矛盾・要議論

- cycle 1 で「観察 RUN」と位置づけたが Run 10 は実質的な前進を見せた → 構造変更（施策1）の優先度を再検証する必要
- Stage B 全滅の原因切り分け: (a) wf 設定が窓に対して大きすぎる、(b) median_oos_sharpe_min=0.20 が厳しすぎる、(c) 個体の OOS 性能が実際に悪い

## 統合改善提案（優先度順）

| # | 提案 | 優先度 | target_metric | failure_mode | 期待効果 |
|---|------|--------|--------------|-------------|---------|
| 1 | **Stage B 全滅の原因切り分け** | Critical | Stage B pass | wf 窓 / 閾値 / 実 OOS 性能のどれが原因か不明 | 次サイクルの介入対象を特定 |
| 2 | **trade_count を 50 以上に押し上げる軽微なフィットネス調整** | Warning | trade_count | live_criteria 未達 | trade_count_min=50 達成 |
| 3 | **データ窓拡大検討** (構造的) | Warning | Stage B pass | 14 日窓では wf_train_days=120 は不可能 | より長い窓で Stage B 評価可能化 |
| 4 | **PnL 集計監査** (cycle 1 から保留) | Warning | total_pnl 整合性 | 監査未実施 | cycle 3 以降で監査 |
