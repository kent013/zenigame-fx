# Run 35 — run_20260506_030253

**Generated**: 2026-05-06T03:03:05.358993+00:00
**dataset_epoch_id**: `epoch_20251001_20260401`
**Dataset**: EUR_JPY `2025-10-01T00:00:00+00:00` → `2026-04-01T00:00:00+00:00` (bars=183403)
  - bars_stage_a: 86400
  - bars_stage_b: 97003
  - bars_holdout: 20457
  - Stage B excludes Stage A window (stage_b: 2025-10-01T00:00:00+00:00 → 2026-01-06T18:25:00+00:00, stage_a: 2026-01-06T18:26:00+00:00 → 2026-03-31T23:59:00+00:00)

## 使命判定

未達

- ❌ **sharpe**: 0.2417390315293707 / threshold 1.0
- ❌ **total_pnl**: 28590.0 / threshold 50000.0
- ✅ **max_drawdown_pct**: 0.0 / threshold 20.0
- ✅ **trade_count**: 53 (range 50〜5000)

## GA 設定

- population_size: 96
- generations: 60
- mutation_rate: 0.5
- crossover_rate: 0.7
- tournament_size: 3
- elite_count: 2
- max_depth: 4
- fitness_metric: sharpe
- seed: 23

## Best 個体

- name: `g56_i28`
- generation: 56
- fitness: **0.22223903152937072**
- fitness_finite: ✅
- stage_a_pass: ✅
- stage_b_pass: ❌
- stage_c_pass: ❌
- trade_count: 53
- total_pnl: 28590.0
- sharpe: 0.2417390315293707
- sortino: —
- calmar: —
- max_drawdown_pct: 0.0

**Archive 補足情報**:
- lane_id: tier1_EUR_JPY
- instrument: EUR_JPY
- fold_sign_ratio: 0.2000
- dsr: —
- ii_lite_pass: —
- n_nodes: 4
- active_clause: 1

## Stage 通過数

- 全 archive 行数: 5856
- Stage A pass: 1999
- Stage B pass: 0
- Stage C pass: 0

## Lane 別落下分布

| lane_id | total | A | B | C |
|---------|-------|---|---|---|
| tier1_EUR_JPY | 5856 | 1999 | 0 | 0 |

## Pair 別落下分布

| instrument | total | A | B | C |
|------------|-------|---|---|---|
| EUR_JPY | 5856 | 1999 | 0 | 0 |

## active_clause / n_nodes 分布

- active_clause: n=5856, mean=1.2939, median=1.0000, std=0.4645, min=0, max=2
- n_nodes: n=5856, mean=3.8945, median=4.0000, std=1.7550, min=1, max=8

## mission_score 分布 (T043 / observation only)

> live_criteria 4 軸 (sharpe/total_pnl/max_drawdown/trade_count) の soft 合算スコア (幾何平均、[0.1, 1.0])。GA fitness や stage_c.passed には 影響しない (詳細: docs/alpha_factory/mission-score.md)。

- mission_score=計測対象 0 件 (Stage C base 評価で Sharpe を出した 個体が無いため未計測)

## fold_sign_ratio / dsr 分布

- fold_sign_ratio: n=1999, mean=0.2164, median=0.2000, std=0.1269, min=0.0000, max=0.7000
- dsr: n=0
- n_fold_effective (Stage A pass): n=1999, mean=8.5128, median=9, std=3.1599, min=0, max=11
- positive_fold_ratio_effective (Stage A pass): n=1900, mean=0.1808, median=0.1818, std=0.1316, min=0.0000, max=1.0000

## Stage B failure reason 集計

- Stage A pass = 1999, Stage B pass = 0, failures = 1999 (primary_sum = 1999)

### Primary reason (先頭 reason、合計 = failures)

| reason | count |
|--------|------:|
| `no_folds` | 0 |
| `insufficient_folds` | 0 |
| `all_folds_unavailable` | 0 |
| `stage_b_window_underfilled` | 0 |
| `median_oos_sharpe<min` | 1999 |
| `positive_fold_ratio<min` | 0 |
| `stage_b_pre_flight_underfilled` | 0 |
| `unknown_reason` | 0 |
| `other` | 0 |

### Any reason incidence (全 reason、合計 >= failures)

| reason | count |
|--------|------:|
| `no_folds` | 0 |
| `insufficient_folds` | 0 |
| `all_folds_unavailable` | 99 |
| `stage_b_window_underfilled` | 0 |
| `median_oos_sharpe<min` | 1999 |
| `positive_fold_ratio<min` | 1999 |
| `stage_b_pre_flight_underfilled` | 0 |
| `other` | 0 |

