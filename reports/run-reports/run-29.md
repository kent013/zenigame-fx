# Run 29 — run_20260504_061526

**Generated**: 2026-05-04T06:15:26.960199+00:00
**dataset_epoch_id**: `epoch_20251001_20260401`
**Dataset**: EUR_JPY `2025-10-01T00:00:00+00:00` → `2026-04-01T00:00:00+00:00` (bars=183403)
  - bars_stage_a: 86400
  - bars_stage_b: 183403
  - bars_holdout: 20457

## 使命判定

未達

- ❌ **sharpe**: 0.11344191310914063 / threshold 1.0
- ❌ **total_pnl**: 0.0 / threshold 50000.0
- ✅ **max_drawdown_pct**: 0.0 / threshold 20.0
- ✅ **trade_count**: 76 (range 50〜5000)

## GA 設定

- population_size: 40
- generations: 15
- mutation_rate: 0.3
- crossover_rate: 0.7
- tournament_size: 3
- elite_count: 2
- max_depth: 4
- fitness_metric: sharpe
- seed: None

## Best 個体

- name: `g15_i26`
- generation: 15
- fitness: **0.09844191310914063**
- fitness_finite: ✅
- stage_a_pass: ✅
- stage_b_pass: ❌
- stage_c_pass: ❌
- trade_count: 76
- total_pnl: 0.0
- sharpe: 0.11344191310914063
- sortino: —
- calmar: —
- max_drawdown_pct: 0.0

**Archive 補足情報**:
- lane_id: tier1_EUR_JPY
- instrument: EUR_JPY
- fold_sign_ratio: 0.2500
- dsr: —
- ii_lite_pass: —
- n_nodes: 3
- active_clause: 1

## Stage 通過数

- 全 archive 行数: 640
- Stage A pass: 241
- Stage B pass: 0
- Stage C pass: 0

## Lane 別落下分布

| lane_id | total | A | B | C |
|---------|-------|---|---|---|
| tier1_EUR_JPY | 640 | 241 | 0 | 0 |

## Pair 別落下分布

| instrument | total | A | B | C |
|------------|-------|---|---|---|
| EUR_JPY | 640 | 241 | 0 | 0 |

## active_clause / n_nodes 分布

- active_clause: n=640, mean=0.9984, median=1.0000, std=0.0395, min=0, max=1
- n_nodes: n=640, mean=2.8703, median=3.0000, std=0.9522, min=1, max=4

## mission_score 分布 (T043 / observation only)

> live_criteria 4 軸 (sharpe/total_pnl/max_drawdown/trade_count) の soft 合算スコア (幾何平均、[0.1, 1.0])。GA fitness や stage_c.passed には 影響しない (詳細: docs/alpha_factory/mission-score.md)。

- mission_score=計測対象 0 件 (Stage C base 評価で Sharpe を出した 個体が無いため未計測)

## fold_sign_ratio / dsr 分布

- fold_sign_ratio: n=241, mean=0.3122, median=0.2500, std=0.1445, min=0.0000, max=0.7500
- dsr: n=0
- n_fold_effective (Stage A pass): n=241, mean=4.4689, median=4, std=1.7618, min=0, max=9
- positive_fold_ratio_effective (Stage A pass): n=240, mean=0.5694, median=0.6333, std=0.1624, min=0.0000, max=1.0000

## Stage B failure reason 集計

- Stage A pass = 241, Stage B pass = 0, failures = 241 (primary_sum = 241)

### Primary reason (先頭 reason、合計 = failures)

| reason | count |
|--------|------:|
| `no_folds` | 0 |
| `insufficient_folds` | 0 |
| `all_folds_unavailable` | 0 |
| `stage_b_window_underfilled` | 0 |
| `median_oos_sharpe<min` | 241 |
| `positive_fold_ratio<min` | 0 |
| `stage_b_pre_flight_underfilled` | 0 |
| `unknown_reason` | 0 |
| `other` | 0 |

### Any reason incidence (全 reason、合計 >= failures)

| reason | count |
|--------|------:|
| `no_folds` | 0 |
| `insufficient_folds` | 0 |
| `all_folds_unavailable` | 1 |
| `stage_b_window_underfilled` | 0 |
| `median_oos_sharpe<min` | 241 |
| `positive_fold_ratio<min` | 241 |
| `stage_b_pre_flight_underfilled` | 0 |
| `other` | 0 |

## Cross-pair shadow 集計

- runtime mode: skipped_single_instrument
- ii_lite_pass: True=0, False=0, None=640

## Graduation

- archive graduated: 0
- summary.graduation_count: 0

## Feasibility 集計

- selection_score schema: `v3_1_stage_b_priority`
- trade_count=0 個体比率: 2.3% (15/640)
- best 個体 trade_count: 76
- best 個体 feasibility: ✅

## Stage A provenance 分布 (T033 / sidecar)

