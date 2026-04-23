# T013 Pair-specific primitives (P1-P12) — Conceptual Design

## 背景

T010-T012 が main にマージ済（`667677d`, 540 tests / 1 skip）。registry には現在 20 個
の generic primitive（F1-F14 + M1-M6）が登録され、`directional × local_gate` の
clause 構造は capacity 上動作する状態にある。

しかし全て `domain="generic"` であり、特定通貨ペアの「個性 (intraday session、
仲値、cross-pair triangulation、商品/EM 連動)」に基づく primitive は未実装。
GA は一律のロジックでペアを跨ぐため、ペア固有の収益機会（東京オープン反転、
WTI ↔ CAD 逆相関、VIX ↔ ZAR ストレス、cross-pair 三角裁定残差など）は表現できていない。

本 TODO は **6 ペア × 2 個 = 12 個の `domain="pair_specific"` primitive** を追加し、
GA がペア固有のエッジを検出可能にすることを目的とする。さらに、cross-pair 系列・
非 OHLC 補助系列 (VIX, SPX, WTI, gold, copper, DXY) を primitive に渡すための
**EvaluationContext 拡張**（`aux_pair_bars`、`aux_series` の用途明確化）を
本 TODO で type-safe に設計する（ロード実装は別 TODO）。

## 目的（仮説）

**仮説**: 「ペア固有の構造（時間帯特性・実需フロー・cross-pair 整合性・原油/金/VIX
連動）を primitive として直接ゲノムに表現できれば、generic primitive の組合せ最適化
だけでは到達できない fitness 領域を GA が探索でき、Stage A→B→C 通過率が改善する」。

成功判断:
1. T013 merge 後、registry の `pair_specific` domain が 12 件、合計 32 件
2. 各 primitive が compute / compute_all_bars 両 API を満たし、look-ahead bias 0
3. aux_series / aux_pair_bars 欠損時は warning + safe default で graceful degrade
4. F1-F14 / M1-M6 既存テストが後方互換で全件通過

## スコープ

### 実装対象（全 12 件、domain="pair_specific"）

| ID | 名称 | 設計起点ペア | category | 出力域 | 必要 aux データ |
|----|------|-------------|----------|--------|----------------|
| P1 | LondonNYOverlapMomentum | EUR_USD | TREND_FOLLOW | [-1, +1] | なし (bar_time + ohlc) |
| P2 | IntradayRangeFade | EUR_USD | MEAN_REVERT | [-1, +1] | なし |
| P3 | TokyoOpenReversal | USD_JPY | MEAN_REVERT | [-1, +1] | なし |
| P4 | YenFixingBias | USD_JPY | TREND_FOLLOW | [-1, +1] | なし |
| P5 | CrossPairTriangulation | EUR_JPY | MEAN_REVERT | [-1, +1] | aux_pair_bars["EUR_USD"], aux_pair_bars["USD_JPY"] |
| P6 | EuroHourVolRegime | EUR_JPY | MODULATOR | [0, 1] | なし |
| P7 | RiskOnOffProxy | AUD_JPY | TREND_FOLLOW | [-1, +1] | vix_snapshot + aux_series["macro.spx500"] |
| P8 | CommodityFlowBias | AUD_JPY | TREND_FOLLOW | [-1, +1] | aux_series["macro.copper"] (or "macro.commodity_index") |
| P9 | OilPriceInverseFlow | USD_CAD | TREND_FOLLOW | [-1, +1] | aux_series["macro.wti"] |
| P10 | NADataProximityGate | USD_CAD | MODULATOR | [0, 1] | event_snapshot |
| P11 | EmergingMarketStressGate | USD_ZAR | MODULATOR | [0, 1] | vix_snapshot + aux_series["macro.dxy"] |
| P12 | GoldCorrelationBias | USD_ZAR | TREND_FOLLOW | [-1, +1] | aux_series["macro.gold"] |

> **Codex 1-1 反映 (P10 rename)**: 当初「NADataSurpriseGate」としていたが、actual を参照しないため
> "surprise" は不適切。M4 EconomicEventGate の機能を「対象通貨を CAD/USD に絞り、北米
> セッション (12:00-21:00 UTC) のみ active」に**地理 / 通貨 specialize** した
> proximity gate と再定義し、`P10 NADataProximityGate` に rename。差別化は
> (a) currency filter を base/quote ではなく {USD, CAD} 固定、
> (b) bar_time の hour が NA セッション外なら gate を 1.0 (無効化) で M4 と切り分ける。

