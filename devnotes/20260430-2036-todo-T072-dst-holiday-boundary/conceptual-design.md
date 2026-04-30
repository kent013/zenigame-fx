# T072 — Timezone / DST / holiday session boundary contract (概念設計)

**作成日時**: 2026-04-30 20:36 JST (Round 2 改訂 20:55、 Round 3 改訂 21:25、 Round 4 改訂 21:50、 Round 5 改訂 22:15)
**親 TODO**: T072 (synthesis § 18.2 T914 — Timezone / DST / holiday session boundary contract: FX 専用 UTC 基準 + 祝日カレンダ + 週末 gap 処理)
**Milestone**: M5 最終 (T070 / T071 完了済、 T072 完了で M5 終結)
**前提 commit**: `main@a8ecd1d` (T071 Observability layer 設計完了時点)
**Round 1 反映**: C1-C6 / W1-W7 / S1-S7 (Round 1 概念レビュー)
**Round 2 反映**: C1-C5 / W1-W7 / S1-S5 (Round 2 概念レビュー) — broker schedule と market holiday observability を完全分離
**Round 3 反映**: C1-C4 / W1-W6 / S1-S5 (Round 3 概念レビュー) — `open_minutes` を primary field 化、 broker date_overrides 追加、 DST season 境界 semantics 確定、 default の granularity-aware 化
**Round 4 反映**: C1 / W1-W6 / S1-S5 (Round 4 概念レビュー) — H3 を granularity 集合から除外 (= 28800 % 10800 ≠ 0、 8h セッション block と非整合)、 closed_full tolerance 別扱い / date_overrides 重複 reject 原則 / production 部分構成 warning / D・W 対象外明記 / to_record(include_derived=True) audit 必須化

**関連設計 (前提)**:
- `devnotes/20260428-2300-cascade-port-debate/synthesis.md` § 4.1 / § 4.4 / § 18.2 T914 / § 15
- `devnotes/20260430-1810-todo-T070-backtest-engine-extension/conceptual-design.md` § 3.2 / § 4 / § 6 (BLOCK_BUCKET_RANGES_UTC SSOT)
- `devnotes/20260430-1810-todo-T070-backtest-engine-extension/detailed-design.md` § 3.1 / § 3.2
- `devnotes/20260430-1925-todo-T071-observability/conceptual-design.md` § 3.6 (`session_pass_pattern` 3 bit)
- `devnotes/20260429-2210-todo-T060-partition-fold-generator/detailed-design.md` § Period

---

## 0. 結論 (TL;DR)

T070 SSOT (`BLOCK_BUCKET_RANGES_UTC`、 `compute_bucket_for_*`、 `aggregate_session_blocks` の date universe = bars+trades touched UTC date set) は **不変**。 T072 は universe 内 block (= 平日中心 + 部分営業 bucket) に対して contract を mark する。 Round 2-3 で broker 配信 schedule と市場 holiday observability を完全分離、 Round 4 で **open_minutes を primary field 化** + **broker date_overrides 追加** + **DST season 境界 semantics 確定** + **default の granularity-aware 化**:

1. **broker 配信 schedule (= expected の唯一の入力)**: `BrokerTradingSchedule` を date-aware API (`open_window_for_utc_date(d) -> tuple[int, int]`) として SSOT 化 (Round 2 [C1] [S1] [S2] / [W4]、 Round 3 [C3] [S2] 反映)。 優先順位 = **`date_overrides` (early close / late open / partial close 等の date 別上書き) > `broker_full_close_holidays` > weekly/DST season > weekday default**。 weekly_close_hour 固定は廃止
2. **市場 holiday observability (= 解釈用、 expected には影響しない)**: `MarketHolidayCalendar` は TSE/LSE/NYSE 公式 holiday (= 観測情報)。 `ObservabilityFlags.holiday_markets` で archive / log に保持、 expected には touch しない (Round 2 [C2] 反映)
3. **bucket-local eligibility は削除** (Round 2 [C3] 反映): FX bucket は流動性時間帯、 holiday 単独除外は collider bias。 T071 caller は `open_minutes > 0` (= broker 配信あり) で判定、 holiday_markets は condition として任意使用。 **collider bias 回避指針**: T071 / T064 / T066 詳細設計に「holiday_markets 単独で drop/filter せず、 必ず stratified audit する」 を統一規範として申し送り (Round 3 [W3] 反映)
4. **`open_minutes` を primary field 化** (Round 3 [C2] [S1] 反映): SessionBlock の primary は `open_minutes` (= broker-open 区間 ∩ bucket UTC 区間 の minutes)。 `expected_bar_count` は `compute_expected_bar_count(open_minutes, granularity_seconds)` 経由で derived (= storage しない)、 `schedule_status` も `open_minutes` から derived。 **粗い granularity で partial 消失問題を解消** (= H4 で Sunday NY 120 min は open_minutes=120 で保持、 expected_bar_count=0 でも schedule_status="closed_partial" を維持)
5. **default の granularity-aware 化** (Round 3 [C1] 反映): broker_schedule=None 時の default は `open_minutes=8*60=480` (= bucket full minutes)、 `expected_bar_count` は granularity_seconds 駆動で計算。 480 hard-code は invariant 昇格しない
6. **DST season 境界 semantics 確定** (Round 3 [C4] 反映): `dst_aware_close_table` の `region_start` / `region_end` は **inclusive**、 region は **互いに disjoint** + `[period_start, period_end]` を **連続 cover**。 春切替日 (= DST 開始日) は **当日が DST region の region_start**、 前日 (土曜) は standard region の region_end。 金曜 close は前々日 standard region の close_hour 採用、 日曜 reopen は当日 DST region の reopen_hour 採用 (= date 単位で切替なので自然)
7. **fail-closed は load 時のみ** (Round 1 [S5] / Round 2 [W3] 完全反映): per-call ValueError 廃止
8. **ObservabilityFlags の精緻化**:
   - `is_dst_transition: bool` → `dst_transition_markets: frozenset[MarketCode]` (Round 2 [W1])
   - `is_g3_holiday` → `all_g3_market_holiday` rename (Round 2 [W2] / Round 3 [S5] 反映、 「market holiday であることを明示」)
9. **complex case 表 § 6.5 で全列挙** (Round 2 [S5] 反映、 H4 Sunday NY reopen / Christmas Eve early close / DST start Friday close vs Sunday reopen を Round 3 [S3] で追加)
10. **tolerance は ceil(max(abs=5, ratio=expected*0.01))** (Round 2 [W6] / Round 3 [W5] 反映、 整数 bar tolerance に固定)
11. **backward-compat の eq/hash は既存 fixture 形式依存** (Round 2 [W7] 反映): 詳細設計で T070 fixture grep
12. **synthesis Round 22 改訂は本 PR と同期 (or 先)** (Round 2 [W5] 反映)
13. **`SessionBlock.to_record(include_derived: bool=False)` を追加** (Round 3 [W1] 反映): asdict は storage field のみ出力、 audit/export consumer が schedule_status / expected_bar_count を見落とすリスクを `to_record(include_derived=True)` で contract 化
14. **broker_special_windows (= date_overrides) を SSOT に追加** (Round 3 [C3] [S2] 反映): early close (= 例: クリスマス前日 18:00 close) / late open / partial close を date 単位で表現
15. **granularity_seconds は M1+ 限定 (M1, M2, M4, M5, M10, M15, M30, H1, H2, H3, H4)** (Round 3 [W4] 反映): 8h を割り切る granularity のみ許容、 S5/S10/S15/S30 は意図的に除外、 「session block は M1+ の complete candle 前提」 を明記
16. **YAML schema に provenance** (Round 3 [W6] 反映): `source` / `verified_at` / `confidence` / `notes` を追加
17. **broker_schedule / calendars 部分構成は test/debug 限定** (Round 3 [W2] 反映): production は「両方 None (= T070 互換)」 or 「両方 provided (= T072 本番)」 を主、 片方のみは test 用途と明記

---

## 1. T072 が解決する問題

### 1.1 T070 で残された未解決事項 (= synthesis § 18.2 T914)

| 残存課題 | T070 での扱い | T072 で解決 |
|---|---|---|
| 営業日 (business_date) の精緻化 | UTC date のまま | business_date 自体は UTC date 維持。 broker 配信時間に基づく overlap で expected_bar_count を導出 |
| 週末 gap | bars が無ければ block 不在 (= date universe SSOT) | T072 は universe 内 block のみ mark。 部分営業 bucket (= 金曜 ny / 日曜 ny / 月曜 tokyo reopen 直後 / DST shift 等) の expected_bar_count を broker schedule overlap で正確判定 |
| 祝日 (Tokyo / London / NY) | 区別不可 | MarketHolidayCalendar で観測情報を YAML 化、 ObservabilityFlags.holiday_markets で持つ。 broker が bar 配信している限り expected_bar_count は影響受けない |
| DST 切替日 (London / NY) | 区別不可 | ObservabilityFlags.dst_transition_markets (= frozenset) で market 別 mark。 expected_bar_count は BrokerTradingSchedule.open_window_for_utc_date が DST shift を date-aware に内包 |
| `is_partial_bar_block` の expected_bar_count | M1 hard-coded 480 | broker schedule の overlap × granularity で導出、 SessionBlock.granularity_seconds で M5/H1 拡張余地 |

### 1.2 T071 / T064 / T066 から T072 への期待 (Round 2 [C3] 大改訂)

- **T071 SessionEntropyMetric**: `session_pass_pattern` (3 bit) を archive member ごとに集計。 T072 は **eligibility を直接提供しない** (= caller 責務に委譲)。 caller は `expected_bar_count > 0` で broker 配信あり判定し、 holiday_markets を任意の condition として使う。 「Tokyo holiday の Tokyo bucket を分母から外す」 か否かは T071 詳細設計の判断 (= collider bias 検証は T071 責務)
- **T064 stage_bc_evaluator**: fold 境界が closed_partial / closed_full を跨ぐ場合の pooled_dd 計算は「expected_bar_count の差を pnl 重み or 除外として下流が決定」、 T072 は事実 field のみ提供
- **T066 cpps_archive**: archive admission 時の session_pass_pattern 生成は T071 caller と同じ semantic (= holiday_markets を任意の condition として使う)

### 1.3 synthesis § 4.1 の前提と Round 22 改訂候補 (Round 2 [W5] 反映)

