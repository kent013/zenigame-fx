# マージ分析: Run 53

**Generated**: 2026-05-09 07:20 JST
**run_id**: `run_20260507_142410`

## 合意事項 (両者一致)

| # | 観察 / 仮説 | Claude | Codex |
|---|---|---|---|
| 1 | Stage A=1439, Stage B=0, Stage C=0, graduated=0 | ✓ | ✓ |
| 2 | best 個体 (g57_i15) は n_fold_effective=0 で fold 評価不能、 GA が短期集中トレーダーを上位化 | I6 | H3 賛成 |
| 3 | seed=100 と seed=42 で primitive collapse 領域が完全に異なる (F4+F13+F11 vs F6+F8+M2) | I1 | H2 賛成 |
| 4 | seed=100 領域は profitability 構造的に低い (max PnL 27,800 vs 58,830) | I2 | 賛成 |
| 5 | Stage B 全員 fail with `median_oos_sharpe<min` AND `positive_fold_ratio<min` | F9 | Facts |
| 6 | T091 (median 0.025) 単独では seed=100 の graduate に繋がらない (positive_fold_ratio<min も同時 trigger) | I3 | I3 賛成 |
| 7 | clauses-level diversity は 0.823-1.0 で健全だが、 機能多様性 (primitive entropy) は seed 別に大幅低下 | F7 / F6 | Interpretations |

## Claude 独自の発見

| # | 発見 |
|---|---|
| C1 | run-53 の Stage A pass の pfre 中央値=0.111 は run-52 の 0.40 と大きく異なる → 短期集中トレーダー支配 |
| C2 | best 個体 g57_i15 の trade=32 で n_fold_effective=0 = 全 fold で trade<10 で fold_unavailable → selection_score の lex 順序で fitness_pen が支配 → trade<50 個体が best 候補化 |
| C3 | trade_count vs Stage B pass の関係を bin 別に集計、 trade>=50 で全 0 件、 全分布で 0% (run-52 と異なり trade=10-30 でも 0%) |

## Codex 独自の発見

| # | 発見 |
|---|---|
| Z1 | clauses 多様性は維持されているが **機能多様性 (primitive entropy)** が崩れている → 探索の実質多様性は低下 |
| Z2 | cross-pair shadow が `skipped_single_instrument` で実行されていない → ii-lite 通過判定が INCONCLUSIVE のまま |
| Z3 | T091 単独では「Stage B が gate 問題か候補品質問題か」 が分離できない → 閾値調整前に固定少数 seed 比較で先に分離検証すべき (Critical 推奨) |

## 矛盾・要議論

| # | 論点 | Claude | Codex | 判断 |
|---|---|---|---|---|
| M1 | seed=42 を次 RUN に固定するか | [Warning] 固定推奨 | REJECT (Reactive / cherry-pick) | **Codex 採用** (Reactive 兆候を回避) |
| M2 | T091 を単独で進めるか、 Z3 (seed-robustness 検証) を先行するか | T091 + niching 並行 | T091 単独 + Layer 1 replay で先に検証、 seed 戦略は別議論 | **Codex 採用** (T091 を先に Layer 1 で因果検証) |

## 統合改善提案 (優先度順)

| # | 提案 | 優先度 | 出所 | target_metric | failure_mode | 期待効果 | 分類 |
|---:|---|---|---|---|---|---|---|
| 1 | **T091 実装 (Stage B gate redesign Phase 1)** | High | TODO | Sharpe + Total PnL の必要条件 | Stage B 全滅 (median + pfre 両方 trigger) | Layer 1 archive replay で 1+ 件 Stage B pass、 Layer 2 RUN で trade_count_full_dataset>=50 + pnl>=50,000 個体 1+ 件 | Structural + Principled Parametric |
| 2 | **n_fold_effective=0 上位化ガード (新規 TODO)** | High | Codex (Z3 / I6) | best 個体の品質 | best 個体が trade<50 / n_fold_eff=0 で評価不能 | best 個体が trade>=50 + n_fold_eff>=5 を満たす個体になる | Structural |
| 3 | (Phase 2 候補) primitive entropy 監視 | Medium | Codex (Z1) | 探索多様性 | 機能多様性低下が seed 別に発生 | 世代単位 primitive entropy が 1.5 以上を維持 | Structural |
| 4 | (Phase 2 候補) cross-pair shadow 復帰 | Medium | Codex (Z2) | mission 監査性 | ii-lite 判定が INCONCLUSIVE のまま | shadow 評価結果が archive に記録 | Structural |

### 採用判断

- **今 cycle 採用**: 提案 1 (T091)
- **次 cycle 採用候補 (新規 TODO 登録のみ今 cycle で実施)**: 提案 2 (n_fold_eff=0 ガード)
- **Phase 2 移動**: 提案 3, 4 (Z1, Z2)

### 次フェーズ申し送り

- T091 の実装を Phase C (詳細設計) で確認 (既存 detailed-design.md は Codex APPROVED 済み、 統合テスト計画と各段階のテストを明示する程度の確認)
- 提案 2 (n_fold_eff=0 ガード) は plan-and-design 範囲外で別途 `/zenigame-fx-alpha-design` で設計開始 (Phase B-4 に申し送り、 Phase D で TODO 登録)
- 次 RUN の seed 戦略は Layer 1 検証完了後に別議論で決定 (今 cycle では決めない)
