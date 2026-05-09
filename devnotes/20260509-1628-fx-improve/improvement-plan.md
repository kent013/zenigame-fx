# 最終改善計画: Run 56 → Run 57 (cycle 4)

## 合議ステータス: CONSENSUS REACHED (Round 1)

## 確定施策一覧

| # | 施策名 | 内容 | 変更対象 | 優先度 | 変更分類 | target_metric | failure_mode | causal_path | falsification | success_criterion | 合議結果 |
|---|--------|------|---------|--------|---------|--------------|-------------|------------|---------------|-------------------|---------|
| C1 | dataset 範囲見直しで Stage C holdout 60日を構造的に確保 | dataset.start: 2025-10-01 → 2024-04-01、 dataset.end: 2026-04-01 → 2026-02-19 | `config/alpha_factory/default.yaml` | Critical | Structural | trade_count / total_pnl / sharpe (Stage C 60日評価環境の正常化) | holdout 21日で stage_partition_guard B-2 が WARN 通過必須、 smoke-test mode opt-in 必須、 live_criteria 評価窓が config 仕様未達 | dataset.end が DB 終端と近すぎ → Stage C holdout 短すぎ → live_criteria 評価窓が壊れる → mission 達成判定不能 | 変更後 Run も `--allow-holdout-short` 不要で完走しなければ False (calendar gap 等の別問題) | Run 57 で smoke-mode flag なしで完走、 stage_partition_guard.passed が holdout_short_override=False で通る、 dataset_holdout calendar span >= 48 日 | APPROVED |

## 却下された提案

なし (1 件のみ提示し全員 APPROVE)

## 保留事項

なし (合議 1 round で収束)

## cycle 4 内施策の射程

- 本サイクルは **C1 単独**。 1 cycle 1 構造的施策の方針 (Codex Q3 で APPROVE)
- DSR 配線復帰、 cross-pair shadow 再有効化、 elite collapse 対策は cycle 5+ に分散

## cycle 5+ 候補 (Codex Q4 推薦、 cycle 開始時に再評価)

| 優先 | 施策 | 変更分類 | 概要 |
|-----|------|---------|------|
| 高 | DSR 配線復帰 | Structural | `run_ga.py` で `compute_audit_dsr_for_genome` を呼び archive に格納、 多重比較補正の telemetry 再生 |
| 中 | cross-pair shadow forward path 再有効化 | Structural | `ii_lite_pass` を inline_shadow 相当で復旧、 EUR_USD 等で shadow ポジション追跡 |
| 中 | elite collapse 対策 (niche preserving / re-entry guard) | Principled | Stage B pass 458 に対し unique fp=96 (21%) の集団偏在を解消、 selection 構造を理論根拠で改良 |

## Run 比較可能性ガイドライン (Codex Q2)

- Run 57 以降は **新 dataset baseline (start=2024-04-01, end=2026-02-19)** を使用
- Run 56 以前は **pre-fix** として archive、 直接 fitness 比較しない
- 後続レポートは「同一 dataset 範囲」のみを比較セットとして扱う
- Stage B/C sharpe は z-score normalize / rolling percentile で regime 差吸収を検討 (Cycle 5+ で導入可)

## 次フェーズへの申し送り

Phase C で C1 の詳細設計を作成。 変更は `config/alpha_factory/default.yaml` の dataset セクション 2 行のみ。 波及変更チェック: AGENTS.md / SKILL.md には dataset 値の絶対参照はないはず (要確認)、 docs/alpha_factory/stage-gates.md / runbook.md に dataset.start/end が記載されていれば同期更新。
