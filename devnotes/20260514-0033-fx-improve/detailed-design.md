# 詳細設計: Run 76 施策 (cycle 23)

## 使命・制約

zenigame-fx-codex-review 継承。 FX 固有制約: イントラデイ / ロング・ショート両方向 / スワップ・スプレッド純利益反映。

## 施策一覧

| # | 施策名 | 変更ファイル | target_metric |
|---|--------|------------|--------------|
| C1 | 🚨 live_criteria.sharpe 単位整合性修正 | `scripts/alpha_factory/run_ga.py` / tests | live_criteria.sharpe.pass / mission達成個体数 |
| C2 | graduation KPI 分離 (3 KPI 並列表示) | `scripts/alpha_factory/generate_run_report.py` / tests | KPI 誤読率低減 |
| C3 | 過去 19 RUN retroactive 再評価 script | `scripts/alpha_factory/audit_live_criteria_retroactive.py` (新規) | 過去 RUN の真 mission 候補数 |
| C4 | trade_count 境界張り付き report 化 | `scripts/alpha_factory/generate_run_report.py` | 境界張り付き構造把握 |

---

## C1: 🚨 live_criteria.sharpe 単位整合性修正

### target_metric / failure_mode / causal_path / falsification / success_criterion

- **target_metric**: `summary.live_criteria.checks.sharpe.pass`、 `live_criteria.all_pass`、 mission達成個体数
- **failure_mode**: `_check_live_criteria` で Stage A スコープの trade-level `trade_sharpe_raw` を annualized `sharpe_min=1.0` と直接比較 → 構造的 bug
- **causal_path**: 単位不整合で sharpe pass=False 固定 → all_pass=False → mission 0
- **falsification**: 修正後も best 個体で sharpe 判定が継続 False なら別仮説 (Stage C で真に低い)
- **success_criterion**: Run 76 best 個体で sharpe pass=True、 retroactive 再評価で過去 RUN で mission 候補多数発見

### 変更箇所

#### 1. `scripts/alpha_factory/run_ga.py:916-952` `_check_live_criteria` 改修

**Before** (現状コード):
```python
def _check_live_criteria(
    row: Mapping[str, Any] | None,
    criteria: Mapping[str, float | int],
) -> dict[str, Any]:
    if row is None:
        return {"checks": {}, "all_pass": False}
    checks: dict[str, dict[str, Any]] = {}
    raw_version = row.get("sharpe_calc_version")
    version = "v1_bar_annualized" if raw_version is None else str(raw_version)
    if version not in ("v1_bar_annualized", "v2_trade_level"):
        logger.warning(...)
    sharpe_raw = (
        row.get("trade_sharpe_raw") if version == "v2_trade_level" else None
    )
    sharpe_min = float(criteria.get("sharpe_min", 0.0))
    if sharpe_raw is None:
        checks["sharpe"] = {"value": None, ..., "pass": False, ...}
    else:
        sharpe_val = float(sharpe_raw)
        checks["sharpe"] = {
            "value": str(sharpe_val),
            "threshold": str(sharpe_min),
            "pass": sharpe_val >= sharpe_min,  # ← bug
            "sharpe_calc_version": version,
        }
    ...
```

