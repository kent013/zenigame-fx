# 詳細設計: T081 — RunObservabilityReport 9 metric 実値配線

**作成日時**: 2026-05-02 22:06 JST、 **本格化**: 2026-05-02 23:43 JST、 **Round 2 改訂**: 2026-05-03 00:13 JST (Codex Round 1 [Critical] 3 + [Warning] 2 取込)、 **Round 3 改訂**: 2026-05-03 00:25 JST (Codex Round 2 [Critical] 1 + [Warning] 3 取込)、 **Round 4 改訂**: 2026-05-03 00:33 JST (Codex Round 3 [Warning] 1 取込 = numpy 型ガード)
**status**: **Round 4 改訂済 (= 6 step segmentation で step 1 を完全詳細化、 step 2-6 は signature / file path 確定の skeleton で残し、 各 step 着手時に追加詳細化する運用)**

---

## 0. 使命・制約 (絶対遵守)

### zenigame-fx Alpha Factory 使命
live_criteria 全指標同時充足 + (ii-lite) 通過で使命達成。
絶対制約: イントラデイ / ロング・ショート両方向 / スワップ・スプレッド反映。

### 禁止事項
1. A・B・C 評価期間を根拠なしに延長
2. 見た目の数値改善
3. GA ハック
4. live_criteria 緩和
5. 過度な複雑化
6. 取引回数削減で成績を見せる
7. オーバーナイト保有前提

### コーディングルール
- **テストファースト** (バグ修正は再現テスト先)
- **全施策にテスト必須**
- **uv 必須**: `uv run pytest tests/alpha_factory/`
- **ruff / mypy 通過**: `uv run ruff check src/ tests/` / `uv run mypy src/`
- Python 3.13 + numpy + pandas

---

## 1. 概念設計リファレンス

`devnotes/20260502-2206-todo-T081-observability-real-values/conceptual-design.md`

T080a (commit `de9b7d7`) で確立した stub builder 経路 (= 9 metric を valid status / default 値で構築) を、 各 metric の実値計算経路に置換する。

---

## 2. 改訂対象一覧 (= 6 step segmentation、 各 step 1 worktree commit)

| # | step | 内容 | 主たる touch | 性質 | 優先 |
|---|---|---|---|---|---|
| 1 | step1 | ABDivergenceMetric 実値配線 | run_ga.py + swim_lane (score 収集) + test | 中 | High |
| 2 | step2 | ArchiveChurn / BypassRatio + admission-history state file | run_ga.py + state file 経路 + test | 中 | High |
| 3 | step3 | SessionEntropy / FeasibleRatio | run_ga.py + StageAControllerState 抽出 + test | 中 | Medium |
| 4 | step4 | Selection 実値配線 | run_ga.py + GenerationSelectionResult 経路 + test | 中 | Medium |
| 5 | step5 | InflowConsistency / Failure | run_ga.py + WarmstartReport / RunFailureSummary 経路 + test | 中 | Medium |
| 6 | step6 | QForceRecommendation + cross-run state file + T063 配線 | run_ga.py + stage_a_evaluator.py + state file + test | 重 | High |

### 2.1 各 step 共通方針

- 1 step = 1 worktree commit (= incremental、 `worktree todo/T081` 内で順次 commit)
- 各 step 完了後に `pytest tests/alpha_factory/ -x` 全 PASS 確認
- 各 step 完了後に `uv run mypy src/` clean 確認 + `uv run ruff check src/ tests/`
- 各 step 完了後に `zenigame-fx-codex-review` (gpt-5.3-codex / high) で impl-review (= APPROVED まで)
- run_ga.py 末尾の `build_stub_run_observability_report` を **段階的に** 実値版 (= 9 個別 metric ごとに本物の値で置換) に切替
- stub builder は touch なし (= debug / fallback 用途で残存、 削除は **B Phase 2 切替コミット** スコープ)

---

## 3. Step 1 詳細設計 (ABDivergenceMetric 実値配線、 完全詳細化)

### 3.1 SSOT signature 確認

**`src/alpha_factory/observability/run_metrics.py:606-651`**

```python
def compute_ab_divergence_on_b_evaluated(
    a_proxy_scores_b_evaluated: Sequence[Decimal],
    b_pooled_scores: Sequence[Decimal],
) -> ABDivergenceMetric:
    """B 評価対象個体集合に conditioning した Pearson correlation."""
    # n < AB_MIN_ACTIONABLE_PAIRS で status="insufficient_data"
    # var_a / var_b == 0 で status="zero_variance"
    # それ以外で status="ok", corr=Decimal in [-1, 1]
```

= caller が **同一 individual_index に対する (A 評価 score, B 評価 score) ペア** を Stage B で評価済みの個体だけ集めれば良い。

### 3.2 score 取得経路 (caller 側)

**A_proxy_score** (= Stage A の A→B 相関 source score):
- `src/alpha_factory/stage_bc_evaluator.py:1113-1125`
  ```python
  def compute_a_b_correlation_source_score(cf_result: CanonicalFiveResult) -> float:
      """1 / (1 + max(0, gate_worst_gap)) ∈ (0, 1] の higher-is-better スカラー."""
      safe_gap = max(0.0, cf_result.gate_worst_gap)
      return 1.0 / (1.0 + safe_gap)
  ```
