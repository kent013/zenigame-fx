# 概念設計: aux_pair_bars の columnar 化 (main RSS 削減 step A)

## 前提 (C4)

| 項目 | 状態 | 根拠 |
|---|---|---|
| T106 (DB load streaming) で main RSS は ~10GB → 6.5GB (before_ga_loop) に低下 | **verified** | smoke_t106_20260520_123002 phase marker |
| after_aux_bundle_built で main RSS = 3277MB (after_holdout_load 698MB から +2.6GB) | **verified** | 同 phase marker |
| aux_pair_bars_index = `dict[str, dict[datetime, PriceBar]]` (EUR_USD/USD_JPY) | **verified** | aux_loader.py:177 |
| aux pair の期間は 1.5 年拡張 (stage_b_window_months=18 × 30 + holdout) | **verified** | aux_preflight.py:69, config window_months=18 |
| aux_pair_bars の唯一の消費者は P5 CrossPairTriangulation | **verified** | grep: pair_specific.py:402 のみが `ctx.aux_pair_bars` を実値消費 |
| P5 は aux PriceBar から bar_time (整列チェック) と bid.close/ask.close (mid) のみ使用 | **verified** | _aligned_pair_close (pair_specific.py:75-109): `out[i] = (float(ab.bid.close)+float(ab.ask.close))*0.5` |
| OHLC 残り 4 値・volume・complete は P5 で未使用 | **verified** | _aligned_pair_close は close 2 値しか参照しない |
| aux_pair_bars は worker に pickle 送信される (aux_bundle 経由) | **verified** | parallel_eval が aux_bundle を initargs で渡す (T057) |

## 背景・課題

T106 で DB ロード二重保持は解消したが、phase marker 実測で main RSS の残る
最大塊が判明した:

```
after_holdout_load:      698 MB
after_aux_bundle_built: 3277 MB  (+2.6 GB ← aux_pair_bars_index 構築)
before_ga_loop:         6535 MB  (+3.3 GB ← alignment 系/lane 構築)
```

`aux_pair_bars_index` は EUR_USD + USD_JPY を 1.5 年分、分単位で
`dict[datetime, PriceBar]` として保持する。PriceBar は Decimal × 8 + 2 Ohlc
dataclass + datetime + str + int + bool の重量級オブジェクトで、約 2.2M 個
保持される (≈ +2.6GB)。

**しかし P5 (唯一の消費者) は各 aux bar から mid close = (bid.close +
ask.close)/2 と bar_time しか使わない。** 重い PriceBar dataclass の 90% は
死に荷物である。

> **本施策単体では strategy quality は改善しない。改善するのは GA 探索を最後
> まで回せる確率 (OOM 回避) だけである。** (Round 1 [Suggestion] 1)

**aux pair を「重い PriceBar dict」から「mid close の float64 配列 (columnar)」
に置き換える。採用は A1 (新契約 `aux_pair_mid_close` 導入) に確定。**
(Round 1 [Critical] 3, 6 / Q1 反映)

P5 が必要とするのは bar_time 整列済みの mid close 列のみ。よって:

1. **raw 保持** (`aux_pair_bars_index` → `aux_pair_mid_index`): `dict[datetime,
   PriceBar]` を、bar_time でソート済みの軽量 columnar 表現に置換。
   - 構造: pair 毎に `ts_epoch_ns: np.ndarray[int64]` (UTC epoch **ナノ秒**、
     strict monotonic increasing + unique) + `mid_close: np.ndarray[float64]`
   - epoch 単位は **ナノ秒で固定**し、 target 側も同一の変換関数のみを使う契約
     (Round 2 [Warning] 1: 単位揺れによる false miss / golden 不一致を防ぐ)
   - 配列は align 後 `setflags(write=False)` で **read-only** 化し、 primitive が
     入力配列を破壊できないようにする (Round 2 [Warning] 2)
   - PriceBar dataclass を作らない
   - **raw 構築時に UTC / strict monotonic / unique を fail-fast 検証**
     (Round 1 [Critical] 2 / Q3)
