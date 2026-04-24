---
name: zenigame-run-report
description: Alpha Factory RUN結果からレポート（reports/run-reports/**/run-N.md）を生成する
argument-hint: "[run_id] [--run_number N]"
---

# Alpha Factory Runレポート作成

RUN完了後のレポートを作成する。improve-cycleのPhase 5として呼び出される独立スキル。

## 引数

| 引数 | 必須 | 説明 |
|------|------|------|
| `run_id` ($1) | No | 対象のrun_id（例: run_20260314_010806）。省略時は最新RUNを自動検出 |
| `run_number` ($2) | No | レポート番号（例: 320）。省略時は既存レポートの最大番号+1を自動採番 |

**入力**: GA実行済みの結果（winners JSON、ゲノムアーカイブ、ログ等）
**出力**: `reports/run-reports/run-{block}/run-{N}.md`（block = `run-NNNN-NNNN`、100単位ブロック）

**独立利用**: YES — RUN実行やTODO遷移なしにレポートだけ生成できる

---

## 判断基準の選択（adaptive vs C-Sharpe）

レポート全体の個体選出・ランキング・主要指標は `adaptive_live_criteria_enabled` の値で切り替わる:

| | adaptive_live_criteria_enabled=**true** | adaptive_live_criteria_enabled=**false** |
|---|---|---|
| Top個体選出 | **adaptive_mission_score** 降順 Top5 | C-Sharpe 降順 Top5 |
| Top10テーブル | **adaptive_mission_score** 降順 Top10 | C-Sharpe 降順 Top10 |
| 冒頭サマリの主指標 | **adaptive_mission_pass数 + adaptive D* score** | C-Sharpe Top1 |
| Mission判定カード | **Adaptive判定が主**、standard判定は参考 | standard判定が主 |
| Top-5 Gap スコアボード | adaptive基準でのgap | standard基準でのgap |
| 結果サマリ Top1 | **adaptive_mission_score Top1** | C-Sharpe Top1 |

C-Sharpeは完全に削除しない。窓別テーブルの1列（worst-window Sharpe）として、またstandard参考値として残す。

**【絶対遵守】adaptive_live_criteria_enabled=true の場合、以下を必ず出力すること。省略は禁止。**
1. 冒頭サマリにadaptive_mission_pass数（**太字**で最初に記載）
2. Adaptive Mission判定カード（Standard判定カードの**前**に配置）
3. Top個体ドシエの窓別テーブルにadaptive_pass/adaptive_criteria_type列
4. Top個体ドシエにAdaptive Mission Score行
5. 結果サマリにadaptive_mission_pass個体数/adaptive D* score行

---

## Step 1. 対象RUNの特定

### run_id が指定されている場合
そのまま使用。

### run_id が未指定の場合
最新のRUN結果を検出:
```bash
# winnersディレクトリから最新のrun_idを取得
ls -t config/alpha_factory/winners/ | head -5
```
winnersファイル名からrun_idを抽出する。

## Step 2. レポート番号の決定

### run_number が指定されている場合
そのまま使用。

### run_number が未指定の場合
既存レポートの最大番号+1。**SSoT = `reports/run-reports/run-metrics-summary.md`** の表行から最大値を取得する（共通ヘルパー経由、パス探索はフォールバック）:
```bash
latest_n=$(uv run python scripts/alpha_factory/get_latest_run_number.py) || exit 1
run_number=$((latest_n + 1))
```

### 書き込み先のブロック決定

Run 番号からブロック名を決定し、ブロックディレクトリを自動作成する:
```bash
N={run_number}
block_start=$((N / 100 * 100))
block_end=$((block_start + 99))
block="run-${block_start}-${block_end}"
mkdir -p "reports/run-reports/${block}"
# レポート書き込み先: reports/run-reports/${block}/run-${N}.md
```

## Step 3. 前回RUNレポートの読み込み

前回レポート（ブロック配下に存在）を `find` で解決して読み、比較用データを把握する。
`--require-file` オプションで summary と実ファイルの不整合を防ぐ:
```bash
prev_n=$(uv run python scripts/alpha_factory/get_latest_run_number.py --max-below "${run_number}" --require-file) || prev_n=""
if [ -n "${prev_n}" ]; then
  prev_report=$(find reports/run-reports -maxdepth 2 -name "run-${prev_n}.md" -not -path '*/old/*' | head -1)
  if [ -z "${prev_report}" ]; then
    echo "WARNING: prev_n=${prev_n} but no file found. Skipping previous report comparison." >&2
    prev_report=""
  fi
fi
```

