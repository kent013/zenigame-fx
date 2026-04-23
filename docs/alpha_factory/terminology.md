# 用語集 (Terminology)

## 目的

zenigame-fx Alpha Factory の全ドキュメントから参照される横断用語集。各用語の初出は必ず本ファイルの anchor へリンクする。

## スコープ

本 Alpha Factory 固有の概念・略語・統計指標を収録する。一般的な金融用語（Sharpe, Drawdown など）は収録しない。

## 用語リンク

本ドキュメントが SSOT のため、他ファイルへのリンクは不要（本ファイルへの被リンク側のみ）。

## 主要定義

### Clause

`<a id="clause"></a>` Clause — ゲノムを構成する最小の判断単位。`directional × local_gate × weight` の 3 要素で 1 clause が構成される。複数 clause を `composite score` で合成して売買判定に使う。Jordan & Jacobs (1994) Mixture of Experts の系譜。

### Composite Score

`<a id="composite-score"></a>` Composite Score — 複数 clause を加重合成して得られる最終判断スコア。形: `Σ(cw_k × cs_k) / Σ|cw_k|`。ヒステリシス付き閾値判定でエントリー・エグジットを出す。

### Directional

`<a id="directional"></a>` Directional Signal — 方向性（long / short）を決める signal 群の加重和。形: `Σ(w_i × x_i) / Σ|w_i|`。

### Local Gate

`<a id="local-gate"></a>` Local Gate — 同じ clause 内の directional signal を閉じる / 開くゲート関数群。`[0, 1]` sigmoid 有界。

### Modulator

`<a id="modulator"></a>` Modulator — local_gate / global_gate を構成するプリミティブ群（ATRRegimeGate / SessionGate / VIXRegimeGate 等）。方向性を生まず、他 signal の効力を調整する。

### SignalConfig

`<a id="signal-config"></a>` SignalConfig — `src/dsl/genome.py` の frozen dataclass。`name`（primitive ID）+ `weight`（directional: [0.1, 2.0] / gate: [-2.0, 2.0]）+ `params`（primitive 固有パラメータ辞書）の 3 フィールド。生成時に `__post_init__` で `params` を defensive copy する。

### ClauseConfig

`<a id="clause-config"></a>` ClauseConfig — `src/dsl/genome.py` の frozen dataclass。1 clause を表現する `directional: tuple[SignalConfig, ...]` + `local_gate: tuple[SignalConfig, ...]` + `weight: float` の 3 フィールド。

### PositionConfig

`<a id="position-config"></a>` PositionConfig — `src/dsl/genome.py` の frozen dataclass。`entry_threshold`（θ_on）/ `exit_threshold`（θ_off）/ `max_pos` / `time_stop_min`。`enforce_consistency` で `entry > exit` を保証。

### RiskConfig

`<a id="risk-config"></a>` RiskConfig — `src/dsl/genome.py` の frozen dataclass。`stop_atr` / `take_atr` の ATR 係数。

### Hysteresis (ヒステリシス)

`<a id="hysteresis"></a>` Hysteresis — Composite Score が `entry_threshold` (θ_on) を超えてエントリー、`exit_threshold` (θ_off) を下回って決済する 2 閾値方式。`θ_on > θ_off` 必須（enforce_consistency で強制）。チャタリング抑止（Schmitt trigger の金融時系列応用）。

### PrimitiveEvaluator

`<a id="primitive-evaluator"></a>` PrimitiveEvaluator — `src/dsl/strategy.py` で定義される Protocol。`evaluate(bars, idx, signal) -> float` を実装する primitive 評価インターフェース。実装本体は `RegistryEvaluator`（T010 で導入）で提供される。

### PrimitiveSpec

`<a id="primitive-spec"></a>` PrimitiveSpec — `src/alpha_factory/primitives/_base.py` の frozen dataclass（T010 で導入）。1 primitive の正式仕様。`id` / `name` / `category` / `domain` / `param_schema` / `required_data` / `compute` / `compute_all_bars` の 8 フィールド。`register()` 時に `validate_primitive_spec()` で不変条件検証を受ける。

### ParamSpec

