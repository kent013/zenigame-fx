# GA 機能不全 監査 (Run 1〜16 時点) — Claude 独立分析

**監査対象**: zenigame-fx Alpha Factory（Phase 2 architecture + Run 16 まで）
**目的**: GA が「適切に動作」していない根因を、コードと観測データに基づき網羅的に洗い出し、次の手当ての論点を Codex と議論する。
**前提**: AGENTS.md「仕組みが機能していない段階で値を弄るな。設計そのものを見直せ。」を適用。閾値調整ではなく構造論点を中心に置く。

---

## 1. 観察事実（Fact / data-derived）

### 1.1 Run 1〜16 mission 達成度の推移

| Run | best_fitness | sharpe | trade_count | total_pnl | A_pass | B_pass | C_pass | 備考 |
|----:|------------:|------:|-----------:|---------:|------:|------:|------:|------|
| 10 | 18.481 | 18.49 | **3** | 18,860 | — | — | — | no-trade attractor (見かけ Sharpe) |
| 11 | 0.119 | 0.128 | 31 | 0 | — | — | — | feasibility 適用後 |
| 12 | 0.274 | 0.052 | 72 | 7,610 | — | — | — | trade_count 充足 |
| 13 | 0.417 | 0.329 | 68 | 36,110 | — | — | — | total_pnl 過去最高 |
| 14 | 0.121 | 0.140 | 59 | 0 | — | — | — | total_pnl 0 退行 |
| 15 | 0.466 | 0.069 | 70 | 8,660 | — | — | — | sharpe 退行 |
| 16 | 0.332 | 0.341 | 30 | 0 | **0** | **0** | **0** | trade_count 後退 |

- 16 Run の累積で **Stage C pass を 1 体も生成していない**。Stage A pass すらゼロの Run が出始めた（Run 16）。
- 2 Run 連続で best_fitness の方向性が逆転（13→14 大幅退行、15→16 再退行）。**seed のばらつきで全ての性能が支配されている可能性**。
- 短中期 FX で Sharpe 1.0 以上は本来狙える水準だが、**現状の best fitness は plateau ≤0.5**。

### 1.2 Run 16 archive の構造的指標（5856 行）

- `active_clause`: n=5856, **mean=0, median=0, std=0, min=0, max=0**
- `n_nodes`: mean=2.29, median=2, std=0.79, min=1, **max=4**
- `fold_sign_ratio`: n=0（Stage A pass が 0 なので fold 評価対象なし）
- `dsr`: n=0（同上）
- Stage B failure reason: 集計対象 0 件（A pass=0 のため B 評価到達なし）
- 全 archive が `lane_id=tier1_EUR_JPY`、`instrument=EUR_JPY` の 1 通貨ペア。
- cross-pair shadow: `runtime mode = skipped_single_instrument`、ii_lite_pass は全行 None。

### 1.3 収束履歴（Run 16）

- gen 0: 0.0 → gen 11: 0.275 → gen 13: 0.301 → gen 18: 0.306 → gen 26: 0.332
- **gen 26 〜 gen 60（35 世代）best_fitness 完全凍結 0.3321706…**。population_size=96, mutation_rate=0.3, plateau_cycles=3 設定だが、auto plateau bump は本 Run では発火していない（improve_cycle 内のループ単位で発火、1 Run 内では走らない）。

### 1.4 コードの構造的事実

#### (a) `active_clause` は **placeholder** で常に 0
`src/alpha_factory/archive.py:171-183`
```python
def _compute_n_nodes(genome: Genome) -> int:
    return sum(len(c.directional) + len(c.local_gate) for c in genome.clauses)

def _compute_active_clause_placeholder() -> int:
    """**Phase 2 placeholder**: runtime 発火 clause 数取得経路が未整備のため
    ``0`` を返す。
    将来 ``DslStrategy`` / engine 側に発火カウンタを追加し、
    ``collect_stage_a`` の引数で受け渡すよう拡張予定（別 TODO）。
    """
    return 0
```
- TODO T037 として登録済（Critical / 設計あり）。**しかし未実装のまま 16 Run が走った**。clause が「実際に発火しているか」は構造的に観測不能で、archive 解析・bug claim・改善議論は **盲目** で進めてきた。