**After** (修正コード):
```python
from src.alpha_factory.stage_gate import _annualize_trade_sharpe  # 新規 import

def _check_live_criteria(
    row: Mapping[str, Any] | None,
    criteria: Mapping[str, float | int],
    holdout_days: int,  # 新規引数 (Codex Round 1 MODIFY: holdout_days 必須化)
) -> dict[str, Any]:
    """live_criteria 判定。 Stage C 内部判定 (evaluate_stage_c) と整合化。

    sharpe は trade-level → annualized 換算後に sharpe_min と比較する。
    比較値は trade_sharpe_stage_c を第一優先、 無ければ trade_sharpe_raw fallback。
    """
    if row is None:
        return {"checks": {}, "all_pass": False}
    checks: dict[str, dict[str, Any]] = {}

    # Codex Round 1 MODIFY: Stage C scope の trade_sharpe_stage_c を第一優先、
    # fallback は trade_sharpe_raw (Stage A scope、 既存挙動互換)
    raw_version = row.get("sharpe_calc_version")
    version = "v1_bar_annualized" if raw_version is None else str(raw_version)
    if version not in ("v1_bar_annualized", "v2_trade_level"):
        logger.warning(
            "live_criteria.unknown_sharpe_calc_version",
            sharpe_calc_version=version,
        )

    # trade_sharpe_stage_c が存在すれば優先、 無ければ trade_sharpe_raw
    sharpe_trade_level: float | None = None
    sharpe_source: str = "none"
    if version == "v2_trade_level":
        stage_c_sharpe = row.get("trade_sharpe_stage_c")
        if stage_c_sharpe is not None:
            sharpe_trade_level = float(stage_c_sharpe)
            sharpe_source = "trade_sharpe_stage_c"
        else:
            raw_sharpe = row.get("trade_sharpe_raw")
            if raw_sharpe is not None:
                sharpe_trade_level = float(raw_sharpe)
                sharpe_source = "trade_sharpe_raw"  # Stage A scope fallback

    trade_count = int(row.get("trade_count", 0) or 0)
    sharpe_min = float(criteria.get("sharpe_min", 0.0))

    # T042 annualize (= Stage C 内部判定と同じ式)
    sharpe_annualized = _annualize_trade_sharpe(
        sharpe_trade_level, trade_count, holdout_days
    ) if sharpe_trade_level is not None else None

    if sharpe_annualized is None:
        checks["sharpe"] = {
            "value": None,
            "value_trade_level": (
                str(sharpe_trade_level) if sharpe_trade_level is not None else None
            ),
            "threshold": str(sharpe_min),
            "pass": False,
            "sharpe_calc_version": version,
            "sharpe_source": sharpe_source,
            "holdout_days": holdout_days,
        }
    else:
        checks["sharpe"] = {
            "value": str(sharpe_annualized),  # annualized が SSOT
            "value_trade_level": str(sharpe_trade_level),  # 併記
            "threshold": str(sharpe_min),
            "pass": sharpe_annualized >= sharpe_min,
            "sharpe_calc_version": f"{version}_annualized",  # v2_trade_level_annualized
            "sharpe_source": sharpe_source,
            "holdout_days": holdout_days,
        }

    # 他 (total_pnl / max_drawdown / trade_count) は不変
    ...
```

#### 2. `_check_live_criteria` の caller (line 1015 付近) 更新

**Before**:
```python
live_check = _check_live_criteria(best_row, cfg.live_criteria)
```

**After**:
```python
live_check = _check_live_criteria(
    best_row,
    cfg.live_criteria,
    holdout_days=cfg.stage_gate.stage_c_holdout_days,  # 新規引数
)
```

### 波及変更

- `AGENTS.md`: live_criteria.sharpe 比較の単位 (annualized で統一済) 明記
- `docs/alpha_factory/stage-gates.md`: cycle 23 セクション追加 (Stage C 内部判定と summary.json 出力の整合化)
- `docs/alpha_factory/sharpe-rescale.md`: live_criteria 判定でも annualize が適用される旨を補記

### テスト計画

新規 (`tests/scripts/test_alpha_factory_run_ga.py` or 新規 `test_check_live_criteria.py`):

- `test_check_live_criteria_sharpe_uses_annualized`: trade-level 0.18 + trade_count=51 + holdout_days=60 → annualized 約 2.69 → sharpe_min=1.0 で pass=True
- `test_check_live_criteria_sharpe_trade_level_below_annualized_threshold`: trade-level 0.05 + trade_count=51 + holdout_days=60 → annualized 約 0.73 → pass=False
- `test_check_live_criteria_prefers_trade_sharpe_stage_c`: row に `trade_sharpe_stage_c=0.20` と `trade_sharpe_raw=0.10` 両方あれば `stage_c` 採用
- `test_check_live_criteria_fallback_to_trade_sharpe_raw`: `trade_sharpe_stage_c=None` で `trade_sharpe_raw=0.18` あれば raw 採用、 `sharpe_source="trade_sharpe_raw"`
- `test_check_live_criteria_none_when_both_absent`: 両方 None → pass=False、 value=None
- `test_check_live_criteria_value_trade_level_co_recorded`: value (annualized) と value_trade_level (= raw) が併記される
- `test_check_live_criteria_v1_bar_annualized_skipped`: version="v1_bar_annualized" で sharpe_trade_level=None → pass=False
- `test_check_live_criteria_holdout_days_propagated`: holdout_days パラメータが annualize に渡される (= 60 → λ_day=trade_count/60)

### リスク

1. 過去 archive で `trade_sharpe_stage_c` が None の行がある可能性 → fallback で `trade_sharpe_raw` を使う設計で吸収
2. `_annualize_trade_sharpe` の import 経路 (scripts → src) は既存パターンと整合か確認 (run_ga.py 内で既に src.alpha_factory.* を import している)
3. 既存テストで `_check_live_criteria(row, criteria)` の signature が変わるため 2 引数呼び出しが全箇所 fail。 caller も同時更新必要

