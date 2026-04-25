# Run 10 — run_20260425_004002

**Generated**: 2026-04-25T00:40:13.448688+00:00
**Dataset**: EUR_JPY `2026-03-01T00:00:00+00:00` → `2026-03-15T00:00:00+00:00` (bars=14351)
  - bars_stage_a: 14351
  - bars_stage_b: 14351
  - bars_holdout: 37832

## 使命判定

未達

- ✅ **sharpe**: 18.491182265575507 / threshold 1.0
- ❌ **total_pnl**: 18860.0 / threshold 50000.0
- ✅ **max_drawdown_pct**: 0.0 / threshold 20.0
- ❌ **trade_count**: 3 (range 50〜5000)

## GA 設定

- population_size: 96
- generations: 60
- mutation_rate: 0.3
- crossover_rate: 0.7
- tournament_size: 3
- elite_count: 2
- max_depth: 4
- fitness_metric: sharpe
- seed: None

## Best 個体

- name: `g60_i21`
- generation: 60
- fitness: **18.480682265575506**
- fitness_finite: ✅
- stage_a_pass: ✅
- stage_b_pass: ❌
- stage_c_pass: ❌
- trade_count: 3
- total_pnl: 18860.0
- sharpe: 18.491182265575507
- sortino: —
- calmar: —
- max_drawdown_pct: 0.0

**Archive 補足情報**:
- lane_id: tier1_EUR_JPY
- instrument: EUR_JPY
- fold_sign_ratio: —
- dsr: —
- ii_lite_pass: —
- n_nodes: 2
- active_clause: 0

## Stage 通過数

- 全 archive 行数: 5856
- Stage A pass: 4291
- Stage B pass: 0
- Stage C pass: 0

## Lane 別落下分布

| lane_id | total | A | B | C |
|---------|-------|---|---|---|
| tier1_EUR_JPY | 5856 | 4291 | 0 | 0 |

## Pair 別落下分布

| instrument | total | A | B | C |
|------------|-------|---|---|---|
| EUR_JPY | 5856 | 4291 | 0 | 0 |

## active_clause / n_nodes 分布

- active_clause: n=5856, mean=0, median=0.0000, std=0.0000, min=0, max=0
- n_nodes: n=5856, mean=2.0441, median=2.0000, std=0.7019, min=1, max=4

## fold_sign_ratio / dsr 分布

- fold_sign_ratio: n=0
- dsr: n=0

## Cross-pair shadow 集計

- runtime mode: skipped_single_instrument
- ii_lite_pass: True=0, False=0, None=5856

## Graduation

- archive graduated: 0
- summary.graduation_count: 0

## Archive Top-5 個体一覧

> Best とは別物です。`fitness_pen` 単独降順。Best は (stage_c_pass, stage_b_pass, stage_a_pass, fitness_pen) の辞書式。

| rank | name | gen | lane | instrument | fitness_pen | fitness_raw | A | B | C | trade_count | sharpe |
|-----:|------|----:|------|------------|------------:|------------:|---|---|---|----:|-------:|
| 1 | `g60_i21` | 60 | tier1_EUR_JPY | EUR_JPY | 18.4807 | 18.4912 | ✅ | ❌ | ❌ | 3 | 18.4912 |
| 2 | `g20_i53` | 20 | tier1_EUR_JPY | EUR_JPY | 18.3150 | 18.3255 | ✅ | ❌ | ❌ | 3 | 18.3255 |
| 3 | `g21_i0` | 21 | tier1_EUR_JPY | EUR_JPY | 18.3150 | 18.3255 | ✅ | ❌ | ❌ | 3 | 18.3255 |
| 4 | `g21_i18` | 21 | tier1_EUR_JPY | EUR_JPY | 18.3150 | 18.3255 | ✅ | ❌ | ❌ | 3 | 18.3255 |
| 5 | `g21_i73` | 21 | tier1_EUR_JPY | EUR_JPY | 18.3150 | 18.3255 | ✅ | ❌ | ❌ | 3 | 18.3255 |

## 収束履歴