## Cross-pair shadow 集計

- runtime mode: skipped_single_instrument
- ii_lite_pass: True=0, False=0, None=5856

## Graduation

- archive graduated: 0
- summary.graduation_count: 0

## Feasibility 集計

- selection_score schema: `v3_1_stage_b_priority`
- trade_count=0 個体比率: 4.9% (285/5856)
- best 個体 trade_count: 53
- best 個体 feasibility: ✅

## Stage A provenance 分布 (T033 / sidecar)

> Stage A 落ち個体の `total_pnl_stage_a` 分布を可視化 (`reports/run-reports/run-{N}/diagnostics/stage_a_provenance.parquet`)。archive `total_pnl=0.0` が「Stage A 落ち = 投影仕様」「実 PnL=0」「コスト過大」のいずれかを切り分けるための観測指標 (詳細: docs/alpha_factory/diagnostics-sidecar.md)。

- sidecar 行数: 5856
- metric_stage 分布: stage_a_evaluated=1999, stage_a_only=3857
- (1) Stage A 落ち全体 `total_pnl_stage_a` 分布: n=3857, mean=-415780.6948, median=-121740.0000, std=458997.3253, min=-1006190.0000, max=20760.0000
- (2) Stage A 落ち かつ trade_count>0 の `total_pnl_stage_a` 分布 (n=3572): n=3572, mean=-448954.6865, median=-154150.0000, std=461079.5853, min=-1006190.0000, max=20760.0000
  - うち PnL=0 個体: 0 件 (取引したのに PnL=0 = Run 9 監査の対象観測)
- (3) Stage A 通過個体 `total_pnl_stage_a` 分布 (n=1999): n=1999, mean=13153.7519, median=19160.0000, std=85900.9314, min=-1000940.0000, max=42970.0000

## Archive Top-5 個体一覧

> Best とは別物です。`fitness_pen` 単独降順。Best は (feasible, -violation, stage_b_pass, stage_c_feasible, stage_c_pass, stage_b_pass, stage_a_pass, fitness_pen) の辞書式 (v3.1_stage_b_priority, T046)。

| rank | name | gen | lane | instrument | fitness_pen | fitness_raw | A | B | C | trade_count | sharpe |
|-----:|------|----:|------|------------|------------:|------------:|---|---|---|----:|-------:|
| 1 | `g26_i95` | 26 | tier1_EUR_JPY | EUR_JPY | 0.2699 | 0.2894 | ✅ | ❌ | ❌ | 44 | — |
| 2 | `g39_i74` | 39 | tier1_EUR_JPY | EUR_JPY | 0.2338 | 0.2533 | ✅ | ❌ | ❌ | 48 | — |
| 3 | `g32_i47` | 32 | tier1_EUR_JPY | EUR_JPY | 0.2246 | 0.2591 | ✅ | ❌ | ❌ | 44 | — |
| 4 | `g56_i28` | 56 | tier1_EUR_JPY | EUR_JPY | 0.2222 | 0.2417 | ✅ | ❌ | ❌ | 53 | — |
| 5 | `g57_i0` | 57 | tier1_EUR_JPY | EUR_JPY | 0.2222 | 0.2417 | ✅ | ❌ | ❌ | 53 | — |

## 収束履歴

