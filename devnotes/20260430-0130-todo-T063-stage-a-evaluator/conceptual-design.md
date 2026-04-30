# 概念設計: T063 — Stage A evaluator

**Round 1 修正反映** (Codex CHANGES_REQUESTED → CHANGES_APPLIED):
- T061 への依存契約と threshold 派生責務の衝突を解消 (T063 が orchestrator も兼ね、 thresholds 派生 + T061 呼出 + ranking を実施)
- `divergence_cycle_count` signed semantic を撤廃、 `divergence_offset_steps: int >= 0` (clamp [0, cap]) に単純化
- immutable state API 統一 (`evaluate_generation(state, inputs) -> (StageAResult, new_state)` の純粋関数化、 controller class 廃止)
- net_pnl_min / trade_rate denominator / top-N rounding の 3 つの「Decision Pending」 を概念設計内で確定 (Round 2 で議論)
- `StageAResult` の default-deny 契約を docstring 明記
- `threshold_score: float | None` (空集合ケース対応)

## 背景・課題

synthesis § 5.1 で確定した **Stage A: Hard gate + q_force (top%)** は selection cascade の最初のフィルタで、 GA 各世代で「mission 達成可能性が高い候補」 を Stage B 以降に進ませる役割を担う。 zenigame の `StageAGateController` (`stage_a_gate.py`) を fx 用に再実装するが、 以下の重要な拡張がある:

1. **canonical 5 worst gate_score (T061)** を使う (旧 zenigame の同名 score とは数式が異なる、 synthesis § 6 確定式)
2. **q_force 動的計算** (`clamp(0.15 + 0.15 × max(0, 0.10 - feasible_ratio_ema)/0.10, 0.15, 0.30)`) — 旧 zenigame は固定値
3. **A→B 乖離自動引き上げ** (`q_force_max = 0.40`、 上限・戻し条件含む) — 旧 zenigame は監視のみ
4. **trade_count は trade_rate で評価** (絶対値判定なし、 hard floor は trades>=2 のみ) — synthesis § 5.1
5. **A-fail は完全排除** (Pareto 圧計算からも除外) — synthesis § 5.5

具体的な責務:

1. **gate_score 計算**: T061 `evaluate_canonical_five` で canonical 5 worst を計算、 `gate_score = 1 / (1 + worst_gap)` (旧 zenigame と同じ単調変換)
2. **hard_pass 判定**: invariant 違反個体 (T061 InvariantFlags.is_feasible=False) と trade_count<2 を排除
3. **世代内 top q_force% 選抜**: hard_pass 個体を gate_score 降順ソートし top-N
4. **q_force 動的計算 + A→B 乖離自動引き上げ**: state-ful controller で q_force_offset を管理
5. **A-pass / A-fail フラグ**: A-fail 個体は当世代の selection / archive 全段階から排除 (T065-T067 申し送り)

T063 は **stage 評価器 (= state-ful controller)** を提供する。 T061-T062 が pure stateless engine だったのに対し、 T063 は q_force_offset / A→B 乖離 EWMA など state を持つ。 T065 (NSGA-II) への組込は Phase 2。

## 前提検証 (C4) — current HEAD `main@ea56484` 基準

| 前提 | verified | 出典 |
|---|---|---|
| Stage A 評価期間 = 末尾 8w (recent proxy)、 T060 stage_a Period | ✓ | synthesis § 5.1 / § 4.3 / T060 設計 APPROVED |
| Stage A 評価指標 = canonical 5 worst gate_score (T061) | ✓ | synthesis § 5.1 |
| 通過判定 = 世代内 gate_score 降順 top q_force% (hard pass) | ✓ | synthesis § 5.1 |
| q_force 動的式 = `clamp(0.15 + 0.15 × max(0, 0.10 - feasible_ratio_ema)/0.10, 0.15, 0.30)` | ✓ | synthesis § 5.1 / § 17 |
| A→B 乖離時 q_force 自動引き上げ: 上限 0.40 / 0.02/Run / 戻し条件 corr>=0.5 | ✓ | synthesis § 8.7 |
| trade_count は trade_rate で評価、 hard floor = trades>=2 | ✓ | synthesis § 5.1 |
| A-fail は Pareto 圧計算からも除外、 archive にも入らない | ✓ | synthesis § 3 / § 5.5 |
| Stage A の gate_score は Stage A 専用ランキング (Stage B 以降は別評価値) | ✓ | synthesis § 5.5 |
| 既存 zenigame-fx は q_force 動的計算 + A→B 乖離自動引き上げを持たない | ✓ | grep `q_force` で hit なし |
| 既存 `stage_gate.py:evaluate_stage_a` は旧 Sharpe + complexity penalty 仕様 (canonical 5 worst なし) | ✓ | `stage_gate.py:6` (docstring) |

## 改善アイデア

### 設計方針 (Round 1 [Critical] 1, 3 反映で大幅改訂)

**「pure functions + immutable state pass-through」**:

