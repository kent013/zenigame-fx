# T070 詳細設計レビュー Round 1

## 0. 本レビューの前提 (C4)
- 前提1（verified）: レビュー対象は提示された「詳細設計本文」単体。
- 前提2（未検証）: `conceptual-design.md` / Round 4 本文 / 実コード / git 履歴は本ターンでは未参照（ツール制限に従い、外部照合なし）。
- 前提3（verified）: 判定は「本文内部の整合性」「PRに落とせる実装粒度」「転記漏れ防止観点」に限定。
- 前提4（verified）: Round 1 は Falsification-first として、破綻しうる経路を優先的に探索。

## 1. 結論
[NEEDS_REVISION]

## 2. Critical (PR レベルで修正必須)
- [C1] `compute_bucket_for_bar` が `BLOCK_BUCKET_RANGES_UTC` を参照せず 8/16 を直書きしており、SSOT が二重化。Facts: 定数と実装ロジックが別管理。Interpretation: T072 以降で境界更新時に静かに乖離し、bucket 帰属が壊れる経路が未封鎖。
- [C2] `apply_spread_stress` 後の `Trade` が F13 契約（`Trade.pnl + Trade.holding_cost == raw_pnl`）を満たさない定義になっている。Facts: `pnl` のみ減額し `holding_cost` は不変。Interpretation: 「通常 Trade」と「stress 済 Trade」の会計契約境界が曖昧で、下流が同一不変条件を仮定すると破綻。
- [C3] 「caller signature 完全展開」が方針（grep）止まりで、要求された網羅リストになっていない。Facts: `Trade/BacktestResult/_close_one/apply_bar_holding_cost/run_backtest` の実 caller パス列挙が無い。Interpretation: 転記漏れ検知の監査証跡として不十分。
- [C4] 擬似コードがそのまま実装に落ちる粒度に未達。Facts: `apply_spread_stress` で `replace(...)` 使用だが import 記述なし（`Sequence` も同様）。Interpretation: 実装直前で機械的エラーが発生する設計書。

## 3. Warning (修正推奨)
- [W1] `_compute_trade_spread_cost` に `bar.spread_close < 0` ガードがない。Facts: 異常データ時に負の `spread_cost` が入りうる。Interpretation: `spread_cost_total >= 0` 契約と衝突し、集計の信頼性を落とす。
- [W2] F1-F23 の 1:1 トレーサビリティが弱い。Facts: F1/F18 統合、F3/F15 の対応表現が入れ替わり気味、F14/F21 は実テストでなく PR check。Interpretation: 失敗モード起点の追跡が難しい。
- [W3] Phase 区分の記述が不整合。Facts: §10 見出し「合計7項目」と実列挙（Phase1=6, Phase2=7）に齟齬、§1.3 と粒度も差分。Interpretation: 実装範囲の誤読リスク。

## 4. Suggestion (詳細で考慮)
- [S1] 会計契約を `Trade(normal)` と `Trade(stressed)` で明示分離（型またはフラグ）し、F13 適用範囲を仕様に固定すると監査しやすい。
- [S2] `aggregate_session_blocks` に property-based test（不変式・順序性・date universe 完全性）を追加すると、将来改修での退行を検出しやすい。
- [S3] spread 近似の根拠メモを短く追記推奨（例: Roll, 1984, “A Simple Implicit Measure of the Effective Bid-Ask Spread” 要確認）。

## 5. 強み (継続すべき設計判断)
- `SessionBlock.__post_init__` で会計不変式を実行時検証している点は堅い。
- `_close_one` の cash ロジックを維持しつつ `holding_cost/spread_cost` を記録分離した最小変更方針は妥当。
- `BacktestResult.session_blocks` を transport SSOT とした判断は、再計算禁止の設計意図と整合。
- `entry_spread` 厳密化を Phase 2 へ明示的に送り、Phase 1 の複雑化を抑えている点は良い。

## 6. 次 Round への申し送り (NEEDS_REVISION 時のみ)
- `compute_bucket_for_bar` を `BLOCK_BUCKET_RANGES_UTC` 駆動に変更し、境界の単一SSOT化を明記。
- `apply_spread_stress` の契約を再定義し、F13 との適用境界を仕様とテストに追記。
- caller 完全展開表を「実ファイルパス単位」で追加（各 caller の影響有無を明記）。
- 擬似コードの import/型依存を補完し、「そのまま実装可能」状態にする。
- F1-F23 マトリクスを failure→test/check の 1:1 で正規化し、Phase 1/2 の責務境界を再整理。