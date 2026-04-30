# 概念設計: T061 — canonical 5 engine

**Round 1 修正反映** (Codex CHANGES_REQUESTED → CHANGES_APPLIED): denom_floor 1e-6 厳密準拠 / annual 換算 T061 内部単一化 / block 数 hard fail 削除 / Bailey 引用要確認化 / 入出力 invariant 追加 / C2 grep 強化 / 周辺 consumer chain checklist 追加 / 3 列差分表 追加 / infeasible_reason_codes 追加。

## 背景・課題

synthesis § 6 で確定した **canonical 5 worst aggregation** は zenigame-fx Alpha Factory の selection cascade 全体 (Stage A/B/C-lite/C、 archive admission、 GA Pareto 軸) で**最頻出の評価コア**である。 単一の API で実装し、 全 stage / GA / archive 経路から共通参照させる必要がある。

具体的な責務:

1. **canonical 5 metric 計算**: SR_session_worst (HAC Bartlett q=5)、 net_pnl_after_cost、 max_dd、 trade_count、 session_block_win_rate_worst
2. **signed slack + worst gap 集約**: 5 指標 → signed_slack → gate_worst_gap → gate_pass
3. **補助 helper**: slack_to_range (trade_count [L, U] range 用)、 log_pf_clip (archive lexicographic 末端 tie-break 用)
4. **invariant fail-fast 検出**: session_close_drop > 0、 negative_equity_drop_open > 0
5. **deterministic / pure**: stage / GA / archive consumer から呼ぶため、 副作用なし

T061 は **engine (= pure 計算モジュール) のみ**を提供する。 stage 評価器 (Stage A/B/C-lite/C) や GA selection への組込は T062 (mission_inf_gap engine) と T063-T064 (stage 評価器) の責務。

## 前提検証 (C4) — current HEAD `main@ea56484` 基準

| 前提 | verified | 出典 |
|---|---|---|
| canonical 5 = (SR_session_worst, net_pnl_after_cost, max_dd, trade_count, session_block_win_rate_worst) | ✓ | synthesis § 2 / § 6.1 |
| SR_session_worst は HAC Bartlett q=5 補正 + 3 bucket worst | ✓ | synthesis § 6.2 |
| session_block_win_rate_worst は trade=0 block を 0.5 neutral、 3 bucket worst | ✓ | synthesis § 6.3 |
| gate_worst_gap = max_m max(0, -slack_m)、 gate_pass <=> gate_worst_gap == 0 | ✓ | synthesis § 6.4 |
| mission_inf_gap (Pareto f3) は live_criteria 4 指標のみ (slack_wr 含まない) | ✓ | synthesis § 6.4 / § 17 (用語) |
| log_pf_clip = clip(log((GP+1e-6)/(GL+1e-6)), -2, 2) — archive lex 末端 tie-break のみ | ✓ | synthesis § 6.4 |
| invariant fail-fast 2 種 (session_close_drop > 0、 negative_equity_drop_open > 0) | ✓ | synthesis § 6.6 |
| spread_consumption_ratio は tie-break + monitor (gate 圏外) | ✓ | synthesis § 6.7 |
| Pareto 3 軸 (max net_pnl, min max_dd, min mission_inf_gap) は T062 で別実装 | ✓ | synthesis § 6.5 |
| session bucket boundary (UTC 8h × 3) の確定値は T070 backtest engine / T072 DST 担当 | ✓ | synthesis § 18.2 (T913/T914 = fx 番号で T070/T072) |
| 既存 `src/alpha_factory/stage_gate.py` の `evaluate_stage_a` 等は旧仕様 (Sharpe + complexity penalty) で canonical 5 worst なし | ✓ | `stage_gate.py:6` (docstring) + grep |
| 既存 `swim_lane.py` / `stage_gate.py` は `live_criteria_gap.py` 相当の helper を持たない (zenigame 側のみ) | ✓ | grep `find /Users/ishitoya/repository/zenigame-fx/src -name "live_criteria_gap*"` で hit なし |

## 改善アイデア

### 設計方針

**「pure stateless engine + 入力契約 + 出力契約」 の 3 層分離**:

1. **入力契約**: trade-level + bar-level の正規化 dataclass で受け取る。 session bucket 割当 / business day index は upstream で確定済み (T070 backtest engine 拡張の責務、 T061 は consume するのみ)
2. **engine 本体**: 5 metric の数式を synthesis § 6 に厳密準拠して実装。 純粋関数、 副作用なし、 deterministic
3. **出力契約**: `CanonicalFiveResult` dataclass で 5 raw metric + 5 signed slack + worst gap + gate_pass + invariant flag + (補助) log_pf_clip を返す

### Module 構造