- = Stage A の `evaluate_stage_a` 戻り値 `StageResult.metrics["payload"]` に **CanonicalFiveResult が直接含まれていない** (`stage_gate.py:493-516`)。

**B_pooled_score** (= Stage B pooled OOS の A→B 相関 source score):
- 同上 `compute_a_b_correlation_source_score` を `b_pooled_cf_result` に適用
- `src/alpha_factory/stage_bc_evaluator.py:282-302` で `StageBResult.b_pooled_cf_result: CanonicalFiveResult | None`
  - `b_pooled_cf_result is None` (= invariant 未満) は除外する契約 (Pareto 軸 source 契約)
- swim_lane.py 経由では `StageResult` (stage_gate.py の wrapping) しか handle しないため **adaptor 必要**

### 3.3 swim_lane 配線設計 (caller side)

ポイント: swim_lane.py の Tier1Lane evaluate ループは `StageResult` (stage_gate.py) を返している (`swim_lane.py:553-684`)。 `StageResult.metrics["payload"]` は `compute_a_b_correlation_source_score` の入力 `CanonicalFiveResult` を **持っていない** (= Stage A は fast screen で T061 canonical 5 を計算しない設計、 stage_gate.py:381-522 で確認)。

**選択肢の評価**:

| option | 内容 | 評価 |
|---|---|---|
| A: payload に cf_result 同梱 | StageResult.metrics["payload"]["a_cf_result"] に cf_result 添加 | ❌ Stage A 経路で T061 canonical 5 を計算する経路追加が必要 (= 別 TODO スコープ、 step 1 で扱うのは過剰) |
| B: 既存 fitness_pen / median_oos_sharpe を score にする | A=fitness_pen / B=median_oos_sharpe | ✅ 両方 Sharpe-derived higher-is-better スカラー、 Pearson correlation の内部整合性は保たれる |
| C: 別チャネルで score 集約 (= Sequence) | swim_lane が `list[tuple[float, float]]` を別途集約 | ✅ archive 契約に触れず、 caller 注入規範 |

**採用: option B + option C 併用** (= score source は fitness_pen / median_oos_sharpe、 集約 channel は別 list)

**SSOT 乖離の判定 (Codex Round 1 [Critical] 1 取込)**:
- SSOT 関数 `compute_a_b_correlation_source_score(cf_result: CanonicalFiveResult) -> float` は cf_result を要求。
- Stage A は fast screen 設計 (= sharpe + complexity penalty のみ) で cf_result を計算していない。 SSOT 統一には Stage A での T061 canonical 5 評価追加が必要 = 評価コスト増 + 別 TODO スコープ。
- **Pearson correlation は scale 不変** なので、 a/b それぞれが内部整合的な higher-is-better スカラーであれば correlation は意味を持つ (= fitness_pen は sharpe_raw - α*size_norm、 median_oos_sharpe は walk-forward median Sharpe で、 両方 higher-is-better)。
- **Phase 1 採用は妥当** だが、 後続別 TODO で SSOT 統一を可視化する `score_source` annotation を導入し、 mixing 防止 / 将来移行コスト削減を担保する。

### 3.4 別チャネル設計 (option C)

**新規 module 不要**、 swim_lane 既存の Tier1Lane evaluate ループ (`swim_lane.py:553-684`) 内に **score-pair 集約 dict** を追加。

```python
# swim_lane.py: _run_tier1_generation_legacy + _run_tier1_generation_via_evaluator 双方
# generation 単位ループ内で集約
ab_score_pairs: dict[str, tuple[float, float]] = {}  # {genome_name: (a_score, b_score)}

# Stage A 評価後 (= a_result が StageResult、 cf_result は内部で再計算が必要)
# → stage_gate.py 側で a_cf_result を返すか、 a_proxy_score を直接 payload に追加するのが
#   最小コスト
# 推奨: stage_gate.py の evaluate_stage_a / evaluate_stage_b で payload に
#       "a_b_corr_source_score": float (or None) を直接添加 (archive Parquet 互換破壊なし、
#       payload は in-memory only)。
```

**詳細**:

#### 3.4.1 stage_gate.py side: payload に a_b_corr_source_score 添加

**変更箇所**: `src/alpha_factory/stage_gate.py:493-516` (evaluate_stage_a の payload 構築) + `:743-765` (evaluate_stage_b の payload 構築)

**Stage A 側**:
- 現行: payload に fitness_raw / fitness_pen / sharpe_raw / trade_count / total_pnl 等
- 追加: `"a_b_corr_source_score": float | None`
  - 計算: `compute_a_b_correlation_source_score(cf_result)` (cf_result は evaluate_stage_a 内部で `evaluate_canonical_five` を呼んで取得しているはず) ← **要確認**
  - cf_result が evaluate_stage_a 内部で生成されていない場合 (= 簡易 fitness 計算のみ) は **Stage A 経路で T061 canonical 5 を計算する経路追加** が必要 → これは別 step (= 過剰スコープ) なので、 step 1 では **fitness_pen を a_proxy_score として暫定使用** + Stage B 側のみ source_score に統一
  - **暫定 (step 1 内)**: `a_proxy_score = float(fitness_pen)` (None / NaN / Inf 時は除外)

