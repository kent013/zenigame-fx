## Section A: 実装候補の判定（T091）

**判定: APPROVE（今 cycle 実装）**

- `target_metric`: 妥当  
  - Stage B pass 率の回復だけでなく、`trade_count_full_dataset>=50` かつ `total_pnl>=50,000` の出現を要求しており、見かけ改善を抑制できる。
- `failure_mode`: 妥当  
  - 現状は `median_oos_sharpe` と `positive_fold_ratio` の同時失敗で全滅。gate 側の設計ミスマッチを直接叩いている。
- `causal_path`: 妥当  
  - run-52 archive 直読で「候補は存在するが gate で遮断」を検証済み。探索能力不足ではなく判定系の欠陥という因果が通る。
- `falsification`: 妥当（必須）  
  - Layer1 replay で `g70_i9/g83_i12` のうち 1+ 件が Stage B 通過しなければ、T091 仮説は **REJECT/INCONCLUSIVE** に戻す。
- `success_criterion`: 妥当  
  - Layer1（archive replay）で因果確認、Layer2（次 RUN）で一般化確認の二段階は適切。

**メタ過学習ガード分類**  
- **Structural + Principled Parametric の混合**で妥当。  
- Reactive ではない（直近 run-53 の見た目改善目的ではなく、run-52 archive の反証可能事実と理論根拠に基づく）。

---

## Section B: TODO 全体の関係分析

- 重複・統合  
  - T091 と 4候補は重複なし。統合すべきは「監視系」2件（primitive entropy / cross-pair shadow）で1パッケージ化可能。
- 依存関係  
  - `n_fold_effective=0 guard` は T091 と非競合で並走可能。  
  - `seed-robustness検証` は「次の閾値調整」を縛る前提タスクとして有効（T091後の追加調整前に必須化）。
- 陳腐化  
  - 現時点で陳腐化 TODO はなし。T091 は still-open の中核。

---

## Section C: 総合推薦

1. 今 cycle は **T091 を最優先で実装**。  
2. 並行で新規 TODO 登録は **1件だけ**: `n_fold_effective=0 上位化ガード`（評価不能個体の誤選抜を遮断）。  
3. `seed=42 単独で次 RUN` は **REJECT**（Reactive/cherry-pick 寄り）。  
4. T091 完了後は、まず Layer1 replay で単独有効性を検証し、その後 Layer2 は seed 戦略を別議論（固定少数 seed 比較）で決める。

---

## Section D: TODO vs GA 改善のバランス判断

**結論: `todos` 寄り（実質 T091 主導）**

- 今 cycle の主眼は GA パラメータ微調整ではなく、gate 構造欠陥の是正。  
- GA 改善（seed 戦略最適化、entropy監視など）は **次 cycle** に分離するのが監査 discipline（C4/C9）に整合。