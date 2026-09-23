# 改善計画: Run 88 → Run 89 (cycle 7)

## 合議ステータス: 設計ドラフト（Codex consensus/design-review は次ステップ）

## 背景・診断
cycle 6 T115 (cross-pair in-loop selection pressure, bool tie-break) は本番動作 (schema v3_4/effective=True) したが ii_lite_pass=True 0/619 (受入未達)。診断: bool tie-break `int(aggregate_fitness>0)` は **gen0 から全個体 >0 で飽和し上昇圧ゼロ** (gen 別 median 0.027→0.022 平坦、pass 閾値 mean_sharpe_cross≥0.15 到達 0)。Codex=CRITICAL_DRIFT。

## 確定施策 (cycle 7, Codex Critical): T116 連続値選択圧 + pass 条件観測列
bool tie-break を **連続値**に置換し勾配を継続付与。同時に pass 3 条件 (mean_sharpe_cross/min_sharpe_cross/sharpe_target_cross_ratio) の実値を archive 観測列に追加し、(b) 天井検証 (実 max mean_sharpe_cross が 0.15 近傍か) + proxy 整合性 (aggregate と mean_sharpe_cross が同方向に climb するか、メタ過学習ガード) を世代別記録。

| target_metric | failure_mode | causal_path | falsification | success_criterion |
|--------------|-------------|------------|---------------|-------------------|
| ii_lite_pass>0 / cross_pair fitness の gen 上昇 | bool tie-break が gen0 飽和で上昇圧ゼロ | 連続値で勾配付与 → cross-pair fitness が世代で上昇 → pass 閾値到達 | R89 で連続値化後も median が ~0.05 で頭打ち & ii_lite_pass=0 → 単一ペア学習の天井確定 → multi-pair へ | R89 で cross_pair fitness median が上昇 (gen 傾き正) & ii_lite_pass=True>=1 |

## 設計方向 (detailed-design で確定)
1. **_selection_key 連続値化** (run_ga.py): 現 `cp_pref = int(cross_pair_margin > threshold)` を **連続値** `cp_val = cross_pair_margin if (not None and finite) else -inf` に置換 (fold_robust と fitness_pen の間)。NaN/inf guard で lex float 比較安定性確保。default OFF (selection_pressure=False) では現行 10-tuple 不変 (bit-exact)。
   - 連続値の指標: cross_pair_margin (=aggregate_fitness) をそのまま使うか、mean_sharpe_cross (pass 直結) に変えるか → Codex 合議で確定 (pass 整合性重視なら mean_sharpe_cross)。
2. **pass 3 条件観測列追加** (archive、観測専用・selection 非影響): `cross_pair_mean_sharpe` / `cross_pair_min_sharpe` / `cross_pair_target_ratio` を CrossPairResult.metrics (mean_sharpe/min_sharpe/sharpe_target_cross_ratio) から 4 点セットで追加。天井検証 + proxy 整合性の世代別観測 (Codex Warning1)。
3. config: 既存 `cross_pair.selection_pressure` を流用 (連続値化は実装変更のみ、新 flag 不要)。or `selection_pressure_mode: Literal["bool","continuous"]` で bool/continuous 切替 (後方互換、Codex で要否確認)。

## Codex Warning 反映
- W1 (proxy 整合性): pass 3 条件実値の観測列で「aggregate が climb しても mean_sharpe_cross が climb しない」ミスアラインを検知。
- W2 (multi-pair spike): 連続値化が天井頭打ちなら cycle 8 で multi-pair training 最小 spike (2 ペア短窓) でコスト見積。

## 使命・禁止事項
連続値選択圧は汎化要求の探索反映 (緩和でなく勾配付与)。default OFF で挙動不変。観測列は selection 非影響。メタ過学習ガード: cross-pair fitness は Structural。閾値引き上げは汎化達成後。

## 次フェーズ
Codex consensus + design-review (連続値指標 aggregate vs mean_sharpe_cross / lex float NaN-inf 安定性 / default bit-exact / pass 条件観測列 / bool→continuous 切替の後方互換) → detailed-design 確定 → implement (T116) → R89 (連続値化 A/B vs R88 bool / R87 OFF) → report → cycle 8。
