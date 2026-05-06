# 詳細設計: Run 36 施策 (cycle 3) — 最終版

## 合議ステータス: APPROVED (Round 2)

Codex Round 1 で REQUEST_CHANGES (Critical 1 + Warning 4)、 全採用して Round 2 で APPROVED + 1 Warning (read_table を fail-open 内側に移動)。 計 6 修正項目すべて反映済。

## 使命・制約（絶対遵守、 codex-review 継承）

**FX 固有絶対制約**: イントラデイ前提 / ロング・ショート両方向許容 / スワップ・スプレッドを fitness に反映。

## 施策一覧

| # | 施策名 | 変更ファイル | target_metric |
|---|--------|------------|--------------|
| C1 | Stage A 上位群 fold robustness sidecar parquet 追加 | `src/alpha_factory/diagnostics_stage_a_top_fold.py` (新規) + `scripts/alpha_factory/run_ga.py` (import + hook 追加) + `tests/alpha_factory/test_diagnostics_stage_a_top_fold.py` (新規) | Stage A 上位群の世代別 fold robustness 可観測性 |
| C2 | archive Top-1 trade<50 stage_a_pass 経路 調査ノート | `devnotes/20260506-1345-fx-improve-c3/investigation-stage-a-pass-trade-min.md` (新規、 実コード非変更) | live_criteria 整合性 |

---

## C1: Stage A 上位群 fold robustness sidecar parquet 追加

### target_metric / failure_mode / causal_path / falsification / success_criterion

- **target_metric**: Stage A 上位群の世代別 fold robustness 可観測性（cycle 4 で相関検証可能か）
- **failure_mode**: top20% 集計だけだと分母・選抜基準不明で誤読、 NaN 混入時に解釈不能
- **causal_path**: 観測設計の曖昧さが「目的関数不整合」仮説の反証可能性を下げる
- **falsification**: cycle 4 で「generation ごとの Stage A 順位優位群ほど fold_sign が上がる/上がらない」を統計的に判定できれば仮説検証成立
- **success_criterion**: 各 generation で top 群と母集団の比較ができ、 再計算不要で analyze-run から直接判定可能

### 設計概要

archive Parquet (`.cache/alpha_factory/runs/genomes_{run_id}.parquet`) を入力に、 GA 完了後に sidecar Parquet を `reports/run-reports/run-{N}/diagnostics/stage_a_top_fold_robustness.parquet` へ書き出す。 既存 `diagnostics_sidecar.py` (T033 stage_a_provenance) と同じパターンで fail-open 動作 (書き込みエラー時は warning ログのみ)。

archive に `median_oos_sharpe` 列が**無い**ため、 当初想定の median_oos_sharpe 代わりに **`positive_fold_ratio_effective`** (= positive fold 数 / 有効 fold 数、 Stage B 閾値 0.6 と直接比較可能) を採用。 これは archive に既存。

### sidecar Parquet スキーマ (20 列)

| # | column | dtype | nullable | 説明 |
|---|--------|-------|----------|------|
| 1 | `diagnostics_schema_version` | int32 | False | =1 |
| 2 | `dataset_epoch_id` | string | False | 同定用 |
| 3 | `run_id` | string | False | 同定用 |
| 4 | `generation` | int32 | False | 集計対象世代 |
| 5 | `top_selector` | string | False | 固定 "fitness_pen" |
| 6 | `top_pct` | float64 | False | 0.20 |
| 7 | `population_n` | int32 | False | その世代の Stage A pass 数 |
| 8 | `top_n` | int32 | False | `math.ceil(population_n * 0.20)`、 最低 1 |
| 9 | `n_selected` | int32 | False | 実際 selection された件数 (= top_n、 名称明確化) |
| 10 | `fold_sign_n_valid` | int32 | False | fold_sign_ratio が NaN でない件数 (分母監査) |
| 11 | `pfre_n_valid` | int32 | False | positive_fold_ratio_effective が NaN でない件数 (分母監査) |
| 12 | `fold_sign_mean` | float64 | True | NaN 除外 mean |
| 13 | `fold_sign_median` | float64 | True | NaN 除外 median |
| 14 | `fold_sign_nonzero_ratio` | float64 | True | fold_sign_ratio > 0.0 比率。 列名は「非ゼロ＝符号反転あり」の意味 (fold_sign_ratio 自体は 0..1 の符号反転率) |
| 15 | `positive_fold_ratio_effective_mean` | float64 | True | NaN 除外 mean |
| 16 | `positive_fold_ratio_effective_median` | float64 | True | NaN 除外 median |
| 17 | `positive_fold_ratio_effective_nan_ratio` | float64 | True | NaN 比率 (= 1 - pfre_n_valid / n_selected) |
| 18 | `n_fold_effective_mean` | float64 | True | NaN 除外 mean |
| 19 | `fitness_pen_mean` | float64 | True | NaN 除外 mean |
| 20 | `fitness_pen_median` | float64 | True | NaN 除外 median |

