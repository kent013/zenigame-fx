**Fact**
- Round 1 の W1/W2/S1/S2 は差分上すべて対応されています。
- spread filter は乗算前 sentinel を持ち、overflow 時に `STATUS_OVERFLOW` で Decimal fallback します。
- margin/session/EOD 同一 bar 競合は parity テストが追加され、margin 先勝ちと二重 close なしを検証しています。
- fallback ログと `active_clause_indices` parity も追加されています。
- コマンド実行制限に従い、今回は提示差分ベースの静的レビューのみです。

**Interpretation**
- Round 1 指摘への対応は妥当です。
- ただし `selection-invariant performance-only change` としては、まだ `int64` overflow の閉じ方が不完全です。

**ファイル別判定**

[src/backtest/_sim_kernel.py](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T108/src/backtest/_sim_kernel.py)  
判定: **Warning あり**

[Warning] `pnl_factor * price_delta` と `cash + unreal` / `cash += pnl` の overflow sentinel がありません。  
spread/margin の cross-multiply は保護されましたが、以下の経路は `np.int64` wrap が起きると Decimal 経路へ戻れず、trade PnL、equity、margin 判定、最終 fitness に逆流し得ます。

対象例:
```python
unreal = pnl_factor * (bid_c[i] - pos_entry)
pnl = pnl_factor * (exit_px - pos_entry)
equity_pre = cash + unreal
cash += pnl
out_equity_scaled[i] = cash + unreal_rec
```

修正案:
- `pnl_factor * delta` の前に `abs(delta) > INT64_MAX // abs(pnl_factor)` を検査し、超過なら `STATUS_OVERFLOW`。
- `cash + unreal` / `cash + pnl` の前に加算 overflow guard を入れ、超過なら `STATUS_OVERFLOW`。
- `pnl_factor` 自体の初期化時にも `abs(units) > INT64_MAX // scale_ratio` を検査。
- 最小対応としては、kernel 内の PnL 計算を小さな guarded helper 相当に寄せ、全 PnL/equity 更新箇所で同じ guard を使うのが安全です。

[src/backtest/engine.py](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T108/src/backtest/engine.py)  
判定: **APPROVED**

[Critical] なし  
[Warning] なし  
[Suggestion] なし。overflow fallback ログ追加は妥当です。

[tests/backtest/test_sim_kernel_parity.py](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T108/tests/backtest/test_sim_kernel_parity.py)  
判定: **APPROVED**

[Critical] なし  
[Warning] なし  
[Suggestion] PnL overflow fallback の専用 parity テストを 1 件追加すると、上記修正の回帰防止になります。

**全体判定**
**CHANGES_REQUESTED**

Critical はありません。Round 1 の指摘は閉じています。残る Warning は `numba int64 overflow` の対象が spread/margin cross-multiply に限定され、PnL/equity 経路が未保護な点です。ここは GA 選抜不変に直結するため、APPROVED にはできません。