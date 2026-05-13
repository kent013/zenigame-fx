# Run 71/63 系統 warmstart 検討 (= candidate motif として 10% pool)

## 背景

archive 横断分析 (handoff § 監査 3-4) で:
- Run 71: F5+P1+M2+F8+P7+P12 cluster、 64 個体
- Run 63: P2+F14 cluster

= 2 RUN だけが Stage C 20k+ を達成。 同一系統だが「再現性は INCONCLUSIVE」 (= 別 seed で再現するか不明)。 これらを candidate motif として GA 初期 pool に注入し再現性検証。

## 目的

Run 71/63 系統の genome を warmstart 種として GA 初期 population の 10% pool に注入:
- 初期 population の 10% を「Run 71/63 由来 genome の mutation/crossover」 で生成
- 残り 90% は通常 random initialization
- 別 seed で再現するか / 別 instrument で再現するか の実験

## 期待効果

- Run 71/63 系統の再現性検証 (= 実験的)
- 真の robust 戦略空間の存在検証
- novel cluster 発見の足場

## スコープ

- 新規 `src/alpha_factory/warmstart.py` (= candidate motif 抽出 + injection)
- GA initialization で 10% warmstart pool 注入
- archive から genome_json を抽出
- 行動変更 (= 1 RUN smoke 必須)
- experimental TODO (= 必ずしも採用しない、 仮説検証用)

## 非目的

- Run 71/63 系統を hard-code (= 動的に archive から抽出)
- warmstart 種の最適化 (= NSGA-II 等の elite 機構とは別 layer)

## 参考

- handoff § 12 段 TODO 順 10
- handoff § 監査 3-4 (= Run 71/63 cluster artifact 詳細)
