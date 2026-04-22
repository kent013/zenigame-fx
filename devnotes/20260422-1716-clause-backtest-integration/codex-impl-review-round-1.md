**本分析の前提**
- 提供された差分と提示テスト結果のみを根拠にレビューしました（コマンド実行・書き込みは未実施）。
- `detailed-design.md` 本文は未提示のため、依頼文に明記された Round 1/2 論点を設計要求として照合しました（C1準拠の前提）。

**Facts**
- `BacktestConfig` に `max_spread_bps / holding_cost_per_day_bps / session_close_utc_hours / bar_minutes` が追加され、負値・範囲バリデーションが実装済み。
- `run_backtest` 冒頭でイントラデイ絶対制約を検証し、`deposit` より前に実行されている（副作用回避）。
- `MockBroker` は前バー `close` spread による open reject（no-lookahead）、session close 時の pending open drop、bar単位 holding cost 控除、`Trade.pnl` への net 反映を実装。
- `sum(Trade.pnl) == final_cash - initial_cash` を holding cost 経路で検証する統合テストが追加されている。
- `ga.fitness.evaluate_genome` は復活し、`system_failure` と `metric_unavailable` のログを分離。
- `grid_search / walk_forward / ensemble / test_engine.py` 側で `session_close_utc_hours={23}` を付与し、既存単日評価の互換を確保。
- テスト結果（333 passed, 1 skipped / mypy, ruff pass）は変更範囲と整合。

**Interpretations**
- 依頼された Round 1/2 論点（holding cost の Trade.pnl 反映、validate 前副作用回避、max_spread 負値 reject、pending open 抜け道閉塞、pnl-cash 不変条件）は実装・テストの両面で満たしています。
- 禁止事項（見かけ値改善、GAハック、live_criteria 緩和、オーバーナイト前提化）に抵触する変更は見当たりません。
- 4段伝搬は本TODO範囲（BacktestConfig まで）としては整合的で、Phase 2I で config/GaConfig 実配線が必要という状態です。

**反証を探した結果**
- 反証候補1: 「validate 前に `deposit` される」→ 実装順で否定。
- 反証候補2: 「holding cost 二重控除で `pnl-cash` 破綻」→ `cash += raw_pnl` と `Trade.pnl=raw-cost` の分離＋テストで否定。
- 反証候補3: 「spread 判定が lookahead」→ `fill_pending` が `mark_to_market` より先で、前バー close 参照となっており否定。
- 反証候補4: 「session close で pending open がすり抜ける」→ 先頭 drop＋同バー strategy open drop の2段で否定。

**指摘事項（番号付き）**
1. 軽微: `session_close_utc_hours` は「時一致」のため、M1では該当1時間すべてが open 抑止対象になります。仕様意図なら問題ありませんが、取引回数への影響が大きいので docs に「1時間窓」明記を推奨します。
2. 軽微: `max_spread_bps / holding_cost_per_day_bps` の config→GaConfig→BacktestConfig→consumer の4段伝搬は未完了（計画通り）。Phase 2I での実配線漏れ監視を継続してください。

**Verdict**
- `APPROVED_WITH_COMMENTS`