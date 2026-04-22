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

`<a id="primitive-evaluator"></a>` PrimitiveEvaluator — `src/dsl/strategy.py` で定義される Protocol。`evaluate(bars, idx, signal) -> float` を実装する primitive 評価インターフェース。実装本体は後続 TODO `primitives-registry` の `RegistryEvaluator` で提供される。

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
