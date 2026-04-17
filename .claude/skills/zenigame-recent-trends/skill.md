---
name: zenigame-recent-trends
description: 直近N Runの横断観測レポートを生成（run-reports + alpha-sieveから機械抽出、LLMは固定語彙ラベル付けのみ。因果主張はしない。tmp/ へ出力、commitしない）
argument-hint: "[--runs N] [--timeline-observation] [--focus <theme>] [--include-old]"
---

# Recent Trends Report — 直近 N Run 観測レポート

直近 N Run（既定 10）の指標時系列を観測し、改善判断の準備作業の摩擦を下げる補助スキル。

## 目的と制約（絶対遵守）

- **効果判定・因果主張は一切行わない**。本スキルは「観測」ツールであり、改善効果の測定器ではない
- **Alpha Factory の探索性能そのものは上げない**。観測・比較の摩擦を下げるだけ
- レポートは `live_criteria`（default.yaml）到達可能性を基準に評価する。Sharpe/WR 単体の見栄え改善を "良い変化" として扱わない
- **定性解釈の面積を狭く、機械生成の deterministic 部分を広く**とる（禁止事項3: 数値操作 への距離確保）
- **出力は `tmp/` 配下のみ**（`.gitignore` 済、commit しない ephemeral 出力）
- LLM の役割は 4 節「注目点」の**固定語彙ラベル付けのみ**（自由記述禁止）

## 引数

| 引数 | 必須 | 既定 | 説明 |
|------|------|------|------|
| `--runs N` | No | 10 | 直近何 Run を対象とするか |
| `--timeline-observation` | No | off | クローズ TODO と Run の時系列対応を観測する支援モード（旧称 `--measure-impact` は互換 alias） |
| `--focus <theme>` | No | none | `stage-b` / `diversity` / `gate-pass` 等、特定指標に絞るレンズ |
| `--include-old` | No | off | `reports/run-reports/old/` 配下を探索対象に含める |

**独立利用**: YES — 任意タイミングで単体実行可能。改善ループからは呼ばれない

---

## Step 1. 対象 Run 範囲の決定

```bash
# SSoT: 共通ヘルパーで最新 Run 番号を取得
latest_n=$(uv run python scripts/alpha_factory/get_latest_run_number.py) || exit 1
# 直近 N Run の範囲: [latest_n - N + 1, latest_n]
N=${RUNS:-10}
start_n=$((latest_n - N + 1))

# visible 範囲の最小 Run 番号（old/ を除く）を取得
visible_min=$(find reports/run-reports -maxdepth 2 -name 'run-[0-9]*.md' -not -path '*/old/*' -print \
  | sed 's/.*run-\([0-9]*\)\.md/\1/' | sort -n | head -1)

# old に跨るかチェック
if [ "$start_n" -lt "$visible_min" ] && [ "$INCLUDE_OLD" != "true" ]; then
  echo "WARNING: 対象範囲が visible を超えます。old/ 配下を含めるには --include-old を指定してください。" >&2
  start_n=$visible_min
fi
```

## Step 2. 変遷テーブルの生成（deterministic、2節）

`reports/run-reports/run-metrics-summary.md` を `Read` し、対象 Run 番号の行を抽出する。`| run-N | ... |` 形式の表行から主要列を取得:
- C-Sharpe Top1 / mission_score / gap_max / mission_pass_count / top5_p50 / top5_min

`reports/alpha-sieve/sieve-metrics-summary.md` を `Read` し、同じ Run 番号の行を抽出する:
- A-PASS / S-PASS / S-PASS率 / Top Score / Avg OOS Sharpe / Avg OOS Net

`reports/run-reports/diversity-kpi.jsonl` を `grep` し、対応 run_id の行から5指標を追加:
- family_unique_rate / hhi / primitive_entropy / regime_coverage / neighbor_distance_median

2 つのテーブルを Run 番号で join し、変遷テーブル（Run × 主要指標マトリクス）を生成する。この節は**機械生成のみ**、LLM の加工なし。

