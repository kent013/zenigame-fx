1. **[Critical] `equity_at_entry` の実装経路が未定義です。**  
設計は return を `net_pnl_base_currency / equity_at_entry` に固定していますが、現行の `Trade` にはその分母が存在せず、クローズ時にも記録していません。[src/broker/orders.py:33](/Users/ishitoya/repository/zenigame-fx/src/broker/orders.py:33) [src/broker/mock.py:327](/Users/ishitoya/repository/zenigame-fx/src/broker/mock.py:327)  
このままだと `compute_metrics(trades, equity_curve)` だけでは trade return を一意に再構成できません。Phase 1A の概念設計に、`Trade` へ `equity_at_entry` を積むのか、別 ledger を `compute_metrics` に渡すのか、その SSOT を明記する必要があります。

2. **[Critical] `reader hard-fail` の境界が狭すぎて、旧 `sharpe` 読みを止め切れません。**  
現状の reader 本体に見える `GenomeArchive.load()` は単なる `pq.read_table()` で、`sharpe_calc_version` 検証を挟む場所がありません。[src/alpha_factory/archive.py:513](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/archive.py:513)  
加えて、`run_alpha_sieve` は archive から `sharpe` 列をそのまま読んで候補化し、`run_ga` の live criteria / report も `row["sharpe"]` を参照しています。[scripts/alpha_factory/run_alpha_sieve.py:218](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_alpha_sieve.py:218) [scripts/alpha_factory/run_ga.py:490](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py:490) [scripts/alpha_factory/run_ga.py:500](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py:500)  
つまり「load 時 hard-fail」だけでは足りず、`trade_sharpe_raw` を返す canonical accessor に全 reader を寄せる設計まで書かないと、v1/v2 混在を静かに通します。

3. **[Warning] “全 consumer 切替” の列挙が未完で、`sharpe` 名の漏れが残ります。**  
`compute_metrics` の消費先は GA / Stage Gate 系だけではなく、backtest/ensemble の Markdown・JSON 出力も `sharpe` という名前で露出しています。[src/backtest/report.py:56](/Users/ishitoya/repository/zenigame-fx/src/backtest/report.py:56) [src/backtest/report.py:80](/Users/ishitoya/repository/zenigame-fx/src/backtest/report.py:80) [src/backtest/ensemble_report.py:21](/Users/ishitoya/repository/zenigame-fx/src/backtest/ensemble_report.py:21) [src/backtest/ensemble_report.py:58](/Users/ishitoya/repository/zenigame-fx/src/backtest/ensemble_report.py:58)  
Round 2 の禁止事項では「`trade_sharpe_raw` を外部向けに 'Sharpe' と呼ばない」としているので、Phase 1A の対象を Alpha Factory 内部だけに限定するのか、報告系も同時に改名するのかを明示した方がよいです。今の DoD だとここが抜けます。

前提を崩す指摘は上の 2 点です。特に 1 は実装不能、2 は後方互換事故につながるので、Round 3 ではこの 2 点を設計本文に先に閉じるのが妥当です。