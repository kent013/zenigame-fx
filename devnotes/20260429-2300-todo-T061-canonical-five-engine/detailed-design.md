# 詳細設計: T061 — canonical 5 engine

## 使命・制約 (絶対遵守)

### zenigame-fx Alpha Factory 使命

live_criteria 全指標同時充足 + (ii-lite) 通過。 絶対制約: イントラデイ / ロング・ショート両方向 / スワップ・スプレッド反映。

### 禁止事項

1-7 (synthesis § 1.3)
8. archive スキーマ伝搬漏れ ← T058 対応済 (本 TODO は依存先)

### コーディングルール

- バグ修正テストファースト
- 全施策テスト必須、 振る舞いベース命名
- uv 必須、 ruff / mypy 通過、 Python 3.13

## 概念設計リファレンス

`devnotes/20260429-2300-todo-T061-canonical-five-engine/conceptual-design.md` (Round 3 で APPROVED)

## Round 3 review 反映 (Codex 概念レビュー)

| 概念 Round 3 [Warning/Suggestion] | 詳細設計での吸収 |
|---|---|
| [W1] `empty_trade_list` を `infeasible_reason_codes` に含めると synthesis § 6.6 の「戦略的 fail-fast 2 種」 と「入力不正」 境界が曖昧 | `infeasible_reason_codes` を 2 分類: `strategic_*` (synthesis § 6.6 由来) と `input_*` (engine 検出の入力不正)。 詳細 Round 1 [S1] 反映で `InfeasibleReasonCode` StrEnum 化、 prefix 規約を型で強制 |
| [W2] `gate_pass <=> gate_worst_gap == 0` の浮動小数誤差処理 | `GATE_PASS_TOLERANCE: Final[float] = 1e-9` を T061 内 const、 `gate_pass <=> gate_worst_gap <= GATE_PASS_TOLERANCE`。 1e-9 は denom_floor=1e-6 より十分小さく、 numerical noise 許容 |
| [S1] T064 側で `low_sample_buckets` 判定ポリシー先固定 | T064 詳細設計時に同一運用 (例: stage 全体 fail / strict eval skip) を確定。 T061 PR では engine 出力 `low_sample_buckets` を返すまでに留め、 T064 申し送り |
| [S2] provider のバージョン文字列を診断に残す | `CanonicalFiveResult.bucket_validator_version: str` field 追加 (default `"unvalidated"`、 provider 注入時は `provider.version` を記録) |
| [S3] config→StageGateConfig→evaluate_stage_*→result→archive/log の接続統合テスト | T064 PR 担当 (T061 PR では engine unit test のみ)、 申し送り明示 |

## 詳細 Round 1 review 反映 (Codex 詳細レビュー Round 2)

| Round 1 [Critical/Warning/Suggestion] | 修正対応 |
|---|---|
| [C1] WR neutral 0.5 が top-level 経路で無効 (compute_session_blocks が trade>=1 block しか生成しない) | `evaluate_canonical_five` の入力契約に `business_day_universe: dict[SessionBucket, frozenset[int]]` を追加。 T070 が「評価期間で発生し得た全 (bucket, business_day_index) ペア」 を渡し、 T061 は trade と join して **trade=0 でも空 block を生成** (trade_count_block=0, pnl_net_block=0.0)、 `compute_session_block_win_rate_worst` で 0.5 neutral 規約が適用される |
| [C2] top-level no-raise 契約が `_validate_utc_aware` 例外伝播で破れる | no-raise 契約の**境界**を明文化: TradeRecord/BarEquitySeries/CanonicalFiveThresholds の **dataclass 構築時 (`__post_init__`)** は raise する (caller 責務、 既存 frozen dataclass パターン)。 `evaluate_canonical_five` の no-raise 契約は **有効 instance 受領後の内部処理** のみ。 内部 (provider call / HAC 計算 / max_dd 等) の例外は catch して reason code に変換 |
| [C3] compute_max_dd の値域・ゼロ除算 | 仕様厳密化: `max_dd = max_t max(0, (running_max_t - equity_t) / max(running_max_t, MAX_DD_DENOM_FLOOR))` (MAX_DD_DENOM_FLOOR=1e-12 const)。 `running_max <= 0` の bar は drawdown 計算からスキップ (= 0 を加えない)、 全 bar で running_max <= 0 なら max_dd=1.0 (full drawdown sentinel、 invariant flag 経由で gate_pass=False になる)。 結果値域は `[0, 1]` に clip、 docstring + test 名に明記 (Round 1 [Suggestion] 3 反映) |
| [W1] 例外階層の一貫性 (`_validate_utc_aware` が基底例外を raise) | `_validate_utc_aware(name, dt, *, exc_class)` シグネチャに変更、 caller (TradeRecord/BarEquitySeries/CanonicalFiveThresholds の `__post_init__`) が派生例外クラスを指定する形に正規化 |
| [W2] 計算量説明が `O(N+B+3*Q)` で実装と乖離 | 正確化: `O(N + B + Σ_b n_b*Q)` (n_b = bucket b の block 数、 N=trade 数、 B=bar 数、 Q=Bartlett lag)。 fx 想定: N~5000, B~30,000, Σn_b ~ 250 × 3 = 750 → 1 評価 < 1ms 想定 (numpy 化不要) |
| [W3] DoD「Enum + 4 dataclass」 が実 dataclass 数と乖離 | 正確化: `Enum 1 + dataclass 7 (TradeRecord, BarEquityPoint, BarEquitySeries, SessionBlockSummary, CanonicalFiveThresholds, InvariantFlags, CanonicalFiveResult) + Provider protocol 1` |
| [W4] C2 grep が文字列経由動的参照を取りこぼす | T064 PR DoD に **runtime wiring smoke 1 本** (`evaluate_stage_*` を実際に呼んで `evaluate_canonical_five` が configured に走ることを確認する integration test) を追加申し送り |
| [W5] Newey-West 引用の粒度不足 | 学術引用節を full citation 形式に修正: `Newey, W. K., & West, K. D. (1987). "A Simple, Positive Semi-Definite, Heteroskedasticity and Autocorrelation Consistent Covariance Matrix." Econometrica, 55(3), 703-708.` |
| [S1] `infeasible_reason_codes` を StrEnum 化 | `InfeasibleReasonCode` StrEnum を新設、 `infeasible_reason_codes: frozenset[InfeasibleReasonCode]` として型で prefix 規約を強制 |
| [S2] provider 例外注入テスト追加 | テスト計画に `test_evaluate_canonical_five_provider_exception_converted_to_reason_code` 追加 |
| [S3] max_dd 値域明記 | docstring に「value range [0.0, 1.0]、 1.0=full drawdown sentinel」 を明記、 test 名に `_clipped_to_unit_interval` 含める |

## 施策一覧 (Phase 1: T061 PR、 Phase 2 は別 PR)

| # | 施策名 | 変更ファイル | 優先度 |
|---|--------|------------|--------|
| 1 | `canonical_metrics.py` 新規 (Enum + 5 dataclass + helper 群 + top-level entry + 例外) | `src/alpha_factory/canonical_metrics.py` (新規) | Critical |
| 2 | `tests/alpha_factory/test_canonical_metrics.py` 新規 (単体テスト) | (新規) | Critical |

