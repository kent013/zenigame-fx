# Concept: alpha-sieve

## 目的

Stage C を通過した個体は「Stage C holdout 期間で `live_criteria` を満たした」状態に過ぎない。
**Alpha Sieve** は、その個体群を **さらに別の OOS 期間（holdout 直後の 90 日）で再検証** することで、
true positive を絞り込み、過学習・holdout 期間特有のレジーム依存を排除する追加ゲートである。

**位置付け**:
- Stage A → Stage B → Stage C (live_criteria) **→ Alpha Sieve (本ゲート)** → Live Trading 候補
- Phase 4 INFRA-ADAPT の中核。Cross-pair (ii-lite) shadow と並んで Stage C 通過個体の品質保証を担う。

## 設計

### 入力

- `archive Parquet` (`.cache/alpha_factory/runs/genomes_{run_id}.parquet`)
- `summary.json` (`reports/run-reports/run-{N}/summary.json`) — backtest_config / dataset 範囲継承
- 対象個体: `stage_c_pass=True` の全行

### OOS 期間

`holdout_end + sieve_embargo_days(=5) ~ +90 日`（合計 95 日先まで bars が必要）

- `holdout_end` = `dataset.end + stage_c_holdout_days`（GA Run の Stage C 終端）
- 5 日の **embargo** で境界依存（autocorrelation / レジーム持続）を緩和（López de Prado 2018 Ch.7）
- 既存 holdout と重ならず、最新側に 95 日分の bars を要求
- DB に bars が無い場合は `no_data` 理由で skip

### 通過基準（AND）

- `sharpe > 0.5`
- `trade_count >= 30`
- `total_pnl > 0`

(debate-synthesis.md §B Stage C 通過後の追加 OOS 検証として、過度に保守的でない最小ライン。
過学習を排除しつつ、Phase 2 段階での discrimination 能力を確保する目的。
小標本ノイズ抑制のため `trade_count_min` は Stage C 50 / 60d ≒ 0.83 件/日に対し
Sieve は 30 / 90d ≒ 0.33 件/日とし、Stage より緩いが「希にしか取引しない」個体を排除する。)

### Deflated Sharpe Ratio (DSR)

レポート併記のみ（**ゲート判定には未使用**）。Phase 4 で hard gate 化候補。

### 出力

- `reports/alpha-sieve/{yyyy-mm}/sieve-R{run_number}.md`
  - 通過個体一覧（OOS Sharpe / total_pnl / trade_count + GA Stage C metrics 対照）
  - 統計サマリー (mean Sharpe / pass 率 / pass 数 / total 評価数)
  - OOS 期間（実 bar 数）
  - Stage C 通過 0 件時は `no_candidates` レポート

### 関連 skill

- `/zenigame-fx-codex-review` — Codex review 共通呼び出し
- `/zenigame-fx-alpha-sieve` — 本ゲート実行 skill (新設)

### 学術背景

- **OOS Validation の段階化** — Bailey et al. (2014) "PBO" の back-test overfitting 抑制思想
- **Holdout の二段化** — López de Prado (2018) Ch.7 "Cross-Validation in Finance" の精神を Stage C → Sieve に適用
- **Phase 2 は CSCV 簡易版** — 本実装は CSCV (Bailey et al. 2014) の簡易版として **単一追加 OOS 窓** を先行導入。
  Phase 4 で複数非連続窓（例: 45d × 2 with gap）に拡張し、過学習確率推定へ接続する。

## 実装範囲

- `scripts/alpha_factory/run_alpha_sieve.py`（CLI エントリ）
- `.claude/skills/zenigame-fx-alpha-sieve/SKILL.md`（skill 移植）
- `tests/scripts/test_run_alpha_sieve.py`
- `docs/alpha_factory/sieve.md`（詳細運用ドキュメント、本ファイルとは別の運用視点）

## SSOT

- 通過基準 / OOS 期間: 本 concept stub
- 詳細運用 / I/O 仕様: `docs/alpha_factory/sieve.md`
- 用語定義: `docs/alpha_factory/terminology.md`

## 関連 TODO

- T025 (本タスク)
- 後続: post-run-review skill ポート、calibrate-gate ポート
