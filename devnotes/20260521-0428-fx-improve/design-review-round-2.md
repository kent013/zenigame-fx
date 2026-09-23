**全体判定: APPROVED（条件付き）**

Round 1 の Critical は設計方針として解消されています。`stress は realized fill のみ`、`MTM/margin は raw bid/ask のまま` は kernel/Decimal parity を保つ正しい契約です。非負 `spread_diff` から `adj` を計算し、符号を最後に適用する丸め規約も妥当です。

残すべき指摘は 1 件だけです。

[Warning] kernel 側の realized exit 対象を全分岐に明記してください。  
対応マトリクスの `L185/194/203/206` だけだと、entry と signal close だけに見えます。kernel の realized close は `signal close` だけでなく、`margin_call close`、`session_close`、`EOD close`、`end_of_run close` も含みます。ここが漏れると Stage C stress は非ゼロ化しても、強制決済系の exit cost が片側だけ raw のままになり、cost robustness を過小 stress します。

最小変更:
- kernel に `adjust_entry_long/short` と `adjust_exit_long/short` 相当の小 helper を作る。
- `pos_entry = ask_o/bid_o` の 2 箇所へ entry 補正。
- `exit_px = bid_o/ask_o`、`bid_c/ask_c` の全 realized close 分岐へ exit 補正。
- MTM 用の `unreal_pre/post/rec` と margin RHS の `pos_entry` は raw/stressed どちらかを混ぜず、現在の契約どおり raw MTM価格 + 実約定 entry 価格で維持する。

MockBroker 側は `_close_one` の realized exit 直後だけ補正し、`_unrealized_pnl` は raw `_exit_price` を使う設計で問題ありません。実装時は `_close_position` ではなく現行名 `_close_one` に合わせるのが安全です。

この 1 点を設計本文に明記すれば、P2 は **APPROVE** でよいです。