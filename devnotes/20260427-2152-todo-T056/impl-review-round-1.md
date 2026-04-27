# Codex impl-review Round 1 (T056)

判定: **CHANGES_REQUESTED**

## [Critical]
- `test_fill_pending_l2_exception_continues_loop` は L1 (NaN equity) で drop を確認しているのみで、L2 例外発火後の継続を直接検証していない（V7 未達）
  → L1 を bypass した状態で `_open_position` が `InsufficientEquityError` を raise する経路を作る test を追加

## [Warning]
- `test_fill_pending_drops_open_signals_when_equity_is_infinity` で同 bar を再利用しつつ `_cash` を変更すると snapshot cache が前回値を返す可能性
  → 各サブ assertion で別 bar を使うか cache invalidate

## [Suggestion]
- runbook の「100% 以下で発動」と code の `< maintenance_pct`（strict less-than = 100% より小さい）が表現として整合しないので明確化

## ファイル別
- src/broker/orders.py: APPROVE
- src/broker/mock.py: APPROVE
- src/backtest/engine.py: APPROVE
- src/broker/__init__.py: APPROVE
- tests/backtest/test_engine.py: APPROVE
- tests/broker/test_mock_broker.py: CHANGES_REQUESTED
- docs/alpha_factory/runbook.md: WARNING
