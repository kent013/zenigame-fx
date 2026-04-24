---
name: zenigame-fx-run-alpha-factory
description: zenigame-fx Alpha Factory GA 実行（バックグラウンド）+ ログ監視 + 完了検出 + 結果確認
argument-hint: "<run_ga.py args> [--timeout-min N]"
---

# zenigame-fx Alpha Factory GA 実行

`scripts/alpha_factory/run_ga.py` をバックグラウンドで起動し、ログ監視 → 完了検出 → 結果確認 → 報告までを一括で行う。`zenigame-fx-improve-cycle` Phase 3 やユーザー直接呼び出しから利用される。

## 使命・思考原則・禁止事項

`zenigame-fx-codex-review` SKILL.md で定義される使命・禁止事項・C1-C9 discipline を継承。重複記載しない。

**FX 固有の絶対制約**: イントラデイ前提 / ロング・ショート両方向許容 / スワップ・スプレッドを fitness に反映。

## 引数

| 引数 | 必須 | 説明 |
|------|------|------|
| `--timeout-min N` | No | skill 自身の引数。BG 起動から完了までの上限分（既定 60） |
| その他 | No | すべて `scripts/alpha_factory/run_ga.py` に passthrough |

passthrough 対象の主な run_ga.py 引数（一覧は `uv run python scripts/alpha_factory/run_ga.py --help`）:
`--config`, `--instrument`, `--start`, `--end`, `--population-size`, `--generations`,
`--mutation-rate`, `--crossover-rate`, `--tournament-size`, `--elite-count`,
`--max-depth`, `--fitness-metric`, `--seed`

`--run-id` は **skill が自動生成して付与**する。引数で指定された場合も skill 側で上書きされる（log/state とのバインドを保証するため）。

## 呼び出し契約

```
[user / zenigame-fx-improve-cycle Phase 3]
        |
        v
/zenigame-fx-run-alpha-factory  ← 本 skill
        |
        v
scripts/alpha_factory/run_ga.py (T018)
        |
        +--> .cache/alpha_factory/runs/genomes_{run_id}.parquet
        +--> reports/run-reports/run-{N}/summary.json
        +--> .cache/alpha_factory/runs/{run_id}.json
        +--> stdout: [done] ... report={run_dir}
```

完了後の後続処理（レポート生成・分析）は本 skill から自動チェインしない。呼び出し側が必要に応じて
`/zenigame-fx-run-report {N}` または `scripts/alpha_factory/analyze_run.py --run-number {N}`
を呼び分ける（疎結合）。

## 状態ファイル

`.cache/alpha_factory/run_alpha_factory_state.json`

`zenigame-fx-improve-cycle` が使う `current_cycle_state.json` とは**別ファイル**で責務を分離する:

| ファイル | 責務 | source-of-truth |
|---------|------|----------------|
| `current_cycle_state.json` | improve-cycle の orchestration state（cycle_index / phase / history） | improve-cycle skill |
| `run_alpha_factory_state.json` | 単一 GA run の execution state（PID / run_id / log path / status） | 本 skill |

復旧時は両ファイルを併読する。本 skill は `current_cycle_state.json` を **絶対に書き換えない**。

### スキーマ（v1）

```json
{
  "skill": "zenigame-fx-run-alpha-factory",
  "schema_version": 1,
  "status": "running",
  "step": "monitor",
  "pid": 12345,
  "run_id": "run_20260424_123600",
  "run_number_estimate": 6,
  "run_number": null,
  "log_file": ".cache/alpha_factory/runs/run_20260424_123600.log",
  "args_passthrough": ["--instrument", "USD_JPY", "--population-size", "48"],
  "timeout_min": 60,
  "started_at": "2026-04-24T12:36:00+09:00",
  "last_updated": "2026-04-24T12:36:00+09:00",
  "completed_at": null,
  "summary_path": null,
  "archive_path": null,
  "exit_reason": null,
  "failure_reason": null,
  "error_excerpt": null
}
```

`status` 遷移:

```
starting --> running --+--> completed   (run_id 4 点整合 OK)
                       +--> failed      (異常検知 / 整合 NG / timeout)
                       +--> stale       (二重起動防止チェックで判明した古い state)
```

主要フィールド:

| field | 設定タイミング | 意味 |
|-------|--------------|------|
| `status` | 各遷移点 | starting / running / completed / failed / stale |
| `step` | 各 Step 開始時 | validate / precheck / start_bg / monitor / verify / report / cleanup |
| `run_number_estimate` | Step 2 | `get_latest_run_number()+1` の推定値（参考のみ。配置先予測には使わない） |
| `run_number` | Step 4 完了時 | summary.json の `run_number` を SoT として確定 |
| `summary_path` | Step 4 完了時 | `[done]` 行から抽出した run_dir 配下 |
| `archive_path` | Step 4 完了時 | `genomes_{run_id}.parquet` |
| `exit_reason` | Step 3 ループ脱出時 | process_exit / error_detected / done_detected / timeout |
| `failure_reason` | Step 7 進入時 | exit_reason または 4 点整合の失敗種別 |
| `completed_at` | completed / failed 遷移時 | 終端時刻 JST（completed / failed どちらでもこのフィールドに記録、別名は作らない） |
| `error_excerpt` | failed 遷移時 | log から抽出した最大 50 行 |

**書き込みは Write ツール経由**。Bash の `echo > json` は使わない。

## 重要ルール

- **バックグラウンド実行必須**: `nohup ... &` + `disown`
- **`--run-id` は skill 側で生成**: `run_$(TZ=UTC date +%Y%m%d_%H%M%S)`。run_ga.py のデフォルト規則に合わせて UTC
- **summary.json パスは `[done] ... report={run_dir}` 行から確定**。`run_number_estimate` を配置先予測に使わない（並行 run 競合があり得る）
- **context 節約**: 正常進行中はユーザーへの中間出力を一切行わない。ログ全文を context に読み込まず、必ず `tail -n 100 | grep -E '...'` でフィルタしてから読む
- **二重起動防止**: state file `status==running` の場合は cmdline まで検証して PID 再利用を排除（手順 Step 0 参照）
- **JST タイムスタンプ**: `started_at` / `last_updated` / `completed_at` は `TZ=Asia/Tokyo date -Iseconds`

## 実行手順

### Step 0: 引数バリデーション + 二重起動防止

1. skill 自身の `--timeout-min N` を切り出し、残りを `args_passthrough` 配列に格納
2. `--instrument` が含まれていなければ warn（fail はしない）
3. `.cache/alpha_factory/run_alpha_factory_state.json` の存在チェック:
   - 不在 → 新規 run へ
   - `status != "running"` → 新規 run へ
   - `status == "running"` → 以下の **2 段階確認**:
     - (i) `kill -0 ${pid} 2>/dev/null` で PID 生存確認
     - (ii) cmdline に `run_ga.py` と state file の `run_id` の両方が含まれるか
       - macOS: `ps -p ${pid} -o command= | grep -q "run_ga.py" && ps -p ${pid} -o command= | grep -q "${run_id}"`
       - Linux: `tr '\0' ' ' < /proc/${pid}/cmdline 2>/dev/null | grep -q "run_ga.py.*${run_id}"`
     - (i) (ii) 両方成功 → 真の二重起動。**エラー終了**
     - (i) 成功 / (ii) 失敗 → PID 再利用と判定。state を `status=stale` で更新後、新規 run へ
     - (i) 失敗 → 残骸。state を `status=stale` で更新後、新規 run へ

### Step 1: 前提検証

```bash
mkdir -p reports/run-reports
mkdir -p .cache/alpha_factory/runs
test -w reports/run-reports || { echo "FAIL: reports/run-reports not writable"; exit 1; }

# DB 接続軽チェック（任意・失敗は warning のみ）
uv run python -c 'from src.db.connection import SessionLocal; SessionLocal().close()' 2>&1 | head -5 || true
```

### Step 2: バックグラウンド実行

1. `run_id` 生成: `run_id="run_$(TZ=UTC date +%Y%m%d_%H%M%S)"`
2. `log_file=".cache/alpha_factory/runs/${run_id}.log"`
3. `run_number_estimate=$(uv run python scripts/alpha_factory/get_latest_run_number.py)` + 1
4. **Write ツール**で state file を初期化（`status=starting`, `step=start_bg`, `pid=null`）
5. BG 起動（**`setsid` で新規プロセスグループ化**し、後続の Step 7 PGID 停止が親シェルや無関係プロセスを巻き込まないようにする）:

```bash
setsid nohup uv run python scripts/alpha_factory/run_ga.py \
  --run-id "${run_id}" \
  "${args_passthrough[@]}" \
  > "${log_file}" 2>&1 < /dev/null &
pid=$!
disown
```

`setsid` により `pgid == pid` となるため、Step 7 の `kill -TERM -${pgid}` は run_ga.py プロセスツリーのみを対象とする。親シェルの PGID とは分離される。

> macOS で `setsid` が利用不可な環境（古い coreutils 未インストール）の場合は、`python -c 'import os; os.setpgrp(); os.execvp(...)'` でも代替可能。

