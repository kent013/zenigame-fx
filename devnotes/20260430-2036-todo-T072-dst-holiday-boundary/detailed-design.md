# 詳細設計: T072 — Timezone / DST / holiday session boundary contract

**作成日時**: 2026-04-30 22:30 JST
**設計者**: Claude
**前提**: 概念設計 `conceptual-design.md` Round 5 APPROVED 済 (`conceptual-review-round-5.md`)
**SSOT 規約 (§ 11.2)**: 本詳細設計 §3 / §4 の擬似コードは概念設計 §4 / §5 / §6 と同期。 不一致時は概念設計を正本として優先。
**main 基準**: `a8ecd1d` (T071 commit 後)
**改訂履歴**: 概念設計 Round 1-5 で出た指摘 (= C 計 16 / W 計 28+ / S 計 22+) は概念設計に全反映済、 本詳細設計は概念 Round 5 APPROVED 状態を起点とする。 概念 Round 5 で残った Warning (W1-W4) / Suggestion (S1-S3) は本詳細設計で反映 (Round 5 反映項目)。
**Round 1 詳細レビュー反映 (2026-04-30 23:00 JST)**: C1-C6 / W1-W5 / S1-S5 を全反映:
- Round D1 [C1]: SessionBlock の改造を「3 field 追加 + 1 メソッド追加」 に書き分け (= field と method の混同を解消)
- Round D1 [C2]: YAML loader で duplicate key reject を強制、 dataclass 受領後の Mapping 一意性を保証
- Round D1 [C3]: 全 window / bucket / period を **半開区間 `[start, end)`** で統一明記、 overlap 計算契約を SSOT
- Round D1 [C4]: aggregate_session_blocks の `mode` を **必須引数化** (= default 廃止)、 production caller 指定漏れを構造的に防止
- Round D1 [C5]: `to_record` に `STORAGE_FIELDS` / `DERIVED_FIELDS` 定数 + `record_schema_version` 導入で出力 schema 固定
- Round D1 [C6]: `validate_calendar_coverage` の dataset_span を `(start_inclusive, end_inclusive)` と明示
- Round D1 [W1]: __post_init__ 検証順序依存 (= I-7 は I-5/I-6 後) 明文化
- Round D1 [W3]: module-level logger 固定推奨
- Round D1 [W4]: DoD に「OANDA 一次資料未確認なら production 反映禁止」 追加
- Round D1 [W5]: DoD に C2 parallel-path 確認タスク (= utils/time.py / T060 / primitives _SESSION_RANGES_UTC) 追加
- Round D1 [S1]: mode 必須化 (上記 [C4])
- Round D1 [S2]: 半開区間統一 (上記 [C3])
- Round D1 [S3]: record_schema_version / 定数化 (上記 [C5])
- Round D1 [S4]: broker schedule に property-based test 1 本追加
- Round D1 [S5]: PR description 用 collider bias 規範テンプレート追加
- Round D1 [test_id ギャップ]: F1-F4 / F5-F7 の重複整理、 枝番 (F14d/F37i/F44b/F49c) を `Fxxx_<behavior>` 形式に固定
- Round D1 [YAML schema lint]: duplicate key reject loader 必須、 schema 検証 CI、 dst_aware_close_table 連続性 lint を DoD に追加

## 0. 詳細設計の責務

概念設計で確定した SSOT (= 責務分離 / open_minutes primary / date_overrides / DST 境界 / collider bias 規範) を **コード単位** に展開:
- 完全な擬似コード (Python に近いがフォーマットは設計書)
- YAML schema 完全定義 (broker_trading_schedule.yaml + {tokyo,london,ny}_market_holidays.yaml)
- caller signature 完全展開 (T070 SessionBlock / aggregate_session_blocks)
- F1-F53 と test_id の 1:1 対応 (Phase 1 / Phase 2 切り分け)
- DoD / Phase 1 / Phase 2 切り分け

## 1. ファイル / 関数 / クラス 完全リスト

### 1.1 新規ファイル

| Path | 主シンボル | LOC 概算 |
|---|---|---|
| `src/backtest/calendar.py` | `ScheduleStatus`, `MarketCode`, `M1_PLUS_GRANULARITIES`, `HOLIDAY_CALENDAR_VERSION`, `BROKER_SCHEDULE_VERSION`, `BrokerSeasonalCloseSpec`, `BrokerTradingSchedule`, `BrokerSchedulingProvenance`, `MarketHolidayCalendar`, `ObservabilityFlags`, `load_market_holiday_calendar`, `load_broker_trading_schedule`, `validate_calendar_coverage`, `is_market_holiday`, `is_dst_transition`, `compute_observability_flags`, `compute_bucket_open_minutes`, `compute_expected_bar_count` | +400 |
| `tests/backtest/test_calendar.py` | F1-F53 + happy path | +500 |
| `config/calendars/broker_trading_schedule.yaml` | DST table + broker_full_close_holidays + date_overrides + provenance | +80 |
| `config/calendars/tokyo_market_holidays.yaml` | 2022-01-01 ～ 2027-12-31 TSE close 日 + provenance | +130 |
| `config/calendars/london_market_holidays.yaml` | 同期間 LSE close 日 + provenance | +90 |
| `config/calendars/ny_market_holidays.yaml` | 同期間 NYSE close 日 + provenance | +110 |

### 1.2 既存ファイル変更

| Path | 関数 / 行 | 変更内容 | LOC 増減 |
|---|---|---|---|
| `src/backtest/session_block.py` (T070 で新設予定) | `SessionBlock` dataclass | **3 field 追加** (`open_minutes`, `granularity_seconds`, `observability_flags`) + **1 メソッド追加** (`to_record`) + `expected_bar_count` / `schedule_status` を `@property` 化 (Round D1 [C1] 反映) | +30 |
| `src/backtest/session_block.py` | `aggregate_session_blocks` | signature 拡張 (= broker_schedule / calendars / granularity_seconds / mode 引数追加) + production mode reject + open_minutes 駆動の SessionBlock 構築 | +25 |
| `tests/backtest/test_session_block.py` (T070 で新設予定) | T072 関連テスト追加 (F38-F49) | open_minutes / observability_flags / to_record / production mode | +200 |
| `docs/alpha_factory/stage-gates.md` | T072 セクション | 仕様追記 | +50 |

注意: `src/backtest/session_block.py` は T070 で新設予定 (= 設計 only、 src 未実装)。 T072 PR 実装時の merge 順序は Phase 2 で実装フェーズ判断。

### 1.3 Phase 2 申し送り (T072 PR では touch しない)

- T061 canonical_metrics: `SessionBlock.expected_bar_count` 駆動の HAC SR / WR 計算 (= n 補正 / closed_full 除外)
- T064 stage_bc_evaluator: fold 境界の closed_partial / closed_full 扱い (= pnl=0 重みづけ or 除外)
- T066 cpps_archive: archive admission 時の `session_pass_pattern` 生成で `open_minutes > 0` を分母条件、 `holiday_markets` を condition として stratified
- T071 SessionEntropyMetric: 同 semantic で session_pass_pattern 入力
- run_ga.py / backtest_runner: `BacktestResult.session_blocks` の caller 配線 (T070 と同期)
- run report / archive: observability_flags / schedule_status / expected_bar_count の log/report 露出 (= to_record(include_derived=True) 経由)

### 1.4 collider bias 規範 (Round 3 [W3] / Round 5 [S5] 対応)

下流 evaluator (T071 / T064 / T066) 詳細設計改訂申し送りに以下を一行で追加:

> **collider bias 規範**: `holiday_markets` 単独で session_pass_pattern / SR 計算分母を drop / filter してはならない。 必ず stratified audit (= holiday_markets 値別の集計) を行い、 conditioning set を明示する。 holiday を expected_bar_count に混ぜることは T072 SSOT で禁止。

## 2. 既存 caller signature 完全展開

### 2.1 SessionBlock 構築 caller 完全リスト

T070 SessionBlock は **src 未実装** (= 設計 only)。 T072 PR で 4 field 追加 + property 変更を行うが、 既存 caller (= T070 PR で同時実装される `aggregate_session_blocks`) のみが SessionBlock を構築する想定。 T072 + T070 の同期 merge を推奨。

T070 + T072 同期 merge 後の caller:

| ファイル:行 | 構築方法 | T072 PR 影響 |
|---|---|---|
| `src/backtest/session_block.py:aggregate_session_blocks` 内部 | keyword 構築 (T070 既存 fields + T072 追加 fields) | T072 で keyword 引数を 3 つ追加 |

### 2.2 aggregate_session_blocks 関数 caller (signature 拡張)

| Caller | 既存 signature | T072 PR 後 signature |
|---|---|---|
| `src/backtest/engine.py:run_backtest` (T070 で配線予定) | `aggregate_session_blocks(bars_list, broker.trades)` | `aggregate_session_blocks(bars_list, broker.trades, *, broker_schedule=None, calendars=None, granularity_seconds=60, mode="test")` (= optional 引数のみ追加、 既存 caller は positional 不変で互換) |
| Phase 2 で run_ga.py / backtest_runner 配線 | n/a | `aggregate_session_blocks(bars, trades, broker_schedule=..., calendars=..., mode="production")` |

### 2.3 grep DoD (= PR review check)

T072 PR 実装時の確認:
```bash
# T070 SessionBlock 構築 caller 確認
grep -rn "SessionBlock(" src/ tests/ --include="*.py"

# T072 新規 import 確認
grep -rn "from src.backtest.calendar import\|import src.backtest.calendar" src/ tests/ --include="*.py"

# aggregate_session_blocks の caller 確認
grep -rn "aggregate_session_blocks(" src/ tests/ --include="*.py"

# 全 caller が optional 引数追加で破壊変更なしを確認
```

## 3. データモデル詳細 (擬似コード)

### 3.1 型 / 定数

