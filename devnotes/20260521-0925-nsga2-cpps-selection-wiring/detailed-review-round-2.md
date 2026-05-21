**Fact**
- `evaluate_mission_inf_gap(result: CanonicalFiveResult) -> MissionGapResult` の正抜粋により、P3 の前回 Critical は解消。`b_pooled_cf_result` から呼ぶ限り Stage B 完結です。
- P5a は `IndividualEvaluation` を偽装せず、`select_from_pareto_features(...)` 専用入口に切り替わっており、前回 Critical は解消。
- P5b は warmstart / CPPS 枠の優先順と dedup が追加され、前回 Critical の主要部分は解消。
- ただし、修正後設計内にまだ off-by-one / contract 未固定 / schema 伝搬の不整合が残っています。

**P3: ParetoFeaturesLite sidecar**
判定: `REQUEST_CHANGES`

- [Warning] `source_stage="B"` 追加後も、本文に「5 field」「5 列追加」と「新 6 列」が混在しています。禁止事項 8 の観点で schema 伝搬表が未更新です。  
  修正案: `ParetoFeaturesLite.source_stage: Literal["B"] | None` を正式 field に入れ、schema / defaults / `to_rows()` / reader backfill / tests / docs の接続表をすべて「6 列」に更新してください。

- [Warning] 「入力型レベルで Stage B 保証」は言い過ぎです。`CanonicalFiveResult` 自体は Stage C 由来でも同型になり得ます。  
  修正案: `build_pareto_features_from_stage_b_result(b_result: StageBResult)` のような builder に閉じ、呼び出し側が `CanonicalFiveResult` を直接渡せない形にしてください。

- [Warning] P3 は LOG_ONLY なのに、`evaluate_mission_inf_gap` が NaN slack で `ValueError` を投げるため、既存 RUN に対して新しい abort 経路を作る可能性があります。  
  修正案: `b_pooled_cf_result` の slack finite が Stage B 側で既に invariant ならテストで固定。未保証なら P3 側で `pareto_axis_usable=False` に落とすか、LOG_ONLY でも fail-fast する方針を明文化してください。

**P5a: NSGA-II only selection**
判定: `REQUEST_CHANGES`

- [Critical] `GenerationSelectionResult.survivor_indices` と `parent_pairs` を `_breed_next_gen` でどう使うかが未固定です。既存 elite copy と `parent_pairs` 全量 offspring を両方使うと、population size 超過または survivor の二重優遇が起きます。  
  修正案: どちらかに固定してください。推奨は「`survivor_indices` は parent pool ordering / diagnostics 用、次世代生成は `parent_pairs` から `pop_size` 体」で、elite copy を別にしない方式です。elite を残すなら `parent_pairs` は `pop_size - elite_count` 件に縮める必要があります。

- [Warning] `pareto_axis_usable=True` が `is_feasible_invariant=True` を含むか曖昧です。`b_pooled_cf_result is None` が infeasible を完全に表すならよいですが、設計上は別 field として存在しています。  
  修正案: eligible 条件を `pareto_axis_usable and is_feasible_invariant` と明記し、infeasible だが scalar finite な個体が survivor に入らないテストを追加してください。

- [Warning] `pooled_dd_per_fold_max` の符号規約が未明文化です。max drawdown が正の損失額なのか、負値なのかで「小さい方が良い」が反転します。  
  修正案: `pooled_dd_per_fold_max >= 0` を invariant 化し、`f2 = pooled_dd_per_fold_max` の向きテストに負値ケースを入れてください。

- [Warning] `features_by_idx` に存在しない個体をどう扱うか未定義です。  
  修正案: caller は全 population idx を渡す契約にするか、`all_indices` を別引数にして missing を excluded として記録してください。

**P5b: CPPS only injection**
判定: `REQUEST_CHANGES`

- [Critical] warmstart 枠計算に負数 off-by-one があります。`warmstart枠 = floor(pop_size * warmstart_ratio) - anchor` は、例として `pop_size=8, warmstart_ratio=0.1, anchor=1` で `-1` になります。  
  修正案: `warmstart_total = max(1, floor(pop_size * warmstart_ratio)) if warmstart_active else 0`、`anchor_slots = min(1, warmstart_total)`、`warmstart_mutation_slots = warmstart_total - anchor_slots` に分解してください。

- [Warning] `anchor + warmstart + cpps <= pop_size` 超過時に CPPS を切り詰める方針は妥当ですが、実効 ratio が設定値から乖離します。  
  修正案: warning だけでなく `effective_cpps_slots` / `requested_cpps_slots` / `dedup_dropped_slots` を run log と summary に出してください。

- [Warning] `ArchiveCandidate` DTO で Stage C/holdout field を排除する方針は良いですが、Python では closure や外部参照で迂回できます。  
  修正案: `admit_generation_to_archive(candidates: Sequence[ArchiveCandidate])` の API 境界で Stage B DTO だけを受け、eviction sort key も DTO field のみ参照する単体テストを入れてください。

**全体判定**
`REQUEST_CHANGES`

主要な Round 1 Critical はほぼ解消しています。残る最大リスクは P5a の `_breed_next_gen` 統合 contract と、P5b の warmstart slot off-by-one です。ここを閉じれば、設計としては `APPROVE` にかなり近いです。