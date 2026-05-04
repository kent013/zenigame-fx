結論: **(c) Q3 の diagnostic instrumentation を Run-28 で 1 件採用**。ただし GA 設定は不変、`max_clause` も不変。Run-28 は「挙動変更なしの診断 Run」にするべきです。

**Q1: P1 再判定**
- 判定: **P1 は主目的としては不要**
- 理由: `fitness_pen = trade_sharpe_raw - alpha * size_norm` が SSOT で、run-27 best の検算も一致しているため、Round 1 の矛盾仮説は反証済み。
- ただし: 個体別 `fail_reason` 可視化は価値が残るが、それ単体を Run-28 の主施策にするほどではない。
- 扱い: P1 は「契約監査」ではなく、Run-28 diagnostic の一部ログ項目へ格下げ。

**Q2: P3 前倒し判定**
- 判定: **REJECT for Run-28 / Run-29 以降に MODIFY**
- 理由: `max_clause 1→2` は Structural ではなく Principled Parametric 寄りだが、現時点では root cause が未分解。
- 問題: `max_clause=2` は表現力だけでなく `n_nodes`、size penalty、探索空間、過剰取引構造を同時に変えるため、1 RUN では因果が読めない。
- 条件: Run-29 以降にやるなら `same seed × clause=1/2` の AB とし、`trade_count`、`fitness_pen`、`size_norm`、`raw_sharpe` を同時比較する。

**Q3: 採用案**
- 提案: **Stage A 全滅の root cause diagnostic instrumentation**
- 変更分類: **Structural**
- target_metric: `fitness_pen` 分解、`trade_sharpe_raw` 分布、`size_norm` 分布、`trade_count` 分布、`n_nodes` 推移、`NO_EXPOSURE`/`over_trading`/`below_threshold` 理由別件数
- failure_mode: Stage A pass=0 の原因が `primitive 表現力不足`、`探索 dynamics`、`config/penalty 設計` のどれか不明
- causal_path: raw signal が弱いのか、size penalty で落ちているのか、過剰取引で net が死んでいるのか、世代選択が短い genome に潰しているのかを分離する
- falsification: `trade_sharpe_raw` 自体が全世代で天井なら primitive 仮説、raw はあるが `fitness_pen` で落ちるなら penalty/config 仮説、世代で diversity/n_nodes が崩壊するなら探索 dynamics 仮説
- success_criterion: Run-28 後に Run-29 の打ち手を 1 つに分類できること

**Q4: North Star 距離**
- `trade_sharpe_raw` が live 基準から約 1000 倍遠いなら、`max_clause 1→2` 単体を「改善施策」として扱うのは弱いです。
- ただし primitive 改革へ即ジャンプするのも premature。まず「raw edge が全く無い」のか「評価・探索・penalty で潰している」のかを分ける必要があります。
- よって Run-28 は成果改善ではなく、North Star に向けた **誤った次手を防ぐ診断 Run** と位置付けるべきです。

**最終決定**
- Run-28: **(c) diagnostic instrumentation**
- GA 設定: **不変**
- `max_clause`: **1 のまま**
- P1: **反証済みのため主施策から除外**
- P3: **Run-28 診断結果で root cause が表現力不足に寄った場合のみ Run-29 候補**