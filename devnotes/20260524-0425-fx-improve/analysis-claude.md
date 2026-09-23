# 分析 (cycle 15): R96 別seed再現の確定 + 次の pnl 引き上げ幅の根拠データ

## 前提
cycle14 = R96 (run_20260523_122605) = North Star 閾値引き上げ (sharpe1.5/pnl70k/dd20/trade50-5000) の**別seed再現**。R95 (run_20260523_041132) は別seedの初回成功 (378個体)。

## 観察事実（Facts）

### ★ R95/R96 は独立seed (gen0 個体重複 1/191 で実証)
- R96 launch args/state は `--seed 68`。R95 は別seed。**両run gen0 (warmstart9 + random87) の genome_json 重複は 1/191 (ほぼゼロ)** = 独立 RNG ストリームで進化したことを実証 (同seedなら gen0 bit-identical のはず)。warmstart archive・config・pop96/gen60 は完全同一。68/69 のラベルは些細な表記差で、本質 (独立seedで両方達成) は成立。

### ★ 再現性確認 (Codex 条件5) 完全達成
| seed run | StageC pass | mission_candidate(新基準) | best ann_sharpe | best pnl | best dd | best trade |
|----------|-------------|---------------------------|-----------------|----------|---------|------------|
| R95 | 378 | 378 (全StageC) | — | max95470 | — | — |
| R96 | 209 | 209 (全StageC) | 5.359 | 80520 | 1.79% | 51 |

- 両seed共に StageC pass 個体は**全て**新基準 (sharpe1.5∧pnl70k∧dd20∧trade50-5000) を満たす (mission_candidate = StageC count)。
- Codex 5条件: (1)config正✓ (2)StageC>0✓ (3)mission_candidate≥10✓ (両seed) (5)再現性✓。条件4 (Stage B trade≥100再出現) のみ未達=補助指標 (mission必須でない、AGENTS.md KPI分離)。**4/5達成、mission本体は両seed再現で完全達成**。
- cross-pair: ii_lite_pass=0 継続 (shadow観測)。cross_pair_mean_sharpe max 0.168 (>閾値0.15) だが min_sharpe/pair_failure 条件未達。shadow継続。

### ★ 次の pnl 引き上げ幅 sweep (両seed、他基準は全StageCがpass済)
| total_pnl_min | R95 pass数 | R96 pass数 | 判定 |
|---------------|-----------|-----------|------|
| 70000 (現) | 378 | 209 | 現状 |
| 72000 | 175 | 14 | 両≥10 ✓ |
| 74000 | 57 | **12** | 両≥10 ✓ (R96 ギリ) |
| 75000 | 52 | 8 | R96<10 ✗ |
| 76000 | 45 | 5 | R96<10 |
| 78000 | 30 | 1 | R96≈0 |
| 80000 | 18 | 1 | R96≈0 |
| 82000 | 12 | **0** | R96=0 再現崩壊 ✗ |
| 90000 | 2 | **0** | R96=0 再現崩壊 ✗ |

## 解釈・推論（Interpretations）

### 1. ★ ループ prompt の「90k 引き上げ」は弱seed (R96) で再現崩壊 → 棄却
R95 max95470 のみ見ると 90k に余地があるが、**R96 max は80520**。90k は R96 で mission_candidate=0 → 「別seedでも>0」(Codex条件5) を破壊。82k 以上で R96=0。**引き上げ幅は両seedの弱い方 (R96) で律速**。弱seed max80520 を超える閾値は再現性を壊すため不可。

### 2. ★ 両seedで実用水準 (≥10) を保つ上限 = 74000
- 74000: R95=57 / R96=12 → 両seed ≥10 (Codex条件3 維持)。R96 が 12 でギリギリ。
- 75000: R96=8 (<10) → 条件3 を弱seedで割る。
- 72000: R95=175 / R96=14 → より安全マージン (将来の第3seedに対する頑健性)。
- hard要件 (両seed>0) のみなら 80000 まで可 (R96=1) だが、n=1 は lucky-1個体依存で頑健でない。

### 3. 引き上げ方向の正当性
total_pnl_min↑ は品質直結・緩和でなく引き上げ・robustness強化 (取引数操作でない、期間延長でない、overnight保有でない)。default挙動 (feature opt-in) は不変。メタ過学習回避: 閾値を弱seed律速で決めることで、強seed (R95) への過適合を避ける。

## 次サイクル候補
- **[Critical] total_pnl_min 70000→74000 引き上げ** (両seed ≥10維持の上限)。より保守的なら 72000 (R96=14、第3seed頑健性)。Codex合議で 72k vs 74k を確定 (弱seed律速・条件3維持の原則)。
- **[Warning] cross-pair shadow観測継続**、Stage B trade≥100 (条件4補助) は別途調査余地。

## 全体判定
**★North Star 閾値引き上げ完全達成・両seed再現確定 (cycle14)**。次の引き上げは**弱seed (R96 max80520) 律速**で、両seed実用水準 (≥10) を保つ上限は total_pnl_min=74000 (R95 57/R96 12)。prompt示唆の90kは弱seedで再現崩壊するため棄却。Codex合議で 72000 vs 74000 を確定 (緩和禁止・引き上げのみ・弱seed律速)。
