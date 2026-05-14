# RUN run_20260511_201001 (Run 74) 分析（Claude 自己分析）

## 前提差分

なし。`.cache/alpha_factory/runs/genomes_run_20260511_201001.parquet` / `reports/run-reports/run-74/summary.json` / `dsr_audit.json` / `scripts/codex` / docs はすべて存在し、shallow read 成功。

ただし以下を前提として保留:
- 本 skill は archive Parquet の**深い分析**（primitive 再実行、genome_json AST 解析等）を担当しない（`zenigame-fx-analyze-genome-archive` 未移植）
- cross_pair_runtime_mode は `skipped_single_instrument`（EUR_JPY 単独実行）で cross-pair shadow 統計は本 RUN では生成されていない

---

## 観察事実（Facts）

### 1. RUN メタ
- run_id: `run_20260511_201001` / run_number: 74 / instrument: EUR_JPY (single)
- dataset: 2025-04-01 〜 2026-02-19、bars 328,883（Stage A 86,400 / Stage B 242,483 / holdout 60,232）
- ga_config: pop=96, gen=60, seed=**59** (state file history と一致), max_workers=2, mutation_rate=0.5
- ga_config.fitness_metric: sharpe
- stage_gate: stage_a_window=60日、stage_a_threshold=**-0.0172**（calibrate-gate 由来）、stage_b_window=18ヶ月、stage_c_holdout=60日、spread_stress=1.5
- selection_score_schema: `v3_3_stage_b_feasible_priority`
- 完走時間: 約 240 分

### 2. Stage 通過数（archive Parquet 5,856 行）

| Stage | 通過数 | rate vs 全体 | rate vs 前 Stage |
|-------|--------|-------------|------------------|
| Stage A | 1,723 | 29.4% | — |
| Stage B | 96 | 1.64% | 5.57% (96/1723) |
| Stage C | 0 | 0% | 0% (0/96) |
| graduated | 0 | 0% | — |

per_generation 推移:
- gen 0-9: Stage A=0（10 世代不毛）
- gen 10 で初の Stage A pass=1、gen 20 で 28、gen 30 で 39、gen 40-60 で 40-50 で安定
- gen 33 で初の Stage B pass=2、gen 34-60 で 2-6 で振動
- Stage C は per_generation で 1-7 秒 evaluate されているが全て fail（最終 graduation_count=0）

### 3. Best 個体 (selection_score v3_3 = summary.json)

- name: `g60_i45` @ gen 60 / lane: tier1_EUR_JPY / parent: g59_i52 × g59_i57
- fitness_pen: 0.1063 / fitness_raw: 0.1408
- stage_a/b/c: **True/True/False**
- trade_count: **41** / total_pnl: **-15,390** / max_dd: 5.09% / trade_sharpe_stage_b: 0.0311
- median_oos_sharpe: 0.0736 / positive_fold_ratio_effective: 0.618 (>= 0.6 を辛うじて clear) / n_fold_effective: 34
- n_nodes: 7 / active_clause: 2

### 4. archive Parquet 内 fitness_pen 最大個体

- name: `g41_i78` @ gen 41 / parent: g40_i31 × g40_i14
- fitness_pen: **0.2555**（archive 最大）/ fitness_raw: 0.2950
- stage_a/b/c: **True/False/False**
- trade_count: 33 / total_pnl: +28,160 / max_dd: 0%
- trade_sharpe_stage_b: 0.026 / median_oos_sharpe: **0.0** / positive_fold_ratio_effective: **0.0** / n_fold_effective: **11**
- stage_b_reason_codes: `median_oos_sharpe<min;positive_fold_ratio<min`
- n_nodes: 4 / active_clause: 2

→ **fitness_pen 最大個体は Stage B fail**。selection_score (v3_3 stage_b_feasible_priority) で Stage B 通過個体を優先する規約のため、最終 best は **fitness_pen が 1/2.4 倍ある g60_i45** になっている。

### 5. live_criteria 結果（best = g60_i45）

| metric | value | threshold | pass |
|--------|-------|-----------|------|
| sharpe | 0.141 | ≥ 1.0 | ❌ |
| total_pnl | -15,390 | ≥ 50,000 | ❌ |
| max_drawdown_pct | 5.09% | ≤ 20% | ✅ |
| trade_count | 41 | [50, 5000] | ❌ |

→ **1/4 pass**、`live_criteria.all_pass: false`。state file history の cycle 21 (Run 74) 記録「4 中 1 pass」と一致。

