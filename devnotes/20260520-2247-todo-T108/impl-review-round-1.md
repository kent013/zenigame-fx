**前提 (C4)**
- 本レビューは提示された差分と提示済み Fact のみを根拠にした静的監査です（実行は未実施）。
- 反証優先 (C9) で「GA 選抜不変を崩し得る経路」を先に探索しました。

**Fact**
- event 順序は kernel 実装内で `drop_pending -> spread -> pre-fill -> fill -> mark -> margin(post-fill) -> session -> on_bar -> EOD -> equity` と明示され、実コードもその順に並んでいます。  
  [src/backtest/_sim_kernel.py:110](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T108/src/backtest/_sim_kernel.py:110)
- fill 価格と pnl 符号は、open entry が `long=ask_o / short=bid_o`、signal close が open 価格、それ以外強制 close が close 価格で実装されています。  
  [src/backtest/_sim_kernel.py:151](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T108/src/backtest/_sim_kernel.py:151)
- spread filter / margin call は cross-multiply 比較で実装されています。  
  [src/backtest/_sim_kernel.py:128](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T108/src/backtest/_sim_kernel.py:128)  
  [src/backtest/_sim_kernel.py:206](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T108/src/backtest/_sim_kernel.py:206)
- broker 同期は kernel 完了時に `cash / positions / trades / last_bar` を更新しています。  
  [src/backtest/engine.py:432](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T108/src/backtest/engine.py:432)
- parity テストは long/short/EOD/session/spread/margin/time_stop/overflow-fallback を網羅しています。  
  [tests/backtest/test_sim_kernel_parity.py:176](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T108/tests/backtest/test_sim_kernel_parity.py:176)

**Interpretation**
- A/B/C/D/E の主要契約は差分上、設計意図と整合しています。
- ただし「selection-invariant 絶対」を反証する残余リスクが 2 点あります（下記 Warning）。

**ファイル別判定**

[src/backtest/_sim_kernel.py](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T108/src/backtest/_sim_kernel.py)  
- 判定: **Warning あり**
- [Warning] spread filter の積演算に overflow sentinel が無く、`njit` の `int64` wrap により稀に判定反転し得ます。  
  該当: [src/backtest/_sim_kernel.py:128](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T108/src/backtest/_sim_kernel.py:128)  
  修正案: margin と同様に safe-mul ガードを入れ、overflow 検知時は `STATUS_OVERFLOW` を返して Decimal 再実行にフォールバック。
- [Suggestion] `out_equity_scaled` を `EquityCurve` に渡す前に read-only 化して、Decimal 経路との不変条件を明示すると監査しやすいです。

[src/backtest/engine.py](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T108/src/backtest/engine.py)  
- 判定: **概ね適合**
- [Suggestion] kernel→Decimal fallback 時に `overflow_fallback=true` をログ出力すると、run 監査で原因追跡が容易です。

[tests/backtest/test_sim_kernel_parity.py](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T108/tests/backtest/test_sim_kernel_parity.py)  
- 判定: **Warning あり**
- [Warning] 同一 bar で `margin_call / session_close / EOD` が同時成立する競合優先順位の専用テストがありません。event 順序契約 A の回帰検知としては穴が残ります。  
  修正案: 1 ケース追加し、同一 bar で 3 条件成立時に「約定 1 回のみ」「reason は margin_call 優先」「二重 close なし」を明示アサート。
- [Suggestion] `active_clause_indices` の kernel vs Decimal 一致を 1 テスト追加すると E の契約がより強固です。

[tests/backtest/test_columnar.py](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T108/tests/backtest/test_columnar.py)  
- 判定: **APPROVED**
- [Critical] なし
- [Warning] なし

**全体判定**
- **CHANGES_REQUESTED**

理由は、mission が「GA 結果完全不変」絶対制約である以上、`_sim_kernel.py` の spread 判定 overflow 未ガードと、競合優先順位テスト未充足は先に潰しておくべきだからです。  
（現状の Fact ベースで実害は確認されていませんが、反証可能性が残るため承認保留が妥当です。）