# out-of-cluster audit 詳細設計

## 実装方針

### `scripts/alpha_factory/out_of_cluster_audit.py` (新規)

入力:
- `--archive-dir` (= `.cache/alpha_factory/runs/`)
- `--n-runs` (= 直近 N RUN を対象、 default 5)
- `--target-pnl-min` (= 20000 等、 audit 対象個体の閾値)

出力:
- `reports/audit/out-of-cluster-run-{latest_N}.md`
- 内容: 直近 N RUN の Stage C 達成個体 list + cluster 判定

### Clustering 判定

ルールベース:
1. **Run cluster**: 達成個体の Run 番号分布 (= 全部同 RUN なら cluster artifact)
2. **Primitive cluster**: F-* / M-* / P-* 含有 set の Jaccard 類似度
3. **Parent genealogy**: parent_a / parent_b の継承関係 (= 同 cluster なら artifact)
4. **PR3 shadow 一致性**: `canonical_gate_pass_b/c_shadow` と legacy `stage_b_pass`/`stage_c_pass` の不一致率

判定結果:
- `cluster_artifact`: 単一 RUN cluster、 primitive set 高 Jaccard、 同 genealogy
- `novel_cluster`: 複数 RUN / 異なる primitive set / 異なる genealogy
- `inconclusive`: n<10 (= C7 Sample size)

### Output format

```markdown
# Out-of-cluster audit Run N (直近 5 RUN)

## Stage C 達成個体 list (PnL >= 20k)
| individual | run_id | primitives | parent | shadow_consistency | verdict |

## Cluster 判定
- Run cluster: ...
- Primitive Jaccard: ...
- Genealogy 深さ: ...

## Verdict
- {cluster_artifact / novel_cluster / inconclusive}
```

## 受入基準

- [ ] `scripts/alpha_factory/out_of_cluster_audit.py` 新規実装
- [ ] unit test (`tests/scripts/test_out_of_cluster_audit.py`) 5 件以上 (= 各 cluster 判定パターン)
- [ ] `reports/audit/` ディレクトリ生成
- [ ] 既存 archive Parquet (58 列) を読めること
- [ ] CLI 引数の validation
- [ ] ruff / mypy clean

## ロールバック条件

- GA / archive 動作変更検出
- 既存 archive Parquet 読込失敗

## コミット計画

- 1 コミット: `feat(scripts): out-of-cluster audit script (= cluster artifact 自動検出、 PR3 shadow 活用)`