### 6. Stage B 通過群 (n=96) の構造観察

| 指標 | min | max | mean | median |
|------|-----|-----|------|--------|
| fitness_pen | -0.015 | 0.106 | 0.020 | — |
| trade_count | 41 | 58 | 51.4 | 52 |
| total_pnl | **-16,670** | **-6,940** | **-8,813** | **-7,950** |
| trade_sharpe_stage_b | — | — | **-0.033** | **-0.040** |
| median_oos_sharpe | — | — | 0.051 | 0.065 |
| positive_fold_ratio_eff | — | — | 0.623 | 0.618 |
| n_fold_effective | — | — | 34.0 | 34.0 |
| n_nodes | 2 | 7 | 2.05 | — |
| active_clause | 1 | 2 | **1.01** | — |
| max_drawdown_pct | 3.49 | 5.09 | 3.91 | — |

**極めて重要な観察**:
- **Stage B 通過群 96 個体の total_pnl が全例 negative** (max=-6,940)。
- **trade_sharpe_stage_b の mean/median が negative** (-0.033 / -0.040)。median_oos_sharpe は positive (0.05) なのに、Stage B 区間の trade sharpe は negative — sharpe 計算方法（trade-level vs fold-level）の差異。
- **active_clause が 96 個体中ほぼ全員 1**（mean 1.01、95+ が 1 clause）。max_clause=2 設定があるが clause を増やせていない。
- **n_fold_effective が全員 34 で固定**。
- **unique fitness_pen は 6 種類のみ**（6/96 = 6.2%）。クローン汚染が深刻、Stage B 通過群はほぼ同一個体の繰り返し。
  - top 5 unique fp: 0.1063 / 0.0784 / 0.0743 / 0.0421 / 0.0083
  - 0.0784 が圧倒的多数（恐らく ~80 個体）

### 7. Stage B fail 原因コード（Stage A pass 1,723 中の Stage B fail 1,627）

| reason_codes | count | rate |
|--------------|-------|------|
| `median_oos_sharpe<min;positive_fold_ratio<min` | 1,556 | **95.6%** |
| `positive_fold_ratio<min` 単独 | 68 | 4.2% |
| `median_oos_sharpe<min` 単独 | 2 | 0.12% |
| 他 | 1 | <0.1% |

→ **median_oos_sharpe と positive_fold_ratio が同時 trigger** が支配的（95.6%）。fold 全体が弱い構造的問題。

### 8. DSR proxy 監査（dsr_audit.json）

- 全 5,856 個体で **dsr_proxy_pass = 0**
- 上位 Stage B 通過個体（n_fold_effective=34）の dsr_proxy 最高は **0.0266** (best g60_i45)
- dsr_threshold = **0.7144** (sqrt(2*log(5856)/N))
- 最高個体ですら threshold まで **27 倍離れている**

### 9. cross-pair shadow

- `cross_pair_runtime_mode: skipped_single_instrument` → 本 RUN では generation されず。

### 10. 18 RUN 累積（Run 57-74 history より）

- best Stage B pass: 12/18 (67%)
- mission 達成 (live_criteria all_pass): **0/18**
- Stage C pass: 18 RUN 全て 0
- DSR proxy pass: 0/18

---

## 解釈・推論（Interpretations）

C6 Fact/Interpretation 分離: ここから先は推論。

### I1. Stage B 通過 ≡ 「赤字許容」設計の可能性 [Critical]

**観察**: Stage B 通過群 96 個体の total_pnl が **全例 negative** (-6,940 〜 -16,670)。trade_sharpe_stage_b も全例 negative (mean -0.033)。

**仮説**: Stage B 閾値 (positive_fold_ratio >= 0.6, median_oos_sharpe >= 0) は **sign-based 検査**で magnitude を見ない。「sign が positive な fold が 60% 以上」かつ「fold sharpe の中央値が 0 以上」を満たせば通過するため、**多くの fold で微利、少数 fold で大損** という赤字構造でも通過する設計になっている。

**反証可能性**:
- 反証 1: 仮にコストモデルを甘くしたら通過個体が黒字になるはず → 全例 negative なので **コストではなく利益確定不足**
- 反証 2: Stage B 閾値が magnitude を見るなら通過個体は黒字のはず → 通過個体全員赤字 → **sign-based 仮説支持**
- 反証 3: trade_sharpe_stage_b が positive な個体が 1 例でもあれば仮説は弱まる → 96 個体全例 negative → **支持**

