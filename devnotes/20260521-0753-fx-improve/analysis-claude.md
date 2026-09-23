# RUN run_20260520_202321 (Run 85) 分析（Claude 自己分析）

## 前提差分
なし。R85 は P2 (T110: Stage C stress cost-robustness 化) 適用後の検証 run（seed=68 = R83 と同 seed）。

## 観察事実（Facts）

### P2 検証結果（cycle 3 の主眼）
- **stress_pnl_degradation が全 436 Stage-C 評価個体で非ゼロ化**（min 3475 / median 11454 / max 22235）。R83 では全件 0（toothless）→ **P2 で cost stress が実際に PnL を悪化させるようになった**。
- Stage A/B/C = 717/436/**43**（R83 と完全同一）。gap_class 分布も同一（both_pnl_count176/pnl_only162/pass43/count_only35/sharpe_involved20）。
- best g51_i71 は live all_pass=True（sharpe4.24/pnl65210/dd1.49%/tc51）= R83 と同一。**真の spread×1.5 cost stress（~11k PnL 悪化）下でも Stage C 通過 = cost-robust 実証**。
- Stage C 通過数が不変な理由: stress gate 閾値（spread_stress_min_total_pnl=0 / spread_stress_min_sharpe=0）が緩く、43 個体は ~11k cost を吸収しても stressed pnl/sharpe>=0 を維持。

### ★ seed variance（同一 config、EUR_JPY/pop96/gen60/profit_safe_pfr）
| Run | seed | A | B | C |
|-----|------|---|---|---|
| R82 | 67 | 2687 | 941 | 0 |
| R83 | 68 | 717 | 436 | **43** |
| R84 | 69 | 391 | 62 | 0 |
| R85 | 68 | 717 | 436 | **43** |

- **R83 と R85（同 seed=68）は完全同一** → GA は seed 固定で deterministic。
- seed 67/68/69 で Stage C = 0/43/0、Stage B = 941/436/62（15倍変動）→ **探索結果が seed に極端依存（seed-locked trajectory）**。
- R85 で Stage C 個体が初出現するのは **gen 43**（遅い）。mission 個体は後期世代でのみ出現。

### graduation
- graduation_count=0（cross-pair ii-lite が shadow-only、ii_lite_pass 全件 None の構造は不変）。

## 解釈・推論（Interpretations）

### 1. mission 達成は seed=68 で deterministic だが seed 非依存に再現しない（確定）
R83=R85 の完全一致は「同 seed なら確実に 43 mission 個体」を示す。一方 seed 67/69 では 0。**run-to-run noise ではなく seed-locked**。GA の初期集団 + 確率的演算が seed で決まり、profitable region への到達可否が seed で分岐する。
- 反証可能性: もし別の複数 seed でも Stage C>0 が安定して出るなら variance は許容内。実測 4 run 中 seed=68 のみ → seed sensitivity 確定。

### 2. 最大の残課題は seed variance（再現性）であり、これが真の robustness gap
P2 で cost 整合性は解消し、seed=68 mission 個体は cost-robust と実証済。残るのは「mission 個体を **seed 非依存に確実に得る**」こと。これは GA 探索の安定性の問題。
- mission（live_criteria 達成個体を 1 つ得る）の観点では **既に g51_i71 を保持**しているが、システムが再現的に produce できないと「1 個体の偶然」の域を出ない。

### 3. seed variance への構造アプローチ候補
- **(a) warmstart（T101、登録済 standalone）**: 既知 mission 個体（g51_i71）を初期集団に注入 → gen 0 から評価され seed に依らず保持される。mission 個体の喪失を防ぎ再現性を担保。最も直接的で低リスク（初期集団への注入のみ、評価ロジック不変）。
- **(b) multi-seed 評価**: 複数 seed で GA を回し winner を intersect → 頑健性を統計的に確認。コスト N 倍（runtime 増）、loop 停止リスク中。
- **(c) population 安定化 / diversity 維持**: 大集団・selection 変更で seed 依存を低減。GA dynamics 大改変、リスク高。
- **(d) cross-pair ii-lite gate 昇格（P3）**: graduation を真の多ペア汎化ゲートに。seed variance とは別軸（graduation 配線）。

### 4. 禁止事項違反の兆候
なし。P2 は cost 厳格化（緩和でない）。seed variance 対処は探索安定化であり閾値操作でない。

## 次サイクル候補
- **[Critical] seed variance/再現性への構造対処**: 最有力は **warmstart（T101）**— 既知 mission 個体を初期集団に注入し seed 非依存に mission 個体を保持。低リスク（初期集団注入のみ、評価不変）。Codex 合議で warmstart vs multi-seed を 1 つに収束。
- **[Warning] cross-pair ii-lite gate 昇格（P3）**: graduation=0 の構造解消。多ペア汎化を要求する次の壁。中-大リスク。
- **[Warning] stress gate 閾値の妥当性**: P2 で cost が効くようになったが stress gate 閾値（pnl/sharpe>=0）が緩く強フィルタでない。cost-robust を要件として強める余地（ただし mission が seed 脆弱な現状では時期尚早、warmstart で再現性確保が先）。

## 全体判定
**OK（P2 完遂・検証成功、ただし seed variance が残る最大課題）** — cost 整合性問題は解消し seed=68 mission 個体は cost-robust と実証。残るのは mission 個体を seed 非依存に得る再現性。次は warmstart 等で探索安定化（閾値引き上げは再現性確保後）。