2. **align 結果** (新フィールド `aux_pair_mid_close`): per-stage の
   `list[PriceBar | None]` を、target bars に整列済みの
   `aux_pair_mid_close: dict[str, np.ndarray[float64]]` (欠番は NaN) に置換。
   既存の `aux_series` (daily macro) が既に採用している `dict[str, np.ndarray]`
   と同型に揃える (機能の名前に立ち返る)。
3. **消費側** (P5 / `_aligned_pair_close`): `ctx.aux_pair_bars[pair]` の
   list 走査 + mid 計算を、整列済み mid 配列 `ctx.aux_pair_mid_close[pair]` の
   直接参照に置換。consumer 側で mid を再計算しない (SSOT)。

### 契約設計の決定 (Round 1 Q1/Q2/Q3 反映)

**Q1 → A1 採用 + 新契約導入**:
- 旧 `aux_pair_bars` の意味を変えて上書きしない。**新契約 `aux_pair_mid_close`
  を追加**し、P5 のみ移行、旧 `aux_pair_bars` 経路 (および raw
  `aux_pair_bars_index`) は本 PR で撤去する (cross-pair primitive は現状 P5
  のみ = 影響局所、 verified)。
- フィールド名は用途依存の `aux_pair_mid_close` とし、`bars` の名を流用しない
  (Round 1 [Warning] 5)。
- A2 (非侵襲、 値だけ軽量化) は **不採用**: align 後も list を残し object graph
  削減が不足するため (Round 1 [Critical] 6)。

**Q2 → sorted int64 + searchsorted**:
- raw index は `dict[datetime, float]` ではなく `ts_epoch: int64 sorted` +
  `mid_close: float64`。datetime object オーバーヘッドを排除し memory goal と
  exact-match 契約を両立 (Round 1 Q2)。

**Q3 → strict exact-match は `align_to` を SSOT として保全**:
- `align_to is the sole authority for exact timestamp matching.`
  (Round 1 [Critical] 2 / [Warning] C1 明文化要求)
- raw 構築時: UTC / strict monotonic / unique を fail-fast 検証
- align 時: target bar の epoch に対し `searchsorted` で候補位置 pos を出し、
  `raw_ts[pos] == target_ts` の exact-match 行だけ mid を書き、不一致は NaN
- 内部不変条件違反 (pos 範囲外等) は fail-fast。consumer 側では再計算しない。
- これにより現行 `ab.bar_time != tb.bar_time` の misalign fail-fast 契約を
  align 層に移して保全し、 silent NaN 化 / look-ahead 混入を防ぐ。

### 変更範囲 (A1 限定、 Round 1 [Critical] 6)
`aux_loader (load 関数 + AuxBundle.align_to + AlignedAuxBundle) / P5 +
_aligned_pair_close / EvaluationContext + RegistryEvaluator の aux_pair 契約 /
対応テスト` に閉じる。lane や他 primitive へは拡張しない。

## 期待効果 (仮説レンジ)

### 主 KPI (Round 1 [Warning] 2, 7 反映)
**main RSS 差分のみを主 KPI とする**:
- `after_raw_aux_index_built` (raw columnar 構築直後)
- `after_aux_aligned_built` (per-stage align 完了直後)
- `after_aux_bundle_built` / `before_ga_loop`

raw 側と align 側の効果を別々に観測するため phase marker を分割する
(Round 1 [Warning] 3)。

### 仮説
- H1 (主): after_aux_bundle_built の main RSS を **1GB 以上削減** (2.2M
  PriceBar → 2 本の int64/float64 配列 ≈ 数十 MB)
- H2 (主, 一次判定): P5 出力 mid close 配列が **golden 比較で一致**
  (Round 1 [Warning] 4)
- H3 (二次判定): GA best 結果が baseline (g2_i2, fitness
  -0.02894014223533147) と一致 (= 仮説のまま、 bit-identical は事実ではなく期待)
