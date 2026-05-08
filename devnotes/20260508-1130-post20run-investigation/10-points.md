# 20 RUN improve-cycle 後の徹底調査: 10 論点

**Generated**: 2026-05-08 11:30 JST
**前提**: `reports/20-run-improve-cycle-detailed.md` (RUN 34-53、 19 RUN、 60.5 時間)
**情報源**: `src/alpha_factory/`、 `scripts/alpha_factory/`、 `.cache/alpha_factory/runs/genomes_*.parquet`、 `config/alpha_factory/default.yaml`、 zenigame 比較
**実データ調査対象**: run-50 (seed=23 gens=90)、 run-52 (seed=42 gens=90)、 run-53 (seed=100 gens=60)

---

## 観察事実 (FACT) のサマリ

### F1. run-52 archive 内の使命適格個体は **既に 7 件存在**

| name | gen | trade | total_pnl | pfre | n_fold_eff | sb_reasons |
|---|---:|---:|---:|---:|---:|---|
| g70_i9 | 70 | 138 | 56,930 | **0.7** | 10 | median_oos_sharpe<min |
| g71_i36 | 71 | 65 | 58,830 | 0.5 | 10 | median_oos_sharpe<min;positive_fold_ratio<min |
| g72_i64 | 72 | 65 | 58,830 | 0.5 | 10 | 同上 |
| g89_i36 | 89 | 124 | 57,590 | 0.5 | 10 | 同上 |
| g88_i12 | 88 | 124 | 57,590 | 0.5 | 10 | 同上 |
| g65_i88 | 65 | 116 | 53,750 | 0.4 | 10 | 同上 |
| g83_i12 | 83 | 127 | 50,820 | 0.7 | 10 | median_oos_sharpe<min |

**いずれも Stage A pass + trade>=50 + total_pnl>=50,000 を満たし、 Stage B median_oos_sharpe<0.05 で blocked**。
レポートの結論「Stage B + feasible は探索空間内に存在しない (構造的限界)」は **誤読**。 探索空間内には存在し、 **Stage B median_oos_sharpe gate が排除している** だけ。

### F2. trade_count vs Stage B pass の極端な二極化 (run-52)

| trade_bin | count | sb_pass | sb_rate | pfre_med | pnl_max | 備考 |
|---|---:|---:|---:|---:|---:|---|
| 10-20 | 97 | 97 | **100%** | 0.70 | 23,910 | short-burst |
| 20-30 | 37 | 35 | 95% | 0.70 | 27,260 | short-burst |
| 30-50 | 44 | 4 | 9% | 0.40 | 44,850 | mid |
| 50-80 | 725 | 0 | **0%** | 0.50 | **58,830** | mission-feasible |
| 80-120 | 1,020 | 0 | **0%** | 0.45 | 53,750 | mission-feasible |
| 120-200 | 433 | 0 | **0%** | 0.30 | 57,590 | mission-feasible |
| 200+ | 248 | 0 | **0%** | 0.10 | 35,380 | over-trading |

**Stage B pass は trade<=30 に集中、 trade>=50 は 0/2,426 (0%)**。

### F3. Mode collapse on (F6 + F8 + M2)

run-52 の Stage A pass + trade>=50 + PnL>0 個体 (n=2,397) における primitive 使用率:
- **F6 SessionMomentum**: 91% (2,193)
- **M2 SessionGate**: 90% (2,175)
- **F8 BollingerRevert**: 89% (2,127)
- 次点 P12=13%、 P3=12%、 P9=8%、 F4=4%、 F11=3%、 F13=4%、 F12=4%、 F1/F2/F3/F5/F10=ほぼ 0%

**14 個の F primitive (F1-F14) のうち、 F6+F8 のみが GA に選ばれ続け、 残り 12 個が事実上未使用**。 同様に M3-M6 (SpreadConditionGate / EconomicEventGate / VIXRegimeGate / TrendStrengthGate) は使用率<5%。 これは genetic drift / mode collapse。

