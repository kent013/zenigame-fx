# 詳細設計: NSGA-II + CPPS selection 配線（T102 step3/5a/5b）

## 使命・制約（絶対遵守）
- 使命: live_criteria 全指標同時充足 + (ii-lite) 通過個体の出現。絶対制約: イントラデイ / ロング・ショート両方向 / スワップ・スプレッド反映。
- 禁止事項 1–8 遵守（特に 4 live_criteria 緩和なし、8 archive スキーマ値伝搬漏れなし）。
- コーディング: テストファースト（バグ修正）/ 全施策テスト必須 / 振る舞い名 / uv / ruff / mypy / Python 3.13。

## 概念設計リファレンス
[conceptual-design.md](conceptual-design.md)（Codex conceptual-review 3 round APPROVED）。案A固定・案B破棄、step5 を 5a(NSGA-II only)/5b(CPPS only) 分離、成功判定=mission候補再現率(1/3→3/3)、4条件ablation必須。

## verified 前提（C1/C4、現 HEAD コードで確認）
- `mission_inf_gap.py:211 evaluate_mission_inf_gap(result: CanonicalFiveResult) -> MissionGapResult` = **入力が CanonicalFiveResult** → step5a の f3 を Stage B pooled の `b_pooled_cf_result` から導けば **source_stage=B が構造的に保証**（Stage C/holdout 由来値を渡さない限り逆流しない）。
- `stage_bc_evaluator.py`: `StageBResult.b_pooled_cf_result: CanonicalFiveResult|None` / `pooled_dd_per_fold_max: float|None` / `is_b_pass` / `is_feasible_invariant`。`CanonicalFiveResult.net_pnl_after_cost` 有り。コメント L287「GA 主選抜 (T065 Pareto 3 軸) は b_pooled_cf_result is not None の個体のみ消費する責務」= pareto_axis_usable の実体。
- `diagnostics_collector.py`: `DiagnosticsCollector.record_stage_a/b/c` + `to_rows` の LOG_ONLY sidecar（C1 gap_class が同型で稼働中）。step3 はこの機構に相乗り。
- `run_ga.py:779 _breed_next_gen` = elite + `_tournament`(`_selection_key`)。`IndividualCacheEntry`(fitness_pen + pass flags + feasibility)。
- `nsga2_selection.py`: `run_generation_selection(population: Mapping[int, IndividualEvaluation])` / 低レベル `non_dominated_sort` / `crowding_distance` / `make_selection_seed(run_id, gen)`。
- `cpps_archive.py`: `archive_admit` / `archive_evict_ca|da` / `determine_archive_role` / `compute_archive_capacities` / `update_archive_per_run`。

## 施策一覧

| # | 施策名 | 変更ファイル | 優先度 | flag (default) |
|---|--------|------------|--------|----------------|
| P3 | step3: ParetoFeaturesLite sidecar（LOG_ONLY、行動不変） | diagnostics_collector.py, diagnostics_sidecar.py, swim_lane.py | Critical | なし（常時記録、selection 不変） |
| P5a | step5a: NSGA-II only selection | run_ga.py, config.py(GAConfig) | Critical | `nsga2_selection_enabled`(False) |
| P5b | step5b: CPPS only injection | run_ga.py, config.py(GAConfig) | High | `cpps_archive_enabled`(False), `cpps_inject_ratio`(0.0) |

---

## P3: ParetoFeaturesLite sidecar（step3、LOG_ONLY）

### ★ 実装時のスコープ訂正（2026-05-21、ユーザー決定: 忠実=pooled fold-CV 配線）
**当初前提の誤り**: 詳細設計は「`b_pooled_cf`（pooled fold-CV canonical）が production で利用可能」と仮定したが、コード調査で以下が判明:
- `b_pooled_cf` を産む `stage_bc_evaluator.evaluate_stage_b_pooled` は **production 未配線**（cpps/loop_closure/nsga2 からの shadow 参照のみ）。
- production Stage B（`stage_gate.evaluate_stage_b`）が surface するのは `canonical_shadow_b_is`（**IS-monitor** canonical、mission_inf_gap のみ）と per-fold の `canonical_sidecar_b_fold`（**ログ only、未 pooling・未 surface**）。