## Step 4. RUN結果データの収集

以下のデータソースからレポートに必要な情報を収集する:

### 4-1. ゲノムアーカイブ分析
```bash
uv run python scripts/trading/analyze_genome_archive.py {run_id}
```

### 4-2. winnersファイル
```bash
ls config/alpha_factory/winners/*{run_id}*
```
winnersファイルからC-PASS個体の詳細を取得。

### 4-3. candidatesファイル
```bash
ls config/alpha_factory/candidates/*{run_id}*
```

### 4-4. GA実行ログ
```bash
# ログファイルからパラメータ・Gate Stats等を取得
cat .cache/alpha_factory/ga_run.log | head -100
```

### 4-5. Director決定ログ（Director有効時）

DirectorはデフォルトOFF（config `director.mode: off`）。有効時のみ以下を取得:
```bash
cat .cache/alpha_factory/director/director_decisions/{run_id}.json
```

### 4-6. 施策情報（前回RUN開始〜今回RUN開始の間の全変更）

施策セクションには**前回RUN開始時点〜今回RUN開始時点**の間にコミットされた変更のみを記載する。
RUN実行中・実行後のコミットはそのRUNに反映されていないため、次回レポートの施策となる。

**前回RUN開始時刻の取得**: 前回レポート（欠番がある場合は直前の既存レポート）の「開始日時」フィールドから取得する:
```bash
# 直前の既存レポートを共通ヘルパーで検索（--require-file で実ファイル整合を保証）
prev_n=$(uv run python scripts/alpha_factory/get_latest_run_number.py --max-below "${N}" --require-file) || prev_n=""
if [ -z "${prev_n}" ]; then
  echo "ERROR: cannot determine previous Run number" >&2
  exit 1
fi
prev_report=$(find reports/run-reports -maxdepth 2 -name "run-${prev_n}.md" -not -path '*/old/*' | head -1)
if [ -z "${prev_report}" ]; then
  echo "ERROR: prev_n=${prev_n} but no file found (summary/path mismatch)" >&2
  exit 1
fi
# 前回レポートの「開始日時」行からRUN開始時刻を取得
prev_run_start_time=$(grep '開始日時' "${prev_report}" | sed 's/.*| //')
```

**変更の取得**: cycle内（improve-cycle）・cycle外（implement worktree, 手動コミット）の**両方の変更**を含める:
```bash
# 前回RUN開始時点のコミットを取得
prev_run_start_commit=$(git rev-list -1 --before="${prev_run_start_time}" HEAD)
# 今回RUN開始時点のコミットを取得（run_start_timeはStep 4-4のGA実行ログから取得した開始日時）
run_start_commit=$(git rev-list -1 --before="${run_start_time}" HEAD)
# 前回RUN開始〜今回RUN開始の間のAlpha Factory関連変更を取得
git log --oneline "${prev_run_start_commit}..${run_start_commit}" -- src/trading/ tests/alpha_factory/ config/alpha_factory/
```

**注意**: worktreeからのマージコミット（`Merge branch 'worktree-agent-*'`）も含まれる。これらはcycle外で行われたTODO実装等の変更であり、施策セクションに記載すること。

コード変更が一切ない場合は「コード変更なし（パラメータ変更のみ）」等と記載。

### 4-7. 市場レジームコンテキスト（T327）

各評価窓の期間で `market_regime_labels_daily` をクエリし、窓ごとのレジーム分布を取得する:
```bash
# 評価窓の日付範囲はGA実行ログまたはgenome archiveから取得
# DBクエリ例（psqlまたはPythonスクリプト）:
psql -h localhost -p 15432 -U zenigame -d zenigame -t -A -c "
SELECT regime_label, COUNT(*) as days
FROM market_regime_labels_daily
WHERE trade_date BETWEEN '{window_start}' AND '{window_end}'
  AND scope = 'market'
GROUP BY regime_label
ORDER BY days DESC
"
```

窓ごとにレジーム分布を集約し、Top個体ドシエの窓別成績テーブルにregime列として付記する。
例: `W0: trend_up_low_vol(8d), flat_low_vol(6d)`

**レジームデータが取得できない場合**（T327未実行、DBに該当期間のデータなし等）: 「レジームデータなし」と記載してスキップ。

### 4-8. Diversity KPI（T352）

`reports/run-reports/diversity-kpi.jsonl` から対象run_idのレコードを抽出する:
```bash
grep "{run_id}" reports/run-reports/diversity-kpi.jsonl
```
前回run_idのレコードも取得して比較用データとする。