**Phase 1 (T061 PR) スコープ = 上記 2 施策**。 既存 `stage_gate.py` / `swim_lane.py` / `archive.py` / `cross_pair.py` / `config.py` / `default.yaml` への組込は **Phase 2 (別 PR、 T063-T064 と同時)** で実施。 T061 PR 単独 merge で runtime に影響なし。

---

## 施策 1: `canonical_metrics.py` 新規作成

### 変更箇所

- ファイル: `src/alpha_factory/canonical_metrics.py` (新規)

### 波及変更

- `AGENTS.md`: なし (内部 module、 T061 PR では runtime 未組込)
- `.claude/skills/zenigame-fx-{skill}/SKILL.md`: なし
- `config/alpha_factory/default.yaml`: なし (Phase 2 で `live_criteria.win_rate_min: 0.45` 追加 + 旧 stage_a/b/c 全廃)
- `docs/alpha_factory/*.md`: なし (Phase 2 で stage-gates.md 更新)

### 変更後コード

```python
"""T061: canonical 5 engine — synthesis § 6 数式仕様の単一実装.

詳細:
- 概念設計: devnotes/20260429-2300-todo-T061-canonical-five-engine/conceptual-design.md
- synthesis § 6 (canonical 5 + Pareto 3 数式仕様)、 § 17 (用語)
- T060 依存: PeriodLabel / Period 同規約 (UTC 厳密、 frozen dataclass)

Phase 1 (本 TODO): 単体実装 + テストのみ、 stage_gate.py / swim_lane.py 未変更。
Phase 2 (別 PR): T063 (Stage A evaluator) / T064 (Stage B/C-lite/C evaluator) と同時、
9 箇所同時更新 (Phase 2 申し送り参照)。
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Final, Iterable

__all__ = [
    # Enums
    "SessionBucket",
    "InfeasibleReasonCode",
    # DataClasses
    "TradeRecord",
    "BarEquityPoint",
    "BarEquitySeries",
    "SessionBlockSummary",
    "CanonicalFiveThresholds",
    "InvariantFlags",
    "CanonicalFiveResult",
    # Constants
    "DENOM_FLOOR",
    "N_BLOCKS_PER_YEAR",
    "GATE_PASS_TOLERANCE",
    "HAC_BARTLETT_DEFAULT_Q",
    "SIGMA2_LR_EPS",
    "MAX_DD_DENOM_FLOOR",
    "LOG_PF_CLIP_RANGE",
    "LOG_PF_SMOOTH",
    "LOW_SAMPLE_BLOCK_THRESHOLD",
    # Provider protocol
    "SessionBucketBoundaryProvider",
    # Top-level entry
    "evaluate_canonical_five",
    # Helpers
    "compute_session_blocks",
    "compute_sr_session_worst",
    "compute_session_block_win_rate_worst",
    "compute_max_dd",
    "compute_signed_slacks",
    "slack_to_range",
    "log_pf_clip",
    # Exceptions
    "CanonicalMetricsInputError",
    "BarEquityInvalidError",
    "TradeRecordInvalidError",
    "ThresholdsInvalidError",
]


# ---------------------------------------------------------------------------
# Constants (synthesis § 6 厳密準拠)
# ---------------------------------------------------------------------------

DENOM_FLOOR: Final[float] = 1e-6
"""synthesis § 6.1 確定値。 5 指標 signed slack の denom floor 共通値."""

N_BLOCKS_PER_YEAR: Final[int] = 756
"""252 営業日 × 3 session bucket。 SR block-scale → annual-scale 換算用 const.

T072 (DST/holiday) 確定後、 holiday 補正で `n_blocks_observed` 実測ベースに切替する場合は
本 const を関数引数化 (T072 申し送り)。
"""

GATE_PASS_TOLERANCE: Final[float] = 1e-9
"""concept Round 3 [W2] 反映: 浮動小数誤差許容、 gate_pass <=> gate_worst_gap <= 1e-9.
denom_floor=1e-6 より十分小さい桁。
"""

HAC_BARTLETT_DEFAULT_Q: Final[int] = 5
"""synthesis § 6.2 確定値。 Bartlett kernel lag (1 週間相当)."""

SIGMA2_LR_EPS: Final[float] = 1e-12
"""HAC long-run variance の floor (zero-variance 系列保護).
concept Round 1 [C3] 反映: hard fail を入れず eps floor で対応."""

MAX_DD_DENOM_FLOOR: Final[float] = 1e-12
"""max_dd 計算時の running_max 分母 floor (detail Round 1 [C3] 反映).
running_max <= 0 の bar は drawdown 計算からスキップ、 全 bar negative なら max_dd=1.0 (full drawdown sentinel)."""

LOG_PF_CLIP_RANGE: Final[tuple[float, float]] = (-2.0, 2.0)
"""synthesis § 6.4 確定値。 archive lex 末端 tie-break 用."""

LOG_PF_SMOOTH: Final[float] = 1e-6
"""log_pf_clip の smoothing constant: log((GP+ε)/(GL+ε))."""

LOW_SAMPLE_BLOCK_THRESHOLD: Final[int] = 30
"""concept Round 1 [C3] 反映: bucket 内 block 数 < 30 を low_sample で診断出力 (hard fail なし)."""


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class SessionBucket(StrEnum):
    """8h × 3 bucket 固定 (synthesis § 5 / § 17 確定、 6 bucket 不採用).

    boundary は T070 backtest engine / T072 DST contract が確定。
    T061 はラベル済 TradeRecord を consume するのみ。
    """

    TOKYO = "tokyo"
    LONDON = "london"
    NY = "ny"


class InfeasibleReasonCode(StrEnum):
    """infeasible_reason_codes の prefix 規約を型で強制 (detail Round 1 [S1] 反映).

    `strategic_*` prefix: synthesis § 6.6 由来の戦略的 fail-fast 2 種
    `input_*` prefix: engine 検出の入力不正 (provider 例外含む)
    """

    # synthesis § 6.6 戦略的 fail-fast (TradeRecord フラグ集計由来)
    STRATEGIC_SESSION_CLOSE_DROP = "strategic_session_close_drop"
    STRATEGIC_NEGATIVE_EQUITY_DROP_OPEN = "strategic_negative_equity_drop_open"
    # engine 検出の入力不正
    INPUT_INVALID_BAR_SERIES = "input_invalid_bar_series"
    INPUT_BUCKET_ATTRIBUTION_MISMATCH = "input_bucket_attribution_mismatch"
    INPUT_BUCKET_VALIDATOR_EXCEPTION = "input_bucket_validator_exception"
    INPUT_EMPTY_TRADE_LIST = "input_empty_trade_list"
    INPUT_EMPTY_BUSINESS_DAY_UNIVERSE = "input_empty_business_day_universe"
    INPUT_BUSINESS_DAY_UNIVERSE_MISMATCH = "input_business_day_universe_mismatch"
    INPUT_NON_FINITE_PNL = "input_non_finite_pnl"


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class CanonicalMetricsInputError(ValueError):
    """canonical_metrics 入力 dataclass の不変条件違反 (基底クラス).

    本基底例外を直接 raise しない (detail Round 1 [W1] 反映、 例外階層の一貫性)。
    `__post_init__` では必ず派生例外 (TradeRecordInvalidError / BarEquityInvalidError /
    ThresholdsInvalidError) を raise する。
    """


class TradeRecordInvalidError(CanonicalMetricsInputError):
    """TradeRecord __post_init__ 不変条件違反."""


class BarEquityInvalidError(CanonicalMetricsInputError):
    """BarEquitySeries __post_init__ 不変条件違反 (sorted/no-dup/UTC-aware/finite)."""


class ThresholdsInvalidError(CanonicalMetricsInputError):
    """CanonicalFiveThresholds __post_init__ 不変条件違反."""


# ---------------------------------------------------------------------------
# Provider protocol (concept Round 1 [W1] / Round 3 [S2] 反映)
# ---------------------------------------------------------------------------


class SessionBucketBoundaryProvider:
    """T072 で実装する session bucket boundary 契約 (T061 では interface のみ).

    T064 統合時に provider を `_validate_trade_attribution` に注入して、
    TradeRecord.session_bucket / business_day_index が boundary 契約に整合するか double-check する.

    本 module では Protocol-like base class で signature のみ定義。 T072 で具体実装する.
    """

    @property
    def version(self) -> str:
        """provider 識別子 (例: 'session_bucket_boundary_v1'). 監査ログに残す."""
        raise NotImplementedError

    def expected_bucket(self, exit_time_utc: datetime) -> SessionBucket:
        """exit_time_utc が属する正規 bucket. T064 で TradeRecord.session_bucket と比較."""
        raise NotImplementedError

    def expected_business_day_index(self, exit_time_utc: datetime) -> int:
        """exit_time_utc が属する business day index. T064 で TradeRecord.business_day_index と比較."""
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Input DataClasses
# ---------------------------------------------------------------------------


def _validate_utc_aware(
    name: str,
    dt: datetime,
    *,
    exc_class: type[CanonicalMetricsInputError],
) -> None:
    """UTC-aware + utcoffset()==0 厳密 (T060 Period 同規約).

    detail Round 1 [W1] 反映: caller が派生例外クラス (TradeRecordInvalidError /
    BarEquityInvalidError / ThresholdsInvalidError) を指定し、 例外階層の一貫性を保つ.
    """
    if dt.tzinfo is None:
        raise exc_class(
            f"{name} must be timezone-aware datetime, got naive: {dt!r}"
        )
    offset = dt.utcoffset()
    if offset is None or offset != timedelta(0):
        raise exc_class(
            f"{name} must be UTC (utcoffset=0), got offset={offset}: {dt!r}"
        )


@dataclass(frozen=True)
class TradeRecord:
    """1 trade (intraday close-out 前提).

    invariant (`__post_init__` で fail-fast):
    - entry_time_utc / exit_time_utc は UTC-aware + utcoffset()==0
    - entry_time_utc < exit_time_utc
    - pnl_net は finite (NaN/Inf なら raise → caller 側で input_non_finite_pnl reason に変換)
    - business_day_index >= 0

    session_bucket / business_day_index の T070 整合性は `_validate_trade_attribution(provider)`
    で別経路 double-check (concept Round 1 [W1] 反映).
    """

    entry_time_utc: datetime
    exit_time_utc: datetime
    pnl_net: float
    session_bucket: SessionBucket
    business_day_index: int
    is_session_close_drop: bool
    is_negative_equity_drop_open: bool

    def __post_init__(self) -> None:
        _validate_utc_aware(
            "TradeRecord.entry_time_utc", self.entry_time_utc, exc_class=TradeRecordInvalidError
        )
        _validate_utc_aware(
            "TradeRecord.exit_time_utc", self.exit_time_utc, exc_class=TradeRecordInvalidError
        )
        if self.exit_time_utc <= self.entry_time_utc:
            raise TradeRecordInvalidError(
                f"TradeRecord.exit_time_utc ({self.exit_time_utc}) "
                f"must be > entry_time_utc ({self.entry_time_utc})"
            )
        if self.business_day_index < 0:
            raise TradeRecordInvalidError(
                f"TradeRecord.business_day_index must be >= 0: {self.business_day_index}"
            )
        if not math.isfinite(self.pnl_net):
            raise TradeRecordInvalidError(
                f"TradeRecord.pnl_net must be finite: {self.pnl_net}"
            )


@dataclass(frozen=True)
class BarEquityPoint:
    """1 bar の equity (max_dd 計算用、 BarEquitySeries 内部要素)."""

    timestamp_utc: datetime
    equity: float


@dataclass(frozen=True)
class BarEquitySeries:
    """max_dd 計算 input contract.

    invariant (`__post_init__` で fail-fast、 concept Round 1 [W2] 反映):
    - len(points) >= 1
    - 全 timestamp_utc が UTC-aware + utcoffset==0
    - timestamps strict monotone increasing (sorted + 重複なし)
    - 全 equity が finite (NaN/Inf 検出時は BarEquityInvalidError)
    """

    points: tuple[BarEquityPoint, ...]

    def __post_init__(self) -> None:
        if len(self.points) < 1:
            raise BarEquityInvalidError("BarEquitySeries.points must have len >= 1")
        prev_ts: datetime | None = None
        for i, p in enumerate(self.points):
            _validate_utc_aware(
                f"BarEquitySeries.points[{i}].timestamp_utc",
                p.timestamp_utc,
                exc_class=BarEquityInvalidError,
            )
            if not math.isfinite(p.equity):
                raise BarEquityInvalidError(
                    f"BarEquitySeries.points[{i}].equity must be finite: {p.equity}"
                )
            if prev_ts is not None and p.timestamp_utc <= prev_ts:
                raise BarEquityInvalidError(
                    f"BarEquitySeries.points must be strictly monotone increasing: "
                    f"index {i}: {p.timestamp_utc} <= prev {prev_ts}"
                )
            prev_ts = p.timestamp_utc


@dataclass(frozen=True)
class SessionBlockSummary:
    """(business_day_index, session_bucket) 単位の集約結果 (内部 use)."""

    business_day_index: int
    session_bucket: SessionBucket
    pnl_net_block: float
    trade_count_block: int


@dataclass(frozen=True)
class CanonicalFiveThresholds:
    """live_criteria + supplementary thresholds (T061 入力契約).

    field:
    - sharpe_min: annual Sharpe 下限 (例 1.0、 live_criteria.sharpe_min)
    - net_pnl_min: 期間内合計 PnL 下限 (例 50000、 live_criteria.total_pnl_min)
    - max_dd_max: 最大 DD 上限 (例 0.20 ratio、 live_criteria.max_drawdown_max)
    - trade_count_min, trade_count_max: trade_count [L, U] range
        (例 [50, 5000]、 live_criteria.trade_count_min/max)
    - win_rate_min: session_block_win_rate_worst の最低許容 (例 0.45、
        live_criteria.win_rate_min を Phase 2 で追加)

    invariant (`__post_init__` で fail-fast):
    - 全 field finite
    - sharpe_min, net_pnl_min, max_dd_max, win_rate_min > 0
    - 0 < trade_count_min <= trade_count_max
    - 0 < win_rate_min < 1
    - 0 < max_dd_max < 1
    """

    sharpe_min: float
    net_pnl_min: float
    max_dd_max: float
    trade_count_min: int
    trade_count_max: int
    win_rate_min: float

    def __post_init__(self) -> None:
        for name, value in (
            ("sharpe_min", self.sharpe_min),
            ("net_pnl_min", self.net_pnl_min),
            ("max_dd_max", self.max_dd_max),
            ("win_rate_min", self.win_rate_min),
        ):
            if not math.isfinite(value):
                raise ThresholdsInvalidError(
                    f"CanonicalFiveThresholds.{name} must be finite: {value}"
                )
            if value <= 0.0:
                raise ThresholdsInvalidError(
                    f"CanonicalFiveThresholds.{name} must be > 0: {value}"
                )
        if not (0 < self.trade_count_min <= self.trade_count_max):
            raise ThresholdsInvalidError(
                f"CanonicalFiveThresholds: 0 < trade_count_min ({self.trade_count_min}) "
                f"<= trade_count_max ({self.trade_count_max})"
            )
        if not (0.0 < self.win_rate_min < 1.0):
            raise ThresholdsInvalidError(
                f"CanonicalFiveThresholds.win_rate_min must be in (0, 1): {self.win_rate_min}"
            )
        if not (0.0 < self.max_dd_max < 1.0):
            raise ThresholdsInvalidError(
                f"CanonicalFiveThresholds.max_dd_max must be in (0, 1): {self.max_dd_max}"
            )


# ---------------------------------------------------------------------------
# Output DataClasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class InvariantFlags:
    """fail-fast 用 flag (synthesis § 6.6 + concept Round 3 [W1] 分類強化).

    `infeasible_reason_codes` は 2 分類 prefix で区別:
    - `strategic_*`: synthesis § 6.6 由来の戦略的 fail-fast 2 種
        - "strategic_session_close_drop" (session_close_drop_count > 0)
        - "strategic_negative_equity_drop_open" (negative_equity_drop_open_count > 0)
    - `input_*`: engine 検出の入力不正
        - "input_invalid_bar_series" (BarEquitySeries 不変条件違反)
        - "input_bucket_attribution_mismatch" (provider double-check 失敗)
        - "input_empty_trade_list" (trades 空)
        - "input_non_finite_pnl" (TradeRecord.pnl_net NaN/Inf)
    """

    session_close_drop_count: int
    negative_equity_drop_open_count: int
    infeasible_reason_codes: frozenset[InfeasibleReasonCode]

    @property
    def is_feasible(self) -> bool:
        """全 invariant が違反なし."""
        return (
            self.session_close_drop_count == 0
            and self.negative_equity_drop_open_count == 0
            and len(self.infeasible_reason_codes) == 0
        )


@dataclass(frozen=True)
class CanonicalFiveResult:
    """canonical 5 worst aggregation の結果 (T061 出力契約).

    raw values (block-scale → annual-scale 換算後):
        sr_session_worst_block_scale: 3 bucket SR block-scale の min (HAC Bartlett q=5)
        sr_session_worst_annual_estimate: block-scale を sqrt(N_BLOCKS_PER_YEAR) 倍した推定値
        net_pnl_after_cost: 期間内合計 net PnL
        max_dd: 最大 DD (>=0、 ratio スケール)
        trade_count: 期間内 trade 数
        session_block_win_rate_worst: 3 bucket WR の min

    per-bucket diagnostics (T071 observability で消費):
        per_bucket_sr: {SessionBucket: SR block-scale}
        per_bucket_wr: {SessionBucket: WR}
        low_sample_buckets: block 数 < 30 の bucket 集合 (concept Round 1 [C3] 反映)

    signed slack (synthesis § 6.1 厳密、 全 denom_floor=1e-6):
        slack_sharpe, slack_pnl, slack_dd, slack_tc, slack_wr

    集約 (synthesis § 6.4):
        gate_worst_gap = max_m max(0, -slack_m)
        gate_pass = (gate_worst_gap <= GATE_PASS_TOLERANCE) AND invariants.is_feasible

    auxiliary (synthesis § 6.4 / § 6.7):
        log_pf_clip: archive 末端 tie-break (-2 to 2)
        bucket_validator_version: provider double-check 時の version 文字列 (Round 3 [S2])
            default "unvalidated" (provider=None で skip 時)
        invariants: InvariantFlags
    """

    # raw metrics
    sr_session_worst_block_scale: float
    sr_session_worst_annual_estimate: float
    net_pnl_after_cost: float
    max_dd: float
    trade_count: int
    session_block_win_rate_worst: float
    # per-bucket diagnostics
    per_bucket_sr: dict[SessionBucket, float]
    per_bucket_wr: dict[SessionBucket, float]
    low_sample_buckets: frozenset[SessionBucket]
    # signed slack
    slack_sharpe: float
    slack_pnl: float
    slack_dd: float
    slack_tc: float
    slack_wr: float
    # aggregate
    gate_worst_gap: float
    gate_pass: bool
    # auxiliary
    log_pf_clip: float
    bucket_validator_version: str
    invariants: InvariantFlags


# ---------------------------------------------------------------------------
# Helpers (pure functions)
# ---------------------------------------------------------------------------


def compute_session_blocks(
    trades: Iterable[TradeRecord],
    business_day_universe: dict[SessionBucket, frozenset[int]],
) -> dict[SessionBucket, list[SessionBlockSummary]]:
    """trade-level PnL を (business_day_index, session_bucket) 単位の block に集約.

    detail Round 1 [C1] 反映: WR neutral 0.5 規約 (synthesis § 6.3) を本流で有効化するため、
    `business_day_universe` を入力に取り、 trade=0 でも空 block (trade_count_block=0,
    pnl_net_block=0.0) を生成する。 T070 backtest engine が「評価期間で発生し得た全
    (bucket, business_day_index) ペア」 を business_day_universe として渡す責務を持つ.

    attribution rule = exit_time_utc (concept § 重要な設計判断 1):
    すべての trade は exit_time_utc 時点の session_bucket / business_day_index に attribute される
    (T070 が確定済の TradeRecord field を信頼).

    手順:
    1. business_day_universe[bucket] = frozenset[business_day_index] で full grid を初期化
       (各 (bucket, day) ペアで pnl=0.0, count=0 の空 block を生成)
    2. trades を走査し、 (trade.session_bucket, trade.business_day_index) の block に
       pnl_net を加算、 count を +1
    3. trade.business_day_index が business_day_universe[trade.session_bucket] に含まれない
       場合: **fail-fast** (detail Round 2 [W1] 反映、 T070/T072 期間境界不整合の隠蔽防止)。
       本関数は raise せず `dict[SessionBucket, list[SessionBlockSummary]]` を返す契約のため、
       `evaluate_canonical_five` 側で `INPUT_BUSINESS_DAY_UNIVERSE_MISMATCH` reason を立てて
       gate_pass=False に変換する (例外伝播せず deterministic 戻り値を保証)
    4. 各 bucket 内を business_day_index 昇順でソート

    Args:
        trades: TradeRecord iterable
        business_day_universe: {SessionBucket: frozenset[business_day_index]}
            T070 が evaluation period に含まれる全 (bucket, day) ペアを列挙

    Returns:
        {SessionBucket: [SessionBlockSummary, ...]} (各 bucket 内 list は business_day_index 昇順)
    """


def compute_sr_session_worst(
    blocks_by_bucket: dict[SessionBucket, list[SessionBlockSummary]],
    q: int = HAC_BARTLETT_DEFAULT_Q,
    eps: float = SIGMA2_LR_EPS,
) -> tuple[float, dict[SessionBucket, float], frozenset[SessionBucket]]:
    """3 bucket の HAC 補正 SR を計算し、 block-scale worst (= min) を返す.

    Bartlett kernel (Newey-West 1987):
        gamma_b(k) = lag-k autocovariance (population formula、 mean-centered series 上)
        sigma2_LR_b = gamma_b(0) + 2 * sum_{k=1..q}((1 - k/(q+1)) * gamma_b(k))
        SR_b = mu_b / sqrt(max(sigma2_LR_b, eps))

    ガード:
    - bucket が dict に欠損 or block 数 == 0 → SR_b = -inf (worst-case fallback、
      gate_worst_gap で fail させる経路、 hard fail はしない)
    - block 数 < LOW_SAMPLE_BLOCK_THRESHOLD (=30) の bucket は low_sample_buckets に追加
    - block 数 == 1 → SR_b = -inf (variance 計算不可)

    Returns:
        (sr_worst_block, per_bucket_sr_block, low_sample_buckets)
    """


def compute_session_block_win_rate_worst(
    blocks_by_bucket: dict[SessionBucket, list[SessionBlockSummary]],
) -> tuple[float, dict[SessionBucket, float]]:
    """3 bucket WR worst (synthesis § 6.3、 trade=0 block は 0.5 neutral).

    各 block で:
        if trade_count_block > 0:
            win_{b,t} = 1.0 if pnl_net_block > 0 else 0.0
        else:
            win_{b,t} = 0.5

    WR_b = mean(win_{b,t})
    bucket 内 block 数 == 0 → WR_b = 0.0 (worst-case fallback、 gate_worst_gap で fail)

    Returns: (wr_worst, per_bucket_wr)
    """


def compute_max_dd(bars: BarEquitySeries) -> float:
    """equity series 上の max drawdown を比率で返す.

    値域 (detail Round 1 [C3] / [S3] 反映): **[0.0, 1.0] に clip**。
    1.0 は full drawdown sentinel (全 bar で running_max <= 0 の異常系で割当)。

    手順:
    1. 各 bar を時系列順に走査、 running_max = max(running_max, equity_t) を更新
    2. running_max <= 0 の bar は drawdown 計算からスキップ (= 寄与 0、 detail Round 1 [C3])
    3. running_max > 0 の bar:
        bar_dd = max(0, (running_max - equity_t)) / max(running_max, MAX_DD_DENOM_FLOOR)
    4. max_dd = max_t bar_dd
    5. 全 bar が running_max <= 0 (有効寄与なし) なら max_dd = 1.0
    6. final clip: min(1.0, max(0.0, max_dd))

    Note: equity が一時的に負値でも数学的に成立。 negative_equity_drop_open は invariant flag
    で別経路、 max_dd 計算は補助的にしか使われない (gate_pass=False が確定する).
    """


def slack_to_range(value: float, lower: float, upper: float) -> float:
    """trade_count [L, U] range の signed numerator を返す (denom 化は呼出側).

    sign convention:
        value < lower:                return value - lower    (負値、 不足)
        lower <= value <= upper:      return min((value - lower), (upper - value))  (正値、 中央余裕最大、 境界 0)
        value > upper:                return upper - value    (負値、 超過)

    Note: synthesis § 6.1 の `slack_tc = slack_to_range(tc, [TC_min, TC_max]) / max(TC_min, 1e-6)`
    に従い、 caller (compute_signed_slacks) が `/ max(|TC_min|, DENOM_FLOOR)` で正規化.
    """


def log_pf_clip(gross_profit: float, gross_loss: float) -> float:
    """log Profit Factor を [-2, 2] に clip (synthesis § 6.4 厳密).

    GP = sum(positive trade pnl_net)、 GL = sum(|negative trade pnl_net|)
    log_pf = log((GP + LOG_PF_SMOOTH) / (GL + LOG_PF_SMOOTH))
    return clip(log_pf, -2, 2)
    """


def compute_signed_slacks(
    sr_worst_block_scale: float,
    net_pnl_after_cost: float,
    max_dd: float,
    trade_count: int,
    session_block_win_rate_worst: float,
    thresholds: CanonicalFiveThresholds,
) -> dict[str, float]:
    """5 指標の signed slack を計算 (synthesis § 6.1 厳密).

    SR annual 換算は本関数内で完結 (concept Round 1 [C2] 反映、 責務単一化):
        sharpe_ann_estimate = sr_worst_block_scale * sqrt(N_BLOCKS_PER_YEAR)

    全 denom_floor = DENOM_FLOOR (=1e-6)。

    Returns:
        {
            "sharpe": (sharpe_ann_estimate - sharpe_min) / max(|sharpe_min|, DENOM_FLOOR),
            "pnl":    (net_pnl_after_cost - net_pnl_min) / max(|net_pnl_min|, DENOM_FLOOR),
            "dd":     (max_dd_max - max_dd) / max(max_dd_max, DENOM_FLOOR),
            "tc":     slack_to_range(trade_count, [tc_min, tc_max]) / max(|tc_min|, DENOM_FLOOR),
            "wr":     (wr_worst - win_rate_min) / max(win_rate_min, DENOM_FLOOR),
        }

    sr_worst_block_scale = -inf 等の非有限値受領時は slack_sharpe = -inf を返す (fail propagation).
    """


def _validate_trade_attribution(
    trades: Iterable[TradeRecord],
    provider: SessionBucketBoundaryProvider | None,
) -> tuple[bool, str]:
    """provider 注入時に T070 の bucket / business_day attribution を double-check.

    provider=None なら skip 戻り値 (True, "unvalidated") (concept Round 3 [S2] 反映).
    provider!=None なら全 trade を検証、 1 件でも mismatch があれば (False, provider.version).
    """


# ---------------------------------------------------------------------------
# Top-level entry
# ---------------------------------------------------------------------------


def evaluate_canonical_five(
    trades: Iterable[TradeRecord],
    bars: BarEquitySeries,
    thresholds: CanonicalFiveThresholds,
    business_day_universe: dict[SessionBucket, frozenset[int]],
    *,
    bucket_validator: SessionBucketBoundaryProvider | None = None,
    q_bartlett: int = HAC_BARTLETT_DEFAULT_Q,
) -> CanonicalFiveResult:
    """canonical 5 engine top-level entry.

    no-raise 契約の境界 (detail Round 1 [C2] / Round 2 [W2] 反映):
    - **「有効 instance」 = `__post_init__` を例外なく通過した frozen dataclass instance**
      (TradeRecord / BarEquityPoint / BarEquitySeries / SessionBlockSummary /
      CanonicalFiveThresholds 全て同様)。 caller は dataclass 構築時に raise を捕捉する責務を負う。
    - 本関数の no-raise 契約は **有効 instance 受領後の内部処理** のみ。 内部 helper
      (provider call / HAC 計算 / max_dd / signed slack 計算 / business_day_universe mismatch 検出)
      の例外は catch して InfeasibleReasonCode に変換、 deterministic な戻り値を保証。

    例外 → InfeasibleReasonCode 変換マップ (catch 境界):
    - `BarEquityInvalidError` (compute_max_dd 内で再 raise されることはないが念のため):
        → `INPUT_INVALID_BAR_SERIES`
    - `bucket_validator.expected_*()` 例外:
        → `INPUT_BUCKET_VALIDATOR_EXCEPTION` (validator 自体の bug 等)
    - `bucket_validator` mismatch (return False):
        → `INPUT_BUCKET_ATTRIBUTION_MISMATCH`
    - `len(trades) == 0`:
        → `INPUT_EMPTY_TRADE_LIST`
    - `business_day_universe` の任意 bucket key で空集合:
        → `INPUT_EMPTY_BUSINESS_DAY_UNIVERSE` (T070 入力契約違反)
    - `compute_session_blocks` 内で trade.business_day_index が universe に未登録:
        → `INPUT_BUSINESS_DAY_UNIVERSE_MISMATCH` (T070/T072 期間境界不整合の隠蔽防止、 detail Round 2 [W1] 反映)

    手順:
    1. trades を materialize、 空の場合は `INPUT_EMPTY_TRADE_LIST` reason を立てる
    2. business_day_universe の各 bucket が空集合なら `INPUT_EMPTY_BUSINESS_DAY_UNIVERSE` reason
    3. _validate_trade_attribution(trades, bucket_validator) で T070 整合性 double-check
       例外時は `INPUT_BUCKET_VALIDATOR_EXCEPTION`、 mismatch 時は `INPUT_BUCKET_ATTRIBUTION_MISMATCH`
       (validator_version は provider.version 又は "unvalidated")
    4. compute_session_blocks(trades, business_day_universe) → blocks_by_bucket (空 block 含む)
    5. compute_sr_session_worst(blocks_by_bucket, q=q_bartlett, eps=SIGMA2_LR_EPS)
        → SR block-scale + per_bucket_sr + low_sample_buckets
    6. compute_session_block_win_rate_worst(blocks_by_bucket) → WR_worst + per_bucket_wr
    7. compute_max_dd(bars) → max_dd (値域 [0, 1])
    8. net_pnl_after_cost = sum(t.pnl_net for t in trades)
    9. trade_count = len(trades)
    10. GP = sum(t.pnl_net for t in trades if t.pnl_net > 0), GL = sum(|t.pnl_net|...)
        log_pf = log_pf_clip(GP, GL)
    11. compute_signed_slacks(...) → 5 signed slack (annual-scale 換算済)
    12. gate_worst_gap = max(0, max_m (-slack_m for m in [sharpe, pnl, dd, tc, wr]))
    13. invariants = InvariantFlags(
            session_close_drop_count=count(t.is_session_close_drop),
            negative_equity_drop_open_count=count(t.is_negative_equity_drop_open),
            infeasible_reason_codes=collected_codes,
        )
        # session_close_drop_count > 0 → STRATEGIC_SESSION_CLOSE_DROP も infeasible_reason_codes に追加
        # negative_equity_drop_open_count > 0 → STRATEGIC_NEGATIVE_EQUITY_DROP_OPEN 同様
    14. gate_pass = (gate_worst_gap <= GATE_PASS_TOLERANCE) AND invariants.is_feasible
    15. CanonicalFiveResult を frozen で返す

    Args:
        trades: TradeRecord iterable (T070 が session_bucket / business_day_index 確定済)
        bars: BarEquitySeries (max_dd 計算用、 構築時に sorted/no-dup/UTC-aware/finite 検証済)
        thresholds: CanonicalFiveThresholds (live_criteria + win_rate_min、 構築時検証済)
        business_day_universe: T070 が確定する {SessionBucket: frozenset[business_day_index]}
            (synthesis § 6.3 の trade=0 block neutral 0.5 を有効化するため必須、 detail Round 1 [C1])
        bucket_validator: T072 で実装する provider、 None なら attribution check skip
        q_bartlett: HAC Bartlett lag (default 5、 synthesis 確定値)

    Returns:
        CanonicalFiveResult (全 field 必須、 frozen)

    Raises:
        該当なし (有効 instance 受領後の内部処理は no-raise)。
    """
```