**決定（汎化目的のため IS-monitor 不採用）**: P3 は単なる sidecar 相乗りでなく、**`evaluate_stage_b_pooled`（pooled fold-CV、OOS）を production Stage B に dual-path LOG_ONLY で配線**し、その `b_pooled_cf_result` から ParetoFeaturesLite を生成する。= 実質 元 T102 step3「BCEvaluationResult dual-path」。判定・gate・selection は不変（LOG_ONLY、bit-exact）。

**配線方針（既存 fold artifact の直消費、Codex review-6 反映）**:
- `stage_gate.evaluate_stage_b` の fold ループは既に per-fold backtest（fold_bt/fold_trades/fold_equity, L1450）と per-fold canonical（`canonical_sidecar_b_fold`, L1456）を計算済。
- ⚠ **`stage_bc_evaluator.evaluate_stage_b(BCEvaluationInput)` を直接呼ばない**: 同関数は fold period で trades/bars を `filter_to_period`（`[start, end)`）し canonical を**再計算**するため、(a) 二重評価 (b) Stage Gate の `test_bars` から `Period.end` を作る際の最終 bar/trade 落ち off-by-one、のリスクがある。
- 代わりに **新 helper `build_stage_b_pooled_result_from_fold_artifacts(fold_artifacts, live_criteria) -> StageBResult`** を新設。入力は各 fold の既算出 artifact（`canonical_cf_result`（=canonical_sidecar_b_fold）, `canonical_trades`, `canonical_bars`, `canonical_universe`, `fold_period`）に限定し、**backtest 再実行も BCEvaluationInput 再構築も period 再フィルタもしない**。`build_pooled_oos_input` 相当の pooling（per-fold cf を pool して b_pooled_cf_result、per-fold max_dd の max で pooled_dd_per_fold_max）だけ行う。
- **完全 no-raise 境界 `try_build_pareto_lite_from_stage_b_fold_artifacts(...) -> ParetoFeaturesLite`**: fold 数/順序/overlap/empty bars/threshold 構築/pooled canonical 評価まで全体を try で包み、失敗時は `pareto_axis_usable=False, source_stage=None, mission_inf_gap=None` + WARN log のみ（gate/judgment 経路に波及させない）。
- dual-path: `phase2_canonical_metrics_mode != "disabled"` のときのみ算出。
- **sidecar 限定**: pooled 値は diagnostics sidecar 専用に閉じ、archive schema には流さない。`test_collect_stage_b_archive_schema_unchanged`（archive 列が増えないこと）で保証。

> 本訂正版 P3 は Codex design-review Round 6-7 で再レビュー済 → **APPROVE**（fold artifact 直消費 helper・no-raise 境界・sidecar 限定で観測のみ・bit-exact 成立）。
> 実装ノート（Codex R7、既存 StageBResult contract 確認）: **いずれかの fold の `canonical_cf_result.invariants.is_feasible is False` なら `b_pooled_cf_result=None / pooled_dd_per_fold_max=None / is_feasible_invariant=False / pareto_axis_usable=False`** とする。

### 目的
step5a が消費する Pareto 3 軸（Stage B 完結 = pooled fold-CV OOS scalar）を per-individual に算出・記録する観測機構。**selection・判定・archive 本体は一切変更しない**（行動不変、bit-exact）。これにより step5a 実装前に「軸が全 evaluated 個体ぶん出るか」「source_stage=B（pooled OOS）か」を検証可能化。

### ParetoFeaturesLite（新規 dataclass、selection 専用 scalar sidecar、6 field）
```python
@dataclass(frozen=True)
class ParetoFeaturesLite:
    """step5a NSGA-II selection が消費する Stage B 完結 scalar のみ。
    trade/equity 配列・BCEvaluationResult 全体は保持しない（MP 境界・メモリ保護）。"""
    net_pnl_after_cost: float | None   # f1 max, source: b_pooled_cf_result.net_pnl_after_cost (Stage B)
    pooled_dd_per_fold_max: float | None  # f2 min(>=0 invariant), source: StageBResult.pooled_dd_per_fold_max
    mission_inf_gap: float | None      # f3 min, source: evaluate_mission_inf_gap(b_pooled_cf_result)
    is_feasible_invariant: bool        # T061 invariant（Stage B）
    pareto_axis_usable: bool           # = b_pooled_cf_result is not None ∧ 3 scalar finite ∧ is_feasible_invariant
    source_stage: Literal["B"] | None = None  # 逆流監査用。B 完結時 "B"、未算出 None
```

