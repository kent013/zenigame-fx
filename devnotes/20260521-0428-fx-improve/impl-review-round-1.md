[Critical] [src/backtest/_sim_kernel.py](/Users/ishitoya/repository/zenigame-fx/src/backtest/_sim_kernel.py), [src/broker/mock.py](/Users/ishitoya/repository/zenigame-fx/src/broker/mock.py)  
`realized fill のみ補正` 契約に対して、現差分は `MTM/margin` にも影響が漏れています。  
差分では entry 時に `pos_entry` / `Position.entry_price` 自体を adverse 補正しており、その同じ値が `unrealized PnL` と `margin 判定` に使われています。結果として `spread_cost_multiplier > 1` で margin call 境界・equity 推移が変わり、設計条件「MTM/margin は生価格」を満たしません。

反証可能仮説（1つ）  
`m=1.0` と `m=1.5` で、同一 bars・同一 signal のとき `margin_call` 発火タイミング（または exit_reason 列）が一致しないケースが出る。  
設計上はここは一致すべきです。

最小変更（1つ）  
`entry_raw` と `entry_fill` を分離し、`MTM/margin` は常に `entry_raw` を使用、`realized pnl` と trade 記録だけ `entry_fill/exit_fill` を使用する実装に切り替える。  
同時に、上の仮説を直接検証するテストを1本追加（`m=1.0` vs `m=1.5` で margin 系挙動が不変であること）。

ファイルごと判定  
- [src/alpha_factory/stage_gate.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/stage_gate.py): 方向性は妥当（`max_spread_bps` 非依存化）  
- [src/backtest/engine.py](/Users/ishitoya/repository/zenigame-fx/src/backtest/engine.py): 伝搬自体は妥当  
- [src/backtest/_sim_kernel.py](/Users/ishitoya/repository/zenigame-fx/src/backtest/_sim_kernel.py): **CHANGES_REQUESTED**（上記 Critical）  
- [src/broker/mock.py](/Users/ishitoya/repository/zenigame-fx/src/broker/mock.py): **CHANGES_REQUESTED**（上記 Critical）  
- テスト差分: 現状テストは parity と PnL悪化は押さえているが、設計契約（MTM/margin 不変）を直接検証していない

全体判定: **CHANGES_REQUESTED**