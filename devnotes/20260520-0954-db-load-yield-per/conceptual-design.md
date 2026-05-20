# 概念設計: DB ロード `yield_per` ストリーム化 (main RSS 削減 step C)

## 前提 (Round 1 review 反映, C4)

| 項目 | 状態 | 根拠 |
|---|---|---|
| 主要ロード経路 `_load_lane_bars` が `session.scalars(...).all()` で全件 materialize | **verified** | `scripts/alpha_factory/run_ga.py` L531, L548 (直接読み) |
| `load_aux_pair_bars_index` も同パターン | **verified** | `src/alpha_factory/aux_loader.py` L584-592 |
| `order_by(PriceBarM1.bar_time.asc())` が全クエリで指定 | **verified** | 同上 3 箇所すべて |
| SQLAlchemy 2.x + psycopg3 で `stream_results=True` + `yield_per=N` により server-side cursor が有効化される条件 | **unverified** (詳細設計で公式 doc 参照確定) | — |
| Session 寿命と identity map の挙動 (`with SessionLocal() as session` 1 セッション内で 2 連続 streaming) | **unverified** (詳細設計で確定) | — |
| main プロセスの GA 開始前 RSS が 9.8GB に到達 | **verified** (n=1 smoke, 2026-05-20) | tmp/smoke-logs/smoke_mem_20260520_092357.rss.log |
| Run 82 worker RSS = 9.5GB | **verified** | reports/run-reports/run-82/summary.json |
| pymalloc 断片化が main RSS の支配的要因 | **unverified, hypothesis** | コード読みからの推測 (Decimal × 8/bar × ~2.6M bar の churn) |

## 背景・課題

直近 Run 82 で **per-worker RSS が 9.5 GB** に達し過去最悪を記録。
worker recycle (`max_tasks_per_child`, devnotes/20260514-2045-ga-worker-memory/)
+ EquityCurve numpy 化 (devnotes/20260515-0827-backtest-decimal-churn/) の 2
施策投入直後にもかかわらず改善せず、worker 側の対策だけでは不十分。

2026-05-20 smoke (pop=24/gen=5/w=2/mt=12) で、**main プロセスが GA 開始前
40 秒の間にすでに 9.8GB に達し、ピーク 10.7GB** を観察 (n=1)。

### 先行施策がなぜ main pre-GA peak を下げなかったか (Round 1 SR-9)

3 行要約:
1. **worker recycle** は子プロセスを退役するだけで、`main` プロセスは生涯
   1 個。退役できない。
2. **EquityCurve numpy 化** は backtest hot path 内の equity 配列だけが対象。
   ロード段階の PriceBar/Decimal 構築には触れていない。
3. 両施策ともロード段階 (GA loop 開始前) には介入しない設計なので、観察された
   pre-GA 9.8GB の原因は別レイヤ (DB ロード) にある。

### 内訳の仮説 (smoke 観察 + コード読み, n=1)

| 要素 | 仮説サイズ | 根拠 (Fact / Interpretation) |
|---|---|---|
| EUR_JPY PriceBar (Stage A+B+holdout) | ~389k bar × 1KB ≈ 0.4 GB | Fact: 389k bar; Interp: Decimal 8/bar の dataclass ≈ 1KB/bar (詳細設計で実測予定) |
| aux_pair_bars_index (EUR_USD + USD_JPY M1) | ~2.2M bar × 1KB ≈ 2.2 GB | Fact: 1.5 年拡張期間 × 2 pair; Interp: dict[datetime, PriceBar] 構造での占有 |
| DB ロード時の二重保持 (ORM rows + PriceBar list) | +1〜2 GB ピーク (仮説レンジ) | Interp: `.all()` で全 ORM row 展開 → list comprehension 構築の同居期間 |
| pymalloc アリーナ断片化 (Decimal churn) | +5〜7 GB | Interp: main は worker 違い recycle されない |

合計 **~10 GB** の仮説と smoke 観察 (10.7GB) は order-of-magnitude では整合する
が、各内訳の数値は **n=1 の根拠しかなく、C7 sample size を踏まえると因果解釈
は限定的**。

## 改善アイデア

**ORM `session.scalars(...).all()` を「真にストリーム化される実装契約」に
置き換える。**

「真にストリーム化される実装契約」の意味 (Round 1 [Critical] 3, Round 2
[Warning] 1 反映):

- driver 層: psycopg3 で `execution_options(stream_results=True, yield_per=N)`
  を設定し、**server-side cursor** を経由させる (= 全件 client-side バッファを
  禁止)