`<a id="param-spec"></a>` ParamSpec — `src/alpha_factory/primitives/_base.py` の frozen dataclass（T010 で導入）。primitive parameter 1 個の range と型を宣言。`name` / `low` / `high` / `is_int` / `default` の 5 フィールド。`default` は None なら必須、値指定なら `[low, high]` 内必須。`is_int=True` なら `low/high/default` が整数値必須。

### RegistryEvaluator

`<a id="registry-evaluator"></a>` RegistryEvaluator — `src/alpha_factory/primitives/evaluator.py` のクラス（T010 で導入）。`PrimitiveEvaluator` Protocol の実装。`RegistryEvaluator(pair, aux_series=None)` で構築し、`evaluate(bars, idx, signal)` が `get_primitive(signal.name).compute(EvaluationContext(...))` を呼ぶ薄い adapter。状態（キャッシュ）は保持しない。

### PrimitiveDomain

`<a id="primitive-domain"></a>` PrimitiveDomain — `Literal["generic", "pair_specific"]`（T010 で導入）。`generic` は全ペアで利用可、`pair_specific` は `EvaluationContext.pair` を参照して特定ペア向けに最適化されたロジックを持つ。

### PrimitiveCategory

`<a id="primitive-category"></a>` PrimitiveCategory — `Literal["TREND_FOLLOW", "MEAN_REVERT", "NEUTRAL", "MODULATOR"]`（T010 で導入）。primitive の機能カテゴリ。`MODULATOR` は gate 役割（他 signal の効力を調整）、他 3 値は方向性を生む signal。`slot_from_category()` で GA slot（directional / local_gate）へ射影される。

### EvaluationContext

`<a id="evaluation-context"></a>` EvaluationContext — `src/alpha_factory/primitives/_base.py` の frozen dataclass（T010 で導入）。`PrimitiveSpec.compute` に渡される評価文脈。`bars` / `idx` / `pair` / `params` / `aux_series` の 5 フィールド。`aux_series` は `required_data` の非 OHLC キー（atr / spread / macro.* など）に対応する補助時系列の Mapping。骨格段階では空 Mapping 可、後続 TODO でロード実装追加。

### slot_from_category

`<a id="slot-from-category"></a>` slot_from_category — `src/alpha_factory/primitives/_base.py` の関数（T010 で導入）。PrimitiveCategory（4 値）を GA slot（`directional` / `local_gate` の 2 値）に射影。`MODULATOR → "local_gate"`、`TREND_FOLLOW / MEAN_REVERT / NEUTRAL → "directional"`。未知値は `ValueError` で fail-fast。

### RequiredDataKey

`<a id="required-data-key"></a>` RequiredDataKey — `PrimitiveSpec.required_data` の canonical 語彙（T010 で導入）。Literal: `ohlc / atr / spread / swap / calendar.session / calendar.economic_event / macro.vix / macro.dxy / macro.dgs10 / macro.dgs2 / macro.t10yie / macro.spx500`。加えて `cross_pair.<pair>` プレフィックス形式（`<pair>` 非空）を許容。検証関数 `is_valid_required_data(key)`。

### enforce_consistency

`<a id="enforce-consistency"></a>` enforce_consistency — `src/dsl/enforce.py` の pure function。Genome に対して weight clip / dedupe / directional 空 Clause 除去 / Position 閾値 swap / NaN・inf reject 等のルールを適用し、有効な Genome を返す（または ValueError を raise）。GA operators の後処理で呼ばれる想定。有限実数入力で冪等。

### time_stop

`<a id="time-stop"></a>` time_stop — PositionConfig.`time_stop_min` で指定される強制クローズ時間（分）。`0` で無効。イントラデイ前提（North Star 絶対制約）を個体レベルで担保するための要素。

### session close

`<a id="session-close"></a>` session close — DslStrategy の `session_close_utc` 引数で指定される UTC 時刻。`bar.bar_time.time() >= session_close_utc` で強制 close。`None` の場合は backtest engine 側の EOD 強制クローズに委譲する（両方無効は禁止）。

### Complexity Penalty