1. **責務統合 (Round 1 [C1] 反映)**: T063 は **threshold 派生 + T061 呼出 + ranking** を一手に担う orchestrator + ranking。 T065 (NSGA-II) からは「個体 list を渡す → a_pass_indices を返す」 という high-level 契約で見える。 T061 を直接消費するのは T063 内部の責任。
2. **state immutability 厳守 (Round 1 [C3] 反映)**: controller class を**廃止**、 全 helper を pure function 化。 `evaluate_generation(state, inputs) -> (StageAResult, new_state)` の signature で state を引数 + 返値の両方に出す。 内部に state を持つ object を作らない。
3. **入力契約 (Round 1 [C1] 反映)**: 個体の **trade list / bar series / business_day_universe** + live_criteria + feasible_ratio_ema + divergence_state。 T061 の呼出は T063 内部、 caller は T061 を直接知らない。
4. **出力契約 (Round 1 [W4], [W5] 反映)**: `StageAResult` (a_pass_indices: frozenset[int], stats: StageAGateStats with threshold_score: float | None) + `new_state: StageAControllerState`。 default-deny 契約を docstring に明記

### Module 構造 (Round 1 [Critical] 1, 3 反映で大幅改訂、 controller class 廃止)

```
src/alpha_factory/stage_a_evaluator.py (新規、 T063 PR スコープ)
├── DataClasses (frozen)
│   ├── StageAControllerState — divergence_offset_steps (>= 0) + last_a_b_correlation (immutable)
│   ├── StageAIndividualInput — 1 個体の (trades, bars, business_day_universe) + index
│   ├── StageAGenerationInput — list[StageAIndividualInput] + feasible_ratio_ema + state
│   ├── StageAGateStats — 診断用 (gen, n_hard_pass, n_selected, q_force_*, threshold_score: float | None, divergence_offset_steps)
│   └── StageAResult — a_pass_indices: frozenset[int] + stats: StageAGateStats
├── Constants
│   ├── STAGE_A_WINDOW_DAYS = 56  # 8w 固定 (synthesis § 5.1 / T060 stage_a Period)
│   ├── BASELINE_DATASET_DAYS = 730  # 24m baseline = synthesis § 4.1 / live_criteria 想定スコープ
│   ├── Q_FORCE_BASE = 0.15
│   ├── Q_FORCE_RANGE = 0.15
│   ├── Q_FORCE_FEASIBLE_RATIO_THRESHOLD = 0.10
│   ├── Q_FORCE_BASE_MIN = 0.15
│   ├── Q_FORCE_BASE_MAX = 0.30
│   ├── Q_FORCE_DIVERGENCE_MAX = 0.40
│   ├── Q_FORCE_DIVERGENCE_STEP = 0.02
│   ├── Q_FORCE_DIVERGENCE_RECOVERY_CORRELATION = 0.5
│   ├── HARD_FLOOR_MIN_TRADES = 2
│   └── DIVERGENCE_OFFSET_STEPS_MAX = math.ceil((Q_FORCE_DIVERGENCE_MAX - Q_FORCE_BASE_MIN) / Q_FORCE_DIVERGENCE_STEP)
│         # Round 2 [W1] 反映: マジックナンバー回避、 定数から導出 (= ceil((0.40 - 0.15) / 0.02) = 13)
│         # 上限ガード: q_force_with_divergence の clamp により実効上限は 0.40 で保護
├── Helpers (pure functions)
│   ├── derive_stage_a_thresholds(live_criteria) -> CanonicalFiveThresholds
│   │     # synthesis § 5.1 「trade_rate 評価」 を実装、 trade_count_min/max を 8w 比例に変換
│   ├── compute_trade_rate_window_thresholds(live_min, live_max, mode="proportional") -> tuple[int, int]
│   │     # Decision Pending 解決 (Round 1 [W1] [W2]): proportional / rate_per_day / rate_per_week 3 mode
│   ├── compute_q_force_base(feasible_ratio_ema) -> float
│   ├── compute_q_force_with_divergence(base_q_force, divergence_offset_steps) -> float
│   │     # Round 1 [Critical] 2 反映: signed counter 廃止、 unsigned >= 0
│   ├── compute_gate_score(canonical_five_result) -> float  # = 1 / (1 + gate_worst_gap)
│   ├── is_hard_pass(canonical_five_result, trade_count, hard_floor_min_trades) -> bool
│   ├── select_top_q_force_indices(scores: list[tuple[int, float]], q_force: float) -> tuple[frozenset[int], float | None]
│   │     # Round 1 [W3] 反映: rounding 規約 deterministic 確定、 threshold_score (cutoff) を返す
│   ├── update_divergence_state(prev_state, corr: float) -> StageAControllerState
│   │     # Round 1 [Critical] 2 反映: pure function、 prev_state を変えず new_state を返す
│   └── evaluate_generation(state, inputs, *, evaluate_fn) -> tuple[StageAResult, StageAControllerState]
│         # Round 1 [Critical] 1, 3 反映: pure function 化、 evaluate_fn は dependency injection
│         # (test 時 mock 可能、 production で T061.evaluate_canonical_five を渡す)
└── (Controller class は廃止、 全て pure function)
```

### Stage A 用 thresholds の派生 (synthesis § 5.1 「trade_rate 評価」 の解釈)

