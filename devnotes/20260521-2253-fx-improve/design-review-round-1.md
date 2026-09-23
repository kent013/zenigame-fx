施策判定: **REQUEST_CHANGES**

[Critical]
1. **提案シグナルが「cross-pair」ではなく別物です。**  
`mission_signed_margin_b_shadow/c_shadow` は cross-pair 結果ではなく、canonical shadow（Stage B IS / Stage C base）の列です。  
参照: [archive.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/archive.py:156), [stage_gate.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/stage_gate.py:2321), [cross_pair.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/cross_pair.py:369)  
修正案: `CrossPairResult.metrics` の連続値（例: `aggregate_fitness` または `min_sharpe`）を archive 列へ保存し、その値を row→cache→selection に伝搬してください（新規 eval 不要）。

2. **`c_shadow or b_shadow` fallback は壊れます。**  
`0.0` を偽扱いして誤 fallback、`NaN` は真扱いで fallback 不発になります。  
参照: [run_ga.py](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py:1046), [run_ga.py](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py:1202)  
修正案: `or` を使わず、`_coerce_optional_float` 後に `is not None` で明示 fallback してください。

3. **`_selection_key` の thread 漏れリスクが高いです。**  
実呼び出しは `_tournament` を含めて複数経路です。ここを漏らすと「eliteだけ圧が乗る」不整合が出ます。  
参照: [run_ga.py](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py:864), [run_ga.py](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py:989), [run_ga.py](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py:1236)  
修正案: `_tournament` まで `selection_pressure` / `threshold` を引数伝搬し、可能なら `_selection_key` を keyword-only + 明示引数化して漏れを防いでください。

[Warning]
1. **観測系が実際の選抜キーと乖離します。**  
summary/report は v3.3 の 10-tuple 前提のままです。  
参照: [run_ga.py](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py:1582), [generate_run_report.py](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/generate_run_report.py:945)  
修正案: pressure ON 時の `selection_key_schema`（例 `v3_4_cross_pair_pressure`）と effective flag/threshold を summary に残してください。

2. **`selection_pressure=True & enable=False` は warning だけだと運用事故になりやすいです。**  
修正案: 起動時に `effective_selection_pressure=false reason=...` を必ず log/summary に記録してください。さらに `nsga2_selection_enabled=True` 時は pressure が実質 no-op になるため同様に明示警告を推奨します。

[Suggestion]
1. tie-break の位置（fold_robust と fitness_pen の間）は妥当です。初回は bool 化（`margin>threshold`）の弱圧で良いです。  
2. テストは「OFF bit-exact」「ON順序」「_tournament経路」「NaN/0 fallback」「schema表示」を最低限追加してください。

全体判定:  
**根本原因（cross-pair シグナル不在）に対して、現設計のままでは因果的に直撃していません。** まずシグナル源を cross-pair 実測値に置き換える修正が必要です。

【収束】  
反証可能仮説: **`mission_signed_margin_*_shadow` を使う現案では、R88 ON でも `ii_lite_pass` 率は R87 と有意差なく、汎化 0/599 近傍に留まる。**  
最小変更: **`CrossPairResult.metrics["aggregate_fitness"]` を archive に保存し、その `>0` を現行 tie-break 位置に挿入（他設計は据え置き）。**