**Stage B 側**:
- 現行: payload に n_fold / median_oos_sharpe / positive_fold_ratio / dsr / is_full_* / unavailable_reason_counts 等
- 追加: `"b_pooled_cf_result": CanonicalFiveResult | None` を **payload に in-memory only で添加** (= sidecar diagnostics と同型の契約)
  - 注記: archive Parquet には書かない (28+ カラム fixed schema 尊重)
  - 既存 collect_stage_b で payload 全 dict が archive に流れている場合は **payload を archive 流入用と sidecar 流入用に分離** が必要 ← 要確認 (`archive.py` の collect_stage_b 経路)

**Phase 1 採用 (step 1 で確実に動く形)**:
- Stage A の `a_proxy_score` = `payload["fitness_pen"]` (= 既存値、 加工なし、 None/NaN は除外)
- Stage B の `b_pooled_score` = `payload["median_oos_sharpe"]` (= 既存値、 加工なし、 None/NaN は除外)
- 注記コメント: 「Phase 1 暫定 — SSOT (compute_a_b_correlation_source_score) との完全整合は別 TODO で対応」 を run_ga.py / detailed-design.md 双方に明記

= **既存 payload 値をそのまま使う** の最小コスト変更で、 swim_lane / stage_gate / archive を **一切 touch しない**。

#### 3.4.2 swim_lane.py side: score-pair 集約 (Codex Round 1 [Critical] 2 / [Critical] 3 / [Warning] 4 取込)

**ポイント** (Codex Round 1 [Critical] 2 取込): dict[genome_name, ...] では世代横断・lane 横断・cross-pair shadow 経路で **key 衝突** リスク。 `compute_ab_divergence_on_b_evaluated` は `Sequence[Decimal]` を要求するため、 dict は不要 → **`list[tuple[float, float]]`** に変更。

**ポイント** (Codex Round 1 [Critical] 3 取込): legacy / via_evaluator 経路双方で **必須キー化**。 戻り dict は最終的に **TypedDict 化が望ましい** が、 step 1 では既存 dict 戻り値の構造に **必須 4 キー** (`ab_score_pairs` / `ab_score_source` / `ab_b_evaluated_count` / `ab_excluded_preflight_count`) を追加する形 (= TypedDict 移行は別 TODO で実施)。

**ポイント** (Codex Round 1 [Warning] 4 取込): preflight_underfilled で除外した個体数を可視化 → `ab_excluded_preflight_count` / `ab_b_evaluated_count` を戻り dict に併記、 logger でも記録。

`_run_tier1_generation_legacy` (`swim_lane.py:553-684`) 内、 `for genome in lane.population:` loop の中で:

**重要 (Codex Round 2 [Critical] 1 取込)**: 既存 swim_lane.py L606-637 は preflight_underfilled でも `_build_preflight_b_result` 呼出 → archive collect_stage_b / diagnostics record_stage_b を **必ず実行** している。 早期 `continue` は既存挙動を壊すため **使用禁止**。 ab_score 収集は **flag ベース** (`should_collect_ab_pair = not preflight_underfilled`) で skip する。

```python
# 集約 list (Codex Round 1 [Critical] 2 取込: list 化で key 衝突回避)
ab_score_pairs: list[tuple[float, float]] = []
# 診断用 counter (Codex Round 1 [Warning] 4 取込)
ab_b_evaluated_count = 0
ab_excluded_preflight_count = 0

for genome in lane.population:
    # Stage A 評価 (既存)
    a_result = evaluate_stage_a(genome, ...)
    self._archive.collect_stage_a(...)  # 既存
    if self._diagnostics is not None:
        self._diagnostics.record_stage_a(...)  # 既存
    if not a_result.passed:
        continue  # ← 既存 logic、 触らない
    stage_a_pass += 1  # 既存

    # Stage B 評価 (既存) — 必ず実行 (preflight でも _build_preflight_b_result が走る)
    if preflight_underfilled:
        b_result = self._build_preflight_b_result(...)  # 既存
        # AB pair 収集対象から除外 (Codex Round 2 [Critical] 1 取込: 早期 continue 禁止)
        ab_excluded_preflight_count += 1
        should_collect_ab_pair = False
    else:
        b_result = evaluate_stage_b(genome, ...)  # 既存
        ab_b_evaluated_count += 1
        should_collect_ab_pair = True

    # AB pair 収集 (= Stage B 既存処理の前で実施、 副作用なし)
    if should_collect_ab_pair:
        a_payload = a_result.metrics.get("payload", {})
        a_score = a_payload.get("fitness_pen")  # float | None
        b_payload = b_result.metrics.get("payload", {})
        b_score = b_payload.get("median_oos_sharpe")  # float | None
        # NaN / Inf / None / 非数値型フィルタ (Codex Round 2 [Suggestion] 4 + Round 3 [Warning] 1 取込:
        # numbers.Real で numpy.float32 / numpy.int64 等も covered、 bool 除外)
        if (
            isinstance(a_score, numbers.Real) and not isinstance(a_score, bool)
            and isinstance(b_score, numbers.Real) and not isinstance(b_score, bool)
            and math.isfinite(float(a_score))
            and math.isfinite(float(b_score))
        ):
            ab_score_pairs.append((float(a_score), float(b_score)))

    # 既存 archive collect / diagnostics record (= preflight でも実行)
    self._archive.collect_stage_b(...)  # 既存、 触らない
    if self._diagnostics is not None:
        self._diagnostics.record_stage_b(...)  # 既存、 触らない

    if not b_result.passed:
        continue  # ← 既存 logic、 触らない
    stage_b_pass += 1  # 既存
    # Stage C 以降は既存 logic、 触らない
    ...
```