### F4. Clone amplification: run-52 で 60+ 個の `trade=87, pnl=49,020` 個体

`g69_i20` 系統 (clauses ハッシュ `48f169ef` + `40e687a8`) が gen 69 以降に **60 個体以上に増殖**、 全員 Stage B 不通過。 best_fp は gen 41-68 で 0.185 stagnant、 gen 69-90 で 0.191 stagnant。 **gens=90 の最後 22 世代は探索ゼロ、 elite クローン複製のみ**。 explicit な clauses-level diversity は 0.91-0.95 と「健全」に見えるが、 elite slot は同一系統の clone で支配される構造。

### F5. selection_score 10-tuple の dead-code 重複

`scripts/alpha_factory/run_ga.py:208-219` で `int(self.stage_b_pass)` が **位置 4 と 7 の両方**に出現:
```python
return (
    int(self.feasible),                                   # 1
    -v_norm,                                              # 2
    int(stage_b_pass_and_feasible),                       # 3 (cycle 5)
    int(self.stage_b_pass),                               # 4 (T046)
    int(self.stage_c_feasible),                           # 5
    int(self.stage_c_pass),                               # 6
    int(self.stage_b_pass),                               # 7 ← 4 と同値、 functional no-op
    int(self.stage_a_pass),                               # 8
    int(self.fold_robust),                                # 9 (cycle 4)
    fp_norm,                                              # 10
)
```
docstring も両方を `stage_b_pass` と明記。 cycle 4→5 の incremental 変更時に v3.2→v3.3 の旧 4 番位置が残った refactor leftover の可能性。

### F6. Stage C holdout の構造的破綻

config: `stage_c.holdout_days = 60`
実データ: `bars_holdout = 20,457` ≈ **14 日**
→ dataset が 60 日分の holdout を持っていない (dataset.end=2026-04-01、 利用可能データ ~14 日)。

run-52 で Stage B pass=136 のうち、 trade_sharpe_stage_c が non-null は **8 件のみ** (= 残 128 件は holdout で trade を生成できない)、 8 件全員 sharpe<0。 → Stage C は 19 RUN 全 0 件 pass (構造的に通過不可能な状態)。

### F7. trade_count 参照系の scale-misalignment

archive `trade_count` は **Stage A 60 日 window のみ**で計測 (Stage A → archive 直結)。
live_criteria.trade_count_min=50 は使命達成判定で「データセット全期間 (180 日)」 のスコープを含意。
selection_score の `feasible = (trade_count >= 50)` は Stage A trade_count を直接使用。

trade=15 の Stage A pass 個体が n_fold_effective=10 / pfre=0.7 を達成している事実は、 **Stage A (Jan-Mar) と Stage B (Oct-Jan) で trade rate が大きく異なる**ことを示唆。 selection feasibility と live mission feasibility が**別スケール**で判定されている。

### F8. Stage B median_oos_sharpe_min=0.05 の noise floor 整合性

設計コメント (`config/alpha_factory/default.yaml`):
> Lo (2002) "Statistics of Sharpe Ratios" SE ≈ √((1+0.5×SR²)/N) の SE 上限 0.32 から逆算した N=10 を採用。

`stage_b_fold_trade_count_min: 10` で fold あたり trade 下限 10。 SE ≈ √(1/10) ≈ 0.32。 median across 10 folds の SE ≈ 0.32/√10 ≈ 0.10。
→ true SR=0.05 の個体は noise によって median が 0 付近で揺れる確率が極めて高く、 median>=0.05 を**安定通過するには true SR ≥ 0.15 が必要**な閾値設計。 でも mission criteria の sharpe_min=1.0 (annualized、 trade-level だと~0.05-0.10) と整合性が取れていない。

### F9. seed sensitivity の真因は mode collapse + threshold 近接 (H11 上書き)