---

## C2: graduation KPI 分離 (3 KPI 並列表示)

### 変更箇所

`scripts/alpha_factory/generate_run_report.py` の `## 使命判定` セクション (line 534 付近):

**Before**:
```python
# graduation_count = summary['graduation_count']
# (グラデーション数のみ表示)
```

**After**:
```python
# 3 KPI 分離表示:
# - graduation_count: 仕様通り (Stage C pass AND cross_pair pass)
# - stage_c_pass_count: archive で stage_c_pass=True の個体数
# - mission_candidate_count: archive で live_criteria.all_pass 個体数 (C1 修正後の値)

stage_c_pass_count = sum(1 for r in archive_rows if r.get("stage_c_pass"))
mission_candidate_count = sum(
    1 for r in archive_rows
    if r.get("stage_c_pass")
    and _check_live_criteria(r, cfg.live_criteria, holdout_days=cfg.stage_gate.stage_c_holdout_days).get("all_pass")
)
```

レポート出力に以下を追加:
```
## 使命判定

- graduation_count: {N} (仕様: Stage C pass AND cross_pair pass。 single-instrument では構造的 0)
- stage_c_pass_count: {M} (= Stage C 単独通過)
- mission_candidate_count: {K} (= live_criteria.all_pass 個体数、 C1 単位修正後の真値)

### Best 個体 live_criteria:
- (既存 4 軸表示)
```

### テスト

新規 `tests/scripts/test_generate_run_report_kpi.py`:
- `test_report_includes_3_kpis`: graduation_count / stage_c_pass_count / mission_candidate_count の 3 行が報告に含まれる
- `test_mission_candidate_count_matches_archive`: archive 個体で live_criteria.all_pass の数と mission_candidate_count が一致

---

## C3: 過去 19 RUN retroactive 再評価 script

### 新規 `scripts/alpha_factory/audit_live_criteria_retroactive.py`

```python
"""過去 19 RUN (Run 57-75) の archive Parquet を再評価し、
live_criteria.sharpe を annualized で再判定して mission 達成個体数を集計。

cycle 23 C1 修正 (= _check_live_criteria annualize 化) の retroactive 検証用。
"""

import argparse
import json
from pathlib import Path
import pyarrow.parquet as pq

from src.alpha_factory.config import load_config
from src.alpha_factory.stage_gate import _annualize_trade_sharpe
from scripts.alpha_factory.run_ga import _check_live_criteria

def audit_run(run_id: str, criteria, holdout_days: int) -> dict:
    parquet_path = Path(".cache/alpha_factory/runs") / f"genomes_{run_id}.parquet"
    if not parquet_path.exists():
        return {"run_id": run_id, "error": "archive not found"}
    df = pq.read_table(parquet_path).to_pandas()
    sc_pass = df[df["stage_c_pass"].fillna(False).astype(bool)]
    mission_candidates = 0
    sharpe_examples = []
    for _, row in sc_pass.iterrows():
        check = _check_live_criteria(row.to_dict(), criteria, holdout_days=holdout_days)
        if check.get("all_pass"):
            mission_candidates += 1
            sharpe_examples.append({
                "name": row.get("individual_name"),
                "annualized_sharpe": check["checks"]["sharpe"]["value"],
                "trade_count": int(row.get("trade_count", 0)),
                "total_pnl": float(row.get("total_pnl", 0)),
            })
    return {
        "run_id": run_id,
        "stage_c_pass": len(sc_pass),
        "mission_candidates": mission_candidates,
        "top_examples": sorted(sharpe_examples, key=lambda x: -float(x["annualized_sharpe"]))[:5],
    }

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--run-ids", nargs="+", required=True)
    p.add_argument("--output", type=Path, default=Path("reports/audit-live-criteria-retroactive.md"))
    args = p.parse_args()

    cfg = load_config(Path("config/alpha_factory/default.yaml"))
    holdout_days = cfg.stage_gate.stage_c_holdout_days

    results = []
    for run_id in args.run_ids:
        r = audit_run(run_id, cfg.live_criteria, holdout_days)
        results.append(r)
        print(f"{run_id}: mission_candidates={r.get('mission_candidates', 'N/A')} / stage_c={r.get('stage_c_pass', 'N/A')}")

    # markdown 出力
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w") as f:
        f.write("# Live Criteria Retroactive Audit (cycle 23 C1 修正後)\n\n")
        f.write("| run_id | stage_c_pass | mission_candidates | top annualized sharpe |\n")
        f.write("|--------|-------------:|-------------------:|-----------------------|\n")
        for r in results:
            if "error" in r:
                f.write(f"| {r['run_id']} | (error: {r['error']}) | - | - |\n")
            else:
                top = r["top_examples"][0]["annualized_sharpe"] if r["top_examples"] else "-"
                f.write(f"| {r['run_id']} | {r['stage_c_pass']} | {r['mission_candidates']} | {top} |\n")
        f.write("\n## Top examples (annualized sharpe desc, top 5 per run)\n\n")
        for r in results:
            if "top_examples" in r and r["top_examples"]:
                f.write(f"\n### {r['run_id']}\n")
                for ex in r["top_examples"]:
                    f.write(f"- {ex['name']}: annualized_sharpe={ex['annualized_sharpe']}, trade_count={ex['trade_count']}, total_pnl={ex['total_pnl']}\n")

if __name__ == "__main__":
    main()
```