- H4 (副次仮説, 別 KPI): worker への pickle サイズ縮小で worker RSS 改善。
  ただし pickle 縮小 ≠ RSS 縮小の可能性があるため n≥3 で別途評価
  (Round 1 [Warning] 2, 7)
- H5: 既存テスト全 pass

### 成果判定

| 判定 | 条件 | 必要 smoke n |
|---|---|---|
| Step A 合格 | after_aux_bundle_built 削減 ≥ 1.0 GB **かつ** P5 golden 一致 | n=1 で可 |
| 部分成功 | 0.3 ≤ 削減 < 1.0 GB かつ P5 golden 一致 | n≥3 |
| INCONCLUSIVE | < 0.3 GB | n≥3 で再判定 |
| **REJECTED** | **P5 配列不一致 or strict-match 契約逸脱** / 削減なし / テスト fail | n=1 |

worker 安全性 (副次): `worker init 後 RSS peak` を別 KPI として n≥3 で観測
(Round 1 [Warning] 7)。主判定には含めない。

## 効果の限界 (Falsification)

1. **alignment +3.3GB が別要因 (Tier1Lane/bt_factory) 主体だった場合**:
   本施策は aux raw + align の aux pair 部分のみ。before_ga_loop の +3.3GB が
   lane 構築等なら、 そちらは別施策。
2. **mid close の float 化で P5 数値が変わる場合**: 現行は
   `(float(bid.close)+float(ask.close))*0.5`。columnar 化でも同式・同順序の
   float 演算を維持すれば bit-identical のはず。要 semantic equivalence 検証。
3. **worker pickle 縮小が RSS に効かない場合**: spawn 方式では initargs を
   pickle 経由で渡すが、 worker 内で展開後の構造が小さくなければ RSS は不変。

## 制約・前提

### 使命との整合
live_criteria 直接寄与なし。Run 完走可能性 (OOM 回避) を上げる前提整備。
T106 の続き。

### 決定論・ルックアヘッド
- mid close 計算式・順序を厳密維持 → P5 出力 bit-identical
- bar_time strict 一致 (misalign fail-fast) / 欠番 → NaN 契約を維持
- 未来参照なし (align は bar_time 完全一致 lookup、 forward-fill しない)

### 既存アーキ
- `aux_series` (daily macro) が既に `dict[str, np.ndarray]` の columnar align を
  採用 → 同じパターンに揃える (機能の名前に立ち返る)
- AuxBundle.align_to の責務は不変 (per-stage 整列)。**align_to を exact
  timestamp matching の唯一の権威 (SSOT) とする** (Round 1 [Warning] C1)

### 将来拡張時の契約 (Round 1 [Warning] C4)
現時点で cross-pair primitive の consumer は P5 のみ (verified)。新規 consumer
追加時は `aux_pair_mid_close` 契約を参照し、 mid を再計算しない。raw PriceBar を
要求する新 primitive が将来必要になった場合は、 その時点で別途 raw 経路を
再設計する (本施策では P5 の需要のみを満たす)。

## スコープ外
- T106 で済んだ DB ロード streaming
- lane bars (既に 0.7GB)
- alignment +3.3GB の aux pair 以外の要因 (Tier1Lane 等) → 別調査
- E (Stage 別遅延ロード)
- daily series / event_calendar / vix_snapshot (P5 と無関係)

## 検証計画
- smoke (pop=24/gen=5/w=2/mt=12, seed=9999, --no-report): phase marker
  after_aux_bundle_built / before_ga_loop の main RSS を baseline (3277/6535MB)
  と比較
- semantic equivalence: P5 を含むゲノムで mid close 配列が一致することを
  ユニットテストで assert + GA best 結果が baseline (g2_i2, fitness
  -0.02894014223533147) と一致することを smoke で確認
- 既存テスト全 pass (特に test_aux_loader_align.py の P5 / align 系)
