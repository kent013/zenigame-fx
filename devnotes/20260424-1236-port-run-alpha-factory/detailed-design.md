# 詳細設計: zenigame-fx-run-alpha-factory skill

参照: `conceptual-design.md`（APPROVED, 2026-04-24）

## 成果物

`.claude/skills/zenigame-fx-run-alpha-factory/SKILL.md`（md only、新規 1 ファイル）

## SKILL.md ファイル構造

### 1. YAML フロントマター

```yaml
---
name: zenigame-fx-run-alpha-factory
description: zenigame-fx Alpha Factory GA 実行（バックグラウンド）+ ログ監視 + 完了検出 + 結果確認
argument-hint: "<run_ga.py args> [--timeout-min N]"
---
```

- `user-invocable` フィールドは付けない（デフォルト `true` でユーザー直接呼び出し可能）
- `description` は zenigame 版に近づけつつ fx であることを明示

### 2. セクション構成

```
# zenigame-fx Alpha Factory GA 実行

[使命・思考原則・禁止事項の継承メモ → zenigame-fx-codex-review SKILL.md 参照と書く]

## 引数
[テーブル: --instrument, --population-size, --generations, --timeout-min ほか]

## 呼び出し契約
[skill → scripts/alpha_factory/run_ga.py のラップ関係を図示]

## 状態ファイル
[.cache/alpha_factory/run_alpha_factory_state.json の責務とフォーマット]

## 重要ルール
- BG 実行必須
- --run-id は skill 側で生成して passthrough
- 日時は JST（state file の started_at / last_updated）
- summary.json パスは [done] stdout から確定（_estimate を配置予測に使わない）
- improve-cycle の current_cycle_state.json は触らない

## 実行手順
### Step 0: 引数バリデーション
### Step 1: 前提検証
### Step 2: バックグラウンド実行
### Step 3: ログ監視ループ
### Step 4: 完了検出 (3 点整合)
### Step 5: 結果確認
### Step 6: 報告
### Step 7: 失敗時の経路

## エラーハンドリング

## トラブルシューティング

## 参考情報
```

## 各 Step の詳細仕様

### Step 0: 引数バリデーション

- skill 引数を 2 種に分類:
  - **skill 自身の引数**: `--timeout-min N`（既定 60）
  - **passthrough 引数**: それ以外すべて → run_ga.py に丸投げ
- 必須パラメータ: なし（run_ga.py 側のデフォルトに従う）
- 推奨パラメータ警告: `--instrument` が指定されていない場合は warn（run_ga.py 側 default は config 経由で決まるため fail はしない）

#### 二重起動防止（PID 再利用誤検知対策）

`.cache/alpha_factory/run_alpha_factory_state.json` が存在し `status == "running"` の場合、以下の **2 段階確認**で PID 再利用による誤検知を回避:

1. **PID 生存確認**: `kill -0 ${pid} 2>/dev/null` で生存確認
2. **cmdline 検証**: 生存している場合、プロセスの cmdline に `run_ga.py` と state file の `run_id` の両方が含まれているか確認
   - macOS: `ps -p ${pid} -o command= | grep -q "run_ga.py" && ps -p ${pid} -o command= | grep -q "${run_id}"`
   - Linux: `tr '\0' ' ' < /proc/${pid}/cmdline 2>/dev/null | grep -q "run_ga.py.*${run_id}"`
3. 両方満たす → 真の二重起動として **エラー終了**
4. PID は生きているが cmdline 不一致 → PID 再利用と判定し state file を `status=stale` に更新後、新規 run を開始
5. PID 不在 → 前回 run が異常終了した残骸として state file を `status=stale` に更新後、新規 run を開始

### Step 1: 前提検証

```bash
# 出力先ディレクトリの書込権限
mkdir -p reports/run-reports
mkdir -p .cache/alpha_factory/runs
test -w reports/run-reports || exit 1

# DB 接続軽チェック（任意）— 失敗してもログに warning のみ
uv run python -c 'from src.db.connection import SessionLocal; SessionLocal().close()' 2>&1 | head -5 || true
```

### Step 2: バックグラウンド実行

