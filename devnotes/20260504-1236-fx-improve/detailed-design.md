# 詳細設計: Run 28 施策

**作成日時**: 2026-05-04 12:58 JST、 **更新**: 2026-05-04 13:10 JST (Round 3 APPROVED 反映)
**合議ステータス**: **APPROVED (design-review Round 3)**
**前提**: improvement-plan.md (consensus Round 2 APPROVED)
**北極星**: live_criteria 充足 FX イントラデイ戦略個体を 1 つ見つけ出す

## 使命・制約 (絶対遵守)

- イントラデイ前提 / ロング・ショート両方向 / スワップ・スプレッド net 反映
- 禁止事項 #1-#8 全遵守 (= 監査機構のみ追加、 GA 挙動完全不変)

## 施策一覧

| # | 施策名 | 変更ファイル | target_metric |
|---|---|---|---|
| C1 | Stage A root cause diagnostic 集計 script | 新規 `scripts/alpha_factory/analyze_stage_a_diagnostic.py` + テスト | Run-29 の打ち手を 1 仮説に分類できる状態確立 |

---

## C1: Stage A root cause diagnostic 集計 script

### target_metric / failure_mode / causal_path / falsification / success_criterion

- **target_metric**: (前段) Run-29 の打ち手を 1 仮説に分類できる状態の確立
- **failure_mode**: Stage A pass=0 の root cause が (P1) primitive / (P2) penalty / (P3) 探索 dynamics のどれか不明
- **causal_path**: archive Parquet の集計から仮説を 1 つに絞れる (= 既存 data に十分な情報がある)
- **falsification**: 集計出力で (P1)/(P2)/(P3) のどれにも明確分類できなければ仮説外の原因を疑う
- **success_criterion**:
  1. `reports/run-{N}/diagnostics/stage_a_root_cause.md` 生成
  2. (P1)/(P2)/(P3) のいずれか 1 つに分類できる
  3. Run-27 (既存) + Run-28 (新規) 両方に適用して結果安定性確認

### 実装 spec

#### CLI

```
uv run python scripts/alpha_factory/analyze_stage_a_diagnostic.py \
    --run-id {run_id} \
    [--output-dir reports/run-{N}/diagnostics]
```

オプション:
- `--run-id`: 必須、 例 `run_20260504_032451` (= archive parquet path 自動解決 = `.cache/alpha_factory/runs/genomes_{run_id}.parquet`)
- `--output-dir`: 省略時 `reports/run-{N}/diagnostics/` (= summary.json の run_number から自動決定)、 明示指定時はそのパス使用

#### 入力

- `.cache/alpha_factory/runs/genomes_{run_id}.parquet` (= archive Parquet)
- `reports/run-{N}/summary.json` (= run_number 解決用)
- `config/alpha_factory/default.yaml` (= alpha / threshold 値の表示用)

#### 出力

```
reports/run-{N}/diagnostics/
├── stage_a_root_cause.md    # 人間向けレポート
└── stage_a_root_cause.json  # 機械可読集計
```

#### 出力 markdown 構造

```markdown
# Stage A Root Cause Diagnostic: run_{run_id}

## サマリー
- run_id / run_number / dataset_span
- archive 行数 / Stage A pass 数 / Stage B pass 数 / Stage C pass 数
- best fitness_pen / best 個体名

## 仮説分類判定
- 結論: **(P1) primitive 不足** | **(P2) penalty / config 設計** | **(P3) 探索 dynamics** | **INCONCLUSIVE**
- 判定根拠: (= 下記 metric に基づく自動判定)

## fitness_pen 分解
| 統計量 | trade_sharpe_raw | size_norm | alpha * size_norm penalty | fitness_pen |
|---|---|---|---|---|
| max | ... | ... | ... | ... |
| mean | ... | ... | ... | ... |
| std | ... | ... | ... | ... |

## trade_sharpe_raw 分布 (世代別)
| generation | n | max | mean | median | n_positive (>0) |
|---|---|---|---|---|---|

## trade_count バケット別
| バケット | n | trade_sharpe_raw mean | fitness_pen mean |
|---|---|---|---|

## n_nodes / active_clause 推移 (= 探索 dynamics 監視)
| generation | n_nodes mean | n_nodes std | active_clause mean |
|---|---|---|---|

## Stage A 失敗理由分布
(= reason_codes 集計、 archive にない場合は `(集計不能、 reason_codes が archive に未配線)`)
| reason | count | 比率 |
|---|---|---|

## Penalty 効果可視化 (= raw - penalty = fitness_pen)
- raw > 0 個体数: N
- raw > 0 ∧ fitness_pen > 0 個体数: M
- raw > 0 ∧ fitness_pen <= 0 個体数: K (= penalty で潰された個体)
- 結論: ...

## 分類判定ロジック (= 規則)
1. **(P1)**: trade_sharpe_raw max < 0.005 → primitive 不足が支配的
2. **(P2)**: raw > 0 ∧ fitness_pen <= 0 個体数 K >= 5 → penalty / config 設計が支配的
3. **(P3)**: n_nodes std (gen 0) - n_nodes std (gen N-1) > 0.5 ∧ active_clause unique 数 == 1 → 探索 dynamics が支配的
4. **INCONCLUSIVE**: 上記いずれにも明確該当しない、 or 複数該当
```

