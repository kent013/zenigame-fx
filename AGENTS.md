# AGENTS.md

常に日本語で返答してください。すべての応答、説明、コメントは日本語で行ってください。

## プロジェクト概要

**zenigame-fx** — FX（外国為替）取引システム。為替レート・経済指標・関連ニュースを収集し、シグナル生成から自動売買までを一貫して実行するシステムを構築する。

### 最終目標

短中期の為替変動を捉え、検証可能な取引ルールに基づく自動売買で継続的に利益を獲得する。

### 短期目標

**現状**: プロジェクトは初期段階。`AGENTS.md` / `CLAUDE.md` / `README.md` と `.claude/` 設定のみ存在し、ソースコード・データ基盤・インフラは未整備。

まず最初のマイルストーンとして、姉妹プロジェクト [zenigame](../zenigame)（日本株予測システム）を参考に、FX 取引を実行する仕組みの骨格を実装する。

### フェーズ構成（予定）

- **Phase1**: 価格・通貨ペアDB・キャッシュ（基盤）← 次のステップ
- **Phase2**: ニュース・経済指標取り込みと分類
- **Phase3**: シグナル生成と評価（改善ループ）
- **Phase4**: 取引ルール込みの検証（バックテスト）
- **Phase5**: 売買実行（段階導入：Paper Trading → Live）

## 参照プロジェクト: zenigame

`/Users/ishitoya/repository/zenigame` に日本株を対象とした姉妹プロジェクトがある。以下が参考になる:

- ディレクトリ構成（`src/`, `scripts/`, `docs/`, `devnotes/`）
- Dramatiq + RabbitMQ ベースのタスクキュー設計
- PostgreSQL + Alembic によるデータベース設計
- キャッシュ戦略（diskcache、URL訪問トラッカー）
- Alpha Factory（GA によるシグナル探索）の設計思想
- 運用（systemd、Discord 通知、ログローテート）

**重要**: zenigame と zenigame-fx の**コード共有はしない**。同じ課題に対する実装パターンの参考にとどめ、それぞれ独立したコードベースとして進化させる。

zenigame 側のファイルは `.claude/settings.local.json` の `additionalDirectories` で参照可能にしてある。

## 思考原則 — 全議論に適用

**まず仮説を立てろ。** 何を検証したいのか、なぜそう考えるのか、どうなれば成功と判断するのかを明確にしてから手を動かせ。仮説なき改善はただの試行錯誤であり、結果から学ぶことができない。

探索空間は広い。今いる場所が正しいのか、もう少し先に進むべきか、横に移動すべきか、戻って別の道を探るべきかは、これまでの試行と観察の蓄積からしか判断できない。

**データに真摯に向き合え。** 成果だけでなく、変化、構造の揺らぎ、想定外のパターン — 全てが判断材料になる。数値を見て即座に閾値を弄るな。何が起きているのかを理解し、なぜそうなったのかを考え、どの方向に進むべきかを判断してから手を動かせ。

**先人の知恵を探せ。** 自分たちだけで登る必要はない。乗るべき巨人の肩があるなら乗れ。zenigame の既存実装は最初の巨人の一つである。

**機能の名前に立ち返れ。** 名前はその機能が果たすべき役割を示している。現在の設計がその役割を果たしているか、常に問え。

**仕組みが機能していない段階で値を弄るな。** 閾値チューニングやフィールド追加は、設計の方向性が正しいと確認できてから行え。方向性が間違っているなら、値をいくら調整しても意味はない。設計そのものを見直せ。成果が出なければ早期に見切り、次の仮説へ進め。

### 監査・レビュー時の discipline

- **C1 Design-first**: コードの bug claim を出す前に、設計ドキュメント・devnotes・git 履歴を必ず先に読む。grep だけで「バグ」判定しない
- **C2 X が無い = バグ 禁止**: 関数 Y に識別子 X が無いだけでは bug ではない。別経路での計算を広く探す
- **C3 Collider bias**: フィルタ連鎖の中間集団で取った相関を因果解釈しない。Conditioning set を必ず明示する
- **C4 前提検証**: 分析 chain の先頭に前提を bullet 化し、各前提が verified であることを明示してから下流に進む
- **C5 並列独立性**: 並列 sub-agent が同じ出発点を共有している場合、independent verification ではなく「同じ誤読の N 倍冗長実行」であることを認識する
- **C6 Fact / Interpretation 分離**: 観察事実と解釈を別セクションで書く
- **C7 Sample size**: n<30 の相関は明示的に因果解釈を避ける。n<10 の相関 claim は禁止
- **C8 INCONCLUSIVE**: データ不足は正当な結論。無理に CONFIRMED/REJECTED に寄せない
- **C9 Falsification-first**: Round 1 は「この仮説の反証を探せ」から始める