### ルックアヘッドバイアスチェック

- N/A (T061 は既知の trade list を集計するのみで、 strategy 評価 / lookback 操作なし)
- ただし synthesis § 2 原則 0 に従い、 caller 側 (T064 stage 評価器) が embargo 1w 後の period のみを T061 に渡すこと。 T061 内では embargo を扱わない (T060 Period の責務)

### C3 / C7 適用

- **C3**: 該当なし (相関分析を新規導入しない)
- **C7**: HAC q=5 lag 推定で sample n が小さいと sigma2_LR が不安定 → eps=1e-12 floor + low_sample_buckets 診断出力。 hard fail なし (concept Round 1 [C3] 反映)

### パフォーマンスチェック (detail Round 1 [W2] 反映、 計算量正確化)

- 計算量: **O(N + B + Σ_b n_b * Q)** (N=trade 数、 B=bar 数、 Σn_b=block 総数、 Q=Bartlett lag)
- fx 想定値: N ~ 5000 trades / 評価、 B ~ 30,000 bars / 評価、 Σn_b ~ 250 business_days × 3 buckets = 750 blocks / 評価、 Q=5
- 1 評価当り ~0.5ms 想定 (Python dict + math、 numpy 不要)
- pop=192 × gen=64 × eval/Run = 12,288 評価/Run、 全 RUN ~ 6 sec (CPU 1 core)。 並列 4 worker で ~1.5 sec
- ボトルネック: (1) compute_session_blocks の groupby (O(N + Σn_b))、 (2) compute_sr_session_worst の autocovariance ループ (O(Σn_b * Q))
- numpy 化検討は T070 backtest engine 連携時に再評価。 本 PR は dict + math.fsum で OK

