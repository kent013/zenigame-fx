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

| # | 名称 | 役割 |
|---|------|------|
| 15 | ATRRegimeGate | volatility regime |
| 16 | SessionGate | session window |
| 17 | SpreadConditionGate | cost gate |
| 18 | EconomicEventGate | event blackout |
| 19 | VIXRegimeGate | macro fear regime（FRED VIXCLS） |
| 20 | TrendStrengthGate | trend confidence |

### ペア特化 (12)

| # | 名称 | 対象ペア |
|---|------|---------|
| 21 | LondonNYOverlapMomentum | EUR_USD |
| 22 | IntradayRangeFade | EUR_USD |
| 23 | TokyoOpenReversal | USD_JPY |
| 24 | YenFixingBias | USD_JPY |
| 25 | CrossPairTriangulation | EUR_JPY |
| 26 | EuroHourVolRegime | EUR_JPY |
| 27 | RiskOnOffProxy | AUD_JPY |
| 28 | CommodityFlowBias | AUD_JPY |
| 29 | OilPriceInverseFlow | USD_CAD |
| 30 | NADataSurpriseGate | USD_CAD |
| 31 | EmergingMarketStressGate | USD_ZAR |
| 32 | GoldCorrelationBias | USD_ZAR |

### Registry の役割

**T011 時点の状態**: `src/alpha_factory/primitives/_registry.py` の registry に directional generic 14 個（F1-F14）が登録済。Modulator 6 個（M1-M6）と pair_specific 12 個（P1-P12）は未登録。

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

- Literal: `ohlc`, `atr`, `spread`, `swap`, `calendar.session`, `calendar.economic_event`, `macro.vix`, `macro.dxy`, `macro.dgs10`, `macro.dgs2`, `macro.t10yie`, `macro.spx500`
- プレフィックス許容: `cross_pair.<pair>`（`<pair>` 部分は非空必須）
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

- 未着手（Phase 2D: 32 プリミティブ並列実装）
