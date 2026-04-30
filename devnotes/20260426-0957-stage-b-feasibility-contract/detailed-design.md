# 詳細設計: T041 Stage B Feasibility Contract Phase 1

## 使命・制約 (絶対遵守)
- 使命: live_criteria 全達成
- FX 固有制約: イントラデイ / ロング・ショート両方向 / スワップ・スプレッド反映
- 禁止事項 1〜7

## 概念設計リファレンス
`devnotes/20260426-0957-stage-b-feasibility-contract/conceptual-design.md`

## 施策一覧

| # | 施策 | 変更ファイル | 優先度 |
|---|------|------------|--------|
| 1 | `compute_max_folds()` helper 追加 | `src/alpha_factory/walk_forward.py` | High |
| 2 | `StageGateConfig.wf_min_folds_required` 追加 | `src/alpha_factory/config.py` | High |
| 3 | default.yaml に `stage_b.wf_min_folds_required` 追記 | `config/alpha_factory/default.yaml` | High |
| 4 | LaneManager に pre-flight check 追加 | `src/alpha_factory/swim_lane.py` | Critical |
| 5 | known_codes に `stage_b_pre_flight_underfilled` 追加 | `scripts/alpha_factory/generate_run_report.py` | High |
| 6 | テスト 6 件追加 | `tests/alpha_factory/`, `tests/scripts/` | Critical |
| 7 | docs (stage-gates.md / terminology.md) 更新 | `docs/alpha_factory/` | Medium |

## 施策 1: `compute_max_folds()`

### 変更箇所
`src/alpha_factory/walk_forward.py` 末尾

### 変更後コード
```python
def compute_max_folds(
    n_unique_dates: int,
    train_days: int,
    embargo_days: int,
    test_days: int,
    step_days: int,
) -> int:
    """与えられた WF パラメータと観測日数で生成可能な fold 数の最大値を返す.

    `make_wf_folds` のループ条件 (`test_end_excl <= n_days`) と一致させる:
    - k 番目 fold の test_end_excl = step_days * k + train_days + embargo_days + test_days
    - test_end_excl <= n_unique_dates を満たす最大 k+1 を返す
    """
    fold_len = wf_min_unique_dates(train_days, embargo_days, test_days)
    if n_unique_dates < fold_len:
        return 0
    if step_days < 1:
        raise ValueError("step_days must be >= 1")
    return (n_unique_dates - fold_len) // step_days + 1
```

### テスト
- `test_compute_max_folds_returns_zero_when_underfilled`
- `test_compute_max_folds_matches_make_wf_folds_count`
- `test_compute_max_folds_step_progression`

## 施策 2: `StageGateConfig.wf_min_folds_required`

### 変更箇所
`src/alpha_factory/config.py` の `StageGateConfig` (T041 想定: 既存 `wf_train_days` の隣)

### 変更後コード
```python
@dataclass(frozen=True)
class StageGateConfig:
    # ... 既存 ...
    wf_train_days: int = 120
    wf_test_days: int = 20
    wf_step_days: int = 20
    wf_embargo_days: int = 1
    wf_min_folds_required: int = 2  # T041: pre-flight feasibility minimum
    # ... 既存 ...

    def __post_init__(self) -> None:
        # ... 既存 ...
        if self.wf_min_folds_required < 1:
            raise ValueError("stage_gate.wf_min_folds_required must be >= 1")
```

### loader 更新
`_build_stage_gate` 内で `b_raw.get("wf_min_folds_required", 2)` を kwargs に追加

### テスト
- `test_wf_min_folds_required_default_value`
- `test_wf_min_folds_required_invalid_zero`

## 施策 3: default.yaml

```yaml
stage_b:
  wf_train_days: 60
  wf_test_days: 10
  wf_step_days: 10
  wf_embargo_days: 1
  wf_min_folds_required: 2  # T041: pre-flight feasibility (max_folds<min なら全 lane で skip)
```

## 施策 4: LaneManager pre-flight check

### 変更箇所
`src/alpha_factory/swim_lane.py` の `run_generation`