### テスト計画 (施策 2 で詳述)

### リスク

- T060 未マージ時は問題なし (T060 と独立、 import 関係なし)
- T058 / T059 未マージでも独立して merge 可能 (本 module は datetime/dataclass/math のみに依存)
- 既存 stage_gate.py / swim_lane.py に touch しないため Phase 1 単体では runtime に影響なし

---

## 施策 2: `tests/alpha_factory/test_canonical_metrics.py` 新規作成

### 変更箇所

- ファイル: `tests/alpha_factory/test_canonical_metrics.py` (新規)

### テスト計画

振る舞いベース test 名 (synthesis § 6 数式の数値確認 + invariant fail-fast):

#### Constants
- `test_denom_floor_is_synthesis_strict_value`
- `test_n_blocks_per_year_is_756`
- `test_gate_pass_tolerance_is_smaller_than_denom_floor`

#### SessionBucket
- `test_session_bucket_has_three_values_tokyo_london_ny`
- `test_session_bucket_str_values_are_lowercase`

#### TradeRecord
- `test_trade_record_rejects_naive_datetime_for_entry_or_exit`
- `test_trade_record_rejects_jst_aware_datetime`
- `test_trade_record_rejects_exit_le_entry`
- `test_trade_record_rejects_negative_business_day_index`
- `test_trade_record_rejects_non_finite_pnl_net`
- `test_trade_record_accepts_valid_utc_record`