`<a id="complexity-penalty"></a>` Complexity Penalty — fitness に加算される size 罰則。`fitness_pen = fitness_raw - α × size_norm(genome)`。Luke & Panait (2006) の parsimony pressure に基づき、max_clause / max_depth hard cap と併用して bloat を抑制する。

### size_norm

`<a id="size-norm"></a>` size_norm — Clause Genome の構造的複雑性を `size_ref` で正規化した指標。形: `(nodes + 0.5 × max_width + 2 × (n_clause - 1) + 0.5 × gate_nodes) / size_ref`。`max_width` は 1 clause の幅最大値（深さではない、入れ子木構造ではないため）。

### attempted-edits 契約

`<a id="attempted-edits"></a>` attempted-edits 契約 — GA mutate の rate 意味論。`n_attempts ~ Binomial(n_edit_max, mutation_rate)` で編集試行回数を先引きする。`rate=0` で 0 attempts 確定、`rate=1` で `n_edit_max` attempts 確定。各 attempt は実行可能 kernel を一様選択。effective-diffs（実際に構造が変わった回数）は保証しない。

### EvaluationResult

`<a id="evaluation-result"></a>` EvaluationResult — `src/ga/runner.py` の frozen dataclass。`fitness_raw: float` + `meta: Mapping[str, object]`。`evaluator: Callable[[Genome], EvaluationResult]` が run_ga に外部注入される。NaN / inf の fitness_raw は runner 側で `-math.inf` に置換。

### Tier

`<a id="tier"></a>` Tier — スイムレーンの階層。Tier 1 = per-instrument GA、Graduation lane = 卒業個体の universal 探索。

### Lane

`<a id="lane"></a>` Lane — スイムレーン内の独立した GA 個体群。instrument × tier で 1 レーン。

### Graduation

`<a id="graduation"></a>` Graduation — Tier 1 で Stage C 通過かつ (ii-lite) shadow 基準超えの個体を Graduation lane に昇格させる条件・処理。

### Stage A

`<a id="stage-a"></a>` Stage A — Fast Screen。短期窓で低コストスクリーニング + 複雑度ペナルティ α_A 適用。

### Stage B

`<a id="stage-b"></a>` Stage B — Full IS + Walk-Forward OOS。train / test / step / embargo の 4 パラメータで WF を実行、median OOS Sharpe / 正 fold 比率 / DSR の複合判定。

### Stage C

`<a id="stage-c"></a>` Stage C — Live Criteria 判定 + スプレッド stress + trade range チェック + (ii-lite) 評価。

### Walk-Forward

`<a id="walk-forward"></a>` Walk-Forward (WF) — 時系列 OOS 検証手法。train 窓で学習、test 窓で評価、step 幅で前進。embargo で train/test 境界のリーク防止。López de Prado (2018) Advances in Financial ML。

### IS / OOS

`<a id="is-oos"></a>` IS / OOS — In-Sample / Out-of-Sample。学習に使った区間 / 使っていない区間。

### DSR

`<a id="dsr"></a>` DSR — Deflated Sharpe Ratio。複数試行・非正規分布を補正した Sharpe の有意性指標。Bailey & López de Prado (2014)。

### PBO

`<a id="pbo"></a>` PBO — Probability of Backtest Overfitting。CSCV (Combinatorially Symmetric Cross-Validation) で得られる過学習確率。Bailey et al. (2014)。

### Reality Check

`<a id="reality-check"></a>` Reality Check — 複数戦略の同時有意性検定。ブートストラップで null 分布を構成し p 値を得る。White (2000)。

### SPA

`<a id="spa"></a>` SPA — Superior Predictive Ability test。Reality Check の改良版。Hansen (2005)。

### CRN

`<a id="crn"></a>` CRN — Common Random Numbers。複数戦略を同じ乱数系列で比較してノイズを相殺する分散削減手法。

### TC

`<a id="tc"></a>` TC — Transaction Cost。スプレッド・スリッページ・手数料・スワップを合算した取引コスト。本プロジェクトでは fitness に必ず反映する（絶対制約）。

### Spread Filter