| gen | best_fitness |
|-----|--------------|
| 0 | -0.036511484633228654 |
| 1 | -0.0319411810750956 |
| 2 | -0.0319411810750956 |
| 3 | 0.008183593274836639 |
| 4 | 0.008183593274836639 |
| 5 | 0.0267055293483965 |
| 6 | 0.149714460202822 |
| 7 | 0.03140854028223269 |
| 8 | 0.03140854028223269 |
| 9 | 0.03140854028223269 |
| 10 | 0.03140854028223269 |
| 11 | 0.0432778368111328 |
| 12 | 0.05010482931060396 |
| 13 | 0.05445714307913524 |
| 14 | 0.05445714307913524 |
| 15 | 0.12673834278431068 |
| 16 | 0.08409148460103993 |
| 17 | 0.06981602717127808 |
| 18 | 0.09782775776566816 |
| 19 | 0.075437860456114 |
| 20 | 0.075437860456114 |
| 21 | 0.095928501821253 |
| 22 | 0.09720715568596278 |
| 23 | 0.1710709746092857 |
| 24 | 0.1746897686884248 |
| 25 | 0.1746897686884248 |
| 26 | 0.2699400194568124 |
| 27 | 0.1746897686884248 |
| 28 | 0.1746897686884248 |
| 29 | 0.17566007632298067 |
| 30 | 0.17566007632298067 |
| 31 | 0.19886586134947973 |
| 32 | 0.2246256255637327 |
| 33 | 0.21084401307700307 |
| 34 | 0.21084401307700307 |
| 35 | 0.21084401307700307 |
| 36 | 0.21084401307700307 |
| 37 | 0.21084401307700307 |
| 38 | 0.21084401307700307 |
| 39 | 0.2338411742544719 |
| 40 | 0.21084401307700307 |
| 41 | 0.22147686997826332 |
| 42 | 0.21084401307700307 |
| 43 | 0.21084401307700307 |
| 44 | 0.21084401307700307 |
| 45 | 0.21084401307700307 |
| 46 | 0.21084401307700307 |
| 47 | 0.21084401307700307 |
| 48 | 0.21084401307700307 |
| 49 | 0.2117150834955932 |
| 50 | 0.2117150834955932 |
| 51 | 0.2131167121616712 |
| 52 | 0.2131167121616712 |
| 53 | 0.2131167121616712 |
| 54 | 0.2131167121616712 |
| 55 | 0.2131167121616712 |
| 56 | 0.22223903152937072 |
| 57 | 0.22223903152937072 |
| 58 | 0.22223903152937072 |
| 59 | 0.22223903152937072 |
| 60 | 0.22223903152937072 |

## 分析

### analysis-claude.md

# RUN run_20260505_043320 (run-34 新, cycle 1 後の RUN) 分析（Claude 自己分析）

cycle 2/10。 cycle 1 で `collect_stage_a` の `total_pnl` 伝搬 bug を修正。 同設定 (population=96, gen=60, mut=0.5, seed=23, EUR_JPY) で再 RUN し、 archive の真値を観測できるようになった上での 2 周目分析。

## 前提差分

なし。

- archive Parquet: `.cache/alpha_factory/runs/genomes_run_20260505_043320.parquet` 存在 (1.09 MB, 5856 rows)
- summary.json: `reports/run-reports/run-34/summary.json` 存在 (run_id 一致)
- **T087 partition 契約は新 schema で完全整合** (cycle 1 C1 持ち越し問題は解消済)

## 観察事実（Facts）

### dataset / partition (T087 検証)

| 区間 | bars | timestamp range |
|---|---|---|
| 全 dataset | 183403 (= 86400+97003) | 2025-10-01 ~ 2026-04-01 |
| Stage A | 86400 (~60 日) | 2026-01-06T18:26 ~ 2026-03-31T23:59 |
| Stage B | 97003 (~67 日) | 2025-10-01 ~ 2026-01-06T18:25 |
| holdout | 20457 (~21 日) | 2026-04-01 ~ 2026-04-21T07:25 |

- **`bars_stage_b_excludes_stage_a: true`** が summary に明示
- A + B = 全 bars 検算 ✓
- partition_guard log `passed` (cycle 1 RUN 時に確認済)
- holdout は `holdout_days=60` 設定だが DB データが 2026-04-21 までで bars=20457 (~21 日)

→ **T087 partition は実装通り disjoint**。 cycle 1 で Codex が指摘した「stage_b=全期間」は **旧 schema の表示** (cycle 0 で観測した R34 旧 = run_20260504_132300 は schema 古い経路) で、 新 schema では解消済。

### Stage 通過数 (cycle 1 fix 後)

| Stage | Pass 件数 | 全体比 | 旧 R34 比較 |
|---|---|---|---|
| Stage A | 2929 / 5856 | 50.0% | 52.9% (微減) |
| Stage B | 22 / 5856 | 0.4% | 26 件 (微減) |
| Stage C | 0 / 5856 | 0.0% | 0% (不変) |
| graduated | 0 | 0% | 0 (不変) |

best 選定 (`v3_1_stage_b_priority`): g48_i70, fitness_pen=0.171, total_pnl=**40140**, trade_count=54, sharpe=0.189

### **Stage B pass 群の構造 (cycle 1 fix で初めて明らかになった重要事実)**