### 集計ロジック (要点)

```python
import math

sa_only = archive_df[archive_df["stage_a_pass"].fillna(False).astype(bool)]
for gen, grp in sa_only.groupby("generation", sort=True):
    pop_n = len(grp)
    if pop_n == 0:
        continue
    top_n = max(1, math.ceil(pop_n * TOP_PCT_DEFAULT))
    top = grp.nlargest(top_n, "fitness_pen")
    n_selected = len(top)

    fsr = top["fold_sign_ratio"].dropna() if "fold_sign_ratio" in top.columns else pd.Series(dtype=float)
    fsr_n_valid = len(fsr)
    fsr_mean = float(fsr.mean()) if fsr_n_valid > 0 else None
    fsr_median = float(fsr.median()) if fsr_n_valid > 0 else None
    fsr_nonzero_ratio = float((fsr > 0.0).sum() / fsr_n_valid) if fsr_n_valid > 0 else None

    pfre = top["positive_fold_ratio_effective"] if "positive_fold_ratio_effective" in top.columns else pd.Series(dtype=float)
    pfre_clean = pfre.dropna()
    pfre_n_valid = len(pfre_clean)
    pfre_mean = float(pfre_clean.mean()) if pfre_n_valid > 0 else None
    pfre_median = float(pfre_clean.median()) if pfre_n_valid > 0 else None
    pfre_nan_ratio = float(1.0 - pfre_n_valid / n_selected) if n_selected > 0 else None

    nfe = top["n_fold_effective"].dropna() if "n_fold_effective" in top.columns else pd.Series(dtype=float)
    nfe_mean = float(nfe.mean()) if len(nfe) > 0 else None

    fp = top["fitness_pen"]
    fp_mean = float(fp.mean())
    fp_median = float(fp.median())

    rows.append({...})
```

### 変更箇所

#### 1. 新規ファイル: `src/alpha_factory/diagnostics_stage_a_top_fold.py`

`write_stage_a_top_fold` は **archive_path を受け取って内部で read+build+write を完結** (Round 2 Warning 反映、 fail-open 一貫化):

