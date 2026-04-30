# T070 概念設計レビュー Round 2

## 0. 本レビューの前提 (C4)
- 入力は提示された Round 2 概念設計本文のみ。
- 判定対象は概念設計の整合性・SSOT・責務分離・転記漏れ耐性であり、実装詳細の正否は対象外。
- Falsification-first で、破綻経路が残っていないかを優先確認。

## 1. 結論
**NEEDS_REVISION**

## 2. Critical (設計の根幹を揺るがす欠陥、 必須修正)
- [C4] **holding_cost の転記漏れが残存**  
  Fact: `Trade.holding_cost` を追加した設計（§3.5/§4.4）がある一方、変更一覧は `spread_cost` のみ記載が残る（§6.2、§9.1 #2/#3/#5）。  
  Interpretation: 「config→model→producer→consumer」の伝搬漏れ再発パターンで、Round 1 重点項目の再燃リスクが高い。`holding_cost` を全変更箇所・テスト計画・申し送りに明示統一が必要。
- [C5] **`apply_bar_holding_cost` と `Trade.holding_cost` の会計契約が未確定**  
  Fact: §3.4.2 で「barごとに cash 控除済」、同時に §3.5/§6.3 で close 時 `net_pnl = gross - spread - holding` を採用。  
  Interpretation: close 時の cash 反映規約を明文化しないと holding cost の二重控除/未控除が起こり得る。概念レベルで「cash debit はどこで1回だけ行うか」を確定すべき。

## 3. Warning (修正推奨だが概念設計でブロックしない)
- [W4] Falsification 表に旧語彙が残存（F6: `pnl_gross`、F10: `holding_cost_per_bar`）。SSOT語彙を `pnl_before_costs` / trade-level cost に統一した方がよい。
- [W5] §1 ゴール4に `pnl_gross` が残っており、本文の命名変更と不一致。
- [W6] テスト方針が「F1-F12」中心のままで、Round 2 追加の F13-F18 を必須ケースとして昇格していない。

## 4. Suggestion (詳細設計で考慮)
- [S4] 会計契約を1行で固定: `equity_delta = realized_price_pnl - spread_cost - holding_cost` の適用地点を明示。
- [S5] 変更管理表を `spread_cost` と `holding_cost` の2列で持ち、伝搬漏れ監査を機械化。
- [S6] `BacktestResult.session_blocks` を唯一入力とする lint/レビュー規約を追加し、再計算禁止を運用で担保。

## 5. Falsification-first 観察 (失敗モード追加候補)
- [F19] close 時に `holding_cost` を `pnl` に反映しつつ、cash 側でも再控除して二重計上。
- [F20] 伝搬漏れで `holding_cost` が `Trade` にはあるが report/archive に落ちない。
- [F21] `session_blocks` は同梱されるが、一部 caller が旧再計算経路を保持して指標差分を生む。

## 6. 強み (継続すべき設計判断)
- Round 1 の C1/C2/C3 に対する方向性自体は適切で、特に `BacktestResult.session_blocks` の transport SSOT 化は有効。
- `exit_time` 基準で全コスト帰属を統一した判断は、バケット跨ぎの曖昧性を減らしている。
- 8h covering partition と primitives 9h overlap の責務分離は明確。

## 7. 次 Round への申し送り (NEEDS_REVISION 時のみ)
- `holding_cost` を §6.2/§9.1/§12 に完全反映し、転記漏れゼロの形に修正。
- `apply_bar_holding_cost` と close 時 `net_pnl` の二重計上防止契約を概念設計本文で明文化。
- 旧語彙 (`pnl_gross` / `holding_cost_per_bar`) を全削除し、F表とテスト方針を Round 2 SSOT に揃える。