- 24m primary、 104w
- **synthesis 文言**: 「M1 24/7 fill (週末は実取引なし、 5 営業日/週で評価)」
- **実装現実**: src/ingest/candles.py:80,144 (OANDA `complete=true` のみ upsert) + OANDA M1 candles の週末配信不在
- **synthesis Round 22 改訂候補 (本 PR と同期、 or 先)**: § 4.1 を「M1 source は実質 24/5 (= broker 配信仕様: 金曜 NY close ～ 日曜 NY reopen 不在、 季節別 DST shift)、 週次 reopen/close bucket は部分営業 (= T072 closed_partial)、 5 営業日/週で評価、 holiday は別 layer (= T072 MarketHolidayCalendar) で観測 mark」 に明文化。 **改訂前 merge は上位 SSOT と一時矛盾を生むため、 改訂と T072 は同期推奨 (or 改訂を先に)**

### 1.4 OANDA / FX 週境界の前提 (Round 2 [C1] [C2] 反映)

`src/ingest/candles.py:80,144` および OANDA 開発者仕様より:
- OANDA M1 candles: 金曜 NY close 〜 日曜 NY reopen は配信なし
  - **DST season で時刻が変わる**: 北米 DST 期間中 (3月第2日曜 ～ 11月第1日曜) は 金曜 21:00 UTC close / 日曜 21:00 UTC reopen、 標準時期間は 金曜 22:00 UTC close / 日曜 22:00 UTC reopen
- holiday は通常 bar 配信あり (= observability 情報、 broker availability は不変)
- ただし **broker full-close holiday** (= 例: クリスマス、 新年) は bar 配信が止まる場合がある

→ T072 は:
- `BrokerTradingSchedule.open_window_for_utc_date(d)`: date-aware で DST season + broker full-close holiday を内包
- `MarketHolidayCalendar`: 取引所公式 holiday を観測情報として保持、 expected には影響なし
- 2 つを完全分離 (= broker 配信 schedule ⊥ 市場 holiday observability)

### 1.5 FX bucket = 流動性時間帯 (Round 2 [C3] 反映、 重要)

T070 の `SessionBlockBucket` (Tokyo 0-8 / London 8-16 / NY 16-24 UTC) は **物理取引所ではなく流動性時間帯**:
- bucket="tokyo": 「Tokyo 流動性時間帯 (= JST 9:00-17:00 + α)」 を表すが、 EUR/USD や USD/JPY の取引 bar は東京祝日でも他参加者 (シンガポール、 香港、 シドニー、 ロンドン早朝) によって生じる
- bucket="london": 「London 流動性時間帯」 だが、 LSE 祝日でも EU 大陸 / 中東 / アフリカ参加者の取引は継続
- bucket="ny": 「NY 流動性時間帯」 だが、 NYSE 祝日でも カナダ / 中南米 / アジア前場参加者の取引は (薄いが) 継続

→ **「Tokyo holiday」 を「Tokyo bucket は分母外」 と短絡するのは collider bias** (Round 2 [C3])。 holiday は単に「該当市場の主要参加者が休み」 という観測情報、 流動性時間帯の bar は broker が配信している限り存在する。 T072 は:
- expected_bar_count: broker schedule のみで決定 (= holiday は影響しない)
- holiday_markets: ObservabilityFlags に保持、 caller (T071 / T064 / T066 詳細設計) が分析時に任意の condition として使う

---

## 2. 設計の SSOT 原則

### 2.1 不変 (T070 / T071 / synthesis SSOT)

- `BLOCK_BUCKET_RANGES_UTC` (= Tokyo 0-8 / London 8-16 / NY 16-24 UTC、 8h × 3 covering partition) — T070 SSOT
- `compute_bucket_for_bar` / `compute_bucket_for_trade` — T070 SSOT
- `aggregate_session_blocks` の date universe SSOT — T070 SSOT、 T072 で改変しない
- `business_date` 定義 = UTC date — T070 SSOT
- 24m primary / 104w / stride=4w / 5 営業日/週で評価 — synthesis § 4.1 (Round 22 改訂後)

### 2.2 T072 で新設 (SSOT)

#### 型・定数

- `ScheduleStatus = Literal["regular", "closed_full", "closed_partial"]` (= **derived label**、 storage field ではなく `expected_bar_count` から計算する property)
- `MarketCode = Literal["tokyo", "london", "ny"]` (= 物理市場、 SessionBlockBucket と同字面・別 semantic)
- `HOLIDAY_CALENDAR_VERSION: Final[str] = "1.0.0"`
- `BROKER_SCHEDULE_VERSION: Final[str] = "1.0.0"`
- `M1_GRANULARITY_SECONDS: Final[int] = 60`

#### dataclass

- `BrokerTradingSchedule` (frozen): date-aware open_window_for_utc_date(d) を提供
  - 内部 SSOT: `dst_aware_close_table` (= DST season 別 close hour、 disjoint + 連続 cover) + `broker_full_close_holidays: frozenset[date]` + `date_overrides: Mapping[date, tuple[int, int]]` (Round 3 [C3] [S2]) + `provenance: BrokerSchedulingProvenance` (Round 3 [W6]) + `version`
- `BrokerSeasonalCloseSpec` (frozen): name / region_start (inclusive) / region_end (inclusive) / close_hour_utc / reopen_hour_utc
- `BrokerSchedulingProvenance` (frozen): source / verified_at / confidence / notes (Round 3 [W6])
- `MarketHolidayCalendar` (frozen): 単一市場の観測 holiday、 観測情報のみ
  - 内部: market / period_start / period_end / holidays / schema_version
- `ObservabilityFlags` (frozen):
  - `dst_transition_markets: frozenset[MarketCode]` (= 0..2 個、 Tokyo は不在)
  - `holiday_markets: frozenset[MarketCode]` (= 0..3 個)
  - `has_all_g3_holidays` property (= rename from is_g3_holiday)

#### 関数

- `is_market_holiday(market, d, calendar) -> bool`: market 一致 + 検証済 calendar の raw lookup
- `is_dst_transition(market, d) -> bool`: zoneinfo 駆動 (Tokyo は常に False)
- `compute_observability_flags(business_date, calendars) -> ObservabilityFlags`
- `compute_bucket_open_minutes(business_date, bucket, broker_schedule) -> int`: BrokerTradingSchedule.open_window_for_utc_date(d) と bucket UTC 区間の overlap (= holiday は touch しない)
- `compute_expected_bar_count(open_minutes, granularity_seconds) -> int`: open_minutes × 60 / granularity_seconds
- `validate_calendar_coverage(calendars, broker_schedule, dataset_span) -> None`: load 時集約検証 (= 必須前提)
- `load_market_holiday_calendar(market, yaml_path) -> MarketHolidayCalendar`
- `load_broker_trading_schedule(yaml_path) -> BrokerTradingSchedule`

#### YAML / 設定

- 祝日 YAML scope: 2022-01-01 ～ 2027-12-31 (= dataset 期間 + buffer 1 年)
- `config/calendars/{tokyo,london,ny}_market_holidays.yaml` (= MarketHolidayCalendar 用)
- `config/calendars/broker_trading_schedule.yaml` (= BrokerTradingSchedule 用、 OANDA spec 準拠)

### 2.3 T072 で扱わない (削除案も含む、 Round 2 [C3] 反映)

- **`is_bucket_eligible_for_pattern` を削除**: T071 caller が `expected_bar_count > 0` (= broker 配信あり) で判定、 holiday の意味づけは下流の analytic 責務
- 下流 evaluator (T061 canonical 5 / T064 stage_bc / T071 session entropy / T066 cpps_archive) における status / flags の **意味づけ** (= holiday_markets を condition として使う / 使わないは下流判断)
- T070 caller の BacktestResult.session_blocks 配線 (= Phase 2)
- audit layer (T073) からの統計 export (= T073 で消費)

### 2.4 不変条件の根拠 (Round 2 [W7] 反映で明示)

backward-compat の eq/hash claim は「旧 SessionBlock オブジェクトとの比較」 を意味しない (= dataclass field 追加で旧オブジェクトはそもそも存在しない)。 「**既存 fixture / snapshot の期待値形式が新 default 値と整合するか**」 を検証する。 詳細設計で T070 既存 fixture を grep 確認 (= zenigame-fx で T070 SessionBlock は src 未実装、 fixture も未存在のはず)。

---

## 3. アーキテクチャ概観

```
src/backtest/
├── session_block.py  (T070 SSOT、 dataclass + bucket 計算)
│   ├── BLOCK_BUCKET_RANGES_UTC          [T070 SSOT、 不変]
│   ├── SessionBlockBucket                [T070 SSOT、 不変]
│   ├── SessionBlock                      [T072 で 4 field 追加 + schedule_status は derived property]
│   ├── compute_bucket_for_bar            [T070 SSOT、 不変]
│   ├── compute_bucket_for_trade          [T070 SSOT、 不変]
│   ├── aggregate_session_blocks          [T072 で broker_schedule/calendars 引数 (両方 optional)]
│   └── apply_spread_stress               [T070 SSOT、 不変]
│
└── calendar.py       (T072 新規)
    ├── ScheduleStatus / MarketCode       [T072 SSOT]
    ├── HOLIDAY_CALENDAR_VERSION          [T072 SSOT]
    ├── BROKER_SCHEDULE_VERSION           [T072 SSOT]
    ├── M1_GRANULARITY_SECONDS            [T072 SSOT]
    ├── BrokerTradingSchedule             [T072 SSOT、 frozen dataclass、 date-aware API]
    ├── MarketHolidayCalendar             [T072 SSOT、 frozen dataclass、 観測のみ]
    ├── ObservabilityFlags                [T072 SSOT、 frozen dataclass、 観測のみ]
    ├── load_market_holiday_calendar      [YAML 読込 + invariant]
    ├── load_broker_trading_schedule      [YAML 読込 + invariant]
    ├── validate_calendar_coverage        [dataset_span 一括検証 (calendars + broker_schedule)]
    ├── is_market_holiday                 [検証済 calendar の raw lookup]
    ├── is_dst_transition                 [zoneinfo 経由]
    ├── compute_observability_flags       [business_date 単位の集計]
    ├── compute_bucket_open_minutes       [overlap 計算 (broker schedule のみ、 holiday touch しない)]
    └── compute_expected_bar_count        [open_minutes × granularity 換算]

config/calendars/
├── broker_trading_schedule.yaml          [T072 SSOT、 OANDA spec、 DST table + broker_full_close_holidays]
├── tokyo_market_holidays.yaml            [T072 SSOT、 TSE 公式]
├── london_market_holidays.yaml           [T072 SSOT、 LSE 公式]
└── ny_market_holidays.yaml               [T072 SSOT、 NYSE 公式]
```

### 3.1 T072 が touch する既存ファイル