```bash
# 1) run_id 生成（JST ではなく UTC で run_ga.py のデフォルトに合わせる）
run_id="run_$(TZ=UTC date +%Y%m%d_%H%M%S)"

# 2) ログファイルパス確定
log_file=".cache/alpha_factory/runs/${run_id}.log"

# 3) 状態ファイルを Write で初期化（status=starting）
#    Write ツール使用、bash の echo は使わない

# 4) BG 起動
nohup uv run python scripts/alpha_factory/run_ga.py \
  --run-id "${run_id}" \
  {passthrough_args} \
  > "${log_file}" 2>&1 &
pid=$!
disown

# 5) 状態ファイル更新（status=running, pid, started_at）
```

**重要**: skill 内で Bash の `echo` で JSON を書いてはならない（AGENTS.md `Write` 推奨ルール）。**Write ツール**で更新する。

### Step 3: ログ監視ループ

```bash
# ループ変数
timeout_sec=$((timeout_min * 60))
elapsed=0
poll_interval=30
exit_reason=""  # "process_exit" / "error_detected" / "done_detected" / "timeout"

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

# ループ脱出後の分岐
if [ -z "${exit_reason}" ]; then
  exit_reason="timeout"
fi

# exit_reason ごとの遷移先:
#   done_detected → Step 4
#   process_exit  → Step 4 (3 点整合 OK なら正常完了、NG なら Step 7)
#   error_detected → Step 7（プロセスを kill して error 抽出）
#   timeout       → Step 7（プロセスを kill して timeout 報告）
#   状態ファイルに exit_reason を記録（status はまだ running のまま、Step 4/7 で確定）
```

**context 節約ルール（zenigame 版から継承）**:
- 正常進行中はユーザーへの中間報告を一切行わない
- ログ全文を context に読み込まない（必ず grep でフィルタしてから読む）

### Step 4: 完了検出（run_id 4 点整合）

run_ga.py が同一 `run_id` を伝搬する 4 経路（log の `ga.run.done` / archive Parquet ファイル名 / `[done]` stdout / summary.json 内 `run_id`）を全て検証。

```bash
# (a) ga.run.done log + run_id 一致
if ! grep -F "ga.run.done" "${log_file}" | grep -q "${run_id}"; then
  echo "FAIL: ga.run.done log line not found or run_id mismatch"
  goto Step7  # 失敗理由: "no_done_log"
fi

# (b) archive Parquet 存在（ファイル名で run_id バインド）
parquet=".cache/alpha_factory/runs/genomes_${run_id}.parquet"
if ! [ -f "${parquet}" ]; then
  echo "FAIL: archive Parquet not found: ${parquet}"
  goto Step7  # 失敗理由: "no_parquet"
fi

# (c-1) [done] stdout 行の存在確認
done_line=$(grep -F '[done]' "${log_file}" | tail -1)
if [ -z "${done_line}" ]; then
  echo "FAIL: [done] stdout line not found in log"
  goto Step7  # 失敗理由: "no_done_stdout"
fi

# (c-2) report=... 抽出
run_dir=$(printf '%s\n' "${done_line}" | sed -E 's/.*report=([^ ]+).*/\1/')
if [ -z "${run_dir}" ] || [ "${run_dir}" = "${done_line}" ]; then
  # sed 不一致時は元行がそのまま返る → 抽出失敗
  echo "FAIL: report= path could not be extracted from [done] line"
  goto Step7  # 失敗理由: "report_extract_failed"
fi

# (c-3) summary.json 存在
summary_path="${run_dir}/summary.json"
if ! [ -f "${summary_path}" ]; then
  echo "FAIL: summary.json not found at ${summary_path}"
  goto Step7  # 失敗理由: "no_summary"
fi

# (c-4) summary.json 内 run_id 一致
summary_run_id=$(uv run python -c "import json; print(json.load(open('${summary_path}'))['run_id'])")
if [ "${summary_run_id}" != "${run_id}" ]; then
  echo "FAIL: summary.json run_id mismatch (${summary_run_id} != ${run_id})"
  goto Step7  # 失敗理由: "run_id_mismatch"
fi
```

**run_id 伝搬チェック点（仕様）**:
1. log の `ga.run.done ... run_id=...` に skill 側 run_id が含まれる
2. archive Parquet ファイル `genomes_${run_id}.parquet` が存在
3. `[done] ... report=...` stdout 行が存在し `report=` パスが抽出可能
4. そのパス配下の `summary.json` の `run_id` フィールドが skill 側 run_id と一致

