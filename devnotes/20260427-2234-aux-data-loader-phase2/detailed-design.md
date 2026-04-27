# 詳細設計: aux data loader Phase 2 — 実データ取得 + production wiring

## 使命・制約

zenigame-fx Alpha Factory 使命: live_criteria 全指標同時充足 + (ii-lite) 通過。
絶対制約: イントラデイ / ロング・ショート両方向 / swap・spread 反映。

禁止事項 1-7（評価期間延長 / 数値改善 / GA ハック / live_criteria 緩和 / 過度な複雑化 / 取引回数操作 / オーバーナイト前提）。

コーディングルール: テストファースト、uv 必須、ruff / mypy 通過。

## 概念設計リファレンス

[devnotes/20260427-2234-aux-data-loader-phase2/conceptual-design.md](./conceptual-design.md)（Round 3 APPROVED）

主要決定:
- AuxBundle (raw container) + AlignedAuxBundle (stage 別に align された結果)
- DailyObservation の `effective_from_utc` 契約（保守的 policy 既定、`source` 列で区別）
- preflight check: hard_required / soft_required 分離、hard 不足は fail-closed
- DB SSOT 一本化（aux_loader を DB reader 化）
- numpy ndarray 化（aux_series）
- 3 段階 Acceptance Gate（A 契約 → B wiring → C strict）

## 既存 DB schema（重要、verified）

- `MacroIndexDaily` (`macro_index_daily`): `series_id, date, value, fetched_at` — **`effective_from_utc` 列なし**
- `EconomicEventRow` (`economic_event`): `event_time, currency, name, impact, forecast, actual, source` — 経済指標 events 既存
- `PriceBarM1` (`price_bar_m1`): aux_pair_bars 用に EUR_USD/USD_JPY を fetch_historical で同経路追加可能

---

## 施策一覧（9 件、Gate A/B/C 単位）

| # | 施策 | Gate | 担当 | 規模 |
|---|---|---|---|---|
| 1 | AuxBundle / AlignedAuxBundle re-design | A | `src/alpha_factory/aux_loader.py` | 中 |
| 2 | DailyObservation + effective_from_utc 契約 + DB migration 004 | A | `aux_loader.py` / `src/db/models.py` / `src/db/migrations/versions/004_*.py` | 中 |
| 3 | aux_loader を DB reader 化（SSOT 一本化） | B | `aux_loader.py` / `src/ingest/fred.py` | 中 |
| 4 | scripts/fetch_fred.py 拡張（series 追加 + effective_from_utc 計算） | B | `scripts/fetch_fred.py` / `src/ingest/fred.py` | 小 |
| 5 | aux_pair_bars DB loader（欠番 None / misalign fail-fast） | B | `aux_loader.py` | 小 |
| 6 | events.csv 30 件 scaffold + load_economic_events 動作確認 | B | `data/raw/calendar/events.csv` | 小 |
| 7 | run_ga.py preflight + stage 別 evaluator + strict_aux_required default True | B+C | `scripts/alpha_factory/run_ga.py` / `config/alpha_factory/default.yaml` | 中 |
| 8 | aux_series numpy ndarray 化 + primitive 側互換確認 | C | `aux_loader.py` / `pair_specific.py`（最小 read 互換性） | 小 |
| 9 | AGENTS.md / runbook.md / fetch_aux_data.sh wrapper | C | docs / `scripts/fetch_aux_data.sh` | 小 |

---

## 施策 1: AuxBundle / AlignedAuxBundle re-design (Gate A)

### 変更箇所
`src/alpha_factory/aux_loader.py`

### 現行 AuxBundle
```python
class AuxBundle:
    """既存（Phase 1）: 1 段で aux_series / aux_pair_bars を保持"""
    aux_series: dict[str, list[float]]
    event_snapshot: EconomicEventSnapshot | None
    vix_snapshot: VixSeriesSnapshot | None
    aux_pair_bars: dict[str, list[PriceBar | None]]
```

