全体判定: **CHANGES_REQUESTED**

**Fact**
- 現行の Alpha Factory 本流は [run_ga.py](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py#L110) の `selection_score = (stage_c_pass, stage_b_pass, stage_a_pass, fitness_pen)` で選抜しており、トーナメントと elite もこの辞書式順序を使っています。[run_ga.py](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py#L363) [run_ga.py](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py#L382) [run_ga.py](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py#L470)
- Stage A は `trade_count < 1` で `reason_codes=("no_trades",)` にしますが、その場合 `fitness_raw` / `fitness_pen` は計算されず `None` のまま payload に入ります。[stage_gate.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/stage_gate.py#L302) [stage_gate.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/stage_gate.py#L325)
- archive 側は row template の既定値として `fitness_raw=0.0`, `fitness_pen=0.0` を持ち、`collect_stage_a` でも payload 欠落時は `_required_float(..., default=0.0)` でそのまま 0.0 を保存します。[archive.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/archive.py#L101) [archive.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/archive.py#L337)
- Run 9 の summary では全世代で `stage_a_pass=0`, `stage_b_pass=0`, `stage_c_pass=0`, `best_fitness_pen=0.0` で、best は `g0_i1`, `trade_count=0`, `selection_score=[0,0,0,0.0]` です。[summary.json](/Users/ishitoya/repository/zenigame-fx/reports/run-reports/run-9/summary.json#L45) [summary.json](/Users/ishitoya/repository/zenigame-fx/reports/run-reports/run-9/summary.json#L107)
- Run 9 の archive [genomes_run_20260425_002330.parquet](/Users/ishitoya/repository/zenigame-fx/.cache/alpha_factory/runs/genomes_run_20260425_002330.parquet) を直接読むと、120 行中 `trade_count=0` が 90、`trade_count>0` が 30、`fitness_pen max=0.0`, `mean=-8.91`、`trade_count>0` 部分の `sharpe` は全て負でした。
- 提案書が主変更点として挙げている [src/ga/runner.py](/Users/ishitoya/repository/zenigame-fx/src/ga/runner.py#L90) は、確かに `fitness_pen` 単独で選抜しますが、Alpha Factory 本流の Run 9 経路では使われていません。[runner.py](/Users/ishitoya/repository/zenigame-fx/src/ga/runner.py#L104) [runner.py](/Users/ishitoya/repository/zenigame-fx/src/ga/runner.py#L183)
- `ga.min_exposure_trade_count` を足しても、現状の loader はその項目を読みません。[config.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/config.py#L101) [config.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/config.py#L243)

**Interpretation**
- 「無取引で `fitness_pen=0` が選ばれる」現象自体は、Run 9 については現行コードで実際に起きていると言えます。
- ただし、因果列は提案書の `runner._tournament / evaluator.meta` ではなく、「Stage A の `no_trades` で `fitness_pen=None` → archive が 0.0 に正規化 → Run GA が全員 `stage_*_pass=0` の局面で `fitness_pen` を最後の tie-break に使う」です。ここを誤ると対策ファイルも誤ります。

1. 使命との整合性  
[Warning] 方向性自体は使命に整合していますが、「正 Sharpe 個体が発生する素地」「Stage B/C 到達率が改善」とまで言い切るのは強すぎます。Run 9 から確実に言えるのは「無取引個体の構造的優位を消すと、少なくとも trivial な no-trade plateau は崩せる」です。  
修正提案: 期待効果は「無取引優位の除去」「評価可能個体への選抜圧回復」までに落とし、成功判定を `trade_count=0 比率`, `best_no_trade_rate`, `stage_a_pass 件数` に置き換えてください。

2. 禁止事項違反  
[Suggestion] `live_criteria.trade_count_min` を緩めていないので #4 には直接抵触しませんし、無取引優位の除去は #6 の趣旨にも沿います。  
[Warning] ただし `min_exposure_trade_count` を大きくすると、実質的に新しい hard gate になります。  
修正提案: `0 < min_exposure_trade_count < live_criteria.trade_count_min` を不変条件として明記し、初期値は 1 か 2 程度の極小値に固定してください。

3. 実現可能性  
[Critical] 実装対象が現行コード経路とずれています。提案書は [conceptual-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260425-0937-risk-no-trade-fitness-guard/conceptual-design.md#L63) で `src/ga/runner.py` と `evaluator.meta['trade_count']` を主対象にしていますが、Run 9 を再発させた本流は [run_ga.py](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py#L110) と [stage_gate.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/stage_gate.py#L302) と [archive.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/archive.py#L337) です。  
修正提案: 変更対象を `src/alpha_factory/stage_gate.py`, `src/alpha_factory/archive.py`, `scripts/alpha_factory/run_ga.py`, `src/alpha_factory/config.py` に置き直してください。`src/ga/runner.py` は別系統なので scope out が妥当です。
[Warning] `ga.min_exposure_trade_count` を YAML に追加しても現状 loader が取り込みません。  
修正提案: [config.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/config.py#L101) の `GAConfig` と [config.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/config.py#L243) の `_build_ga` までセットで更新対象に含めてください。
[Warning] `evaluator.meta['trade_count']` は Alpha Factory 本流では SSOT ではありません。  
修正提案: `trade_count` は Stage A payload / archive row を SSOT としてください。

4. 期待効果の妥当性  
[Warning] C3/C7 の観点で、`trade_count>0` の 30 個体だけを見て「だから no-trade を罰すれば正 Sharpe に進化する」は言えません。これは `trade_count>0` で条件づけた集合で、しかも単一 Run の境界的サンプルです。  
修正提案: 効果主張を「no-trade dominance の解消」に限定し、`positive sharpe emergence` や `Stage B/C 改善` は仮説に降格してください。
[Suggestion] 反証設計としては 3-5 seed で `best_no_trade_rate` と `stage_a_pass_count` を比較するのが最小です。

5. リスク  
[Warning] `_NO_EXPOSURE_FITNESS=-1e10` は既存の `_FAILURE_FITNESS=-1e12` と序列が中途半端です。設計意図次第では「system failure より no exposure の方がマシ」という意味になります。  
修正提案: sentinel の序列を明示するか、既存 failure sentinel に寄せて一貫性を取ってください。
[Warning] `reason='no_exposure'` を archive で追跡すると書いていますが、現行 schema にその列はありません。[archive.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/archive.py#L54)  
修正提案: 初手は `trade_count` と `fitness_pen` だけで診断し、必要なら別タスクで bounded enum / bool を追加してください。

6. スコープの適切さ  
[Warning] archive schema 変更まで入れると、schema guard・tests・report 生成まで波及します。概念設計の割に広がりが大きいです。  
修正提案: Phase 1 は schema 無変更で selection 修復だけに絞り、診断列追加は別施策に分けてください。

7. メモリ制約  
[Suggestion] scalar config と bool/int 1 列程度なら 24GB × 6 ワーカーで問題ありません。  
[Suggestion] ただし archive に自由文字列 reason を積むのは避け、必要でも bool か短い enum に留めてください。

8. 前提検証 (C4)  
[Critical] 「無取引で `fitness_pen=0` が選ばれる」は verified ですが、提案書の根本原因記述 [conceptual-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260425-0937-risk-no-trade-fitness-guard/conceptual-design.md#L14) は現行コードと不一致です。  
修正提案: 背景節を「`evaluate_stage_a(no_trades)` では `fitness_pen=None`、`collect_stage_a` が 0.0 に落とし、`run_ga` が pass bit 全滅時にその 0.0 を勝たせる」という verified chain に差し替えてください。
[Suggestion] regression test は `run_ga` 側で「`trade_count=0, fitness_pen=0.0` の個体が、`trade_count>0, fitness_pen<0` の個体より勝つ現象」を再現し、その逆転を確認する形が適切です。

9. Design-first (C1)  
[Critical] 最新の orchestrator / archive / config loader を先に読まず、generic runner を主対象に据えているため、Design-first を満たしていません。  
修正提案: 根拠参照を [docs/alpha_factory/README.md](/Users/ishitoya/repository/zenigame-fx/docs/alpha_factory/README.md), [run_ga.py](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py), [stage_gate.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/stage_gate.py), [archive.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/archive.py), Run 9 summary/parquet に更新してください。

結論として、問題認識そのものは正しいです。修正が必要なのは「どこが原因で、どこを直すべきか」です。現案のままでは Run 9 を生んだ本流に効かないので、設計を一段書き直してから詳細設計に進むべきです。