#### (b) `max_clause = 1` で構造的に composite genome を探索不能
- `src/alpha_factory/config.py:136` `max_clause: int = 1`
- `config/alpha_factory/default.yaml` に `ga.max_clause` の override **無し**
- `src/ga/random_gen.py:200` `n_clause = rng.randint(1, max_clause)` → 常に 1
- 1 clause = 1〜max_depth(=4) directional + 0〜1 gate
- `n_nodes mean=2.29` がこれと一致（1 dir + 1 gate がモード）
- **clause-architecture.md が謳う "mixture of experts" の理論的根拠（Jacobs 1991, Jordan & Jacobs 1994）が、運用レベルで一切活用されていない**。GA は単純な「1 directional + 0-1 gate」の浅い構造のみを探索している。

#### (c) Pair-specific primitive 12 個の "死荷重" 化
- 全 primitive 32 = directional 14 + modulator 6 + pair-specific 12
- pair-specific (P1-P12) は各々 EUR_USD/USD_JPY/EUR_JPY/AUD_JPY/USD_CAD/USD_ZAR の cross-pair / aux series を要求
- Run 16 は EUR_JPY 単独運用、`aux_pair_bars` / VIX snapshot は warning + safe default で「常に 0 / 中立」を返している可能性が高い（pair_specific.py:_warn_missing/safe default の挙動）
- **実効的な探索 primitive は 14 (dir) + 6 (mod) ≈ 20 のみ**。設計では 32 だが運用上は 60% 近くが eval 不能な状態。
- zenigame の primitive class 数（`_momentum/_reversion/_volume/_market/_session/_condition/_core` 配下）は ≈76。**zenigame-fx は 1/4 以下**（実効ベース）。

#### (d) `swim_lane` / `cross_pair` 設定はあるが run-ga は 1 lane で動作
- yaml: `swim_lane.tier1.population_size=30, generations=15`、`cross_pair.anchors` に 6 ペア定義
- 実運用 (Run 16): population_size=96, generations=60, lane=1（tier1_EUR_JPY のみ）, cross-pair=skipped
- run-ga が `swim_lane` 設定を**消費していない**（または 1 instrument 運用に decay している）。多通貨化は「設計だけ存在し、ランナー未統合」の状態。

#### (e) Hard binary live_criteria のみ／soft fitness 無し
- `live_criteria`: sharpe≥1.0 AND total_pnl≥50k AND dd≤20% AND 50≤trade≤5000
- GA fitness: `sharpe` 単軸（trade_count_min_for_sharpe=30 と feasibility ペナルティ付き）
- **使命の 4 要素のうち 3 つ（pnl, dd, trade_count）が fitness に直接寄与していない**。
- zenigame 比較: `amscore`（adaptive mission score）= 各 window で sharpe/net%/tc を soft 化した連続値で、86 Run 連続未達でも 0.7731 の gradient を保持。zenigame-fx は best fitness が肥大化した sharpe (= no-trade で +18) か feasibility ペナルティ後の 0〜0.5 の谷に落ちるかの bimodal で、勾配が出にくい。

### 1.5 zenigame との report 構造比較（Run 1260 vs Run 16）

