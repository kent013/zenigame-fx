# RUN 57 分析（Codex 独立分析）
使用スキル: zenigame-analyze-run（Alpha Factory RUN結果の深層分析）

## 観察事実 (Facts)
- Stage A pass 1084 (Run 56: 1219)、Stage B pass 105 (Run 56: 458)、Stage B最初の通過世代はgen30。
- Stage B fail内訳: median_oos_sharpe<min かつ positive_fold_ratio<min が941件、positive_fold_ratio<min単独37件、all_folds_unavailable併発1件。
- Stage B pass集合のtrade_count_stage_a中央値64、trade_count_stage_b中央値181、trade_count_stage_b≥50充足率100%。
- Stage B passのunique fp比率10%、上位5 fpで占有率89%。
- Stage A passのfp中央値0.040、Stage B passのfp中央値0.111、最高fp 0.1957。
- g55_i41はlive_criteriaでsharpe 0.215、total_pnl -24580、max_dd 2.95%、trade_count 30。
- archive内のdsr列が全てNaN、`compute_audit_dsr_for_genome`実装済ながら`run_ga.py`から未呼び出し。

## 解釈・推論 (Interpretations)
- H1 [Low / Confirmed]: 施策C1目的（holdout 60日確保とtrade_count構造改善）はStage B passのtrade_count統計とguardログで反証材料なし。
- H2 [High / Confirmed]: Stage B pass数の77%減とgen30初通過は評価窓がRun 56より厳格化した仮説と整合し、他要因（クラッシュ等）の根拠不明。
- H3 [Critical / Confirmed]: DSR配線未稼働はarchiveのNaN実測と`audit.py`実装状況で反証不可、リスク監視指標欠落が続く。
- H4 [Warning / Confirmed]: Stage B passのunique fp 10%かつ上位5 fp比率89%は多様性崩壊を示し、mutator設定や移民率変更記録が無いため別要因によるとの反証なし。
- H5 [High / Confirmed]: Stage B failの96%がSharpe閾値とpositive_fold_ratio閾値同時違反で、他カテゴリが37件と少数なため「Sharpe計測が支配的阻害要因」仮説の反証なし。
- H6 [Medium / Inconclusive]: Stage A pass fp中央値0.040への縮退が選択圧歪みを生みStage B探索を阻害している可能性は示唆されるが、基準値の改定履歴が未確認で結論保留。George E. P. Box (1976)『Science and Statistics』の指摘どおり、計測系の有用性検証が必要。

## 次サイクル候補
- [Critical] DSR配線復帰: (a) Stage B〜C評価でリスク指標を記録しmission達成判定の計器を再稼働; (b) DSR系列があればSharpe低下と損失の切り分けが可能; (c) 禁止事項抵触リスク: なし; (d) 実装複雑性: `run_ga.py`から既存`compute_audit_dsr_for_genome`呼出とarchive書き込みを追加する配線作業。
- [Warning] Stage B regimeセグメント分析: (a) Stage B失敗の時間帯・通貨ペア偏り仮説を検証; (b) 失敗集中窓を特定すれば次施策で対象プリミティブやフィルタを決められる; (c) 禁止事項抵触リスク: なし; (d) 実装複雑性: 既存genome archive集計スクリプトでカレンダーとfold指標をクロス集計。
- [Warning] コスト分解レビュー: (a) g55_i41の負P&L要因をspread・swap寄与で分解; (b) コストモデル誤差や手数料推定過小を検出すればSharpe改善余地を定量化; (c) 禁止事項抵触リスク: なし; (d) 実装複雑性: backtestログとarchive統計の照合、既存データ取り出しで完結。
- [Warning] Stage Aフィットネススケール監査: (a) fp中央値0.040への縮退が選択圧を歪めていないか検証; (b) スケール不整合を是正すればGAの探索幅が戻る可能性; (c) 禁止事項抵触リスク: なし; (d) 実装複雑性: 旧Runとのログ比較と計算式トレース。

## 全体判定: CONCERN

## Claude 自己分析との差分
- Stage Aフィットネス縮退を探索圧の潜在ボトルネックとして追加し、H6として扱った。
- best個体がSharpe基準を満たしつつtotal_pnlで敗退している点を強調し、コスト分解レビューを次サイクル候補に含めた。
- DSR配線復帰をCritical施策として承認しつつ、Sharpe低下の時間窓特定タスクを補完提案として列挙。