### 変更後（2 段階構造）
```python
@dataclass(frozen=True)
class DailyObservation:
    observation_date: date
    value: float
    effective_from_utc: datetime
    source: Literal["fred_realtime_start", "policy_conservative"] = "policy_conservative"


@dataclass(frozen=True)
class AuxBundle:
    """Raw container — stage 別 bars に align される前。"""
    daily_series: dict[str, list[DailyObservation]]    # series_id → 時系列昇順 obs
    event_calendar: EconomicCalendar | None
    aux_pair_bars_index: dict[str, dict[datetime, PriceBar]]  # pair_id → bar_time → PriceBar
    
    def align_to(
        self,
        bars: Sequence[PriceBar],
        *,
        as_of_strict: bool = True,
    ) -> AlignedAuxBundle:
        """指定 bars に per-bar align した bundle を返す。"""
        ...


@dataclass(frozen=True)
class AlignedAuxBundle:
    """bars と同じ長さに整列済の bundle（per-stage instance）。"""
    aux_series: dict[str, np.ndarray]                   # ndarray[float64]、bars と同長
    event_snapshot: EconomicEventSnapshot | None        # bars[-1].bar_time が as_of
    vix_snapshot: VixSeriesSnapshot | None
    aux_pair_bars: dict[str, list[PriceBar | None]]     # bars と同長、bar_time strict 一致
    
    def as_evaluator_kwargs(self) -> dict:
        return {
            "aux_series": self.aux_series,
            "event_snapshot": self.event_snapshot,
            "vix_snapshot": self.vix_snapshot,
            "aux_pair_bars": self.aux_pair_bars,
        }
```

### `align_to` 実装（look-ahead bias 防止の核）

**Round 1 [Critical] 反映: 空 bars 対応**

```python
def align_to(self, bars: Sequence[PriceBar], *, as_of_strict: bool = True) -> AlignedAuxBundle:
    if not bars:
        # 空 bars 契約: 空 AlignedAuxBundle を返す（test fixture や warmup-only シナリオ用）
        return AlignedAuxBundle(
            aux_series={},
            event_snapshot=None,
            vix_snapshot=None,
            aux_pair_bars={},
        )
    n = len(bars)
    
    # 1. aux_series を per-bar 展開（look-ahead 防止）
    aux_series: dict[str, np.ndarray] = {}
    for series_id, observations in self.daily_series.items():
        # 時系列昇順前提
        arr = np.zeros(n, dtype=np.float64)
        obs_iter = iter(observations)
        next_obs: DailyObservation | None = next(obs_iter, None)
        current_value = 0.0  # warmup default
        for i, bar in enumerate(bars):
            # bar.bar_time >= obs.effective_from_utc を満たす最新 obs を採用
            while next_obs is not None and next_obs.effective_from_utc <= bar.bar_time:
                current_value = next_obs.value
                next_obs = next(obs_iter, None)
            arr[i] = current_value
        aux_series[f"macro.{series_id_to_key(series_id)}"] = arr
    
    # 2. event_snapshot: as_of = bars[-1].bar_time (per-bar lookup は primitive 側 T039)
    event_snapshot = (
        EconomicEventSnapshot(
            calendar=self.event_calendar,
            as_of=bars[-1].bar_time,
            as_of_strict=as_of_strict,
        )
        if self.event_calendar is not None else None
    )
    
    # 3. vix_snapshot: 全期間 VIX series（既存設計、bar 別 lookup ではない）
    vix_snapshot = self._build_vix_snapshot()
    
    # 4. aux_pair_bars: bar_time strict 一致で取得、欠番は None
    aux_pair_bars: dict[str, list[PriceBar | None]] = {}
    for pair_id, bar_time_index in self.aux_pair_bars_index.items():
        aligned: list[PriceBar | None] = []
        for bar in bars:
            aligned.append(bar_time_index.get(bar.bar_time))  # 欠番 None
        aux_pair_bars[pair_id] = aligned
    
    return AlignedAuxBundle(
        aux_series=aux_series,
        event_snapshot=event_snapshot,
        vix_snapshot=vix_snapshot,
        aux_pair_bars=aux_pair_bars,
    )
```

### per-stage 単位の align キャッシュ（Round 1 [Warning] 反映）

