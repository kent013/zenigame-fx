## 本分析の前提
- 対象は Round 2 改訂版 `detailed-design.md` 本文。
- C1 に基づき、前ラウンドで確認済みの現行実装（`engine.py` / `mock.py` / `fitness.py` / `strategy.py` / 既存テスト）との整合観点で再評価。
- 判定は C9（反証優先）で「設計意図を壊す経路」の有無を先に検証。

## Verdict: APPROVED_WITH_COMMENTS

## Facts
- Round 1 の主要5指摘に対し、設計上の対応は明示されている。
- `run_backtest` は `validate -> deposit -> set_spread_filter` に順序修正され、副作用汚染リスクを下げている。
- `BacktestConfig.__post_init__` に `max_spread_bps < 0` の拒否が追加されている。
- `MockBroker` に `self._holding_cost_by_position` を持たせ、`_close_one` で `net_pnl = raw_pnl - cost_accum` とする設計になっている。
- `test_session_close_drops_pending_open` は `len(result.trades)==0` かつ `len(open_positions)==0` の強条件に強化されている。
- `evaluate_genome` の try/except は広いまま維持し、`error_type` ログで判別する方針が明記されている。

## Interpretations
- Round 1 でのブロッカー（holding cost が total_pnl に乗らない問題）は、`Trade.pnl` 反映方式で解消方向になっている。
- `final_cash - initial_cash` と `sum(Trade.pnl)` の整合は、設計前提を満たせば閉じる。
- 現時点の懸念は「設計破綻」ではなく「テストの分離度・運用品質」のレベル。

## 反証を探した結果
- 反証仮説: `holding cost` が total_pnl に依然未反映。  
  反証結果: `_close_one` で `cost_accum` を引く契約により、理論上は反映される。
- 反証仮説: validate 前副作用が残る。  
  反証結果: broker 状態副作用は抑制済み。残るのは `bars` iterable の消費のみ。
- 反証仮説: 強制クローズ経路で cost 回収漏れ。  
  反証結果: 現行構造上 `close_all -> _close_all_internal -> _close_one` に収束するため、設計上は回収可能。

## 指摘事項（番号付き）
1. `TestSessionCloseEngine.test_session_close_hour_forces_close` は day-boundary の EOD クローズでも通り得るため、session close 固有挙動の分離検証としては弱いです（テスト改善コメント）。
2. 同テストの evaluator script で `60` キー指定は bar index と直交し、意図伝達が弱いです（可読性/保守性コメント）。
3. `final_cash - initial_cash == sum(Trade.pnl)` の不変条件は重要なので、専用テストを 1 本追加して固定化した方が安全です（実装時コメント）。

## 追加質問への回答
1. はい、閉じます。前提は「全クローズ経路が `_close_one` を通る」「cash 変動源が `deposit`/`apply_bar_holding_cost`/`_close_one(raw_pnl加算)` に限定される」ことです。この前提下では厳密に一致します。  
2. broker 状態に関しては、validate 前副作用は解消されています。残る副作用は `bars` iterable の消費（`list(bars)`) のみです。  
3. はい、現行構造では `margin_call` / `session_close` / `eod` いずれも `close_all -> _close_one` に到達するため回収されます。設計通りに担保するには、この3経路それぞれで `cost_accum` 回収を検証するテスト追加が有効です。