| ファイル | 改造内容 | 既存挙動への影響 |
|---|---|---|
| `src/backtest/session_block.py` | `SessionBlock` dataclass に `expected_bar_count` / `granularity_seconds` / `observability_flags` の 3 field 追加 (default 値で T070 単独 merge 互換)、 `schedule_status` は `@property` で `expected_bar_count` から計算 (= storage field ではない、 Round 2 [S4] 反映)、 `aggregate_session_blocks` で broker_schedule / calendars 引数追加 | T070 既存 invariant 不変、 default 値で fixture 互換 (詳細設計で grep 確認) |
| `tests/backtest/test_session_block.py` | T072 関連テスト追加 (expected / observability / schedule_status property) | T070 既存テスト不変 |

### 3.2 T072 で新設するファイル

| ファイル | 内容 | 行数概算 |
|---|---|---|
| `src/backtest/calendar.py` | 上記 SSOT 群 | +400 |
| `tests/backtest/test_calendar.py` | F1-F50 + happy path | +450 |
| `config/calendars/broker_trading_schedule.yaml` | DST table + broker_full_close_holidays | +60 |
| `config/calendars/tokyo_market_holidays.yaml` | 2022-01-01 ～ 2027-12-31 | +120 |
| `config/calendars/london_market_holidays.yaml` | 同期間 | +90 |
| `config/calendars/ny_market_holidays.yaml` | 同期間 | +110 |

---

## 4. データ構造 SSOT

### 4.1 ScheduleStatus (= derived label、 Round 2 [C4] [S4] 反映)

```python
ScheduleStatus = Literal["regular", "closed_full", "closed_partial"]
```

**storage field ではない** (= SessionBlock dataclass に保持しない)。 SessionBlock の `@property` として `expected_bar_count` から計算:

```python
@property
def schedule_status(self) -> ScheduleStatus:
    """T072 derived (Round 2 [S4]). expected_bar_count を primary として導出.
    
    SSOT:
        bucket_full_minutes = 8 × 60  # M1: 480 minutes (BLOCK_BUCKET_RANGES_UTC × 60)
        bucket_full_bars = bucket_full_minutes × 60 / granularity_seconds
        - expected_bar_count == bucket_full_bars → "regular"
        - expected_bar_count == 0                → "closed_full"
        - 0 < expected_bar_count < bucket_full_bars → "closed_partial"
    """
```

**Round 2 [C4] 反映**: storage は `expected_bar_count` のみ、 partial 強度の情報は失われない (= 120 vs 360 が caller で観測可能)。

### 4.2 MarketCode (新設)

```python
MarketCode = Literal["tokyo", "london", "ny"]
```

`SessionBlockBucket` (T070) と同字面、 別 semantic (= T070 流動性時間帯 vs T072 物理市場)。 Round 2 [C3] で「物理対応で eligibility を判定するのは collider bias」 と確認、 T072 は MarketCode を **観測 holiday の市場 label** としてのみ使用、 expected には touch しない。

### 4.3 BrokerTradingSchedule (Round 4 改訂、 date_overrides 追加 + DST 境界 semantics 確定)

```python
@dataclass(frozen=True)
class BrokerTradingSchedule:
    """broker (OANDA) の date-aware 配信 schedule SSOT.

    Round 3 [C3] [S2] 反映: open_window_for_utc_date(d) の優先順位 SSOT:
        1. date_overrides[d]              (= early close / late open / partial close 等の date 単位上書き)
        2. broker_full_close_holidays     (= broker 全 closed)
        3. weekday=Sat                    → (0, 0)
        4. weekday=Sun                    → (reopen_hour_utc * 60, 1440)  # season 別
        5. weekday=Fri                    → (0, close_hour_utc * 60)       # season 別
        6. otherwise (Mon-Thu)            → (0, 1440)                      # full open

    内部 SSOT:
        dst_aware_close_table: 季節別 close/reopen 表 (= DST season 別、 region は disjoint かつ連続 cover)
        broker_full_close_holidays: broker 全 closed の holiday set
        date_overrides: date → (start_min, end_min) の date 単位上書き表 (early close 等)
        provenance: source / verified_at / confidence / notes (Round 3 [W6])
        version: BROKER_SCHEDULE_VERSION

    DST season 境界 semantics SSOT (Round 3 [C4] 反映):
        - region_start / region_end は **inclusive** で互いに disjoint + 連続 cover
        - 春切替日 (= 例: 2024-03-10) は **当日が DST region の region_start**、
          前日 (= 2024-03-09 土曜) は standard region の region_end
        - 金曜 close は当日が金曜なら当日 region の close_hour 採用、 日曜 reopen は
          当日 region の reopen_hour 採用 (= 各 date が単一 region に属するため自然)
    """

    dst_aware_close_table: tuple[BrokerSeasonalCloseSpec, ...]
    broker_full_close_holidays: frozenset[date]
    date_overrides: Mapping[date, tuple[int, int]]  # Round 3 [C3] 反映
    period_start: date
    period_end: date
    provenance: BrokerSchedulingProvenance            # Round 3 [W6] 反映
    version: str

    def __post_init__(self) -> None:
        # version == BROKER_SCHEDULE_VERSION
        # dst_aware_close_table は disjoint + 連続区間で [period_start, period_end] cover
        # broker_full_close_holidays ⊂ [period_start, period_end]
        # date_overrides の key は [period_start, period_end] 内 + (start_min, end_min) 妥当 (0..1440, start<=end)
        # **date_overrides と broker_full_close_holidays の重複は reject** (= SSOT 一意性、 Round 3 [C3] / Round 4 [W3] 反映)
        #   理由: ambiguity 防止、 例外的状況は date_overrides に集約する原則
        # season region 重複・隙間検証 (Round 4 [S3])
        # date_overrides 1 日 1 window、 split session は v1 では非対応 (Round 4 [W4] 申し送り)
        ...

    def open_window_for_utc_date(self, d: date) -> tuple[int, int]:
        """SSOT 優先順位 (上記 docstring 参照)."""
        # 1. date_overrides 最優先
        if d in self.date_overrides:
            return self.date_overrides[d]
        # 2. broker_full_close_holidays
        if d in self.broker_full_close_holidays:
            return (0, 0)
        # 3-6. weekday + season
        weekday = d.weekday()
        if weekday == 5:
            return (0, 0)
        spec = self._find_season(d)
        if weekday == 6:
            return (spec.reopen_hour_utc * 60, 1440)
        if weekday == 4:
            return (0, spec.close_hour_utc * 60)
        return (0, 1440)


@dataclass(frozen=True)
class BrokerSeasonalCloseSpec:
    """DST season 別 close/reopen spec.

    SSOT (Round 3 [C4] 反映):
        region_start <= region_end (inclusive)
        region は互いに disjoint
        全 region で [period_start, period_end] を連続 cover (= 隙間なし)
        region 切替日は新 region の region_start (= 同日に新 region の close/reopen 値を使用)
    """
    name: str                 # e.g. "ny_dst" / "ny_standard"
    region_start: date        # inclusive
    region_end: date          # inclusive
    close_hour_utc: int       # 0..23
    reopen_hour_utc: int      # 0..23

    def __post_init__(self) -> None:
        # close_hour_utc / reopen_hour_utc in 0..23
        # region_start <= region_end
        ...


@dataclass(frozen=True)
class BrokerSchedulingProvenance:
    """YAML schema provenance (Round 3 [W6] 反映)."""
    source: str               # 例: "OANDA Developer Portal v20"
    verified_at: date         # YAML 最終確認日
    confidence: Literal["high", "medium", "low"]
    notes: str                # 備考
```

YAML 例 (config/calendars/broker_trading_schedule.yaml):
```yaml
period_start: "2022-01-01"
period_end: "2027-12-31"
version: "1.0.0"
provenance:
  source: "OANDA Developer Portal v20"
  verified_at: "2026-04-30"
  confidence: "high"
  notes: "金曜 NY close / 日曜 NY reopen の標準/DST 切替を IANA tz database から手動列挙"
dst_aware_close_table:
  - name: "ny_dst_2024"
    region_start: "2024-03-10"   # DST 春切替日 = 当日から DST
    region_end:   "2024-11-02"
    close_hour_utc: 21
    reopen_hour_utc: 21
  - name: "ny_standard_2024_2025"
    region_start: "2024-11-03"   # DST 秋切替日 = 当日から standard
    region_end:   "2025-03-08"
    close_hour_utc: 22
    reopen_hour_utc: 22
  # 以降 2025/2026/2027 …
broker_full_close_holidays:
  - "2024-12-25"
  - "2025-01-01"
  # …
date_overrides:                  # 早閉まり / 遅 open / 部分閉鎖
  "2024-12-24":                  # クリスマス前日 = 早閉まり 18:00 UTC close
    - 0                          # start_min
    - 1080                       # end_min (= 18:00 UTC)
  "2024-07-04":                  # 米独立記念日早閉まり 17:00 UTC
    - 0
    - 1020
```

**設計判断**:
- DST shift は date-aware に内包 (= season 別 region で 21/22 UTC を切替)
- broker_full_close_holidays (= broker 自体が bar 出さない) のみが expected を 0 に落とす、 通常の market holiday は touch しない
- season region の境界日は YAML で deterministic に列挙 (= IANA tz database を信頼するが、 broker spec が IANA と異なる可能性に備え自前管理)

### 4.4 MarketHolidayCalendar (新設、 観測のみ、 Round 2 [C2] [S2] 反映)

```python
@dataclass(frozen=True)
class MarketHolidayCalendar:
    """単一市場の取引所公式 holiday (観測情報のみ).
    
    SSOT (Round 2 [C2] [S2] 反映):
        - 用途: ObservabilityFlags.holiday_markets を埋める観測情報
        - expected_bar_count には touch しない (= broker 配信が継続している限り bar 出る)
        - caller (T071 等) は holiday_markets を任意の condition として使う、 T072 は事実 field のみ提供
    """

    market: MarketCode
    period_start: date
    period_end: date
    holidays: frozenset[date]
    schema_version: str

    def __post_init__(self) -> None: ...

    def contains(self, d: date) -> bool:
        """検証済 calendar の raw lookup (Round 1 [S5] / Round 2 [W3] 完全反映).
        
        前提: validate_calendar_coverage が dataset_span を覆うことを load 時に集約検証済.
        period 外 d を渡すのは設計上の bug (= caller 違反).
        実装は AssertionError or silent False を選択、 詳細設計で fix.
        """
        return d in self.holidays
```

### 4.5 ObservabilityFlags (Round 2 [W1] [W2] / Round 3 [S5] 反映)

