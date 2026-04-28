#!/bin/bash
# T057 Phase 2 Gate C: aux データ一括取得 wrapper.
#
# 使用例:
#   scripts/fetch_aux_data.sh                                # default 期間で取得
#   scripts/fetch_aux_data.sh 2025-08-01 2026-04-30          # 期間指定
#
# 取得対象:
#   1. FRED 9 series (DEFAULT_SERIES と同期):
#      VIXCLS, DTWEXBGS, DGS10, DGS2, T10YIE,
#      DCOILWTICO, PCOPPUSDM, PALLFNFINDEXM, SP500
#      (GOLDPMGBD228NLBM は FRED で discontinued → step 2 で Yahoo 経由取得)
#   2. Yahoo Finance Gold Futures (GC=F) daily → MacroIndexDaily.GC_F_YAHOO
#   3. aux pair bars (M1): EUR_USD, USD_JPY
#   4. economic events: data/raw/calendar/events.csv (手動 scaffold) の DB upsert
#
# preflight check が `run_ga.py` 起動時に走るので、欠落時は明確な error log で判定可能。

set -euo pipefail

# Stage B 18 ヶ月 history を含めて余裕を持たせる。
# Codex impl-review-round-1 [Suggestion] 反映: END 既定を 「今日 (UTC)」 に動的化
# (固定 2026-04-30 だと 2026-05 以降 stale 化するため運用事故リスクが高い).
START="${1:-2024-08-01}"
END="${2:-$(date -u '+%Y-%m-%d')}"
LOG="/tmp/fetch_aux_data_$(date +%Y%m%d_%H%M%S).log"

echo "[1/4] FRED series fetch (9 series, GOLD は別経路)..." | tee -a "$LOG"
# scripts/fetch_fred.py:DEFAULT_SERIES と同期 (GOLDPMGBD228NLBM は FRED 廃止のため除外)
uv run python scripts/fetch_fred.py \
    --from "$START" --to "$END" \
    --series VIXCLS,DTWEXBGS,DGS10,DGS2,T10YIE,DCOILWTICO,PCOPPUSDM,PALLFNFINDEXM,SP500 \
    2>&1 | tee -a "$LOG"

echo "[2/4] Yahoo Finance Gold Futures (GC=F) daily..." | tee -a "$LOG"
uv run python scripts/fetch_gold_daily.py \
    --from "$START" --to "$END" \
    2>&1 | tee -a "$LOG"

echo "[3/4] Aux pair bars fetch (EUR_USD / USD_JPY)..." | tee -a "$LOG"
for pair in EUR_USD USD_JPY; do
    echo "  fetching $pair M1 bars..." | tee -a "$LOG"
    uv run python scripts/fetch_historical.py \
        --instrument "$pair" --start "$START" --end "$END" \
        2>&1 | tee -a "$LOG"
done

echo "[4/4] Economic events load..." | tee -a "$LOG"
EVENTS_CSV="data/raw/calendar/events.csv"
if [ -f "$EVENTS_CSV" ]; then
    uv run python scripts/load_economic_events.py \
        --csv "$EVENTS_CSV" 2>&1 | tee -a "$LOG"
else
    echo "  [warn] $EVENTS_CSV not found, skip events load" | tee -a "$LOG"
fi

echo "[done] aux data ready for production RUN. Log: $LOG" | tee -a "$LOG"