4 点全て満たして初めて `status=completed` に遷移。

### Step 5: 結果確認

`<<'PY'` の quoted heredoc はシェル変数展開を抑止するため、**環境変数経由**でパスを渡す（誤って `${summary_path}` がリテラルにならないよう）。

```bash
# summary.json から指標抽出（環境変数で path を渡す）
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

- live_criteria 達成判定は本 skill では行わない（`zenigame-fx-run-report` / `analyze-run` 側の責務）
- 状態ファイルを `status=completed` で更新

### Step 6: 報告

ユーザー向けレポート（簡潔・ASCII 装飾なし）:

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

失敗理由（`failure_reason`）を Step 3/4 から引き継ぎ、状態ファイルに記録。
プロセスが生きていれば **猶予待ちループ + プロセスグループ停止**で確実に終了させる。

```bash
# 1) プロセス停止（プロセスグループ単位で監視・猶予待ち・SIGKILL）
#    親 PID 単独監視だと、親終了後に子プロセス（worker subprocess 等）が残った場合に見逃す。
#    必ず PGID 基準で「グループ全体の生存確認」を行う。

pgid=$(ps -o pgid= -p ${pid} 2>/dev/null | tr -d ' ')

# helper: プロセスグループに 1 つでも生きているプロセスがあるか
group_alive() {
  if [ -n "${pgid}" ]; then
    # kill -0 -<pgid> はプロセスグループ全体に signal 0 を送り、
    # 1 つでも残っていれば成功 (rc=0)。全滅していれば失敗 (rc=1)。
    kill -0 -"${pgid}" 2>/dev/null
  else
    kill -0 "${pid}" 2>/dev/null
  fi
}

if group_alive; then
  # SIGTERM をプロセスグループに送る（子孫プロセスも対象）
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

  # グループにまだプロセスが残っていれば SIGKILL を投下
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

# 3) 状態ファイル更新
#    status=failed
#    completed_at=<現在時刻 JST>     ← schema フィールド名は completed_at で統一
#    failure_reason=<exit_reason or 4 点整合の失敗種別>
#    error_excerpt=<上記抽出>
#    （`ended_at` は使わない）

# 4) ユーザー報告（失敗時テンプレート）
echo "## Alpha Factory GA 実行失敗"
echo "- run_id: ${run_id}"
echo "- failure_reason: ${failure_reason}"
echo "- log: ${log_file}"
echo "### error excerpt"
echo "${error_excerpt}"
```

**設計意図**:
- `completed_at` は status が `completed` でも `failed` でも「終端時刻」として使う（schema 統一）。`ended_at` は使わない
- プロセスグループ停止により worker / subprocess のオーファン化を防ぐ
- 猶予待ちは 1 秒×30 ループ（最大 30 秒）。run_ga.py の archive flush は数秒〜十数秒かかり得るため `sleep 2` 固定では不足

## 状態ファイル: 完全フォーマット

`.cache/alpha_factory/run_alpha_factory_state.json`

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

### `status` 遷移

```
starting  ─→  running  ─┬─→  completed   (4 点整合 OK)
                        ├─→  failed      (error_detected / no_done_log / no_parquet /
                        │                  no_done_stdout / report_extract_failed /
                        │                  no_summary / run_id_mismatch / timeout)
                        └─→  stale       (二重起動防止チェックで PID 不在 / cmdline 不一致と判明)
```

### フィールド意味

| field | 設定タイミング | 意味 |
|-------|--------------|------|
| `status` | 各遷移点で更新 | `starting` / `running` / `completed` / `failed` / `stale` |
| `step` | 各 Step 開始時 | `validate` / `precheck` / `start_bg` / `monitor` / `verify` / `report` / `cleanup` |
| `run_number_estimate` | Step 0 時点 | `get_latest_run_number()+1` の事前推定値（参考のみ） |
| `run_number` | Step 4 完了時 | summary.json の `run_number` を SoT として確定 |
| `summary_path` | Step 4 完了時 | `[done]` 行から抽出した run_dir 配下 |
| `archive_path` | Step 4 完了時 | `.cache/alpha_factory/runs/genomes_${run_id}.parquet` |
| `exit_reason` | Step 3 ループ脱出時 | `process_exit` / `error_detected` / `done_detected` / `timeout` |
| `failure_reason` | Step 7 進入時 | `exit_reason` または 4 点整合の失敗種別（上記 status 表参照） |
| `completed_at` | `completed` / `failed` 遷移時 | 終端時刻 JST。`ended_at` は使わない |
| `error_excerpt` | `failed` 遷移時 | log から抽出した最大 50 行 |

## 関連 skill との結合

```
[user / improve-cycle]
        |
        v