### builder に閉じる（fold artifact 直消費、CanonicalFiveResult 直渡し禁止）
- 唯一の生成経路を **`try_build_pareto_lite_from_stage_b_fold_artifacts(fold_artifacts, live_criteria) -> ParetoFeaturesLite`**（no-raise）に限定。内部で `build_stage_b_pooled_result_from_fold_artifacts(...) -> StageBResult` を呼び `b_pooled_cf_result` を得る。呼び出し側は `CanonicalFiveResult` / Stage C 由来 cf を直接渡せない。
- builder 内: `cf = pooled.b_pooled_cf_result`。`cf is None`（fold 不足/infeasible/例外）→ 全 scalar None / pareto_axis_usable=False / source_stage=None。`cf is not None` → net_pnl_after_cost / pooled_dd_per_fold_max / `evaluate_mission_inf_gap(cf).mission_inf_gap` を算出、`source_stage="B"`。

### NaN slack の abort 回避（Codex Warning: LOG_ONLY で新 abort 経路を作らない）
- `evaluate_mission_inf_gap` は NaN slack で ValueError を投げる。builder では **try で捕捉せず、事前に cf の finite を検査**し、非 finite なら `mission_inf_gap=None, pareto_axis_usable=False` に落とす（LOG_ONLY で RUN を止めない）。
- `test_pareto_lite_nonfinite_cf_falls_back`（非 finite cf で pareto_axis_usable=False、例外を投げない）。

### 変更箇所
- `diagnostics_collector.py`:
  - `IndividualDiagnostics` に **6 field** 追加（net_pnl_after_cost / pooled_dd_per_fold_max / mission_inf_gap / is_feasible_invariant / pareto_axis_usable / source_stage）。default None/False。
  - `record_stage_b(...)` に `pareto_lite: ParetoFeaturesLite | None = None` 引数追加 → rec に格納（後方互換: 省略時 None）。
  - `to_rows()` に **6 列** materialize。invariant assert: `pareto_axis_usable=True ⇒ source_stage=="B"` かつ 3 scalar finite。
- `diagnostics_sidecar.py`: `STAGE_A_PROVENANCE_SCHEMA` に **6 列**追加（pa.float64 ×3, pa.bool_ ×2, **pa.string() ×1 = source_stage**）。`DIAGNOSTICS_SCHEMA_VERSION` を +1 し `assert_diagnostics_v*` 整合。
- `swim_lane.py` `_run_tier1_generation_via_evaluator`（L719-907）: Stage B 評価後に `b_result.b_pooled_cf_result` から `ParetoFeaturesLite` を構築し `collector.record_stage_b(..., pareto_lite=...)`。**Stage C/holdout/cross-pair の値は渡さない**。

### mission_inf_gap の Stage B 限定（逆流防止）— 契約確定
- **実シグネチャ**: `mission_inf_gap.py:297 evaluate_mission_inf_gap(result: CanonicalFiveResult) -> MissionGapResult`（slacks 版 `compute_mission_inf_gap_from_slacks` は内部 helper、L201）。CanonicalFiveResult を受け内部で slacks 導出 → mission_inf_gap を返す。**型整合あり**（detailed-review R1 の「contract 齟齬」は私が L205-260 の slacks helper 抜粋を送った誤誘導。L297 が正）。
- 入力は `b_result.b_pooled_cf_result`（Stage B pooled CanonicalFiveResult）**のみ**。`evaluate_mission_inf_gap(b_pooled_cf_result).mission_inf_gap` を使う。Stage B 完結が**入力型レベルで保証**（Stage C の StageCLiteResult を渡す経路が存在しない）。
- `b_pooled_cf_result is None`（B fail / infeasible）の個体は `mission_inf_gap=None, pareto_axis_usable=False`。
- ParetoFeaturesLite に **`source_stage: str = "B"` 列を明示**追加（逆流監査を機械化、Codex Suggestion）。
- Stage C 評価結果は本算出に一切参照しない（`test_mission_inf_gap_source_stage_b_only` で保証）。

