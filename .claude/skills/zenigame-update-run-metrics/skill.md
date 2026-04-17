---
name: zenigame-update-run-metrics
description: RUN指標サマリー（reports/run-reports/run-metrics-summary.md）を最新レポートで更新する
argument-hint: "[run_number]"
---

# RUN指標サマリー更新

RUNレポート作成後に `reports/run-reports/run-metrics-summary.md` を更新する。run-reportから呼ばれるLayer 1プリミティブ。

## 引数

| 引数 | 必須 | 説明 |
|------|------|------|
| `run_number` ($1) | No | 更新対象のレポート番号（例: 341）。省略時は最新レポートを自動検出 |

**入力**: `reports/run-reports/**/run-{N}.md`（作成済みレポート、ブロック配下）
**出力**: `reports/run-reports/run-metrics-summary.md`（更新済み）

**独立利用**: YES — 任意のタイミングで単体実行可能

---

## Step 1. 対象レポートの特定

### run_number が指定されている場合
そのまま使用。

### run_number が未指定の場合
最新レポートを検出（共通ヘルパー経由）:
```bash
latest_n=$(uv run python scripts/alpha_factory/get_latest_run_number.py) || exit 1
latest_report=$(find reports/run-reports -maxdepth 2 -name "run-${latest_n}.md" -not -path '*/old/*' | head -1)
```

## Step 2. 既存サマリーの読み込み

`reports/run-reports/run-metrics-summary.md` を `Read` する。

## Step 3. 対象レポートの読み込み

対象レポート（ブロック配下、`find` で解決したパス）を `Read` し、以下の情報を抽出する:

### 3-1. North Star進捗テーブル用データ

| フィールド | 抽出元 |
|-----------|-------|
| Run番号 | ファイル名 |
| best_C_sharpe | Top個体ドシエ（C-Sharpe Top1） |
| best_C_genome | Top個体ドシエ（C-Sharpe Top1のgenome ID） |
| gap_max | Mission判定カード |
| cvar_gap | Mission判定カード（R431以降。それ以前はN/A） |
| mission_score | Mission判定カード（R431以降。それ以前はN/A） |
| mission_pass_count | 結果サマリ → mission_pass個体数（R431以降。それ以前はN/A） |
| unmet | Mission判定カード |
| bottleneck | Mission判定カード（最大gap指標） |
| top5_p50 | Top-5 gapスコアボード（C-Sharpe中央値を計算） |
| top5_min | Top-5 gapスコアボード（C-Sharpe最小値） |

### 3-2. ボトルネック地図用データ

| フィールド | 抽出元 |
|-----------|-------|
| 最弱窓 | ボトルネック因果 → 窓別通過率テーブル（最低通過率の窓） |
| fail_reason最頻 | ボトルネック因果 → fail_reason分解テーブル（1位） |
| fail_reason 2nd | ボトルネック因果 → fail_reason分解テーブル（2位） |

### 3-3. C-Sharpe Top3個体データ

Top個体ドシエ + 付録から上位3個体の情報を抽出:
- Genome ID
- C-Sharpe
- B-Sharpe
- n_clauses（R431以降。Top個体ドシエの「Clause構造」行から取得。それ以前はN/A）
- シグナル構成

C-PASS=0の場合は「—」で埋める。

### 3-4. D*スコアデータ（Mission Dashboard）

Mission判定カードからD*個体の情報を抽出:
- D* Genome ID
- gap_max
- cvar_gap（R431以降。それ以前はN/A）
- mission_score（R431以降。それ以前はN/A）
- unmet（未達成指標数、例: 3/5）
- D* C-Sharpe
- D* n_clauses（R431以降。Top個体ドシエから取得。それ以前はN/A）
- ボトルネック（最大gapの指標名とその値）

Mission判定カードが存在しないRUNはスキップ。

### 3-5. 集団統計データ（付録用）

付録の結果サマリから:
- pop, B-PASS, C-PASS, A-PASS率, Best B-Sharpe, B-net/trade, コスト/グロス比, 実行時間

付録のClause比統計から（R431以降）:
- Clause比(C-PASS) = C-PASS内のClause個体比率

付録の結果サマリから（R431以降）:
- mission_pass個体数

## Step 4. North Star進捗テーブルの更新

### 4-1. 新規行の追加

「North Star進捗」テーブルに対象Runの行が**存在しない場合**は新規行を追加する。Run番号の昇順を維持する。

**既に存在する場合**は値を上書き更新する（再生成時の二重追加防止）。

### 4-2. ボトルネック地図テーブルの更新