### 4-9. Clause比統計・n_clauses別分布

`analyze_genome_archive.py --sections clause` の出力から取得。
n_clauses分布テーブルにC-PASS列とC-Sharpe Top1が含まれる。

**注意**: 現在 min_clauses=2 が強制されており n_clauses=1（Flat）は生成されない。n_clauses=0/1の行は不要。実際に存在する n_clauses 値（2〜max_clauses）のみ記載する。

### 4-10. Top個体Stock Exposure + Cost（T328）

`analyze_genome_archive.py --sections stock_exposure` の出力から「Top個体 Stock Exposure」セクションを取得する。
Top個体のバケット別trade/pnl share、HHI、gross/cost breakdownが含まれる。

### 4-11. Stage C窓選択情報

GA実行ログからStage Cの各窓（W0/W1/W2）の期間・役割・レジーム分布を取得する:
```bash
# GA実行ログからStage C窓情報を抽出
grep -E "Stage C window [0-9]|Stage C multi-window.*roles|T443.*stress probe" .cache/alpha_factory/runs/{run_id}.log
```

ログ出力フォーマット例:
```
Stage C window 0 (stratified, role=diversity): IS=20 days (2025-05-22~2025-06-18), OOS=10 days (2025-06-19~2025-07-02) [regimes: flat_low_vol:8/10, trend_up_low_vol:2/10]
Stage C window 1 (stratified, role=diversity): IS=20 days (2025-07-07~2025-08-04), OOS=10 days (2025-08-05~2025-08-19) [regimes: flat_high_vol:2/10, trend_up_high_vol:8/10]
Stage C window 2 (stratified, role=stress): IS=20 days (2025-12-17~2026-01-19), OOS=10 days (2026-01-20~2026-02-02) [regimes: flat_high_vol:1/10, trend_down_high_vol:9/10]
```

ログが見つからない場合は `.cache/alpha_factory/ga_run.log` も確認する。

### 4-12. Adaptive指標の取得（T425: RASI）

`adaptive_live_criteria_enabled=true` の場合、ゲノムアーカイブから以下のadaptive指標を取得する:
- `adaptive_mission_score`: RASI（Regime Adaptation Score Index）スコア
- `adaptive_mission_pass`: 全窓でadaptive基準を達成したか（bool）
- `adaptive_mission_window_pass_count`: adaptive基準を達成した窓数
- `stage_c_w{N}_adaptive_criteria_type`: 各窓に適用されたadaptive criteriaの名前（trend_up / defensive / default）

```bash
# analyze_genome_archive.pyの出力にadaptive指標が含まれる
# 個体詳細取得時にadaptive指標も出力される
uv run python scripts/trading/analyze_genome_archive.py {run_id} --genome-id {id1},{id2},...
```

## Step 5. レポート作成

以下の構成でレポートを作成する。

### レポートのトーン・視点（厳守）

#### 1. Top個体中心の分析（最重要）

使命は「飛び抜けて成績が高い戦略を1つ生み出す」こと。集団の平均統計ではない。

| 無意味（書かない） | 意味がある |
|------------------|----------|
| B-PASS全体の平均net/trade | **Top 1個体**のStage C各窓での具体的な成績と失敗原因 |
| C不通過474個体の平均C-Sharpe | **Top 5個体**それぞれがC不通過になった具体的条件（どの窓で何が閾値未満か） |
| A-PASS率の前Run比較 | Top個体のシグナル構成・パラメータの特徴と、そこから次に何を変異させるか |
| B-gross/trade の集団平均 | Top個体のgross/tradeとcost/tradeのバランス |

考察セクションの主題は常に：**「最良個体はなぜ全窓adaptive基準を達成できないのか、何が足りないのか、どうすれば届くのか」**（adaptive enabled時）

#### 2. 形容詞・修飾語の禁止（厳守）

数値に量的形容詞・修飾語をつけない。数値だけ書けば読み手が判断できる。これはレポート全体（考察・次のアクション含む）に適用される。

**禁止語リスト（これらを含む文は書き直す）**:
大幅、劇的、爆発的、飛躍的、壊滅的、改善、悪化、良好、顕著、安定、不安定、急激、著しい、画期的、前向き、有望、深刻、微小、確立、浸透、成長、堅調、順調

**禁止パターン**:
- 「X倍の〇〇的増加」→ 「R337: 210, R336: 59」
- 「過去最高/最低」→ 数値を並べれば読み手がわかる
- 「〜が確立された」→ 出現率の数値を書くだけ
- 「方向性は正しい」「兆候がある」→ 書かない