### 既存 (T035 で追加した skip-path のすぐ前)
```python
lane_n_unique_dates = n_unique_dates(lane.bars_18m)
wf_min_dates = wf_min_unique_dates(...)
```

### 追加
```python
max_folds = compute_max_folds(
    lane_n_unique_dates,
    self._stage_gate_config.wf_train_days,
    self._stage_gate_config.wf_embargo_days,
    self._stage_gate_config.wf_test_days,
    self._stage_gate_config.wf_step_days,
)
preflight_underfilled = max_folds < self._stage_gate_config.wf_min_folds_required
```

### Stage A pass 後
```python
if preflight_underfilled:
    # T041: pre-flight で fold 不足判明、Stage B 評価せず明示 reason で skip
    b_result = StageResult(
        stage="B",
        passed=False,
        metrics={
            "stage": "B",
            "genome_name": genome.name,
            "n_bars": len(lane.bars_18m),
            "wall_time_seconds": 0.0,
            "payload": {
                "n_unique_dates": lane_n_unique_dates,
                "wf_min_unique_dates": wf_min_dates,
                "max_folds": max_folds,
                "wf_min_folds_required": self._stage_gate_config.wf_min_folds_required,
                "n_fold": 0,
                "n_fold_unavailable": 0,
                "n_fold_effective": 0,
                "oos_sharpes": (),
                "median_oos_sharpe": None,
                "positive_fold_ratio": None,
                "positive_fold_ratio_effective": None,
                "dsr": None,
                "is_full_sharpe": None,
                "is_full_total_pnl": None,
                "is_full_trade_count": None,
            },
        },
        reason_codes=("stage_b_pre_flight_underfilled",),
    )
elif lane_n_unique_dates < wf_min_dates:
    # T035 既存 skip-path
    b_result = StageResult(..., reason_codes=("stage_b_window_underfilled",))
else:
    b_result = evaluate_stage_b(...)
```

### 排他性
`max_folds < min_folds_required` (T041) と `n_unique_dates < wf_min_dates` (T035) は前者が後者を内包する (前者 True ⇒ 後者 True もありうる)。優先順位は **T041 を先に判定** (より informative)。

## 施策 5: known_codes 追加

```python
known_codes = (
    "no_folds",
    "insufficient_folds",
    "all_folds_unavailable",
    "stage_b_window_underfilled",
    "median_oos_sharpe<min",
    "positive_fold_ratio<min",
    "stage_b_pre_flight_underfilled",  # T041
)
```

## 施策 6: テスト

| ファイル | テスト | 内容 |
|---------|--------|------|
| test_walk_forward.py | test_compute_max_folds_returns_zero_when_underfilled | n_unique_dates < fold_len → 0 |
| test_walk_forward.py | test_compute_max_folds_matches_make_wf_folds_count | 実際の fold 数と一致 |
| test_walk_forward.py | test_compute_max_folds_step_progression | step による fold 数推移 |
| test_config.py | test_wf_min_folds_required_default_value | default=2 |
| test_config.py | test_wf_min_folds_required_invalid_zero | 0 で ValueError |
| test_swim_lane.py | test_stage_b_skipped_pre_flight_when_max_folds_below_min | pre-flight 動作確認 |
| test_generate_run_report_stage_b_reason.py | test_stage_b_reason_pre_flight_underfilled | known_codes に含まれる |

## 施策 7: docs

- `docs/alpha_factory/stage-gates.md`: Reason Code 表に `stage_b_pre_flight_underfilled` 追加
- `docs/alpha_factory/terminology.md`: `wf_min_folds_required` / `compute_max_folds` 用語追加

## ルックアヘッドバイアス・パフォーマンスチェック
- 該当なし (config + skip-path のみ、bar 計算なし)

## リスク
- T035 `wf_min_unique_dates` 経路と T041 `compute_max_folds` 経路の二重判定 → 排他順位を明示で回避
- min_folds_required=2 が gate 緩和すぎ/きつすぎ → 設定可能化で運用調整

## 実装モード: incremental
判断: 既存 schema 変更なし (reason_codes 文字列追加のみ)、影響範囲は LaneManager + walk_forward + config の 3 ファイル + テスト + docs。
