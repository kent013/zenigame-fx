# Stage C stratified allocation (= Stage B decile + primitive 多様性)

## 背景

現状 Stage C 評価集団は Stage B pass 順 (= fitness_pen 上位) で集約され、 lucky 個体 + 同 cluster artifact が混入しがち。 archive 実測で Run 71/63 系統 (= 64 個体) が単一 cluster artifact、 「群」 として扱うべきでない問題が顕在化 (handoff § 監査 3-4)。

## 目的

Stage C 評価集団の **stratified allocation** 導入:
- Stage B pass decile (= persistence_score_shadow / positive_fold_ratio_effective 分布) × primitive set 多様性 で 層別
- 各層から fixed 比率で抽出 → 同 cluster artifact 集中緩和
- novel cluster の Stage C 評価機会を確保

= PR3 で追加した shadow 列 (= canonical_gate_pass_b_shadow / mission_inf_gap_b_shadow / persistence_score_shadow) を活用した stratifier。

## 期待効果

- Stage C 評価集団の cluster 多様性向上
- novel cluster の発見率向上
- lucky 集中による Stage C 通過バイアス緩和

## スコープ

- Stage C 評価対象選定ロジック (= `evaluate_stage_c` 直前 or swim_lane) に stratifier 導入
- archive 経由で Stage B 評価済個体集合から strata 構築
- 行動変更 (= 1 RUN smoke 必須)

## 非目的

- Stage A/B の evaluation 集団変更 (= Stage C 限定)
- 完全 ML stratifier (= まず rule-based)

## 参考

- handoff § 12 段 TODO 順 9
