# PR5: Stage B gate pfr_only opt-in A/B

## 背景

archive 実測で:
- median_oos_sharpe → trade_sharpe_stage_c: Spearman ρ = **-0.361** (= 逆予測)
- positive_fold_ratio_effective → trade_sharpe_stage_c: ρ = **+0.345** (= 唯一の正予測)

= 現 Stage B gate (= `median_oos_sharpe_min` + `positive_fold_ratio_min` AND) は curve-fit 選好の疑い (Codex H_X'' PARTIAL CONFIRMED)。

## 目的

Stage B gate に `pfr_only` opt-in mode 導入:
- `legacy` (default): 現状 `median_oos_sharpe + positive_fold_ratio` AND
- `pfr_only` (opt-in): `positive_fold_ratio_effective` 単独 gate (= median_oos_sharpe は observe-only)

= 行動変更、 1 RUN smoke 必須。 PR4 と直交独立した opt-in。

## 期待効果

- curve-fit 個体 (= median 偏重) の Stage B 通過率低下
- 持続性候補 (= 高 positive_fold_ratio) の通過率上昇
- PR3 で追加した `persistence_score_shadow` との整合性確認

## スコープ

- `StageGateConfig.stage_b_gate_kind: Literal["legacy", "pfr_only"]` 追加
- `evaluate_stage_b` の gate 判定分岐
- default `legacy` で行動完全不変
- 1 RUN smoke 必須 (= ユーザー実行)

## 非目的

- median_oos_sharpe 廃止 (= observe-only として残す)
- archive predictor 化 (= Codex Y Round 4 で REJECTED)

## 参考

- `devnotes/20260513-1402-handoff-pr1-pr2-postdebate/handoff.md` § 12 段 TODO 順 5
- `tmp/codex-debate-round2/.codex-output-debate-Y-round-4.md` § Q1