### 波及変更
- `AGENTS.md`: diagnostics sidecar 列追加を「診断 sidecar」節に 1 行追記。
- `.claude/skills/zenigame-fx-run-report/SKILL.md`: 新列の集計表示（任意、observation）。今サイクルは「列追加のみ、report 表示は後続」で可。
- `config/alpha_factory/default.yaml`: なし（P3 は flag なし）。
- `docs/alpha_factory/diagnostics-sidecar.md`: ParetoFeaturesLite 列の定義・source_stage=B を追記。

### スキーマ伝搬接続表（禁止事項 8）
| 段 | 箇所 | P3 |
|----|------|-----|
| schema 定義 | diagnostics_sidecar.STAGE_A_PROVENANCE_SCHEMA | 6 列追加(float64×3/bool×2/string×1) |
| record 初期値 | IndividualDiagnostics field default | None/False |
| 書き込み | swim_lane → build_pareto_features_from_stage_b_result → collector.record_stage_b(pareto_lite=) | 追加 |
| flush 出力 | collector.to_rows() | 6 列 materialize + invariant assert |
| reader backfill | diagnostics_sidecar 欠損列 null 補完 | 6 列 |
| consumer/test | tests/alpha_factory/test_diagnostics_*.py | 追加 |

### テスト計画
- `test_pooled_result_from_fold_artifacts_no_refilter`: fold artifact を直消費し、period 再フィルタ・再 backtest をしない（最終 bar/trade が落ちない）。
- `test_pareto_features_lite_recorded_for_b_pass`: B pass 個体で 3 scalar finite かつ pareto_axis_usable=True、source_stage="B"。
- `test_pareto_lite_none_for_b_fail`: fold 不足/infeasible で mission_inf_gap=None, pareto_axis_usable=False, source_stage=None。
- `test_try_build_pareto_lite_is_noraise`: pooling 内部例外（empty bars / fold overlap 等）で例外を投げず pareto_axis_usable=False に落ちる（LOG_ONLY 隔離）。
- `test_mission_inf_gap_source_stage_b_only`: mission_inf_gap が pooled b cf のみ由来（Stage C 結果を変えても不変）= 逆流禁止の機械的保証。
- `test_collect_stage_b_archive_schema_unchanged`: P3 で archive 列が増えない（sidecar 限定）。
- 既存 sidecar テスト更新（6 列 additive nullable）。
- baseline 不変: `test_breed_next_gen_bit_exact`（P3 で selection 出力・gate 判定が変わらない）。

### schema 後方互換（Codex Warning 対応）
- `diagnostics_sidecar.py` に**欠損列 null 補完 reader** を明示実装（旧版 parquet を読む際、新 6 列が無ければ null 列を付与してから返す）。strict schema reader での破綻を防ぐ。
- `test_sidecar_reads_old_schema_with_null_backfill`（旧版固定 parquet fixture を読み欠損列が null になる）を追加。

### リスク
- selection 不変なので RUN 挙動リスクは無い（bit-exact）。schema bump は上記互換 reader + 旧データ回帰テストで担保。

---

## P5a: NSGA-II only selection（step5a）