```python
@dataclass(frozen=True)
class ObservabilityFlags:
    """schedule とは独立の audit / log 用 mark.

    Round 2 / Round 3 反映:
        - is_dst_transition (bool) → dst_transition_markets (frozenset[MarketCode]) [Round 2 W1]
        - is_g3_holiday → has_all_g3_holidays → all_g3_market_holiday (rename、 Round 3 [S5])
    """

    dst_transition_markets: frozenset[MarketCode]  # 0..2 個、 Tokyo は不在
    holiday_markets: frozenset[MarketCode]          # 0..3 個

    def __post_init__(self) -> None:
        # dst_transition_markets ⊂ {"london", "ny"}
        # holiday_markets ⊂ {"tokyo", "london", "ny"}
        ...

    @property
    def all_g3_market_holiday(self) -> bool:
        """Round 3 [S5] rename: len(holiday_markets) == 3 を market holiday であることを明示."""
        return len(self.holiday_markets) == 3
```

### 4.6 SessionBlock (T070 改造、 Round 3 [C1] [C2] [S1] 反映で `open_minutes` を primary 化)

```python
@dataclass(frozen=True)
class SessionBlock:
    # T070 既存 fields (不変)
    business_date: date
    bucket: SessionBlockBucket
    bar_count: int
    trade_count: int
    pnl_net: Decimal
    pnl_before_costs: Decimal
    spread_cost_total: Decimal
    holding_cost_total: Decimal

    # T072 追加 (default で T070 単独 merge 互換)
    open_minutes: int = 480                     # primary field (Round 3 [C2] [S1]、 default は bucket full=8h)
    granularity_seconds: int = 60                # M1 default (Round 2 [C5])
    observability_flags: ObservabilityFlags = field(
        default_factory=lambda: ObservabilityFlags(
            dst_transition_markets=frozenset(),
            holiday_markets=frozenset(),
        )
    )

    def __post_init__(self) -> None:
        # T070 既存 invariant (= bar_count >= 0, F6 等) は不変
        # T072 invariant (Round 3 [W4] / [W5] / [C1] [C2] 反映):
        #   granularity_seconds in M1_PLUS_GRANULARITIES (= 8h を割り切る granularity のみ)
        #   bucket_full_minutes = 8 * 60 = 480 (= BLOCK_BUCKET_RANGES_UTC × 60)
        #   0 <= open_minutes <= bucket_full_minutes
        #   bucket_full_bars = bucket_full_minutes * 60 / granularity_seconds  (= 整数)
        #   expected = compute_expected_bar_count(open_minutes, granularity_seconds)
        #   tolerance = math.ceil(max(5, expected * 0.01))  # 整数 bar tolerance (Round 3 [W5])
        #   bar_count <= expected + tolerance (warning)
        ...

    @property
    def expected_bar_count(self) -> int:
        """Round 3 [C2] derived. open_minutes を primary に昇格、 expected は derived."""
        return compute_expected_bar_count(self.open_minutes, self.granularity_seconds)

    @property
    def schedule_status(self) -> ScheduleStatus:
        """Round 3 [C2] open_minutes から direct derived (= 粗い granularity でも partial 維持).

        SSOT (= bucket_full_minutes 駆動):
            - open_minutes == 480 (= bucket_full_minutes) → "regular"
            - open_minutes == 0                          → "closed_full"
            - 0 < open_minutes < 480                     → "closed_partial"

        例: H4 (granularity_seconds=14400) で Sunday NY 120 min →
            expected_bar_count = 0 (= 120 * 60 / 14400 切捨て)
            schedule_status = "closed_partial" (= open_minutes=120 で保持、 partial 強度を失わない)
        """
        if self.open_minutes == 480:
            return "regular"
        if self.open_minutes == 0:
            return "closed_full"
        return "closed_partial"

    @property
    def is_partial_bar_block(self) -> bool:
        """T070 後方互換 + T072 改訂: bar_count < expected_bar_count."""
        return self.bar_count < self.expected_bar_count

    def to_record(self, *, include_derived: bool = False) -> dict:
        """Round 3 [W1] / Round 4 [W6] audit/export contract.

        include_derived=False (default): storage field のみ (= dataclasses.asdict 同等)
        include_derived=True: schedule_status / expected_bar_count / is_partial_bar_block /
            ObservabilityFlags.all_g3_market_holiday (Round 4 [S5]) 等 derived property も含む

        **audit / export caller は include_derived=True を必須使用** (Round 4 [W6] 反映)。
        backward-compat 最小化のため default は False、 移行用途のみ.
        """
        ...
```

**Round 3 [C1] 反映**: broker_schedule=None default は `open_minutes=480` (= bucket full minutes 固定値、 granularity 非依存)。 expected_bar_count は granularity_seconds から derived で自動的に M1=480 / M5=96 / H4=2 等になる。 480 hard-code は invariant 昇格しない。

**Round 3 [C2] 反映**: schedule_status は open_minutes から derived (= expected_bar_count 経由でない)。 H4 で Sunday NY 120 min → open_minutes=120 / expected_bar_count=0 / schedule_status="closed_partial"。 partial 強度は open_minutes に保持される。

**Round 2 [W7] / Round 3 [W1] 反映**: backward-compat の eq/hash は既存 fixture 形式依存、 詳細設計で T070 fixture grep。 audit/export consumer が schedule_status / expected_bar_count を見落とさないよう `to_record(include_derived=True)` を contract 化。

**Round 3 [W4] / Round 4 [C1] [S1] [S4] 反映**: granularity_seconds は **M1+ かつ 8h (= 28800 秒) を割り切るもの限定**:
```python
M1_PLUS_GRANULARITIES: Final[frozenset[int]] = frozenset({
    60,    # M1
    120,   # M2
    240,   # M4
    300,   # M5
    600,   # M10
    900,   # M15
    1800,  # M30
    3600,  # H1
    7200,  # H2
    14400, # H4
})  # 10 種類、 H3=10800 は 28800 % 10800 = 7200 で除外 (Round 4 [C1] 反映)
```
- S5/S10/S15/S30 は意図的に除外 (= M1+ の complete candle 前提)
- H3 は意図的に除外 (= 8h block と non-integer 整合、 Round 4 [C1])
- D (=86400) / W (=604800) は **session block の対象外** と SSOT 明記 (Round 4 [S4] 反映)、 8h block と概念的に合わない
- 詳細設計で「8h を割り切る integer granularity」 という SSOT を明示

### 4.7 主要関数 SSOT (Round 2 [C2] [C3] 大改訂)

#### compute_observability_flags

```python
def compute_observability_flags(
    business_date: date,
    calendars: Mapping[MarketCode, MarketHolidayCalendar],
) -> ObservabilityFlags:
    """business_date 単位の observability flags 集計.
    
    Round 2 [W1] 反映: dst_transition_markets を frozenset で bucket-local 説明力を保持.
    """
    dst_markets = frozenset(
        m for m in ("london", "ny")
        if is_dst_transition(m, business_date)
    )
    holiday_markets = frozenset(
        m for m in ("tokyo", "london", "ny")
        if is_market_holiday(m, business_date, calendars[m])
    )
    return ObservabilityFlags(
        dst_transition_markets=dst_markets,
        holiday_markets=holiday_markets,
    )
```

#### compute_bucket_open_minutes (Round 2 [C2] 反映、 holiday は touch しない)

```python
def compute_bucket_open_minutes(
    business_date: date,
    bucket: SessionBlockBucket,
    broker_schedule: BrokerTradingSchedule,
) -> int:
    """指定 (date, bucket) の broker-open minutes (= bucket UTC ∩ broker open window).
    
    SSOT (Round 2 [C2] 反映): broker_schedule のみで決定、 market holiday は touch しない.
    
    Args:
        business_date: UTC date
        bucket: SessionBlockBucket (T070)
        broker_schedule: BrokerTradingSchedule (T072 SSOT)
    
    Returns:
        int (0..480 for M1)
    """
    open_start, open_end = broker_schedule.open_window_for_utc_date(business_date)
    start_hour, end_hour = BLOCK_BUCKET_RANGES_UTC[bucket]
    bucket_start_min = start_hour * 60
    bucket_end_min = end_hour * 60
    overlap_start = max(bucket_start_min, open_start)
    overlap_end = min(bucket_end_min, open_end)
    return max(0, overlap_end - overlap_start)
```

#### compute_expected_bar_count (Round 2 [C5] 反映、 granularity-aware)

```python
def compute_expected_bar_count(open_minutes: int, granularity_seconds: int) -> int:
    """granularity から期待 bar 数を導出.
    
    M1 (granularity_seconds=60): open_minutes そのまま
    M5 (granularity_seconds=300): open_minutes / 5
    H1 (granularity_seconds=3600): open_minutes / 60
    """
    return open_minutes * 60 // granularity_seconds
```

#### validate_calendar_coverage (Round 1 [S5] / Round 2 [W3] 完全反映、 必須)

```python
def validate_calendar_coverage(
    calendars: Mapping[MarketCode, MarketHolidayCalendar],
    broker_schedule: BrokerTradingSchedule,
    dataset_span: tuple[date, date],
) -> None:
    """dataset 全期間が calendars + broker_schedule の period 内に収まるか一括検証.
    
    SSOT: load 時に caller が一回呼び、 検証済前提で contains() / open_window_for_utc_date()
    を raw lookup. per-call ValueError は廃止 (Round 2 [W3]).
    
    Raises:
        ValueError: いずれかの calendars / broker_schedule の period が dataset_span を覆わない
        KeyError: calendars に "tokyo" / "london" / "ny" のいずれかが欠落
    """
    ...
```

### 4.8 削除 (Round 2 [C3] 反映)

- **`is_bucket_eligible_for_pattern` を削除**: T071 caller は `expected_bar_count > 0` で broker 配信あり判定、 holiday の意味づけは下流の analytic 責務 (= holiday_markets を condition として使う/使わないは T071 詳細設計判断)
- **per-call ValueError 経路を廃止**: validate_calendar_coverage 必須前提

---

## 5. 主要関数 API SSOT (§ 11.2 SSOT 規約準拠)