---

## 開発ルール

### 基本原則

- 冗長な記述より簡潔な記述
- 明確な指示がない限り、設計は概念レベル・方針決定レベルで行う
- 出力は最小限に（大量の出力は避ける）
- ファイルの削除・コピーはコマンドで解決
- dev サーバーは立ち上げない（ブラウザ確認はユーザーが行う）
- 了承を得ない限り、キャッシュは絶対に消してはいけない

### 設計ファイル管理

- 設計時は `devnotes/YYYYMMDD-HHMM-{topic}/` 以下にフォルダを作成して md ファイルを保存
- 新要件が与えられた時は極力同じファイルを修正（別ファイルの場合は元ファイルにリンク）
- 不必要な設計ファイルは削除し、常に最新の設計を維持
- ファイル名に「final」をつけるのは禁止
- タイムスタンプは日本時間（JST）
- **devnotes は必ずコミットすること** — 未コミットの設計ノートを残さない

### 実装

- **uv 必須**: `uv run python script.py`, `uv pip install pkg`
- **外部 API・ライブラリを使う前に必ず MCP で公式ドキュメントを確認**
  - **Context7 MCP**: Python/JavaScript ライブラリのドキュメント検索に使用
  - WebFetch や WebSearch ではなく、MCP サーバーを優先的に使用すること
- 新規スクリプトは `devnotes/` に配置 → 本番確定後に `scripts/` へ移動

### テスト

- pytest 形式で実装
- 外部通信（API、クローラー、LLM）は必ずモック化
- fixtures を活用して共通セットアップをまとめる
- テスト名は**振る舞いを説明する汎用的な名前**にする（日付・セッション固有の識別子を含めない）
- テストは対象モジュールに対応するテストファイルに配置

---

## aux データ pipeline と preflight 運用 (T057 Phase 2)

本番 RUN 前に **`scripts/fetch_aux_data.sh`** を実行して aux データを取得する。wrapper は FRED 10 series (VIXCLS, DTWEXBGS, DGS10, DGS2, T10YIE, GOLDPMGBD228NLBM, DCOILWTICO, PCOPPUSDM, PALLFNFINDEXM, SP500) + EUR_USD/USD_JPY M1 bars + economic events scaffold を一括取得する。

`run_ga.py` 起動時に preflight check が走り、**HARD_REQUIRED** (VIXCLS / DTWEXBGS / EUR_USD_M1 / USD_JPY_M1) が不足すると fail-closed (override: `--allow-aux-missing`)。**SOFT_REQUIRED** (Gold / WTI / Copper / commodity / SP500) は WARN log のみで safe default 経路に落ちる。

look-ahead bias 防止: `macro_index_daily.effective_from_utc` 契約 (daily +24h / 月次 +35d) で、`bar.bar_time >= effective_from_utc` を満たす obs しか forward-fill しない。詳細: `docs/alpha_factory/runbook.md` § 6 / `devnotes/20260427-2234-aux-data-loader-phase2/`。

---

## calibrate-gate と state file 経由の自動適用 (T054)

`scripts/alpha_factory/calibrate_gate.py` は Stage A threshold 決定時に以下を実行:
1. `config/alpha_factory/default.yaml` の `stage_gate.stage_a.threshold` を atomic 書き戻し
2. `reports/calibrate-gate/history.jsonl` に cross-run contamination guard 用 metadata 付き record を append (`schema_version=1`, `base_config_hash`, `full_config_hash`, `dataset_span`, `instrument`, `stage_gate_version`, `applied_from_run_id`)

`run_ga.py` 起動時、優先順位 `CLI > history > yaml` で effective threshold を確定:
- CLI: `--stage-a-threshold X` (明示指定、最優先) → `source="cli"`
- history: 最新適用可能 record (`base_config_hash` 一致 + `decision in (tighten, loosen)` + isfinite + range 内) → `source="history"`
- yaml: `default.yaml` の値 (initial seed) → `source="config"`

yaml を chore commit で reset しても history が新しければ history 値が effective になる (cross-run 一貫性)。startup 時に必ず `stage_gate.effective_threshold stage_a_threshold=X source={config|history|cli}` log を出力する。