| NG | OK |
|----|-----|
| 「C-PASS=210（3.6倍の**爆発的増加**）」 | 「C-PASS 210（R336: 59）」 |
| 「デケイ**劇的改善**(-0.0762)」 | 「B→Cデケイ -0.0762（R336: -0.4110）」 |
| 「MAVR+RL+SFPR三位一体構造の**確立**」 | 「C-PASSでのMAVR含有率100%, SFPR 98%, RL 94%」 |
| 「net/tradeが-45.5%と**大幅**低下」 | 「net/trade 0.0030%（R140: 0.0055%）」 |
| 「**方向性は正しい**」 | 書かない。C-PASS=0の施策に方向性の評価は不要 |

#### 3. 使命との距離感

- **使命未達の現実を最初に述べる**。C-PASS=0ならそれが最重要事実
- Run間の微小変動を「成果」として記述しない
- 「可能性を示す」「前向きな兆候」「良好」等のポジティブ修飾語を使わない

### レポート構成

````markdown
# Run {N} レポート

> **adaptive_mission_pass={値}体**（R{N-1}: {前回値}体）。adaptive D* score={値}（R{N-1}: {前回値}）。adaptive window_pass分布: 3窓={値}, 2窓={値}, 1窓={値}, 0窓={値}。adaptive_mission_score Top1={値}（{genome_id}）。C-PASS={値}（R{N-1}: {前回値}）。W{最弱窓}通過率{値}%（R{N-1}: {前回値}%）。best B-Sharpe={値}（R{N-1}: {前回値}）。Clause比={値}%（C-PASS内Clause個体率）。{施策要約}。
> （参考: standard mission_pass={値}体、C-Sharpe Top1={値}）

{adaptive_live_criteria_enabled=false の場合: adaptive関連指標を先頭から除外し、C-Sharpe Top1を主指標として冒頭に配置（従来形式）}

## 実行パラメータ

| パラメータ | 値 |
|-----------|-----|
| run_id | {run_id} |
| 開始日時 | {YYYY-MM-DD HH:MM} |
| 終了日時 | {YYYY-MM-DD HH:MM} |
| 実行時間 | {値}分 |
| pop-size | {値} |
| generations | {値} |
| routing_mode | {値} |
| min_clauses | {値} |
| max_clauses | {値} |
| adaptive_live_criteria | {enabled/disabled} |
| ... | ... |
````

開始・終了日時はGA実行ログの最初と最後のタイムスタンプから取得する:
```bash
head -1 .cache/alpha_factory/ga_run.log  # 開始時刻
tail -5 .cache/alpha_factory/ga_run.log  # 終了時刻
```

````markdown
## Stage C窓選択

| 窓 | 役割 | IS期間 | OOS期間 | レジーム分布 |
|----|------|--------|---------|-------------|
| W0 | {diversity/stress} | {YYYY-MM-DD〜YYYY-MM-DD} | {YYYY-MM-DD〜YYYY-MM-DD} | {regime:count/total, ...} |
| W1 | {diversity/stress} | {YYYY-MM-DD〜YYYY-MM-DD} | {YYYY-MM-DD〜YYYY-MM-DD} | {regime:count/total, ...} |
| W2 | {diversity/stress} | {YYYY-MM-DD〜YYYY-MM-DD} | {YYYY-MM-DD〜YYYY-MM-DD} | {regime:count/total, ...} |
````

Step 4-11で取得したGA実行ログのStage C窓情報からテーブルを構築する。stress窓はTDHV（trend_down_high_vol）含有率が最大の窓、diversity窓はJS-divergence最大化で選択された窓。

````markdown
## 施策

| # | 施策 | 内容 |
|---|------|------|
| {T-ID / C-N / fix / refactor} | {施策名} | {内容} |
````

**施策の記載ルール**: Step 4-6で取得したgit logの**全コミット**を施策テーブルに記載する。「コード変更なし」はgit logが**完全に空**の場合のみ。

| git logのパターン | # 列の書き方 | 例 |
|------------------|------------|-----|
| `feat: T316 ...` / `Merge branch 'todo/T316'` | TODO ID | `T316` |
| improve-cycle内の施策コミット | `C-N` | `C-1` |
| `fix: ...` | `fix` | `fix` |
| `refactor: ...` / `perf: ...` | コミットprefix | `refactor` |
| その他（パラメータ変更等） | `config` / `chore` | `config` |

cycle内・cycle外の区別が必要な場合は「内容」列に付記する（例:「cycle外実装済み」）。Mergeコミットはマージ元のコミット内容を要約して1行にまとめる。

