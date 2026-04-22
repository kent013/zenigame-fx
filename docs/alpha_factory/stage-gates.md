# Stage Gates

## 目的

Stage A / B / C ゲートの構造・期間・通過条件・ペナルティ運用を一箇所に集約する。実装詳細は `concepts/stage-gate-implementation.md` および後続 TODO で扱う。

## スコープ

- 各 Stage の役割と通過条件の構造
- Stage B での Walk-Forward (WF) パラメータ構造
- 期間延長禁止（禁止事項 #1）の構造的明示
- live_criteria への接続点

数値（窓長・通過率・閾値）は SSOT 参照。期間延長は強い根拠なしに行わない（禁止事項 #1）。

## 用語リンク

本ドキュメントで使用する用語: [Stage A](terminology.md#stage-a), [Stage B](terminology.md#stage-b), [Stage C](terminology.md#stage-c), [Walk-Forward](terminology.md#walk-forward), [IS / OOS](terminology.md#is-oos), [DSR](terminology.md#dsr), [(ii-lite)](terminology.md#ii-lite), [TC](terminology.md#tc)

## 主要定義

### Stage A — Fast Screen

- 短期窓で低コストにスクリーニング
- 複雑度ペナルティ α_A を fitness から控除
- 通過率目標を持ち、過剰通過 / 過少通過を `calibrate-gate` で調整
- 失敗個体は Stage B に進めない

### Stage B — Full IS + Walk-Forward OOS

- 完全 IS 期間でのフィット + WF-OOS 評価の二段
- WF パラメータ構造: `train_days / test_days / step_days / embargo_days`
- 通過条件は **複合 AND**:
  1. median OOS Sharpe ≥ 閾値
  2. 正 fold 比率 ≥ 閾値
  3. DSR ≥ 閾値（Phase 2 では monitor、Phase 3+ で hard）

### Stage C — Live Criteria + Stress + (ii-lite)

- holdout 期間で live_criteria 全条件を AND 評価
- spread × N stress test（コスト悪化耐性）
- trade_count が `[trade_count_min, trade_count_max]` 範囲内
- (ii-lite) 評価（Phase 2 shadow / Phase 6 hard）

### 期間延長禁止

A / B / C いずれの評価期間も「強い根拠なしに延長しない」。延長を提案する場合は概念設計に**反証を含む議論**を要する（禁止事項 #1）。

## SSOT 参照

| 項目 | 参照キーパス（config/alpha_factory/default.yaml） |
|------|--------------------------------------------------|
| live_criteria.sharpe_min | `live_criteria.sharpe_min` |
| live_criteria.total_pnl_min | `live_criteria.total_pnl_min` |
| live_criteria.max_drawdown_max | `live_criteria.max_drawdown_max` |
| live_criteria.trade_count_min | `live_criteria.trade_count_min` |
| live_criteria.trade_count_max | `live_criteria.trade_count_max` |
| Stage A 窓長 / 通過率目標 | Phase 2I で `stage_gate.stage_a.*` 追加予定（未定義） |
| Stage B WF パラメータ | Phase 2I で `stage_gate.stage_b.wf_*` 追加予定（未定義） |
| Stage B 通過条件 | Phase 2I で `stage_gate.stage_b.pass_criteria.*` 追加予定（未定義） |
| ペナルティ α_A / α_BC | Phase 2I で `ga.complexity_penalty.*` 追加予定（未定義） |

## 関連ドキュメント

- [clause-architecture.md](clause-architecture.md) — composite score / max_clause
- [statistics.md](statistics.md) — DSR / 正 fold 比率の計算
- [cross-pair.md](cross-pair.md) — Stage C 内 (ii-lite)
- [migration-triggers.md](migration-triggers.md) — Stage 通過率の崩壊検知
- [concepts/stage-gate-implementation.md](concepts/stage-gate-implementation.md)

## 関連 TODO

- 未着手（Phase 2E: `src/alpha_factory/stage_gate.py`）