```python
# src/backtest/calendar.py

ScheduleStatus = Literal["regular", "closed_full", "closed_partial"]
MarketCode = Literal["tokyo", "london", "ny"]
HOLIDAY_CALENDAR_VERSION: Final[str] = "1.0.0"
BROKER_SCHEDULE_VERSION: Final[str] = "1.0.0"
M1_GRANULARITY_SECONDS: Final[int] = 60


@dataclass(frozen=True)
class BrokerSeasonalCloseSpec:
    name: str
    region_start: date
    region_end: date
    close_hour_utc: int
    reopen_hour_utc: int

    def __post_init__(self) -> None: ...


@dataclass(frozen=True)
class BrokerTradingSchedule:
    dst_aware_close_table: tuple[BrokerSeasonalCloseSpec, ...]
    broker_full_close_holidays: frozenset[date]
    period_start: date
    period_end: date
    version: str

    def __post_init__(self) -> None: ...
    def open_window_for_utc_date(self, d: date) -> tuple[int, int]: ...


@dataclass(frozen=True)
class MarketHolidayCalendar:
    market: MarketCode
    period_start: date
    period_end: date
    holidays: frozenset[date]
    schema_version: str

    def __post_init__(self) -> None: ...
    def contains(self, d: date) -> bool: ...


@dataclass(frozen=True)
class ObservabilityFlags:
    dst_transition_markets: frozenset[MarketCode]
    holiday_markets: frozenset[MarketCode]

    def __post_init__(self) -> None: ...
    @property
    def all_g3_market_holiday(self) -> bool: ...   # Round 3 [S5] rename


def load_market_holiday_calendar(market: MarketCode, yaml_path: Path) -> MarketHolidayCalendar: ...
def load_broker_trading_schedule(yaml_path: Path) -> BrokerTradingSchedule: ...
def validate_calendar_coverage(
    calendars: Mapping[MarketCode, MarketHolidayCalendar],
    broker_schedule: BrokerTradingSchedule,
    dataset_span: tuple[date, date],
) -> None: ...

def is_market_holiday(market: MarketCode, d: date, calendar: MarketHolidayCalendar) -> bool: ...
def is_dst_transition(market: MarketCode, d: date) -> bool: ...

def compute_observability_flags(
    business_date: date,
    calendars: Mapping[MarketCode, MarketHolidayCalendar],
) -> ObservabilityFlags: ...

def compute_bucket_open_minutes(
    business_date: date,
    bucket: SessionBlockBucket,
    broker_schedule: BrokerTradingSchedule,
) -> int: ...

def compute_expected_bar_count(open_minutes: int, granularity_seconds: int) -> int: ...
```

---

## 6. アルゴリズム詳細 (擬似コード)

### 6.1 BrokerTradingSchedule.open_window_for_utc_date (Round 2 [C1] 中核)

```python
def open_window_for_utc_date(self, d: date) -> tuple[int, int]:
    # 1. broker_full_close_holidays は最優先で全 closed
    if d in self.broker_full_close_holidays:
        return (0, 0)
    
    # 2. weekday 別
    weekday = d.weekday()  # 0=Mon..6=Sun
    if weekday == 5:  # Saturday
        return (0, 0)
    
    # 3. season 検索 (dst_aware_close_table から d を含む region を線形探索)
    spec: BrokerSeasonalCloseSpec | None = None
    for s in self.dst_aware_close_table:
        if s.region_start <= d <= s.region_end:
            spec = s
            break
    if spec is None:
        # validate_calendar_coverage で防いでいるはず、 fail-closed
        raise AssertionError(f"date {d} not covered by dst_aware_close_table")
    
    if weekday == 6:  # Sunday
        return (spec.reopen_hour_utc * 60, 1440)
    if weekday == 4:  # Friday
        return (0, spec.close_hour_utc * 60)
    # Mon-Thu
    return (0, 1440)
```

### 6.2 compute_observability_flags

```python
def compute_observability_flags(business_date, calendars):
    dst_markets = frozenset(
        m for m in ("london", "ny") if is_dst_transition(m, business_date)
    )
    holiday_markets = frozenset(
        m for m in ("tokyo", "london", "ny")
        if is_market_holiday(m, business_date, calendars[m])
    )
    return ObservabilityFlags(
        dst_transition_markets=dst_markets,
        holiday_markets=holiday_markets,
    )
```

### 6.3 compute_bucket_open_minutes (broker schedule のみ、 holiday touch しない)

```python
def compute_bucket_open_minutes(business_date, bucket, broker_schedule):
    open_start, open_end = broker_schedule.open_window_for_utc_date(business_date)
    start_hour, end_hour = BLOCK_BUCKET_RANGES_UTC[bucket]
    bucket_start_min = start_hour * 60
    bucket_end_min = end_hour * 60
    overlap_start = max(bucket_start_min, open_start)
    overlap_end = min(bucket_end_min, open_end)
    return max(0, overlap_end - overlap_start)
```

### 6.4 aggregate_session_blocks 改造 (T070 + T072、 Round 3 [W2] 反映で本番は両方提供推奨)

```python
def aggregate_session_blocks(
    bars: Sequence[PriceBar],
    trades: Sequence[Trade],
    *,
    broker_schedule: BrokerTradingSchedule | None = None,
    calendars: Mapping[MarketCode, MarketHolidayCalendar] | None = None,
    granularity_seconds: int = M1_GRANULARITY_SECONDS,
) -> tuple[SessionBlock, ...]:
    """Round 3 [C1] [C2] 反映: open_minutes を primary、 default も granularity-aware.

    部分構成は 4 通り全許容 (semantic 矛盾なし、 broker_schedule と calendars は独立):
        両方 None          → T070 互換 (open_minutes=480 default、 flags=default) [本番非推奨]
        broker_schedule のみ → schedule 駆動、 flags=default                       [test/debug]
        calendars のみ      → flags 駆動、 open_minutes=480 default               [test/debug]
        両方 provided       → フル機能 (= T072 本番)                               [本番推奨]

    Round 3 [W2] 反映: 本番は「両方 None」 (= T070 互換) or 「両方 provided」 (= T072 本番)
        を主用途とし、 片方のみは test/debug 限定。 詳細設計で warning log 付与検討.

    date universe SSOT (T070 不変): bars+trades touched UTC date set × 3 bucket.
    """
    # T070 既存 logic (date_set / 集計)
    ...
    for d in sorted(date_set):
        flags = (
            compute_observability_flags(d, calendars) if calendars is not None
            else ObservabilityFlags(frozenset(), frozenset())
        )
        for bucket in _BUCKETS:
            ...
            if broker_schedule is not None:
                open_min = compute_bucket_open_minutes(d, bucket, broker_schedule)
            else:
                open_min = 480  # bucket full default (Round 3 [C1])

            blocks.append(SessionBlock(
                ..., open_minutes=open_min,
                granularity_seconds=granularity_seconds,
                observability_flags=flags,
            ))
    return tuple(blocks)
```

**Round 3 [C1] 反映**: broker_schedule=None 時の default は `open_minutes=480` (= bucket full minutes、 granularity 非依存)。 expected_bar_count は granularity_seconds 駆動で自動計算 (M1=480 / M5=96 / H4=2)。 480 hard-code は invariant 昇格しない。

**Round 3 [W2] / Round 4 [W5] 反映**: 部分構成は許容するが、 production では「両方 None」 (= T070 互換) or 「両方 provided」 (= T072 本番) を推奨、 片方のみは test/debug 限定。 **詳細設計で `mode: Literal["production", "test"]` 引数を追加し、 `mode="production"` 時に片方のみ渡されたら ValueError raise** (= 誤用防止、 Round 4 [W5] 反映)。

### 6.5 複合ケース表 (Round 2 [S5] 反映)

| Case | weekday | bucket | 状況 | open_window | bucket_range_min | overlap | expected (M1) | schedule_status | flags |
|---|---|---|---|---|---|---|---|---|---|
| C1 平日 normal | Wed | tokyo | no holiday、 standard season | (0, 1440) | (0, 480) | 480 | 480 | regular | default |
| C2 平日 normal | Wed | london | 同上 | (0, 1440) | (480, 960) | 480 | 480 | regular | default |
| C3 平日 normal | Wed | ny | 同上 | (0, 1440) | (960, 1440) | 480 | 480 | regular | default |
| C4 金曜 close standard | Fri | ny | standard season、 close=22:00 | (0, 1320) | (960, 1440) | 360 | 360 | closed_partial | default |
| C5 金曜 close DST | Fri | ny | DST season、 close=21:00 | (0, 1260) | (960, 1440) | 300 | 300 | closed_partial | default |
| C6 土曜 | Sat | any | full closed | (0, 0) | any | 0 | 0 | closed_full | default |
| C7 日曜 reopen standard | Sun | ny | standard、 reopen=22:00 | (1320, 1440) | (960, 1440) | 120 | 120 | closed_partial | default |
| C8 日曜 reopen DST | Sun | ny | DST、 reopen=21:00 | (1260, 1440) | (960, 1440) | 180 | 180 | closed_partial | default |
| C9 日曜 tokyo bucket | Sun | tokyo | reopen=22:00 (= 1320) | (1320, 1440) | (0, 480) | 0 | 0 | closed_full | default |
| C10 月曜 normal | Mon | tokyo | no holiday | (0, 1440) | (0, 480) | 480 | 480 | regular | default |
| C11 Tokyo holiday | Mon | tokyo | TSE 休 | (0, 1440) | (0, 480) | 480 | 480 | regular | holiday_markets={"tokyo"} |
| C12 Tokyo holiday / ny bucket | Mon | ny | TSE 休 | (0, 1440) | (960, 1440) | 480 | 480 | regular | holiday_markets={"tokyo"} |
| C13 G3 holiday (broker open) | Wed | london | TSE+LSE+NYSE 全休、 broker は配信 | (0, 1440) | (480, 960) | 480 | 480 | regular | holiday_markets={tokyo,london,ny} (all_g3_market_holiday=True) |
| C14 broker full close holiday | Wed | london | 12/25 broker 全 closed | (0, 0) | (480, 960) | 0 | 0 | closed_full | holiday_markets={tokyo,london,ny} |
| C15 London DST 切替日 | Sun | london | 春 3月最終日曜、 reopen=22:00 (前日金曜が standard 想定) | (1320, 1440) | (480, 960) | 0 | 0 | closed_full | dst_transition_markets={"london"} |
| C16 NY DST 切替日 (春) | Sun | ny | 3月第2日曜、 reopen 切替日 | (1260 or 1320, 1440) | (960, 1440) | 120 or 180 | 120 or 180 | closed_partial | dst_transition_markets={"ny"} |
| C17 broker_full_close + Tokyo holiday | Wed | tokyo | 12/25 / Tokyo holiday | (0, 0) | (0, 480) | 0 | 0 | closed_full | holiday_markets={tokyo} (london/ny は別途) |
| C18 H4 Sun NY reopen (Round 3 [S3]) | Sun | ny | DST、 reopen=21:00 / granularity=H4 (14400s) | (1260, 1440) | (960, 1440) | 180 | 0 (= 180×60/14400 切捨て) | closed_partial (= open_minutes=180 で保持) | default |
| C19 Christmas Eve early close (Round 3 [S3]) | Tue (12/24) | ny | broker date_overrides[12-24]=(0, 1080) (= 18:00 UTC close) | (0, 1080) | (960, 1440) | 120 | 120 (M1) | closed_partial | default |
| C20 DST start Friday close (Round 3 [S3]) | Fri (前日) | ny | DST 切替日 (= 日曜) の前々日。 当該 Friday は standard region | (0, 1320) | (960, 1440) | 360 | 360 (M1) | closed_partial | default |
| C21 DST start Sunday reopen (Round 3 [S3]) | Sun | ny | DST 切替日 = 当日 DST region 開始、 reopen=21:00 | (1260, 1440) | (960, 1440) | 180 | 180 (M1) | closed_partial | dst_transition_markets={"ny"} |
| C22 calendars only (test/debug、 Round 3 [W2]) | Wed | london | calendars provided / broker_schedule=None | (0, 1440) [default] | (480, 960) | 480 [default] | 480 (M1) | regular | flags 駆動 (例: holiday_markets={"tokyo"}) |