**Round 1 [Critical] 1 反映**: `StageAThresholds` 独自 dataclass は**廃止**。 T063 は `derive_stage_a_thresholds(live_criteria)` で T061 の `CanonicalFiveThresholds` を直接構築する (Stage A 用にカスタマイズ済の T061 入力)。 caller は T061 を直接知らず、 T063 が T061 呼出も含めて Stage A 評価を完結させる。

#### Decision Pending 解決 (Round 1 [Critical] 4 / [Warning] 1, 2 反映、 Round 2 で議論)

3 つの Decision Pending を概念設計内で**先取り解決**する (本 PR で確定、 必要なら Round 2 でユーザ判断):

**Decision 1: trade_rate denominator (Round 1 [W1])**

| 候補 | denominator | 8w window での trade_count_min 換算 |
|---|---|---|
| **採用案 (proportional)** | `live_criteria_dataset_days` (730 days、 24m baseline) | `ceil(50 * 56 / 730) = 4` |
| 候補 B (per-tradable-day) | tradable days (~252 / year * 24m / 12m = 504) | `ceil(50 * (52*5/(8*5)) / (504/56)) = ...` (複雑) |
| 候補 C (per-week) | weeks | `ceil(50 * 8 / 104) = 4` |

採用根拠: synthesis § 5.1 は「trade_rate で評価」 と書くだけで denominator 明示なし。 計算簡潔性 + live_criteria.trade_count_min が「24m dataset 内の総 trade 数」 という解釈で proportional が最も整合 (24m dataset → 8w window scale)。 **C8: INCONCLUSIVE** だが proportional で先行確定、 smoke 後再校正候補。

**Decision 2: net_pnl_min window-aware (Round 1 [Critical] 4 / Round 2 [W2])**

| 候補 | Stage A 8w で使う net_pnl_min | リスク |
|---|---|---|
| **採用案 (proportional)** | `live_criteria.total_pnl_min * 56 / 730 = 50000 * 56/730 ≈ 3836 JPY` | mission stringency 緩和 |
| 候補 B (full mission) | `50000 JPY` (24m そのまま) | worst_gap が PnL 軸支配で「短期 PnL 未達ランキング」 化 (Round 1 [C4]) |

採用根拠 (Round 2 [W2] 反映で synthesis § 5.4 対応を明示): candidate B (full mission) は Stage A の 8w window で `worst_gap` がほぼ常に PnL 軸支配となり、 「canonical 5 の近接度」 ではなく「短期 PnL 未達量ランキング」 に偏る (Stage A の役割は Stage B 進出候補抽出の proxy)。 candidate A (proportional) は mission stringency を弱めるが、 **synthesis § 5.4 で Stage C が「12w contiguous holdout + spread stress + cross-pair shadow validation で live_criteria 4 指標全達成 + stress pass + cross_pair pass = mission_pass」** と確定しており、 mission stringency は Stage C で確保される。 Stage A は proxy として「直近 8w の達成余裕」 を測る役割。 **proportional が筋**。 INCONCLUSIVE タグで smoke 後再校正候補。

**Decision 3: top q_force% rounding (Round 1 [W3] / Round 2 [Critical])**

```python
# 採用案 (Round 2 [Critical] 反映、 空集合ケース対応):
if n_hard_pass == 0:
    target_n = 0  # 空集合 (threshold_score = None)
else:
    target_n = max(1, int(n_hard_pass * q_force))  # zenigame 同等 (floor + 最低 1)
```

採用根拠: zenigame の標準 (`max(1, int(...))` = floor + 最低 1) を採用しつつ、 `n_hard_pass=0` の世代で「1 件選抜」 が発生する矛盾を回避 (Round 2 [Critical] 指摘)。 deterministic、 上限引き上げ余地は q_force 動的化で吸収。

**Decision 4: trade_count_max_window rounding (Round 1 [W2])**

```python
trade_count_min_window = max(1, ceil(live_min * window_ratio))  # 下限は ceil で「下回らない」
trade_count_max_window = floor(live_max * window_ratio)         # 上限は floor で「上回らない」
```

採用根拠: 下限 ceil で「最低 N 取引」 を厳格化、 上限 floor で「最大 N 取引」 を厳格化、 直感整合。

#### derive_stage_a_thresholds の signature

```python
def derive_stage_a_thresholds(
    live_criteria: dict,  # config.alpha_factory.live_criteria
    window_days: int = STAGE_A_WINDOW_DAYS,  # 56 default
    baseline_dataset_days: int = BASELINE_DATASET_DAYS,  # 730 default
) -> CanonicalFiveThresholds:
    """synthesis § 5.1 / Decision 1, 2, 4 に従い T061 thresholds を構築.

    前提ガード (Round 2 [Suggestion] 2 反映、 詳細設計で実装):
        - baseline_dataset_days > 0
        - window_days > 0
        - window_days <= baseline_dataset_days
        - live_criteria.trade_count_max >= live_criteria.trade_count_min
        - live_criteria の必須 keys 存在 (sharpe_min, total_pnl_min, max_drawdown_max,
          trade_count_min/max, win_rate_min)
        - 違反時は ValueError raise (caller=T065 の orchestration bug indicator)

    Returns:
        CanonicalFiveThresholds:
            - sharpe_min: live_criteria.sharpe_min (annual scale、 T061 内部で換算)
            - net_pnl_min: live_criteria.total_pnl_min * (window_days / baseline_dataset_days)
            - max_dd_max: live_criteria.max_drawdown_max (window 比例しない、 instantaneous)
            - trade_count_min: max(1, ceil(live_criteria.trade_count_min * window_days / baseline_dataset_days))
            - trade_count_max: floor(live_criteria.trade_count_max * window_days / baseline_dataset_days)
            - win_rate_min: live_criteria.win_rate_min (Phase 2 で追加された field、 instantaneous、 window 比例しない)
    """
```