#### 出力 JSON 構造

```json
{
  "run_id": "run_20260504_032451",
  "run_number": 27,
  "diagnosis": "P1" | "P2" | "P3" | "INCONCLUSIVE",
  "diagnosis_rationale": ["..."],
  "stage_pass_counts": {"a": 0, "b": 0, "c": 0},
  "fitness_pen_decomposition": {
    "trade_sharpe_raw": {"max": 0.001134, "mean": -0.081, "std": 0.105},
    "size_norm": {"max": ..., "mean": ..., "std": ...},
    "penalty": {"max": ..., "mean": ..., "std": ...},
    "fitness_pen": {"max": -0.007866, "mean": ..., "std": ...}
  },
  "trade_sharpe_by_generation": [
    {"generation": 0, "n": 40, "max": ..., "mean": ..., "median": ..., "n_positive": 0},
    ...
  ],
  "trade_count_buckets": [
    {"bucket": "0", "n": 9, "trade_sharpe_mean": null, "fitness_pen_mean": -1e9},
    {"bucket": "1-49", "n": 8, ...},
    ...
  ],
  "diversity": [
    {"generation": 0, "n_nodes_mean": 3.05, "n_nodes_std": ..., "active_clause_mean": 1.0},
    ...
  ],
  "penalty_effect": {
    "n_raw_positive": M,
    "n_raw_positive_and_penalty_killed": K,
    "n_raw_positive_and_pass": ...
  }
}
```

### 変更箇所

