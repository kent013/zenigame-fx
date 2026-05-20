**Fact**
- `margin_lhs_factor` / `margin_rhs_factor` は guard 後の段階計算に移動され、前回指摘した `maint_num * units * scale_ratio` の未保護 overflow は閉じています。
- PnL 積は `pnl_factor` guard と `max_abs_price <= pnl_safe` で一括証明され、cash/equity 加算は `_add_overflows` で保護されています。
- margin / spread gate は overflow 時に `STATUS_OVERFLOW` を返し、Decimal 再実行へ戻る設計です。
- 今回も提示差分ベースの静的レビューで、コマンド実行はしていません。

**Interpretation**
- selection-invariant を崩す主要経路は閉じています。
- Round 3 の Warning は解消済みです。
- 現行 preflight 前提下では、残る Critical/Warning はありません。

**ファイル別判定**

[src/backtest/_sim_kernel.py](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T108/src/backtest/_sim_kernel.py)  
判定: **APPROVED**

[Critical] なし  
[Warning] なし  
[Suggestion] `time_stop_min * 60_000_000_000` と `spread_lhs_factor = 20000 * max_spread_den` は、現在の設計前提では実害なしと見ます。kernel 単体契約をさらに硬くするなら、前者は `time_stop_min <= INT64_MAX // 60_000_000_000`、後者は `max_spread_den > 0 and max_spread_den <= INT64_MAX // 20000` の guard を足すと監査上はより明快です。

[tests/backtest/test_sim_kernel.py](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T108/tests/backtest/test_sim_kernel.py)  
判定: **APPROVED**

[Critical] なし  
[Warning] なし  
[Suggestion] なし。`margin_rhs_factor` 境界を分離して検証する追加方針は妥当です。

**全体判定**
**APPROVED**

前提は、`PriceBar/Ohlc` が正値価格と high>=open/close を保証し、engine 経路では `scale_ratio=1000`、`max_spread_den=1`、通常の intraday `time_stop_min` が渡ることです。この前提下で、T108 は `selection-invariant performance-only change` として承認できます。