現行ワークツリーには Round 2 設計の変更はまだ入っていません。以下は提示された修正後設計に対するレビューです。

**Round 1 指摘対応**
| # | 判定 | コメント |
|---|---|---|
| 1 post-filter 不整合 | `RESOLVED` | `trade_sharpe_stage_b` 後段マスク廃止で、`stage_b_pass=False` 反転後に `stage_c_pass=True` が残る問題は消えます。 |
| 2 config 4段伝搬 | `RESOLVED` | `_build_stage_gate` と `compute_base_config_hash` 追加で方針は妥当。ただし YAML 配置を `stage_gate` 直下にするのか `stage_gate.stage_b` 配下にするのかは実装で統一してください。 |
| 3 trade_sharpe None/非有限 | `RESOLVED` | 条件自体を削除するため解消。 |
| 4 `median_oos_total_pnl` NaN 防御 | `PARTIAL` | finite guard は妥当ですが、`legacy` mode で `fold_total_pnl` 非有限を理由に `fold_sharpe=None` へ変えると legacy 完全不変ではありません。 |
| 5 archive test 更新 | `RESOLVED` | 新 nullable 列追加 + テスト更新で妥当。 |
| 6 report known reason codes | `RESOLVED` | 新 reason 3個追加で妥当。 |
| 7 `__post_init__` 範囲検証 | `RESOLVED` | finite / 0..1 / min>=1 / enum check で十分。 |

**残課題**
[Warning] `median_oos_total_pnl >= 0` だけでは「赤字許容構造」を完全には閉じません。中央値なので、例えば 20 folds のうち 11 fold が小幅プラス、9 fold が大幅マイナスなら通過し得ます。  
最小修正案: `sum_oos_total_pnl >= 0` も payload と gate 条件に追加してください。条件は `pfr_effective >= threshold AND median_oos_total_pnl >= 0 AND sum_oos_total_pnl >= 0 AND n_fold_effective >= min` が、名前どおりの `profit_safe` に近いです。

[Warning] finite guard は `profit_safe_pfr` 用の PnL 集計だけに影響させ、`legacy` 判定の `fold_sharpe` / `fold_reason` は変えないでください。  
最小修正案: `fold_total_pnl` が非有限なら `oos_total_pnls` へ入れず、`profit_safe_pfr` 側で `median_oos_total_pnl is None` または `sum_oos_total_pnl is None` により fail-closed。`legacy` の Sharpe 判定経路は完全不変にします。

**質問への回答**
1. `trade_sharpe_stage_b` 条件削除は、不整合回避として妥当です。ただし `median_oos_total_pnl` だけでは aggregate 赤字を防げないため、`sum_oos_total_pnl >= 0` を足すのが最小で堅いです。
2. 非有限 PnL を unavailable 扱いにする方針は妥当ですが、legacy 経路の `fold_sharpe` 判定を変えない形にしてください。
3. config 伝搬は方針として漏れなし。`default.yaml` の配置、loader、CLI override、startup log、`compute_base_config_hash` のキー名を一致させれば十分です。

**全体判定**
`CHANGES_REQUESTED`

残りは小さいです。`sum_oos_total_pnl >= 0` の追加と、finite guard を legacy 判定から隔離すれば `APPROVED` にできます。