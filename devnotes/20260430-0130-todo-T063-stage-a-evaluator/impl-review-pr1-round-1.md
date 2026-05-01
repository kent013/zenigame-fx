## 結論
APPROVED

## 検出された問題 (検出順、 severity 別)
### Critical (= merge blocker)
- なし

### Warning (= 修正推奨だが merge は可)
- なし

### Suggestion (= 改善提案)
- Phase 2 組み込み前に、`config -> GaConfig -> genome.meta -> consumer` の4段接続を機械的に検査するCIテスト（転記漏れ検出用）を1本追加すると、既知の再発パターンにさらに強くなります。

## Falsification (反証探索) サマリー
- 前提: 本レビューは、提示された証跡テキスト（設計要件、テスト結果、grep結果、lint/typecheck結果）を対象に実施。
- 反証仮説: `StageAGenerationInput` に `state` field が混入している。結果: 3 field契約および該当テスト記述と整合し、反証成立。
- 反証仮説: `select_top_q_force_indices` の tie-break が非決定的。結果: `(-score, index)` 契約とテスト記述により、反証成立。
- 反証仮説: `update_divergence_state` が `10 <= n < 30` で `divergence_offset_steps` を更新する。結果: INCONCLUSIVE経路で不変という契約/テスト記述と整合し、反証成立。
- 反証仮説: `n < 10` を raiseせず握りつぶす。結果: `StageAInputError` raise 契約/テスト記述と整合し、反証成立。
- 反証仮説: `n_hard_pass=0` で `IndexError` が起きる。結果: `(frozenset(), None)` 返却契約/テスト記述と整合し、反証成立。
- 反証仮説: PR1スコープ外への配線混入がある。結果: 5段階grep 0 hit の証跡と整合し、反証成立。