# Alpha Factory TODO (Closed/Obsoleted)

## Closed

| ID | タイトル | テーマ | 優先度 | 完了日時 | Run ID |
|----|---------|-------|-------|---------|--------|
| T001 | DROP 7 zenigame-* skills を _archived/ に退避 | skill-port | High | 2026-04-22 08:26 | 53bbe9a |
| T002 | docs/alpha_factory/ 骨格ドキュメント 10 本作成 | infrastructure | High | 2026-04-22 09:29 JST | 700132a |
| T003 | port-rename-only zenigame-* skill 4 件を zenigame-fx-* に | skill-port | Medium | 2026-04-22 10:24 | 3b5eb5f |
| T004 | FRED ingest 実装 (VIX/DXY/金利日足) | data-ingest | High | 2026-04-22 11:43 | c7d3c59 |
| T005 | OANDA CFD instrument 疎通試験 | data-ingest | Medium | 2026-04-22 13:05 | 1ea6a6b |
| T006 | 統計検定最小セット実装 (DSR/fold sign/block bootstrap) | statistics | Critical | 2026-04-22 14:10 JST | e2434c0 |
| T007 | Clauseベース Genome 構造に再構築 | ga-architecture | Critical | 2026-04-22 15:30 JST | 22ddf7da0baa2e3ff61e06e6232c8d194d3efaa7 |
| T008 | GA operators/random_gen/runner を Clause 対応に再実装 | ga-architecture | Critical | 2026-04-22 17:11 | bf976a1 |
| T009 | backtest engine を Clause DslStrategy に対応 + fitness 復活 | ga-architecture | Critical | 2026-04-22 21:45 | 47c738d |
| T010 | primitives registry + RegistryEvaluator 骨格 | primitives | High | 2026-04-22 22:34 | 25ba841872b2899fa22c7f8403ac8d2e1ea3a09a |
| T011 | Directional primitive 14 個実装 (F1-F14) | primitives | High | 2026-04-23 09:51 | 1e72414 |
| T012 | Modulator primitive 6 個実装 (M1-M6) | primitives | High | 2026-04-23 13:55 JST | a4eb0bf |
| T013 | Pair-specific primitive 12 個実装 (P1-P12) | primitives | Medium | 2026-04-23 15:35 | 4348144d3ab721468c353191ae41877032548c3d |
| T014 | Stage A/B/C gate 実装 + WF folds + live_criteria | stage-gate | Critical | 2026-04-23T18:18:30+09:00 | 0f7aa06 |
| T015 | Genome archive schema + Parquet 書き込み | ga-architecture | Critical | 2026-04-23T19:15:00+09:00 | 39619ec |
| T016 | (ii-lite) cross-pair evaluation shadow 実装 | cross-pair | Critical | 2026-04-23T21:09:57+09:00 | a594c50 |
| T017 | Swim lane manager (Tier 1 + Graduation) | swim-lane | Critical | 2026-04-23 23:20 | fa7824f |
| T018 | run_ga.py 全面改修 (Phase 2 統合) | ga-architecture | Critical | 2026-04-23T23:58:00+09:00 | efaf365 |
| T019 | MockBroker 非 JPY-quote 通貨ペア対応 | infrastructure | High | 2026-04-24 06:57 | 5cde521a6c55d131c08daa14992a398b6ef1d3d2 |
| T020 | skill port: zenigame-fx-analyze-run | skill-port | High | 2026-04-24 07:45 | 819a3aa321e6fada603625b36c07c5b10ae8c1ca |
| T021 | skill port: zenigame-fx-run-report + generate_run_report.py 拡張 | skill-port | High | 2026-04-24 11:38 | ad925d02e4d0f55e3f6f57b695df7e51b99280e5 |
| T022 | skill port: zenigame-fx-plan-and-design | skill-port | High | 2026-04-24 12:35 | 144d797 |
| T023 | skill port: zenigame-fx-run-alpha-factory | skill-port | High | 2026-04-24T13:20:13+09:00 | 3fa0881 |
| T024 | skill rewrite: zenigame-fx-improve-cycle full version (Phase 2 architecture) | skill-port | Critical | 2026-04-24 14:13 | d2e1b90310db2abe95c6c13ea798dade14e9b074 |
| T025 | alpha-sieve OOS validation framework + skill port | cross-pair | Critical | 2026-04-24 16:18 | 76cc5df |
| T026 | post-run-review skill port (BG テーマレビュー) | skill-port | High | 2026-04-24 17:52 | 4c32d3840be91334d4d98d4f06b790c4ba1f8a35 |
| T027 | calibrate-gate port + Stage A threshold 動的調整 | stage-gate | High | 2026-04-24T19:22:48+09:00 | 7f2894e |
| T028 | broker snapshot caching | infrastructure | High | 2026-04-25 02:50 | - |
| T029 | strategy signal cache flatten | ga-architecture | High | 2026-04-25 03:47 | - |
| T030 | bars mid ohlc cache | primitives | High | 2026-04-25 04:41 | - |
| T038 | Sharpe 計算根本修正 Phase 1A: bar-level annualized → trade_sharpe_raw + sample-size guard | stage-gate | Critical | 2026-04-25 18:56 | todo/T038 |
| T031 | regime-participation-constraint Phase 1: trade_count=0 を selection_score feasibility 制約で淘汰 | cross-pair | Critical | 2026-04-25 23:56 | - |
| T035 | stats-completeness-gate-stage-b: Stage B 統計可観測性ハード契約と reason_codes 集計 | statistics | Critical | 2026-04-26 01:46 | - |
| T041 | stage-c-spread-stress-unblock: max_spread_bps を設定して Stage C stress 関門を機能させる | stage-gate | Critical | 2026-04-26 10:42 | - |
| T043 | mission-score-soft-aggregate: live_criteria 4 軸 soft 合算スコアを archive/report に追加 | statistics | High | 2026-04-26 12:39 | - |
| T042 | sharpe-threshold-rescale: live_criteria/StageA/B 閾値を v2 trade-level スケールへ再標準化 | stage-gate | Critical | 2026-04-26 13:15 | - |
| T037 | signal-active-clause-metric: clause 発火カウンタの runtime 計測と archive 反映 | primitives | Critical | 2026-04-26 13:39 | - |
| T034 | risk-no-trade-fitness-guard: no-trade 時の fitness sentinel 一貫化と統合経路テスト整備 | stage-gate | Critical | 2026-04-26 22:37 | - |
| T036 | factor-shadow-plane (FSP) Phase 1: single-instrument 用 daily diagnostic shadow layer | cross-pair | Critical | 2026-04-26 23:11 | - |
| T033 | cost-pnl-ledger-eventsource: PnL/コスト sidecar 出力で Stage A Provenance 分布を可視化 | general | Critical | 2026-04-27 00:09 | - |
| T039 | economic-event-as-of-strict: M4/P10 未来 schedule 漏洩防止 | primitives | Medium | 2026-04-27 00:27 | - |
| T040 | calibrate-gate-drift-monitor: 直近 N Run の threshold/decision 横断観察 | stage-gate | Low | 2026-04-27 00:42 | - |
| T044 | trade-sharpe-overwrite: trade_sharpe_raw 上書き bug 修正 (archive スキーマに stage 別 sharpe 列追加) | stage-gate | Critical | 2026-04-27 10:04 | - |
| T045 | stageb-pnl-negative: Stage B 通過群 total_pnl 全 negative の物理調査 (WF fold dump) | stage-gate | Critical | 2026-04-27 10:10 | - |
| T046 | p10-strict-aux: P10 NADataProximityGate strict_aux 標準化 (常時 1.0 開放を解消) | primitives | High | 2026-04-27 10:13 | - |
| T047 | pair-specific-aux-loader: pair_specific 用 aux data loader 整備 (DXY/VIX/Copper/Gold) | data-ingest | Critical | 2026-04-27 10:16 | - |
| T048 | max-drawdown-zero: max_drawdown=0 多発調査 (equity_curve dump) | statistics | Medium | 2026-04-27 10:20 | - |
| T049 | negative-equity: negative equity warnings 調査 + ストップアウト logic 整備 | infrastructure | Critical | 2026-04-27 10:22 | - |
| T050 | selection-tie-drift: selection_score tie drift 調査 (HHI / 多様性測定) | ga-architecture | Medium | 2026-04-27 10:23 | - |
| T051 | calibrate-monotone-tighten: calibrate-gate monotone tighten 観測 (Run 23-25 drift CLI 集計) | stage-gate | Low | 2026-04-27 10:26 | - |
| T052 | ga-parallel-workers | ga-architecture | High | 2026-04-27 14:32 | - |
| T053 | composite per-bar 計算の Numba JIT 化（dict → ndarray, fused kernel） | primitives | High | 2026-04-27 18:22 | - |
| T054 | Stage A→B Pipeline Health Fix（calibrate 伝搬不全 + Stage B all_folds_unavailable） | stage-gate | Critical | 2026-04-27 20:26 | - |
| T055 | backtest per-bar info ログの throttle（呼び出し完全削除 + 集計サマリ化） | infrastructure | High | 2026-04-27 21:03 | - |
| T056 | negative equity 再発の根本修正（多層防御 + OANDA spec 文書化） | infrastructure | Critical | 2026-04-27 22:18 | - |
| T057 | aux data loader Phase 2 — 実データ取得 + production wiring（FRED + aux_pair_bars + events + preflight + strict 化） | data-ingest | Critical | 2026-04-28 00:31 | - |
| T058 | T058-schema-v2-contract | infrastructure | Critical | 2026-05-01 15:35 | - |
| T059 | T059-epoch-window-manager | infrastructure | Critical | 2026-05-01 17:03 | - |
| T060 | T060-partition-fold-generator | stage-gate | Critical | 2026-05-01 17:48 | - |
| T061 | T061-canonical-five-engine | stage-gate | Critical | 2026-05-01 20:01 | - |
| T062 | T062-mission-inf-gap-engine | ga-architecture | Critical | 2026-05-01 21:11 | - |
| T063 | T063-stage-a-evaluator | stage-gate | Critical | 2026-05-01 21:36 | - |
| T064 | T064-stage-bc-evaluator | stage-gate | Critical | 2026-05-01 22:35 | - |
| T065 | T065-nsga2-core-and-main-selection | ga-architecture | Critical | 2026-05-01 23:10 | - |
| T066 | T066-cpps-fsm-and-archive | ga-architecture | Critical | 2026-05-01 23:54 | - |
| T067 | T067-loop-closure-warmstart-emergency | ga-architecture | Critical | 2026-05-02 00:57 | - |
| T068 | T068-failure-handling | infrastructure | Critical | 2026-05-02 01:56 | - |
| T069 | T069-calibrate-gate-scope | stage-gate | Δ | 2026-05-02 02:14 | - |
| T070 | T070-backtest-engine-extension | infrastructure | Critical | 2026-05-02 02:47 | - |
| T071 | T071-observability | infrastructure | Critical | 2026-05-02 03:38 | - |
| T072 | T072-DST-holiday-boundary-contract | infrastructure | Critical | 2026-05-02 04:38 | - |
| T073 | T073-audit-layer-DSR-PBO-SPA-scaffold | statistics | Critical | 2026-05-02 05:32 | - |
| T074 | T074-graduation-lane-batch-evaluator-scaffold | swim-lane | None active、 empty archive 業務不足扱い、 recent-first head N) / GraduationTriggerEvaluation (4 status / cross-field invariant / partial pass diagnostic 保持) / MultiPairAggregationSketch (status='not_implemented' 固定、 数値 field なし、 T073 SSOT 継承)。 6 batch pair = frozenset (= synthesis § 11.2 厳密準拠、 T064 STAGE_C_ANCHOR_PAIR ∪ STAGE_C_SHADOW_PAIR_LIST 集合等価)。 LANE_PARALLELISM=1 (synthesis § 11.2)。 recent_epochs_with_mission_pass_required は caller 引数 (Phase 1 で定数化しない)。 既存 swim_lane / archive / cross_pair touch しない (= 純ライブラリ + early gate ではない)。 collider bias 規範 (T072 / T073 継承) は T074 で判定しない、 Phase 2 で T071 経由 stratified audit。 robust 系 aggregation は synthesis_schema_version>=22 まで Literal 追加禁止。 Phase 2 で run_ga.py が唯一の SSOT adapter (= 同一 archive snapshot 単一 transaction、 案 A snapshot DTO 推奨)。 batch 系 dataclass (GraduationBatchInput / GraduationBatchReport) は Phase 4 で導入 | 2026-05-02 06:12 | - |
| T075 | T075-bigbang-cleanup-smoke | infrastructure | config | 2026-05-02 07:10 | - |

## Obsoleted

| ID | タイトル | テーマ | 優先度 | 廃止日時 | 理由 |
|----|---------|-------|-------|---------|------|
| T032 | signal-eval-consistency-fix | primitives | Critical | 2026-04-26 01:30 | superseded by T031 (selection_score feasibility added in cycle 1, T032 design content fully overlaps) |
