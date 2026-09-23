# 詳細設計: Run 88 施策 (cycle 6: cross-pair in-loop selection pressure)

## 使命・制約
mission 個体を多ペア汎化させる。GA 選択に cross-pair 汎化シグナルを弱く注入し、in-sample 過学習(0/599 汎化)から脱却。default OFF で挙動完全不変(selection_score bit-exact)。閾値緩和なし(加点のみ)。メタ過学習ガード: cross_pair_margin は Structural シグナル(Reactive Parametric でない)。

## 真因 (cycle 6 確定)
GA fitness_pen = EUR_JPY in-sample sharpe のみ。cross-pair は最終評価でのみ計算され GA 選択に汎化シグナルが入らない → 0/599 汎化(margin median -1.37)。

## ★ 設計の核 (新規 eval 不要) — 【Codex Round1 Critical 訂正】
R87 で cross-pair は `cross_pair.enable=True` 時に evaluate_genome 内で Stage B pass 個体全件で既に計算済。GenomeEntry(IndividualCacheEntry) には未伝搬。
→ **既計算の cross-pair シグナルを selection_score へ伝搬するだけ**。新規 eval なし、コスト R87 同等。

### ★ シグナル源の訂正 (Codex Round1 Critical 1)
当初案の `mission_signed_margin_c_shadow/_b_shadow` は **cross-pair でなく canonical shadow (Stage B IS / Stage C base) の in-sample 系メトリクス** (archive.py:156, stage_gate.py:2321)。これを使うと **in-sample margin を注入してしまい根本原因に直撃しない** (Codex 反証仮説: R88 ON でも ii_lite_pass 改善せず)。
→ 真の cross-pair シグナル = **`CrossPairResult.metrics["aggregate_fitness"]`** (cross_pair.py:369、連続値 F = mean − λ·std)。これを archive 列に保存し row→cache→selection へ伝搬する。
- 追加調査(次): CrossPairResult.metrics の正確なキー (`aggregate_fitness` / `min_sharpe` / `mean_sharpe`) と、cross-pair payload→archive 列保存箇所 (新規列 `cross_pair_aggregate_fitness` を GENOMES_SCHEMA + 書込経路に追加、4 段セット)。これは「新規 eval なし」だが「新規 archive 列 + 4 段書込」を伴う (T109 同様の sidecar/schema 追加パターン)。

### target_metric / failure_mode / causal_path / falsification / success_criterion
- target_metric: ii_lite_pass 率 / mission_signed_margin_c_shadow の baseline(R87)比改善、汎化個体(ii_lite_pass=True)>0。
- failure_mode: 0/599 汎化 = GA 汎化探索圧ゼロ。
- causal_path: cross-pair margin を selection_score に弱く反映 → 汎化寄りの個体が選択で残り繁殖 → 世代を経て margin 分布が正方向シフト・ii_lite_pass=True 出現。
- falsification: R88(ON)で ii_lite_pass 率/margin が R87 比改善せず or 汎化個体=0 → 施策無効、ロールバック。
- success_criterion: R88 で ii_lite_pass=True>=1 or mission_signed_margin_c_shadow median が有意改善 (e.g. -1.37 → -1.0 以上)。

## 変更箇所

### 1. config (`src/alpha_factory/cross_pair.py` CrossPairConfig)
- `selection_pressure: bool = False` (default OFF=selection_score 不変 bit-exact)。`cross_pair.enable=True` が前提 (margin 計算に必要)。
- `selection_pressure_margin_threshold: float = 0.0` (tie-break の margin 閾値、Principled: 正 margin=cross-pair 寄与ありを優遇)。
- `_build_cross_pair` (config.py:607) に `_strict_bool(raw.get("selection_pressure"), False)` + threshold 読込。
- `__post_init__`: selection_pressure=True かつ enable=False なら warning (margin 計算されないため無効) — fail-soft (raise でなく warn、default OFF 不変)。

### 2. CLI (`run_ga.py`)
- `--cross-pair-selection-pressure` (store_const True default None) + `_args_to_overrides` の cross_pair section に `selection_pressure`。

### 3. IndividualCacheEntry (`run_ga.py:~160`)
- `cross_pair_margin: float | None = None` 追加 (pareto_* と同様の optional)。
- selection_score は **純粋保持** (config 非依存)。反映は _selection_key で行う (下記)。

### 3.5. 新規 archive 列 `cross_pair_aggregate_fitness` (Codex Round1 Critical 1)
- cross_pair payload (CrossPairResult.metrics["aggregate_fitness"]) を archive 列に保存。GENOMES_SCHEMA 定義 + _create_row_template 初期値(None) + cross-pair 結果書込箇所 + flush の 4 点セット (T109 schema 追加パターン踏襲)。enable=False では None。

### 4. cache 構築 (`run_ga.py:1206` IndividualCacheEntry(...))
- `cross_pair_margin=_coerce_optional_float(row.get("cross_pair_aggregate_fitness"))` を追加 (cross-pair 実測シグナル)。
- ★ fallback は `or` 禁止 (Codex Round1 Critical 2: 0.0 偽扱い/NaN 真扱いで壊れる)。`_coerce_optional_float` 後 `is not None` で明示。本設計は単一列 (cross_pair_aggregate_fitness) のみなので fallback 不要。
- ★ 4 段伝搬 (Codex impl-review 重点): cross_pair payload → archive 列 cross_pair_aggregate_fitness → row → IndividualCacheEntry.cross_pair_margin → _selection_key。