詳細: `docs/alpha_factory/stage-gates.md` § "T054: state file 経由の自動適用".

---

## Stage A/B disjoint 化と Stage Partition Guard (T087)

`run_ga.py` は dataset を以下の 3 区間に時系列上 disjoint に分割する:

- Stage A: `[dataset.end - stage_a_window, dataset.end)` (GA fitness 評価対象、 末尾固定)
- Stage B: `[dataset.start, dataset.end - stage_a_window)` (fold WF + IS monitor、 Stage A 期間を除外)
- Stage C holdout: `[dataset.end, dataset.end + stage_c_holdout_days)`

起動時 `stage_partition_guard.validate_stage_partition` が以下を fail-closed で検証 (escape hatch なし):

- B-0 入力健全性 (non_empty / UTC tz / not null / monotonic / unique-within-stage)
- B-1 partition 整合性 (chronological order 3 条件 + exact timestamp disjoint 3 条件)

旧 `stage_windows.allow_stage_c_fallback_slice` は廃止。 holdout が DB から取得できない場合は常に RuntimeError。test fixture で synthetic holdout が必要な場合は test-only helper で `LaneBarsBundle` を直接構築する。

`STAGE_GATE_VERSION` は `v4_stage_b_disjoint` に bump 済み (旧 `v3_stage_b_fold_min_trade_count` 期の calibrate-gate history は cross-run guard で誤適用されない)。

詳細: `docs/alpha_factory/stage-gates.md` § "Stage A/B disjoint 契約 (T087)" / `docs/alpha_factory/runbook.md` § 4-1。

---

## T099 cycle 22: Stage B gate `profit_safe_pfr` opt-in (2026-05-13 improve-cycle)

`StageGateConfig.stage_b_gate_kind: Literal["legacy", "profit_safe_pfr"]` で Stage B gate を切替可能化:

- `legacy` (default): 現行 `median_oos_sharpe + positive_fold_ratio` AND
- `profit_safe_pfr`: 4 条件 AND (`pfr_eff>=0.4` ∧ `median_oos_total_pnl>=0` ∧ `sum_oos_total_pnl>=0` ∧ `n_fold_effective>=20`) + `oos_total_pnl_unavailable` fail-closed

CLI override: `scripts/alpha_factory/run_ga.py --stage-b-gate-kind profit_safe_pfr`。

起動時に `stage_gate.stage_b_gate_kind kind=X profit_safe_pfr_threshold=0.4 profit_safe_pfr_min_n_fold=20` log を出力する。`compute_base_config_hash` に 3 field 反映されているため、gate kind 切替時に過去 history record の calibrate-gate threshold が誤適用されない。

根拠: archive 実測 Spearman ρ(median_oos_sharpe → trade_sharpe_stage_c)=-0.361 (curve-fit 逆予測)、Run 74 で Stage B 通過 96 個体全例赤字。

### warmstart pool (T101)

GA 初期集団に既知 mission/Stage-C 個体を注入し、mission 個体を **seed 非依存に保持** する再現性確保機構 (seed-locked 探索への対処)。評価関数・閾値・selection は不変。

- `GAConfig.warmstart_ratio: float = 0.0` (default 0.0 = 完全行動不変)、`warmstart_motif_archive: str | None`。
- CLI: `scripts/alpha_factory/run_ga.py --warmstart-ratio 0.1 --warmstart-motif-archive .cache/alpha_factory/runs/genomes_run_XXX.parquet`。
- motif 抽出: archive から `stage_c_pass==True AND total_pnl>=20000` を mission_score 降順で最大 64 件。初期集団の先頭 1 個体は最良 motif の非 mutate アンカー (厳密保持)、残りは mutate 派生。
- `warmstart_ratio=0.0` で initialize は random_genome のみ (rng 消費順・population 完全不変)。archive 不在/該当 0 は fail-soft (warmstart なしで継続)。

詳細: `docs/alpha_factory/stage-gates.md` § "T099 cycle 22: Stage B gate profit_safe_pfr opt-in" / `devnotes/20260513-2007-fx-improve/detailed-design.md` (Codex Round 3 APPROVED)。

### NSGA-II selection 配線 (T111/T112、Phase2 step3/5a)

GA 選択を**単一目的 tournament から多目的 NSGA-II へ置換**し、seed variance / モノカルチャー収束に対処する (default OFF で bit-exact)。