| 指標 | Stage A pass (n=2929) | Stage B pass (n=22) |
|---|---|---|
| total_pnl mean | **+17,013** | **-14,303** |
| total_pnl median | 16,280 | -12,750 |
| trade_count mean | 65.5 | 16.5 |
| trade_count median | 61 | 16 |
| trade_sharpe_raw mean | 0.0793 | 0.0230 |
| n_fold_effective | n/a | 2.0 (最低基準) |
| fold_sign_ratio | 0.178 (集団) | 0.000 |
| positive_fold_ratio | n/a | 1.000 |
| n_nodes mean | 3.46 | 3.41 |

→ **Stage B 通過個体は集団全体 (Stage A 通過群) より「悪い」**。 平均 PnL は negative、 trade_count は 4 分の 1 に減少。 「Stage B pass = 良い品質個体」という前提が崩壊。

### Stage B fail reason codes (5856 - 22 = 5834 fail)

| reason code | 件数 | 旧 R34 比較 |
|---|---|---|
| `median_oos_sharpe<min;positive_fold_ratio<min;all_folds_unavailable` | **2248** | 216 (10x 増) |
| `median_oos_sharpe<min;positive_fold_ratio<min` | 414 | 2823 (大幅減) |
| `positive_fold_ratio<min` | 243 | 29 |
| `median_oos_sharpe<min` | 2 | 2 |

**最大の変化**: `all_folds_unavailable` が 216 → 2248 に **10 倍増**。 fold 評価そのものが機能していない個体が大量発生。

### per_generation null 状況 (W3 持ち越し問題)

| key | null 率 |
|---|---|
| best_fitness_pen | 0/61 (記録 OK) |
| best_fitness_raw | **61/61 (全 null)** |
| median_fitness_pen | **61/61 (全 null)** |
| stage_a_pass_count | **61/61 (全 null)** |
| stage_b_pass_count | **61/61 (全 null)** |
| stage_c_pass_count | **61/61 (全 null)** |
| population_diversity | **61/61 (全 null)** |

cycle 1 C2 fix では per_generation 経路には触れていないので、 W3 (持ち越し) は依然として broken。

### Top-5 fitness_pen (Stage A only)

```
g48_i70 gen48 fitness_pen=0.1710 total_pnl=40140 trade_count=54
g49_i0  gen49 fitness_pen=0.1710 total_pnl=40140 trade_count=54
g49_i53 gen49 fitness_pen=0.1710 total_pnl=40140 trade_count=54
g50_i0  gen50 fitness_pen=0.1710 total_pnl=40140 trade_count=54
g50_i1  gen50 fitness_pen=0.1710 total_pnl=40140 trade_count=54
```

→ gen 48 で best 出現後、 gen 49-50 で同個体が複製され続ける (mut=0.5 でも elite 経由)。 探索停滞。

### live_criteria 達成

| 指標 | 閾値 | best (g48_i70) | 達成率 |
|---|---|---|---|
| sharpe_min | ≥1.0 | 0.189 | 19% (未達) |
| total_pnl_min | ≥50,000 | 40,140 | 80% (未達、 真値) |
| max_drawdown_max | ≤0.2 | 0.0 | trivial 達成 (drawdown=0) |
| trade_count_min | ≥50 | 54 | 達成 ✓ |
| trade_count_max | ≤5,000 | 54 | 達成 ✓ |

**live_pass=False**。 Sharpe が圧倒的に未達 (≥1.0 に対し 0.189)。

## 解釈・推論（Interpretations）

### 仮説 H_c2_1: **Stage B 評価層が小サンプル偽陽性を pass させている**

**根拠**: Stage B pass 群 (n=22) で:
- n_fold_effective=2 (`wf_min_folds_required=2` 最低基準ぎりぎり)
- trade_count median=16 (Stage A の 65 → 4 分の 1 に急減)
- fold_sign_ratio=0.000 (fold 値が 0 = trade なし fold が多い)
- positive_fold_ratio=1.000 (2 fold 中 2 fold が positive、 偶然による偽陽性可能性高)
- total_pnl mean=-14,303 (集団全体より悪い)

つまり「fold が成立した稀な 2 fold で偶然 positive、 OOS Sharpe が min を超えた」だけの個体が pass している。 selection_score_schema=`v3_1_stage_b_priority` が **これら偽陽性を best 選定で優先している恐れ** (本 RUN では best=g48_i70 は Stage B fail なので、 Stage A の中で最大 fitness が選ばれた、 これは healthy)。

**反証可能性**:
- `wf_min_folds_required` を 2 → 4 (or 5) に引き上げた RUN で Stage B pass 数がさらに減るが total_pnl mean が改善 (positive 化) すれば仮説 verify
- 改善なしなら Stage B 設計全体に問題

