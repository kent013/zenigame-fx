# Best 個体構造比較 (cycle 4-8)

## 4 RUN best 個体メトリクス

| Run | seed | name | fp | a/b/c | trade_a | n_fold | pos_fold | primitives |
|----|----:|------|---:|------|------:|------:|---------:|-----------|
| 57 | 42 | g46_i51 | 0.2043 | ✓/✓/✗ | 35 | 8 | 0.875 | F7, P8, P5 |
| 59 | 44 | g55_i15 | 0.2840 | ✓/✗/✗ | 74 | 30 | 0.43 | F6, P8, F1, F14, P7 |
| 60 | 45 | g34_i33 | 0.5418 | ✓/✗/✗ | 33 | **4** | ? | F8, F7, F12 |
| 61 | 46 | g55_i66 | 0.0325 | ✓/✓/✗ | 105 | 34 | 0.62 | P2, P9, F13 |

## 重要発見

### Run 60 best (fp 0.54) は artifact の疑い

- **n_fold_effective=4** (wf_min_safe_folds=5 未満)
- Stage B 評価が成立していない (all_folds_unavailable 近接)
- median_oos_sharpe が NaN/Inf 推定で fitness_pen が高く出た可能性
- 真の Sharpe (Stage B 期間 fold OOS) は 0.58 より大幅低い見込み

これは「sharpe 0.58 達成 = mission 進捗」と見えていた cycle 7 の評価が、 観測の裏付けによって覆る可能性を示す。 **Codex 思考原則「データに真摯に向き合え」** の実例。

### Run 61 best (Stage B pass) は逆方向の bias

- **n_fold_effective=34** (理論最大に近い、 fold robust)
- positive_fold_ratio=0.62 (60% 閾値ぎりぎり)
- Stage A fp=0.03 (極低、 best 個体だが Stage A 表現力弱)
- live_criteria sharpe=0.05 (Run 60 の 1/12)
- fold robust だが Stage C 期間で大損失 (-48540)

### mission 達成の必要条件 (5 RUN 観測から)

| 条件 | 内容 | 5 RUN 観測 |
|------|------|----------|
| Stage A 表現力 | fp 0.20+ + trade_count 50+ | Run 57/59 (fp 0.20-0.28、 trade 35-74) |
| Stage B fold robust | n_fold>=5 ∧ pos_fold>=0.6 | Run 57/61 |
| Stage C profitable | total_pnl>=50000 ∧ sharpe>=1.0 | 該当なし (best max=Run 60 sharpe 0.58 だが artifact 疑い) |
| **3 条件同時** | - | **0 RUN** |

## 仮説 cycle 9-11 軽量観測 phase の主目標

1. n_fold_effective<5 個体は archive に出さない or Stage A pass 自体を除外する gating の検討 (next cycle で議論)
2. Stage A 表現力 ∧ Stage B fold robust の同時達成個体を探すために mutation 構造の検討 (cycle 16+ elite collapse 緩和と関連)
3. Stage C 期間の cost 分解 (Codex 推薦順序 3) で実損失構造を特定

## 次サイクル候補 (cycle 9 完了時点)

- **cycle 10 [Critical 観測]**: n_fold_effective<5 個体の Stage A pass 観察 — Run 60 best のような artifact 値が GA selection をミスリードしていないか調査
- **cycle 11 [Warning 観測]**: Run 60 best の Stage C 詳細実行 (best_genome.json から再現backtest) で実 sharpe / total_pnl を測定
- **cycle 12+**: Codex 戦略順守で DSR 配線復帰
