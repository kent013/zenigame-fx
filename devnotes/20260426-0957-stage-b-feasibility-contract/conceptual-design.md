# 概念設計: T041 Stage B Feasibility Contract

## 背景・問題定義

cycle 3 (Run-13) で `Stage B failure reason = insufficient_folds 100%` 単峰確認。
WF 必要観測日数 (`train_days + embargo_days + test_days`) > Stage B window 観測日数で構造的に fold 1 個しか作れず常に reject。

cycle 3 で WF パラメータ短縮 (60/10) で対症療法 (案 A) → fold 成立、しかし:
- cycle 4 (Run-14): gate 過剰で Stage A 全滅
- cycle 5 (Run-15): Stage A 復旧、median_oos_sharpe<min が新ボトルネック
- cycle 6+ (Run-16+): calibrate ratchet 副作用

**根本原因**: WF profile (train/test/embargo/step) は dataset window 観測日数と独立に設定されており、不整合発生時に fail-fast する仕組みがない。Stage B 全滅原因が観測されるまで気づけない。

## 使命整合性

- live_criteria 全達成のためには Stage B 通過が前提
- 現状は Stage B 構造的不成立 → Stage C / live_criteria 評価へ届かない
- 構造的 feasibility contract で「動かない原因 vs 性能問題」を明確化、改善ループを実効化

## 解決方針

### 案 1: Pre-flight Feasibility Check (推奨)
LaneManager の Stage B 評価開始時に以下を事前計算:
1. `max_folds = floor((n_unique_dates - train - embargo) / step)` ※ test_days 制約も加味
2. `min_folds_required` を config で指定 (default: 2)
3. `max_folds < min_folds_required` の場合、**fail-fast** で全 lane の Stage B を `stage_b_pre_flight_underfilled` reason で skip

### 案 2: WF Profile Dynamic Selection
複数 WF profile を YAML で定義し、`max_folds >= min_folds_required` を満たす最大 train 系を自動選択。
- 例: `[(120,1,20,20), (60,1,10,10), (30,1,5,5)]` 順に試行
- 選択結果を archive に記録し、profile 統計を集計可能化

### 採用方針
**案 1 を Phase 1**、**案 2 は Phase 2** で段階的実装。Phase 1 で fail-fast の構造を入れ、Phase 2 で profile 自動選択を載せる方が実装規模が小さく、副作用も少ない。

## 影響範囲

- `src/alpha_factory/swim_lane.py`: LaneManager に pre-flight check 追加
- `src/alpha_factory/walk_forward.py`: `compute_max_folds()` helper 追加
- `src/alpha_factory/config.py`: `StageGateConfig` に `wf_min_folds_required` 追加 (default: 2)
- `config/alpha_factory/default.yaml`: 新 config 追記
- `scripts/alpha_factory/generate_run_report.py`: known_codes に `stage_b_pre_flight_underfilled` 追加
- tests: 各層

## リスク・制約

- 既存の "後段で insufficient_folds" 経路と二重発火しないよう排他性を確保 (skip 後は fold 評価に進まない)
- `min_folds_required=2` がデフォで適切か → 設定可能化で運用調整余地確保
- 既存 archive parquet の reason_codes に `stage_b_pre_flight_underfilled` が増える → 後方互換性は前 fix (cycle 5) と同様 known_codes に追加で吸収

## Phase 1 と既存 T035 (cycle 3 で merged) の差別化

T035 は **既存 evaluate_stage_b 内部** での observability (n_fold_effective, reason_codes 永続化)。
T041 Phase 1 は **LaneManager レベル** での pre-flight (evaluate_stage_b に到達する前に判定)。
直交関係で重複なし。
