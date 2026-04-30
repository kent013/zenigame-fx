# T070 概念設計レビュー Round 3

## 0. 本レビューの前提 (C4)
- 提示された Round 3 本文のみを根拠に判定。
- 概念設計の SSOT 一貫性、会計契約、転記漏れ耐性を評価対象とした。

## 1. 結論
**NEEDS_REVISION**

## 2. Critical (設計の根幹を揺るがす欠陥、 必須修正)
- [C6] **spread_cost 契約が本文内で矛盾しており、会計 SSOT が単一化されていない**  
  Fact: §3.4.0/§3.5 は「`Trade.spread_cost` は記録のみ・`Trade.pnl` 未反映」。一方で §7.3 F13 は `pnl + spread_cost + holding_cost == gross_pnl` を検証対象、§13-4 は「exact decomposition / 推定値禁止」と記載。  
  Interpretation: `spread_cost` を「pnl内訳の正本」とするのか「監査用の別記録」とするのかが二重定義。`apply_spread_stress` の意味が実装者ごとに変わるため、Critical。
- [C7] **holding_cost 転記の設計展開にまだ不一致が残る**  
  Fact: §9.1 では `spread_cost + holding_cost` 追加を明記したが、§6.2 は依然 `spread_cost` のみ、§3.1 のモジュール図も `spread_cost` のみ。  
  Interpretation: Round 2 C4 の「転記漏れ再発防止」が完全達成ではない。実装タスク分解で漏れを誘発するため、Critical。

## 3. Warning (修正推奨だが概念設計でブロックしない)
- [W7] §4.3 の `pnl_net` 説明が「trade.pnl は spread/holding 控除済」となっており、§3.4.0/§3.5 の新契約（holdingのみ控除済）と不一致。
- [W8] §7.3 F8 が `_close_position` 表記、本文本体は `_close_one` 表記で揺れている。
- [W9] §12 の「F13-F21 必須化」と本文の一部説明（F19-F21はPhase2中心）の境界が曖昧。

## 4. Suggestion (詳細設計で考慮)
- [S7] 会計契約を1本化して明文化: `Trade.pnl` の定義、`spread_cost` の意味、`gross_pnl` の定義を1節に固定し、他節は参照のみ。
- [S8] 「変更点一覧」は自動チェック用の監査表形式にして、`spread_cost`/`holding_cost` の両列を必須化。
- [S9] F13 の検算式を現契約に合わせて修正し、テスト名も同一語彙で統一。

## 5. Falsification-first 観察 (失敗モード追加候補)
- [F22] 実装者Aは「spreadはpnl内訳」、実装者Bは「spreadは監査記録」で実装し、stress結果が環境依存で分岐する。
- [F23] `orders.py` への `holding_cost` 追加漏れが起きても、`mock.py` 側だけ更新されて静かに壊れる。

## 6. 強み (継続すべき設計判断)
- Round 2 の C5 に対する方向性（既存 cash 挙動を壊さない）は妥当。
- `BacktestResult.session_blocks` による transport SSOT 固定は有効。
- 8h covering と primitives 9h overlap の責務分離は明確。

## 7. 次 Round への申し送り (NEEDS_REVISION 時のみ)
- `spread_cost` の定義を **「正本内訳」か「監査記録」か** に一本化し、F13・§13-4・§4.3 を同時修正。
- §3.1/§6.2/§9.1 を同一記述に揃え、`holding_cost` 伝搬の不一致をゼロ化。
- `pnl_net`/`gross`/`raw_pnl` の語彙を単一辞書化して全節に反映。