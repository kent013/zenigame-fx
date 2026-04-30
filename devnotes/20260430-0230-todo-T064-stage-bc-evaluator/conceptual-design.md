# 概念設計: T064 — Stage B + C-lite + C evaluator

**Round 1 修正反映** (Codex CHANGES_REQUESTED → CHANGES_APPLIED): 5 Critical 全対応。
- spread stress placeholder で嘘の stress_pass を返さない → `StagePassStatus` Enum (PASS / FAIL / PENDING) で tri-state、 PENDING 時 mission_pass=PENDING
- Stage B infeasible 個体の Pareto 軸混入防止 → `is_feasible_invariant=False` 時に `b_pooled_cf_result` を None (downstream 識別) + BCEvaluationResult 契約で「Pareto 軸として使用可能なのは feasible 個体のみ」 明記
- pooled OOS fold 境界規約 → `build_pooled_oos_input()` (raw concat ではない builder) で fold 境界 aware の trade/bar/equity series 連結契約を確定 (fold.test 非重複・時系列順 + bar/equity boundary-aware 再構成)
- cross-pair 母集団 → anchor を cross-pair 集計に**含めない**、 **shadow 5 pair (anchor 除く)** で全通過要求
- A→B 乖離 corr score source → T064 で「higher is better に正規化した単一スカラー (= -gate_worst_gap or gate_score=1/(1+gap))」 を確定

## 背景・課題

synthesis § 5.2 / § 5.3 / § 5.4 で確定した **Stage B (5 fold pooled WF-OOS gate) / Stage C-lite (3 disjoint windows × 15 セル worst) / Stage C (12w + spread stress + cross-pair)** は selection cascade の主判定層。 Stage A 通過個体に対し:

1. **Stage B**: 62w を 5 fold rolling-origin で分割し pooled OOS で canonical 5 worst aggregation。 **GA 主選抜 (Pareto 3 軸) は B-pooled 指標で計算** (synthesis § 3 確定)
2. **Stage C-lite**: 3 disjoint 6w windows × canonical 5 worst → **15 セル worst** で評価、 全窓 AND (mission_pass) または **top 30% 強制通過** (sample size 不足時の cycle 健全性)、 `progress_pass = 2/3 windows`
3. **Stage C**: 12w contiguous holdout + spread stress (×1.5) + cross-pair shadow validation (5 通貨) → mission_pass 確定
4. **A→B 乖離計算**: T063 update_divergence_state に注入する `corr(A_proxy_score, B_pooled_score)` を Run 終了時計算 (T071 申し送りだが、 source data は T064 が産出)
5. **invariant fold fail-fast**: Stage B で 1 fold でも違反なら infeasible 確定
6. **shadow_robustness_score**: archive CA #6 (synthesis § 8.3) で消費される cross-pair 通過強度

これは M2 最大の TODO。 3 stage の評価ロジック + cross-pair shadow + spread stress を一手に扱う。

## 前提検証 (C4) — current HEAD `main@ea56484` 基準

| 前提 | verified | 出典 |
|---|---|---|
| Stage B 評価期間 = 62w (T060 stage_b Period)、 5 fold rolling-origin | ✓ | synthesis § 4.4 / § 5.2 / T060 設計 APPROVED |
| Stage B 主判定 = 5 fold 連結 pooled OOS の canonical 5 worst aggregation | ✓ | synthesis § 5.2 |
| Stage B 補助 = 各 fold invariant fail-fast (1 fold 違反で infeasible 確定) | ✓ | synthesis § 5.2 |
| GA 主選抜 (Pareto 3 軸) は **B-pooled** 指標で計算 (Round 19 確定) | ✓ | synthesis § 3 / § 21 |
| Stage C-lite 評価期間 = 6w × 3 disjoint temporal windows | ✓ | synthesis § 4.3 / § 5.3 / T060 c_lite_1/2/3 |
| Stage C-lite 評価指標 = 各 window canonical 5 worst → **15 セル worst** | ✓ | synthesis § 5.3 |
| Stage C-lite 通過 = 全窓 AND (mission_pass) または **top 30% 強制通過** | ✓ | synthesis § 5.3 |
| progress_pass = 2/3 windows pass (synthesis § 5.3 / § 8.2) | ✓ | synthesis § 5.3 / § 8.2 |
| Stage C 評価期間 = 12w contiguous holdout | ✓ | synthesis § 4.3 / § 5.4 / T060 stage_c |
| Stage C 評価指標 = live_criteria 4 指標全達成 + spread stress (×1.5) + cross-pair shadow (5 通貨) | ✓ | synthesis § 5.4 |
| Stage C 通過 = live_criteria AND + stress pass + cross_pair pass = mission_pass | ✓ | synthesis § 5.4 |
| spread_consumption_ratio は tie-break + monitor (gate 圏外) | ✓ | synthesis § 6.7 |
| cross-pair shadow score = validation axis + archive metadata (selection 圧から除外) | ✓ | synthesis § 6.7 |
| 既存 zenigame-fx は 5 fold pooled / 15 セル worst / cross-pair shadow を新仕様で持たない | ✓ | grep 確認 |

## 改善アイデア

### 設計方針

**「3 stage 並列実装、 共通 helper を抽出、 pure function 化」**:

1. **module 分割の是非**: 3 stage を 1 module で扱うか、 3 module に分けるか
   - **採用**: 1 module `stage_bc_evaluator.py` で 3 stage を扱う (共通 helper の重複回避、 import 関係単純化)
   - 代替案 (棄却): 3 module 分離 → 共通 helper の DRY が困難、 import 関係複雑化
2. **入力契約**: Stage A pass 個体 (T063 a_pass_indices) の trades / bars / business_day_universe + T060 Partition + T060 Folds + cross-pair pair list
3. **出力契約**: 3 stage 各々の Result dataclass + mission_pass 集約フラグ + B-pooled CanonicalFiveResult (GA 主選抜用)
4. **責務分離**: T061 evaluate_canonical_five を消費、 T062 evaluate_mission_inf_gap を内部 metadata として使用
5. **A→B 乖離計算**: T064 で `compute_a_b_correlation(a_proxy_scores, b_pooled_scores) -> tuple[float, int]` (corr + sample_size) を提供。 caller (T065/T071) が T063 update_divergence_state に注入

### Module 構造 (Round 1 全 Critical 反映で大幅改訂)

```
src/alpha_factory/stage_bc_evaluator.py (新規、 T064 PR スコープ)
├── Enum
│   └── StagePassStatus — PASS / FAIL / PENDING (Round 1 [Critical] 1 / [Suggestion] 1 反映)
├── DataClasses (frozen)
│   ├── StageBFoldResult — 1 fold の cf_result + is_feasible_invariant
│   ├── StageBResult — b_pooled_cf_result: CanonicalFiveResult | None (Round 1 [C2]) + per_fold + invariant_fail_fast
│   ├── StageCLiteWindowResult — 1 window の cf_result
│   ├── StageCLiteResult — 3 windows + cells_worst + mission_pass: StagePassStatus / progress_pass: StagePassStatus + sample_size_flag (Round 1 [W5])
│   ├── PairBacktestBundle — pair 別 (Round 1 [Suggestion] 4): pair / genome_id / config_hash / partition_label / trades / bars / business_day_universe
│   ├── StageCResult — 12w cf_result + stress_cf_result | None + per_pair_results: dict[str, CanonicalFiveResult] +
│   │     stress_pass: StagePassStatus + cross_pair_pass: StagePassStatus + mission_pass: StagePassStatus +
│   │     shadow_robustness_score: float | None (Round 1 [W3])
│   ├── BCEvaluationInput — 1 個体の (trades, bars, business_day_universe, partition, folds, shadow_pairs: dict[str, PairBacktestBundle])
│   └── BCEvaluationResult — 全 stage 統合 (b_result, c_lite_result, c_result, mission_pass: StagePassStatus,
│         b_pooled_cf: CanonicalFiveResult | None,  # Round 1 [C2]: feasible 個体のみ Pareto 軸 source
│         pareto_axis_usable: bool)
├── Constants
│   ├── STAGE_B_NUM_FOLDS = 5
│   ├── STAGE_C_LITE_NUM_WINDOWS = 3
│   ├── STAGE_C_LITE_FORCED_PASS_RATIO = 0.30
│   ├── STAGE_C_LITE_PROGRESS_PASS_MIN_WINDOWS = 2
│   ├── STAGE_C_LITE_SAMPLE_SIZE_BOUNDARY_BLOCKS = 30  # Round 1 [W5]
│   ├── STAGE_C_SPREAD_STRESS_MULTIPLIER = 1.5
│   ├── STAGE_C_ANCHOR_PAIR = "EUR_JPY"  # synthesis § 5.4 (anchor)
│   ├── STAGE_C_SHADOW_PAIR_LIST = ("USD_JPY", "EUR_USD", "AUD_JPY", "USD_CAD", "USD_ZAR")  # Round 1 [C4]: anchor 除く 5 pair
│   └── STAGE_C_SHADOW_REQUIRED_COUNT = 5  # 全 shadow pair 通過要求 (5/5、 Round 1 [C4])
├── Helpers (pure functions)
│   ├── evaluate_stage_b(individual_input, *, evaluate_fn, live_criteria) -> StageBResult
│   ├── evaluate_stage_c_lite(individual_input, *, evaluate_fn, live_criteria) -> StageCLiteResult
│   ├── evaluate_stage_c(individual_input, *, evaluate_fn, live_criteria, spread_stress_supported: bool = False) -> StageCResult
│   │     # Round 1 [C1]: spread_stress_supported=False (default) なら stress_pass=PENDING、 mission_pass=PENDING
│   ├── apply_spread_stress(trades, multiplier) -> tuple[TradeRecord, ...]
│   │     # Round 1 [C1] / Phase 1 では NotImplementedError raise (caller が呼ばない契約)
│   ├── compute_cross_pair_shadow_score(per_pair_results: dict[str, CanonicalFiveResult]) -> float | None
│   │     # Round 1 [W3] / [C4]: shadow 5 pair の通過率 (anchor 含まず)、 概念は仮、 詳細設計で確定
│   ├── compute_a_b_correlation_source_score(cf_result: CanonicalFiveResult) -> float
│   │     # Round 1 [C5]: higher-is-better の単一スカラー (= 1 / (1 + gate_worst_gap))
│   ├── compute_a_b_correlation(a_proxy_scores: dict[int, float], b_pooled_scores: dict[int, float]) -> tuple[float, int]
│   │     # 両 score とも higher-is-better で正規化済の前提 (Round 1 [C5])
│   ├── build_pooled_oos_input(fold_results, individual_input) -> PoolFoldedInput
│   │     # Round 1 [C3] / [Suggestion] 3: raw concat ではなく fold 境界 aware builder
│   │     # invariant: fold.test 非重複・時系列順、 bar/equity boundary-aware 再構成
│   └── select_top_clite_forced_pass_indices(per_individual_clite_results, ratio) -> frozenset[int]
│         # Round 1 [W1] / [Suggestion] 2: deterministic ranking key 明文化
└── Top-level entry
    └── evaluate_bc_for_a_pass(a_pass_inputs, *, evaluate_fn, live_criteria, spread_stress_supported=False) -> dict[int, BCEvaluationResult]
```

