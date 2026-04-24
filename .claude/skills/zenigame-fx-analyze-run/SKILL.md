---
name: zenigame-fx-analyze-run
description: zenigame-fx Alpha Factory RUN 結果の深層分析（自己分析 + Codex 独立分析）。archive Parquet / run-reports を読み、改善点を洗い出す
argument-hint: "<run_id> [--tmp_dir path]"
---

# zenigame-fx Alpha Factory RUN 分析

`scripts/alpha_factory/run_ga.py` 完了後に生成される archive Parquet / reports を深層分析し、次サイクルの改善設計に繋げる。Claude 自己分析 + Codex 独立分析の 2 観点。

## 引数

| 引数 | 必須 | 説明 |
|------|------|------|
| `run_id` ($1) | Yes | 分析対象の run_id（例: `run_20260424_093015`）。`.cache/alpha_factory/runs/genomes_{run_id}.parquet` が存在する必要がある |
| `--tmp_dir` | No | 中間成果物保存先。省略時 `devnotes/{YYYYMMDD-HHMM}-analyze-run-{run_id_short}/` 自動生成 |

**出力**:
- `{tmp_dir}/analysis-claude.md` — Claude 自己分析
- `{tmp_dir}/analysis-codex.md` — Codex 独立分析

## 呼び出し契約

### 現契約
```
User / manual invocation → /zenigame-fx-analyze-run
/zenigame-fx-analyze-run → /zenigame-fx-codex-review  (Codex 独立分析)
                         → /zenigame-fx-codex-vscode  (codex 呼び出し規約)
                         → /zenigame-fx-post-run-review        (改善案 hook の標準起動点は improve-cycle Phase 1 末尾。analyze-run スタンドアロン実行時は起動しない)
                         × /zenigame-fx-analyze-genome-archive (未移植、shallow read のみ委譲予定)
```

### 将来契約（別 follow-up TODO で切替）
```
/zenigame-fx-improve-cycle → /zenigame-fx-analyze-run
```

**重要**: 現状 `zenigame-fx-improve-cycle` は `scripts/alpha_factory/analyze_run.py` を直接呼ぶ。skill 経由切替は本 TODO 範囲外。

---

## 使命・思考原則・禁止事項

`zenigame-fx-codex-review` SKILL.md で定義される使命・禁止事項・C1-C9 discipline を継承。重複記載しない。

**FX 固有の絶対制約（再掲、逸脱検知対象）**:
- イントラデイ前提（オーバーナイト保有を前提にする設計は避ける）
- ロング・ショート両方向許容（FX の性質上）
- スワップ・スプレッドを fitness に反映（見かけの PnL ではなく純利益）

---

## Step 0: 前提検証（C4 — 未検証前提の明示）

本 skill が機能する前提が崩れている場合、分析を**継続せず**に first finding として報告する。

### Verify 必須

1. `.cache/alpha_factory/runs/genomes_{run_id}.parquet` が存在
2. `reports/run-reports/run-{run_number}/summary.json` が存在
3. `scripts/alpha_factory/analyze_run.py` が動作可能
4. `scripts/codex` が疎通（Codex 独立分析が走るか）
5. `docs/alpha_factory/primitives.md` / `stage-gates.md` / `clause-architecture.md` が最新

前提差分があれば `{tmp_dir}/analysis-claude.md` の冒頭に「## 前提差分 (行動停止)」として記録し、後続 Step をスキップ。

---

## Step 1: tmp_dir 作成と archive shallow read

### 1-1. tmp_dir 作成

```bash
TZ=Asia/Tokyo date '+%Y%m%d-%H%M'
```
で `devnotes/{YYYYMMDD-HHMM}-analyze-run-{run_id_short}/` を作成。
`run_id_short` は `run_id` から `run_` prefix を除いた部分の先頭 12 文字。

### 1-2. archive Parquet の shallow read（軽量集計のみ）

```python
import pyarrow.parquet as pq
t = pq.read_table(f".cache/alpha_factory/runs/genomes_{run_id}.parquet")
# 以下の軽量集計のみ許可:
# - 件数（行数、Stage 別 pass 数）
# - best fitness（fitness_pen 最大行）
# - Stage pass 率、instrument 別、lane 別
# - active_clause / n_nodes 分布（基本統計量）
# - fold_sign_ratio / dsr の分布
# - ii_lite_pass の分布（shadow 集計）
# - graduated 件数
```

**禁止**: `genome_json` の再評価・primitive 実行等の深い分析は本 skill スコープ外（`zenigame-fx-analyze-genome-archive` 整備後に委譲）。

### 1-3. summary.json / history.json / best_genome.json を Read

`reports/run-reports/run-{N}/summary.json` から以下を取得:
- run_id / run_number / dataset / per_generation / best / archive_parquet / graduation_count / cross_pair_runtime_mode

---

## Step 2: Claude 自己分析（`analysis-claude.md`）

### 2-1. 観察事実（Facts）

以下のセクションで**数値を手で集計して並べる**（解釈を混ぜない）:

- **Stage 通過数**: A / B / C それぞれの件数、前 Run との差分（前 Run archive あれば）
- **Best fitness**: fitness_pen / fitness_raw、対応 genome name、lane_id、generation
- **Lane 別落下分布**: Tier1_{pair} ごと・Graduation ごとに Stage A→B→C でどこまで生き残ったか
- **Pair 別偏在**: instrument × Stage pass 数、どのペアで止まりやすいか
- **active_clause / n_nodes**: 分布（Stage A 通過群と全体の比較）
- **保有時間分布**: trade-level の avg holding duration（archive から取れる範囲）
- **セッション跨ぎ比率**: （archive に直接は入っていないので summary.json から推定、不可なら「not measured」と明記）
- **ロング/ショート偏重**: trade 方向比率（取れる場合のみ）
- **fold_sign_ratio / dsr / ii_lite_pass**: Stage B/C 通過群の分布