| gen | best_fitness |
|-----|--------------|
| 0 | 8.11512761939894 |
| 1 | 8.11512761939894 |
| 2 | 8.606361745254393 |
| 3 | 9.50625788686992 |
| 4 | 9.579339545307809 |
| 5 | 14.964480394504683 |
| 6 | 14.964480394504683 |
| 7 | 14.964480394504683 |
| 8 | 14.964480394504683 |
| 9 | 14.964480394504683 |
| 10 | 14.964480394504683 |
| 11 | 17.312947373630614 |
| 12 | 17.312947373630614 |
| 13 | 17.312947373630614 |
| 14 | 17.312947373630614 |
| 15 | 17.634316681209032 |
| 16 | 17.634316681209032 |
| 17 | 17.634316681209032 |
| 18 | 17.793569719508397 |
| 19 | 17.793569719508397 |
| 20 | 18.314965221298483 |
| 21 | 18.314965221298483 |
| 22 | 18.314965221298483 |
| 23 | 18.314965221298483 |
| 24 | 18.314965221298483 |
| 25 | 18.314965221298483 |
| 26 | 18.314965221298483 |
| 27 | 18.314965221298483 |
| 28 | 18.314965221298483 |
| 29 | 18.314965221298483 |
| 30 | 18.314965221298483 |
| 31 | 18.314965221298483 |
| 32 | 18.314965221298483 |
| 33 | 18.314965221298483 |
| 34 | 18.314965221298483 |
| 35 | 18.314965221298483 |
| 36 | 18.314965221298483 |
| 37 | 18.314965221298483 |
| 38 | 18.314965221298483 |
| 39 | 18.314965221298483 |
| 40 | 18.314965221298483 |
| 41 | 18.314965221298483 |
| 42 | 18.314965221298483 |
| 43 | 18.314965221298483 |
| 44 | 18.314965221298483 |
| 45 | 18.314965221298483 |
| 46 | 18.314965221298483 |
| 47 | 18.314965221298483 |
| 48 | 18.314965221298483 |
| 49 | 18.314965221298483 |
| 50 | 18.314965221298483 |
| 51 | 18.314965221298483 |
| 52 | 18.314965221298483 |
| 53 | 18.314965221298483 |
| 54 | 18.314965221298483 |
| 55 | 18.314965221298483 |
| 56 | 18.314965221298483 |
| 57 | 18.314965221298483 |
| 58 | 18.314965221298483 |
| 59 | 18.314965221298483 |
| 60 | 18.480682265575506 |

## 分析

### analysis-claude.md

# Run 9 分析

**run_id**: `run_20260425_002330`
**generated_at**: 2026-04-25T00:23:31.205910+00:00

## 観察事実

### 使命判定 (live_criteria)

- ❌ sharpe: None / 閾値 1.0
- ❌ total_pnl: 0.0 / 閾値 50000.0
- ✅ max_drawdown_pct: 0.0 / 閾値 20.0
- ❌ trade_count: 0 (許容 50〜5000)

### Best 個体

- name: `g0_i1`
- fitness (sharpe): 0
- trade_count: 0
- total_pnl: 0.0
- sharpe: None
- max_drawdown_pct: 0.0
- win_rate: None

### 収束状況

- 世代数: 6
- 初世代 best_fitness: 0
- 最終世代 best_fitness: 0
- Δfitness: 0
- plateau: True

### 前回 Run との比較

- best_fitness: 9.651541951434448 ↓ 0 (Δ=-9.651541951434448)
- trade_count: 1 → 0

## 解釈

- 未達: sharpe, total_pnl, trade_count。これらが次サイクルの改善ターゲット。
- plateau 検出: 最終 3 世代で best_fitness が変化なし。mutation_rate 増加 or 初期集団多様化を検討。
- 前回より後退。seed のばらつきの可能性もあるので、即座に閾値を弄らず複数 Run の傾向で判断する。

### analysis-codex.md