`<a id="spread-filter"></a>` Spread Filter — `BacktestConfig.max_spread_bps` で指定する約定前フィルタ（T009 導入）。`MockBroker.fill_pending` 冒頭で「前バー close spread_bps」が上限を超えていればその bar の pending open 系シグナルを reject。判定値は「前バー close 時点の観測値」のみを使い lookahead を回避する。`None` で無効。

### Holding Cost Proxy

`<a id="holding-cost-proxy"></a>` Holding Cost Proxy — `BacktestConfig.holding_cost_per_day_bps` で指定する保有時間比例コスト（T009 導入、旧名 `swap_cost_per_day_bps` から改名）。bar 単位で `per_bar_bps = per_day_bps × bar_minutes / 1440` を按分し `|notional|` に乗じた額を cash から控除、同時に position 単位で累計して `_close_one` 時に `Trade.pnl` から差し引く（net_pnl）。不変条件: `sum(Trade.pnl) == final_cash - initial_cash`。実 rollover swap（日付境界固定・水曜 3 倍・side 別）の精密再現は将来 TODO。

### Session Close (engine)

`<a id="session-close-engine"></a>` Session Close (engine) — `BacktestConfig.session_close_utc_hours: frozenset[int]`（T009 導入）。hour 粒度で該当時刻 bar に入った際、pending open drop → fill_pending → mark + holding cost → margin call → 保有があれば `close_all(reason="eod")` → strategy.on_bar → strategy からの open 系 drop の順で処理する。DslStrategy の `session_close_utc: time | None` は fail-safe（engine 側が primary）。HH:MM 粒度は将来 TODO。

### Intraday Absolute Constraint

`<a id="intraday-absolute-constraint"></a>` Intraday Absolute Constraint — North Star「イントラデイ絶対制約」の engine レベル担保（T009 導入）。`run_backtest` 冒頭で `session_close_utc_hours` が非空か `bars` が複数 UTC date に跨るかのどちらかが成立しなければ `ValueError`。短時間単日 backtest であっても例外なくイントラデイ強制クローズを担保する意図的ポリシー。

### IC

`<a id="ic"></a>` IC — Information Coefficient。signal 値と将来リターンの順位相関（Spearman）。プリミティブ評価の基本指標。

### (ii-lite)

`<a id="ii-lite"></a>` (ii-lite) Cross-pair Evaluation — target ペア + アンカー 2 ペアで同一ゲノムを評価し、集約指標で通過判定する軽量 cross-pair 検証。hard gate 化は Phase 6。

### Anchor Pair

`<a id="anchor-pair"></a>` Anchor Pair — (ii-lite) で target と並走評価するアンカー通貨ペア。target ごとに 2 本固定。

### FRED

`<a id="fred"></a>` FRED — Federal Reserve Economic Data。St. Louis Fed が提供する公開経済データ API。zenigame-fx では VIX / DXY / Treasury yields / breakeven 等の日足マクロ指標を `macro_index_daily` テーブルへ取り込む（`scripts/fetch_fred.py`）。primitive M5 VIXRegimeGate / P7 RiskOnOffProxy 等の前提データ。

### VIXCLS

