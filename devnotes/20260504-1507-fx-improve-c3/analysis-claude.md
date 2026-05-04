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
