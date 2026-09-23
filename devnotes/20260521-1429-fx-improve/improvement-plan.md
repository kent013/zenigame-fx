# 改善計画: Run 86 → Run 87 (cycle 5)

## 合議ステータス: 設計ドラフト（Codex consensus/design-review は次ステップ）

## 背景
cycle 4 で T101 warmstart 成功 → mission は 達成可能+cost-robust(P2)+再現可能(warmstart) に到達。R86 の 622 mission 個体は in-sample 特化 (cross-pair margin med -1.0)。残フロンティアは**汎化**。
真因確定: graduation=0 は cross-pair ii-lite が **単一銘柄実行で構造的スキップ** (run_ga.py:1934 で `GraduationLane(pair_bars={})` 空ハードコード → cross_pair_runtime_mode=skipped_single_instrument)。機構 (CrossPairConfig mode shadow/hard、graduation_criteria、_build_cross_pair_args) は揃うが**複数ペアデータ未供給**。

## 確定施策 (cycle 5): P3 cross-pair multi-pair shadow 有効化
**目的**: anchor ペアの holdout bars を GraduationLane.pair_bars に供給し cross-pair を **shadow で実走**させ、ii_lite_pass を None→True/False にして汎化の壁を定量化する。**default (anchor 未指定=空=skipped) は挙動完全不変**。hard gate 化は汎化の壁を見てから次サイクル。

| target_metric | failure_mode | causal_path | falsification | success_criterion |
|--------------|-------------|------------|---------------|-------------------|
| cross-pair ii_lite_pass 分布 (汎化定量化) → graduation 経路 | graduation=0 が単一銘柄で cross-pair 構造スキップのため | anchor ペア holdout bars を GraduationLane.pair_bars に供給 → _build_cross_pair_args が evaluator 返す → cross-pair shadow 実走 → ii_lite_pass が True/False に | anchor 供給後も cross_pair_runtime_mode=skipped / ii_lite_pass=None のまま (配線漏れ) | R87 で cross_pair_runtime_mode=enabled、ii_lite_pass が True/False 分布を持ち、何個体が多ペア汎化するか定量化できる |

## 設計詳細 (detailed-design.md 参照)
- 新規 CLI/config: `--cross-pair-anchors USD_JPY,EUR_USD` (default 空 = 現状 skipped 維持)。
- run_ga.py: anchor ペアごとに既存 `_stream_bars`/`_load_lane_bars` で holdout bars をロードし、`pair_bars = {target: holdout, anchor1: holdout1, ...}` / `pair_meta` を構築して `GraduationLane(pair_bars=..., pair_meta=...)` に供給。
- cross_pair_config.mode は **shadow 維持** (graduation 強制せず、ii_lite_pass 計測のみ)。
- メモリ: anchor 1-2 ペア × holdout 60d M1 (~60k bars) × workers。24GB 制約下で anchor 数を 1-2 に制限。Codex で scope 確定。

## 段階方針 (低リスク)
1. cycle 5 (本): anchor 1-2 ペアで cross-pair **shadow 実走**。ii_lite_pass 分布で汎化定量化。default 不変。
2. 次サイクル: 汎化の壁を見て cross_pair mode=hard or partial で graduation 要求。

## 使命・禁止事項
cross-pair shadow 有効化は汎化の観測 (評価/閾値不変、graduation 強制せず)。閾値緩和・期間延長なし。default 挙動不変。

## 次フェーズ
Codex consensus + design-review (scope: anchor 数/メモリ/Phase2 T102 重複回避/default 不変) → implement → R87 (multi-pair shadow、warmstart 併用検討) → report → cycle 6。
