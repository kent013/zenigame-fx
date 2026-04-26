# Primitives

## 目的

プリミティブ 32 個カタログの索引。各プリミティブの実体（関数 signature・実装手順）は別 TODO で扱う。

## スコープ

- 32 プリミティブの分類（汎用 Directional 14 / 汎用 Modulator 6 / ペア特化 12）
- 各プリミティブが持つべき必須メタ情報
- registry の役割

実装本体・パラメータ範囲は別 TODO（`concepts/primitives-registry.md` 等）で扱う。

## 用語リンク

本ドキュメントで使用する用語: [Directional](terminology.md#directional), [Modulator](terminology.md#modulator), [Local Gate](terminology.md#local-gate), [IC](terminology.md#ic)

## 主要定義

### 必須メタ情報（registry 登録時）

各プリミティブは以下を必ず宣言する:

- `name` — 一意な識別子（PascalCase）
- `category` — `directional` / `modulator`
- `domain` — `generic` / `pair_specific`
- `required_data` — 必要な系列（`ohlcv`, `fred:VIXCLS`, `oanda:SPX500_USD` 等）

### 汎用 Directional (14)

T011 で `src/alpha_factory/primitives/directional_generic.py` に実装・登録済。
出力は全て `[-1, +1]` bounded（F14 のみ `[0, +1]`）。`required_data=("ohlc",)`、`domain=generic`。

| ID | 名称 | Category | 数式 | 主要パラメータ |
|----|------|----------|------|----------------|
| F1 | TrendEMA | TREND_FOLLOW | `tanh((EMA(fast) - EMA(slow)) / ATR)` | fast_n[5,30], slow_n[20,100], atr_n[7,28] |
| F2 | MACDSignal | TREND_FOLLOW | `tanh((MACD - Signal) / rolling_std(MACD-Signal, scale_n))` | fast_n[6,20], slow_n[12,40], signal_n[5,15], scale_n[20,100] |
| F3 | DonchianBreak | TREND_FOLLOW | `tanh((close - DC_mid) / (k * ATR))` | n[10,60], k[0.5,3.0], atr_n[7,28] |
| F4 | ADXTrend | TREND_FOLLOW | `max(0, tanh((ADX - 25) / scale)) * sign(+DI - -DI)` | n[7,28], scale[5,30] |
| F5 | VolatilityBreak | TREND_FOLLOW | `max(0, tanh(k * (ATR_short/ATR_long - 1))) * sign(EMA_fast - EMA_slow)` | short_n[3,20], long_n[30,120], k[1,10] |
| F6 | SessionMomentum | TREND_FOLLOW | `tanh((close - session_open_close) / (k * ATR))` | session{0=tokyo,1=london,2=ny}, k[0.5,3.0], atr_n[7,28] |
| F7 | RSIRevert | MEAN_REVERT | `tanh((50 - RSI) / scale)` | n[7,28], scale[5,30] |
| F8 | BollingerRevert | MEAN_REVERT | `tanh((BB_mid - close) / (k * BB_std))` | n[10,60], k[1.0,3.0] |
| F9 | StochRevert | MEAN_REVERT | `tanh((50 - %K) / scale)` | n[7,28], scale[10,40] |
| F10 | ZScoreRevert | MEAN_REVERT | `tanh(-zscore(close, n))` | n[10,60] |
| F11 | MeanReversionRange | MEAN_REVERT | `tanh(-(close - range_mid) / (range_width + eps))` | n[10,60] |
| F12 | RealizedVolZScore | NEUTRAL | `tanh(zscore(realized_vol, window) / k_scale)` | n[10,60], window[60,500], k_scale[1.5,4.0] |
| F13 | ReturnAutocorrLag | NEUTRAL | `rolling_corr(r, r[shift=lag], w)`（tanh 不要、定義域 [-1,+1]） | w[20,200], lag[1,10] |
| F14 | TrendStrengthRatio | NEUTRAL | `tanh(|EMA_diff| / (rv * scale * close) / k_scale)` → [0,+1] | fast_n[5,30], slow_n[20,100], rv_n[10,60], scale[0.5,5.0], k_scale[1.0,5.0] |

**lookahead 回避**: rolling_*/Wilder recurrence/F6 session_key 遷移/F13 lag shift すべて過去方向のみ参照。`test_no_lookahead_property` で 14 primitive すべてに property test 適用（後続バー改変で過去 index 不変）。

**技術指標ヘルパー** (`src/alpha_factory/primitives/_indicators.py`): EMA / ATR / RSI / ADX (+DI/-DI 含) / Bollinger / Stochastic / MACD / Donchian / realized_vol / zscore / rolling_{sum,mean,std,max,min,corr} を numpy で O(N) 実装。


### 汎用 Modulator (6)

T012 で `src/alpha_factory/primitives/modulator_generic.py` に実装・登録済。
出力は全て `[0, 1]` bounded（warmup は np.nan、`compute` は neutral 値で吸収）。
`category="MODULATOR"`, `domain="generic"`, GA slot は `local_gate`。

| ID | 名称 | 数式 | 主要パラメータ | 外部データ |
|----|------|------|----------------|-----------|
| M1 | ATRRegimeGate | `sigmoid(direction * (atr_rel - threshold_rel) / scale_rel)`（`atr_rel = ATR/close` で pair 非依存化） | n[7,28], threshold_rel[0.0001,0.02], scale_rel[1e-5,0.01], prefer_high∈{0,1} | なし |
| M2 | SessionGate | `in_session ? 1 : 0`（`soft_edge_min>0` で境界 sigmoid blend、open_gate * close_gate の AND-like） | session{0=tokyo,1=london,2=ny}, soft_edge_min[0,60] | なし |
| M3 | SpreadConditionGate | `sigmoid(-k*(spread_bps - threshold_bps))`（`spread_bps = (ask.close - bid.close) / mid * 10000`） | threshold_bps[0.1,20], k[0.1,5] | `spread` |
| M4 | EconomicEventGate | `1 - sigmoid((window_min - |Δt_min|)/scale_min)`（min_impact 以上の event を currency filter） | window_min[5,120], scale_min[1,30], min_impact{1,2,3} | `calendar.economic_event` (`event_snapshot`) |
| M5 | VIXRegimeGate | `sigmoid((threshold - vix)/scale)`（直近 publication_ts < bar_time の vix_close） | threshold[10,40], scale[1,15] | `macro.vix` (`vix_snapshot`) |
| M6 | TrendStrengthGate | `sigmoid((ADX(n) - theta)/scale)` | n[7,28], theta[10,40], scale[2,15] | なし |

**look-ahead 回避**:
- M1 / M6: ATR / ADX は Wilder smoothing で過去のみ参照
- M2: bar_time の hour/minute から計算、deterministic
- M3: bar close 時点のスプレッドを参照（signal at close → execute next bar open 規約と整合、MVP では proxy）
- M4: `event.actual` を一切参照せず `event.event_time` のみ使用。`EconomicEventSnapshot.as_of` を 1 段目 cap として `event_time > as_of` のイベントを除外。**T039: `as_of_strict=True` のとき per-bar gate (二段目) を有効化し、各 bar で `event_time > bar_time[i]` のイベントを bisect で除外** (causality 強制)。
- P10: M4 と同方針 (USD/CAD 限定 NA セッション内 gate)。`as_of_strict` で per-bar gate を有効化 (T039)。
- M5: `bisect_left(pubs, bar_time)` の strict less than で同時刻 publication を除外

**snapshot 欠損時挙動**:
- M4 `event_snapshot=None` → 1.0 safe default + `RuntimeWarning`（gate 開放）
- M5 `vix_snapshot=None` or 空 → 0.5 neutral + `RuntimeWarning`
- `EvaluationContext.strict_snapshot_required=True` 時は `RuntimeError` で fail-fast（production backtest runner はこの flag を使い snapshot 伝搬漏れを検知する）

**EvaluationContext 拡張** (T012、後方互換):
- `event_snapshot: EconomicEventSnapshot | None = None`
- `vix_snapshot: VixSeriesSnapshot | None = None`
- `strict_snapshot_required: bool = False`

T011 既存テストは新フィールドを指定せず `EvaluationContext(bars=..., idx=..., pair=..., params=...)` で構築するため壊れない（frozen dataclass への default 値付きフィールド追加は backward-compatible）。

**snapshot dataclass** (`_base.py`):
- `EconomicEventSnapshot(calendar, as_of, as_of_strict=False)` — `EconomicCalendar` と as-of cap のペア。`as_of_strict=True` で M4/P10 の per-bar gate を有効化 (T039、production 推奨)。`__post_init__` で `as_of` の tz-aware を強制 (T039 fail-fast)。
- `VixSeriesSnapshot(observations: tuple[(datetime, float), ...])` — publication_ts_utc 昇順、`__post_init__` で tz-aware 強制 + 昇順検証。`lookup(bar_time)` は strict less than で O(N) lookup（compute_all_bars 内で繰り返し呼ぶ場合は呼び出し側で pubs 列をキャッシュして bisect_left を直接使うこと、M5 実装参照）

**実行タイミング規約**: zenigame-fx の backtest は `signal at close → execute next bar open`。
M3/M4/M5 の primitive は bar close 時点で観測される情報のみ参照する。

### ペア特化 (12)

T013 で `src/alpha_factory/primitives/pair_specific.py` に実装・登録済。
`domain="pair_specific"`、設計の起点は特定ペアだが他ペアでも crash しない（symbol-agnostic 計算）。
出力域: directional は `[-1, +1]`、MODULATOR (P6/P10/P11) は `[0, 1]`。

| ID | 名称 | 起点ペア | Category | 数式概要 | 主要パラメータ | 必要 aux データ |
|----|------|---------|----------|----------|----------------|----------------|
| P1 | LondonNYOverlapMomentum | EUR_USD | TREND_FOLLOW | UTC 13-17 帯内で `tanh(return_n / scale)` (帯外 0) | n[2,24], scale[1e-4,0.02] | なし |
| P2 | IntradayRangeFade | EUR_USD | MEAN_REVERT | アジア時間 (0-7 UTC) range 外 NY (12-21 UTC) close で reversion | atr_n[7,28] | なし |
| P3 | TokyoOpenReversal | USD_JPY | MEAN_REVERT | UTC 0-2 帯内で `-tanh(return_n / scale)` | n[1,12], scale[1e-4,0.02] | なし |
| P4 | YenFixingBias | USD_JPY | TREND_FOLLOW | 仲値 (00:55 UTC) 前 + / 後 - の bar_time 距離 sigmoid | window_min[5,120], scale_min[1,30] | なし |
| P5 | CrossPairTriangulation | EUR_JPY | MEAN_REVERT | `-tanh(zscore(EURJPY - EURUSD*USDJPY, n) / scale)` | z_n[20,200], scale[0.5,5] | aux_pair_bars[EUR_USD, USD_JPY] |
| P6 | EuroHourVolRegime | EUR_JPY | MODULATOR | UTC 7-15 帯内で `sigmoid((atr_rel - threshold)/scale)` | atr_n[7,28], threshold_rel[1e-4,0.02], scale_rel[1e-5,0.01] | なし |
| P7 | RiskOnOffProxy | AUD_JPY | TREND_FOLLOW | `tanh(2*(sigmoid(vix_threshold-vix)-0.5) + tanh(spx_mom/0.01))` | spx_n[2,48], vix_threshold[10,40], vix_scale[1,15], vix_staleness_days[1,30], spx_staleness_bars[1,500] | vix_snapshot + macro.spx500 |
| P8 | CommodityFlowBias | AUD_JPY | TREND_FOLLOW | `tanh(copper_mom / scale)` (copper or commodity_index fallback) | mom_n[2,48], scale[1e-3,0.1], staleness_bars[1,500] | macro.copper OR macro.commodity_index |
| P9 | OilPriceInverseFlow | USD_CAD | TREND_FOLLOW | `-tanh(wti_mom / scale)` (USD_CAD は WTI と逆相関) | mom_n[2,48], scale[1e-3,0.1], staleness_bars[1,500] | macro.wti |
| P10 | NADataProximityGate | USD_CAD | MODULATOR | NA セッション (12-21 UTC) かつ USD/CAD イベント proximity で `1 - sigmoid((window_min - |Δt|)/scale_min)`、外 1.0 | window_min[5,120], scale_min[1,30], min_impact{1,2,3} | event_snapshot |
| P11 | EmergingMarketStressGate | USD_ZAR | MODULATOR | `1 - 0.5*(sigmoid((vix - threshold)/scale) + sigmoid(dxy_mom/0.005))` | dxy_n[2,120], vix_threshold[10,40], vix_scale[1,15], vix_staleness_days[1,30], dxy_staleness_bars[1,500] | vix_snapshot + macro.dxy |
| P12 | GoldCorrelationBias | USD_ZAR | TREND_FOLLOW | `-tanh(gold_mom / scale)` (ZAR は金順相関 → USD_ZAR 逆相関) | mom_n[2,48], scale[1e-3,0.1], staleness_bars[1,500] | macro.gold |

**look-ahead 回避**:
- P1-P4, P6: bar_time UTC 固定時刻 + 過去 close / Wilder ATR のみ
- P5: aux_pair_bars[k][i].bar_time == bars[i].bar_time の strict 一致を assert（misalign は ValueError）
- P7, P11: VIX は `bisect_left(pubs, bar_time)` で publication < bar_time 厳守、SPX/DXY は loader 責務 (bar-aligned forward-fill)
- P8, P9, P10, P12: aux_series は loader 責務 (forward-fill) + `_stale_mask` で staleness_bars 超過を NaN

**3 状態の挙動**:

| 状態 | 検出 | 戻り値 (default) | strict_snapshot_required=True |
|------|------|-------------------|-------------------------------|
| MISSING_KEY | 必要 aux key 自体が無い | RuntimeWarning + 全 bar safe default (directional=0.0, P10=1.0, P6/P11=0.5) | RuntimeError fail-fast |
| STALE_VALUE | aux_series NaN / aux_pair_bars[i] None / VIX 古い publication | 当該 bar NaN (compute は neutral 値に吸収) | 同左 |
| MISALIGNMENT | aux_pair_bars 長さ不一致 / bar_time 不一致、aux_series 長さ不一致 | ValueError fail-fast | 同左 |

**EvaluationContext 拡張** (T013、後方互換):
- `aux_pair_bars: Mapping[str, Sequence[PriceBar | None]] = field(default_factory=dict)` — cross-pair primitive (P5) 用
- `strict_snapshot_required` の意味を「snapshot + aux 全般の per-call strict」に拡張（field 名は維持、後方互換）

**PrimitiveSpec 拡張** (T013、後方互換):
- `optional_data_groups: tuple[tuple[str, ...], ...] = ()` — OR-semantics 依存。P8 は `(("macro.copper", "macro.commodity_index"),)` で「銅 OR 商品 index のいずれか必須」を表現
- `validate_primitive_spec` で各 key を `is_valid_required_data` でチェック、required_data との重複も拒否

**RegistryEvaluator 拡張** (T013):
- `aux_pair_bars` / `event_snapshot` / `vix_snapshot` を kwarg で保持し EvaluationContext に流す
- `strict_aux_required: bool = False` + `selected_primitive_ids: Iterable[str] | None = None` — 起動時 preflight verify
  - 各 selected primitive の `required_data` + `optional_data_groups` を union し、provider 有無を確認
  - 不足あれば `RuntimeError("required aux missing for selected primitives: ...")` で fail-fast
  - production GA runner はこの flag を True にして「選択 primitive が required_data 未充足のまま走る」failure を起動時に検出する規約
- `_BARS_PROVIDED_KEYS = frozenset({"ohlc", "atr", "spread", "swap", "calendar.session"})` — bars 自体で provide される key 集合 (preflight でスキップ)

**新規 macro key** (T013、`RequiredDataKey` Literal + `_REQUIRED_DATA_LITERALS` 同期更新):
- `macro.copper` (P8 1 次)
- `macro.commodity_index` (P8 fallback)
- `macro.wti` (P9)
- `macro.gold` (P12)

**aux データ ingest (本 TODO 範囲外)**:
- OANDA CFD pipeline (XAU_USD, WTICO_USD, SPX500_USD, XCU_USD) は別 TODO
- FRED 既存 ingest (DTWEXBGS=DXY) を loader で bar-aligned forward-fill する別 TODO
- 本 TODO ではテストでモック注入し primitive ロジックのみ検証

**実行タイミング規約**: zenigame-fx の backtest は `signal at close → execute next bar open`。
P1-P12 は bar close 時点で観測される情報のみ参照する。

### Registry の役割

**T013 時点の状態**: `src/alpha_factory/primitives/_registry.py` の registry に directional generic 14 個（F1-F14）+ modulator generic 6 個（M1-M6）+ pair_specific 12 個（P1-P12）の合計 32 個が登録済。`_registry.ensure_registered()` は `directional_generic.ensure_registered()` + `modulator_generic.ensure_registered()` + `pair_specific.ensure_registered()` の 3 つを呼ぶ。

`directional_generic.category_counts()` は **本モジュール固有の内訳** (F1-F14 のみ) を返し、`"MODULATOR": 0` は「directional モジュール内に MODULATOR は無い」の意。registry 全体の category 別 count は `_registry.list_by_category(category)` を使うこと。

**並行安全な登録**: `register_if_absent(spec)` が lock 内で atomic に存在確認＋登録を行う。`ensure_registered()` は `register_if_absent` を使って冪等性を保証する。

**Bootstrap 手順**:

- 各 primitive モジュールが import 時に `register(PrimitiveSpec(...))` を呼ぶ
- production path（GA entry）は `ensure_registered()` を 1 回明示的に呼んでから `list_all()` / `get_primitive(id)` を使う
- 骨格段階では `ensure_registered()` は no-op、登録件数は 0

**登録時 validation**:

- `register()` は `validate_primitive_spec()` で不変条件を検証（`id/name` 非空、`param_schema` 名重複禁止、`low <= high`、`default` の範囲・is_int 整合、`required_data` の canonical naming）
- 重複 id は `ValueError`（silent override 禁止）
- 並行 register/clear は `threading.Lock` で保護

**category → slot 射影**:

- `slot_from_category(category)` で 4 値 PrimitiveCategory（TREND_FOLLOW / MEAN_REVERT / NEUTRAL / MODULATOR）を 2 値 GaSlot（directional / local_gate）に射影
- MODULATOR → `local_gate`、それ以外 → `directional`
- 未知値は `ValueError` で fail-fast
- GA random_gen は本関数経由で registry を参照する（tests/ga/ の移行は T010-d）

**required_data の canonical 語彙**:

- Literal (T010 時点): `ohlc`, `atr`, `spread`, `swap`, `calendar.session`, `calendar.economic_event`, `macro.vix`, `macro.dxy`, `macro.dgs10`, `macro.dgs2`, `macro.t10yie`, `macro.spx500`
- Literal (T013 追加): `macro.copper`, `macro.commodity_index`, `macro.wti`, `macro.gold`
- プレフィックス許容: `cross_pair.<pair>`（`<pair>` 部分は非空必須、P5 で使用）
- 検証関数: `is_valid_required_data(key)`

## SSOT 参照

プリミティブは config 駆動でなく registry 駆動のため、`default.yaml` への参照は無い。パラメータ範囲は各プリミティブ実装内で定義。

## 関連ドキュメント

- [clause-architecture.md](clause-architecture.md) — directional / local_gate での利用
- [concepts/primitives-registry.md](concepts/primitives-registry.md)
- [concepts/primitives-directional-generic.md](concepts/primitives-directional-generic.md)
- [concepts/primitives-modulator-generic.md](concepts/primitives-modulator-generic.md)
- [concepts/primitives-pair-specific.md](concepts/primitives-pair-specific.md)

## 関連 TODO

- T011 (merged): 14 directional generic primitives (F1-F14)
- T012 (merged): 6 modulator generic primitives (M1-M6)
- T013 (本 TODO): 12 pair_specific primitives (P1-P12) + EvaluationContext 拡張 + preflight verify
- 別 TODO: aux_series ingest pipeline (OANDA CFD, FRED 系列の bar-aligned forward-fill loader)
- 別 TODO: `RegistryEvaluator` を GA backtest entry に組み込む際の `selected_primitive_ids` 抽出
