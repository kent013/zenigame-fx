**施策判定**
`CHANGES_REQUESTED`（重大2件）

**[Critical]**
1. 本線経路で cross-pair が有効化されません。  
事実: `run_ga` は `LaneEvalContext.cp_inputs=None` を固定しており（[run_ga.py:2011](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py:2011)）、実行は `GenomeEvaluator` 経路が常時使われます（[run_ga.py:2068](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py:2068), [swim_lane.py:577](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/swim_lane.py:577)）。`evaluate_genome` は `cp_inputs is not None` の時だけ cross-pair を呼びます（[parallel_eval.py:344](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/parallel_eval.py:344)）。  
修正案: anchor指定時は `GraduationLane.pair_bars` だけでなく `LaneEvalContext.cp_inputs` にも同じ `pair_bars/meta` を配線してください。

2. 1 anchor 指定では設計どおりに実走しません。  
事実: 現実装は target ごとに「固定2アンカー必須」です（[cross_pair.py:63](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/cross_pair.py:63), [cross_pair.py:285](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/cross_pair.py:285)）。`EUR_JPY` は `EUR_USD` と `USD_JPY` が必要で、`USD_JPY` のみだと `missing_bars` で skipped になります（[cross_pair.py:287](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/cross_pair.py:287)）。  
修正案: `--cross-pair-anchors` は「2本必須」にするか、`ANCHOR_PAIRS[target]` を自動採用する仕様にしてください（1本運用は別タスクで評価関数契約変更が必要）。

**[Warning]**
1. `cross_pair_runtime_mode` の算出が実実行と乖離し得ます。  
現状は `graduation_lane.pair_bars` だけで `enabled` 判定（[run_ga.py:1939](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py:1939)）なので、`cp_inputs` 未配線でも `enabled` 表示になります。  
修正案: `lane_ctx.cp_inputs` ベースで判定。

2. anchor取得に `_load_lane_bars` を流用すると Stage A/B まで毎回ロードして過剰です（[run_ga.py:657](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py:657)）。  
修正案: anchor用に holdout-only loader を分離。

**[Suggestion]**
- 観点2の解釈（shadowでも graduation 側で `cross_pair.passed` を使う）は正しいです。Stage C `passed` 非介入（[stage_gate.py:1879](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/stage_gate.py:1879), [stage_gate.py:2288](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/stage_gate.py:2288)）と両立しています。  
- T102（NSGA-II/CPPS/loop_closure）とは主責務が別で、競合は `run_ga.py` の同時編集範囲だけです（[TODO.md:14](/Users/ishitoya/repository/zenigame-fx/docs/alpha_factory/TODO.md:14)）。

**全体判定**
方向性は妥当ですが、現状の詳細設計のままでは R87 で「cross-pair 実走」を達成できない可能性が高いです。

**【収束】**
- 反証可能仮説: この設計のまま実装すると、R87で `cross_pair_runtime_mode=enabled` でも `ii_lite_pass` は `None` 優勢のままになる。  
- 最小変更: anchor指定時に `LaneEvalContext.cp_inputs` へ `target + 固定2anchor` を配線し、`--cross-pair-anchors` は2本必須に制約する。