6. **Write ツール**で state を更新（`status=running`, `step=monitor`, `pid=${pid}`, `started_at=...`, `last_updated=...`）

### Step 3: ログ監視ループ

```bash
timeout_sec=$((timeout_min * 60))
elapsed=0
poll_interval=30
exit_reason=""

while [ $elapsed -lt $timeout_sec ]; do
  # (a) プロセス生存確認
  if ! kill -0 ${pid} 2>/dev/null; then
    exit_reason="process_exit"
    break
  fi

  # (b) ERROR / Traceback 検出（直近 100 行のみ、context 節約）
  errors=$(tail -n 100 "${log_file}" | grep -E 'ERROR|Traceback|Exception' | tail -5)
  if [ -n "${errors}" ]; then
    exit_reason="error_detected"
    break
  fi

  # (c) ga.run.done 検出
  if grep -q 'ga.run.done' "${log_file}"; then
    exit_reason="done_detected"
    break
  fi

  sleep ${poll_interval}
  elapsed=$((elapsed + poll_interval))
done

[ -z "${exit_reason}" ] && exit_reason="timeout"
```

`exit_reason` ごとの遷移先:

| exit_reason | 次 Step |
|-------------|--------|
| done_detected | Step 4（4 点整合 OK で completed） |
| process_exit | Step 4（OK なら completed、NG なら Step 7） |
| error_detected | Step 7（kill + error 抽出） |
| timeout | Step 7（kill + timeout 報告） |

state を **Write ツール**で更新（`exit_reason` 記録、`status` はまだ running のまま）。

### Step 4: 完了検出（run_id 4 点整合）

run_ga.py が同一 `run_id` を伝搬する 4 経路をすべて検証する:

1. log の `ga.run.done ... run_id=...` に skill 側 run_id が含まれる
2. archive Parquet ファイル `.cache/alpha_factory/runs/genomes_${run_id}.parquet` が存在
3. `[done] ... report=...` stdout 行が存在し `report=` パスが抽出可能
4. そのパス配下の `summary.json` の `run_id` フィールドが skill 側 run_id と一致

```bash
# (a) ga.run.done log + run_id 一致
if ! grep -F "ga.run.done" "${log_file}" | grep -q "${run_id}"; then
  failure_reason="no_done_log"
  goto Step7
fi

# (b) archive Parquet 存在
parquet=".cache/alpha_factory/runs/genomes_${run_id}.parquet"
if ! [ -f "${parquet}" ]; then
  failure_reason="no_parquet"
  goto Step7
fi

# (c-1) [done] stdout 行の存在
done_line=$(grep -F '[done]' "${log_file}" | tail -1)
if [ -z "${done_line}" ]; then
  failure_reason="no_done_stdout"
  goto Step7
fi

# (c-2) report=... 抽出
run_dir=$(printf '%s\n' "${done_line}" | sed -E 's/.*report=([^ ]+).*/\1/')
if [ -z "${run_dir}" ] || [ "${run_dir}" = "${done_line}" ]; then
  failure_reason="report_extract_failed"
  goto Step7
fi

# (c-3) summary.json 存在
summary_path="${run_dir}/summary.json"
if ! [ -f "${summary_path}" ]; then
  failure_reason="no_summary"
  goto Step7
fi

# (c-4) summary.json 内 run_id 一致
summary_run_id=$(SUMMARY_PATH="${summary_path}" uv run python -c 'import json,os; print(json.load(open(os.environ["SUMMARY_PATH"]))["run_id"])')
if [ "${summary_run_id}" != "${run_id}" ]; then
  failure_reason="run_id_mismatch"
  goto Step7
fi
```

4 点全て満たして初めて `status=completed` に遷移。Write ツールで state 更新（`run_number`, `summary_path`, `archive_path`, `completed_at`）。

### Step 5: 結果確認

`<<'PY'` quoted heredoc はシェル変数展開を抑止する。**環境変数経由で path を渡す**:

```bash
SUMMARY_PATH="${summary_path}" uv run python <<'PY'
import json, os
s = json.load(open(os.environ["SUMMARY_PATH"]))
print(f"run_number={s['run_number']}")
print(f"best_name={s['best']['name']}")
print(f"best_fitness={s['best']['fitness']}")
print(f"stage_a_pass={s['best']['stage_a_pass']}")
print(f"stage_b_pass={s['best']['stage_b_pass']}")
print(f"stage_c_pass={s['best']['stage_c_pass']}")
print(f"graduation_count={s.get('graduation_count', 0)}")
PY
```

live_criteria 達成判定は本 skill では行わない（`zenigame-fx-run-report` / `analyze_run.py` の責務）。

