**1. Round 19 修正 8 件への最終判定**

最終判定は **OK（採用）** です。  
実装上の注意は 2 点だけです。

- `gen=48 fallback` は、FSM が比率閾値だけで遷移するなら再校正不要。`gen>=N` の強制遷移を残す場合のみ再校正が必要です。
- `A→B 乖離 warn-only` は妥当ですが、`q_force` 自動引き上げの上限・戻し条件を明文化してください（未定義だと暴走します）。

**2. T901-T918 統合案の最終確認**

過不足はほぼありません。順序も成立しています。依存を明示すると以下です。

- 先行必須: `T901 -> T902 -> T903`
- 評価系: `T904 -> T905 -> T906 -> T907`
- GA中核: `T908 -> T909 -> T910 -> T911`
- 運用制御: `T912 -> T915`
- 基盤拡張: `T913 -> T914`
- 監査/展開: `T916 -> T917 -> T918`

修正提案は 1 点だけです。  
`T909`（CPPS）と `T910`（warmstart）の境界を固定し、`archive admission/eviction` は `T909`、`injection/reuse/cooldown` は `T910` に限定してください。

**3. 18 章構成の最終確定**

確定して問題ありません。  
最終版は以下で固定を推奨します。

1. Mission / 非交渉制約  
2. 設計原則（gate/search 分離）  
3. 全体アーキテクチャ（7段）  
4. Dataset / Epoch / Partition  
5. Stage A/B/C-lite/C 仕様  
6. canonical5 + Pareto3 数式  
7. NSGA-II + CPPS（2-state）  
8. Archive / Sieve / Warmstart / Emergency  
9. Schema v2 契約（dataset_epoch_id）  
10. Observability / Audit（DSR先行, PBO/SPA未実装）  
11. Graduation lane batch 仕様  
12. Big-bang 移行・削除一覧  
13. Round1-10 の記録位置づけ  
14. zenigame 実装対応表（file/line）  
15. INCONCLUSIVE と再校正計画  
16. Risk Top5 と緩和策  
17. 用語・判定辞書  
18. TODO T901-T918 実装計画

**4. T918 smoke gate（DoD）**

以下を満たしたら smoke 完了で良いです。

- 1 Run 完走（クラッシュ無し、NaN/Inf fail-soft 動作）
- `A-pass only B-eval` をログで検証（A-fail が B/親選択へ入らない）
- 主選抜が B-pooled 指標のみで計算されている
- archive 書込の全レコードで `dataset_epoch_id` 必須（欠落=fail）
- inflow / per_run_max / warmstart_share が設定どおり
- CA/DA 配分が state ごとに一致（pop192: push 84/108, pull 120/72）
- invariant fail-fast（`session_close_drop`, `negative_equity_drop_open`）が有効
- 連続 5 Run で epoch 汚染なし（prev_epoch 20% 制約順守）

**5. fx→zenigame 逆輸入**

**追加すべきです。** synthesis に独立節を置いてください。候補はこの4つで十分です。

- `dataset_epoch_id` 全経路契約 + schema lint
- `session_block_win_rate` 指標
- HAC 補正 Sharpe の標準化
- A/B 乖離監視 + 自動 q_force 調整

**6. 最終 consensus（合意 / 異論 / INCONCLUSIVE）**

- 合意:
  - lane=1, pop192/256, gen64, 24m rolling, B=5fold
  - gate/search 分離、主選抜 B-pooled 統一
  - NSGA-II + 純CPPS 2-state
  - archive=120, inflow=8, per_run_max=12, warmstart 20%（緊急25%）
  - schema v2 + dataset_epoch_id 必須
  - factor_shadow 縮退保持

- 異論:
  - なし（設計矛盾は解消済み）

- INCONCLUSIVE:
  - push→pull の最終閾値（`feasible_ratio_ema` の固定値）
  - DST/holiday 境界の厳密運用定義
  - PBO/SPA の実装時期（現時点は未実装タグで正当）
  - cost model の epoch 再校正導入時期

この内容で Round 20 を最終確定して問題ありません。