```python
# src/backtest/calendar.py

from __future__ import annotations
import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Final, Literal
from zoneinfo import ZoneInfo

import yaml  # PyYAML

from src.backtest.session_block import SessionBlockBucket, BLOCK_BUCKET_RANGES_UTC


__all__ = [
    "ScheduleStatus",
    "MarketCode",
    "M1_PLUS_GRANULARITIES",
    "HOLIDAY_CALENDAR_VERSION",
    "BROKER_SCHEDULE_VERSION",
    "BrokerSeasonalCloseSpec",
    "BrokerTradingSchedule",
    "BrokerSchedulingProvenance",
    "MarketHolidayCalendar",
    "ObservabilityFlags",
    "load_market_holiday_calendar",
    "load_broker_trading_schedule",
    "validate_calendar_coverage",
    "is_market_holiday",
    "is_dst_transition",
    "compute_observability_flags",
    "compute_bucket_open_minutes",
    "compute_expected_bar_count",
]


ScheduleStatus = Literal["regular", "closed_full", "closed_partial"]
MarketCode = Literal["tokyo", "london", "ny"]


# ---------------------------------------------------------------------------
# Granularity SSOT (Round 4 [C1] [S1] / Round 5 [S1] 反映)
# ---------------------------------------------------------------------------
# すべて 28800 (= 8h × 3600) を割り切る integer granularity (= 8h block と整合).
# - S5/S10/S15/S30 は意図的に除外 (= session block は M1+ の complete candle 前提)
# - H3=10800 は 28800 % 10800 = 7200 で割り切らないため除外 (Round 4 [C1])
# - D=86400 / W=604800 は session block の対象外 (= 8h block と概念的に合わない)
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
})  # 10 種類、 すべて 28800 を割り切る (= I5 / I7 SSOT)


HOLIDAY_CALENDAR_VERSION: Final[str] = "1.0.0"
BROKER_SCHEDULE_VERSION: Final[str] = "1.0.0"

# bucket full minutes (= 8h × 60) は SSOT 定数として保持
BUCKET_FULL_MINUTES: Final[int] = 8 * 60  # 480
BUCKET_FULL_MINUTES_X60: Final[int] = BUCKET_FULL_MINUTES * 60  # 28800 = 8h × 3600

# Round D1 [C3] / [S2] 反映: 区間契約 SSOT
# - すべての (start_minute, end_minute) は **半開区間 [start, end)** (= start inclusive, end exclusive)
# - bucket UTC range (T070 BLOCK_BUCKET_RANGES_UTC) も半開区間 (例: tokyo=[0, 8) UTC)
# - broker open_window_for_utc_date(d) の戻り値も半開区間 [start_min, end_min)
#   例: 平日 full open = [0, 1440)、 Sat closed = [0, 0) (= 空区間)、 Fri close=22:00 = [0, 1320)
# - overlap = max(0, min(end_a, end_b) - max(start_a, start_b)) は半開区間 SSOT 前提
# - 境界値: start == open_end → overlap 0 (= 空)、 end == open_start → overlap 0 (= 空)

# Round D1 [C5] [S3] / Round D2 [C1] [S1] 反映: to_record schema 定数
# 出力 record の field 表現を **path 形式** で統一 (= top-level / nested の不整合解消)
RECORD_SCHEMA_VERSION: Final[str] = "1.0.0"
# bump 条件 (Round D2 [W1]):
# - MAJOR: field 削除 / 意味変更 / 型変更 / nested path 変更 (= consumer 互換性破壊)
# - MINOR: field 追加 (= consumer は新 field を ignore で動作可)
# - PATCH: バグ fix (= 出力値の修正のみ、 schema 不変)

SESSION_BLOCK_STORAGE_FIELDS: Final[tuple[str, ...]] = (
    "business_date",
    "bucket",
    "bar_count",
    "trade_count",
    "pnl_net",
    "pnl_before_costs",
    "spread_cost_total",
    "holding_cost_total",
    "open_minutes",
    "granularity_seconds",
    "observability_flags.dst_transition_markets",
    "observability_flags.holiday_markets",
)  # 12 path

SESSION_BLOCK_DERIVED_FIELD_PATHS: Final[tuple[str, ...]] = (
    "schedule_status",
    "expected_bar_count",
    "is_partial_bar_block",
    "observability_flags.all_g3_market_holiday",  # nested path で明示 (Round D2 [C1] [S1])
)  # 4 path
```

**Round D1 [C3] [S2] 反映**: 区間契約は **半開区間 `[start, end)` で統一**。 bucket UTC range / open_window_for_utc_date の戻り値 / overlap 計算 / coverage 判定で同一規約。 境界値の挙動も一意:
- `start_a == end_b` → overlap = 0 (= 空区間)
- `end_a == start_b` → overlap = 0 (= 空区間)

**Round D1 [C5] [S3] / Round D2 [C1] [S1] 反映**: to_record の出力 schema を **path 形式** で固定。 `observability_flags.all_g3_market_holiday` のような nested path を `SESSION_BLOCK_DERIVED_FIELD_PATHS` 定数で明示し、 top-level / nested 不整合を排除。 future field 追加時も path 形式で更新するだけで済む。 RECORD_SCHEMA_VERSION 1.0.0、 bump 条件は MAJOR/MINOR/PATCH を docstring 明記 (Round D2 [W1])。

### 3.2 BrokerSeasonalCloseSpec

```python
@dataclass(frozen=True)
class BrokerSeasonalCloseSpec:
    """DST season 別 close/reopen spec.

    SSOT (概念 § 4.3、 Round 3 [C4] 反映):
        region_start <= region_end (inclusive)
        region は互いに disjoint
        全 region で [period_start, period_end] を連続 cover (= 隙間なし)
        春切替日は当日が新 (DST) region の region_start
    """
    name: str                 # e.g. "ny_dst_2024" / "ny_standard_2024_2025"
    region_start: date        # inclusive
    region_end: date          # inclusive
    close_hour_utc: int       # 0..23
    reopen_hour_utc: int      # 0..23

    def __post_init__(self) -> None:
        if not (0 <= self.close_hour_utc <= 23):
            raise ValueError(
                f"close_hour_utc must be in 0..23, got {self.close_hour_utc} "
                f"(name={self.name!r})"
            )
        if not (0 <= self.reopen_hour_utc <= 23):
            raise ValueError(
                f"reopen_hour_utc must be in 0..23, got {self.reopen_hour_utc} "
                f"(name={self.name!r})"
            )
        if self.region_start > self.region_end:
            raise ValueError(
                f"region_start ({self.region_start}) > region_end ({self.region_end}) "
                f"(name={self.name!r})"
            )
```

### 3.3 BrokerSchedulingProvenance

```python
@dataclass(frozen=True)
class BrokerSchedulingProvenance:
    """YAML schema provenance (Round 3 [W6] 反映)."""
    source: str               # 例: "OANDA Developer Portal v20"
    verified_at: date         # YAML 最終確認日
    confidence: Literal["high", "medium", "low"]
    notes: str                # 備考

    def __post_init__(self) -> None:
        if self.confidence not in ("high", "medium", "low"):
            raise ValueError(f"confidence must be high/medium/low, got {self.confidence!r}")
```

### 3.4 BrokerTradingSchedule (Round 5 [S2] 反映: __post_init__ 検証 test matrix 化対応)

```python
@dataclass(frozen=True)
class BrokerTradingSchedule:
    """broker (OANDA) の date-aware 配信 schedule SSOT.

    SSOT 優先順位 (Round 3 [C3] [S2]、 概念 § 4.3):
        1. date_overrides[d]              (= early close / late open / partial close)
        2. broker_full_close_holidays
        3. weekday=Sat                    → (0, 0)
        4. weekday=Sun                    → (reopen_hour_utc * 60, 1440)  # season 別
        5. weekday=Fri                    → (0, close_hour_utc * 60)       # season 別
        6. otherwise (Mon-Thu)            → (0, 1440)                      # full open

    DST season boundary semantics (Round 3 [C4]):
        region_start / region_end は inclusive、 disjoint、 連続 cover
        春切替日は当日が新 region の region_start

    Round 5 [W3] 反映: 重複 reject の SSOT
        date_overrides ∩ broker_full_close_holidays == ∅ (= ambiguity 防止)
    """

    dst_aware_close_table: tuple[BrokerSeasonalCloseSpec, ...]
    broker_full_close_holidays: frozenset[date]
    date_overrides: Mapping[date, tuple[int, int]]
    period_start: date
    period_end: date
    provenance: BrokerSchedulingProvenance
    version: str

    def __post_init__(self) -> None:
        # Round 5 [S2] / [W3] / Round D1 [W1] 反映: 検証 8 項目、 順序依存明文化
        # 順序契約: I-1 → I-2 → I-3/I-4 (= dst table) → I-5 → I-6 → I-7 (= I-5/I-6 後)
        # I-1: version 整合 (= 最初に弾く、 旧 schema 流入を遮断)
        if self.version != BROKER_SCHEDULE_VERSION:
            raise ValueError(
                f"version must be {BROKER_SCHEDULE_VERSION!r}, got {self.version!r}"
            )

        # I-2: period 妥当性 (= 後続検証の前提)
        if self.period_start > self.period_end:
            raise ValueError(
                f"period_start ({self.period_start}) > period_end ({self.period_end})"
            )

        # I-3: dst_aware_close_table が period を連続 cover
        if not self.dst_aware_close_table:
            raise ValueError("dst_aware_close_table must be non-empty")
        sorted_specs = sorted(self.dst_aware_close_table, key=lambda s: s.region_start)
        if sorted_specs[0].region_start > self.period_start:
            raise ValueError(
                f"dst_aware_close_table starts at {sorted_specs[0].region_start}, "
                f"after period_start {self.period_start}"
            )
        if sorted_specs[-1].region_end < self.period_end:
            raise ValueError(
                f"dst_aware_close_table ends at {sorted_specs[-1].region_end}, "
                f"before period_end {self.period_end}"
            )
        # I-4: dst_aware_close_table 隣接 region の連続性 (= 隙間なし、 重複なし)
        for prev, curr in zip(sorted_specs, sorted_specs[1:]):
            if prev.region_end + timedelta(days=1) != curr.region_start:
                raise ValueError(
                    f"region gap or overlap: {prev.name!r} ends {prev.region_end}, "
                    f"{curr.name!r} starts {curr.region_start}"
                )

        # I-5: broker_full_close_holidays ⊂ [period_start, period_end] (= I-2 後)
        for d in self.broker_full_close_holidays:
            if not (self.period_start <= d <= self.period_end):
                raise ValueError(
                    f"broker_full_close_holiday {d} out of period "
                    f"[{self.period_start}, {self.period_end}]"
                )

        # I-6: date_overrides の key / value 検証 (= I-2 後)
        # 半開区間 [start_min, end_min) 規約 (Round D1 [C3])
        for d, window in self.date_overrides.items():
            if not (self.period_start <= d <= self.period_end):
                raise ValueError(
                    f"date_override key {d} out of period "
                    f"[{self.period_start}, {self.period_end}]"
                )
            start_min, end_min = window
            if not (0 <= start_min <= end_min <= 1440):
                raise ValueError(
                    f"date_override[{d}] window invalid: ({start_min}, {end_min}). "
                    f"Required: 0 <= start <= end <= 1440 (半開区間 [start, end))"
                )

        # I-7: date_overrides ∩ broker_full_close_holidays == ∅ (Round 5 [W3])
        # **順序依存**: I-5 (full_close 妥当) / I-6 (overrides 妥当) 後に重複検出
        overlap = set(self.date_overrides.keys()) & set(self.broker_full_close_holidays)
        if overlap:
            raise ValueError(
                f"date_overrides and broker_full_close_holidays must not overlap. "
                f"Overlapping dates: {sorted(overlap)}"
            )

        # I-8: date_overrides は 1 日 1 window
        # Round D1 [C2] 反映: Mapping 型の構造保証は不十分 (= YAML loader が duplicate key を
        # 黙って上書きするため). load_broker_trading_schedule で **duplicate key reject** を
        # 強制する SafeLoader subclass を使用、 YAML→Mapping 変換時に検出.
        # dataclass 受領後は Mapping 一意性が保証される (= YAML lint で検出済).

    def open_window_for_utc_date(self, d: date) -> tuple[int, int]:
        """SSOT 優先順位 (上記 docstring 参照).

        **Round D1 [C3] 反映**: 戻り値は半開区間 `[start_min, end_min)`:
            - 0 <= start_min <= end_min <= 1440
            - start_min == end_min == 0 → 完全 closed (空区間)
            - start_min == 0, end_min == 1440 → 完全 open
            - 境界値 (= start == 他区間の end) は overlap 計算で 0 を返す

        Args:
            d: UTC date (= bar.bar_time.date() 想定).

        Returns:
            (start_min, end_min) 半開区間 [start_min, end_min).
        """
        # 1. date_overrides 最優先
        if d in self.date_overrides:
            return self.date_overrides[d]
        # 2. broker_full_close_holidays
        if d in self.broker_full_close_holidays:
            return (0, 0)
        # 3-6. weekday + season
        weekday = d.weekday()  # 0=Mon..6=Sun
        if weekday == 5:  # Saturday
            return (0, 0)
        spec = self._find_season(d)
        if weekday == 6:  # Sunday
            return (spec.reopen_hour_utc * 60, 1440)
        if weekday == 4:  # Friday
            return (0, spec.close_hour_utc * 60)
        # Mon-Thu
        return (0, 1440)

    def _find_season(self, d: date) -> BrokerSeasonalCloseSpec:
        """dst_aware_close_table から d を含む region を線形探索 (deterministic)."""
        for spec in self.dst_aware_close_table:
            if spec.region_start <= d <= spec.region_end:
                return spec
        # __post_init__ で連続 cover を検証済、 ここに到達しないはず
        raise AssertionError(
            f"date {d} not covered by dst_aware_close_table "
            f"(period: [{self.period_start}, {self.period_end}])"
        )
```

