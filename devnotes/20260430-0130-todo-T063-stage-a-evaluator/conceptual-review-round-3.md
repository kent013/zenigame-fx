[VERDICT] **APPROVED**（実装着手可）

[Critical]

- 該当なし。

[Warning]

- **`divergence_offset_steps` の上限導出は妥当ですが、`Q_FORCE_BASE_MIN` 基準固定のため、`base_q_force` が高い run では回復時に実効 `q_force` がしばらく 0.40 に張り付く可能性があります。**  
  仕様として許容するなら「cap 飽和中は見かけ上 0.02/Run で下がらない期間がある」を明記してください。  
  出典: Round 3 抜粋「定数導出」、synthesis §8.7（要原文照合）。

- **Decision 1/2 は INCONCLUSIVE 扱いの方針で問題ありませんが、smoke 後再校正の判定基準を 1 行だけ先に固定しておくと運用ぶれを防げます。**  
  出典: Round 3 抜粋「Decision 2 根拠強化」、synthesis §5.1/§5.4（要原文照合）。

[Suggestion]

- `q_force` の飽和・回復を検証するテスト（「乖離継続→cap到達→corr>=0.5連続時の推移」）を T063 単体テスト観点に追加すると、§8.7 追従が監査しやすくなります。  
- `derive_stage_a_thresholds` は境界値テスト（`window_days=1`, `window_days=baseline`, `trade_count_min=max`）を先に入れると T065 統合時の事故を減らせます。  
- 現時点の概念設計は Round 1/2 指摘に整合しており、Phase 分離・責務境界・immutable 方針も成立しています。