### Stage B 評価 (synthesis § 5.2 厳密準拠、 Round 1 [C2] / [C3] 反映)

```python
def evaluate_stage_b(
    individual_input: BCEvaluationInput,
    *,
    evaluate_fn: Callable[..., CanonicalFiveResult],
    live_criteria: dict,
) -> StageBResult:
    """5 fold rolling-origin pooled OOS canonical 5 worst aggregation.

    手順:
    1. T060 FoldGenerator から 5 folds (= individual_input.folds)
    2. 各 fold で:
        a. fold.test period に含まれる trades / bars をフィルタ
        b. evaluate_fn を呼び CanonicalFiveResult 取得 (StageBFoldResult)
        c. invariant fail-fast: cf_result.invariants.is_feasible が False → fold 違反フラグ
    3. **1 fold でも違反なら StageBResult.is_feasible_invariant=False** (synthesis § 5.2)
    4. is_feasible_invariant=False の場合 (Round 1 [C2] 反映):
        b_pooled_cf_result = None を設定 (downstream で識別可能化、 Pareto 軸 source として使用不可)
    5. is_feasible_invariant=True の場合のみ:
        a. build_pooled_oos_input(fold_results, individual_input) で fold 境界 aware の
            連結 input を構築 (Round 1 [C3] 反映、 raw concat ではない)
        b. pooled input で 1 回 evaluate_fn 呼出 → b_pooled CanonicalFiveResult
    6. StageBResult を返す:
        - b_pooled_cf_result: CanonicalFiveResult | None (None=invariant_fail)
        - per_fold_results (5 fold 個別)
        - is_feasible_invariant (全 fold OK で True)
        - is_b_pass = (b_pooled_cf_result is not None AND b_pooled_cf_result.gate_pass)

    Pareto 軸 source 契約 (Round 1 [C2] 反映):
    GA 主選抜の Pareto 3 軸 (T065) は **b_pooled_cf_result が None でない個体のみ**を使用する。
    BCEvaluationResult.pareto_axis_usable で明示。 T065 PR DoD で test 必須。
    """


def build_pooled_oos_input(
    fold_results: list[StageBFoldResult],
    individual_input: BCEvaluationInput,
) -> "PoolFoldedInput":
    """Round 1 [C3] / [Suggestion] 3 反映: fold 境界 aware の pooled input builder.

    raw concat の問題:
    - bar/equity series で fold 境界に擬似 DD / 擬似連続性が入る
    - HAC serial dependence で fold 跨ぎ autocovariance が誤計算される
    - business_day_universe の重複 (fold.test 非重複前提だが contract 化されていない)

    解決:
    1. fold.test 非重複・時系列順を assert
    2. trades: 各 fold.test の trades を時系列順に concat (重複なし契約)
    3. bars: 各 fold.test 期間の bar を時系列順に concat、
       fold 境界で running_max を **fold 内でリセット** (擬似 DD 防止)、
       または bar boundary metadata で T061 max_dd 計算が fold 内で完結する経路
    4. business_day_universe: 各 fold.test の (bucket, day) ペアを union 集合に
    5. 出力 PoolFoldedInput dataclass:
        - pooled_trades: tuple[TradeRecord, ...]
        - pooled_bars: BarEquitySeries (boundary-aware)
        - pooled_business_day_universe: dict[SessionBucket, frozenset[int]]
        - fold_boundaries: tuple[int, ...] (各 fold の trades 境界 index、 診断用)

    Note: bar boundary-aware 再構成の詳細は **詳細設計で確定**:
    - 案 A: 各 fold で bar 連結時に running_max を reset (擬似 DD 防止)
    - 案 B: T061 に fold_boundaries 引数を追加 (全経路改修)
    - 採用案: A (T064 内部で完結、 T061 改修なし)
    """
```

### Stage C-lite 評価 (synthesis § 5.3 厳密準拠)

