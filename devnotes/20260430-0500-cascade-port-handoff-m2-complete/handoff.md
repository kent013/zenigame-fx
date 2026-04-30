# Selection Cascade Port — Session Handoff (M2 完了時点)

**作成日時**: 2026-04-30 05:00 JST
**Session**: M2 (評価層) 完了、 全 4 TODO (T061-T064) 設計フェーズ完了
**前セッション**: M1 (基盤層 T058-T060) → 中間 M2 部分 (T061-T062) → 本セッション M2 完了 (T063-T064)
**次セッション**: M3 (GA 中核 T065-T066) から続行予定

---

## 0. 現在地 (Where we are)

### 完了済 (M1 + M2 全完了)

**M1 基盤層** (前セッション完了):
- T058 Schema v2 contract: 概念 4 round + 詳細 7 round で APPROVED + TODO 登録済
- T059 Epoch / Window Manager: 概念 5 round + 詳細 2 round で APPROVED + TODO 登録済
- T060 Partition + fold generator: 概念 2 round + 詳細 2 round で APPROVED + TODO 登録済

**M2 評価層** (中間セッション + 本セッション完了):
- **T061 canonical 5 engine**: 概念 3 round + 詳細 3 round で APPROVED + TODO 登録済 (中間セッション)
- **T062 mission_inf_gap engine**: 概念 2 round + 詳細 2 round で APPROVED + TODO 登録済 (中間セッション)
- **T063 Stage A evaluator**: 概念 3 round + 詳細 2 round で APPROVED + TODO 登録済 (本セッション)
- **T064 Stage B + C-lite + C evaluator**: 概念 3 round + 詳細 3 round で APPROVED + TODO 登録済 (本セッション、 M2 最大)

### 未着手 (M3 以降)

- T065 NSGA-II + 主選抜 (B-pooled 指標で計算)
- T066 CPPS 2-state FSM (push/pull) + CA/DA archive admission/eviction
- T067 Loop closure (warmstart + emergency mode + calibrate-gate scope + 3 層流入 archive admission)
- T068-T069 (Failure handling / Calibrate scope / Emergency mode)
- T070 Backtest engine 拡張 (session bucket / business_day_index / spread_cost / cross-pair backtest)
- T071-T072 (Observability / DST/holiday boundary contract)
- T073-T075 (Audit / Graduation / Smoke)

### 重要: 設計のみ完了、 実装はまだ

T058-T064 全 7 TODO は **devnotes/ の概念設計 + 詳細設計のみ完了**、 src/ に新規コードは未実装。 既存 stage_gate.py / swim_lane.py / archive.py / cross_pair.py には**一切 touch していない**。

---

## 1. 全体ロードマップ

| Milestone | TODO 範囲 | 進捗 |
|---|---|---|
| **M1: 基盤層** | T058-T060 | ✅ **完了** |
| **M2: 評価層** | T061-T064 | ✅ **完了** (本セッションで全 4 TODO 設計 APPROVED) |
| **M3: GA 中核** | T065-T066 (NSGA-II + CPPS 2-state) | 次セッション |
| **M4: Loop+緊急** | T067-T069 | 後続 |
| **M5: Engine+DST+Observability** | T070-T072 | 後続 |
| **M6: Audit+Graduation+Smoke** | T073-T075 | 最終 |

---

## 2. 本セッションで完成した M2 残 (T063 + T064)

### T063 Stage A evaluator

**設計**: `devnotes/20260430-0130-todo-T063-stage-a-evaluator/`
**最終 review**: 詳細設計 Round 2 で APPROVED 条件付き (Warning 4 件吸収済)