- **T111 (step3)**: Stage B pooled fold-CV (OOS) から NSGA-II 用 Pareto 3軸 (net_pnl / max_dd / mission_inf_gap) を `ParetoFeaturesLite` として算出 (`src/alpha_factory/pareto_features.py`)。観測専用 (sidecar `pareto_*` 6列)、bit-exact。fold artifact 直消費 pooling (period 再フィルタ/再 backtest なし)、完全 no-raise。
- **T112 (step5a)**: `_breed_next_gen` の parent 選抜を NSGA-II (non-dominated sort + crowding) に置換。`GAConfig.nsga2_selection_enabled: bool = False`、CLI `--nsga2-selection`。
  - 軸は archive `pareto_b_*` 4列 (net_pnl/pooled_dd/mission_inf_gap/axis_usable) 経由で breed cache へ (payload→collect_stage_b→archive→`_update_cache`→`IndividualCacheEntry` の 4段伝搬)。
  - NSGA-II 入口は `nsga2_selection.select_from_pareto_features` (低レベル non_dominated_sort/crowding を再利用、IndividualEvaluation 契約を経由しない)。parent_pairs 長 = population_size、elite copy なし (front-1 を parent pool 優先)。
  - parent 選抜 rng = `make_selection_seed(run_id, gen)` で deterministic、crossover/mutate は GA 主 rng。
  - eligible (pareto_axis_usable ∧ 3 scalar finite) が 0 の世代は従来 tournament に fallback。`nsga2_selection_enabled=False` で legacy 経路と完全 bit-exact (Pareto 列は selection_score 不関与)。
- 次段 (T113, step5b): CPPS archive injection (`cpps_archive_enabled`、未実装)。

詳細: `devnotes/20260521-0925-nsga2-cpps-selection-wiring/` (概念/詳細設計、Codex 7round APPROVED) / `docs/alpha_factory/diagnostics-sidecar.md` (ParetoFeaturesLite 列)。

### cross-pair multi-pair shadow 有効化 (T114)

mission 個体の**汎化** (多ペア通用) を観測可能にする。cross-pair (ii-lite) は単一銘柄 run では構造的にスキップ (anchor 必須) されるため、`ANCHOR_PAIRS[target]` の holdout を本番 parallel 経路の `LaneEvalContext.cp_inputs` に供給して shadow 実走させ、`ii_lite_pass` を計測。graduation は cross_pair.passed で自然機能 (Stage C passed 非介入)。

- `CrossPairConfig.enable: bool = False` (default OFF = 現状 cross-pair skip、挙動完全不変)。CLI: `scripts/alpha_factory/run_ga.py --cross-pair-enable`。
- enable 時、target の `ANCHOR_PAIRS` 2 anchor (例 EUR_JPY→EUR_USD+USD_JPY) の holdout を holdout-only loader でロード (coverage fail-closed)。`cross_pair_runtime_mode` = `skipped_disabled` (enable=False) / `skipped_target_not_configured` (ANCHOR_PAIRS 未定義 target) / `enabled`。
- cross_pair mode は shadow 維持 (graduation 強制は別途)。汎化の壁を ii_lite_pass 分布で定量化する観測機構。

### cross-pair in-loop selection pressure (T115)

R87 で cross-pair 汎化 0/599 (EUR_JPY mission 個体は in-sample 過学習) と判明。根本原因は GA 選択が in-sample sharpe のみで cross-pair が最終評価でしか効かず**汎化探索圧ゼロ**。これに対し、真の cross-pair シグナル `CrossPairResult.metrics["aggregate_fitness"]` (= mean_sharpe − λ·std) を GA 選択キーに弱く反映し汎化方向へ探索圧をかける。新規 eval なし (既計算シグナルを伝搬)。

- `CrossPairConfig.selection_pressure: bool = False` (default OFF = selection_score 10-tuple 不変・bit-exact)。`cross_pair.enable=True` 前提。CLI: `--cross-pair-selection-pressure`。`selection_pressure_margin_threshold` (default 0.0)。
- 伝搬: cross-pair payload → archive 列 `cross_pair_aggregate_fitness` → `IndividualCacheEntry.cross_pair_margin` → `_selection_key` (ON 時のみ fold_robust と fitness_pen の間に `int(margin>threshold)` tie-break 挿入で 11-tuple)。
- effective 判定は `_resolve_cross_pair_selection_pressure(cfg)` 単一 helper (selection_pressure=False / enable=False / nsga2_selection_enabled=True で no-op)。summary に `selection_key_schema` (v3_3/v3_4) + effective/reason 記録。
- 閾値緩和でなく加点。aggregate_fitness は Structural シグナル (Reactive Parametric でない)。

