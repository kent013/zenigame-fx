# 改善計画 + 詳細設計: Run 58 → Run 59 (cycle 6)

## 合議ステータス: CONSENSUS REACHED (Round 1)、 APPROVED (案 Y seed sweep)

## Codex 推薦戦略 cycle 6-23 全体配分

| cycle | 内容 | 変更分類 |
|-----|------|----|
| 6-8 | seed sweep (44→45→46) | Principled (探索独立性) |
| 9-11 | 軽量観測 (regime セグメント分析) | Structural (観測) |
| 12-15 | DSR 配線復帰 (4 cycle 段階実装) | Structural |
| 16-20 | 追加 seed sweep (47-50) + elite collapse 緩和 | Principled |
| 21-23 | 縮小シグナル数 試験 RUN | Principled |

mission 達成見通し (Codex Q4): 20 RUN 内では困難、 Sharpe 0.4-0.6 底上げが現実目標。 live_criteria 達成は cycle 8 以降の structural 施策成功時のみ射程。

## 施策 C6-1: seed sweep continuation (seed=44)

### 内容

- run_ga.py 引数 `--seed 43` → `--seed 44`
- dataset / config / コード 変更なし

### target_metric / failure_mode / causal_path / falsification / success_criterion

- **target_metric**: fp 分布の variance、 Run 57 (seed=42)/58 (seed=43)/59 (seed=44) の 3 サンプル variance プロファイル
- **failure_mode**: cycle 5 で Run 57/58 のみで variance 推定、 multiple sample で代表値か outlier かの判別困難
- **causal_path**: 単一 seed → 確率変動含む 1 試行 → 多サンプルで variance 推定 → 後続 cycle structural 施策の効果判定 base data
- **falsification**:
  - Run 59 の Stage B pass / fp / completion time が Run 57/58 と全く同じ → seed が探索に効いていない bug 仮説
- **success_criterion**:
  - Run 59 完走 (smoke-mode opt-in なし)
  - Run 57/58 と異なる Best 個体出現
  - Stage A/B/C 通過数の 3 サンプル variance データ取得

### 変更ファイル

なし (run 引数のみ)

### 波及変更

なし

### 実装手順

1. `/zenigame-fx-run-alpha-factory --instrument EUR_JPY --population-size 96 --generations 60 --mutation-rate 0.5 --seed 44 --max-workers 2`
2. Run 59 完走確認 (推定 70-211 分、 seed 依存で variance 大)
3. summary.json + archive Parquet で 4 点整合確認
4. `/zenigame-fx-run-report 59 --analysis-dir devnotes/20260509-2326-fx-improve`

### Run 59 実行パラメータ

| パラメータ | 値 | R58 からの変更 |
|-----------|-----|-------------|
| seed | **44** | **43 → 44** |
| 他 | 変更なし | - |

### Codex 全体判定: APPROVED (案 Y)、 1 round
