# T021: skill port — zenigame-fx-run-report 詳細設計

概念設計: `conceptual-design.md`（Round 2 修正反映済み）。

## 成果物

| パス | 役割 | 規模目安 |
|------|------|---------|
| `.claude/skills/zenigame-fx-run-report/SKILL.md` | skill 定義（新規） | 約 150 行 |
| `scripts/alpha_factory/generate_run_report.py` | レポート生成本体（拡張） | 既存 119 行 → 約 500 行 |
| `tests/scripts/test_generate_run_report.py` | テスト（新規） | 約 250 行 |
| `docs/alpha_factory/runbook.md` | 既存に skill 記載追記 | 数行 |

## scripts/alpha_factory/generate_run_report.py 拡張

### モジュール構造

```python
# 既存
def main(argv: list[str] | None = None) -> int: ...

# 新規 helper（module-private）
def _resolve_summary(run_dir: Path) -> dict[str, Any] | None: ...   # summary.json 読み込み
def _resolve_archive(summary: Mapping[str, Any]) -> pa.Table | None: ...  # archive Parquet 読み込み（読取失敗で None + warn）
def _collect_analysis_paths(
    md_paths: list[Path], dirs: list[Path]
) -> list[Path]: ...   # dedup + warn (resolve 化、glob analysis-*.md)

# 新規 section builder（dict / Table → list[str] (markdown lines)）
def _build_header(summary: Mapping[str, Any]) -> list[str]: ...
def _build_live_criteria(summary: Mapping[str, Any]) -> list[str]: ...
def _build_configs(summary: Mapping[str, Any]) -> list[str]: ...
def _build_best(summary: Mapping[str, Any], archive: pa.Table | None) -> list[str]: ...
def _build_stage_pass_counts(archive: pa.Table | None) -> list[str]: ...
def _build_lane_breakdown(archive: pa.Table | None) -> list[str]: ...
def _build_pair_breakdown(archive: pa.Table | None) -> list[str]: ...
def _build_clause_node_distribution(archive: pa.Table | None) -> list[str]: ...
def _build_fold_dsr_distribution(archive: pa.Table | None) -> list[str]: ...
def _build_cross_pair_shadow(archive: pa.Table | None) -> list[str]: ...
def _build_graduated_count(archive: pa.Table | None) -> list[str]: ...
def _build_archive_top_n(archive: pa.Table | None, n: int = 5) -> list[str]: ...
def _build_history(run_dir: Path, summary: Mapping[str, Any]) -> list[str]: ...
def _build_analysis(paths: list[Path]) -> list[str]: ...

# Helper 共通
def _stat_summary(values: Iterable[float | None]) -> dict[str, Any]: ...  # min/median/p90/max/n_null
def _markdown_table(headers: list[str], rows: list[list[str]]) -> list[str]: ...
def _archive_skipped_block(reason: str) -> list[str]: ...   # 「archive Parquet なし、計算スキップ」見出し付きブロック
```

### CLI 仕様

```python
import argparse

p = argparse.ArgumentParser(description="Generate Alpha Factory FX run report")
p.add_argument("--run-number", type=int, required=True)
p.add_argument(
    "--analysis-md",
    type=Path,
    action="append",
    default=None,    # None → [] に正規化
    help="分析 md のパス（複数回指定可）",
)
p.add_argument(
    "--analysis-dir",
    type=Path,
    action="append",
    default=None,
    help="分析 md を含むディレクトリ（複数回指定可、analysis-*.md を自動収集）",
)
p.add_argument(
    "--archive-top-n",
    type=int,
    default=5,
    help="archive Top-N 個体一覧の N（既定 5）",
)
```

`action="append"` のデフォルト None → `[]` に正規化する。

### main() フロー