> Stage A 落ち個体の `total_pnl_stage_a` 分布を可視化 (`reports/run-reports/run-{N}/diagnostics/stage_a_provenance.parquet`)。archive `total_pnl=0.0` が「Stage A 落ち = 投影仕様」「実 PnL=0」「コスト過大」のいずれかを切り分けるための観測指標 (詳細: docs/alpha_factory/diagnostics-sidecar.md)。

- sidecar 行数: 640
- metric_stage 分布: stage_a_evaluated=241, stage_a_only=399
- (1) Stage A 落ち全体 `total_pnl_stage_a` 分布: n=399, mean=-429062.8571, median=-128750.0000, std=459937.3223, min=-1001700.0000, max=13360.0000
- (2) Stage A 落ち かつ trade_count>0 の `total_pnl_stage_a` 分布 (n=384): n=384, mean=-445823.1250, median=-147735.0000, std=460796.6994, min=-1001700.0000, max=13360.0000
  - うち PnL=0 個体: 0 件 (取引したのに PnL=0 = Run 9 監査の対象観測)
- (3) Stage A 通過個体 `total_pnl_stage_a` 分布 (n=241): n=241, mean=13087.8423, median=14400.0000, std=7197.5816, min=-170.0000, max=24100.0000

## Archive Top-5 個体一覧

> Best とは別物です。`fitness_pen` 単独降順。Best は (feasible, -violation, stage_b_pass, stage_c_feasible, stage_c_pass, stage_b_pass, stage_a_pass, fitness_pen) の辞書式 (v3.1_stage_b_priority, T046)。

| rank | name | gen | lane | instrument | fitness_pen | fitness_raw | A | B | C | trade_count | sharpe |
|-----:|------|----:|------|------------|------------:|------------:|---|---|---|----:|-------:|
| 1 | `g8_i22` | 8 | tier1_EUR_JPY | EUR_JPY | 0.1300 | 0.1480 | ✅ | ❌ | ❌ | 36 | — |
| 2 | `g14_i22` | 14 | tier1_EUR_JPY | EUR_JPY | 0.1025 | 0.1205 | ✅ | ❌ | ❌ | 47 | — |
| 3 | `g15_i26` | 15 | tier1_EUR_JPY | EUR_JPY | 0.0984 | 0.1134 | ✅ | ❌ | ❌ | 76 | — |
| 4 | `g14_i7` | 14 | tier1_EUR_JPY | EUR_JPY | 0.0978 | 0.1128 | ✅ | ❌ | ❌ | 73 | — |
| 5 | `g15_i0` | 15 | tier1_EUR_JPY | EUR_JPY | 0.0978 | 0.1128 | ✅ | ❌ | ❌ | 73 | — |

## 収束履歴

| gen | best_fitness |
|-----|--------------|
| 0 | -0.036400917418168845 |
| 1 | -0.03187463278409085 |
| 2 | -0.028766980329463156 |
| 3 | -0.028766980329463156 |
| 4 | -0.01827794415877892 |
| 5 | -0.012139240554125883 |
| 6 | 0.025235258927940145 |
| 7 | 0.06525119960765778 |
| 8 | 0.12997983968825172 |
| 9 | 0.08801975144598378 |
| 10 | 0.08801975144598378 |
| 11 | 0.09254507769205857 |
| 12 | 0.08801975144598378 |
| 13 | 0.088583359003194 |
| 14 | 0.1025384183175071 |
| 15 | 0.09844191310914063 |

## 分析

### analysis-claude.md

# RUN run_20260504_055856 (run-28) 分析（Claude 自己分析、 cycle 3）

**作成日時**: 2026-05-04 15:08 JST
**前提**: cycle 1 (Run-28 = run_20260504_043138) で Stage A 突破 → cycle 2 (Run-29 = run_20260504_055856) で完全退行
**cycle 3 主題**: **calibrate-gate 振動現象の解消** = cycle 1 best state 復元

## 観察事実 (Facts)

### F1. Run-29 全壊滅 (= cycle 2 退行)

- stage_a_pass: 0 / 640 (Run-28 142 から退行)
- best fitness_pen: -0.003342 (Run-28 +0.098 から退行)
- best generation: 5 / plateau_length: 11 (= gen 5 から best 不変、 GA 進化停止)
- trade_count median: 3415 (Run-28 55 から over-trading 復帰)
- diagnosis: **P2 high** (= penalty 支配)
  - raw_max=0.0057、 raw>0 個体 62 個 全て penalty で潰されている

### F2. calibrate-gate history (= 振動現象)

```
Run-27 (cycle 0): threshold=0.0      → actual_pass=0.0%   → loosen → new=-0.0172
Run-28 (cycle 1): threshold=-0.0172  → actual_pass=41%    → tighten → new=0.0128 (clamped by max_delta)
Run-29 (cycle 2): threshold=0.0128   → actual_pass=0%     → loosen 提案 (再振動)
```