```
src/alpha_factory/canonical_metrics.py (新規、 T061 PR スコープ)
├── DataClasses
│   ├── TradeRecord  — 1 trade (entry/exit time UTC, pnl_net, session_bucket_label)
│   ├── BarEquityPoint  — 1 bar の (timestamp_utc, equity)
│   ├── SessionBlock  — (business_day_index, session_bucket) 単位の集約結果
│   ├── CanonicalFiveThresholds  — live_criteria + tc range + session_count 補助
│   └── CanonicalFiveResult  — 5 raw + 5 slack + worst_gap + gate_pass + invariants + log_pf_clip
├── Enums
│   └── SessionBucket  — TOKYO / LONDON / NY (3 値固定、 string base)
├── Helpers (pure functions)
│   ├── compute_session_blocks(trades, bars) -> dict[SessionBucket, list[SessionBlock]]
│   ├── compute_sr_session_worst(blocks_by_bucket, q=5) -> tuple[float, dict[SessionBucket, float]]
│   ├── compute_session_block_win_rate_worst(blocks_by_bucket) -> tuple[float, dict[SessionBucket, float]]
│   ├── compute_net_pnl_after_cost(trades) -> float
│   ├── compute_max_dd(bars) -> float
│   ├── compute_trade_count(trades) -> int
│   ├── compute_signed_slacks(metrics, thresholds) -> dict[str, float]
│   ├── slack_to_range(value, lower, upper, denom_floor) -> float
│   ├── log_pf_clip(gross_profit, gross_loss) -> float
│   └── detect_invariant_violations(trades, bars) -> InvariantFlags
└── Top-level entry
    └── evaluate_canonical_five(trades, bars, thresholds) -> CanonicalFiveResult
```

### 入力 dataclass 仕様

```python
class SessionBucket(StrEnum):
    """8h × 3 bucket、 boundary は T070 backtest engine が確定 (T061 consume のみ)."""
    TOKYO = "tokyo"
    LONDON = "london"
    NY = "ny"


@dataclass(frozen=True)
class TradeRecord:
    """1 trade (intraday close-out 前提).

    invariant (engine が `__post_init__` で fail-fast 検証):
    - entry_time_utc / exit_time_utc は **UTC-aware datetime + utcoffset()==0** (T060 Period と同規約)
    - entry_time_utc < exit_time_utc
    - session_bucket / business_day_index は **T070 が確定**、 T061 は consume のみ
    - **(exit_time_utc, session_bucket, business_day_index) 一致性**: T061 内 helper
      `_validate_trade_attribution(trade, bucket_boundary_provider)` で T070 出力を再検証可能に
      する provider hook を入れる。 デフォルトは provider=None で skip (T070 確定値を信頼)、
      T064 統合時に provider=`SessionBucketBoundaryV1()` を注入して double-check (Round 1
      [Warning] 1 反映: T070 側転記漏れ静的検出)
    - pnl_net は spread + swap 反映済 (絶対制約 1.3 三項目)
    - is_session_close_drop / is_negative_equity_drop_open は T070 が判定したフラグ
    """
    entry_time_utc: datetime
    exit_time_utc: datetime
    pnl_net: float          # net of spread + swap
    session_bucket: SessionBucket
    business_day_index: int  # T070 が割当 (例: 2025-01-01 = 0)
    is_session_close_drop: bool  # T070 が判定 (intraday 制約違反: 翌日跨ぎ等)
    is_negative_equity_drop_open: bool  # T070 が判定 (資本破綻 open 中)


@dataclass(frozen=True)
class BarEquityPoint:
    """1 bar の equity (max_dd 計算用)."""
    timestamp_utc: datetime
    equity: float


@dataclass(frozen=True)
class BarEquitySeries:
    """max_dd 計算の input contract (Round 1 [Warning] 2 反映).

    Series 全体の invariant を `__post_init__` で fail-fast 検証:
    - 全 BarEquityPoint.timestamp_utc が UTC-aware (utcoffset==0)
    - timestamps が strict monotone increasing (sorted + 重複なし)
    - len(points) >= 1
    - equity が finite (NaN/Inf 検出時は `BarEquityInvalidError` を raise → engine 側で
      `infeasible_reason_codes.add("invalid_bar_series")` して gate_pass=False に変換、
      raw exception は呼出側に伝播しない)

    max_dd 計算が不定にならないことを保証 (Round 1 [Warning] 2 反映)。
    """
    points: tuple[BarEquityPoint, ...]


@dataclass(frozen=True)
class CanonicalFiveThresholds:
    """live_criteria + supplementary thresholds.

    sharpe_min: annual Sharpe (T042 換算後比較、 SR_session_worst が daily-block scale なので
        ここで √(252/expected_blocks_per_year) 換算が必要 — 詳細は § 数式仕様 で説明)
    net_pnl_min: 期間内合計 PnL の絶対値 (JPY)
    max_dd_max: 最大 DD 上限 (例 0.20 = 20%、 abs ratio)
    trade_count_min, trade_count_max: trade_count [L, U] range
    win_rate_min: session_block_win_rate_worst の最低許容 (例 0.45)

    Note: live_criteria の sharpe_min, total_pnl_min, max_drawdown_max, trade_count_min/max を
    そのまま受け取る。 win_rate_min は live_criteria に無いので別 source (config) から渡す。
    """
    sharpe_min: float
    net_pnl_min: float
    max_dd_max: float
    trade_count_min: int
    trade_count_max: int
    win_rate_min: float
```