**戻り値**: `_run_tier1_generation_legacy` の戻り dict に **以下 4 必須キー** を追加:

```python
return {
    "lane_id": lane.lane_id,
    ...,
    # T081 step 1 追加 (= ABDivergenceMetric 実値配線、 必須キー)
    "ab_score_pairs": ab_score_pairs,            # list[tuple[float, float]]
    "ab_score_source": "fitness_pen+median_oos_sharpe_phase1",  # str (mixing 防止用 annotation)
    "ab_b_evaluated_count": ab_b_evaluated_count,            # int (b_result.passed 不問の真評価個体数)
    "ab_excluded_preflight_count": ab_excluded_preflight_count,  # int (preflight skip 個体数)
}
```

同じ pattern で `_run_tier1_generation_via_evaluator` (`swim_lane.py:686-875`) にも追加 (= via_evaluator は L860 でも同様の dict を返す、 同じ 4 キーを追加)。

`_noop_summary` (`swim_lane.py:962-973`、 = state != "active" lane 用) は `ab_score_pairs=[]` / `ab_score_source="noop"` / counter 0 を返す (= 必須キー化で run_ga.py の `update` 経路で missing key 例外回避)。

#### 3.4.3 run_ga.py side: 全世代から集約 → ABDivergenceMetric 計算 (Codex Round 1 [Critical] 2 取込)

**変更箇所**: `scripts/alpha_factory/run_ga.py:1427-1517` (世代ループ) + `:1571-1592` (stub builder 呼出箇所)

**世代ループ内**:
```python
# Run loop 起動前で初期化 (Codex Round 1 [Critical] 2 取込: list で集約)
all_ab_score_pairs: list[tuple[float, float]] = []
all_ab_b_evaluated_count: int = 0
all_ab_excluded_preflight_count: int = 0
ab_score_source: str | None = None  # 初回設定後固定 (= 異なる source の mixing 検出)

for gen in range(cfg.ga.generations + 1):
    ...
    summary_out = lane_manager.run_generation(lane_id)
    # 集約 (Codex Round 1 [Critical] 3 取込: 必須キー前提、 .get(...) は契約違反検出のための defensive default)
    new_pairs = summary_out.get("ab_score_pairs", [])
    all_ab_score_pairs.extend(new_pairs)
    all_ab_b_evaluated_count += int(summary_out.get("ab_b_evaluated_count", 0))
    all_ab_excluded_preflight_count += int(summary_out.get("ab_excluded_preflight_count", 0))
    new_source = summary_out.get("ab_score_source", "noop")
    if new_source != "noop":
        if ab_score_source is None:
            ab_score_source = new_source
        elif ab_score_source != new_source:
            # 別 source の mixing は契約違反 (Codex [Critical] 1 取込)
            raise RuntimeError(
                f"ab_score_source mixing detected: "
                f"existing={ab_score_source} new={new_source}"
            )
    ...
```

**Run 末尾 (= stub builder 呼出箇所)**:
```python
# 診断 log (Codex [Warning] 4 取込)
logger.info(
    "ga.observability.ab_score_pairs_collected",
    run_id=run_id,
    n_pairs=len(all_ab_score_pairs),
    b_evaluated_count=all_ab_b_evaluated_count,
    excluded_preflight_count=all_ab_excluded_preflight_count,
    score_source=ab_score_source or "noop",
)

# ABDivergenceMetric 実値計算 (= list[tuple] → Sequence[Decimal] 2 本に分解)
a_scores = [Decimal(repr(a)) for a, _ in all_ab_score_pairs]
b_scores = [Decimal(repr(b)) for _, b in all_ab_score_pairs]
ab_divergence_metric = compute_ab_divergence_on_b_evaluated(a_scores, b_scores)

# stub default (= 残り 8 metric。 step 1 範囲外、 stub builder の引数構造と整合)
stub_q_force = QForceRecommendation(...)  # 既存 stub builder と同じ default
stub_archive_churn = ArchiveChurnMetric(status="insufficient_runs", ...)
... (8 件)

# build_run_observability_report に実値 + stub default を供給
observability_report = build_run_observability_report(
    run_id=run_id,
    dataset_epoch_id=run_context.dataset_epoch_id,
    generation_count=cfg.ga.generations,
    ab_divergence=ab_divergence_metric,  # ← step 1 で実値
    q_force_recommendation=stub_q_force,
    archive_churn=stub_archive_churn,
    bypass_ratio=stub_bypass_ratio,
    session_entropy=stub_session_entropy,
    feasible_ratio=stub_feasible_ratio,
    selection=stub_selection,
    inflow_consistency=stub_inflow_consistency,
    failure=stub_failure,
)
```