`align_to` を per-genome × per-stage に毎回呼ぶと総コストが急増する。**stage 単位に 1 回 align し、同 stage 内の全 genome で共有**する設計:

```python
class AuxAlignmentCache:
    """stage 別に AlignedAuxBundle をキャッシュ。bars identity (id(bars)) で hash。"""
    def __init__(self, raw: AuxBundle) -> None:
        self._raw = raw
        self._cache: dict[int, AlignedAuxBundle] = {}
    
    def get(self, bars: Sequence[PriceBar], *, as_of_strict: bool = True) -> AlignedAuxBundle:
        key = id(bars)  # immutable bars list の identity 比較
        if key not in self._cache:
            self._cache[key] = self._raw.align_to(bars, as_of_strict=as_of_strict)
        return self._cache[key]
```

`run_ga.py` 側では `cache = AuxAlignmentCache(aux_raw)` を 1 回作り、stage 別に `cache.get(bars_60d)` / `cache.get(bars_18m)` / `cache.get(bars_holdout)` を呼ぶ。各 stage で 1 回だけ展開。

### 波及変更
- `pair_specific.py:170` の `_check_aux_series_length` は `len(arr) == n` で動作（ndarray でも同じ）
- 既存 caller の `build_aux_bundle` 戻り値は `AuxBundle (raw)` に変更、test fixture も更新

### テスト計画（V2 / V5 反映）
- [x] `test_align_to_macro_series_uses_only_past_obs`: bar_time 直前の obs しか使わない（look-ahead bias なし）
- [x] `test_align_to_macro_series_warmup_zero`: dataset 開始時点で obs が無い場合 0.0
- [x] `test_align_to_macro_series_weekend_holiday`: 週末跨ぎ obs が forward-fill される
- [x] `test_align_to_aux_pair_bars_missing_returns_none`: 欠番は None
- [x] `test_align_to_aux_pair_bars_misalign_does_not_corrupt`: dict lookup なので misalign 自体は発生しない（時刻一致しなければ None になるだけ、misalign は primitive 側 fail-fast で別 layer）
- [x] `test_align_to_returns_ndarray_dtype_float64`: aux_series が np.ndarray、dtype=float64

---

## 施策 2: DailyObservation + effective_from_utc 契約 + DB migration (Gate A)

### 変更箇所
- `src/db/models.py` の `MacroIndexDaily` に `effective_from_utc: datetime`, `source: str` 列追加
- `src/db/migrations/versions/004_macro_index_daily_effective_from.py`（新規）
- `src/ingest/fred.py` の `FredObservation` に `effective_from_utc` 追加
- `src/alpha_factory/aux_loader.py` で `DailyObservation` ローカル dataclass 定義（DB から読み出し時に変換）

### Migration 004 概要

**Round 1 [Critical] 反映**: SQL 方言依存（`INTERVAL` / `TIMESTAMP WITH TIME ZONE`）を排除し、**Python での series 別 lag backfill**に変更:

```python
# Alembic migration 004
def upgrade():
    op.add_column("macro_index_daily", sa.Column("effective_from_utc", sa.DateTime(timezone=True), nullable=True))
    op.add_column("macro_index_daily", sa.Column("source", sa.String(40), nullable=True))
    
    # backfill: Python で series 別 lag を計算（方言非依存）
    # SERIES_POLICY_CONSERVATIVE は src/ingest/effective_from.py に移動
    from src.ingest.effective_from import SERIES_POLICY_CONSERVATIVE, compute_effective_from_utc
    
    bind = op.get_bind()
    rows = bind.execute(sa.text("SELECT id, series_id, date FROM macro_index_daily WHERE effective_from_utc IS NULL")).fetchall()
    for row in rows:
        eff = compute_effective_from_utc(row.series_id, row.date)
        bind.execute(
            sa.text("UPDATE macro_index_daily SET effective_from_utc = :eff, source = :src WHERE id = :id"),
            {"eff": eff, "src": "policy_conservative", "id": row.id},
        )
    
    # NOT NULL 化
    op.alter_column("macro_index_daily", "effective_from_utc", nullable=False)
    op.alter_column("macro_index_daily", "source", nullable=False)


def downgrade():
    op.drop_column("macro_index_daily", "source")
    op.drop_column("macro_index_daily", "effective_from_utc")
```

