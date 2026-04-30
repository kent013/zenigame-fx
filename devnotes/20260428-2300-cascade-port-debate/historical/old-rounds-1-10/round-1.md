**前提**
- このラウンドは、あなたが本文で与えた要約を暫定の設計ソースとして扱います。
- `T508/T509/T511/T513` のローカル設計本文、fx 側の現コード、git 履歴は、あなたの「コマンド実行禁止」制約のため未検証です。したがって、ここでの結論は「設計仮説の優先順位づけ」であり、「実装監査の確定診断」ではありません。
- 反証から始めます。早期結論は避けます。

**0. 反証から入る暫定仮説**
1. **H1**: `6カ月`の現行 dataset だけでは、zenigame の `3窓 × canonical 5` をそのまま disjoint に移植するのは無理がある。崩れる条件は、期間延長なしでも `C-lite` の窓重複依存が小さく、rotation を変えても上位個体の集合が安定し、最終 holdout 成績も落ちないことです。([papers.ssrn.com](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4366573))
2. **H2**: `canonical 5` は worst のまま維持し、FX 固有項目はまず `constraint / invariant / tie-break` に分解すべきです。崩れる条件は、FX 固有項目が canonical 5 条件付きでも Stage C 失敗を強く予測し、かつ undertrading を誘発しないことです。([papers.ssrn.com](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2460551))
3. **H3**: `pop=40, gen=15` では `CPPS` のフルポートより、軽量版のほうが先に falsify されるべきです。崩れる条件は、軽量版が family 多様性を維持できず、可行領域に入れず、full CA/DA だけが明確に改善することです。([research.birmingham.ac.uk](https://research.birmingham.ac.uk/en/publications/two-archive-evolutionary-algorithm-for-constrained-multi-objectiv?utm_source=openai))
4. **H4**: `P2` はまず `volatility regime` を主軸に置き、`session` は二次軸か archive tag に留めるべきです。崩れる条件は、vol だけでは失敗様式を説明できず、session を足したときだけ安定に OOS が改善することです。([kellogg.northwestern.edu](https://www.kellogg.northwestern.edu/academics-research/research/detail/1998/deutsche-mark-dollar-volatility-intraday-activity-patterns-macroeconomic-announcements/))
5. **H5**: `Archive→Warmstart` は必要だが、`sieve_share=0.33` は fx では強すぎる可能性が高い。崩れる条件は、0.33 を入れても新規 family が死なず、archive 由来個体が holdout で継続優位を示すことです。([papers.ssrn.com](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2326253))

**1. 論点間の相互依存マップ**
- `論点1 (stage/data plan)` は最上流です。ここで `6カ月で何窓置けるか` と `Stage B を gate として残すか` が決まらないと、`P2` も `CPPS` も決まりません。
- `論点2 (canonical 5 vs FX 固有指標)` は `margin_inf` の定義、`exec_floor` の意味、`sieve_score` の対象を決めるので、`論点3/5` の前提です。
- `論点4 (P2)` は `C-lite` の粒度、archive の diversity constraint、warmstart の多様性単位を決めるので、`論点3/5` の前提です。
- `論点3 (CPPS scope)` は `Archive/Warmstart` の器を決めるので、`論点5` の前提です。

提案する議論順は `1 → 2 → 4 → 3 → 5` です。  
合議の単位は次の 4 つに切るのがよいです。
1. `Topology`: A/B/C-lite/C/AS の役割と dataset plan
2. `Objective Taxonomy`: worst に入れるもの、constraint に落とすもの、順位補助に留めるもの
3. `Regime Taxonomy`: P2 と spectral の最小構成
4. `Loop Closure`: CPPS, Archive, Warmstart の範囲

**2. 各論点の論争軸**

**論点1: Stage 構造と dataset plan**

`事実`  
現行条件 `2025-10-01〜2026-04-01` の約 6 カ月で、`1 fold = 71営業日` なら、`3本の独立 fold` を置くには約 200 営業日前後が必要です。つまり、zenigame の `3窓` をそのまま disjoint に置くのは物理的に難しく、現状でやるなら重複窓か期間延長が前提です。加えて、time-series CV では validation sample size 自体が効き、同じ履歴を fold 数だけ増やしても独立な regime support は増えません。複数候補を同じ履歴で選び続けると、White の data snooping 問題、Hansen の SPA、Bailey らの PBO、Bailey & López de Prado の DSR が警告する selection inflation が強くなります。FX の intraday は sessionality と volatility persistence が強く、window の切り方だけでごまかしにくいです。([papers.ssrn.com](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4366573))

`解釈`  
したがって、`18-24カ月延長`、`6カ月のまま fold 増`、`6カ月 rotation` は同格ではありません。  
`fold 増` は boundary sensitivity の検査にはなりますが、新しい市場状態を増やしません。  
`rotation` は across-run の頑健性検査にはなりますが、within-run の情報量不足を埋めません。  
`期間延長` だけが genuinely 新しい state support を増やします。ただし古い regime を入れ過ぎると recent-fit を壊すので、延長したとしても period-aware な quota か recency-aware な扱いが必要です。これは推論です。([papers.ssrn.com](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4366573))

`主要な対立軸`
- **A: 18-24カ月延長を前提に再設計する**
- **B: 6カ月のまま fold を増やして凌ぐ**
- **C: 6カ月 rotation を複数 run に分散して凌ぐ**
- **D: hybrid**
  6カ月で再設計は先に進めるが、`C-lite` と `P2` は 6カ月で成立する最小構成に落とし、18-24カ月化は別タスクに切る

`私見`  
Round 1 の暫定順位は `D > A > C > B` です。  
理由は、`B` は逆ピラミッド是正には役立っても、3窓化と rich P2 の根拠には弱いからです。`C` は archive 汚染を起こしやすい。`A` は理にかなうが、設計を data acquisition にロックする危険がある。  
`Stage B` の full IS monitor は、gate としては撤廃寄りです。残すなら「上位少数個体にだけ当てる global audit」に役割変更すべきです。full-history を中流 gate に置くと、最も重い backtest を最も多くの個体にかけるうえ、selection bias も強めます。これは推論です。([papers.ssrn.com](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2326253))

`想定される反証データ`
- `A` が崩れる条件: 18-24カ月に延ばしたのに recent holdout と cross-pair shadow が悪化し、winner が stale regime 依存になる。
- `B` が崩れる条件: fold 増後も rotation 変更で elite の顔ぶれが激変し、Stage C 到達率が安定しない。
- `C` が崩れる条件: rotation ごとの winner overlap が低いのに、archive/warmstart を通すと同じ family だけが自己増殖する。
- `Stage B 撤廃` が崩れる条件: 撤廃後に full-span catastrophic DD や trade drought が増え、A/C-lite/C だけでは拾えない global pathology が頻発する。

**論点2: canonical 5 worst aggregation の fx 適用**

`事実`  
PBO, DSR, White, Hansen, Harvey/Liu が共通して言っているのは、見つけたあとに ranking axis を増やすほど、見かけの有意性が膨らむことです。FX では bid-ask spread が volatility や inventory/overnight risk と結びつくことは文献的にも自然ですが、それは「edge の objective」でもあれば「execution の constraint」でもありえます。そこを混ぜると設計が壊れます。([papers.ssrn.com](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2326253))

`解釈`  
ここは `objective / constraint / invariant / rank-aid` の分離が要ります。  
私の暫定整理は次です。
- `canonical 5` は worst のまま維持する
- `spread_consumption_ratio` はまず tie-break か exec-floor 候補
- `session_close_drop_count` は intraday 制約の compliance metric
- `negative_equity_drop_open_count` は invariant breach なので fail-fast

理由は単純で、`spread` はすでに cost-adjusted PnL / Sharpe / spread stress に二重に乗る可能性が高く、worst に入れると「取引を減らして spread を食わない個体」が有利になりやすいからです。これは禁止事項 6 と衝突します。`session_close_drop_count` も worst に入れると、close 近辺を避けて trade_count を減らす方向に圧がかかる。`negative_equity_drop_open_count` は最適化対象ではなく、そもそも発生してはいけない種類の病変です。これは推論です。([papers.ssrn.com](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2460551))

`主要な対立軸`
- **A: FX 固有指標も worst に入れて 6〜8 指標化する**
- **B: canonical 5 は閉じたまま、FX 指標は constraint / tie-break に分ける**
- **C: canonical 5 から `win_rate` を外し、FX 指標と置換する**

`私見`  
暫定支持は `B` です。  
ただし唯一保留をかけるなら `win_rate` です。mission は `Sharpe / Total PnL / Max DD / Trade Count 範囲` を名指しており、`win_rate` は mission-level 指標ではありません。  
なので「faithful port を優先するなら win_rate を残す」「fx 適応を優先するなら、将来的に最初に demote 候補になるのは win_rate」という整理が妥当です。今すぐ入れ替える理由はまだありません。これは推論です。([papers.ssrn.com](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2326253))

`想定される反証データ`
- `spread_consumption_ratio` を worst に上げるべき条件: canonical 5 条件付きでも Stage C 落ちを強く予測し、trade_count を不自然に削らず、cross-pair でも頑健。
- `session_close_drop_count` を worst に上げるべき条件: close drop が単なる時計境界 artifact ではなく、実際に overnight attempt や spread stress failure に直結する。
- `win_rate` を demote すべき条件: 他の 4 指標条件付きで増分情報がほぼなく、むしろ skew を使う有効個体を落としている。
- `negative_equity_drop_open_count` が ranking metric で足りる条件: ありません。非ゼロなら selection の問題ではなく simulator/accounting 設計の問題です。

**論点3: CPPS フルポート vs 軽量版**

`事実`  
CA/DA の two-archive と push/pull は、 constrained MOEA の文脈では筋のよい設計です。Li らの TAEA は convergence / diversity / feasibility の分離を正面から扱い、Fan らの PPS は infeasible region を push で横断してから pull で feasible PF に寄せる考え方を明示しています。small feasible region 向けの派生研究でも、CA/DA と cooperative mating の有効性が繰り返し出ています。一方で、AMGA2 系は very small working population と external archive の組み合わせで速い収束を狙います。([research.birmingham.ac.uk](https://research.birmingham.ac.uk/en/publications/two-archive-evolutionary-algorithm-for-constrained-multi-objectiv?utm_source=openai))

`解釈`  
だから争点は「CPPS が正しいか」ではなく、「`pop=40, gen=15` に full stack を載せる帯域があるか」です。  
私の暫定見解は、**full port をいきなり入れる根拠はまだ薄い** です。  
`CA/DA + Push/Pull FSM + exec_floor warmup→ramp→hard` まで入れると、有限の 15 世代が状態推定に吸われます。  
fx の first port は、次のいずれかが現実的です。
- **軽量案**: `single working population + external archive + (net, dd, margin_inf)` の 3軸 Pareto
- **中間案**: 上記に `one-switch` の push→pull と単純な exec floor を足す
- **フル案**: CA/DA と FSM まで入れる

私は `中間案 > 軽量案 > フル案` で見ます。  
理由は、full two-archive の思想自体は有効でも、いまの compute では「理論上必要な状態分離」が「単なるサンプル希薄化」になりやすいからです。これは推論です。([research.birmingham.ac.uk](https://research.birmingham.ac.uk/en/publications/two-archive-evolutionary-algorithm-for-constrained-multi-objectiv?utm_source=openai))

`主要な対立軸`
- **A: full CA/DA + PPS/FSM をそのまま移植**
- **B: single archive + margin_inf 追加だけ**
- **C: single working population + external archive + one-switch feasibility control**

`exec_floor` について  
fx では `execution metric` が zenigame より単純そう、という直感はかなり妥当です。  
ただし `intraday-only`, `spread`, `negative-equity`, `cross-pair shadow` を明示制約として持つなら、exec_floor は「複雑な多段 FSM」より「少数の hard/soft floor」に落としたほうが役割が明確です。  
full ramp が必要なのは、execution failure が世代の早期探索にとって有益なノイズである場合だけです。そこは未検証です。これは推論です。([sciencedirect.com](https://www.sciencedirect.com/science/article/pii/S2210650218300233))

`想定される反証データ`
- `軽量案` が崩れる条件: feasible ratio が最後まで立ち上がらず、同一 family に早期収束し、cross-pair shadow で壊滅する。
- `フル案` が正当化される条件: CA/DA 分離でのみ diversity entropy と feasible discovery rate が改善する。
- `FSM` が不要と分かる条件: one-switch で full FSM と同等の可行化と最終成績が出る。
- `exec_floor 簡略化` が崩れる条件: 簡略版だと economic metrics は通るのに execution pathologies が後段に大量流入する。

**論点4: P2 次元の fx 再定義**

`事実`  
FX intraday には session 別の activity / volatility pattern があり、volatility clustering と regime switching も強いです。さらに cross-rate は volatility interdependence の主要経路になりえます。したがって P2 に regime-aware な軸を入れる発想自体は正しいです。([kellogg.northwestern.edu](https://www.kellogg.northwestern.edu/academics-research/research/detail/1998/deutsche-mark-dollar-volatility-intraday-activity-patterns-macroeconomic-announcements/))

`解釈`  
ただし `P2` は **外生的で、低コストで、サンプルが足りる** 軸でなければいけません。  
この基準で切ると、私は次の整理です。
- `(a) volatility regime`: **主軸候補**
- `(b) session bucket`: **副軸候補**
- `(c) aux factor regime`: **将来候補**
- `(d) cross-pair shadow`: **validation axis、P2 主軸ではない**
- `(e) period bucket`: **temporal robustness axis、P2 主軸ではない**
- `(f) regime_pass_pattern`: **archive diversity tag。P2 にしてはいけない**

一番危険なのは `(f)` です。`regime_pass_pattern` は outcome-derived なので、これを difficulty normalization に使うと selection の結果で regime を定義する collider になります。  
`(d)` も早期 stage に入れ過ぎると、「EUR_JPY の edge」ではなく「USD 系共通因子への過適応」を拾う危険があります。  
`(e)` は robustness には有効ですが、time-slice 自体を P2 に入れると論点1と二重カウントになります。これは推論です。([kellogg.northwestern.edu](https://www.kellogg.northwestern.edu/academics-research/research/detail/1998/deutsche-mark-dollar-volatility-intraday-activity-patterns-macroeconomic-announcements/))

`主要な対立軸`
- **A: 3 regime**
  `volatility` のみ
- **B: 6 regime**
  `volatility × session(2 super-buckets)` 程度
- **C: さらに aux / cross-pair / period を足す**

`私見`  
現条件では `A` が第一候補です。  
`B` は 18-24カ月化した後の候補です。  
`C` は今やると過剰です。  
理由は単純で、`pop=40` で 6 bucket を切ると、平均 `6〜7個体/bucket` 程度に落ちやすく、C7 の警戒域に入るからです。  
P2 は重くするほど良いのではなく、「難易度正規化に必要な最小限」まで削るべきです。これは推論です。([kellogg.northwestern.edu](https://www.kellogg.northwestern.edu/academics-research/research/detail/1998/deutsche-mark-dollar-volatility-intraday-activity-patterns-macroeconomic-announcements/))

`spectral weight` について  
ここで重要なのは、**weight は pass/fail ではなく rank aid だけに使う** ことです。  
そのうえで私は、3 bucket なら fixed な強傾斜より、`support-aware で緩い配分` を推します。例えば `[0.40, 0.35, 0.25]` くらいが上限で、これ以上の傾斜は現 sample ではノイズを増やしやすいです。  
6 bucket をやるなら、3 bucket weight に `session 2-way split` を掛けて再正規化する形は筋がよいですが、**今は採用しない** のが妥当です。これは推論です。([kellogg.northwestern.edu](https://www.kellogg.northwestern.edu/academics-research/research/detail/1998/deutsche-mark-dollar-volatility-intraday-activity-patterns-macroeconomic-announcements/))

`想定される反証データ`
- `A` が崩れる条件: volatility 3 bucket だけでは failure mode が分離できず、session を足したときだけ Stage C precision が改善する。
- `B` が崩れる条件: 6 bucket 化で各 cell が疎になり、rank が run ごとに不安定化する。
- `aux regime` が主軸化できる条件: missingness が低く、vol/session 条件付きでも増分情報がある。
- `cross-pair shadow` を P2 に上げる条件: early-stage から入れても anchor pair の edge を壊さず、むしろ live_criteria 達成率が上がる。

**論点5: Sieve→Archive→Warmstart の閉じ方**

`事実`  
multiple testing 系の文献が一貫して警告するのは、同じ履歴から選んだ winner を再注入し続けると、探索が discovery ではなく reselection に変わることです。一方で micro-MOEA 系では external archive 自体は有効です。したがって問題は archive の有無ではなく、**feedback loop をどう制限するか** です。([papers.ssrn.com](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2326253))

`解釈`  
fx で持ち込むべき制約は次です。
- `source_run_id cap`: **必要**
- `family_key cap`: **必要**
- `effective_dataset_period cap`: **rotation を採るなら必要**
- `regime_pass_pattern tag`: **必要。ただし diversity 用であり gate ではない**
- `per_seed_min 相当`: **そのまま移植しない**

fx は universe seed がないので、`per_seed_min` を無理に作ると概念がねじれます。  
代わりに `per_run cap + per_family cap + per_period cap(if any)` で十分です。  
`transition_pass` も、zenigame の W3 mixing に対応する構造がないなら、いったん持ち込まないほうが自然です。  
`score_bypass` は anti-extinction 用に必要でも、`top-K` はかなり小さくすべきです。これは推論です。([papers.ssrn.com](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2326253))

`archive cap / inflow / warmstart share` について  
`archive=100` は cap 単独では良し悪しを決められません。重要なのは cap ではなく quota です。  
ただし `pop=40` で `sieve_share=0.33` は、初期個体の約 13 体が archive 由来になる計算なので、single-pair FX では強すぎる疑いがあります。  
暫定仮説としては次です。
- `archive inflow/run`: `6〜10`
- `warmstart share`: `0.15〜0.25`
- `score_bypass K`: `2〜3`
- `transition_pass`: いったん無し

これは「確定値」ではなく、最初に falsify すべき default です。([papers.ssrn.com](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2326253))

`想定される反証データ`
- `share 0.33` が成立する条件: warmstart 由来が Stage A/B を支配しても、新規 family の流入が死なず、holdout 改善も維持する。
- `share 0.15〜0.25` が低すぎる条件: archive 由来がほぼ全滅し、fresh のみに比べて有意な価値を出せない。
- `transition_pass 不要` が崩れる条件: stage handoff で extinction が頻発し、bypass だけでは足りない。
- `per_seed_min 不要` が崩れる条件: run/family/period cap を入れても archive が単一パターンへ集中する。

**3. 学術引用候補**
1. Deb, Pratap, Agarwal, Meyarivan (2002), *A Fast and Elitist Multiobjective Genetic Algorithm: NSGA-II*  
MOEA の基本線。Pareto ranking と diversity の標準参照。([ui.adsabs.harvard.edu](https://ui.adsabs.harvard.edu/abs/2002ITEC....6..182D/abstract))
2. Li, Chen, Fu, Yao (2019), *Two-Archive Evolutionary Algorithm for Constrained Multi-Objective Optimization*  
CA/DA の原典。fx に full two-archive を持ち込むなら必読。([research.birmingham.ac.uk](https://research.birmingham.ac.uk/en/publications/two-archive-evolutionary-algorithm-for-constrained-multi-objectiv?utm_source=openai))
3. Fan et al. (2019), *Push and Pull Search for Solving Constrained Multi-objective Optimization Problems*  
push/pull の原典。FSM 導入の理屈づけ。([sciencedirect.com](https://www.sciencedirect.com/science/article/pii/S2210650218300233))
4. Xia, Dong (2022), *A Novel Two-Archive Evolutionary Algorithm for Constrained Multi-Objective Optimization with Small Feasible Regions*  
「可行領域が狭い」ケースへの two-archive 派生。fx の rare-feasible 問題に近い。([sciencedirect.com](https://www.sciencedirect.com/science/article/pii/S0950705121009503?utm_source=openai))
5. Tiwari, Fadel, Deb (2011), *AMGA2: Improving the Performance of the Archive-based Micro-genetic Algorithm for Multi-objective Optimization*  
small working population と external archive の参考。fx の `pop=40` に近い論点。([tandfonline.com](https://www.tandfonline.com/doi/full/10.1080/0305215X.2010.491549?utm_source=openai))
6. White (2000), *A Reality Check for Data Snooping*  
「同じ履歴で選び続ける」問題の古典。([econpapers.repec.org](https://econpapers.repec.org/RePEc%3Aecm%3Aemetrp%3Av%3A68%3Ay%3A2000%3Ai%3A5%3Ap%3A1097-1126))
7. Hansen (2005), *A Test for Superior Predictive Ability*  
Reality Check より irrelevant alternatives に強い比較法。([papers.ssrn.com](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=264569))
8. Bailey, Borwein, López de Prado, Zhu (2015/2017), *The Probability of Backtest Overfitting*  
PBO / CSCV。Archive→Warmstart の自己強化を疑う理論的背景。([papers.ssrn.com](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2326253))
9. Bailey, López de Prado (2014), *The Deflated Sharpe Ratio: Correcting for Selection Bias, Backtest Overfitting and Non-Normality*  
Sharpe をそのまま gate に置く危険の補正視点。([papers.ssrn.com](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2460551))
10. Harvey, Liu (2015), *Backtesting*  
Sharpe haircut と multiple tests の実務的視点。([papers.ssrn.com](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2345489))
11. Deng (2023), *Time Series Cross Validation: Theoretical Properties and Empirical Performance*  
validation sample size を軽視できない、という論点に直結。([papers.ssrn.com](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4366573))
12. Andersen, Bollerslev (1998), *Deutsche Mark-Dollar Volatility: Intraday Activity Patterns, Macroeconomic Announcements, and Longer Run Dependencies*  
session / announcement / volatility persistence の基本。([kellogg.northwestern.edu](https://www.kellogg.northwestern.edu/academics-research/research/detail/1998/deutsche-mark-dollar-volatility-intraday-activity-patterns-macroeconomic-announcements/))
13. Ito, Hashimoto (2006), *Intraday Seasonality in Activities of the Foreign Exchange Markets*  
Tokyo/London/NY の intraday 差異、volatility と spread の関係。([nber.org](https://www.nber.org/papers/w12413?utm_source=openai))
14. Kinkyo (2020), *Volatility Interdependence on Foreign Exchange Markets: The Contribution of Cross-rates*  
cross-pair shadow を early objective ではなく validation axis とみなす根拠候補。([sciencedirect.com](https://www.sciencedirect.com/science/article/pii/S1062940820301807?utm_source=openai))

**4. fx 文脈での読み替え可能性**
- **そのまま持ち込めるもの**
  `worst = pass/fail`, `majority = prefilter`, `spectral = tie-break` の役割分離。  
  世代内 forced pass による extinction 回避。  
  Archive diversity cap の考え方。
- **読み替えが必要なもの**
  `canonical 5` の意味づけ。  
  `C-lite 3窓` の窓構成。  
  `P2` の regime taxonomy。  
  `warmstart share` と `archive inflow` の量。  
  `exec_floor` の段階数。
- **そのまま持ち込むべきでないもの**
  universe seed 前提の `per_seed_min`。  
  W3 mixing 起源の `transition_pass`。  
  6カ月 dataset のままの rich 6-regime/15-cell。  
  `Stage B full-IS monitor` を gate として残す発想。

**5. C1-C9 discipline チェック**
- `C1 Design-first`  
  ローカル設計本文未読なので未充足。だから bug claim は出していません。
- `C2 X が無い = バグ 禁止`  
  現コード未検証なので、「fx に C-lite が無い」から即バグ、のような言い方はしていません。
- `C3 Collider bias`  
  危険なのは `regime_pass_pattern` を P2 に使うこと、`session_close_drop_count` を生存個体上だけで因果解釈すること、`cross-pair shadow` を early-stage objective に混ぜることです。
- `C4 前提検証`  
  verified は prompt 条件と文献、unverified は repo 実装本文です。
- `C5 並列独立性`  
  sub-agent は使っていません。独立確認の錯覚は入れていません。
- `C6 Fact / Interpretation 分離`  
  各論点で分離しました。
- `C7 Sample size`  
  6-regime や 15-cell を 6カ月/pop40 に載せると疎になるので、因果主張は不可。ここは INCONCLUSIVE が正当です。
- `C8 INCONCLUSIVE`  
  `win_rate` を残すか、full CA/DA が要るか、18-24カ月を前提化すべきかは、まだ確定させていません。
- `C9 Falsification-first`  
  各論点に「これが出たら崩れる」を先に置きました。

Round 1 の暫定結論だけ短くまとめると、**先に決めるべきは `Stage B を gate から降ろすか` と `FX 固有指標を worst に入れず taxonomy 分離するか` の2点**です。ここが固まると、`P2 は vol 主軸の最小構成`、`CPPS は中間案`、`Warmstart は 0.33 より薄く` という形で後段が自然に定まります。