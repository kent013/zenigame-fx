# 最終改善計画: Run 12 → Run 13

## 合議ステータス: CONSENSUS REACHED (Round 1 圧縮モード)

Codex (`analysis-codex.md`) は CRITICAL_DRIFT 判定で **T032 signal-eval-consistency-fix** を Critical 推奨。  
本サイクルの整合性チェック: T032 詳細設計 (`devnotes/20260425-0939-signal-eval-consistency-fix/detailed-design.md`) を確認したところ **施策内容が T031 (selection_score に feasibility 追加) と完全に重複** しており、T031 が cycle 1 で main にマージされた現時点では **T032 は superseded (obsolete)**。

Codex の本旨は「Stage B 全滅の根本原因を観測可能にする」(success_criterion #3 で `reason_codes` の単峰化を要求) にあるため、最も近い候補 **T035 stats-completeness-gate-stage-b** に振替える。

## cycle_focus

`mixed`: TODO 由来 1 件 (T035) + GA 分析の含意確認 (B 全滅打破の観測強化)

## 確定施策一覧

| # | 施策名 | 内容 | 変更対象 | 優先度 | 変更分類 | target_metric | failure_mode | causal_path | falsification | success_criterion | 合議結果 |
|---|--------|------|---------|--------|---------|--------------|-------------|------------|---------------|-------------------|---------|
| C1 (T035) | Stage B 統計可観測性ハード契約 + reason_codes | walk_forward sufficiency helper / LaneManager skip-path / stage_gate observability metrics / archive schema 3 列追加 / run-report 世代別 reason histogram | `src/alpha_factory/{walk_forward,swim_lane,stage_gate,archive}.py`, `scripts/alpha_factory/generate_run_report.py`, tests, docs | Critical | Structural (新観測層) | 観測可能性 + Stage B pass の単峰化 | Run-12 で B=0/5856 の内訳が見えない (Sharpe 不足? PnL 不足? cost 過大? wf 観測日数不足?) | reason_codes 不在 → B 失敗内訳ブラックボックス → 探索が局所最適へ陥る | T035 導入後も reason_codes が分布せず B=0 のままなら H 棄却 (次は T036/T033 へ) | Run-13 で B 失敗の主要 reason_code が単峰化（top-1 が >50%）するか、または B-pass≥1 出現 | APPROVED (Codex 本旨「reason_codes 単峰化」と整合) |

## 却下・差し替えた提案

| # | 提案 | 却下/差替理由 |
|---|------|---------|
| T032 (Codex 推奨) | T031 と施策内容完全重複 (`feasible_trade` = `trade_count >= 1` flag、selection_score 拡張)。T031 が cycle 1 で main マージ済みで superseded |
| T032 → T035 振替 | T035 は Codex success_criterion #3 (`reason_codes` 単峰化) を直接実現する設計。Codex の analysis recommendation 本旨と整合 |
| 同時着手 (T033/T034/T036/T037) | 1 サイクル変更箇所最小化、T035 単独効果測定を優先 |

## 保留事項 (次 Run 検証申し送り)

| # | 仮説 | 最小変更案 | 検証条件 |
|---|------|----------|---------|
| H1 | reason_codes 導入で B 失敗の主要因が判明するが、根本対策はそれを見て決める | cycle 3 で T033 (PnL/cost ledger) または T034 (no-trade fitness guard) を選択 | Run-13 reason_codes 分布から判断 |
| H2 | wf 観測日数不足 (eval consistency 問題) が真因なら T035 で B-pass 出現の可能性 | T035 単独 | Run-13 で B-pass≥1 |

## 次フェーズへの申し送り

T035 詳細設計は `devnotes/20260425-0937-stats-completeness-gate-stage-b/detailed-design.md` を SSoT として使用。  
T032 は本 cycle で Closed (obsolete: superseded by T031) として TODO リストから除く。

## 副次タスク

- T032 を `obsolete` でクローズ (理由: superseded by T031)