### 変更箇所
- `config.py` `GAConfig`: `nsga2_selection_enabled: bool = False` 追加（+ CLI `--nsga2-selection`）。
- **`nsga2_selection.py` に専用入口を新設**（Codex Critical 対応、IndividualEvaluation 偽装を回避）:
  ```python
  def select_from_pareto_features(
      features_by_idx: Mapping[int, ParetoFeaturesLite],
      *, offspring_count: int, rng: random.Random,
      genome_hash_by_idx: Mapping[int, str],
  ) -> GenerationSelectionResult:
      """ParetoFeaturesLite(scalar)から直接 non_dominated_sort + crowding_distance を呼ぶ
      lite 入口。bc_result/IndividualEvaluation を構築しない（contract 偽装回避）。
      eligible = pareto_axis_usable=True の個体のみ。parent_pairs の長さ = offspring_count。"""
  ```
  - **`offspring_count` 引数化（Codex Critical: P5b 同時有効時の頭数整合）**: parent_pairs を `pop_size` 固定でなく `offspring_count` 件返す。P5a-only では `offspring_count=pop_size`、P5a+P5b では `offspring_count=breed_slots`（注入枠を除いた数）。
  内部で既存 `non_dominated_sort` / `crowding_distance` / `_build_sort_keys` / parent_pairs 生成を再利用（DRY）。`run_generation_selection` 本体は触らない。
- **caller 契約（Codex Warning）**: `features_by_idx` は **全 population idx を渡す**。pareto_axis_usable=False の idx は内部で excluded として記録（missing idx は ValueError）。
- `run_ga.py` `_breed_next_gen`: flag True 時のみ `select_from_pareto_features(...)`。False 時は現行 elite + `_tournament`（bit-exact）。
- `IndividualCacheEntry` に ParetoFeaturesLite を保持（P3 算出済 scalar を cache へ。trade/equity 非保持）。

### _breed_next_gen 統合 contract（Codex Critical: pop 超過回避・P5a/P5b 統合）
**slot allocation を先に確定 → breed_slots を生成器に渡す**単一フローに統一（P5a/P5b/both すべてここを通る）:
```
(warmstart_total, anchor, warmstart_mut, cpps_slots, breed_slots) = allocate_slots(...)  # P5b 節の式
inject = anchor + warmstart_mut + cpps 注入個体（計 pop_size - breed_slots 体）
breed:
  if nsga2_selection_enabled:
      res = select_from_pareto_features(features_all_idx, offspring_count=breed_slots, rng=..., genome_hash_by_idx=...)
      parent_pairs = res.parent_pairs   # 長さ breed_slots
  else:
      parent_pairs = [tournament×2 を breed_slots 回]   # 現行 tournament
  breed 個体 = crossover/mutate(parent_pairs)            # breed_slots 体
next_gen = inject + breed 個体  → 合計 == pop_size（test で固定）
```
- NSGA-II 経路では **elite copy をしない**（front-1 を **parent pool として優先**するだけで survivor copy はしない＝二重カウント防止。"elitism 内包" という表現は撤回）。
- P5b 無効時は `inject` は従来通り（warmstart のみ or なし）、`breed_slots = pop_size - warmstart_total`。P5a/P5b 完全無効時は現行と bit-exact。
- `survivor_indices` は diagnostics 用のみ。
- `test_breed_population_size_exact_all_modes`（①②③④ すべてで出力が常に pop_size 体）。

### eligible 条件（Codex Warning）
- eligible = `pareto_axis_usable and is_feasible_invariant`。`test_nsga2_excludes_infeasible_with_finite_scalar`（finite scalar だが infeasible は survivor/parent に入らない）。

### dd 符号 invariant（Codex Warning）
- `pooled_dd_per_fold_max >= 0`（損失額の正値）を builder で invariant 検査。`f2 = pooled_dd_per_fold_max`（小さいほど良い）。`test_pareto_axis_direction` に負値ケース（invariant 違反検出）を含める。

### 軸符号正規化（Codex Warning）
- dominance 比較直前に **f1 = -net_pnl_after_cost（最大化を最小化へ反転）/ f2 = pooled_dd_per_fold_max / f3 = mission_inf_gap** に符号統一し「全軸最小化」へ正規化。`test_pareto_axis_direction`（net_pnl 大が優位、dd/gap 小が優位）で回帰固定。

### eligible 不足時の規約（Codex Critical/Warning: offspring_count 整合）
- eligible == 0: parent_pairs=()、上位で従来 tournament breed へ fallback（warning `nsga2_eligible_empty`）。
- eligible == 1: `parent_pairs = ((i, i),) * offspring_count`（deterministic self-mating、mutation only。**長さ = offspring_count を厳守**）、warning `nsga2_eligible_below_2`。
- 1 < eligible < offspring_count: 既存 NSGA-II の parent_pairs 生成（crowded tournament）を offspring_count 件まで生成、sample_size_warnings 踏襲。
- `test_nsga2_eligible_below_2_self_mating`（parent_pairs 長 == offspring_count かつ生成個体数 == offspring_count を検証）。

