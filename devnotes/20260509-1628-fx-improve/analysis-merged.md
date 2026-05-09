# マージ分析: Run 56 (run_20260509_023253)

## 合意事項（両者一致）

### F1. Stage C 通過 0 / graduation 0
- Stage A pass=1219 → B pass=458 → C pass=**0**
- best g46_i51: stage_c_pass=False, Sharpe=-3.45, total_pnl=-4100, trade_count=17
- live_criteria 4 項目中 1 項目のみ pass (max_dd<20%)、 残り 3 項目 (sharpe / total_pnl / trade_count) 未達

### F2. archive 観測の重大欠落
- **DSR (Deflated Sharpe Ratio)**: 全 5856 件 NaN — 多重比較補正が無効化されている
- **ii_lite_pass**: 全件 NaN — cross-pair shadow が `skipped_single_instrument` で稼働せず
- **source_stage**: 全件 NaN — archive_role 記録欠落
- これらは「観測の質そのもの」の問題であり、 戦略改善の前提が揺らぐ

### F3. GA 多様性の崩壊（elite collapse）
- Stage B pass 458 個体のうち unique fitness_pen=96 (21%)
- 上位 5 fp で 220 個体 (48%) を占有
- 最頻 fp=0.2029 が 84 個体 (g32_i9 系列)
- → 実質 ~96 unique 戦略、 多様性が失われている

### F4. trade_count_min=50 が現状の戦略集団で構造的に未達
- Stage B pass の trade_count_stage_a 中央値=39 (live_criteria の 50 を下回る)
- 60 日で 50 trades = 0.83 trades/day がイントラデイ短期戦略の必要回転率

## Claude 独自の発見

### C1. Stage C 期間が 21 日と短い（Codex により reframe された）
- 当初 Claude H1: 「21 日 holdout で sharpe>=1.0 判定が小サンプル過小、 multi-block holdout 提案」
- → Codex の反証: Sharpe -3.45 はノイズ域を超過している。 期間問題ではなく**実測が大幅赤字**である事実を直視すべき
- → 残る価値: 21 日が config の 60 日と乖離している点は別問題（C2 で詳述）

### C2. Stage A 表現力の飽和
- Stage A pass の active_clause: mean=1.96 (max=2 で飽和)、 全体 mean=1.63
- max_clause=2 を使い切る個体ばかりが Stage A 通過 → 表現力の上限に達している

### C3. Stage B fail 理由 dominance
- median_oos_sharpe<min;positive_fold_ratio<min: 499/761 (66%)
- median_oos_sharpe<min;positive_fold_ratio<min;all_folds_unavailable: 225/761 (30%)
- → Stage B 落ちの 96% が「sharpe + fold_ratio」の同時 trigger

## Codex 独自の発見

### X1. Stage C ホールドアウト データ範囲欠損 (CRITICAL)
- `stage_gate_config.stage_c_holdout_days = 60` 設定
- しかし dataset.bars_holdout = 20457 (約 21.3 日) のみ
- holdout_bar_first=2026-04-01 / holdout_bar_last=2026-04-21 → **39 日分が欠落**
- → 評価ループそのものが構造的に壊れている（mission 必須要件の trade_count>=50 を確保不能）

### X2. Stage C 実測が深い赤字 (Sharpe -3.45) はノイズ域超過
- Lo, A. W. (2002), "The Statistics of Sharpe Ratios", Financial Analysts Journal — 小標本でも Sharpe -3.45 は単なる noise では説明困難
- → 期間延長より先に「データセット完全性 + 評価環境の修復」を優先

### X3. Bailey, Borwein, López de Prado, Zhu (2014) の DSR / PBO 引用
- "The Probability of Backtest Overfitting" (J. Computational Finance)
- 5856 個体を試験して best を選ぶ多重検定リスクは正に PBO の典型例
- → DSR 計算が NaN は致命的観測欠陥

## 矛盾・要議論

### M1. Stage C 期間の扱い
- Claude: 「21 日が短すぎ、 multi-block にすべき」
- Codex: 「21 日でも -3.45 は明らかに失敗。 期間延長より先にデータ範囲修復・統計補正復活」
- → **Codex 採用**: データ範囲そのものの欠損（X1）が先決問題。 multi-block 化は X1 修復後に再検討

### M2. trade_count_min の扱い
- Claude H4: 「50 trades / 60 日が構造的に厳しい、 max_clause=3 拡張で検証」
- Codex: trade_count<50 は live_criteria 違反だが、 まずは Stage A→C の評価環境修復が先。 max_clause 拡張は次々サイクル
- → **Codex 採用**: 評価環境を直してから max_clause を弄る (思考原則「仕組みが機能していない段階で値を弄るな」)

## 統合改善提案（優先度順）

| # | 提案 | 優先度 | 出所 | target_metric | failure_mode | 期待効果 | 分類 |
|---|------|--------|------|--------------|-------------|---------|------|
| 1 | Stage C ホールドアウトデータ範囲修復 (60日確保) | **Critical** | Codex X1 | trade_count, total_pnl, sharpe | bars_holdout=20457 (21日) で config 60日と乖離 | 評価ループの整合性回復 → Stage C 通過個体が観測可能になる | Structural |
| 2 | DSR (Deflated Sharpe Ratio) 算出パイプライン復活 | **Critical** | Codex X3 / Claude H5 | 多重比較補正による Stage B/C false positive 抑制 | dsr 全件 NaN | 5856 個体試験での overfitting リスク低減、 後続サイクルの判断材料蓄積 | Structural |
| 3 | GA 多様性監視 (unique fp / fingerprint dedup 観測先行) | Warning | Claude H3 / Codex H4 | Stage B/C 通過個体の集団多様性 | unique fp=21%, 上位 5 が 48%占有 | elite collapse の定量化、 後続サイクルでの selection 改善判断材料 | Structural (観測先行) |

## 棄却された提案 / 保留

| # | 提案 | 出所 | 棄却/保留 理由 |
|---|------|------|---------------|
| - | Stage C を multi-block holdout に再設計 | Claude H1 | Codex X1 (データ範囲欠損) が先決問題。 X1 修復後に再検討 |
| - | regime indicator の archive 書き込み | Claude H4 | 観測先行型の正当な提案だが、 X1/X3 修復が優先。 次々サイクルで採用 |
| - | max_clause=3 拡張 A/B 検証 | Claude H5 | 「仕組みが機能していない段階で値を弄るな」原則。 評価環境修復後に検討 |
| - | regime_penalty_weight 等のパラメータ調整 | (Reactive Parametric 例) | メタ過学習ガード抵触、 Reactive 分類のため |

## 全体判定: CRITICAL_DRIFT (Codex 判定継承)

Stage C ホールドアウトデータ欠損 (config 60日 vs 実 21日) と DSR 観測停止が同時発生。 現状 GA サイクルは mission 達成に向けた正当な評価環境を確保できていない。
**最優先**: 評価環境（データ完全性 + 多重比較補正）の構造的修復。 戦略レベルの改善 (multi-block / max_clause / regime indicator 等) はこの修復後に再評価する。