#### BarEquityPoint / BarEquitySeries
- `test_bar_equity_series_rejects_empty_points`
- `test_bar_equity_series_rejects_non_utc_aware_timestamps`
- `test_bar_equity_series_rejects_jst_aware_timestamps`
- `test_bar_equity_series_rejects_non_monotonic_timestamps`
- `test_bar_equity_series_rejects_duplicate_timestamps`
- `test_bar_equity_series_rejects_non_finite_equity`
- `test_bar_equity_series_accepts_valid_strict_monotone_utc`

#### CanonicalFiveThresholds
- `test_thresholds_rejects_zero_or_negative_sharpe_min`
- `test_thresholds_rejects_max_dd_max_outside_unit_interval`
- `test_thresholds_rejects_win_rate_min_outside_unit_interval`
- `test_thresholds_rejects_inverted_trade_count_range`
- `test_thresholds_accepts_canonical_live_criteria_values`

#### compute_session_blocks
- `test_compute_session_blocks_groups_by_bucket_and_business_day`
- `test_compute_session_blocks_attribution_uses_exit_time`
- `test_compute_session_blocks_returns_empty_when_no_trades`

#### compute_sr_session_worst (HAC Bartlett q=5)
- `test_sr_session_worst_constant_block_pnl_yields_high_sr_with_eps_floor`
  (定数 series で sigma2_LR=0 → eps floor → SR が finite で large positive)
