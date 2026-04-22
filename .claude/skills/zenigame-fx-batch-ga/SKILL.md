---
name: zenigame-fx-batch-ga
description: zenigame-fx Alpha Factory の GA-Only バッチ N 回連続実行（分析BG、クロスラン統計）
argument-hint: '[--n 10] [--calibrate] [--label baseline] [--snapshot-before name] [--run-args "..."] [--resume batch_id]'
user-invocable: true
---

# zenigame-fx GA-Only バッチ実行

> **トリガー条件**: ユーザーが明示的に「batch」「バッチ」と言った場合のみ使用する。
> 「2RUN 走らせて」「N 回まわして」等の一般的な RUN 指示では `/zenigame-fx-improve-cycle` を使うこと。

コード凍結状態で GA を N 回連続実行し、ベースライン分布を確立する。
分析はバックグラウンドで実行し、GA 回転速度を最優先する。

## 思考原則 / 使命 / 禁止事項

`zenigame-fx-codex-review` で定義される内容を適用する。

## 実行前提チェック

本スキルは依存 script + 関連 skill の充足が必要。起動時に以下を確認し、不足時は列挙してアボート。

### script (必須)

- `scripts/alpha_factory/run_ga.py`
- `scripts/alpha_factory/extract_batch_metrics.py`
- `scripts/alpha_factory/compare_batch_runs.py`
- `scripts/alpha_factory/get_latest_run_number.py`

各 script は `ls scripts/alpha_factory/{script_name}` でファイル存在を確認。不在なら不足リストに追加。

### artifact (参照依存・skill では直接チェックしない)

- `.cache/alpha_factory/runs/winners_latest.json`
- `.cache/alpha_factory/runs/candidates_latest.json`

これらは Phase 0-3 で run_args 構築時に参照されるが、`run_ga.py` 起動時に存在チェックされる責務。本 skill では事前存在を必須とせず、`run_ga.py` のエラーを尊重する。

### related skill (必須)

- `/zenigame-fx-snapshot`
- `/zenigame-fx-calibrate-gate`
- `/zenigame-fx-run-alpha-factory`
- `/zenigame-fx-run-report`

各 related skill は `ls .claude/skills/{skill_name}/SKILL.md` でファイル存在を確認。不在なら不足リストに追加。

#### executable 状態の判定方針

理想的には各 related skill が `executable=executable` であることを確認したいが、現時点では skill メタデータに executable 状態を保持する仕組みは存在しない。本 skill では暫定的に **「`SKILL.md` ファイルが存在 = 利用可能」** として扱う。

related skill 内で更にその skill の依存が abort される場合、その時点で連鎖的に batch-ga も停止する（ベストエフォート）。将来的に skill メタデータに `executable` フィールドを追加する別 TODO で精緻化する。

### 注意（依存ではない）

- `/zenigame-fx-improve-cycle` は本 skill から呼び出さない（コード凍結が前提）。**依存リストに含めない**
- `/zenigame-fx-post-run-review` はバッチ中スキップ対象であり、依存ではない（スキル不在でも batch-ga は動作可能）

zenigame 側スクリプト・skill をフォールバック参照しない。

---

## 引数

| 引数 | デフォルト | 説明 |
|------|----------|------|
| `--n` | 10 | 実行回数 |
| `--calibrate` | off | 各 Run 間に calibrate-gate を実行 |
| `--label` | なし | バッチのラベル（比較用） |
| `--snapshot-before` | なし | バッチ開始前にスナップショット作成 |
| `--run-args` | 前回 Run 設定 | GA 実行引数（`/zenigame-fx-run-alpha-factory` に渡す） |
| `--resume` | なし | 中断バッチの再開（batch_id 指定） |

---

## コンテキスト圧縮対策

長時間のバッチ実行中にコンテキスト圧縮が発生する。**状態ファイル** `batch_state.json` を各ステップで更新し、圧縮復帰時に読み込んで再開する。

