# 概念設計: NSGA-II + CPPS selection を _breed_next_gen に実配線（T102 step3+step5 最短経路）

## verified 前提（C1/C4、親 agent がコードで確認済み）
- `scripts/alpha_factory/run_ga.py:779 _breed_next_gen` = elite + `_tournament`（`_selection_key` 9 要素 lex、末尾 fitness_pen）のみ。NSGA-II/CPPS/crowding 呼び出しは grep で 0 件。
- `src/alpha_factory/nsga2_selection.py` の主入口 `run_generation_selection(population: Mapping[int, IndividualEvaluation])`。`IndividualEvaluation` は `bc_result: BCEvaluationResult|None` / `mission_gap: MissionGapResult` / `invariant_flags: InvariantFlags` を要求。`extract_pareto_axis` は `bc_result.b_pooled_cf.net_pnl_after_cost`(f1 max) / `bc_result.b_result.pooled_dd_per_fold_max`(f2 min) / `mission_gap.mission_inf_gap`(f3 min) を使用 = **3 軸とも Stage B 完結量**。
- `src/alpha_factory/cpps_archive.py` に `archive_admit` / `determine_archive_role` / `compute_archive_capacities` 等実装済。import 元は `loop_closure.py` のみ、その import 元は `observability/run_metrics.py` のみ = **shadow 専用**。
- T102 既存設計: `devnotes/20260513-1915-todo-phase2-integration-step3-7/` が umbrella（step3–7、step5 = `_breed_next_gen` を NSGA-II+CPPS 置換、「NSGA-II と CPPS を同時に入れない」と明記）。

## 背景・課題

### 観察事実（Facts）
- 実 RUN (R82–R85) の世代生成は `scripts/alpha_factory/run_ga.py:779 _breed_next_gen` の **elite + tournament のみ**。tournament は `_selection_key`（9 要素 lex、末尾 `fitness_pen`）に基づく単一目的選択で、多様性保存機構は一切無い。
- `src/alpha_factory/nsga2_selection.py`（NSGA-II 多目的選抜）と `src/alpha_factory/cpps_archive.py`（CPPS archive admission/eviction）は実装済みだが、import するのは `loop_closure.py` のみ、その `loop_closure.py` を import するのは `observability/run_metrics.py` のみ = **shadow（観測）専用で selection 未配線**。
- archive の `canonical_gate_pass_c_shadow` / `persistence_score_shadow` 等は算出されているが次世代生成に影響しない（cross-pair ii-lite が shadow-only なのと同型）。
- seed variance 実測: 同一設定で seed のみ変え、Stage A は 391–2687（7 倍）、Stage B は 62–941（15 倍）、Stage C pass は seed67→0 / seed68→43 / seed69→0。mission 達成は seed=68 の 1 つのみ。
- R83 と R85 は seed=68 で best_genome がビット一致（決定論的）。R85 の Stage C 通過 43 個体は distinct primitive-set 6 / 43（~6 genotype・P7+P9+F4+P11 モチーフ 1 ファミリーへ収束）。

### 解釈（Interpretations、有力仮説）
- 多様性保存ゼロの単一目的トーナメント GA は、初期集団と RNG 経路（= seed）次第で 1 モチーフへ収束しうる。これが seed variance と低 genotype 多様性の**有力な構造的原因仮説**である（断定はしない。seed 標本数が少なく C7 ガード適用）。
- 対立仮説（反証候補、詳細設計で ablation により切り分け）:
  - H-alt1: 主因は selection でなく **objective misalignment**（fitness が live_criteria と乖離）。NSGA-II 化だけでは mission 候補は増えない。
  - H-alt2: **mutation/crossover の探索半径不足**（表現制約）。selection を変えても family が広がらない。
  - H-alt3: 効くのは **CPPS のみで NSGA-II は無効**（or 逆）。
- → これらを切り分けるため、後述の **4 条件 ablation を必須**とする。多様性増加と mission 達成は同義でない点を踏まえ、成功判定は Stage C pass 数でなく **mission 候補再現率 / live_criteria 同時充足率**に置く。

## 改善アイデア

T102 umbrella（Phase 2 統合 step3–7）のうち、本ゴールに必要な **step3 と step5 のみ** を最短で配線する。

- **step3**: Stage B 評価から **selection 専用の scalar sidecar `ParetoFeaturesLite`**（net_pnl_after_cost / pooled_dd_per_fold_max / mission_inf_gap の 3 scalar + feasibility/invariant flags のみ）を per-individual に供給。`BCEvaluationResult` 全体を multiprocessing 境界で流さない（trade/equity 配列は持たない = メモリ・性能保護）。判定は従来 `_selection_key` のまま = 行動不変（dual-path LOG_ONLY）。
- **step5a（NSGA-II only）**: `_breed_next_gen` の parent/survivor 選抜を NSGA-II（non-dominated sort + crowding）に置換。CPPS は入れない。`GAConfig.nsga2_selection_enabled`（default False）で gate、OFF で bit-exact。
- **step5b（CPPS only）**: 別 flag `GAConfig.cpps_archive_enabled`（default False）で CPPS archive admission（CA/DA、diversity memory）を積む。step5a 完了・smoke 後に分離導入。

→ NSGA-II と CPPS を**同一 PR で同時に効かせない**（効果帰属・反証可能性のため。T102「同時に入れない」方針と一致）。step4（stage_a_evaluator）/ step6（loop_closure warmstart 統合）/ step7（failure_handling）は本ゴール不要、T102 umbrella 配下で後続。

