# マージ分析: Run 35 (run_20260506_030253)

cycle 3 / 20 — Claude / Codex 両分析の統合。

## 合意事項（両者一致）

| # | 観察 / 仮説 | 含意 |
|---|------|------|
| M1 | cycle 2 WF 窓整合化で fold 評価が機能化 (n_fold_effective median 0→9)、 Stage B pass 0 は退化ではなく **真の品質測定の結果** | 評価機構修正は CONFIRMED 改善 |
| M2 | max_clause=2 拡張は Stage A 通過率に逆効果（active_clause=1: 44.0% vs active_clause=2: 11.6%） | 複合 clause は現状「ノイズ拡張」寄り、 探索拡張になっていない |
| M3 | best 個体は trade_count_min=50 ぎりぎり (53)、 Top-3 (fitness_pen 単独 max) は trade<50 で sharpe NaN | trade_count attractor の疑い + Stage A 目的関数と live 適合性のギャップ |
| M4 | live_criteria 不変、 Stage A threshold 不変 (-0.0172) — 禁止事項 1, 2, 4 は未発生 | 数値弄りによる見栄え改善は無し |
| M5 | cross-pair shadow 全 skip 継続 (single instrument) | anchors 設計が機能していない、 監視欠落（要対応だが優先度は Stage gates 後） |

## Claude 独自の発見

| # | 観察 | Codex はなぜ取り上げなかったか |
|---|------|---------------------------|
| L1 | positive_fold_ratio_min=0.6 を「過厳格」と仮説化 (H3) | Codex は「閾値より探索圧不整合が主因」として閾値仮説を**棄却寄り**（修正点）|
| L2 | total_pnl=0 かつ trade>0 が 0 件で cycle 1 fix 機能継続 | Codex も観察したが因果に踏み込まず |
| L3 | fold_sign_ratio max=0.7 で天井、 GA 探索空間の構造限界仮説 (H4) | Codex も近い指摘 (fold_sign 停滞) を出しているが構造限界とは言わず |

## Codex 独自の発見（Claude が見落とした観点）

| # | 観察 | Claude の見落とし |
|---|------|------------------|
| C1 | **探索圧不整合**: GA は fitness_pen (Stage A) 最大化方向に進化、 fold_sign_mean は世代を重ねても 0.20 帯で停滞 | Claude H4 は近いが「primitive 設計の限界」に話を膨らませた。 Codex は **Stage A 目的関数自体が Stage B 要件と整合していない** という構造的な問題を指摘 |
| C2 | **`fitness_pen` 上位が trade<50 / sharpe NaN / fold_sign=0 でも上に来る** = live 適合性と GA 目的関数のギャップは強い警告 | Claude W3 で確認依頼に留めた、 Codex は最重要警告として位置付け |
| C3 | メタ過学習ガード: max_clause=2 維持・調整は **Reactive Parametric** （直近 Run ベース） で、 同じデータへの当てはめ強化のリスク | Claude は max_clause=2 維持/戻し/調整の三択を提示するに留め、 メタ過学習リスクは明示せず |

## 矛盾・要議論

| # | Claude の見解 | Codex の見解 | 議論 |
|---|------------|------------|------|
| D1 | positive_fold_ratio_min=0.6 を緩和候補に検討 (H3) | 「閾値より Stage A 目的関数の不整合が主因」、 閾値変更を **早計** と判断 | **Codex 優位** — fold_sign_ratio max=0.7 で天井なのは「fold で robust に勝つ signal が探索範囲に無い」可能性。 閾値緩和は禁止事項 4 (ステージ飛ばし) に抵触する恐れ。 まず Stage A 目的関数監査を先行 |
| D2 | max_clause=2 を 戻す or 評価論理見直し or 初期生成確率調整の三択 | max_clause=1 に戻した A/B 反証実験を Critical | **Codex 優位** — Claude 案 (a)(b)(c) のうち (a) が最も反証可能性が高い。 ただしユーザー指示で max_clause=2 baseline 設定があるため、 戻すには user confirm が必要 |
| D3 | best trade_count attractor を Warning | 同 | 一致 |

## 統合改善提案（優先度順）

