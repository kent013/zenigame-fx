# T070 概念設計レビュー Round 1

## 0. 本レビューの前提 (C4)
- 本レビューは、提示された T070 概念設計本文のみを根拠に行う。`synthesis.md`、T064/T061/T072 の原文、実コードは本ラウンドでは未提示のため、本文中の「前提検証 ✓」は文書内自己申告として扱う。
- 本ラウンドの判定対象は概念設計であり、実装詳細の良し悪しではなく、SSOT、責務分離、値伝搬契約、後続タスクへの境界条件が概念レベルで確定しているかを評価する。
- falsification-first に従い、「この設計が後段で破綻する経路が残っていないか」を先に見る。
- Facts と Interpretations は分離して書く。Fact は提示文書に書かれている内容、Interpretation はその設計含意である。

## 1. 結論
**NEEDS_REVISION**

## 2. Critical (設計の根幹を揺るがす欠陥、 必須修正)
- [C1] Fact: §4.3 / §5.2 では `trade.pnl` を `exit_time` 側 bucket に全額帰属させる一方、`holding_cost_total` は `holding_cost_per_bar` を bar 所属 bucket に積む設計になっている。さらに `pnl_gross == pnl_net + spread_cost_total + holding_cost_total` を `SessionBlock` 不変条件として要求している。 Interpretation: 複数 bucket を跨ぐ trade で holding cost だけが時系列配賦、PnL 本体は exit bucket 一括帰属になるため、block 単位の gross/net 分解が代数的に一致しない。これは詳細設計送りではなく、概念で「holding cost も exit bucket 一括帰属にする」か「block の gross invariant を捨てる」かを確定すべき。
- [C2] Fact: §3.5 / §5.3 / §6.3 では `spread_cost` を T064 `apply_spread_stress` の基礎量に使う一方、`MockBroker._close_position` の算出根拠は「bid/ask 差から推定」「等」とされ、`trade.pnl` に内在する既存 spread 控除と厳密一致する契約が概念で定義されていない。 Interpretation: `new_pnl = trade.pnl - trade.spread_cost * (multiplier - 1)` は、`spread_cost` が既存 `pnl` に埋め込まれた spread 成分の正確な分解値である場合にしか正しくない。近似値や事後推定だと stress 評価そのものが歪む。T070 では「推定」ではなく「`pnl` 分解の正本」という契約を概念で固定する必要がある。
- [C3] Fact: §6.4 / §9.2 では `BacktestResult` を変更せず、Phase 2 で caller 側が `aggregate_session_blocks(bars, trades)` を直接呼ぶ方針としている。 Interpretation: SessionBlock 生成の正本が engine 出力ではなく周辺 caller に分散し、`bars` の採り方、`holding_cost_per_bar` の供給有無、date universe の決め方が実装箇所ごとにズレる余地が残る。T061 canonical 5 engine と T064 stage evaluator が評価の本線である以上、SessionBlock の transport path は概念で 1 本に固定すべきで、「BacktestResult に載せるのか」「post-process 関数を唯一の正式入口にするのか」を今ラウンドで決める必要がある。

## 3. Warning (修正推奨だが概念設計でブロックしない)
- [W1] Fact: §5.2 は empty block を含むとしているが、どの date 集合に対して `(date, bucket)` を生成するかが未確定である。 Interpretation: `bars` に現れた UTC date のみを対象にするのか、backtest span の全 calendar date を対象にするのかで neutral block 数が変わり、`session_block_win_rate_worst` の分母が変わる。T072 に holiday を切り出すとしても、T070 で最低限「通常は bars に存在する UTC date を母集合とする」等の初期契約は明文化した方がよい。
- [W2] Fact: T064 側の文言は `TradeRecord.spread_cost`、T070 側は `Trade.spread_cost` になっている。 Interpretation: 実体が同一概念でも命名不整合は Phase 2 の転記漏れ温床になる。概念設計の時点でインターフェース名を統一した方が安全である。
- [W3] Fact: §7.1 で「collider bias リスク 0」と断定している。 Interpretation: T070 自体は集計層なので強い問題ではないが、`trade_count=0 neutral` を含む block 定義は後段の比較分析で conditioning の置き方に影響する。ここは「T070 では因果解釈をしないため本タスク内では未評価」と書く方が discipline に整合的。

## 4. Suggestion (詳細設計で考慮)
- [S1] `SessionBlock` に `is_empty_trade_block` と `is_partial_bar_block` 相当の派生情報を持たせると、T061/T072 で neutral 扱いと boundary 例外を機械的に分岐しやすい。
- [S2] `compute_bucket_for_bar()` と trade の bucket 決定規約は別関数名に分けた方がよい。bar 用と trade 用で基準時刻が異なるため、詳細設計で API を曖昧にしない方がよい。
- [S3] `spread_cost_total` を block に置くなら、`pnl_gross` を持つより `pnl_before_spread` / `pnl_before_carry` のように分解方向を明示した方が invariant 設計がしやすい。

## 5. Falsification-first 観察 (失敗モード追加候補)
- [F13] `spread_cost` が exact decomposition ではなく近似値のまま実装され、`apply_spread_stress` の出力が見かけ上だけ整合する。
- [F14] SessionBlock を engine 外で複数 caller が再計算し、`holding_cost_per_bar` の有無だけで canonical 5 指標が変わる。
- [F15] date universe の定義差により、週末・祝日・欠損日の neutral block 数が evaluator ごとにズレる。
- [F16] `entry_time` と `exit_time` が異なる bucket の trade で、spread は exit bucket、holding は経時 bucket という混在配賦が起き、bucket PnL の解釈が壊れる。
- [F17] `Trade.spread_cost` 追加は通っても、ログ・レポート・archive 側に出ず、Phase 2 で「値はあるが見えない」状態になる。
- [F18] `_SESSION_RANGES_UTC` と `BLOCK_BUCKET_RANGES_UTC` が将来別々に変更され、設計者の意図した「重複 windows と covering partition の併存」が文書ではなく属人的知識になる。

## 6. 強み (継続すべき設計判断)
- synthesis §4.4 / §6.2 / §6.3 / §18.2 T913 を明示アンカーにしており、8h covering partition を primitives の 9h overlap と分離した判断は妥当。
- `exit_time` 基準を概念で先に固定したのはよい。ここを曖昧にすると後段の canonical metrics が揺れる。
- empty block を明示的に扱う方向性は、`trade=0 -> neutral` を落とさないために必要で、設計意図として正しい。
- DST / holiday を T072 に切り出しつつ、T070 は UTC 単純基準で先に SSOT を固める段階分割も妥当。
- `Trade.spread_cost` を default 付き末尾追加にして既存 caller 破壊を避ける方針は、概念としては筋がよい。

## 7. 次 Round への申し送り (NEEDS_REVISION 時のみ)
- `holding_cost_total` の帰属規約を概念で確定すること。`exit bucket 一括帰属` か `bar 配賦を維持して block gross invariant を撤回` の二択を曖昧にしない。
- `spread_cost` を「推定値」ではなく「既存 `trade.pnl` に埋め込まれた spread 成分の正本」と定義し、`apply_spread_stress` の代数前提を明文化すること。
- SessionBlock の transport SSOT を確定すること。`BacktestResult` に載せるか、engine 後段の唯一の正式 post-process として固定するかを決め、Phase 2 の 5 経路で再計算させない。
- empty block の date universe を概念で固定すること。少なくとも T070 の通常ケースで何を母集合にするかは書き切ること。
- T064/T070 の命名 (`TradeRecord` / `Trade`) とログ出力責務を揃え、転記漏れレビュー観点を概念設計本文に明記すること。