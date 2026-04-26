# Run 1〜16 GA 機能不全 — Codex 独立分析

## 0. 本分析の前提（C4）
- verified: Run 16 は instrument=EUR_JPY、`ga.max_clause=1`、`cross_pair_runtime_mode="skipped_single_instrument"`、`stage_a_threshold=0.4655` で実行されている（`reports/run-reports/run-16/summary.json:6`, `reports/run-reports/run-16/summary.json:14-44`）。
- verified: archive の `active_clause` は `_compute_active_clause_placeholder()` が常に 0 を返す placeholder のまま（`src/alpha_factory/archive.py:176`）。
- verified: 初期個体生成・突然変異ともに `max_clause` の上限を超える clause を作れず、Run 16 設定では clause=1 から増えない（`src/ga/random_gen.py:194-207`, `src/ga/operators.py:293-327`, `reports/run-reports/run-16/summary.json:21-24`）。
- verified: `RegistryEvaluator` は aux_series/event_snapshot を渡さず生成されており、pair-specific primitive の required_data を満たす経路がない（`scripts/alpha_factory/run_ga.py:872-896`, `src/alpha_factory/primitives/evaluator.py:57-88`）。
- verified: pair-specific primitive は aux データ欠損時に警告を出し安全値（0.0/1.0/0.5）へフォールバックする実装になっている（`src/alpha_factory/primitives/pair_specific.py:145`, `src/alpha_factory/primitives/pair_specific.py:407`）。
- verified: Stage C stress は `max_spread_bps` 未設定の場合に理由 `spread_stress_skipped` を追加し必ず fail させる（`src/alpha_factory/stage_gate.py:620-633`）。
- verified: Run 16 の全世代で Stage A/B/C pass は 0 のまま推移し、best_fitness_pen が世代 26 以降 0.33217… で停滞している（`reports/run-reports/run-16/summary.json:45-716`）。
- unverified: pair-specific primitive が実際の genome でどの程度選択されているか（archive の `genome_json` 分布）は未計測。

## 1. Claude 監査の事実 (Sec 1) への反証チェック (C9)
- (a) { 主張: `active_clause`=0 placeholder で発火数が観測不能 / 反証仮説: Stage A/B/C の他メトリクスや `genome_json` から代替観測できる / 反証結果: archive には `n_nodes` と構造 JSON しかなく runtime の発火情報は残らないため反証失敗（観測盲目は継続） / 追加観察: Stage A payload も trade_sharpe/trade_count のみで clause 活性化を推定できない（`src/alpha_factory/archive.py:171-207`, `src/alpha_factory/stage_gate.py:270-347`） / 残存リスク: instrumentation 未整備のまま max_clause を緩めても評価が困難 }  
- (b) { 主張: `max_clause=1` が GA を決定的に制限し composite 探索不能 / 反証仮説: mutation/crossover で clause 数が増えている、あるいは単一 clause でも十分な表現力がある / 反証結果: `max_clause` が 1 のため初期生成・突然変異とも clause 追加は無効、複数 clause 混合は実現しない。反証失敗（構造の狭さは実在）ただし “決定的” かは未検証 / 追加観察: 単一 clause 内では最大 4 signal を重み付け合成できるため完全に一次元ではないが、Stage A pass=0 の現状では clause 拡張より gate 再校正の方が優先度高いと判断（`src/ga/random_gen.py:194-207`, `src/ga/operators.py:293-327`, `reports/run-reports/run-16/summary.json:45-716`） / 残存リスク: clause を増やしても Stage A threshold が trade-level Sharpe に未調整な限り pass 0 が続く可能性 }  
- (c) { 主張: pair-specific primitive 12 個が aux データ欠如で “死荷重” / 反証仮説: lane 構築時に aux_series や snapshot が注入されており有効活用されている / 反証結果: `RegistryEvaluator` はデフォルト引数のみで生成され、aux_map も snapshot も空。safe default へ落ちる実装通り “死荷重” 状態が確認されたため反証失敗 / 追加観察: strict_aux_required も無効で preflight が走らず、warning だけで実質 0/1/0.5 の定数信号になっている（`scripts/alpha_factory/run_ga.py:872-896`, `src/alpha_factory/primitives/evaluator.py:57-106`, `src/alpha_factory/primitives/pair_specific.py:145-183`） / 残存リスク: genome が pair-specific を選択しても探索空間が歪み、警告が大量に出る可能性 }  
- (d) { 主張: swim_lane / cross_pair が実機未統合で 1 lane 固定 / 反証仮説: `LaneManager` が複数 lane を生成し、`pair_bars` を渡して cross-pair shadow を回している / 反証結果: run-ga は `tier1_{instrument}` 1 本のみ生成し、Graduation lane の `pair_bars`/`pair_meta` を空 dict で初期化。結果 `cross_pair_mode="skipped_single_instrument"` となり shadow も未実行で、反証失敗（未統合が確認された）（`scripts/alpha_factory/run_ga.py:872-905`, `reports/run-reports/run-16/summary.json:44`, `src/alpha_factory/swim_lane.py:596-608`） / 追加観察: Graduation lane は seed_graduates を append するだけで、Stage C pass が発生しない現状では昇格動線が完全に閉じている / 残存リスク: multi-lane 移行時に bars ロード／選抜契約が未検証 }  
- (e) { 主張: 世代 26 以降 35 世代 plateau は GA バグの症状 / 反証仮説: selection/mutation の実装バグや cache 更新不備が plateau を引き起こしている / 反証結果: cache は Stage A の `fitness_pen` を世代ごとに保持できており（`scripts/alpha_factory/run_ga.py:504-556`）、停滞理由は Stage A threshold 0.4655 > 最良 fitness 0.332 のため pass=0 が続きリーグ全体が同じ谷に落ちている構造的状況と説明できた。よって「バグ」と断定する主張は反証成立 / 追加観察: Stage C 以前で淘汰が止まり、`improve_cycle` の plateau_mutation_bump も Run 内では走らない設計。mutation_rate=0.3 で `n_edit_max=3` のため探索圧も弱い（`reports/run-reports/run-16/summary.json:45-716`, `config/alpha_factory/default.yaml:14-38`, `src/alpha_factory/stage_gate.py:270-327`） / 残存リスク: Stage A threshold が trade-level Sharpe 用に再校正されていない点を修正しない限り plateau 繰り返しが予想される }