### 出力 dataclass 仕様

```python
@dataclass(frozen=True)
class InvariantFlags:
    """fail-fast 用 flag (synthesis § 6.6).

    - session_close_drop_count: trade-level の intraday 制約違反 (T070 判定済) 件数
    - negative_equity_drop_open_count: open 中の資本破綻 (T070 判定済) 件数
    - infeasible_reason_codes: 上記 2 種に加えて T061 engine 内で検出した不変条件違反コード
      (Round 1 [Suggestion] 2 反映): 例 `invalid_bar_series` / `bucket_attribution_mismatch` /
      `empty_trade_list` / `non_finite_pnl`
    """
    session_close_drop_count: int
    negative_equity_drop_open_count: int
    infeasible_reason_codes: frozenset[str]  # T063/T064 統合時の診断安定化

    @property
    def is_feasible(self) -> bool:
        return (
            self.session_close_drop_count == 0
            and self.negative_equity_drop_open_count == 0
            and len(self.infeasible_reason_codes) == 0
        )


@dataclass(frozen=True)
class CanonicalFiveResult:
    """canonical 5 worst aggregation の結果.

    raw values:
        sr_session_worst: 3 bucket SR の min (HAC Bartlett q=5 補正)
        net_pnl_after_cost: 期間内合計 net PnL
        max_dd: 最大 DD (>=0、 ratio スケール)
        trade_count: 期間内 trade 数
        session_block_win_rate_worst: 3 bucket WR の min

    signed slack (各指標、 + = 余裕、 - = 未達):
        slack_sharpe, slack_pnl, slack_dd, slack_tc, slack_wr

    集約:
        gate_worst_gap = max_m max(0, -slack_m)
        gate_pass = (gate_worst_gap == 0)

    補助:
        log_pf_clip: archive 末端 tie-break (-2 to 2)
        per_bucket_sr: 診断用 (3 bucket SR)
        per_bucket_wr: 診断用 (3 bucket WR)

    invariant:
        invariants.is_feasible が False なら gate_pass = False を強制
    """
    # raw metrics
    sr_session_worst: float
    net_pnl_after_cost: float
    max_dd: float
    trade_count: int
    session_block_win_rate_worst: float
    # per-bucket diagnostics
    per_bucket_sr: dict[SessionBucket, float]
    per_bucket_wr: dict[SessionBucket, float]
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
    invariants: InvariantFlags
```

### 数式仕様 (synthesis § 6 厳密準拠)

#### synthesis ↔ T061 数式 差分ゼロ確認表 (Round 1 [Suggestion] 1 反映)

| # | synthesis § 6 式 | T061 実装式 | 差分 | 補足 |
|---|---|---|---|---|
| 1 | `slack_sharpe = (sharpe_ann - S_min) / max(|S_min|, 1e-6)` | 同上 (denom_floor=1e-6 厳密) | **ゼロ** | sharpe_ann は T061 内部で `SR_session_worst * sqrt(N_blocks_per_year)` で確定 |
| 2 | `slack_pnl = (net_pnl - R_min) / max(|R_min|, 1e-6)` | 同上 (denom_floor=1e-6 厳密) | **ゼロ** | R_min は CanonicalFiveThresholds.net_pnl_min そのまま |
| 3 | `slack_dd = (DD_max_adj - max_dd) / max(DD_max_adj, 1e-6)` | 同上 (denom_floor=1e-6 厳密) | **ゼロ** | DD_max_adj = thresholds.max_dd_max (synthesis § 5 の adj は engine 外責務) |
| 4 | `slack_tc = slack_to_range(tc, [TC_min, TC_max]) / max(TC_min, 1e-6)` | 同上 (denom_floor=1e-6 厳密) | **ゼロ** | slack_to_range の中身も synthesis 文意通り (中央 + 範囲外 -) |
| 5 | `slack_wr = (WR_worst - WR_min) / max(WR_min, 1e-6)` | 同上 (denom_floor=1e-6 厳密) | **ゼロ** | WR_worst は session_block_win_rate_worst (3 bucket min) |
| 6 | `gate_worst_gap = max_m max(0, -slack_m)` | 同上 (5 指標全てを worst 集約) | **ゼロ** | invariant fail-fast は別経路で gate_pass を override |
| 7 | `gate_pass <=> gate_worst_gap == 0` | 同上 + `is_feasible` AND 条件 | **拡張のみ** | invariants.is_feasible=False なら gate_pass=False を強制 (synthesis § 6.6 該当) |
| 8 | `mission_inf_gap = max(slack_*4 worst)` | **T061 では計算しない** (T062 担当) | **責務分離** | synthesis § 6.4 の「win_rate を含まない」制約を T062 で実装 |
| 9 | `log_pf_clip = clip(log((GP+1e-6)/(GL+1e-6)), -2, 2)` | 同上 | **ゼロ** | trade-level GP/GL から計算 (block-level ではない) |
| 10 | SR HAC Bartlett q=5 (synthesis § 6.2) | 同上 | **ゼロ** | 詳細は次節 |
| 11 | session_block_win_rate trade=0→0.5 neutral (synthesis § 6.3) | 同上 | **ゼロ** | 詳細は次節 |

