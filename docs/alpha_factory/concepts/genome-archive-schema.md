# Concept: genome-archive-schema

> **実装状況**: T015 完了済み (`src/alpha_factory/archive.py`)。本ドキュメントが
> 列意味論の SSOT。詳細設計は
> `devnotes/20260423-1826-genome-archive-schema/{conceptual,detailed}-design.md`。

## 目的

ゲノム archive を Parquet 形式で `.cache/alpha_factory/runs/genomes_{run_id}.parquet`
に出力。横断分析（複数 Run 比較）・系譜追跡（parent_a / parent_b）を可能にする。

## スキーマ (33 カラム、`GENOMES_SCHEMA`)

> 履歴: 28 カラム (T015 当初) → 30 カラム (T-sharpe Phase 1A: `trade_sharpe_raw`, `sharpe_calc_version`) → 33 カラム (T035: `n_fold_effective`, `positive_fold_ratio_effective`, `stage_b_reason_codes`)。

主キー: **複合キー (lane_id, generation, individual_name)**
（multi-lane で同名個体が衝突しないため lane_id を必須に含める）

| カラム | 型 | nullable | 説明 |
|-------|----|----------|------|
| run_id | str | NO | `run_YYYYMMDD_HHMMSS` |
| run_number | int32 | NO | 連番 |
| generation | int32 | NO | 世代 |
| individual_name | str | NO | `gX_iY` |
| instrument | str | NO | 対象通貨ペア |
| lane_id | str | NO | `tier1_{pair}` or `graduation` |
| parent_a | str | YES | 系譜追跡 |
| parent_b | str | YES | 系譜追跡 |
| genome_json | str | NO | シリアライズ済み Genome (`json.dumps(genome_to_dict(g), sort_keys=True)`) |
| fitness_raw | float64 | NO | ペナルティ前 (Stage A `payload.fitness_raw`) |
| fitness_pen | float64 | NO | ペナルティ後 (Stage A `payload.fitness_pen`) |
| stage_a_pass | bool | NO | |
| stage_b_pass | bool | NO | |
| stage_c_pass | bool | NO | |
| trade_count | int32 | NO | Stage A → B → C で順次上書き（最後段が prevail） |
| total_pnl | float64 | NO | Stage B `is_full_total_pnl` → Stage C `total_pnl` で上書き |
| sharpe | float64 | YES | Stage A `sharpe_raw` → B `is_full_sharpe` → C `sharpe` で上書き |
| sortino | float64 | YES | **Phase 2 placeholder = None** (BacktestMetrics 拡張後に上書き) |
| calmar | float64 | YES | **Phase 2 placeholder = None** (同上) |
| max_drawdown_pct | float64 | NO | Stage C `max_drawdown_frac × 100`（% に戻す） |
| active_clause | int32 | NO | **Phase 2 placeholder = 0**（runtime 発火数取得経路は別 TODO） |
| n_nodes | int32 | NO | 構造的複雑度 = `Σ(len(directional)+len(local_gate))` |
| bootstrap_ci_lower | float64 | YES | **本 TODO スコープ外** (block_bootstrap_sharpe_ci 統合は別 TODO) |
| bootstrap_ci_upper | float64 | YES | 同上 |
| fold_sign_ratio | float64 | YES | `statistics.fold_sign_ratio(payload.oos_sharpes)` 実値計算（n_fold<2 で 0.0、未提供で None） |
| dsr | float64 | YES | Deflated Sharpe (Stage B `dsr`、Phase 4 まで通常 None) |
| ii_lite_pass | bool | YES | Stage C `payload.cross_pair.result.passed` から導出（skipped → None） |
| graduated | bool | NO | Tier 1 → Graduation lane 卒業フラグ (`mark_graduated`) |

## 4 段伝搬契約

```
GENOMES_SCHEMA (定義)
    │
    ▼
_create_row_template()  ← 全カラムを default で初期化
    │ (import-time assert で SCHEMA と完全一致を保証)
    ▼
collect_stage_a/b/c()   ← StageResult.metrics["payload"] から partial 上書き
    │
    ▼
flush()                 ← last-mile guard: row keys != schema names で ValueError
    │                    pa.Table.from_pylist(rows, schema=GENOMES_SCHEMA)
    ▼
Parquet ファイル
```

## monotonic enrich (重複 collect ポリシー)

各 row は内部に `_max_stage_seen: Literal["", "A", "B", "C"]` を持ち、stage 順序
（`{"":0,"A":1,"B":2,"C":3}`）で次のように振る舞う:

| 状況 | 動作 |
|------|------|
| 新規行 (key 未登録) | template から作成、collect 適用 |
| 後段 stage 適用 (`_max_stage_seen < incoming`) | enrich 上書き |
| 同一 stage 再 collect | 上書き + WARN `archive.same_stage_recollect` |
| 前段 stage 逆流 | **無視 (no-op)** + WARN `archive.stage_regression_ignored` |

`_max_stage_seen` 自体は Parquet には書き出さない（in-memory 専用）。

## 実装

`src/alpha_factory/archive.py`:
- `GENOMES_SCHEMA` (`pa.Schema`)
- `_create_row_template()` 初期値
- `GenomeArchive(run_id, run_number)` クラス:
  - `collect_stage_a(genome, lane_id, generation, stage_result, *, instrument, parent_a=None, parent_b=None)`
  - `collect_stage_b(genome, lane_id, generation, stage_result, *, instrument=None)`
  - `collect_stage_c(genome, lane_id, generation, stage_result, *, instrument=None)`
  - `mark_graduated(lane_id, generation, individual_name)`
  - `flush(output_dir=None) -> Path`
  - `load(parquet_path) -> pa.Table` (`@staticmethod`)

`instrument` は **Stage A 常時必須**、Stage B/C は新規行作成時のみ必須
（既存行への enrich なら省略可）。

## テスト

`tests/alpha_factory/test_archive.py` (36 ケース):
- スキーマの全カラムが `_create_row_template` で初期化されている
- `collect_stage_*` で値が正しく設定される
- Parquet 読み込みで型・nullable が保たれる
- monotonic enrich の 3 パターン（新規 / 同 stage / 逆流）
- 複合キー（lane_id 違い、generation 違い）の独立性
- payload 欠損 / 型不正の defensive 動作
- mark_graduated の lane 別動作

## 優先度・モード

- Priority: Critical
- Mode: standalone
- テーマ: ga-architecture

## 関連 TODO

- **T015 (Closed)**: 本仕様の実装。
- 次段（未着手）: swim-lane-manager (T016) / run-ga-full-rewrite (T017)
  で `GenomeArchive` を Stage gate evaluation pipeline に組み込む。
- 別 TODO: `active_clause` の runtime 発火カウンタ実装、`bootstrap_ci_*` の
  block_bootstrap_sharpe_ci 統合、`sortino` / `calmar` の BacktestMetrics 拡張。

## 関連ドキュメント

- [clause-architecture.md](../clause-architecture.md) §Genome Archive
- [terminology.md](../terminology.md#genome-archive) — `GenomeArchive` / `GENOMES_SCHEMA` / monotonic enrich
- [stage-gates.md](../stage-gates.md) — Stage A/B/C payload structure (StageResult.metrics)