「ボトルネック地図」テーブルに対象Runの行を追加または更新する。

### 4-3. D*スコアテーブルの更新

「D* スコア」テーブルに対象Runの行を追加または更新する（Mission判定カードが存在するRUNのみ）。

## Step 5. C-Sharpe Top3テーブルの更新

「各RUN C-Sharpe Top3 個体一覧」テーブルに対象Runの行を追加または更新する。

## Step 6. 歴代Top30の更新

### 6-1. C-Sharpe歴代Top30

全RUNの C-Sharpe Top3個体テーブルから全個体を収集し、C-Sharpe降順でソートして上位30個体を再構成する。
n_clauses列を含める（R430以前の個体はN/A）。

### 6-2. B-Sharpe歴代Top30

全RUNの Best B-Sharpe値でRUNをランキングし、上位30 RUNを再構成する。

### 6-3. 共通特徴セクション

C-Sharpe Top30個体のシグナル出現頻度を再集計し、共通特徴セクションを更新する。
n_clauses分布（Flat / 2clause / 3+clause の個体数）を追記する。

## Step 7. 付録: 集団統計テーブルの更新

### 7-1. 集団統計行の追加

「付録: 集団統計」テーブルに対象Runの行を追加または更新する。

### 7-2. フェーズ別統計の再計算

フェーズ区分ごとの統計値（中央値、平均、最小、最大）を再計算する。
- pop-size=96 期: popカラムが96のRUN
- pop-size=192 期: popカラムが192のRUN

### 7-3. 備考の更新

- レポート欠番の更新
- C-PASS=0のRUN一覧更新
- generations/pop-size変更点の更新

## Step 8. ファイル書き込み

更新済みの内容で `reports/run-reports/run-metrics-summary.md` を `Write` する。

**サマリーファイルの構成**:

```markdown
# Alpha Factory RUN指標サマリ（R285〜R{最新}）

生成日: {YYYY-MM-DD}

## North Star進捗

| Run | best_C_sharpe | best_C_genome | gap_max | cvar_gap | mission_score | mission_pass_count | unmet | bottleneck | top5_p50 | top5_min |
|-----|---------------|---------------|---------|----------|---------------|--------------------|-------|------------|----------|----------|

{R430以前: cvar_gap/mission_score/mission_pass_count列はN/A}

## ボトルネック地図

| Run | 最弱窓 | fail_reason最頻 | 2nd最頻 |
|-----|--------|----------------|---------|

## D* スコア（Mission最近接個体）

| Run | D* Genome | gap_max | cvar_gap | mission_score | unmet | D* C-Sharpe | D* n_clauses | ボトルネック |
|-----|-----------|---------|----------|---------------|-------|-------------|-------------|-------------|

{D*傾向テキスト}

## 各RUN C-Sharpe Top3 個体一覧

| Run | #1 ID | #1 C-Sharpe | #1 n_clauses | #2 ID | #2 C-Sharpe | #2 n_clauses | #3 ID | #3 C-Sharpe | #3 n_clauses |
|-----|-------|-------------|-------------|-------|-------------|-------------|-------|-------------|-------------|

{R430以前: n_clauses列はN/A}

## C-Sharpe歴代Top30個体

{既存フォーマット + n_clauses列を追加}

## B-Sharpe歴代Top30個体

{既存フォーマット維持}

## 歴代Top個体の共通特徴

{既存フォーマット維持 + Clause構造傾向を追記}
- n_clauses分布: Flat={値}個体, 2clause={値}個体, 3+clause={値}個体

---

## 付録: 集団統計

| Run | pop | B-PASS | C-PASS | A-PASS率 | Best B-Sharpe | B-net/trade | コスト/グロス比 | Clause比(C-PASS) | mission_pass | 実行時間 |
|-----|-----|--------|--------|----------|---------------|-------------|----------------|-------------------|-------------|----------|

{R430以前: Clause比(C-PASS)/mission_pass列はN/A}

### フェーズ別統計

{pop-size=96期、pop-size=192期の中央値/平均/最小/最大}

### 備考

{欠番、C-PASS=0、generations変更等}
```

**コミットは行わない** — 呼び出し元（run-report）がコミットを管理する。単体実行時は自身でコミットする:

```bash
git add reports/run-reports/run-metrics-summary.md
git commit -m "$(cat <<'EOF'
docs: Run指標サマリー更新（Run {N}）

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## エラーハンドリング

- サマリーファイルが存在しない場合: テンプレートから新規作成
- 対象レポートが存在しない場合: エラー終了
- データ抽出に失敗したフィールド: `N/A` で埋める
