## 本分析の前提
- 対象は提示された `detailed-design.md` 全文。
- C1 に従い、現行 `src/backtest/engine.py` / `src/broker/mock.py` / `src/ga/fitness.py` / `src/dsl/strategy.py` / `tests/backtest/test_engine.py` / `tests/_helpers.py` / `docs/alpha_factory/clause-architecture.md` / 関連 `git log` を先読した。
- 事実と解釈を分離し、C9（反証優先）で「設計意図が壊れる経路」を先に探索した。

## Verdict: NEEDS_REVISION

## Facts
- 詳細設計の spread filter は `fill_pending` 前段で `_last_close_spread_bps` を参照し、`run_backtest` の順序は `fill_pending -> mark_to_market` なので、判定値は前バー由来になる設計。
- 詳細設計の session close 順序は `drop_pending_open -> fill_pending -> mark_to_market -> holding_cost -> margin -> close_all -> strategy.on_bar -> open submit drop` で定義されている。
- 詳細設計の `evaluate_genome(metric="total_pnl")` は `compute_metrics(...).total_pnl` を返す設計。
- 現行 `compute_metrics` の `total_pnl` は `sum(trade.pnl)`（約定トレード損益の合計）であり、cash 直接控除（holding cost）は `total_pnl` に入らない実装。
- 詳細設計の変更対象一覧に `src/backtest/metrics.py` は含まれていない。
- `tests/backtest/test_engine_clause.py::test_session_close_drops_pending_open` の期待は `assert all(t.exit_reason != "signal" ...)` で、`open が誤って成立して eod で閉じた` ケースを検出できない。

## Interpretations
- Lookahead 回避設計（spread 判定タイミング）は整合しており、ここは破綻していない。
- session close の pending open 封鎖順序も概ね妥当で、抜け道はかなり塞げている。
- ただし「holding cost を fitness に反映」の主目的は、`metric="total_pnl"` 経路で未達になる。Stage A が `total_pnl` スクリーニング想定のままだと、holding cost が選抜に効かない。
- よって North Star/絶対制約（コスト反映）に対して設計レベルの欠陥が残るため、実装進行は早い。

## 反証を探した結果
- 反証仮説A: 「sharpe/calmar で cost が効くので問題ない」  
  反証結果: Stage A 想定が `total_pnl` のため、主要経路で cost 非反映が残る。
- 反証仮説B: 「session_close pending open テストで漏れは検出できる」  
  反証結果: 現行アサーションでは `eod` クローズに偽陽性で通る。
- 反証仮説C: 「4段伝搬漏れはない」  
  反証結果: Phase 2I 委譲自体は明示されているが、`total_pnl` 定義との整合が未閉路。

## 指摘事項（番号付き）
1. 重大: `holding_cost_per_day_bps` が `metric="total_pnl"` で fitness に反映されない設計矛盾。`total_pnl` 定義変更（equityベース）か、fitness 経路で明示調整が必要。
2. 中: `test_session_close_drops_pending_open` の期待条件が弱く、pending open 抜け道を十分に検出できない。`trade_count==0` などの強い条件に要修正。
3. 中: `run_backtest` が絶対制約チェック前に `deposit` するため、`ValueError` 時に broker 状態が副作用汚染される。
4. 中: `BacktestConfig.__post_init__` に `max_spread_bps >= 0` 検証がなく、設定ミスで全 open reject を招く余地がある。
5. 軽中: `fitness.py` の `try/except` が広く、設計ミス（例: strategy 初期化失敗）と runtime 失敗の粒度分離が曖昧。

## 次ラウンド要求（NEEDS_REVISION の場合）
- `holding cost` を `total_pnl` 系 fitness に確実反映する設計を明文化（式・責務・変更ファイルを明示）。
- `tests/backtest/test_engine_clause.py` の session close/pending open 検証条件を強化。
- `run_backtest` の副作用順序（validate before deposit）を修正。
- `BacktestConfig` の spread バリデーション方針を追加。
- `evaluate_genome` の `try/except` スコープ境界を明示（何を system_failure とみなすか定義）。