```python
def main(argv: list[str] | None = None) -> int:
    args = p.parse_args(argv)
    run_dir = RUN_REPORTS_DIR / f"run-{args.run_number}"

    summary = _resolve_summary(run_dir)
    if summary is None:
        print(f"[error] summary not found: {run_dir / 'summary.json'}", file=sys.stderr)
        return 1

    archive = _resolve_archive(summary)  # None なら警告ログ済み

    md_paths = _collect_analysis_paths(
        list(args.analysis_md or []),
        list(args.analysis_dir or []),
    )

    lines: list[str] = []
    lines += _build_header(summary)
    lines += _build_live_criteria(summary)
    lines += _build_configs(summary)
    lines += _build_best(summary, archive)
    lines += _build_stage_pass_counts(archive)
    lines += _build_lane_breakdown(archive)
    lines += _build_pair_breakdown(archive)
    lines += _build_clause_node_distribution(archive)
    lines += _build_fold_dsr_distribution(archive)
    lines += _build_cross_pair_shadow(archive)
    lines += _build_graduated_count(archive)
    lines += _build_archive_top_n(archive, n=args.archive_top_n)
    lines += _build_history(run_dir, summary)
    lines += _build_analysis(md_paths)

    out_path = RUN_REPORTS_DIR / f"run-{args.run_number}.md"
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[done] report written to {out_path}")
    return 0
```

### Section builder 詳細

#### _resolve_archive

```python
def _resolve_archive(summary: Mapping[str, Any]) -> pa.Table | None:
    archive_path_str = summary.get("archive_parquet")
    if not archive_path_str:
        print("[warn] summary['archive_parquet'] missing — archive sections skipped",
              file=sys.stderr)
        return None
    p = REPO_ROOT / archive_path_str if not Path(archive_path_str).is_absolute() else Path(archive_path_str)
    if not p.exists():
        print(f"[warn] archive parquet not found: {p}", file=sys.stderr)
        return None
    try:
        return pq.read_table(p)
    except Exception as e:
        print(f"[warn] archive parquet read failed: {p} ({e})", file=sys.stderr)
        return None
```

注: scope is module-private。`from typing import Any` / `Mapping` は from collections.abc。

#### _collect_analysis_paths

```python
def _collect_analysis_paths(md_paths: list[Path], dirs: list[Path]) -> list[Path]:
    seen: set[Path] = set()
    result: list[Path] = []

    def _add(p: Path) -> None:
        try:
            resolved = p.resolve(strict=True)
        except (FileNotFoundError, OSError) as e:
            print(f"[warn] analysis md not accessible: {p} ({e})", file=sys.stderr)
            return
        if resolved in seen:
            return
        seen.add(resolved)
        result.append(resolved)

    for p in md_paths:
        _add(p)
    for d in dirs:
        if not d.exists() or not d.is_dir():
            print(f"[warn] analysis-dir not found: {d}", file=sys.stderr)
            continue
        for p in sorted(d.glob("analysis-*.md")):
            _add(p)
    return result
```

#### _build_header / _build_live_criteria / _build_configs

`summary` の各キーは `dict.get(key)` で取得し、欠落時は「未記録」表示。

`_build_live_criteria` は既存ロジックをほぼ流用（`live_criteria.checks` を ✅/❌ で並べる）。`live_criteria` 自体が欠落していたら「使命判定: 未記録」見出しのみ。

`_build_configs` は 4 つのテーブル（GA / Backtest / Stage Gate / Cross-pair）。各 dict が欠落していたら「未記録（旧 schema）」と表示。

#### _build_best

```python
def _build_best(summary, archive):
    best = summary.get("best") or {}
    lines = ["", "## Best 個体", ""]
    if not best:
        lines.append("- 未記録")
        return lines
    metrics = best.get("metrics", {})
    lines.extend([
        f"- name: `{best.get('name')}`",
        f"- generation: {best.get('generation')}",
        f"- fitness: **{best.get('fitness')}**",
        f"- selection_score: {best.get('selection_score')}",
        f"- stage_a_pass: {best.get('stage_a_pass')}",
        f"- stage_b_pass: {best.get('stage_b_pass')}",
        f"- stage_c_pass: {best.get('stage_c_pass')}",
        f"- trade_count: {metrics.get('trade_count')}",
        f"- total_pnl: {metrics.get('total_pnl')}",
        f"- sharpe: {metrics.get('sharpe')}",
        f"- sortino: {metrics.get('sortino')}",
        f"- calmar: {metrics.get('calmar')}",
        f"- max_drawdown_pct: {metrics.get('max_drawdown_pct')}",
    ])
    if archive is not None:
        # name + generation で archive 行 lookup（lane_id を超えて全 lane を検索）
        rows = _filter_archive_by_name_gen(archive, best.get("name"), best.get("generation"))
        if not rows:
            lines.append("- archive 補足: 該当行なし（設計通り、WARN なし）")
        else:
            for r in rows:
                lines.append(
                    f"- archive 行（lane={r['lane_id']}, instrument={r['instrument']}）: "
                    f"fold_sign_ratio={r['fold_sign_ratio']}, dsr={r['dsr']}, "
                    f"ii_lite_pass={r['ii_lite_pass']}, n_nodes={r['n_nodes']}, "
                    f"active_clause={r['active_clause']}"
                )
    return lines
```