- `test_sr_session_worst_known_series_matches_hand_computed_hac`
  (固定系列 [1, 2, 3, 4, 5] × q=2 で hand-computed と一致)
- `test_sr_session_worst_returns_min_across_three_buckets`
- `test_sr_session_worst_missing_bucket_yields_negative_infinity`
  (bucket 欠損 / block 数 0 → SR=-inf、 hard fail なし)
- `test_sr_session_worst_low_sample_bucket_recorded_in_low_sample_set`
  (bucket 内 block 数 < 30 → low_sample_buckets に含まれる、 SR は計算継続)
- `test_sr_session_worst_q_default_is_5`

#### compute_session_block_win_rate_worst
- `test_wr_session_worst_trade_zero_block_assigned_neutral_half`
  (block で trade_count=0 なら win_{b,t}=0.5)
- `test_wr_session_worst_returns_min_across_three_buckets`
- `test_wr_session_worst_empty_bucket_yields_zero`
  (bucket 内 block 数 0 → WR=0.0)
- `test_wr_session_worst_all_winning_blocks_yields_one`

#### compute_max_dd (値域 [0, 1] clip、 detail Round 1 [C3] / [S3])
- `test_max_dd_monotone_increasing_equity_yields_zero`
- `test_max_dd_known_drawdown_pattern_matches_expected_ratio`
- `test_max_dd_clipped_to_unit_interval_when_equity_drops_to_zero`
  (equity drop 時に値域 [0, 1] 内に clip)