```python
def evaluate_stage_c_lite(
    individual_input: BCEvaluationInput,
    *,
    evaluate_fn: Callable[..., CanonicalFiveResult],
    live_criteria: dict,
) -> StageCLiteResult:
    """3 disjoint windows × canonical 5 worst → 15 セル worst.

    手順 (世代内 ranking 用 forced_pass は別関数で世代単位で集約、 本関数は 1 個体評価のみ):
    1. T060 Partition から 3 c_lite Periods を取得 (c_lite_1/2/3)
    2. 各 window で evaluate_fn を呼び CanonicalFiveResult 取得 (StageCLiteWindowResult × 3)
    3. **15 セル worst**: 5 指標 × 3 windows = 15 値の worst (= 各 window の gate_worst_gap の max)
    4. **mission_pass** = 全 3 windows で gate_pass=True AND invariant_feasible (= 15 セル worst <= TOLERANCE)
    5. **progress_pass** = 2/3 windows で gate_pass=True (synthesis § 5.3 / § 8.2)
    6. forced_pass フラグは本関数では設定せず、 世代単位で別関数 select_top_clite_forced_pass_indices
       が世代内 ranking で top 30% を確定する (caller=T065 が世代単位で集約)
    7. StageCLiteResult を返す:
        - per_window_results (3 windows)
        - cells_worst (15 セル worst)
        - mission_pass (全 3 windows pass)
        - progress_pass (2/3 windows pass)
        - forced_pass フラグは別経路 (世代 ranking で別途確定)
    """


def select_top_clite_forced_pass_indices(
    per_individual_clite_results: dict[int, StageCLiteResult],
    ratio: float = STAGE_C_LITE_FORCED_PASS_RATIO,
) -> frozenset[int]:
    """世代内 top 30% 強制通過 (synthesis § 5.3 sample size 不足時 cycle 健全性).

    Args:
        per_individual_clite_results: 当世代の全個体 (a_pass のみ) の StageCLiteResult
        ratio: forced_pass 比率 (default 0.30)

    Returns:
        forced_pass_indices: top 30% (cells_worst 昇順 = 良い順) の index 集合

    Note: top 30% 強制通過は「sample size 不足時の cycle 健全性確保」 (synthesis § 5.3) のため、
    世代単位で a_pass 個体を ranking し top 30% を確定する。 mission_pass=True 個体は
    自動的に上位ランクするので、 mission_pass の補完として progress_pass / 順位中位を
    archive 流入候補にする経路 (T067 archive admission で消費)。
    """
```

### Stage C 評価 (synthesis § 5.4 厳密準拠、 Round 1 [C1] / [C4] 反映)

```python
class StagePassStatus(StrEnum):
    """Round 1 [C1] / [Suggestion] 1 反映: tri-state pass status."""
    PASS = "pass"
    FAIL = "fail"
    PENDING = "pending"  # spread stress 未実装等で判定不可


def evaluate_stage_c(
    individual_input: BCEvaluationInput,
    *,
    evaluate_fn: Callable[..., CanonicalFiveResult],
    live_criteria: dict,
    spread_stress_supported: bool = False,
) -> StageCResult:
    """12w contiguous holdout + spread stress + cross-pair shadow validation.

    Round 1 [C1] 反映: spread_stress_supported=False (default) の場合、 stress_pass=PENDING、
    mission_pass=PENDING。 嘘の stress_pass=True を返さない。
    Round 1 [C4] 反映: cross-pair は **anchor 除く 5 shadow pair (USD_JPY/EUR_USD/AUD_JPY/USD_CAD/USD_ZAR)
    の全通過 (5/5)** を要求。 anchor (EUR_JPY) は 12w main 判定でカバー、 cross-pair に含めない。

    手順:
    1. T060 Partition から stage_c Period (12w) を取得
    2. 12w trades / bars で evaluate_fn を呼び CanonicalFiveResult 取得 (c_cf_result)
        - live_criteria_pass = c_cf_result.gate_pass
    3. spread stress (Round 1 [C1]):
        if spread_stress_supported:
            apply_spread_stress(trades, 1.5) → stress_cf_result
            stress_pass = StagePassStatus.PASS if stress_cf_result.gate_pass else StagePassStatus.FAIL
        else:
            stress_cf_result = None
            stress_pass = StagePassStatus.PENDING  # T070 で TradeRecord.spread_cost 追加後に有効化
    4. cross-pair shadow validation (Round 1 [C4]):
        - shadow_pairs = STAGE_C_SHADOW_PAIR_LIST (5 pair、 anchor 除く)
        - 各 shadow pair について individual_input.shadow_pairs[pair] で
          PairBacktestBundle (provenance guard 含む、 Round 1 [W4]) を取得
        - 各 pair で evaluate_fn を呼び CanonicalFiveResult を取得
        - cross_pair_pass = StagePassStatus.PASS if 全 5 pair で gate_pass else FAIL
        - shadow_robustness_score = compute_cross_pair_shadow_score(per_pair_results) (Round 1 [W3])
    5. mission_pass: tri-state 集約 (Round 2 [Critical] 1 反映、 完全 truth table 適用):
        # FAIL 優先ルール: 確定 FAIL は PENDING を上書き
        if (live_criteria_pass=False) OR (cross_pair_pass=FAIL) OR (stress_pass=FAIL):
            mission_pass = StagePassStatus.FAIL
        elif (live_criteria_pass=True) AND (cross_pair_pass=PASS) AND (stress_pass=PASS):
            mission_pass = StagePassStatus.PASS
        else:
            # この経路は (1) live_criteria=True、 (2) cross_pair_pass != FAIL、 (3) stress_pass=PENDING のみ
            mission_pass = StagePassStatus.PENDING

    完全 truth table (Round 2 [Suggestion] 1 反映):

    | live_criteria | stress    | cross_pair | mission     |
    |---------------|-----------|------------|-------------|
    | False         | *         | *          | FAIL        |
    | *             | *         | FAIL       | FAIL        |
    | *             | FAIL      | *          | FAIL        |
    | True          | PASS      | PASS       | PASS        |
    | True          | PENDING   | PASS       | PENDING     |
    | True          | PENDING   | (n/a 評価skip) | PENDING |

    ("*" = 任意値で確定 FAIL なら他に関係なく FAIL)
    6. StageCResult を返す
    """


def apply_spread_stress(
    trades: tuple[TradeRecord, ...],
    multiplier: float,
) -> tuple[TradeRecord, ...]:
    """Round 1 [C1] / Phase 1 では NotImplementedError raise.

    spread cost を別 field 化する TradeRecord 拡張は T070 (backtest engine) 担当。
    T064 PR では本関数は呼ばれない経路 (`spread_stress_supported=False` で skip)。
    Phase 2 で T070 実装後に正式化、 evaluate_stage_c が `spread_stress_supported=True` で呼ぶ。
    """
    raise NotImplementedError(
        "apply_spread_stress requires TradeRecord.spread_cost field "
        "(T070 Phase 2 申し送り)"
    )


def compute_cross_pair_shadow_score(
    per_pair_results: dict[str, CanonicalFiveResult],
) -> float | None:
    """Round 1 [W3] / [C4] 反映: shadow 5 pair の通過強度.

    現案 (Decision Pending、 詳細設計で確定):
    - 全 pair が gate_pass=True なら 1.0
    - 1 pair でも fail なら 通過率 (= pass 数 / 5) を返す
    - 全 pair fail なら 0.0
    - per_pair_results が空集合なら None (computation impossible)

    archive CA #6 (synthesis § 8.3) で消費。 selection 圧から除外 (synthesis § 6.7、
    validation axis のみ)。 詳細設計で zenigame の robustness 計算を参考に確定する.
    """
```

