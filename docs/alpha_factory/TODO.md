# Alpha Factory TODO

zenigame-fx Alpha Factory の改善タスク一覧。

## Open

| ID | タイトル | テーマ | 概要 | 優先度 | 実装モード | 設計 | 追加日時 |
|----|---------|-------|------|-------|----------|------|---------|
| T079 | T070 DST/holiday → BLOCK_BUCKET_RANGES_UTC 連携完成 | infrastructure | DST/holiday 連携 option 選定 (= A/B/C 議論) | Medium | standalone | [設計](devnotes/20260502-1130-todo-t079-t070-dst-holiday-connect/) | 2026-05-02 13:35 |
| T081 | RunObservabilityReport 9 metric 実値配線 (T080 follow-up、 6 step 内包) | infrastructure | T080a stub → 実値置換 (= AB / Churn / Bypass / Entropy / Feasible / Sel / Inflow / Failure / QF 9 件) | High | standalone | [設計](devnotes/20260502-2206-todo-T081-observability-real-values/) | 2026-05-02 22:11 |
| T082 | TradeRecord.spread_cost / holding_cost 伝搬経路配線 (T078 follow-up) | ga-architecture | Trade(broker) → TradeRecord 変換で値伝搬 + WARN ガード | High | standalone | [設計](devnotes/20260502-2300-todo-T082-spread-cost-propagation/) | 2026-05-02 22:44 |

## Conditional

| ID | タイトル | テーマ | 概要 | トリガー条件 | 昇格時優先度 | 実装モード | 設計 | 追加日時 |
|----|---------|-------|------|------------|------------|----------|------|---------|
