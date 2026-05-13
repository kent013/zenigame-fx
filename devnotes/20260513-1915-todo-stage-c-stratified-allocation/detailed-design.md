# Stage C stratified allocation 詳細設計

## 実装方針

### stratifier 仕様 (rule-based、 PR3 shadow 活用)

入力: Stage B pass 個体集合 (= archive から抽出 or in-memory)
出力: Stage C 評価候補 list (= top-N、 stratified)

層分類:
1. **persistence decile**: `persistence_score_shadow` を 10 分位
2. **primitive cluster**: F-* / M-* / P-* 含有 set の Jaccard 類似度で cluster 化
3. **canonical shadow consistency**: `canonical_gate_pass_b_shadow=True/False/None`

各層から抽出:
- top decile (= persistence 上位 10%): 各 cluster から 1-2 個体
- mid decile (= persistence 中位): random sampling
- canonical_gate_pass_b_shadow=True 優先

合計 N 個体 (= 既存 Stage C 評価枠と整合)。

### config

```python
class Phase7Config:
    stage_c_allocation_mode: Literal["legacy", "stratified"] = "legacy"
    n_top_decile: int = 10
    n_mid_decile: int = 5
    primitive_cluster_jaccard_threshold: float = 0.7
```

### swim_lane / evaluate_stage_c の修正

stage_b pass list の Stage C 評価選定で stratifier 経由する分岐。

## 受入基準

- [ ] Phase7Config + 4 段接続
- [ ] stratifier helper 実装 + unit test
- [ ] integration test (= legacy mode regression 0)
- [ ] 1 RUN smoke 計画

## smoke 合格条件

- Stage C 評価集団の primitive 多様性 (= Jaccard 平均) が baseline 比 25% 以上向上
- novel cluster の Stage C 通過率が baseline 以上

## コミット計画

- 1 コミット: `feat(swim_lane): Stage C stratified allocation (= PR3 shadow 活用、 default OFF)`
