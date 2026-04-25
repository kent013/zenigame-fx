# マージ分析: Run 9 (run_20260425_002330)

## 合意事項（両者一致）

- best_fitness=0、trade_count=0 個体が支配的（90/120 = 75%）
- Stage A/B/C/graduation すべて 0 件（パイプラインが ステージ A で全滅）
- 取引が発生した個体の sharpe は全て負（max -4.76、min -93.10）
- live_criteria はすべて未達（sharpe / total_pnl / trade_count）
- 直前 Run 8 の best_fitness=9.65 から急落、構造的劣化のサイン

## Claude 独自の発見

- 前回比較で best_fitness が 9.65 → 0、trade_count 1 → 0 と総崩れ
- 同一データ・同一構成（pop=20 gen=5）で大きく振れたという観測
- 解釈は浅く、改善方向の列挙までは未実施

## Codex 独自の発見

- **構造的問題: 「無取引が相対優位」**: trade_count=0 → fitness_pen=0 で、取引した負 Sharpe 個体（fitness_pen<0）より上位に評価される設計欠陥
- 世代推移: trade_count 平均 380→100→44→14→22→82（U字、世代3-4で収縮）
- primitive 偏在: P7/F11/P9/P5 で組合せが少数化、最頻組合せ ('F11','P5','P7','P9') が 26/120 = 22%
- 取引した個体は total_pnl=0 で固定（PnL 集計経路の整合性疑義）
- cross_pair_runtime_mode="skipped_single_instrument" で shadow 統計は INCONCLUSIVE

## 矛盾・要議論

なし（Codex の解釈の方が深い、Claude 解釈は表層的なため吸収）

## 統合改善提案（優先度順）

| # | 提案 | 優先度 | 出所 | target_metric | failure_mode | 期待効果 |
|---|------|--------|------|--------------|-------------|---------|
| 1 | **無取引ペナルティの構造的導入** | Critical | Codex 仮説1 | trade_count、Stage A pass | 取引数 0 が相対優位で GA が「沈黙」へ収束 | trade_count 分布の右シフト、Stage A pass>0 |
| 2 | **PnL 集計経路の数値整合性監査** | Warning | Codex 仮説2 | total_pnl | trade_count>0 でも total_pnl=0 が 100% | PnL の正しい伝搬、live_criteria 評価の信頼性 |
| 3 | **primitive 多様性の世代追跡** | Warning | Codex Facts | (diagnostic) | 組合せ縮退で探索空間が壊滅 | novelty 圧 or 同型抑制で多様性維持 |
| 4 | **cross-pair shadow の実測検証** | Warning | Codex 仮説（C8）| (diagnostic) | shadow が単独 RUN で skip され検証不能 | 複数ペア RUN で shadow が動くか確認 |

## 補足: 直近サイクルのコンテキスト

- Run 4-9 はストレステストの 6 サイクル（pop=20×gen=5×14日窓）
- Run 4 best=2.52 → Run 7 best=10.15 → Run 9 best=0 で振れ幅大
- Run 9 は cycle 6 中で停止指示があり archive Parquet が中途完了の可能性
- 今 cycle は pop=96×gen=60 への大幅スケールアップなので、評価コストは ~30倍。
  仮説1（無取引ペナルティ）の検証は本 cycle で最優先で取り組む価値がある。
