#!/bin/bash
# B step 1.8 memory / performance smoke (= acceptance B2 / B3 merge 条件、
# 詳細設計 § 12.3 SSOT)。
#
# psutil sampler を background で起動して per-worker RSS を計測 (= SSOT)。
# /usr/bin/time -l は補助観測 (= macOS では process group max RSS の挙動が
# OS 依存のため SSOT としては使わない)。
#
# Usage:
#   ./scripts/smoke/measure_step1.8_memory.sh [N_RUNS=5]
#
# Round 5 [Suggestion 施策 6] 反映: psutil sampler の sampler 自身 PID 除外 +
# 対象 root process は cmdline 一致の最も早く起動した process を sample。

set -euo pipefail

N_RUNS=${1:-5}
LOG_DIR="reports/smoke/step1.8"
mkdir -p "$LOG_DIR"

# stale file contamination guard (= Codex impl-review Round 4 [Critical 1] 反映、
# 過去 run の run-*.log / sample-*.jsonl が残ったまま再実行されると、
# 現在 run の sampler 失敗を aggregate が見逃す可能性があるため初期化)
rm -f "$LOG_DIR"/run-*.log "$LOG_DIR"/sample-*.jsonl

for i in $(seq 1 "$N_RUNS"); do
    echo "=== run $i / $N_RUNS ==="

    # psutil による per-worker RSS sampling を background で開始
    # (= sampled_max_worker_rss SSOT 指標を取得、 acceptance B2 主条件)。
    # sampler 側で create_time guard (= sampler 起動時刻以後の process 限定) を
    # かけているため、 既存の別 run_ga が残っていても捕捉しない設計
    # (= Codex impl-review Round 2 [Warning 施策 6] 反映)。
    uv run python scripts/smoke/sample_worker_rss.py \
        --output "$LOG_DIR/sample-$i.jsonl" \
        --interval 1.0 \
        --target-cmdline "src.alpha_factory.run_ga" \
        --run-index "$i" &
    SAMPLER_PID=$!

    # /usr/bin/time -l で参考 RSS / wall time を取得 (= 補助指標、 macOS では
    # 解釈に注意、 詳細設計 § 12.3)
    /usr/bin/time -l uv run python -m src.alpha_factory.run_ga \
        --config config/alpha_factory/default.yaml \
        --smoke \
        2>&1 | tee "$LOG_DIR/run-$i.log"

    # sampler を停止
    kill "$SAMPLER_PID" 2>/dev/null || true
    wait "$SAMPLER_PID" 2>/dev/null || true
done

# peak RSS / wall time 集計 (= max / mean を計算、 step 1.7 比較)
# Round 2 [Warning 施策 6] 反映: python3 直呼びを uv run python に統一
# Round 3 [Warning 施策 6] 反映: psutil sampling 結果を主指標として併合
echo
echo "=== aggregating ==="
uv run python scripts/smoke/aggregate_step1.8_memory.py "$LOG_DIR"
