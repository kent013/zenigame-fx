# Concept: primitives-modulator-generic

## 目的

local_gate として使う MODULATOR primitive 6 個を実装。

## 実装対象

| ID | 名前 | 概要 |
|----|------|------|
| M1 | ATRRegimeGate | ATR レンジ帯でゲート（高ボラ / 低ボラ選好） |
| M2 | SessionGate | tokyo / london / ny セッションで on/off |
| M3 | SpreadConditionGate | スプレッドが閾値以下の時のみ通過 |
| M4 | EconomicEventGate | `src/events/` 既存連携、高 impact 指標発表 ±window 抑制 |
| M5 | VIXRegimeGate | FRED VIXCLS で risk-on/off 判定 |
| M6 | TrendStrengthGate | ADX > θ の時のみ通過 |

## 共通仕様

- 出力は `[0, 1]`（sigmoid/step/gaussian）
- steepness を GA 進化対象パラメータに
- 日足データ（VIX）は M1 バーに前営業日 close で左結合

## 前提

- M5: `macro_index_daily` テーブル（`fred-ingest-implementation` 完了後）
- M4: `src/events/` 既存（EconomicCalendar, list_events_in_range）

## テスト

- 各 gate の境界値テスト
- 出力が [0, 1] に収まる
- ルックアヘッドバイアス: 未来の event / VIX を参照していない

## 優先度・モード

- Priority: High
- Mode: incremental
- テーマ: primitives
