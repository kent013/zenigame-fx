# RUN run_20260509_011256 (run-55) 分析 — Claude 自己分析

**Generated**: 2026-05-09 11:30 JST
**run_id**: `run_20260509_011256` (run-55)
**T091 全段階適用後 (smoke RUN)**: median 0.025 + trade_count_full_dataset + partition guard + 二重 opt-in

---

## 観察事実 (Facts)

### F1. Stage 通過数 (run-54 比較)

| Stage | run-55 | run-54 | 差分 |
|---|---:|---:|---:|
| A pass | **997** | 1,439 | **-442 (-31%)** |
| B pass | 0 | 0 | ±0 |
| C pass | 0 | 0 | ±0 |

→ T091 段階 2 selection 切替で GA dynamics 大幅変化 verified。

### F2. Best 個体

- name: g49_i86 (gen 49)、 fitness_pen=**0.2851** (archive max)
- trade_count (Stage A)=31、 trade_count_stage_b=20、 trade_count_full_dataset=**51**
- total_pnl=19,270、 **median_oos_sharpe=0.0**、 **n_fold_effective=0**、 pfre=NaN
- active_clause=2、 selection_score=[1, -0.0, 0, 0, 1, 0, 0, 1, 0, 0.2851]
- → **selection の feasibility=1 (full_dataset 51>=50)、 fold_robust=0 (fold 評価不能)**

### F3. Stage A pass の trade_count スケール変化 (T091 段階 2 effect)

| metric | Stage A | full_dataset | ratio |
|---|---:|---:|---:|
| median trade_count | 37 | 66 | 1.78x |
| feasibility (>=50) 判定 | 旧: false (37<50) | 新: true (66>=50) | 切替 |

→ 旧 selection では infeasible だった個体が新 selection で feasible に変化、 feasibility 母数が大幅増。

### F4. median_oos_sharpe 分布 (T091 段階 2 archive 新列、 Layer 1 検証データ)

- count: 997 (Stage A pass 全件で計算済)
- **max: 0.0000**
- >0: 0 件
- >=0.025 (T091): 0 件
- >=0.05 (旧): 0 件

→ **seed=100 領域では median_oos_sharpe が 0 を超える個体が一切存在しない**。 T091 段階 1 (median 0.025 緩和) の効果は seed=100 で **完全にゼロ**であることが verified。

### F5. primitive 使用率 (Stage A pass + trade>=50、 n=295)

F4=99% / F13=86% / M3=11% / F10=6% / P10=6% / F12=5% / F1=4% / F7=4%
→ run-53/54 の seed=100 collapse パターン (F4+F13+F11) と同一、 mode collapse 維持。

---

## 解釈・推論 (Interpretations)

### I1. T091 段階 2 effect verified、 段階 1 は seed=100 で構造的無効

**事実**: archive 新列が全 997 Stage A pass 個体で non-null 書き込み。 selection 切替で Stage A pass 数 -31%、 feasibility 母数大幅増。 しかし median max=0.0 で gate 通過個体ゼロ。

**解釈**:
- 段階 2 の selection 整合化は **GA dynamics に明確な効果あり** (Stage A 1439→997)
- 段階 1 (median 0.05→0.025) は **seed=100 領域で完全に無意味** (median max=0 < 0.025)
- 真の Layer 1 検証は **別 seed (seed=42)** で実施する必要がある

### I2. n_fold_effective=0 個体の上位化問題が再確認

**事実**: best 個体 g49_i86 は n_fold_eff=0 で fold 評価不能 (run-54 best と同パターン)。 selection_score lex で feasible=1 + fitness_pen が支配し、 fold_robust=0 でも上位化。

**解釈**: cycle 1/2 Codex consensus で確認済の「n_fold_effective=0 上位化ガード」 が依然として必要。 selection_score に評価可能性ペナルティ要素を追加すべき。

### I3. cycle 3 の方針: Layer 1 検証相当 RUN を seed=42 で実施

**事実**: T091 全段階 適用後の archive を seed=100 で取得済。 真の Layer 1 検証 (mission-eligible 個体に類する pfre>=0.6 個体が gate を通るか) は **別 seed が必須**。

**解釈**: cycle 3 を「seed=42 + T091 全段階適用 + 二重 opt-in smoke RUN」 で短縮実施。 これは:
- 設計・実装 skip (T091 は完了済)
- 即 RUN 開始可能
- 旧 run-52 (seed=42) との比較で T091 全段階 effect を直接検証可能

**反証可能性**: seed=42 RUN-56 で Stage B pass 数が run-52 (=136) と比較して大幅増加なら T091 effect verified。 同等以下なら別根因再調査。

---

## cycle 3 方針

**Layer 1 検証相当の seed=42 smoke RUN を実施**:
- 設計・実装 skip (T091 全段階完了済)
- run_args: `--seed 42 --generations 60 --allow-holdout-short` + env `ZENIGAME_FX_SMOKE_TEST=1`
- 期待効果:
  - run-52 (seed=42、 T091 適用前): Stage B pass=136、 mission-eligible=7
  - run-56 (seed=42、 T091 全段階適用): selection 切替で feasibility 母数変化、 Stage B pass の trade_count 中央値変化
  - **mission-eligible 個体が Stage B pass する**個体数を verify

## 全体判定

**OK** (T091 全段階適用 + GA dynamics 変化 verified、 残課題は別 seed 検証 or mode collapse 介入)