directional 9 / MODULATOR 3。ペアごとに少なくとも 1 directional を含む。
全 primitive は他ペアでも crash せず動く（出力符号・絶対値は変化しうる）。

### 非スコープ

- aux_series / aux_pair_bars の本物データ ingest（OANDA CFD: SPX500_USD, WTICO_USD,
  XAU_USD, XCU_USD; FRED: DGS10/DXY 等の bar-aligned forward-fill）は別 TODO
  - 本 TODO ではテストでモック注入し primitive ロジック側のみ検証
- cross-pair データローダ（複数 pair を時刻整合させる正規化処理）の実装は
  別 TODO。本 TODO では `aux_pair_bars: dict[str, list[PriceBar]]` の interface
  を `EvaluationContext` に追加し、テストでモック
- snapshots loader の helper（`load_aux_series` / `load_aux_pair_bars`）も別 TODO
- live trading での aux_series 注入経路は別 TODO

## 設計上の核心論点

### L1. EvaluationContext の拡張（aux_pair_bars / aux_series 整理）

現在の `EvaluationContext`:
```python
bars: Sequence[PriceBar]
idx: int
pair: str
params: Mapping[str, float | int]
aux_series: Mapping[str, Sequence[float]] = field(default_factory=dict)
event_snapshot: EconomicEventSnapshot | None = None
vix_snapshot: VixSeriesSnapshot | None = None
strict_snapshot_required: bool = False
```

**追加する field**:

```python
aux_pair_bars: Mapping[str, Sequence[PriceBar | None]] = field(default_factory=dict)
```

- key は OANDA pair 名（"EUR_USD", "USD_JPY"）
- value は同一時刻軸（bar_time が揃う）にアラインされた PriceBar 列
  - 各要素は `PriceBar` または `None`
  - `PriceBar`: 当該 bar_time で valid な aux pair データあり
  - `None`: stale (loader が staleness cap 超過判定) または source データ欠損
- **時刻軸アライン責務**は loader（別 TODO）にあり、primitive 側は
  「`len(aux_pair_bars[k]) == len(bars)` かつ
  `aux_pair_bars[k][i] is None or aux_pair_bars[k][i].bar_time == bars[i].bar_time`」を
  fail-fast assert する規約。**bar_time が違う非 None 要素は misalignment** で ValueError
- 欠損キー（必要 pair の key が dict に無い）は **missing key state**（後述 L6 表参照）

> **Codex 2-1 反映**: `Sequence[PriceBar | None]` に明示型化。stale/None mask は
> 同 Sequence 内で表現し、別 mask 配列・別メタ dict は本 TODO で導入しない
> （二重契約回避）。`PriceBar` の hash 不変性に依存しないため `Sequence` で問題なし。

**aux_series の用途明確化**:
- `aux_series` は **既存の bar-aligned float 列**（VIX 以外の macro 系列、SPX, WTI, gold, copper, DXY）
- key は `_REQUIRED_DATA_LITERALS` の `macro.*` を流用（必要なら拡張）
- 値の長さは `len(bars)` と一致、bar_time の整合性は loader 責務
- 個別 macro 系列のうち、VIX だけは publication_ts ベース lookup が必要なため
  既存の `vix_snapshot` 経路を踏襲し、aux_series["macro.vix"] には載せない
  （二重経路の混乱を避けるため）

**新規 macro key 追加（_base.py の Literal を拡張）**:
- `macro.copper`, `macro.commodity_index`, `macro.wti`, `macro.gold`
- これらは bar-aligned float 列（前営業日 close を forward-fill する loader 想定）
- `macro.spx500` は既存 Literal にあるので追加不要

### L2. cross-pair データの look-ahead bias と alignment contract

P5 CrossPairTriangulation は EUR_USD × USD_JPY の合成 mid と実 EUR_JPY mid の
乖離 (residual) を取り、**乖離が拡がった方向と逆向き** (mean revert) の signal を返す。

**alignment contract（Codex 1-3 反映、矛盾解消）**:

aux_pair_bars の各 PriceBar は **必ず bar_time が一致**する `aligned synthetic bar` で
あることを契約とする。**forward-fill は loader 側で行うが、forward-fill 後の bar の
bar_time は target pair の bar_time に書き換える**（synthetic bar）。

