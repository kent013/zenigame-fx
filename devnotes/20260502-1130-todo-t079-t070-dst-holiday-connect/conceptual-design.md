# 概念設計 (skeleton): T079 — T070 DST/holiday → BLOCK_BUCKET_RANGES_UTC 連携完成

**作成日時**: 2026-05-02 11:30 JST
**起源**: cascade port v2 Phase 2 配線 handoff § 6 残作業 3 (T070 follow-up)
**性質**: 接続漏れ解消 + DST/holiday 例外連携の完成
**位置付け**: cascade port v2 follow-up (= 設計品質向上、 イントラデイ評価の正確性強化)
**status**: **skeleton (= 後続セッションで zenigame-fx-alpha-design による Codex review で詳細化、 詳細範囲は調査要)**

---

## 背景・課題

### 現状

`src/backtest/session_block.py` L75 で `BLOCK_BUCKET_RANGES_UTC` (= 8h × 3 covering partition、 tokyo/london/ny) が定義されている。 T072 で `observability_flags` field (= dst_transition_markets + holiday_markets) が追加されたが、 **`BLOCK_BUCKET_RANGES_UTC` 自体は固定 partition** で、 DST/holiday 例外は別経路 (`MarketHolidayCalendar` + `BrokerTradingSchedule`) で扱われている。

### handoff § 6 の申し送り

「T070 follow-up (BLOCK_BUCKET_RANGES_UTC への DST 例外連携)」 と記載。 具体的には:
- DST 期間 (= UTC offset shift) で tokyo/london/ny の bucket boundary を変動させるか、 固定保持か
- holiday 例外 (= 市場休日) で BUCKET 内 trade_count = 0 の扱い

### 現状調査結果 (= 本 skeleton 時点)

T072 で `compute_observability_flags` 関数が `dst_transition_markets` と `holiday_markets` を計算しているが、 これが `BLOCK_BUCKET_RANGES_UTC` に **どう連携されているか** は要詳細調査。 `aggregate_session_blocks` で `observability_flags` を `SessionBlock` に格納しているが、 `BLOCK_BUCKET_RANGES_UTC` 自体の boundary 変動はしていない可能性。

---

## 改善アイデア

### option A: BLOCK_BUCKET_RANGES_UTC を固定保持 (= 現状維持)

DST/holiday は `observability_flags` で flag 化のみ、 BUCKET boundary は不変 (= UTC 固定 partition)。 利点: 設計シンプル、 partition contract 不変。 欠点: DST 期間で「tokyo open hour が変動」 を反映しない (= イントラデイ精度低下)。

### option B: BLOCK_BUCKET_RANGES_UTC を DST 動的にシフト

DST 期間で tokyo/london/ny の UTC bucket を ±1h シフト。 利点: イントラデイ精度向上。 欠点: partition contract 動的化、 caller 全件確認、 24h covering invariant が複雑化。

### option C: BLOCK_BUCKET_RANGES_UTC + 別 DST adjustment table

固定 BLOCK_BUCKET_RANGES_UTC + DST/holiday 期間用の adjustment table を別途用意。 caller が必要に応じて参照。

### 推奨: option A (現状維持) + 詳細設計レビューで判断

実は handoff の申し送りが具体的でない (= 「BLOCK_BUCKET_RANGES_UTC への DST 例外連携」 という抽象記述)。 後続セッションで:
1. 現状の `observability_flags` 連携状況を精査
2. Stage A/B/C 評価で DST 期間の精度がどう影響するか定量評価
3. option A/B/C の trade-off を Codex 議論で確定

= 本 skeleton では「**connection 状況の精査 + option 選定**」 を後続セッションのスコープとし、 具体的な実装は option 確定後。

---

## 2026-05-02 22:50 JST 追記: 現状調査結果 → option A (既実装) 採用 → T079 close

T079 の現状調査 (`grep -nE "compute_observability_flags|observability_flags|BLOCK_BUCKET_RANGES_UTC"`) で以下が判明:

1. `src/backtest/calendar.py` L510 `compute_observability_flags(business_date, calendars)` で **DST 検出 (= `is_dst_transition`) + holiday 検出 (= `is_market_holiday`) を統合計算** + ObservabilityFlags 返却
2. `src/backtest/calendar.py` L531 `compute_bucket_open_minutes(business_date, bucket, broker_schedule)` で **broker_schedule × BLOCK_BUCKET_RANGES_UTC overlap で open_minutes 計算** (= 部分開市場日の bar 数調整)
3. `src/backtest/session_block.py` L142 SessionBlock dataclass で **observability_flags field を保持** + `aggregate_session_blocks` で集計時に格納
4. tests/backtest/test_calendar.py で **observability_flags 関連 14 件カバー済**