### 3.5 MarketHolidayCalendar

```python
@dataclass(frozen=True)
class MarketHolidayCalendar:
    """単一市場の取引所公式 holiday (観測情報のみ).

    SSOT (Round 2 [C2] [S2] / 概念 § 4.4):
        - 用途: ObservabilityFlags.holiday_markets を埋める観測情報
        - expected_bar_count には touch しない (= broker 配信が継続している限り bar 出る)
        - caller (T071 等) は holiday_markets を任意の condition として stratified 使用
    """

    market: MarketCode
    period_start: date
    period_end: date
    holidays: frozenset[date]
    schema_version: str

    def __post_init__(self) -> None:
        if self.market not in ("tokyo", "london", "ny"):
            raise ValueError(f"market must be tokyo/london/ny, got {self.market!r}")
        if self.schema_version != HOLIDAY_CALENDAR_VERSION:
            raise ValueError(
                f"schema_version must be {HOLIDAY_CALENDAR_VERSION!r}, "
                f"got {self.schema_version!r} (market={self.market!r})"
            )
        if self.period_start > self.period_end:
            raise ValueError(
                f"period_start ({self.period_start}) > period_end ({self.period_end}) "
                f"(market={self.market!r})"
            )
        for d in self.holidays:
            if not (self.period_start <= d <= self.period_end):
                raise ValueError(
                    f"holiday {d} out of period "
                    f"[{self.period_start}, {self.period_end}] (market={self.market!r})"
                )

    def contains(self, d: date) -> bool:
        """検証済 calendar の raw lookup (Round 1 [S5] / Round 2 [W3]).

        前提: validate_calendar_coverage が dataset_span を覆うことを load 時に集約検証済.
        period 外 d を渡すのは設計上の bug (= caller 違反).
        """
        return d in self.holidays
```

### 3.6 ObservabilityFlags

```python
@dataclass(frozen=True)
class ObservabilityFlags:
    """schedule とは独立の audit / log 用 mark.

    Round 2 [W1] [W2] / Round 3 [S5] 反映:
        - is_dst_transition (bool) → dst_transition_markets (frozenset[MarketCode])
        - has_all_g3_holidays → all_g3_market_holiday rename
    """

    dst_transition_markets: frozenset[MarketCode]  # 0..2 個、 Tokyo は不在
    holiday_markets: frozenset[MarketCode]          # 0..3 個

    def __post_init__(self) -> None:
        invalid_dst = self.dst_transition_markets - frozenset({"london", "ny"})
        if invalid_dst:
            raise ValueError(
                f"dst_transition_markets must be subset of {{'london', 'ny'}}, "
                f"got invalid: {invalid_dst}"
            )
        invalid_holiday = self.holiday_markets - frozenset({"tokyo", "london", "ny"})
        if invalid_holiday:
            raise ValueError(
                f"holiday_markets must be subset of {{'tokyo', 'london', 'ny'}}, "
                f"got invalid: {invalid_holiday}"
            )

    @property
    def all_g3_market_holiday(self) -> bool:
        """Round 3 [S5] rename: len(holiday_markets) == 3."""
        return len(self.holiday_markets) == 3
```

### 3.7 SessionBlock (T070 改造、 概念 § 4.6)

```python
# src/backtest/session_block.py (T070 で新設、 T072 で 4 field 追加 + property 変更)

from src.backtest.calendar import (
    M1_PLUS_GRANULARITIES,
    BUCKET_FULL_MINUTES,
    BUCKET_FULL_MINUTES_X60,
    ObservabilityFlags,
    ScheduleStatus,
    compute_expected_bar_count,
)


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
    open_minutes: int = BUCKET_FULL_MINUTES                     # primary field (Round 3 [C2] [S1])
    granularity_seconds: int = 60                                # M1 default
    observability_flags: ObservabilityFlags = field(
        default_factory=lambda: ObservabilityFlags(
            dst_transition_markets=frozenset(),
            holiday_markets=frozenset(),
        )
    )

    def __post_init__(self) -> None:
        # T070 既存 invariant (= bar_count >= 0, F6 (= pnl_before_costs == pnl_net + spread + holding) 等) は不変
        # T072 invariant:
        if self.granularity_seconds not in M1_PLUS_GRANULARITIES:
            raise ValueError(
                f"granularity_seconds must be in M1_PLUS_GRANULARITIES "
                f"(= {sorted(M1_PLUS_GRANULARITIES)}), got {self.granularity_seconds}"
            )
        if BUCKET_FULL_MINUTES_X60 % self.granularity_seconds != 0:
            # I5 の念押し (= M1_PLUS_GRANULARITIES の SSOT 整合性、 概念 § 4.6 invariant)
            raise ValueError(
                f"granularity_seconds {self.granularity_seconds} does not divide "
                f"BUCKET_FULL_MINUTES_X60 ({BUCKET_FULL_MINUTES_X60})"
            )
        if not (0 <= self.open_minutes <= BUCKET_FULL_MINUTES):
            raise ValueError(
                f"open_minutes must be in [0, {BUCKET_FULL_MINUTES}], got {self.open_minutes}"
            )

        # I8 tolerance check (Round 3 [W5] / Round 5 [W4] 反映)
        # open block (open_minutes > 0): bar_count <= expected + ceil(max(5, expected*0.01))
        # closed_full block (open_minutes == 0): bar_count == 0 を厳密期待 (= warning escalation)
        # 注: __post_init__ では raise しない (= warning は logger 経由、 詳細実装で logger 接続)
        # 実装時は logger.warning() で別系列ログ名を発火:
        #   open block: logger.warning("session_block_bar_count_exceeds_tolerance", ...)
        #   closed_full: logger.warning("closed_full_unexpected_bars", ...)  # Round 5 [W4]

    @property
    def expected_bar_count(self) -> int:
        """Round 3 [C2] / 概念 § 4.6 derived. open_minutes + granularity_seconds から導出."""
        return compute_expected_bar_count(self.open_minutes, self.granularity_seconds)

    @property
    def schedule_status(self) -> ScheduleStatus:
        """Round 3 [C2] / 概念 § 4.6 derived.

        open_minutes == BUCKET_FULL_MINUTES (= 480) → "regular"
        open_minutes == 0                            → "closed_full"
        else                                         → "closed_partial"

        例: H4 で Sunday NY 120 min →
            open_minutes=120 / expected_bar_count=0 / schedule_status="closed_partial"
            (= partial 強度を open_minutes に保持、 expected の floor 演算で消失しない)
        """
        if self.open_minutes == BUCKET_FULL_MINUTES:
            return "regular"
        if self.open_minutes == 0:
            return "closed_full"
        return "closed_partial"

    @property
    def is_partial_bar_block(self) -> bool:
        """T070 後方互換 + T072 改訂 (概念 § 4.6)."""
        return self.bar_count < self.expected_bar_count

    def to_record(self, *, include_derived: bool = False) -> dict:
        """Round 3 [W1] / Round 4 [W6] / Round 5 [W3] / Round D1 [C5] [S3] / Round D2 [C1] [S1]
        audit/export contract.

        SSOT 出力 schema (= SESSION_BLOCK_STORAGE_FIELDS / SESSION_BLOCK_DERIVED_FIELD_PATHS):
            include_derived=False: SESSION_BLOCK_STORAGE_FIELDS の 12 path
                (= 9 top-level + 2 nested observability_flags + 1 record_schema_version)
            include_derived=True : 上記 + SESSION_BLOCK_DERIVED_FIELD_PATHS の 4 path
                (= 3 top-level + 1 nested observability_flags.all_g3_market_holiday)

        **audit / export caller は必ず include_derived=True を使うこと**
        (Round 4 [W6] 反映、 docstring contract).

        record_schema_version = RECORD_SCHEMA_VERSION (= "1.0.0").
        bump 条件 (Round D2 [W1]):
            MAJOR: field 削除 / 意味変更 / 型変更 / nested path 変更
            MINOR: field 追加
            PATCH: 出力値の bug fix のみ (= schema 不変)
        future field 追加は SESSION_BLOCK_DERIVED_FIELD_PATHS の更新 + RECORD_SCHEMA_VERSION bump.
        """
        record = {
            "record_schema_version": RECORD_SCHEMA_VERSION,
            "business_date": self.business_date,
            "bucket": self.bucket,
            "bar_count": self.bar_count,
            "trade_count": self.trade_count,
            "pnl_net": self.pnl_net,
            "pnl_before_costs": self.pnl_before_costs,
            "spread_cost_total": self.spread_cost_total,
            "holding_cost_total": self.holding_cost_total,
            "open_minutes": self.open_minutes,
            "granularity_seconds": self.granularity_seconds,
            "observability_flags": {
                "dst_transition_markets": sorted(self.observability_flags.dst_transition_markets),
                "holiday_markets": sorted(self.observability_flags.holiday_markets),
            },
        }
        if include_derived:
            record["schedule_status"] = self.schedule_status
            record["expected_bar_count"] = self.expected_bar_count
            record["is_partial_bar_block"] = self.is_partial_bar_block
            # Round D2 [C1] [S1]: SESSION_BLOCK_DERIVED_FIELD_PATHS の path で明記 (nested)
            record["observability_flags"]["all_g3_market_holiday"] = (
                self.observability_flags.all_g3_market_holiday
            )
        return record
```

