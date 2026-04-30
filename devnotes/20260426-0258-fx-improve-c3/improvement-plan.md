# 最終改善計画: Run 13 → Run 14 (cycle 3)

## 合議ステータス: CONSENSUS REACHED (Codex 案 A 採用、1 ラウンド圧縮)

Codex (`analysis-codex.md`) 全体判定 **CRITICAL_DRIFT**:
> 性能ドリフトではなく、検証パイプラインの構造不成立。Stage B feasibility 不成立が根因。最優先は「Stage B で fold を作れる条件を満たすこと」。ここを直さない限り他 TODO は効かない。

## cycle_focus

`ga_improvements`: GA config 介入 (TODO 由来施策なし、構造対応 T038 は別 cycle で本格実装)

## 確定施策一覧

| # | 施策名 | 内容 | 変更対象 | 優先度 | 変更分類 | target_metric | failure_mode | causal_path | falsification | success_criterion | 合議結果 |
|---|--------|------|---------|--------|---------|--------------|-------------|------------|---------------|-------------------|---------|
| C1 | WF パラメータ短縮 (Stage B fold 成立目的) | `wf_train_days` 120→60, `wf_test_days` 20→10, `wf_step_days` 20→10 (合計最小観測日数 141→71) | `config/alpha_factory/default.yaml` | Critical | Principled Parametric (理論: 必要日数 < 利用可能日数を満たすため。Run-13 で fold 不足が定量確認済み) | Stage B `insufficient_folds_rate` 100% → ≪50% | Run-13 で Stage A pass=2000、Stage B pass=0、insufficient_folds=2000 (100%) | dataset_days (~127) と WF 必要日数 (141) の不整合 → fold 不足 → 全個体 reject | Run-14 で reason 単峰の主因が insufficient_folds のままなら H 棄却 (短窓化が原因解消にならない → 根本的に dataset 期間延長 / 構造対応必須) | Run-14 で Stage B pass≥1 出現、または primary reason 首位が insufficient_folds 以外に変化 | APPROVED (Codex 案 A、Sharpe 閾値不変・期間不変・構造より先に「動く」を優先) |

## 却下・差替え

| # | 提案 | 理由 |
|---|------|---------|
| 案 B (dataset 期間延長) | 禁止事項 1 (期間延長) リスク。Codex も「end 日固定で start 前倒し」前提付きの保留扱い |
| 案 C (T038 完全実装) | 構造的 feasibility contract + WF プロファイル動的選択は実装規模大 (1-2h)。次サイクルで本格設計し別 cycle で実装 |
| 同時着手 (T033/T034/T036/T037) | Stage B 全滅が解消するまで他 TODO は効果不明 |

## 保留事項

| # | 仮説 | 検証条件 |
|---|------|---------|
| H1 | 短窓化で fold 成立 → Stage B pass 出現 | Run-14 で B-pass≥1 |
| H2 | 短窓化でも別 reason (median_oos_sharpe<min / positive_fold_ratio<min) で reject される可能性 | Run-14 reason 分布から判断 |
| H3 | T038 Feasibility Contract (max_folds 事前計算 + WF profile 動的選択) を cycle 4 で本格実装 | Run-14 結果に応じて優先度判断 |

## 次フェーズへの申し送り

cycle 3 は config-only 介入のため worktree 不要、実装フェーズ skip。Phase 4 (GA RUN-14) 直行。
