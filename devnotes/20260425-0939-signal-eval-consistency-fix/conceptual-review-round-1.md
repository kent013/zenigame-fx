**全体判定**

CHANGES_REQUESTED

**本分析の前提**

- C1 実施済み。[`docs/alpha_factory/README.md`](/Users/ishitoya/repository/zenigame-fx/docs/alpha_factory/README.md)、[`docs/alpha_factory/stage-gates.md`](/Users/ishitoya/repository/zenigame-fx/docs/alpha_factory/stage-gates.md)、[`docs/alpha_factory/concepts/genome-archive-schema.md`](/Users/ishitoya/repository/zenigame-fx/docs/alpha_factory/concepts/genome-archive-schema.md)、[`docs/alpha_factory/clause-architecture.md`](/Users/ishitoya/repository/zenigame-fx/docs/alpha_factory/clause-architecture.md)、[`devnotes/20260423-2324-run-ga-full-rewrite/conceptual-design-r2.md`](/Users/ishitoya/repository/zenigame-fx/devnotes/20260423-2324-run-ga-full-rewrite/conceptual-design-r2.md)、[`devnotes/20260425-0931-fx-improve/improvement-plan.md`](/Users/ishitoya/repository/zenigame-fx/devnotes/20260425-0931-fx-improve/improvement-plan.md)、`git log` を確認。
- C4 検証済み。Stage A payload に `total_pnl` は無く、archive でも Stage A は `total_pnl` を書いていません。[`src/alpha_factory/stage_gate.py#L320`](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/stage_gate.py#L320) [`src/alpha_factory/archive.py#L337`](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/archive.py#L337)
- C4 検証済み。`total_pnl` は Stage B の `is_full_total_pnl` と Stage C の `total_pnl` で上書きされる設計です。[`src/alpha_factory/archive.py#L392`](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/archive.py#L392) [`src/alpha_factory/archive.py#L443`](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/archive.py#L443) [`docs/alpha_factory/concepts/genome-archive-schema.md`](/Users/ishitoya/repository/zenigame-fx/docs/alpha_factory/concepts/genome-archive-schema.md)
- C4 検証済み。best 選抜は archive snapshot 由来の `(stage_c_pass, stage_b_pass, stage_a_pass, fitness_pen)` です。[`scripts/alpha_factory/run_ga.py#L100`](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py#L100) [`scripts/alpha_factory/run_ga.py#L437`](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py#L437)
- C4 検証済み。run-9 の best は `g0_i1`, `fitness=0`, `trade_count=0`, Stage A/B/C 全不通過です。[`reports/run-reports/run-9/summary.json#L107`](/Users/ishitoya/repository/zenigame-fx/reports/run-reports/run-9/summary.json#L107)

**観察された事実**

- archive の現行 SSOT では、`total_pnl` は Stage A の値ではありません。[`docs/alpha_factory/clause-architecture.md#L358`](/Users/ishitoya/repository/zenigame-fx/docs/alpha_factory/clause-architecture.md#L358)
- Stage B 進出は `stage_a_result.passed` で決まり、archive の `total_pnl` は参照されません。[`src/alpha_factory/swim_lane.py#L313`](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/swim_lane.py#L313)
- calibrate-gate は archive の `fitness_pen` 分布を quantile 集計に使います。[`src/alpha_factory/calibrate_gate.py#L317`](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/calibrate_gate.py#L317) [`src/alpha_factory/calibrate_gate.py#L548`](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/calibrate_gate.py#L548)
- 既存の改善計画では、Critical は「無取引優位の構造修正」、PnL 側は「挙動非変更の監査」が合意済みです。[`devnotes/20260425-0931-fx-improve/improvement-plan.md#L7`](/Users/ishitoya/repository/zenigame-fx/devnotes/20260425-0931-fx-improve/improvement-plan.md#L7)

**解釈**

- `A-1` は監査性の改善にはなり得ますが、best 選抜や Stage B 進出の主因にはなりません。
- `B-1` を archive の canonical `fitness_pen` に直接入れると、選抜だけでなく calibrate-gate の制御対象まで変質します。
- この設計は「記録整合性修復」と「選抜圧修正」を一つの TODO に混ぜており、スコープが広がっています。

**観点別レビュー**

1. 使命との整合性

[Critical] `A-1` の期待効果にある「正しい `total_pnl` が Stage B 進出判定や best 選抜に効く」は、現行コード経路と一致していません。Stage B 進出は `stage_a_result.passed`、best 選抜は `selection_score` で決まり、archive `total_pnl` はその場で使われません。[`src/alpha_factory/swim_lane.py#L313`](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/swim_lane.py#L313) [`scripts/alpha_factory/run_ga.py#L470`](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py#L470)  
修正提案: `A-1` は「監査性向上」に格下げし、使命への直接寄与は `trade_count=0` を選抜で不利化する施策に限定してください。

[Warning] 既存合議では「無取引優位の構造修正」が Critical、「PnL は監査のみ」が MODIFY です。今回案はその整理を崩しています。[`devnotes/20260425-0931-fx-improve/improvement-plan.md#L7`](/Users/ishitoya/repository/zenigame-fx/devnotes/20260425-0931-fx-improve/improvement-plan.md#L7)  
修正提案: 本設計を `selection-fix` と `pnl-audit` の 2 本に分割してください。

2. 禁止事項違反

[Warning] `B-1` を archive の canonical `fitness_pen` に入れる案は、実質的に「GA 選抜のために fitness の意味を変える」変更です。禁止事項 #3 に近いグレーです。  
修正提案: canonical `fitness_pen` は保持し、選抜専用に `feasible_trade_participation` の bool を `selection_score` 先頭へ追加する形に寄せてください。

3. 実現可能性

[Critical] `A-1` は archive の `total_pnl` 列意味論を壊します。現行 SSOT は「Stage B full IS → Stage C holdout」であり、Stage A 60d PnL を同じ列に入れると、report / live_criteria 判定で異なる期間の値が混在します。[`docs/alpha_factory/concepts/genome-archive-schema.md`](/Users/ishitoya/repository/zenigame-fx/docs/alpha_factory/concepts/genome-archive-schema.md) [`docs/alpha_factory/clause-architecture.md#L358`](/Users/ishitoya/repository/zenigame-fx/docs/alpha_factory/clause-architecture.md#L358)  
修正提案: Stage A の PnL が必要なら `stage_a_total_pnl` の別フィールドにしてください。schema を触りたくないなら report/log の監査情報に留めてください。

[Warning] 変更対象として `src/ga/runner.py` を挙げていますが、Alpha Factory の実選抜は [`scripts/alpha_factory/run_ga.py`](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py) 側です。  
修正提案: 実装スコープを `scripts/alpha_factory/run_ga.py` ベースで引き直してください。

4. 期待効果の妥当性

[Critical] `A-1` の causal path が過大評価です。`total_pnl` 記録修復だけでは no-trade 優位は解消しません。  
修正提案: `A-1` の成功条件を「観測可能性の回復」に限定し、`best_no_trade_rate` 改善は `B` 系施策の評価指標に分離してください。

[Warning] `pnl_record_consistency = P(trade_count>0 かつ total_pnl != 0.0)` は不適切です。実測 PnL が真に 0.0 のケースを誤検知します。  
修正提案: 「再計算した backtest 値と archive 値が一致する率」か、「recorded_from_stage` フラグ」で測ってください。

[Warning] 「短縮 RUN 2 本で有意低下」は C7 に反します。2 本は有意性判断の根拠になりません。同一 seed の反復も独立試行ではありません。  
修正提案: 2 本は smoke check と明記し、因果主張は 5 本以上の descriptive comparison に下げてください。

5. リスク

[Critical] `B-1` の sentinel を archive `fitness_pen` に入れると、calibrate-gate の quantile pool を汚染します。多数の `-1e12` が入ると threshold が floor 側へ寄り、Stage A を別方向に壊すリスクがあります。[`src/alpha_factory/calibrate_gate.py#L317`](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/calibrate_gate.py#L317) [`src/alpha_factory/calibrate_gate.py#L578`](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/calibrate_gate.py#L578)  
修正提案: sentinel は archive canonical 値に入れず、選抜専用 cache か feasibility bit で処理してください。どうしても archive に入れるなら calibrate 側で除外規約が必要です。

[Warning] `exception_caught / no_trades 時 total_pnl=0.0` は「未測定」と「実測ゼロ」を依然として混同します。  
修正提案: `pnl_measured: bool` か `metric_state` を別で持ってください。無理なら `reason_codes` ベースの監査に留めてください。

6. スコープの適切さ

[Warning] 1 つの概念設計に `A-1`, `B-1`, `B-2`, 実験計画まで入っており、最小変更になっていません。  
修正提案: 今回は `trade_count=0` をどう下位化するかだけに絞り、PnL 側は別 TODO に切ってください。`B-2` は今回から落とすべきです。

7. メモリ制約

[Suggestion] メモリ影響は軽微です。ここは懸念なしです。

8. 前提検証 (C4)

[Warning] 「記録経路の不整合が主因」は archive `total_pnl` については verified ですが、選抜崩壊の主因としては未証明です。選抜崩壊は `fitness_pen=0` の no-trade 優位だけで説明できます。  
修正提案: `A-1` は「archive observability gap」、`B-1` は「selection pathology」と分けて記述してください。

9. Design-first 原則 (C1)

[Suggestion] 調査自体は方向性が良いです。設計本文に「現行 SSOT をどこで意図的に上書きするのか」を明記すると、レビュー通過しやすくなります。

**結論**

現状のままでは通せません。主な理由は 2 つです。  
1 つ目は `A-1` が archive `total_pnl` の列意味論を壊す点です。  
2 つ目は `B-1` が calibrate-gate を巻き込んで canonical `fitness_pen` を汚す点です。

最小修正版としては、`total_pnl` は canonical 列のまま維持し、`trade_count=0` の下位化は [`scripts/alpha_factory/run_ga.py`](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py) の `selection_score` に feasibility を足す方向を推奨します。PnL 側は別 TODO の audit/log に切り出すのが妥当です。