**Round D1 [W3] 反映 logger 取得方針**: `src/backtest/session_block.py` の **module-level logger** を使用 (= `logger = logging.getLogger(__name__)`)、 `__post_init__` 内では `logger.warning()` で warning emit:
- open block tolerance 違反: `logger.warning("session_block_bar_count_exceeds_tolerance", extra={...})`
- closed_full block 異常 bar: `logger.warning("closed_full_unexpected_bars", extra={...})` (Round 5 [W4] 別系列)

logger 取得は `__post_init__` 開始時 (= dataclass instance ごと) でなく module-level で 1 回、 ログ分散を防ぐ。

## 4. アルゴリズム詳細 (擬似コード)

### 4.1 is_dst_transition

```python
def is_dst_transition(market: MarketCode, d: date) -> bool:
    """d が market の DST 切替日なら True (London / NY のみ).

    SSOT: zoneinfo (IANA tz database) 経由で transition を deterministic 判定.

    判定方法: d 00:00 local と d+1 00:00 local の utcoffset が異なれば transition.

    Tokyo は常に False (= Asia/Tokyo は DST なし).

    Round 3 [W2] open question (runtime tzdata version log) は本関数では touch せず、
    詳細設計の audit layer (T071/T073) で別途記録.
    """
    if market == "tokyo":
        return False
    if market == "london":
        tz = ZoneInfo("Europe/London")
    elif market == "ny":
        tz = ZoneInfo("America/New_York")
    else:
        raise ValueError(f"unknown market: {market!r}")

    midnight_today = datetime.combine(d, time(0, 0), tzinfo=tz)
    midnight_tomorrow = datetime.combine(d + timedelta(days=1), time(0, 0), tzinfo=tz)
    return midnight_today.utcoffset() != midnight_tomorrow.utcoffset()
```

### 4.2 is_market_holiday

```python
def is_market_holiday(market: MarketCode, d: date, calendar: MarketHolidayCalendar) -> bool:
    """d が market の holiday なら True. calendar.market 一致確認 + raw lookup.

    前提: validate_calendar_coverage が dataset_span を覆うことを load 時に集約検証済.
    """
    if calendar.market != market:
        raise ValueError(
            f"calendar.market={calendar.market!r} != requested market={market!r}"
        )
    return calendar.contains(d)
```

### 4.3 compute_observability_flags

```python
def compute_observability_flags(
    business_date: date,
    calendars: Mapping[MarketCode, MarketHolidayCalendar],
) -> ObservabilityFlags:
    """business_date 単位の observability flags 集計.

    Round 2 [W1] / 概念 § 4.5 反映: dst_transition_markets を frozenset で bucket-local 説明力.
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

### 4.4 compute_bucket_open_minutes

```python
def compute_bucket_open_minutes(
    business_date: date,
    bucket: SessionBlockBucket,
    broker_schedule: BrokerTradingSchedule,
) -> int:
    """指定 (date, bucket) の broker-open minutes (= bucket UTC ∩ broker open window).

    SSOT (Round 2 [C2] / 概念 § 4.7): broker_schedule のみで決定、 market holiday touch しない.

    Args:
        business_date: UTC date.
        bucket: SessionBlockBucket (T070 SSOT).
        broker_schedule: BrokerTradingSchedule.

    Returns:
        int (0..480) = bucket UTC 区間の broker-open minutes.
    """
    open_start, open_end = broker_schedule.open_window_for_utc_date(business_date)
    start_hour, end_hour = BLOCK_BUCKET_RANGES_UTC[bucket]
    bucket_start_min = start_hour * 60
    bucket_end_min = end_hour * 60
    overlap_start = max(bucket_start_min, open_start)
    overlap_end = min(bucket_end_min, open_end)
    return max(0, overlap_end - overlap_start)
```

### 4.5 compute_expected_bar_count

```python
def compute_expected_bar_count(open_minutes: int, granularity_seconds: int) -> int:
    """granularity から期待 bar 数を導出.

    Round 4 [S2] 反映: complete candle 数を数えるため floor (= integer 切り捨て).
        例: H4 (granularity_seconds=14400) で open_minutes=120 →
            120 * 60 / 14400 = 0.5 → floor = 0 (= H4 candle 完成しない)
        open_minutes=120 自体は SessionBlock.open_minutes に保持、 partial 強度維持.

    Args:
        open_minutes: 0..480.
        granularity_seconds: M1_PLUS_GRANULARITIES.

    Returns:
        int >= 0.
    """
    return open_minutes * 60 // granularity_seconds
```

### 4.6 validate_calendar_coverage

```python
def validate_calendar_coverage(
    calendars: Mapping[MarketCode, MarketHolidayCalendar],
    broker_schedule: BrokerTradingSchedule,
    dataset_span: tuple[date, date],
) -> None:
    """dataset 全期間が calendars + broker_schedule の period 内に収まるか一括検証.

    SSOT (Round 1 [S5] / Round 2 [W3] / 概念 § 4.7 / Round D1 [C6]):
        load 時に caller が一回呼び、 検証済前提で contains() / open_window_for_utc_date()
        を raw lookup. per-call ValueError は廃止.

    **Round D1 [C6] 反映**: dataset_span は **両端 inclusive** `(start_inclusive, end_inclusive)`:
        - 検証条件 (両端 inclusive): start <= end / period_start <= start / period_end >= end
        - period も両端 inclusive (= MarketHolidayCalendar / BrokerTradingSchedule 双方の SSOT)
        - bucket UTC range / open_window は半開区間だが、 date 単位の period / dataset_span は両端 inclusive
          (= 異なる粒度 (date vs minute) で異なる規約、 命名で区別)

    Args:
        calendars: 全 3 市場の MarketHolidayCalendar.
        broker_schedule: BrokerTradingSchedule.
        dataset_span: (start_date_inclusive, end_date_inclusive).

    Raises:
        ValueError: いずれかの calendars / broker_schedule の period が dataset_span を覆わない.
        KeyError: calendars に "tokyo" / "london" / "ny" のいずれかが欠落.
    """
    start, end = dataset_span
    if start > end:
        raise ValueError(f"dataset_span start ({start}) > end ({end})")

    # broker_schedule period check
    if broker_schedule.period_start > start:
        raise ValueError(
            f"broker_schedule.period_start ({broker_schedule.period_start}) > "
            f"dataset_span start ({start})"
        )
    if broker_schedule.period_end < end:
        raise ValueError(
            f"broker_schedule.period_end ({broker_schedule.period_end}) < "
            f"dataset_span end ({end})"
        )

    # calendars period check (= 全 3 市場)
    for market in ("tokyo", "london", "ny"):
        cal = calendars[market]  # KeyError if missing
        if cal.period_start > start:
            raise ValueError(
                f"calendar[{market!r}].period_start ({cal.period_start}) > "
                f"dataset_span start ({start})"
            )
        if cal.period_end < end:
            raise ValueError(
                f"calendar[{market!r}].period_end ({cal.period_end}) < "
                f"dataset_span end ({end})"
            )
```

### 4.7 load_market_holiday_calendar

```python
def load_market_holiday_calendar(market: MarketCode, yaml_path: Path) -> MarketHolidayCalendar:
    """YAML から MarketHolidayCalendar を構築.

    YAML schema (例 config/calendars/tokyo_market_holidays.yaml):
        market: "tokyo"
        schema_version: "1.0.0"
        period_start: "2022-01-01"
        period_end: "2027-12-31"
        provenance:
          source: "JPX 公式 holiday list 2022-2027"
          verified_at: "2026-04-30"
          confidence: "high"
          notes: "国民の祝日 + TSE 取引所 close 日"
        holidays:
          - "2022-01-01"
          - "2022-01-03"
          - ...
    """
    with open(yaml_path, "r", encoding="utf-8") as f:
        data = yaml.load(f, Loader=_DuplicateKeyRejectLoader)  # Round D1 [C2]
    if data["market"] != market:
        raise ValueError(
            f"yaml market={data['market']!r} != requested market={market!r} "
            f"(yaml_path={yaml_path})"
        )
    return MarketHolidayCalendar(
        market=market,
        period_start=date.fromisoformat(data["period_start"]),
        period_end=date.fromisoformat(data["period_end"]),
        holidays=frozenset(date.fromisoformat(d) for d in data["holidays"]),
        schema_version=data["schema_version"],
    )
```

### 4.8 load_broker_trading_schedule

```python
class _DuplicateKeyRejectLoader(yaml.SafeLoader):
    """Round D1 [C2] / Round D2 [C2] [S2] 反映: YAML duplicate key + merge key を reject する SafeLoader subclass.

    PyYAML default の SafeLoader は:
        - duplicate key を silently 最後勝ちで上書き
        - merge key `<<` を flatten_mapping で展開し、 元の duplicate を見えなくする
    本 subclass は両方を構造的に reject:
        - duplicate key: yaml.constructor.ConstructorError raise
        - merge key (= tag:yaml.org,2002:merge): カレンダー設定では使用禁止、 ConstructorError raise

    date_overrides の I-8 (= 1 日 1 window) を YAML 段階で構造保証.
    """


def _construct_mapping_no_duplicates(loader, node, deep=False):
    """Round D2 [C2] [S2] 反映: duplicate key + merge key を reject."""
    mapping = {}
    for key_node, value_node in node.value:
        # Round D2 [C2] [S2]: merge key `<<` 禁止 (= flatten 経由の重複迂回を防止)
        if key_node.tag == "tag:yaml.org,2002:merge":
            raise yaml.constructor.ConstructorError(
                None, None,
                "YAML merge key '<<' is not allowed in calendar configs "
                "(prevents flatten-then-overwrite duplicate keys)",
                key_node.start_mark,
            )
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            raise yaml.constructor.ConstructorError(
                None, None,
                f"duplicate key {key!r} found in YAML mapping",
                key_node.start_mark,
            )
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


_DuplicateKeyRejectLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_mapping_no_duplicates,
)


def load_broker_trading_schedule(yaml_path: Path) -> BrokerTradingSchedule:
    """YAML から BrokerTradingSchedule を構築.

    Round D1 [C2] 反映: _DuplicateKeyRejectLoader 使用で duplicate key を YAML 段階で reject.

    YAML schema (例 config/calendars/broker_trading_schedule.yaml):
        version: "1.0.0"
        period_start: "2022-01-01"
        period_end: "2027-12-31"
        provenance:
          source: "OANDA Developer Portal v20"
          verified_at: "2026-04-30"
          confidence: "high"
          notes: "金曜 NY close / 日曜 NY reopen の DST 切替を IANA tz から手動列挙"
        dst_aware_close_table:
          - name: "ny_dst_2024"
            region_start: "2024-03-10"
            region_end:   "2024-11-02"
            close_hour_utc: 21
            reopen_hour_utc: 21
          - name: "ny_standard_2024_2025"
            region_start: "2024-11-03"
            region_end:   "2025-03-08"
            close_hour_utc: 22
            reopen_hour_utc: 22
        broker_full_close_holidays:
          - "2024-12-25"
          - "2025-01-01"
        date_overrides:
          "2024-12-24": [0, 1080]  # クリスマス前日早閉まり 18:00 UTC
          "2024-07-04": [0, 1020]  # 米独立記念日早閉まり 17:00 UTC
    """
    with open(yaml_path, "r", encoding="utf-8") as f:
        data = yaml.load(f, Loader=_DuplicateKeyRejectLoader)

    specs = tuple(
        BrokerSeasonalCloseSpec(
            name=s["name"],
            region_start=date.fromisoformat(s["region_start"]),
            region_end=date.fromisoformat(s["region_end"]),
            close_hour_utc=s["close_hour_utc"],
            reopen_hour_utc=s["reopen_hour_utc"],
        )
        for s in data["dst_aware_close_table"]
    )

    full_close = frozenset(
        date.fromisoformat(d) for d in data["broker_full_close_holidays"]
    )

    overrides = {
        date.fromisoformat(k): tuple(v)
        for k, v in (data.get("date_overrides") or {}).items()
    }

    prov_data = data["provenance"]
    provenance = BrokerSchedulingProvenance(
        source=prov_data["source"],
        verified_at=date.fromisoformat(prov_data["verified_at"]),
        confidence=prov_data["confidence"],
        notes=prov_data["notes"],
    )

    return BrokerTradingSchedule(
        dst_aware_close_table=specs,
        broker_full_close_holidays=full_close,
        date_overrides=overrides,
        period_start=date.fromisoformat(data["period_start"]),
        period_end=date.fromisoformat(data["period_end"]),
        provenance=provenance,
        version=data["version"],
    )
```

### 4.9 aggregate_session_blocks 改造 (T070 + T072)

```python
# src/backtest/session_block.py (T070 で新設、 T072 で signature 拡張)

def aggregate_session_blocks(
    bars: Sequence[PriceBar],
    trades: Sequence[Trade],
    *,
    mode: Literal["production", "test"],   # Round D1 [C4] [S1] 反映: 必須引数化
    broker_schedule: BrokerTradingSchedule | None = None,
    calendars: Mapping[MarketCode, MarketHolidayCalendar] | None = None,
    granularity_seconds: int = 60,
) -> tuple[SessionBlock, ...]:
    """T072 改訂: open_minutes primary 駆動の SessionBlock 構築.

    SSOT (概念 § 4.6 / § 6.4):
        date universe (T070 不変): bars + trades touched UTC date set × 3 bucket.
        open_minutes 駆動 (Round 3 [C1] [C2]):
            broker_schedule provided → compute_bucket_open_minutes(d, bucket, broker_schedule)
            broker_schedule None    → BUCKET_FULL_MINUTES (= 480、 granularity 非依存 default)
        observability_flags 駆動 (Round 2):
            calendars provided → compute_observability_flags(d, calendars)
            calendars None    → ObservabilityFlags(frozenset(), frozenset()) [= default]

    部分構成 (Round 3 [W2] / Round 5 [W2] / Round D1 [C4] [S1]):
        mode は **必須引数** (= default 廃止、 Round D1 [C4]).
        mode="production":
            broker_schedule と calendars **両方 provided** を要求 (= 片方欠落で ValueError raise).
            T070 互換 (両方 None) も production では reject (= 明示的に T072 機能を使う前提).
        mode="test":
            4 通り全許容 (両方 None / どちらかのみ / 両方 provided).
            test/debug 用 (= migration / T070 単独 merge / 部分テスト).

    **Round 5 [S3] 反映**: C22 calendars-only は test/debug 専用、 production 想定外.

    Args:
        bars: backtest 期間の全 bar (時系列順、 UTC tz-aware).
        trades: backtest で生成された全 trade.
        broker_schedule: BrokerTradingSchedule (Round 3 [C1] 反映).
        calendars: 全 3 市場の MarketHolidayCalendar.
        granularity_seconds: bar の granularity.
        mode: production / test.

    Returns:
        SessionBlock の tuple. (date, bucket) で sort.

    Raises:
        ValueError: mode="production" で部分構成、 bar_time / trade.exit_time 非 UTC.
    """
    # production mode reject (Round 5 [W2])
    if mode == "production":
        if broker_schedule is None or calendars is None:
            raise ValueError(
                "production mode requires both broker_schedule and calendars to be provided. "
                "T070 互換 (両方 None) は test/debug 専用. "
                "片方のみ提供は誤用 (= T072 SSOT で部分構成は禁止)."
            )

    # T070 既存 logic (date_set / 集計): bars と trades から (date, bucket) でグループ化
    bar_count_map: dict[tuple[date, SessionBlockBucket], int] = {}
    date_set: set[date] = set()
    for bar in bars:
        bucket = compute_bucket_for_bar(bar.bar_time)
        d = bar.bar_time.date()
        date_set.add(d)
        bar_count_map[(d, bucket)] = bar_count_map.get((d, bucket), 0) + 1

    trade_groups: dict[tuple[date, SessionBlockBucket], list[Trade]] = {}
    for trade in trades:
        bucket = compute_bucket_for_trade(trade)
        d = trade.exit_time.date()
        date_set.add(d)
        trade_groups.setdefault((d, bucket), []).append(trade)

    # date universe = bars + trades が触れた全 UTC date × 3 bucket (T070 SSOT 不変)
    blocks: list[SessionBlock] = []
    for d in sorted(date_set):
        flags = (
            compute_observability_flags(d, calendars)
            if calendars is not None
            else ObservabilityFlags(
                dst_transition_markets=frozenset(),
                holiday_markets=frozenset(),
            )
        )
        for bucket in _BUCKETS:
            key = (d, bucket)
            bar_count = bar_count_map.get(key, 0)
            block_trades = trade_groups.get(key, [])
            trade_count = len(block_trades)

            # T070 SSOT 集計 (concept §3.4.0)
            pnl_net = sum(
                (t.pnl - t.spread_cost for t in block_trades), start=Decimal(0)
            )
            pnl_before_costs = sum(
                (t.pnl + t.holding_cost for t in block_trades), start=Decimal(0)
            )
            spread_cost_total = sum(
                (t.spread_cost for t in block_trades), start=Decimal(0)
            )
            holding_cost_total = sum(
                (t.holding_cost for t in block_trades), start=Decimal(0)
            )

            # T072 open_minutes (Round 3 [C1] [C2])
            if broker_schedule is not None:
                open_min = compute_bucket_open_minutes(d, bucket, broker_schedule)
            else:
                open_min = BUCKET_FULL_MINUTES  # 480 default

            blocks.append(SessionBlock(
                business_date=d,
                bucket=bucket,
                bar_count=bar_count,
                trade_count=trade_count,
                pnl_net=pnl_net,
                pnl_before_costs=pnl_before_costs,
                spread_cost_total=spread_cost_total,
                holding_cost_total=holding_cost_total,
                open_minutes=open_min,
                granularity_seconds=granularity_seconds,
                observability_flags=flags,
            ))
    return tuple(blocks)


def aggregate_session_blocks_production(
    bars: Sequence[PriceBar],
    trades: Sequence[Trade],
    *,
    broker_schedule: BrokerTradingSchedule,
    calendars: Mapping[MarketCode, MarketHolidayCalendar],
    granularity_seconds: int = 60,
) -> tuple[SessionBlock, ...]:
    """Round D2 [C3] [S3] 反映: production-only wrapper.

    production caller (= run_ga.py / backtest_runner、 Phase 2 配線) は **本 wrapper のみ呼ぶ**.
    mode 引数を内部で "production" 固定するため、 caller が誤って "test" を渡す経路がない.

    aggregate_session_blocks(mode=...) 直接呼出は test/debug 限定.

    Args:
        bars: backtest 期間の全 bar.
        trades: backtest で生成された全 trade.
        broker_schedule: 必須 (= production では None 不可).
        calendars: 全 3 市場の MarketHolidayCalendar (必須).
        granularity_seconds: bar の granularity.

    Returns:
        SessionBlock の tuple.

    Raises:
        ValueError: aggregate_session_blocks が production mode で raise する条件 (= 本 wrapper 内では
            broker_schedule / calendars が型システム上必須なので構造的に発生しない).
    """
    return aggregate_session_blocks(
        bars,
        trades,
        mode="production",
        broker_schedule=broker_schedule,
        calendars=calendars,
        granularity_seconds=granularity_seconds,
    )
