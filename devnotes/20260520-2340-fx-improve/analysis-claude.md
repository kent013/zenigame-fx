# RUN run_20260514_211202 (Run 82) 分析（Claude 自己分析）

## 前提差分
なし（archive Parquet / summary.json / analyze_run.py / codex 全て疎通確認済み）。

## 観察事実（Facts）

### Stage 通過数（vs Run 81）
| Stage | Run 82 | Run 81 | 差分 |
|-------|--------|--------|------|
| A pass | 2687 | 2293 | +394 (+17%) |
| B pass | **941** | 718 | +223 (+31%) ← ループ累積で最多 |
| C pass | **0** | 0 | ±0 |
| graduated | 0 | 0 | ±0 |
| rows | 5856 | 5856 | — |

- stage_b_gate_kind: 全個体 `profit_safe_pfr`（seed=67）。

### Best fitness_pen 個体
- `g53_i19` @ tier1_EUR_JPY, gen 53
- fitness_pen=0.489 / fitness_raw=0.528（ループ内でも高水準）
- **stage_b_pass=False**（best は Stage B すら通過していない＝高 fitness と gate 通過が乖離）
- trade_count=41, total_pnl=+43240, max_dd=0.0%, n_fold=19, positive_fold_ratio=0.526
- active_clause=2, n_nodes=6（浅い）

### live_criteria（graduation 候補評価、summary.json）
| 指標 | value | threshold | pass |
|------|-------|-----------|------|
| sharpe (annualized) | 2.276 | 1.0 | ✅ |
| total_pnl | 4670 | 50000 | ❌ |
| max_drawdown_pct | 1.23% | 20% | ✅ |
| trade_count | 23 | 50–5000 | ❌ |

→ **2/4 pass**（sharpe・max_dd 達成、total_pnl・trade_count 未達）。cycle 23 の sharpe annualize 修正以降、sharpe は安定して pass するようになった。trade-level sharpe は 0.23。

### Stage B pass 群（n=941）の分布
| 指標 | min | median | max | mean | nan |
|------|-----|--------|-----|------|-----|
| trade_count | 11 | 34 | 112 | 39.8 | 0 |
| total_pnl | -33910 | **-1950** | 13080 | -1905 | 0 |
| trade_sharpe_stage_c | -0.361 | **-0.038** | 0.179 | -0.032 | 290 |
| trade_sharpe_stage_b | -0.056 | 0.045 | 0.114 | 0.042 | 0 |
| max_drawdown_pct | 1.04 | 1.69 | 4.50 | 1.75 | 0 |
| positive_fold_ratio_eff | 0.50 | 0.59 | 0.69 | 0.59 | 0 |
| n_fold_effective | 20 | 25 | 34 | 24.7 | 0 |
| mission_score | 0.273 | 0.310 | 0.690 | 0.352 | 290 |

- **Stage B 通過群の total_pnl 中央値が負（-1950）**。trade_sharpe_stage_c 中央値も負（-0.038）。
- B 通過群で trade_sharpe_stage_c 最大でも 0.179（top: g54_i8 / g56_i11, pnl ~13000, tc 32-34, pfr 0.61-0.68）。

### Stage C を阻む reason codes（全集団 fail 理由 top）
| reason | count |
|--------|-------|
| median_oos_total_pnl<min ; sum_oos_total_pnl<min | 621 |
| positive_fold_ratio<min ; median_oos_total_pnl<min ; sum_oos_total_pnl<min | 509 |
| sum_oos_total_pnl<min | 265 |
| n_fold_effective_below_profit_safe_min | 105 |

→ Stage C 不通過の支配的理由は **OOS total_pnl が負/不足**（median・sum とも min 割れ）。

### 構造分布
- active_clause（A pass）: 1→1570, 2→1117（3 以上ゼロ）。
- n_nodes（A pass）: min2 / median3 / max8（**全体に浅い**）。
- primitive 頻度（A pass sample 500）: P7=586・P2=585（ほぼ全個体が使用）、F4=107（最頻 signal）、M5/M3/F6… と tail に多様性あり。

### 未計測（C4 明示）
- 保有時間分布・セッション跨ぎ比率・ロング/ショート方向比率: archive に trade-level 情報なし → **not measured**（深掘りは analyze-genome-archive 整備後）。

## 解釈・推論（Interpretations）

### 1. 壁は「sharpe」から「total_pnl × trade_count」へ移動した
cycle 23 の sharpe annualize 修正が効き、Run 82 の best は sharpe 2.28 で楽々 pass。残る未達は **total_pnl=4670（目標 50000 の 9%）と trade_count=23（最低 50 の 46%）**。best 個体は「少数・高品質取引で高 sharpe だが、取引が少なすぎて絶対利益も足りない」過選択状態。
- 反証可能性: もし trade_count を増やした個体が total_pnl も比例増させるなら、両者はトレードオフでなく単に「取引機会の取り逃し」。逆に trade_count 増で sharpe/pnl が劣化するなら本質的トレードオフ。→ 次サイクルで trade_count と pnl の散布を確認すべき。

