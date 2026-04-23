# Conceptual Design: Genome Archive Schema (T015)

## 目的

Alpha Factory の GA 個体評価結果を **Parquet 形式** で
`.cache/alpha_factory/runs/genomes_{run_id}.parquet` に保存し、
横断分析（複数 Run 間比較）と系譜追跡（parent_a / parent_b）を可能にする。

## 背景

T014 までで Stage A/B/C 評価 + Clause Genome + 32 primitive + fitness が
出揃った。次の段階（T016 swim-lane-manager / T017 run-ga-full-rewrite）では
1 Run あたり数千個体の評価結果を出力する必要があり、その**永続化基盤**が必要。

## Hypothesis (検証したい仮説)

1. **個体単位 1 行**で全評価指標を保存する flat schema の方が、
   `Mapping[str, object]` のネスト dict より分析親和性が高い
   - pandas / polars / DuckDB から SQL 風に集計できる
2. Stage A/B/C は時系列に進行するため、**partial fill** スタイル
   （Stage A 通過 → Stage B 通過 → Stage C 通過 で逐次更新）が自然
3. **行の主キーは複合 (run_id, lane_id, generation, individual_name)** とする。
   1 Run 内で同じ lane_id × 同じ generation × 同じ individual_name は単一 row
   （lane を跨ぐ同名個体は別 row、`g{gen}_i{idx}` の lane 衝突を防ぐ）。
   重複 collect は **stage 順序を尊重した「monotonic enrich」ポリシー**
   （後段 stage による enrich のみ許可、前段への逆流は ignore + WARN）。

## スコープ

### In Scope

- **GENOMES_SCHEMA**: pyarrow.Schema（28 カラム）
- **GenomeArchive**: 1 Run 分の buffering + flush クラス
- **collect_stage_a/b/c**: StageResult.metrics → row への射影
- **mark_graduated**: Tier 1 → Graduation lane 卒業フラグ
- **flush**: Parquet 書き出し（pyarrow.parquet）
- **load**: 静的メソッドで Parquet 読み戻し
- **pyarrow 依存追加** (Parquet I/O のため)

### Out of Scope

- swim-lane manager 統合 (T016)
- run-ga 統合 (T017)
- 複数 Run 横断クエリ ツール (将来)
- Schema 進化対応 (将来 — 当面は schema fix)

## 設計方針

### A. スキーマ哲学: Flat & Self-describing

- **1 行 = 1 個体 (individual_name × generation)**
- ネスト dict / list は `genome_json` (str) に集約
- それ以外は scalar 型（pandas/duckdb 親和性）
- nullable 型は pa.field(..., nullable=True) で明示（Parquet null サポート）

### B. 4段伝搬契約

GENOMES_SCHEMA から書き出し Parquet ファイルまでカラム抜けがない契約:

```
GENOMES_SCHEMA (定義)
   │
   ▼
_create_row_template()  ← 全カラムを default で初期化（None / 0 / False）
   │
   ▼
collect_stage_X(genome, lane_id, generation, stage_result, ...)
   │ ← StageResult.metrics["payload"] から値抽出 (Stage 別 mapper)
   ▼
self._rows[(generation, individual_name)] = updated_row
   │ (複合キー、_max_stage_seen で stage 順序を追跡)
   ▼
flush() → pa.Table.from_pylist(rows, schema=GENOMES_SCHEMA)
       → pq.write_table(...)
```

**抜けチェック**: テスト `test_template_has_all_columns` で
`set(template.keys()) == set(SCHEMA.names)` を検証。

### C. Stage 別マッピング

#### Stage A → row partial fill

```
fitness_raw         ← payload["fitness_raw"]
fitness_pen         ← payload["fitness_pen"]
stage_a_pass        ← stage_result.passed
trade_count         ← payload["trade_count"]
sharpe              ← payload["sharpe_raw"]   # raw Sharpe
n_nodes             ← genome 構造から計算（複雑度: directional+local_gate node 数合計）
active_clause       ← **Stage A backtest 中に実際に発火した clause 数**
                       （詳細設計で発火カウンタ取得方法を確定。
                        現時点で取得経路が確立していない場合は
                        `0` のまま残し schema doc 側を「future ext.」と注記
                        する案も併記、最終決定は detailed-design）
genome_json         ← json.dumps(genome_to_dict(genome))
```

> **注**: `active_clause` は schema 仕様上「runtime 発火数」であり、
> structural な「`weight != 0` の clause 数」とは別物。本 TODO では
> runtime 発火数を取れる経路（DslStrategy / engine からの戻り）が
> 既存にないため、detailed-design で次の 2 案から選ぶ:
> - (a) Stage A backtest を `clause_fired_counter` 付き strategy で再実行
> - (b) 暫定的に `0` を入れ、別 TODO で発火カウンタ実装後に上書き
>
> 列名の意味と実装値の乖離を避けるため、(b) の場合は schema doc 側を
> 「future: runtime 発火数。現状は placeholder=0」と明記する。