- ORM 層 (第一候補): **ORM entity を経由しない**。必要列だけの
  `select(PriceBarM1.bar_time, PriceBarM1.open_bid, ...)` で tuple row /
  `mappings()` 経由で受け、PriceBar を直接構築する (identity map に載せない)
- ORM 層 (代替): どうしても ORM entity が必要な場合のみ、**caller-owned
  Session には触らない短命 Session パターン**を採用 (`SessionLocal()` の中で
  処理完結)。`session.expunge_all()` を caller の Session に対して呼ぶのは
  禁止 (`load_aux_pair_bars_index` のように外部 Session を受ける関数では副作用
  が呼び出し側に波及するため)

`partitions(N)` の単独使用は採用しない: server-side streaming が有効化されない
場合、partitions は単に client-side で chunk 化するだけで二重保持を救わない
ため。

### スコープ

1. `scripts/alpha_factory/run_ga.py:_load_lane_bars` の 2 箇所 (Stage B+A 統合
   ロード + holdout ロード)
2. `src/alpha_factory/aux_loader.py:load_aux_pair_bars_index` の aux pair M1
   ロード

### 非スコープ

- `aux_loader.py:_load_daily_series_observations` (daily 解像度、件数小)
- PriceBar / Ohlc の Decimal → numpy 化 (= 別 TODO 「A. aux_pair_bars_index
  numpy 化」/「B. PriceBar 全体 numpy columnar 化」)
- worker 側 RSS の追加対策 (= worker recycle 済)

## 期待効果 (仮説レンジ表記, Round 1 [Warning] 4 反映)

### 仮説 (検証対象)

H1: main プロセスのロード中 peak RSS は、`.all()` → streaming 化で**少なく
    とも 0.5 GB は下がる**
H2: 削減幅は 1〜2 GB のレンジに入る (point hypothesis ではなく **plausibility
    range**)
H3: 既存テスト (`tests/alpha_factory/`) は全 pass する

### 成果判定 (Round 1 [Warning] 6, 7 反映)

| 判定 | 条件 | 必要 smoke n | 次アクション |
|---|---|---|---|
| **Step C 合格** | main peak 削減 ≥ 1.0 GB | **n=1 で可** (差が大きいためノイズ耐性あり) | 後続 A/E に進む |
| **部分成功** | 0.5 GB ≤ 削減 < 1.0 GB | **n≥3 の median delta** で判定 (Round 2 [Warning] 4 反映) | A/E 検討、本施策は完了扱い |
| **INCONCLUSIVE** | 削減 < 0.5 GB かつ実測ノイズ範囲内 | n≥3 で再判定 | A/E 直行 |
| **REJECTED** | 削減なし or 悪化、または既存テスト fail | n=1 で可 | revert、A or E に直行 |
| (備考) | **削減 > 2 GB** は H2 上振れ。失敗扱いではなく成功 | n=1 で可 | 後続 A/E に進む |

**本番投入合格 (別指標)**: 想定 worker 数で main + worker × N の総 RSS が
24 GB 枠内に収まる。本施策単独では達成しないため、A/B/E と合わせて評価する。

### 等価性保証 (Round 1 [Critical] 5 反映)

「L3 artifact bit equivalence」は**主張しない**。代わりに以下の **semantic
equivalence** を検証する (Round 2 [Warning] 2, 3 反映):

- バー数一致 (Stage A / Stage B / holdout / aux EUR_USD / aux USD_JPY 全て)
- 各 lane/aux の **先頭 + 末尾 bar_time が一致**
- 各 lane/aux の **`(bar_time, bid OHLC, ask OHLC, volume, complete)` の安定
  digest (sha256) が一致**
  - canonical serialization: Decimal は `str(value)` (正規化なし、DB から得た
    string 表現そのまま)、datetime は UTC ISO 8601 (例
    `2025-04-01T00:00:00+00:00`)、bool/int はそのまま str 化
  - 区切り文字を含む TSV 形式で 1 bar/行 → `sha256(utf8_encode(joined))`
- `validate_stage_partition` の disjoint 検証 PASS
- aux V15 fail-fast (同 minute 重複) 検出ロジック PASS

これらが満たされれば、下流 (Stage A/B/C, backtest) は決定論的に同一動作する
契約 (semantic equivalence)。

## 効果の限界 (明示, Round 1 [Warning] 10 = Falsification)

本施策で **改善されない / 効果不足のシナリオ**:

1. **aux_pair_bars_index の live size が支配的だった場合**: dict 構造 + ~2.2M
   PriceBar の steady state 占有が ~2GB 以上を占めるなら、ロード時ピーク削減
   は steady state には効かず、Run 全体の RSS 天井は下がらない。