つまり:
- 入力 contract: `aux_pair_bars[k][i].bar_time == bars[i].bar_time` (strict)
- 違反時: `ValueError` で fail-fast (data bug)
- forward-fill 元の本来の close timestamp を保持したい場合は、別途 `aux_pair_bars_meta`
  で source_ts を露出するが、本 TODO 範囲外 (loader が後続 TODO で実装する際に判断)

**MVP の loader 規約**:
- bar i の aux_pair_bar[k][i] は「`bars[i].bar_time` 以前に既知な aux pair k の最新 close
  を bid/ask close フィールドに格納し、bar_time だけ `bars[i].bar_time` に書き換えた
  synthetic PriceBar」を生成する
- staleness cap (例: 5 bar 以上前のデータは無効) は loader が判断、超過時は
  `is_stale=True` flag を付けるか、PriceBar を None に置き換える。本 TODO の primitive
  側は `aux_pair_bars[k][i] is None` のとき NaN 出力 (warmup 同等扱い)

look-ahead bias 観点:
- 上記 alignment contract により、同一時刻 bar の close 同士で計算するため future leak は
  発生しない (同 bar close は同時刻に既知という MVP 仮定)
- loader 責務: `bar_time` 以前に既知な値しか forward-fill しない (これは loader 別 TODO で
  unit test 必須項目とする)
- primitive 側: bar_time 一致 strict assert は実装する (fail-fast)

### L3. 時間帯依存 primitive の DST と pair time zone

P1 LondonNYOverlapMomentum (13:00-17:00 UTC), P3 TokyoOpenReversal (00:00-02:00 UTC),
P4 YenFixingBias (仲値 = 東京 9:55 JST = 00:55 UTC), P6 EuroHourVolRegime (07:00-15:00 UTC)
は全て **UTC 固定時刻**で定義する（DST 簡略化）。

理由:
- DST に厳密対応すると pair / 時期で時間帯が揺れ、look-ahead テスト/再現性が
  下がる。MVP では UTC 固定で十分（M2 SessionGate と同方針）
- 仲値は 9:55 JST が DST に依存しないため UTC 換算 00:55 で固定可
- 後続 TODO で「銀行祝日 / DST 厳密対応」を別途実装する余地は残す

### L4. directional 出力の符号と pair 反転耐性

P1/P3/P4/P5/P7/P8/P9/P12 は出力 [-1, +1]（買い側 = +、売り側 = −）。
**「買い側」は GA random_gen が weight に符号を付けることで吸収される**ため、
primitive 自体は「内部統計の自然な符号」を返すが、**MEAN_REVERT primitive は
"reversion 方向"を自然符号として返す**（Codex 1-2 反映）。

例:
- P9 OilPriceInverseFlow: USD_CAD では「WTI 上昇 → CAD 上昇 → USD_CAD 下落」だから
  `-tanh(wti_momentum)` を返すのが自然 (target pair の買い符号で表現)。AUD_USD に
  流用すると weight が GA で fit されるため crash しない
- P5 CrossPairTriangulation (MEAN_REVERT): residual = mid_EURJPY − mid_EURUSD * mid_USDJPY
  に対し、**mean-revert として `signal = -tanh(residual_z)` を返す**。
  - residual > 0 (実 EUR_JPY が合成より高い → 過大評価) → signal < 0 (売り)
  - residual < 0 (過小評価) → signal > 0 (買い)
  - これは category=MEAN_REVERT (P11 BollingerRevert と同方針) の自然符号

### L5. MODULATOR 3 個 (P6, P10, P11) の MODULATOR 共通規約

M1-M6 と同じ規約に従う:
- 出力 [0, 1]
- safe default は P10 (event gate) → 1.0 (ゲート開放), P6/P11 → 0.5 (neutral)
- snapshot None + strict mode → RuntimeError、それ以外 → RuntimeWarning + safe default
- `_make_compute_single(_pX_compute_all, neutral=...)` パターンを再利用

### L6. aux_series / aux_pair_bars 欠損時の挙動（伝搬漏れ防止、Codex 1-4/2-2/2-3 反映）

**3 状態の明示定義**:

| 状態 | 検出方法 | strict=False (default) | strict=True (production) |
|------|----------|------------------------|--------------------------|
| **MISSING_KEY** | `key not in aux_series/aux_pair_bars` (必要 key 自体が無い) | `RuntimeWarning` 一回 + primitive ごとの safe default を **全 bar 一括返却** | preflight verify で `RuntimeError` (compute 到達せず) |
| **STALE_VALUE** | `aux_series[k][i]` が NaN、または直前 finite からの距離が `staleness_bars` 超過; `aux_pair_bars[k][i] is None` | 当該 bar 出力 = `np.nan` (warmup 同等)。warning は **発しない**（loader 側で発する想定）。`compute` 経由なら `_make_compute_single` が neutral 値に吸収 | 同左（preflight では検出不能、bar level の data quality 問題） |
| **MISALIGNMENT** | `aux_pair_bars[k][i] is not None and aux_pair_bars[k][i].bar_time != bars[i].bar_time`; `len(aux_*[k]) != len(bars)` | `ValueError` で fail-fast (data bug) | 同左 |

**safe default 値（MISSING_KEY 時）**:
- directional (P5/P7/P8/P9/P12): `0.0` (no signal)
- MODULATOR: P10 → `1.0` (gate open), P6/P11 → `0.5` (neutral gate)

**STALE_VALUE 時の出力**:
- compute_all_bars: `np.nan` を返却 (loader 側 stale 判定 / NaN forward を尊重)
- compute (single point): `_make_compute_single` の neutral 値 (directional=0.0,
  MODULATOR は P10=1.0 / P6/P11=0.5)
- これは F1-F14 の warmup NaN 処理と一貫性

**MISALIGNMENT 時の挙動**:
- ValueError は strict 関係なく必ず raise (data integrity bug)
- 設計上、loader は alignment を保証する責任を持つ → primitive 側はトリビアル check のみ

**preflight verify の入力境界（Codex 2-3 反映）**:

`RegistryEvaluator` の **新 API**:
```python
class RegistryEvaluator:
    def __init__(
        self,
        *,
        pair: str,
        aux_series: Mapping[str, Sequence[float]] | None = None,
        aux_pair_bars: Mapping[str, Sequence[PriceBar | None]] | None = None,
        event_snapshot: EconomicEventSnapshot | None = None,
        vix_snapshot: VixSeriesSnapshot | None = None,
        strict_aux_required: bool = False,
        # 本 TODO 新設: preflight verify の対象 primitive ID 集合
        selected_primitive_ids: Iterable[str] | None = None,
    ) -> None:
        ...
        if strict_aux_required:
            if selected_primitive_ids is None:
                raise ValueError(
                    "strict_aux_required=True requires selected_primitive_ids "
                    "to be provided (preflight verify input)"
                )
            self._preflight_verify(selected_primitive_ids)
```

**preflight verify の処理**:
1. `selected_primitive_ids` 各 ID を `get_primitive(id)` で lookup
2. その `required_data` を集約: union of all required keys
3. 各 key に対し、provider が存在するか確認:
   - `ohlc` / `spread` / `swap` / `calendar.session` → `bars` 自体で provide (常に OK)
   - `calendar.economic_event` → `event_snapshot is not None`
   - `macro.vix` → `vix_snapshot is not None and vix_snapshot.observations`
   - `macro.*` (上記 vix 以外) → `aux_series and key in aux_series`
   - `cross_pair.<pair>` → `aux_pair_bars and <pair> in aux_pair_bars`
4. 不足があれば `RuntimeError("required aux missing for selected primitives: "
   "{id} requires {key}, not provided")` で fail-fast

**production backtest runner（GA entry）の規約（本 TODO 不変条件）**:
- runner は **GA に組み込まれる SignalConfig.name の集合（= selected primitive id）** を
  RegistryEvaluator に渡し `strict_aux_required=True` を設定する
- これにより「ゲノムで選択された primitive の required_data 未充足」が runner 起動時に
  検出される。compute 中に silent 0.0 が混ざる failure を防ぐ
- runner 側の selected ids 抽出ロジックは「現世代 + 過去 elite で参照される全 primitive ID」を
  union する設計（実装は別 TODO だが本 TODO の design 仕様として記録）

**戦略**:
- `MISSING_KEY` は通常テスト/開発フローでも発生するので safe default + warning 路線
  (test を mock で簡易にするため)
- `STALE_VALUE` は loader 側で NaN として表現する責務 → primitive は機械的に NaN 処理
- `MISALIGNMENT` は data integrity bug なので必ず fail-fast
- `strict_aux_required=True` で MISSING_KEY をも production で許さなくなる（preflight）