**反証 (棄却条件)**: 
- `wf_min_folds_required` 引き上げ後、 Stage B pass 群の total_pnl mean が依然 negative なら仮説棄却 (Stage B 設計より深い問題)

### 仮説 H_c2_2: **Stage B `all_folds_unavailable` 多発 (2248 件、 全体の 38%) は trade 生成稀少が主因**

**根拠**: 旧 R34 (cycle 1 の前) では 216 件、 新 R34 (cycle 1 後の同設定 RUN) では 2248 件。 同設定 deterministic re-run なので **本来同じ値**になるはずだが大幅に変化。 これは:
- (a) cycle 1 fix 後に集計経路が変わった (`stage_b_reason_codes` の集計対象が変わった可能性)
- (b) seed=23 deterministic 再現が崩れた (config 差分?)
- (c) 計算経路に副作用 (cycle 1 fix が間接的に Stage B 評価へ波及)

**反証可能性**:
- (a) なら過去 archive (cycle 1 修正前) の reason codes 集計を verify
- (b) なら ga_config の差分を確認
- (c) なら collect_stage_a 修正で Stage B 経路に何が変わったかを実装で確認

→ これは **cycle 1 fix の予期せぬ副作用** の疑いがある。 cycle 2 で先に検証が必要。

### 仮説 H_c2_3: **selection_score_schema v3_1_stage_b_priority + Stage B 偽陽性は組み合わせ問題**

**根拠**: Stage B 偽陽性 (H_c2_1) が放置されると、 future RUN で Stage B pass 数が増えると best 選定が「小サンプル偽陽性」に向かう恐れ。 cycle 1 では Stage B pass 数 22 で best=g48_i70 (Stage A pass のみ) が選ばれた、 これは selection_score の Stage A pass (= 1) が Stage B pass=False の Stage B pass=True 偽陽性個体より上位にきている = 偶然または schema 設計が適切。

**反証可能性**:
- Stage B 偽陽性 22 件の selection_score を実測して g48_i70 (Stage A only) と比較
- 偽陽性が上位にくるなら schema 設計問題

### 禁止事項違反の兆候 (C4 検知)

| # | 禁止事項 | 兆候 | コメント |
|---|---|---|---|
| 1 | 評価期間延長 | なし | 不変 |
| 2 | 見た目数値改善 | **疑い** | best fitness=0.171 は cycle 0 の 0.227 から低下、 ただし cycle 0 は計測 bug 故の見かけ高値、 0.171 が真値 |
| 3 | GA ハック | なし | seed/mut 変更なし |
| 4 | 閾値緩和でステージ飛ばし | なし | threshold 不変 |
| 5 | 複雑案 | なし | clause/depth 不変 |
| 6 | 取引回数削減で見かけ改善 | **疑い** | Stage B pass 群で trade_count が 16 (mean) と Stage A 65 から大幅減。 これは「取引数を減らして fold が成立した個体が pass」の構造、 つまり Stage B 評価が間接的に「取引回数削減個体」を選好している |
| 7 | オーバーナイト保有前提 | 未測定 | trade-level 詳細未集計 |

→ 6. の **「Stage B が取引回数削減個体を間接選好」** は禁止事項に抵触する構造的問題。 H_c2_1 と整合。

## 次サイクル候補

cycle 2 で plan-and-design に渡す候補 (新発見ベース):

1. **[Critical] H_c2_2 検証: cycle 1 fix の副作用調査** — `all_folds_unavailable` が 216→2248 に 10 倍増した理由を切り分ける。 (a) 集計経路変更 / (b) deterministic 崩れ / (c) cycle 1 fix の波及。 これが原因不明のままだと cycle 3 以降の比較性が崩れる
2. **[Critical] H_c2_1 検証: Stage B 偽陽性 (`wf_min_folds_required` 引き上げ実験)** — 2 → 4 (or 5) に引き上げ、 Stage B pass 群の total_pnl mean が positive 化するか観察。 「Stage B pass 数の量」 ではなく「品質」 を評価軸に
3. **[Warning] selection_score_schema 適切性検証** — Stage B 偽陽性個体と Stage A 単独 pass 個体の selection_score を比較、 偽陽性が上位に来ない設計か確認
4. **[Warning] W3 (持ち越し): per_generation observability schema 拡張** — 7/8 key が全 null。 計測経路追加 / schema 修正
5. **[Suggestion] holdout 期間が 21 日 (60 日設定と乖離)** — DB データが 2026-04-21 までで hold が 60 日に届かない。 cycle 2 でも対応不要、 docs 明記のみ