**主要成果**:
- T061 canonical 5 engine の出力を消費し、 q_force 動的計算 + A→B 乖離自動引き上げ + 世代内 top-N 選抜を行う state-immutable pure function
- `evaluate_generation(state, inputs, *, evaluate_fn, live_criteria) -> tuple[StageAResult, new_state]` で immutable state pass-through (controller class 廃止)
- `derive_stage_a_thresholds(live_criteria)` で T061 thresholds を Stage A 用 (8w 比例) に派生 (Decision 1, 2, 4 確定: trade_count proportional / net_pnl proportional / 下限 ceil + 上限 floor)
- q_force 動的: `clamp(0.15 + 0.15 × max(0, 0.10 - feasible_ratio_ema)/0.10, 0.15, 0.30)`
- A→B 乖離自動引き上げ: `divergence_offset_steps: int >= 0` (unsigned)、 corr<0.5 で +1、 corr>=0.5 で -1、 上限 0.40 (= base_q_force_max + N steps)
- C7 sample-size guard: corr 計算で `n<10` ValueError、 `10<=n<30` INCONCLUSIVE (state 不変)、 `n>=30` 通常更新
- deterministic tie-break: top q_force% 選抜は `(-score, index)` で同点時 index 昇順
- default-deny 契約: `a_pass_indices` のみ返し、 caller (T065) が補集合を Pareto 圧から除外する責務

**Phase 2 申し送り (T065 統合と同時、 別 PR)** 8 箇所:

| # | ファイル / 箇所 | 担当 |
|---|---|---|
| 1 | `stage_gate.py:evaluate_stage_a` 全廃 → T063 evaluate_generation に置換 | T065 |
| 2 | (新規) `ga/stage_a_orchestrator.py`: T065 NSGA-II loop の T061 → T063 chain | T065 |
| 3 | `run_ga.py`: per-generation T063 evaluate_generation + Run 終了時 update_divergence_state | T065 |
| 4 | (新規) `observability/a_b_divergence.py`: corr 計算 + T063 注入 | T071 |
| 5 | `config.py:StageGateConfig` 旧 stage_a.* 全廃、 stage_a.window_days: 56 のみ | T065 |
| 6 | `default.yaml` 旧 stage_gate.stage_a.* 全廃、 stage_a.window_days: 56 のみ | T065 |
| 7 | `archive.py`: A-fail 個体を archive admission 全段階から排除 + default-deny test | T067 |
| 8 | T063 controller state を archive metadata or run cache に保存 | T067 |

### T064 Stage B + C-lite + C evaluator

**設計**: `devnotes/20260430-0230-todo-T064-stage-bc-evaluator/`
**最終 review**: 詳細設計 Round 3 で APPROVED (M2 最大 TODO、 Critical 5+1 件 + Warning 多数を全反映)

**主要成果**:
- 3 stage を 1 module で扱う (DRY、 共通 helper を抽出): `evaluate_stage_b` / `evaluate_stage_c_lite` / `evaluate_stage_c` + top-level `evaluate_bc_for_a_pass`
- **Stage B**: 5 fold rolling-origin pooled OOS canonical 5 worst aggregation
  - **`build_pooled_oos_input` で fold 境界 aware** (各 fold で running_max reset、 擬似 DD 防止)
  - **DD 集約: `pooled_dd_per_fold_max = max over folds of fold.max_dd`** (synthesis § 5.2 準拠)
  - **`compute_gate_pass_excluding_dd`** で max_dd 軸を除いた gate_pass を計算、 `is_b_pass = gate_pass_ex_dd AND dd_pass` で concat DD 経路完全遮断
  - 1 fold でも invariant fail → `b_pooled_cf_result=None`、 Pareto 軸 source として使用不可 (T065 PR DoD で検証 test 必須)
- **Stage C-lite**: 3 disjoint windows × canonical 5 worst → 15 セル worst (= max over 3 windows of gate_worst_gap)
  - `mission_pass = StagePassStatus.PASS` if 全 3 windows pass、 `progress_pass = PASS` if 2/3 pass
  - `SampleSizeFlag` (OK/BOUNDARY/INSUFFICIENT)、 INSUFFICIENT 時 mission/progress を PENDING 強制
- **Stage C**: 12w + spread stress (×1.5) + cross-pair shadow (anchor 除く 5 pair で 5/5 全通過)
  - `StagePassStatus` Enum (PASS/FAIL/PENDING) で tri-state、 spread_stress_supported=False (default) なら stress=PENDING、 mission_pass=PENDING
  - 完全 truth table 実装 (FAIL 優先、 6 パターン parameterized test)
  - `mission_fail_reason` で FAIL 理由を保持 (T071 observability 用)
  - `PairBacktestBundle.validate_against(anchor_bundle)` で provenance guard (genome_id / config_hash / partition_label 一致検証)