**stub default 値の DRY 化** (= step 1 内の追加修正): `build_stub_run_observability_report` から **個別 metric の default constructor** を 8 個 export (= `build_default_q_force_recommendation()` 等) し、 step 1 caller がそれを利用。 これにより stub builder と実値配線版で default が DRY 担保される。

**ab_score_source 永続化** (Codex Round 2 [Warning] 2 取込): observability.json に `ab_divergence` (`ABDivergenceMetric`) を含む全体構造で source も保存可能だが、 ABDivergenceMetric の現行 dataclass (= `status` / `corr` / `n_pairs` の 3 field) には source が無い。 step 1 では:
- **観測 log のみで対応** (= `logger.info("ga.observability.ab_score_pairs_collected", ..., score_source=...)` が source を log/structured 記録)
- step 6 (= cross-run state file) で `q-force-state.json` に `ab_score_source` を含める設計を追加 (= step 6 詳細設計時に詳細化)
- step 1 完了後、 別 TODO で ABDivergenceMetric dataclass 拡張 (= `score_source: str` field 追加) を検討。 source が dataclass に乗れば observability.json に自動永続化 (= JSON serializer が dataclass field を出す既存契約)。

**run-time vs cross-run の source mismatch handling** (Codex Round 2 [Warning] 3 取込):
- **run 内** (= 同一 Run 内で異なる source の summary_out が来る): `RuntimeError` raise で fail-fast (上記 mixing 検出経路)
- **cross-run** (= step 6 の連続乖離 Run カウント) : `q-force-state.json` 読込時に `previous_source != current_source` なら **skip old record + warn log** (= 別系列扱い、 fail-closed 過剰回避)。 step 6 設計時に詳細化。

**注記**: `build_run_observability_report` (= 9 個別 metric を全て caller-supplied で受け取る関数) が T071 module に既に実装されている前提 (`src/alpha_factory/observability/run_metrics.py:1100-...` で確認済)。 もし不在なら新規追加する (= step 1 内で実施)。 stub builder の default 値生成ロジックを **共有** すれば DRY 担保。

#### 3.4.4 build_run_observability_report の契約確認

`src/alpha_factory/observability/run_metrics.py:1100` 付近で signature 確認:
```python
def build_run_observability_report(
    *,
    run_id: str,
    dataset_epoch_id: str,
    generation_count: int,
    ab_divergence: ABDivergenceMetric,
    q_force_recommendation: QForceRecommendation,
    archive_churn: ArchiveChurnMetric,
    bypass_ratio: BypassRatioMetric,
    session_entropy: SessionEntropyMetric,
    feasible_ratio: FeasibleRatioMetric,
    selection: SelectionMetric,
    inflow_consistency: InflowConsistencyMetric,
    failure: FailureMetric,
) -> RunObservabilityReport:
    ...
```

→ **要確認** (実装着手時に grep で実 signature を確定)。 不在なら step 1 内で新規追加。

### 3.5 ルックアヘッドバイアスチェック (primitive 変更なし)

step 1 は **primitive 変更なし** (= score 集約のみ)。 ルックアヘッドバイアス unchanged。

### 3.6 パフォーマンスチェック

- Run loop に dict update 1 回 (O(N_pop)) 追加のみ → 無視できる
- 末尾 ABDivergence 計算 1 回 (O(N_pop)) 追加 → 無視できる

### 3.7 テスト計画 (step 1、 Codex Round 1 [Warning] 5 取込)

新規 test ファイル: `tests/alpha_factory/test_run_ga_observability_ab_divergence.py` (= run_ga 経路) + 既存 `tests/alpha_factory/test_swim_lane.py` 拡張 (= legacy/via_evaluator パリティ)

**run_ga 経路 (新規ファイル、 11 ケース最小)**:
1. `test_ab_divergence_real_value_computed_when_n_pairs_above_min`: smoke 用 fixture で N=10+ ペア生成 → status="ok" + corr finite
2. `test_ab_divergence_insufficient_when_n_pairs_below_min`: N=5 → status="insufficient_data"
3. `test_ab_divergence_zero_variance_when_a_or_b_constant`: 全個体で a_score 同値 → status="zero_variance" (Codex [Warning] 5 追加)
4. `test_ab_divergence_excludes_genomes_with_none_or_nan_scores`: a_score=None, b_score=NaN を持つ個体は除外
5. `test_ab_divergence_excludes_preflight_underfilled_individuals`: preflight_underfilled=True の Stage B 個体は除外
6. `test_ab_score_pairs_aggregated_across_generations`: cfg.ga.generations=2 (= ループ 0..2、 計 3 世代) で N_pop=10 → 30 ペア集約 (Codex [Warning] 5 追加: generation_count 整合 / +1 ループ)
7. `test_observability_json_persisted_with_ab_divergence_real_value`: observability.json の `ab_divergence.status` が "ok" / corr が float 値
8. `test_observability_json_other_8_metrics_remain_stub_default`: step 1 では他 8 metric は stub default
9. `test_ab_score_source_mixing_raises_error`: 異なる source の summary_out が dict update されたら RuntimeError (Codex [Critical] 1 取込)
10. `test_ab_excluded_preflight_count_logged`: preflight skip 個体が log に記録されることを確認 (Codex [Warning] 4 取込)
11. `test_ab_score_pairs_no_key_collision_across_lanes_or_generations`: 同名 genome が複数世代に出現しても全 pair が記録される (Codex [Critical] 2 取込)