### q_force 動的計算 (Round 1 [Critical] 2 反映、 signed counter 廃止)

```python
def compute_q_force_base(feasible_ratio_ema: float) -> float:
    """synthesis § 5.1 確定式: q_force_base = clamp(0.15 + 0.15 × max(0, 0.10 - ratio)/0.10, 0.15, 0.30).

    feasible_ratio_ema 高い (>= 0.10) → q_force = 0.15 (探索集中)
    feasible_ratio_ema 低い (< 0.10) → q_force 引き上げ (供給確保)
    feasible_ratio_ema = 0.0 → q_force = 0.30 (最大供給)
    """
    deficit = max(0.0, Q_FORCE_FEASIBLE_RATIO_THRESHOLD - feasible_ratio_ema)
    raw = Q_FORCE_BASE + Q_FORCE_RANGE * (deficit / Q_FORCE_FEASIBLE_RATIO_THRESHOLD)
    return clamp(raw, Q_FORCE_BASE_MIN, Q_FORCE_BASE_MAX)


def compute_q_force_with_divergence(
    base_q_force: float,
    divergence_offset_steps: int,  # >= 0、 unsigned counter (Round 1 [C2] 反映)
) -> float:
    """synthesis § 8.7 確定式: A→B 乖離時に q_force_offset を加算.

    divergence_offset_steps: A→B 乖離 cycle counter (unsigned >= 0)
    - 0: 正常 (q_force = base のみ)
    - > 0: 乖離中 or 回復中の current step 数。 q_force = base + 0.02 × steps (上限 0.40)

    state update は別関数 update_divergence_state(state, corr):
    - corr < 0.5 (乖離継続): steps += 1 (clamp [0, DIVERGENCE_OFFSET_STEPS_MAX])
    - corr >= 0.5 (回復): steps -= 1 (min 0 で停止)

    Returns:
        min(base_q_force + 0.02 × divergence_offset_steps, Q_FORCE_DIVERGENCE_MAX=0.40)
    """
    if divergence_offset_steps < 0:
        raise ValueError(
            f"divergence_offset_steps must be >= 0 (unsigned): {divergence_offset_steps}"
        )
    offset = Q_FORCE_DIVERGENCE_STEP * divergence_offset_steps
    raw = base_q_force + offset
    return min(raw, Q_FORCE_DIVERGENCE_MAX)


def update_divergence_state(
    prev_state: StageAControllerState,
    corr: float,
) -> StageAControllerState:
    """A→B 乖離 corr を受け取り new_state を返す pure function (Round 1 [C2] / [C3] 反映).

    Args:
        prev_state: 前 Run 終了時の state (immutable)
        corr: corr(A_proxy_score, B_pooled_score)、 [-1, 1]

    Returns:
        new_state with:
        - divergence_offset_steps:
            corr < Q_FORCE_DIVERGENCE_RECOVERY_CORRELATION (= 0.5):
                clamp(prev.divergence_offset_steps + 1, 0, DIVERGENCE_OFFSET_STEPS_MAX)
            else (corr >= 0.5):
                max(0, prev.divergence_offset_steps - 1)
        - last_a_b_correlation: corr

    state は immutable: prev_state を変えず new instance を返す。
    """
```

### gate_score + hard_pass 判定

```python
def compute_gate_score(canonical_five_result: CanonicalFiveResult) -> float:
    """synthesis § 5.1: gate_score = 1 / (1 + worst_gap).

    worst_gap = canonical_five_result.gate_worst_gap
    - 全達成 → worst_gap=0 → gate_score=1.0 (max)
    - 1 指標未達 → worst_gap>0 → gate_score < 1.0
    - infeasible → gate_score 計算は不可、 caller (is_hard_pass) で別途排除
    """
    return 1.0 / (1.0 + canonical_five_result.gate_worst_gap)


def is_hard_pass(
    canonical_five_result: CanonicalFiveResult,
    trade_count: int,
    hard_floor_min_trades: int = HARD_FLOOR_MIN_TRADES,
) -> bool:
    """synthesis § 5.1 hard floor 判定: invariant feasible AND trades >= 2.

    Args:
        canonical_five_result: T061 評価結果
        trade_count: 当該個体の trade_count (T061 内に含まれる)
        hard_floor_min_trades: synthesis § 5.1 の「trades>=2」、 default 2

    Returns:
        True if invariant feasible AND trade_count >= hard_floor_min_trades
    """
    return (
        canonical_five_result.invariants.is_feasible
        and trade_count >= hard_floor_min_trades
    )
```

### State + evaluate_generation API (Round 1 [Critical] 1, 2, 3 反映、 controller class 廃止)

