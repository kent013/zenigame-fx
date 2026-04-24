## 判定: APPROVED

## 対応マトリクス
| # | 前回指摘 | 対応箇所 | 評価 |
|---|---|---|---|
| 1 | `target_pass_rate` を使命そのものとして扱わないことを明文化し、Stage B/C 到達数 / `live_criteria` gap を従属監視指標として追加 | §1「使命との関係」、§5.3 `calibrate_gate.monitoring` | 対応済み |
| 2 | `actual` の定義を一本化（generation-aware aggregation 推奨） | §4.1 `aggregation_mode` を SSOT 化、`actual` と quantile 計算の集計範囲も統一 | 対応済み |
| 3 | survivor bias 対策を本 TODO に引き戻す | §4.1 `last_k_generations` / `generation_weighted_mean` を in-scope 化、既定も明記 | 対応済み |
| 4 | 制御則の説明を `quantile-snap + hysteresis + delta clamp` に修正、他自動調整機構との相互作用ルール追加 | §4.2 制御則名称と擬似コード、§4.5 衝突回避ルール | 対応済み |
| 5 | failure mode 拡張（全 fail n>=10 / 全 pass / ゼロ分散 / NaN / schema mismatch / atomic yaml update） | §5.2 atomic update、§7 失敗モードと対処 | 対応済み |
| 6 | calibrate キー名を単位が分かる形に | §4.2 パラメータ表、§5.1 YAML 例 (`pass_rate_tolerance_abs`, `threshold_delta_abs_max`) | 対応済み |

## 全体所感

前回 REVISE の 6 点は、概念設計レベルとしては十分に取り込まれています。特に、`target_pass_rate` を North Star から切り離した点、`actual` の集計定義を SSOT 化した点、survivor bias を「別 TODO 逃がし」せず本設計へ戻した点で、設計の軸がかなり明確になりました。

制御則の説明も前回より正確です。`quantile-snap + hysteresis + delta clamp` という記述に直され、さらに他の自動調整機構との順序・ログ方針まで入ったため、少なくとも概念設計レビューとしての不備は解消しています。failure mode とキー命名も十分です。

非 blocking の補足だけ挙げると、詳細設計では `generation_weighted_mean` の重み式と `live_criteria_gap` の符号規約を明文化すると実装時のブレが減ります。ただしこれは APPROVED を覆す論点ではありません。

## 必須修正点（REVISE のみ）

該当なし。