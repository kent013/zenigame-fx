# 詳細設計: Run 11 施策

## 使命・制約（絶対遵守）

- 使命: live_criteria 全指標同時充足
- FX 固有制約: イントラデイ前提 / ロング・ショート両方向許容 / スワップ・スプレッド反映
- 禁止事項 1〜7（codex-review 規約参照、特に取引回数削減は今回の改善対象そのもの）

## 施策一覧

| # | 施策名 | 変更ファイル | target_metric |
|---|--------|------------|--------------|
| C1 (T031) | Stage A trade_count feasibility 制約 | `src/alpha_factory/config.py`, `config/alpha_factory/default.yaml`, `scripts/alpha_factory/run_ga.py`, `scripts/alpha_factory/generate_run_report.py`, `tests/scripts/test_alpha_factory_run_ga.py` | trade_count, total_pnl |

## C1: T031 Phase 1 — regime-participation-constraint

### 詳細設計の SSoT

`devnotes/20260425-0937-regime-participation-constraint/detailed-design.md` を SSoT として使用する。本ファイルでは要点のみ再掲。

### target_metric / failure_mode / causal_path / falsification / success_criterion

improvement-plan.md C1 行参照（同内容）。

### 変更箇所サマリー（SSoT 抜粋）

1. `src/alpha_factory/config.py`: `GAFeasibilityConfig` dataclass 追加（entry_count_min=1, hard_cap=10000, fallback enable）
2. `config/alpha_factory/default.yaml`: `ga.feasibility` セクション追加
3. `scripts/alpha_factory/run_ga.py`:
   - `IndividualCacheEntry` に feasibility / violation フィールド追加
   - `selection_score` を 6 要素化（feasibility を最初の鍵に追加）
   - `_update_cache()` で feasibility 計算
4. `scripts/alpha_factory/generate_run_report.py`: 6 要素説明 + tc=0 比率追加
5. `tests/scripts/test_alpha_factory_run_ga.py`: 既存 smoke test の 6 要素期待値更新 + 新規 RPC test

### 波及変更

- AGENTS.md: なし
- skill: なし
- config: `default.yaml` 変更済（施策 2）
- docs: run-report 自動説明で吸収

### ルックアヘッドバイアスチェック

primitive 変更なし。selection_score の評価は世代内集計のみで未来データ非参照。

### パフォーマンスチェック

- compute_all_bars 影響なし（feasibility 判定は per-individual の冗長計算のみ）
- メモリ影響軽微（int field 1-2 個追加）

### テスト計画

- 既存 smoke test の selection_score 6 要素期待値更新
- 新規 RPC test:
  - trade_count=0 個体が selection_score で下位に淘汰されること
  - feasibility=True 個体がいない場合に fallback で従来 5 要素 selection が動作すること
  - apply_from_generation の境界値（generation=0 から有効、past 世代に適用なし）

### リスク

- **fallback 経路バグ**: feasibility=True 個体がゼロのとき fallback が機能しないと GA 全停止のリスク。SSoT 設計で `enable_fallback_when_all_infeasible=True` がデフォルト。テスト必須。
- **過淘汰**: entry_count_min=1 が厳しすぎる可能性。Phase 1 では最小値で開始し、Run 11 結果を観測してから引き上げ判断。

## Run 11 実行パラメータ

| パラメータ | 値 | R10 からの変更 |
|-----------|-----|--------------|
| population_size | 96 | 変更なし |
| generations | 60 | 変更なし |
| instrument | EUR_JPY | 変更なし |
| crossover_rate | 0.7 | 変更なし |
| mutation_rate | 0.3 | 変更なし |
| ga.feasibility.entry_count_min | 1 | **新規追加** |
| ga.feasibility.apply_from_generation | 0 | **新規追加** |
| ga.feasibility.enable_fallback_when_all_infeasible | true | **新規追加** |

## Codex レビュー

合議ループは時間制約により 1 ラウンドに圧縮。SSoT 設計（`devnotes/20260425-0937-regime-participation-constraint/`）が既に Codex レビュー 2 ラウンド完了済みのため、本サイクルでは該当 conceptual-review-round-1/2.md および detailed-review-round-1/2.md を継承する。
