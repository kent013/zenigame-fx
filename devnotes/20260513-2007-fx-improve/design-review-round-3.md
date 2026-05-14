**Round 2 指摘対応**
| # | 判定 | コメント |
|---|---|---|
| 1 aggregate 赤字構造 | `RESOLVED` | `median_oos_total_pnl >= 0` に加えて `sum_oos_total_pnl >= 0` を入れることで、11小幅勝ち + 9大幅負けのような中央値すり抜けは防げます。 |
| 2 finite guard の legacy 隔離 | `RESOLVED` | 非有限 PnL 時に `fold_sharpe` / `fold_reason` / `reason_counts` を触らず、PnL 集計だけから除外する設計なら legacy mode は完全不変です。 |

**確認事項**
1. `sum_oos_total_pnl >= 0` 追加で、少なくとも fold OOS の有限 PnL 集計上の aggregate 赤字は防げます。`profit_safe_pfr` という名前にも整合します。
2. finite guard は提示コードどおり「PnL 配列に追加しないだけ」に限定されており、legacy 判定経路には影響しません。
3. 実装時は `len(oos_total_pnls) < n_fold_effective` のケースを fail-closed にしてください。非有限 PnL fold を黙って除外したまま残り fold だけで pass すると、profit-safe 判定が部分データになります。reason は `oos_total_pnl_unavailable` などで十分です。

**全体判定**
`APPROVED`

上記 3 点目は実装時の受入条件として入れてください。Round 2 の Warning 2 件は設計上解消されています。