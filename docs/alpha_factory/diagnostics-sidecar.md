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
| `stage_c_gap_class` | string | YES | T109: Stage B→C gap 分類 enum (下記)。Stage C 未評価個体は None |
| `stage_c_base_total_pnl` | float64 | YES | T109: Stage C base(unstressed) holdout total_pnl |
| `stage_c_base_trade_count` | int32 | YES | T109: Stage C base holdout trade 数 |
| `stage_c_stress_pnl_degradation` | float64 | YES | T109: spread×1.5 stress の PnL 劣化量 (base - stress)。stress skip 時 None |
| `stage_c_stress_trade_count` | int32 | YES | T109: stress 評価時の trade 数。stress skip 時 None |
| `pareto_net_pnl_after_cost` | float64 | YES | T111: Pareto f1 (max)。Stage B pooled fold-CV(OOS) の net PnL。Stage B 未評価個体は None |
| `pareto_pooled_dd_per_fold_max` | float64 | YES | T111: Pareto f2 (min, >=0)。per-fold max_dd の max |
| `pareto_mission_inf_gap` | float64 | YES | T111: Pareto f3 (min)。`evaluate_mission_inf_gap(b_pooled_cf)` (Stage B 完結) |
| `pareto_is_feasible_invariant` | bool | YES | T111: 全 fold feasible なら True |
| `pareto_axis_usable` | bool | YES | T111: 軸算出可能 (b_pooled_cf 算出 ∧ 3 scalar finite ∧ feasible) |
| `pareto_source_stage` | string | YES | T111: usable なら "B" (逆流監査用)、未算出は None |

主キー: `(lane_id, generation, individual_name)` (archive と整合)。

> T109 で追加した 5 列、T111 で追加した 6 列 (`pareto_*`) は全て nullable。`DIAGNOSTICS_SCHEMA_VERSION` は 2 のまま据え置く (v2 contract の required field 集合を変えない additive 拡張、`assert_diagnostics_v2` は required field のみ検証)。
>
> **T111 ParetoFeaturesLite** は T112 (NSGA-II selection) が消費する Stage B 完結軸の観測機構。pooled fold-CV(OOS) の per-fold canonical artifact を直消費して算出 (`pareto_features.py`)。selection/gate/judgment/archive は不変 (LOG_ONLY, bit-exact)。`pareto_axis_usable=True ⇒ pareto_source_stage=="B"` を `to_rows` で assert (CI invariant)。`win_rate_min` 欠落 config は 0.45 fallback (stage_gate dual-path と同値)。

### `stage_c_gap_class` enum (T109)

Stage C 評価個体の B→C 汎化ギャップ主因分類。`_derive_stage_c_gap` が base `live_criteria_pass` / `stress` / `reason_codes` から導出 (新規 backtest なし、観測専用、fail-soft)。

| value | 条件 |
|-------|------|
| `pass` | Stage C 通過 |
| `pnl_only` | base live_criteria で total_pnl のみ未達 |
| `count_only` | base live_criteria で trade_count (min/max) のみ未達 |
| `both_pnl_count` | total_pnl ∧ trade_count 両方未達 |
| `sharpe_involved` | sharpe を含む base live_criteria 未達 (上記以外) |
| `mixed` | 上記以外の base live_criteria 未達組合せ |
| `stress_or_other` | base live_criteria 全通過だが stress/intraday 等で不通過 |
| `system_fail` | system_failure / worker_error (実行時障害) |
| `unknown` | payload 不整合 / live_criteria_pass 欠落 (defensive) |

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
- I4: `stage_c_gap_class` が None または `VALID_STAGE_C_GAP_CLASSES` 内 (`to_rows` で assert、T109)
- I5: `pareto_axis_usable=True` なら `pareto_source_stage=="B"` かつ 3 scalar が finite (`to_rows` で assert、T111)

## Phase A スコープ外 (将来 TODO)

- Phase B: コスト分解 (spread/swap/holding cost) の sidecar 拡張
- Phase C: CI invariant ハーネス (`summary.diagnostics.invariant_violations`)
- archive Parquet schema 拡張 (28+ カラム fixed を尊重)
- production GA での invariant penalty (fitness への寄与)

## 変更履歴

- 2026-04-26: T033 Phase A 初期実装。collector + sidecar writer + run_ga 統合 + run-report 拡張 + テスト 28 件。
- 2026-05-21: T111 ParetoFeaturesLite 6 列追加 (NSGA-II selection 用 Stage B 完結軸、観測専用)。`pareto_features.py` の pooled fold-CV 直消費 helper + collector/sidecar 拡張 + stage_gate/swim_lane 配線。default OFF 不要 (観測のみ bit-exact)。Codex design-review 7round + impl-review 3round APPROVED。
