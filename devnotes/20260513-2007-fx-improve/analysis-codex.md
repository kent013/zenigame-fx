# Run 74 独立分析 (Codex)

## 観察事実（Facts）
- Stage通過率: A `1723/5856 (29.4%)`、B `96/5856 (1.64%, A通過内5.57%)`、C `0/5856 (0%)`
- gen 0-9 は Stage A 通過 `0`、gen 33 で初 Stage B 通過、Stage C は評価されるが全 fail
- selection best `g60_i45`: `fitness_pen=0.1063`、`A/B/C=True/True/False`、`trade_count=41`、`total_pnl=-15,390`、`trade_sharpe_stage_b=0.0311`
- archive fitness_pen 最大 `g41_i78`: `fitness_pen=0.2555`、`A/B/C=True/False/False`、`total_pnl=+28,160`、`median_oos_sharpe=0.0`、`positive_fold_ratio=0.0`
- Stage B通過群 (n=96): `total_pnl max=-6,940 (全件マイナス)`、`trade_sharpe_stage_b mean=-0.033/median=-0.040`、`active_clause mean=1.01`、`unique fitness_pen=6/96 (6.2%)`
- Stage B fail理由: `median_oos_sharpe<min;positive_fold_ratio<min` が `95.6% (1556/1627)`
- live_criteria(best): `1/4 pass`（sharpe/pnl/trade_count fail）
- DSR proxy: 全個体 pass `0`、上位でも `0.0266`、threshold `0.7144`
- cross-pair shadow: `skipped_single_instrument`
- 18 run累積: mission達成 `0/18`、Stage C pass `0/18`、DSR pass `0/18`

## 解釈・推論（Interpretations）
前提（verified）:
- 入力は archive/reports 要約値のみで、個別約定ログ（保有時間、long/short内訳、コスト内訳）は未提示
- よって FX固有制約の一部は「検証不能」を明示する

1. Stage gate のボトルネック仮説  
仮説: `Stage B条件が探索を過度に絞り、収益性と乖離した通過を生む`  
falseなら観測されるはず: `Stage B通過群に正のtotal_pnlが一定数混在` し、`Stage C候補が漸増`  
観測: Stage B通過96件が全件マイナスpnl、Stage Cは0  
判定: **反証できず（仮説支持）**。Bが実質ボトルネック

2. 禁止事項違反の兆候（イントラデイ/取引回数削減/live緩和/ショート偏重）  
仮説: `禁止事項逸脱は発生していない`  
falseなら観測されるはず:  
- イントラデイ逸脱: 保有時間が日跨ぎ中心  
- 取引回数削減依存: trade_countが下限付近に貼り付き  
- live緩和: threshold改変の痕跡  
- ショート偏重: side別寄与の偏り  
観測: trade_countは `41-58` で下限50近傍に集中（bestは41でfail）。一方、保有時間・売買方向内訳・閾値変更履歴は未提示  
判定: **部分的懸念 + INCONCLUSIVE**。取引回数最適化への寄りは疑わしいが、イントラデイ逸脱/ショート偏重は未証明

3. primitive偏在と多様性崩壊  
仮説: `探索多様性は維持されている`  
falseなら観測されるはず: `active_clauseが1へ収束`、`fitness_pen重複率が高い`  
観測: `active_clause mean=1.01`、`unique fitness_pen=6.2%`  
判定: **反証できず（崩壊を支持）**。I2/I3は妥当

4. selection_score_schema v3_3 の探索歪み  
仮説: `v3_3は純利益方向と整合`  
falseなら観測されるはず: `高selection個体が赤字、黒字個体がBで落ちる`  
観測: bestはB通過だが赤字、archive最大fitness_penは黒字だがB fail  
判定: **反証できず（歪みを支持）**。I4は妥当。特に「feasible優先」が収益性より上位にある兆候

5. FX固有制約（スワップ/スプレッド純利益反映）  
仮説: `fitnessが純利益整合で、コストを適切反映`  
falseなら観測されるはず: `fitness良好でも純損失が常態化`  
観測: Stage B通過群が全件マイナスpnl  
判定: **設計上の不整合は強い**。ただし「コスト未反映」そのものはログ不足で断定不能。現時点で言えるのは「通過条件が純利益を保証していない」

## 次サイクル候補
- [Critical] Stage B feasible条件を sign判定から純利益整合へ拡張する（例: `median_oos_total_pnl >= 0` と `trade_sharpe_stage_b > 0` を必須化、selectionでも同順位以上で評価）
- [Warning] `active_clause` の collapse対策は「2個強制」より、`clause使用率ペナルティ/下限制約` を段階導入して副作用検証（強制固定は探索空間を不自然に歪める）
- [Warning] 多様性ガードを追加（`unique fitness_pen比率` や `genotype距離` の下限監視、niching/sharingを小さく導入）
- [Warning] FX制約の監査指標を必須出力化（`overnight_hold_ratio`、`long/short別PnL`、`spread_cost`、`swap_cost`、`net_pnl_after_cost`）。これがない限り逸脱検知はINCONCLUSIVEが続く

## 全体判定
CRITICAL_DRIFT