| seed | gens | max_pnl (Stage A pass + trade>=50) | mission達成個体数 |
|---|---:|---:|---:|
| 23 | 90 | 48,640 | 0 (1,360 short!) |
| 42 | 90 | **58,830** | 7 |
| 100 | 60 | 27,800 | 0 |

レポートは「H11 verified: GA は seed sensitive、 multi-seed batch が必要」 と結論。 しかし 19 RUN 全てで GA は **(F6+F8+M2) attractor に collapse**。 seed が決めるのは「F6+F8+M2 内のパラメータ点群がたまたまどこに着地するか」 の差。 seed=23 は 1,360 円差で達成失敗、 seed=42 は超過、 seed=100 は離れた局所解。

→ multi-seed batch は symptomatic な mitigation (確かに 5-10 seed で 1-2 件は graduate するだろう)。 root cause は **GA 探索が primitive 多様性を維持できない構造**。

### F10. archive schema の未使用 column

`archive_role`、 `source_stage`、 `dsr` 全て null。 schema 拡張が部分的に放置されている。 minor だが design hygiene の問題。

---

## 論点 (DISCUSSION POINTS) — Codex 議論用

### 論点 1: 使命達成は「探索の問題」 か 「ゲートの問題」 か

**FACT**: 使命適格個体 (Stage A pass + trade>=50 + PnL>=50K) は run-52 archive に **既に 7 件存在** (F1)。 これらは `median_oos_sharpe < 0.05` で全員 blocked。

**論点**: 報告書の最終結論「Stage B + feasible は探索空間内に **存在しない** (構造的限界)」は事実誤認。 真の問題は探索ではなく **Stage B median_oos_sharpe_min=0.05 の閾値設計**と **fold WF 構造**。 真の限界か、 ゲート設計の問題か、 を切り分けるべき。

**仮説 H_F1**: median_oos_sharpe_min を「fold 内 trade-level Sharpe の median + SE-aware lower bound」 に置き換えると、 7 件の使命適格個体のうち少なくとも 1 件は Stage B pass する。 (検証可能)

**設計選択肢**:
- (A) median_oos_sharpe_min を 0.05 → 0.0 に緩和 (まず最小介入で run-52 archive を replay)
- (B) median を t-statistic ベース (median × √N_eff / SE) に置換し、 「median が 0 から有意に外れているか」 で判定
- (C) median_oos_sharpe_min を保持しつつ、 **positive_fold_ratio_effective が十分高い (≥0.6)** 場合は OR で通過 (current AND を OR にゆるめる)

### 論点 2: Stage B の short-burst noise vs feasible 二極化

**FACT** (F2): trade<=30 個体は 132/134 (98.5%) Stage B pass、 trade>=50 個体は 0/2,426 (0%) Stage B pass。 報告書は「mutually exclusive populations」 と結論。

**論点**: これは **WF fold 内 trade 数の偏りによるアーティファクト**ではないか:
- trade=15 個体: 全期間 Stage B 67日で trade=15 だが、 個別 fold (18日) で trade>=10 なら fold_sharpe 計算可能。 14 trade を 10 fold に分けて 1 fold に集中したら per-fold N=10 で SR は noise 上振れしやすい
- trade=80 個体: per-fold N=8 程度、 fold_trade_count_min=10 を割って fold_unavailable → median が 0 で imputed → fail

→ **trade=80 個体が fold_unavailable に落ちている**のではないか? 確認: run-52 archive で trade>=50 個体の n_fold_effective median=10。 fold_unavailable は起きていない。 では何が違う?

→ trade=80 個体は fold が effective だが per-fold sharpe が low (true SR=0.03〜0.05 程度) で安定低位。 trade=15 個体は per-fold sharpe が **乱れた高低分布**で median が偶発的に 0.05 を超える (noise-driven survivor bias)。

**仮説 H_F2**: Stage B 通過個体の OOS holdout 性能は trade>=50 群 < trade<=30 群となる (ノイズ通過の表れ)。 検証: cycle 19 archive の Stage B pass 個体を分析・holdout で実 Sharpe 測定。

