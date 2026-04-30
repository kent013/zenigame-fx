[Warning] `scripts/alpha_factory/generate_run_report.py:610-663`  
Stage A provenance セクションでは sidecar 全行数と metric_stage 別件数、そして Stage A 落ち個体の `total_pnl_stage_a` 分布だけを出力していますが、詳細設計 (devnotes/20260425-0937-cost-pnl-ledger-eventsource/detailed-design.md:582-586) で合意された「`trade_count > 0` の Stage A 落ち個体件数とその分布」「Stage A 通過個体の分布」が抜けています。`trade_count > 0` を明示的にフィルタしないと Run 9 で問題化した「取引しているのに PnL=0」ケースを観測できず、本施策の監査目的が満たせません。`trade_count` によるフィルタと Stage A 通過群の統計出力を追加してください。

全体判定: CHANGES_REQUESTED