**denom_floor 1e-6 厳密準拠の根拠** (Round 1 [Critical] 1 反映): synthesis § 6.1 の確定値に従う。 zenigame の T513 cascade audit で metric 別 floor を導入したのは「`adaptive_live_criteria.defensive.min_net_return=0.0` で gap が暴走する fix」 であり、 zenigame-fx では live_criteria.* が**全て >0 の固定値** (sharpe_min=1.0, total_pnl_min=50000, max_drawdown_max=0.2, trade_count_min=50, win_rate_min は新規定義で >0 を契約) なので 1e-6 floor で問題が起きない (threshold が極小値にならない)。 smoke 後に metric 別 floor 必要性を再判定 (synthesis § 15 に追記候補)。

#### SR_session_worst (HAC Bartlett q=5)

```python
def compute_sr_session_worst(
    blocks_by_bucket: dict[SessionBucket, list[float]],  # 各 bucket の block PnL series
    q: int = 5,
    eps: float = 1e-12,
) -> tuple[float, dict[SessionBucket, float], frozenset[str]]:
    """3 bucket の HAC 補正 SR を計算し、 block-scale worst (= min) を返す.

    Bartlett kernel (Newey-West 1987 の三角窓):
        gamma_b(k) = lag-k autocovariance (population formula)
        sigma2_LR_b = gamma_b(0) + 2 * sum_{k=1..q}((1 - k/(q+1)) * gamma_b(k))
        SR_b = mu_b / sqrt(max(sigma2_LR_b, eps))

    Note: SR は **block scale** (1 block = 1 営業日 × 1 bucket = 8h)。 annual scale 換算は
    `compute_signed_slacks` 内で完結する (Round 1 [Critical] 2 反映: 換算責務を T061 内部で
    単一化)。 呼出側に block-scale を漏らさない、 annual-scale slack のみを返す。

    Args:
        blocks_by_bucket: {Tokyo/London/NY: [block_pnl_0, block_pnl_1, ...]}
        q: Bartlett lag (default 5、 1 週間相当、 synthesis 確定)
        eps: sigma2_LR の最小 floor (zero variance 系列保護)

    Returns:
        (sr_worst, per_bucket_sr, low_sample_buckets):
        - sr_worst: 3 bucket の min (block-scale)
        - per_bucket_sr: 診断用 dict
        - low_sample_buckets: block 数 < 30 の bucket 集合 (Round 1 [Critical] 3 反映:
          hard fail はせず、 caller 側で診断ログに使う。 sample-size 警告のみ。
          Newey-West (1987) は q=5 lag 推定で finite-sample bias を許容する論文だが、
          n>=30 を厳密要件と読むのは過剰解釈)。
    """
```

#### session_block_win_rate_worst

```python
def compute_session_block_win_rate_worst(
    blocks_by_bucket: dict[SessionBucket, list[SessionBlockSummary]],
) -> tuple[float, dict[SessionBucket, float]]:
    """3 bucket WR の worst (= min)。 trade=0 block は 0.5 neutral.

    Args:
        blocks_by_bucket: {Tokyo/London/NY: [SessionBlockSummary, ...]}
            SessionBlockSummary には pnl_net (block 内 sum) と trade_count_block が必要

    Returns:
        (wr_worst, per_bucket_wr): bucket 内 block 数 = 0 なら WR = 0.0 (= worst-case)
    """

# SessionBlockSummary は内部 dataclass:
@dataclass(frozen=True)
class SessionBlockSummary:
    business_day_index: int
    session_bucket: SessionBucket
    pnl_net: float
    trade_count: int
```

#### slack_to_range (trade_count 用、 2 段階契約)

`slack_to_range` は **分子部分 (signed numerator) のみ**を返し、 denom 化は呼出側 (`compute_signed_slacks`) が `1e-6` floor で実施する (synthesis § 6.1 の `slack_tc = slack_to_range(tc, [TC_min, TC_max]) / max(TC_min, 1e-6)` を分割実装)。 詳細は次節 `signed slack 集約` 参照。

#### log_pf_clip

```python
def log_pf_clip(gross_profit: float, gross_loss: float) -> float:
    """log Profit Factor を [-2, 2] に clip (archive 末端 tie-break のみ).

    GP = sum of positive trade PnL, GL = sum of |negative trade PnL|

    log_pf = log((GP + 1e-6) / (GL + 1e-6))
    return clip(log_pf, -2, 2)
    """
```

#### signed slack 集約