- `test_max_dd_returns_one_when_running_max_remains_non_positive`
  (全 bar で running_max <= 0 の異常系で max_dd=1.0)
- `test_max_dd_skips_bars_with_non_positive_running_max`
  (running_max <= 0 の bar は drawdown 計算から除外)
- `test_max_dd_zero_division_protected_by_denom_floor`
  (running_max が極小値 e.g. 1e-15 でも MAX_DD_DENOM_FLOOR で保護)

#### slack_to_range
- `test_slack_to_range_value_below_lower_returns_negative_value_minus_lower`
- `test_slack_to_range_value_above_upper_returns_negative_upper_minus_value`
- `test_slack_to_range_value_at_center_returns_max_positive_slack`
- `test_slack_to_range_value_at_boundary_returns_zero`

#### log_pf_clip
- `test_log_pf_clip_balanced_gp_gl_returns_zero`
- `test_log_pf_clip_only_profits_returns_upper_bound_two`
- `test_log_pf_clip_only_losses_returns_lower_bound_minus_two`
- `test_log_pf_clip_zero_gp_zero_gl_returns_zero`
  (1e-6 smoothing で 0/0 を未定義にしない、 log(1)=0)

#### compute_signed_slacks
- `test_signed_slacks_perfect_metrics_yield_all_positive_slacks`
- `test_signed_slacks_failing_sharpe_yields_negative_slack_sharpe`
- `test_signed_slacks_sharpe_annual_conversion_uses_sqrt_756`
  (sr_block=0.0364 ≈ 1.0/sqrt(756) → slack_sharpe ≈ 0)
- `test_signed_slacks_denom_floor_is_1e_minus_6_per_synthesis_6_1`
- `test_signed_slacks_tc_in_range_yields_positive_slack`
- `test_signed_slacks_tc_below_min_yields_negative_slack`
- `test_signed_slacks_tc_above_max_yields_negative_slack`

#### evaluate_canonical_five (top-level entry)
- `test_evaluate_canonical_five_perfect_run_yields_gate_pass_true`
- `test_evaluate_canonical_five_failing_sharpe_yields_gate_pass_false`
  (gate_worst_gap > 0)
- `test_evaluate_canonical_five_session_close_drop_forces_gate_pass_false`
  (invariant fail-fast、 gate_worst_gap=0 でも gate_pass=False、 STRATEGIC_SESSION_CLOSE_DROP code 含む)
- `test_evaluate_canonical_five_negative_equity_drop_open_forces_gate_pass_false`
- `test_evaluate_canonical_five_empty_trades_records_input_reason_and_fails_gate`
- `test_evaluate_canonical_five_empty_business_day_universe_records_input_reason`
  (T070 から空集合受領、 INPUT_EMPTY_BUSINESS_DAY_UNIVERSE)
- `test_evaluate_canonical_five_business_day_universe_mismatch_records_input_reason`
  (detail Round 2 [W1] 反映: trade.business_day_index が universe に未登録 → INPUT_BUSINESS_DAY_UNIVERSE_MISMATCH)
- `test_evaluate_canonical_five_provider_exception_converted_to_reason_code`
  (detail Round 1 [S2] 反映、 provider が任意例外を raise しても evaluate は raise せず、
  INPUT_BUCKET_VALIDATOR_EXCEPTION code を返す)
- `test_evaluate_canonical_five_provider_mismatch_records_attribution_mismatch_reason`
  (provider が False を返す trade があれば INPUT_BUCKET_ATTRIBUTION_MISMATCH)
- `test_evaluate_canonical_five_no_raise_contract_for_invalid_bucket_validator`
  (provider が無効でも raw exception は呼出側に伝播しない)
- `test_evaluate_canonical_five_gate_pass_tolerance_handles_floating_noise`
  (gate_worst_gap = 1e-12 → gate_pass=True、 1e-6 → gate_pass=False)
- `test_evaluate_canonical_five_default_validator_version_is_unvalidated`
- `test_evaluate_canonical_five_provider_validates_attribution_and_records_version`
  (mock provider with version="test_provider_v1"、 一致時に validator_version 記録)
- `test_evaluate_canonical_five_returns_frozen_dataclass`
- `test_evaluate_canonical_five_zero_trade_blocks_get_neutral_half_win_rate`
  (detail Round 1 [C1] 反映: business_day_universe で trade=0 day を含めて空 block 生成、
  WR_b の neutral 0.5 が反映されることを確認)

#### invariants 分類
- `test_invariant_flags_strategic_prefix_for_synthesis_6_6`
- `test_invariant_flags_input_prefix_for_engine_input_errors`
- `test_invariant_flags_is_feasible_only_when_all_clear`

### リスク

- (テストのみ、 リスク軽微)

---

## 実装モード

| 項目 | 内容 |
|------|------|
| 推奨モード | **standalone** (T058 / T059 / T060 同様、 単体実装可、 Phase 2 で 9 箇所同時更新を別 PR) |
| 判断根拠 | T061 PR は単体テストのみで既存 stage_gate / swim_lane / archive 経路に touch しない |
| 競合リスク | T058 / T059 / T060 マージ済前提、 ただし各 module 直接 import は無いので独立 merge 可能 |
| 想定実装時間 | 中 (2 施策、 1 day 想定。 HAC autocovariance / signed slack の数式 unit test が test 工数の主) |

