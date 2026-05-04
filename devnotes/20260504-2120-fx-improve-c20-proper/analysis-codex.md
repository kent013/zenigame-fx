前提 (verified / inconclusive)
- Verified: Stage B 判定は `median_oos_sharpe` と `positive_fold_ratio`（全 fold 母数）で行われ、`trade_sharpe_stage_b` は判定 SSOT ではない。根拠: [stage_gate.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/stage_gate.py:1163), [stage_gate.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/stage_gate.py:1171), [archive.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/archive.py:527)
- Verified: `positive_fold_ratio_effective` は unavailable fold を除外した観測値で、判定に使う `positive_fold_ratio`（全 fold）とは別。根拠: [stage_gate.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/stage_gate.py:1164), [stage_gate.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/stage_gate.py:1166)
- Verified: cycle 13 相当 run (`run_20260504_111153`) は `analytical_AND=29` に対し `stage_b_pass=2` を再現。29個の失敗 reason は 28個が `median_oos_sharpe<min;positive_fold_ratio<min`、1個が `positive_fold_ratio<min`（実測）。
- Verified: stage_b_pass=2 個体 (`g8_i33`, `g12_i17`) は archive 上 `trade_count=16/17`, `stage_c_pass=False`, `trade_sharpe_stage_c=None` で live_criteria 未達。
- Inconclusive: cycle 6-19 の14 RUN全体をローカル生成物だけで再集計するための seed/run 対応メタが一部欠損（batch run の report 不在）。ただしユーザー提示集計と cycle13 実測は整合。
- Verified(ドリフト): `genome-archive-schema.md` の一部記述は現実装(T044)とズレあり（上書き説明が旧仕様）。根拠: [genome-archive-schema.md](/Users/ishitoya/repository/zenigame-fx/docs/alpha_factory/concepts/genome-archive-schema.md:35), [archive.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/archive.py:534)

Facts / Interpretations
- Fact (Q1): `trade_sharpe_stage_b` は Stage B IS 全期間 Sharpe の観測列で、判定に使う `median_oos_sharpe` とは別定義。
- Interpretation (Q1): (a) 設計意図の可能性が高い。少なくとも実装・テストはその前提で一貫している。根拠: [test_archive.py](/Users/ishitoya/repository/zenigame-fx/tests/alpha_factory/test_archive.py:343)

- Fact (Q2): `n_fold_effective=9` は「imputed 異常」ではなく、unavailable=0 を意味する。
- Fact (Q2): `trade_count=16/17` は Stage C 側値（B pass 後に C 評価で更新）であり、Stage B fold 判定の母数を直接示さない。根拠: [archive.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/archive.py:597)
- Interpretation (Q2): 主因は (c) Other。  
  - `trade_sharpe_stage_b` と `median_oos_sharpe` の取り違え  
  - `positive_fold_ratio_effective` と `positive_fold_ratio` の取り違え  
  の二重ミスマッチが F1/F2 の核心。

- Fact (Q3): 低 trade 個体が B を抜ける芽はある（少なくとも C で即 reject）。  
- Interpretation (Q3): 禁止事項 #6 の本質リスクは「見栄え改善」そのものより、「誤った代理指標で意思決定すること」。まず SSOT 同期が先。

反証可能性 (C9)
- 仮説 H0: 「F2差分はバグではなく、比較指標の不一致で説明可能」  
- 反証テスト:
1. `trade_sharpe_stage_b>=0.05 && positive_fold_ratio_effective>=0.60` 集合を抽出  
2. その集合の `stage_b_reason_codes` を集計  
3. `median_oos_sharpe<min` / `positive_fold_ratio<min` が主因なら H0 支持、そうでなければ H0 棄却  
- 現時点結果(cycle13): H0 支持（29中29が reason で説明可能、pass は2のみ）

次サイクル候補 (Critical 1 / Warning 2)
- Critical 1: 案A（Stage B 判定 SSOT監査）  
  - 具体: report/analyze で `median_oos_sharpe` と `positive_fold_ratio` を直接可視化し、`trade_sharpe_stage_b` との混同を禁止。
- Warning 1: `inspect_stage_b_folds.py` は fold Sharpe 再計算で `trade_count_min_for_sharpe` を使っており、Stage B本体の `fold_trade_count_min` と不一致。診断結果の解釈に注意。根拠: [inspect_stage_b_folds.py](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/inspect_stage_b_folds.py:123), [stage_gate.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/stage_gate.py:1046)
- Warning 2: archive schema ドキュメントの旧記述を放置すると、今後も同型誤読が再発。

全体判定
- CONCERN

Q4（1つに絞る）: 案A  
- 理由: 現在の主要リスクは性能不足より「判定SSOTと分析列の乖離認知」。ここを閉じずに案Bへ進むと、禁止事項 #2/#4/#6 に接触しやすい。

Q5（Falsification-first next experiment）
1. 次 cycle で `stage_b_pass` 全個体について `median_oos_sharpe`, `positive_fold_ratio`, `positive_fold_ratio_effective`, `trade_sharpe_stage_b` を同時出力  
2. 「B pass だが C trade_count_min 未達」の件数を毎 run 監査  
3. 件数が増えるなら初めて B/C 接続設計（案B）を検討、増えないなら現状維持で signal 強化に戻る