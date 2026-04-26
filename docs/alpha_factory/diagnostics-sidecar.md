# Stage A Diagnostics Sidecar (T033 / Phase A)

**TODO**: T033 (cost-pnl-ledger-eventsource Phase A)
**実装**:
- [`src/alpha_factory/diagnostics_collector.py`](../../src/alpha_factory/diagnostics_collector.py)
- [`src/alpha_factory/diagnostics_sidecar.py`](../../src/alpha_factory/diagnostics_sidecar.py)
**設計**: `devnotes/20260425-0937-cost-pnl-ledger-eventsource/` (Round 4 APPROVED)

## 目的

Run 9 で `trade_count > 0 ∧ archive.total_pnl == 0.0` が観測された問題への対応。

archive Parquet では Stage A 段階で `total_pnl` が転記されない設計のため、Stage A で落ちた個体は `archive.total_pnl == 0.0` のように見えてしまう。これが
- (a) Stage A 投影仕様 (落ちた = まだ書かれていない)
- (b) 実 PnL=0 (シグナル不発で trade なし)
- (c) コスト過大計上

のどれによる 0 なのか、post-RUN 分析で切り分けが困難だった。

**FSP は archive Parquet schema を touch せず、sidecar Parquet として観測情報を出力**する (北極星制約: archive 28+ カラム fixed schema を尊重)。

## アウトプット

| パス | 内容 |
|------|------|
| `reports/run-reports/run-{N}/diagnostics/stage_a_provenance.parquet` | per-individual Stage A diagnostics |
| `summary.json::diagnostics_sidecar` | 上記 sidecar への相対 path (書き込み成功時のみ) |

## sidecar Parquet schema (`STAGE_A_PROVENANCE_SCHEMA`)

| 列 | 型 | nullable | 意味 |
|----|----|---------|------|
| `lane_id` | string | NO | Tier1 lane id (`tier1_{instrument}` etc.) |
| `generation` | int32 | NO | 世代番号 |
| `individual_name` | string | NO | genome name |
| `metric_stage` | string | NO | post-hoc 確定 enum (下記) |
| `trade_count` | int32 | NO | Stage A backtest 中の trade 数 |
| `total_pnl_stage_a` | float64 | NO | Stage A backtest 中の total_pnl (NaN/Inf は 0.0 に正規化) |
| `sharpe_stage_a` | float64 | YES | trade_sharpe_raw (None = 計算不能) |
| `stage_a_pass` | bool | NO | Stage A 通過 |
| `stage_b_pass` | bool | YES | None = 未評価 |
| `stage_c_pass` | bool | YES | None = 未評価 |

主キー: `(lane_id, generation, individual_name)` (archive と整合)。

### `metric_stage` enum

「到達した最高通過段」(pass-based)。`DiagnosticsCollector.derive_metric_stage` で flush 時に決定。

| value | 条件 |
|-------|------|
| `stage_a_only` | Stage A 不通過 |
| `stage_a_evaluated` | Stage A 通過、Stage B 未評価 / 不通過 |
| `stage_b_evaluated` | Stage B 通過、Stage C 未評価 / 不通過 |
| `stage_c_evaluated` | Stage C 通過 |

## ライフサイクル

1. `run_ga.py` で run-level `DiagnosticsCollector()` を生成
2. `LaneManager(diagnostics_collector=...)` に optional 渡し
3. 各 stage 評価点で `record_stage_a/b/c` を呼ぶ (collector が None なら no-op)
4. GA 完了時 `write_stage_a_provenance(collector, path)` で flush
5. 書き込み成功時のみ `summary.json::diagnostics_sidecar` に相対 path を記録
6. `generate_run_report.py` が sidecar を optional で読み「Stage A provenance 分布」セクションを出力 (sidecar 不在時は "not available")

## 北極星制約・禁止事項チェック

| 禁止事項 | 該当性 |
|---------|------|
| 1. 評価期間延長 | 該当なし (post-RUN observability) |
| 2. 見た目の数値改善 | 該当なし (archive 観測のみ追加、live_criteria/fitness 不変) |
| 3. GA hack | 該当なし (selection / breed には影響無し) |
| 4. live_criteria 緩和 | 該当なし |
| 5. 過剰な複雑化 | Phase A は sidecar diagnostics に限定 |
| 6. 取引回数削減 | 該当なし |
| 7. オーバーナイト前提 | 該当なし |
| 8. archive スキーマ伝搬漏れ | **archive schema は touch しない (sidecar 別 Parquet)** |

## fail-open 契約

- `write_stage_a_provenance` の I/O 失敗時は warning ログのみ、GA は完走する
- summary.json の `diagnostics_sidecar` field は **書き込み成功時のみ** 出力 (consumer は missing field を無視できる)
- run-report は sidecar 不在時に「not available」明記 (固定セクション、契約ぶれ回避)

## CI invariant

- I1: sidecar 行数 == backtest 評価された個体数
- I2: `metric_stage` の値が enum 内 (`to_rows` で assert)
- I3: `total_pnl_stage_a` が finite (NaN/Inf は collector で 0.0 に正規化)

## Phase A スコープ外 (将来 TODO)

- Phase B: コスト分解 (spread/swap/holding cost) の sidecar 拡張
- Phase C: CI invariant ハーネス (`summary.diagnostics.invariant_violations`)
- archive Parquet schema 拡張 (28+ カラム fixed を尊重)
- production GA での invariant penalty (fitness への寄与)

## 変更履歴

- 2026-04-26: T033 Phase A 初期実装。collector + sidecar writer + run_ga 統合 + run-report 拡張 + テスト 28 件。
