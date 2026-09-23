# 概念設計: multi-pair training 最小 spike (T117, cycle 8)

## 背景
7 サイクルで mission を 達成可能/cost-robust/再現可能/汎化定量化(0/599) にし cross-pair 選択圧 bool→連続値化したが ii_lite_pass=0。T116 観測列 + falsification で真因完全特定: cross-pair 0 汎化は (1)EUR_JPY 学習個体の大半が anchor で取引せず pair_failure (2)取引する 7 個体も anchor 低性能 (mean_sharpe max 0.087<<pass 0.15)。EUR_JPY 単一学習の構造限界。

## 目的
GA fitness を EUR_JPY 単一でなく複数ペアで評価し、全ペアで取引+利益する汎化戦略を進化させる。anchor 取引枯渇 (pair_failure) と anchor 低性能の両方を根本解消。

## スコープ (最小 spike、Codex consensus 収束)
- **Stage A fitness のみ multi-pair 化** (Stage B/C は EUR_JPY 現状維持 = 効果帰属明確化)。
- pairs: EUR_JPY + USD_JPY (2 ペア)。aggregate: min-across-pairs (全ペアで機能強制)。
- default OFF (`multi_pair_training.enable=False`) = 単一 = 現挙動 bit-exact。
- 軽量 run (pop48 gen20 workers2) でコスト/効果見積。

## 非目的
- full (全 anchor / Stage B/C 拡張): spike 効果確認後 cycle 9。
- 閾値緩和・取引回数操作 (取引する戦略の進化は正当)。
- 閾値引き上げ (汎化達成後)。

## 期待効果
R90 で anchor pair_failure 率低下 + anchor mean_sharpe median 上昇 + ii_lite_pass>0 の兆候。spike 完了条件 3 軸 (pair_failure=0 比率 / mean_sharpe max の 0.15 接近 / wall-time・RSS) で full 可否判断。

## 使命・禁止事項整合
fitness を複数ペアで評価 = 汎化を学習側で根本対処 (評価の拡張、緩和でない)。default OFF で挙動不変。trade_count 直接優遇でなく fitness_pen(PnL/sharpe/size) の min 集約。メタ過学習ガード: out-of-run 固定期間再現。

## 詳細設計
`detailed-design.md` 参照 (Codex consensus MODIFY→収束、Critical 3 件反映: evaluate_stage_a で統一/anchor は _load_lane_bars/メモリ worker 制限)。