**重要**:
- C11 / C12: Tokyo holiday でも bucket="ny" の open_window は影響なし (= broker は配信)、 expected=480 / regular。 holiday_markets は別軸 mark
- C13: G3 全休でも broker が配信していれば expected=480 / regular。 has_all_g3_holidays=True を caller が見て分析
- C14: broker_full_close は最優先で expected=0
- C15-C16: DST 切替日も schedule は date-aware で正確、 dst_transition_markets で観測

### 6.6 is_dst_transition (zoneinfo)

```python
def is_dst_transition(market: MarketCode, d: date) -> bool:
    if market == "tokyo":
        return False
    tz = ZoneInfo("Europe/London") if market == "london" else ZoneInfo("America/New_York")
    midnight_today = datetime.combine(d, time(0, 0), tzinfo=tz)
    midnight_tomorrow = datetime.combine(d + timedelta(days=1), time(0, 0), tzinfo=tz)
    return midnight_today.utcoffset() != midnight_tomorrow.utcoffset()
```

---

## 7. 既存挙動への影響 (C2 parallel-path)

### 7.1 直 import 経路

`src/backtest/calendar.py` 新規。 既存 touch は `src/backtest/session_block.py` のみ。 primitives `_SESSION_RANGES_UTC` は別責務、 T072 で touch しない。

### 7.2 5 段階 grep

- 直 import: Phase 1 では `src/backtest/session_block.py` のみ
- alias / relative / 再エクスポート: なし
- runtime シンボル: T072 field 参照は Phase 2 で T061 / T064 / T071 / T066 から (= まだ実装されていない)

### 7.3 fail-closed 経路

- YAML 読込失敗 → ValueError
- schema_version / version 不一致 → ValueError
- holidays / broker_full_close_holidays が period 外 → ValueError
- dst_aware_close_table の region 重複 / 隙間 → ValueError
- market 不一致 (YAML vs 引数) → ValueError
- DST 判定で zoneinfo data 不在 → ZoneInfoNotFoundError (= 環境異常)
- validate_calendar_coverage 失敗 → ValueError (= load 時集約検証、 必須前提)

---

## 8. 不変条件 (invariant)

| ID | 不変条件 | 担保 |
|---|---|---|
| I1 | BLOCK_BUCKET_RANGES_UTC は T072 で touch しない | T070 SSOT |
| I2 | compute_bucket_for_bar / compute_bucket_for_trade は T072 で touch しない | T070 SSOT |
| I3 | aggregate_session_blocks の date universe は T070 SSOT のまま | T070 SSOT |
| I4 | SessionBlock.open_minutes in [0, 480] (= bucket_full_minutes 範囲、 Round 3 [S1] 反映) | __post_init__ |
| I5 | bucket_full_bars = 480 × 60 / granularity_seconds が整数 (= granularity_seconds が 28800 秒を割り切る) | __post_init__ |
| I6 | expected_bar_count = compute_expected_bar_count(open_minutes, granularity_seconds) (= derived 整合) | property、 storage しない (Round 3 [C2]) |
| I7 | granularity_seconds in M1_PLUS_GRANULARITIES (= {60, 120, 240, 300, 600, 900, 1800, 3600, 7200, 14400} の 10 種類、 H3 除外、 Round 4 [C1] [S1] 反映) | __post_init__ |
| I8 | (open block) bar_count <= expected_bar_count + ceil(max(5, expected_bar_count * 0.01)) (Round 3 [W5] 整数固定)。 (closed_full block) bar_count == 0 を厳密期待、 1-5 bar も warning escalation 対象 (Round 4 [W2] 反映) | __post_init__ で warning |
| I9 | ObservabilityFlags.dst_transition_markets ⊂ {"london", "ny"} | __post_init__ |
| I10 | ObservabilityFlags.holiday_markets ⊂ {"tokyo", "london", "ny"} | __post_init__ |
| I11 | MarketHolidayCalendar.holidays ⊂ [period_start, period_end] | __post_init__ |
| I12 | MarketHolidayCalendar.schema_version == HOLIDAY_CALENDAR_VERSION | __post_init__ |
| I13 | BrokerTradingSchedule.version == BROKER_SCHEDULE_VERSION | __post_init__ |
| I14 | BrokerTradingSchedule.dst_aware_close_table が [period_start, period_end] を連続区間で全 cover | __post_init__ |
| I15 | BrokerTradingSchedule.broker_full_close_holidays ⊂ [period_start, period_end] | __post_init__ |
| I16 | BrokerSeasonalCloseSpec.close_hour_utc / reopen_hour_utc in 0..23 | __post_init__ |
| I17 | is_dst_transition("tokyo", d) == False (常に) | early return |
| I18 | is_dst_transition("london"/"ny") は zoneinfo deterministic | unit test 6 件 (重要 transition 2024-2026) |
| I19 | open_window_for_utc_date(d) は d in broker_full_close_holidays または d.weekday()==5 で (0, 0)、 他は妥当な (start, end) with start<=end | unit test |
| I20 | schedule_status / expected_bar_count は open_minutes + granularity_seconds から derived (= storage しない、 Round 3 [C2]) | @property、 不一致は構造上不可能 |
| I21 | compute_bucket_open_minutes は broker_schedule のみで決定 (= holiday 入力なし) | 関数 signature で構造強制 (Round 2 [C2]) |
| I22 | T070 既存 SessionBlock invariant (bar_count >=0, F6 等) は不変 | __post_init__ 旧 logic 不変 |

---

## 9. リスクと緩和

| リスク | 影響 | 緩和 |
|---|---|---|
| F1 holiday YAML / broker schedule の更新漏れ | 評価 fail | period 外で validate_calendar_coverage が ValueError、 buffer 1 年、 詳細設計で「YAML 更新 SOP」 |
| F2 zoneinfo data の OS 依存 | DST 判定誤 | bundled 前提、 重要 transition 6 件 unit test 固定値、 詳細設計で runtime tzdata version log |
| F3 broker spec 変更 (= OANDA close 時刻 季節差変更等) | overlap 計算誤 | BrokerTradingSchedule YAML 更新、 別 PR、 dst_aware_close_table の region で deterministic 管理 |
| F4 weekday 判定で日曜全閉と誤判定 (Round 1 [C2] 防止) | partial bucket 漏れ | open_window_for_utc_date(d) の date-aware SSOT、 weekday + season + broker_full_close_holidays の disjoint 判定 |
| F5 schedule_status を storage field に保持すると derived と齟齬 (Round 2 [C4] 防止) | partial 強度情報落ち | schedule_status は @property derived、 storage は expected_bar_count のみ |
| F6 holiday を expected_bar_count に混ぜる (Round 2 [C2] 防止) | broker availability vs market holiday observability の混同 | I21 で関数 signature 強制、 holiday は ObservabilityFlags にのみ持つ |
| F7 bucket-local eligibility の collider bias (Round 2 [C3] 防止) | T071 entropy 計算 bias | is_bucket_eligible_for_pattern 削除、 T071 caller が holiday_markets を condition として任意使用 |
| F8 SessionBlock dataclass field 追加で T070 既存テスト breakage | 互換性 | § 11 で 4 面 backward-compat 検証、 詳細設計で T070 fixture grep |
| F9 expected_bar_count = 480 hard-code (Round 2 [C5] 防止) | granularity 変更耐性損失 | granularity_seconds から bucket_full_bars 導出、 default は M1=60 (= 480) |
| F10 schedule と calendars の部分構成 | semantic 揺らぎ | broker_schedule と calendars は完全独立 (Round 2 [C2] 反映)、 4 通り (両方 / どちらかのみ / 両方 None) を全許容、 部分構成でも矛盾しない |
| F11 universe に未来日が含まれる | YAML period 外で validate fail | aggregate_session_blocks の date universe は bars+trades touched (= run 期間内のみ)、 buffer で安全 |
| F12 holiday list の精度 | holiday_markets 漏れ | YAML source = 主要取引所公式 calendar、 詳細設計で source URL 明示、 audit log で集計 |
| F13 dst_transition_markets の bucket 別観測精度 (Round 2 [W1] 反映) | 「London DST と NY DST の cross-bucket 影響」 観測 | frozenset で 0..2 個保持、 caller が任意の bucket 別 audit |
| F14 BrokerTradingSchedule.version forward-compat | 旧 YAML 読込破壊 | __post_init__ で reject、 移行は別 PR |
| F15 tolerance buffer 絶対値固定の bias (Round 2 [W6] 反映) | expected=120 で 5 bar = 4.2% 過剰許容 | tolerance = max(5, expected_bar_count * 0.01)、 abs / ratio の max |

---

## 10. テスト計画 (概要、 詳細は detailed-design.md で)

### 10.1 pure function tests

- F1: `is_dst_transition("tokyo", d)` — 任意 date で False
- F2: `is_dst_transition("london", d)` — 2024-2026 春 (3月最終日曜) / 秋 (10月最終日曜)、 重要 transition 6 件 + 他 False
- F3: `is_dst_transition("ny", d)` — 2024-2026 春 (3月第2日曜) / 秋 (11月第1日曜)、 重要 transition 6 件 + 他 False
- F4: `is_market_holiday` — period 内 True / False、 market 不一致 ValueError

### 10.2 BrokerSeasonalCloseSpec / BrokerTradingSchedule tests

- F5: BrokerSeasonalCloseSpec(hour_utc=24) → ValueError
- F6: dst_aware_close_table が region 重複 → ValueError
- F7: dst_aware_close_table が region 隙間 (= period 内 cover 不完全) → ValueError
- F8: open_window_for_utc_date / 平日 → (0, 1440)
- F9: open_window_for_utc_date / 土曜 → (0, 0)
- F10: open_window_for_utc_date / 日曜 / standard season → (1320, 1440)
- F11: open_window_for_utc_date / 日曜 / DST season → (1260, 1440)
- F12: open_window_for_utc_date / 金曜 / standard → (0, 1320)
- F13: open_window_for_utc_date / 金曜 / DST → (0, 1260)
- F14: open_window_for_utc_date / broker_full_close_holiday → (0, 0)

### 10.3 MarketHolidayCalendar tests

- F15: happy path (load + contains + period 内 lookup)
- F16: schema_version 不一致 ValueError
- F17: market 不一致 ValueError
- F18: holidays が period 外 ValueError

