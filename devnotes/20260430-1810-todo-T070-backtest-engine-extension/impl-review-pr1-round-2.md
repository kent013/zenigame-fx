## 前提
- 設計 SSOT は verified: `devnotes/20260430-1810-todo-T070-backtest-engine-extension/conceptual-design.md:134` と `devnotes/20260430-1810-todo-T070-backtest-engine-extension/detailed-design.md:292` の会計契約を確認。
- 実装本文は verified: `src/backtest/session_block.py:104`、`src/broker/orders.py:33`、`src/broker/mock.py:400`、`src/backtest/engine.py:75` を直接確認。
- caller 経路は verified: `Trade(` / `BacktestResult(` の grep と既存 fixture 本文を確認し、実 constructor は keyword 構築だった。
- テスト証跡は verified: `tests/backtest/test_session_block.py:237`、`tests/broker/test_orders.py:32`、`tests/broker/test_mock.py:87`、`tests/backtest/test_engine.py:305` を確認。テスト実行ログは提示ログを根拠にした。

## Hypothesis 検証結果
H1 (aggregate_session_blocks SSOT 整合): **CONFIRMED**  
`SessionBlock.__post_init__` は `bar_count/trade_count/cost_total >= 0` と `pnl_before_costs == pnl_net + spread_cost_total + holding_cost_total` を検証している。`aggregate_session_blocks` は SSOT 通り `pnl_net=sum(t.pnl - t.spread_cost)`、`pnl_before_costs=sum(t.pnl + t.holding_cost)`、cost total を同一 block 内で集計しており、date universe も bars と trades の union。`compute_bucket_for_bar` は UTC validation と未カバー hour の `RuntimeError` を持つ。

H2 (Trade field 破壊変更なし): **CONFIRMED**  
`Trade.spread_cost` / `Trade.holding_cost` は dataclass 末尾に default `Decimal(0)` 付きで追加されている。既存 caller は `tests/backtest/test_advanced_metrics.py:14`、`tests/backtest/test_metrics.py:21`、`tests/alpha_factory/test_stage_gate.py:854` など keyword 構築で、default 適用により破壊変更なし。

H3 (cash 動作不変): **CONFIRMED**  
`src/broker/mock.py:405` で `raw_pnl`、`src/broker/mock.py:409` で `cost_accum`、`src/broker/mock.py:410` で `net_pnl` を計算し、`src/broker/mock.py:415` は従来契約通り `self._cash += raw_pnl` のまま。`spread_cost` / `holding_cost` は `Trade` への転記のみで、F19 二重計上経路は確認できなかった。

H4 (transport SSOT): **CONFIRMED**  
`BacktestResult.session_blocks` は `default_factory=tuple` で backward-compatible。`run_backtest` 末尾で `aggregate_session_blocks(bars_list, broker.trades)` を 1 回計算し、戻り値へ同梱している。新 `aggregate_session_blocks` の production caller は `src/backtest/engine.py:203` のみ。

H5 (apply_spread_stress 代数): **CONFIRMED**  
`src/backtest/session_block.py:329` で finite、`src/backtest/session_block.py:331` で `>= 1` を検証し、`src/backtest/session_block.py:338` で `trade.pnl - trade.spread_cost * (multiplier - 1)`、`src/backtest/session_block.py:339` で `spread_cost * multiplier` を実装している。multiplier=1 no-op、multiplier>1 の追加 spread 分控除、NaN/Infinity/<1 raise はテストで対応済み。

## 反証で発見された issue
- Critical: なし。
- Warning: `compute_bucket_for_bar` の `RuntimeError` は未カバー hour 防御であり、range overlap は runtime では検出しない。ただし現 const と `tests/backtest/test_session_block.py:448` / `tests/backtest/test_session_block.py:458` で 24h covering / no overlap は検証済み。
- Warning: `Trade(stressed)` は通常 `Trade` と型で区別されないため、将来 caller が `aggregate_session_blocks` に渡すと spread 二重控除になり得る。現実装は `src/backtest/session_block.py:316` で caller 責務を明記し、現 grep 上の混入経路はない。
- Suggestion: Phase 2 の T064/T061 配線時に、stressed trade を `aggregate_session_blocks` に渡さない契約をテストまたは型で補強する。

## 最終判定
**APPROVED**

T070 PR1 は詳細設計通り実装され、H1-H5 は全て **CONFIRMED**。残る懸念は将来配線時の misuse 防止であり、PR1 の修正必須事項ではない。