#### Stage B → row update

```
stage_b_pass        ← stage_result.passed
fold_sign_ratio     ← src.alpha_factory.statistics.fold_sign_ratio(
                          [s for s in payload["oos_sharpes"]]
                       )  # 列名どおりの符号反転比率を実値計算
                       (n_fold < 2 の場合は 0.0、no_folds 時は None)
dsr                 ← payload["dsr"] (Phase 4 まで None)
sharpe              ← payload["is_full_sharpe"] で上書き（より rich）
total_pnl           ← payload["is_full_total_pnl"]
trade_count         ← payload["is_full_trade_count"] で上書き
bootstrap_ci_lower  ← None (Stage B では計算しない、別 TODO)
bootstrap_ci_upper  ← None
```

#### Stage C → row update

```
stage_c_pass        ← stage_result.passed
sharpe              ← payload["sharpe"] (Stage C base) で上書き
total_pnl           ← payload["total_pnl"] で上書き
max_drawdown_pct    ← payload["max_drawdown_frac"] * 100 (% に戻す)
trade_count         ← payload["trade_count"] で上書き
ii_lite_pass        ← payload["cross_pair"]["result"].passed
                       if not payload["cross_pair"]["skipped"] else None
                       （**StageResult から一意に導出**。collect_stage_c
                       には別引数を作らない、SSOT は StageResult.metrics）
sortino, calmar     ← Stage C payload には現状無い → None
                      (将来 BacktestMetrics 拡張時に上書き)
```

### D. 重複 collect ポリシー（monotonic enrich）

行は **複合キー (run_id, generation, individual_name)** で識別する。
内部 dict は `self._rows[(generation, individual_name)]` で保持する
（run_id はインスタンス単位で固定）。

各 row は **`_max_stage_seen: Literal["", "A", "B", "C"]`** という内部
フィールドで「これまでに collect された最深 stage」を追跡する。

| 状況 | 動作 |
|------|------|
| 新規行 (key 未登録) | template から作成、collect 適用、`_max_stage_seen` 更新 |
| 後段 stage 適用 (`_max_stage_seen < incoming_stage`) | enrich 上書き OK、`_max_stage_seen` 更新、INFO ログ |
| 同一 stage 再 collect (`_max_stage_seen == incoming_stage`) | 上書き OK、WARN ログ `archive.same_stage_recollect` |
| 前段 stage 逆流 (`_max_stage_seen > incoming_stage`) | **無視 (no-op)**、WARN ログ `archive.stage_regression_ignored` |

ステージ順序: `A < B < C` (Literal 比較ではなく `STAGE_ORDER = {"":0,"A":1,"B":2,"C":3}` で実装)。

`_max_stage_seen` 自体は Parquet には書き出さない（in-memory のみの
契約フィールド）。flush 直前に row dict から pop する。

- 別 Run の同名 individual_name は別 GenomeArchive インスタンスで分離管理

### E. nullable / 型の扱い

| 種別 | デフォルト | 例 |
|------|----------|----|
| string nullable | None | parent_a, parent_b |
| string non-null | "" | run_id, individual_name |
| float64 nullable | None | sharpe, sortino, calmar, dsr, ... |
| float64 non-null | 0.0 | fitness_raw, fitness_pen, total_pnl, max_drawdown_pct |
| int32 non-null | 0 | trade_count, active_clause, n_nodes, generation |
| bool non-null | False | stage_a_pass, stage_b_pass, stage_c_pass, graduated |
| bool nullable | None | ii_lite_pass |

PyArrow の `pa.field(name, type, nullable=True/False)` で明示。
Parquet 書き出し時に nullable 不一致でエラーにならないよう template を厳密に揃える。

### F. ファイル配置

- `src/alpha_factory/archive.py`: 新規モジュール
- `tests/alpha_factory/test_archive.py`: 新規テスト
- 出力先: `.cache/alpha_factory/runs/genomes_{run_id}.parquet`
  - Repository root 直下の `.cache/` を共通 cache root とする
  - テストでは tmp_path に書き出し、本番パスは write しない

### G. pyarrow 依存

- `pyproject.toml [project] dependencies` に `pyarrow>=15.0` を追加
- 既存依存は numpy>=1.26 で arrow と互換
- `uv add pyarrow` で uv.lock 更新

## API スケッチ

