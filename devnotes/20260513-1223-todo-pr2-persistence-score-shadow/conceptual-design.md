# PR2: Stage B persistence_score_shadow 列追加 (shadow audit)

## 背景

30 ラウンド Codex 議論 + archive 実測で、 **Stage B gate (median_oos_sharpe + positive_fold_ratio) は Stage C 持続性を予測しない** ことが判明:

- median_oos_sharpe → trade_sharpe_stage_c: Spearman ρ = **-0.361** (逆予測)
- positive_fold_ratio_effective → trade_sharpe_stage_c: ρ = **+0.345** (唯一の正予測)
- fold_sign_ratio → trade_sharpe_stage_c: ρ = +0.248 (弱い正)
- Stage B pass 12/18 RUN だが Stage C pass 0/72 RUN

Codex H_X'' (PARTIAL CONFIRMED): Stage B gate は curve-fit 個体 (F9 lift 10.65x、 Stage C 0%) を選好し、 真の持続性候補を捨てている可能性。

## 目的

Stage B 評価時に **`persistence_score_shadow`** を計算して archive に記録。 selection / gate には一切影響させず、 **観測専用** とする。 これは:

1. PR4 (= legacy_pnl_smoke fitness 切替) で elite 1 枠の選別基準として将来使う
2. PR5 (= Stage B gate `pfr_only` opt-in A/B) の判定根拠を蓄積
3. Stage C 観測増量 (= Stage C stratified allocation) の基礎データ

## スコープ縮小

元案では PR2 = `archive_role + persistence_score_shadow` を同時に入れる予定だったが、 archive_role は `cpps_archive.determine_archive_role(bc_result)` 経由で **BCEvaluationResult 計算が新規必要** = swim_lane への BC 統合配線を伴うため、 別 PR (= PR7 候補) に切り出し。

PR2 = **`persistence_score_shadow` のみ**、 既存 collect_stage_b 内で簡易計算。

## 期待効果

- Stage B 評価済個体に persistence_score_shadow が populated される
- 既存 GA selection / fitness / gate 判定への影響なし (= 完全行動不変)
- 後続 PR (PR4 / PR5) の判定基盤データ
- archive Parquet schema に 1 列追加 (= 50 → 51 列、 nullable float)

## 計算式 (簡易合成)

archive 実測 Spearman 上位の Stage B metric を使って:

```python
persistence_score_shadow = clip(
    0.7 * positive_fold_ratio_effective + 0.3 * fold_sign_ratio,
    0.0, 1.0
)
```

- `positive_fold_ratio_effective` (ρ=+0.345) を主体 (weight 0.7)
- `fold_sign_ratio` (ρ=+0.248) を補助 (weight 0.3)
- 両 None なら `persistence_score_shadow = None` (= 計算不可)
- 片方 None なら他方のみで計算

将来 (PR4 以降) で wright や合成式を洗練できる余地を残す。 PR2 では「**観測列を populated にする最小実装**」 が目的。

## 非目的

- archive_role 値入力 (= 別 PR、 BCEvaluationResult 配線が前提)
- canonical_metrics / mission_inf_gap shadow 配線 (= PR3、 別 PR)
- selection / fitness への persistence_score 反映 (= PR4 以降)
- Stage B gate 修正 (= PR5)

## 関連 TODO (12 段)

| 順 | TODO | 状態 |
|---|---|---|
| 1 | PR1: source_stage 値入力 | **Completed (e81dc85)** |
| 2 | **PR2: persistence_score_shadow 追加** | **本 TODO** |
| 3 | PR3: canonical_metrics / mission_inf_gap shadow | 未着手 |
| 4 | PR4: legacy_pnl_smoke + anti-luck guard | 未着手 |
| 5 | PR5: Stage B gate pfr_only opt-in A/B | 未着手 |
| 6+ | docs / out-of-cluster audit / grammar 等 | 未着手 |
| 7+ | archive_role 値入力 (BCEvaluationResult 配線) | 未着手 |

詳細議論: `tmp/codex-debate-round2/` (Round 1-5 × 3 論点)