`_filter_archive_by_name_gen` は `pyarrow.compute.equal` の boolean mask で filter。

#### _build_stage_pass_counts

archive がある場合、`stage_{a,b,c}_pass` 列の True 数 / 総数 / 通過率を表で出す。
ない場合は `_archive_skipped_block("Stage 通過数")`。

#### _build_lane_breakdown / _build_pair_breakdown

archive を `lane_id` / `instrument` で `group_by` し、Stage A/B/C pass 数を集計。
pyarrow の `group_by` は `aggregate([(col, "sum")])` で True を 1 として sum できる（bool 列）。
出力テーブル例:

```markdown
| lane_id | total | A pass | B pass | C pass | C/A 通過率 |
|---------|-------|--------|--------|--------|-----------|
| tier1_EUR_JPY | 100 | 30 | 12 | 5 | 16.7% |
| graduation | 8 | 8 | 6 | 4 | 50.0% |
```

#### _build_clause_node_distribution / _build_fold_dsr_distribution

`_stat_summary(values)` を使って min/median/p90/max/n_null を出す。
fold_sign_ratio / dsr は Stage B 通過群と Stage C 通過群でフィルタしてから集計。

#### _build_cross_pair_shadow

`ii_lite_pass` 列の True / False / None 件数を出す。

#### _build_graduated_count

`graduated == True` 行数。

#### _build_archive_top_n

```python
def _build_archive_top_n(archive, n=5):
    lines = ["", f"## archive Top-{n} 個体一覧（観察用、Best とは別物）", ""]
    if archive is None:
        lines.append("archive Parquet なし、計算スキップ")
        return lines
    # fitness_pen 降順に sort、上位 n 行を取り出す
    sorted_indices = pa.compute.sort_indices(archive, sort_keys=[("fitness_pen", "descending")])
    top = archive.take(sorted_indices[:n]).to_pylist()
    headers = ["rank", "name", "generation", "lane_id", "instrument",
               "fitness_pen", "fitness_raw", "A", "B", "C", "trade_count", "sharpe"]
    rows = []
    for i, r in enumerate(top, start=1):
        rows.append([
            str(i), r["individual_name"], str(r["generation"]),
            r["lane_id"], r["instrument"],
            f"{r['fitness_pen']:.6g}", f"{r['fitness_raw']:.6g}",
            "Y" if r["stage_a_pass"] else "N",
            "Y" if r["stage_b_pass"] else "N",
            "Y" if r["stage_c_pass"] else "N",
            str(r["trade_count"]),
            "" if r["sharpe"] is None else f"{r['sharpe']:.4g}",
        ])
    lines.extend(_markdown_table(headers, rows))
    return lines
```

#### _build_history

既存の `history.json` 読みを流用。`summary["per_generation"]` も併記候補だが、history.json 優先（既存仕様維持）。`history.json` 読取失敗時は `summary["per_generation"]` fallback、それも欠落なら「収束履歴: 未記録」。

#### _build_analysis

```python
def _build_analysis(paths):
    if not paths:
        return []
    lines = ["", "## 分析", ""]
    for p in paths:
        try:
            content = p.read_text(encoding="utf-8").strip()
        except (OSError, UnicodeDecodeError) as e:
            print(f"[warn] analysis md read failed: {p} ({e})", file=sys.stderr)
            continue
        lines.extend(["", f"### {p.name}", "", content, ""])
    return lines
```