`<a id="vixcls"></a>` VIXCLS — CBOE Volatility Index Daily Close（[FRED](#fred) シリーズ ID）。S&P 500 オプションのインプライド・ボラティリティ指数。リスク回避指標として M5 VIXRegimeGate 等で利用。

### DTWEXBGS

`<a id="dtwexbgs"></a>` DTWEXBGS — Nominal Broad U.S. Dollar Index, Daily（[FRED](#fred) シリーズ ID）。米ドルの貿易加重指数（Broad）。USD ペアの方向感に利用。

### DGS10 / DGS2

`<a id="dgs10-dgs2"></a>` DGS10 / DGS2 — 10-Year / 2-Year Treasury Constant Maturity Rate, Daily（[FRED](#fred) シリーズ ID）。米国債利回り。利回り曲線スプレッド（DGS10 - DGS2）等に利用。

### T10YIE

`<a id="t10yie"></a>` T10YIE — 10-Year Breakeven Inflation Rate, Daily（[FRED](#fred) シリーズ ID）。10 年物名目国債と TIPS の利回り差から導出される期待インフレ率。

### macro_index_daily

`<a id="macro-index-daily"></a>` macro_index_daily — [FRED](#fred) 日足マクロ指標を保持するテーブル（`series_id`, `date`, `value NULL`, `fetched_at` の 4 主要列 + 一意制約 `(series_id, date)`）。**T+1 利用原則**: `date=D` の値は `D+1` 以降の primitive 判断にのみ使う（look-ahead bias 防止）。

### StageResult

`<a id="stage-result"></a>` StageResult — `src/alpha_factory/stage_gate.py` の frozen dataclass（T014）。Stage A/B/C 評価の単一返却型。`stage: Literal["A","B","C"]` / `passed: bool` / `metrics: Mapping[str, object]`（共通 envelope: `stage` / `genome_name` / `n_bars` / `wall_time_seconds` / `payload`） / `reason_codes: tuple[str, ...]`（空タプル = 通過、非空 = 失敗）の 4 フィールド。`reason_if_failed` property で `";".join(reason_codes)` を返す。

### WF Fold

`<a id="wf-fold"></a>` WF Fold — `make_wf_folds` (`src/alpha_factory/walk_forward.py`、T014) で生成される `(train_bars: list[PriceBar], test_bars: list[PriceBar])` tuple。observed-day index ベースで切り出され、train と test の間に embargo 区間（どちらにも含めない）が入る。`train_days + embargo_days + test_days > n_unique_dates` のときは空 list を返す（呼び出し側で `no_folds` reason に変換）。

### Embargo

`<a id="embargo"></a>` Embargo — Walk-Forward において train と test の間に置く隔離観測日数（`embargo_days`）。lookahead leak / autocorrelation contamination の緩和（López de Prado 2018, *Advances in Financial ML*, Ch.7）。embargo 区間の bars は train / test どちらにも含めない。

### CrossPairResult

`<a id="cross-pair-result"></a>` CrossPairResult — `src/alpha_factory/stage_gate.py` の frozen dataclass（T014、interface 定義）。cross-pair (ii-lite) 評価の戻り値。`target_pair: str` / `anchor_pairs: tuple[str, ...]` / `aggregator_name: str` / `window: tuple[datetime, datetime]` / `passed: bool`（Phase 2 では shadow only、Phase 4 で hard gate 化） / `metrics: Mapping[str, object]` / `reason_codes: tuple[str, ...]` の 7 フィールド。`CrossPairEvaluator` Protocol の `evaluate(...)` が返す。本実装は T016 (`src/alpha_factory/cross_pair.py`) で完了。`metrics` 辞書には canonical key 集合 (`sharpe_per_pair / mean_sharpe / std_sharpe / min_sharpe / aggregate_fitness / aggregator_lambda / sharpe_target_single / sharpe_target_cross / sharpe_target_cross_ratio / liquidity_weighted_mean / pass_criteria / skipped / skip_reason / mode`) で詳細値を格納する。

### CrossPairConfig

`<a id="cross-pair-config"></a>` CrossPairConfig — `src/alpha_factory/cross_pair.py` の frozen dataclass (T016)。cross-pair (ii-lite) 評価の設定。`sharpe_target_cross_ratio_min: float` (default 0.8) / `mean_sharpe_cross_min: float` (default 0.15) / `min_sharpe_cross_min: float` (default -0.20) / `aggregator_lambda: float` (default 0.5、`F = mean - λ × std`) / `mode: Literal["shadow","hard"]` (default "shadow") の 5 フィールド。`__post_init__` で aggregator_lambda >= 0、ratio_min ∈ [0, 1]、mode ∈ {shadow, hard} を検証。Phase 2 default は `mode='shadow'` で Stage C `passed` 判定への副作用なし。

### StageCRunCrossPairEvaluator

`<a id="stage-c-run-cross-pair-evaluator"></a>` StageCRunCrossPairEvaluator — `src/alpha_factory/cross_pair.py` のクラス (T016)。T014 `CrossPairEvaluator` Protocol の実装オブジェクト。constructor で `(primitive_evaluator, cross_pair_config, anchor_pairs=None, sharpe_target_single_provider=None)` を受け取り、`evaluate(...)` 内で `evaluate_cross_pair(...)` を呼ぶ thin adapter。`sharpe_target_single_provider: Callable[[], float | None] | None` は opt-in (Phase 2 default は None で ratio 判定 skip)。Stage C `evaluate_stage_c(cross_pair_evaluator=...)` に注入する。

### ANCHOR_PAIRS

`<a id="anchor-pairs"></a>` ANCHOR_PAIRS — `src/alpha_factory/cross_pair.py` の `Mapping[str, tuple[str, str]]` 定数 (T016)。target ペアごとに 2 アンカーを固定割当 (debate-synthesis.md SSOT)。`MappingProxyType` で frozen 化。6 target (EUR_JPY / USD_JPY / EUR_USD / AUD_JPY / USD_CAD / USD_ZAR)。Phase 2 時点では MockBroker quote==JPY 制約により、すべての target で少なくとも 1 つの非 JPY-quote anchor が含まれるため実 backtest 経由では構造的 pair_failure が発生する (= MockBroker 拡張別 TODO で解消)。

### Reason Code

`<a id="reason-code"></a>` Reason Code — Stage 横断で canonical な失敗理由文字列（T014）。`StageResult.reason_codes: tuple[str, ...]` に格納し、archive / swim-lane の consumer が文字列パースせず set 比較できる設計。Stage 別の語彙は [stage-gates.md](stage-gates.md#reason-code-語彙-canonical) 参照。空タプルは通過を意味する。

### Genome Archive

`<a id="genome-archive"></a>` Genome Archive — `src/alpha_factory/archive.py::GenomeArchive`（T015）。1 Run 分の GA 個体評価結果（28 カラム）を buffering し、`flush()` で `.cache/alpha_factory/runs/genomes_{run_id}.parquet` に書き出す永続化基盤。主キーは複合キー `(lane_id, generation, individual_name)`。`collect_stage_a/b/c` で Stage 別に partial fill、`mark_graduated(lane_id, generation, individual_name)` で Tier 1 → Graduation lane 卒業 flag。

### GENOMES_SCHEMA

`<a id="genomes-schema"></a>` GENOMES_SCHEMA — `src/alpha_factory/archive.py` の `pyarrow.Schema`（T015）。28 カラム flat schema で、ネスト構造は `genome_json` (str) に集約。run_id / run_number / generation / individual_name / instrument / lane_id / parent_a / parent_b / genome_json / fitness_raw / fitness_pen / stage_a_pass / stage_b_pass / stage_c_pass / trade_count / total_pnl / sharpe / sortino / calmar / max_drawdown_pct / active_clause / n_nodes / bootstrap_ci_lower / bootstrap_ci_upper / fold_sign_ratio / dsr / ii_lite_pass / graduated。列意味論 SSOT: [concepts/genome-archive-schema.md](concepts/genome-archive-schema.md)。

### Monotonic Enrich

`<a id="monotonic-enrich"></a>` Monotonic Enrich — [Genome Archive](#genome-archive) の重複 collect ポリシー（T015）。各 row は内部に `_max_stage_seen ∈ {"", "A", "B", "C"}` を持ち、stage 順序（`{"":0,"A":1,"B":2,"C":3}`）に基づいて: 後段 stage 適用は enrich 上書き OK、同一 stage 再 collect は WARN + 上書き、前段 stage 逆流（B→A 等）は WARN + no-op。後段ほど rich な指標が prevail する設計。`_max_stage_seen` は in-memory 専用（Parquet には書かない）。

## SSOT 参照

本ファイル自身が用語の SSOT。`config/alpha_factory/default.yaml` への参照は無い。

## 関連ドキュメント

- [clause-architecture.md](clause-architecture.md)
- [stage-gates.md](stage-gates.md)
- [swim-lane.md](swim-lane.md)
- [cross-pair.md](cross-pair.md)
- [statistics.md](statistics.md)
- [migration-triggers.md](migration-triggers.md)

## 関連 TODO

- 未着手（用語追加は各 doc 作成時に随時）