> **Codex 2-2 反映**: 3 状態の戻り値・テスト期待値が一致するようにテスト戦略にも
> 個別 case を明示する（後述）。

helper 自体（`load_aux_series` など）の実装は別 TODO（aux ingest pipeline）だが、
**preflight verify と strict_aux_required flag は本 TODO で実装し、別 TODO でデータ
注入を始めた瞬間から fail-fast が機能する状態にしておく**。

### L7. P2 IntradayRangeFade の レンジ定義

「アジア時間 (00:00-07:00 UTC) の高値/安値レンジ」を rolling 単位で計算し、
NY 時間に上下限到達時に reversion を出す。

具体:
- 当日 (UTC 日付) の 00:00-07:00 UTC bar の rolling max/min
- bar_time が NY 時間 (12:00-21:00 UTC) で `close > range_high` → -1 (reversion 売り)
- `close < range_low` → +1 (reversion 買い)
- 上下限内 → 0 (no signal)
- 距離は `tanh((close - range_high) / atr)` のように atr 正規化で連続値化

look-ahead bias:
- アジア時間 range は **過去 bar の close** から計算 (current bar の close は使わない)
- 当日のアジア時間 bar は完了済 → bar_time ≥ 07:00 UTC でレンジが確定
- 朝方バー (UTC 07:00-12:00) は range 計算の途中なので signal を 0 で抑制

### L8. P4 YenFixingBias の実装方針

東京仲値 (9:55 JST = 00:55 UTC) 前後の bar で「実需フロー bias」を表現する。
具体的な経済仮説 (Goyenko & Marshall 2024 等で Tokyo fix の AR 効果が報告):
- 仲値 ±30 分 window 内、bar_time が仲値以前 → bias_sign = +1 (実需買い見込み)
- 仲値以後 ±30 分 → bias_sign = -1 (反転バイアス減衰)
- window 外 → 0
- 強度 = `sigmoid(-|Δt| / scale)` × bias_sign

look-ahead: 仲値時刻は固定、bar_time のみ参照、deterministic。

### L9. P12 GoldCorrelationBias の参照方向

ZAR は南アフリカランドで金産出国通貨。金価格上昇 → ZAR 上昇 → USD_ZAR 下落。
`-tanh(gold_momentum)` を返す。「rolling momentum (n bar 前 close との比率)」を
gold series から計算。aux_series["macro.gold"] が None なら warning + 0.0。

### L10. aux_series の freshness / staleness cap（Codex 1-6 反映）

P7/P11 (VIX + SPX/DXY 二経路) および P8/P9/P12 (商品/金 series) は外部データの
publish タイミングが FX bar 軸とずれる:
- VIX は米国市場 close 後 (publication_ts ≈ 21:15 UTC、M5 と同方針)
- SPX, WTI, gold は当該市場の取引時間外 (アジア時間/週末) に値が古くなる
- DXY (FRED DTWEXBGS) は **日次** 系列で更新頻度が低い

本 TODO の **必須仕様**:
- aux_series の各 key に対して `staleness_bars` param を持たせる
  (例: `staleness_bars_default=120` = 5 日 (1h bar 換算))
- 各 bar i において「aux_series[k][i] と直前 finite 値の bar 距離」が `staleness_bars` を
  超えたら **stale 判定 → primitive 出力 NaN (warmup 同等)**
- VIX (publication_ts ベース) は M5 と同様 `bisect_left` 規則。staleness は
  「`bar_time - publication_ts` が 7 日を超えたら stale」を **publication-based 専用 cap** で
  別途 enforce (例: `vix_staleness_days_default=7`)
- **stale 判定発動回数は metric として露出する余地**を残す (本 TODO では metric は実装
  しない、別 TODO で追加)

stale 判定は loader 側でも primitive 側でも実装可能だが、**本 TODO の MVP では
primitive 側で `np.isfinite` チェック + 直前 finite 値からの距離で簡易判定**する。
loader 側で staleness 情報を渡す masked array 設計は別 TODO 案。

## 共通仕様

- 出力: directional [-1, +1] / MODULATOR [0, 1]、warmup は np.nan
- `compute(ctx) -> float` / `compute_all_bars(ctx) -> np.ndarray` の両 API
- `domain = "pair_specific"`
- `required_data` は canonical key で宣言 (新規 macro 系列は L1 で追加)
- `_make_compute_single` ヘルパーを再利用（neutral 値で directional/modulator 切替）
- bar_time は `astimezone(UTC)` で正規化し、UTC 固定時刻と比較

