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
