**観察事実**
- Run-20→Run-21で `stage_a_threshold` は **0.0→0.0778** に上昇（H2要因は実在）。
- ただし Stage A pass は 2750→2395（-12.9%）なのに、Stage B pass は 834→0（-100%）。
- Run-21 は Stage A通過2395件すべてで primary reason が `median_oos_sharpe<min`、かつ `n_fold_effective` が全件0。
- `selection_score_schema` は Run-20=`v2_feasibility`、Run-21=`v3_stage_c_feasibility`（T045）。

**解釈（C9: 反証先行）**
- H3（randomness）: **反証**。Run-20のB通過率30.3%が維持ならRun-21でB=0は統計的にほぼ起こりえない。
- H2（gate厳格化）: **単独真因は反証**。A通過減は軽微で、B全滅を説明できない。
- H1（T045選抜とWF指標の乖離）: **最有力**。v3で「単期間PnL/Sharpe正」に寄る一方、Stage BのWF `median_oos_sharpe` を直接最適化していないため、fold単位で崩れる個体群に収束した可能性が高い。

**推奨施策（1件）**
- T045を**撤回せず修正**し、`selection_score` の先頭側に Stage B整合を入れる。  
  具体: `stage_c_feasible` より前に `stage_b_pass` と `wf_shortfall`（`median_oos_sharpe`・`positive_fold_ratio`の不足量）を置く。  
  目的: 「PnL/Sharpe正」改善を維持しつつ、B=0退行を構造的に防ぐ。

**全体判定**
- **判定: H1優勢（H2は副次、H3は棄却）。T045は全撤回でなく“B整合付きv3.1”へ後退修正が妥当。**