- **A→B 乖離 corr 計算源**: `compute_a_b_correlation_source_score(cf_result) = 1 / (1 + max(0, gate_worst_gap))` (higher-is-better で正規化)、 `compute_a_b_correlation` で deterministic 戻り値 (StatisticsError catch + isfinite check)

**Phase 2 申し送り (T065 統合 + T070 と同時、 別 PR)** 11 箇所:

| # | ファイル / 箇所 | 担当 |
|---|---|---|
| 1 | `stage_gate.py:evaluate_stage_b` 全廃 → T064 | T065 |
| 2 | `stage_gate.py:evaluate_stage_c` 全廃 → T064 | T065 |
| 3 | (新規) `stage_gate.py:evaluate_stage_c_lite` → T064 | T065 |
| 4 | `cross_pair.py` を T064 per_pair_results 統合 | T065 |
| 5 | (新規) `observability/a_b_divergence.py` → T064 compute_a_b_correlation 呼出 + T063 注入 | T071 |
| 6 | `run_ga.py` per-generation T063 → T064 → T062 chain | T065 |
| 7 | `config.py:StageGateConfig` 旧 stage_b/c.* 全廃、 新仕様 | T065 |
| 8 | `default.yaml` 旧 stage_b/c.* 全廃、 新仕様 + cross-pair list | T065 |
| 9 | `archive.py` で 3 層流入 (mission_pass/progress_pass/score_bypass) を BCEvaluationResult から識別 | T067 |
| 10 | (別 TODO) `TradeRecord.spread_cost` field 追加 + apply_spread_stress 正式実装 | T070 |
| 11 | `docs/stage-gates.md` を新仕様に書き換え | T065 |

---

## 3. 次セッションの開始手順

### 3.1 まず読むもの (15 分)

1. **本ハンドオフ**: `devnotes/20260430-0500-cascade-port-handoff-m2-complete/handoff.md` (これ)
2. **synthesis 全体**: `devnotes/20260428-2300-cascade-port-debate/synthesis.md` (特に § 7 NSGA-II + CPPS、 § 8 Archive/Sieve)
3. **TODO リスト**: `docs/alpha_factory/TODO.md` (T058-T064 が Open に登録済)
4. **M2 完了 4 TODO の詳細設計** (T065-T066 で参照、 特に T064 が最重要)
5. **前セッション handoff (履歴参照のみ、 active ではない)**:
   - `devnotes/cascade-port-handoffs-historical/20260430-0100-m2-mid/handoff.md` (M2 中間時点)
   - `devnotes/cascade-port-handoffs-historical/20260429-2245-m1-complete/handoff.md` (M1 完了時点)
   - **canonical な引き継ぎは本ファイル (M2 完了時点) のみ**、 過去 handoff は historical/ に archive 済

### 3.2 T065 開始時のチェックリスト

T065 (NSGA-II core + 主選抜 B-pooled) は M3 の最初の TODO:

- 評価値: synthesis § 3 「主選抜評価値 = Stage B pooled」、 T064 `BCEvaluationResult.b_pooled_cf` を消費
- Pareto 3 軸 (synthesis § 6.5):
  - f1: maximize `net_pnl_after_cost` (T061 出力)
  - f2: minimize `max_dd` (T064 `pooled_dd_per_fold_max` 推奨、 concat DD 回避)
  - f3: minimize `mission_inf_gap` (T062 出力)
- **constrained-domination (Deb 2000)** 必須: feasible vs infeasible は feasible が unconditionally dominate、 infeasible 同士は constraint_violation 小さい方が dominate (T062 詳細設計の T065 申し送り参照)
- pop=192 baseline / 256 promotion、 gen=64
- selection: NSGA-II rank + 標準 crowding (3 軸正規化) + deterministic tie-break (genome_hash)
- A-fail 個体は Pareto 圧計算から除外 (T063 default-deny 契約)
- B-fold-invariant-fail 個体 (b_pooled_cf=None) は Pareto 軸 source から除外 (T064 [C2] 契約)
- T065 PR DoD で「test_a_fail_individual_excluded_from_nsga_selection」 「test_b_invariant_fail_individual_excluded_from_pareto_axis」 必須

参考: synthesis § 7.1 (NSGA-II core) / § 7.2 (Push/Pull FSM) / § 7.3 (CA/DA 配分)
zenigame: `ga/nsga2/optimize.py` / `breeding.py` / `archives.py`