**重要性**: これは禁止事項 #6（取引回数削減で見かけ改善）の **逆方向の問題**。GA は「利益を出す」ではなく「sign positive fold 60% を達成する」最適化に流れている。

### I2. clause collapse (active_clause 1.01) [Critical]

**観察**: max_clause=2 だが Stage B 通過群の active_clause mean 1.01。

**仮説**: GA の selection / mutation が **1 clause** に収束する dynamic を持つ。Stage A の fitness が **1 clause で十分な水準**（threshold -0.0172、相当緩い）に達するため、複雑性ペナルティ込みで 1 clause が常勝。

**反証可能性**:
- 反証: 全体集団の active_clause を見て同様に 1 集中なら GA dynamics 由来、Stage B 通過群だけ 1 集中なら閾値設計由来 → 全体 mean 3.92 (Stage A pass) → **集団は多 clause 探索しているが Stage B で 1 clause に絞られる** → I1 と整合（多 clause は赤字幅が大きく Stage B 通過しにくい）

### I3. 多様性崩壊 (Stage B unique fp 6.2%) [Critical]

**観察**: Stage B 通過群 96 個体の unique fitness_pen は 6 種類。0.0784 が dominant。

**仮説**: Stage B 通過の経路が非常に狭く、GA が同一個体（または極めて近い copy）を量産している。selection_score v3_3 が Stage B pass を強く preference するため、一度発見した Stage B pass 個体が elite として残り続け、population 全体に拡散。

**反証可能性**:
- 反証: parent_a/b の unique 数を見れば実質的な lineage 数が分かる → unique parents 110/138 → 親も多様性低下、cross-lineage 探索が機能していない

### I4. fitness_pen と Stage B pass の乖離 [Warning]

**観察**: archive 最大 fitness_pen (g41_i78, fp=0.255) は Stage B fail、selection_score best (g60_i45, fp=0.106) は Stage B pass。

**仮説**: Stage A 評価関数 (sharpe-based) と Stage B fold 評価関数 (positive_fold_ratio + median_oos_sharpe) が**異なる最適解**を生む。Stage A 最強は Stage A 期間 (60日) に過適合し、Stage B (18ヶ月) で剥がれる。

**反証可能性**:
- 反証: fitness_pen 上位 N 個体の Stage B pass 率を見る → archive 全体 Stage B pass 96/5856=1.6% に対し fitness_pen 上位の Stage B pass 率を測定する必要がある（未測定、Codex 委譲候補）

### I5. DSR proxy 27 倍離れ [Warning]

**観察**: dsr_proxy 最高 0.0266 vs threshold 0.7144。

**仮説**: M=5856 trials の多重比較補正で全個体 fail。これは「探索数が多すぎて統計的有意性を主張できない」状態。

**反証可能性**:
- 反証 1: pop_size を下げれば M も下がり threshold も下がる → 探索効率と statistical robustness のトレードオフ
- 反証 2: より「真に強い」個体が出現すれば proxy が threshold に近づく → 現状の構造改善が必要

### I6. 禁止事項違反兆候の検査 (C4)

- **イントラデイ逸脱**: trade_count_full_dataset mean 252 / Stage B mean 181 → 18ヶ月 × 月 10 trade ≒ 180 トレード ≒ 平均 1.5 日/トレード。intraday と言うには長いが、明確な逸脱ではない（要確認: 保有時間分布）
- **取引回数削減で見かけ改善**: best 個体の trade_count=41 で live_criteria 50 下限を下回っている。fitness_raw 0.14 を維持しつつ trade_count を削った形跡はあるが、Stage B 通過全員が赤字なので「見かけ改善」より「赤字許容」のほうが本質
- **live_criteria 緩和**: 設計に閾値固定の history があり、本 RUN では緩和の痕跡なし
- **ショート追加で見かけ改善**: 本 skill では trade-level direction の集計をしていない（archive に shorts / longs 別の trade_count なし）— Codex 委譲候補

### I7. live_criteria 達成見通し

18 RUN 累積で all_pass=0。最大 sharpe は Run 60 の 0.581 (single)、best total_pnl は Run 60 の +36,030 (≒ live 50k の 72%)、trade_count は Run 61 の 74 まで届いた。**しかし 4 条件同時達成 (sharpe ≥ 1.0 ∧ pnl ≥ 50k ∧ dd ≤ 20% ∧ trade ∈ [50, 5000]) は 0 例**。Stage B 通過群がそもそも赤字構造の中で live を達成するのは構造改革なしに困難。