新規ファイル `scripts/alpha_factory/analyze_stage_a_diagnostic.py`:
```python
"""Stage A root cause diagnostic 集計 script (Run-28 施策 C1)。

既存 archive Parquet (`.cache/alpha_factory/runs/genomes_{run_id}.parquet`)
を入力に、 fitness_pen 分解 / trade_sharpe_raw 分布 / penalty 効果 /
n_nodes / active_clause 推移 を集計し、 Stage A pass=0 の root cause を
(P1) primitive / (P2) penalty / (P3) 探索 dynamics / INCONCLUSIVE に分類する。

GA 挙動には一切影響しない post-RUN diagnostic script。
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow.parquet as pq

REPO_ROOT = Path(__file__).resolve().parents[2]
ARCHIVE_DIR = REPO_ROOT / ".cache" / "alpha_factory" / "runs"
RUN_REPORTS_DIR = REPO_ROOT / "reports" / "run-reports"


# ---------------------------------------------------------------------------
# 集計 helper
# ---------------------------------------------------------------------------


def _bucket_label(trade_count: int) -> str:
    if trade_count == 0:
        return "0"
    if trade_count < 50:
        return "1-49"
    if trade_count < 500:
        return "50-499"
    if trade_count < 1500:
        return "500-1499"
    return ">=1500"


def compute_fitness_pen_decomposition(df: pd.DataFrame, alpha: float) -> dict[str, Any]:
    """fitness_pen = trade_sharpe_raw - alpha * size_norm の 4 項分解."""
    # archive には size_norm 列がないため、 fitness_pen = trade_sharpe_raw - alpha * size_norm
    # から逆算する: size_norm = (trade_sharpe_raw - fitness_pen) / alpha
    sub = df[df["fitness_pen"] > -1e6].copy()  # sentinel 除外
    sub["penalty"] = (sub["trade_sharpe_raw"] - sub["fitness_pen"]).fillna(0.0)
    sub["size_norm_inferred"] = sub["penalty"] / alpha
    out = {}
    for col in ["trade_sharpe_raw", "size_norm_inferred", "penalty", "fitness_pen"]:
        s = sub[col].dropna()
        if len(s) > 0:
            out[col] = {"max": float(s.max()), "mean": float(s.mean()), "std": float(s.std())}
        else:
            out[col] = {"max": None, "mean": None, "std": None}
    return out


def compute_trade_sharpe_by_generation(df: pd.DataFrame) -> list[dict[str, Any]]:
    rows = []
    for gen, g in df.groupby("generation"):
        ts = g["trade_sharpe_raw"].dropna()
        rows.append({
            "generation": int(gen),
            "n": int(len(g)),
            "max": float(ts.max()) if len(ts) else None,
            "mean": float(ts.mean()) if len(ts) else None,
            "median": float(ts.median()) if len(ts) else None,
            "n_positive": int((ts > 0).sum()),
        })
    return rows


def compute_trade_count_buckets(df: pd.DataFrame) -> list[dict[str, Any]]:
    df = df.copy()
    df["bucket"] = df["trade_count"].apply(_bucket_label)
    order = ["0", "1-49", "50-499", "500-1499", ">=1500"]
    out = []
    for label in order:
        sub = df[df["bucket"] == label]
        ts = sub["trade_sharpe_raw"].dropna()
        fp = sub[sub["fitness_pen"] > -1e6]["fitness_pen"]
        out.append({
            "bucket": label,
            "n": int(len(sub)),
            "trade_sharpe_mean": float(ts.mean()) if len(ts) else None,
            "fitness_pen_mean": float(fp.mean()) if len(fp) else None,
        })
    return out


def compute_diversity(df: pd.DataFrame) -> list[dict[str, Any]]:
    rows = []
    for gen, g in df.groupby("generation"):
        rows.append({
            "generation": int(gen),
            "n_nodes_mean": float(g["n_nodes"].mean()),
            "n_nodes_std": float(g["n_nodes"].std() if len(g) > 1 else 0.0),
            "active_clause_mean": float(g["active_clause"].mean()),
            "active_clause_unique": int(g["active_clause"].nunique()),
        })
    return rows


def compute_penalty_effect(df: pd.DataFrame) -> dict[str, Any]:
    sub = df[(df["fitness_pen"] > -1e6) & (df["trade_sharpe_raw"].notna())]
    raw_pos = sub[sub["trade_sharpe_raw"] > 0]
    return {
        "n_raw_positive": int(len(raw_pos)),
        "n_raw_positive_and_penalty_killed": int((raw_pos["fitness_pen"] <= 0).sum()),
        "n_raw_positive_and_pass": int((raw_pos["fitness_pen"] > 0).sum()),
    }


def diagnose_root_cause(
    decomposition: dict[str, Any],
    diversity: list[dict[str, Any]],
    penalty_effect: dict[str, Any],
) -> tuple[str, list[str]]:
    """(P1) primitive / (P2) penalty / (P3) 探索 dynamics / INCONCLUSIVE を判定."""
    rationale: list[str] = []
    raw_max = decomposition.get("trade_sharpe_raw", {}).get("max")

    p1_match = raw_max is not None and raw_max < 0.005
    p2_match = penalty_effect["n_raw_positive_and_penalty_killed"] >= 5
    if diversity:
        first_std = diversity[0]["n_nodes_std"]
        last_std = diversity[-1]["n_nodes_std"]
        active_unique = diversity[-1]["active_clause_unique"]
        p3_match = (first_std - last_std) > 0.5 and active_unique == 1
    else:
        p3_match = False

    if p1_match:
        rationale.append(f"trade_sharpe_raw max={raw_max:.4f} < 0.005 = primitive 表現力不足が支配的")
    if p2_match:
        rationale.append(
            f"raw>0 ∧ fitness_pen<=0 個体 = {penalty_effect['n_raw_positive_and_penalty_killed']} >= 5 "
            f"= penalty / config 設計が支配的"
        )
    if p3_match:
        rationale.append(
            f"n_nodes std 崩壊 (gen 0: {first_std:.2f} → gen last: {last_std:.2f}) "
            f"+ active_clause unique=1 = 探索 dynamics が支配的"
        )

    matches = [m for m, ok in [("P1", p1_match), ("P2", p2_match), ("P3", p3_match)] if ok]
    if len(matches) == 1:
        return matches[0], rationale
    if len(matches) > 1:
        return "INCONCLUSIVE", rationale + [f"複数仮説該当: {matches} = 1 つに絞れず"]
    return "INCONCLUSIVE", rationale + ["どの仮説にも明確該当せず"]


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


def main() -> int:
    p = argparse.ArgumentParser(description="Stage A root cause diagnostic")
    p.add_argument("--run-id", required=True, help="例: run_20260504_032451")
    p.add_argument("--output-dir", type=Path, default=None)
    p.add_argument("--alpha", type=float, default=0.03,
                   help="config stage_a.alpha (default 0.03)")
    args = p.parse_args()

    archive_path = ARCHIVE_DIR / f"genomes_{args.run_id}.parquet"
    if not archive_path.exists():
        print(f"[error] archive not found: {archive_path}")
        return 2

    df = pq.read_table(archive_path).to_pandas()

    # run_number 解決
    run_number: int | None = None
    if "run_number" in df.columns and len(df) > 0:
        run_number = int(df["run_number"].iloc[0])

    # output_dir 確定
    if args.output_dir is not None:
        out_dir = args.output_dir
    elif run_number is not None:
        out_dir = RUN_REPORTS_DIR / f"run-{run_number}" / "diagnostics"
    else:
        print("[error] run_number 解決不能、 --output-dir を明示してください")
        return 2
    out_dir.mkdir(parents=True, exist_ok=True)

    # 集計
    decomposition = compute_fitness_pen_decomposition(df, args.alpha)
    by_gen = compute_trade_sharpe_by_generation(df)
    buckets = compute_trade_count_buckets(df)
    diversity = compute_diversity(df)
    penalty_effect = compute_penalty_effect(df)
    diagnosis, rationale = diagnose_root_cause(decomposition, diversity, penalty_effect)

    payload = {
        "run_id": args.run_id,
        "run_number": run_number,
        "diagnosis": diagnosis,
        "diagnosis_rationale": rationale,
        "stage_pass_counts": {
            "a": int((df["stage_a_pass"] == True).sum()),  # noqa: E712
            "b": int((df["stage_b_pass"] == True).sum()),  # noqa: E712
            "c": int((df["stage_c_pass"] == True).sum()),  # noqa: E712
        },
        "fitness_pen_decomposition": decomposition,
        "trade_sharpe_by_generation": by_gen,
        "trade_count_buckets": buckets,
        "diversity": diversity,
        "penalty_effect": penalty_effect,
    }

    (out_dir / "stage_a_root_cause.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    # markdown 出力 (= human readable)
    md = _render_markdown(payload, args.alpha)
    (out_dir / "stage_a_root_cause.md").write_text(md, encoding="utf-8")

    print(f"[done] diagnosis={diagnosis} run={args.run_id}")
    print(f"  -> {out_dir / 'stage_a_root_cause.md'}")
    print(f"  -> {out_dir / 'stage_a_root_cause.json'}")
    return 0


def _render_markdown(payload: dict[str, Any], alpha: float) -> str:
    """payload から markdown レポートを構築 (詳細実装は省略、 人間向け表組み)."""
    # ... (詳細は実装フェーズで render、 spec に記載済み)
    return f"# Stage A Root Cause: {payload['run_id']}\n\n(implementation rendering)"


if __name__ == "__main__":
    raise SystemExit(main())
```