| 観察軸 | zenigame (R1260) | zenigame-fx (R16) |
|-------|-----------------|-------------------|
| Stage 通過数 | A=1490 / B=1384 / C=10 | A=0 / B=0 / C=0 |
| Mission 評価 | hard amp=0 + soft amscore=0.7731 | hard 4 要素 (3 未達) のみ |
| Window 分割 | W0 flat / W1 trend_up / W2 defensive (regime 別 IS) | 単一 IS 期間 |
| Bucket | Bucket 0-4 を時間別に rotate | 単一 |
| Director (LLM) | 99.7s 応答, 重み audit, hypothesis 適応 | 無し |
| Sieve warmstart | 15 体 (adaptive_pass/progress 評価) | 無し（alpha-sieve は別 Run で実行） |
| 多様性指標 | HHI=0.120, Diversity intervention 自動発火 | 無し |
| Epoch 追跡 | 連続 SUCCESS で c_lift 集計 | 無し |
| Best 個体 clause 構成 | n_clauses=6, primitive 9 種 | n_nodes=2 (固定) |
| Top-5 archive | adaptive_mission_score / amwpc 表示 | fitness_pen のみ |

zenigame-fx の report は **archive 落下分布と best 1 体の表面情報のみ**。regime / multi-window / director / diversity / epoch といった「探索プロセスの健康診断」軸が欠落している。

### 1.6 周辺の状態

- TODO Open: T033 cost-pnl ledger / T034 no-trade fitness guard / T036 FSP single-instr / T037 active-clause metric / T039 economic-event as_of strict / T040 calibrate-gate drift monitor。**T036/T037 が「いま埋めるべき盲点」に直撃するが、Critical 表記のまま open**。
- 改善 cycle 1〜6 は「閾値 reset → calibrate-skip → 再 calibrate」の往復に時間を使い、構造論点（max_clause / active_clause / multi-instrument / soft fitness）に到達していない。

---

## 2. 解釈（Interpretation, fact から分離）

### H1. **構造的探索不足 (Underexploration)**
`max_clause=1` で composite/mixture genome を一度も試していない。GA の表現力が clause-architecture 設計の最低ラインに達しておらず、「1 directional + 0-1 gate」の浅い空間で plateau が連続発生。これだけで mission 達成は理論的にも厳しい。

### H2. **観測の盲目化 (Observation gap)**
`active_clause=0` 固定により、「genome が実際に発火しているか / 何個の clause が貢献しているか」が分からない。Run 16 で best が 30 trade を出したが、それが偶発か（1 clause がたまたま当たった）構造的に再現可能か（複数 clause の合算）を区別できない。

### H3. **Pair-specific primitive の死荷重 + 多通貨化未着手**
全 primitive の 37.5%（12/32）が single instrument 運用では実質的に safe default を返すだけ。FX 特性（cross-pair, session, news）を取り込む primitive を増やしたい設計だが、実機が 1 通貨 1 lane で停滞。

### H4. **Hard fitness の勾配欠損**
sharpe 単軸 + feasibility 二値で、no-trade attractor を潰した結果、population の大半が fitness ≤ 0.3 の谷に落ち勾配を失う。GA は「全員ほぼ同じ低 fitness」状態で tournament selection が drift に近くなる（plateau が 35 世代続く力学的根拠）。

### H5. **report の解像度不足が改善議論を制約**
window/regime/lane/director/diversity が無いため、Codex/Claude/人間のいずれも「次に何を試すか」を data-driven で詰めにくい。Run 1〜16 の改善 cycle が "stage_a.threshold をいじる" に偏ったのも、これが原因の一つ。

### H6. **改善 cycle の局所最適化**
cycle 3 で WF 短縮 → cycle 4 で gate reset → cycle 5/6 で再 calibrate のループは、上記 H1-H5 の構造論点を素通りしている。AGENTS.md「仕組みが機能していない段階で値を弄るな」が遵守されていない。

---

## 3. 論点（Codex に問いたい）

優先順位の判断と、見落としている軸を独立に評価してほしい。

### Q1. 最優先で潰すべき構造論点はどれか
候補（複数選択可）:
- (a) `max_clause` を 2-3 に上げて composite genome を探索する
- (b) T037 active-clause metric を実装し archive 解析の盲目を解く
- (c) T036 FSP single-instrument daily diagnostic を入れる
- (d) cross_pair / swim_lane を実機統合し multi-instrument に切り替える
- (e) live_criteria を soft 化して fitness に勾配を与える（amscore 相当）
- (f) zenigame の director / sieve warmstart を移植
- (g) primitive 拡張（session / order-flow / news 系を追加）

