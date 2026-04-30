# 概念設計: calibrate-gate monotone tighten 観測

**起点監査**: [audit-codex.md §2 (20)](../20260427-0050-bug-hunt-audit/audit-codex.md) — INCONCLUSIVE

## 仮説

Run 20 (threshold=0.0) → Run 21 (0.0778) → Run 22 (0.1778) で calibrate-gate が連続 tighten。Stage A pass 数 2750 → 2395 → 1758 と縮小。T040 の drift CLI で `monotone_tighten` アラート発火条件 (>= 4 回) には未到達だが既に 2 回連続。次 Run で 3 回目、4 回目で alert 発火する見込み。

## 検証済み事実

- T040 で drift CLI / JSONL 永続化は完成
- Run 20-22 の threshold 推移は手動観察済
- calibrate-gate の制御則は変更しない (記録のみ、C3 collider bias 回避)

## 解決方針

T040 で枠は完成済 (`scripts/alpha_factory/calibrate_gate_drift.py`)。本 TODO は **Run 23+ を実行して history.jsonl が蓄積された段階で drift CLI を発火させる運用 TODO**。

drift alert 発火時の対応:
- 自動化しない (人間判定主体、C3)
- alert 発火 → calibrate-gate を手動 freeze (`enabled=false`) → root cause 調査の TODO 起票

## 成功判定

- Run 23, 24, 25 で history.jsonl の累積観察
- monotone_tighten 4 回連続発火するか / band_excess アラートが出るか
- 出た場合は別 TODO で control law 修正検討