### Pareto 軸の出所（決定）
**案 A（BCEvaluationResult 忠実、3 軸とも Stage B 完結量）に固定**。
- 案 B（archive holdout metric 流用）は **破棄**。理由: holdout（Stage C）/cross-pair は North Star の「検証・最低条件レーン」であり、それを selection（探索器の最適化対象）に昇格させると検証の独立性が壊れ、禁止事項 2（見かけ数値改善）/3（GA ハック）/8（値伝搬）に抵触する。
- archive は **diversity memory + admission のみ**に使い、selection 軸の値源泉には使わない。
- `mission_inf_gap` は **Stage B 可観測量のみ**で定義。各構成要素に `source_stage=B` を明記し、Stage C/holdout/cross-pair 参照を**テスト観点で禁止検証**（詳細設計で式・算出窓・入力元を 1 行ずつ固定）。Pareto 軸が live_criteria にどう接続するかも詳細設計で明文化。

## 期待効果と成功判定（acceptance criteria、事前固定）
- 主指標: **mission 候補再現率** = seed 67/68/69 のうち live_criteria 全充足個体（mission candidate）が ≥1 出る seed の割合。R85 時点 1/3 → 目標 3/3。
- 副指標: live_criteria 各項目（sharpe/total_pnl/max_dd/trade_count）の**同時充足率**、Stage C 通過個体の distinct primitive-set 数（R85: 6/43 比で増加）。
- 多様性測定は **selection 前 cohort（全 evaluated 個体）** で行う（C3 collider 回避。Stage C pass subset 上の相関で軸妥当性を語らない）。
- **4 条件 ablation（必須、同一 seed セットで比較）**: ①baseline（現行 tournament）②NSGA-II only ③CPPS only ④NSGA-II+CPPS。これにより H-alt1/2/3 を切り分け、効果を機構別に帰属する。
- shadow 追加指標: parent lineage concentration / mutation novelty（H-alt2「探索半径不足」の観測用）。
- 注: 多様性増加は mission 達成の十分条件ではない。本サイクルの判定は「再現率が改善するか」であり、改善しなければ objective misalignment 等の別仮説へ早期に見切る。

## 実装方針（概要、step3 / step5a / step5b 分割に厳密対応）
1. **step3（LOG_ONLY、行動不変）**: swim_lane 評価経路で **`ParetoFeaturesLite`**（net_pnl_after_cost / pooled_dd_per_fold_max / mission_inf_gap の 3 scalar + feasibility/invariant flags）を per-individual sidecar として算出・添付。`BCEvaluationResult` 全体や trade/equity 配列は MP 境界に流さない。判定は従来 `_selection_key` のまま。
2. **step5a（NSGA-II only）**: `run_ga.py:_breed_next_gen` に NSGA-II 経路を追加。`GAConfig.nsga2_selection_enabled`（default False）。ON 時のみ `ParetoFeaturesLite` から `ParetoAxis` を構築し non-dominated sort + crowding で survivor/parent を決定。CPPS は使わない。OFF で bit-exact。
3. **step5b（CPPS only）**: `GAConfig.cpps_archive_enabled`（default False）。**作用点 = 現行 tournament selection を維持したまま、CPPS archive（CA/DA）から次世代初期枠の一定割合 `cpps_inject_ratio`（diversity memory からの再注入）を供給**する形で配線。`archive_admit` で世代跨ぎ multi-niche を保存し、収束した population に archive 由来の多様な個体を注入する。NSGA-II とは独立 flag。
   - ablation ③CPPS only = `nsga2_selection_enabled=False` ∧ `cpps_archive_enabled=True`（tournament + CPPS 注入）として実験条件が成立する。
   - ablation ④両方 = 両 flag True（NSGA-II selection + CPPS 注入）。

## 制約・前提
- default OFF で baseline と bit-exact 一致（既存テスト全 pass）。flag は step5a/5b で独立。
- メモリ: selection には trade/equity 配列を持たず `ParetoFeaturesLite`（3 scalar + flags）のみ流す。詳細設計で「個体数 × 世代 × row size」概算を提示し 24GB / 6 worker / 3GB/worker 内を確認。
- archive スキーマ伝搬: 詳細設計に「config → GAConfig → runtime meta → archive row → consumer/test」の接続表を必須添付（禁止事項 8 / zenigame 転記漏れ再発防止）。
- 各 step（step3 / step5a / step5b）で個別 PR・個別 1 RUN smoke。
- 決定論: NSGA-II の tie-break は `make_selection_seed(run_id, gen)` で run 跨ぎ deterministic。

## 詳細設計への申し送り（Codex conceptual-review Round 3 Suggestion）
1. **CPPS の決定論を固定**: 注入対象の選択順 / archive eviction tie-break / 同順位 CA/DA の扱いを deterministic に（seed 間比較・smoke 再現性のため）。
2. **CPPS admission/eviction の入力 provenance を `source_stage=B` or diversity-only に限定**（archive 経由の間接的な Stage C/holdout/cross-pair 逆流を防ぐ）。テスト観点に追加。
3. mission_inf_gap の式・算出窓・入力元を 1 行ずつ固定し、source_stage=B をテストで検証。

## スコープ外
- T102 step4 / step6 / step7。
- T075 big-bang 切替（旧 BacktestMetrics 経路削除）。
- live_criteria 閾値の変更（緩和も引き上げも本サイクルでは行わない）。
- cross-pair ii-lite の gate 化（別レーン）。
