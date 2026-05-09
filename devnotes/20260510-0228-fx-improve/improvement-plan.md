# 改善計画 + 詳細設計: Run 59 → Run 60 (cycle 7)

## Codex 戦略 (cycle 6 で確定) 継承

cycle 7 は seed sweep 継続 (cycle 6-8 区間の 2 番目)。

## 施策 C7-1: seed sweep continuation (seed=45)

### 内容
- run_ga.py 引数 `--seed 44` → `--seed 45`
- dataset / config / コード 変更なし

### success_criterion
- Run 60 完走 (smoke-mode opt-in なし)
- Run 57/58/59 と異なる Best 個体 + fp/sharpe/total_pnl/trade_count の 4 サンプル variance プロファイル拡張
- Stage B pass>0 が再現するか確認 (現状 1/3 RUN = Run 57 のみ)

### 3 RUN variance 観測 (cycle 6 まで)
- best fp: 0.13 / 0.20 / 0.26 (range 0.13、 mean 0.197)
- sharpe: 0.16 / 0.22 / 0.29 (range 0.13、 mean 0.222)
- total_pnl: -4100 / +16700 / +33230 (大きな bias、 Run 56 -→59 で改善傾向)
- trade_count: 30 / 55 / 45
- Stage B pass: 105 / 0 / 0 (Run 57 lucky draw)

### Codex 全体判定: APPROVED (戦略 Y 継承、 cycle 6 で確定済)
