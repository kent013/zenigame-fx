**Findings（重大順）**
1. [Critical] anchor 評価時の `pair` 文脈が target のままです。  
[parallel_eval.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/parallel_eval.py) の `_aggregate_multi_pair_stage_a` は `primitive_evaluator` を使い回しており、`RegistryEvaluator` の `pair` は生成時固定です（[evaluator.py:204](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/primitives/evaluator.py:204)）。  
`M4 EconomicEventGate` は `ctx.pair` を参照するため（[modulator_generic.py:307](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/primitives/modulator_generic.py:307)）、anchor=USD_JPY でも EUR_JPY 文脈でイベント通貨選択され、multi-pair fitness が歪む可能性があります。  
修正案: `RegistryEvaluator.with_pair(pair)` を追加し、anchor ごとに pair を差し替えた evaluator を作ってから `evaluate_stage_a` を呼ぶ。

2. [Warning] calibrate-gate の cross-run contamination guard に multi-pair 設定が反映されていません。  
`compute_base_config_hash` は `multi_pair_training` を含んでいないため（[calibrate_state.py:56](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/calibrate_state.py:56)）、single-pair 時代の threshold が multi-pair 有効 run に再利用され得ます。  
修正案: `enable/pairs/aggregate/scope` を `base_config_hash` payload に追加（必要なら `stage_gate_version` も更新）。

3. [Warning] Stage A 専用機能なのに anchor 読み込みが `_load_lane_bars` 依存で holdout 必須になり、失敗面とI/Oコストが過大です。  
[scripts/alpha_factory/run_ga.py](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py) の `_build_multi_pair_train_inputs` は Stage A 用 `bars_a` しか使わないのに A/B/C 全ロードします。  
修正案: anchor 向けに Stage A-only loader を用意し、holdout 不要契約を明示する。

**ファイルごと判定**
- [parallel_eval.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/parallel_eval.py): **要修正（Critical あり）**
- [run_ga.py](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py): **条件付き可（Warning あり）**
- [config.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/config.py): **概ね妥当（Suggestion: `pairs` 重複禁止・target 含有チェックを追加すると安全）**

**全体判定**
- 現時点は **APPROVED ではありません**（Critical 1件）。

【収束】  
反証可能仮説: `M4` を含む genome で、anchor 評価の `pair` を target 固定にした場合と anchor に差し替えた場合で `fitness_pen` が一致しない。  
最小変更: `RegistryEvaluator.with_pair()` を追加し、`_aggregate_multi_pair_stage_a` の anchor 評価直前で `pair=anchor` evaluator を使う。