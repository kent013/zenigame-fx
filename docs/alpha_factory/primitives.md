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

| # | 名称 | カテゴリ |
|---|------|---------|
| 1 | TrendEMA | trend |
| 2 | MACDSignal | trend |
| 3 | DonchianBreak | breakout |
| 4 | ADXTrend | trend |
| 5 | VolatilityBreak | breakout |
| 6 | SessionMomentum | session |
| 7 | RSIRevert | mean-revert |
| 8 | BollingerRevert | mean-revert |
| 9 | StochRevert | mean-revert |
| 10 | ZScoreRevert | mean-revert |
| 11 | MeanReversionRange | mean-revert |
| 12 | RealizedVolZScore | volatility |
| 13 | ReturnAutocorrLag | autocorr |
| 14 | TrendStrengthRatio | trend |

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

**T010 時点の状態**: `src/alpha_factory/primitives/_registry.py` の registry（module-level dict）は **空**。契約（`PrimitiveSpec` / `ParamSpec` / `EvaluationContext` / `RegistryEvaluator`）のみ整備済。32 primitive は後続 TODO（T010-a/b/c）で段階的に登録する。

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
