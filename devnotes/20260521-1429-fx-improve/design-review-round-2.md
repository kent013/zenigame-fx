**施策判定**
`APPROVED`

前回の `[Critical]` 2件は解消されています。特に、本番経路が [parallel_eval.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/parallel_eval.py:344) の `ctx.cp_inputs is not None` で発火するため、[run_ga.py](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py:2004) の `LaneEvalContext.cp_inputs` に入れる方針で正しいです。固定2anchorも [cross_pair.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/cross_pair.py:284) の `required=(target,a1,a2)` 契約と一致しています。

**残 Warning**
1. `cross_pair_runtime_mode` は `cp_inputs is None` の全ケースを `skipped_single_instrument` に畳まない方がよいです。  
修正案: `enable=False -> skipped_disabled`、`enable=True かつ target not in ANCHOR_PAIRS -> skipped_target_not_configured`、`cp_inputs != None -> enabled`。少なくとも summary/log で「明示 enable したが未設定でskip」を識別可能にしてください。

2. `_load_holdout_only` は non-empty だけでなく holdout span/coverage を fail-closed してください。  
修正案: target と同じ `[dataset.end, dataset.end + holdout_days)` で、先頭・末尾・単調性・重複なしを検証。短い anchor holdout で `ii_lite_pass` が bool 化すると、観測値だけ正しく見えて解釈が壊れます。

**全体判定**
R87 の目的には十分です。`--cross-pair-enable`、`EUR_JPY -> EUR_USD + USD_JPY`、`cp_inputs` 配線、`runtime_mode=enabled`、`ii_lite_pass` bool化、graduation 発生確認、という検証計画で進めて問題ありません。

【収束】APPROVED