```markdown
# analysis-codex.md
# Run 9 Codex独立分析（run_20260425_002330）

## Facts（観察事実）

- 前提（C4）
- `n=120`（6世代 x 20個体）で、`n<30` ではない
- 対象データは `EUR_JPY` 単一銘柄（cross-pair は単独実行条件）
- 参照元は archive parquet と `reports/run-reports/run-9/summary.json`

- ステージ通過
- `stage_a_pass=0/120`
- `stage_b_pass=0/120`
- `stage_c_pass=0/120`
- `graduated=0/120`

- 収益・フィットネス
- `total_pnl` は全120個体で `0.0`（min=max=mean=0.0）
- `fitness_pen` は `max=0.0`, `mean=-8.9138`, `min=-93.1091`
- `fitness_pen=0.0` は 90個体、`fitness_pen<0` は 30個体

- 取引回数
- `trade_count=0` は 90個体（75%）
- `trade_count>0` は 30個体（25%）
- `trade_count<=10` は 94個体
- `trade_count_max=1331` だが、取引した個体の `sharpe` は全て負（min -93.10, max -4.76）

- 世代推移
- 世代平均 `trade_count`: `380.9 -> 100.6 -> 44.7 -> 14.2 -> 22.15 -> 82.1`
- 世代平均 `fitness_pen`: `-25.45 -> -8.39 -> -4.56 -> -3.37 -> -3.95 -> -7.76`
- `summary.ga_config.generations=5` だが実アーカイブは `generation 0..5` の6世代

- 禁止事項関連の観測
- イントラデイ逸脱の直接兆候なし（`time_stop_min` は 8〜189、`>1440` は 0）
- `live_criteria.trade_count_min=50` は維持（緩和の痕跡なし）
- `best` 個体は `trade_count=0` で選抜（`fitness=0`）

- primitive / 多様性
- 出現 primitive は 21種、directional slot 合計291
- 上位シェア: `P7(18.6%), F11(13.4%), P9(12.0%), P5(11.3%)`
- 組合せは初期20種から後半7〜10種へ縮退
- 最頻組合せ `('F11','P5','P7','P9')` が 26/120

- cross-pair shadow
- `cross_pair_config.mode=shadow`, `aggregator_lambda=0.5`
- 実行時は `cross_pair_runtime_mode="skipped_single_instrument"`
- archive列に cross-pair/shadow 実測列は見当たらない

## Interpretations（解釈・推論）

- 仮説1（Stage gateボトルネック）  
  `trade_count=0` 個体の `fitness_pen=0` が、取引する個体（負Sharpe）より相対優位になり、GAが「無取引」へ収束した可能性が高い。  
  反証可能性: `trade_count=0` に明示ペナルティを与えたA/B実験で、`stage_a_pass` と `trade_count` 分布が改善しなければこの仮説は棄却。

- 仮説2（評価一貫性の問題）  
  `trade_count>0` なのに全個体 `total_pnl=0.0` は、PnL集計経路の不整合（丸め/別系列参照/保存欠落）を示唆。  
  反証可能性: 同一個体の約定列・エクイティカーブから `total_pnl` を再計算し一致確認。一致するなら仮説棄却、不一致なら確定。

- 仮説3（禁止事項 #7 の構造的再発）  
  ルールを緩和していなくても、評価関数の形が「取引しないほど有利」を生み、実質的に取引回数削減を誘発している。  
  反証可能性: `trade_count` 下限制約（soft/hard）を入れても依然 `tc=0` 優勢なら、主因は別（シグナル死滅や執行条件）であり本仮説は弱まる。

- cross-pair shadow 妥当性  
  今回は single instrument で shadow がスキップされており、cross-pair 統計の有効性は判定不能（C8: INCONCLUSIVE）。  
  反証可能性: 複数ペア同時RUNで shadow 指標が実際に記録されることを確認する。

## 次サイクル候補

- Critical（1）
- **無取引優位の即時反証実験**  
  `tc=0` へのペナルティ付与 or `trade_count_min` を fitness 側に内生化し、同条件で短縮RUNを2本実施。成功基準は `stage_a_pass>0` かつ `tc=0` 比率の有意低下。

- Warning（2-3）
- **PnL集計監査**  
  `trade_count>0` 個体の `total_pnl=0` 固定の原因を特定（評価系の数値整合テストを追加）。
- **primitive縮退監視**  
  組合せ多様性の世代縮退を監視し、novelty圧または同型抑制の有無を検証。
- **cross-pair shadow の実装妥当性確認**  
  複数通貨ペアRUNで shadow が「実際に」評価へ反映されるかを検証（single instrument skip は仕様として妥当だが、現状は未検証）。

## 全体判定

**CRITICAL_DRIFT**
```