### 決定論
- tie-break は `make_selection_seed(run_id, gen)` で run 跨ぎ deterministic。genome_hash は既存 deterministic hash。

### live_criteria への接続（明文化）
- f1 net_pnl_after_cost ↑ = live total_pnl 方向、f2 max_dd ↓ = live max_drawdown 方向、f3 mission_inf_gap ↓ = live 4 指標の最大 shortfall を直接縮める。3 軸とも live_criteria と単調整合（緩和でなく充足方向）。trade_count は eligible 判定（feasibility）側で担保。

### 波及変更
- `AGENTS.md`: GA 設定節に `nsga2_selection_enabled` + CLI を追記。
- `config/alpha_factory/default.yaml`: `ga.nsga2_selection_enabled: false` 明記。

### テスト計画
- `test_nsga2_selection_disabled_is_bit_exact`: flag False で従来 `_breed_next_gen` と完全一致。
- `test_nsga2_selection_enabled_uses_pareto_front`: 既知 ParetoFeaturesLite 集合で survivor が non-dominated front 優先・crowding 降順。
- `test_nsga2_selection_deterministic_across_runs`: 同 run_id/gen で再現一致。
- `test_nsga2_eligible_excludes_pareto_axis_unusable`: pareto_axis_usable=False を eligible から除外。

### リスク
- eligible（B pass ∧ pareto_axis_usable）が pop_size 未満の世代で survivor 不足 → `sample_size_warnings` で観測、parent_pairs の self-mating fallback を許容（既存 NSGA-II 仕様）。1 RUN smoke で warning 頻度を確認。

---

## P5b: CPPS only injection（step5b）

### 作用点（概念設計で確定）
現行 tournament selection を維持したまま、CPPS archive（CA/DA）から次世代初期枠の `cpps_inject_ratio` 割合を再注入。NSGA-II とは独立。

### 変更箇所
- `config.py` `GAConfig`: `cpps_archive_enabled: bool = False`, `cpps_inject_ratio: float = 0.0`。
- `run_ga.py`: per-generation 用 archive 更新 API を呼び `archive_admit`（CA/DA）。`_breed_next_gen` の初期枠に archive member を注入。
  - **`update_archive_per_run` の意味論不一致回避（Codex Warning）**: per-run API を世代ループで流用せず、**per-generation 用ラッパ `admit_generation_to_archive(...)` を新設**（呼び出し頻度契約を docstring + test で固定）。

### 初期枠の決定論的スロット配分（Codex Critical: warmstart 競合）
`sum<=1.0` だけでは不足のため、**整数スロットを固定優先順で確定**（off-by-one 修正、Codex Critical）:
**`warmstart_active` 定義（Codex Warning: ratio=0.0 で bit-exact 維持）**:
`warmstart_active = (warmstart_ratio > 0.0) and (warmstart_motif_archive usable) and (motif_count > 0)`。
archive が存在するだけでは active にならない（`ratio=0.0` で `warmstart_total=0` = T101 完全行動不変）。`test_warmstart_ratio_zero_bit_exact`。
```
slots = pop_size
warmstart_total = max(1, floor(pop_size * warmstart_ratio)) if warmstart_active else 0
anchor_slots    = min(1, warmstart_total)                 # アンカー(T101 非mutate厳密保持)
warmstart_mut_slots = warmstart_total - anchor_slots       # >=0 保証
cpps_slots      = floor(pop_size * cpps_inject_ratio) if cpps_enabled else 0
# guard: 超過時 cpps を切り詰め
requested_cpps  = cpps_slots
cpps_slots      = max(0, min(cpps_slots, pop_size - warmstart_total))   # requested_inject
# --- 注入を materialize してから breed_slots を再確定（Codex Warning: dedup 後の頭数整合） ---
injected        = dedup_by_genome_hash(anchor個体 + warmstart_mut個体 + cpps個体)  # 注入順で先勝ち
breed_slots     = pop_size - len(injected)        # ★ dedup 後に再確定（>=0）
→ 注入順 anchor → warmstart_mut → cpps → breed。dedup で注入数が減れば breed_slots が増えて pop_size を埋める。
```
- `requested_inject_slots`(=warmstart_total+requested_cpps) と `actual_injected`(=len(injected)) を分離。`select_from_pareto_features(..., offspring_count=breed_slots)` / tournament もこの**再確定後** breed_slots を使う。
- `test_dedup_recomputes_breed_slots_to_pop_size`（注入個体に重複を仕込み、dedup 後も next_gen == pop_size）。
- 実効乖離の可観測化（Codex Warning）: `effective_cpps_slots` / `requested_cpps_slots`(=requested_cpps) / `dedup_dropped_slots` を run log + summary に出力。
- `test_slot_allocation_no_negative`（pop_size=8, warmstart_ratio=0.1, cpps_inject_ratio=0.1 等の境界で全枠 >=0 かつ合計 == pop_size）。`test_slot_allocation_deterministic`（dedup 回帰固定）。