---

## 次サイクル候補

### [Critical] C22-1: Stage B 通過の sign-based 検査の magnitude 化

**仮説**: I1 (Stage B 通過 ≡ 赤字許容) を反証/支持するため、Stage B 閾値に **magnitude 要件**を追加する。

**具体策**:
- Stage B 通過の必要条件として `median_oos_total_pnl >= 0` （または `mean_fold_pnl >= 0`）を **追加**
- 既存の `positive_fold_ratio >= 0.6` と `median_oos_sharpe >= 0` は維持
- 旧 stage_b 閾値設計の cross-run guard で `stage_gate_version` を bump（誤適用防止）

**反証実験**: 次 RUN で magnitude 要件を追加し、
- Stage B pass 数が激減 → 仮説支持（現在の Stage B pass 大半が赤字経由）
- Stage B pass 数がほぼ不変 → 仮説否定

### [Warning] C22-2: clause 2 個強制 (active_clause floor)

**仮説**: I2 (clause collapse) 対策として GA 初期化と mutation で active_clause >= 2 を強制。

**具体策**:
- `genome_init` で active_clause=2 を必須化
- mutation で active_clause が 1 に減る突然変異を抑制 (floor=2)

**反証**: clause 2 強制で Stage A pass 数が激減すれば clause collapse は GA dynamics 由来ではなく Stage A 閾値の都合 → 別仮説検証へ

### [Warning] C22-3: 多様性回復施策 (fitness sharing or niching)

**仮説**: I3 (Stage B unique 6.2%) 対策として GA selection に fitness sharing を追加。

**具体策**:
- 同一 fitness_pen (rounded to 6 digits) の個体に対し sharing penalty
- または structural diversity metric (genome AST 距離) で niching

ただし大規模変更となるため、まず **観測**段階で「Stage B unique 数の cycle ごと推移」を sieve するスクリプトを書き、データ集めから始める。

### [Warning] C22-4: cross-pair lane 復活 (single → multi-instrument)

**観察**: cross_pair_runtime_mode が `skipped_single_instrument` で shadow 統計ゼロ。EUR_JPY 単独で 18 RUN 同じ regime を擦り続けている可能性。

**具体策**:
- 次 RUN を **USD_JPY** または **EUR_USD** にスイッチして regime shift の影響を観察
- または `--instrument-list "EUR_JPY,USD_JPY"` で multi-instrument mode に切替（実装可能性は別途確認）

---

## 全体判定

**CRITICAL_DRIFT (= I1: Stage B 通過個体が全例赤字)** — 構造的に Stage B 閾値が利益を保証しない設計になっている可能性が高い。閾値チューニングではなく **設計レベルの是正**が必要。

次サイクル C22 では C22-1 (magnitude 閾値追加) を**最優先**で実装し、反証実験を行う。

---

## 未接続 hook

- `zenigame-fx-post-run-review`: 接続済 (improve-cycle Phase 1 末尾の launcher で起動。本 skill スタンドアロンでは起動しない)
  - cycle 22 では 30 RUN ループのリソース管理上 skip（marker pre-write）
- `zenigame-fx-analyze-genome-archive`: 未移植（primitive 偏在 / genome AST 距離分析が未実施 — clause collapse 仮説 I2 と多様性 I3 の verification が宙）

---

## 滞留 TODO 判断

直近 Closed TODO: T094 @ 2026-05-13 18:28。
Open TODO はすべて 2026-05-13 19:15 追加（T095-T103）→ **滞留 TODO なし**（全件 1 時間以内に新規追加）。

| ID | 判断 | 理由 |
|----|------|------|
| (なし) | — | 全 Open TODO が直近追加で滞留ゼロ |

## Conditional 昇格チェック

| ID | タイトル | トリガー条件 | 評価 | アクション |
|----|---------|-------------|------|----------|
| T104 | PR6: F6/F10/F4/F7 grammar soft downweight opt-in | PR4 smoke で F6 含有率 top decile が baseline×1.5 超 | **未成立**（PR4 smoke 結果未生成。T094 (PR4) は 2026-05-13 18:28 close 済だが Run 74 は PR4 smoke ではない） | スキップ（次サイクルで再評価） |

## TODO 選定結果

