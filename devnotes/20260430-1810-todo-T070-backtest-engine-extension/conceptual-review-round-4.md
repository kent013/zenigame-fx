# T070 概念設計レビュー Round 4

## 0. 本レビューの前提 (C4)
- 判定対象は提示された Round 4 概念設計本文。
- 評価軸は C6/C7 の解消、会計 SSOT 一貫性、転記漏れ防止、Phase 境界監査性。

## 1. 結論
**APPROVED**

## 2. Critical (設計の根幹を揺るがす欠陥、 必須修正)
- なし（Round 3 の [C6] [C7] は解消済み）。

## 3. Warning (修正推奨だが概念設計でブロックしない)
- [W10] §4.3 の `pnl_net` 説明文が「`sum(trade.pnl)` で spread/holding 控除済」と読める表現のまま。本文 SSOT（`pnl_net = sum(t.pnl - t.spread_cost)`）に合わせて文言統一を推奨。
- [W11] §5.4 に `_close_position` 表記が残り、本文の主表記 `_close_one` と揺れている。
- [W12] §13 の要約 4/5 に「exact decomposition」語が残存し、Round 4 の「spread_cost は独立記録」契約と語感が衝突しうる。

## 4. Suggestion (詳細設計で考慮)
- [S10] §3.4.0 を唯一の会計 SSOT 節として明示し、他節は「§3.4.0 参照」に寄せると将来ドリフトを防ぎやすい。
- [S11] Phase 2 で `spread_cost=0 fallback` 発生率を必須メトリクス化すると、監査品質が上がる。
- [S12] F17/F20 の log/report/archive 露出は受け入れ条件（DoD）に固定するのが安全。

## 5. Falsification-first 観察 (失敗モード追加候補)
- F22/F23 への防御は本文で明示され、監査可能な形まで落ちている。
- 残留リスクは主に Phase 2 実装品質（露出経路・fallback 率）で、概念設計段階の阻害要因ではない。

## 6. 強み (継続すべき設計判断)
- `spread_cost` を「監査・stress 用独立記録」と定義し、`Trade.pnl` 非反映契約を SSOT 化できている。
- `orders.py` への `spread_cost + holding_cost` 追加が §3.1/§6.2/§9.1 で整合。
- F1-F23 を Phase 1/2 に分離し、監査観点が運用可能な粒度になっている。

## 7. 次 Round への申し送り (NEEDS_REVISION 時のみ)
- なし（PR 化可能）。