### markdown helper

```python
def _markdown_table(headers, rows):
    align = "|".join(["---"] * len(headers))
    out = ["| " + " | ".join(headers) + " |", "|" + align + "|"]
    for r in rows:
        out.append("| " + " | ".join(r) + " |")
    return out
```

### typing 配慮（mypy 通過のため）

- `pa.Table | None` を多用するので、各 builder は最初に `if archive is None: return _archive_skipped_block(...)` の早期リターン
- `summary: Mapping[str, Any]` を引数型にし、内部で `summary.get(...)` のみ
- `pa.compute` import は alias `pc`

## SKILL.md 構成

```markdown
---
name: zenigame-fx-run-report
description: zenigame-fx Alpha Factory RUN 結果から運用レポート（reports/run-reports/run-{N}.md）を生成
argument-hint: "<run_number> [--analysis-md path]... [--analysis-dir dir]..."
---

# zenigame-fx Alpha Factory RUN レポート生成

`scripts/alpha_factory/run_ga.py` 実行後、archive Parquet + summary.json から `reports/run-reports/run-{N}.md` を生成する独立 skill。
RUN 実行・TODO 遷移とは分離（独立利用 YES）。

## 引数

| 引数 | 必須 | 説明 |
|------|------|------|
| `run_number` ($1) | Yes | 対象 RUN の番号（reports/run-reports/run-{N}/summary.json が存在する必要あり） |
| `--analysis-md` | No | 分析 md のパス。複数回指定可 |
| `--analysis-dir` | No | 分析 md を含むディレクトリ。analysis-*.md を自動収集（複数回指定可） |
| `--archive-top-n` | No | archive Top-N の N（既定 5） |

**入力**: `reports/run-reports/run-{N}/{summary.json,history.json}` + `summary["archive_parquet"]` 指す Parquet。
**出力**: `reports/run-reports/run-{N}.md`

## 呼び出し契約

### 現契約
```
User / manual invocation → /zenigame-fx-run-report {N}
zenigame-fx-improve-cycle Phase 4 → scripts/alpha_factory/generate_run_report.py を直接呼ぶ（既存維持）
```

### 将来契約（別 follow-up TODO）
```
zenigame-fx-improve-cycle Phase 4 → /zenigame-fx-run-report {N}
```

## 使命・思考原則・禁止事項

`zenigame-fx-codex-review` SKILL.md の使命・禁止事項・C1-C9 を継承。重複記載しない。

**FX 固有の絶対制約（再掲、レポート出力での逸脱検知観点）**:
- イントラデイ前提
- ロング・ショート両方向許容
- スワップ・スプレッドを fitness に反映

## Step 1: 入力検証

- `reports/run-reports/run-{N}/summary.json` 存在確認、無ければ即終了
- archive Parquet は summary["archive_parquet"] から取得（無ければ警告のみ）
- `--analysis-md` / `--analysis-dir` は dedup（`Path.resolve()` 後）

## Step 2: レポート生成

```bash
uv run python scripts/alpha_factory/generate_run_report.py --run-number {N} [...]
```

## Step 3: 出力検証

`reports/run-reports/run-{N}.md` が生成されたことを確認。
以下の必須見出しが含まれることを grep で検証:

- `## 使命判定`
- `## GA 設定`
- `## Best 個体`
- `## Stage 通過数`
- `## Lane 別落下分布`
- `## Pair 別落下分布`
- `## active_clause / n_nodes 分布`
- `## fold_sign_ratio / dsr 分布`
- `## cross-pair shadow 集計`
- `## graduated 件数`
- `## archive Top-` （Top-N の N が可変なので prefix 一致）
- `## 収束履歴`

archive 不在時は archive 依存セクションが「archive Parquet なし、計算スキップ」と書かれていることも grep 確認。

## Step 4: 報告

最終アウトプット形式:

