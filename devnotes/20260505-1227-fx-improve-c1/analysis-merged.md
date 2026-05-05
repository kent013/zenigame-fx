# マージ分析: Run 34 (run_id=run_20260504_132300)

cycle 1/10 — improve-cycle 自走ループ起点。 Claude / Codex 両分析の統合。

## 合意事項（両者一致）

| # | 観察 | 含意 |
|---|------|------|
| M1 | Stage A 高通過 (52.9%) / Stage B 低通過 (0.4%) のミスマッチが主要課題 | A→B 変換効率の構造的問題 |
| M2 | Best 個体で `total_pnl=0.0` だが Sharpe positive — 計測 / 記録経路に異常の疑い | live_criteria `total_pnl_min=50000` 判定が常に false 化する構造 bug の可能性 |
| M3 | cross-pair shadow が single_instrument で skip されているのは設計通り、 ただし監視欠落 | multi-instrument RUN への復帰検討 (elective) |
| M4 | live_criteria は緩和されていない (sharpe≥1.0 / pnl≥50000) | 禁止事項 4「閾値緩和でステージ飛ばし」は **未発生** |
| M5 | Stage B fail 主因は `median_oos_sharpe<min` と `positive_fold_ratio<min` の同時不達 (2823件) | Stage B 評価層の閾値はそのままで、 候補品質が不足 |

## Claude 独自の発見

| # | 観察 | Codex はなぜ取り上げなかったか |
|---|------|---------------------------|
| L1 | seed=23 deterministic 再現で「改善でなく観測」になっている可能性 (cycle 13 と完全同値) | Codex は提示事実から再現性を直接観察できず、 仮説保留 |
| L2 | per_generation の median_fitness_pen / stage_X_pass_count などほぼ全行 null — 観測経路欠陥 | Codex は per_generation 抜粋を 5 件のみ受領、 全期間欠陥は判別困難 |
| L3 | Stage A 通過後の Stage B 落下率 99.2% から Stage A の selectivity 不足を仮説化 | Codex H1 と概ね同じだが、 Codex は「閾値緩和禁止」を強調し慎重 |
| L4 | dsr 全 NaN を「計算機構不全」と仮説化 | Codex も観察したが、 Stage C dropout 100% との因果に踏み込まず |

## Codex 独自の発見

| # | 観察 | Claude が見落とした要因 |
|---|------|---------------------|
| C1 | **Stage partition/holdout 契約乖離**: `stage_b=183,403 (全期間)` と T087 disjoint 契約の不整合 | Claude は dataset.bars=stage_b を fact として観察したが、 T087 契約 (Stage B = Stage A 期間を除外) との比較を行わず |
| C2 | **`holdout_days=60` vs `holdout bars=20,457` の量的乖離** が Stage C 全滅の説明変数になり得る | Claude は holdout=20,457 を観察したが「~14日相当」と注記したのみで Stage C dropout との接続を仮説化せず |
| C3 | max_clause=1 主因断定は早い ―「探索空間制約の寄与仮説」に留めるべき | Claude H2 は確かに「段階的緩和」と書いたが Critical/Warning 分けで Critical 寄りにした |
| C4 | Stage A 実通過率 0.529 vs target_pass_rate 0.15 の乖離。 calibrate.enabled=False で放置 | Claude L3 も近い指摘だが、 target_pass_rate との比較は明示せず |

## 矛盾・要議論

| # | Claude の見解 | Codex の見解 | 議論 |
|---|------------|------------|------|
| D1 | Stage C 評価機構の健全性 (dsr NaN / mission_score 不在) を Critical 1 | T087 partition/holdout 契約乖離を Critical 1 (Stage C dropout 100% 自体より境界整合が先) | Codex 優位 — partition 整合性が破綻していたら Stage C 解釈そのものが無意味。 Claude H1 (evaluator 不全) は partition 検証後の二次仮説として残す |
| D2 | max_clause=1 は Stage B 制約の主因 (Warning) | max_clause=1 主因断定は早い、 寄与仮説に留めるべき | Codex 優位 (n=26 で因果断定不可)。 Warning 維持だが「主因」表現を「寄与仮説」に訂正 |