## 実装順序

T061 PR で 2 施策を 1 PR で着地。 Phase 2 (9 箇所同時更新) は T063-T064 評価層実装と同時に別 PR (別 TODO)。

---

## DoD (Definition of Done)

T061 PR 完了基準:

### コード DoD (detail Round 1 [W3] 正確化)

- [ ] `src/alpha_factory/canonical_metrics.py` 新規作成:
  - Enum 2 (`SessionBucket`, `InfeasibleReasonCode`)
  - dataclass 7 (`TradeRecord`, `BarEquityPoint`, `BarEquitySeries`, `SessionBlockSummary`, `CanonicalFiveThresholds`, `InvariantFlags`, `CanonicalFiveResult`)
  - Provider protocol 1 (`SessionBucketBoundaryProvider`)
  - 例外 4 (`CanonicalMetricsInputError`, `TradeRecordInvalidError`, `BarEquityInvalidError`, `ThresholdsInvalidError`)
  - helper 関数群 (`compute_session_blocks`, `compute_sr_session_worst`, `compute_session_block_win_rate_worst`, `compute_max_dd`, `compute_signed_slacks`, `slack_to_range`, `log_pf_clip`)
  - top-level entry (`evaluate_canonical_five`)
- [ ] `tests/alpha_factory/test_canonical_metrics.py` 新規作成 (上記 test 全 pass)
- [ ] `uv run pytest tests/alpha_factory/test_canonical_metrics.py` 全 pass
- [ ] `uv run ruff check src/ tests/` clean
- [ ] `uv run mypy src/` clean
- [ ] `stage_gate.py` / `swim_lane.py` / `archive.py` / `cross_pair.py` / `config.py` / `default.yaml` / `docs/alpha_factory/stage-gates.md` を変更しない (Phase 1 スコープ厳守)

### Phase 1 (T061 PR) C2 parallel-path 確認 DoD (concept Round 1 [W3] 4 段階強化)

- [ ] **段階 1 (直 import)**: `grep -rn "from src.alpha_factory.canonical_metrics" scripts/ src/` の結果が `src/alpha_factory/canonical_metrics.py` (自身) と `tests/alpha_factory/test_canonical_metrics.py` 以外で hit しない
- [ ] **段階 2 (再エクスポート)**: `grep -rn "canonical_metrics" src/alpha_factory/__init__.py src/alpha_factory/*.py | grep -v "src/alpha_factory/canonical_metrics.py:"` が 0 hit
- [ ] **段階 3 (alias / wrapper)**: `grep -rn -E "from .* import .* as.*[Cc]anonical|^.* = canonical" src/ scripts/` が 0 hit
- [ ] **段階 4 (runtime 配線)**: `grep -rn -E "evaluate_canonical_five|CanonicalFiveResult" src/alpha_factory/stage_gate.py src/alpha_factory/swim_lane.py src/alpha_factory/cross_pair.py src/alpha_factory/archive.py scripts/alpha_factory/run_ga.py` が 0 hit

### Phase 2 (T063-T064 と同時、 別 PR) DoD (申し送り、 9 箇所 + 周辺 consumer chain)

- [ ] `stage_gate.py:evaluate_stage_a` を旧 Sharpe + complexity penalty から T061 + q_force ranking に置換 (T063)
- [ ] `stage_gate.py:evaluate_stage_b` を旧 fold-based から新 5 fold pooled + T061 worst aggregation に置換 (T064)
- [ ] `stage_gate.py:evaluate_stage_c` を旧 spread stress から新 12w + T061 + cross-pair shadow validation に置換 (T064)
- [ ] (新規) `stage_gate.py:evaluate_stage_c_lite` を 3 disjoint windows × T061 worst aggregation で実装 (T064)
- [ ] `cross_pair.py` の shadow validation を T061 + cross-pair pass 判定に統合 (T064)
- [ ] `config.py:StageGateConfig` に `win_rate_min` 新規 field 追加、 旧 `stage_a/b/c.{*_sharpe_min, fold_*}` 全廃 (T063/T064)
- [ ] `default.yaml`: `live_criteria.win_rate_min: 0.45` 追加 (smoke 後再校正)、 旧 `stage_gate.{stage_a,stage_b,stage_c}` の `*_sharpe_min, fold_*` 全廃 + 新仕様反映 (T063/T064)
- [ ] `swim_lane.py` (該当箇所) で tier1 evaluator が新 stage_gate 経路を呼ぶよう再構築 (T064)
- [ ] `archive.py` (該当箇所) で archive admission が `CanonicalFiveResult.gate_pass` / `log_pf_clip` / `is_feasible` を直接消費 (T067)
- [ ] **接続統合テスト** (concept Round 3 [S3] 反映): config → StageGateConfig → evaluate_stage_* → CanonicalFiveResult → archive admission / log の経路を 1 本の統合 test で固定 (T064 PR)
- [ ] **runtime wiring smoke** (detail Round 1 [W4] 反映、 文字列経由動的参照漏れ予防): `evaluate_stage_*` を実際に呼んで `evaluate_canonical_five` が configured に走ることを確認する E2E smoke 1 本を T064 PR で追加

### Phase 2 周辺 consumer chain checklist (concept Round 1 [W4] 反映、 T060 同型漏れ予防)

- [ ] `default.yaml` → `StageGateConfig` field 接続 (`win_rate_min`)
- [ ] `StageGateConfig` → `evaluate_stage_*` 引数経路
- [ ] `evaluate_stage_*` → `CanonicalFiveResult` 消費経路 (gate_pass / signed slack / log_pf_clip)
- [ ] `CanonicalFiveResult.invariants.is_feasible` → archive admission / GA selection (T067/T065)
- [ ] `archive.py:GENOMES_SCHEMA` (T058 schema v2) に `cf_gate_pass`, `cf_gate_worst_gap`, `cf_log_pf_clip`, `cf_low_sample_buckets`, `cf_bucket_validator_version` 等を追加 (T058 接続、 T064 PR で確定)
- [ ] log 出力: `evaluate_canonical_five` 呼出位置で `gate_pass` / `per_bucket_sr` / `per_bucket_wr` / `low_sample_buckets` を 1 行 INFO ログ (T071 observability)

---

## 関連 / 後段 TODO

- T058: Schema v2 contract (依存先、 設計 APPROVED)
- T059: EpochManager (依存先、 設計 APPROVED)
- T060: Partition + Fold generator (依存先、 設計 APPROVED)
- T062: mission_inf_gap engine (T061 の signed slack 4 指標を inf-norm 集約)
- T063: Stage A evaluator (T061 engine を q_force ranking で消費、 Phase 2 で 9 箇所同時更新)
- T064: Stage B/C-lite/C evaluator (T061 engine を 5 fold pooled / 3 disjoint windows / 12w + cross-pair で消費)
- T065-T066: NSGA-II + CPPS (T061 / T062 を Pareto 軸で消費)
- T070: backtest engine の session bucket label / business day index 割当 (T061 の入力契約)
- T071: observability (per_bucket_sr / per_bucket_wr / low_sample_buckets 監視)
- T072: DST / holiday session boundary contract (`SessionBucketBoundaryV1` provider 実装)
