# 詳細設計 (cycle 21): profit_safe_pfr_threshold 0.4→0.55 (fold一貫性 robustness 軸の引き上げ)

## 決定 (Codex consensus-round-1: (A) 採用)
新品質軸 = **fold一貫性 (positive_fold_ratio_effective)** を引き上げ。Codex 推奨値 0.55。

### 実装方式: 既存 Stage B gate threshold の引き上げ (新配線不要)
- positive_fold_ratio_effective は **Stage B profit_safe_pfr gate** に既に in-loop 配線済 (stage_gate.py:1619、threshold=profit_safe_pfr_threshold)。
- live_criteria (Stage C/holdout) への新規追加は cross-stage 配線が必要で複雑 → **既存の `stage_gate.profit_safe_pfr_threshold` を 0.4→0.55 に引き上げ**るのが最小・正確な実装 (positive_fold_ratio_effective gate そのもの)。
- これは Stage B funnel の fold一貫性要件を 40%→55% に引き上げ = OOS robustness の直交品質軸引き上げ。

## 達成分布データ (R101 dd2% StageC 723)
- StageC pfr_eff: ≥0.55:720(100%) / ≥0.60:388(54%) / ≥0.65:2。
- StageB pfr_eff: min0.500/med0.618、≥0.55:2065/2170 (105 cut = 軽度binding、dd5%ほどnon-bindingでない)。
- → 0.55 は軽度binding (StageB 105 cut)。0.60 が次の本格binding点 (StageC 54%帯)。

## 変更
1. `config/alpha_factory/default.yaml` stage_gate.profit_safe_pfr_threshold 0.4→0.55。
2. 関連テストあれば 0.55 に更新。

## R103 = R101(dd2%,pfr0.4) 反実仮想 (同一seed70、pfrのみ0.4→0.55)
dd と同型の反実仮想。dd型(安全=fold一貫性選抜がmission整合)か74k型(崩壊=StageB改善だがholdout犠牲)かを in-loop 判定。

## R103 反証可能成功/失敗基準 (Codex提示5条件)
1. live_criteria+pfr≥0.55 達成数 ≥145 (R101 723の20%)。
2. 達成群 holdout median total_pnl ≥80000。
3. 達成群 holdout median ann sharpe ≥5.3。
4. 74k崩壊検知なし: StageB median上昇とholdout median pnl大幅低下(-10%超)の乖離が発生しない。
5. 別seed再現で達成数≥100 ∧ median pnl≥75000。

## 判定後
- dd型(安全、基準充足)→pfr0.55採用、さらにpfr0.60(本格binding)へ。
- 74k型(崩壊、holdout犠牲)→pfr0.55棄却し0.4へrevert(非緩和)、fold一貫性は selection に逆効果と確定。
- 連動なし(holdout改善せず形式的)→Codex助言通り打ち切り。

## launch条件
pop96/gen60/EUR_JPY/profit_safe_pfr/warmstart0.1/cross-pair-enable+selection-pressure、seed=70、dd2%/pnl70k/sharpe1.5維持、profit_safe_pfr_threshold=0.55。default挙動bit-exact (feature opt-inでなくgate threshold変更=探索影響あり、これは意図的robustness引き上げ)。
