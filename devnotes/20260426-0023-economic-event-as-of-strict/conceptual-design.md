# 概念設計: EconomicEventSnapshot as_of 厳密化

## 背景

リーク監査 (2026-04-26) で唯一の実害可能性として検出された項目。

`src/alpha_factory/primitives/_base.py:120-141` の `EconomicEventSnapshot` は MVP 仮定として
"backtest 使用時は calendar 全量を `as_of=+∞ 近似` で渡す運用を許容（schedule の late
amendment leakage は別 TODO で厳密化）" を明記している。

現状の production path:

- `scripts/alpha_factory/run_ga.py:872` — `RegistryEvaluator(pair=...)` のみ。`event_snapshot` 未指定
- `scripts/alpha_factory/run_alpha_sieve.py:803` — 同上

そのため M4 EconomicEventGate / P10 (pair_specific 経済イベント参照 primitive) は
現在「no-op (gate 開放)」状態であり、現時点で実害は発生していない。
**ただし、production loader を整備して event_snapshot を流し始めた瞬間に**
MVP の "全量を as_of=+∞" 運用が有効化され、未来の schedule（late amendment や
revision 含む）が bar_time 時点で既知扱いされる leakage が生じる。

## 目的

EconomicEvent ベースの primitive を production で有効化する前提として、
`event_snapshot.as_of` が **必ず bar_time 以下** であることを runtime / 型契約で
保証し、MVP 近似を撤廃する。

## 成功条件

1. `as_of` 設定が「bar_time に対して strict に過去」であることを compute / evaluator
   いずれかのレイヤで形式的に保証する
2. backtest run 中、bar ごとに変化する `as_of` を効率的に供給できる
   （compute_all_bars の loop 内で O(1) 切替できる）
3. M4/P10 を有効化した backtest run で leak 兆候が無いことを既存 indicators causality
   テスト同等の方式で形式検証できる
4. live (paper/real) と backtest で snapshot 構築経路が共通化できる

## 失敗モード

- as_of=+∞ 撤廃により、loader 整備されるまで M4/P10 が常に strict_snapshot_required
  例外を投げるようになり、選抜が機能停止する → **既存の "snapshot 不在 → safe default 1.0"
  経路は撤廃せず、production toggle を新設**して切替える
- per-bar snapshot 再生成のコストが evaluation を slowdown させる → snapshot は immutable
  に保ち、`(calendar, as_of)` の `as_of` のみ差し替えできる cheap 構造にする

## 想定アプローチ（決定は詳細設計で）

A. `EconomicEventSnapshot` を「(events tuple, as_of)」の immutable view に変更し、
   compute 内で event_time <= as_of の filter は維持。loader が events 全量を一度
   ロードし、per-bar に as_of だけ更新する pattern を確立。

B. `EvaluationContext` の bar_time 情報から `as_of = ctx.bars[i].bar_time -
   embargo` を compute 内で導出し、event_snapshot 側の as_of は最も保守的な上限値
   （= dataset.end）として使う「二段ガード」。

C. loader 整備のためのデータソース調査（FRED / OANDA economic calendar / 外部 ICS）。

## 制約

- AGENTS.md C2: 現在 leak は "起きていない"（no-op のため）。**bug claim ではなく
  "production 化する前に整備すべき技術債務"** として扱う
- FX 固有: イントラデイ前提（M1/M5）。as_of 粒度を 1 分にすると O(N×events) ループに
  なる可能性 → bisect で O(log E) 化
- 実装モード: `incremental`（M4/P10 単体 primitive 有効化と連動するため、
  event loader 設計と並行進行）

## 次ステップ

- 詳細設計で A/B/C の具体案を採点
- causality 検証は `tests/alpha_factory/primitives/test_indicators_causality.py`
  と同方式で M4/P10 単体に対し設計