```python
DENOM_FLOOR: Final[float] = 1e-6  # synthesis § 6.1 厳密準拠 (Round 1 [Critical] 1 反映)
N_BLOCKS_PER_YEAR: Final[int] = 756  # 252 営業日 × 3 bucket、 T061 内 const

def compute_signed_slacks(
    sr_session_worst_block_scale: float,
    net_pnl_after_cost: float,
    max_dd: float,
    trade_count: int,
    session_block_win_rate_worst: float,
    thresholds: CanonicalFiveThresholds,
) -> dict[str, float]:
    """5 指標の signed slack を計算 (synthesis § 6.1 厳密).

    SR annual 換算は本関数内で完結 (Round 1 [Critical] 2 反映: 責務単一化):
        sharpe_ann_estimate = sr_session_worst_block_scale * sqrt(N_BLOCKS_PER_YEAR)

    全 denom_floor = 1e-6 (synthesis § 6.1 確定値)。

    Returns:
        {
            "sharpe": (sharpe_ann_estimate - thresholds.sharpe_min) / max(|sharpe_min|, 1e-6),
            "pnl":    (net_pnl - thresholds.net_pnl_min) / max(|net_pnl_min|, 1e-6),
            "dd":     (max_dd_max - max_dd) / max(max_dd_max, 1e-6),
            "tc":     slack_to_range(trade_count, [tc_min, tc_max]),
            "wr":     (wr_worst - win_rate_min) / max(win_rate_min, 1e-6),
        }
    """


def slack_to_range(value: float, lower: float, upper: float) -> float:
    """trade_count [L, U] range の signed slack (synthesis § 6.1 整合).

    synthesis § 6.1: slack_tc = slack_to_range(tc, [TC_min, TC_max]) / max(TC_min, 1e-6)
    本 helper は分子部分 (signed slack の絶対値) を返し、 denom 化は呼出側 (= compute_signed_slacks)
    が行う。 denom = max(|TC_min|, 1e-6) で synthesis 整合。

    sign convention:
        value < lower:  return (value - lower)        # 負値 (不足)
        lower <= value <= upper:
                        return min((value - lower), (upper - value))   # 正値 (中央余裕最大、 境界 0)
        value > upper:  return (upper - value)        # 負値 (超過)

    呼出側で `slack_tc = slack_to_range(...) / max(|TC_min|, 1e-6)` する。
    """

### 重要な設計判断

**1. trade attribution rule (どの timestamp で session_bucket / business_day を決めるか)**

- **採用**: `exit_time_utc` (trade close 時点) を attribution rule とする
- **理由**:
  - PnL は exit 時点で realized、 イベントベースで自然
  - Stage A/B/C-lite/C 全 stage で deterministic
  - intraday 制約 (synthesis § 1.2) により entry/exit は同 business day を要求 → entry/exit attribution の差は最小
- **責務分離**: `session_bucket` と `business_day_index` の割当は **T070 backtest engine** の責務。 T061 はラベル済 TradeRecord を consume するのみ
- **転記漏れ防止 (Round 1 [Warning] 1 反映)**: T061 内に `_validate_trade_attribution(trade, provider)` hook を持ち、 T064 統合時に `provider=SessionBucketBoundaryV1()` (T072 確定 boundary 契約) を注入して double-check 可能にする

**2. block scale → annual scale 換算 (Sharpe)**

- **採用**: `SR_annual = SR_block * sqrt(N_blocks_per_year)`、 `N_BLOCKS_PER_YEAR = 756` (T061 内 const、 const 名で文書化)
- **責務単一化 (Round 1 [Critical] 2 反映)**: 換算は `compute_signed_slacks` 内で完結、 呼出側に block-scale を漏らさない。 内部 helper `compute_sr_session_worst` は block-scale を返すが、 これは internal use のみ (top-level `evaluate_canonical_five` は annual-scale slack を返す)
- **論文**: Lo (2002) "The Statistics of Sharpe Ratios" — IID 仮定下では sqrt(T) scaling、 HAC 補正後の SR も同じ scaling

**3. invariant fail-fast の扱い**

- **採用**: `is_feasible=False` なら `gate_pass=False` を**強制** (gate_worst_gap が 0 でも fail)
- **理由**: synthesis § 6.6 で「selection 全段階から排除」 と明記、 canonical 5 で gate_pass=True を返すと downstream で誤って通過してしまう
- **infeasible_reason_codes (Round 1 [Suggestion] 2 反映)**: `InvariantFlags.infeasible_reason_codes` (frozenset[str]) で具体的 code を返す。 T063/T064 が原因別に集計可能

**4. session bucket 数 = 3 固定 (Tokyo/London/NY)**

- **採用**: `SessionBucket` Enum で 3 値固定
- **理由**: synthesis § 5 / § 17 で「session_bucket 3 (Tokyo/London/NY) 固定、 6 bucket 不採用 (C-lite で C7 違反)」 と明記
- **拡張**: 別値は別 TODO (C-lite の sample size 観測後に再検討)

**5. denom floor = 1e-6 (synthesis 厳密準拠、 Round 1 [Critical] 1 反映)**

- **採用**: 5 指標全て `1e-6` (synthesis § 6.1 確定値)
- **理由**: synthesis 確定値を変えない (handoff § 4.4 「synthesis 確定値を変えない、 思想ベースで議論し直すなら別」)。 zenigame の metric 別 floor は `defensive.min_net_return=0.0` 暴走 fix のためで、 zenigame-fx は live_criteria.* が**全て >0 固定**なので 1e-6 で問題発生しない
- **smoke 後再校正候補 (synthesis § 15 追記候補)**: smoke で gap 値分布を観測、 metric 別 floor が必要なら別 TODO で synthesis を改訂

**6. T062 (mission_inf_gap) との分離**

- **T061 の出力**: 5 raw metric + 5 signed slack + worst_gap + gate_pass + log_pf_clip + invariant
- **T062 の責務**: T061 の signed slack 4 指標 (sharpe/pnl/dd/tc) を inf-norm 集約 → mission_inf_gap (Pareto 3 軸 f3、 win_rate を含まない)
- **T061 単体では mission_inf_gap を計算しない** (synthesis § 6.4 で明記された「win_rate を含まない」 制約を T062 で実装)

## 期待効果

### live_criteria 達成への構造的貢献

- **canonical 5 worst aggregation の SSOT 化**: Stage A/B/C-lite/C で同じ engine を呼び、 metric 計算ロジックの分散による gap (synthesis § 13 の旧 zenigame で発生したパターン) を排除
- **HAC 補正 SR の標準化**: 旧 zenigame-fx の Sharpe (per-trade or per-bar、 serial correlation 無補正) を block-level HAC 補正で置換 → Lo (2002) serial correlation 警告対応
- **session bucket 主軸の正規化**: synthesis § 2 原則 2 (難易度次元の明示的正規化) を実装層で実現
- **invariant fail-fast の構造化**: synthesis § 6.6 の 2 種類を `InvariantFlags` で明示集計、 silent pass を防ぐ

### 副次効果

- **T063-T064 の実装簡素化**: stage 評価器は T061 engine を呼ぶだけで canonical 5 worst を計算可能
- **DSR (T072) との整合**: HAC 補正 SR は Bailey & López de Prado (2014) の DSR 入力としてそのまま使える
- **逆輸入候補**: synthesis § 19 の 4 候補のうち #2 (session_block_win_rate)、 #3 (HAC 補正 Sharpe 標準化) を本 TODO で先行実装、 zenigame に逆輸入可能

## 実装方針 (概要)

### コンポーネント変更 (Phase 1: T061 PR)

| ファイル | 変更内容 |
|---|---|
| `src/alpha_factory/canonical_metrics.py` | **新規作成**。 SessionBucket Enum + 5 dataclass + helper 関数群 + top-level entry |
| `tests/alpha_factory/test_canonical_metrics.py` | **新規**。 数式 unit test + 各 helper の振る舞い test + invariant fail-fast test |

**Phase 1 (T061 PR) スコープは上記 2 施策のみ**。 既存 `stage_gate.py` / `swim_lane.py` / `archive.py` への組込は **Phase 2 (T063-T064 評価層実装と同時)** で実施。 T061 PR 単独では既存経路に touch しない。

### Phase 2 (別 TODO、 T063-T064 と同時) 申し送り

T061 完了後、 stage 評価器が T061 engine を消費する形に置換する必要がある。

**Phase 2 で同時更新が必要な箇所** (5 箇所 + 周辺 consumer 4 箇所、 Round 1 [Warning] 4 反映):

| # | ファイル / 箇所 | 変更内容 | 担当 TODO |
|---|---|---|---|
| 1 | `src/alpha_factory/stage_gate.py:evaluate_stage_a` | 旧 Sharpe + complexity penalty 経路を全廃、 T061 + q_force ranking に置換 | T063 |
| 2 | `src/alpha_factory/stage_gate.py:evaluate_stage_b` | 旧 fold-based 経路を新 5 fold pooled + T061 worst aggregation に置換 | T064 |
| 3 | `src/alpha_factory/stage_gate.py:evaluate_stage_c` | 旧 spread stress 経路を新 12w + T061 + cross-pair shadow validation に置換 | T064 |
| 4 | (新規) `src/alpha_factory/stage_gate.py:evaluate_stage_c_lite` | 3 disjoint windows × T061 worst aggregation を新規実装 | T064 |
| 5 | `src/alpha_factory/cross_pair.py` | shadow validation を T061 canonical 5 + cross-pair pass 判定に統合 | T064 |
| 6 | `src/alpha_factory/config.py:StageGateConfig` | `win_rate_min` 新規 field 追加 (live_criteria に無いため別 source、 T061 入力契約) + 旧 `stage_a/b/c.{*_sharpe_min, fold_*}` 全廃 | T063/T064 |
| 7 | `config/alpha_factory/default.yaml` | `stage_gate.{stage_a,stage_b,stage_c}` 新仕様反映 + `live_criteria.win_rate_min: 0.45` 追加 (smoke 後再校正)、 旧 stage_a/b/c の `*_sharpe_min, fold_*` を全廃 | T063/T064 |
| 8 | `src/alpha_factory/swim_lane.py` (該当箇所) | tier1 evaluator が新 stage_gate を呼ぶよう経路再構築 | T064 |
| 9 | `src/alpha_factory/archive.py` (該当箇所) | archive admission が CanonicalFiveResult の `gate_pass` / `log_pf_clip` / `is_feasible` を直接消費 | T067 (Loop closure 担当) |

**周辺 consumer chain 検証 checklist (T060 で起きた漏れと同型を予防、 Round 1 [Warning] 4 反映)**:

- [ ] `config/alpha_factory/default.yaml` → `src/alpha_factory/config.py:StageGateConfig` field 接続
- [ ] `StageGateConfig` → `evaluate_stage_*` 引数経路 (`win_rate_min` / 旧フィールド削除分)
- [ ] `evaluate_stage_*` → `CanonicalFiveResult` 消費経路 (gate_pass / signed slack / log_pf_clip)
- [ ] `CanonicalFiveResult.invariants.is_feasible` → archive admission / GA selection 経路 (T067/T065 で完成)
- [ ] `archive.py:GENOMES_SCHEMA` (T058 schema v2) に `cf_gate_pass`, `cf_gate_worst_gap`, `cf_log_pf_clip` 等を追加するか、 既存 field を再利用するか (T058 接続)
- [ ] log 出力: `evaluate_canonical_five` 呼出位置で gate_pass / per_bucket_sr / per_bucket_wr を 1 行 INFO ログ (T071 observability)

これらを同時更新しないと「engine は新仕様で動くが stage 評価器 / config / archive は旧仕様」 の不整合が発生する。

### C2 parallel-path 確認 (Phase 1 DoD、 T060 同様 + Round 1 [Warning] 3 強化)

旧経路と新経路の物理的分離を以下 4 段階で grep 検証 (再エクスポート / alias / wrapper も検出):

1. **直 import 検出**: `grep -rn "from src.alpha_factory.canonical_metrics" scripts/ src/` → 自身 + tests 以外 hit なし
2. **module-level 再エクスポート検出**: `grep -rn "canonical_metrics" src/alpha_factory/__init__.py src/alpha_factory/*.py | grep -v "src/alpha_factory/canonical_metrics.py:"` → 0 hit
3. **alias / wrapper 検出**: `grep -rn -E "from .* import .* as.*[Cc]anonical|^.* = canonical" src/ scripts/` → 0 hit (rename import / 別名注入なし)
4. **runtime 配線検出**: `grep -rn -E "evaluate_canonical_five|CanonicalFiveResult" src/alpha_factory/stage_gate.py src/alpha_factory/swim_lane.py src/alpha_factory/cross_pair.py src/alpha_factory/archive.py scripts/alpha_factory/run_ga.py` → 0 hit (Phase 2 まで配線禁止)

**Phase 2 解禁基準**: T063/T064 PR で配線時は上記 grep が**意図した hit のみ**になるよう test で確認。

**並走期間 (Phase 1 merge 後 Phase 2 まで) のリスク許容**: T061 module は import されないので runtime 計算 0、 dual-path duplicate の懸念なし (= dead code として merge、 T063/T064 で初めて runtime 計算開始)。 旧経路は無変更で動作維持。

## C3 / C7 適用

- **C3 (Collider bias)**: T061 は metric 計算の数式実装のみで、 selection chain 中間集団の相関分析を行わない。 C3 該当なし
- **C7 (Sample size、 Round 1 [Critical] 3 反映)**: HAC Bartlett q=5 lag 推定は Newey-West (1987) で finite-sample bias を許容する論文だが、 sample 数 n が極端に小さいと sigma2_LR_b が不安定。 **対策**: hard fail はせず、 `sigma2_LR_b` に `eps=1e-12` の floor を入れて zero-variance 系列を保護。 加えて block 数 < 30 の bucket を `low_sample_buckets: frozenset[SessionBucket]` で診断出力 (raw warning 用)。 caller 側 (T064 stage 評価器) が sample-size 不足を検出した場合の挙動 (例: stage 全体 fail / strict eval スキップ) は別 TODO で議論。 T061 engine 自体は hard fail を入れない (synthesis § 6 にない仕様追加を避ける)

## 制約・前提

- **session bucket 割当 / business day index は T070 が担当**: T061 はラベル済 TradeRecord を consume するのみ
- **annual scale 換算は T061 内で完結**: `N_blocks_per_year = 756` は T061 内 const、 yaml override 不要
- **denom floor は T061 内 const**: zenigame `GAP_DENOM_FLOOR` と整合、 yaml override 不要
- **invariant fail-fast は engine 側で強制**: caller が `is_feasible` を見落としても `gate_pass=False` で防ぐ
- **GP/GL は trade 単位の sum**: log_pf_clip は trade-level PnL から直接計算 (block-level ではない)

## スコープ外

- T058 / T059 / T060: 依存先 (Schema v2 / EpochManager / Partition+Fold)
- T062: mission_inf_gap engine (T061 の signed slack 4 指標を inf-norm 集約)
- T063: Stage A evaluator (T061 engine を q_force ranking で消費)
- T064: Stage B/C-lite/C evaluator (T061 engine を 5 fold pooled / 3 disjoint windows / 12w + cross-pair で消費)
- T065-T066: NSGA-II + CPPS (T061 / T062 を Pareto 軸で消費)
- T070: backtest engine の session bucket label / business day index 割当 (T061 の入力契約を満たす責務)
- T072: DST / holiday session boundary contract (session bucket boundary 確定)

## 学術引用 / 先行知見 (Round 1 [Suggestion] 3 反映、 粒度を厳密化、 detail Round 1 [W5] 反映で full citation 化)

- **Lo, A. W. (2002). "The Statistics of Sharpe Ratios." Financial Analysts Journal, 58(4), 36-52.**: serial correlation **問題提起** (IID 仮定下の標準 Sharpe が serial-correlated returns で biased)。 HAC 補正手法そのものは提案していない。 T061 は本論文の警告を踏まえて HAC 補正経路を採用
- **Newey, W. K., & West, K. D. (1987). "A Simple, Positive Semi-Definite, Heteroskedasticity and Autocorrelation Consistent Covariance Matrix." Econometrica, 55(3), 703-708.**: Bartlett kernel HAC 推定量の方法論的根拠。 T061 が採用する `sigma2_LR = gamma(0) + 2 * sum_k (1 - k/(q+1)) * gamma(k)` の元
- **Bailey, D. H., & López de Prado, M. (2014). "The Deflated Sharpe Ratio: Correcting for Selection Bias, Backtest Overfitting, and Non-Normality." Journal of Portfolio Management, 40(5), 94-107.**: DSR は **selection bias / backtest overfitting / non-normality** 補正のための論文。 「HAC SR 必須」 と書かれているかは**要確認** (Round 1 [Critical] 4 反映: 記憶曖昧、 確証が取れるまで「HAC SR を直接 input 可能」 という主張は外し、 T072 担当 TODO で必要なら別途確認する)
- synthesis § 6: canonical 5 + Pareto 3 数式仕様 (確定値)
- zenigame `evaluation/fitness.py:461` (`calc_stage_a_gate_score`) — canonical 5 worst gap の実装パターン
- zenigame `evaluation/live_criteria_gap.py` (`compute_signed_slack_margin`) — signed slack 5 指標の実装パターン

## Round 1 → Round 2 の改訂点 (Codex review 反映サマリ)

| Round 1 [Critical/Warning/Suggestion] | 修正対応 |
|---|---|
| [C1] denom_floor が synthesis § 6.1 (1e-6) と乖離 (1.0/0.05/0.10) | denom_floor=1e-6 厳密準拠に統一、 metric 別 floor 提案を撤回。 smoke 後再校正候補として synthesis § 15 追記候補化 |
| [C2] annual scale 換算責務が呼出側と T061 内で矛盾 | `compute_signed_slacks` 内で annual 換算を完結、 top-level `evaluate_canonical_five` は annual-scale slack のみ返す。 block-scale は internal use only |
| [C3] block 数 >= 30 を Newey-West (1987) 根拠で hard fail とした | hard fail 削除。 sigma2_LR に eps=1e-12 floor、 `low_sample_buckets` で診断出力のみ。 caller 側 (T064) で sample-size 判定 |
| [C4] Bailey 2014 DSR が「HAC 補正後 SR 必須」 と書かれている記述 | 「**要確認**」 と明記、 確証が取れるまで「HAC SR を DSR に直接 input 可能」 という主張は外す |
| [W1] `(exit_time_utc, session_bucket, business_day_index)` の一致性 invariant が無い | TradeRecord に `_validate_trade_attribution(trade, provider)` hook 追加、 T064 統合時に provider 注入で double-check 可能化 |
| [W2] BarEquityPoint が単調増加・重複なし・tz-aware を invariant 化していない | `BarEquitySeries` dataclass を新設、 `__post_init__` で fail-fast 検証 (sorted/no-dup/UTC-aware/finite) |
| [W3] C2 grep が import だけで再エクスポート / alias / wrapper を検出しない | grep 検証を 4 段階化 (直 import / 再エクスポート / alias / runtime 配線) |
| [W4] Phase 1/2 周辺 consumer 漏れ (T060 と同型) checklist 不足 | Phase 2 申し送り 5→9 箇所に拡張、 周辺 consumer chain checklist 追加 |
| [S1] synthesis 式 / T061 実装式 / 差分 の 3 列表 | 数式仕様冒頭に 11 行表追加、 差分ゼロを機械的に確認可能 |
| [S2] `infeasible_reason_codes` 戻り値追加で診断安定化 | InvariantFlags に `infeasible_reason_codes: frozenset[str]` を追加 |
| [S3] 学術引用の粒度厳密化 (Lo / Newey-West / DSR) | 各引用の役割を 1 行で明記、 DSR は要確認化 |

## 残論点 (Round 2 以降で議論可能)

1. **`win_rate_min` の SSOT**: `live_criteria` に追加するか、 `stage_gate.canonical_five.win_rate_min` で別管理か (現状概念設計は Phase 2 申し送り 7 で `live_criteria.win_rate_min: 0.45` を提案、 詳細設計で確定)
2. **`N_BLOCKS_PER_YEAR = 756` の holiday 補正**: T072 (DST/holiday) 確定後、 T061 内 const を `n_blocks_observed` 実測ベースに切替するか
3. **`SessionBucketBoundaryV1` provider interface 定義**: T061 で interface のみ定義、 実装は T072 で。 詳細設計で interface signature 確定
