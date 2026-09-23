# 詳細設計: Run 89 施策 (T116: 連続値選択圧 + pass 条件観測列)

## 使命・制約
cross-pair 汎化個体を得る。T115 bool tie-break は gen0 飽和で上昇圧ゼロ → 連続値化で勾配付与。pass 3 条件実値を観測し天井検証 + proxy 整合性監視。default OFF で挙動不変。閾値緩和なし。

## 診断 (cycle 7 確定)
T115 `cp_pref = int(aggregate_fitness > 0)` は gen0 から全個体 >0 で飽和 (gen median 0.027→0.022 平坦)、pass mean_sharpe_cross≥0.15 到達 0。max aggregate 0.0485。

## 施策 T116

### 1. _selection_key 連続値化 (run_ga.py)
現 (T115):
```python
cp_pref = int(entry.cross_pair_margin is not None and entry.cross_pair_margin > margin_threshold)
return (*score[:9], cp_pref, score[9])
```
変更後 (連続値、NaN/inf guard):
```python
m = entry.cross_pair_margin
cp_val = float(m) if (m is not None and math.isfinite(m)) else -math.inf
return (*score[:9], cp_val, score[9])
```
- fold_robust(idx8) と fitness_pen(idx9) の間に **連続値** cp_val。None/NaN/inf → -inf (最下位、cross-pair 評価なし個体は不利、pass 整合)。
- **default (selection_pressure=False) では現行 10-tuple をそのまま返す (bit-exact 不変)**。連続値は selection_pressure=True 時のみ。
- lex float 比較安定性: -inf guard で NaN 比較破壊を回避 (既存 fitness_pen の finite guard と同パターン)。
- margin_threshold は連続値では未使用 (bool 専用) → 後方互換のため引数は残すが連続値経路では無視 (or Codex 判断で削除)。

### 連続値の指標: cross_pair_margin (=aggregate_fitness) を継続使用
- cross_pair_margin は既に aggregate_fitness (=mean_sharpe − λ·std)。これは cross-pair 汎化の単調指標で、連続選択圧として勾配を与える。
- mean_sharpe_cross (pass 直結) への変更も検討したが、aggregate_fitness は std ペナルティ込みで「安定して全ペアで効く」個体を優遇 = pass 基準 (min_sharpe≥-0.20 含む) と方向整合。**まず aggregate_fitness 継続** (Codex で mean_sharpe_cross 優位なら変更)。観測列で両者の climb を比較し proxy 整合性を検証。

### 2. pass 3 条件観測列追加 (archive、観測専用・selection 非影響)
CrossPairResult.metrics から 3 列を 4 点セットで追加 (T115 cross_pair_aggregate_fitness と同じ archive.py:853 の cross-pair 書込箇所):
- `cross_pair_mean_sharpe` (metrics["mean_sharpe"]) — pass: ≥0.15
- `cross_pair_min_sharpe` (metrics["min_sharpe"]) — pass: ≥-0.20
- `cross_pair_target_ratio` (metrics["sharpe_target_cross_ratio"]) — pass: ≥0.8
- 各: GENOMES_SCHEMA float64 nullable + _create_row_template None + cross-pair 書込 (skipped/None→None, else _finite_or_none(metrics.get(...))) + flush。
- 目的: (b) 天井検証 = 実 max mean_sharpe_cross が 0.15 近傍か / (Codex W1) proxy 整合性 = aggregate climb 時 mean_sharpe も climb するか (メタ過学習ガード)。selection には一切使わない (観測専用)。

### 3. config
既存 `cross_pair.selection_pressure: bool` を流用 (連続値化は実装変更のみ)。新 flag 不要。bool→continuous は実装の置換 (旧 bool 挙動は破棄、merged T115 は実運用未使用のため後方互換不要 → Codex 確認)。

### default bit-exact 保証
selection_pressure=False で _selection_key は現行 10-tuple (cp_val 挿入なし)。観測列 3 つは archive のみ (selection_score 不変)。既存テスト全 pass。