これにより:
- SQLite / PostgreSQL 両対応（既存 migration 群と整合）
- 月次系列（PCOPPUSDM / PALLFNFINDEXM）も lag=35日で正しく backfill

### SERIES_POLICY_CONSERVATIVE

**Round 1 [Warning] 反映**: レイヤ汚染防止のため、`alpha_factory/aux_loader.py` ではなく **`src/ingest/effective_from.py` (新規)** に配置。`alpha_factory/aux_loader.py` と `ingest/fred.py` の両方からインポート:

```python
# src/ingest/effective_from.py（新規）
from enum import Enum
from datetime import date, datetime, time, timedelta, UTC
from typing import Final


class EffectiveFromSource(str, Enum):
    """effective_from_utc の出所（Round 1 [Suggestion] 反映で enum 化）。"""
    POLICY_CONSERVATIVE = "policy_conservative"
    FRED_REALTIME_START = "fred_realtime_start"  # Phase 2 既定では未使用、将来 TODO
    OANDA_RELEASE_TIME = "oanda_release_time"    # 将来拡張


SERIES_POLICY_CONSERVATIVE: Final[dict[str, dict[str, int]]] = {
    "VIXCLS":           {"lag_hours": 24},
    "DTWEXBGS":         {"lag_hours": 24},
    "GOLDPMGBD228NLBM": {"lag_hours": 24},
    "DCOILWTICO":       {"lag_hours": 24},
    "PCOPPUSDM":        {"lag_hours": 24 * 35},   # 月次は 35 日 lag
    "PALLFNFINDEXM":    {"lag_hours": 24 * 35},
    "SP500":            {"lag_hours": 24},
}


def compute_effective_from_utc(series_id: str, observation_date: date) -> datetime:
    """observation_date + policy lag で effective_from_utc を計算（保守的）。"""
    lag = SERIES_POLICY_CONSERVATIVE.get(series_id, {"lag_hours": 24})["lag_hours"]
    return datetime.combine(observation_date, time.min, tzinfo=UTC) + timedelta(hours=lag)


def max_policy_lag_days() -> int:
    """全 SERIES_POLICY_CONSERVATIVE で最大の lag を日単位で返す。"""
    return max(p["lag_hours"] // 24 for p in SERIES_POLICY_CONSERVATIVE.values())
```

### テスト計画
- [x] `test_compute_effective_from_utc_daily_series_24h_lag`
- [x] `test_compute_effective_from_utc_monthly_series_35d_lag`
- [x] `test_migration_004_backfill_existing_rows`

---

## 施策 3: aux_loader を DB reader 化（SSOT 一本化、Gate B）

### 変更箇所
`src/alpha_factory/aux_loader.py`

### 現行
- `_read_csv_dict` で `data/raw/fred/{name}.csv` を CSV 直読み
- `load_dxy_series` / `load_vix_snapshot` / `load_aux_series` が CSV 経由

### 変更後
```python
def load_daily_series_from_db(
    *,
    db_session: Session,
    series_id: str,
    period: tuple[datetime, datetime],
) -> list[DailyObservation]:
    """MacroIndexDaily を読み出し DailyObservation list を返す。
    period (start, end) で filter、observation_date 昇順。
    """
    # Round 1 [Warning] 反映: 60 days マジックナンバーを max_policy_lag_days() + safety から導出
    buffer_days = max_policy_lag_days() + 7  # safety margin
    rows = db_session.scalars(
        select(MacroIndexDaily)
        .where(MacroIndexDaily.series_id == series_id)
        .where(MacroIndexDaily.date >= period[0].date() - timedelta(days=buffer_days))
        .where(MacroIndexDaily.date <= period[1].date())
        .order_by(MacroIndexDaily.date.asc())
    ).all()
    return [
        DailyObservation(
            observation_date=r.date,
            value=float(r.value) if r.value is not None else float("nan"),
            effective_from_utc=r.effective_from_utc,
            source=r.source,
        )
        for r in rows if r.value is not None
    ]
```