## 統合改善提案（優先度順）

| # | 提案 | 優先度 | 出所 | target_metric | failure_mode | causal_path | falsification | success_criterion |
|---|------|--------|------|--------------|-------------|-----------|--------------|------------------|
| **P1** | **Stage partition/holdout 実測監査** | **Critical** | Codex C1 + Claude H1 | データ境界の正当性 (live_criteria 共通基盤) | `stage_b=183403=全期間` で T087 disjoint 契約と矛盾、 holdout bars=20457 が holdout_days=60 と乖離 | partition guard が validate しているが、 summary 表示の `bars_stage_b` 集計が contract と異なる経路を通っている恐れ。 もしくは guard 自体に bug | partition 境界 timestamp で実測し disjoint なら partition guard 健全、 contract 通り。 重複していたら **構造 bug** 確定で即修正 | partition が disjoint で stage_b の timestamp range が `[dataset.start, dataset.end - stage_a_window)` ⊂ Stage A 期間外を満たす |
| **P2** | **`total_pnl=0.0` 計測経路の健全性チェック** | **Critical** | Claude H3 + Codex H3 | `total_pnl_min=50000` 判定の正当性 | best 個体で trade_count=67, sharpe=0.24 (positive) なのに total_pnl=0.0 | trade-level Sharpe → summary 集約経路で PnL 単位変換 / 集計欠陥の疑い | best 個体 g54_i35 を local 再評価し trade ledger を集計、 0 ではない値が出れば計測経路 bug | 集計後 PnL > 0 (or 数学的に 0) で recording / display 整合 |
| **P3** | Stage A 選別力の再調整実験 (厳格化のみ) | Warning | Codex C4 + Claude H5 | Sharpe / Stage B pass rate | Stage A 通過率 52.9% (target 0.15 の 3.5 倍) で selectivity 不足 | 緩い Stage A で「真に良くない個体」が Stage B に流れ込み median_oos_sharpe を引き下げ | Stage A threshold を厳格化した RUN で Stage A→B 変換率が改善せず Stage B 絶対数も増えなければ Stage A 不要 (棄却) | Stage A pass rate ≈ 0.15 (target 一致) で Stage B pass 数が増加 or 不変 |
| **P4** | max_clause=1 制約の探索空間寄与仮説の小規模 A/B (寄与仮説に留める) | Warning | Claude H2 + Codex H4 | Stage B pass count | active_clause=1 全員一致、 探索空間が clause 1 個に制約 | 単一 clause では robust signal を作れず median_oos_sharpe ≥ 0.05 を超える個体が稀 | max_clause=2 の対照 RUN で Stage B pass の質 / 量が不変なら多様性不足説は **棄却** | max_clause=2 で Stage B pass 数の有意増加 + median_oos_sharpe 分布の右シフト |
| **P5** | cross-pair shadow の最小有効化検証 (multi-instrument 2-3 pair) | Warning | 両者一致 | cross_pair sharpe target / 監視充実 | single_instrument で cross_pair 全 skip。 anchors 設計が機能していない | shadow 統計の情報価値を確認 | multi で shadow 有効化しても指標差が実質ゼロなら現運用 skip は妥当 (棄却) | shadow が pass/fail 判定に有意な情報を加える (差 > ノイズ閾値) |

## 全体判定

**CONCERN** — Stage C 0% 自体より、 `stage_b disjoke/holdout` 契約乖離疑いと `total_pnl=0.0` 異常シグナルが同時に存在し、 閾値調整より先に **計測経路と境界整合の検証** が必要。 cycle 1 は P1 / P2 を Critical として最優先、 P3-P5 は Warning として次以降に回せる。

## 滞留 TODO 判断

Open / Conditional 共に 0 件。 棚卸し対象なし。

## Conditional 昇格チェック

Conditional 0 件。 評価対象なし。