```python
"""Stage A top-fold robustness diagnostics sidecar (cycle 3, plan-and-design 由来)。

archive Parquet から generation 別 Stage A pass 上位 20% (fitness_pen 基準) の
fold robustness 集計を sidecar Parquet として書き出す。

production GA からは fail-open で呼ばれる (書き込みエラー時は warning ログのみ、 GA は止めない)。

詳細: devnotes/20260506-1345-fx-improve-c3/detailed-design.md § C1
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Final

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import structlog

logger = structlog.get_logger(__name__)

__all__ = [
    "STAGE_A_TOP_FOLD_SCHEMA",
    "STAGE_A_TOP_FOLD_SCHEMA_VERSION",
    "TOP_PCT_DEFAULT",
    "TOP_SELECTOR_DEFAULT",
    "build_top_fold_table",
    "stage_a_top_fold_relative_path",
    "write_stage_a_top_fold",
]

STAGE_A_TOP_FOLD_SCHEMA_VERSION: Final[int] = 1
TOP_PCT_DEFAULT: Final[float] = 0.20
TOP_SELECTOR_DEFAULT: Final[str] = "fitness_pen"

STAGE_A_TOP_FOLD_SCHEMA: Final[pa.Schema] = pa.schema(
    [
        pa.field("diagnostics_schema_version", pa.int32(), nullable=False),
        pa.field("dataset_epoch_id", pa.string(), nullable=False),
        pa.field("run_id", pa.string(), nullable=False),
        pa.field("generation", pa.int32(), nullable=False),
        pa.field("top_selector", pa.string(), nullable=False),
        pa.field("top_pct", pa.float64(), nullable=False),
        pa.field("population_n", pa.int32(), nullable=False),
        pa.field("top_n", pa.int32(), nullable=False),
        pa.field("n_selected", pa.int32(), nullable=False),
        pa.field("fold_sign_n_valid", pa.int32(), nullable=False),
        pa.field("pfre_n_valid", pa.int32(), nullable=False),
        pa.field("fold_sign_mean", pa.float64(), nullable=True),
        pa.field("fold_sign_median", pa.float64(), nullable=True),
        pa.field("fold_sign_nonzero_ratio", pa.float64(), nullable=True),
        pa.field("positive_fold_ratio_effective_mean", pa.float64(), nullable=True),
        pa.field("positive_fold_ratio_effective_median", pa.float64(), nullable=True),
        pa.field("positive_fold_ratio_effective_nan_ratio", pa.float64(), nullable=True),
        pa.field("n_fold_effective_mean", pa.float64(), nullable=True),
        pa.field("fitness_pen_mean", pa.float64(), nullable=True),
        pa.field("fitness_pen_median", pa.float64(), nullable=True),
    ]
)


def stage_a_top_fold_relative_path(run_number: int) -> Path:
    """sidecar Parquet の相対 path SSOT."""
    return Path(
        f"reports/run-reports/run-{run_number}/diagnostics/"
        "stage_a_top_fold_robustness.parquet"
    )


def build_top_fold_table(
    archive_df: pd.DataFrame,
    run_id: str,
    dataset_epoch_id: str,
) -> pa.Table:
    """archive DataFrame から generation 別 Stage A 上位 20% fold 集計テーブルを構築する。

    Stage A pass=True 個体のみを対象とし、 generation 内で fitness_pen 降順 上位 20% を集計する。
    Stage A pass 0 の世代は row を出力しない。
    """
    rows: list[dict] = []
    if "stage_a_pass" not in archive_df.columns:
        return pa.Table.from_pylist([], schema=STAGE_A_TOP_FOLD_SCHEMA)

    sa_only = archive_df[
        archive_df["stage_a_pass"].fillna(False).astype(bool)
    ]
    if len(sa_only) == 0:
        return pa.Table.from_pylist([], schema=STAGE_A_TOP_FOLD_SCHEMA)

    for gen, grp in sa_only.groupby("generation", sort=True):
        pop_n = len(grp)
        if pop_n == 0:
            continue
        top_n = max(1, math.ceil(pop_n * TOP_PCT_DEFAULT))
        top = grp.nlargest(top_n, "fitness_pen")
        n_selected = len(top)

        fsr = top["fold_sign_ratio"].dropna() if "fold_sign_ratio" in top.columns else pd.Series(dtype=float)
        fsr_n_valid = len(fsr)
        fsr_mean = float(fsr.mean()) if fsr_n_valid > 0 else None
        fsr_median = float(fsr.median()) if fsr_n_valid > 0 else None
        fsr_nonzero_ratio = float((fsr > 0.0).sum() / fsr_n_valid) if fsr_n_valid > 0 else None

        pfre = top["positive_fold_ratio_effective"] if "positive_fold_ratio_effective" in top.columns else pd.Series(dtype=float)
        pfre_clean = pfre.dropna()
        pfre_n_valid = len(pfre_clean)
        pfre_mean = float(pfre_clean.mean()) if pfre_n_valid > 0 else None
        pfre_median = float(pfre_clean.median()) if pfre_n_valid > 0 else None
        pfre_nan_ratio = float(1.0 - pfre_n_valid / n_selected) if n_selected > 0 else None

        nfe = top["n_fold_effective"].dropna() if "n_fold_effective" in top.columns else pd.Series(dtype=float)
        nfe_mean = float(nfe.mean()) if len(nfe) > 0 else None

        fp = top["fitness_pen"]
        fp_mean = float(fp.mean())
        fp_median = float(fp.median())

        rows.append(
            {
                "diagnostics_schema_version": STAGE_A_TOP_FOLD_SCHEMA_VERSION,
                "dataset_epoch_id": dataset_epoch_id,
                "run_id": run_id,
                "generation": int(gen),
                "top_selector": TOP_SELECTOR_DEFAULT,
                "top_pct": TOP_PCT_DEFAULT,
                "population_n": pop_n,
                "top_n": top_n,
                "n_selected": n_selected,
                "fold_sign_n_valid": fsr_n_valid,
                "pfre_n_valid": pfre_n_valid,
                "fold_sign_mean": fsr_mean,
                "fold_sign_median": fsr_median,
                "fold_sign_nonzero_ratio": fsr_nonzero_ratio,
                "positive_fold_ratio_effective_mean": pfre_mean,
                "positive_fold_ratio_effective_median": pfre_median,
                "positive_fold_ratio_effective_nan_ratio": pfre_nan_ratio,
                "n_fold_effective_mean": nfe_mean,
                "fitness_pen_mean": fp_mean,
                "fitness_pen_median": fp_median,
            }
        )

    return pa.Table.from_pylist(rows, schema=STAGE_A_TOP_FOLD_SCHEMA)


def write_stage_a_top_fold(
    archive_path: Path,
    out_path: Path,
    run_id: str,
    dataset_epoch_id: str,
) -> Path | None:
    """archive Parquet を読んで sidecar parquet を書き出す。 fail-open 一貫化。

    Round 2 Warning 反映: read+build+write を 1 関数内に寄せて fail-open を一貫化する。
    archive_path の読込・build・write のいずれの段階で失敗しても warning + None 返却。

    Args:
        archive_path: archive Parquet のパス
        out_path: 書き出し先 (絶対 path 推奨)
        run_id: archive の run_id (sidecar に埋め込む)
        dataset_epoch_id: archive の dataset_epoch_id

    Returns:
        書き出し成功時は out_path、 失敗時は None
    """
    try:
        archive_df = pq.read_table(archive_path).to_pandas()
        table = build_top_fold_table(archive_df, run_id, dataset_epoch_id)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        pq.write_table(table, out_path)
        logger.info(
            "diagnostics.stage_a_top_fold.written",
            path=str(out_path),
            n_generations=table.num_rows,
            run_id=run_id,
        )
        return out_path
    except Exception as exc:
        logger.warning(
            "diagnostics.stage_a_top_fold.write_failed",
            error=str(exc),
            error_type=type(exc).__name__,
            run_id=run_id,
        )
        return None
```

