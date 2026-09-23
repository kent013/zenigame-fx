# 概念設計: cross-pair in-loop selection pressure (T115, cycle 6)

## 背景
cycle 5 で T114 cross-pair enable 成功 → 汎化を定量化: R87 Stage C 599 個体すべて ii_lite_pass=False、cross-pair 汎化 0/599、aggregate margin median -1.37（深い in-sample 過学習）。
根本原因 (Codex CRITICAL_DRIFT): GA fitness_pen = EUR_JPY in-sample sharpe のみで、cross-pair は最終評価でしか効かず GA 選択に汎化シグナルが入らない → 純 in-sample winner に収束。

## 目的
GA 選択に **真の cross-pair 汎化シグナル** (`CrossPairResult.metrics["aggregate_fitness"]` = mean_sharpe − λ·std) を弱く注入し、in-sample 過学習からの脱却を促す。新規 eval なし（既計算シグナルを伝搬）。default OFF で挙動完全不変。

## スコープ
- 新規 archive 列 `cross_pair_aggregate_fitness` (cross-pair 実測シグナル保存、enable=False で None)。
- `CrossPairConfig.selection_pressure: bool = False` (default OFF=bit-exact、enable=True 前提) + threshold。CLI `--cross-pair-selection-pressure`。
- IndividualCacheEntry.cross_pair_margin + cache populate + `_selection_key` keyword-only 拡張 (ON 時のみ tie-break 挿入)。
- effective flag 単一 helper + summary schema 分岐。

## 非目的
- top-N 疎注入 / 世代間キャッシュ (将来コスト最適化、本サイクルは全件=R87 同等コスト)。
- multi-pair training / overfit proxy (別施策)。
- 閾値引き上げ (汎化達成後)。
- cross_pair mode=hard (graduation 強制、別サイクル)。

## 期待効果
R88 (ON) で ii_lite_pass 率 / cross_pair_aggregate_fitness が R87(OFF) 比改善、汎化個体 (ii_lite_pass=True) > 0 の出現。

## 使命・禁止事項整合
cross-pair 汎化シグナルの選択反映 = 汎化要求の探索反映 (緩和でなく加点、評価閾値不変)。default OFF で挙動不変。メタ過学習ガード: aggregate_fitness は Structural シグナル (Reactive Parametric でない)。

## 詳細設計
`detailed-design.md` 参照 (Codex design-review APPROVED Round 2)。