**swim_lane パリティ (既存 test 拡張、 4 ケース追加)**:
12. `test_swim_lane_legacy_and_via_evaluator_return_same_keys_for_ab`: 双方経路で `ab_score_pairs` / `ab_score_source` / `ab_b_evaluated_count` / `ab_excluded_preflight_count` キーが必須で同型 (Codex Round 1 [Critical] 3 取込)
13. `test_swim_lane_noop_summary_returns_empty_ab_score_pairs`: state != "active" lane で空 list / "noop" source
14. `test_swim_lane_preflight_underfilled_does_not_skip_archive_collect_or_diagnostics_record` (Codex Round 2 [Critical] 1 取込): preflight 個体で archive.collect_stage_b と diagnostics.record_stage_b が **必ず呼ばれる** ことを spy で確認、 ab_score_pairs に append しないことも併せて確認
15. `test_swim_lane_payload_score_must_be_numeric_for_ab_pair_collection` (Codex Round 2 [Suggestion] 4 取込): payload["fitness_pen"] が str 等の非数値型なら ab_score_pairs に append しないことを assertion

**stub builder 互換性 test (Codex Round 2 [Suggestion] 1 取込)**:
16. `test_stub_run_observability_report_equality_after_default_constructor_export`: 既存 `build_stub_run_observability_report(run_id, dataset_epoch_id, generation_count)` の戻り `RunObservabilityReport` が、 個別 default constructor 8 件を combine した結果と **完全 equality** であること (= JSON serialize 後 byte-for-byte 一致)

**all-inactive run の専用 test (Codex Round 2 [Suggestion] 3 取込)**:
17. `test_observability_json_when_all_lanes_inactive_returns_insufficient_data`: 全 lane が state != "active" の Run で `ab_score_source = None → log 上は "noop"`、 `ab_divergence.status="insufficient_data"`, `n_pairs=0`

合計 17 ケース最小。

既存 test 修正:
- `tests/alpha_factory/observability/test_run_metrics.py` (= stub builder の引数構造変更があれば追従)
- `tests/alpha_factory/test_swim_lane.py` (= 既存 test に必須キー存在 assert 追加)

### 3.8 リスク (step 1、 Codex Round 1 + Round 2 全取込後)

| リスク | 影響 | 緩和 |
|---|---|---|
| swim_lane 戻り dict に新 key 追加で既存 caller が破綻 | 中 | 必須キー化 + `_noop_summary` も返す → run_ga.py の `.get(..., default)` で missing 時 default、 旧 caller は無視 (Codex Round 1 [Critical] 3 取込) |
| fitness_pen / median_oos_sharpe を a/b score に使うのが SSOT (compute_a_b_correlation_source_score) と乖離 | 中 | `ab_score_source="fitness_pen+median_oos_sharpe_phase1"` annotation で明示、 mixing 検出 RuntimeError、 別 TODO で SSOT 同期 (Codex Round 1 [Critical] 1 取込) |
| genome_name 衝突で score-pair 上書きロス | 中 | `dict` を **`list[tuple[float, float]]`** に変更で衝突回避 (Codex Round 1 [Critical] 2 取込) |
| preflight 除外で n_pairs<10 常態化 | 中 | `ab_excluded_preflight_count` / `ab_b_evaluated_count` を log + 戻り dict で可視化 (Codex Round 1 [Warning] 4 取込) |
| legacy / via_evaluator 経路の戻り dict が異なる | 中 | 両経路 + `_noop_summary` で必須 4 キーを定義、 swim_lane parity test 追加 (Codex Round 1 [Critical] 3 取込) |
| 早期 `continue` で既存 Stage B 処理 (archive collect / diagnostics record) を skip する事故 | 高 | flag ベース (`should_collect_ab_pair`) で AB pair 収集だけ skip、 既存処理は不変、 spy test 追加 (Codex Round 2 [Critical] 1 取込) |
| ab_score_source の cross-run 永続化なし → step 6 で source mixing を検出不能 | 中 | step 1 では log 記録のみ、 step 6 設計時に q-force-state.json に保存。 別 TODO で ABDivergenceMetric.score_source field 追加 (Codex Round 2 [Warning] 2 取込) |
| run-time fail-fast (RuntimeError) が cross-run source migration 時に過剰 | 低 | run 内は RuntimeError、 cross-run history (= step 6) は skip old + warn に分離 (Codex Round 2 [Warning] 3 取込) |
| AB_MIN_ACTIONABLE_PAIRS=10 と C7 (n<30) の discipline mismatch | 低 | step 1 では status 判定のみ。 step 6 設計時に q_force 自動判断で causal claim 回避注記 (Codex Round 2 [Warning] 4 取込) |
| 非数値型の payload score (= str / None / list) が ab_score_pairs に流入 | 低 | `isinstance(score, numbers.Real) and not isinstance(score, bool)` ガード (= numpy.float32 / int64 covered、 bool 除外) + test 15 で固定 (Codex Round 2 [Suggestion] 4 + Round 3 [Warning] 1 取込) |