## Step 3. `live_criteria` 到達可能性の算出（deterministic、3節）

`config/alpha_factory/default.yaml` から `live_criteria` を `Read` で読み込む。各 Run の最高値・中央値を `live_criteria` 閾値と比較し、到達率（%）を計算する。最も遠い指標を特定する。

**必須内容**: この節では `live_criteria` の各閾値との距離を中心に記述し、Sharpe/WR 単体の改善を "良い変化" として扱わない。最も遠い指標に焦点を当てる。

## Step 4. 注目点の検出（ルールベース、4節、JSON 出力）

検出器（**閾値固定**、再現性確保のため）:

| 検出器 | 閾値 | ラベル候補 |
|--------|------|-----------|
| 乖離検出 (anomaly) | 最新値が直近 9 Run の中央値から \|value - median\| > 2σ | `anomaly-high` / `anomaly-low` |
| 連続方向検出 (trend) | 直近 3 Run で単調増加/減少（全差分が同符号） | `trend-up` / `trend-down` |
| 停滞検出 (stagnant) | 直近 5 Run で値の max - min < 0.5σ | `stagnant` |
| 回復検出 (recovering) | 直近 3 Run 以前が下降トレンドで最新 Run で反転 | `recovering` |
| 悪化検出 (degrading) | 直近 3 Run 以前が上昇トレンドで最新 Run で反転 | `degrading` |
| サンプルサイズ不足 | `n < 10` Run | 自動 `inconclusive-sample-too-small` |

**許可語彙（固定、自由記述禁止）**:
```
trend-up, trend-down, stagnant, anomaly-high, anomaly-low,
recovering, degrading, inconclusive-sample-too-small
```

LLM は検出器が生成した候補に、上記 8 個の固定語彙から 1 つを選んで付与するだけ。最大 3 項目。

### 出力フォーマット（厳格固定、バリデータで検証）

```markdown
## 4. 注目点（最大3項目）

\`\`\`json
{
  "schema_version": 1,
  "items": [
    {
      "label": "trend-up",
      "metric": "stage_b_survivors",
      "window": "run-98..run-100",
      "value_first": 32,
      "value_last": 47
    }
  ]
}
\`\`\`
```

**構文制約**:
- 4 節は fenced JSON ブロックを **exactly 1 個**持つ
- JSON ブロック前のテキストは空 or 許可された固定短文のみ（「（最大 3 項目）」「（最大3項目）」）
- JSON ブロック後のテキストは空のみ
- スキーマ: `{schema_version: 1, items: [{label, metric, window, value_first, value_last}]}` の完全一致（余分キー禁止、items 長 <= 3、label は許可語彙のみ）

## Step 5. 警告・未解決事項の抽出（deterministic、5節）

```bash
for n in $(seq $start_n $latest_n); do
  run_file=$(find reports/run-reports -maxdepth 2 -name "run-${n}.md" -not -path '*/old/*' | head -1)
  [ -z "$run_file" ] && continue
  grep -nE 'ERROR|CRITICAL|bug' "$run_file" | head -20
done
```

LLM による加工は行わない。grep 結果をそのまま列挙する。

## Step 6. 観測: 実装と Run の時系列対応（`--timeline-observation` 時のみ、6節）

`--timeline-observation`（または互換 alias `--measure-impact`）が指定された場合のみ出力する。

### 必須: 固定免責テンプレート（HTML コメントマーカーで挟む）

Section 6 の冒頭に以下を**必ず**出力する（バリデータが免責マーカー範囲を検査）:

```markdown
## 6. 観測: 実装と Run の時系列対応

<!-- recent-trends:disclaimer-start -->
本節は観測であり因果主張ではありません。以下の理由により対応付けは approximate です:
- squash merge で複数 TODO が同一コミットに入った場合、個別寄与は分離不能
- cherry-pick で複数ブランチに登場するコミットは時刻が前後する
- 実装 → Run 実行の間に遅延があるため、Run 番号への対応は approximate
- 実装以外の交絡要因（config 変更、他の実装、データ更新）を含む

verdict（効果あり/なし/判定不能）は生成しません。対比表の数値を見て判断は人間が行ってください。
<!-- recent-trends:disclaimer-end -->
```