```python
@dataclass(frozen=True)
class StageAControllerState:
    """Stage A controller state — Run 跨ぎ persistence (immutable).

    field:
    - divergence_offset_steps: A→B 乖離 cycle counter (unsigned >= 0、 Round 1 [C2] 反映)
        - 0: 正常 (q_force = base のみ)
        - > 0: 乖離中 or 回復中の current step 数 (clamp [0, DIVERGENCE_OFFSET_STEPS_MAX])
    - last_a_b_correlation: 直近 Run の corr(A_proxy_score, B_pooled_score)、 戻し条件判定用
        - None for initial state
    """
    divergence_offset_steps: int   # unsigned (>= 0)
    last_a_b_correlation: float | None

    @classmethod
    def initial(cls) -> "StageAControllerState":
        """初期 state (divergence_offset_steps=0, last_corr=None)."""
        return cls(divergence_offset_steps=0, last_a_b_correlation=None)


def evaluate_generation(
    state: StageAControllerState,
    inputs: StageAGenerationInput,
    *,
    evaluate_fn: Callable[..., CanonicalFiveResult],  # T061.evaluate_canonical_five を注入
    live_criteria: dict,
) -> tuple[StageAResult, StageAControllerState]:
    """1 世代の Stage A 評価 — pure function (Round 1 [C1], [C3] 反映).

    手順:
    1. derive_stage_a_thresholds(live_criteria) で T061 用 thresholds を構築 (Decision 1, 2, 4 反映)
    2. 各 individual_input について:
        cf_result = evaluate_fn(trades, bars, thresholds, business_day_universe, ...)
        is_hard_pass(cf_result, trade_count) を判定
    3. hard_pass のみ gate_score = compute_gate_score(cf_result) で計算
    4. q_force_base = compute_q_force_base(inputs.feasible_ratio_ema)
       q_force = compute_q_force_with_divergence(q_force_base, state.divergence_offset_steps)
    5. (a_pass_indices, threshold_score) = select_top_q_force_indices(scores, q_force)
    6. StageAGateStats を構築 (gen, n_hard_pass, n_selected, q_force_*, threshold_score, divergence_offset_steps)
    7. (StageAResult, state) を返す (state は変更しない、 next Run の update_divergence_state で更新)

    Note: state は本関数では変更しない (世代内 ranking で完結)。 Run 終了時に
    別途 update_divergence_state(state, corr) で new_state を取得する。

    Args:
        state: 前 Run 終了時の state (initial() で初期 state 取得)
        inputs: 1 世代の評価入力 (個体 list + feasible_ratio_ema)
        evaluate_fn: T061 評価関数の dependency injection (test 時 mock 可)
        live_criteria: config から渡される live_criteria dict (sharpe_min, total_pnl_min,
            max_drawdown_max, trade_count_min/max, win_rate_min)

    Returns:
        (StageAResult, state): state は本関数では変更しないので prev_state をそのまま返す
        (caller が update_divergence_state で別途 new_state を取得する責務、 Phase 2 申し送り)
    """
```

**default-deny 契約 (Round 1 [W4] / Round 2 [W3] 反映)**:
- T063 出力を消費する T065 NSGA-II 等 caller は **a_pass_indices に含まれない個体を既定で棄却**する責務を負う
- T063 は a_fail_indices を返さない (a_pass_indices の補集合として caller が暗黙に扱う)
- docstring + Phase 2 申し送りで明示
- **検証観点 (Round 2 [W3] 反映)**: T065 PR DoD に「a_pass_indices の補集合が Pareto 圧計算 / archive admission に含まれていないことを test で確認」 を追加。 例: `test_a_fail_individual_excluded_from_nsga_selection`、 `test_a_fail_individual_excluded_from_archive_admission`

**Index 安定性 (Round 2 [Suggestion] 1 反映)**:
- `evaluate_generation` は `inputs.individuals[i].index == i` を前提とする (caller が deterministic に index を付与)
- `a_pass_indices` 内の int は `inputs.individuals` の同 index 個体に対応
- 並列評価導入時 (T070 backtest engine) は parallel-safe な index 維持を caller の責務とする (T065 申し送り)

### 出力契約 (Round 1 [W4], [W5] 反映)

```python
@dataclass(frozen=True)
class StageAGateStats:
    """診断用 stats (T071 observability で消費)."""
    generation: int
    n_hard_pass: int
    n_selected: int
    q_force_base: float                # feasible_ratio_ema からの計算値
    q_force_with_divergence: float     # divergence offset 加算後 (= 実際に使用された q_force)
    divergence_offset_steps: int       # Round 1 [C2] 反映: unsigned counter
    threshold_score: float | None      # 選抜境界の gate_score (cutoff)、 空集合時 None (Round 1 [W5])
    min_selected_score: float | None
    max_selected_score: float | None


@dataclass(frozen=True)
class StageAResult:
    """1 世代の Stage A 評価結果.

    default-deny 契約 (Round 1 [W4] 反映):
    - **a_pass_indices に含まれない個体は selection / archive 全段階から既定で棄却される**
    - T063 は a_pass_indices のみ返す。 a_fail_indices は補集合として caller が暗黙に扱う
    - T065 NSGA-II の constrained-domination 実装で「a_fail 個体は Pareto 圧計算に含めない」
      ことを保証する責務 (Phase 2 申し送り、 T065 PR DoD)
    """
    a_pass_indices: frozenset[int]
    stats: StageAGateStats
```