### 波及変更 (= 全て不要)
- AGENTS.md: 不要 (= 単独 script、 運用変更なし)
- .claude/skills/: 不要
- config/: 不要
- docs/: 任意 (= 別 TODO で `docs/alpha_factory/diagnostics.md` に追記検討)

### ルックアヘッドバイアスチェック (= primitive 変更なし、 N/A)
- [ ] 未来バー参照なし → N/A
- [x] 既存 archive parquet を読むだけ = post-RUN diagnostic、 lookahead 不可能

### パフォーマンスチェック (= primitive 変更なし、 N/A)
- [x] pandas / pyarrow の集計のみ、 1 RUN archive (640 行) で 1 秒未満想定

### テスト計画

新規 `tests/scripts/test_analyze_stage_a_diagnostic.py`:
- [x] **再現テスト先行**: Run-27 archive を fixture として読み、 expected diagnosis を比較
- [x] `compute_fitness_pen_decomposition` 単体: alpha=0.03 で逆算が合うか
- [x] `compute_trade_count_buckets` 単体: バケット境界 (0/49/499/1499) 動作
- [x] `diagnose_root_cause`:
  - P1 case: trade_sharpe_raw max=0.001 で P1 判定
  - P2 case: raw>0 ∧ penalty_killed >= 5 で P2 判定
  - P3 case: n_nodes std 崩壊 + active_clause unique=1 で P3 判定
  - INCONCLUSIVE case: 複数該当 / 該当なし