## look-ahead bias 対策（一覧）

| ID | 参照データ | 対策 |
|----|-----------|------|
| P1 | bar_time + ohlc | 自バー時刻と過去 close 系列のみ |
| P2 | bar_time + ohlc | アジア時間 range は完了済バーから |
| P3 | bar_time + ohlc | 東京 open 時刻の前 N バー return から |
| P4 | bar_time のみ | 仲値時刻に対する自バー時刻 Δt のみ |
| P5 | aux_pair_bars (同時刻軸) | bar_time 一致を assert、同 bar close 同士のみ |
| P6 | bar_time + ohlc (ATR) | Wilder ATR は過去のみ |
| P7 | vix_snapshot + spx series | vix は publication_ts < bar_time、spx は bar-aligned forward-fill (loader 責務) |
| P8 | aux_series["macro.copper"] | bar-aligned (loader 責務)、過去 momentum |
| P9 | aux_series["macro.wti"] | 同上 |
| P10 | event_snapshot | M4 と同方針、event.event_time のみ参照、actual 不参照 (rename: ProximityGate) |
| P11 | vix_snapshot + dxy series | M5 と同方針、bisect_left + bar-aligned |
| P12 | aux_series["macro.gold"] | bar-aligned、過去 momentum |

## テスト戦略

`test_modulator_generic.py` のパターンを踏襲。

- `TestRegistryIntegration`: P1-P12 が pair_specific domain として登録、合計 32 件
- `TestEachPrimitiveCommon (parametrize)`: compute == compute_all_bars[idx]、出力域、
  no-lookahead property
- 個別テスト:
  - P1: London-NY 帯で過去 N バー momentum が正なら +、外で 0
  - P2: アジア range 上限超え → -1 寄り、内側 → 0
  - P3: 東京 open 直後ギャップ反転 → 反転方向の signal
  - P4: 仲値 ±30 分で signal が出る、それ以外 0
  - P5: aux_pair_bars 欠損 → warning + 0.0、整合データで residual sign が出る
  - P6: 欧州時間内かつ ATR 高 → 1 寄り
  - P7: vix_snapshot + spx series 欠損 → warning + 0.0、リスクオン (低 VIX + SPX 上昇) で +
  - P8: copper series 欠損 → warning + 0.0、上昇 momentum で +
  - P9: wti series 欠損 → warning + 0.0、上昇 momentum で - (USD_CAD 下落 bias)
  - P10: event_snapshot 欠損 → warning + 1.0、event ±window 内で 0 寄り
  - P11: snapshot/series 欠損 → warning + 0.5、高 VIX + DXY 高で 0 寄り (取引抑制)
  - P12: gold series 欠損 → warning + 0.0、上昇 momentum で - (USD_ZAR 下落 bias)
- **3 状態の挙動別テスト**（Codex 2-2 反映）:
  - MISSING_KEY: aux key 自体未提供 → RuntimeWarning + safe default を全 bar 一括返却
  - STALE_VALUE: aux_series[k][i] = np.nan / aux_pair_bars[k][i] = None → 当該 bar 出力 = np.nan
    （warning は発しない、`compute` は `_make_compute_single` で neutral 値に吸収）
  - MISALIGNMENT: bar_time 不一致 / 長さ不一致 → ValueError raise
- preflight verify: `RegistryEvaluator(strict_aux_required=True, selected_primitive_ids=...)` で
  - 必要 aux 欠損時 RuntimeError raise
  - 必要 aux 揃っているとき正常初期化
  - `strict_aux_required=True` かつ `selected_primitive_ids=None` → ValueError
- strict mode で snapshot/aux 欠損 → RuntimeError
- 後方互換: 既存 F1-F14 / M1-M6 が aux_pair_bars 未指定でも動く

## EvaluationContext 注入経路

T012 で議論した 4 段方針を踏襲:
1. **loader (別 TODO)**: `src/alpha_factory/snapshots.py::load_aux_series(...)` /
   `load_aux_pair_bars(...)` helper
2. **RegistryEvaluator**: `__init__` に `aux_pair_bars` kwarg を追加（default={}）
3. **GA backtest entry (別 TODO)**: 起動時に loader を呼び snapshot/aux を構築
4. **tests**: fixture でモック

