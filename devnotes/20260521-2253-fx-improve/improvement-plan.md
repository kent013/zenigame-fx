# 改善計画: Run 87 → Run 88 (cycle 6)

## 合議ステータス: 設計ドラフト（Codex consensus/design-review は次ステップ）

## 背景・根本原因
cycle 5 で T114 cross-pair enable 成功 → 汎化を定量化: R87 Stage C 599 個体すべて ii_lite_pass=False、cross-pair 汎化 0/599、margin median -1.37（深い過学習）。
根本原因 (Claude=OK / Codex=CRITICAL_DRIFT 一致): GA fitness_pen = EUR_JPY in-sample sharpe − α·size のみで、cross-pair は最終 Stage C でしか評価されない → **GA 選択に汎化シグナルがゼロ** → 純 in-sample winner に収束。

## 確定施策 (cycle 6, Codex Critical): (b) cross-pair in-loop selection pressure（opt-in 段階導入）
GA 選択中に cross-pair シグナルを弱く注入し、汎化方向へ探索圧をかける。default OFF で挙動完全不変。

| target_metric | failure_mode | causal_path | falsification | success_criterion |
|--------------|-------------|------------|---------------|-------------------|
| ii_lite_pass 率 / mission_signed_margin_c_shadow の baseline(R87)比改善、汎化個体>0 | 0/599 汎化 = GA 汎化探索圧ゼロ | Stage B 上位個体に疎く cross-pair shadow eval → margin を selection_score に弱く反映 → 汎化個体が選択で残り繁殖 | R88(opt-in)で ii_lite_pass 率/margin が R87 比改善せず or 汎化個体=0 のまま → ロールバック | R88 で ii_lite_pass=True が 1 個体以上 or margin median が有意改善 |

## 調査結果 (GA selection key)
- `run_ga.py:207` `selection_score`: **10-tuple lex** `(feasible, -violation, stage_b_pass_and_feasible, stage_b_pass, stage_c_feasible, C_pass, B_pass, A_pass, fold_robust, fitness_pen)`。末尾 fitness_pen。
- `_selection_key` (255): schema により selection_score / _legacy を返す。best 選定・tournament・NSGA2 がこれを使用。
- cross-pair eval は parallel_eval の cp_inputs 経由（cycle 5 で配線済）。現状は Stage C のみ。

## ★ 設計の重要な簡素化 (追加調査で判明)
R87 では cross-pair は **Stage B 通過 1970 個体すべてで既に評価済み** (ii_lite_pass=False が 1970 件、Stage C 599 だけでない)。cross-pair eval は `cross_pair.enable=True` 時に evaluate_genome (parallel_eval) 内で Stage B pass 後に走り、結果(margin)は archive payload に流れる。
**しかし GenomeEntry(cache、selection_score の元) には cross-pair margin フィールドが無く伝搬していない** (GenomeEntry fields 確認済: fitness_pen/stage_*_pass/feasible/violation/fold_robust/pareto_* のみ)。
→ ∴ in-loop 選択圧は「**新規 eval 不要、既計算の margin を payload→GenomeEntry へ伝搬し selection_score に弱く反映するだけ**」で成立。コストは R87 と同等 (cross-pair は既に全 Stage B 個体で走る)。top-N 疎注入/キャッシュは**将来のコスト最適化**で本サイクルでは不要 (minimal pressure injection を優先)。

## 設計方向 (detailed-design で確定、簡素版)
1. config opt-in flag `cross_pair.selection_pressure: bool = False` (default OFF=selection_score 10-tuple 不変で bit-exact)。`cross_pair.enable=True` が前提 (margin が計算される)。
2. **伝搬経路追加** (新規 eval なし): evaluate_genome の cross_pair payload から margin (mission_signed_margin or ii_lite margin) を取り出し、GenomeEntry に `cross_pair_margin: float | None = None` 追加 → cache 構築時に payload から populate (Codex 4 段伝搬: payload→GenomeEntry→selection_score)。
3. selection_score に**弱く**反映: selection_pressure ON 時のみ、fold_robust と fitness_pen の間に `int(cross_pair_margin > 閾値 or margin>0)` を tie-break 挿入 (案A) or fitness_pen に小重みブレンド (案B)。**default OFF では挿入せず 10-tuple 完全不変** (bit-exact)。閾値緩和でなく加点。
4. コスト: 新規 eval なし = R87 と同等。将来 top-N 疎注入で削減可 (本サイクル範囲外)。

## Codex Warning 反映
- overfit proxy (sub-period 安定性/分散) は **prefilter 専用**に限定し最終判定へ直結させない（Reactive Parametric 回避）。本サイクルは (b) のみ、proxy は将来。
- R88 は複数 seed (68/69) A/B 比較。改善なければロールバック。

## 使命・禁止事項
cross-pair 選択圧は汎化要求の探索反映（緩和でない、評価関数の閾値は不変）。default OFF で挙動不変。メタ過学習ガード: Reactive Parametric 禁止（cross-pair margin は構造的シグナルで Structural 分類）。閾値引き上げは汎化達成後。

## 次フェーズ
Codex consensus + design-review (cost 機構/selection_score 反映位置/default bit-exact/Reactive 回避/圧の強さ) → detailed-design 確定 → implement → R88 (複数 seed A/B) → report → cycle 7。