---

## cycle 23: live_criteria.sharpe 単位整合性修正 (2026-05-14 improve-cycle)

cycle 22 (Run 75 profit_safe_pfr) で発見した **Critical bug**: `scripts/alpha_factory/run_ga.py` の `_check_live_criteria` が **trade-level `trade_sharpe_raw` を annualized `sharpe_min=1.0` と直接比較**していた (= summary.json 出力経路の単位不整合)。 一方 `evaluate_stage_c` 内部判定は `_annualize_trade_sharpe` で年率化後に比較しており、 **二重基準** が存在。 結果として「Stage C pass=217 だが summary.live_criteria.all_pass=False」という矛盾。

修正後の `_check_live_criteria`:
- keyword-only 引数 `holdout_days` / `stage_a_window_days` を必須化
- sharpe 比較値の優先順位: `trade_sharpe_stage_c` (Stage C scope) > `trade_sharpe_raw` (Stage A scope) fallback
- 各 sharpe の annualize window: stage_c は `holdout_days`、 raw は `stage_a_window_days` (Codex Round 1 Warning 反映)
- `_annualize_trade_sharpe` で年率化、 SSOT 比較値は annualized
- 出力 `checks["sharpe"]`: `value` (annualized) / `value_trade_level` (元値) / `sharpe_source` / `annualize_window_days` / `sharpe_calc_version="v2_trade_level_annualized_live"` (summary 内専用、 archive 列は変更なし)

retroactive 検証 (`scripts/alpha_factory/audit_live_criteria_retroactive.py`): Run 75 で **mission_candidates=217 / Stage C pass=217**、 top annualized sharpe **5.02**。 18 RUN 累積 mission 0/19 は完全に bug 由来の過小評価。

`generate_run_report.py` に新セクション追加:
- `## KPI 分離 (cycle 23 C2)`: graduation_count / stage_c_pass_count / mission_candidate_count を並列表示 (single-instrument では graduation 構造的 0 で KPI 誤読する問題対応)
- `## trade_count 境界張り付き分析 (cycle 23 C4)`: live_criteria.trade_count_min 狙い撃ち最適化の構造把握 (= 境界張り付き群 vs 非張り付き群の median PnL / sharpe 比較)

詳細: `docs/alpha_factory/stage-gates.md` § "cycle 23: live_criteria.sharpe 単位整合性修正" / `devnotes/20260514-0033-fx-improve/detailed-design.md` (Codex design-review Round 1 APPROVED)。

---

## T108: backtest engine の numba njit kernel 化 (wall-time 削減)

`src/backtest/engine.py` の `run_backtest` は、preflight を満たす場合に broker per-bar simulation を **numba njit kernel** (`src/backtest/_sim_kernel.py::simulate` + columnar scaled-int 表現 `src/backtest/columnar.py`) で実行する。**selection-invariant performance-only change** であり GA 結果は bit-identical (seed=9999 smoke で best=g2_i2 / fitness_pen=-0.02894014223533147 不変)。

- **数値表現**: price=PRICE_SCALE(1e5) / cash・equity=CASH_SCALE(1e8) の scaled-int64。signal/composite は既に float64 (T030/T053) で本件不変、Decimal 厳密性は broker に閉じる。約定数に逆流する 2 gate (margin call / spread filter) は商を作らず整数 cross-multiply で判定 (finite-granularity 証明で Decimal と bit-identical)。
- **preflight (kernel 適用条件)**: `holding_cost_per_day_bps==0` / `maintenance==100` / `max_spread が整数 bps` / `leverage==3` / DslStrategy (prepared path) かつ session_close なし。**不成立は現行 Decimal engine (`_run_backtest_decimal`) にフォールバック** (observable behavior 不変)。
- **overflow**: kernel 内 runtime sentinel (積/加算の乗算前ガード) で検出し `STATUS_OVERFLOW` を返すと caller がその backtest だけ Decimal engine で再実行する (`backtest.kernel_overflow_fallback` ログ)。静的 hard gate は使わない。
- **検証**: `tests/backtest/test_sim_kernel_parity.py` が kernel vs Decimal を同一入力で trades 全フィールド・equity 配列・broker cash・active_clause_indices まで bit 比較 (long/short/EOD/session/spread/margin/time_stop/同一bar競合/overflow-fallback を網羅)。`tests/backtest/test_sim_kernel.py` が overflow sentinel を直接検証。