**standalone 確認**: Open テーブルに standalone 5 件（T099, T100, T101, T102, T103）あり → SKILL.md ルール「最優先 standalone 1 件、incremental 混在禁止」を適用。

**選定**: **T099 (High, standalone)** を採用。

| ID | タイトル | 優先度 | target_metric | failure_mode | causal_path | falsification | success_criterion | 判定 | 理由 |
|----|---------|--------|--------------|-------------|------------|---------------|-------------------|------|------|
| **T099** | PR5: Stage B gate pfr_only opt-in A/B | High | Stage C trade_sharpe median / Stage C pass count / Stage B 通過群 total_pnl 中央値 | Run 74 で Stage B 通過 96 個体全例赤字 (-6,940〜-16,670)、trade_sharpe_stage_b median -0.040、18 RUN 累積で Stage C pass = 0。過去 Codex 合議で archive 実測 Spearman ρ(median_oos_sharpe → trade_sharpe_stage_c) = **-0.361** (curve-fit 逆予測)、ρ(positive_fold_ratio → trade_sharpe_stage_c) = **+0.345** (唯一の正予測) | median_oos_sharpe gate が curve-fit 個体選好 → Stage C で持続性失う | Run 75 (smoke `--stage-b-gate-kind pfr_only`) で Stage B pass 数が legacy 比で激減 or Stage C median trade_sharpe が悪化なら仮説否定 (= legacy に戻す)、観測:Stage B 通過群 median total_pnl が positive 化 or Stage C pass >= 1 が出現すれば仮説支持 | Run 75 で Stage C pass >= 1 出現 OR Stage B 通過群の median total_pnl が positive 化 | **採用** | High 優先 standalone、archive 実測根拠あり、Run 74 で発見した「Stage B 全員赤字」「Stage C pass 0」を直接対処 |

**非採用** (incremental 混在禁止ルール / standalone 1 件のみルールにより):
| ID | タイトル | モード | 判定 | 理由 |
|----|---------|--------|------|------|
| T095 | T092 fold guard fixture 修正 | incremental | 見送り | standalone 採用時は混在禁止 (SKILL ルール) |
| T096 | archive.py:335 mypy narrowing fix | incremental | 見送り | 同上 |
| T097 | docs progress_criteria 明文化 | incremental | 見送り | 同上、docs 系で GA mission に直結せず |
| T098 | scripts out-of-cluster audit | incremental | 見送り | 同上 |
| T100 | Stage C stratified allocation | standalone | 見送り | T099 採用、 standalone 1 件のみルール。T099 と機能領域は重なるが T099 が pfr_only opt-in (gate 側)、T100 は Stage C 評価集団 stratifier (allocation 側) で本来両立可能。次サイクル候補に持ち越し |
| T101 | Run 71/63 系統 warmstart | standalone | 見送り | 同上、Low 優先で T099 を優先 |
| T102 | Phase 2 統合 Step 3-7 | standalone | 見送り | 同上、Medium 優先で大規模 (5 sub-PR) のため smoke 検証フローと衝突 |
| T103 | primitive 拡張 (82 primitive 相当) | standalone | 見送り | 同上、Low 優先で大規模 |

## GA 分析由来の改善候補 (Phase B で合議)

T099 と並走可能な GA 改善（competing と統合の両方を Codex 合議で判断）:

- **C22-1 (Codex Critical 提案)**: Stage B feasible 条件に純利益要件追加 (`median_oos_total_pnl >= 0` ∧ `trade_sharpe_stage_b > 0`)
  - T099 (pfr_only opt-in) と機能領域が**重なる**: 両者とも Stage B gate を改修。T099 は「median_oos_sharpe を gate から外す」、C22-1 は「pnl/sharpe magnitude 条件を追加」
  - 統合可能性: pfr_only mode + magnitude floor (`pfr >= 0.4` ∧ `median_total_pnl >= 0` ∧ `trade_sharpe_stage_b > 0`)
  - 競合可能性: T099 だけだと curve-fit 防止は効くが赤字許容構造は残る (positive_fold_ratio 0.4 を満たしても 60% が損失 fold は可能)。C22-1 を併用すれば magnitude も保証
  - **判断**: Phase B Codex consensus 合議で T099 を **strict superset** に統合提案（pfr_only + magnitude）。Codex が NG なら T099 単独で smoke 実行

cycle_focus 暫定判断: **mixed** (T099 standalone + GA 改善 C22-1 統合の 1-2 件)