**設計選択肢**:
- 現行の median_oos_sharpe ベース判定そのものを「fold 標本ノイズに対して脆弱」 と認識し直す
- fold 集約を median から **「fold 数を補正した t-stat」「DSR (Deflated Sharpe)」** に切り替える
- DSR (`dsr` column) は monitor_only で機能していないので有効化を検討 (cycle 0 design)

### 論点 3: Mode collapse 対策 — 真の primitive 多様性の確保

**FACT** (F3): 14 個の F primitive と 6 個の M primitive のうち、 (F6=SessionMomentum、 F8=BollingerRevert、 M2=SessionGate) の **3 個に GA が完全 collapse**。 残り 17 primitive は使用率<5%。 P (pair-specific) は 5 個程度が使用されているが siginal-shaping の核は 3 個に集中。

**論点**: 19 RUN 全てで同じ attractor に落ちる現象は GA の発散圧不足。 selection_score lex 順序で fitness_pen は最下位 → top-tier (feasible / stage_b_pass / fold_robust) で勝負がつく → 構造的に同一 lineage が elite slot を独占し新 primitive が拡散する余地が消える。

**設計選択肢**:
- (A) **NSGA-II / Pareto front maintenance**: fitness_pen vs fold_sign vs trade_count で多目的最適化、 単一スカラー lex 排除 (報告書も推奨)
- (B) **Niching / fitness sharing**: clauses 構造ハッシュで同一系統の selection_score にペナルティ
- (C) **mandatory primitive diversity in initial population**: 96 個の seed pop で 14 個の F primitive を均等に割り当て (各 ~7 個)
- (D) **mutation で primitive 種類変更のレート増加**: 現状 mutate は param/weight 主体、 種類置換は稀 → 種類置換確率を 10-30% に引き上げ

### 論点 4: Clone amplification の elite/tournament 暴走

**FACT** (F4): run-52 で gen 69 以降の 22 世代は best_fp 完全 stagnant、 同一系統 clone が 60 個体に増殖。 gens=90 の最後 22 世代は探索ゼロ。

**論点**: tournament_size=3 + elite_count=2 + 96 個 pop で、 一度 feasible 個体が出現すると全 elite 路線がそれに飲み込まれる構造。 cycle 7 baseline (gens=60) は早期 best_fp ATH を達成しているが、 cycle 17 で gens=90 にした効果は **22 世代の clone 増殖**だった可能性。

**仮説 H_F4**: clone を deduplicate (clauses-level ハッシュで同系統は selection_score にペナルティ) すると、 best_fp ATH は 0.310 のまま (探索品質は維持) だが gens=60 で十分な収束を得られる (時間効率向上)。

**設計選択肢**:
- (A) clauses ハッシュ重複で `effective_clone_count` を計算、 selection_score に `-clone_count` 要素を追加 (上位ほど clone は不利)
- (B) elite_count=2 → elite_count=1、 残 1 を **diversity-reserved slot** (= 各世代の中で primitive 種類が最も多様な個体を 1 つ無条件 elite)
- (C) plateau detection: best_fp が n 世代 stagnant なら mutation_rate を ramp up (`improve_cycle.plateau_mutation_bump=0.05` は既に存在するが GA 内では適用されていない)

### 論点 5: trade_count 参照系の scale-misalignment 修正

**FACT** (F7): archive `trade_count` は Stage A 60 日のみ。 live_criteria.trade_count_min=50 は実質的に annualized レート要求。 selection の `feasible` 判定は Stage A trade_count を使う一方、 mission 判定はデータセット全期間。

**論点**: スケール不整合により、 selection は「Stage A で trade>=50」 個体を優先するが、 これは **Stage A 60 日で年率 304 trades** に相当 (= 6.5 trade/day)。 一方 mission criteria は実質「1 trade/day 程度」 で十分なはず。 selection 圧が過剰に高頻度 trader 方向にかかっている可能性。

