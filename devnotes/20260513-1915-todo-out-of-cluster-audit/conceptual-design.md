# scripts: out-of-cluster audit (PR3 shadow 列活用、 novel cluster artifact 検出)

## 背景

30 ラウンド議論の 4 回監査で発覚:
- Stage C 20k+ 出現 = 1-2 RUN cluster (= Run 71 / Run 63 のみ)
- F8/F5/M2/P1/P7/P12 含有 = Run 71 cluster artifact、 同一系統の 64 個体
- 「群」 として扱うべきでない単一戦略の派生集合

= 毎 RUN 後に archive 横断で「novel cluster かどうか」 を自動判定する script が必要 (= cluster artifact 再発防止)。

## 目的

archive 横断 audit script (= `scripts/alpha_factory/out_of_cluster_audit.py` 新規):
- 直近 N RUN の Stage C pass 個体 (= 20k+ や Z-1 達成) を集計
- primitive 集合 / parent genealogy / Stage A/B/C 数値の clustering 判定
- novel cluster vs cluster artifact を機械的に区別
- PR3 で追加した `canonical_gate_pass_b/c_shadow` / `mission_inf_gap_b/c_shadow` 列を活用

## 期待効果

- 毎 RUN 後の自動 audit で cluster artifact 即検出
- Run 71/63 のような再発を未然防止
- 撤退条件 (= 「20k+ が単一 cluster で out-of-cluster 再現なし」) の機械判定

## スコープ

- 新規 `scripts/alpha_factory/out_of_cluster_audit.py`
- 既存 archive Parquet (58 列) を input
- 出力: `reports/audit/out-of-cluster-run-{N}.md`
- 行動不変 (= analysis script、 GA 動作 touch なし)

## 非目的

- archive 列追加 (= 既存 58 列で十分)
- fitness / gate への audit 結果反映 (= 別 PR)
- clustering ML model 化 (= まず ruleベース、 必要なら ML 化)

## 参考

- `devnotes/20260513-1402-handoff-pr1-pr2-postdebate/handoff.md` § 監査 3-4
- PR3 設計: `devnotes/20260513-1419-todo-pr3-canonical-mission-shadow/`
