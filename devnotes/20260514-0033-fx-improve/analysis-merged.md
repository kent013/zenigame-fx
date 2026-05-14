# マージ分析: Run 75 → Run 76 (cycle 23)

## 合意事項 (Claude + Codex 一致)

1. **profit_safe_pfr 効果 完全支持 [MAJOR_BREAKTHROUGH]**:
   - Stage B pass 96 → 827 (+760%), Stage C pass 0 → 217 (累積初突破)
   - Stage B 通過群の median total_pnl -7,950 → +38,520 (黒字化)
   - active_clause 1.01 → 1.47 (multi-clause 復活), unique fp 6% → 60% (10 倍改善)
   - cycle 22 で立てた仮説 (Stage B が curve-fit + 赤字許容) は完全に支持

2. **🚨 Critical bug: live_criteria.sharpe 単位不整合**:
   - `scripts/alpha_factory/run_ga.py:934-952` `_check_live_criteria` で trade-level `trade_sharpe_raw` を annualized `sharpe_min=1.0` と直接比較 → 常に False
   - 一方 `evaluate_stage_c` (stage_gate.py:1902) では `_annualize_trade_sharpe` で annualized 換算後に判定 → 217 個体が pass
   - 結果: Stage C pass=217 だが summary.json live_criteria.all_pass=False という矛盾
   - Codex 実測: Stage C 通過 217 個体の annualized sharpe **min=2.596, median=2.764, mean=2.883, max=5.023** → **全件 ≥ 1.0**

3. **graduation_count=0 の構造要因 (新発見)**:
   - 卒業条件 = `Stage C pass AND cross_pair pass`
   - Run 75 は `pair_bars={}` (single-instrument) で `cross_pair_runtime_mode=skipped_single_instrument`
   - → single-instrument 運用では卒業が **原理的に 0**
   - graduation_count KPI 解釈の修正が必要 (= stage_c_pass_count を別 KPI として監視)

4. **trade_count 下限張り付き**: Stage C 通過 217 個体中 **173 個体が trade_count=51** (= 79.7%)。境界張り付きが強い → 「取引回数最適化への寄り」の懸念は残る

## Claude 独自の発見

- best 個体 (g60_i46) の特徴: trade_sharpe_stage_c=0.184、 annualized 換算で ~2.69 → live_criteria.sharpe.value=0.190 (summary 出力) は **trade-level 値が誤って annualized 1.0 と比較されている**
- multi-clause 復活 (1.01→1.47) は profit_safe_pfr の副次効果 (gate が positive_fold_ratio 中心になり、 clause 数増加でも pfr 劣化しない)

## Codex 独自の発見

- **ショート偏重 / overnight / swap / spread 集計** が archive 列にないため、 イントラデイ逸脱・ショート偏重・コスト未反映の deceit 検知が INCONCLUSIVE
- Stage C 通過 217 個体の annualized sharpe を実測 (min=2.596, median=2.764, mean=2.883, max=5.023) — **全件 live_criteria.sharpe_min=1.0 を超過**
- graduation 条件の structural 分析 (`swim_lane.py:408,410,977` 参照、 cross_pair skip で卒業不可能)

## 矛盾・要議論

なし。 両者は完全に同方向。

## 統合改善提案 (優先度順)

| # | 提案 | 優先度 | 出所 | target_metric | failure_mode | 期待効果 |
|---|------|--------|------|--------------|-------------|---------|
| **1** | **🚨 `_check_live_criteria` を annualized 換算に統一** (Stage C 内部判定と一致) | **Critical** | Claude + Codex (両者一致) | live_criteria.sharpe.pass / mission達成個体数 | trade-level vs annualized 単位不整合で sharpe pass=False に固定 | Run 75 best g60_i46 が mission 達成 (= 217 個体相当)、 過去 19 RUN 累積でも再評価で多数の mission 達成個体が発見される可能性 |
| 2 | graduation KPI 解釈修正 / stage_c_pass_count 分離 | Warning | Codex | KPI の意思決定影響 | 卒業条件に cross_pair pass を含むため single-instrument で原理的に 0 → KPI 誤読 | KPI ダッシュボード正常化、 mission 達成定義の再認識 |
| 3 | seed sweep で profit_safe_pfr 再現性確認 | Warning | Codex | Stage B/C pass 数 variance / best annualized Sharpe | seed=60 のみで variance 未測定 | Run 75 の 217 通過が lucky draw でないことを確認 |
| 4 | 禁止事項 deceit 検知列追加 (long/short / overnight / swap / spread) | Warning | Codex | INCONCLUSIVE 解消 | archive に列がなく検知不能 | イントラデイ逸脱・ショート偏重・コスト未反映の構造的検出 |
| 5 | trade_count 境界張り付き (173/217=51 trade) の構造分析 | Suggestion | Claude (新) | 取引回数最適化偏り | live_criteria.trade_count_min=50 を狙い撃ちで稼ぐ個体が支配 | 真の利益最大化が起きていない構造 |

## 次フェーズへの申し送り

- **cycle 23 で施策 #1 (Critical bug fix) のみ実装** → Run 76 (seed=61 profit_safe_pfr) で reproduce + mission 達成個体数測定
- #2 (KPI 修正) は docs 更新のみで実装容易、 #1 と併せて 1 commit
- #3-#5 は次サイクル以降の TODO 候補

### Codex 合議で確認したい点

- **施策 #1 の最小実装**: `_check_live_criteria` 内で `_annualize_trade_sharpe` を呼ぶ minimal change (~20 行) で十分か? それとも archive 列に `trade_sharpe_annualized` を新規追加してから比較する大きな変更が必要か?
- **mission 達成の定義変更影響**: live_criteria fix で過去 19 RUN の archive を再評価したとき、 mission 達成個体が大量に発見されるシナリオ → これは GA selection 経路 / archive 集計経路への波及はあるか?