**設計選択肢**:
- (A) `trade_count_min` を Stage A 期間に応じて scale (60 日なら 50/180×60 ≈ 17)、 selection feasibility を 17 trades/60d に緩和
- (B) archive に `trade_count_full_dataset` (Stage A + Stage B trades 合算) を追加し、 selection はそちらを使用
- (C) 現行を維持しつつ、 mission criteria の trade_count_min を Stage A スケール (例: 50→17) に統一

### 論点 6: Stage C holdout の構造的不足の対処

**FACT** (F6): config holdout_days=60 だが actual=14 日。 19 RUN 全 Stage C pass=0。 Stage B pass の 128/136 は holdout で trade 不在。

**論点**: 現行 dataset (2025-10-01 〜 2026-04-01) では Stage C を意味のある形で評価できない。 残された方法は (1) dataset 期間延長、 (2) holdout window 縮小 + 適切な評価指標、 (3) cross-pair shadow を hard 化して replacement とする。

**設計選択肢**:
- (A) dataset.end を 2026-02-15 等に短縮、 holdout を 45 日確保
- (B) holdout_days を 14 (実態) に整合、 spread_stress 評価ロジックを「最低 trade_count 5」 等に再設計
- (C) Stage C 評価機構を Phase 4 として保留、 Phase 2 では Stage B pass を mission target とする (運用判断)
- (D) dataset 自体を延長 (新規 bars データ取得 — Phase 1 価格パイプライン拡張)

### 論点 7: median_oos_sharpe gate の noise-floor 整合性

**FACT** (F8): fold_trade_count_min=10 で per-fold trade-level Sharpe の SE ≈ 0.32。 10 fold median の SE ≈ 0.10。 median_oos_sharpe_min=0.05 は noise floor とほぼ同じ。 → true SR≥0.15 が安定通過に必要だが、 mission criteria sharpe_min=1.0 (annualized) は trade-level で~0.05-0.10 程度。

**論点**: gate の検出力 (statistical power) と mission criteria の整合性が取れていない。 「mission の sharpe_min=1.0 を満たす個体は median_oos_sharpe>=0.05 を必ず満たす」 という暗黙仮定が間違っている可能性。

**仮説 H_F8**: mission criteria sharpe_min=1.0 (annualized) を trade-level scale に変換すると 0.05〜0.10 程度。 現行 gate はその下限を要求しているため「ほぼ mission criteria 同等の厳格性」を gate で要求している (= ほぼ通らない)。 → **gate を mission の半分** に緩めるべき。

**設計選択肢**:
- (A) median_oos_sharpe_min を 0.025 に緩和 (mission の半分目処)
- (B) 「median + SE-aware lower bound (median - 1 SE)」 を gate にし、 SE 大きい個体は緩く、 小さい個体は厳しく
- (C) DSR (Deflated Sharpe Ratio) を有効化し、 median と組み合わせ

### 論点 8: selection_score の dead-code 重複削除

**FACT** (F5): `_selection_key` が `int(self.stage_b_pass)` を位置 4 と 7 の両方に置く。

**論点**: 機能的には no-op だが、 コードの維持性・デバッグ性に害。 cycle 4→5 の transition で v3.2 (9-tuple) の `stage_b_pass` 位置が残ったまま v3.3 (10-tuple) で再追加された refactor leftover の可能性。

**設計選択肢**:
- (A) 位置 7 の `int(self.stage_b_pass)` を削除、 9-tuple に整理 (schema_name は v3_4 に bump)
- (B) 位置 7 を別の意味のある要素に置換 (例: `int(stage_b_pass and self.fold_robust)` 等)
- (C) docstring に「duplicate intentional for backward compat」 と明記し維持

### 論点 9: gens=90 vs gens=60 の費用対効果