### A→B 乖離計算 (synthesis § 8.7、 Round 1 [C5] 反映)

```python
def compute_a_b_correlation_source_score(
    cf_result: CanonicalFiveResult,
) -> float:
    """Round 1 [C5] 反映: higher-is-better の単一スカラーに正規化.

    定義: gate_score = 1 / (1 + max(0, cf_result.gate_worst_gap))
    値域: (0, 1]、 全達成で 1.0、 worst_gap 大で 0 に近づく
    higher = better、 corr 解釈で「 A が高ければ B も高い」 が positive correlation

    Round 2 [W2] 反映: 定義域ガード追加.
    cf_result.gate_worst_gap は T061 contract で >= 0 (sentinel +inf 撤廃済、 詳細 Round 1 [C1])。
    本関数は max(0, gap) clip で defensive、 gap < 0 (理論上ありえない) でも安全に 1.0 で計算.
    """
    safe_gap = max(0.0, cf_result.gate_worst_gap)
    return 1.0 / (1.0 + safe_gap)


def compute_a_b_correlation(
    a_proxy_scores: dict[int, float],   # a_pass 個体の higher-is-better スカラー (T063 gate_score)
    b_pooled_scores: dict[int, float],  # 同個体の T064 b_pooled higher-is-better スカラー
) -> tuple[float, int]:
    """corr(A_proxy_score, B_pooled_score) を Run 終了時に計算.

    両 score とも higher-is-better で正規化済の前提 (Round 1 [C5] 反映).
    a_proxy_scores: T063 a_pass_indices に対応する gate_score (= 1 / (1 + worst_gap_a))
    b_pooled_scores: T064 b_pooled_cf_result から compute_a_b_correlation_source_score で取得

    Args:
        a_proxy_scores: dict[index, score] (T063 stats 由来)
        b_pooled_scores: dict[index, score] (T064 b_pooled 由来、 None は除外、
            invariant_fail_fast 個体は b_pooled_cf_result=None で除外される、 Round 1 [C2])

    Returns:
        (corr, sample_size):
        - corr: Pearson 相関係数 [-1, 1]
        - sample_size: a_proxy_scores ∩ b_pooled_scores の共通 index 数

    Note: T071 (observability) で Run 終了時に計算、 caller (T065 GA loop) が T063
    update_divergence_state(prev, corr, corr_sample_size=sample_size) に注入する責務。
    """
```

### 重要な設計判断

**1. 3 stage を 1 module に統合**

- **採用**: `stage_bc_evaluator.py` 1 module で 3 stage 全て扱う
- **理由**: 共通 helper (apply_spread_stress、 compute_cross_pair_shadow_score、 compute_a_b_correlation) を DRY で実装、 import 関係単純化
- **代替案 (棄却)**: 3 module に分離 → 共通 helper の重複 or 共通 module 抽出が必要 (実質的に同じ)

**2. T061 への直接依存 (T062 / T063 と同じ pipeline)**

- **採用**: T064 helper は `evaluate_fn` (T061.evaluate_canonical_five) dependency injection
- **理由**: T063 と同じパターン、 test 時 mock 可能、 production で T061 に統一

**3. Stage B pooled OOS の実装方針**

- **採用**: 5 fold の trades / bars / business_day_universe を**連結して単一 evaluate_fn 呼出**
- **理由**: synthesis § 5.2 「5 fold 連結 pooled OOS」 = 5 fold を時系列順に concat した single trade list で canonical 5 を計算、 per-fold 計算後の集約ではない
- **代替案 (棄却)**: per-fold cf_result を集約 → synthesis 文言と乖離、 fold 跨ぎ HAC 補正不能

