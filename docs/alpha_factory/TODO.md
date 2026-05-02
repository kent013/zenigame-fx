# Alpha Factory TODO

zenigame-fx Alpha Factory の改善タスク一覧。

## Open

| ID | タイトル | テーマ | 概要 | 優先度 | 実装モード | 設計 | 追加日時 |
|----|---------|-------|------|-------|----------|------|---------|
| T077 | T058 docstring 改訂 + applied_from_run_id v2 必須化 | infrastructure | HistoryRecord v2 で None 不可 + T058 doc 改訂 | Medium | standalone | [設計](devnotes/20260502-1130-todo-t077-t058-history-record-required/) | 2026-05-02 13:35 |
| T078 | T064 apply_spread_stress 重複解消 + TradeRecord schema 拡張 | ga-architecture | TradeRecord に spread_cost field + skeleton 削除 | High | standalone | [設計](devnotes/20260502-1130-todo-t078-t064-spread-stress-import/) | 2026-05-02 13:35 |
| T079 | T070 DST/holiday → BLOCK_BUCKET_RANGES_UTC 連携完成 | infrastructure | DST/holiday 連携 option 選定 (= A/B/C 議論) | Medium | standalone | [設計](devnotes/20260502-1130-todo-t079-t070-dst-holiday-connect/) | 2026-05-02 13:35 |
| T081 | RunObservabilityReport 9 metric 実値配線 (T080 follow-up、 6 step 内包) | infrastructure | T080a stub → 実値置換 (= AB / Churn / Bypass / Entropy / Feasible / Sel / Inflow / Failure / QF 9 件) | High | standalone | [設計](devnotes/20260502-2206-todo-T081-observability-real-values/) | 2026-05-02 22:11 |

## Conditional

| ID | タイトル | テーマ | 概要 | トリガー条件 | 昇格時優先度 | 実装モード | 設計 | 追加日時 |
|----|---------|-------|------|------------|------------|----------|------|---------|
