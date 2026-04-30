# 詳細設計: Run 13 施策

## 使命・制約 (絶対遵守)
- 使命: live_criteria 全指標同時充足
- FX 固有制約: イントラデイ前提 / ロング・ショート両方向許容 / スワップ・スプレッド反映
- 禁止事項 1〜7

## 施策一覧

| # | 施策名 | 変更ファイル | target_metric |
|---|--------|------------|--------------|
| C1 (T035) | Stage B 統計可観測性ハード契約 + reason_codes | `src/alpha_factory/{walk_forward,swim_lane,stage_gate,archive}.py`, `scripts/alpha_factory/generate_run_report.py`, tests, docs | reason_codes 単峰化 + B 失敗内訳可視化 |

## C1: T035 — Stage B Metric Completeness Gate

### SSoT
`devnotes/20260425-0937-stats-completeness-gate-stage-b/detailed-design.md` を SSoT として使用。本サイクルでは設計改訂はせず参照のみ。

### target_metric / failure_mode / causal_path / falsification / success_criterion
improvement-plan.md C1 行参照。

### 変更箇所サマリー (SSoT 抜粋)
1. `src/alpha_factory/walk_forward.py`: `wf_min_unique_dates(train, embargo, test) -> int` helper 追加 + `make_wf_folds` 内部もこの helper 使用 (SSOT 二重化回避)
2. `src/alpha_factory/swim_lane.py`: LaneManager で観測日数充足検査 → 不足時 skip-path
3. `src/alpha_factory/stage_gate.py`: Stage B 観察可能性メトリクス (median_oos_sharpe / positive_fold_ratio / dsr / wf_fold_count / wf_train_days_used) を pass/fail 関係なく出力
4. `src/alpha_factory/archive.py`: schema 3 列追加 (`stage_b_reason_code`, `stage_b_n_folds`, `stage_b_n_unique_dates`)
5. `scripts/alpha_factory/generate_run_report.py`: 世代別 reason_code histogram + 分布表示
6. `tests/alpha_factory/`: 各施策にテスト
7. `docs/alpha_factory/`: stage-gates.md / genome-archive-schema.md 更新

### reason_code 列挙 (SSoT 抜粋)
- `STAGE_B_PASS`: 通過
- `WF_INSUFFICIENT_UNIQUE_DATES`: 観測日数不足
- `MEDIAN_OOS_SHARPE_LOW`: median_oos_sharpe < threshold
- `POSITIVE_FOLD_RATIO_LOW`: positive_fold_min 未達
- `DSR_LOW`: dsr_min 未達
- `NO_TRADES_IN_OOS`: OOS で取引ゼロ
- `EXCEPTION`: 評価中の例外

### 波及変更
- AGENTS.md: なし
- skill: `.claude/skills/zenigame-fx-run-report/SKILL.md` の「reason_code histogram」追記 (波及)
- config: なし
- docs: stage-gates.md / genome-archive-schema.md / terminology.md (helper 言及)

### ルックアヘッドバイアスチェック
primitive 変更なし。Stage B 評価結果のメタデータ追加のみで未来データ非参照。

### パフォーマンスチェック
- compute_all_bars 影響なし
- archive 3 列追加でメモリ影響軽微 (int + str)

### テスト計画
- `tests/alpha_factory/test_walk_forward.py`: wf_min_unique_dates の単体テスト + sufficiency 境界値
- `tests/alpha_factory/test_swim_lane.py`: skip-path テスト
- `tests/alpha_factory/test_stage_gate.py`: 観測 metrics の pass/fail 独立性 + reason_code 算出
- `tests/alpha_factory/test_archive.py`: schema 3 列の存在 + 値型
- `tests/scripts/test_generate_run_report.py`: reason_code histogram セクション

### リスク
- archive schema 拡張 → 旧 archive の Parquet 読み込み backward 互換性: 既存 archive 列は変更なし、新規 3 列は missing → defensive null 扱い
- LaneManager skip-path で「観測日数不足個体」の selection_score 影響: T031 fallback 経路で legacy 4 要素にフォールバック (B/C 全 False で fitness_pen 順)

## Run 13 実行パラメータ

| パラメータ | 値 | R12 からの変更 |
|-----------|-----|--------------|
| population_size | 96 | 変更なし |
| generations | 60 | 変更なし |
| instrument | EUR_JPY | 変更なし |
| ga.feasibility (T031) | 既定 | 変更なし |

## Codex レビュー
合議 1 ラウンド圧縮。SSoT (`devnotes/20260425-0937-stats-completeness-gate-stage-b/`) は既に Codex 詳細レビュー Round 3 APPROVED 済みで継承。impl 段階で再 review。