**4. invariant fail-fast の per-fold 検出**

- **採用**: 5 fold 各々で invariant 検出 (1 fold 違反で StageBResult.is_feasible_invariant=False)
- **理由**: synthesis § 5.2 「各 fold で invariant fail-fast (1 fold でも違反なら infeasible 確定)」
- **実装**: pooled 評価とは別途 fold 個別評価で invariant flag を集計、 1 fold OR で fail

**5. Stage C-lite forced_pass の世代単位 ranking**

- **採用**: `evaluate_stage_c_lite` は 1 個体評価で `forced_pass` フラグを設定しない、 世代単位で `select_top_clite_forced_pass_indices` を別途呼ぶ
- **理由**: top 30% 強制通過は世代内 ranking が必要、 個体単独では決定不能
- **代替案 (棄却)**: forced_pass を個体評価内で計算 → 世代単位の ranking 情報が必要なため不可能

**6. spread stress の実装**

- **採用**: `apply_spread_stress(trades, 1.5)` で spread を 1.5x にした trade list を生成、 同じ evaluate_fn で再評価
- **問題**: 現 TradeRecord は spread cost を分離していない (`pnl_net` は net of spread + swap で全体集約)。 stress 適用には spread cost 単独 field が必要
- **解決**: Phase 1 (T064 PR) では `apply_spread_stress` を skeleton (`raise NotImplementedError`) で実装、 Phase 2 で T070 が `TradeRecord.spread_cost` field 追加 + apply_spread_stress 実装。 T064 PR の `evaluate_stage_c` は stress_pass=True を一旦 placeholder で返す (T070 完了後に正式実装)
- **代替案 (検討)**: T064 で spread_cost field を TradeRecord に追加 → T061 schema 変更が広範囲、 T064 のスコープ外

**7. cross-pair shadow の入力契約**

- **採用**: `BCEvaluationInput.cross_pair_data: dict[str, tuple[TradeRecord列, BarEquitySeries, business_day_universe]]` で 6 pair 分の trades/bars を caller (T070) が事前準備
- **理由**: T064 は cross-pair backtest を内部で行わない、 T070 backtest engine が pair 別に同じ genome を実行した結果を T064 に渡す
- **代替案 (棄却)**: T064 で pair 別 backtest 実行 → 責務肥大化、 T070 と機能重複

**8. shadow_robustness_score の semantic**

- **採用**: synthesis § 8.3 archive CA #6 用、 「cross-pair 通過強度」 として:
  - Stage C cross_pair_pass 数 / 総 pair 数 (例: 5/6 = 0.83)
  - + 各 pair の `b_pooled_cf_result.gate_worst_gap` 反転スコア集約 (補助)
- **詳細仕様は Round 2 で議論**: synthesis § 8.3 は「shadow_robustness_score = TBD」 と明記なし。 Decision Pending として Round 2 で確定

## 期待効果

### live_criteria 達成への構造的貢献