### 重要な設計判断 (Round 1 修正反映)

**1. T063 が threshold 派生 + T061 呼出 + ranking を一手に担う (Round 1 [Critical] 1 反映)**

- **採用**: T063 は orchestrator 兼 ranking。 caller (T065) は T061 を直接知らず、 T063 が個体毎に T061 を呼ぶ
- **理由**: 旧設計 (CanonicalFiveResult を input に取る) は「T063 が後から threshold を変えられない」 矛盾を生む。 trade_rate / net_pnl の Stage A 用カスタマイズは T063 内部で完結させる必要
- **代替案 (棄却)**: threshold 派生を T065 orchestrator に寄せ T063 を ranking のみに縮退 → T065 と responsibility 分散、 「Stage A 評価器」 という名前と機能が乖離

**2. trade_rate 評価の実装方針 (synthesis § 5.1)**

- **採用**: `derive_stage_a_thresholds(live_criteria)` で T061 thresholds を Stage A 用 (8w 比例) に派生
- **Decision 1 (proportional)**: `trade_count_*_window = round(live_criteria.trade_count_* × window_days / baseline_dataset_days)`
- **Decision 2 (proportional)**: `net_pnl_min_window = live_criteria.total_pnl_min × window_days / baseline_dataset_days`
- **Decision 4 (asymmetric rounding)**: 下限 ceil、 上限 floor

**3. hard floor (trades>=2) の独立判定**

- **採用**: T063 内 `is_hard_pass(result, trade_count, hard_floor=2)` で判定、 T061 thresholds の trade_count_min とは独立
- **理由**: synthesis § 5.1 「絶対値判定なし、 trades>=2 の破綻排除のみ」 を素直に実装

**4. State immutability (Round 1 [Critical] 3 反映、 controller class 廃止)**

- **採用**: `StageAControllerState` は immutable frozen dataclass、 全 helper / `evaluate_generation` は pure function。 `evaluate_generation(state, inputs, *, evaluate_fn) -> (StageAResult, new_state)` で state を引数 + 返値の両方に出す
- **理由**: 「state は immutable」 と「controller が破壊的更新」 は両立不能。 純粋関数化で test 容易性 + state 一貫性確保
- **代替案 (棄却)**: controller class 内部で state を持つ → immutable 方針と矛盾

**5. divergence_offset_steps を unsigned counter に単純化 (Round 1 [Critical] 2 反映)**

- **採用**: `divergence_offset_steps: int >= 0`、 `update_divergence_state(state, corr)` で +1 (corr<0.5) or -1 (corr>=0.5、 min 0)
- **理由**: signed counter の semantic は「乖離中=+ / 回復中=-」 が分かりにくく、 update 式と整合しなかった (Round 1 [C2])。 unsigned で「現在の引き上げ step 数」 として直観整合

**6. A-fail の完全排除は default-deny 契約 (Round 1 [W4] 反映)**

- **採用**: T063 は `a_pass_indices: frozenset[int]` のみ返し、 docstring に「caller は a_pass_indices に含まれない個体を既定で棄却する責務」 を明記
- **理由**: T065 で「A-fail 個体は Pareto 圧計算から除外」 を別経路で実装する責務 (Phase 2 申し送り)。 redundant な flag を返さない

**7. A→B 乖離 corr 計算の責務分離**

- **採用**: T063 は `update_divergence_state(prev_state, corr)` で external に corr を受け取る、 corr 計算自体は別 module (T071 observability)
- **理由**: T063 は Stage A 専用評価器、 B-pooled 結果との相関計算は cross-stage 責務 (T064 出力との結合)
- **代替案 (棄却)**: T063 内で corr 計算 → T064 出力への直接依存が発生、 cross-module 結合度上昇

**8. 世代内ランキング (vs Run 跨ぎ ranking)**

- **採用**: zenigame と同じ世代内ランキング (`evaluate_generation` 単位で完結)
- **理由**: synthesis § 5.1 / zenigame `stage_a_gate.py:1-11` で「世代間統計は phase ラグ要因」 と確立済

## 期待効果

### live_criteria 達成への構造的貢献

