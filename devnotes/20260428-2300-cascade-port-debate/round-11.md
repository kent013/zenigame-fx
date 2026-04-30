**結論**
今回の fresh design で一番重要なのは、`canonical 5 は gate metric`、`GA の Pareto objective は 3 本`と分離することです。ここを分離すると、`5 指標だから NSGA-III`、`6 通貨あるから 6 lane`、`3 年あるから全部使う`という default 固執が全部外れます。私の提案は、`tier1 は EUR_JPY の 1 lane`、`dataset は rolling 24m`、`GA は NSGA-II + full CPPS(ただし exec_floor なし)`、`canonical 5 は session-based`、`P2 は session 3 のみ`です。35m 化、6 lane 並列、trade-level win_rate 維持は、現段階では全部筋が悪いです。([research.birmingham.ac.uk](https://research.birmingham.ac.uk/en/publications/a-fast-and-elitist-multi-objective-genetic-algorithm-nsga-ii/))

**前提**
- 固定条件として採用するのは、あなたが列挙した思想、7 段カスケード、live_criteria 使命、invariant fail-fast、cross-pair shadow 非選抜、P2 主軸=session 3、3 層流入、emergency mode、calibrate-gate 凍結窓です。
- 後方互換性、既存 default、過去 RUN 接続性は拘束条件から外します。
- 反証起点で進めるので、各提案には「なぜ別案を落としたか」を付けます。

**反証起点**
- `35m / 3y を primary dataset にする案`は落とします。24m でも M1 bar は約 105 万本あり、35m は約 153 万本で約 46% 重く、3 年は約 158 万本で約 50% 重いです。Lo/Tashman/Bailey 系が問題にしているのは「生の bar 数不足」より「依存構造」「rolling OOS」「multiple testing」「selection inflation」なので、tier1 の compute は長期化より layered OOS に回すべきです。([rpc.cfainstitute.org](https://rpc.cfainstitute.org/research/financial-analysts-journal/2002/the-statistics-of-sharpe-ratios))
- `6 lane 並列案`も落とします。`pop=256, gen=64` の総評価回数は 16,384 で、これを 6 lane に均等配分すると lane あたり約 2,731 評価しか残りません。64 generation を維持すると lane あたり pop は約 43、pop=256 を維持すると gen は約 11 まで落ちるので、Pareto front coverage が壊れます。cross-pair shadow は validation axis のままでよく、search lane にしてはいけません。
- `5 指標 = 5 objective だから NSGA-III`も落とします。NSGA-III は many-objective、特に 4+ objective を主対象に導入された手法です。今回の 5 指標は gate であって Pareto objective ではなく、search objective を 3 本に保てるので、NSGA-II で十分です。([research.birmingham.ac.uk](https://research.birmingham.ac.uk/en/publications/a-fast-and-elitist-multi-objective-genetic-algorithm-nsga-ii/))
- `5th metric として trade-level win_rate を維持する案`も落とします。tier1 では「trade 勝率」、graduation lane では「pair-level 勝率」になって意味が変わるからです。5th metric は semantic invariant でなければいけません。FX の intraday は sessionality が強いので、勝ち負けの単位を trade ではなく ex ante な session-block に置く方が自然です。([scholars.northwestern.edu](https://www.scholars.northwestern.edu/en/publications/deutsche-mark-dollar-volatility-intraday-activity-patterns-macroe/))

**観察事実**
- FX intraday は Tokyo/London/NY で活動量とボラティリティに強い time-of-day pattern があり、USD/JPY・EUR/USD の EBS データでは deal 数と volatility の正相関、deal 数と spread の負相関も確認されています。P2 の一次軸を session 3 に置くのは、経験則ではなく market microstructure と整合しています。([scholars.northwestern.edu](https://www.scholars.northwestern.edu/en/publications/deutsche-mark-dollar-volatility-intraday-activity-patterns-macroe/))
- Sharpe は serial correlation に弱く、Lo は「月次 Sharpe を単純に √12 で年率化できるのは特殊条件だけ」と述べ、相関があると順位すら大きく変わり得ると示しています。したがって M1 return 直列で Sharpe を gate に使うのは危険で、非重複 block ベースに落とすべきです。([rpc.cfainstitute.org](https://rpc.cfainstitute.org/research/financial-analysts-journal/2002/the-statistics-of-sharpe-ratios))
- 単一時系列の OOS 評価では、rolling-origin と multiple test periods が有利です。依存データ向けには hv-block CV のような gap 付き split が理論的に支持されています。金融 backtest 文脈では、単純 hold-out は PBO 推定に不十分とされます。([sciencedirect.com](https://www.sciencedirect.com/science/article/abs/pii/S0169207000000650))
- DSR は selection bias と non-normality を補正し、White RC と Hansen SPA は data snooping / multiple comparison の post-selection audit に向いています。特に Hansen SPA は White RC より poor / irrelevant alternatives に頑健で強力です。これは stage gate というより archive/report の監査指標として使うのが筋です。([papers.ssrn.com](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2460551))
- MOEA 側では、NSGA-II は 2-3 objective の標準基盤、NSGA-III は 4+ objective の many-objective 用、MOEA/D は decomposition による低計算量と 3-objective での均等分布が強みです。一方、CA/DA 二重 archive と push/pull は「feasible region が薄い・遠い」状況で convergence / diversity / feasibility の両立を狙う設計です。今回の mission 探索は後者の性質に近いです。([research.birmingham.ac.uk](https://research.birmingham.ac.uk/en/publications/a-fast-and-elitist-multi-objective-genetic-algorithm-nsga-ii/))

**論点A: 計算リソース・規模**
- 提案は `lane_parallelism=1`、`pop=256`、`gen=64`、`max_workers=floor(0.75 * physical_cores)`、上限 16、下限 8 です。理由は、今回の search objective が 3 本で front coverage を確保したいからで、gen を深くするより pop を厚くする方が archive / warmstart / P2 正規化と相性が良いからです。headroom が出たら `gen` より先に `pop 256 -> 320` を上げます。([research.birmingham.ac.uk](https://research.birmingham.ac.uk/en/publications/a-fast-and-elitist-multi-objective-genetic-algorithm-nsga-ii/))
- 定量目標は `Stage A の front-1 cardinality >= 24`、`front-1 + front-2 >= 64`、`session-bucket entropy >= 0.8` です。これを満たさないなら `pop` が足りません。逆に wall-time が厳しいなら、先に `gen 64 -> 48` を落とし、`pop` は維持します。
- INCONCLUSIVE は `max_workers` の実飽和点です。これは evaluator 実装とメモリ帯域に依存するので、F-1 smoke で `eval/sec/core` を見ないと決まりません。

**論点B: dataset 期間と fold 構造**
- tier1 primary dataset は `rolling 24m` にします。35m は tier1 primary ではなく graduation-lane audit 側に回します。24m でも 105 万 M1 bar あり、primary 問題は「長さ」より「どれだけ独立な OOS block を切れるか」です。([rpc.cfainstitute.org](https://rpc.cfainstitute.org/research/financial-analysts-journal/2002/the-statistics-of-sharpe-ratios))
- 24m を週ベースで `104w` と見なし、partition は `[Stage B zone 70w] [gap 1w] [C-lite 6w] [gap 1w] [C-lite 6w] [gap 1w] [C-lite 6w] [gap 1w] [Stage C 12w]` を推します。これで final holdout を完全に分離しつつ、C-lite を recency 側に置けます。
- Stage A は `8w` proxy window にします。Stage B は `train 36w / embargo max(1w, Lmax) / test 5w / step 5w` の rolling-origin で 6 folds です。5w にする理由は sample-size discipline で、4w test だと session-bucket あたり 28 block しかなく、あなたの C7 基準に引っ掛かるからです。5w なら 35 block / bucket です。([sciencedirect.com](https://www.sciencedirect.com/science/article/abs/pii/S0169207000000650))
- Stage C-lite は `6w x 3 disjoint`、Stage C は `12w contiguous holdout` が最適です。6w C-lite なら 1 bucket あたり 42 block、12w C なら 84 block あるので、session-based canonical 5 を測るには十分です。test 窓が足りない場合は dataset 延長より先に `Stage B 5w -> 6w` を検討します。([rpc.cfainstitute.org](https://rpc.cfainstitute.org/research/financial-analysts-journal/2002/the-statistics-of-sharpe-ratios))
- 反証条件は明確で、`Stage B 5w fold の median trade_count < 30` なら fold が短すぎます。その場合は dataset を 35m にする前に `test=6w` に延ばします。逆に fold で十分 trade があるなら 35m 化の便益は薄いです。

**論点C: canonical 5 の指標構成**
- 私の提案は `Lo-adjusted Sharpe_session / net_pnl_after_cost / max_dd / trade_count / session_block_win_rate` です。ここで `Sharpe_session` は非重複 session PnL series に対する Lo 補正 Sharpe、`session_block_win_rate` は ex ante な pair×session block の黒字率です。([rpc.cfainstitute.org](https://rpc.cfainstitute.org/research/financial-analysts-journal/2002/the-statistics-of-sharpe-ratios))
- これを推す理由は 3 つです。1 つ目は trade-level win_rate の semantic break を消せること、2 つ目は M1 直列相関を避けられること、3 つ目は P2=session 3 と unit が揃うことです。tier1 では single-pair の session block 勝率、graduation lane では multi-pair の pair×session block 勝率になり、同じ「ex ante block の安定性」という意味が保てます。
- `profit_factor`、`expectancy`、trade-level win_rate は canonical 5 から外し、tie-break / monitor に落とします。PF は denominator instability があり、expectancy は net と trade_count の重複が強すぎます。trade-level win_rate は lane を跨ぐと意味が変わるので gate metric としては不適切です。
- 反証条件は、F-1 smoke 後に `session_block_win_rate` が `Sharpe_session` と極端に collinear なら見直します。そのときだけ 5th metric の代替として clipped `profit_factor` を再評価しますが、初期値として trade-level win_rate を残す理由はありません。

**論点D: 多目的 GA の構造選択**
- 採用案は `(a) NSGA-II + full CPPS ただし exec_floor なし` です。ここで CPPS は公開 acronym ではなく、あなたの内部 bundle と理解します。文献的に支持されるのはその構成要素、つまり `NSGA-II`、`CA/DA two-archive`、`push/pull`、`small-feasible-region 対応` です。([research.birmingham.ac.uk](https://research.birmingham.ac.uk/en/publications/a-fast-and-elitist-multi-objective-genetic-algorithm-nsga-ii/))
- Pareto objective は 3 本で固定します。`maximize net_pnl_after_cost`、`minimize max_dd`、`minimize mission_inf_gap` です。`mission_inf_gap` は live_criteria に対する標準化 inf-norm shortfall で、Sharpe_session・total_pnl・max_dd・trade_count range を含みます。canonical 5 全部を objective に入れません。
- NSGA-III は不要です。many-objective の問題にしてしまうのは、gate と objective を混同しているからです。MOEA/D は comparator としてはありですが、主力にはしません。理由は今回の本質が「薄くて離れた feasible region を見つけること」で、scalarization の綺麗さより CA/DA と push/pull の恩恵が大きいからです。([researchgate.net](https://www.researchgate.net/publication/264387359_An_Evolutionary_Many-Objective_Optimization_Algorithm_Using_Reference-Point-Based_Nondominated_Sorting_Approach_Part_I_Solving_Problems_With_Box_Constraints))
- cross-pair shadow と spread_consumption_ratio は objective に入れません。前者は fixed constraint 通り validation axis、後者は fixed constraint 通り tie-break + monitor です。
- 反証条件は `front-1 が population の 70% 以上に膨らみ、dominance discrimination が崩れる` 場合です。そのとき初めて MOEA/D comparator を本気で回します。NSGA-III に飛ぶ順番ではありません。

**論点E: Sieve → Archive → Warmstart の量的設計**
- `pop=256` 前提なら、`archive_total=160`、内訳 `CA=96 / DA=64` を推します。比率で言うと `archive_total ≈ 0.6*pop` です。単一通貨ペアで feasible region が薄いので、zenigame の `cap=100` をそのまま持ってくる理由はありません。([research.birmingham.ac.uk](https://research.birmingham.ac.uk/en/publications/two-archive-evolutionary-algorithm-for-constrained-multi-objectiv))
- `target_inflow/run=10`、`per_run_max=16` にします。一般則は `target_inflow ≈ 0.04*pop`、`per_run_max ≈ 0.06*pop` です。これなら archive の記憶半減期が短すぎず、run ごとの偶然勝ちが archive を埋め尽くしません。
- `warmstart_share=20%` を通常値、`30%` を emergency 値にします。draw 比率は通常 `CA:DA = 2:1`、emergency は `1:1` に寄せます。mission drought 時に convergence seed だけ増やすと diversity が死ぬからです。
- 上限系は `max_per_source_run=2`、`max_per_session_pattern=2`、`max_family=2`、`max_reuse=3`、`cooldown=2 runs`、`rolling_window=6 runs` を推します。`score_bypass K=8`、emergency で `12` に上げます。
- `eviction_score の weighted sum` は初期値として反対です。ここは数値いじりの温床なので、lexicographic に `mission_pass > progress_pass > score_bypass > C-pass-depth > mission_margin > shadow_robustness > novelty > recency` で切る方が良いです。weighted sum は telemetry を見てからで十分です。
- 反証条件は `archive churn > 50% / 3 runs` か、`warmstart seed の子孫が 5 runs 連続で de novo seed を下回る` 場合です。前者なら inflow 過多または cap 過小、後者なら warmstart_share を 15% に落とします。

**論点F: P2 difficulty 軸の数**
- 現時点の最適解は `(i) session 3 のみ` です。volatility 2 や aux regime を P2 本軸に入れるのは早すぎます。FX sessionality 自体は十分強いですが、bucket 数を増やすと per-bucket sample が急減します。([scholars.northwestern.edu](https://www.scholars.northwestern.edu/en/publications/deutsche-mark-dollar-volatility-intraday-activity-patterns-macroe/))
- 私の提案した Stage B 5w fold だと、3 bucket では 1 bucket あたり 35 session block、6 bucket では 17.5 block です。C-lite 6w でも 3 bucket は 42、6 bucket は 21 です。つまり 6 bucket は Stage B/C-lite の両方であなた自身の sample-size discipline を踏みます。
- したがって `volatility_2` と `aux-regime` は monitor / archive metadata に留めます。selection 圧に入れるのは graduation lane か、少なくとも F-1 smoke 後です。
- 6 bucket 解禁条件は `Stage B の median trades_per_bucket >= 30`、`C-lite >= 50`、`front-1 >= 48`、`session entropy >= 0.8` の同時成立です。満たさない限り session 3 を守るべきです。

**論点G: 適用順序**
- Round 12 以降の依存順は `B -> C -> D -> A -> E -> F -> G` です。dataset/fold を先に決めないと sample unit が決まらず、sample unit が決まらないと canonical 5 も objective も決まりません。
- 実装 Phase の順序は `設計 doc` → `metric/schema contract` → `dataset splitter / embargo contract` → `Stage A/B/C-lite/C evaluators` → `NSGA-II + CA/DA + push/pull core` → `Sieve/archive/warmstart/emergency` → `PBO/DSR/SPA + observability` → `graduation lane scaffold` が良いです。PBO/DSR/SPA は early gate ではなく archive/report 層に置きます。([papers.ssrn.com](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2460551))
- `archive スキーマ伝搬漏れ` を防ぐため、コード実装前に `mission_inf_gap`、canonical 5、session-block diagnostics、shadow metadata、archive admission reason の schema を確定させるべきです。ここを後回しにすると禁止事項 8 を踏みます。

**Round 12 の優先順**
- 最優先は `B` です。5w / 6w / 12w の時間単位を確定しないと、C7 を満たす metric unit を設計できません。
- 次が `C` です。`session_block_win_rate` を採るかどうかで canonical 5 と `mission_inf_gap` の構造が変わります。
- その次が `D` です。objective 3 本を固定して初めて NSGA-II + CPPS の細部が決まります。
- `A` はそのあとです。pop/gen/max_workers は evaluator 実装の実測 throughput に依存するので、設計だけ先に固定しても数字はまだ揺れます。
- `E` と `F` は `A` の結果を見て詰めるべきです。archive cap と bucket 数は compute と sample size の両方に依存します。
- `G` は最後でよいです。

**INCONCLUSIVE**
- `pop=256` と `320` の最終確定は F-1 smoke の `front-1 size` と wall-time 実測待ちです。
- `max_workers` の飽和点は hardware/evaluator 実装依存なので未確定です。
- Stage B `train=36w` が最適か `40w` が最適かは、trade density と drift の実測待ちです。
- `session_block_win_rate` の canonical 5 採用はかなり有力ですが、Sharpe_session と過度に collinear なら差し替え余地はあります。
- graduation lane の primary dataset を `35m` にするか `30m` にするかは、tier1 で mission-pass 候補が出てからの方が筋です。
- weighted eviction は今は採りませんが、archive telemetry が十分集まれば再議論余地はあります。

**残っている default 固執**
- `5 指標あるから 5 objective` という固執。
- `6 通貨あるから 6 lane` という固執。
- `bar が多いほど統計的に強い` という固執。Lo の論点はそこではありません。([rpc.cfainstitute.org](https://rpc.cfainstitute.org/research/financial-analysts-journal/2002/the-statistics-of-sharpe-ratios))
- `win_rate は trade 勝率であるべき` という固執。
- `archive は weighted sum で掃除するもの` という固執。
- `35m は 24m より常に優れる` という固執。
- `max_workers は config の定数` という固執。
- `shadow pair を selection 圧に入れた方が robust` という固執。
- `4w fold は自然` という固執。今回の discipline では 5w の方が自然です。

次に詰めるべきは `B` と `C` です。ここが固まれば、D/A/E/F はかなり機械的に落ちます。