```python
@dataclass
class GenomeArchive:
    run_id: str               # "run_YYYYMMDD_HHMMSS"
    run_number: int

    def collect_stage_a(
        self,
        genome: Genome,
        lane_id: str,
        generation: int,
        stage_result: StageResult,
        *,
        instrument: str,
        parent_a: str | None = None,
        parent_b: str | None = None,
    ) -> None: ...

    def collect_stage_b(
        self,
        genome: Genome,
        lane_id: str,
        generation: int,
        stage_result: StageResult,
        *,
        instrument: str | None = None,  # 既存行から引継ぎ可
    ) -> None: ...

    def collect_stage_c(
        self,
        genome: Genome,
        lane_id: str,
        generation: int,
        stage_result: StageResult,
        *,
        instrument: str | None = None,
    ) -> None:
        """ii_lite_pass は stage_result.metrics["payload"]["cross_pair"] から導出."""

    def mark_graduated(self, generation: int, individual_name: str) -> None:
        """主キーは (generation, individual_name)."""

    def flush(self, output_dir: Path | None = None) -> Path:
        """Parquet 書き出し。output_dir 未指定なら .cache/alpha_factory/runs/ ."""

    @staticmethod
    def load(parquet_path: Path) -> pa.Table: ...
```

## テスト方針

- `test_schema_has_all_28_columns`: GENOMES_SCHEMA カラム数・名前
- `test_template_initializes_all_columns`: `_create_row_template()` の戻り値キーが
  schema.names と完全一致
- `test_collect_stage_a_fills_partial`: Stage A 後の row 内容
- `test_collect_stage_b_updates_row`: Stage B で sharpe/total_pnl/trade_count が
  上書きされる
- `test_collect_stage_c_max_drawdown_pct`: drawdown が % で記録される
  (`frac * 100`)
- `test_collect_stage_c_ii_lite_pass_from_stage_result`:
  StageResult.metrics の cross_pair 状態 (skipped / passed=True / passed=False)
  によって ii_lite_pass が None / True / False になる
- `test_mark_graduated_flag`: `graduated = True` セット
- `test_flush_and_load_roundtrip`: 書き出し → load → 同一データ
- `test_same_stage_recollect_overwrites_with_warn`: Stage A → Stage A 重複は
  上書き + WARN
- `test_stage_regression_ignored_with_warn`: Stage B → Stage A 逆流は
  no-op + WARN（B 値が保持される）
- `test_stage_enrich_progresses`: Stage A → B → C の正常順序で各 stage の
  値が累積される
- `test_n_nodes_computed_from_genome`: n_nodes が構造から正しく計算される
- `test_composite_key_generation_individual_name`: 同 individual_name 異
  generation は別 row として保持される

## 受け入れ条件

- [x] GENOMES_SCHEMA 28 カラム定義
- [x] `_create_row_template()` で 28 カラム初期化（テスト確認）
- [x] collect_stage_a/b/c で Stage 別カラム書き込み
- [x] flush → Parquet → load round-trip OK
- [x] mark_graduated で graduated=True
- [x] mypy / ruff クリーン
- [x] 既存テスト（681 + 新規）全 pass
- [x] pyarrow 依存追加 + uv.lock 更新

## SSOT 明示

- **列意味論の SSOT**: 本 conceptual-design.md（implementation 開始時点）
  → 以後は `docs/alpha_factory/concepts/genome-archive-schema.md` に
  本 TODO 完了時点で**反映**して docs を SSOT に昇格する（step G で実施）。
- 詳細設計は本ファイルを参照、**実装は本ファイル + 詳細設計を参照**。
- `active_clause` placeholder = 0 と `fold_sign_ratio` 実値計算は step G で
  schema doc にも明記する。

## リスク・オープン課題

- **`fold_sign_ratio` カラムの厳密な意味**: 現在 Stage B は positive_fold_ratio
  しか持たない。fold_sign_ratio (符号反転比率) は statistics.py の
  `fold_sign_ratio()` を別途呼ぶ必要があるが、本 TODO ではスコープ外。
  → **暫定方針**: positive_fold_ratio の値をそのまま記録、別 TODO で
     `fold_sign_ratio()` 呼び出しに切り替える。
- **`sortino` / `calmar`**: BacktestMetrics に sortino フィールドがあれば
  記入、無ければ None。現実装は Sharpe のみ → 当面 None。
- **`bootstrap_ci_lower/upper`**: 計算は別 TODO（block_bootstrap_sharpe_ci 統合）
- **`sharpe` の上書き順序**: Stage A (raw 60d) → Stage B (IS 18mo) →
  Stage C (holdout) と段階で上書き。これは「最後に成功した最も rich な評価」
  を残す方針。

## 参考資料

- `docs/alpha_factory/concepts/genome-archive-schema.md`
- `src/alpha_factory/stage_gate.py` (StageResult.metrics 構造)
- `src/dsl/serialize.py::genome_to_dict`
- `src/ga/complexity.py::genome_size_norm` (n_nodes 計算参考)
- PyArrow docs: https://arrow.apache.org/docs/python/parquet.html