```

## 5. テスト計画 (詳細、 概念 § 10 を test_id 1:1 で展開)

### 5.0 命名規約 (Round D1 [test_id ギャップ])

- 各 test_id は **`Fxxx_<behavior>` 形式**で pytest 関数名と 1:1 対応 (= 枝番 / 接尾辞は `<behavior>` で表現)
- 旧 F1-F4 と F5-F7 で is_market_holiday を二重記載 → **F5-F7 を削除し、 is_market_holiday は F4 系列に統合**
- テスト責務境界を `test_<symbol>_<behavior>_<expected>` (= 関数名) で固定

### 5.1 `tests/backtest/test_calendar.py` (新規)

#### F1-F5: pure function tests (is_dst_transition / is_market_holiday)

| test_id | 内容 | pytest 関数名 |
|---|---|---|
| F1 | `is_dst_transition("tokyo", d)` は任意 date で False | `test_is_dst_transition_tokyo_always_false` |
| F2 | `is_dst_transition("london", d)` 重要 transition 6 件 (= 2024-2026 春/秋) で True、 反例 | `test_is_dst_transition_london_critical_transitions` |
| F3 | `is_dst_transition("ny", d)` 重要 transition 6 件 (= 2024-2026 春/秋) で True、 反例 | `test_is_dst_transition_ny_critical_transitions` |
| F4 | `is_dst_transition` unknown market → ValueError | `test_is_dst_transition_unknown_market_raises` |
| F5 | `is_market_holiday` happy path + market 不一致 ValueError + period 内 True/False (= 旧 F5/F6/F7 統合) | `test_is_market_holiday_happy_and_mismatch` |

#### F8-F14: BrokerSeasonalCloseSpec / BrokerTradingSchedule tests (Round 5 [S2] test matrix)

| F8 | BrokerSeasonalCloseSpec(close_hour_utc=24) → ValueError | `test_seasonal_close_spec_invalid_hour_raises` |
| F9 | BrokerSeasonalCloseSpec(region_start > region_end) → ValueError | `test_seasonal_close_spec_invalid_region_order_raises` |
| F10 | BrokerTradingSchedule version 不一致 → ValueError | `test_broker_schedule_version_mismatch_raises` |
| F11 | BrokerTradingSchedule period_start > period_end → ValueError | `test_broker_schedule_invalid_period_raises` |
| F12 | dst_aware_close_table が region 重複 → ValueError | `test_broker_schedule_dst_table_overlap_raises` |
| F13 | dst_aware_close_table が region 隙間 → ValueError | `test_broker_schedule_dst_table_gap_raises` |
| F14_full_close_out_of_period | broker_full_close_holidays が period 外 → ValueError | `test_broker_schedule_full_close_out_of_period_raises` |
| F14_overrides_out_of_period | date_overrides の key が period 外 → ValueError | `test_broker_schedule_overrides_out_of_period_raises` |
| F14_overrides_invalid_window | date_overrides の window 不正 (start > end / 範囲外) → ValueError | `test_broker_schedule_overrides_invalid_window_raises` |
| F14_overrides_overlap_full_close | date_overrides ∩ broker_full_close_holidays 重複 → ValueError (Round 5 [W3]) | `test_broker_schedule_overrides_overlap_with_full_close_raises` |
| F14_yaml_duplicate_key_reject | YAML duplicate key (= date_overrides) は load 時 ConstructorError (Round D1 [C2]) | `test_broker_schedule_yaml_duplicate_key_rejected` |
| F14_yaml_merge_key_reject | YAML merge key `<<` は load 時 ConstructorError (Round D2 [C2] [S2]、 flatten 経由の重複迂回防止) | `test_broker_schedule_yaml_merge_key_rejected` |
| F14_yaml_duplicate_after_flatten | merge key 経由の duplicate も検出 (= merge key reject で構造的に防止確認) | `test_broker_schedule_yaml_duplicate_after_merge_attempt_rejected` |
| F14_property_based_continuous_cover | property-based test: ランダム生成された dst_aware_close_table が連続 cover かつ非重複なら pass、 隙間/重複なら ValueError (Round D1 [S4]) | `test_broker_schedule_property_continuous_cover` |

#### F15-F22: open_window_for_utc_date tests (複合ケース表 § 6.5 駆動)

| F15 | Mon-Thu (= weekday 0-3) → (0, 1440) | `test_open_window_weekday_full_open` |
| F16 | Sat → (0, 0) | `test_open_window_saturday_closed` |
| F17 | Sun standard season (reopen=22) → (1320, 1440) | `test_open_window_sunday_standard_reopen` |
| F18 | Sun DST season (reopen=21) → (1260, 1440) | `test_open_window_sunday_dst_reopen` |
| F19 | Fri standard season (close=22) → (0, 1320) | `test_open_window_friday_standard_close` |
| F20 | Fri DST season (close=21) → (0, 1260) | `test_open_window_friday_dst_close` |
| F21 | broker_full_close_holiday (例: 12/25) → (0, 0) | `test_open_window_full_close_holiday` |
| F22 | date_override (例: 12/24 に [0, 1080]) → (0, 1080) | `test_open_window_date_override_priority` |

#### F23-F28: MarketHolidayCalendar tests

| F23 | happy path (load + contains) | `test_market_holiday_calendar_load_and_contains` |
| F24 | YAML schema_version 不一致 → ValueError | `test_market_holiday_calendar_version_mismatch_raises` |
| F25 | YAML market 不一致 (yaml.market != requested) → ValueError | `test_market_holiday_calendar_market_mismatch_raises` |
| F26 | YAML holidays が period 外 → ValueError | `test_market_holiday_calendar_out_of_period_raises` |
| F27 | period_start > period_end → ValueError | `test_market_holiday_calendar_invalid_period_raises` |
| F28 | unknown market → ValueError | `test_market_holiday_calendar_unknown_market_raises` |

#### F29-F33: ObservabilityFlags / compute_observability_flags tests

| F29 | dst_transition_markets ⊂ {"london","ny"} | `test_observability_flags_dst_subset_invariant` |
| F30 | holiday_markets ⊂ {"tokyo","london","ny"} | `test_observability_flags_holiday_subset_invariant` |
| F31 | all_g3_market_holiday: size==3 で True、 他 False | `test_observability_flags_all_g3_property` |
| F32 | 平日 / no holiday / no DST → flags=default | `test_compute_observability_flags_normal_day` |
| F33 | G3 holiday + London DST → holiday_markets=3 / dst={"london"} | `test_compute_observability_flags_compound_case` |

#### F34-F37: compute_bucket_open_minutes / compute_expected_bar_count tests

| F34 | Mon-Thu / 全 bucket / no override → 480 / expected (M1)=480 | `test_bucket_open_minutes_normal_weekday` |
| F35 | Sat / 全 bucket → 0 / expected=0 | `test_bucket_open_minutes_saturday_closed` |
| F36 | Sun / tokyo / standard → 0 / expected=0 (= reopen 22:00 は ny bucket 内) | `test_bucket_open_minutes_sunday_tokyo_closed` |
| F37 | Sun / ny / standard → 120 / expected (M1)=120 | `test_bucket_open_minutes_sunday_ny_partial` |
| F37_sunday_ny_dst | Sun / ny / DST → 180 / expected (M1)=180 / expected (H4)=0 (= floor) | `test_bucket_open_minutes_sunday_ny_dst_partial_h4_floor` |
| F37_friday_ny_standard | Fri / ny / standard → 360 | `test_bucket_open_minutes_friday_ny_close_partial` |
| F37_friday_tokyo_normal | Fri / tokyo / standard → 480 | `test_bucket_open_minutes_friday_tokyo_normal` |
| F37_holiday_no_impact | Mon-Thu / Tokyo holiday / tokyo bucket → 480 (Round 2 [C2]) | `test_bucket_open_minutes_holiday_no_impact` |
| F37_full_close | broker_full_close_holiday / 全 bucket → 0 | `test_bucket_open_minutes_full_close_holiday` |
| F37_date_override | date_override (12/24 = [0, 1080]) / ny bucket → 120 | `test_bucket_open_minutes_date_override` |
| F37_m5_granularity | M5 (granularity_seconds=300) → expected = open_minutes * 60 / 300 | `test_compute_expected_bar_count_m5` |
| F37_h4_floor | H4 で open_minutes=120 → expected=0 (floor) | `test_compute_expected_bar_count_h4_floor` |
| F37_boundary_overlap | 半開区間境界 (= bucket end == open_start / bucket start == open_end) で overlap=0 (Round D1 [C3]) | `test_bucket_open_minutes_half_open_boundary` |

#### F38-F44: SessionBlock backward-compat tests

| F38 | SessionBlock(default) constructor → open_minutes=480 / granularity_seconds=60 / flags=default | `test_session_block_default_construction` |
| F39 | schedule_status property derived: regular (480) / closed_full (0) / closed_partial (120) | `test_session_block_schedule_status_derived` |
| F39_h4_partial_preserved | H4 で open_minutes=120 → schedule_status="closed_partial" / expected_bar_count=0 | `test_session_block_schedule_status_h4_partial_preserved` |
| F40_eq_hash_compat | T070 既存 fixture 形式と T072 default 構築の eq/hash 互換 | `test_session_block_t070_compat_eq_hash` |
| F41_to_record_storage | to_record(include_derived=False) で SESSION_BLOCK_STORAGE_FIELDS の 12 path のみ含む | `test_session_block_to_record_storage_only` |
| F41_to_record_derived | to_record(include_derived=True) で SESSION_BLOCK_DERIVED_FIELD_PATHS の 4 path (= schedule_status / expected_bar_count / is_partial_bar_block / observability_flags.all_g3_market_holiday) を含む (Round 5 [W3] / Round D1 [C5] / Round D2 [C1]) | `test_session_block_to_record_include_derived` |
| F41_to_record_schema_version | to_record 出力に record_schema_version=="1.0.0" 含む (Round D1 [C5]) | `test_session_block_to_record_schema_version` |
| F41_to_record_derived_field_paths_match | SESSION_BLOCK_DERIVED_FIELD_PATHS の各 path が実出力 dict 内に存在 (= 定数と実装の整合、 Round D2 [C1] [S1]) | `test_session_block_to_record_derived_field_paths_match_schema_constants` |
| F42_invalid_granularity | granularity_seconds=45 (= S5 想定外) → ValueError | `test_session_block_invalid_granularity_raises` |
| F42_h3_rejected | granularity_seconds=10800 (H3) → ValueError (Round 4 [C1]) | `test_session_block_h3_granularity_rejected` |
| F43_invalid_open_minutes | open_minutes=500 (= 480 超) → ValueError | `test_session_block_invalid_open_minutes_raises` |
| F44_tolerance_warning_open | open block: M1 で expected=120 / bar_count=125 → warning ログ "session_block_bar_count_exceeds_tolerance" 発火 | `test_session_block_tolerance_warning_open` |
| F44_closed_full_warning | closed_full block (open_minutes=0) で bar_count=2 → warning ログ "closed_full_unexpected_bars" 発火 (Round 5 [W4]、 別系列名) | `test_session_block_closed_full_warning_separate_log` |

#### F45-F49: aggregate_session_blocks 改造 tests

| F45 | mode="test" / 全 None → 全 block default (= T070 互換) | `test_aggregate_test_mode_all_none_defaults` |
| F46 | mode="test" / broker_schedule のみ → schedule 駆動、 flags=default | `test_aggregate_test_mode_broker_only` |
| F47 | mode="test" / calendars のみ → flags 駆動、 open_minutes=480 default | `test_aggregate_test_mode_calendars_only` |
| F48 | mode="test" / 両方 provided → フル機能 | `test_aggregate_test_mode_both_provided` |
| F48_production_both | mode="production" / 両方 provided → フル機能 | `test_aggregate_production_mode_both_provided` |
| F48_production_partial | mode="production" / 片方 None → ValueError (Round 5 [W2]) | `test_aggregate_production_mode_partial_raises` |
| F48_production_all_none | mode="production" / 両方 None → ValueError | `test_aggregate_production_mode_all_none_raises` |
| F48_mode_required | mode 引数なし呼出 → TypeError (= 必須引数、 Round D1 [C4]) | `test_aggregate_mode_argument_required` |
| F48_production_wrapper | aggregate_session_blocks_production wrapper 呼出 → mode="production" 固定 (Round D2 [C3] [S3]) | `test_aggregate_session_blocks_production_wrapper` |
| F49_production_callers_no_test_mode | production code path (= src/) で aggregate_session_blocks(mode=...) 直接呼出が aggregate_session_blocks_production wrapper 経由のみであることを grep で確認 (Round D2 [C3] [S3]) | `test_production_callers_use_wrapper_only` |
| F49_friday_ny_partial | 金曜 ny / standard → schedule_status="closed_partial" / open_minutes=360 | `test_aggregate_friday_ny_partial` |
| F49_tokyo_holiday_obs | 月曜 / Tokyo holiday / tokyo bucket → schedule_status="regular" / open_minutes=480 / holiday_markets={"tokyo"} | `test_aggregate_tokyo_holiday_observability_only` |
| F49_christmas_full_close_g3 | 12/25 / london bucket → schedule_status="closed_full" / open_minutes=0 / holiday_markets={tokyo,london,ny} | `test_aggregate_christmas_full_close_g3` |

#### F50-F53: validate_calendar_coverage tests

| F50_happy | dataset_span が calendars + broker_schedule period 内 → 正常 (= ValueError raise しない) | `test_validate_coverage_happy_path` |
| F51_calendars_out | dataset_span が calendars period 外 → ValueError | `test_validate_coverage_calendars_out_of_period_raises` |
| F52_broker_out | dataset_span が broker_schedule period 外 → ValueError | `test_validate_coverage_broker_out_of_period_raises` |
| F53_missing_market | calendars に market 欠落 → KeyError | `test_validate_coverage_missing_market_raises` |
| F53_inclusive_boundary | dataset_span 両端 inclusive: span.start == period_start / span.end == period_end → pass、 span.start == period_start - 1 day → ValueError (Round D1 [C6]) | `test_validate_coverage_inclusive_boundary` |

### 5.2 YAML 検証 tests (= F14 系の延長)

`tests/backtest/test_calendar.py` 内で `config/calendars/*.yaml` を実 load して invariant 通過を確認:
- `test_load_real_yaml_market_holidays`: tokyo/london/ny 全 yaml が period 範囲・schema_version invariant を満たす
- `test_load_real_yaml_broker_schedule`: broker_trading_schedule.yaml が dst_aware_close_table 連続 cover、 重複なし、 全 invariant 通過

## 6. YAML 完全 schema (config/calendars/)

### 6.1 broker_trading_schedule.yaml

```yaml
version: "1.0.0"
period_start: "2022-01-01"
period_end: "2027-12-31"
provenance:
  source: "OANDA Developer Portal v20 (https://developer.oanda.com/rest-live-v20/instrument-ep/)"
  verified_at: "2026-04-30"
  confidence: "high"
  notes: "金曜 NY close / 日曜 NY reopen の DST 切替を IANA tz database (zoneinfo) から手動列挙. early close は OANDA spec 確認後 source URL に追記."

dst_aware_close_table:
  # 2022-2027 の DST season を完全列挙 (= [period_start, period_end] 連続 cover、 disjoint)
  # NY DST 切替: 春 = 3月第2日曜 / 秋 = 11月第1日曜
  - name: "ny_standard_2022"
    region_start: "2022-01-01"
    region_end:   "2022-03-12"
    close_hour_utc: 22
    reopen_hour_utc: 22
  - name: "ny_dst_2022"
    region_start: "2022-03-13"
    region_end:   "2022-11-05"
    close_hour_utc: 21
    reopen_hour_utc: 21
  - name: "ny_standard_2022_2023"
    region_start: "2022-11-06"
    region_end:   "2023-03-11"
    close_hour_utc: 22
    reopen_hour_utc: 22
  # ... (2023, 2024, 2025, 2026, 2027 すべて列挙)
  - name: "ny_standard_2027_2028"
    region_start: "2027-11-07"
    region_end:   "2027-12-31"
    close_hour_utc: 22
    reopen_hour_utc: 22

broker_full_close_holidays:
  # OANDA が bar 配信を完全停止する holiday (= クリスマス / 新年)
  # 詳細設計時に OANDA spec 確認、 経験則ベースで列挙
  - "2022-12-25"
  - "2023-01-01"
  - "2023-12-25"
  - "2024-01-01"
  - "2024-12-25"
  - "2025-01-01"
  - "2025-12-25"
  - "2026-01-01"
  - "2026-12-25"
  - "2027-01-01"
  - "2027-12-25"

date_overrides:
  # 早閉まり / 遅 open / 部分閉鎖の date 単位上書き (Round 3 [C3])
  # 例: クリスマス前日 18:00 UTC close (= 米国早閉まり慣行)
  "2022-12-23": [0, 1080]   # 18:00 UTC close (金曜)
  "2023-12-22": [0, 1080]   # 同 (金曜)
  "2024-12-24": [0, 1080]   # 同 (火曜、 23 日休出禁止 + 24 日早閉まり)
  "2025-12-24": [0, 1080]
  "2026-12-24": [0, 1080]
  "2027-12-24": [0, 1080]
  # 米独立記念日早閉まり 17:00 UTC (= 7/3 or 7/4 の前後)
  "2024-07-03": [0, 1020]
  "2025-07-03": [0, 1020]
```

### 6.2 tokyo_market_holidays.yaml

```yaml
market: "tokyo"
schema_version: "1.0.0"
period_start: "2022-01-01"
period_end: "2027-12-31"
provenance:
  source: "JPX 公式 holiday list / 国民の祝日法 (内閣府)"
  verified_at: "2026-04-30"
  confidence: "high"
  notes: "国民の祝日 + TSE 取引所 close 日 (1/2-3 大納会・大発会休、 12/31 大晦日 close 等)"
holidays:
  # 2022
  - "2022-01-01"  # 元日
  - "2022-01-03"  # 振替休日
  - "2022-01-10"  # 成人の日
  # ... (2022-2027 全列挙)
```

### 6.3 london_market_holidays.yaml

```yaml
market: "london"
schema_version: "1.0.0"
period_start: "2022-01-01"
period_end: "2027-12-31"
provenance:
  source: "LSE 公式 trading days / UK bank holidays (gov.uk)"
  verified_at: "2026-04-30"
  confidence: "high"
  notes: "UK bank holidays + LSE 早閉まり日 (= early close は対象外、 full close のみ列挙)"
holidays:
  # 2022
  - "2022-01-03"  # New Year (replacement)
  - "2022-04-15"  # Good Friday
  # ... (2022-2027 全列挙)
```

### 6.4 ny_market_holidays.yaml

```yaml
market: "ny"
schema_version: "1.0.0"
period_start: "2022-01-01"
period_end: "2027-12-31"
provenance:
  source: "NYSE 公式 holiday calendar / Federal Reserve Bank holidays"
  verified_at: "2026-04-30"
  confidence: "high"
  notes: "NYSE / NASDAQ holiday + Federal Reserve holiday の和集合 (= early close は対象外)"
holidays:
  # 2022
  - "2022-01-17"  # Martin Luther King Day
  - "2022-02-21"  # Presidents Day
  # ... (2022-2027 全列挙)
```

## 7. 失敗モード / fail-closed 経路 (Round 1-5 反映の総括)

| ID | 失敗パターン | 対応 |
|---|---|---|
| FC1 | YAML 読込失敗 (file 不在) | FileNotFoundError → caller responsibility |
| FC2 | YAML schema_version / version 不一致 | __post_init__ ValueError |
| FC3 | YAML holidays / broker_full_close / date_overrides が period 外 | __post_init__ ValueError |
| FC4 | dst_aware_close_table の region 重複 / 隙間 | __post_init__ ValueError |
| FC5 | date_overrides の window 不正 (start > end / 範囲外) | __post_init__ ValueError |
| FC6 | date_overrides ∩ broker_full_close_holidays 重複 (Round 5 [W3]) | __post_init__ ValueError |
| FC7 | market 不一致 (YAML vs 引数) | load_*_calendar / is_market_holiday ValueError |
| FC8 | DST 判定で zoneinfo data 不在 | zoneinfo.ZoneInfoNotFoundError (= OS 設定問題) |
| FC9 | validate_calendar_coverage で dataset_span が period 外 | ValueError (= load 時集約) |
| FC10 | mode="production" で部分構成 | ValueError (Round 5 [W2]) |
| FC11 | granularity_seconds が M1_PLUS_GRANULARITIES 外 | __post_init__ ValueError (Round 4 [C1]) |
| FC12 | open_minutes が範囲外 (= 0..480 外) | __post_init__ ValueError |

## 8. backward-compat 4 面検証 (Round 1 [S7] / Round 2 [W7] 反映)

### 8.1 constructor 互換

T070 既存 fixture (= test_session_block.py、 T070 で新設予定) は positional/keyword 両方使われる可能性。 T072 PR は default 付き field 追加のみで positional 互換 (= 既存 caller 不変)。

検証 grep:
```bash
grep -rn "SessionBlock(" src/ tests/ --include="*.py"
```

### 8.2 eq / hash 互換

T070 default 値の SessionBlock と T072 default 値の SessionBlock は **意味的に等価** (= 全 field default で hash も同じ)。 ただし「T070 既存 fixture が dataclass 構築時に T072 field を全 default で構築」 する前提 = T070 + T072 同期 merge 推奨。

検証 test:
```python
def test_session_block_t070_compat_eq_hash():
    # T070 既存 fixture と T072 default 構築が等価
    block = SessionBlock(
        business_date=date(2024, 1, 15),
        bucket="tokyo",
        bar_count=480, trade_count=3,
        pnl_net=Decimal("10"), pnl_before_costs=Decimal("12"),
        spread_cost_total=Decimal("1"), holding_cost_total=Decimal("1"),
    )
    block_t072 = SessionBlock(
        business_date=date(2024, 1, 15),
        bucket="tokyo",
        bar_count=480, trade_count=3,
        pnl_net=Decimal("10"), pnl_before_costs=Decimal("12"),
        spread_cost_total=Decimal("1"), holding_cost_total=Decimal("1"),
        open_minutes=480,
        granularity_seconds=60,
        observability_flags=ObservabilityFlags(frozenset(), frozenset()),
    )
    assert block == block_t072
    assert hash(block) == hash(block_t072)
```

### 8.3 serialization / asdict / repr 互換

`dataclasses.asdict(block)` は T072 field を含む dict を返す。 既存 caller が「キー集合厳密一致」 をテストしている場合は breakage 候補。 grep で確認:
```bash
grep -rn "asdict.*SessionBlock\|dataclasses.asdict" src/ tests/
```

→ T070 SessionBlock は src 未実装、 caller 不在の見込み。 詳細設計実装時に再 grep。

`to_record(include_derived=False)` は asdict と同等 (= storage のみ)。 audit/export 用途は include_derived=True を必須。

### 8.4 既存 fixture / snapshot 互換

T070 detailed-design F1-F22 全 test pass を T072 PR で確認。 T070 docstring SSOT 不変。

## 9. DoD (Definition of Done)

T072 PR が完了するための最小条件:

### 9.1 実装完了

- [ ] `src/backtest/calendar.py` 新設、 §3 / §4 全関数実装 (= 18 シンボル)
- [ ] `src/backtest/session_block.py` (T070) に SessionBlock の **3 field 追加 + 1 メソッド追加** + `expected_bar_count` / `schedule_status` を `@property` 化 (Round D1 [C1])
- [ ] `src/backtest/session_block.py` の aggregate_session_blocks に broker_schedule / calendars / mode 引数追加 + production reject、 **mode は必須引数** (Round D1 [C4])
- [ ] `_DuplicateKeyRejectLoader` 実装 + load_*_calendar / load_broker_trading_schedule で使用 (Round D1 [C2])
- [ ] `RECORD_SCHEMA_VERSION` / `SESSION_BLOCK_STORAGE_FIELDS` / `SESSION_BLOCK_DERIVED_FIELDS` 定数化 (Round D1 [C5])
- [ ] 半開区間 [start, end) 規約を全 docstring / 関数で統一 (Round D1 [C3])
- [ ] `validate_calendar_coverage` の dataset_span 両端 inclusive を docstring 明記 (Round D1 [C6])
- [ ] module-level logger 使用、 `closed_full_unexpected_bars` 別系列ログ名 (Round D1 [W3] / Round 5 [W4])

### 9.2 テスト

- [ ] `tests/backtest/test_calendar.py` 新設、 全 test pass (= 下記 § 5 全項目、 重複・枝番整理済)
- [ ] `tests/backtest/test_session_block.py` の T072 関連テスト全 pass
- [ ] BrokerTradingSchedule の **property-based test** 1 本以上 (= 連続 cover / 非重複、 hypothesis 等使用、 Round D1 [S4])
- [ ] mypy / ruff pass

### 9.3 設定 / ドキュメント

- [ ] `config/calendars/{tokyo,london,ny}_market_holidays.yaml` 新設、 2022-2027 全 holidays 列挙、 provenance 記載
- [ ] `config/calendars/broker_trading_schedule.yaml` 新設、 dst_aware_close_table 連続 cover (2022-2027)、 broker_full_close_holidays + date_overrides + provenance 記載
- [ ] **YAML schema lint を CI に追加 5 段** (Round D1 / Round D2 [YAML schema lint]):
  1. **duplicate / merge key reject**: `<<` 禁止 + duplicate key 検出 (= _DuplicateKeyRejectLoader 経由、 Round D2 [C2])
  2. **schema 検証**: 必須キー (version / period / provenance / dst_aware_close_table 等) / 型チェック
  3. **period 連続性**: dst_aware_close_table が period_start/end を隙間なく cover、 region 重複検出
  4. **coverage 検証**: dataset_span を含むかの validate_calendar_coverage 試走
  5. **production gate checklist** (Round D2 [W5] 反映): OANDA spec 参照日 / URL / 確認者 / YAML 反映差分の record
- [ ] `docs/alpha_factory/stage-gates.md` に T072 セクション追加

### 9.4 互換性 / 監査

- [ ] T070 fixture grep を実施 (= asdict キー厳密一致 caller 不在を確認)
- [ ] **C2 parallel-path 確認** (Round D1 [W5]): 以下経路への影響を grep で確認:
  - `src/utils/time.py` (= UTC stdlib utility)
  - `src/alpha_factory/primitives/_indicators.py:51-55` (= primitives `_SESSION_RANGES_UTC`、 別責務)
  - T060 Period UTC 厳密性 (= `src/alpha_factory/walk_forward.py` 等で Period を使う caller)
- [ ] PR description に **collider bias 規範テンプレート** (= 下記 § 9.6) を T071/T064/T066 詳細設計改訂申し送りとして明記
- [ ] PR description に **OANDA 一次資料未確認 production 反映禁止 ゲート** (Round D1 [W4]) を明記:
  > 本 PR の broker_trading_schedule.yaml は OANDA Developer Portal 公式 spec 確認後に Phase 2 で production 反映する。 Phase 1 は単体テスト範囲、 production 反映前に OANDA spec 一次資料を URL 含めて再確認。

### 9.5 production gate (Round D2 [C3] [S3] 反映で wrapper 化)

- [ ] **production caller (= Phase 2 配線) は `aggregate_session_blocks_production(...)` wrapper のみ使用**: mode="production" を構造的に強制 (= 型上 broker_schedule/calendars 必須、 mode 引数を caller が触れない)
- [ ] `aggregate_session_blocks(mode=...)` 直接呼出は **test/debug 限定**、 production code path から grep + lint で除外確認:
  ```bash
  # production code path で aggregate_session_blocks(mode=...) 直接呼出は禁止
  grep -rn "aggregate_session_blocks(" src/ --include="*.py" | grep -v "aggregate_session_blocks_production"
  # 上記の検索結果が src/backtest/session_block.py 内部 (= wrapper の呼び元) のみであることを確認
  ```
- [ ] validate_calendar_coverage を caller が一回呼んだ後に aggregate_session_blocks_production を呼ぶ
- [ ] `tests/backtest/test_calendar.py` に **F49_production_callers_do_not_use_test_mode** テスト追加 (= production caller が wrapper を経由している grep 検証、 Round D2 test_id ギャップ反映)

### 9.6 PR description 用 collider bias 規範テンプレート (Round D1 [S5])

```markdown
## T072 collider bias 回避規範 (T071/T064/T066 詳細設計改訂申し送り)

T072 は session block の `holiday_markets` (= 観測情報) と `expected_bar_count`
(= broker 配信契約) を完全分離した。 下流 evaluator (T071 / T064 / T066) で
holiday_markets を消費する際は **以下を必ず遵守**:

### Fact (= T072 SSOT)
- broker schedule は `BrokerTradingSchedule.open_window_for_utc_date(d)` 駆動
- market holiday は `MarketHolidayCalendar` 観測のみ、 `expected_bar_count` には touch しない
- `bucket` (= 流動性時間帯) と `holiday_markets` (= 物理市場) は直交
- bucket="tokyo" でも Tokyo holiday なら他参加者の bar が存在する (= EUR/USD 等は他参加者)

### Interpretation (= 因果解釈時の規範)
- `holiday_markets` 単独で session_pass_pattern / SR 計算分母を drop / filter してはならない
- `holiday_markets` を condition variable (= conditioning set) として明示し、
  stratified audit (= holiday_markets 値別の集計) を実施する
- C3 collider bias を意識する: holiday は探索結果 (= 取引活性、 流動性) と相関するが、
  bucket と直接の因果関係はない。 「Tokyo holiday → Tokyo bucket は分母外」 のような
  短絡は collider conditioning bias を生む

### Conditioning set 明記例
- T071 SessionEntropyMetric: `n_archive_members` 計算時、
  `expected_bar_count > 0` の bucket を分母とする (= broker 配信ありを条件)。
  holiday_markets は audit log に出力し、 stratified report (= holiday 別 entropy) で参照可能に
- T064 stage_bc_evaluator: pooled_dd_per_fold_max 計算時、
  `schedule_status != "regular"` の block を pnl=0 で扱うか除外するかは fold 内
  block 構成に応じて decide。 holiday_markets は別軸 audit
- T066 cpps_archive: archive admission 時の session_pass_pattern 生成で
  `expected_bar_count > 0` を分母条件、 holiday_markets を stratified audit
```

## 10. Phase 1 / Phase 2 切り分け

### 10.1 Phase 1 (T072 PR)

§ 1.1 / § 1.2 全範囲。 単体テストのみで runtime 未組込 (= Phase 1 共通原則)。

### 10.2 Phase 2 (別 TODO、 cascade port 切替時)

§ 1.3 申し送り全項目。 主要:
- `aggregate_session_blocks` の broker_schedule / calendars 必須化 (= mode default を "production" に変更)
- T061 / T064 / T066 / T071 で SessionBlock T072 field 消費
- run_ga.py で broker_schedule / calendars を load + BacktestResult 経由で配線
- run report / archive で to_record(include_derived=True) export

### 10.3 同期 PR 候補 (Round 2 [W5] / Round 5 反映)

- synthesis Round 22 改訂: § 4.1 文言を「24/7 fill」 → 「24/5 + reopen/close partial」 に明文化 (= 本 PR と同期 merge or 先 merge)
- T064 詳細設計改訂: TradeRecord → Trade、 session_pass_pattern 3 bit 統一 (= T071 hard dependency と同時)
- T058 詳細設計改訂: applied_from_run_id v2 必須化 (= T069 申し送り)

## 11. 参考文献

- Andersen, T.G. & Bollerslev, T. (1998). *Deutsche Mark-Dollar Volatility: Intraday Activity Patterns, Macroeconomic Announcements, and Longer Run Dependencies.* Journal of Finance 53(1). (要確認、 intraday session boundary)
- Dacorogna, M. et al. (2001). *An Introduction to High-Frequency Finance.* Academic Press. (要確認、 FX 24h 取引)
- Müller, U.A. et al. (1990). *Statistical Study of Foreign Exchange Rates.* Journal of Banking & Finance 14. (要確認)
- Goodhart, C. & O'Hara, M. (1997). *High Frequency Data in Financial Markets.* Journal of Empirical Finance 4. (要確認)
- IANA Time Zone Database (= tzdata). https://www.iana.org/time-zones (= DST 一次資料)
- RFC 6557 (Procedures for Maintaining the Time Zone Database) / RFC 8536 (Time Zone Information Format)
- OANDA Developer Portal, *Instrument candle specification.* https://developer.oanda.com/rest-live-v20/instrument-ep/ (= broker schedule 一次資料、 詳細設計実装時に最新確認)
- JPX 公式 holiday list (= TSE 取引所 close 日)
- LSE 公式 holiday calendar / UK bank holidays (gov.uk)
- NYSE 公式 holiday calendar / Federal Reserve Bank holidays

---

これで T072 詳細設計は完成。 概念設計 Round 5 APPROVED 状態を起点に、 Round 5 [W1-W4] / [S1-S3] を本詳細設計で全反映。 Codex 詳細レビュー (gpt-5.3-codex / high) で最終確認。