## 2. Q1〜Q7 への独立解
- Q1: 最優先は (b) T037 active-clause 実装と (c) T036/FSP ではなく、Stage C stress 条件の整備と Stage A threshold の trade-level 再校正を先にやるべき。active_clause 計測は同時に進める価値があるが、`max_clause` 引き上げは Stage A pass が常時 0 の現状では効果測定ができず Claude 案ほど優先度は高くない。Claude 案とは部分一致（T037 先行は賛同）、順序は再配置すべき。
- Q2: 実効 primitive は generic 20 程度で不足よりも data パイプライン未整備がボトルネック。aux データを供給し safe default を解消するまで新規 primitive 追加は後回し。Claude 案の「先に composite 化」より “aux 供給 → 選択状況の集計 → 必要なら追加” を推奨。
- Q3: Single instrument でも Stage C stress 条件と trade-level gate を整えれば mission 追求は可能。ただし swap/spread を fitness に入れるという North Star 制約が今の config では満たせず（`backtest.max_spread_bps` 未設定）Stage C 通過が論理的に不可能。Claude 案の FSP 代替は有効だが前提条件の整備が欠かせない。
- Q4: plateau 破りは mutation bump より先に Stage A threshold 再校正と `trade_count_min_for_sharpe` の感度分析が必要。ハイパー mutation を足しても gate が閉じたままでは改善しない。Claude 案とは判断不一致。
- Q5: 最小コアは (1) Stage A reason 分布と trade_count ヒスト、(2) clause 構造ヒスト（active_clause/N_nodes）、(3) fitness 多様性指標（HHI）で十分。Director や bucket は後続。Claude 案より軽量セットを推奨。
- Q6: `live_criteria.sharpe_min=1.0` は bar-level スケール前提というコメント通り（`src/alpha_factory/stage_gate.py:575-577`）。trade-level Sharpe に移行した現在は replay で閾値再推定が必須。緩和ではなく再標準化すべき。Claude 案が閾値維持と仮定しているなら不一致。
- Q7: Claude 監査では Stage C stress skip・trade-level threshold 未校正・cost modelling 欠如が抜けていた。詳細は §4 に記載（Claude 案と不一致）。

## 3. Claude 仮案の優先順位への反証
- T037 → 同意。ただし同時に Stage C stress 条件（`max_spread_bps` 設定）と Stage A threshold 再校正を割り込ませる必要がある。観測だけ整えても Stage C が論理的に pass 不可能なままでは “観測” しかできない。
- max_clause の即時拡張 → 現時点では時期尚早。Stage A pass=0 では複雑化の効果検証ができず、むしろ search space を広げると mutation が diffuse し plateau が長期化する恐れがある。
- soft fitness → amscore 導入は賛成。ただし trade-level 指標での参照値再校正とセットでないとハード gate が壁のまま。
- FSP (single-instrument diagnostics) → その前に pair-specific aux データ注入で “死荷重” を解消しないと FSP の観測対象がそもそも働かない。
- plateau-aware operator → Stage A gate 調整後に必要なら検討。現状 plateau の主因は gate の閉塞と stress 条件不足であり operator 追加は二次的。
- report 拡張 → 観測系の中でも Clause 活性や Stage A reason を先に作り、HHI/epoch は後続で問題なし。