````markdown
## Mission判定カード

**【セクション順序: 厳守】** adaptive_live_criteria_enabled=true時、Adaptive Mission判定カードを**先に**記載し、Standard Mission判定カードを「参考」として**後に**記載する。この順序の入れ替えは禁止。

### Adaptive Mission判定カード（主セクション）

{adaptive_live_criteria_enabled=true時、このセクションが主。false時は省略}

### Sieve送信個体一覧

adaptive_mission_pass個体（正規経路）+ score_bypass個体（バイパス経路、config `sieve_warmstart.score_bypass_top_n` で指定）の全個体を掲載。
バイパス経路: C-PASS個体からmission_gap_max昇順 → adaptive_mission_score降順で上位N体を選択。

| # | genome_id | sieve_source | n_clauses | adaptive_score | adaptive_pass | adaptive_window_pass | worst_gap | C-Sharpe | C-Net(%) | Signals |
|---|-----------|-------------|-----------|---------------|---------------|---------------------|-----------|---------|---------|---------|
| 1 | {id} | {adaptive_pass/score_bypass} | {値} | {値} | {Y/N} | {N}/{窓数} | {値} | {値} | {値} | {シグナル略称} |

窓別詳細（上位5体）:

| # | genome_id | W0 adaptive | W1 adaptive | W2 adaptive | W0 criteria | W1 criteria | W2 criteria |
|---|-----------|------------|------------|------------|-------------|-------------|-------------|
| 1 | {id} | {Y/N (Sharpe=X vs 閾値Y)} | {Y/N (Sharpe=X vs 閾値Y)} | {Y/N (Sharpe=X vs 閾値Y)} | {type} | {type} | {type} |

Sieve送信サマリ: adaptive_pass={値}体 + score_bypass={値}体 = 合計{値}体（score_bypass_top_n={設定値}）
adaptive_mission_pass個体数: {値}体（前Run: {前回値}体）

### Standard Mission判定カード（参考）

{adaptive enabled時は「参考」として小さく記載}

| D* genome | gap_max | cvar_gap | mission_score | unmet | bottleneck | best C-Sharpe(参考) | best C-Sharpe genome |
|-----------|---------|----------|---------------|-------|------------|---------------------|---------------------|
| {D* id} | {値} | {値} | {値} | {N/5} | {最大gap指標} | {値} | {C-Sharpe Top1 id} |

前Runとの差分: gap_max {前回値}→{今回値}
mission_pass個体数: {mission_pass=Trueの個体数}（前Run: {前回値}）

{Mission Gap Scoreデータなし時: 「Mission Gap Scoreデータなし（T316未実装）」}

**指標定義（参考）**:
- gap_max = D*個体の mission_worst_gap（全窓横断で最大のgap）
- cvar_gap = mission_cvar_gap（worst 2窓のgap平均）
- mission_score = 1 - gap_max（1.0で使命達成）
- **注**: standard mission基準は全窓一律閾値（例: min_sharpe=1.0）。窓のレジームを考慮しない単一数値であり、adaptive基準に比べて情報量が少ない

{adaptive_live_criteria_enabled=false の場合: 従来通りMission判定カードを主セクションとして記載。Adaptive判定カードは省略}
````

````markdown
## Top個体ドシエ
````

**レポートの最重要セクション。** 使命に最も近い個体を理解するための詳細カード。

### 掲載個体の選出基準

**adaptive_live_criteria_enabled=true時**: **adaptive_mission_score順**（C-Sharpe順ではない）で上位から最大5個体を掲載。以下の優先順で選出し、重複を除外して繰り上げる:
1. adaptive_mission_score Top1（= Adaptive D*個体）
2. adaptive_mission_score Top2
3. adaptive_mission_score Top3
4. adaptive_mission_pass=True の最高C-Sharpe個体（上記と異なる場合）
5. 3/3窓全通過の最高adaptive_mission_score個体（上記と異なる場合）

**adaptive_live_criteria_enabled=false時**: C-Sharpe上位から最大5個体（従来通り）:
1. C-Sharpe Top1（= D*個体と同一の場合が多い）
2. D*個体（C-Sharpe Top1と異なる場合）
3. C-Sharpe Top2
4. C-Sharpe Top3
5. 3/3窓全通過の最高C-Sharpe個体（上記と異なる場合）

**B-Sharpe Top1は掲載しない**。B-Sharpe上位個体の情報は付録B-Sharpe Top10テーブルで十分。

### 必須データの取得（厳守）

