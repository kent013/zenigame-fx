施策判定: **MODIFY**

[Critical]
- `cross_pair._run_pair_sharpe` の**直接転用は不可**です。ここは `metric_unavailable` を `0.0` 返却する設計で、Stage A の sentinel/penalty 契約と一致しません（`stage_a.threshold=-0.0172` との組合せで誤選抜リスク）。`evaluate_stage_a` と同じ評価系（`fitness_pen`）で multi-pair 集約すべきです。  
  参照: [cross_pair.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/cross_pair.py:144), [cross_pair.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/cross_pair.py:200), [stage_gate.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/stage_gate.py:1112), [config default](/Users/ishitoya/repository/zenigame-fx/config/alpha_factory/default.yaml:117)
- 学習用 multi-pair bars を `holdout_only` 経路で流用してはいけません。`_load_holdout_only` は Stage C 区間専用です。Stage A/B 学習は `_load_lane_bars` 相当で A/B 区間を別途ロードする必要があります。  
  参照: [run_ga.py](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py:819), [run_ga.py](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py:2264)
- 24GB 環境で worker×pair の増加は高リスクです。現実装は `spawn` + `LaneEvalContext` ブロードキャストで worker ごと複製されるため、spike は worker 数を絞る前提が必須です。  
  参照: [parallel_eval.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/parallel_eval.py:589), [parallel_eval.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/parallel_eval.py:130), [ga-worker-memory](/Users/ishitoya/repository/zenigame-fx/devnotes/20260514-2045-ga-worker-memory/conceptual-design.md:18)

[Warning]
- Stage A/B/C を同時に multi-pair 化すると、効果帰属が崩れます。**spike は Stage A のみ**に限定し、B/C は現状維持で差分評価してください。  
  参照: [parallel_eval.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/parallel_eval.py:287)
- 集約は `mean` より `min` が妥当です。ただし tie の多発を避けるため、診断用に `mean` も併記して監視してください（選抜キー本体は min）。
- `default OFF = bit-exact` は必須。OFF 時に既存 selection/order が不変である回帰テストを明示化してください。

[Suggestion]
- spike 完了条件を先に固定: `pair_failure=0` 比率、`cross_pair_mean_sharpe`、wall-time/peak RSS の3軸。
- out-of-run 固定期間の再現チェックを必須ゲート化（メタ過学習ガード）。

推奨（集約方式と段階）
- 集約方式: **min-across-pairs 推奨**（学習時に「全ペアで機能」を最短で強制）。
- 段階: **Stage A multi-pair only（spike）→必要なら Stage B へ拡張**。Stage C は既存 cross-pair 評価を維持。

最小 spike 構成（推奨）
- pair: `EUR_JPY + USD_JPY`（2ペア）
- scope: `Stage A fitness` のみ multi-pair
- metric: 各ペア `evaluate_stage_a` 相当の `fitness_pen`
- aggregate: `min(fitness_pen_pair)`
- run: `population=48, generations=20, max_workers=2`（他は R89 と同一）

【収束】
- 反証可能仮説: 「Stage A の2ペア min 学習で、`pair_failure=0` 比率が現状（7/2142）から有意に上昇し、`cross_pair_mean_sharpe` 上限が 0.15 に到達する」  
- 最小変更: 「`multi_pair_training.enable=true` + `pairs=[EUR_JPY,USD_JPY]` + `scope=stage_a_only` + `aggregate=min`（他設定据え置き）」