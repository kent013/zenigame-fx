# PR5: Stage B gate pfr_only opt-in 詳細設計

## 実装方針

### config (PR4 Phase4Config pattern を踏襲)

```python
@dataclass(frozen=True)
class Phase5Config:
    stage_b_gate_kind: Literal["legacy", "pfr_only"] = "legacy"
    # pfr_only mode 用 threshold (= positive_fold_ratio_effective_min)
    pfr_threshold: float = 0.4
```

`StageGateConfig` に `phase5_stage_b_gate_kind` / `phase5_pfr_threshold` 追加 (= 二重防御)。

### stage_gate.py evaluate_stage_b 分岐

```python
if stage_config.phase5_stage_b_gate_kind == "legacy":
    # 現状 gate (= median + positive_fold_ratio AND)
    if median_oos < stage_config.stage_b_median_oos_sharpe_min:
        reasons.append("median_oos_sharpe<min")
    if positive_ratio < stage_config.stage_b_positive_fold_min:
        reasons.append("positive_fold_ratio<min")
elif stage_config.phase5_stage_b_gate_kind == "pfr_only":
    # positive_fold_ratio_effective 単独 (median は observe-only)
    if positive_ratio_effective < stage_config.phase5_pfr_threshold:
        reasons.append("positive_fold_ratio_effective<min")
    # median は observe-only として log 出力するが gate 判定には使わない
```

### CLI

```bash
--stage-b-gate-kind {legacy,pfr_only}
```

### payload 拡張

`phase5_stage_b_gate_kind` / `phase5_pfr_threshold` / `phase5_median_observation` (= observe-only)

## 受入基準

- [ ] Phase5Config + StageGateConfig 4 段接続
- [ ] gate 分岐 + observe-only median 出力
- [ ] CLI `--stage-b-gate-kind`
- [ ] PR5 tests: helper + integration + config (~20 件)
- [ ] alpha_factory 全 pass
- [ ] 1 RUN smoke 計画 (= 別途 user 実行)

## smoke 合格条件 (Codex Y Round 4 確定)

- pfr_only mode で Stage B pass 数が legacy と同等以上
- Stage C 持続性 (= trade_sharpe_stage_c median) が legacy 以上
- 持続性悪化なら flag off

## コミット計画

- 1 コミット: `feat(stage_gate): Stage B gate pfr_only opt-in (PR5、 default OFF)`