### 3.9 step 1 着手手順 (= 後続 worktree todo/T081 で実施)

1. `git worktree add -b todo/T081 ../zenigame-fx-todo-T081 main` で worktree 作成
2. `tests/alpha_factory/test_run_ga_observability_ab_divergence.py` 新規追加 + 既存 `test_swim_lane.py` parity test 追加 (= テストファースト、 13 ケース最小、 RED 確認)
3. `src/alpha_factory/observability/run_metrics.py` の `build_run_observability_report` signature 確認 (= **verified**: L1099-1128) + 個別 metric default constructor 関数 8 件 export 追加 (= stub builder の DRY 化)
4. `src/alpha_factory/swim_lane.py` の `_run_tier1_generation_legacy` / `_run_tier1_generation_via_evaluator` / `_noop_summary` に **必須 4 キー** (`ab_score_pairs` / `ab_score_source` / `ab_b_evaluated_count` / `ab_excluded_preflight_count`) 追加
5. `scripts/alpha_factory/run_ga.py` の Run loop で `all_ab_score_pairs` (list 集約) + counter 集約 + score_source mixing 検出 + 末尾 `compute_ab_divergence_on_b_evaluated` 呼出 + diagnostic log
6. `pytest tests/alpha_factory/ -x` 全 PASS 確認
7. `uv run mypy src/` clean / `uv run ruff check src/ tests/` 確認
8. impl-review (gpt-5.3-codex / high) → APPROVED まで対応
9. step 1 commit (= worktree 内で `feat(T081 step 1): ABDivergenceMetric 実値配線`)
10. step 2 へ続く

---

## 4. Step 2 詳細設計 (ArchiveChurn / BypassRatio + admission-history state file、 skeleton)

### 4.1 SSOT signature

- `compute_archive_churn(recent_admission_reports: Sequence[AdmissionReport]) -> ArchiveChurnMetric`
  (`src/alpha_factory/observability/run_metrics.py:758-793` 推定)
- `compute_bypass_ratio(admission_report: AdmissionReport) -> BypassRatioMetric`
  (同上 `:801-824` 推定)

### 4.2 元値取得経路

- AdmissionReport 定義: `src/alpha_factory/cpps_archive.py:285-316`
- run_ga.py 内で `archive.admission_history` から取得 (T066 配線済)、 = 当 Run の `AdmissionReport` 1 件
- cross-run 用に **直近 N (= 3) Run の AdmissionReport** が必要

### 4.3 admission-history state file 設計

| 項目 | 設計 |
|---|---|
| Path | `reports/admission-history/{run_id}.json` |
| Format | AdmissionReport を `dataclasses.asdict` → JSON serialize |
| 書込 | atomic (= `Path.write_text(...) + os.replace(...)` パターン、 Cascade Port v2 と同型) |
| 読込 | Run 起動時に `reports/admission-history/*.json` を mtime sort で直近 N (=3) 件読込 |
| Cleanup | 別 TODO (= 30 日以上古い JSON は別バッチで削除) |

### 4.4 step 2 着手時に追加詳細化

= **step 1 完了後にこのセクションを elaborate** (= 各メソッドの concrete code、 atomic write helper の DRY 化、 test plan)

---

## 5. Step 3 詳細設計 (SessionEntropy / FeasibleRatio、 skeleton)

### 5.1 SSOT signature

- `compute_session_entropy(session_pass_patterns: Sequence[str], n_runs_aggregated: int, *, weekly_window_size: int) -> SessionEntropyMetric`
  (`src/alpha_factory/observability/run_metrics.py:832-930` 推定)
- `FeasibleRatioMetric(...)` 直接構築 (= compute 関数なし)

### 5.2 元値取得経路

- archive members の session_pass_pattern (3 bit string "[01]{3}") を caller 計算 (= T064 stage_a_evaluator 結果から、 archive Parquet schema 経由)
- T063 `StageAControllerState` (= `src/alpha_factory/stage_a_evaluator.py:139-183`) から feasible_ratio_ema / fsm_state / counts 抽出

### 5.3 step 3 着手時に追加詳細化

---

## 6. Step 4 詳細設計 (Selection、 skeleton)

### 6.1 SSOT signature

- `extract_selection_metrics(result: GenerationSelectionResult, *, feasible_ratio: Decimal, mean_constraint_violation: Decimal, generation: int) -> SelectionMetric`
  (`src/alpha_factory/observability/run_metrics.py:931-966` 推定)

### 6.2 元値取得経路

- `GenerationSelectionResult`: `src/alpha_factory/nsga2_selection.py:144-167`
- run_ga.py で最終世代の selection result をキャプチャ
- caller-supplied feasible_ratio / mean_constraint_violation / generation は cache から計算

### 6.3 step 4 着手時に追加詳細化

---

## 7. Step 5 詳細設計 (InflowConsistency / Failure、 skeleton)

### 7.1 SSOT signature

- `extract_inflow_consistency(warmstart_report, admission_report, *, warmstart_share_target, per_source_run_violations) -> InflowConsistencyMetric`
  (`:969-1031` 推定)
