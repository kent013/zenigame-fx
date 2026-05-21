**Fact**
- Round 2 の主要修正で、P3 の Stage B builder 化、P5a の `IndividualEvaluation` 非偽装、P5b の slot off-by-one は概ね解消しています。
- ただし全文側には、対応欄と食い違う記述がまだ残っています。
- 特に P5a と P5b を同時有効にした場合の `_breed_next_gen` contract が未確定です。

**P3: ParetoFeaturesLite sidecar**
判定: `REQUEST_CHANGES`

- [Warning] 6 field 化したはずですが、変更箇所と schema 伝搬表がまだ「5 field」「5 列追加」「5 列 materialize」のままです。  
  修正案: `source_stage` を含めて `IndividualDiagnostics` / schema / `to_rows()` / reader backfill / 接続表 / tests をすべて「6 列」に統一してください。`pa.string()` 追加、旧版 backfill は `None`、valid row invariant は `pareto_axis_usable=True => source_stage=="B"` が妥当です。

- [Suggestion] `finite 検査` の対象を明文化してください。少なくとも `net_pnl_after_cost`、`pooled_dd_per_fold_max`、`slack_sharpe/pnl/dd/tc` は builder で確認対象にするのが安全です。

**P5a: NSGA-II only selection**
判定: `REQUEST_CHANGES`

- [Critical] `eligible == 1` の規約が `parent_pairs=[(i,i)]` だと、P5a の「parent_pairs 長さ pop_size から pop_size 体生成」contract と矛盾します。  
  修正案: `eligible == 1` では `parent_pairs=((i, i),) * pop_size` にするか、`offspring_count` を引数化して必要数だけ self-mating pair を返してください。`test_nsga2_eligible_below_2_self_mating` は parent_pairs 長と生成個体数まで見るべきです。

- [Critical] P5b と同時有効時の contract が未定義です。P5a は `parent_pairs` から `pop_size` 体生成、P5b は warmstart/CPPS 注入後に breed 枠だけ生成なので、both 条件で個体数超過します。  
  修正案: slot allocation を先に行い、`breed_slots` を `select_from_pareto_features(..., offspring_count=breed_slots)` に渡す設計にしてください。P5a-only では `breed_slots=pop_size`、P5a+P5b では `breed_slots=pop_size-injected_slots`。

- [Warning] 「elite なし方式だが NSGA-II の front-1 が elitism を内包」は不正確です。survivor copy しないなら front-1 は保存ではなく親選択圧です。  
  修正案: 文言を「front-1 を parent pool として優先する」に変えるか、真に elitism が必要なら survivor copy + offspring 数調整へ戻してください。

**P5b: CPPS only injection**
判定: `REQUEST_CHANGES`

- [Critical] P5a との同時有効時の slot / parent_pairs 連携が未定義です。ablation ④ both を実行計画に含めるなら、ここは必須 contract です。  
  修正案: `anchor -> warmstart_mut -> cpps -> breed` で `breed_slots` を確定し、breed の生成器を `nsga2_selection_enabled ? NSGA-II : tournament` に分岐してください。

- [Warning] `warmstart_active` の定義が必要です。T101 は `warmstart_ratio=0.0` で完全行動不変なので、archive が存在するだけで `warmstart_total=1` になってはいけません。  
  修正案: `warmstart_active = warmstart_ratio > 0 and warmstart_motif_archive is usable and motif_count > 0` と明記し、`ratio=0.0` の bit-exact テストを追加してください。

**全体判定**
`REQUEST_CHANGES`

残る論点は実装前に閉じるべきです。P3 は軽微な schema 文面不整合ですが、P5a/P5b の both 経路は population size と選抜圧に直撃します。`offspring_count / breed_slots` contract を導入すれば、次ラウンドで APPROVE 可能です。