#### 2. `scripts/alpha_factory/run_ga.py` への変更

**imports** (line 46 付近に追加、 既存 import 群と整合):
```python
from src.alpha_factory.diagnostics_stage_a_top_fold import (
    stage_a_top_fold_relative_path,
    write_stage_a_top_fold,
)
```
※ `pq` は不要（write_stage_a_top_fold 内部で使う）

**hook 追加** (line 1733 周辺、 `write_stage_a_provenance` 直後):
```python
    # cycle 3 (improve-cycle): Stage A 上位 20% fold robustness sidecar 追加。
    # archive Parquet を入力に、 generation 別 集計を生成し、
    # reports/run-reports/run-{N}/diagnostics/stage_a_top_fold_robustness.parquet に書き出す。
    # fail-open 一貫化 (read+build+write は write_stage_a_top_fold 内部、 例外は関数内で握り潰す)。
    # 詳細: devnotes/20260506-1345-fx-improve-c3/detailed-design.md § C1
    top_fold_path_written: Path | None = None
    if not args.no_report and archive_path is not None and archive_path.exists():
        top_fold_path_written = write_stage_a_top_fold(
            archive_path,
            REPO_ROOT / stage_a_top_fold_relative_path(run_number),
            run_id=run_id,
            dataset_epoch_id=run_context.dataset_epoch_id,
        )
```

