# 概念設計: Stage B 通過群の total_pnl 全 negative 物理調査

**起点監査**: [audit-codex.md §1 / §5 不確定領域](../20260427-0050-bug-hunt-audit/audit-codex.md) — Codex INCONCLUSIVE (Parquet 読取制約)

## 仮説

Run 20 で Stage B 通過 834 個体すべて total_pnl<0 / trade_sharpe_raw<0 だが、positive_fold_ratio 0.80 で fold の 80% は positive sharpe を持つ。「per-fold で 80% positive」と「全期間 total negative」は通常両立しない。これが
- (a) 短い fold (test=10 日) での偶発的 positive (統計帰結)
- (b) Stage B WF と Stage A 60 日 backtest が異なる bars 集合を使う構造的不一致
- (c) WF fold backtest の sign / state bug
のどれかを切り分ける必要がある。

## 検証済み事実

- Run 20 archive: Stage B pass=834、全員 trade_sharpe_raw mean=-0.19, total_pnl mean=-16,522, positive 件数 0/834
- positive_fold_ratio_effective mean=0.80 (Stage B 通過条件 0.60 を全員クリア)
- n_fold_effective median=8

## 解決方針

調査スクリプト `scripts/alpha_factory/inspect_stage_b_folds.py` を新設し、Run N の Stage B 通過個体について以下を dump:

1. fold ごとの (start, end, n_trade, sum_pnl, oos_sharpe)
2. 全 fold の sum_pnl 合計 vs Stage A trade_sharpe_raw / Stage B is_full sharpe との比較
3. fold 80% positive sharpe での total negative の物理的説明 (sample size と統計的帰結を可視化)

これで bug か統計的帰結かを切り分け、必要なら fold 計算 logic への修正 TODO を別途起票。

## 成功判定

- 1 個体分の fold ごと metrics を dump できる
- 「fold 80% positive で total negative」が (a) 統計帰結 / (b) 構造的不一致 / (c) bug のどれかを根拠付きで判定
- 結果に応じた次 TODO の方向性が決まる

## 北極星制約

調査のみ。GA / fitness / selection への変更なし (observability)。
