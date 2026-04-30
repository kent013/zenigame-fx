[VERDICT] REVISE REQUIRED

[Critical]
1. **Stage C の spread stress placeholder が仕様準拠を壊しています。**  
   本文では Phase 1 で `apply_spread_stress` を `NotImplementedError`、同時に `stress_pass=True` placeholder を返す案になっていますが、これは synthesis §5.4 の「live_criteria AND + stress pass + cross_pair pass」を満たしていないのに満たした形の戻り値を作る設計です。未統合でも、`StageCResult.mission_pass` / `stress_pass` の意味論が先に壊れます。Phase 1 は `stress_pass: Pending/Unsupported` の tri-state にするか、`evaluate_stage_c` 自体を「stress 未実装時は mission 判定不可」に寄せるべきです。

2. **Stage B の infeasible 個体が downstream で選抜軸に混入し得る契約になっています。**  
   本文では「1 fold でも invariant 違反なら infeasible 確定」としつつ、同時に `b_pooled_cf_result` を常に返し、これを GA Pareto 3 軸 source としています。T065 側が constraint-domination を明示実装しない限り、fold infeasible 個体が数値上は強く見えて選抜に残る危険があります。`is_feasible_invariant=False` のとき `b_pooled_cf_result` を選抜不可 sentinel に落とすか、`BCEvaluationResult` 契約で「Pareto 軸として使用可能なのは feasible 個体のみ」と固定してください。

3. **Stage B pooled OOS の「連結 single trade list」案は path-dependent 指標の扱いが未定義です。**  
   `trades / bars / business_day_universe` を単純連結すると、fold 境界で equity series の連続性、DD、exposure、HAC/serial dependence の扱いが曖昧です。特に `bars` が累積 equity を含むなら、fold 間ギャップで擬似 DD や擬似連続性が入ります。本文は「単一 evaluate_fn 呼出」で止まっており、fold 境界の正規化規約がありません。ここは `pool_fold_results()` の入力契約に「fold.test は非重複・時系列順」「bar/equity は boundary-aware に再構成」を明記しないと危険です。

4. **cross-pair pass の母集団定義が曖昧です。**  
   本文は `STAGE_C_CROSS_PAIR_LIST = 6 pairs`、`REQUIRED_COUNT = 5` としつつ、「anchor 含む」「5 通貨」「5/6 通貨」が混在しています。anchor pair を 6 本の中に含めるなら、Stage C main の 12w 判定と shadow validation が二重計上され、shadow の意味が薄れます。ここは「anchor を cross-pair 集計に含めるのか」「required 5 は 6 pair 中 5 なのか、shadow 5 pair 全通過なのか」を今の段階で固定すべきです。

5. **A→B 乖離 corr の計算源が未確定のままです。**  
   `b_pooled_scores` が `gate_worst_gap` か `gate_score` か未確定で、符号の向きも未定義です。これは T071 申し送りではなく T064 の責務境界です。ここが曖昧だと、同じ run でも corr の解釈が逆転し、T063 の divergence 制御に誤入力します。少なくとも「higher is better に正規化した単一スカラー」を T064 側で固定してください。

[Warning]
1. **Stage C-lite forced_pass の ranking 仕様が不足しています。**  
   `cells_worst` 昇順だけでは tie、`n * 0.30` の丸め、`invariant_fail` 個体の扱い、`progress_pass` との優先順位が未定義です。本文のままだと generation ごとに forced_pass 数が不安定になります。

2. **`15セル worst = 各 window の gate_worst_gap の max` は T061 契約依存です。**  
   これは `gate_worst_gap` が「その window 内 5 指標 gap の厳密 max」である場合のみ成立します。T061 の `CanonicalFiveResult` が別定義なら、15 cell worst の実装が synthesis §5.3 からずれます。

3. **`shadow_robustness_score` を float で確定 field にしているのに、意味論は Decision Pending です。**  
   archive CA #6 で消費される前提なら、未確定のまま float を返すより `None | Pending` にした方が安全です。

4. **cross-pair input contract に provenance guard がありません。**  
   caller=T070 が pair 別結果を渡す設計自体は妥当ですが、`genome_id`, `config_hash`, `partition_id`, `bar_span` が一致している保証が本文にありません。誤 pair / 誤設定の結果混入を T064 が検知できません。

5. **C7 的に Stage C-lite 6w は境界なので、bool 断定だけだと強すぎます。**  
   本文でも「30 blocks/bucket は境界」と認識しています。なら `StageCLiteResult` に diagnostic な `sample_size_flag` / `is_inconclusive_boundary` を持たせる方が整合的です。

[Suggestion]
1. `StageCResult` の pass 系は `bool` ではなく `Enum(PASS, FAIL, PENDING)` に寄せると、spread stress 未実装期間を嘘なく表現できます。

2. `select_top_clite_forced_pass_indices()` の ranking key を明文化してください。  
   例: `mission_pass desc -> progress_pass desc -> invariant_ok desc -> cells_worst asc -> individual_id asc`。  
   さらに forced 数は `max(1, ceil(n * 0.30))` か `floor` かを固定してください。

3. `pool_fold_results()` は raw concat helper ではなく、fold 境界 aware な builder にした方が安全です。  
   名前も `build_pooled_oos_input()` の方が責務が明確です。

4. `cross_pair_data` は `dict[str, PairBacktestBundle]` の dataclass 化を推奨します。  
   `pair`, `genome_id`, `config_hash`, `partition_label`, `trades`, `bars`, `business_days` を 1 つに束ねると検証しやすいです。

5. `compute_a_b_correlation()` は今の段階で score source を固定してください。  
   私なら `higher is better` に統一した単一 scalar を T064 から返し、T071 は corr を計算するだけにします。

総評として、**方向性自体は良い**です。特に `forced_pass を世代単位に分離した点`、`cross-pair backtest を T070 に寄せた点`、`Stage B pooled を per-fold 集約で誤魔化さない点` は妥当です。  
ただし Round 1 の falsification-first 観点では、**Stage C placeholder**, **Stage B infeasible の downstream 契約**, **pooled OOS の fold 境界規約**, **cross-pair 母集団定義**, **A→B corr source 固定** の 5 点は概念設計段階で閉じるべきです。ここを曖昧にしたまま詳細設計へ進めるのは危険です。