**全体判定 (preliminary)**: **CONCERN** — H_c2_2 (cycle 1 fix 副作用疑い) は構造的 risk。 H_c2_1 (Stage B 偽陽性) は禁止事項 6 の構造抵触。 cycle 2 では H_c2_2 を先に検証してから H_c2_1 に進むのが妥当。

### analysis-codex.md

# RUN run_20260505_043320 分析（Codex 独立分析）

## 前提差分（C4）
- 前提A（「旧R34と新R34は同条件比較」）は **棄却**。  
  旧R34（`run_20260504_132300`）の `summary.json` では `bars_stage_b=183403`、新R34（`run_20260505_043320`）は `bars_stage_b=97003` かつ `bars_stage_b_excludes_stage_a=true`。  
  つまり Stage B 評価対象期間が異なるため、`all_folds_unavailable` の単純比較は collider（条件集合不一致）になりうる。
- 検証元: [旧 summary (git show a31a22a)](/Users/ishitoya/repository/zenigame-fx/reports/run-reports/run-34/summary.json), [新 summary](/Users/ishitoya/repository/zenigame-fx/reports/run-reports/run-34/summary.json), [archive collect 実装](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/archive.py), [selection 実装](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py)

## 観察事実（Facts、 C6 分離遵守）
- 新R34の Stage B fail 主因コンボは `median_oos_sharpe<min;positive_fold_ratio<min;all_folds_unavailable` が 2248 件。
- 旧R34では同コンボ 216 件。  
- ただし旧R34は Stage B が 183403 bars（実質 A+B）、新R34は 97003 bars（Bのみ）。
- `n_fold_effective` 分布:
  - 新R34 Stage A pass群: `{0:2248, 1:623, 2:58}`（max=2）
  - 旧R34 Stage A pass群: `{0:216, 1:370, 2:533, 3:1185, ... ,9:26}`（max=9）
- Stage B pass群（新R34, n=22）は `total_pnl mean=-14,303`, `trade_count mean=16.5`, `trade_sharpe_raw mean=0.023`, `n_fold_effective mean=2.0`。
- Stage A pass群（新R34, n=2929）は `total_pnl mean=+17,013`, `trade_count mean=65.5`, `trade_sharpe_raw mean=0.0793`。
- cycle1修正 (`collect_stage_a` の `total_pnl` 伝搬) により、`stage_c_feasible` 判定材料（`pnl>0 && sharpe>0`）が実質変化しうる設計（selection tupleに含まれる）。

## 解釈・推論（Interpretations、 C9 反証可能性付き）
- 仮説H1: `all_folds_unavailable` 10倍は cycle1 bugfix副作用が主因。  
  - 現時点判定: **反証寄り**。まず Stage B期間が旧新で違う（183403→97003）ため、fold数低下（max 9→2）だけで大半を説明できる。  
  - 反証条件: 同一コード・同一データ・同一partition（B=97003固定）で `collect_stage_a` 修正有無だけA/B実行し、`all_folds_unavailable` が有意差なく一致すればH1棄却。
- 仮説H2: Stage B pass群 negative PnL は禁止事項6（取引回数削減で見かけ改善）構造。  
  - 判定: **抵触兆候あり**。pass群で trade_count が 65.5→16.5 に急減し、PnLは負。  
  - ただし n=22（<30）なので因果断定は禁止（C7）。  
  - 反証条件: trade_count帯で層別（例: 10-20, 20-40, 40+）しても Stage B pass優位が消えないなら「回数削減だけが主因」は棄却。
- 仮説H3: `wf_min_folds_required 2→4` は有効対策。  
  - 判定: **現状では不適切**。新R34の `n_fold_effective` が max=2 のため、4へ上げると原理的に全滅しやすい。偽陽性対策ではなく gate停止になる。  
  - 反証条件: 先に Stage B window設計を増やして `n_fold_effective>=4` が十分発生することを確認できた場合のみ有効化余地。
- 仮説H4: `v3_1_stage_b_priority` は偽陽性増加時に歪む。  
  - 判定: **歪むリスク高い**。tupleで `stage_b_pass` が上位かつ重複キーで入っており、偽陽性B-passが増えると選抜圧が偏る。  
  - 反証条件: B-pass偽陽性群の selection score を全世代で再計算し、上位占有が起きないならリスクは限定的。

