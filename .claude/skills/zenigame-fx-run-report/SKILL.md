---
name: zenigame-fx-run-report
description: zenigame-fx Alpha Factory RUN 結果から reports/run-reports/run-{N}.md レポートを生成する
argument-hint: "<run_number> [--analysis-md path]... [--analysis-dir dir]..."
---

# zenigame-fx Alpha Factory RUN レポート生成

`scripts/alpha_factory/run_ga.py` 完了後、`reports/run-reports/run-{N}/` に出力された `summary.json` / `history.json` と `.cache/alpha_factory/runs/genomes_{run_id}.parquet` を集約し、`reports/run-reports/run-{N}.md` を生成する。

## 引数

| 引数 | 必須 | 説明 |
|------|------|------|
| `run_number` ($1) | Yes | レポート対象 Run の番号（例: 3） |
| `--analysis-md path` | No | 分析 md ファイルパス。複数回指定可 |
| `--analysis-dir dir` | No | ディレクトリ内の `analysis-*.md` を自動収集。複数回指定可 |

**出力**: `reports/run-reports/run-{N}.md`

## 呼び出し契約

```
User / manual invocation → /zenigame-fx-run-report
/zenigame-fx-run-report → scripts/alpha_factory/generate_run_report.py
```

将来 `zenigame-fx-improve-cycle` Phase 5 から呼ばれる経路を想定（現状は run_ga 完了後にユーザー or improve-cycle が直接 generate_run_report.py を呼んでいる）。

---

## 使命・思考原則・禁止事項

`zenigame-fx-codex-review` SKILL.md で定義される使命・禁止事項・C1-C9 discipline を継承。重複記載しない。

**FX 固有の絶対制約**: イントラデイ前提 / ロング・ショート両方向許容 / スワップ・スプレッドを fitness に反映。

---

## 出力レポートのセクション構造

レポートは以下セクションを必ず含む（archive Parquet 不在等で計算スキップになっても**見出しは残す**）:

1. メタ情報（run_id, run_number, generated_at, dataset）
2. 使命判定（live_criteria 各項目 ✅/❌）
3. GA 設定
4. Best 個体（summary.best SSoT、archive 補足あり）
5. Stage 通過数（A / B / C 件数）
6. Lane 別落下分布（lane_id × Stage pass）
7. Pair 別落下分布（instrument × Stage pass）
8. active_clause / n_nodes 分布
9. fold_sign_ratio / dsr 分布
10. Cross-pair shadow 集計（ii_lite_pass の True/False/None 件数）
11. Graduation（archive graduated 件数 + summary.graduation_count）
12. **Archive Top-5 個体一覧**（Best とは別物。`fitness_pen` 単独降順）
13. 収束履歴（per_generation または history.json fallback）
14. 分析（指定された analysis-*.md があれば）

---

## 手順

### Step 0: 前提検証

1. `reports/run-reports/run-{N}/summary.json` 存在確認
2. archive Parquet パス（`summary["archive_parquet"]`）の存在確認（無ければ warning、レポート生成は継続）

### Step 1: スクリプト実行

```bash
uv run python scripts/alpha_factory/generate_run_report.py \
  --run-number {N} \
  [--analysis-md {path}]... \
  [--analysis-dir {dir}]...
```

### Step 2: 出力検証

`reports/run-reports/run-{N}.md` の必須セクション存在確認:

```bash
for section in "## 使命判定" "## Best 個体" "## Stage 通過数" "## Lane 別落下分布" "## Pair 別落下分布" "## active_clause / n_nodes 分布" "## Cross-pair shadow 集計" "## Archive Top-5 個体一覧" "## 収束履歴"; do
  grep -q "^${section}" reports/run-reports/run-{N}.md || echo "MISSING: $section"
done
```

すべて存在することを確認。

### Step 3: 報告

```
## RUN {N} レポート生成完了

- 出力: reports/run-reports/run-{N}.md ({size} bytes)
- 必須セクション: すべて存在
- archive 集計: {OK / archive Parquet なしでスキップ}
- analysis-md 取り込み: {N} 件
```

---

## エラーハンドリング

### summary.json 不在

スクリプトが exit 1。ユーザーに報告して停止。

### archive Parquet 読取失敗

warning ログのみ、レポートは部分生成（archive 依存セクションは「計算スキップ」表示）。

### analysis-md 指定 path 不在

該当ファイルだけ skip、他は通常処理（warning ログ）。

---

## SSoT / 設計上の注意

- **Best 個体のソース**: `summary["best"]` が SSoT。`run_ga.py` の Best 選定は `(stage_c_pass, stage_b_pass, stage_a_pass, fitness_pen)` の辞書式最大なので、archive の `fitness_pen` 単独 max とは異なる結果になり得る（**設計通り**、WARN は出さない）
- archive Top-5 セクションは「archive 視点での観察」、Best とは別物（混同注意）
- 旧 RUN（拡張キー欠落）でも部分生成で動く（Defensive）

---

## 使用例

### 例 1: マニュアル生成
```
/zenigame-fx-run-report 3
```

### 例 2: 分析 md を統合
```
/zenigame-fx-run-report 3 --analysis-md devnotes/20260424-1000-analyze/analysis-claude.md
```

### 例 3: 分析 dir を自動収集
```
/zenigame-fx-run-report 3 --analysis-dir devnotes/20260424-1000-analyze/
```

### 例 4: 複数 analysis 統合
```
/zenigame-fx-run-report 3 \
  --analysis-md path/A.md \
  --analysis-md path/B.md \
  --analysis-dir devnotes/20260424-1000-analyze/
```

重複 path は `Path.resolve()` で正規化後 dedup される。