### 2. profit_safe_pfr は「fold 一貫性」を選ぶが「利益の大きさ」を選んでいない疑い
Stage B 通過 941 個体の **total_pnl 中央値が負（-1950）、trade_sharpe_stage_c 中央値も負**。つまり gate は positive_fold_ratio（≈0.59）と n_fold を満たす個体を通すが、OOS の絶対利益がマイナスの個体を大量に通過させている。これが Stage C（OOS pnl 正を要求）で全滅する直接原因。
- 反証可能性: もし B 通過群の pnl 負が「holdout 期間の regime 固有」なら別期間で正に転じるはず（Alpha Sieve OOS で検証可能）。gate 設計の問題なら期間に依らず負。

### 3. C=0 の根本は OOS profitability の欠如であり、fold robustness ではない
reason codes は `median_oos_total_pnl<min` / `sum_oos_total_pnl<min` が支配的。fold 数や正 fold 比率は満たせている（n_fold med 25, pfr med 0.59）。**「ばらつきは小さいが期待値が負」**の個体群。これは「分散を抑える」方向の改善（fold robustness 強化）では解決せず、「期待 PnL の符号と大きさ」を直接押し上げる構造介入が必要。

### 4. genome が浅い（n_nodes median 3, active_clause ≤2）
表現力が低く、イントラデイの「頻度高く・利益も出る」複合シグナルを捉えきれていない可能性。ただし複雑化は禁止事項 #5（やたら複雑な案）と緊張するため、深さペナルティの妥当性検証に留めるべき。

### 5. 禁止事項違反の兆候
- イントラデイ逸脱: 直接計測不可だが max_dd 1-4% と低く、保有暴走の兆候は薄い。
- 取引回数削減で見かけ改善（禁止 #6）: **むしろ逆方向の懸念**。best が trade_count 23 と少なく、これは「回数削減で sharpe を稼いでいる」可能性。live_criteria の trade_count 下限 50 がこれを正しく弾いている。
- live_criteria 緩和: 兆候なし。

## 次サイクル候補

- **[Critical] Stage B/C gate の「OOS profitability magnitude」要件強化**: profit_safe_pfr が median_oos_total_pnl 負の個体を 941 通過させている。Stage B 通過条件に「median OOS pnl > 正の下限」を課す（または fitness に OOS pnl 期待値の符号付き項を加える）ことで、Stage C で全滅する無益な探索を上流で削減し、選択圧を profitability に向ける。閾値緩和ではなく**正方向への要件追加**である点に注意（禁止 #4 非該当）。
- **[Warning] total_pnl × trade_count トレードオフの実証**: 次 Run で trade_count と total_pnl/sharpe の散布を確認し、「取引機会取り逃し」か「本質的トレードオフ」かを判定。前者なら entry 条件の緩和系 primitive を、後者なら fitness の pnl 項重み調整を検討。
- **[Warning] seed variance の低減**: 前ループ Run75-81 で Stage B pass が 827→0→0→458→175→718 と激しく変動。mission(Run75) は seed=60 lucky draw 依存。多seed 平均 or 評価の頑健化を検討（ただし評価コスト増に注意）。
- **[Warning] genome 深さペナルティの妥当性検証**: n_nodes median 3 と浅い。深さペナルティが過剰で表現力を削いでいないか確認（複雑化推奨ではなく、ペナルティ係数の健全性点検）。

## 全体判定
**CONCERN** — mission 未達（C=0）。Stage B は record 高（941）だが、その大半が OOS pnl 負であり gate が profitability を選べていない。sharpe の壁は越えたが total_pnl/trade_count が新たな壁。閾値緩和でなく gate/fitness の profitability 要件強化が次の打ち手。

---

## 【重要訂正】解釈 #2 の撤回 — gate は正しく動作している（Codex Critical 検証結果）

Codex の Critical 提言（B判定メトリクスと archive 集計メトリクスのスコープ一致監査）を実施した結果、**解釈 #2「profit_safe_pfr が OOS pnl 負の個体を通過させている」は誤りだったため撤回する**。

検証（Stage B pass n=941）:
| カラム | min | median | max | n<0 |
|--------|-----|--------|-----|-----|
| `total_pnl`（当初参照、誤）| -33910 | -1950 | 13080 | 581 |
| `median_oos_total_pnl`（gate 実使用）| 15 | 1280 | 3775 | **0** |
| `sum_oos_total_pnl`（gate 実使用）| 40 | 18250 | 74380 | **0** |