- **canonical 5 worst gate の Stage A 適用**: 旧 zenigame-fx の Sharpe + complexity penalty 経路を全廃、 5 指標全達成圧を Stage A で実現
- **q_force 動的計算で fail-soft**: feasible 個体率が低下しても自動で供給確保、 cycle 全滅防止
- **A→B 乖離自動補正**: A_proxy が B_pooled と乖離した時、 q_force 自動引き上げで Stage B 進出個体を確保 (warn-only ではなく自動補正、 synthesis § 19 #4 逆輸入候補)
- **trade_rate 評価でイントラデイ短期戦略の通過**: hard floor は trades>=2 のみ、 短い 8w window でも適切に評価

### 副次効果

- **T065-T067 の実装簡素化**: GA selection が `StageAResult.a_pass_indices` を消費するだけで Stage B 進出個体を確定可能
- **T071 observability**: `StageAGateStats` で各世代の q_force / threshold_score / divergence_cycle を時系列記録可能

## 実装方針 (概要)

### コンポーネント変更 (Phase 1: T063 PR)

| ファイル | 変更内容 |
|---|---|
| `src/alpha_factory/stage_a_evaluator.py` | **新規作成**。 5 dataclass + Controller class + helper 関数群 + Constants |
| `tests/alpha_factory/test_stage_a_evaluator.py` | **新規**。 q_force 動的計算 / divergence 自動引き上げ / hard floor / 世代内 ranking / state 不変性 / 4 代表ケース |

**Phase 1 (T063 PR) スコープは上記 2 施策のみ**。 既存 `stage_gate.py:evaluate_stage_a` への置換は **Phase 2 (T065 統合と同時)** で実施。 T063 PR 単独では既存経路に touch しない。

### Phase 2 (T065 統合と同時、 別 PR) 申し送り

T063 完了後、 GA / runner が T063 controller を消費する形に置換する必要がある。

| # | ファイル / 箇所 | 変更内容 | 担当 |
|---|---|---|---|
| 1 | `src/alpha_factory/stage_gate.py:evaluate_stage_a` | **全廃** (旧 Sharpe + complexity penalty 経路)、 caller を T063 `StageAGateController` に置換 | T065 |
| 2 | (新規) `src/alpha_factory/ga/stage_a_orchestrator.py` | T065 NSGA-II loop が T061 → T063 controller を呼ぶ orchestration | T065 |
| 3 | `scripts/alpha_factory/run_ga.py` (該当箇所) | per-generation で T063 controller を持ち、 evaluate_generation を呼ぶ | T065 |
| 4 | (新規) `src/alpha_factory/observability/a_b_divergence.py` | corr(A_proxy_score, B_pooled_score) を Run 終了時に計算、 T063 に注入 | T071 |
| 5 | `src/alpha_factory/config.py:StageGateConfig` | 旧 `stage_a.{target_pass_rate, alpha, threshold, calibrate.*, min_exposure_trade_count}` 全廃、 `stage_a_window_days: int = 56` のみ残す (8w 固定) | T065 |
| 6 | `config/alpha_factory/default.yaml` | 旧 `stage_gate.stage_a.*` 全廃、 `stage_gate.stage_a.window_days: 56` のみ | T065 |
| 7 | `src/alpha_factory/archive.py` (該当箇所) | A-fail 個体を archive admission 全段階から排除 | T067 |
| 8 | T063 controller state の persistence (`divergence_cycle_count`, `last_a_b_correlation`) を archive metadata or run cache に保存 | T067 |

### C2 parallel-path 確認 (Phase 1 DoD、 T062 同様 5 段階)

1. 直 import: `grep -rn "from src.alpha_factory.stage_a_evaluator" scripts/ src/ tests/` → 自身 + tests のみ
2. `import as` alias: `grep -rn -E "import\s+src\.alpha_factory\.stage_a_evaluator" src/ scripts/ tests/` → 自身 + tests のみ
3. relative import: `grep -rn -E "from\s+\.+\s*stage_a_evaluator" src/ scripts/ tests/` → 自身 + tests のみ
4. 再エクスポート: `grep -rn "stage_a_evaluator" src/alpha_factory/__init__.py src/alpha_factory/*.py | grep -v "src/alpha_factory/stage_a_evaluator.py:"` → 0 hit
5. runtime シンボル: `grep -rn -E "StageAGateController|evaluate_generation|StageAResult" src/alpha_factory/stage_gate.py src/alpha_factory/swim_lane.py scripts/alpha_factory/run_ga.py` → 0 hit

## C3 / C7 適用

- **C3 (Collider bias)**: 該当なし (世代内 ranking + 動的 q_force 計算のみ、 相関分析を新規導入しない)
- **C7 (Sample size)**:
  - q_force 動的計算で feasible_ratio_ema を使うが、 これは run-level で十分 sample (各 Run 12,288 評価 = pop 192 × gen 64) → C7 適用範囲内
  - A→B 乖離 corr は run-level の 1 数値 (run 内全 individual の (A_proxy, B_pooled) ペア集計) → 各 Run で n>=192 (pop) で C7 OK
  - hard floor (trades>=2) は absolute 値で、 sample size 依存なし

## 制約・前提

- **T061 マージ後前提**: T063 は `from src.alpha_factory.canonical_metrics import CanonicalFiveResult` で T061 module を import
- **T060 Period 認識**: Stage A 評価期間 = 8w 固定 (T060 stage_a Period の length)、 T060 提供 Period dataclass を直接消費しないが、 期間長 (56 days) を constants で固定
- **state 管理は immutable dataclass**: state は常に new instance を生成 (mutability 排除)
- **synthesis § 5.1 確定値厳密準拠**: q_force 式 / 0.40 上限 / trades>=2 hard floor / 0.02 step / corr 0.5 戻し条件
- **A-fail の完全排除は T065 申し送り**: T063 は a_pass_indices を返すのみ、 排除実装は T065 責務

## スコープ外

- T058-T062: 依存先 (Schema v2 / EpochManager / Partition+Fold / canonical 5 / mission_inf_gap)
- T064: Stage B/C-lite/C evaluator (B/C 用評価器、 T063 と並列だが別 module)
- T065-T066: NSGA-II + CPPS (T063 controller を消費)
- T067: Loop closure (T063 controller state の persistence + archive 排除)
- T070: backtest engine の TradeRecord 生成 (T061 入力契約)
- T071: observability (corr(A_proxy, B_pooled) 計算、 T063 update_a_b_divergence に注入)

## 学術引用 / 先行知見

- synthesis § 5.1 / § 5.5 / § 8.7 / § 17 / § 19 #4: Stage A hard gate / q_force 動的計算 / A→B 乖離自動引き上げ / 用語 / 逆輸入候補
- zenigame `ga/nsga2/stage_a_gate.py` (`StageAGateController`): 世代内 ranking 選択の元実装。 fx 側は **q_force 動的化 + A→B 乖離自動引き上げ** を新規追加
- zenigame `ga/nsga2/optimize.py:950, 1006/1195`: GA optimize loop での Stage A pass 経路 (Phase 2 で T065 が再実装)
- T061 詳細設計 APPROVED: canonical 5 worst gate_score の上位 contract
- T062 詳細設計 APPROVED: mission_inf_gap engine (T063 では使わないが、 後段 GA で使用)

## Round 1 → Round 2 の改訂点 (Codex review 反映サマリ)

| Round 1 [Critical/Warning/Suggestion] | 修正対応 |
|---|---|
| [C1] T061 依存契約 (CanonicalFiveResult input) と StageAThresholds 派生責務の衝突 | T063 を **threshold 派生 + T061 呼出 + ranking を一手に担う orchestrator** に再定義。 入力契約を `(individuals, feasible_ratio_ema, state, evaluate_fn, live_criteria)` に変更、 `StageAThresholds` 独自 dataclass 廃止 (`derive_stage_a_thresholds(live_criteria) -> CanonicalFiveThresholds` で T061 入力構築) |
| [C2] divergence_cycle_count signed semantic と更新式の整合性なし | **signed counter を撤廃**、 `divergence_offset_steps: int >= 0` (unsigned) に単純化。 update: corr<0.5 で +1 (clamp upper)、 corr>=0.5 で -1 (clamp >= 0) |
| [C3] immutable state 方針と controller API の矛盾 | **controller class 廃止**、 全 helper を pure function 化。 `evaluate_generation(state, inputs) -> (StageAResult, new_state)` で immutable 一貫 |
| [C4] net_pnl_min window-aware が未確定で worst_gap ranking に流すリスク | **proportional 採用 (Decision 2)**: `net_pnl_min_window = live * 8/104 ≈ 3836`。 stringency は Stage C で確保される根拠を明記 (synthesis § 5.4)。 INCONCLUSIVE タグで smoke 後再校正候補 |
| [W1] trade_rate denominator 仕様化 | **proportional 採用 (Decision 1)**: `live_criteria_dataset_days=730 (24m baseline)` で割る。 calendar day / tradable day / per-week 候補を比較した上で proportional 採用 |
| [W2] trade_count_max_window で ceil が不自然 | **下限 ceil + 上限 floor (Decision 4)**: 下限は「下回らない」、 上限は「上回らない」 で直感整合 |
| [W3] top q_force% の N 算出規則未定義 | **Decision 3**: `target_n = max(1, int(n_hard_pass * q_force))` (zenigame 同等、 floor + 最低 1) |
| [W4] StageAResult が a_pass_indices のみで default-deny 漏れ | docstring に **default-deny 契約**: 「caller は a_pass_indices 外を既定で棄却する責務」 を明記。 T065 PR DoD 申し送り |
| [W5] threshold_score を float 固定だと空集合表現不能 | `threshold_score: float \| None` に変更 |
| [S1] state を unsigned `divergence_offset_steps: int` に単純化 | [C2] と統合済 |
| [S2] T063 責務を 2 分割 (threshold derive vs evaluate_generation) | [C1] 解決として「同一 module 内で 2 関数に分離」、 ただし caller からは evaluate_generation だけ見えれば良い (high-level API) |
| [S3] Decision Pending を本文に明示 | 4 つの Decision (1-4) を本概念設計内で先取り解決、 INCONCLUSIVE タグで smoke 後再校正候補化 |

## 残論点 (Round 2 以降で議論可能)

1. **state persistence (T067 申し送り)**: T063 PR では state を file 化しない、 in-memory のみ。 Run abort 時の state lost を許容するか
2. **corr(A_proxy, B_pooled) の計算源 (T071 申し送り)**: A_proxy = stage_a の gate_score、 B_pooled = stage_b の gate_score、 これらの値を per-individual で記録する必要 (T058 schema v2 接続候補)
3. **`evaluate_fn` dependency injection の使い分け**: production で T061.evaluate_canonical_five、 test で mock。 Phase 2 で T065 が production 経路を確定する責務
4. **smoke 後再校正候補 (synthesis § 15 追記候補)**: Decision 1 (trade_rate denominator)、 Decision 2 (net_pnl_min window-aware)、 Decision 3 (top-N rounding) — 全て smoke 観測で別解釈に切替する余地