**`_write_reports` への引数追加** (signature line 866 周辺):
```python
def _write_reports(
    *,
    # ... 既存引数 ...
    diagnostics_sidecar_path: Path | None = None,
    top_fold_sidecar_path: Path | None = None,  # 追加
    # ...
):
```

**summary.json 構築箇所** (line 1056 周辺、 既存の `diagnostics_sidecar` ブロック直下):
```python
if top_fold_sidecar_path is not None:
    try:
        summary["diagnostics_stage_a_top_fold"] = str(
            top_fold_sidecar_path.relative_to(REPO_ROOT)
        )
    except ValueError:
        summary["diagnostics_stage_a_top_fold"] = str(top_fold_sidecar_path)
```

**`_write_reports` 呼び出し箇所** (line 1734 周辺):
```python
_write_reports(
    # ... 既存引数 ...
    diagnostics_sidecar_path=sidecar_path_written,
    top_fold_sidecar_path=top_fold_path_written,  # 追加
    # ...
)
```

#### 3. 新規テスト: `tests/alpha_factory/test_diagnostics_stage_a_top_fold.py` (10 件)

**unit 7 件**:
1. `test_build_top_fold_table_empty_returns_empty_table` — 空入力
2. `test_build_top_fold_table_no_stage_a_pass_returns_empty` — Stage A pass 0
3. `test_build_top_fold_table_basic` — 基本集計 (top_n / n_selected / fitness_pen の値検証)
4. `test_build_top_fold_table_multi_generation` — 複数世代
5. `test_build_top_fold_table_nan_handling` — NaN 対応 (fold_sign_n_valid / pfre_nan_ratio)
6. `test_write_stage_a_top_fold_creates_parquet` — Parquet 書き出し成功
7. `test_write_stage_a_top_fold_fail_open_on_error` — read/write 例外時 None 返却

**graceful 1 件**:
8. `test_build_top_fold_table_handles_missing_columns` — archive に positive_fold_ratio_effective / fold_sign_ratio 列不在で None で埋まる

**統合 2 件**:
9. `test_run_ga_writes_stage_a_top_fold_sidecar` — run_ga.py 経由で sidecar 生成 (smoke fixture)
10. `test_run_ga_skips_sidecar_when_no_report` — `--no-report` で sidecar 生成 skip

### 波及変更

| ファイル | 変更 | 理由 |
|---------|------|------|
| `src/alpha_factory/diagnostics_stage_a_top_fold.py` | **新規作成** | 主体実装 |
| `scripts/alpha_factory/run_ga.py` | import + hook + `_write_reports` 引数 1 + summary 1 行 | 完了後の sidecar 書き出し + summary 配線 |
| `tests/alpha_factory/test_diagnostics_stage_a_top_fold.py` | **新規作成** | テスト 10 件 |
| `AGENTS.md` | 不要 | 公開 API / CLI 変更なし、 内部観察データ追加のみ |
| `.claude/skills/zenigame-fx-*/SKILL.md` | 不要 | skill 契約変更なし |
| `config/alpha_factory/default.yaml` | 不要 | 設定不要 (固定値で実装) |
| `docs/alpha_factory/diagnostics-sidecar.md` | 任意 (cycle 4 で stage_a_top_fold 追加文書を書く) | cycle 3 では実装のみ、 ドキュメント追記は次 cycle |

### ルックアヘッドバイアスチェック (primitive 変更時必須)
- [x] 該当しない: 本施策は archive Parquet (post-RUN) からの集計のみで、 primitive 計算経路に触れない

### パフォーマンスチェック (primitive 変更時必須)
- [x] 該当しない: 本施策は per-RUN 1 回の集計 (5,856 行 を pandas で 1 度処理)、 GA 評価ループの hot path には影響なし

### テスト計画

- [x] 既存テスト更新: なし
- [x] 新規テスト 10 件 (unit 7 + graceful 1 + 統合 2、 上記)

### リスク

