# Round 1 Design Review

## P1-1 (Stage B window guard) 判定
REQUEST_CHANGES

- [Critical] 「現実装に guard がない」は事実不一致です。既に `run_ga` 起動時に `n_unique_dates + compute_max_folds` の preflight があり、`wf_min_folds_required` と比較しています（[run_ga.py#L1493](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py#L1493), [swim_lane.py#L476](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/swim_lane.py#L476), [walk_forward.py#L48](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/walk_forward.py#L48)）。
- [Critical] 提案式が `bars_per_day` 前提なのは SSOT 不整合です。実 fold 生成は observed-day（`make_wf_folds`）で行っており、24/7・24/5固定換算は誤判定リスクが高いです（[walk_forward.py#L3](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/walk_forward.py#L3)）。
- [Critical] 擬似コードは `passed` ログを先に出してから例外を投げるため監査ログが逆転します（[detailed-design.md#L66](/Users/ishitoya/repository/zenigame-fx/devnotes/20260505-1529-fx-improve-c2/detailed-design.md#L66)）。
- [Warning] `projected_fold_count` 式は underfilled 時に負値化し得ます。`max(0, ...)` か `compute_max_folds` 再利用に統一が必要です。
- 修正案: `bars_per_day` ベースをやめ、既存 `compute_max_folds` を使って「起動時 fail-closed」に変更する。

## P1-2 (WF 窓値変更) 判定
REQUEST_CHANGES

- [Critical] 「Principled Parametric」と言える条件は満たし切れていません。根拠計算が `bars_per_day` 依存で、実装 SSOT（observed-day）と不一致です。
- [Critical] `wf_min_folds_required=2` のまま「実質 min=5 を guard で確保」は設計の二重基準です（[detailed-design.md#L153](/Users/ishitoya/repository/zenigame-fx/devnotes/20260505-1529-fx-improve-c2/detailed-design.md#L153)）。
- [Warning] テスト対象に `test_stage_b_evaluator.py` が挙がっていますが現行に該当ファイルがありません（[detailed-design.md#L169](/Users/ishitoya/repository/zenigame-fx/devnotes/20260505-1529-fx-improve-c2/detailed-design.md#L169)）。
- 境界判断: 閾値（Sharpe/positive_fold）を緩めていない点は良いですが、窓短縮は実質的に通過難易度へ影響するため「幾何制約のSSOT一致 + 事前定義した反証条件」が必須です。

## P4 (per_generation 補修) 判定
REQUEST_CHANGES

- [Critical] `best_fitness_raw / median_fitness_pen / population_diversity` は現行 `per_generation` に存在しません。writer 欠陥というより schema 未定義です（[run_ga.py#L903](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py#L903), [run-34.md#L166](/Users/ishitoya/repository/zenigame-fx/reports/run-reports/run-34.md#L166)）。
- [Critical] `stage_X_pass_count` は命名不一致で、実際は `stage_a_pass/stage_b_pass/stage_c_pass` が既に記録済みです（[run_ga.py#L1644](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py#L1644)）。
- [Warning] 参照予定の `docs/alpha_factory/architecture.md` は現状存在しません。
- 修正案: 「writer補修」ではなく「追加する観測項目の定義・算出式・保存先」を先に確定する。

## P2 (分析のみ trade_count 層別) 判定
INCONCLUSIVE

- [Warning] n=22 全体で、層別後は n<10 が出る可能性が高く、因果断定は不可です（C7）。  
- [Warning] Stage A pass / Stage B pass で層別比較する時点で conditioning が入るため、collider bias 回避の明記が必要です（C3）。
- 修正案: 本ラウンドは記述統計（中央値・符号率・件数）に限定し、結論は `INCONCLUSIVE` を許容する。

## 全体判定
CHANGES_REQUESTED

## 主要指摘
- Facts: Stage B pass 22件、`n_fold_effective` は Stage A pass母集団で max=2（[run-34.md#L61](/Users/ishitoya/repository/zenigame-fx/reports/run-reports/run-34.md#L61), [run-34.md#L92](/Users/ishitoya/repository/zenigame-fx/reports/run-reports/run-34.md#L92)）。
- Facts: WF feasibility の計算 SSOTは既に `compute_max_folds`（observed-day）です（[walk_forward.py#L48](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/walk_forward.py#L48)）。
- Interpretation: 今回の最小収束は「1仮説=有効fold不足が主因」「1最小変更=既存 `compute_max_folds` 判定を起動時 fail-closed 化（bars/day式は不採用）」に絞るのが妥当です。