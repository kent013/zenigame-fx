# 概念設計: worker RSS 削減 (backtest hot-path) — investigation-first (step B)

## 前提 (C4, Round 1 で拡充)

| 項目 | 状態 | 根拠 |
|---|---|---|
| worker per-worker RSS = 9.5GB (Run 82) | **verified** | reports/run-reports/run-82/summary.json max_rss_mb_per_worker=9501.8 |
| **実運用 max_workers = 2** (skill template の 6 は誤り) | **verified** | config/alpha_factory/default.yaml:68 max_workers: 2 |
| main RSS は T106/T107 で 2.3GB に低下 | **verified** | smoke_t107 phase marker before_ga_loop=2317MB |
| GA loop 中 同時稼働 peak_total_rss_mb (T106/T107 後) | **unverified — B-1 で再測定** | before_ga_loop=2.3GB は GA loop 前の下限参考値。 GA loop 中 peak は別途実測要 |
| primitives は T030 で float64 numpy cache 化済 (Decimal 生成ゼロ) | **verified** | primitives/_bars_cache.py |
| MockBroker / Trade / DslStrategy に per-bar/per-trade Decimal | **verified** | mock.py:279-323, orders.py:34-54, dsl/eval.py:25-32 |
| **worker RSS 9.5GB の内訳 (retained vs transient churn)** | **unverified — B-1 で実測する** | 未測定 |
| Decimal churn が支配要因 | **unverified, hypothesis** | T105 background の延長 |
| 各 monetary/price 量が固定 scale で int64 表現可能か | **unverified — B0 設計で確定** | — |

## 背景・課題

T106/T107 で main RSS は ~10GB → 2.3GB。 worker per-worker RSS は依然 9.5GB。
**max_workers=2** で現状 ~21.3GB / 24GB、 headroom ~2.7GB と薄い。

### 運用 RSS 予算 (Round 1 [Critical] 4/7 + Round 2 [Critical] 反映)

- 機械: 24GB。 安全 headroom 目標 ≥4GB (OS/他プロセス + ピーク変動吸収)。
- max_workers=2 固定 (現状の運用要件。 3rd worker 追加は副次目標)。
- **成功条件は同一 run の同時稼働 peak で判定する** (Round 2 [Critical]):
  primary metric = `summary.json の peak_total_rss_mb ≤ 20GB`
  (= main + worker×2 の同時ピーク。 before_ga_loop marker 由来の 2.3GB は
  GA loop 前の値であり、 GA loop 中の main peak とは別物のため予算基準にしない)。
- 補助 metric: `peak_main_rss_mb` (GA loop 中の main 同時ピーク) と
  `peak_rss_mb_per_worker` を同一 run から取得し内訳を見る。
- **基準値の前提状態**: Run 82 (T106/T107 前) は peak_main=6468MB,
  peak_worker=9502MB, peak_total=23657MB (verified)。 T106/T107 後の GA loop 中
  peak_main は **未測定** (before_ga_loop=2.3GB は下限の参考値のみ) → **B-1 で
  同一 run の peak_main/peak_worker/peak_total を実測**してから worker 目標を
  確定する。
- worker 目標の暫定レンジ: peak_main が GA loop 中も 2-3GB 圏なら worker ≤8.5GB、
  6GB 台に戻るなら worker ≤6.7GB。 **確定は B-1 実測後**。
- 3rd worker を可能にするなら peak_total ≤20GB をより厳しく (worker ≤5.9GB 級)。

## 改善アイデア — 4 段階 investigation-first (Round 1 [Critical] 3 / Q2 / Q3 反映)

仮説「Decimal churn が支配」は未検証。 反証順序を厳密化する:

### B-1: memory attribution (必須先行、 最重要)
worker RSS 9.5GB の **retained vs transient churn 比率**を実測で切り分ける。
同時に **同一 run の peak_main/peak_worker/peak_total を取得** し運用予算の基準値を
確定する (Round 2 [Critical]):
- 計測点: task 終了直前 / `gc.collect()` 後 / child recycle 後 の RSS 差分
- live object census: `gc.get_objects()` 由来の Decimal 数 / Trade 数 / PriceBar 数
- recycle 前後の RSS 差 (= 断片化で OS に返らない量の推定)
- 出力: 「retained (bars/Trade 蓄積) X GB」「churn 断片化 Y GB」の内訳 +
  GA loop 中 peak_main
- **判定**: churn 支配 (Y が大) なら B0 へ。 retained 支配 (X が大) なら別施策
  (Trade 蓄積の columnar 化 / bars 共有メモリ化) に方針転換。

### B0.5: recycle 短縮 比較 (低リスク・即効、 ガードレール)
`max_tasks_per_child` 12→6 (or 動的) の 2-arm 比較 (Round 2 [Suggestion]):
- arm A: baseline (現状 mt=12)
- arm B: recycle 短縮のみ (mt=6、 exactness 不変、 コード変更最小)
- recycle 短縮で運用可能域 (peak_total ≤20GB) に届くなら、 それを即効薬として
  採用し scaled-int の必要性を再評価 (Round 1 Q3)。