| リスク | 評価 | 緩和策 |
|---|---|---|
| archive Parquet 読み込みが遅延 | 低 (5,856 行 pandas 1 回 read) | fail-open で skip 可 |
| diagnostics ディレクトリ書き込み権限 | 低 (既存 stage_a_provenance.parquet と同一ディレクトリ) | mkdir parents=True |
| schema mismatch (古い RUN で positive_fold_ratio_effective 列 不在) | 低 (column 不在チェック付き) | None で nullable 列に書く |
| GA hot path 影響 | なし | post-RUN フックのみ |
| silent skip (Codex Round 1 Critical) | **解消** (fail-open 関数内一貫化) | write_stage_a_top_fold 内で全 IO を吸収 |

---

## C2: archive Top-1 trade<50 stage_a_pass 経路 調査ノート

### 調査範囲

- `g26_i95` (run-35 archive top-1 by fitness_pen) の trade_count=44, sharpe=NaN, fold_sign_ratio=0.0、 でも stage_a_pass=True の経路を log + grep で追跡
- `stage_gate.canonical_five.dual_path` ログで stage=A の判定経路を確認
- `src/alpha_factory/stage_gate.py` の `evaluate_stage_a` 系関数で trade_count_min をチェックしているか
- `src/alpha_factory/stage_a_evaluator.py` の通過判定ロジック確認

### Codex 推測 (Round 1 で判明、 cycle 3 調査で詳細化)

> Stage A 判定は `min_exposure` と `fitness_pen threshold` で、 live_criteria.trade_count_min は Stage C で適用 ([stage_gate.py:835](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/stage_gate.py#L835), [stage_gate.py:1492](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/stage_gate.py#L1492))

→ 設計通り (bug ではない) の可能性が高いが、 cycle 3 で `g26_i95` の log を追って verified にする。

### 出力

`devnotes/20260506-1345-fx-improve-c3/investigation-stage-a-pass-trade-min.md` に 1 ページで以下をまとめる:

1. 観察事実 (g26_i95 の log 抜粋、 関連 stage_gate 判定経路)
2. trade_count_min が Stage A 通過判定に組み込まれているか / いないか
3. 設計通り (live_criteria は Stage C 軸で Stage A は GA 内部評価) なのか bug なのか
4. cycle 4 での fix 必要性 (Yes/No/Defer)

### 実コード変更

なし (cycle 3 では調査のみ)

### 波及変更

なし

### テスト計画

なし (調査ノート作成のみ)

### リスク

なし

---

## Run 36 実行パラメータ

| パラメータ | 値 | R35 からの変更 |
|-----------|-----|--------------|
| instrument | EUR_JPY | 不変 |
| population_size | 96 | 不変 |
| generations | 60 | 不変 |
| mutation_rate | 0.5 | 不変 |
| crossover_rate | 0.7 | 不変 |
| tournament_size | 3 | 不変 |
| elite_count | 2 | 不変 |
| max_depth | 4 | 不変 |
| max_clause | 2 | 不変 (cycle 3 では維持、 cycle 4 以降で再評価) |
| seed | 23 | 不変 |
| max_workers | 2 | 不変 |
| Stage A threshold | -0.0172 (history 由来) | 不変 |
| live_criteria | sharpe>=1.0 / pnl>=50000 / dd<=0.2 / [50, 5000] | 不変 |

## 使命・禁止事項チェック (最終)

- ✅ 禁止事項 1 (期間延長): 該当なし、 dataset 不変
- ✅ 禁止事項 2 (見栄え改善): C1 sidecar は観察データのみ、 fitness や Stage 通過には影響しない
- ✅ 禁止事項 3 (GA ハック): 該当なし
- ✅ 禁止事項 4 (閾値緩和): 該当なし
- ✅ 禁止事項 5 (複雑化): C1 = 1 ファイル新規 + import 1 行 + hook 1 ブロック + 1 引数 + summary 1 行 + 10 テスト
- ✅ 禁止事項 6 (取引回数削減): 該当なし
- ✅ 禁止事項 7 (オーバーナイト保有前提): 該当なし
- ✅ FX 固有制約: 該当なし (本 cycle は GA 評価ロジック非変更)
- ✅ メタ過学習ガード: C1 = Structural (sidecar 観察追加)、 C2 = Structural (調査のみ) で全 APPROVE 可