| # | 提案 | 優先度 | 出所 | 変更分類 | target_metric | failure_mode | causal_path | falsification | success_criterion |
|---|------|--------|------|---------|--------------|-------------|------------|---------------|-------------------|
| **P1** | **Stage A 目的関数と Stage B 要件の整合監査 (観察 sidecar 追加)** | **Critical** | Codex C1 + Claude H4 | **Structural** | Stage B pass count / Sharpe robustness | GA は fitness_pen 増加方向に進化するが fold_sign_mean は 0.20 帯で停滞 → Stage A 目的関数 (fitness_pen = sharpe - α·size_norm) が WF 頑健性を測れていない | Stage A 目的関数に WF fold-aware の構造的シグナルが欠落、 結果として Stage B 不通過が世代を重ねても解消しない | Stage A pass 群で **世代別の fold_sign_mean / median_oos_sharpe 分布を sidecar parquet に出力**、 後 Run の analyze で「Stage A 上位群でも fold_sign が世代と共に上昇しない」が verified なら H1 棄却 (= 閾値や primitive の問題)、 verified なら本仮説確証で Phase 4 で目的関数改修 | sidecar parquet が世代別 stage_a 上位 N 件の fold_sign / median_oos_sharpe を含み、 cycle 4 の analyze で Stage A 順位と fold robustness の相関を測定可能 |
| **P2** | **archive Top-1 (g26_i95) trade<50 / sharpe NaN / fold_sign=0 個体の stage_a_pass 経路調査** | **Critical** | Codex C2 + Claude W3 | **Structural** (調査のみ、 修正は別 cycle) | live_criteria 整合性 | trade_count<50 で stage_a_pass=True、 さらに fitness_pen 単独 ranking で top に来る = GA selection / Stage A 評価が live 制約を反映していない | Stage A の通過判定が trade_count_min をチェックしていない、 もしくは別経路 (selection_score) が trade_count<50 を許容している | g26_i95 の stage_a_pass 経路を grep + log で追跡。 stage_gate.canonical_five.dual_path で stage_a_pass=True が出ているなら canonical の閾値経路を確認 | trade_count<50 で stage_a_pass=True になる経路が特定され、 設計通り or bug の判定が可能 |
| **P3** | trade_count attractor 監視 (cycle 4-5 で経時観測) | Warning | Claude W1 + Codex Warning 2 | 観察のみ | trade_count 分布 | best trade_count 53-54 が cycle 1, 2, 3 で固定化したら attractor 確証 | cycle 4-5 で best trade_count が 50-55 帯から離れれば棄却 | best trade_count が 50-55 帯に集中せず分散する |
| **P4** | cross-pair shadow 妥当性確認は **明示保留** | Warning | 両者一致 | 観察のみ | shadow 統計の情報価値 | single instrument 運用中は判断不能 | multi-instrument RUN 復帰までは判断保留 | multi RUN 後に shadow 指標と本番指標の整合を測定 |
| **P5** | max_clause=2 維持/戻しの判断は **保留**（C3 メタ過学習ガード） | Warning | Codex C3 + Claude H2 | Reactive Parametric (要注意) | active_clause 別 Stage A 通過率 | max_clause=2 拡張で複合 clause 個体の Stage A 通過率が 1/4 | (a) 戻す / (b) 評価論理見直し / (c) 初期生成確率調整 のいずれを取るか、 P1 (Stage A 目的関数監査) の結果を見てから判断 | P1 sidecar で「Stage A 上位は単一 clause 偏重 = 複合 clause が Stage A に不適」が verified なら (b) の方向、 不変なら (c)、 Codex 推薦は (a) | P1 結果に基づく根拠ある判断 |

**保留事項**:
- P5 (max_clause=2 baseline 維持/変更) は P1 (Stage A 目的関数監査) の結果を待ってから cycle 4 以降で判断する。 ユーザー指示 (max_clause=2 baseline) を尊重しつつ、 観測データで根拠ある判断を優先

## 全体判定

**CONCERN（Codex CRITICAL_DRIFT を踏まえつつ、 cycle 3 の介入は P1 観察 sidecar 追加に絞る）**

cycle 2 の WF 機能化は CONFIRMED 改善。 ただし「探索圧不整合」「live 適合性ギャップ」「max_clause=2 メタ過学習リスク」 の 3 つの concern を抱えた状態で、 cycle 3 では **P1 (sidecar 観察追加)** という structural / 観察のみ の最小介入で進む。 P2 (Top-1 経路調査) は調査メイン、 修正は cycle 4 以降。

「仕組みが機能していない段階で値を弄るな」 「機能の名前に立ち返れ」 の原則に従い、 閾値や max_clause の調整は cycle 4 以降の決断とする。