## 次サイクル候補
- [Critical] 旧新比較の前提是正: 「同条件再現」検証を先に実施（partition固定・code固定・data hash固定でA/B）。  
- [Critical] Stage B gate設計再検証: `wf_min_folds_required` を上げる前に、まず fold生成可能性（B期間長とWF窓）を契約化。  
- [Warning] Stage B pass品質監査: n<30明記のうえ、trade_count層別で偽陽性構造を検証。  
- [Warning] selection score感度分析: `stage_b_pass`重み（重複キー含む）が選抜を歪めるか再評価。  
- [Warning] reason code集計の正規化: `stage_b_reason_codes` がセミコロン連結文字列で、primary/any集計の解釈齟齬を生みやすい。

## 全体判定
**CRITICAL_DRIFT**  
根拠: 旧新比較が同条件でなく（Stage B対象期間が別物）、その状態で `all_folds_unavailable` 10倍を副作用扱いするのは誤判定リスクが高い。加えて Stage B pass品質（negative PnL + 低trade_count）が悪い。

## Claude 分析との差分
- 同意点: Stage B pass品質が悪く、禁止事項6の兆候がある点。  
- 反対: `all_folds_unavailable` 10倍を「cycle1修正の副作用疑い」と強く置く点。まず **partition差分（183403→97003）** を主因候補として先に反証すべき。  
- Claudeが見落とした観点: `wf_min_folds_required 2→4` は現データ幾何（`n_fold_effective max=2`）では対策でなく fail-closed 化になりやすい。

### analysis-merged.md

# マージ分析: Run 34 新 (cycle 1 後 RUN, run_id=run_20260505_043320)

cycle 2/10。 Codex の C4 前提是正を全面採用し、 Claude の H_c2_2 (cycle 1 副作用疑い) を棄却寄りに更新。

## 合意事項（両者一致）

| # | 観察 | 含意 |
|---|------|------|
| M1 | Stage B pass 群 (n=22) で total_pnl mean=-14,303、 trade_count mean=16.5 (Stage A 65.5 から急減) | Stage B が「品質保証」になっていない |
| M2 | T087 partition は新 schema で完全整合 (`bars_stage_b_excludes_stage_a: true`、 timestamp range disjoint) | cycle 1 C1 持ち越し問題は **解消済** |
| M3 | per_generation の 7/8 key が全 null (best_fitness_pen のみ記録) | W3 (持ち越し) 依然 broken |
| M4 | 禁止事項 6 (取引回数削減で見かけ改善) の構造抵触兆候あり | n=22<30 で因果断定不可 (C7)、 だが構造的 risk |

## **Claude の前提誤り → Codex により是正 (C4)**

| Claude 主張 (H_c2_2) | Codex 是正 |
|---|---|
| 「旧 R34 と新 R34 は同設定 deterministic 再現」 | **棄却**: bars_stage_b が **183403 (旧) → 97003 (新)** で Stage B 評価期間が違う、 同条件比較不可 |
| 「`all_folds_unavailable` 216→2248 (10倍増) は cycle 1 fix の副作用疑い」 | **棄却寄り**: partition 差分 (B 期間短縮) で WF fold 数が減ったのが主因。 n_fold_effective max が **旧 9 → 新 2** に低下 (B 期間 67 日に WF train=60d+test=10d の窓を当てると fold 1-2 個が構造的必然) |

→ Claude の C4 違反 (前提未検証) を Codex が指摘。 真因は **Stage B WF 窓設計と新 partition の構造的不整合**。

## Codex 独自の発見

| # | 観察 | Claude が見落とした要因 |
|---|------|---------------------|
| C1 | n_fold_effective 分布: 旧 max=9 (`{0,1,2,3,...,9}`) vs 新 max=2 (`{0:2248, 1:623, 2:58}`) | Claude は B 期間短縮で fold 数が減る構造を看過 |
| C2 | `wf_min_folds_required 2→4` 引き上げは現データ幾何 (max=2) で fail-closed 化、 偽陽性対策にならない | Claude H_c2_1 提案 ("min_folds 2→4") は **不適切**、 fold 生成可能性を先に契約化すべき |
| C3 | Stage B window 設計 (期間長 + WF 窓) を契約化していない → DB データ拡張時 / partition 変更時に fold 数が予測不能 | 設計レベルの欠落 |
| C4 | reason code がセミコロン連結文字列 (例: `median_oos_sharpe<min;positive_fold_ratio<min;all_folds_unavailable`) で primary/any 集計の解釈齟齬を生みやすい | 集計ロジックの曖昧さ |
| C5 | Stage B pass 偽陽性の selection_score を全世代で実測すれば歪みの有無が verify 可能 | 量的検証手順 |