- [x] CLI test: `--run-id` で fixture を指定して exit code 0 + 出力 file 生成

### リスク

- **Risk 1**: archive Parquet schema 変更で集計失敗 → schema_version チェックで guard
- **Risk 2**: size_norm の逆算 (= `(raw - pen) / alpha`) が浮動小数誤差を増幅 → 直接 size_norm 列が archive にないため、 docstring で「逆算による近似」 明記、 `alpha=None` 時は size_norm を「参考値」 扱い (R2-W1)
- **Risk 3**: 分類判定の閾値 (raw < 0.005 / penalty_killed >= max(3, 0.01*N) 等) は heuristic、 Run-29 で再校正の可能性 → SSOT を script 内 const に集約、 docstring で根拠明示
- **Risk 4** (R2-Sg3): run-effective config snapshot (= summary.json の ga_config / stage_gate_config) が不完全 / 不在の場合、 P3 判定が `config_unavailable` で degrade、 confidence は最大 medium。 default.yaml にフォールバックすると過去 Run 診断と当時 config が乖離するため**禁止**

## design-review Round 3 で確定した実装 spec (= APPROVED)

### Round 1-3 反映済み Delta 一覧
- **Delta A**: `load_run_effective_config(run_number)` → `summary.json` から取得、 不能時 warnings 記録 (R2-Cr1 / R2-W1)
- **Delta B**: `diagnose_root_cause(..., run_effective_config)` で P3 を `max_clause<=1` で N/A 化、 `evaluated_hypotheses` 明示 (R1-Cr1 / R2-Cr1 / R2-Sg1)
- **Delta C**: `compute_valid_mask` に `np.isfinite` 追加、 `compute_plateau_length` に `math.isclose(abs_tol=1e-12)` 適用 (R2-W2 / R2-W3)
- **Delta D**: `compute_extra_metrics` で raw_positive_count / fitness_pen_positive_count / sentinel_by_generation / best_generation 追加 (R2-Sg2)
- **Delta E**: JSON schema 確定 (= `evaluated_hypotheses` / `falsification` / `config_source` / `run_effective_config` / `summary_path` / `summary_run_id_matched`)
- **Delta F**: リスク 4 追加 (R2-Sg3)

### Round 3 残 Warning (= 実装時 guard、 設計差し戻しなし)
- **R3-W1**: `summary.run_id == archive_run_id` 検証必須。 不一致なら fail-closed か `config_unavailable` degrade
- **R3-Sg1**: JSON に `run_effective_config: {...}` と `summary_path` を audit trail として出力

### Run-27 分類予測 (= 全 Round 反映、 確定)
- `diagnosis = "P1"` (= primitive 表現力不足が支配的)
- `confidence = "high"`
- `config_source = "run_effective"` (= summary.json から取得済)
- `evaluated_hypotheses = ["P1", "P2"]` (= P3 は max_clause=1 で N/A、 反証ではなく「評価不能」)
- `falsification.P1 = {match: true, actual: 0.001134, condition: "raw_max < 0.005"}`
- `falsification.P2 = {match: false, actual: 1, condition: "penalty_killed >= 7"}`
- `falsification.P3 = {match: false, actual: "non_evaluable", non_evaluable_reason: "run-effective max_clause=1 <= 1"}`

## Run 28 実行パラメータ

| パラメータ | 値 | R-27 からの変更 |
|---|---|---|
| population_size | 40 | **不変** |
| generations | 15 | **不変** |
| max_clause | 1 | **不変** |
| max_depth | 4 | **不変** |
| max_workers | 2 | **不変** |
| stage_a.threshold | 0.0 | **不変** |
| stage_a.alpha | 0.03 | **不変** |
| その他 default.yaml | **完全不変** | — |

= **GA 挙動完全不変**。 Run-28 は (a) Run-27 と同 setting で結果安定性確認 (b) diagnostic script を Run-27 / Run-28 両方に適用して root cause 仮説分類確定。

## 保留事項 (= 詳細設計レベルで残った論点)

| # | 論点 | 検証 |
|---|---|---|
| H1 | size_norm 列が archive parquet に直接含まれるか? なければ逆算精度 | code Read で archive write 経路を確認 (= 詳細設計 R1 で課題化) |
| H2 | Stage A reasons (= reason_codes) は archive に書かれるか? | 同上 |
| H3 | render_markdown の実装詳細 (= 表組み formatting) | 実装フェーズで具体化、 spec で十分 |