**C6 Fact/Interpretation 分離**: 本セクションは**事実のみ**。解釈は次のセクション。

### 2-2. 解釈（Interpretations）

Step 2-1 の事実を根拠に、以下の仮説を立てる:

- **禁止事項違反の兆候**（C4 検知観点）:
  - イントラデイ逸脱（保有時間が極端に長い）
  - 取引回数削減で見かけ改善（fitness_raw が trade_count 低下で高い）
  - live_criteria 緩和の気配（specific metric が不自然に閾値近辺）
- **Stage gate のボトルネック**: どの Stage で集団が壊滅しているか、その原因仮説
- **primitive 偏在**: 特定 primitive（F3 DonchianBreak 等）が active_clause の大半を占めていないか
- **cross-pair shadow pass 率**: 極端に高い/低い → anchor 定義の妥当性確認が必要

各仮説に**反証可能性**を付記（「この仮説が false なら何が観察されるはず」）。

### 2-3. 次サイクルへの提案

現段階で確認可能な改善方向を 3-5 個列挙。禁止事項・live_criteria に整合する範囲のみ。大規模変更は Warning 扱いで保留、小規模 tuning は明記。

### 2-4. 出力

`{tmp_dir}/analysis-claude.md` に以下の構造で保存:

```markdown
# RUN {run_id} 分析（Claude 自己分析）

## 前提差分
（なし / 内容）

## 観察事実（Facts）
...

## 解釈・推論（Interpretations）
...

## 次サイクル候補
...
```

---

## Step 3: Codex 独立分析（`analysis-codex.md`）

### 3-1. プロンプト準備

`{tmp_dir}/.codex-prompt-analysis.md` を作成。`zenigame-fx-codex-review` の規定に従い使命・禁止事項・C1-C9 は自動挿入される前提（重複記載しない）。

**system 部**:
```
あなたは Alpha Factory の分析レビュアーです。提示された RUN の archive 集計 / reports 要約を読み、以下の観点で C9 falsification-first 分析を行ってください:

1. Stage gate のボトルネックの仮説と反証可能性
2. 禁止事項違反の兆候（イントラデイ逸脱 / 取引回数削減 / live_criteria 緩和）
3. primitive 偏在と多様性
4. cross-pair shadow 統計の妥当性
5. 次サイクル候補（Critical 1 個 / Warning 2-3 個）

出力形式:
- 観察事実（Facts）
- 解釈・推論（Interpretations、C6 分離遵守）
- 次サイクル候補
- 全体判定: OK / CONCERN / CRITICAL_DRIFT
```

**user 部**: Step 1-3, Step 2-1 で集めた事実集計 + summary.json / per_generation 抜粋。

### 3-2. Codex 呼び出し

```bash
scripts/codex exec --ephemeral --sandbox read-only -m gpt-5.3-codex \
  -c 'model_reasoning_effort="medium"' \
  -o {tmp_dir}/analysis-codex.md \
  - < {tmp_dir}/.codex-prompt-analysis.md
```

### 3-3. Codex エラー時

`scripts/codex` が非ゼロ終了の場合、30 秒待って 1 回リトライ。2 回失敗で Codex なしで続行し `analysis-codex.md` に「Codex 失敗」記録。

---

## Step 4: 最終報告

```
## RUN {run_id} 分析完了

### 成果物
- {tmp_dir}/analysis-claude.md
- {tmp_dir}/analysis-codex.md

### サマリー
- Stage A/B/C 通過: {A} / {B} / {C}
- Best fitness_pen: {value}（{genome_name} @ {lane_id} gen {N}）
- 次サイクル候補:
  - [Critical] {改善案}
  - [Warning] {改善案}
  - [Warning] {改善案}
- 全体判定: {OK / CONCERN / CRITICAL_DRIFT}

### 未接続 hook（整備後に起動）
- zenigame-fx-post-run-review: 接続済 (improve-cycle Phase 1 末尾の launcher で起動。analyze-run スタンドアロンでは起動しない)
- zenigame-fx-analyze-genome-archive: 未移植（shallow read のみ委譲予定）
```

---

## エラーハンドリング

### archive Parquet 不在
前提差分として first finding に記録、Step 2/3 を skip。

### summary.json 不在
同上。

### Codex API エラー
30 秒 × 1 リトライ、ダメなら Codex 抜きで続行。

---

## 注意事項

- 本 skill は **Markdown 編集のみ**で動くように設計された run report analyzer。archive の**深い分析は `zenigame-fx-analyze-genome-archive`（未移植）に委譲**する予定
- `zenigame-fx-post-run-review` の起動 owner は **improve-cycle Phase 1 末尾のみ** (T026 接続済)。analyze-run スタンドアロン実行時に hook を発火させない (二重起動防止のため)。手動起動は `docs/alpha_factory/runbook.md` の Post-Run Review 節を参照
- 既存 `zenigame-analyze-run`（zenigame 側）は参照保持、**zenigame-fx 系からは参照しない**（reference-only）
- artifact 名は `analysis-claude.md` / `analysis-codex.md` に SSoT 統一

## 使用例

### 例 1: マニュアル分析
```
/zenigame-fx-analyze-run run_20260424_093015
```

### 例 2: tmp_dir 明示
```
/zenigame-fx-analyze-run run_20260424_093015 --tmp_dir devnotes/20260424-1000-custom-analysis
```
