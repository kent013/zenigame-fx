# マージ分析: Run 57 (run_20260509_084752)

## 合意事項（両者一致）

### F1. 施策 C1 (cycle 4) の主要効果は達成
- stage_partition_guard B-2 が holdout_short_override=False で pass
- holdout 60日構造的に確保 (60232 bars)
- trade_count_stage_b>=50 充足率 100% (Run 56: 33% から劇的改善)

### F2. mission 達成は依然遠い
- Stage C pass=0、 graduation=0
- best g55_i41 live_criteria 4 中 1 (max_dd) のみ pass

### F3. archive 観測欠落 (継続課題)
- DSR / ii_lite_pass / source_stage 全 NaN
- 多重比較補正 telemetry 完全停止

### F4. GA 多様性悪化
- unique fp ratio 21% → 10% (Stage B pass のうち実質 10 unique 戦略)

### F5. 新 Stage B 期間が前 RUN より厳しい regime
- Stage A pass median fp 0.185 → 0.040 (-78%)
- positive_fold_ratio median 0.80 → 0.62
- gen 30 で初の Stage B pass (Run 56 は gen 10)

## Codex 独自の発見

### X1. H6: Stage A fp 縮退が選択圧を歪めている可能性 (Inconclusive)
- Stage A pass fp median 0.040 という低水準が Stage B 探索を阻害している可能性
- George E. P. Box (1976) "Science and Statistics" — 計測系の有用性検証が必要

### X2. best 個体は Sharpe 基準を満たしつつ total_pnl で敗退
- g55_i41: sharpe=0.215, trade_count=30、 total_pnl=-24580
- コスト (spread / swap) 寄与の分解が必要

## 統合改善提案 (優先度順)

| # | 提案 | 優先度 | 出所 | target_metric | failure_mode | 期待効果 | 分類 |
|---|------|--------|------|--------------|-------------|---------|------|
| 1 | DSR 配線復帰 | **Critical** | Codex 順序 1 / Claude H3 | 多重比較補正 telemetry | dsr 全 NaN | 5856 個体試験での overfitting risk 観測可能化 | Structural |
| 2 | 再現性 check (seed=43 で Run 58) | Warning | Claude 追加 | fp 分布の安定性 | Run 57 が cycle 4 後の最初 RUN で variance 不明 | 新 baseline の安定性確認、 fp variance 推定 | Principled (探索独立性) |
| 3 | regime セグメント分析 | Warning | Codex 順序 2 | Stage B fail の時間 / pair 偏り | Stage B fail 96% が同一 reason | 失敗集中窓特定で primitive / filter 設計の根拠データ蓄積 | Structural (観測先行) |
| 4 | コスト分解レビュー | Warning | Codex 順序 3 | total_pnl 分解 (spread / swap) | best total_pnl=-24580 の構造不明 | コスト過小 / 過大の検出、 純 PnL 改善余地定量化 | Structural (観測先行) |
| 5 | Stage A fitness スケール監査 | Warning | Codex H6 | 選択圧歪み | Stage A pass fp median 0.040 縮退 | スケール不整合是正で GA 探索幅復活可能性 | Inconclusive (要調査) |

## 棄却 / 保留

| # | 提案 | 理由 |
|---|------|------|
| - | median_oos_sharpe_min 閾値緩和 | 禁止事項 4 抵触 |
| - | max_clause=3 拡張 A/B 検証 | 思考原則「仕組みが機能していない段階で値を弄るな」 (cycle 4 と同じ判断) |

## 全体判定: CONCERN (Codex 判定継承)

cycle 4 施策 C1 は意図通り成功、 ただし mission 達成に向けた「観測の質」と「戦略の進化」の両面で課題。 cycle 5 では観測強化 (DSR 配線復帰) を Critical 施策として進めるか、 実装複雑性ゆえに分割が必要かを Codex 合議で決定する。