## 4. 見落とし論点（Q7 への回答）
1. **Stage C 恒久失敗**: `BacktestConfig.max_spread_bps` が None のため、Stage C は毎回 `spread_stress_skipped` を理由に fail する（`src/alpha_factory/stage_gate.py:620-633`）。North Star の「スプレッド反映」にも反する。最優先で設定し、stress backtest が回るようにする必要がある。
2. **trade-level Sharpe への閾値未再校正**: Stage A/B/C すべてが v2 trade-level Sharpe を使う一方、`stage_a_threshold=0.4655`、`stage_b_median_oos_sharpe_min=0.20`、`live_criteria.sharpe_min=1.0` は旧スケール前提のまま（`config/alpha_factory/default.yaml:32-38`, `src/alpha_factory/stage_gate.py:270-489`, `src/alpha_factory/stage_gate.py:575-577`）。この乖離が Stage A pass=0 を招いている。
3. **コストモデル未実装**: North Star は swap/spread を fitness に反映することだが、`BacktestSectionConfig` の `holding_cost_per_day_bps=0`、`max_spread_bps=None` で評価しており、実質ゼロコスト前提。Spread stress を通すとともに base backtest でも実コストを掛ける必要がある。
4. **pair-specific data pipeline 不在**: aux_series/event_snapshot/vix_snapshot の供給がなく safe default で実行されている（`scripts/alpha_factory/run_ga.py:872-896`, `src/alpha_factory/primitives/evaluator.py:57-106`）。pair-specific primitive の真価評価と FSP/T036 の意味付けのために、データ基盤側の整備が必須。

## 5. 最小経路 roadmap（1〜2 weeks）
- Week 1-前半: Stage C stress を有効化するため `config/alpha_factory/default.yaml` に `max_spread_bps`（現実的なベーススプレッド）と `holding_cost_per_day_bps` を設定し、backtest エンジン側のスプレッド反映を確認（`src/alpha_factory/stage_gate.py:620-638`）。同時に Stage A/B/C gate を trade-level Sharpe で再校正するための replay スクリプトを `devnotes/` に設計。
- Week 1-後半: T037 active-clause 計測を実装し、Stage A payload→archive までの 4 段伝搬を整備（`src/alpha_factory/archive.py:171-207`）。あわせて Stage A reason 分布・fitness ヒストを report に出す軽量ダッシュボードを追加（`scripts/alpha_factory/run_ga.py:667-809`）。
- Week 2-前半: pair-specific data pipeline を実装（aux_series のロード、event/vix snapshot の取得と `RegistryEvaluator` への注入、strict_aux_required の利用）。`scripts/alpha_factory/run_ga.py:872-896` と `src/alpha_factory/primitives/evaluator.py:57-106` を改修。
- Week 2-後半: `ga.max_clause` を 2 に引き上げる前に、active_clause ログを用いた頻度分析を実施し、再校正済み Stage A/B gate で plateau が収束するか検証。必要なら mutation_rate や `n_edit_max` の感度分析を追加。
- 反対案評価: 現状構造のまま閾値調整だけで Run を積み増しても、Stage C stress skip（常時 fail）と trade-level 閾値の不整合が解決しない限り mission 達成確率は 0%。追加 Run は証跡を増やすだけで意味がない。

## 6. Verdict
- 全体: PARTIALLY CONFIRMED（構造的盲点と underexploration は実在するが、plateau=バグ という結論は反証した）。
- H1 Underexploration: PARTIALLY CONFIRMED — clause=1 制約は存在するが最優先課題は gate 再校正。
- H2 Observation gap: CONFIRMED — active_clause placeholder により runtime 可視化ゼロ。
- H3 Pair-specific 死荷重: CONFIRMED — aux データ未配線で安全値へ落下。
- H4 Hard fitness 勾配欠損: CONFIRMED — fitness は trade-level Sharpe 単軸で live_criteria がハード閾値のみ（`src/alpha_factory/stage_gate.py:270-613`）。
- H5 Report 解像度不足: CONFIRMED — summary.json が best/世代統計のみで clause/多様性指標なし（`scripts/alpha_factory/run_ga.py:667-809`）。
- H6 改善サイクル局所最適化: INCONCLUSIVE — improve-cycle のログ未確認で判断保留。
- 不確定領域: pair-specific primitive の実利用率、再校正後の Stage A pass レート、multi-lane 実装時の分散挙動は n=1 Run では推測に留まるため別途計測が必要。