# 詳細設計: Run 14 施策 (cycle 3)

## 使命・制約 (絶対遵守)
- 使命: live_criteria 全指標同時充足
- FX 固有制約: イントラデイ前提 / ロング・ショート両方向許容 / スワップ・スプレッド反映
- 禁止事項 1〜7

## 施策一覧

| # | 施策名 | 変更ファイル | target_metric |
|---|--------|------------|--------------|
| C1 | WF パラメータ短縮 | `config/alpha_factory/default.yaml` | Stage B insufficient_folds_rate 100%→≪50% |

## C1: WF パラメータ短縮

### 変更前
```yaml
stage_b:
  wf_train_days: 120
  wf_test_days: 20
  wf_step_days: 20
  wf_embargo_days: 1
```
合計最小観測日数: 120+1+20 = **141 日**

### 変更後
```yaml
stage_b:
  wf_train_days: 60
  wf_test_days: 10
  wf_step_days: 10
  wf_embargo_days: 1
```
合計最小観測日数: 60+1+10 = **71 日**

Stage B window 観測日数 (~127 日) > 必要日数 (71 日) → fold 成立可能。

### 期待 fold 数
- Run-13 dataset (10/01〜04/01 = ~127 観測日相当の Stage B window)
- 71 日で 1 fold → step=10 で進行 → (127-71)/10 ≈ 5 fold + 1 = **6 fold 程度**
- 既存 `make_wf_folds` は train_days+embargo+test_days <= n_unique_dates で fold 算出
- 旧 1 fold (insufficient_folds で reject) → 新 ~6 fold (median/positive で評価可能)

### 反証可能性 (C9)
- 反証条件: Run-14 で primary reason 首位が依然 insufficient_folds なら短窓化が無効 → H 棄却
- 副次反証: 別 reason (median_oos_sharpe<min) が首位化 → 探索品質問題に焦点移行 (cycle 4 以降)

### 波及変更
- AGENTS.md: なし (config 値変更のみ)
- skill: なし
- docs: stage-gates.md にも `wf_train_days=120 / wf_test_days=20 / wf_step_days=20` 既定値の記述があるが、本変更は **default.yaml の SSoT 上書き** で運用 (docs は次 cycle で同期更新)
- tests: なし (config 変更で挙動が変わるが既存テスト fixture は wf params をハードコードしているため影響なし)

### ルックアヘッドバイアス / パフォーマンスチェック
- 該当なし (config 値のみ)

### リスク
- **リスク 1 (高)**: 短窓化で OOS Sharpe の信頼区間が広がり、median/positive_fold の閾値で reject される可能性 → 反証で追跡
- **リスク 2 (中)**: 短窓 fold で「過学習しやすい」可能性 → Stage C (60 日 holdout) で検出される設計、Stage B 単独で OK 判断はしない
- **リスク 3 (低)**: SSoT 設計 (T035) 内の `wf_min_unique_dates(120,1,20)=141` ハードコード参照は config 変更で 71 になり連動

### テスト計画
- 既存テスト変更なし (config-only)
- Run-14 で reason 分布変化を観測

### Codex レビュー
合議 1 ラウンド圧縮。設計シンプル (config-only)、Codex 案 A の禁止事項チェック (値いじり化リスク → 目的を fold 成立に限定で回避) を反映。

## Run 14 実行パラメータ

| パラメータ | 値 | R13 からの変更 |
|-----------|-----|--------------|
| population_size | 96 | 変更なし |
| generations | 60 | 変更なし |
| instrument | EUR_JPY | 変更なし |
| ga.feasibility (T031) | 既定 | 変更なし |
| stage_b.wf_train_days | 60 | **120 → 60** |
| stage_b.wf_test_days | 10 | **20 → 10** |
| stage_b.wf_step_days | 10 | **20 → 10** |
| stage_b.wf_embargo_days | 1 | 変更なし |
| stage_b.median_oos_sharpe_min | 0.20 | 変更なし |
| stage_b.positive_fold_min | 0.60 | 変更なし |