### 実行

```bash
uv run python scripts/alpha_factory/audit_live_criteria_retroactive.py \
  --run-ids run_20260507_011702 run_20260507_220812 ... run_20260513_120619 \
  --output reports/audit-live-criteria-retroactive.md
```

### テスト

- `tests/scripts/test_audit_live_criteria_retroactive.py`:
  - `test_audit_run_with_synthetic_archive`: 合成 archive で mission_candidates 数が期待値と一致
  - `test_audit_run_missing_archive_handles_gracefully`: archive 不在で `error` 記録

---

## C4: trade_count 境界張り付き report 化

### 変更箇所

`scripts/alpha_factory/generate_run_report.py` に新規セクション追加:

```markdown
## trade_count 境界張り付き分析

Stage C 通過群の trade_count 分布:

| trade_count | count | pct |
|-------------|-------|-----|
| 50 (= min) | N | N% |
| 51 | M | M% |
| 52+ | L | L% |

`trade_count == live_criteria.trade_count_min` (境界張り付き) 群の特徴:

- count: K (Stage C 通過群中の比率: K/M%)
- median total_pnl: X
- median annualized sharpe: Y
- median trade_sharpe_stage_c: Z
- max_drawdown_pct: W

`trade_count > min` 群との比較:

| 指標 | 境界張り付き (==min) | 非張り付き (>min) | 差 |
|------|---------------------|------------------|-----|
| count | K | L | |
| median total_pnl | X | X' | dX |
| median annualized sharpe | Y | Y' | dY |
```

### テスト

- `test_trade_count_concentration_section_present`: 報告に「trade_count 境界張り付き分析」セクションが含まれる

---

## Run 76 実行パラメータ

| パラメータ | 値 | R75 からの変更 |
|-----------|-----|----------------|
| instrument | EUR_JPY | 不変 |
| population-size | 96 | 不変 |
| generations | 60 | 不変 |
| mutation-rate | 0.5 | 不変 |
| seed | **61** | 60 → 61 (cycle_index+38 規約: cycle 23 → seed 61) |
| max-workers | 2 | 不変 |
| stage-b-gate-kind | **profit_safe_pfr** | profit_safe_pfr 継続 (= Run 75 の再現確認) |

実行コマンド:
```bash
uv run python scripts/alpha_factory/run_ga.py \
  --instrument EUR_JPY \
  --population-size 96 --generations 60 \
  --mutation-rate 0.5 --seed 61 --max-workers 2 \
  --stage-b-gate-kind profit_safe_pfr
```

---

## 全体テスト計画

- C1 関連: 8 件 (新規)
- C2 関連: 2 件 (新規)
- C3 関連: 2 件 (新規)
- C4 関連: 1 件 (新規)
- 既存テスト: `_check_live_criteria` signature 変更で全 caller 更新必要 (= 既存テストの 1 引数追加)

## リスク統合

1. **C1 signature 変更**: 既存 caller (run_ga.py 内 1 箇所 + 既存テスト N 件) を全て更新必要
2. **C3 過去 19 RUN 再評価**: archive 列に `trade_sharpe_stage_c` がない古い RUN (Run 57 以前等) で fallback 経路の挙動を確認
3. **C2 mission_candidate_count 計算**: archive 全行で `_check_live_criteria` を呼ぶため計算負荷が増える (=O(N) where N=5856) — 計算負荷は許容範囲