/zenigame-fx-run-alpha-factory  ← 本 skill (新規)
        |
        v
scripts/alpha_factory/run_ga.py (T018)
        |
        +--> .cache/alpha_factory/runs/genomes_{run_id}.parquet
        +--> reports/run-reports/run-{N}/summary.json
        +--> .cache/alpha_factory/runs/{run_id}.json
        +--> stdout: [done] ... report={run_dir}
```

完了後、ユーザーまたは improve-cycle が:
- `/zenigame-fx-run-report {N}` でレポート生成
- `scripts/alpha_factory/analyze_run.py --run-number {N}` で分析

を呼び分ける（本 skill から自動チェインしない＝疎結合）。

## 禁止事項（実装時）

- `docs/alpha-factory/`（ハイフン版）への参照を書かない（fx は `docs/alpha_factory/` アンダースコア版）
- `src/trading/` 配下のスクリプト（zenigame 由来）を呼ばない
- `/zenigame-codex-review`、`/zenigame-codex-vscode`、`/zenigame-analyze-genome-archive` 等の zenigame skill を参照しない
- `~/.local/bin/codex-vscode` のような外部バイナリ直接パスを書かない（scripts/codex 経由のみ）
- LLM 変異 / Director / cost-stress / DSR / smoke-test / profile / warmstart / validate-only の項目を書かない（run_ga.py 未対応）
- ショート禁止条項を書かない（fx は両方向許容）

## verify

実装完了後の検証コマンド:

```bash
# (1) ファイル存在
test -f .claude/skills/zenigame-fx-run-alpha-factory/SKILL.md

# (2) zenigame 由来禁止参照ゼロ（必須仕様: タスク手順 D）
test "$(grep -cE 'docs/alpha-factory|src/trading|/zenigame-codex|~/.local/bin/codex-vscode|/zenigame-analyze-genome-archive|/zenigame-codex-review' .claude/skills/zenigame-fx-run-alpha-factory/SKILL.md)" = "0"

# (2-bis) 削除 zenigame オプション群への言及禁止（拡張）
test "$(grep -ciE 'llm-mutation|llm-cooldown|director-mode|cost-stress|--dsr|entry-delay-test|--profile\b|smoke-test|warmstart|validate-only|analyze-genome-archive' .claude/skills/zenigame-fx-run-alpha-factory/SKILL.md)" = "0"

# (3) 必須要素
grep -q 'scripts/alpha_factory/run_ga.py' .claude/skills/zenigame-fx-run-alpha-factory/SKILL.md
grep -q 'run_alpha_factory_state.json' .claude/skills/zenigame-fx-run-alpha-factory/SKILL.md
grep -q 'ga.run.done' .claude/skills/zenigame-fx-run-alpha-factory/SKILL.md
grep -q 'genomes_${run_id}.parquet' .claude/skills/zenigame-fx-run-alpha-factory/SKILL.md
grep -q '\[done\]' .claude/skills/zenigame-fx-run-alpha-factory/SKILL.md
grep -q 'completed_at' .claude/skills/zenigame-fx-run-alpha-factory/SKILL.md
# 旧フィールド名 ended_at が混入していないこと
test "$(grep -c 'ended_at' .claude/skills/zenigame-fx-run-alpha-factory/SKILL.md)" = "0"

# (4) AGENTS.md 更新
grep -q 'zenigame-fx-run-alpha-factory' AGENTS.md
```

## 行数目安

zenigame 版が 623 行、fx 版は LLM/Director/cost-stress/profile/smoke/warmstart/validate-only 等を削除し、状態ファイル責務分離・3 点整合検出を追加するため、おおよそ **250-330 行** を目標。

過度に詳細化せず、運用に必要な手順とエラーハンドリングに絞る。