本 TODO の `RegistryEvaluator` 改修範囲:
- `aux_pair_bars` を受け付け、`EvaluationContext` に流す
- `event_snapshot` / `vix_snapshot` も既に kwarg 化済（T012）→ 後方互換維持

## Definition of Done

- [ ] `src/alpha_factory/primitives/pair_specific.py` (P1-P12 + ensure_registered)
- [ ] `_base.py` の `EvaluationContext` に `aux_pair_bars` field 追加（default={}）
- [ ] `_base.py` の `RequiredDataKey` に `macro.copper`, `macro.commodity_index`,
      `macro.wti`, `macro.gold` 追加（既存 `is_valid_required_data` の literal 集合
      `_REQUIRED_DATA_LITERALS` も同期更新する。validate_primitive_spec の振る舞いに
      影響しないことを test で confirm）
- [ ] `_registry.py::ensure_registered()` が pair_specific も bootstrap
- [ ] `RegistryEvaluator` に `aux_pair_bars` + `strict_aux_required` +
      `selected_primitive_ids` kwarg 追加 (Codex 1-4/2-3 反映、preflight verify 実装)
- [ ] aux_pair_bars 型は `Mapping[str, Sequence[PriceBar | None]]`、stale を None で表現
- [ ] 12 primitive すべて registry 登録、`pair_specific` domain count = 12, 合計 32
- [ ] `tests/alpha_factory/primitives/test_pair_specific.py` で個別 + parametrize +
      no-lookahead property + aux 注入 + strict mode テスト + preflight verify テスト
- [ ] P5 alignment misalign → ValueError テスト
- [ ] P7/P11 staleness cap 動作テスト
- [ ] 既存テスト全件通過（後方互換）
- [ ] `docs/alpha_factory/primitives.md` に P1-P12 の詳細テーブル追記 (P10 = ProximityGate)
- [ ] mypy / ruff 通過

## 関連 TODO / dependencies

- T010 / T011 / T012 (merged, `667677d`)
- aux_series / aux_pair_bars 本物データ ingest → 別 TODO（OANDA CFD pipeline）
- snapshots loader → 別 TODO

## Should-consider

- S1: P5 CrossPairTriangulation は EUR_USD / USD_JPY の他にも様々な triangle
  (AUD_USD * USD_JPY ↔ AUD_JPY) で展開可能。本 TODO では EUR_JPY 起点だけ実装し、
  triangle 一般化は別 TODO に切り出す
- S2: P10 NADataProximityGate (rename 後) は M4 と機能一部重複。M4 を base とし
  「currency 固定 (USD/CAD)」「session フィルタ (12-21 UTC)」を加えて差別化。
  必要に応じ M4 の param を expose してもよいが、本 TODO は専用 primitive で
  実装の独立性を優先
- S3: aux_series の loader 実装時に「forward-fill 期間の上限」(stale データ拒否) を
  決める必要がある (例: 5 bar 以上前のデータは無効)。本 TODO では loader を実装
  しないため interface のみ定義 (L10 で primitive 側 stale 判定を簡易実装)
- S4: 改善仮説の falsification 条件 (Codex 1-Should-consider 反映): 本 TODO 単体では
  effect を測れないため、後続 RUN で「同 seed・同 budget で pair_specific primitive 群を
  random_gen 候補から外した baseline run」と「含めた treatment run」を比較する設計を
  別 TODO で立てる。Stage A 通過率・純利益分布・trade_count 分布の差分を見る
- S5: Codex は「12 本一括は過大、Phase 1 (P1-P4, P6) と Phase 2 に分割せよ」と
  指摘。本 TODO は **autopilot サイクル指示で 12 個を 1 TODO 範囲と明記**されているため
  分割せず実装する。ただし complexity が想定を超えた場合の中間判断ポイント:
  - Phase 1 = 価格/時刻だけで閉じる P1/P2/P3/P4/P6 を先に実装+テスト
  - Phase 2 = aux 依存 P5/P7/P8/P9/P10/P11/P12 を追加実装
  - Phase 1 で問題噴出時は Phase 2 を別 TODO に切り出して T013 を Phase 1 のみで close する
  この判断ポイントを implement 中の中間チェックとして明示する
- S6: pair_specific 探索空間の肥大化対策: `preferred_pairs` メタデータは別 TODO。
  本 TODO は domain="pair_specific" を crash-safe で他ペアにも適用可能にする
  ことに focus し、preference は GA fitness landscape に任せる
