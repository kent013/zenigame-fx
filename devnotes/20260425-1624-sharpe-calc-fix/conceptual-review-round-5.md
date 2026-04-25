**Findings**

1. 重大: `GenomeArchive.get_trade_sharpe(row)` だけではクリティカルパスを置き換えられません。現状の AF 本体は archive 行ではなく `compute_metrics(...).sharpe` を直接読んでいます。[stage_gate.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/stage_gate.py#L279) [stage_gate.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/stage_gate.py#L389) [stage_gate.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/stage_gate.py#L518) [cross_pair.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/cross_pair.py#L145) [fitness.py](/Users/ishitoya/repository/zenigame-fx/src/ga/fitness.py#L66) [run_alpha_sieve.py](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_alpha_sieve.py#L400)  
このままだと Phase 1A 後も Stage A/B/C、cross-pair、sieve OOS が旧 bar-level annualized Sharpe を使い続け、Round 4 の根本修正が AF の選別本体に入りません。archive accessor とは別に、`BacktestMetrics` 側の canonical accessor か、Stage Gate 系 payload 契約の明示切替が必要です。

2. 重大: `Trade.equity_at_entry` を `Trade` に足すだけでは値を保持できません。現在はエントリー時に保持されるのは `Position` で、`Trade` はクローズ時に `Position` から生成されています。[orders.py](/Users/ishitoya/repository/zenigame-fx/src/broker/orders.py#L21) [orders.py](/Users/ishitoya/repository/zenigame-fx/src/broker/orders.py#L33) [mock.py](/Users/ishitoya/repository/zenigame-fx/src/broker/mock.py#L305) [mock.py](/Users/ishitoya/repository/zenigame-fx/src/broker/mock.py#L327)  
そのため multi-bar position では entry 時点の equity を close 時点まで運べません。`Position` に持たせるか、`position_id -> equity_at_entry` の sidecar map を broker SSOT として設計に明記すべきです。

3. 高: 再校正対象が不足しています。現在の Sharpe 系しきい値はすべて旧スケール前提です。[stage_gate.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/stage_gate.py#L63) [default.yaml](/Users/ishitoya/repository/zenigame-fx/config/alpha_factory/default.yaml#L31) [default.yaml](/Users/ishitoya/repository/zenigame-fx/config/alpha_factory/default.yaml#L63) [default.yaml](/Users/ishitoya/repository/zenigame-fx/config/alpha_factory/default.yaml#L80) [cross_pair.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/cross_pair.py#L95)  
`live_criteria.sharpe_min` だけでなく、`stage_a_threshold`、`stage_b_median_oos_sharpe_min`、`spread_stress_min_sharpe`、cross-pair の Sharpe 系 pass criteria も replay 再校正対象に入れないと、ゲート通過率が任意になります。

4. 中: `run_ga` の summary 契約が二重意味になります。`best.metrics.sharpe` は row の `sharpe` をそのまま出力し、live 判定も別に Sharpe を読んでいます。[run_ga.py](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py#L483) [run_ga.py](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py#L500)  
Phase 1A で live 判定だけ trade-level に切り替えると、同じ `summary.json` 内で `sharpe` が bar-level と trade-level の混在になります。`trade_sharpe_raw` と `legacy_bar_sharpe` を併記するか、少なくとも `sharpe_calc_version` を summary/report に露出した方が安全です。

**Open Questions**

- Phase 1A で本当に差し替える対象は「archive consumer」だけなのか、「Stage Gate / cross-pair / sieve を含む AF 全体」なのかを先に固定した方がいいです。今の記述は後者を示していますが、実装手段は前者寄りです。
- `equity_at_entry` の保持先は `Trade` ではなく `Position` か broker 内 sidecar のどちらを SSOT にするか、設計で明文化した方が実装がぶれません。

上の 4 点を潰せば、Round 4 の critical には概ね応答できる設計になります。