### 対比表の生成

1. `docs/alpha-factory/TODO-closed.md` から直近 K 件の close エントリを抽出（`--runs N` に合わせて K = N / 2 程度）
2. 各エントリに対し `git log --format='%H %ct %s' -- docs/alpha-factory/TODO-closed.md | grep ...` でコミット時刻を取得
3. 対象期間の前後 M Run のサマリ値を対比表として出力

**verdict は出さない**: 「効果あり」「効果なし」「判定不能」のようなラベル禁止。対比表の数値と、時系列対応を示す文字列のみ。

## Step 7. データ出典の列挙（deterministic、7節）

使用した全ファイルのパスを一覧表として出力する。LLM 加工なし。

## Step 8. バリデータで書き込み前検査

書き込み先: `tmp/recent-trends_$(date +%Y%m%d_%H%M%S).md`

スキル内で draft を作成した後、書き込み直前に以下を実行する:

```bash
mkdir -p tmp
OUTPUT="tmp/recent-trends_$(date +%Y%m%d_%H%M%S).md"
DRAFT="${OUTPUT}.draft"

# draft を書き込む（セクション1〜7 を結合）
# ... (各セクションの中間出力を draft に集約)

# バリデータ実行（禁止語・JSON構造・Section 6 マーカーを機械検査）
uv run python scripts/alpha_factory/validate_recent_trends.py "$DRAFT" || {
  echo "ERROR: Validation failed. Aborting." >&2
  rm -f "$DRAFT"
  exit 1
}

mv "$DRAFT" "$OUTPUT"
cat "$OUTPUT"
echo ""
echo "Report: $OUTPUT"
```

**バリデータが fail した場合**: スキルは**異常終了**する。LLM 生成文に禁止語や自由記述が混入した場合、再試行することなく fail を報告し、人間が内容を確認する必要がある。

---

## 固定語彙リスト（LLM はこの 8 個から選ぶだけ）

```
trend-up, trend-down, stagnant,
anomaly-high, anomaly-low,
recovering, degrading,
inconclusive-sample-too-small
```

## 禁止語（バリデータが機械検査）

因果主張を連想させる以下の語彙は**禁止**（免責セクション内を除く）:

- 日本語: 効果があ/ない、有効/無効、原因、起因、由来、寄与、効く/効いた、改善効果、判定不能/可能、効いている、によって、結果として、示唆、影響した、効果的、につながる、もたらす、引き起こす、ゆえに、起こした、招いた、結果的に、その結果
- 英語: Effective, Ineffective, Caused by, Due to, Thanks to, Because of, As a result, Led to, Driven by, Therefore, Thus

注: 「ため」は「〜するため」が日本語で頻出するため禁止語から**除外**（誤検知防止）。

---

## エラーハンドリング

### 共通ヘルパー失敗時
- `get_latest_run_number.py` が exit 1 → 「最新 Run 番号を取得できません」とエラー終了

### バリデータ失敗時
- draft を削除してエラー終了
- 再試行しない（人間が内容を見て判断する）

### サマリファイル欠損時
- `run-metrics-summary.md` が存在しない場合、fallback でパス探索するが変遷テーブルは空になる
- 「データ不足」と 3 節で明示し、`inconclusive-sample-too-small` を 4 節に出力

---

## 使用例

### 例1: 直近 10 Run の標準レポート
```
/zenigame-recent-trends
```

### 例2: 直近 5 Run + 時系列対応観測
```
/zenigame-recent-trends --runs 5 --timeline-observation
```

### 例3: Stage B に焦点、old 配下も含める
```
/zenigame-recent-trends --runs 20 --focus stage-b --include-old
```