### CPPS 決定論・provenance（conceptual Round 3 Suggestion + Codex Warning）
- 注入対象選択順 / eviction tie-break / 同順位 CA/DA は `_ca_eviction_sort_key` / `_da_eviction_sort_key`（既存 deterministic key）に従い、最終 tie は genome_hash。
- **API 境界で Stage B DTO のみ受ける**（Codex Warning）: `admit_generation_to_archive(candidates: Sequence[ArchiveCandidate])` が ArchiveCandidate（Stage C/holdout/cross-pair フィールドを持たない DTO）のみ受け、eviction sort key も DTO field のみ参照。`test_cpps_admission_api_accepts_stage_b_dto_only`（DTO に Stage C field が無いこと）+ `test_cpps_eviction_sortkey_uses_dto_fields_only`（値面）で両面保証。

### 波及変更
- `AGENTS.md`: warmstart 節の近傍に CPPS injection 設定を追記。
- `config/alpha_factory/default.yaml`: `ga.cpps_archive_enabled: false`, `ga.cpps_inject_ratio: 0.0`。

### テスト計画
- `test_cpps_disabled_is_bit_exact`（ratio 0.0 / flag False で従来一致）。
- `test_cpps_injection_ratio_respected`（指定割合の初期枠が archive 由来）。
- `test_cpps_admission_inputs_stage_b_only`（admission/eviction が Stage C/holdout を参照しない）。
- `test_cpps_eviction_deterministic`。

### リスク
- archive 注入で population 多様性は上がるが探索が散漫化し収束が遅れる可能性 → ratio を小さく（smoke で 0.1–0.2 を試す）。default 0.0 で完全退避。

---

## ablation 実行計画（成功判定）
| 条件 | nsga2 | cpps | 期待観測 |
|------|-------|------|---------|
| ① baseline | F | F | 現行（seed 67→0/68→43/69→0 再現） |
| ② NSGA-II only | T | F | mission候補再現率・primitive-set 多様性 |
| ③ CPPS only | F | T(ratio>0) | 同上（機構別帰属） |
| ④ both | T | T | 上限効果 |
- 各条件 seed 67/68/69 を実行。主指標 = mission 候補が ≥1 出る seed 割合（1/3 → 目標 3/3）。多様性は selection 前 cohort で測定（C3）。

## 実装モード
| 項目 | 内容 |
|------|------|
| 推奨モード | standalone（3 sub-TODO に分割: P3 → P5a → P5b、各別 worktree/PR/smoke） |
| 判断根拠 | selection hot path 変更 + schema 変更を含み他施策と干渉。順次・分離で効果帰属とバグ切り分けを確保（T102 方針一致） |
| 競合リスク | T101 warmstart（初期集団注入）と P5b CPPS injection の初期枠配分が競合 → 詳細は P5b 実装時に warmstart_ratio + cpps_inject_ratio の合算 ≤ 1.0 を guard |
| 想定実装時間 | P3 短 / P5a 中 / P5b 中 |