= **dead-band tolerance=0.05 / max_delta=0.03 が振動抑制不全**。 0%/41% が target=15%±5% を大きく外れる。 制御則が安定値に収束していない。

### F3. cycle 1 vs cycle 2 の trade pattern 大幅変動 (= GA 戦略空間の不連続)

| metric | Run-28 (threshold=-0.0172) | Run-29 (threshold=0.0128) |
|---|---|---|
| stage_a_pass | 142 / 640 (22%) | 0 / 640 (0%) |
| best fitness_pen | +0.098 | -0.003 |
| trade_count median | 55 (low-trade) | 3415 (over-trading) |
| trade_sharpe_raw max | 0.160 | 0.006 |
| raw_positive_count | 139 | 62 |
| diagnosis | INCONCLUSIVE | P2 high |

= **同 GA / 同 dataset で threshold 設定により集団 trade pattern が劇的に変動**。 GA 戦略空間に「low-trade attractor」 「over-trade attractor」 の 2 極があり、 threshold が境界を超えると pop が一方に転落。

## 解釈・推論 (Interpretations)

### I1 (Critical, 反証可能性 高): calibrate-gate 振動 = dead-band/max_delta 設計の不備

- 観察 F2: 0% → 22% → 0% の振動 pattern
- dead-band=0.05 (= ±15%) を 0%/41% が大きく外れ、 制御則が「強い修正」 を発動
- max_delta=0.03 で clamp しても、 GA 戦略空間の不連続性 (I2) が振動を増幅
- **反証**: 単純に threshold を Run-28 best (-0.0172) に固定 + calibrate-gate 無効化で振動が止まり、 stage_a_pass ~= 142 が再現すれば I1 支持

### I2 (Critical, 観察事実): GA 戦略空間に 2 攻撃子 (= low-trade vs over-trade)

- F3: 同 GA で threshold 設定により集団が「median 55」 か「median 3415」 に二極化
- = trade_count distribution が連続的でなく、 threshold が境界 → 跳躍する
- これは primitive 表現力 / GA 探索 dynamics の構造的特徴
- **反証**: threshold を Run-28 値に戻しても population trade pattern が再現しない場合、 GA seed variance が支配的

### I3 (Notable, 重要 learning): improvement loop の自動制御メカニズム自身が「真の root cause」 候補

- cycle 1: 仮説 P1/P2/P3 全部外れ、 真は **threshold 設計**
- cycle 2: 仮説 I1 反証、 真は **time-concentrated 取引**
- cycle 3: **calibrate-gate という自動制御機構自身が改善ループを阻害**
- = improvement loop の「メタレベル」 で root cause が浮上

## 次サイクル候補 (= cycle 3 で実施)

### [Critical] calibrate-gate 一時無効化 + threshold 手動固定 (= cycle 1 baseline 復元)

- **target_metric**: Run-30 で stage_a_pass ≈ 142 / best fitness_pen ≈ +0.098 の再現
- **failure_mode**: calibrate-gate 振動で集団 trade pattern が劇的変動、 cycle 1 良 result が失われた
- **causal_path**: dead-band tolerance 不適切 → threshold 大幅変動 → GA 戦略空間の attractor 切替 → 集団壊滅
- **falsification**:
  - (a) 再現せず stage_a_pass < 50: GA seed variance が支配的、 calibrate-gate は副次要因
  - (b) 再現するが trade pattern が異なる: GA 戦略 attractor が history dependent
  - (c) 再現する: I1 支持、 calibrate-gate 設計改善が次の打ち手
- **success_criterion**: Run-30 で stage_a_pass >= 100 (= cycle 1 と同等水準)
- **変更分類**: Structural (= 振動メカニズムの一時停止 + baseline 復元)

### 実装 spec

config 修正 (= 2 箇所):
```yaml
stage_gate:
  stage_a:
    threshold: -0.0172    # cycle 3: 0.0128 → -0.0172 (cycle 1 best 復元)
    calibrate:
      enabled: false      # cycle 3: true → false (振動停止)
```

### 補助監視
- Run-30 archive で trade_count distribution を確認 (= low-trade attractor へ収束したか)
- Run-30 best が Run-28 best (g14_i29) と同型 genome か (= 探索が同 attractor に到達したか)

## 全体判定: **PROGRESSING (with regression in cycle 2)**

cycle 1 で大前進、 cycle 2 で退行。 cycle 3 で baseline 復元 + 振動メカニズム停止 を試行。

**北極星距離**: cycle 1 best trade_sharpe_raw=0.16 / live_criteria sharpe_min=1.0 = 6 倍改善余地 (cycle 1 時点)。 cycle 2 退行で遠ざかったが、 cycle 3 で復元できれば再び 6 倍に近づく。