**圧縮復帰手順**: コンテキスト圧縮後に状態が不明になった場合:
1. `batch_state.json` を `Read` で読み込む
2. `current_run_index` と `runs` 配列から再開位置を特定
3. Phase 1 のループを再開位置から継続

---

## 実行フロー

### Phase 0: 初期化

**0-1. batch_id 生成**

```python
batch_id = f"batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
batch_dir = f".cache/alpha_factory/batch/{batch_id}"
```

`batch_dir/metrics/` ディレクトリも作成する。

```bash
mkdir -p .cache/alpha_factory/batch/{batch_id}/metrics
```

**0-2. スナップショット（任意）**

`--snapshot-before` 指定時:
```
/zenigame-fx-snapshot create {snapshot_name}
```

**0-3. run_args 決定**

`--run-args` が明示指定されていない場合、最新の Run レポートから設定を取得する:
```bash
latest_n=$(uv run python scripts/alpha_factory/get_latest_run_number.py) || exit 1
latest_report=$(find reports/run-reports -maxdepth 2 -name "run-${latest_n}.md" -not -path '*/old/*' | head -1)
```
取得した「実行パラメータ」テーブルからコマンド引数を組み立てる。

**重要**: バッチ実行時は以下を自動付与:
- `--load-winners .cache/alpha_factory/runs/winners_latest.json`
- `--load-candidates .cache/alpha_factory/runs/candidates_latest.json`
- `--llm-mutation 0.05 --llm-cooldown 3`
- `--warmstart-auto`（前回 Run からの引き継ぎ）

**0-4. batch_state.json 書き込み**

`Write` ツールで `{batch_dir}/batch_state.json` を作成:
```json
{
  "batch_id": "batch_20260303_150000",
  "label": "baseline",
  "total_runs": 10,
  "completed_runs": 0,
  "current_run_index": 0,
  "status": "running",
  "run_args": "--pop-size 96 --generations 60 ...",
  "calibrate": true,
  "snapshot_name": "pre-experiment",
  "runs": [],
  "started_at": "2026-03-03T15:00:00+09:00",
  "last_updated": "2026-03-03T15:00:00+09:00"
}
```

**ユーザーに報告**:
```
## バッチ GA 開始
- batch_id: {batch_id}
- 実行回数: {n}
- ラベル: {label}
- calibrate: {on/off}
- スナップショット: {snapshot_name or なし}
- run_args: {run_args}
```

---

### Phase 1: 連続 GA ループ (i = 1..N)

以下を N 回繰り返す。

**1-1. batch_state.json 更新**

`current_run_index = i` に更新。

**1-2. キャリブレーション（任意）**

`i > 1` かつ `--calibrate` が有効の場合:
```
/zenigame-fx-calibrate-gate {prev_run_id}
```

calibrate 前後の `stage_b_ratio` を記録しておく（runs 配列に含める）。

**1-3. GA 実行**

`/zenigame-fx-run-alpha-factory` と同等の手順で GA 実行する。ただし以下をスキップ:
- **Step 7（ゲノムアーカイブ分析）**: 代わりに extract_batch_metrics.py（軽量 10 秒）を使用
- **Step 8（繰り返しモード）**: batch-ga 側で制御するためスキップ

具体的には `/zenigame-fx-run-alpha-factory` の Step 1〜6 を実行する:
1. 前提条件確認
2. バックグラウンド実行: `uv run python scripts/alpha_factory/run_ga.py {run_args}`
3. ログ監視ループ（エラー時のみ報告）
4. 完了検出
5. 結果確認（run_id 取得）
6. 結果報告（**簡潔に**: C-PASS 数、B-PASS 数、Best B-Sharpe のみ）

**1-4. 軽量メトリクス抽出**

```bash
uv run python scripts/alpha_factory/extract_batch_metrics.py {run_id} \
  --output .cache/alpha_factory/batch/{batch_id}/metrics/{run_id}.json \
  --report .cache/alpha_factory/batch/{batch_id}/reports/{run_id}.md
```