### B0: scaled-int prototype spike (B-1 が churn 支配を示した場合のみ)
最 hot な mark_to_market + holding_cost + snapshot を scaled-int 化した
prototype で smoke 実測。 baseline / recycle短縮 / scaled-int proto の 3-arm で
peak_total を比較 (Round 2 [Suggestion]: B0.5 の 2-arm に scaled-int を加えた
3-arm)。 運用可能域到達 + exactness 維持を検証。

### B1: 本実装 (B0 が有望な場合のみ)
broker 内部表現を scaled-int 化。

## scaled-int 厳密性契約 (Round 1 [Critical] 2/5 反映)

scaled-int が exact なのは「固定 scale で表現可能な量」に限る。 各量の scale を
明記する (詳細設計で確定、 概念段階の枠):

| 量 | scale 案 | 単位 |
|---|---|---|
| price (quote/base) | 10^display_precision (pair 依存、 JPY 系 3, その他 5) | int64 |
| units (数量) | 整数 (既に int) | int |
| bps | 10^? (per_day_bps の小数桁) | int64 |
| pnl / cash / notional | account currency の最小単位 (10^2 or pair quote scale) | int64 |
| swap | 同上 | int64 |

- **丸め規則**: 各境界 (notional×bps/10000 等) で発生する丸めを明示。 既存
  Decimal 実装の quantize/rounding を踏襲 (= 同値の前提)。
- **オーバーフロー上限**: int64 範囲 (±9.2×10^18) に対し price×units×scale が
  収まることを確認 (notional の最大規模で検証)。
- **境界変換**: int↔Decimal 変換は **report / archive / 公開 API 境界のみ**。
  `on_bar / mark_to_market / holding_cost / snapshot` の bar 単位経路では
  Decimal を作らない (Round 1 [Critical] 5)。
- **golden case**: long / short / spread / swap / cross-currency notional /
  Trade.pnl+holding_cost==raw_pnl 不変条件 を列挙し Decimal 版と一致検証。

## 期待効果 (仮説、 運用可能域基準)

- H1 (B-1): worker RSS の retained vs churn 内訳を定量化 (これ自体が成果)
- H2 (B0/B0.5): **median `peak_total_rss_mb ≤ 20GB` (n≥3) に到達** (primary)。
  worker per-worker RSS 目標は B-1 で peak_main 実測後に確定する補助指標
  (暫定 ≤8.5GB / ≤6.7GB)
- H3: PnL/drawdown/Sharpe/trade ledger/pass-fail が Decimal 版と**設計上同値**
  (scaled-int は exact、 同値軸ごとに検証)
- H4: GA best 結果一致 (baseline g2_i2)、 既存テスト全 pass

### 成果判定

| 判定 | 条件 |
|---|---|
| B-1 完了 | retained/churn 内訳 + GA loop 中 peak_main/peak_total が定量化され、 次段方針と worker 目標が確定 |
| Step B 合格 | (B0.5 or B0 で) median `peak_total_rss_mb ≤ 20GB` (n≥3) かつ 同値維持 |
| 方針転換 | retained 支配 → Trade/bars 削減施策へ |
| REJECTED | churn 削減しても peak_total >20GB / exactness 破れ / throughput 大幅悪化 / recycle 短縮で同等以上の改善 (= scaled-int 不要) |

## 効果の限界 (Falsification, Round 1 [Warning] 10 反映)

1. retained memory (Trade 蓄積/bars) が支配的 → churn 削減は効かない (B-1 で判明)
2. scalar int も 256 超はヒープオブジェクト → 断片化が Decimal 比で減らない可能性
3. recycle 短縮で同等以上の改善 → scaled-int 不要 (B0.5 で判明)
4. scaled-int で exactness 契約が破れる → 即 REJECT
5. throughput (wall-time) 大幅悪化 → REJECT

## 制約・前提

### 使命との整合
- live_criteria 直接寄与なし。 探索完走 (OOM 回避) の前提整備。
- 成果判定に「OOM なしで所定 worker 数を維持」を含める (Round 1 [Warning] 1)。
- **本施策単体では strategy quality を改善しない。 完走率改善を品質改善と混同
  しない** (Round 1 [Suggestion] 2)。

### 正確性 (絶対、 ユーザー指示)
- float64 不可。 scaled-int は exact。 公開 API (Trade.pnl: Decimal) / archive
  スキーマ不変、 内部表現のみ変更。

### 既存アーキ
- primitives (T030) touch しない。 T070 不変条件維持。

## スコープ外
- primitives (T030 済) / main RSS (T106/T107 済) / aux (T107 済) / DB (T106 済)
- float64 化 (正確性により却下)
- 評価期間・閾値・取引回数 (禁止事項)

## 検証計画
- B-1: smoke (pop=24/gen=5/w=2/mt=12, seed=9999) に attribution 計測を仕込み、
  retained/churn 内訳 + object census を取得
- B0.5: 2-arm (baseline / recycle短縮) の median peak_total RSS (n≥3)。
  B0: scaled-int proto を加えた 3-arm 比較
- 同値: PnL/drawdown/Sharpe/trade ledger/pass-fail の Decimal 版一致 (決定論)
- GA best 一致 (g2_i2)、 既存テスト全 pass