Top個体ドシエの各フィールドは**全て必須**。「データなし」「不明」での省略は禁止。
- winnersファイル、candidatesファイル、ゲノムアーカイブParquetのいずれかから必ず取得する
- ゲノムアーカイブParquetが最も情報量が多い。`analyze_genome_archive.py {run_id} --genome-id {id}` で個体詳細を取得（カンマ区切りで複数指定可）
- winnersファイルからシグナル構成・パラメータを取得できない場合は、Parquetのsignal_names列から取得する

### Top個体カードのフォーマット

````markdown
### Top 1: {id} (adaptive_score={値}, C-Sharpe={値}, n_clauses={値})

{adaptive_live_criteria_enabled=false時: ヘッダは「Top 1: {id} (C-Sharpe={値}, n_clauses={値})」}

**Clause構造**: {clause_structure}（n_clauses={値}）
**窓別成績**（最重要テーブル）:
| 窓 | adaptive_criteria_type | adaptive_pass | Sharpe | net_return(%) | DD | trades | win_rate | C-stage pass/fail | regime |
|----|----------------------|--------------|--------|--------------|-----|--------|----------|-------------------|--------|
| W0 | {trend_up/defensive/default} | {Y/N (Sharpe=X vs 閾値Y)} | {値} | {値} | {値} | {値} | {値} | {Y/N} | {レジーム分布} |
| W1 | {trend_up/defensive/default} | {Y/N (Sharpe=X vs 閾値Y)} | {値} | {値} | {値} | {値} | {値} | {Y/N} | {レジーム分布} |
| W2 | {trend_up/defensive/default} | {Y/N (Sharpe=X vs 閾値Y)} | {値} | {値} | {値} | {値} | {値} | {Y/N} | {レジーム分布} |

{レジームデータなしの場合はregime列を省略}
{adaptive_live_criteria_enabled=false の場合は adaptive_criteria_type / adaptive_pass 列を省略、mission_pass列を追加}

**シグナル構成**: {シグナル一覧（フルネーム + 略称）}
**fail_reason**: {adaptive基準での不達理由: どの窓でどのcriteria_typeの何が閾値未満か。adaptive_pass=True時は「adaptive全窓達成」}
**Adaptive Mission Score** (adaptive_live_criteria_enabled=true時): adaptive_mission_score={値}, adaptive_mission_pass={Y/N}, adaptive_mission_window_pass_count={値}/{窓数}
**Standard Mission Score（参考）**: mission_worst_gap={値}, mission_cvar_gap={値}, mission_score={値}, mission_window_pass_count={値}/{窓数}
**IC/firing_rate**: B-IC={値}, B-FR={値}, C-IC={値}
**Stock Exposure**: {バケット上位3つ: bucket=pnl NN%, bucket=pnl NN%, ...  HHI={値}}
**Cost**: gross/trade={値}%, cost/trade={値}%, cost_ratio={値}%
**パラメータ**: entry_threshold={値}, max_pos={値}, stop_atr={値}, take_atr={値}

{n_clauses >= 2 の場合のみ以下を追記}
**Clause診断（T359）**:
- 専門化: MI(E;R)={diag_mi_e_r}bit, H(E|R)={diag_h_e_given_r}bit, clause_corr={diag_clause_corr}, jaccard={diag_jaccard}
- Headroom: h_signal={値}, h_abs_net={値}, h_causal_net={値}
- ABCD分解: A(合成器)={diag_a_pct}%, B(予測力)={diag_b_pct}%, C(コスト)={diag_c_pct}%, D(窓バイアス)={diag_d_pct}%

### Top 2: {id} (adaptive_score={値}, C-Sharpe={値}, n_clauses={値})
{同じフォーマット}

### Top 3〜5: ...
{同じフォーマット。5個体まで}
````

````markdown
## ボトルネック因果
````

Mission Dashboardのfail_reason分解と窓別通過率から、使命未達の構造を因果鎖で記述する。

**adaptive enabled時**: adaptive基準での窓別未達分析を主とする。

````markdown
### fail_reason分解（B-PASS→C-FAIL個体）
| カテゴリ | 出現率 |
|----------|--------|
| {カテゴリ} | {値}% |

### 窓別通過率
| 窓 | 通過率 | Sharpe平均 | TC平均 |
|----|--------|-----------|--------|
| W0 | {値}% | {値} | {値} |
| W1 | {値}% | {値} | {値} |
| W2 | {値}% | {値} | {値} |

### 因果鎖
````