### 3.3 T066 開始時のチェックリスト

T066 (CPPS 2-state FSM + CA/DA admission/eviction) は M3 の 2 番目:

- Push/Pull FSM (synthesis § 7.2、 zenigame `push_pull_fsm.py:45` 同等):
  - push state: CA 84 / DA 108 (pop=192)、 infeasible 領域許容
  - pull state: CA 120 / DA 72、 feasible 領域収束
  - 遷移: feasible_ratio_ema >= θ_switch (smoke 後再校正)、 一方向 (push → pull のみ)
- CA/DA 動的比率 + offspring → CA/DA 振り分け
- archive admission: T064 `BCEvaluationResult.mission_pass` の 3 層流入 (mission_pass / progress_pass / score_bypass)
- archive eviction: lex 順序 (synthesis § 8.3、 CA #5 = `mission_signed_margin` (T062)、 CA #6 = `shadow_robustness_score` (T064))

参考: synthesis § 7.4 (offspring) / § 8.1-8.3 (Archive 構成 + admission + eviction)

### 3.4 設計フローのテンプレート (T061-T064 と同じ)

```
1. devnotes/{YYYYMMDD-HHMM}-todo-T{NNN}-{topic}/ ディレクトリ作成
2. 概念設計 → Codex 概念レビュー (gpt-5.4 / medium) → APPROVED まで Round
3. 詳細設計 → Codex 詳細レビュー (gpt-5.3-codex / high) → APPROVED まで Round
4. /zenigame-fx-todo-add で TODO 登録
```

### 3.5 重要な原則 (T065-T066 でも遵守)

- **Phase 1 / Phase 2 分離**: 各 TODO PR は単体テストのみで runtime 未組込
- **Phase 2 申し送りを設計時に明示**: 後段で同時更新が必要な箇所を漏らさず列挙
- **C2 parallel-path 5 段階 grep**: T062-T064 で確立した 5 段階手順 (直 import / alias / relative / 再エクスポート / runtime シンボル)
- **C4 前提検証**: 設計書冒頭で `main@<commit>` 基準を明示
- **synthesis 確定値を変えない**: 安易な変更禁止、 矛盾発見時は synthesis 改訂 PR を別途 (T062 の §8.3 mission_margin 命名矛盾と同じ手順)

### 3.6 T065-T066 が消費する依存先 module (T058-T064 すべて)

- **T060 Partition+Fold**: Period / Fold dataclass
- **T061 canonical_metrics**: `CanonicalFiveResult` / `evaluate_canonical_five` / `BarEquitySeries`
- **T062 mission_inf_gap**: `MissionGapResult` / `evaluate_mission_inf_gap` / `compute_constraint_violation`
- **T063 stage_a_evaluator**: `StageAControllerState` / `evaluate_generation` / `update_divergence_state`
- **T064 stage_bc_evaluator**: `BCEvaluationResult` / `evaluate_bc_for_a_pass` / `StagePassStatus` / `compute_a_b_correlation`

### 3.7 注意事項 (T064 で発生した重要な設計決定)

- **Stage B DD 集約 = `pooled_dd_per_fold_max`**: concat DD は擬似 DD を含むので Pareto 軸 source / B pass 判定で使わない (T064 詳細 Round 2 [Critical] で確立)
- **`compute_gate_pass_excluding_dd`**: max_dd 軸を除いた 4 指標で gate_pass を計算する helper (T064 詳細設計提供、 T065 PR で b_pooled_cf 消費時に使用)
- **synthesis § 8.3 mission_margin の semantic 矛盾**: T062 で発見、 `mission_signed_margin = min(slack_*4)` を新設 (実用 SSOT)。 synthesis § 8.3 改訂 PR は T064 PR 完了後に別途 (本セッション完了で synthesis 改訂のタイミングが到来)

---

## 4. リソース / Contact 点

### 4.1 重要 docs / devnotes

| 場所 | 内容 |
|---|---|
| `devnotes/20260428-2300-cascade-port-debate/synthesis.md` | 設計上位文書 21 章 |
| `devnotes/20260429-1912-todo-T058-schema-v2-contract/` | T058 設計 (M1) |
| `devnotes/20260429-2113-todo-T059-epoch-window-manager/` | T059 設計 (M1) |
| `devnotes/20260429-2210-todo-T060-partition-fold-generator/` | T060 設計 (M1) |
| `devnotes/20260429-2300-todo-T061-canonical-five-engine/` | T061 設計 (M2) |
| `devnotes/20260430-0030-todo-T062-mission-inf-gap-engine/` | T062 設計 (M2) |
| `devnotes/20260430-0130-todo-T063-stage-a-evaluator/` | T063 設計 (M2) |
| `devnotes/20260430-0230-todo-T064-stage-bc-evaluator/` | T064 設計 (M2 最大) |
| `devnotes/20260430-0500-cascade-port-handoff-m2-complete/handoff.md` | **本ハンドオフ (M2 完了、 canonical な引き継ぎ)** |
| `devnotes/cascade-port-handoffs-historical/20260429-2245-m1-complete/handoff.md` | M1 完了時 handoff (履歴参照のみ) |
| `devnotes/cascade-port-handoffs-historical/20260430-0100-m2-mid/handoff.md` | M2 中間 handoff (履歴参照のみ) |
| `docs/alpha_factory/TODO.md` | TODO 一覧 (T058-T064 が Open に登録済) |
| `AGENTS.md` | プロジェクト全体規約 |

### 4.2 zenigame コード参照 (T065-T066 で参考)

| 機構 | zenigame ファイル |
|---|---|
| GA optimize loop | `/Users/ishitoya/repository/zenigame/src/trading/alpha_factory/ga/nsga2/optimize.py:950, 1006/1195, 2125/2141` |
| Push/Pull FSM (2-state) | `.../ga/nsga2/push_pull_fsm.py:45` |
| CA/DA Two-Archive | `.../ga/nsga2/archives.py` |
| breeding (parent selection, crossover, mutation) | `.../ga/nsga2/breeding.py:211, 255` |
| Sieve filter (4 層流入) | `.../alpha_sieve/filter.py` |
| Archive admission/eviction | `.../alpha_sieve/archive_updater.py:123` |
| determinism (RNG seed) | `.../ga/nsga2/core.py:114, 1026/1085` |

### 4.3 Codex 呼び出し方 (T061-T064 と同じ)

- 概念レビュー: `gpt-5.4` / `medium`、 label `conceptual-review`
- 詳細レビュー: `gpt-5.3-codex` / `high`、 label `detailed-review`
- skill: `zenigame-fx-codex-review`
- **重要**: Codex は file read を「コマンド実行禁止」 と誤解釈して拒否することがある。 Round 1 で本文を inline で貼り付けるのが確実 (本セッションで全 Round で確認)

### 4.4 TODO 登録方法

```bash
uv run python scripts/alpha_factory/todo_manager.py add \
  --id "T0XX" \
  --title "T0XX-{topic}" \
  --theme "{stage-gate|infrastructure|ga-architecture|...}" \
  --summary "..." \
  --priority "Critical" \
  --mode "incremental" \
  --design-link "[設計](devnotes/{dir}/)" \
  --added-at "$(TZ=Asia/Tokyo date '+%Y-%m-%d %H:%M')"
```

---

## 5. 進捗状況サマリー

```
synthesis  ████████████████████ 100% (Codex × 20 round で確定)
M1 (基盤)  ████████████████████ 100% (T058-T060 完了)
M2 (評価)  ████████████████████ 100% (T061-T064 完了)
M3 (GA)    ░░░░░░░░░░░░░░░░░░░░   0% (T065-T066 未着手)
M4 (Loop)  ░░░░░░░░░░░░░░░░░░░░   0% (T067-T069 未着手)
M5 (Eng)   ░░░░░░░░░░░░░░░░░░░░   0% (T070-T072 未着手)
M6 (Fin)   ░░░░░░░░░░░░░░░░░░░░   0% (T073-T075 未着手)
```

**全体進捗**: 設計 18 件中 7 件完了 (38.9%)、 実装は 0%

---

## 6. 次セッションの最初の指示テンプレート

ユーザが次セッションで以下のように指示すると即座に再開可能:

> 引き継ぎは `devnotes/20260430-0500-cascade-port-handoff-m2-complete/handoff.md` 読んで。 T065 (NSGA-II core + 主選抜 B-pooled) から続行してください。 同じ flow (概念設計 → Codex レビュー APPROVED → 詳細設計 → Codex レビュー APPROVED → TODO 登録) で。

---

## 補足: 本セッションで学んだこと (T065-T066 で適用)

- **synthesis 内部矛盾の発見と対処**: T062 で synthesis § 8.3 「mission_margin = -mission_inf_gap、 達成超過余裕」 の数式と命名矛盾を発見。 解決策: synthesis 命名は backward compat で保持、 実用 SSOT は別 field (mission_signed_margin)、 synthesis 改訂は別 PR で。 T064 では追加発見なし
- **DD 集約の擬似 DD 問題**: Stage B pooled で concat DD は fold 境界の擬似 DD を含むため、 per-fold DD max を採用。 さらに `compute_gate_pass_excluding_dd` で gate_pass の max_dd 軸も別経路化 (T064 詳細 Round 2 [Critical])
- **truth table 完全網羅の重要性**: Stage C tri-state (PASS/FAIL/PENDING) で FAIL 優先ルールを明示しないと PENDING 漏れが発生。 6 パターン parameterized test で 1:1 対応
- **provenance guard (cross-pair 系)**: PairBacktestBundle に validate_against method、 anchor との genome_id / config_hash / partition_label 一致を必須化。 別設定・別期間の shadow 混入を fail-closed で防止
- **Codex 詳細レビューの Critical 多発**: T064 詳細 Round 1 で Critical 5 件、 Round 2 で Critical 1 件。 数式準拠 / 例外契約 / 値域 / provenance / -O 対策 (assert→raise) が頻出
- **Decision Pending の早期解決**: T063 で 4 つの Decision (trade_rate denominator / net_pnl window-aware / top-N rounding / asymmetric rounding) を概念設計内で先取り解決、 INCONCLUSIVE タグで smoke 後再校正候補化。 後の手戻りを最小化
- **state immutability の徹底**: T063 で controller class 廃止、 全 helper を pure function 化、 `evaluate_generation(state, inputs) -> (result, new_state)` で immutable 一貫。 test 容易性 + state 一貫性確保
- **C7 sample size の積極的判定**: T063 で `n<10` ValueError、 `10<=n<30` INCONCLUSIVE。 T064 で SampleSizeFlag (OK/BOUNDARY/INSUFFICIENT)、 INSUFFICIENT は PENDING 強制。 C7 の系統的適用

これらの教訓は次セッションでも継続適用する。

---

## 7. synthesis 改訂 PR (T065 着手前または並行で別 PR 推奨)

T064 完了で synthesis 内部矛盾の修正条件が満たされた。 **T065 概念設計開始前 or 並行で別 PR を切る**ことを推奨:

### 改訂対象 (synthesis.md)

| 章 | 現状 (矛盾あり) | 改訂後 |
|---|---|---|
| § 8.3 archive eviction CA #5 | `mission_margin (= -mission_inf_gap、 達成超過余裕)` (数式と命名乖離、 値域 <= 0 で達成超過を表現不能) | `mission_signed_margin (= min(slack_sharpe, slack_pnl, slack_dd, slack_tc)、 4 指標 signed slack の min)` (T062 で実装済の暫定 SSOT を昇格) |
| § 6.4 / § 6.5 補足 | (現状 mission_inf_gap = max(...) のみ) | mission_inf_gap は Pareto f3 minimize 用、 mission_signed_margin は archive CA #5 ordering 用、 と用途分離を明記 |
| § 15 残論点追記 | (現状 12 項目) | 13. mission_signed_margin smoke 後再校正候補 (denom 正規化、 通過率 vs 強度のバランス) を追記 |
| § 17 用語追加 | mission_margin のみ | mission_signed_margin (実用 SSOT) と mission_margin (BACKWARD COMPAT) の 2 entry に整理 |
| § 21 議論履歴 | Round 11-20 のみ | Round 21 として「T064 完了で mission_margin 命名矛盾を発見、 mission_signed_margin 新設 + synthesis 改訂」 を追記 |

### 改訂 PR の手順

```
1. 別ブランチ切る: synthesis-revise-mission-signed-margin
2. devnotes/{YYYYMMDD-HHMM}-synthesis-revise-mission-signed-margin/ 作成
3. 改訂前後の diff を rationale ドキュメントで明示
4. synthesis.md 更新 (上記 5 章)
5. T062 詳細設計の「synthesis § 8.3 改訂候補」 言及を「改訂済」 に更新 (devnotes 内)
6. T064 詳細設計の「synthesis § 8.3 改訂は T064 PR 完了後」 言及を更新
7. main に merge (実装影響なし、 docs 改訂のみ)
```

T065 設計時に「synthesis 改訂済」 として参照可能にしておく。 T065 / T067 の archive eviction 設計が CA #5 = mission_signed_margin で確定した synthesis に依拠できる。

---

## 8. 実装フェーズへの移行判断 (Decision Pending、 ユーザ判断要)

設計フェーズ完了タイミングの選択肢:

| 案 | 内容 | 利点 | 欠点 |
|---|---|---|---|
| **A: M3-M6 設計を先に全完成** | T065-T075 全 11 TODO の設計を完了させてから実装着手 | 全体整合性が高い、 設計時点で発見した矛盾を全反映可能 | 実装着手まで時間が長い、 設計時点で見つけられない実装制約が後で出る可能性 |
| **B: M3 完了で実装フェーズ並列化** | T065-T067 (M3+M4 前半) 設計完了で T058-T064 の実装を並行開始 | 実装フィードバックを後段設計に反映可能、 全体時間短縮 | M3-M4 設計と implement の同時進行で整合性ぶれリスク |
| **C: M2 完了で M1 実装フェーズ開始** | T058-T064 の設計を全 APPROVED 済の今、 T058 から順次実装開始 | 早期実装で smoke 観測前倒し、 INCONCLUSIVE Decision の検証可能 | M3-M6 設計が遅れる、 大型 cascade port の big-bang 性が薄れる |

**推奨**: **案 B (M3 完了で実装フェーズ並列化)**。 理由:
- M3 (T065-T066) は GA 中核、 これが固まれば evaluator 群 (T061-T064) の consume 仕様が確定
- T067 (Loop closure) は archive admission/eviction で T064 出力契約を消費、 ここまで設計揃えば T058-T067 の実装を並行で着手可能
- M5 (T070 backtest engine) は T061 入力契約への準拠で大物だが、 T058-T067 の実装と並行で進められる
- 設計でカバーしきれない実装制約は smoke (T075) 前に observability (T071) で吸収

**判断保留**: ユーザが本 handoff を読んだ時点で M3 設計後に実装を始めるか、 M6 まで設計完了させるか確認したい。

---

## 9. M3 (T065-T066) の重要事項先取り

T065-T066 は M3 で **GA 中核**。 これまでの M1+M2 設計を統合運用する最初の TODO。 注意点:

1. **Pareto 軸 source の二重契約**: f1=net_pnl + f2=max_dd は T064 から取る (concat DD でない `pooled_dd_per_fold_max` を使う)、 f3=mission_inf_gap は T062 から取る
2. **constrained-domination 必須**: T062 詳細設計で T065 申し送りに「Deb (2000) constrained-domination 実装が必須」 と明記済。 T065 概念設計で疑似コードを再確認:
   ```python
   def constrained_dominates(p, q):
       if p.is_feasible and not q.is_feasible: return True
       if not p.is_feasible and q.is_feasible: return False
       if not p.is_feasible: return p.constraint_violation < q.constraint_violation
       return p.dominates_pareto(q)
   ```
3. **A-fail / B-fold-invariant-fail 個体の排除**:
   - T063 a_pass_indices に含まれない個体 (= A-fail) → Pareto 圧計算から除外
   - T064 b_pooled_cf=None (= B fold invariant fail) → Pareto 軸 source として使用不可
   - T065 PR DoD で両方の検証 test 必須
4. **synthesis § 8.3 改訂 PR**: T064 完了で synthesis 改訂の condition が満たされた。 T065 設計開始前か並行で synthesis § 8.3 (CA #5 = mission_signed_margin)、 § 15 (残論点追記) を改訂する別 PR を出す検討 (詳細は § 7 参照)

---

## 10. Codex Review 統計 (M1+M2 集計、 監査・トラブルシュート用)

### 全 7 TODO の Round 数集計

| TODO | 概念 Rounds | 詳細 Rounds | 合計 | 主な Critical 修正 |
|---|---|---|---|---|
| T058 | 4 | 7 | 11 | schema lint / artifact inventory / contract version 共存 |
| T059 | 5 | 2 | 7 | atomic reservation / fail-closed reset / RSS gate |
| T060 | 2 | 2 | 4 | UTC 厳密性 / Phase 2 申し送り 9 箇所 |
| T061 | 3 | 3 | 6 | denom_floor 1e-6 厳密 / annual 換算単一化 / WR neutral 0.5 経路 / max_dd 値域 / business_day_universe 必須化 |
| T062 | 2 | 2 | 4 | sentinel +inf 撤廃 / constraint_violation 新設 / mission_signed_margin 新設 (synthesis 矛盾発見) |
| T063 | 3 | 2 | 5 | T061 orchestration 統合 / divergence_offset_steps unsigned / immutable state / Decision 1-4 |
| T064 | 3 | 3 | 6 | StagePassStatus tri-state / build_pooled_oos_input / cross-pair anchor 除外 / compute_gate_pass_excluding_dd |
| **合計** | **22** | **21** | **43** | — |

### Codex review コスト (gpt-5.4 medium = 概念、 gpt-5.3-codex high = 詳細)

- 概念レビュー: 22 round × ~30K tokens/round ≈ 660K tokens
- 詳細レビュー: 21 round × ~50K tokens/round ≈ 1050K tokens
- 合計: ~1.7M tokens (gpt-5.4 / gpt-5.3-codex 混在)

### 主要な学び (M3 以降に適用)

- **Codex は常に Critical を出す前提**: Round 1 で APPROVED は稀、 Round 2-3 で Critical 解消が標準
- **synthesis 内部矛盾を発見した場合の対処**: synthesis 改訂 PR を別途出すパターンが確立 (T062 § 8.3)
- **Phase 2 申し送り表は具体ファイル + 行番号必須**: 「申し送り」 という曖昧記述では Phase 2 で漏れ (T060 で経験)
- **Codex の file read 拒否**: `--sandbox read-only` でも誤拒否、 Round 1 の prompt に inline 貼り付けが確実
- **C2 parallel-path 5 段階 grep**: T062 で確立、 直 import / `import as` / relative / 再エクスポート / runtime シンボル
- **C7 sample-size guard 系統化**: T063 で `n<10/10-29/n>=30` 三段、 T064 で SampleSizeFlag (OK/BOUNDARY/INSUFFICIENT)
- **State immutability の徹底**: T063 で controller class 廃止、 全 helper を pure function 化

---

## 11. M2 完了時点の TODO リスト最終形

`docs/alpha_factory/TODO.md` の Open セクション (T058-T064、 7 件 Critical):

```
| ID  | タイトル                          | テーマ           | 設計 | 追加日時 |
| T058| schema-v2-contract               | infrastructure   | ✓    | 2026-04-29 21:12 |
| T059| epoch-window-manager             | infrastructure   | ✓    | 2026-04-29 22:10 |
| T060| partition-fold-generator         | stage-gate       | ✓    | 2026-04-29 22:44 |
| T061| canonical-five-engine            | stage-gate       | ✓    | 2026-04-30 00:00 |
| T062| mission-inf-gap-engine           | ga-architecture  | ✓    | 2026-04-30 00:42 |
| T063| stage-a-evaluator                | stage-gate       | ✓    | 2026-04-30 09:41 |
| T064| stage-bc-evaluator               | stage-gate       | ✓    | 2026-04-30 10:20 |
```

実装は Phase 2 で T065-T067 と統合する形で並行着手 (§ 8 案 B 推奨)。

---

## 12. このセッションでの未解決事項 / 次セッション最初に確認

1. **synthesis 改訂 PR のタイミング**: T065 設計前 / 並行 / 後 — ユーザ判断 (§ 7)
2. **実装フェーズ移行戦略**: 案 A (M6 設計後) / 案 B (M3 設計後) / 案 C (M2 完了の今すぐ) — ユーザ判断 (§ 8)
3. **T065 着手順序**: T065 → T066 並行可能か直列か (T065 NSGA-II が固まらないと T066 archive admission 設計が決まらない、 直列推奨)
4. **synthesis 改訂と T065 設計の依存**: T065 詳細設計で archive eviction を扱う場合、 synthesis 改訂済みの方が引用整合性が高い (synthesis 改訂 PR を T065 概念前に merge 推奨)