### テスト計画
- [ ] default bit-exact: selection_pressure=False で _selection_key 10-tuple 完全一致 (連続値挿入なし)。既存 run_ga_parallel pass。
- [ ] 連続値順序: selection_pressure=True で高 cross_pair_margin 個体が同 fold_robust の低 margin 個体より上位 (連続、bool でない)。None/NaN → -inf 最下位。
- [ ] 既存 T115 bool テスト (test_cross_pair_selection_pressure) を連続値仕様に更新。
- [ ] 観測列 3 つ populate (metrics→archive、None 含む)。schema 66→69 列。
- [ ] _tournament 経路も連続値反映。

### リスク
低-中。default OFF で bit-exact。連続値の lex 比較は -inf guard で安定。観測列追加は schema 列数変更 (test 更新)。

## Run 89 実行パラメータ
| パラメータ | 値 |
|-----------|-----|
| --cross-pair-enable | 有効 |
| --cross-pair-selection-pressure | 有効 (連続値化済) |
| warmstart-ratio | 0.1 (motif=R86) |
| seed | 68 (R88 bool / R87 OFF と A/B) |

> R89: cross_pair_aggregate_fitness/cross_pair_mean_sharpe の median と **gen 傾き** (R88 bool 平坦 vs R89 連続で上昇するか) + **max mean_sharpe_cross** (0.15 近傍か=天井検証) + ii_lite_pass=True>0 (受入基準) を確認。頭打ち (median 上昇も mean_sharpe_cross<<0.15) なら単一ペア学習の天井確定 → cycle 8 multi-pair training。

## Codex design-review Round 1: REQUEST_CHANGES → 反映

### ★ Critical: selection_key_schema bump (実験識別)
bool 版は pressure 有効時 `v3_4_cross_pair_pressure` を出力。連続値版は **`v3_5_cross_pair_pressure_continuous`** に bump し R88(bool)/R89(continuous) を識別可能に。
- `_write_reports` の `selection_key_schema` 分岐: pressure effective かつ continuous なら `v3_5_cross_pair_pressure_continuous`、OFF なら `v3_3`。(bool 経路は破棄するため v3_4 は出さない。)

### Warning1: margin_threshold 死に設定 → fail-closed
連続値経路では margin_threshold 不使用。`__post_init__` (CrossPairConfig) で `selection_pressure=True かつ selection_pressure_margin_threshold != 0.0` を **ValueError fail-closed** (「continuous 化で threshold は無効、0.0 にせよ」)。サイレント無視を防ぐ。

### Warning2: 天井判定は複数 seed
R89 単一 seed の max(mean_sharpe_cross) 未達だけで「単一ペア学習の天井」を断定しない。**R89(seed68) + 追加 seed69 の 2 run で max(mean_sharpe_cross) を確認**してから天井確定 → multi-pair へ。

### Suggestion 反映
- pair_failure 監視列 `cross_pair_pair_failure_count` (metrics["pass_criteria"] or reasons 由来) を観測列に追加 (aggregate 上昇の偽陽性=pair_failure で集約値が壊れるケース検知)。観測専用。→ scope 次第、Codex Round2 で要否最終確認 (まず 3 pass 条件列 + これで 4 観測列)。
- test 更新: test_cross_pair_selection_pressure (bool→continuous)、test_archive schema 列数/nullable。

## Codex design-review: REQUEST_CHANGES → 反映済 (Round 2 で確認)

## Codex design-review: APPROVED (Round 2)
設計は APPROVED。実装5ステップ: (1)_selection_key を cp_val連続値置換 (2)selection_key_schema v3_5_cross_pair_pressure_continuous (3)CrossPairConfig.__post_init__ で selection_pressure&threshold!=0.0 ValueError (4)archive に cross_pair_mean_sharpe/min_sharpe/target_ratio/pair_failure_count 追加 (5)test_cross_pair_selection_pressure(bool→continuous)+test_archive(schema列数66→70)更新。
