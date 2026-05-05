# RUN run_20260504_132300 (run-34) 分析（Codex 独立分析）

## 前提差分（C4）
- 前提1（verified）: 本分析の定量根拠は、ユーザー提示の事実集計のみを使用。
- 前提2（verified）: 現行設計（T087）は Stage A/B/C の時系列 disjoint を要求。
- 前提3（差分）: 入力事実では `stage_b=183,403 (全期間)` かつ `stage_a=86,400` で、T087 契約と整合しない可能性がある。
- 前提4（差分）: `stage_c.holdout_days=60` に対し `holdout=20,457 bars` は量的乖離がある。

## 観察事実（Facts、 C6 Fact/Interpretation 分離遵守）
- Archive は `5856 (=96 × 61)` 行で、実行試行数は設定と整合。
- Stage 通過率: A `52.9%`、B `0.4%`、C `0.0%`、graduated `0`。
- Stage A 目標通過率 `0.15` に対し実績 `0.529`、`calibrate.enabled=False`。
- Stage B fail 主因は `median_oos_sharpe<min` と `positive_fold_ratio<min` の同時不達（2823件、+同 reason で all_folds_unavailable 216件）。
- Stage B pass 群は `n=26`、`positive_fold_ratio_effective mean=0.787`、`n_fold_effective median=8`。
- Best 個体は `sharpe=0.24`、`trade_count=67`、`total_pnl=0.0`、Stage B/C 不通過。
- top fitness_pen には `sharpe=NaN` 個体が含まれる。
- live_criteria は緩和されていない（`sharpe_min=1.0`, `total_pnl_min=50000` など）。
- `dsr` 全 NaN、`mission_score` 未計測、`archive_role/source_stage/fsp_*` は空。
- `cross_pair_runtime_mode=skipped_single_instrument`（single instrument 実行）。

## 解釈・推論（Interpretations、 C9 反証可能性付き）
### 仮説H1: 主ボトルネックは「Stage A の選別力不足」→「Stage B で大量脱落」
- 根拠: A通過率 52.9%（目標15%）に対し B通過率 0.4%、A通過後のB通過は約0.84%。
- 反証条件: 同一データ・同一seedで Stage A しきい値を厳格化し A通過率を目標帯へ寄せても、B通過“率/絶対数”が改善しなければ本仮説は棄却。

### 仮説H2: Stage B の fail は「閾値が厳しすぎる」より「候補品質不足」が主因
- 根拠: B fail reason が二重不達に集中。B pass 群では fold 有効数は確保されている。
- 反証条件: Stage A 通過群の `median_oos_sharpe`/`positive_fold_ratio` 分布が閾値近傍に密集していれば「閾値感度」が主因、遠く下方に偏るなら品質主因が支持。

### 仮説H3: `total_pnl=0.0` は計測/記録経路の異常シグナル
- 根拠: trade_count>0 かつ sharpe>0 と `total_pnl=0.0` の同時発生。
- 反証条件: 該当個体の取引明細再集計で実PNLが0に一致すれば異常ではない。不一致なら計測経路不整合が確定。

### 仮説H4: primitive 多様性は「退化」より「探索空間制約（max_clause=1）」の影響が大きい
- 根拠: `active_clause=1.00`（全員）で、構造上の多様性が限定。
- 反証条件: `max_clause` を 2 にした対照RUNで B通過の質/量が不変なら、多様性不足原因説は棄却。
- 注記（C7）: `n=26` のため因果断定は避ける。

### 仮説H5: cross-pair shadow skip は Phase2 設計上は妥当だが、頑健性監視の盲点を残す
- 根拠: single instrument 時 `skipped_single_instrument` は fail-close ではなく shadow非実施。
- 反証条件: multi-instrument で shadow を有効化しても指標差が実質ゼロなら、現運用の skip は実務上妥当。差が大きければ監視欠落。

## 次サイクル候補
- [Critical] Stage partition/holdout 実測監査: `stage_b` が Stage A と truly disjoint か、`holdout_days=60` と実 bars 乖離の理由を境界timestampで検証（契約違反なら即修正）。
- [Warning] Stage A 選別力の再調整実験: 「閾値厳格化のみ」で A→B 変換効率が改善するかを 1-run A/B テストで検証（緩和は禁止）。
- [Warning] `total_pnl` 計測経路の健全性チェック: best 個体の trade ledger から summary 集約までを突合し、0固定化/単位不整合を切り分ける。
- [Warning] cross-pair shadow の最小有効化検証: 2-3 pair の小規模 run で shadow 統計の情報価値を確認し、single-only運用の妥当性を判断。

## 全体判定
CONCERN  
Stage C 0% 自体より、`stage_b disjoint/holdout` 契約乖離疑いと `total_pnl=0.0` 異常シグナルが同時に存在し、閾値調整より先に計測・境界整合の検証が必要。

## Claude 分析との差分（最後に確認した結果）
- 同意点
  - Stage A 高通過/Stage B 低通過のミスマッチが主要課題。
  - `total_pnl=0.0` は優先調査対象。
  - cross-pair が single instrument で skip されている点は監視上の弱点。
- 反対意見・補足
  - `max_clause=1` を主因と断定するのは早い。現時点では「探索空間制約の寄与仮説」に留めるべき。
  - Stage C evaluator 不全を第一仮説に置く前に、T087 契約乖離（stage_b/holdout量）を先に反証すべき。
- Claude が見落としている可能性のある観点
  - `stage_b=全期間` と T087 disjoint 契約の不整合自体が、統計解釈の前提破壊点になっている可能性。
  - `holdout_days=60` と `holdout bars=20,457` の乖離は Stage C 全滅の説明変数になり得るため、まずデータ境界監査が必要。