**1-5. レポート生成（`/zenigame-fx-run-report` スキル呼び出し）**

バッチでも正式レポートと同じ品質で生成する。Mission Dashboard 等の全セクションが含まれる。

```
/zenigame-fx-run-report --run_id {run_id}
```

**注意**: レポート生成は GA 回転のクリティカルパスに入る。レポート生成中に次の Run を開始することはしない（前 Run のレポートが正しく生成されることを保証するため）。

**1-6. batch_state.json 更新**

```json
{
  "runs": [
    ...既存...,
    {
      "index": i,
      "run_id": "run_YYYYMMDD_HHMMSS",
      "status": "completed",
      "c_pass_count": 15,
      "b_pass_count": 42,
      "best_b_sharpe": 0.4523,
      "calibrate_before": 0.15,
      "calibrate_after": 0.17
    }
  ],
  "completed_runs": i,
  "last_updated": "..."
}
```

**1-7. 進捗報告**

```
Run {i}/{N}: C-PASS={c_pass_count}, B-PASS={b_pass_count}, Best B-Sharpe={best_b_sharpe:.4f}
```

**エラーハンドリング**:

| シナリオ | 対応 |
|---------|------|
| GA run 失敗 | エラーログ記録、`runs[i].status="failed"`、次 Run へ進む |
| 連続 3 回失敗 | **バッチ中断**: ユーザーに報告して停止 |
| 成功率 50% 未満（4 回以上完了後） | **バッチ中断**: ユーザーに報告して停止 |
| メトリクス抽出失敗 | 警告表示、metrics=null、次 Run へ進む |

---

### Phase 2: 集計

**2-1. クロスラン集計レポート生成**

```bash
uv run python scripts/alpha_factory/compare_batch_runs.py --batch-dir .cache/alpha_factory/batch/{batch_id}
```

**2-2. batch_state.json 最終更新**

`status` を `"completed"` に更新。

**2-3. ユーザーに集計レポート表示**

`{batch_dir}/comparison_report.md` を `Read` で読み込んで表示する。

---

### Phase 3: 再開 (`--resume` 時)

**3-1. batch_state.json 読み込み**

```bash
cat .cache/alpha_factory/batch/{batch_id}/batch_state.json
```

**3-2. 再開位置の特定**

- `status="running"` の run は再実行
- `current_run_index` から Phase 1 ループを再開

---

## ストレージ

```
.cache/alpha_factory/batch/{batch_id}/
  batch_state.json          # 進捗管理（再開用）
  metrics/                  # Per-run メトリクス JSON
    run_YYYYMMDD_HHMMSS.json
  reports/                  # Per-run 軽量 Markdown レポート
    run_YYYYMMDD_HHMMSS.md
  comparison_report.md      # バッチ完了後の集計レポート
  batch_summary.json        # 集計メトリクス
```

---

## Before/After ワークフロー（使い方ガイド）

```bash
# Step 1: ベースライン 10 回
/zenigame-fx-batch-ga --n 10 --calibrate --label baseline --snapshot-before pre-experiment

# Step 2: ユーザーがコード変更を実施

# Step 3: トリートメント 10 回
/zenigame-fx-batch-ga --n 10 --calibrate --label treatment

# Step 4: Before/After 比較
uv run python scripts/alpha_factory/compare_batch_runs.py \
  --baseline .cache/alpha_factory/batch/{baseline_batch_id} \
  --treatment .cache/alpha_factory/batch/{treatment_batch_id}

# Step 5: 壊滅した場合のロールバック
/zenigame-fx-snapshot restore pre-experiment
```

---

## 注意事項

- **zenigame-fx-post-run-review はバッチ中全スキップ**（GA 回転速度最優先）
- **zenigame-fx-improve-cycle は呼び出さない**（コード凍結が前提）
- `current_run_state.json` は各 Run 中のみ使用（batch_state.json とは別管理）
- ロックファイル `alpha_factory.lock` による排他制御は通常通り有効