### CSV reader は test fixture 用にのみ残す
```python
# 既存 _read_csv_dict は test 専用 helper として保持
# production パスは load_daily_series_from_db のみ
```

### テスト計画
- [x] `test_load_daily_series_from_db_filters_by_period`
- [x] `test_load_daily_series_from_db_orders_by_date_ascending`
- [x] `test_load_daily_series_from_db_skips_null_values`

---

## 施策 4: fetch_fred.py 拡張 + effective_from_utc 計算 (Gate B)

### 変更箇所
- `scripts/fetch_fred.py` の `DEFAULT_SERIES` 拡張
- `src/ingest/fred.py` の `upsert_observations` に `effective_from_utc / source` 列を追加して書き込み

### 拡張後 DEFAULT_SERIES
```python
DEFAULT_SERIES = (
    "VIXCLS",            # M5, P7
    "DTWEXBGS",          # P11 (DXY)
    "GOLDPMGBD228NLBM",  # P12 Gold
    "DCOILWTICO",        # P9 WTI
    "PCOPPUSDM",         # P8 Copper
    "PALLFNFINDEXM",     # P8 commodity index
    "SP500",             # P7 SPX500
    "DGS10", "DGS2", "T10YIE",  # 既存
)
```

### upsert で effective_from_utc 計算
```python
def upsert_observations(session: Session, rows: Iterable[FredObservation]) -> int:
    for row in rows:
        eff = compute_effective_from_utc(row.series_id, row.obs_date)
        # MacroIndexDaily に effective_from_utc, source="policy_conservative" で upsert
        ...
```

---

## 施策 5: aux_pair_bars DB loader (Gate B)

### 変更箇所
`src/alpha_factory/aux_loader.py` 末尾に `load_aux_pair_bars_index` 追加

**Round 1 [Warning] 反映**: tz / 分解能の正規化を契約化（datetime 完全一致 lookup の取りこぼし防止）

```python
def _normalize_bar_time(ts: datetime) -> datetime:
    """M1 bar_time の正規化: tz-aware UTC + 秒・マイクロ秒を 0 に丸める。"""
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=UTC)
    else:
        ts = ts.astimezone(UTC)
    return ts.replace(second=0, microsecond=0)


def load_aux_pair_bars_index(
    *,
    db_session: Session,
    pairs: Sequence[str],
    period: tuple[datetime, datetime],
) -> dict[str, dict[datetime, PriceBar]]:
    """aux pair の M1 bars を bar_time index で取得。
    
    return: pair_id → {normalized_bar_time: PriceBar} の dict（O(1) lookup）
    align_to で target_bars をループしながら lookup する設計。
    bar_time は M1 解像度に正規化（tz-aware UTC + 秒切り捨て）→ DB データと target bars の同一視を担保。
    """
    out: dict[str, dict[datetime, PriceBar]] = {}
    for pair_id in pairs:
        pair = db_session.scalars(
            select(CurrencyPair).where(CurrencyPair.oanda_name == pair_id)
        ).one_or_none()
        if pair is None:
            out[pair_id] = {}
            continue
        rows = db_session.scalars(
            select(PriceBarM1)
            .where(PriceBarM1.pair_id == pair.id)
            .where(PriceBarM1.bar_time >= period[0])
            .where(PriceBarM1.bar_time < period[1])
            .order_by(PriceBarM1.bar_time.asc())
        ).all()
        out[pair_id] = {
            _normalize_bar_time(r.bar_time): _bar_row_to_price_bar(r, pair_id)
            for r in rows
        }
    return out
```

`align_to` 側でも `bar.bar_time` を `_normalize_bar_time` で正規化してから lookup する。

### テスト計画
- [x] `test_load_aux_pair_bars_returns_bar_time_indexed_dict`
- [x] `test_load_aux_pair_bars_missing_pair_returns_empty_dict`

---

## 施策 6: events.csv 30 件 scaffold (Gate B)

