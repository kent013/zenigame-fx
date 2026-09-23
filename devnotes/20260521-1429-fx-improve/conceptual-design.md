# 概念設計: cross-pair multi-pair shadow 有効化 (T114, cycle 5)

## 背景
4 サイクルで mission は 達成可能(R83)+cost-robust(R85/P2)+再現可能(R86/T101 warmstart) に到達。だが R86 の 622 mission 個体は in-sample 特化 (cross-pair margin med -1.0)。残フロンティアは**汎化**。
graduation=0 の真因確定: run が単一銘柄 (EUR_JPY) で cross-pair が構造的にスキップ (run_ga.py:1934 GraduationLane(pair_bars={}) 空 + 本番 parallel 経路 LaneEvalContext.cp_inputs=None ハードコード)。cross-pair 機構 (ANCHOR_PAIRS / CrossPairConfig / graduation_criteria) は揃うが複数ペアデータ未供給。

## 目的
anchor ペア (ANCHOR_PAIRS[target]、EUR_JPY→EUR_USD+USD_JPY) の holdout bars を本番 parallel 経路の LaneEvalContext.cp_inputs に供給し、cross-pair を **shadow で実走**させる。これにより ii_lite_pass が None→bool 化し、mission 個体が多ペアで通用するか (汎化) を定量化する。graduation は cross_pair.passed で自然に機能 (Stage C passed 非介入=shadow の意味は保持)。

## スコープ
- config `CrossPairConfig.enable: bool = False` (default OFF=挙動完全不変) + CLI `--cross-pair-enable`。
- enable 時、ANCHOR_PAIRS[target] の holdout を holdout-only loader でロードし CrossPairLaneInputs を構築 → LaneEvalContext.cp_inputs (本線) + GraduationLane.pair_bars (逐次経路)。
- cross_pair_runtime_mode 細分化。default OFF で現状 (skipped) 完全不変。

## 非目的
- cross_pair mode=hard 化 (graduation 強制): 汎化の壁を見てから次サイクル。
- 複数ペア同時学習 / Phase 2 統合 (T102 CPPS/loop_closure): 別レーン。
- 閾値引き上げ: 汎化確認後。

## 期待効果
- cross_pair_runtime_mode=enabled、ii_lite_pass True/False 分布で汎化の壁を定量化。
- cross-pair pass 個体があれば graduation>0 が自然発生。

## 使命・禁止事項整合
cross-pair shadow 有効化は汎化の観測 (評価/閾値不変、graduation 強制せず)。default OFF で挙動不変。閾値緩和・期間延長なし。

## 詳細設計
`detailed-design.md` 参照 (Codex design-review APPROVED Round 2)。