詳細: `devnotes/20260520-1949-handoff-backtest-engine-numba/` (概念設計 Codex Round 2 / 詳細設計 Codex Round 4 APPROVED) / `devnotes/20260520-2247-todo-T108/` (impl-review Round 4 APPROVED)。

---

## .claude/ 設定の現状

`.claude/skills/` 配下は以下の三層構成:

1. **`zenigame-fx-*`**（移植・新設済み）: zenigame-fx 環境で動く正式 skill 群（autopilot, codex-vscode, codex-review, alpha-design, todo-add, todo-close, implement, update-docs, improve-cycle [full Phase 2 architecture orchestrator], analyze-run, run-report, run-alpha-factory, plan-and-design 他）
2. **`zenigame-*`**（流用そのまま）: zenigame 由来でまだ移植中・参考保持の skill 群。zenigame-fx 用 inflastructure 整備後に zenigame-fx-* 版へ順次置き換える
3. **`_archived/zenigame-*`**（退避済み）: zenigame 固有インフラ（Dramatiq, systemd, Discord, J-Quants）依存で zenigame-fx では動作しないため `_archived/` プレフィックス配下に退避し、Claude Code の skill 候補一覧から除外（実地検証済み: 2026-04-21）

退避済み 7 件:
- `zenigame-enqueue-task`, `zenigame-manage-alert`, `zenigame-manage-timer`, `zenigame-restart-worker`, `zenigame-troubleshoot-worker`, `zenigame-primitive-ic-eval`, `zenigame-primitive-ic-sync`

復活条件・退避理由は `.claude/skills/_archived/README.md` を参照。

方針:
- 新設の zenigame-fx-* は `zenigame-fx-codex-review` の使命・禁止事項を継承する
- zenigame-* 残存分は zenigame-fx-* 版を整備したタイミングで削除 or `_archived/` 退避
- `.claude/hooks/bash-permissions.py` は汎用的なので残す
- 移植進捗は `devnotes/20260421-1850-fx-skill-port/master-plan.md` を参照

### code-review-graph（構造マップ / blast-radius）

コードベースを Tree-sitter で構造グラフ化し、変更の blast-radius（影響を受ける caller / dependent / test）を MCP 経由で提供するツール。レビュー・リファクタ・デバッグ時に全ファイルを読まず、影響範囲だけを最小コンテキストで読むために使う。

- **導入**: `uv tool install code-review-graph`（`code-review-graph` / `crg-daemon`）。MCP は `.mcp.json`（`uvx code-review-graph serve`）。生成 skill: `review-changes` / `explore-codebase` / `refactor-safely` / `debug-issue`。グラフ実体は `.code-review-graph/`（gitignore 済み）
- **使い方**: コードレビュー・影響調査では grep 全読みの前に MCP の blast-radius / impact を引く
- **hook 排他（重要）**: グラフ更新は ① PostToolUse hook（`.claude/settings.json`、`Edit\|Write\|Bash`）と ② git pre-commit hook の 2 経路で `code-review-graph update` を発火する。並列ツール呼び出しで同時書き込みが起きると、overlay/fakeowner FS（Dev Container）上では SQLite の WAL 排他が壊れ `graph.db` が物理破損する。対策として両 hook を **flock 先勝ち非ブロッキング排他**（lock は必ず `/tmp` 配下、repo パス cksum 由来キー）でラップ済み。flock の無い macOS ホストでは SQLite 内蔵 lock が正常に効くため直接実行にフォールバック
- **破損時の復旧**: `rm .code-review-graph/graph.db*` → `code-review-graph build`

---

## 次のアクション候補

このドキュメントを読んだ時点でインフラはまだ無い。最初のマイルストーンとしては以下のいずれかを想定:

1. **データソース調査**: FX データ取得元の選定（OANDA API、MetaTrader5、Dukascopy、Alpha Vantage 等）
2. **ディレクトリ骨格構築**: `src/` `scripts/` `tests/` `docs/` `devnotes/` と `pyproject.toml`、基本設定ファイル
3. **最小限の価格取得パイプライン**: 1 通貨ペアのヒストリカルデータを取得し PostgreSQL に格納する
4. **バックテスト基盤の設計**: zenigame の alpha_factory を参考にした FX 版 GA / 評価フローの概念設計

進める際は、まず 1 件を `devnotes/YYYYMMDD-HHMM-{topic}/` で概念設計するところから始める。
