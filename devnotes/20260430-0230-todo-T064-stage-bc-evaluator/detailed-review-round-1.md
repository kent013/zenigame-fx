[VERDICT] **CHANGES_REQUESTED（Round 1 は未承認）**  
重大な設計不整合があり、このまま実装に入ると T064 の数式準拠性と runtime 安定性を満たせません。

[Critical]
- **Stage B の fold 境界仕様が自己矛盾**（対象: [stage_bc_evaluator.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/stage_bc_evaluator.py) `build_pooled_oos_input` / `StageBResult`）  
  事実: `StageBFoldResult` に `test` が無いのに、`fold_results[i].test.*` を invariant 検証に使う記述。さらに `pooled_dd_per_fold_max` を追加すると書かれているが dataclass 定義に存在しない。  
  影響: 実装不能 or 実装者裁量で逸脱。  
  修正: fold 境界は `individual_input.folds` 由来で検証し、`StageBResult`/`PoolFoldedInput` に `pooled_dd_per_fold_max` を明示追加。

- **synthesis §5.2 の DD 集約準拠が崩れる**（対象: `evaluate_stage_b`）  
  事実: `is_b_pass = b_pooled_cf.gate_pass` のままだと、concat DD（擬似 DD 含む）で判定される。設計文は「pooled_DD = per-fold max」を要求。  
  影響: 数式準拠違反、選抜軸が不安定。  
  修正: Stage B 判定で使う DD は `pooled_dd_per_fold_max` を優先する明示ロジックに固定。

- **cross-pair provenance guard が不十分**（対象: `evaluate_stage_c` / `PairBacktestBundle`）  
  事実: `bundle.pair` しか検証していない。`genome_id/config_hash/partition_label` 未検証。  
  影響: 別設定・別期間の shadow 混入を検知できない（因果ループ破断リスク）。  
  修正: 3 フィールド一致を必須化し、不一致は `StageBCInputError`。

- **`assert` 依存の契約固定は本番で無効化され得る**（対象: `evaluate_stage_c`）  
  事実: `assert cross_pair_pass in (...)` は `python -O` で除去。  
  影響: 二値契約の防波堤にならない。  
  修正: 明示 `if ...: raise StageBCInputError` に置換。

- **相関計算が定数系列で例外化する**（対象: `compute_a_b_correlation`）  
  事実: `statistics.correlation` は分散 0 で `StatisticsError`。  
  影響: observability 経路でランタイム停止。  
  修正: 例外ハンドリングし、`(0.0, n)` など contract 固定。

[Warning]
- **§5.3/§5.4 厳密準拠と言いつつ閾値が Decision Pending**（`derive_stage_c_lite_thresholds`, `derive_stage_c_thresholds`）。現時点は **INCONCLUSIVE**。
- **Stage C truth table テストに優先順位衝突ケースが不足**（`cross_pair=FAIL` かつ `stress=FAIL` 時に reason が `CROSS_PAIR` になることを明示すべき）。
- **`select_top_clite_forced_pass_indices` の ranking key に `invariant_ok` があるが、型定義に独立フィールドが無い**（実装時ぶれやすい）。
- **sample_size 判定は全 window・全 bucket の global min**。かなり保守的で、意図説明を 1 行追加しないと誤実装されやすい。
- **`apply_spread_stress` の unsupported 経路は明確だが、`spread_stress_supported=True` で NotImplemented が出る挙動の上位ハンドリング方針が未記述**。
- **Phase 2「11 箇所」記述と列挙数が一致していない**（運用時の取りこぼしリスク）。

[Suggestion]
- truth table を文章でなく **機械可読表（入力3軸→出力2軸）** にして、pytest を parameterized で 1:1 対応させる。  
- provenance guard は `PairBacktestBundle` に `validate_against(anchor_bundle)` メソッドを持たせると再利用しやすい。  
- `live_criteria: dict` は型を絞る（TypedDict/dataclass）と閾値導出の齟齬を抑制できる。  
- C2 DoD の grep 対象に `src/alpha_factory/__init__.py` を明示追加すると再エクスポート漏れ検知が強くなる。

以上です。今回の Round 1 は、**Critical 解消後に再レビュー**が妥当です。