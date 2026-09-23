# 詳細設計 (cycle 22): R104 = nsga2-selection 探索効率改善

## 決定 (Codex consensus-round-1: (A)採用)
閾値飽和後の North Star 継続 = **探索効率改善で達成分布を上方シフト**。Codex 最有力単一変更 = **`--nsga2-selection` 有効化** (既実装レバー、計算コスト小、上位尾部[高pnl・低dd]押し上げ期待、warmstart強化のmode崩壊リスク/pop増の線形コストを回避)。

## 実装
- config/code 変更不要。CLI flag `--nsga2-selection` を R104 args に追加するのみ。
- frontier 据置 (sharpe1.5/pnl70k/dd2%/trade50/pfr0.4 = R101 と同一)。selection のみ tournament→NSGA2 多目的。
- feature opt-in (default OFF) ゆえ default挙動 bit-exact 維持。

## R104 = R101(dd2%, tournament) 反実仮想 (同一seed70、selection のみ NSGA2)
nsga2 の上位尾部押し上げ効果を単一変数で測定。

## R104 反証可能基準 (Codex提示5条件、全充足で成功)
1. mission_candidate_count ≥650 (R101 723比で大幅退行しない)。
2. median StageC ann sharpe ≥5.75 (R101 5.582比 +3%)。
3. median StageC total_pnl ≥86000 (R101 82k比 +5%)。
4. live_criteria達成個体で max_dd≤0.02 を100%維持 ∧ p95(max_dd)≤0.019。
5. 追試seed(seed71)で条件2,3が本run比 -10%以内 (再現性)。

判定: 5条件全充足→成功 (nsga2採用、分布上方シフト確認→将来gate引き上げ余地再生)。1つでも未達→失敗 (nsga2は分布押し上げず、別レバーへ)。データ欠損→INCONCLUSIVE。

## launch条件
pop96/gen60/EUR_JPY/profit_safe_pfr/warmstart0.1/cross-pair-enable+selection-pressure、seed=70、**+--nsga2-selection**。frontier config据置。
