**前提確認**

- このレビューは、提示された [conceptual-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260423-1540-stage-gate-implementation/conceptual-design.md) の本文だけを根拠にしています。
- `debate-synthesis.md` 本文は未提示のため、§B の数値整合は「この設計文中の自己申告と矛盾しないか」までしか検証できません。独立検証としては **INCONCLUSIVE** です。

**指摘事項**

- **重大**: §3.6 の WF 分割算法が「観測日インデックス」と「暦日加算」を混在させています。`sorted_dates[step_days * k]` で開始点を取りつつ、`train_end_date = start + (train_days - 1)日` で終点を決めると、週末・祝日 gap がある場合に「120 営業日 train / 20 営業日 test」を保証できません。設計文は「date ベースで robust」と言っていますが、現状の算法は robust ではありません。`sorted_observed_dates` のインデックスだけで train/test/embargo を切る方式に統一すべきです。
- **重大**: Stage C の「session 跨ぎ遵守」を engine 不変条件への信頼だけで済ませており、Stage Gate の出力に証跡が残りません。North Star がイントラデイ戦略であり、禁止事項にもオーバーナイト回避が明記されている以上、Stage C は少なくとも `overnight_positions_detected=False` 相当の明示的な確認結果を `metrics` に残すべきです。未知なら pass ではなく fail closed に寄せる方が整合的です。
- **重大**: Stage C の spread stress が「trade_count 下限だけ hard gate」で、Sharpe/PnL 劣化は monitor のみです。これだと base 条件を満たすが 1.5x spread で純利益が崩壊する個体が通ります。絶対制約の「スプレッドを fitness に反映」に対して弱いです。少なくとも `stress_total_pnl >= 0` か `stress_sharpe >= 0` のような下限、もしくは `degradation_max` を conceptual の時点で固定すべきです。
- **重大**: `max_spread_bps=None` のとき Stage C が stress test をスキップして通過可能なのは危険です。スプレッド耐性を見ないまま live_criteria 候補に残せてしまいます。`spread_stress_skipped=True` は warning ではなく「Stage C 判定不能」として fail させる設計の方が使命と整合します。
- **中重大**: `CrossPairEvaluator` の interface が将来接続用として弱いです。`evaluate(self, genome, target_bars, meta, backtest_config) -> dict` では「どの通貨ペア群を、どの窓で、どの集約ルールで評価したか」が外から見えません。shadow hook にしても、戻り値は `StageResult` に寄せた構造、入力は `pair_bars_map` か `evaluation_context` を受ける形にしないと、将来の ii-lite hard gate へ無理なく昇格できません。
- **中重大**: Stage B の `positive_fold_ratio` と `metric_unavailable` の扱いが曖昧です。本文は `# positive / n_fold` と書く一方で、`None` fold は「カウント対象から除外」とも書いています。分母が全 fold なのか有効 fold なのかで gate の厳しさが変わります。no-trade / low-vol fold を除外すると見かけ上 pass しやすくなるので、ここは conceptual で固定が必要です。
- **中重大**: Stage B は名称が「Full IS + WF-OOS」なのに、実際の評価フローは fold test 上の OOS Sharpe 集計だけです。§6.2 の説明は理解できますが、それなら Stage B の責務名を `WF-OOS gate` に寄せるか、18 ヶ月全体の固定 genome IS metrics を monitor として必ず残すべきです。名前と責務のズレがあります。
- **中**: Stage C の max drawdown は `%` と `fraction` の変換を「詳細設計で明記」に留めていますが、ここは概念設計段階で canonical unit を固定した方がよいです。`max_drawdown_frac` に正規化して gate 比較する、あるいは config も `%` に揃える、のどちらかを今決めるべきです。放置すると実装時の典型的な事故点です。
- **中**: `StageResult.metrics` が stage ごとに自由 dict のままだと、archive / swim-lane 統合時に schema drift を起こしやすいです。pure function 方針自体は良いですが、統合面では「共通 envelope + stage-specific payload」程度の最小契約は必要です。特に `reason_if_failed` だけ文字列連結にする設計は consumer 側で扱いにくいです。
- **軽微**: §3.7 に `target_pass_rate: 0.15` と `dsr_min: 0.0` が入っていますが、本 TODO ではどちらも gate に効きません。将来用の予約値なら、`monitor_only` と明示しないと「設定されているのに効かない」死に設定になります。
- **軽微**: §9 の「18 ヶ月 ≈ 540 営業日」は FX の 24/5 前提と噛み合っていません。ここでも time axis の定義が揺れています。WF 設計の曖昧さと同根です。

**確認できた良い点**

- pure function を評価の唯一ルートに寄せる方針自体は妥当です。統合前に stage 判定を独立検証できる形になっています。
- Stage A の `threshold=0.0` を暫定固定し、calibrate-gate を別 TODO に切る判断は概ね妥当です。ただし「暫定である」ことを config と docs にもっと強く出した方がよいです。
- DSR `n_trials=1` を hard gate に入れない判断も方向性としては妥当です。単一 genome の WF に DSR を無理に当てない、という論理は通っています。

**修正要求の要点**

- WF 分割を「観測日インデックスのみ」で閉じるように再定義すること。
- Stage C に「イントラデイ遵守の明示的証跡」を入れること。
- spread stress を fail-open にしないこと。`None` skip pass はやめること。
- cross-pair hook を将来 hard gate へ昇格できる interface に引き上げること。
- Stage B の fold 有効数・分母・ unavailable policy を概念段階で固定すること。
- max drawdown の canonical unit を今決めること。

**判定**

`REQUEST_CHANGES`

方向性そのものは維持可能ですが、WF 分割の時間軸定義と Stage C の live-ready 証跡が未確定のまま詳細設計に進むのは危険です。ここを固めれば、その先の詳細設計には進めます。