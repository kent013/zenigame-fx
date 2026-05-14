**Facts**
- Run 75 実データ確認: `A/B/C/graduated = 1291/827/217/0`（archive 5,856 行）。
- `profit_safe_pfr` 効果は再現: Run 74 比で Stage B 通過が `96 → 827`、Stage C 通過が `0 → 217`。
- Stage C 通過 217 の Sharpe は trade-level だと低い一方、年率換算では全件 `>=1.0`。
  - 実測: 年率換算 Sharpe `min=2.596, median=2.764, mean=2.883, max=5.023`（trade_count/60日で換算）。
- `summary.json` の live_criteria 判定は trade-level の `trade_sharpe_raw` をそのまま `>=1.0` 比較している。  
  参照: [run_ga.py](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py:916), [run_ga.py](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py:924), [run_ga.py](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py:935), [run_ga.py](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py:950)
- 一方で Stage C 本体は「trade-level → annualized に換算してから」live_criteria.sharpe 判定している。  
  参照: [stage_gate.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/stage_gate.py:1670), [stage_gate.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/stage_gate.py:1902), [stage_gate.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/stage_gate.py:1911), [stage-gates.md](/Users/ishitoya/repository/zenigame-fx/docs/alpha_factory/stage-gates.md:26)
- best `g60_i46` はログ上 `legacy_sharpe=2.7286`（C_base）で、`summary` の `sharpe=0.1904` と単位不一致。  
  参照: [.cache run log](/Users/ishitoya/repository/zenigame-fx/.cache/alpha_factory/runs/run_20260513_120619.log), [summary.json](/Users/ishitoya/repository/zenigame-fx/reports/run-reports/run-75/summary.json:1320)
- `graduation_count=0` は構造要因:
  - 卒業条件は `Stage C pass AND cross_pair pass`。cross_pair が `None/skipped` なら必ず不合格。  
    参照: [swim_lane.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/swim_lane.py:408), [swim_lane.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/swim_lane.py:410), [swim_lane.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/swim_lane.py:977)
  - Run 75 は `pair_bars={}` で `cross_pair_runtime_mode=skipped_single_instrument`。  
    参照: [run_ga.py](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py:1674), [run_ga.py](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py:1681), [run-75.md](/Users/ishitoya/repository/zenigame-fx/reports/run-reports/run-75.md:138)
- Stage C 通過群は trade_count が下限近傍に集中（`51件が173/217`）。境界張り付きが強い。
- 禁止事項観点:
  - イントラデイ逸脱: Stage C pass については `intraday_constraint_violation` があれば落ちる設計なので、通過217は少なくとも C 判定上は逸脱なし。
  - ショート偏重: archive に long/short 集計列が無く、**INCONCLUSIVE**。
  - スワップ・スプレッド純利益: stress 判定は通過条件に含まれるが、swap 内訳の十分性は本データだけでは **INCONCLUSIVE**。

**Interpretations**
- Q1（A/B仮説）: **A（bug/不整合）支持**。  
  理由は「Stage C 本体は annualized 判定で217通過」「report/live_criteria だけ trade-level 判定で失敗表示」という二重基準が同時に存在するため。B（意図的にtrade-level 1.0要求）なら Stage C pass=217 と両立しない。
- Q2（graduation=0）: **selection_score 問題ではなく graduation 条件の構造**。cross_pair が skip の運用では卒業が原理的に0。
- Q3（再現性）: n=1 seed（60）のみなので因果主張は不可。`profit_safe_pfr` の効果は大きいが、variance 未測定。

**次サイクル候補**
1. **Critical**: `summary/live_criteria` の sharpe 単位を Stage C と同じ annualized に統一（もしくは trade-level と annualized を明示して別キーで併記し、`all_pass` は annualized SSOT へ）。  
   影響先: `analyze_run.py` など `summary.live_criteria.all_pass` 依存処理。
2. **Warning**: `graduation_count` KPI の解釈を修正。single-instrument で cross_pair skip の間は「卒業0は仕様通り」。KPI を `stage_c_pass_count` と分離して監視。
3. **Warning**: seed sweep で再現性評価（例: seed 61-70 の10本）。最小限メトリクス: Stage B/C pass数、best annualized Sharpe、C通過率、trade_count下限張り付き率。
4. **Warning**: 禁止事項の deceit 検知を可能にするため、archive か sidecar に `long/short件数`、`overnight_violations`、`swap_cost`、`spread_cost` の集計列を追加（現状は判定不能項目が残る）。

**全体判定**
- **CONCERN**  
  `profit_safe_pfr` 自体は有望（Stage B/C は明確改善）だが、`live_criteria.sharpe` 表示系の単位不整合と、cross_pair skip 下で卒業が不可能なKPI設計が意思決定を歪めるリスクが高いです。