### ファイル: `data/raw/calendar/events.csv`
```csv
event_time_utc,currency,name,impact,forecast,actual
2025-10-08T13:30:00+00:00,USD,FOMC Meeting Minutes,3,,
2025-10-15T12:30:00+00:00,USD,CPI MoM,3,,
2025-11-07T13:30:00+00:00,USD,NFP,3,,
2025-11-25T18:00:00+00:00,USD,FOMC Meeting Minutes,3,,
2025-12-12T12:30:00+00:00,USD,CPI MoM,3,,
... (主要指標 約 30 件)
```

選定基準: 主要 high-impact (impact=3) のみ。USD（FOMC, CPI, NFP）/ EUR（ECB Rate, CPI）/ JPY（BoJ Rate）。dataset.start (2025-10-01) 〜 dataset.end (2026-04-01) の 6 ヶ月で月平均 5 件。

### load_economic_events.py 動作確認
既存 script を `--csv data/raw/calendar/events.csv` で実行し DB upsert することを確認。

### Phase 2 で **partial coverage** と明記（Round 1 W4 反映）

---

## 施策 7: run_ga.py preflight + stage 別 evaluator + strict_aux_required default True (Gate B/C)

### 変更箇所
- `scripts/alpha_factory/run_ga.py:1145` 周辺
- `config/alpha_factory/default.yaml`
- 新規 `src/alpha_factory/aux_preflight.py`

### preflight check 実装
```python
# src/alpha_factory/aux_preflight.py（新規）
@dataclass(frozen=True)
class PreflightResult:
    hard_satisfied: list[str]
    hard_missing: list[str]
    soft_satisfied: list[str]
    soft_missing: list[str]
    
    @property
    def passes(self) -> bool:
        return not self.hard_missing


HARD_REQUIRED_AUX = {
    "VIXCLS":   "macro.vix",
    "DTWEXBGS": "macro.dxy",
}
HARD_REQUIRED_PAIRS = ("EUR_USD", "USD_JPY")  # P5

SOFT_REQUIRED_AUX = {
    "GOLDPMGBD228NLBM": "macro.gold",
    "DCOILWTICO":       "macro.wti",
    "PCOPPUSDM":        "macro.copper",
    "PALLFNFINDEXM":    "macro.commodity_index",
    "SP500":            "macro.spx500",
}


def preflight_check_aux_data(
    *,
    db_session: Session,
    period: tuple[datetime, datetime],         # Stage A 評価期間 (= dataset)
    stage_b_window_months: int,                # Round 1 [Critical] 反映
    stage_c_holdout_days: int,
    allow_missing: bool = False,
    min_finite_coverage_pct: float = 50.0,     # Round 1 [Critical] 反映: stale 検出
) -> PreflightResult:
    # Round 1 [Critical] 反映: preflight period が Stage B 18ヶ月履歴を含む
    extended_start = period[0] - timedelta(days=stage_b_window_months * 30)  # ~18ヶ月前
    extended_end = period[1] + timedelta(days=stage_c_holdout_days)
    extended_period = (extended_start, extended_end)
    
    def _check_series(series: str) -> bool:
        """Round 1 [Critical] 反映: 存在判定だけでなく finite coverage と最終有効時刻 check"""
        return (
            _series_finite_coverage_pct(db_session, series, extended_period) >= min_finite_coverage_pct
            and _series_latest_effective_from(db_session, series) >= extended_start
        )
    
    hard_satisfied, hard_missing = [], []
    for series, key in HARD_REQUIRED_AUX.items():
        if _check_series(series):
            hard_satisfied.append(series)
        else:
            hard_missing.append(series)
    
    for pair in HARD_REQUIRED_PAIRS:
        if _pair_bars_finite_coverage(db_session, pair, extended_period) >= min_finite_coverage_pct:
            hard_satisfied.append(f"{pair}_M1")
        else:
            hard_missing.append(f"{pair}_M1")
    
    soft_satisfied, soft_missing = [], []
    for series, key in SOFT_REQUIRED_AUX.items():
        if _check_series(series):
            soft_satisfied.append(series)
        else:
            soft_missing.append(series)
    
    result = PreflightResult(hard_satisfied, hard_missing, soft_satisfied, soft_missing)
    if not result.passes and not allow_missing:
        raise RuntimeError(
            f"preflight aux check FAILED: hard_missing={hard_missing}. "
            f"Run scripts/fetch_aux_data.sh to populate, or use --allow-aux-missing for dev."
        )
    return result
```