```
## RUN run-{N} レポート生成完了

### 成果物
- reports/run-reports/run-{N}.md

### サマリー
- 必須見出し: {n}/12 確認
- archive Parquet 利用: {yes/no}
- analysis md 取り込み: {n} 件
```

## 注意事項

- skill は **Markdown 編集のみ**で動くように設計。重い集計は `generate_run_report.py` 側
- `--run-id` は採用しない（`run_number → summary.json → archive_parquet` の SSoT 一本鎖）
- archive Top-N と Best 個体は別物。混同しないこと（Best は `(stage_c_pass, stage_b_pass, stage_a_pass, fitness_pen)` 辞書式最大、Top-N は `fitness_pen` 単独降順）
- 既存 zenigame 側 `zenigame-run-report` は参考保持（reference-only）
```

## tests/scripts/test_generate_run_report.py 設計

### fixture

```python
import json
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

@pytest.fixture
def sample_summary():
    return {
        "run_id": "run_20260424_120000",
        "run_number": 99,
        "generated_at": "2026-04-24T12:00:00+00:00",
        "dataset": {"instrument": "EUR_JPY", "start": "...", "end": "...", "bars": 7000,
                    "bars_stage_a": 7000, "bars_stage_b": 7000, "bars_holdout": 30000},
        "ga_config": {"population_size": 4, "generations": 2, "crossover_rate": 0.7,
                      "mutation_rate": 0.3, "tournament_size": 3, "elite_count": 2,
                      "max_depth": 4, "max_clause": 1, "units": 10000,
                      "fitness_metric": "sharpe", "seed": 42},
        "backtest_config": {"initial_cash": "1000000", "leverage": 25, "units": 10000},
        "stage_gate_config": {"stage_a_window_days": 60, "stage_a_alpha": 0.03,
                              "stage_a_threshold": 0.0, "stage_b_window_months": 18,
                              "stage_c_holdout_days": 60, "spread_stress_multiplier": 1.5},
        "cross_pair_config": {"mode": "shadow", "aggregator_lambda": 0.5},
        "cross_pair_runtime_mode": "skipped_single_instrument",
        "per_generation": [
            {"generation": 0, "n_evaluated": 4, "stage_a_pass": 1, "stage_b_pass": 0,
             "stage_c_pass": 0, "graduation_count": 0, "best_fitness_pen": 1.5,
             "best_fitness_pen_finite": True},
        ],
        "best": {
            "name": "g0_i1", "generation": 0, "fitness": "1.5", "fitness_finite": True,
            "stage_a_pass": True, "stage_b_pass": False, "stage_c_pass": False,
            "selection_score": [0, 0, 1, 1.5],
            "metrics": {"total_pnl": "100.0", "sharpe": "1.5", "sortino": None, "calmar": None,
                        "max_drawdown_pct": "5.0", "trade_count": 50},
        },
        "live_criteria": {
            "checks": {
                "sharpe": {"value": "1.5", "threshold": "1.0", "pass": True},
                "total_pnl": {"value": "100.0", "threshold": "50000.0", "pass": False},
                "max_drawdown_pct": {"value": "5.0", "threshold": "20.0", "pass": True},
                "trade_count": {"value": 50, "threshold_min": 50, "threshold_max": 5000, "pass": True},
            },
            "all_pass": False,
        },
        "population_size": 4,
        "graduation_count": 0,
        "archive_parquet": "<set in fixture below>",
    }


@pytest.fixture
def sample_archive_table():
    """T015 GENOMES_SCHEMA に準拠した最小 archive Table。"""
    from src.alpha_factory.archive import GENOMES_SCHEMA
    rows = [
        {  # Best 個体に該当 (g0_i1, gen 0, tier1_EUR_JPY)
            "run_id": "run_20260424_120000", "run_number": 99,
            "generation": 0, "individual_name": "g0_i1",
            "instrument": "EUR_JPY", "lane_id": "tier1_EUR_JPY",
            "parent_a": None, "parent_b": None, "genome_json": "{}",
            "fitness_raw": 1.6, "fitness_pen": 1.5,
            "stage_a_pass": True, "stage_b_pass": False, "stage_c_pass": False,
            "trade_count": 50, "total_pnl": 100.0, "sharpe": 1.5,
            "sortino": None, "calmar": None, "max_drawdown_pct": 5.0,
            "active_clause": 0, "n_nodes": 4,
            "bootstrap_ci_lower": None, "bootstrap_ci_upper": None,
            "fold_sign_ratio": None, "dsr": None, "ii_lite_pass": None,
            "graduated": False,
        },
        # ... 数行追加（Stage B/C 通過、別 lane 等を含めて branchごとの集計を確認）
    ]
    return pa.Table.from_pylist(rows, schema=GENOMES_SCHEMA)