- `extract_failure_metrics(summary, *, fingerprint_top_n_by_stage) -> FailureMetric`
  (`:1034-1070` 推定)

### 7.2 元値取得経路

- `WarmstartReport`: `src/alpha_factory/loop_closure.py:301-324`
- `RunFailureSummary`: `src/alpha_factory/failure_handling.py:209-217`
- run_ga.py で各々を生成 / 取得 → extract 関数に渡す

### 7.3 step 5 着手時に追加詳細化

---

## 8. Step 6 詳細設計 (QForceRecommendation + cross-run state file + T063 配線、 skeleton)

### 8.1 SSOT signature

- `recommend_q_force_adjust(current_q_force, divergence, consecutive_divergent_runs, *, delta_per_run, q_force_max, restore_threshold, q_force_min, divergence_threshold) -> QForceRecommendation`
  (`src/alpha_factory/observability/run_metrics.py:659-...`)

### 8.2 元値取得経路 + state file

- 当 Run の divergence は **step 1 で計算済** (= ab_divergence_metric)
- 連続乖離 Run カウント: `reports/q-force-state/q-force-state.json` に永続化
  ```json
  { "consecutive_divergent_runs": 0, "last_divergence_corr": null, "last_run_id": "..." }
  ```
- `recommend_q_force_adjust` の戻り `QForceRecommendation.next_q_force` を T063 `StageAControllerState` の next q_force update に配線

### 8.3 step 6 着手時に追加詳細化 (= 重い、 cross-run state file + T063 配線で最終)

---

## 9. 機械検証手順 (全 step 共通)

各 step ごとに:
- run_ga.py の build_run_observability_report 呼出が build_stub_* ではなく実値版になっていることを grep
- 各 metric の status が "ok" or 適切な status になることを test で確認
- `pytest tests/alpha_factory/ -x` 全 PASS
- `uv run ruff check src/ tests/`
- `uv run mypy src/`
- impl-review (gpt-5.3-codex / high) → APPROVED

---

## 10. 波及変更

| target | step 1 | step 2 | step 3 | step 4 | step 5 | step 6 |
|---|---|---|---|---|---|---|
| `AGENTS.md` | なし | なし | なし | なし | なし | なし |
| `.claude/skills/zenigame-fx-*/SKILL.md` | なし | なし | なし | なし | なし | なし |
| `config/alpha_factory/default.yaml` | なし | なし | なし | なし | なし | なし |
| `docs/alpha_factory/runbook.md` | step 6 完了後に observability.json 説明追加 (別 TODO) |
| `docs/alpha_factory/stage-gates.md` | T081 全完了後に "Phase 2 配線完了" マーク |

---

## 11. 実装モード

| 項目 | 内容 |
|---|---|
| 推奨モード | **incremental** (= 6 step を 1 worktree 内で順次 commit) |
| 判断根拠 | 各 step が caller injection で互いに非干渉、 stub builder fallback で部分実装でも runtime safe |
| 競合リスク | step 6 のみ T063 stage_a_evaluator.py 配線で他 TODO (= 将来の T063 拡張) と干渉可能性、 step 6 着手時に再評価 |
| 想定実装時間 | step 1: 短 / step 2-5: 中 / step 6: 長 |

---

## 12. 後続 step 詳細化フロー

step 1 完了後の運用:
1. step 1 worktree commit が main fast-forward merge
2. step 2 着手前に detailed-design.md § 4 を本格化 (= 同 file 上書き編集、 別 commit)
3. step 2 設計の Codex review (= zenigame-fx-codex-review、 design-review label) → APPROVED
4. step 2 worktree 実装
5. step 3-6 同様

= step 1 だけ Codex 設計レビューで通し、 step 2-6 は **着手直前にその step だけ詳細化 + Codex review** で同じファイルを継続更新する運用。

---

## 13. T080 follow-up との関係

T080 (= T080a で stub builder 経路確立、 close 済) の後継として T081 を新規登録。 handoff の T080b-g 申し送りは T081 の 6 step として吸収。 後続 B Phase 2 切替コミット の前提条件 (= 9 metric 実値配線完了) を T081 で達成する。

---

## 14. ABDivergence (step 1) 完了条件 (DoD)

- [ ] swim_lane.py の Tier1Lane evaluate ループに `ab_score_pairs` 集約追加 (legacy + via_evaluator 双方)
- [ ] run_ga.py の Run loop で `all_ab_score_pairs` 集約 + 末尾 `compute_ab_divergence_on_b_evaluated` 呼出
- [ ] `build_run_observability_report` 関数が ab_divergence 引数を実値で受け取る (= stub default fallback も維持)
- [ ] 新規 test `tests/alpha_factory/test_run_ga_observability_ab_divergence.py` 全 PASS (= 6 ケース最小、 上記 § 3.7)
- [ ] 既存 test 全 PASS (= regression 0)
- [ ] mypy / ruff clean
- [ ] impl-review (gpt-5.3-codex / high) APPROVED
- [ ] commit message: `feat(T081 step 1): ABDivergenceMetric 実値配線 (=共通 swim_lane 集約 + run_ga.py 末尾配線)`