{adaptive enabled時}:
adaptive基準での最弱窓 {WN}（Top5中adaptive_pass=N: {M}/{5}個体）→ criteria_type={type}, 閾値={値} → Top個体での具体的gap: Sharpe={現在値} vs adaptive閾値{閾値}
→ gap縮小に最も効く介入仮説: {1行}

{adaptive disabled時（従来）}:
最弱窓 {WN}（通過率{値}%）→ 主要fail_reason: {カテゴリ}（{値}%）→ Top個体での具体的gap: {指標}={現在値} vs 閾値{閾値}
→ gap縮小に最も効く介入仮説: {1行}

````markdown
## 戦略判断 (Strategic Questions)
````

以下の各問を必ず記載する。形容詞禁止。数値のみで判断材料を提示する。
毎Run固定の3問 + Run固有の問い（0-2問）。

````markdown
### Q1: 信号空間は十分か
- 根拠: {C-Sharpe歴代Top30のシグナル構成パターン、MAVR依存率等}
- 確信度: {High/Medium/Low}
- 不足データ: {あれば}

### Q2: GAの探索戦略は正しいか
- 根拠: {多様性指標（ユニーク組み合わせ数）、B-Top→C-PASS接続率、世代間エリート系譜}
- 確信度: {High/Medium/Low}
- 不足データ: {あれば}

### Q3: 使命のボトルネックは何か
- 根拠: {adaptive D* scoreの推移（enabled時）、TC天井、窓別adaptive_pass率}
- 確信度: {High/Medium/Low}
- 不足データ: {あれば}

### Q{N}: {Run固有の問い}（任意）
- 根拠: {データポイント}
- 確信度: {High/Medium/Low}
- 不足データ: {あれば}

## 次のアクション

{Run結果から導かれる技術的観察のみ。TODO IDやTODOタイトルへの言及禁止}

## 付録
````

以下は運用健全性の確認用。主要な意思決定には使わないが、異常検知のために残す。

````markdown
### 結果サマリ

| 指標 | R{N} | R{N-1} |
|------|------|--------|
| adaptive_mission_pass個体数 | {値} | {前回値} |
| adaptive D* score | {値} | {前回値} |
| adaptive_mission_score Top1 | {値} | {前回値} |
| B-PASS | {値} | {前回値} |
| C-PASS | {値} | {前回値} |
| A-PASS率 | {値} | {前回値} |
| Best B-Sharpe | {値} | {前回値} |
| B-net/trade | {値} | {前回値} |
| コスト/グロス比 | {値} | {前回値} |
| ユニーク組み合わせ | {値} | {前回値} |
| mission_pass個体数 | {値} | {前回値} |
| C-Sharpe Top1（参考） | {値} | {前回値} |
| 実行時間 | {値} | {前回値} |

{adaptive_live_criteria_enabled=false の場合: adaptive関連3行を省略し、C-Sharpe Top1を「C-Sharpe Top1」として記載（従来形式）}
````

````markdown
### Clause比統計

| Stage | Clause個体 | Flat個体 | 合計 | Clause比 |
|-------|-----------|---------|------|----------|
| 全個体 | {値} | {値} | {値} | {値}% |
| A-PASS | {値} | {値} | {値} | {値}% |
| B-PASS | {値} | {値} | {値} | {値}% |
| C-PASS | {値} | {値} | {値} | {値}% |
````

Clause A-PASS率: {値}% vs Flat A-PASS率: {値}%

**注意**: 現在 min_clauses=2 が強制されており、全個体がClause個体（n_clauses >= 2）となる。Flat個体（n_clauses < 2）は生成されない。Flat列が全て0の場合は「Flat個体なし（min_clauses=2強制）」と注記する。

**n_clauses別分布（C-PASS内）**:

| n_clauses | 個体数 | 比率 | C-Sharpe Top1 |
|-----------|--------|------|---------------|
| 2 | {値} | {値}% | {genome_id, C-Sharpe} |
| 3 | {値} | {値}% | {genome_id, C-Sharpe} |
| 4 | {値} | {値}% | {genome_id, C-Sharpe} |

{実際に存在するn_clauses値のみ記載。現在 min_clauses=2, max_clauses=4 が設定されており、n_clauses=0/1は生成されない}

````markdown
### Gate Stats

| 指標 | 値 |
|------|-----|
| stage_b_ratio | {値} |
| total_evaluated | {値} |
| a_pass_rate | {値} |
| total_gate_blocked | {値} |

### Director サマリ/仮説検証
````

{Director有効時のみ。DirectorはデフォルトOFF（config `director.mode: off`）}
- source / accepted / epoch情報
- 重み上位3・下位3
- 仮説と結果の整合性（重みとC-PASS出現率の対応テーブル）

