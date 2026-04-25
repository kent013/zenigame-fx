# Alpha Factory TODO

zenigame-fx Alpha Factory の改善タスク一覧。

## Open

| ID | タイトル | テーマ | 概要 | 優先度 | 実装モード | 設計 | 追加日時 |
|----|---------|-------|------|-------|----------|------|---------|
| T032 | signal-eval-consistency-fix | primitives | [r:sq] eval-consistency-fix | Critical | incremental | [設計](devnotes/20260425-0939-signal-eval-consistency-fix/) | 2026-04-25 09:58 |
| T033 | cost-pnl-ledger-eventsource: PnL/コスト sidecar 出力で Stage A Provenance 分布を可視化 | general | [r:ce] cost-pnl ledger | Critical | incremental | [設計](devnotes/20260425-0937-cost-pnl-ledger-eventsource/) | 2026-04-25 16:17 |
| T034 | risk-no-trade-fitness-guard: no-trade 時の fitness sentinel 一貫化と統合経路テスト整備 | stage-gate | [r:rm] no-trade fitness guard | Critical | incremental | [設計](devnotes/20260425-0937-risk-no-trade-fitness-guard/) | 2026-04-25 16:17 |
| T035 | stats-completeness-gate-stage-b: Stage B 統計可観測性ハード契約と reason_codes 集計 | statistics | [r:ro] stats completeness gate | Critical | incremental | [設計](devnotes/20260425-0937-stats-completeness-gate-stage-b/) | 2026-04-25 16:17 |
| T036 | factor-shadow-plane (FSP) Phase 1: single-instrument 用 daily diagnostic shadow layer | cross-pair | [r:ra] FSP single-instr daily | Critical | incremental | [設計](devnotes/20260425-0956-factor-shadow-plane-single-instr/) | 2026-04-25 16:17 |
| T037 | signal-active-clause-metric: clause 発火カウンタの runtime 計測と archive 反映 | primitives | [r:sq] active-clause metric | Critical | incremental | [設計](devnotes/20260425-0958-signal-active-clause-metric/) | 2026-04-25 16:17 |

## Conditional

| ID | タイトル | テーマ | 概要 | トリガー条件 | 昇格時優先度 | 実装モード | 設計 | 追加日時 |
|----|---------|-------|------|------------|------------|----------|------|---------|