### Q2. Primitive 数 32（実効 20）は不足か、それとも先に max_clause/composite 化が先か
不足だとして、FX 特化で次に追加すべき primitive 群（カーボン/ファクターでもよい）の優先度。

### Q3. Single instrument を維持しつつ GA を機能させる道は成立するか
multi-instrument 化が「設計だけ存在し、ランナー未統合」状態の中、(d) を本格実装する前に EUR_JPY 単体で何ができるか。FSP (T036) は single instrument 用の代替策として十分か。

### Q4. Plateau 35 世代凍結への構造的対策
- mutation_rate bump（既存 plateau_cycles=3 仕掛け）は cycle 単位で 1 Run 内では発火しない。1 Run 内で plateau を破る仕組み（island model / re-init / novelty pressure / hyper-mutation）を入れる必要は？
- それとも 1 Run の generations を増やすより population/lane を増やすほうが探索効率が高いか？

### Q5. report 拡張の最小コア
zenigame の amscore / window / bucket / HHI / director を移植するとしたら、まず何から入れるべきか。FX で意味を持たない要素（株式市場特有の bucket 等）は何か。

### Q6. Hard mission criteria を変えるべきか
sharpe≥1.0 / pnl≥50k / dd≤20% / 50≤trade≤5000 は妥当か。短中期 FX イントラデイで現実的なベンチマークか、見直し余地があるか。

### Q7. 監査の盲点
本監査が**取り上げていないが致命的**である可能性のある軸（例: リーク・コスト・データ・broker 仮定・bar 生成・evaluator 数値計算など）。Codex 視点で追加してほしい。

---

## 4. 提案する次の一手（Claude 仮案、Codex への叩き台）

仮の優先順位（**Codex の独立判断で覆る前提**）:

1. **T037 active-clause metric 実装**（観測盲目を解く。1〜2 日規模）
2. **`max_clause` を 2 に引き上げ、初期世代の 1 clause 比率を 50% にして compositional 探索を開始**（小規模設定変更 + 評価）
3. **`live_criteria` の soft 化（amscore 相当）を Run 評価に加える**（GA fitness は当面 sharpe のまま、観測指標として導入）
4. **multi-instrument 化（cross_pair / swim_lane の実機統合）は (d) より先に T036 FSP single-instr daily で代替評価**（cross-pair 化は Phase 4 想定の重作業）
5. **plateau-aware operator**（1 Run 内で best 不変が N 世代続いたら hyper-mutation または部分 re-init）
6. **report 拡張**: regime split / clause 構造分布 / fitness diversity (HHI 相当) / plateau 警告

但し 1〜6 は **互いに独立ではない**（active_clause なしで max_clause 上げても観測できない、soft fitness なしで multi-instrument 化しても勾配出ない 等）。Codex には依存関係を含めた最小経路の提示を求める。

---

## 5. Codex への明示的依頼

1. 上記 Q1〜Q7 を独立に評価し、**反証可能性のある形で**回答してほしい（C9 Falsification-first、Round 1 は Claude 仮案の反証から始める）。
2. **見落としている重大論点**（特に Q7）があれば優先順位込みで提示。
3. 仮に GA を「動作する」状態にする最小経路を 1〜2 weeks 規模で示せるか（roadmap）。
4. 反対に「現状の構造のまま閾値調整だけで何 Run 続ければ mission 達成可能性が出るか」の見解（諦観論の妥当性チェック）。

discipline:
- C1 Design-first / C6 Fact-Interp 分離 / C7 sample size / C8 INCONCLUSIVE 受容 / C9 Falsification-first
- bug claim する場合は該当ファイル + 行番号 + 現象を必ず添付
- single Run 観測（Run 16）からの一般化はサンプル数不足である点に留意（n=1）