= **option A (= BLOCK_BUCKET_RANGES_UTC 固定 + DST/holiday は observability_flags + open_minutes 別レイヤー) は既に実装完了済**。

### option B/C 不採用判断

- **option B (BLOCK_BUCKET_RANGES_UTC dynamic shift)**: partition contract (= 24h covering / bucket non-overlap) が崩れる + caller 全件確認必要、 大規模改造。 効果は「DST 期間で tokyo/london/ny の bucket boundary が UTC 上で ±1h ずれる」 表現だけで、 これは observability_flags でも flag 化済 → 実害なし
- **option C (別 adjustment table)**: 抽象度上昇のみで効果薄、 既存 observability_flags 経路で十分

### 結論

**T079 は実装変更不要として close**。 「BLOCK_BUCKET_RANGES_UTC への DST 例外連携」 = 既に observability_flags + open_minutes で別レイヤー実装済 (= T072 で完了)、 handoff の申し送り解釈が「BLOCK_BUCKET_RANGES_UTC 自体の改造」 と過剰だった。 cascade port v2 follow-up としては option A 採用 + 既実装で完結。

将来的に DST 期間の精度問題が定量観測されたら、 別 TODO として再検討 (= Conditional 候補、 ただし優先度低)。

---

## 期待効果 (option 確定後)

- **イントラデイ評価の DST 期間精度向上** (= 該当する場合)
- **holiday 期間の SessionBlock invariant 強化** (= bar_count = 0 の取扱明確化)
- **observability 経路の活用拡大** (= flag だけでなく boundary 連携)

---

## 実装方針 (概要、 option 確定後)

### 変更ファイル候補

1. `src/backtest/session_block.py`: BLOCK_BUCKET_RANGES_UTC 周辺 (option B の場合は dynamic 化、 option A なら不変、 option C なら adjustment table 追加)
2. `src/backtest/calendar.py`: DST detection ロジック (= 既存 + 拡張)
3. `src/backtest/holiday_calendar.py`: holiday detection ロジック (= 既存 + 拡張)
4. tests/: option 別の test 追加

---

## 制約・前提

- T072 で確立した `observability_flags` 経路は不変 (= flag 自体は維持)
- partition contract (= 24h covering、 bucket non-overlap) は不変
- イントラデイ前提の使命遵守

---

## スコープ外

1. session boundary を時間帯別 (= tokyo open / close / pre-market 等) に細分化 (= 別 TODO)
2. cross-pair の市場時間調整 (= 別 TODO)

---

## リスク

| リスク | 影響 | 緩和 |
|---|---|---|
| option B 採用で partition contract 不変が崩れ caller 全件壊れる | 大 | option 選定段階で慎重に検討、 option A を default に |
| holiday 期間の bar_count=0 invariant が現状コードで処理済か未処理か不明 | 中 | 後続セッションで grep + test 確認 |
| DST 精度向上効果が evaluation accuracy に与える定量影響不明 | 中 | option 選定前に定量評価 (= 直近 Run の DST 期間影響を測定) |

---

## 参考資料

- handoff: `devnotes/20260502-0710-cascade-port-v2-phase2-complete-handoff/handoff.md` § 6 残作業 3
- T070 detailed-design: `devnotes/20260502-0247-cascade-port-T070-complete-handoff/handoff.md`
- T072 detailed-design: `devnotes/20260502-0438-cascade-port-T072-complete-handoff/handoff.md`
- 実装: `src/backtest/session_block.py` L75 (BLOCK_BUCKET_RANGES_UTC)
- 関連: `src/backtest/calendar.py` (DST detection)

---

## skeleton から本格設計への昇格手順

1. 後続セッションで現状調査 (= compute_observability_flags の連携状況を grep + 図示)
2. option A/B/C の trade-off 定量評価 (= 直近 Run の DST 期間影響測定)
3. zenigame-fx-alpha-design skill で option 選定 + Codex 議論
4. detailed-design 起草 + Codex review → APPROVED
5. zenigame-fx-implement で実装 (worktree todo/T079)
