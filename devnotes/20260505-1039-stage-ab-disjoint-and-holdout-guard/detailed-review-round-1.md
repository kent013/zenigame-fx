**本分析の前提 (C4)**
- 前提1: レビュー対象は提示された詳細設計テキストのみ。検証状態: Verified  
- 前提2: 実コード・docs・git履歴の実体照合は未実施（ユーザー指定によりコマンド未実行）。検証状態: Unverified  
- 前提3: 判定は「設計としての整合性・実装時リスク」に限定。検証状態: Verified  

**主要指摘（先に重大順）**

1. [Critical] Stage C fallback と partition guard が設計上矛盾しています。  
Facts: [run_ga.py](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py:426) の fallback は `bars_holdout` を `bars_stage_b` 末尾から切り出し、[stage_partition_guard.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/stage_partition_guard.py) は A/B/H の timestamp disjoint を必須化しています。  
Interpretation: fallback 有効時に guard が恒常的に fail-closed になり、実行不能化リスクがあります（ルックアヘッド/汚染防止意図は正しいが、現仕様と両立しない）。  
修正案: `allow_stage_c_fallback_slice=true` をこのTODOで廃止・エラー化するか、guard呼び出し前に「fallback使用時はStage CをINCONCLUSIVE扱いで別フロー」に分岐してください。

2. [Critical] `stage_b_statistical_inconclusive` の伝搬定義が不完全です。  
Facts: 施策5で flag 追加を提案していますが、archive 4点セット（`GENOMES_SCHEMA` / row template / collect / flush）への明示接続が不足しています。  
Interpretation: 転記漏れ再発パターン（あなたが警戒している8番）に該当します。  
修正案: row列として扱うなら必ず4点セットを明記し、summary専用なら「archive非保持」を明文化して責務を分離してください。

3. [Warning] `dataset["bars"]` の意味変更は後方互換リスクがあります。  
Facts: 施策5で `bars` を `stage_a + stage_b` に変更。  
Interpretation: 既存consumerが `bars_stage_b` 意味で解釈していると回帰します。  
修正案: `bars` は据え置き、`bars_dataset_total` を新設する方が安全です。

4. [Warning] parquet metadata 注入方式は将来拡張に弱いです。  
Facts: 施策6は `with_metadata({...})` の全置換案。  
Interpretation: 既存metadataが将来入った場合に上書き消失します。  
修正案: `existing = GENOMES_SCHEMA.metadata or {}` をmergeしてから設定してください。

5. [Warning] `n_fold_effective < 3` 判定の NaN/None ケースが未定義です。  
Facts: 施策5で bool flag をこの条件で定義。  
Interpretation: 欠損時に例外または誤判定の余地があります。  
修正案: `isinstance(n_fold_effective, int)` を前提化し、欠損は `True`（保守的INCONCLUSIVE）に寄せてください。

6. [Suggestion] C1チェックリストの証跡保存先は `tmp/` だと消失しやすいです。  
修正案: `devnotes/.../c1-checklist.md` に置いて監査可能性を上げてください。

---

**施策ごとの判定**
1. `_load_lane_bars` disjoint化: **REQUEST_CHANGES**  
2. `stage_partition_guard.py` 新規: **REQUEST_CHANGES**  
3. 起動時 partition guard 呼び出し: **REQUEST_CHANGES**  
4. `bars_18m -> bars_stage_b` rename: **APPROVE**  
5. summaryフラグ追加: **REQUEST_CHANGES**  
6. archive metadata追加: **REQUEST_CHANGES**  
7. `STAGE_GATE_VERSION` bump: **APPROVE**  
8. run report注記: **APPROVE**  
9. structured logキー整備: **APPROVE**

**全体判定**
- **CHANGES_REQUESTED**

**補足（観点対応）**
- ルックアヘッドバイアス: disjoint化自体は改善だが、fallback併存時は汚染再導入。  
- メモリ/性能: 現設計は24GB/6worker制約内で妥当。  
- テスト網羅: 方向性は良いが、fallback矛盾ケースの失敗テストを追加必須。  
- C3/C7（相関claim）: 今回は相関主張が主題でないため該当薄。