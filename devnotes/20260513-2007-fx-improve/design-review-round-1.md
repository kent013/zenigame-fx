**前提検証 (C4)**
- [Verified] Stage B の実行 SSOT は [`evaluate_stage_b`](\/Users\/ishitoya\/repository\/zenigame-fx\/src\/alpha_factory\/stage_gate.py:1214) で、`run_ga` 本線は [`swim_lane` 経由](\/Users\/ishitoya\/repository\/zenigame-fx\/src\/alpha_factory\/swim_lane.py:635) です。
- [Verified] `stage_b_pass` は世代サマリにも使われます（[`run_ga.py:1836`](\/Users\/ishitoya\/repository\/zenigame-fx\/scripts\/alpha_factory\/run_ga.py:1836)）。
- [Verified] archive schema は固定管理で、テストが列数・列集合を厳密検証しています（[`test_archive.py:183`](\/Users\/ishitoya\/repository\/zenigame-fx\/tests\/alpha_factory\/test_archive.py:183)）。
- 補足: セッションの利用可能 skill 一覧に `zenigame-fx-codex-review` が出ていないため、AGENTS.md の C1-C9 規律で同等レビューしました。

**施策判定**
1. C1: Stage B gate `profit_safe_pfr` opt-in  
`REQUEST_CHANGES`

**指摘**
- [Critical] `post-filter` を archive 集計後に置くと、`stage_b_pass=False` へ反転後も `stage_c_pass=True` が残る不整合が発生し得ます。`selection_score` でも `stage_c_pass` は別軸評価されるため、ゲート意味論が崩れます。  
修正案: `trade_sharpe_stage_b > 0` 条件は `evaluate_stage_b` 内、または少なくとも Stage C 実行前（`swim_lane` で `collect_stage_b` 前）に統合してください。後段マスクは避ける。  
参照: [`swim_lane.py:651-680`](\/Users\/ishitoya\/repository\/zenigame-fx\/src\/alpha_factory\/swim_lane.py:651), [`run_ga.py:1810-1838`](\/Users\/ishitoya\/repository\/zenigame-fx\/scripts\/alpha_factory\/run_ga.py:1810)

- [Critical] 設計上の config 4段伝搬が不足しています。現状 loader は新 field を読まないため、`default.yaml` 追記だけでは効きません。  
修正案: `_build_stage_gate` に `stage_b_gate_kind` / `profit_safe_pfr_threshold` / `profit_safe_pfr_min_n_fold` を追加し、同時に `compute_base_config_hash` にも反映してください。  
参照: [`config.py:508`](\/Users\/ishitoya\/repository\/zenigame-fx\/src\/alpha_factory\/config.py:508), [`calibrate_state.py:56`](\/Users\/ishitoya\/repository\/zenigame-fx\/src\/alpha_factory\/calibrate_state.py:56)

- [Critical] `trade_sharpe_stage_b > 0` 条件の実装案が `None` を通してしまいます（`is not None` のときのみ fail）。仕様と不一致です。  
修正案: `None` / 非有限 / `<=0` をすべて fail-closed にしてください。

- [Warning] `median_oos_total_pnl` は NaN 防御が必要です。`bt.total_pnl` は型上 `None` になりませんが、非有限値混入は理論上あり得ます。  
修正案: fold 単位で `math.isfinite` をかけ、非有限は unavailable 扱い + reason 追加。

- [Warning] `GENOME_ENTRY_SCHEMA_VERSION=v2` 据え置きは方針上は妥当ですが、既存テストは列数/列集合を固定で検証しているためそのままでは落ちます。  
修正案: schema/version据え置き前提のまま、[`test_archive.py`](\/Users\/ishitoya\/repository\/zenigame-fx\/tests\/alpha_factory\/test_archive.py:183) などを更新。

- [Warning] 新 reason code（`positive_fold_ratio_effective<min`, `median_oos_total_pnl<min`, `n_fold_effective_below_profit_safe_min`, `trade_sharpe_stage_b<=0_post_filter`）を `run_report` の known codes に追加しないと `other` へ吸われます。  
修正案: [`generate_run_report.py`](\/Users\/ishitoya\/repository\/zenigame-fx\/scripts\/alpha_factory\/generate_run_report.py:534) の known code 更新 + テスト追加。

- [Suggestion] `StageGateConfig.__post_init__` に新 field の範囲検証（threshold finite, 0..1, min_n_fold>=1）を追加すると事故防止になります。  
参照: [`stage_gate.py:653`](\/Users\/ishitoya\/repository\/zenigame-fx\/src\/alpha_factory\/stage_gate.py:653)

**Q1 回答**
1. 現状設計は `APPROVE` ではなく `REQUEST_CHANGES`。  
2. `fold_total_pnl` の 0 補完は「no-trade」には合理的ですが、`fold_exception` まで 0 補完すると甘くなるので unavailable として別扱い推奨。  
3. schema v2 据え置きは可能（加算列が nullable のため）が、テスト・周辺解析コード更新は必須。  
4. post-filter は archive 後ではなく Stage B 判定内（または Stage C 前）へ統合が妥当。

**Q2 回答**
1. `bt.total_pnl is None` は現行型では基本発生しません（`Decimal` 必須）。  
2. `median_oos_total_pnl` NaN は非有限値が fold 配列に入ると発生し得るため、finite guard を入れるべき。  
3. `n_fold=0/1` は legacy reason（`no_folds`/`insufficient_folds`）を維持しつつ、profit_safe 条件は fail-closed で整合化するのが安全。

**Q3 回答**
1. default `legacy` なら既存 Stage B fixture の大半は維持可能。  
2. ただし archive 列追加を入れるなら既存 `test_archive.py` は不変では済みません（列数・列集合 assertion があるため）。

**Q4 回答**
1. Critical/Warning は上記の通り。  
2. `stage_b_reason_codes` の `;` 連結自体は既存パーサと整合します。  
3. ロング/ショート相殺問題は今回未解決で妥当（別 TODO）が、monitor 指標は同時に追加推奨。

**Q5 回答**
1. `oos_total_pnls` payload 追加のメモリ増は軽微です（fold数×8byte×個体数程度）。24GB/2workers 制約では実質問題ありません。

**全体判定**
`CHANGES_REQUESTED`