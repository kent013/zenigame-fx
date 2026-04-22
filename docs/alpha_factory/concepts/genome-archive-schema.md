# Concept: genome-archive-schema

## 目的

ゲノム archive を Parquet 形式で `.cache/alpha_factory/runs/genomes_{run_id}.parquet` に出力。横断分析・系譜追跡を可能に。

## スキーマ

| カラム | 型 | 説明 |
|-------|----|------|
| run_id | str | `run_YYYYMMDD_HHMMSS` |
| run_number | int | 連番 |
| generation | int | 世代 |
| individual_name | str | `gX_iY` |
| instrument | str | 対象通貨ペア |
| lane_id | str | `tier1_{pair}` or `graduation` |
| parent_a | str nullable | 系譜追跡 |
| parent_b | str nullable | 系譜追跡 |
| genome_json | str | シリアライズ済み Genome |
| fitness_raw | float | ペナルティ前 |
| fitness_pen | float | ペナルティ後 |
| stage_a_pass | bool | |
| stage_b_pass | bool | |
| stage_c_pass | bool | |
| trade_count | int | |
| total_pnl | float | |
| sharpe | float nullable | |
| sortino | float nullable | |
| calmar | float nullable | |
| max_drawdown_pct | float | |
| active_clause | int | 実際に発火した clause 数 |
| n_nodes | int | 複雑度 |
| bootstrap_ci_lower | float | |
| bootstrap_ci_upper | float | |
| fold_sign_ratio | float | |
| dsr | float nullable | Deflated Sharpe |
| ii_lite_pass | bool nullable | shadow 時は記録のみ |
| graduated | bool | Tier 1 → Graduation lane 卒業 |

## 実装

`src/alpha_factory/archive.py`:
- `GENOMES_SCHEMA` 定義
- `_create_row_template()` 初期値
- `collect_stage_a/b/c` 書き込み
- `flush_to_parquet(run_id)` 出力

## テスト

- スキーマの全カラムが `_create_row_template` で初期化されている
- `collect_stage_*` で値が正しく設定される
- Parquet 読み込みで型が保たれる

## 優先度・モード

- Priority: Critical
- Mode: standalone
- テーマ: ga-architecture