- **Stage B pooled OOS で GA 主選抜の安定化**: synthesis § 3 「主選抜評価値 = Stage B pooled」 を実装、 旧 zenigame の逆ピラミッド (IS + OOS 混在) を全廃
- **Stage C-lite 15 セル worst で over-fitting 抑止**: 3 disjoint windows × 5 指標 = 15 セル全 pass を要求、 局所最適への過適合を排除
- **Stage C cross-pair shadow で多通貨 robustness**: 6 通貨で同じ genome を試して 5 通貨通過を要求、 anchor (EUR_JPY) 過適合排除
- **A→B 乖離自動補正経路の確立**: T064 で corr source 提供、 T063 update_divergence_state に注入、 q_force 自動引き上げ (synthesis § 8.7 / § 19 #4 逆輸入候補)

### 副次効果

- **T065 NSGA-II の Pareto 軸供給**: T064 b_pooled_cf_result が GA 主選抜の f1/f2/f3 source
- **T067 archive admission の 3 層流入対応**: mission_pass / progress_pass / score_bypass を T064 出力で識別可能
- **T071 observability**: per_fold / per_window / per_pair の診断情報を archive metadata に記録可能

## 実装方針 (概要)

### コンポーネント変更 (Phase 1: T064 PR)

| ファイル | 変更内容 |
|---|---|
| `src/alpha_factory/stage_bc_evaluator.py` | **新規作成**。 9 dataclass + 8 helper + 4 top-level evaluate_stage_* + Constants |
| `tests/alpha_factory/test_stage_bc_evaluator.py` | **新規**。 各 stage の数式 + invariant fail-fast + 15 セル worst + forced_pass + cross-pair + 4 代表ケース |

**Phase 1 (T064 PR) スコープは上記 2 施策のみ**。 既存 `stage_gate.py:evaluate_stage_b/c` への置換は **Phase 2 (T065 統合と同時)** で実施。 T064 PR 単独では既存経路に touch しない。

### Phase 2 (T065 統合と同時、 別 PR) 申し送り

T064 完了後、 GA / runner が T064 evaluator を消費する形に置換。

| # | ファイル / 箇所 | 変更内容 | 担当 |
|---|---|---|---|
| 1 | `stage_gate.py:evaluate_stage_b` | 全廃、 caller を T064 evaluate_stage_b に置換 | T065 |
| 2 | `stage_gate.py:evaluate_stage_c` | 全廃、 caller を T064 evaluate_stage_c に置換 | T065 |
| 3 | (新規) `stage_gate.py:evaluate_stage_c_lite` | 新規実装 (T064 evaluate_stage_c_lite 呼出) | T065 |
| 4 | `cross_pair.py` | shadow validation を T064 evaluate_stage_c の per_pair_results に統合 | T065 |
| 5 | (新規) `src/alpha_factory/observability/a_b_divergence.py` | corr 計算は T064 compute_a_b_correlation 呼出、 T063 update_divergence_state 注入 | T071 |
| 6 | `scripts/alpha_factory/run_ga.py` | per-generation で T063 → T064 → T062 の chain を呼ぶ orchestration | T065 |
| 7 | `src/alpha_factory/config.py:StageGateConfig` | 旧 `stage_b.{wf_*, median_*, fold_*}` / `stage_c.{spread_stress_*}` 全廃、 新仕様反映 (T060 申し送りと統合) | T065 |
| 8 | `config/alpha_factory/default.yaml` | 旧 stage_b / stage_c 全廃、 新仕様 (固定 5 folds + 12w + cross-pair list) | T065 |
| 9 | `archive.py` | archive admission が 3 層流入 (mission_pass / progress_pass / score_bypass) を BCEvaluationResult から識別 | T067 |
| 10 | (Phase 2 後段) `TradeRecord.spread_cost` field 追加 | apply_spread_stress 正式実装 | T070 |
| 11 | docs `docs/alpha_factory/stage-gates.md` | Stage B/C-lite/C 仕様を新 Partition / Fold + cross-pair に書き換え | T065 |

### C2 parallel-path 確認 (Phase 1 DoD、 T063 同様 5 段階)

1. 直 import: `grep -rn "from src.alpha_factory.stage_bc_evaluator" scripts/ src/ tests/` → 自身 + tests のみ
2. alias import: 同様
3. relative import: 同様
4. 再エクスポート: 0 hit
5. runtime シンボル: `grep -rn -E "evaluate_stage_b|evaluate_stage_c_lite|evaluate_stage_c|BCEvaluationResult" src/alpha_factory/stage_gate.py src/alpha_factory/swim_lane.py src/alpha_factory/cross_pair.py scripts/alpha_factory/run_ga.py` → 0 hit

## C3 / C7 適用

- **C3 (Collider bias)**: 該当なし (各 stage 評価は独立、 中間集団相関を新規導入しない)
- **C7 (Sample size、 重要)**:
  - Stage B pooled = 125 blocks/bucket (synthesis § 4.4) → C7 OK
  - Stage C-lite single window (6w) = 30 blocks/bucket → 境界、 C7 ぎりぎり
  - Stage C (12w) = 60 blocks/bucket → C7 OK
  - cross-pair (6 pairs × 12w) = pair 別に評価、 各 pair で 60 blocks/bucket → C7 OK
  - **A→B 乖離 corr**: T064 の compute_a_b_correlation は sample_size を返す、 caller (T063) で n>=10 / >=30 ガード適用

## 制約・前提

- **T058-T063 マージ後前提**: T064 は T060 (Period/Fold)、 T061 (CanonicalFiveResult)、 T062 (mission_inf_gap)、 T063 (StageAControllerState) を import
- **T070 backtest engine の cross-pair 出力**: cross_pair_data: dict[str, ...] は caller (T070) が pair 別に同じ genome を backtest した結果を提供する責務
- **TradeRecord.spread_cost 不在**: Phase 1 (T064 PR) では apply_spread_stress を skeleton (NotImplementedError)、 stress_pass placeholder。 Phase 2 (T070) で正式実装
- **synthesis § 5.4 / § 6.7 確定値厳密準拠**: 1.5x stress、 5 通貨 cross-pair、 shadow_robustness_score は selection 圧から除外 (validation only)

## スコープ外

- T058-T063: 依存先
- T065-T066: NSGA-II + CPPS (T064 b_pooled_cf_result / mission_inf_gap を Pareto 軸で消費)
- T067: Loop closure (T064 BCEvaluationResult の 3 層流入を archive admission で消費)
- T070: backtest engine (cross-pair 出力 + spread_cost field、 Phase 2 申し送り)
- T071: observability (corr 計算 + 注入 orchestration)

## 学術引用 / 先行知見

- synthesis § 5.2 / § 5.3 / § 5.4 / § 6.7 / § 8.3 / § 11: Stage B/C-lite/C 仕様
- Tashman (2000) "Out-of-sample tests of forecasting accuracy": rolling-origin pooled OOS の理論基盤 (T060 でも引用済)
- Bailey et al. (2014) CSCV: fold 集約の理論的根拠 (T060 でも引用)
- zenigame `evaluation/stage_gate.py` (Stage B/C 評価の元実装): fx 側で 5 fold pooled + 15 セル worst + cross-pair shadow を新規追加

## Round 1 → Round 2 の改訂点 (Codex review 反映サマリ)

| Round 1 [Critical/Warning/Suggestion] | 修正対応 |
|---|---|
| [C1] spread stress placeholder で stress_pass=True 嘘戻り値 | `StagePassStatus` Enum (PASS/FAIL/PENDING) で tri-state、 spread_stress_supported=False (default) なら stress_pass=PENDING、 mission_pass=PENDING。 嘘の True を返さない |
| [C2] Stage B infeasible 個体が Pareto 軸に混入 | is_feasible_invariant=False 時に `b_pooled_cf_result = None` を設定、 BCEvaluationResult.pareto_axis_usable で明示。 T065 PR DoD で「Pareto 軸 source は b_pooled_cf_result not None の個体のみ」 検証 test 必須 |
| [C3] pooled OOS fold 境界規約未定義 | `build_pooled_oos_input(fold_results, individual_input)` 新設 (raw concat ではない)、 fold.test 非重複・時系列順 + bar/equity boundary-aware 再構成 (各 fold で running_max reset) |
| [C4] cross-pair 母集団曖昧 (anchor 含む or 除く) | **synthesis § 5.4 厳密整合**: 「cross-pair shadow validation (5 通貨)」 = anchor 除く shadow 5 通貨。 § 11 (graduation lane) は Phase 4 別 TODO で 6 anchor pair、 Stage C cross-pair とは別文脈。 **anchor (EUR_JPY) を cross-pair 集計に含めない**、 STAGE_C_SHADOW_PAIR_LIST = (USD_JPY, EUR_USD, AUD_JPY, USD_CAD, USD_ZAR) で **5/5 全通過要求** |
| [C5] A→B 乖離 corr score source 未確定 | T064 で **higher-is-better の単一スカラー (= 1/(1+gate_worst_gap))** を確定、 `compute_a_b_correlation_source_score(cf_result)` 提供 |
| [W1] Stage C-lite forced_pass ranking 仕様不足 | `select_top_clite_forced_pass_indices` で deterministic ranking key 明文化: `mission_pass desc → progress_pass desc → invariant_ok desc → cells_worst asc → individual_id asc`、 forced 数は `max(1, ceil(n * 0.30))` (詳細設計で確定) |
| [W2] 15 cells worst が T061 契約依存 | T061 `CanonicalFiveResult.gate_worst_gap` が「window 内 5 指標 max(0, -slack) の max」 であることを再確認 (T061 詳細設計 APPROVED で確定済)、 詳細設計で T061 import + 利用整合性確認 |
| [W3] shadow_robustness_score Decision Pending を float 確定 field 化リスク | `shadow_robustness_score: float | None` に変更 (Pending or computation impossible で None) |
| [W4] cross-pair input contract に provenance guard 不足 | `PairBacktestBundle` dataclass 新設 (pair / genome_id / config_hash / partition_label / trades / bars / business_day_universe)、 T064 で provenance 検証 |
| [W5] C7 Stage C-lite 6w 境界 | `StageCLiteResult` に `sample_size_flag: SampleSizeFlag` (OK / BOUNDARY / INSUFFICIENT) 追加、 30 blocks/bucket 境界で BOUNDARY を返す |
| [S1] Pass を Enum tri-state | [C1] と統合 |
| [S2] forced_pass ranking key 明文化 | [W1] と統合 |
| [S3] pool_fold_results を build_pooled_oos_input にリネーム | [C3] と統合 |
| [S4] cross_pair_data を PairBacktestBundle dataclass 化 | [W4] と統合 |
| [S5] compute_a_b_correlation で higher-is-better 統一 | [C5] と統合 |

## Round 2 [Warning/Suggestion] 反映 (詳細設計で吸収)

| Round 2 指摘 | 対応 |
|---|---|
| [W1] build_pooled_oos_input の running_max reset で全期間 pooled OOS の DD を過小評価する可能性 | 詳細設計で「fold 内の running_max は fold 開始時に reset、 ただし pooled DD 計算は per-fold DD の max を取る」 と数式レベル明記 |
| [W2] compute_a_b_correlation_source_score の定義域ガード未記載 | 上記コードに `safe_gap = max(0.0, gap)` clip 追加、 docstring に「T061 contract で gap >= 0 だが defensive で max clip」 明記 |
| [W3] forced_pass strict ranking spec 未確定 | 詳細設計で deterministic ranking key (mission_pass desc → progress_pass desc → invariant_ok desc → cells_worst asc → individual_id asc) を実装、 Enum 比較順序明文化、 invariant_fail 個体は ranking 対象外 |
| [W4] SampleSizeFlag と pass 判定の結合規約 | 詳細設計で「`INSUFFICIENT` (n < 25) は mission_pass / progress_pass を **PENDING** 強制」、 「`BOUNDARY` (25 <= n < 30) は判定継続 + diagnostic 出力のみ」 と確定 (C7 一貫性) |
| [S1] truth table 追記 | Stage C tri-state 完全 truth table を Round 2 改訂で追記済 |
| [S2] cross-pair denominator 1 行固定 | 「shadow only 5 pair (anchor 除く) の 5/5」、 ログ表現も同様に統一 |
| [S3] compute_a_b_correlation_source_score domain assert | 上記 [W2] で defensive clip 採用、 詳細設計で test に domain edge case 追加 |

## 残論点 (詳細設計または別 PR で確定)

1. **shadow_robustness_score の正式数式**: 通過率 vs 通過強度 (詳細設計で確定)
2. **bar boundary running_max reset の implementation 詳細**: BarEquitySeries 拡張 vs 内部 helper (詳細設計で確定)
3. **Phase 1 (T064 PR) spread stress テスト方針**: spread_stress_supported=False のみで mission_pass=PENDING の test (詳細設計で追加)
