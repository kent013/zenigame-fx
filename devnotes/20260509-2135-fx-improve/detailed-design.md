# 詳細設計: Run 58 施策 (cycle 5)

## 使命・制約（絶対遵守）

`zenigame-fx-codex-review` 継承。 FX 固有制約のみ再掲: イントラデイ前提 / ロング・ショート両方向許容 / スワップ・スプレッドを fitness に反映。

## 施策一覧

| # | 施策名 | 変更ファイル | target_metric |
|---|--------|------------|--------------|
| C5-1 | 再現性 check (seed=43 で Run 58) | (実装変更なし、 run_ga.py 引数のみ) | fp 分布 variance / elite collapse 再現性 |

## 変更分類

**Principled Parametric (探索独立性)**: seed は GA 探索の独立試行を生成する手段。 同じ data / config / code で異なる seed → 戦略空間の independent draw。 メタ過学習に該当しない (config / 閾値の調整ではない)。

---

## C5-1: 再現性 check (seed=43 で Run 58)

### target_metric / failure_mode / causal_path / falsification / success_criterion

- **target_metric**: fp 分布の variance、 elite collapse 再現性
- **failure_mode**: Run 57 が新 baseline で 1 RUN のみ、 fp variance 不明、 elite collapse 悪化が seed 起因か構造起因か切り分けできない
- **causal_path**: seed=42 単一試行で得た Run 57 の指標 (fp / unique fp ratio / Stage 通過数) は GA 探索の確率変動を含む → Run 58 (seed=43) の独立試行で variance 推定 → 後続 cycle の施策評価で「効果か noise か」判別の base data 確保
- **falsification**:
  - Run 58 が Run 57 と完全同一結果 (Best 個体 / fp 分布) → 仮説 false (seed が探索結果に効いていない、 何か固定的な bias / hash 衝突等)
  - Run 58 で smoke-mode opt-in 必須 → 仮説 false (cycle 4 C1 の structural 修復に問題)
- **success_criterion**:
  - Run 58 完走 (smoke-mode opt-in なし)
  - Run 57 と異なる Best 個体が出現 (seed 効果 confirmed)
  - fp 分布 / unique fp ratio / Stage 通過数の差分を observability table に記録
  - elite collapse の再現性データ取得

### 変更箇所

- なし (config / コード / docs 変更なし)
- run 引数のみ: `--seed 42` → `--seed 43`

### 波及変更

- なし

### 現行コード

(変更なし)

### 変更後コード

(変更なし)

### ルックアヘッドバイアスチェック

該当なし (primitive 変更ではなく seed 変更のみ)

### パフォーマンスチェック

- 実行時間: Run 57 と同等 (約 211 分)
- メモリ: Run 57 と同等 (3GB 制約内)
- データ量: 変更なし

### テスト計画

- [ ] **既存テスト変更なし** (実装変更なし)
- [ ] 手動検証:
  - Run 58 を `--seed 43` で実行
  - smoke-mode opt-in なしで完走確認
  - Run 57 (seed=42) との Best 個体 / fp 分布比較データ取得
  - 比較レポートを cycle 5 Phase 1 (cycle 6 開始時の analyze-run) で作成

### リスク

- **R1**: Run 58 の Best 個体 fp が Run 57 より大幅悪化 → 「Run 57 は単発の lucky draw だった」evidence になる。 後続 cycle の施策設計に影響 (Stage B 期間自体が過酷で安定 fp 0.10 達成困難等)。 mission 達成の見通しが厳しくなる
- **R2**: Run 58 完走時間が Run 57 と乖離 (例 +50%) → 計算量が seed 依存で大きく変わる構造的問題の可能性
- **R3**: 何らかの理由で Run 58 が Run 57 と同一結果 → seed が探索に効いていない potential bug
- すべて R1-R3 は cycle 6 以降で対処すべき次の調査テーマであり、 cycle 5 内では reporting で完了

### 実装手順

1. `/zenigame-fx-run-alpha-factory --instrument EUR_JPY --population-size 96 --generations 60 --mutation-rate 0.5 --seed 43 --max-workers 2` を実行
2. Run 58 完走確認 (約 211 分)
3. summary.json + archive Parquet で 4 点整合確認
4. `/zenigame-fx-run-report 58 --analysis-dir devnotes/20260509-2135-fx-improve` でレポート生成

### Run 58 実行パラメータ

| パラメータ | 値 | R57 からの変更 |
|-----------|-----|--------------|
| instrument | EUR_JPY | 変更なし |
| population_size | 96 | 変更なし |
| generations | 60 | 変更なし |
| mutation_rate | 0.5 | 変更なし |
| seed | **43** | **42 → 43** (再現性 check の主目的) |
| max_workers | 2 | 変更なし |
| --allow-holdout-short | 不指定 | 変更なし |
| ZENIGAME_FX_SMOKE_TEST | 未設定 | 変更なし |
| dataset.start (config) | 2025-04-01 | 変更なし (cycle 4 C1) |
| dataset.end (config) | 2026-02-19 | 変更なし (cycle 4 C1) |

---

## 全体判定

cycle 5 確定施策 (C5-1) は **完全に実装変更なし**、 run 引数のみ変更。 Codex 設計レビューは形式的に 1 round で完結期待。 リスクは R1-R3 が後続 cycle の analyze テーマで完了。

C5-1 の `success_criterion` (Run 58 完走 + Run 57 と異なる Best 個体 + variance 計測) を確認後、 cycle 6 で DSR 配線復帰を本格実装 (Codex 推薦順序 1)。
