# Concept: stage-gate-implementation

## 目的

Stage A / B / C ゲートを `src/alpha_factory/stage_gate.py` に実装。

## 設計

### Stage A — Fast Screen

- 期間: 直近 60 営業日
- 通過率目標: 15%（10-20% 許容）
- ペナルティ: `α_A = 0.03`
- 明らかに悪い個体を除去する軽量フィルタ

### Stage B — Full IS + WF-OOS

- 期間: 過去 18 ヶ月
- Walk-forward: train 120 日 / test 20 日 / step 20 日 / embargo 1 日
- 通過基準:
  - median OOS Sharpe ≥ 0.20
  - 正 fold 比率 ≥ 60%
  - DSR ≥ 0（初期は monitor 可）

### Stage C — Live Criteria

- holdout 期間で live_criteria 評価
- 追加チェック:
  - (ii-lite) gate（shadow / hard）
  - spread × 1.5 stress
  - session 跨ぎ遵守（強制クローズ）
  - trade_count レンジ（50-5000）

## 実装

```python
@dataclass
class StageResult:
    stage: Literal["A", "B", "C"]
    passed: bool
    metrics: dict
    reason_if_failed: str

def evaluate_stage_a(genome, bars_60d, ...) -> StageResult: ...
def evaluate_stage_b(genome, bars_18m, wf_config, ...) -> StageResult: ...
def evaluate_stage_c(genome, bars_holdout, live_criteria, ii_lite_cfg, ...) -> StageResult: ...
```

## テスト

- 通過条件を満たす synthetic genome が Stage A → B → C 通過
- 各 Stage で閾値境界のテスト
- DSR / fold sign が正しく計算される

## 前提

- `statistics-dsr-bootstrap` 完了後（DSR / bootstrap CI / fold sign）

## 優先度・モード

- Priority: Critical
- Mode: standalone
- テーマ: stage-gate
