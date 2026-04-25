全体判定: **APPROVED**

1. [Suggestion] 使命との整合性  
無取引個体が `fitness_pen=0` により取引個体の負 Sharpe を恒常的に上回る現象を、selection 順序だけで下位化する方針は、`live_criteria.trade_count_min` 達成に向けたボトルネックに直接効いています。改善計画の Critical #1 とも整合しています。[improvement-plan.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260425-0931-fx-improve/improvement-plan.md#L7) [run_ga.py](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py#L101)

2. [Suggestion] 禁止事項違反  
Round 1 の問題だった archive 意味論破壊は、archive 列を一切変えない方針で解消されています。現行 selection は cache 上の辞書式比較だけで決まり、archive canonical の `fitness_pen` / `total_pnl` は維持されるため、「GA ハック」の中でも許容境界に収まっています。[run_ga.py](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py#L111) [genome-archive-schema.md](/Users/ishitoya/repository/zenigame-fx/docs/alpha_factory/concepts/genome-archive-schema.md#L27)

3. [Suggestion] 実現可能性  
現行実装でも selection は `IndividualCacheEntry.selection_score` のみを参照しており、archive row には `trade_count` が既に存在します。したがって archive を触らず `feasible_trade` を cache 導出で足すだけで目的は達成可能です。[run_ga.py](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py#L111) [run_ga.py](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py#L444) [genome-archive-schema.md](/Users/ishitoya/repository/zenigame-fx/docs/alpha_factory/concepts/genome-archive-schema.md#L33)

4. [Warning] 期待効果の妥当性  
`best_no_trade_rate -> 0` は言い切りが強すぎます。少なくとも最終母集団に `feasible_trade=True` 個体が 1 体以上いる場合、という条件付きに落とすべきです。全個体 `trade_count=0` の run ではこの施策だけでは 0 になりません。  
修正提案: 成功基準を「`feasible_trade=True` 個体が存在する run では best が no-trade にならない」に変更し、5 RUN smoke は descriptive に限定すると明記してください。

5. [Suggestion] リスク  
calibrate-gate 汚染の懸念は、archive `fitness_pen` を保持する限り解消されています。今回の施策は selection cache の tie-break 追加であり、quantile 母集団そのものには手を入れません。この点は Round 1 指摘に対して十分改善されています。[genome-archive-schema.md](/Users/ishitoya/repository/zenigame-fx/docs/alpha_factory/concepts/genome-archive-schema.md#L28)

6. [Warning] スコープの適切さ  
設計の本体は selection 専用に絞れており良いです。ただし「変更ファイルは `run_ga.py` 1 ファイルに限定」という表現は現状契約と食い違います。summary の `selection_score` 長さを固定で見ている test と、4 要素 tuple を説明している report が既にあります。  
修正提案: スコープ文言を「production logic の変更は `run_ga.py` のみ。追従として test / report / docs 更新あり」に修正してください。[run_ga.py](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py#L653) [test_alpha_factory_run_ga.py](/Users/ishitoya/repository/zenigame-fx/tests/scripts/test_alpha_factory_run_ga.py#L394) [generate_run_report.py](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/generate_run_report.py#L449)

7. [Suggestion] メモリ制約  
`bool` 1 個の追加は無視できる水準で、この観点の懸念はありません。

8. [Warning] 前提検証 (C4)  
`feasible_trade = row.trade_count >= 1` は実装可能ですが、その `trade_count` は archive SSOT 上「Stage A→B→C で最後段が prevail」です。つまり意味は「どこかで一度でも取引した」ではなく「その row の canonical trade_count が 1 以上」です。ここを本文で明示しないと解釈がぶれます。  
修正提案: 前提節に「`feasible_trade` は archive canonical `trade_count` 由来であり、ever-traded 判定ではない」と 1 文追加し、必要なら回帰テストでその意味を固定してください。[genome-archive-schema.md](/Users/ishitoya/repository/zenigame-fx/docs/alpha_factory/concepts/genome-archive-schema.md#L33) [run_ga.py](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py#L444)

9. [Suggestion] Design-first 原則 (C1)  
改善計画の `#1=selection-fix` と `#2=PnL audit` の分離を守れており、Round 1 の scope 混線は解消されています。設計先行の筋は通っています。[improvement-plan.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260425-0931-fx-improve/improvement-plan.md#L7)

補足すると、今回の revised 案は Round 1 の Critical 4 件に対して本質的には解消できています。残るのは「期待効果の表現を弱めること」と「1 ファイル限定の言い方を契約に合わせること」の 2 点です。