2. **driver / Session が全件保持し続けた場合**: psycopg/SQLAlchemy 層が server-
   side cursor を有効化しない (例: 環境変数、driver オプション不一致) と、
   `yield_per` 指定でも client-side で全件 fetch されて効果ゼロ。
3. **pymalloc アリーナ断片化が支配的だった場合**: Decimal 構築・解放の総量は
   streaming 化で変わらないため、断片化由来の RSS は同等に残る。
4. **holdout/aux/main の同時生存が支配的だった場合**: ロード順序の問題で、
   streaming 化しても 3 集合の同時保持期間は残る。本施策は 1 集合内の二重
   保持を解消するだけ。
5. **smoke と本番 Run の RSS プロファイルが大きく違う場合**: smoke で改善
   見えても、pop=96/gen=60 の本番では他要因が支配的になりうる。

上記 1, 4 が現実なら本施策は failure → 即 A (aux_pair_bars_index numpy 化) /
E (Stage 別遅延ロード) に切り替える。

## 制約・前提

### Alpha Factory 使命との整合

- live_criteria には**直接寄与しない**インフラ改善 (Round 1 [Warning] 1 反映)
- 位置づけ: **Run 完走可能性を上げる**前提整備。「24GB 制約達成」の単独達成
  ではなく、後続 A/B/E と組み合わせる土台

### 決定論

- L1 selection: 不変 (バー順序保持)
- L2 row order: 不変 (`order_by(bar_time.asc())` 維持)
- L3: **bit equivalence は主張しない**。semantic equivalence (上記検証項目)
  で代替

### 既存アーキテクチャとの整合

- T087 (`Stage Partition Integrity Guard`): `bars_stage_b_full[-stage_a_n_bars:]`
  / `[:-stage_a_n_bars]` の slice は最終 list 構築後に同形で動作。streaming
  化は影響しない。
- aux_loader V15 fail-fast: dict 構築時の重複検出は変更不要

### 環境前提

- ターゲット (AGENTS.md 規定): 24 GB × 6 worker (1 worker ≤ 3 GB)
- 現状: main ≈ 10 GB + worker ≈ 9.5 GB × 2 ≈ ~29 GB ピーク
- 本施策単独後の見込み: main 8〜9 GB + worker 9.5 GB × 2 ≈ ~27 GB
  (24 GB 達成には不足、後続施策が必要)

## スコープ外 (明示)

| 候補 | 期待効果 | 想定別 TODO |
|---|---|---|
| **A. aux_pair_bars_index numpy 化** | -2 GB live | 別 TODO (中工数) |
| **B. PriceBar 全体 numpy columnar 化** | -2 GB live + -5GB 断片化 | 別 TODO (大工数) |
| **D. main / worker 完全分離** | アーキテクチャ変更 | 別 TODO (大) |
| **E. Stage 別遅延ロード** | -1〜2 GB | 別 TODO (中) |

本施策 (C) は最小工数 / 最小リスクで「DB 二重保持」仮説の反証を狙う一手目。

## 検証計画

### Smoke 計測 (n=1 ~ 必要に応じ n=3)

条件: pop=24/gen=5/w=2/mt=12, --no-report, seed=9999

1. before baseline: 2026-05-20 smoke 結果 (main ピーク 10.7 GB)
2. after: 実装後の同条件 smoke
3. RSS 推移は ps サンプリング (5 秒間隔) で取得
4. 判定: 上記「成果判定」表に従う

### Phase marker RSS (Round 2 [Suggestion] 5 反映, C3 collider 回避)

単一の peak だけでなく、以下の各 phase 直後の RSS を logger.info で
記録する:

- `after_lane_load` (= EUR_JPY Stage B+A ロード完了直後)
- `after_holdout_load` (= holdout ロード完了直後)
- `after_aux_pair_load` (= aux_pair_bars_index 構築完了直後)
- `ga_start` (= GA loop に入る直前)

before/after で各 marker の RSS を比較することで、「どの phase で削減が
発生したか」を切り分け可能にする。単一 peak だけだと、別 phase のピークに
条件付けて誤判定する collider bias を回避する。

### 等価性検証 (実装時の機械検証)

- `validate_stage_partition` PASS
- 各 lane/aux で (bar_time, OHLC×2, volume) チェックサム一致を assert する
  ユニットテストを追加 (tests/alpha_factory/)
- 既存テスト全 pass

### Stop/Go 条件 (Round 1 [Warning] 6 反映)

- batch size 調整は **2 値しか試さない** (例: 10,000 と 5,000)。それ以上の
  探索はしない (Round 1 SR-6)
- 改善 < 0.5 GB なら本施策完了扱いで A or E に切り替える
