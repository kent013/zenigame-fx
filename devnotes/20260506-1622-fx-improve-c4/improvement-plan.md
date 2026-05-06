# 最終改善計画: Run 36 → Run 37 (cycle 4)

## 合議ステータス: CONVERGED (Round 0、 analyze 段階で両者一致)

## 確定施策一覧

| # | 施策名 | 内容 | 変更対象 | 優先度 | 変更分類 | target_metric | failure_mode | causal_path | falsification | success_criterion |
|---|--------|------|---------|--------|---------|--------------|-------------|------------|---------------|-------------------|
| **C1** | **fitness_pen に fold-aware penalty 追加** | fitness_pen 計算式に `- β·max(0, 0.4 - pfre_clamped)` を追加して GA 探索圧を fold 頑健性方向に向ける | `src/alpha_factory/stage_gate.py` (evaluate_stage_a 系) + 設定 (β default value) + 関連テスト | Critical | **Structural** (新項追加、 既存 fitness_pen の拡張) | Stage B pass count、 pfre_mean 後期 | fitness_pen 4 倍に伸びるが fold_sign は -20% で減少 (cycle 3 sidecar で verified) | GA 目的関数の robustness 報酬欠落 → 進化方向の不整合 | cycle 5 で「fitness_pen 上昇に同期して fold_sign / pfre 上昇」 が verified なら確証、 上昇しなければ別問題 | Stage B pass > 0 (主)、 pfre_mean 後期 > 0.4 (副) |

### C1 設計式

```python
# 現行 (run-36 まで)
fitness_pen = fitness_raw - alpha * size_norm

# cycle 4 拡張 (run-37 から)
pfre_clamped = clip(positive_fold_ratio_effective, 0, 1)  # NaN は 0 として扱う
fold_penalty = beta * max(0.0, 0.4 - pfre_clamped)
fitness_pen = fitness_raw - alpha * size_norm - fold_penalty
```

### 数値根拠

- β = 0.05 initial: 最大追加ペナルティ = β × 0.4 = 0.02
- 既存 α·size_norm 寄与は run-35 best で 0.0195 (= 0.243 - 0.222)
- → 追加 penalty は既存 size_norm penalty と同オーダー、 fitness_pen ranking を fold 軸で 1 階層動かせる
- 閾値 0.4 = Stage B 閾値 0.6 の 67% (ヘッドルーム確保、 過厳格回避)

### 注意点

- **実装条件 (Critical)**: pfre 値が Stage A 評価時点で利用可能でないと組み込めない。 Stage A 評価は trade-level であり pfre は WF fold 評価の結果なので、 **Stage A 評価時点では pfre は未確定**
- → 実装は **Stage A 評価後の re-rank phase** か **Stage B 評価結果を archive に書き込んでから次世代 fitness_pen 再計算** のどちらかが必要
- 設計ファイルで両案を検討し、 詳細設計で確定する

## 却下された提案

| # | 提案 | 却下理由 |
|---|------|---------|
| 代案 A | NSGA-II 2 目的化 | 大幅変更、 cycle 4 の規模超過 |
| 代案 B | max_clause=2→1 戻し | Reactive Parametric、 H1 verified 後の再判断 (cycle 5+) |
| 代案 C | primitive 拡張 | 規模超過、 cycle 4 単独では不適 |

## 保留事項

なし (cycle 4 単一介入で完結)

## 次フェーズへの申し送り

- Phase C 詳細設計の論点:
  - **論点 1 (Critical)**: Stage A 評価時点で pfre 不在 → 介入の **timing** をどこに置くか (Stage A 完了直後の再 rank / next generation の selection / archive 書き込み 後)
  - 論点 2: NaN pfre の扱い (0 として penalty 課す vs penalty なし) — 0 として課す案を採用 (Codex 提案)
  - 論点 3: テスト網羅性 (基本集計 + boundary 値 + NaN 処理 + Stage A→Stage B chain 統合)

- Phase 4 RUN 37 の検証ポイント:
  - sidecar データで世代別 fold_sign / pfre 推移が改善するか
  - Stage B pass が 0 → 1 以上に変わるか
  - 副作用: best 個体の trade_count や PnL が大きく劣化しないか (見栄え改善でないかチェック)
