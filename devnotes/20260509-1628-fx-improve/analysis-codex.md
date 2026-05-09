# RUN 56 分析（Codex 独立分析）

## 観察事実 (Facts) ※C6 分離遵守、 数値のみ
- Stage C ホールドアウトは 20457 本（約 21.3 日）で終了し、設定値 60 日との乖離 38.7 日を確認。
- 最良個体 g46_i51 の Stage C 指標は Sharpe -3.45、total_pnl -4100、trade_count 17。
- Stage B 通過 458 件に対し Stage C 通過 0 件、graduation 0 件、ii_lite/DSR/source_stage は全 5856 件で NaN。
- Stage B 失敗 761 件の主因は median_oos_sharpe<min & positive_fold_ratio<min が 499 件、all_folds_unavailable を伴うケース 225 件。
- Stage B 通過群の trade_count_stage_a 平均 49.96（中央値 39）、trade_count_stage_b 平均 55.69、trade_count_full_dataset 平均 105.65。
- Stage B 通過群の unique fitness_pen は 96/458（21%）で、fp=0.2029 系列が 84 個体を占有し、上位 5 fp で 220 個体（48%）を占有。

## 解釈・推論 (Interpretations、 仮説と反証可能性)
- H1 [Rejected]: 「Stage C が 21 日と短いせいで統計判定できない」/ 反証条件: Stage C が閾値から大幅に乖離していれば期間延長の有無に関わらず mission 未達 → Sharpe -3.45、total_pnl -4100 の実測で反証成立（Lo, 2002, “The Statistics of Sharpe Ratios” も小標本で Sharpe が不安定でも、ここまでの負値はノイズ域を超過）。
- H2 [Critical]: 「Stage C のデータ欠損（60 日設定に対し実データ 21 日）が評価ループを破壊している」/ 反証条件: データ取得ログが 60 日を満たし trade_count>=50 を確保できていること → summary でホールドアウト最終時刻 2026-04-21T07:25:00+00:00 を確認、残 39 日が欠落しており反証不可。
- H3 [Warning]: 「DSR パイプライン停止が多重比較補正を無効化し、Stage C 失敗率を底上げしている」/ 反証条件: dsr フィールドが算出済みで統計的有意性検査が適用されていること → 全件 NaN のため未反証。Bailey, Borwein, López de Prado, Zhu (2014) “The Probability of Backtest Overfitting” が警告する多重検定リスクに抵触。
- H4 [Warning]: 「GA の選択圧が特定 fp 系列（g32_i9 由来）へ収束し探索多様性を喪失している」/ 反証条件: 世代別に fp が広く分散し上位占有率が低いこと → 上位 5 fp が 48% を占有し反証できず。
- H5 [Inconclusive]: 「trade_count_min=50 が Stage A 60 日条件下で構造的に不適合」/ 反証条件: Stage A で 50 以上の個体が十分に存在すること → 平均 49.96 で閾値近辺、分布をさらに確かめないと結論不能（追加データ要）。

## 次サイクル候補
- [Critical] Stage C ホールドアウト欠損の起因解析: (a) 60 日分バーを確保し mission 必須要件の trade_count>=50 を満たす (b) 評価ループの整合性回復、負値指標の原因切り分け (c) 禁止事項該当なし (d) データ取得ジョブとステージ分割ロジックの追跡が主体で中程度。
- [Warning] DSR 算出パイプラインの再稼働: (a) 多重比較補正を復元し Stage B→C 移行の信頼度を担保 (b) 偽陽性戦略の排除率向上 (c) 禁止事項該当なし (d) 既存コンポーネントの診断・修正で中程度。
- [Warning] GA 多様性監視と調整（mutation/crossover 設定の軽微検証 + 世代別 fp モニタリング強化）: (a) 単一系列への収束を緩和し Stage B→C 成果率を回復 (b) exploration 向上と過剰適合リスク低下 (c) 禁止事項 5（過度な複雑化）を避け、最小限のパラメータ微調整とモニタに留める (d) 低〜中、既存ログ解析と設定差分評価で対応可能。
- [Warning] Stage C 取引頻度の根拠調査（エントリ条件の intraday 適合性をログで検証）: (a) イントラデイ方針に沿った実際のエントリタイミングを把握 (b) trade_count>=50 を自然に満たす設計可否の判断材料獲得 (c) 禁止事項 6 を避け、閾値を弄らず発生要因の分析に限定 (d) 低、既存 fill ログ/トレードログ解析中心。

## 全体判定: CRITICAL_DRIFT
Stage C データ欠損という構造的バグと DSR 停止による検定抜けが同時発生しており、現状の GA サイクルは mission 達成に向けた正当な評価環境を確保できていない。Stage C 指標も大幅な負値で drift が顕在化。

## Claude 自己分析との差分
- Stage C 失敗を「期間が短い」ではなく、先に実測が大幅赤字である点を強調し、延長提案を反証済みと判断。
- Phase 直近で最優先とすべきはホールドアウト欠損の修復であり、regime shift 仮説や multi-block 化はその後に再検証するべきと結論。
- GA 多様性崩壊をランダム性不足ではなく特定 fitness_pen 系列への偏りとして定量化し、探索パラメータ監視を提案。