### 10.4 ObservabilityFlags / compute_observability_flags tests

- F19: dst_transition_markets ⊂ {"london","ny"}
- F20: holiday_markets ⊂ {"tokyo","london","ny"}
- F21: has_all_g3_holidays 判定
- F22: 平日 / no holiday / no DST → flags=default
- F23: G3 holiday → holiday_markets={"tokyo","london","ny"}
- F24: London DST 切替 + NY 通常 → dst_transition_markets={"london"}
- F25: 同日 London/NY 切替 → dst_transition_markets={"london","ny"}

### 10.5 compute_bucket_open_minutes / compute_expected_bar_count tests

- F26: Mon-Thu / 全 bucket → 480 / expected=480 (M1)
- F27: Sat / 全 bucket → 0 / expected=0
- F28: Sun / tokyo → 0 (reopen=22:00 は ny bucket 内)
- F29: Sun / ny / standard → 120 / expected=120
- F30: Sun / ny / DST → 180 / expected=180
- F31: Fri / ny / standard → 360
- F32: Fri / ny / DST → 300
- F33: Fri / tokyo → 480 (close=22:00 は ny bucket、 tokyo bucket 影響なし)
- F34: Mon-Thu / Tokyo holiday / tokyo bucket → 480 (= holiday は touch しない、 Round 2 [C2])
- F35: Mon-Thu / G3 holiday / 全 bucket → 480 (= broker 配信あり、 holiday_markets observability のみ)
- F36: broker_full_close_holiday / 全 bucket → 0
- F37: M5 granularity (granularity_seconds=300) → expected = open_minutes / 5

### 10.6 SessionBlock backward-compat tests (Round 1 [S7] / Round 2 [W7] 4 面)

- F38: SessionBlock(default) constructor → expected_bar_count=480 / granularity_seconds=60 / flags=default
- F39: schedule_status property derived: regular/closed_full/closed_partial 全 case
- F40: 既存 fixture (T070 想定) を構築して `==` 比較で True (= eq/hash 互換)
- F41: dataclasses.asdict で T072 field 含む dict、 T070 既存 caller 不変 (詳細設計で grep 確認)
- F42: invariant violation: granularity_seconds=45 → ValueError (I7)
- F43: invariant violation: expected_bar_count=500 / M1 → ValueError (I6)
- F44: bar_count = expected + 6 / expected=120 → tolerance = max(5, 1.2) = 5、 violation warning

### 10.7 aggregate_session_blocks 改造 tests

- F45: 全 None → 全 block default (= T070 互換)
- F46: broker_schedule のみ → expected 駆動、 flags=default
- F47: calendars のみ → flags 駆動、 expected=480
- F48: 両方 → フル機能
- F49: 金曜 ny / standard / broker_schedule → expected=360

### 10.8 validate_calendar_coverage tests

- F50: dataset_span が calendars + broker_schedule period 内 → 正常
- F51: dataset_span が calendars period 外 → ValueError
- F52: dataset_span が broker_schedule period 外 → ValueError
- F53: calendars に market 欠落 → KeyError

---

## 11. backward-compat 4 面検証 (Round 1 [S7] / Round 2 [W7] 反映)

### 11.1 constructor 互換

```python
# 既存 (T070 単独)
block = SessionBlock(
    business_date=date(2024, 1, 15), bucket="tokyo",
    bar_count=480, trade_count=3,
    pnl_net=Decimal("10"), pnl_before_costs=Decimal("12"),
    spread_cost_total=Decimal("1"), holding_cost_total=Decimal("1"),
)
# T072 後: expected_bar_count=480 / granularity_seconds=60 / observability_flags=default
# 既存 positional/keyword 互換 ✓
```

### 11.2 eq / hash 互換 (Round 2 [W7])

T072 default 値で構築された block と「既存 fixture の期待値形式」 が一致するかは fixture 側依存。 詳細設計で T070 既存 fixture (= test_session_block.py 内の SessionBlock 構築) を **grep で全列挙**、 default 値拡張で互換性を確認。

zenigame-fx で T070 SessionBlock は **src 未実装** (= 設計 only) のため、 fixture も未存在の見込み。 詳細設計で再確認。

### 11.3 serialization / asdict / repr 互換

`dataclasses.asdict(block)` の出力にキー集合厳密一致をテストしている caller があれば breakage 候補。 T070 SessionBlock は src 未実装で caller 不在の見込み (詳細設計で grep)。

### 11.4 既存 fixture / snapshot 互換

T070 detailed-design F1-F22 全 test pass を T072 PR で確認。 T070 docstring SSOT 不変。

---

## 12. Phase 1 / Phase 2 分離

### 12.1 Phase 1 (T072 PR)

含む:
- `src/backtest/calendar.py` 新規 (上記 SSOT 群、 BrokerTradingSchedule + MarketHolidayCalendar の 2 軸完全分離)
- `src/backtest/session_block.py` の SessionBlock 改造 (= 3 field 追加 + schedule_status property)
- `aggregate_session_blocks` の broker_schedule / calendars / granularity_seconds 引数 (全 optional)
- `tests/backtest/test_calendar.py` 新規 (F1-F53)
- `tests/backtest/test_session_block.py` の T072 関連テスト (F38-F49)
- `config/calendars/{tokyo,london,ny}_market_holidays.yaml` 新規 (2022-01-01 ～ 2027-12-31)
- `config/calendars/broker_trading_schedule.yaml` 新規 (DST table + broker_full_close_holidays)
- 単体テストのみで runtime 未組込 (= Phase 1 共通原則)

含まない:
- T061 / T064 / T066 / T071 で expected_bar_count / observability_flags 消費 (= Phase 2)
- run_ga.py / backtest_runner で broker_schedule / calendars 必須化 (= Phase 2)

### 12.2 Phase 2 (別 TODO、 cascade port 切替時)

- `aggregate_session_blocks` の broker_schedule / calendars 引数を必須化 (= None 経路廃止)
- T061 で `expected_bar_count` 駆動の HAC SR 計算 (= n 補正)
- T064 で fold 境界の closed_partial / closed_full 扱い (= pnl=0 重みづけ or 除外)
- T071 SessionEntropyMetric の入力で `expected_bar_count > 0` の bucket のみ集計 + holiday_markets を任意 condition として使用
- T066 cpps_archive で同 semantic
- run_ga.py で broker_schedule / calendars を load + 伝搬

### 12.3 Phase 2 申し送り (詳細設計で明文化)

- T061 / T064 / T066 / T071 の詳細設計改訂申し送りリスト
- holiday_markets を pattern 計算分母から除外するか否かは **T071 詳細設計判断** (= Round 2 [C3] collider bias 検証含む)

### 12.4 synthesis Round 22 改訂候補 (Round 1 [W5] / Round 2 [W5] 反映)

§ 4.1 改訂案:
- 旧: 「M1 24/7 fill (週末は実取引なし、 5 営業日/週で評価)」
- 新: 「M1 source は実質 24/5 (= broker 配信仕様: 金曜 NY close ～ 日曜 NY reopen 不在、 季節別 DST shift)、 週次 reopen/close bucket は部分営業 (= T072 closed_partial)、 5 営業日/週で評価、 holiday は別 layer (= T072 MarketHolidayCalendar) で観測 mark」

**Round 2 [W5] 反映**: synthesis 改訂と T072 PR を **同期 merge** (= 上位 SSOT との一時矛盾を回避)。 改訂が separate PR の場合は **改訂を先 merge** が次善。

---

## 13. 設計判断 SSOT (synthesis 確定値 vs T072 設計判断値)

### 13.1 synthesis 確定値 (= 厳密準拠)

- 24m primary (104w)、 stride=4w
- M1 source は 5 営業日/週で評価 (synthesis § 4.1、 Round 22 改訂後)
- 8h × 3 covering partition、 UTC 基準 (synthesis § 4.4 / T070 SSOT)
- DST/holiday 詳細境界は T914 で contract 化 (synthesis § 15)

### 13.2 T072 設計判断値 (= synthesis 未明示)

- 主要 3 市場 = Tokyo / London / NY (= G3、 EUR/USD/JPY 中心の major pairs に整合)
- 祝日 source = 静的 YAML (Python `holidays` library / `pandas_market_calendars` 不使用、 deterministic 重視)
- ScheduleStatus enum 3 値 (regular / closed_full / closed_partial)、 derived label
- ObservabilityFlags = dst_transition_markets (frozenset) + holiday_markets (frozenset)、 直交 mark
- BrokerTradingSchedule = date-aware open_window_for_utc_date(d)、 DST shift と broker_full_close_holidays を内包
- DST 切替判定 = `zoneinfo` (Python stdlib) 経由
- expected_bar_count = open_minutes × 60 / granularity_seconds、 granularity-aware
- tolerance = max(5, expected * 0.01)、 abs / ratio の max
- holiday list 期間 = 2022-01-01 ～ 2027-12-31
- M1 default granularity_seconds = 60
- bucket と holiday market は **直交** (= holiday は expected に touch しない、 collider bias 回避)
- broker 配信 schedule と市場 holiday observability の **完全分離** (Round 2 [C2] 反映)

---

## 14. T073 以降への申し送り

- **T073 audit layer**: T072 expected_bar_count / observability_flags / dst_transition_markets / holiday_markets を audit input として消費。 holiday market 別 / DST shift 別 trade 量 / spread 統計を export
- **T075 smoke**: 5 Run 連続で expected / flags 値の deterministic 性を検証 (= 同 dataset で同 hash)
- **T071 Phase 2**: SessionEntropyMetric 計算で `expected_bar_count > 0` の bucket のみ集計、 holiday_markets を任意 condition として使用 (= collider bias 検証は T071 責務)
- **T064 Phase 2**: pooled_dd_per_fold_max 計算で expected_bar_count に応じた重みづけ or 除外
- **synthesis Round 22 改訂**: § 4.1 「M1 24/7 fill」 → 「実質 24/5、 季節別 DST、 reopen/close bucket は部分営業」 を本 PR と同期推奨

---

## 15. open questions (詳細設計で解消)

