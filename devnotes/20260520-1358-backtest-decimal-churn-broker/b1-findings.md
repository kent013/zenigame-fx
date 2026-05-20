# B-1 memory attribution 実測結果 + 結論 (2026-05-20)

## TL;DR
**候補 B (scaled-int による backtest hot-path Decimal churn 削減) は不要。**
OOM 問題は T106+T107 で既に解決済みであることが実測で判明した。

## B-1 attribution 計測 (b1_memory_attribution.py)

単一プロセスで real Stage A bars (86,400) に対し 200 backtest を逐次実行:

| 計測 | 結果 |
|---|---|
| RSS 推移 | 699MB → ~870MB で **plateau** (成長 197MB のみ、 単調増加せず) |
| live object census (gc.collect 後) | PriceBar=389,115 / Ohlc=778,230 で **完全一定**。 Trade/Decimal の retained ゼロ |
| tracemalloc current | **43MB** のみ (Python 追跡の live 割当) |
| tracemalloc top | _bars_cache の float64 配列 + bars 本体 + import 機構 (全て bounded) |

**判定 (Fact)**: backtest の Decimal churn は同一プロセス内で RSS 暴走を起こさない
(pymalloc は再利用される)。 200 backtest 後も 870MB で頭打ち。

**解釈 (Interpretation)**: 「Decimal churn → worker 9.5GB」仮説は **FALSIFIED**。
scaled-int を実装しても worker RSS は下がらない見込み。

## post-T107 worker RSS 実測 (smoke pop=24/gen=5/w=2/mt=12)

ps-tree (親 PID 起点で子孫 RSS 集計):

| 指標 | Run 82 (T106/T107 前) | post-T107 実測 |
|---|---|---|
| peak total RSS | 23,657 MB | **5,813 MB** |
| worker_max (per-worker) | 9,502 MB | **2,541 MB** |

GA best = g2_i2 fitness -0.02894014223533147 (baseline と bit-identical)。

注: monitor の pgrep が uv ランチャ (31MB) を親に取得したため "main" 表示は uv。
実 GA main python + worker 2 個は子プロセスとして集計され、 worker_max=2.5GB /
total=5.8GB が OOM 判定に効く値。

## 真因の最終特定

Run 82 の worker 9.5GB は **per-worker が保持していた 2.2M 個の aux PriceBar dict**
(EUR_USD/USD_JPY を 1.5 年分、 各 worker に pickle コピー) が支配的だった。
**T107 でこれを columnar 配列化** した結果、 worker RSS が 9.5GB → 2.5GB に低下。
backtest Decimal churn は元々支配要因ではなかった。

## 結論・方針

- **B0/B1 (scaled-int 本実装) は Obsoleted**。 OOM は T106+T107 で解決済。
- total peak 23.7GB → 5.8GB (-75%)、 24GB 機で headroom ~18GB。
- B0.5 (recycle 短縮) も不要 (RSS に余裕があるため、 むしろ recycle を緩めて
  wall-time 改善の余地すらある)。
- 副次的な選択肢: headroom が大きいので **max_workers を 2→3 以上に増やして
  GA wall-time を短縮**できる可能性 (別途検討)。

## investigation-first の価値
B-1 measurement (低コストの診断スクリプト) が、 scaled-int という大工事
(broker/orders/dsl の money 計算全面書換 + 厳密性リスク) を **着手前に不要と判定**
した。 「仕組みが機能していない段階で値を弄るな / まず仮説を立てろ」 の実践。

## 留意 (production scale)
本実測は pop=24/gen=5。 production pop=96/gen=60 では main がより多くの archive
行・population cache を保持しうるが、 worker per-worker は bars/aux/stage 機構の
固定コストが支配 (recycle で churn bounded) のため ~2.5GB 圏で大きく変わらない
見込み。 次回 production Run の summary.json max_rss_mb_per_worker で確認可。
