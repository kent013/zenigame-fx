# 詳細設計: calibrate-gate monotone tighten 観測 (運用 TODO)

親: [conceptual-design.md](conceptual-design.md)

## 変更箇所

新規 code 変更なし。**運用観察 TODO**として next 数 Run の history を集計する。

| ファイル | 変更 |
|---------|------|
| (新規 docs) `reports/calibrate-gate/observation-2026-04.md` | Run 20-25 の drift 観察記録 |

## 運用手順

1. Run 23/24/25 を実行
2. `uv run python scripts/alpha_factory/calibrate_gate_drift.py --last 5` で alert 確認
3. monotone_tighten 4 回連続なら freeze (yaml で `calibrate.enabled=false`) + 別 TODO で control law 検討
4. band_excess なら target_pass_rate=0.15 が現状の fitness 分布に対し過剰の可能性 → docs に観察記録

## DoD

- [ ] Run 23-25 の drift 集計を docs に記録
- [ ] alert 発火時の対応 path を documentation
- [ ] 必要なら control law 修正の別 TODO 起票
