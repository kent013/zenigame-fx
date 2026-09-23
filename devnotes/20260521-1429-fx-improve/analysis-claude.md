# RUN run_20260520_232522 (Run 86) 分析（Claude 自己分析）

## 前提差分
なし。R86 は T101 warmstart 適用 (seed=69, warmstart_ratio=0.1, motif=R85 archive) の検証 run。

## 観察事実（Facts）

### warmstart 検証結果（cycle 4 の主眼、成功）
- R84 (seed=69, warmstart なし): Stage A/B/C = 391/62/**0**、mission=0。
- R86 (seed=69, warmstart=0.1): Stage A/B/C = 2198/1630/**622**、**622 個体すべて mission-eligible** (total_pnl>=50k & trade_count>=50)、best g42_i51 live all_pass=True (sharpe4.16/pnl64160/dd1.81%/tc50)。
- Stage C 通過に g0_ws0 (=注入アンカー g51_i71)・g0_ws7 が直接含まれ、子孫 (g1_i0, g2_i0…) も大量繁殖。
- → **seed-locked だった mission (seed=68 のみ) を warmstart で seed=69 でも 622 個体再現 = mission の seed 非依存化に成功**。

### ★ graduation gap / cross-pair 汎化（cycle 5 の核心）
R86 の Stage C 通過 622 個体の cross-pair shadow:
| 列 | 値 |
|----|-----|
| ii_lite_pass | **全 622 件 None** (cross-pair ii-lite は shadow-only、gate 未配線) |
| canonical_gate_pass_c_shadow | **False 618 / True 4** (cross-pair 評価は走るが gate 未接続) |
| mission_signed_margin_c_shadow | **中央値 -1.0** (大半が cross-pair で負マージン) |
| persistence_score_shadow | 中央値 0.53 |
| graduated | **0** |

## 解釈・推論（Interpretations）

### 1. mission は「達成可能 + cost-robust + 再現可能」に到達したが、個体は in-sample 特化
4 サイクルで mission を巡る 3 つの性質を確立:
- 達成可能 (R83): live_criteria 全達成個体が出る。
- cost-robust (R85/P2): 真の spread×1.5 cost stress 下でも通過。
- 再現可能 (R86/warmstart): seed 非依存に保持・繁殖。
しかし R86 の 622 個体は **cross-pair で負マージン (med -1.0)** = EUR_JPY 同一 dataset への in-sample 特化。warmstart は in-sample winner を増やすが汎化はしない (warmstart は再現性であり汎化でないと設計時に明記済)。

### 2. 残るフロンティアは「汎化 (generalization)」であり、graduation=0 がそれを定量化している
graduation = Stage C pass AND cross-pair pass。cross-pair ii-lite が shadow-only (ii_lite_pass=None) のため graduation は構造的に発火不能。**しかし cross-pair 評価自体は走っており (canonical shadow: 618 False/4 True)、その結果は「622 個体中 cross-pair でまともなのは 4 個体のみ」を示す**。つまり in-sample mission 個体の大半は多ペアで通用しない。
- 反証可能性: cross-pair を hard gate 化して graduation>0 が出れば真の多ペア汎化個体が存在。0 のままなら EUR_JPY 過学習が確定的。

### 3. cross-pair ii-lite gate 昇格 (P3) は「汎化の壁を可視化・要求する」次の自然な構造介入
cross-pair 評価は既に走り shadow 結果を出している。これを ii_lite_pass / graduation に配線 (shadow→部分hard) すれば、graduation が真の多ペア汎化ゲートになる。
- リスク: 全面 hard 化は graduation 全滅 (現状 cross-pair まともなのは 4/622) → 段階的 (shadow 計測の可視化強化 → 部分 hard) が安全。
- 代替: OOS 検証 (Alpha Sieve、未移植) / 複数ペア同時学習。

### 4. 禁止事項違反の兆候
なし。warmstart は探索の足場 (評価不変)。cross-pair gate 昇格は汎化要求の厳格化 (緩和でない)。

## 次サイクル候補
- **[Critical] cross-pair ii-lite gate 昇格 (P3)**: cross-pair shadow 結果を ii_lite_pass / graduation に配線。段階的 (まず shadow 計測の確実な記録・可視化 → graduation 判定への部分接続)。全面 hard 化は全滅リスクのため避ける。これにより「mission 個体が多ペア汎化するか」を graduation で定量化。
- **[Warning] 複数ペア同時学習 / OOS 検証**: in-sample 特化を根本緩和する学習側の対処 (大規模、将来)。
- **[Warning] live_criteria 閾値引き上げ**: mission は in-sample で再現可能になったが、汎化未確認のため閾値引き上げは時期尚早 (汎化フロンティアが先)。

## 全体判定
**OK (warmstart 成功、ただし汎化が次フロンティア)** — mission は達成可能+cost-robust+再現可能に到達。R86 が示す残課題は cross-pair 汎化 (622 個体中 cross-pair まとも 4、margin med -1.0 = in-sample 特化)。次は cross-pair ii-lite gate 昇格 (P3) で graduation を真の汎化ゲートにし、汎化の壁を定量化する。

---

## 【重要訂正】graduation=0 の真因 = 単一銘柄実行 (cross-pair 構造的スキップ)

cross-pair 評価経路を確認した結果、graduation=0 の真因は「ii-lite が shadow-only 配線」ではなく **run が単一銘柄 (EUR_JPY) で cross-pair が構造的にスキップされている** ことだった (cross_pair_runtime_mode=skipped_single_instrument)。

検証:
- `scripts/alpha_factory/run_ga.py:1934` で `GraduationLane(pair_bars={}, pair_meta={})` が **空 dict でハードコード**。
- `run_ga.py:1939-1942`: `cross_pair_mode = "enabled" if graduation_lane.pair_bars else "skipped_single_instrument"` → pair_bars 空なので常に skipped。
- cross-pair ii-lite は anchor ペア (複数銘柄) の bars を必要とするが、現状 run_ga は GraduationLane に複数ペアデータを読み込んでいない。
- ∴ ii_lite_pass=None、cross_pair_result=None → graduation_criteria が常に False (swim_lane.py:427)。
- CrossPairConfig には mode="hard" が既に存在 (cross_pair.py:99) し graduation_criteria も配線済 (swim_lane.py:402-429)。**機構は揃っているが、複数ペアデータが供給されていない**だけ。
- R86 の canonical_gate_pass_c_shadow=True 4 件は cross-pair でなく canonical-5 不変条件の shadow (単一銘柄でも計算) で別物。

### 修正された cycle 5 方針 (P3 再定義)
汎化 (graduation) には **multi-pair データを GraduationLane.pair_bars に読み込む配線** が必須。これは ii_lite 配線でなく **data-loading + multi-pair 評価の有効化** であり、規模が大きい (anchor ペアの M1 bars ロード、24GB/6worker メモリ制約、Phase 2 統合 T102 と関連)。
- 段階案: (a) まず anchor ペア 1-2 個 (例 USD_JPY) の holdout bars のみ GraduationLane に供給し cross-pair を **shadow で実際に走らせる** (ii_lite_pass が None でなく True/False を出すようにする) → 汎化の壁を定量化。(b) その後 mode=hard で graduation を要求。
- リスク: メモリ (複数ペア M1)、Phase 2 統合との重複。Codex 合議で scope (anchor 数 / shadow 先行 / メモリ) を確定する。
- これは cycle 1 で Codex が「実装面積大・loop 停止リスク」と REJECT した P3 の本体。段階導入で低リスク化する。