- profit_safe_pfr gate 定義（stage_gate.py:558-573）: ① positive_fold_ratio_effective>=0.4 ② median_oos_total_pnl>=0 ③ sum_oos_total_pnl>=0 ④ n_fold_effective>=20。
- **B 通過 941 個体で ②③ 違反はゼロ件**＝gate は設計通り「fold-CV OOS で黒字」の個体のみ通過させている。
- 当初参照した `total_pnl` は **Stage C holdout 窓（連続 60 日 + spread×1.5 stress, stage_c_holdout_days=60）の PnL** であり、スコープが異なる（Codex 仮説 B が正解）。

### 真のボトルネック（再定義）
**Stage B（dataset 全域の fold-CV OOS）では黒字・頑健なのに、Stage C（連続 60 日 holdout 窓 + spread×1.5 stress）では大半が赤字** という汎化ギャップ。

補強事実:
- B 通過群の trade_count: full_dataset 中央値 192 / stage_b 142 に対し、**Stage C holdout では 34**（短窓ゆえ取引機会が激減）。
- live 候補 best は holdout で trade_count=23（live 下限 50 未達）・total_pnl=4670（50000 未達）。
- これは「fold をまたいだ平均では黒字だが、特定の連続 60 日窓 + stress 下では負/低頻度」という、CV→holdout の典型的な汎化失敗。

→ 改善方向は「gate の profitability 要件強化」ではなく、**(a) Stage C 評価集団の質（lucky cluster 集中の緩和・novel cluster 機会確保）の改善、または (b) Stage B→C 汎化を予測する選択圧の付与**。

---

## TODO 由来の改善候補（standalone ルール適用）

Open テーブルに standalone タスクが存在（T100/T101/T102/T103）→ skill の standalone ルールにより最優先 standalone を **1 件のみ** 選定、incremental は混在させない。

候補比較:
| ID | タイトル | 優先度 | mode | ボトルネック関連性 | 実装リスク |
|----|---------|--------|------|------------------|-----------|
| **T100** | Stage C stratified allocation | Medium | standalone | **高**（Stage C 評価集団の lucky cluster 集中緩和＝今回の C ボトルネック直撃） | 低（config-gated opt-in、行動変更 1 RUN smoke） |
| T101 | Run71/63 warmstart | Low | standalone | 中（再現性検証） | 中 |
| T102 | Phase 2 統合 Step3-7 | Medium | standalone | 低（NSGA-II/CPPS 配線、大規模 5 sub-PR） | 高（loop 停止リスク） |
| T103 | primitive 拡張 30-50個 | Low | standalone | 中（探索空間拡大） | 高（大規模） |

選定: **T100**（Medium、Stage C ボトルネック直撃、既存詳細設計あり、config-gated で低リスク）。

| ID | target_metric | failure_mode | causal_path | falsification | success_criterion | 判定 |
|----|--------------|-------------|------------|---------------|-------------------|------|
| T100 | Total PnL / Trade Count（Stage C 通過個体の出現＝C>0） | Run82 で Stage B 941 通過も Stage C=0。Stage C 評価集団が fitness_pen 上位順で lucky cluster / 同型解に集中し、novel cluster が holdout 評価機会を得られていない疑い | Stage C 評価集団を persistence decile × primitive cluster で層別抽出 → 同型解集中を緩和 → novel cluster が holdout 評価を受ける → holdout で黒字・高頻度な個体が C を通過する確率上昇 | stratified 化後も Stage C pass=0 のまま、かつ評価集団の primitive cluster 多様性が legacy と有意差なし | 次 Run で Stage C 評価集団の cluster 多様性が向上し、かつ Stage C pass>0 または holdout total_pnl 分布の上方シフトが観測される | **REJECT（design-stale）** |

### T100 を design-stale として却下（競合チェック結果）
`swim_lane.py:665-694` を確認した結果、**Stage C 評価には top-N cap / 選定段階が存在せず、Stage B 通過個体は全件その場で `evaluate_stage_c` される**（Run82 では 941 件全件評価）。T100 の設計前提（「Stage C 評価集団は Stage B pass 順で集約され lucky 個体が混入」）は現行コードに対し成立しない。層別化すべき選定対象が無いため、T100 はそのままでは実装不能。

→ `skip_todos: [{id: T100, reason: "design stale: Stage C は全 B-pass を無 cap 評価。stratify する選定段階が現行コードに存在しない"}]`。
→ **cycle_focus を `ga_improvements` に切替**。core bottleneck（B fold-CV → C 60日holdout+stress の汎化ギャップ）に対する GA 構造改善を Codex 合議で 1 つに収束させる。