現在の実行環境が read-only のため、`{tmp_dir}/analysis-codex.md` への直接書き込みはできませんでした。上記内容をそのまま保存すれば要求フォーマットを満たします。

### analysis-merged.md

# マージ分析: Run 9 (run_20260425_002330)

## 合意事項（両者一致）

- best_fitness=0、trade_count=0 個体が支配的（90/120 = 75%）
- Stage A/B/C/graduation すべて 0 件（パイプラインが ステージ A で全滅）
- 取引が発生した個体の sharpe は全て負（max -4.76、min -93.10）
- live_criteria はすべて未達（sharpe / total_pnl / trade_count）
- 直前 Run 8 の best_fitness=9.65 から急落、構造的劣化のサイン

## Claude 独自の発見

- 前回比較で best_fitness が 9.65 → 0、trade_count 1 → 0 と総崩れ
- 同一データ・同一構成（pop=20 gen=5）で大きく振れたという観測
- 解釈は浅く、改善方向の列挙までは未実施

## Codex 独自の発見

- **構造的問題: 「無取引が相対優位」**: trade_count=0 → fitness_pen=0 で、取引した負 Sharpe 個体（fitness_pen<0）より上位に評価される設計欠陥
- 世代推移: trade_count 平均 380→100→44→14→22→82（U字、世代3-4で収縮）
- primitive 偏在: P7/F11/P9/P5 で組合せが少数化、最頻組合せ ('F11','P5','P7','P9') が 26/120 = 22%
- 取引した個体は total_pnl=0 で固定（PnL 集計経路の整合性疑義）
- cross_pair_runtime_mode="skipped_single_instrument" で shadow 統計は INCONCLUSIVE

## 矛盾・要議論

なし（Codex の解釈の方が深い、Claude 解釈は表層的なため吸収）

## 統合改善提案（優先度順）

| # | 提案 | 優先度 | 出所 | target_metric | failure_mode | 期待効果 |
|---|------|--------|------|--------------|-------------|---------|
| 1 | **無取引ペナルティの構造的導入** | Critical | Codex 仮説1 | trade_count、Stage A pass | 取引数 0 が相対優位で GA が「沈黙」へ収束 | trade_count 分布の右シフト、Stage A pass>0 |
| 2 | **PnL 集計経路の数値整合性監査** | Warning | Codex 仮説2 | total_pnl | trade_count>0 でも total_pnl=0 が 100% | PnL の正しい伝搬、live_criteria 評価の信頼性 |
| 3 | **primitive 多様性の世代追跡** | Warning | Codex Facts | (diagnostic) | 組合せ縮退で探索空間が壊滅 | novelty 圧 or 同型抑制で多様性維持 |
| 4 | **cross-pair shadow の実測検証** | Warning | Codex 仮説（C8）| (diagnostic) | shadow が単独 RUN で skip され検証不能 | 複数ペア RUN で shadow が動くか確認 |

## 補足: 直近サイクルのコンテキスト

- Run 4-9 はストレステストの 6 サイクル（pop=20×gen=5×14日窓）
- Run 4 best=2.52 → Run 7 best=10.15 → Run 9 best=0 で振れ幅大
- Run 9 は cycle 6 中で停止指示があり archive Parquet が中途完了の可能性
- 今 cycle は pop=96×gen=60 への大幅スケールアップなので、評価コストは ~30倍。
  仮説1（無取引ペナルティ）の検証は本 cycle で最優先で取り組む価値がある。