**Round 1 [Warning] 反映: CLI vs config 優先順位**:
- 優先順位は **`CLI > config`**（CLI の `--allow-aux-missing` は config の `strict_aux_required: true` を上書き）
- effective strict mode を log で必ず出力:
```python
effective_strict = (cfg.stage_gate.strict_aux_required and not args.allow_aux_missing)
logger.info("preflight.effective_strict_mode", strict=effective_strict, source=("cli_override" if args.allow_aux_missing else "config"))
```

### run_ga.py 変更
```python
# 既存 _load_lane_bars の後で実行
preflight_result = preflight_check_aux_data(
    db_session=session,
    period=(cfg.dataset.start, cfg.dataset.end + timedelta(days=cfg.stage_gate.stage_c_holdout_days)),
    allow_missing=args.allow_aux_missing,
)
logger.info(
    "preflight.aux_data_check",
    hard_satisfied=preflight_result.hard_satisfied,
    hard_missing=preflight_result.hard_missing,
    soft_satisfied=preflight_result.soft_satisfied,
    soft_missing=preflight_result.soft_missing,
)

# AuxBundle build (raw, 1 回)
aux_raw = build_aux_bundle_from_db(
    db_session=session,
    period=...,
    aux_pairs=("EUR_USD", "USD_JPY"),
)

# stage 別 evaluator は per-genome / per-stage で生成（既存 architecture と整合）
# 既存 RegistryEvaluator(pair=...) → AlignedAuxBundle.as_evaluator_kwargs() 展開で注入
```

### config/alpha_factory/default.yaml 変更
```yaml
stage_gate:
  ...
  strict_aux_required: true   # T046 を有効化（Phase 2 Gate C で True 化）
```

### CLI 追加: `--allow-aux-missing`
- 開発・test 用
- production yaml では default false（preflight 必須）

---

## 施策 8: aux_series numpy ndarray 化 (Gate C)

### 変更箇所
- `src/alpha_factory/aux_loader.py`: `align_to` で `aux_series` を `np.ndarray[float64]` で構築（施策 1 で実装済）
- `src/alpha_factory/primitives/pair_specific.py`: `_check_aux_series_length` の互換確認のみ（既に `len(arr) == n` で動作、ndarray でも同じ）

### 互換性確認 grep
```bash
grep -rn "aux_series\[" src/alpha_factory/primitives/ | head
# 各箇所で `arr[i]` の indexing が ndarray でも互換であることを確認
```

### テスト計画
- [x] `test_aux_series_ndarray_works_with_existing_primitive_checks`
- [x] **`test_aligned_aux_bundle_picklable_for_multiprocessing`**（Round 1 [Suggestion] 反映）— pickle round-trip で AlignedAuxBundle が壊れないことを確認、worker 並列で安全

---

## 施策 9: AGENTS.md / runbook.md / fetch_aux_data.sh wrapper (Gate C)

### `scripts/fetch_aux_data.sh`（新規 wrapper）

**Round 1 [Critical] 反映**: DEFAULT_SERIES（既存 5 個 + 新規 5 個 = 計 10 series）を完全列挙し、既存 series を回帰させない。失敗時は再実行性のため step 別の進捗を log:

```bash
#!/bin/bash
# Phase 2 aux data 一括取得 wrapper
set -euo pipefail

START="${1:-2025-08-01}"  # buffer 含む
END="${2:-2026-04-30}"
LOG="/tmp/fetch_aux_data_$(date +%Y%m%d_%H%M%S).log"

echo "[1/3] FRED series fetch (10 series)..." | tee -a "$LOG"
# 既存 5 + 新規 5 を完全列挙（DEFAULT_SERIES 同期、Round 1 [Critical] 反映で回帰防止）
uv run python scripts/fetch_fred.py --start "$START" --end "$END" \
    --series VIXCLS,DTWEXBGS,DGS10,DGS2,T10YIE,GOLDPMGBD228NLBM,DCOILWTICO,PCOPPUSDM,PALLFNFINDEXM,SP500 \
    2>&1 | tee -a "$LOG"

echo "[2/3] Aux pair bars fetch..." | tee -a "$LOG"
for pair in EUR_USD USD_JPY; do
    echo "  fetching $pair..." | tee -a "$LOG"
    uv run python scripts/fetch_historical.py --instrument "$pair" --start "$START" --end "$END" 2>&1 | tee -a "$LOG"
done

echo "[3/3] Economic events load..." | tee -a "$LOG"
uv run python scripts/load_economic_events.py --csv data/raw/calendar/events.csv 2>&1 | tee -a "$LOG"

echo "[done] aux data ready for production RUN. Log: $LOG" | tee -a "$LOG"
```

または **DEFAULT_SERIES を fetch_fred.py 側で hardcode** して、wrapper では `--series` を指定しない方針も可（実装時に判断）。回帰防止のため fetch_fred 側に `DEFAULT_SERIES` の **assert test** を追加する。

### AGENTS.md 追加
- 「本番 RUN 前に scripts/fetch_aux_data.sh を実行する」運用手順
- preflight check が走るので、欠落時は明確なエラーメッセージで判定可能

### docs/alpha_factory/runbook.md 追加
- aux data pipeline セクション
- effective_from_utc 契約の説明
- hard_required / soft_required の運用方針
- Gate C 受け入れ基準（実選択 primitive の充足率 / stale rate）

---

## 検証要件まとめ

| # | 項目 | 合格基準 | Gate |
|---|---|---|---|
| V1 | 既存テスト全パス | `uv run pytest tests/ -x` | A/B/C |
| V2 | look-ahead bias なし | `align_to` test 4 ケース PASS | A |
| V3 | misalign vs 欠番分離 | aux_pair_bars 欠番 None / 完全一致のみ採用 | A/B |
| V4 | preflight check | hard 不足で fail-closed、`--allow-aux-missing` で override | B/C |
| V5 | stage 別 alignment | bars_60d / bars_18m / bars_holdout で正しい長さ | A |
| V6 | strict_aux_required=True | hard_required の RuntimeWarning 0 件 | C |
| V7 | numpy ndarray 互換 | 既存 primitive で fail せず動作 | C |
| V8 | events partial coverage 明記 | runbook.md に明記 | C |
| V9 | ruff / mypy | baseline 維持 | A/B/C |
| V10 | 統合 smoke test | pop=2, gen=1 で run 完走 + RuntimeWarning 0 件（hard） | C |
| V11 | primitive 充足率（Round 3 反映） | 実選択 primitive の required_data 充足率を archive Parquet で計測 | C |
| V12 | series stale rate 監視（Round 3 反映） | 月次系列 lag=35d の stale 率が 80% 未満 | C |
| V13 | freshness の両端 check（Round 3 [Warning] 反映） | `latest_effective_from >= extended_end - safety_lag` も追加（現状の start 側だけだと不十分） | C |
| V14 | AuxAlignmentCache の key + invalidation 明文化（Round 3 [Warning] 反映） | key = `(id(bars), as_of_strict)` 構造、bars が変わったら別 cache（既存設計通り）、invalidation は明示的 reset method を提供 | A |
| V15 | `_normalize_bar_time` 丸め衝突 fail-fast（Round 3 [Warning] 反映） | 同 minute に複数 PriceBar が DB にある異常データを検出し ValueError raise | B |

---

## 実装モード

| 項目 | 内容 |
|------|------|
| 推奨モード | **standalone**（Gate A/B/C の段階進行が必須、incremental 自動選定では合わなくなる） |
| 判断根拠 | 9 施策 + DB migration + run_ga 大幅変更で結合度高、段階 commit 必須 |
| 競合リスク | 中（aux_loader.py / run_ga.py への大幅変更、他 TODO との並行は避ける） |
| 想定実装時間 | **長**（Gate A 1日 + Gate B 1.5日 + Gate C 0.5日 = 計 3 日想定） |