```

### テスト一覧

| テスト名 | 観点 |
|---------|------|
| `test_generate_report_writes_to_run_dir_md` | 基本生成（出力ファイル存在） |
| `test_generate_report_includes_required_sections` | 必須見出し 12 個の存在確認 |
| `test_generate_report_handles_missing_archive` | summary["archive_parquet"] 欠落時に「計算スキップ」表示 |
| `test_generate_report_handles_archive_read_failure` | 破損 Parquet で warning 出して exit 0、summary ベースで部分生成 |
| `test_generate_report_handles_missing_summary` | summary 不在で exit 1 |
| `test_generate_report_handles_missing_config_keys` | backtest_config / stage_gate_config / cross_pair_config 欠落で「未記録」表示、exit 0 |
| `test_generate_report_handles_missing_live_criteria` | live_criteria 欠落で「使命判定: 未記録」表示、exit 0 |
| `test_generate_report_handles_missing_per_generation` | per_generation 欠落 + history.json 不在で「収束履歴: 未記録」 |
| `test_generate_report_with_single_analysis_md` | 既存呼び出し互換: `--analysis-md path` 単一指定 |
| `test_generate_report_with_multiple_analysis_md` | `--analysis-md a --analysis-md b` 複数指定 |
| `test_generate_report_with_analysis_dir` | `--analysis-dir d` で `analysis-*.md` 自動収集 |
| `test_generate_report_dedup_analysis_paths` | `--analysis-md a` と `--analysis-dir d` 併用で同一ファイルが 1 回だけ取り込まれる |
| `test_generate_report_skips_missing_analysis_md` | `--analysis-md nonexistent.md` で warn + 出力には含まれない、exit 0 |
| `test_generate_report_archive_top_n_section` | `## archive Top-` 見出しと「Best とは別物」明記、N=5 行 |
| `test_generate_report_lane_pair_breakdown` | Lane / Pair 別集計テーブルが存在し件数が正しい |
| `test_generate_report_best_archive_lookup` | summary.best と archive 行が一致する場合の補足表示 |
| `test_generate_report_best_archive_no_match` | summary.best が archive に無い場合の「該当行なし、WARN なし」表示（stderr に WARN なし） |

### モック化方針

- `RUN_REPORTS_DIR` を tmp_path にリダイレクト（monkeypatch）
- archive Parquet は tmp_path 内に書いて summary["archive_parquet"] に絶対パス（または REPO_ROOT 相対）を入れる
- 外部通信なし（pyarrow のみ）

## docs/alpha_factory/runbook.md 追記

既存の `| uv run python scripts/alpha_factory/generate_run_report.py | Run レポート生成 |` 行の下に skill エントリを追記。

```markdown
| `/zenigame-fx-run-report {N}` | skill 経由でレポート生成（必須見出し検証付き） |
```

オプション例（複数 analysis md / analysis-dir）も短く記載。

## 実装順序

1. `_build_*` の純関数群を先に実装（archive None 系含む）
2. `_resolve_*` / `_collect_*` helper
3. `main()` で連結
4. tests を fixture から実装
5. SKILL.md 作成
6. runbook 追記
7. mypy / ruff
8. cycle 21 で生成済の `run_20260423_195917` (run-3) で実機実行確認

## 既存テスト（test_alpha_factory_run_ga.py）への影響

`run_ga.py` の出力契約は変えないので影響なし（要確認）。`test_alpha_factory_run_ga.py` は touch しない。

## 受け入れ基準（再掲）

conceptual-design の受け入れ基準 1-10 を全て満たす。