## 矛盾・要議論

| # | Claude | Codex | 結論 |
|---|---|---|---|
| D1 | H_c2_2 (cycle 1 副作用疑い) | partition 差分主因 (棄却寄り) | **Codex 採用**。 真因切り分けは「同 partition で fix 有無の A/B」 のみで verify 可能 (実用上は不要、 partition 差分主因が圧倒的に確からしい) |
| D2 | wf_min_folds_required 2→4 (H_c2_1 minimum 変更案) | 現データ幾何で fail-closed 化、 不適切 | **Codex 採用**。 fold 生成可能性 (B 期間 + WF 窓) の契約化が先 |

## 統合改善提案 (cycle 2 候補、 Codex 提示を中核に)

| # | 提案 | 優先度 | 出所 | target_metric | failure_mode | causal_path | falsification | success_criterion |
|---|------|--------|------|--------------|-------------|-----------|--------------|------------------|
| **P1** | **Stage B WF 窓設計の契約化** | **Critical** | Codex C2/C3 + Claude H_c2_1 修正 | Stage B fold 生成可能性 | B 期間 97003 bars (67 日) に WF train=60d+test=10d を当てると fold max=2 が構造的必然、 wf_min_folds_required 引き上げは fail-closed 化 | partition (T087) と WF 窓 (`wf_train_days / wf_test_days / wf_step_days / wf_min_folds_required`) の幾何的整合が契約化されていない | 契約化 (例: 「B 期間 ≥ wf_train + (wf_min_folds-1)*wf_step + wf_test」 の guard 追加) を実装し、 データ不足時に fail-closed 化、 充足時に WF 設計を健全化 (train/test 短縮 or B 期間拡張 or step 縮小) | 契約 guard が実装され、 現データ (B=97003 bars) で fold 数 ≥ 5 が達成 (wf_train=20d+test=5d+step=5d 程度に短縮) |
| **P2** | **Stage B pass 品質監査 (trade_count 層別)** | **Warning** | Codex Warning + Claude H_c2_3 | Stage B 偽陽性検出 | Stage B pass 群 trade_count mean=16.5 (Stage A の 4 分の 1)、 total_pnl mean=-14,303 | fold が成立した稀な小サンプル個体が positive_fold_ratio=1.000 で偽陽性 pass | trade_count 層別 (10-20 / 20-40 / 40+) で Stage B pass 優位が消えなければ「回数削減主因」棄却 | 層別後 「trade_count 40+ 帯で Stage B pass の total_pnl mean が positive」 確認、 もしくは構造改善で偽陽性減少 |
| **P3** | selection_score_schema 感度分析 | Warning | Codex Warning + Claude H_c2_3 | best 選定の歪み防止 | `v3_1_stage_b_priority` で stage_b_pass が tuple 上位かつ重複キーで偏重 | Stage B 偽陽性が増えると selection 圧が偽陽性に偏る | 偽陽性 22 件 (n=22<30) と Stage A 単独 pass 群の selection score を実測し、 上位占有が起きないか確認 | 偽陽性が上位占有しない or schema 改善案を文書化 |
| **P4** | per_generation observability schema 拡張 (W3 持ち越し) | Warning | 両者 | 観測性 | 7/8 key 全 null (best_fitness_raw / median_fitness_pen / stage_X_pass_count / population_diversity) | recording 経路で writer に値を渡していない、 or schema に存在しない | schema 確認 + 必要なら計測経路追加 (計測ロジックは不変) | per_generation null 率 < 10% (現状 100%) |
| **P5** | reason_code 集計正規化 | Suggestion | Codex C4 | 集計透明性 | `stage_b_reason_codes` がセミコロン連結文字列で primary/any 解釈齟齬 | parse 経路が複数ある可能性 | reason_code を構造化 (list of enum) で記録、 集計関数を SSoT 化 | 単一の集計関数で primary/any 両方が一意に取得可能 |

## 全体判定

**CRITICAL_DRIFT** (Codex 判定継承)

根拠: Stage B WF 窓と新 partition の不整合 (P1) は構造的設計欠陥で、 これが解消されない限り Stage B 偽陽性 (P2) も改善しない。 cycle 2 では P1 を **Critical 1** として最優先、 P2-P5 は Warning。

## 滞留 TODO 判断

Open / Conditional 共に 0 件、 棚卸し対象なし。

## Conditional 昇格チェック

Conditional 0 件、 評価対象なし。

