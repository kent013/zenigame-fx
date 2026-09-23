前提: 手元ワークツリーには Option A 差分が未反映だったため、提示 diff と既存周辺コードを突き合わせてレビューしました。

**Findings**
[Warning] [src/backtest/_sim_kernel.py](/Users/ishitoya/repository/zenigame-fx/src/backtest/_sim_kernel.py)  
`_fill_adj` と stressed fill 後の `pnl_factor * (exit_px - s_entry)` は、既存の overflow 証明が raw price 上限に依存しているため、極端な `spread_cost_multiplier` / spread では sentinel 範囲外になります。Stage C の `1.5` では実害は薄く、`m=1.0` 同一性にも影響しませんが、kernel の「overflow は Decimal fallback」契約を厳密に保つなら、将来 `spread_cost_multiplier` に上限を置くか、adjusted price delta 用の overflow guard を追加するのがよいです。非ブロッキングです。

[Suggestion] [src/backtest/_sim_kernel.py](/Users/ishitoya/repository/zenigame-fx/src/backtest/_sim_kernel.py)  
`end_of_run` 保険分岐は `bars_to_columnar` が末尾 `is_eod=True` にするため通常到達不能ですが、完全な「close 分岐網羅」と読むなら同じ stressed fill helper を適用しておくと監査上きれいです。現仕様の `entry/signal/margin/session/EOD` 契約には抵触しません。

**ファイルごと判定**
[src/backtest/_sim_kernel.py](/Users/ishitoya/repository/zenigame-fx/src/backtest/_sim_kernel.py): APPROVED。`pos_entry` raw 維持、`pos_entry_adj` 分離、MTM/margin raw、realized PnL と trade 記録だけ stressed fill という Option A は Round 1 Critical を解消しています。

[src/broker/mock.py](/Users/ishitoya/repository/zenigame-fx/src/broker/mock.py): APPROVED。`Position.entry_price` raw、`entry_stress_adj` 分離、`_unrealized_pnl` と `entry_margin` が raw を使う構造で設計と一致しています。

[src/broker/orders.py](/Users/ishitoya/repository/zenigame-fx/src/broker/orders.py): APPROVED。`entry_stress_adj` 追加は局所的で、既存 Position の意味を壊していません。

[src/backtest/engine.py](/Users/ishitoya/repository/zenigame-fx/src/backtest/engine.py), [src/alpha_factory/stage_gate.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/stage_gate.py): APPROVED。`BacktestConfig -> broker/kernel` 伝搬、Stage C stress の `max_spread_bps` 非依存化、`spread_cost_multiplier > 1` による cost 厳格化はいずれも施策意図と一致します。

**全体判定**
APPROVED。Round 1 Critical は Option A で解消されています。残る指摘は極端入力に対する kernel overflow 契約の硬化と到達不能分岐の整備で、今回の P2 承認を止める内容ではありません。