### 5. _selection_key (`run_ga.py:255`) — selection_pressure 反映
現状: `_selection_key(entry, fallback)` が entry.selection_score (10-tuple) or _legacy を返す。
変更: `_selection_key(entry, fallback, selection_pressure: bool = False, margin_threshold: float = 0.0)` に拡張。
- selection_pressure=False (default): **現状の 10-tuple をそのまま返す (bit-exact)**。
- selection_pressure=True: 10-tuple の fold_robust(9要素目) と fitness_pen(10要素目) の間に `int(entry.cross_pair_margin is not None and entry.cross_pair_margin > margin_threshold)` を挿入 → 11-tuple。fold_robust より下位・fitness_pen より上位 = 「同 fold_robust なら cross-pair 寄与ある個体を fitness_pen より優先」= 弱い tie-break 圧。
- ★ 呼出側 thread (Codex Round1 Critical 3): `_select_best`(1234) / `_breed_next_gen`(960,989) / 1236 **に加え `_tournament`(864) にも必須** (漏れると elite だけ圧が乗る不整合)。`_selection_key` を **keyword-only 引数** (`*, selection_pressure=False, margin_threshold=0.0`) 化して thread 漏れを型で防ぐ。cfg.cross_pair から各経路へ伝搬。

### default bit-exact 保証 (最重要)
- selection_pressure=False で _selection_key は現行 10-tuple をそのまま返す (新要素挿入なし)。cross_pair_margin フィールド追加は selection_score property に影響しない (property は margin を見ない)。∴ rng/selection/population 完全不変。既存テスト全 pass が条件。

### テスト計画
- [ ] CrossPairConfig.selection_pressure default False / _build_cross_pair 読込 / threshold default 0.0。
- [ ] IndividualCacheEntry.cross_pair_margin default None。
- [ ] ★ bit-exact: selection_pressure=False で _selection_key が現行 10-tuple と完全一致 (cross_pair_margin 設定有無に依らず)。既存 run_ga_parallel pass。
- [ ] selection_pressure=True で 11-tuple、margin>threshold 個体が同 fold_robust の低 margin 個体より上位 (順序テスト)。
- [ ] cache 構築で row.mission_signed_margin_c_shadow → cross_pair_margin populate (fallback 含む)。
- [ ] selection_pressure=True & enable=False で warning (margin None → tie-break 要素 0 で実質無圧、壊れない)。

### リスク
- 中。default OFF で bit-exact。リスクは _selection_key の thread 漏れ (呼出箇所 4 つ全てに渡す) / margin の符号意味取り違え (大が良い=正が汎化寄り)。コストは R87 同等 (新規 eval なし)。
- 選択圧が弱すぎて効かない可能性 → R88 falsification で検証 (改善なければ tie-break 位置を上げる or 将来 fitness ブレンド)。

## Run 88 実行パラメータ
| パラメータ | 値 |
|-----------|-----|
| instrument | EUR_JPY |
| --cross-pair-enable | 有効 (margin 計算に必要) |
| --cross-pair-selection-pressure | 有効 |
| warmstart-ratio | 0.1 (motif=R86、mission 母集団確保) |
| seed | 68 と 69 (A/B、vs R87 baseline) |
| pop/gen | 96/60 |

> R88(ON) で ii_lite_pass 率 / mission_signed_margin_c_shadow が R87(同 seed, pressure OFF) 比改善するか、汎化個体>0 が出るかを A/B 検証。改善なければロールバック。

### Warning 反映 (Codex Round1)
- W1: summary に `selection_key_schema`(pressure ON 時 `v3_4_cross_pair_pressure`) + effective selection_pressure flag/threshold を記録 (run_ga.py:1582 summary + generate_run_report.py:945 観測整合)。
- W2: 起動時 `effective_selection_pressure=true/false reason=...` を log/summary 必須記録 (pressure=True&enable=False → false。nsga2_selection_enabled=True 時も pressure 実質 no-op のため明示警告)。

## Codex design-review: APPROVED (Round 2)
Round1 [Critical] 3件反映 (シグナル源訂正=aggregate_fitness / or fallback 廃止 / _selection_key thread+keyword-only)。
Round2 [Warning] 2件 (実装で反映):
- W1: `_resolve_cross_pair_selection_pressure(cfg) -> tuple[bool, str]` 単一 helper を作り、effective_bool/reason を log・summary・selection 全経路で使用 (pressure=True でも enable=False / nsga2_selection_enabled=True なら no-op の判定を一元化)。
- W2: summary の selection_score 表示は手組みでなく実 `_selection_key(best_entry, fallback, selection_pressure=effective, margin_threshold=...)` の戻り値を list 化、schema を v3_3 / v3_4_cross_pair_pressure で分岐。
Suggestion: bool tie-break で初回可。R88 で cross_pair_aggregate_fitness の p25/median/p75 + >threshold 比率を観測。効かなければ次は連続値を同位置に。
CrossPairResult.metrics キー確認済 (cross_pair.py:374): aggregate_fitness/mean_sharpe/min_sharpe 存在。