### Step 6: 報告

```
## Alpha Factory GA 実行完了

- run_id: {run_id}
- run_number: {run_number}
- log: .cache/alpha_factory/runs/{run_id}.log
- archive: .cache/alpha_factory/runs/genomes_{run_id}.parquet
- summary: reports/run-reports/run-{N}/summary.json

### Best 個体
- name: {best_name}
- fitness: {best_fitness}
- Stage A/B/C pass: {a}/{b}/{c}
- graduation_count: {gc}

### 次のステップ
- レポート生成: /zenigame-fx-run-report {run_number}
- 深層分析: scripts/alpha_factory/analyze_run.py --run-number {run_number}
```

### Step 7: 失敗時の経路

`failure_reason` を Step 3 / Step 4 から引き継ぎ、プロセスグループ単位で停止 → ログ抽出 → 報告。

```bash
# 1) プロセス停止（プロセスグループ基準で監視・猶予待ち・SIGKILL）
#    親 PID 単独監視だと、親終了後に子プロセスが残った場合に見逃す。
#    必ず PGID 基準で「グループ全体の生存確認」を行う。
pgid=$(ps -o pgid= -p ${pid} 2>/dev/null | tr -d ' ')

group_alive() {
  if [ -n "${pgid}" ]; then
    kill -0 -"${pgid}" 2>/dev/null
  else
    kill -0 "${pid}" 2>/dev/null
  fi
}

if group_alive; then
  if [ -n "${pgid}" ]; then
    kill -TERM -"${pgid}" 2>/dev/null || true
  else
    kill -TERM "${pid}" 2>/dev/null || true
  fi

  # 猶予待ち: 1 秒間隔で最大 30 秒（DB flush / Parquet write 完了を待つ）
  for i in $(seq 1 30); do
    group_alive || break
    sleep 1
  done

  if group_alive; then
    if [ -n "${pgid}" ]; then
      kill -KILL -"${pgid}" 2>/dev/null || true
    else
      kill -KILL "${pid}" 2>/dev/null || true
    fi
  fi
fi

# 2) ログから ERROR / Traceback / Exception を最大 50 行抽出
error_excerpt=$(tail -n 500 "${log_file}" | grep -E 'ERROR|Traceback|Exception|FATAL' -A 5 | tail -50)

# 3) 状態ファイル更新（Write ツール使用）
#    status=failed
#    completed_at=$(TZ=Asia/Tokyo date -Iseconds)
#    failure_reason=<exit_reason or 4 点整合の失敗種別>
#    error_excerpt=<上記抽出>
```

ユーザー報告:

```
## Alpha Factory GA 実行失敗

- run_id: {run_id}
- failure_reason: {failure_reason}
- log: .cache/alpha_factory/runs/{run_id}.log

### error excerpt
{error_excerpt}
```

## エラーハンドリング

| 事象 | 対処 |
|------|------|
| Step 1 で reports/ 書込不可 | 即時 fail |
| Step 1 で DB 接続失敗 | warning のみ。run_ga.py 自身が必要時に再試行 |
| Step 3 で `error_detected` | Step 7 で kill → error_excerpt 抽出 → status=failed |
| Step 3 で `timeout` | Step 7 で kill → status=failed, failure_reason=timeout |
| Step 4 各失敗種別 | Step 7 で status=failed, failure_reason=該当種別 |
| 二重起動検知（真） | Step 0 で即時 fail（既存 run の log を案内） |

## トラブルシューティング

- **状態ファイルが残ったまま skill が起動できない** → state file の `status` を確認し、本当に該当 PID が走っているかを `ps -p ${pid}` で確認。残骸なら state file を削除
- **summary.json は出ているが log の `[done]` 行が見つからない** → log buffering の遅延の可能性。`sleep 5` してから再 grep。それでもなければ run_ga.py 側に異常
- **`run_id_mismatch` で失敗** → 並行 run の summary.json を誤読している可能性。`grep -r "run_id" reports/run-reports/run-*/summary.json` で全件確認

## 参考情報

- run_ga.py: `scripts/alpha_factory/run_ga.py`（CLI 引数は `--help` 参照）
- archive 仕様: `src/alpha_factory/archive.py`（`genomes_{run_id}.parquet` の schema は T015）
- 関連 skill: `zenigame-fx-improve-cycle` Phase 3 から本 skill への切替は別 TODO（残課題）
- 関連 skill: `zenigame-fx-run-report`（レポート生成。本 skill から自動呼び出しはしない）
- 設計ノート: `devnotes/20260424-1236-port-run-alpha-factory/`