````markdown
### GA進化効果

| Source | Total | A-PASS | A-PASS率 |
|--------|------:|-------:|--------:|
| offspring | {値} | {値} | {値} |
| random | {値} | {値} | {値} |
| warmstart | {値} | {値} | {値} |

### Diversity KPI（T352）

| 指標 | R{N} | R{N-1} |
|------|------|--------|
| family_unique_rate | {値} | {前回値} |
| HHI | {値} | {前回値} |
| primitive_entropy | {値} | {前回値} |
| regime_coverage | {値} | {前回値} |
| neighbor_distance_median | {値} | {前回値} |
| intervention_active | {Y/N} | {前回値} |
````

{diversity-kpi.jsonlから対象run_idのレコードを抽出。データなしの場合は「Diversity KPIデータなし」と記載}

````markdown
### adaptive_mission_score Top10（C-PASS個体）
````

{adaptive_live_criteria_enabled=true時}

adaptive_mission_scoreで降順ソートしたC-PASS上位10個体。窓別adaptive_pass列を含める。

| # | ID | n_clauses | adaptive_score | adaptive_pass | adaptive_window_pass | C-Sharpe(参考) | C-Net(%) | C-TC | WR | Signals |
|---|-----|-----------|---------------|---------------|---------------------|---------------|---------|------|----|---------|
| 1 | {id} | {値} | {値} | {Y/N} | {N}/{窓数} | {値} | {値} | {値} | {値} | {シグナル略称} |

{adaptive_live_criteria_enabled=false時: 従来のC-Sharpe Top10テーブル}

````markdown
### C-Sharpe Top10（C-PASS個体）（参考）
````

{adaptive_live_criteria_enabled=true時: 「参考」として掲載。adaptive Top10と重複する個体も含む}

| # | ID | n_clauses | C-Sharpe | C-Net(%) | C-TC | WR | mission_pass | adaptive_pass | Signals |
|---|-----|-----------|---------|---------|------|----|-------------|--------------|---------|
| 1 | {id} | {値} | {値} | {値} | {値} | {値} | {Y/N} | {Y/N} | {シグナル略称} |

{adaptive_live_criteria_enabled=false時: C-Sharpe Top10が主テーブル（「参考」注記なし）。adaptive_pass列を省略}

````markdown
### B-Sharpe Top10
````

**C-PASS < 10 の場合のみ掲載**。C-PASSが十分にある場合（>= 10）はこのセクションを省略する。
C-PASS < 10の場合、B-PASS個体の情報がボトルネック分析に必要になるため掲載する。

| # | ID | n_clauses | B-Sharpe | B-net(%) | B-gross(%) | cost(%) | TC | WR | Signals |
|---|-----|-----------|---------|---------|-----------|---------|----|----|---------|

````markdown
### C-PASS窓別通過率

{既存のC-PASS窓別通過率テーブル}

### B→Cデケイ・コスト構造

B→Cデケイ: B-Sharpe平均{値}→C-Sharpe平均{値}。B-net平均{値}%→C-net平均{値}%。
コスト構造: B-gross/trade={値}%, B-cost/trade={値}%, B-net/trade={値}%, cost/gross比={値}%
````

## Step 6. RUN指標サマリー更新

レポート作成後、`/zenigame-update-run-metrics` を呼び出して `reports/run-reports/run-metrics-summary.md` を更新する。

```
/zenigame-update-run-metrics --run_number {N}
```

このスキルが主要指標テーブル、各RUN C-Sharpe Top3、歴代Top30、フェーズ別統計を自動更新する。

## Step 7. コミット

```bash
git add "reports/run-reports/${block}/run-${N}.md" reports/run-reports/run-metrics-summary.md
git commit -m "$(cat <<'EOF'
docs: Run {N} レポート作成

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## 複数RUN一括レポート

引数なしで呼び出された場合、または明示的に範囲指定された場合、レポートが未作成のRUNを検出して順次レポートを生成する。

### 検出手順
1. 既存レポートの最大番号を取得
2. winnersディレクトリから、最終レポート以降のrun_idを時系列で列挙
3. 各run_idに対してStep 3〜7を繰り返す

---

## エラーハンドリング

- ゲノムアーカイブ分析が失敗した場合: ログとwinnersファイルから可能な範囲でレポートを作成
- winnersファイルが見つからない場合: エラー終了（RUN未完了の可能性）
- 前回レポートが見つからない場合: 比較なしでレポートを作成
