**判定（Round 1 結論）**

- 施策 #1: **MODIFY（実装して進める）**
- 施策 #2: **MODIFY（docs-only ではなく report 表示まで）**
- 保留 #3: **REJECT（cycle 23 スコープ外）**
- 保留 #4: **REJECT（cycle 23 スコープ外）**
- 保留 #5: **MODIFY（調査のみ、閾値変更はしない）**

**重要ファクト（C6: Fact）**
- [`_check_live_criteria`](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py:916) は現状 `trade_sharpe_raw` をそのまま `sharpe_min` と比較しており、単位不整合が実在。
- Stage C 本体は [`_annualize_trade_sharpe`](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/stage_gate.py:1680) で年率換算して判定している。
- archive は `trade_sharpe_raw` を Stage A 固定で保持し、Stage C は別列 `trade_sharpe_stage_c`（[`archive.py`](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/archive.py:114)）に保存。

**解釈（C6: Interpretation）**
- #1 は「年率化」だけでなく「参照列を Stage C に合わせる」必要があります。  
  つまり A 案をそのままでは不十分で、**A 修正版**が必要です。

---

### Q1 回答（#1 最小実装）
**回答: A を採用。ただし修正して採用（B は不要）**

- 採用実装（最小）:
1. `_check_live_criteria` に `holdout_days` 引数を追加。
2. sharpe 比較値は `trade_sharpe_stage_c` を第一優先（無ければ `trade_sharpe_raw` fallback）。
3. `annualized = _annualize_trade_sharpe(sharpe_trade, trade_count, holdout_days)` で比較。
4. `checks["sharpe"]` は `value` を annualized、`value_trade_level` を併記。

- target_metric: `summary.live_criteria.checks.sharpe.pass`、`summary.live_criteria.all_pass`
- failure_mode: Stage A trade-level 値を annualized 閾値と比較する単位・スコープ不整合
- causal_path: sharpe 判定固定 False → all_pass False → mission 0
- falsification: 修正後も best 個体で sharpe 判定が継続 False
- success_criterion: Run 76 で best 個体の sharpe 判定が Stage C 年率基準で整合

---

### Q2 回答（#2 graduation KPI）
**回答: `swim_lane.py` の graduation 経路変更は不要。**

- 理由: graduation は仕様上「Stage C AND cross_pair」で正しい（[`swim_lane.py`](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/swim_lane.py:414)）。
- ただし docs-only では不足。`generate_run_report.py` に `stage_c_pass_count` と `mission_candidate_count`（= live_criteria all pass count）を明示表示するのが妥当。

- target_metric: KPI 誤読率（運用判断ミス）低減
- failure_mode: graduation=0 を mission=0 と誤読
- causal_path: single-instrument で cross_pair skip → graduation 構造的 0
- falsification: KPI 分離後も判断が改善しない
- success_criterion: run report で `stage_c_pass` と mission 候補が分離表示される

---

### Q3 回答（過去 19 RUN 再評価）
**回答: 実施推奨。ただし #1 適用後の軽量監査として同 cycle 内の別タスク。**

- 新規大改修は不要。既存 `audit_run_post.py` か小スクリプトで parquet 再評価で十分。
- 目的は historical correction（mission 0/19 の再解釈）。

- target_metric: 過去 RUN の `mission_candidate_count` 再算出
- failure_mode: bug 由来の過小評価を真値と誤認
- causal_path: 不整合判定ロジックで historical bias
- falsification: 再評価しても 0 が継続
- success_criterion: 過去 RUN の再評価値を一貫ルールで提示できる

---

### Q4 回答（trade_count=51 張り付き）
**回答: cycle 23 は「調査のみ」実施、判定閾値変更はしない。**

- これはいま閾値を触ると Reactive になりやすい。
- まず `trade_count` 分布・`trade_count==51` 群の PnL/Sharpe 分布を report 化して因果確認。

- target_metric: 境界張り付きの構造把握
- failure_mode: 閾値狙い撃ち最適化
- causal_path: hard constraint 近傍に探索集中
- falsification: 51 群が他群より実績優位なら「悪性張り付き」仮説は弱まる
- success_criterion: 次 cycle で構造対策要否を判定可能な証拠が揃う

---

### Q5 回答（禁止事項違反兆候監査）
**回答: cycle 23 では本実装は見送り（別 TODO）。**

- long/short 内訳・swap/spread 純利益分解の列追加は schema/計測経路変更が広く、1 ラウンド収束を阻害。
- ただし TODO は即時起票し、cycle 24 で Structural な監査列追加を実施。

- target_metric: 禁止事項違反の検知可能性
- failure_mode: 見かけ黒字の偽改善
- causal_path: 監査列不在で INCONCLUSIVE が継続
- falsification: 監査列追加後も違反兆候なし
- success_criterion: long/short・overnight・cost 監査が run report で自動可視化

--- 

今回の収束案は「**#1を最優先で即実装**、#2は表示KPI分離まで、#3/#4は後ろ倒し、#5は調査のみ」です。