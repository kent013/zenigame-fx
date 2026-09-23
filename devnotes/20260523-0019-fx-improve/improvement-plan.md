# 改善計画: Run 89 → Run 90 (cycle 8)

## 合議ステータス: 設計ドラフト（Codex consensus/design-review は次ステップ）

## 背景・根本原因（falsification 済、完全特定）
7 サイクルで mission を 達成可能/cost-robust/再現可能/汎化定量化(0/599) にし、cross-pair 選択圧を bool(R88)→連続値(R89)化。だが ii_lite_pass=0 のまま。
T116 観測列 + falsification で真因確定:
1. 大半 (2103/2142) は **anchor で取引せず** pair_failure=2 (metric_unavailable)。
2. 全ペアで取引する 7 個体も **anchor 低性能** (mean_sharpe max 0.087 << pass 0.15)。
∴ EUR_JPY 単一学習の構造限界。選択圧・anchor 再選定・trade_count 緩和では不十分。

## 確定施策 (cycle 8, Critical): multi-pair training（最小 spike 先行）
GA fitness を **EUR_JPY 単一でなく複数ペアで評価**し、全ペアで取引+利益する汎化戦略を進化させる。これにより anchor 取引枯渇 (pair_failure) と anchor 低性能の両方を根本解消。

| target_metric | failure_mode | causal_path | falsification | success_criterion |
|--------------|-------------|------------|---------------|-------------------|
| ii_lite_pass>0 / anchor pair_failure 減 / anchor mean_sharpe 上昇 | EUR_JPY単一学習で anchor 取引枯渇+低性能 | fitness を複数ペアで評価 → 全ペアで取引+利益する個体が選択・繁殖 → anchor でも機能 | multi-pair でも pair_failure 高止まり/anchor mean<0.15 のまま | R90 で anchor pair_failure 率低下 & anchor mean_sharpe median 上昇 & ii_lite_pass=True>=1 |

## 現状調査
- fitness は `evaluate_stage_a(ctx.bars_a)` = EUR_JPY Stage A bars 単一ペアの trade_sharpe (parallel_eval.py:289)。fitness_pen = sharpe − α·size。
- `cross_pair.py:_run_pair_sharpe` が per-pair backtest を既に実装 (再利用可能資産)。
- 複数ペア train bars (Stage A/B) は run_ga の aux/bars ロードに anchor 分追加が必要。

## 設計方向 (detailed-design で確定、Codex 合議)
- config opt-in flag `multi_pair_training.enable: bool = False` (default OFF=単一ペア=現挙動 bit-exact)。
- enable 時、fitness 評価を複数ペア (EUR_JPY + anchor) で実施し集約: **min-across-pairs** (全ペアで機能を強制、汎化に強い) or mean。Codex で確定。
- **最小 spike 先行 (Codex rigor)**: 2 ペア (EUR_JPY + USD_JPY) 短窓・generations 少で **コスト/効果見積** (現単一でも ~7h、複数ペアで ×N 倍)。full 実装前にコスト/改善幅を測る。
- メタ過学習ガード: out-of-run 固定期間で再現確認。trade_count 直接優遇は選抜に入れず PnL/DD/汎化軸を維持 (禁止事項 6 回避)。

## Codex Warning 反映 (cycle 8 analysis)
- 取引する戦略を進化させるのは正当 (取引回数操作でない)。閾値緩和なし。
- multi-pair は full 前に最小 spike でコスト見積。

## 使命・禁止事項
multi-pair training は汎化を学習側で根本対処 (評価の厳格化・拡張、緩和でない)。default OFF で挙動不変。閾値緩和・期間延長・取引回数操作なし。閾値引き上げは汎化達成後。

## 次フェーズ
Codex consensus + design-review (集約方式 min/mean / 最小 spike 設計 / メモリ・速度 / default 不変 / メタ過学習ガード) → detailed-design 確定 → implement (最小 spike) → R90 (multi-pair spike) → report → cycle 9。規模大のため段階分割 (spike→full)。
