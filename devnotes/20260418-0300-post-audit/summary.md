# Post-Audit 記録 — 多角的監査と Codex 議論の反映

**作成**: 2026-04-18 03:00 JST
**監査方針**: AGENTS.md § 監査 discipline（C1 Design-first / C2 X 欠如 ≠ バグ / C6 Fact/Interpretation 分離 / C7 n<30 不因果 / C9 反証先行）

---

## 監査体制

Claude 側で 4 並列監査（領域分担で C5 独立性確保）、続いて Codex（`codex-vscode exec`）で findings の検証と横断レビューを実施。

| Audit | 担当領域 |
|-------|---------|
| 1 | broker / backtest / metrics（金融計算） |
| 2 | dsl / ga（式木評価 & 進化） |
| 3 | api / paper_trading / ingest / db / config（IO 運用） |
| 4 | grid / walk-forward / ensemble / events / strategies / docs（残領域） |

---

## 適用した修正（コミット順）

### P0

- **[ef90489]** `fix(dsl)`: `DslStrategy.on_bar` の warmup 境界 `<=` → `<`。warmup=20 で初信号が 21 本目から出ていた off-by-one を解消
  - 影響範囲: DslStrategy のみ。手書き戦略（Bollinger / MA Crossover / RSI / Donchian）は独立の境界処理で同型バグなし

### P1

- **[0b5bc0a]** `fix(oanda)`: `OandaClient.__init__` で空文字列 token / account_id を reject。設定未記入時に 401 で初めて露見する動作を fail-fast に変更
- **[980caa7]** `fix(paper_trading)`: `LiveBarFeed`
  - 例外握り潰しを撤廃。`OandaAuthError` は即時 raise、transient のみ warning、未知例外は error → re-raise
  - polling count を動的化（前回 yield からの経過分 + buffer、上限 500）

### P2

- **[7ab4951]** `fix(dsl)`: `max_lookback` のネスト指標合成。`sma(sma(close,5),3)` は 5 ではなく 7。GA が生成するネスト式で warmup が不足し、部分窓計算で fitness に歪みが入る可能性を排除
- **[f76d65b]** `test(oanda)`: `TokenBucket` の並列アクセス・burst rate limit テストを追加（実装は lock 済だったがテスト未整備だった）

### P3（本コミット）

- **docs**: 本文書（post-audit summary）、runbook / 各 Phase 詳細設計の注釈追記

---

## False-positive として却下した項目

Codex レビューで C2（X 欠如 ≠ バグ）違反と判定された項目:

- **4xx retry 対象外 = バグ**: 設計意図通り。tenacity は 5xx / rate limit / transport のみ retry
- **IfThenElse の型安全性弱い**: 現状のサンプル / ランダム生成では未使用。型不整合は evaluate が TypeError で露見する
- **Sortino `len(downside) < 2` で None**: 保守的判断として妥当（分散が定義できない）
- **MockBroker の margin_level `<` 判定**: 設計書 §5.3 通り。100% ちょうどで発火させるなら業者別の 2 段階制御（Phase 5）で扱う

---

## 次フェーズ（Phase 5 以降）に先送りした事項

- 4xx のカスタム例外階層化（OandaBadRequestError 等）
- Postgres 実 DB UPSERT テスト（testcontainers 活用）
- docker-compose healthcheck retries 調整
- swap 計算の実装（OANDA financing の正確な式）
- quote ≠ home 通貨の換算レート（USD_JPY 以外を扱う段階）
- DSL の `of=Var` 最適化経路（性能上の実害が観測されたら）

---

## 各設計書への補足メモ（差分管理）

- [Phase 2 detailed-design](../20260417-2300-phase2-detailed-design/detailed-design.md): § 5.3 の「`< threshold` で発火」は設計意図（本文に明記済み）
- [Phase 4a detailed-design](../20260417-2345-phase4a-grid-search/detailed-design.md): Bollinger は `statistics.pstdev`（母分散）を採用。標本分散ではない点を本サマリで明記
- [Phase 4b detailed-design](../20260418-0000-phase4b-walk-forward/detailed-design.md): `overfit_score` は `train_total > 0` のときのみ定義（損失でのトレーニング結果は意味を成さない）。`step_days > test_days` は fold に隙間を作るため非推奨
- [Phase 4f detailed-design](../20260418-0130-phase4f-dsl/detailed-design.md): `of = Var("close")` 最適化経路は未実装（現段階では実害なし）