1. **YAML schema 詳細**: provenance field (`source_url` / `published_by` / `last_verified_at`) を含めるか
2. **tolerance buffer**: max(5, expected * 0.01) は妥当か / 他比率検討 (5 bar / 1% / 2% trade-off)
3. **broker_schedule 必須化タイミング**: Phase 1 (optional) → Phase 2 (必須化) の移行タイミング
4. **runtime tzdata version log**: T071 RunObservabilityReport に zoneinfo version export
5. **YAML location**: `config/calendars/` で確定 (vs `config/alpha_factory/calendars/`)
6. **MarketHolidayCalendar.contains の period 外 lookup**: AssertionError vs silent False、 detailed で fix
7. **dst_aware_close_table の region 表現**: tuple of BrokerSeasonalCloseSpec で deterministic 列挙、 IANA tz 自動生成オプション検討 (= 詳細設計で trade-off)
8. **T072 v1 で broker holiday early-close 対応**: クリスマス前日の早閉まり (= 18:00 UTC close 等) は v1 で対応するか v2 送り (= broker_full_close_holidays 拡張で `early_close_hour_utc` 追加)
9. **schedule_status の名称**: storage field でないが「property」 として残すか / 完全削除して caller が直接 expected_bar_count で判定するか (= caller 利便性 vs minimal API)
10. **caller が holiday_markets を pattern 分母 condition に使う統一指針**: Phase 2 で T071 / T066 の合議が必要 (= 同 semantic を保つ)

---

## 16. references / cross-cut

| 項目 | 場所 |
|---|---|
| synthesis § 4.1 (24m / M1 source / 5 営業日/週) | `devnotes/20260428-2300-cascade-port-debate/synthesis.md` |
| synthesis § 4.4 (8h × 3 covering partition、 T070 SSOT 上位) | 同上 |
| synthesis § 15 (T914 INCONCLUSIVE 一覧) | 同上 |
| synthesis § 18.2 T914 (= 本 TODO の親条文) | 同上 |
| T070 BLOCK_BUCKET_RANGES_UTC (T072 で不変) | 設計: `devnotes/20260430-1810-todo-T070-backtest-engine-extension/` |
| T070 SessionBlock.is_partial_bar_block (T072 で expected_bar_count 駆動に改訂) | 同上 detailed-design.md § 3.2 |
| T071 session_pass_pattern 3 bit (T072 hard dependency: caller が holiday_markets / expected_bar_count > 0 を任意使用) | `devnotes/20260430-1925-todo-T071-observability/conceptual-design.md` § 3.6 |
| OANDA M1 fill 仕様 | `src/ingest/candles.py:80,144` |
| Period UTC 厳密性 (T060) | `devnotes/20260429-2210-todo-T060-partition-fold-generator/detailed-design.md` § Period |
| primitives `_SESSION_RANGES_UTC` (9h overlap、 T072 で touch しない別責務) | `src/alpha_factory/primitives/_indicators.py:51-55` |

---

## 17. 学術文献 (Round 1-2 引用候補)

- Andersen, T.G. & Bollerslev, T. (1998). *Deutsche Mark-Dollar Volatility: Intraday Activity Patterns, Macroeconomic Announcements, and Longer Run Dependencies.* (要確認、 intraday session boundary)
- Dacorogna, M. et al. (2001). *An Introduction to High-Frequency Finance.* (要確認、 FX 24h 取引 / session 境界扱い)
- Müller, U.A. et al. (1990). *Statistical Study of Foreign Exchange Rates, Empirical Evidence of a Price Change Scaling Law, and Intraday Analysis.* (要確認、 intraday FX activity)
- Goodhart, C. & O'Hara, M. (1997). *High Frequency Data in Financial Markets.* (要確認)
- Eggert, P. et al. *IANA Time Zone Database.* (DST contract 一次資料)
- RFC 6557 / RFC 8536 (= timezone operational dependency 一次資料)
- OANDA Developer Portal, *Instrument candle specification.* (broker session 一次資料、 詳細設計で URL 確定)

---

## 18. Round 1 → Round 4 対応マトリクス (累積)

### Round 1 → Round 2 対応 (= 既存)

| Round 1 | Round 2 対応 |
|---|---|
| C1 universe 不在 | T070 SSOT 不変、 universe 内 block のみ mark |
| C2 FX 週境界 | overlap 駆動 + BrokerSession 導入 |
| C3 DST が weekend に食われる | 2 軸独立 (schedule_status + observability_flags) |
| C4 holiday_partial 粒度 | bucket-local eligibility 切出 |
| C5 expected_bar_count invariant | overlap 駆動 |
| C6 backward-compat 不十分 | § 11 で 4 面検証 |
| W1 YAML provenance | 詳細設計 |
| W2-W7 / S1-S7 | 全反映 |

### Round 2 → Round 3 対応

| Round 2 | Round 3 対応 |
|---|---|
| C1 BrokerSession の UTC hour 固定不十分 | § 4.3 で BrokerTradingSchedule に改名、 date-aware open_window_for_utc_date(d) + dst_aware_close_table + broker_full_close_holidays を内包 |
| C2 holiday を expected に混ぜたのは責務混同 | § 4.4 / § 4.7 / § 6.3 / I21 で broker schedule と market holiday を完全分離、 holiday は ObservabilityFlags のみ |
| C3 bucket-local eligibility は collider bias | § 4.8 で is_bucket_eligible_for_pattern 削除、 caller が expected_bar_count > 0 + holiday_markets で任意判定 |
| C4 closed_partial 情報落ち | § 4.1 / § 4.6 で schedule_status を derived property、 expected_bar_count を primary field |
| C5 regular=480 invariant 残存 | § 4.6 / I5-I7 で granularity_seconds から bucket_full_bars 導出、 480 hard-code を invariant 昇格しない |
| W1 dst_transition_markets bucket-local | § 4.5 で frozenset[MarketCode] 化 |
| W2 is_g3_holiday 名前危険 | § 4.5 で has_all_g3_holidays に rename |
| W3 validate + per-call 二重 | § 4.4 で per-call ValueError 廃止、 validate_calendar_coverage 必須前提 |
| W4 calendar 責務混在 | § 4.3 / § 4.4 で BrokerTradingSchedule (broker 配信) と MarketHolidayCalendar (観測) を分離 |
| W5 synthesis Round 22 タイミング | § 12.4 で同期 merge (or 改訂先) を明示 |
| W6 tolerance buffer 比率 | I8 で max(5, expected * 0.01) |
| W7 backward-compat 既存 fixture grep | § 11.2 で詳細設計 grep を明記 |
| S1 BrokerTradingSchedule rename | § 4.3 で採用 |
| S2 MarketHolidayCalendar / BrokerTradingCalendar 分離 | § 4.3 / § 4.4 で採用 (BrokerTradingSchedule + MarketHolidayCalendar) |
| S3 PatternEligibility 拡張 | § 4.8 で eligibility 削除 (= caller 委譲)、 別 form の dataclass は不要 |
| S4 schedule_status を derived | § 4.1 / § 4.6 で property 化 |
| S5 複合ケース表 | § 6.5 で 17 ケース全列挙 |

### Round 4 → Round 5 対応

| Round 4 | Round 5 対応 |
|---|---|
| C1 H3=10800 が I5 (28800 % g == 0) と矛盾 | M1_PLUS_GRANULARITIES から H3 除外、 10 種類に確定 (Round 4 [S1] 採用) |
| W1 tolerance ratio 実質 unused | docstring で「M1 で expected<=480 の範囲では abs=5 が常時発火、 ratio 1% は将来 H4 拡張用」 を明記 |
| W2 closed_full の tolerance 過剰 | I8 を「open block」 と「closed_full block」 で分離、 closed_full は厳密 0 期待 + 1-5 bar も warning escalation |
| W3 date_overrides と broker_full_close_holidays 重複 | __post_init__ で reject 原則 SSOT、 ambiguity 防止 |
| W4 同日 split session 不可 | v1 制約として明記、 v2 申し送り |
| W5 部分構成 production 誤用 | mode=production 引数で reject (= 詳細設計で実装) |
| W6 to_record audit 必須 | docstring で「audit/export caller は include_derived=True 必須」 明記 |
| S1 H3 除外 | 採用 (= 上記 C1 と同義) |
| S2 floor コメント | compute_expected_bar_count に「complete candle 数のため floor」 コメント追加予定 (詳細設計) |
| S3 BrokerTradingSchedule.__post_init__ 拡充 | season region 重複/隙間 + date_overrides + full_close 重複 reject (= 概念で要請、 詳細で実装) |
| S4 D/W 対象外 SSOT | M1_PLUS_GRANULARITIES の docstring で明記 |
| S5 all_g3_market_holiday は include_derived=True に含める | to_record docstring で明記 |

### Round 3 → Round 4 対応

| Round 3 | Round 4 対応 |
|---|---|
| C1 broker_schedule=None default expected=480 が granularity-aware 破壊 | § 4.6 / § 6.4 で default を `open_minutes=480` (= bucket full minutes 固定値) に変更、 expected は granularity 駆動 derived |
| C2 schedule_status を expected_bar_count から導出すると粗い granularity で partial 消失 | § 4.6 で `open_minutes` を primary field 化、 schedule_status / expected_bar_count は両方 open_minutes から derived (= H4 でも partial 維持) |
| C3 BrokerTradingSchedule に early close / late open / partial close 表現なし | § 4.3 で `date_overrides: Mapping[date, tuple[int, int]]` 追加、 優先順位 = date_overrides > broker_full_close > weekly/DST > weekday |
| C4 dst_aware_close_table 境界日 semantics 未確定 | § 0 / § 4.3 で region_start/end を inclusive、 disjoint、 連続 cover、 春切替日は当日が新 region の region_start として確定 |
| W1 schedule_status が asdict に出ない | § 4.6 に `to_record(include_derived: bool)` 追加 |
| W2 部分構成の半端 state | § 6.4 で本番は両方 None / 両方 provided 推奨、 片方は test/debug 限定 |
| W3 holiday_markets caller 委譲だけでは collider bias 不足 | § 0 / Phase 2 申し送りで「holiday_markets 単独で drop/filter せず stratified audit」 を統一規範 |
| W4 granularity 12 種類との不一致 | § 4.6 で M1+ 限定を明示、 M1_PLUS_GRANULARITIES = 11 種類 (M1..H4)、 S5/S10/S15/S30 を意図的に除外 |
| W5 tolerance float | I8 で `ceil(max(5, expected*0.01))` に整数固定 |
| W6 broker YAML provenance | § 4.3 に `BrokerSchedulingProvenance` 追加 |
| S1 SessionBlock.open_minutes primary | § 4.6 採用 |
| S2 date_overrides 最優先 | § 4.3 採用 |
| S3 複合ケース表追加 (H4/Christmas Eve/DST start) | § 6.5 で C18-C22 追加 |
| S4 validate_calendar_coverage で broker schedule も検証 | § 4.7 / § 4.4 で coverage に dst_aware_close_table の連続性 + date_overrides の period 内検証含む |
| S5 has_all_g3_holidays naming | § 4.5 で `all_g3_market_holiday` に rename (Round 3 [S5]) |

---

これで T072 概念設計 Round 4 改訂は完成。 Round 1-3 で出た指摘を全反映、 open_minutes を primary field 化 + broker date_overrides + DST 境界 semantics 確定 + default の granularity-aware 化。 Round 4 Codex review で最終確認。
