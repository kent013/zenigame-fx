# マージ分析: Run 36 (run_20260506_054244) — cycle 4

## 合議ステータス: 完全一致 (Round 0、 analyze 段階で収束)

## 合意事項 (両者一致)

| # | 観察 / 仮説 | 信頼度 |
|---|---|---|
| M1 | run-35 vs run-36 fitness_pen 100% 一致 → cycle 3 介入は副作用なし、 純観察 | verified |
| M2 | 仮説 H1 (探索圧不整合) **VERIFIED**: fitness_pen +306% vs fold_sign_mean -20% (gen 5-15 → 50-60) | 中〜高信頼 |
| M3 | pfre_mean 後期 0.296 = Stage B 閾値 0.6 の 49% で天井 → 構造的限界 | verified |
| M4 | cycle 4 介入: fitness_pen に fold-aware penalty 追加が妥当 | 一致 |

## 統合改善提案 (cycle 4 → run-37)

| # | 提案 | 優先度 | 出所 | 変更分類 | target_metric | falsification | success_criterion |
|---|------|--------|------|---------|--------------|---------------|-------------------|
| **C1** | **fitness_pen に fold-aware penalty 追加** | **Critical** | Claude H1 + Codex 採用候補 | **Structural** (新項追加) | Stage B pass count、 pfre_mean 後期 | cycle 5 で fitness_pen 上昇に同期して fold_sign / pfre が上昇しなければ別構造的問題 | Stage B pass > 0 (主)、 pfre_mean 後期 > 0.4 (副) |

### C1 設計詳細 (両者合意済)

```python
fitness_pen = fitness_raw - α·size_norm - β·max(0, 0.4 - pfre_clamped)
```
- α = 0.03 (既存、 不変)
- β = 0.05 (initial、 最大追加ペナルティ = β × 0.4 = 0.02、 既存 α 寄与と同オーダー)
- pfre_clamped = clip(positive_fold_ratio_effective, 0, 1)、 NaN は 0 として扱う

### 禁止事項チェック (両者確認)

- ✅ 期間延長 (1): 該当なし
- ✅ 見栄え改善 (2): fitness_pen の構造的拡張、 数値弄りではない
- ✅ GA ハック (3): 該当なし
- ✅ 閾値緩和 (4): 既存閾値不変、 むしろ Stage A selectivity を強化
- ✅ 複雑化 (5): 1 行追加 (penalty 項)、 概念上の複雑度低い
- ✅ 取引回数削減 (6): pfre は trade_count 直接介入ではない、 ただし要観察
- ✅ オーバーナイト (7): 該当なし
- ✅ メタ過学習ガード: Structural 分類

## 全体判定

**ACTIONABLE** — 仮説 verified、 介入策定済、 cycle 4 implement へ直行。 Phase 2 plan-and-design は最小ラウンドで収束 (analyze 段階で両者合意のため Codex 改善策合議は省略可)。