**FACT** (F4): run-52 で gen 69-90 (22 世代) は探索ゼロ、 elapsed 180 min のうち最後 ~45 min が無駄。 run-50 (gens=90) も同様の clone 飽和。

**論点**: gens=90 で best_fp ATH 0.310 を達成 (cycle 17) が、 これは **gens=60 でも到達可能**な可能性。 探索が止まる時点を plateau 検出で動的に終了する方が時間効率が良い。

**設計選択肢**:
- (A) plateau early-stopping: best_fp が N=15 世代 stagnant なら GA を打ち切る
- (B) plateau-triggered mutation_rate ramp-up (improve_cycle.plateau_mutation_bump 機能を GA 内 wire)
- (C) gens=60 固定 + multi-seed batch (3-5 seed × 60 gens) で同 wall-time でより diverse な探索

### 論点 10: 報告書の seed sensitivity 結論 H11 の再評価

**FACT** (F9): seed=23 max_pnl=48,640 (1,360 円不足!)、 seed=42=58,830、 seed=100=27,800。 全 seed で GA は (F6+F8+M2) に collapse。

**論点**: 報告書「H11 verified: GA は highly seed sensitive」 は **観察事実**としては正しいが、 **解釈**として「multi-seed batch が解」 は不十分。 真因は (F6+F8+M2) 領域内のパラメータ着地点ばらつき。 multi-seed batch は症状緩和 (3-5 seed で 1-2 件 graduate するだろう)、 root cause は GA 探索が primitive 多様性を維持できない構造。

**論点 (継続)**: seed=23 の max_pnl=48,640 は 50,000 まで残り 2.7%。 「探索を多少深めれば達成可能」 領域。 つまり multi-seed よりも、 **同 seed で longer plateau 探索 + primitive 多様性確保** の方が効率的かもしれない。

**設計選択肢**:
- (A) multi-seed batch (報告書推奨)
- (B) primitive diversity 強制 + plateau adaptive mutation (論点 3 + 4)
- (C) hybrid: 5 seed × gens=60 + 各 seed で primitive 多様性強制 + plateau early-stopping

---

## 統合推奨 (Claude による draft、 Codex 議論前)

最大効果領域は **論点 1 + 論点 7** (Stage B median_oos_sharpe_min 緩和) と **論点 3 + 論点 4** (mode collapse 対策)。

### 短期 (Phase 1, 1-2 cycle)
1. **Stage B 閾値緩和の検証**: median_oos_sharpe_min を 0.05 → 0.025 + run-52 archive replay → mission graduate 個体を特定
2. **selection_score dead-code 削除** (論点 8、 cosmetic だが design hygiene)

### 中期 (Phase 2, 3-5 cycle)
3. **DSR / SE-aware median gate** 導入 (論点 7B)
4. **Plateau early-stopping + adaptive mutation** (論点 4C, 9A)
5. **clone deduplication penalty** (論点 4A)

### 長期 (Phase 3, 5-10 cycle)
6. **NSGA-II 多目的最適化** (論点 3A、 報告書も推奨)
7. **mandatory primitive diversity in initial pop** (論点 3C)
8. **Stage C holdout の根本的再設計** (論点 6、 dataset 拡張または gate 再設計)

---

## Codex への質問

1. F1 (mission-eligible 7 個体存在) と現行 Stage B gate 設計のどちらが「真」 か。 Stage B gate を緩めると in-sample over-fitting が進むのか。
2. F3 (mode collapse) に対する最も effective な介入は何か。 NSGA-II vs niching vs mandatory diversity の比較。
3. F6 (Stage C 14日 holdout 不足) は短期的にどう mitigate すべきか。 dataset 延長か Stage C 設計変更か。
4. F8 (median_oos_sharpe noise floor) の DSR 導入は効果あるか。 trade-level v.s. annualized scale の整合性をどう取るべきか。
5. 推奨 Phase 1 (短期) の優先順序: median_oos_sharpe 緩和 vs DSR vs primitive diversity vs plateau early-stopping。
