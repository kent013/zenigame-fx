**施策判定**
- P2（Stage C stress の cost-robustness 化）: **REQUEST_CHANGES**

[Critical] `mark-to-market` 契約が kernel と Decimal でズレるリスクがあります。  
根拠:
- kernel の含み損益/証拠金判定は生の `bid_c/ask_c` を使用（[_sim_kernel.py:166](/Users/ishitoya/repository/zenigame-fx/src/backtest/_sim_kernel.py:166), [_sim_kernel.py:231](/Users/ishitoya/repository/zenigame-fx/src/backtest/_sim_kernel.py:231)）。
- MockBroker は `_unrealized_pnl` が `_exit_price(..., "close")` を参照（[mock.py:483](/Users/ishitoya/repository/zenigame-fx/src/broker/mock.py:483)）。
- この設計のまま `_exit_price` を multiplier 対応で instance 化すると、Decimal 経路だけ MTM/margin に stress が乗り、kernel との parity 契約（[test_sim_kernel_parity.py:1](/Users/ishitoya/repository/zenigame-fx/tests/backtest/test_sim_kernel_parity.py:1)）を壊します。

修正案（最小変更）:
- **契約を「stress は realized fill のみ」に固定**し、MockBroker の MTM は現行どおり生価格のままにする。  
  具体的には `_unrealized_pnl` で stress 付き価格経路を使わない（または `raw_exit_price` と `stressed_fill_price` を分離）。  
  kernel 側は現行どおり MTM は生価格、fill/close 分岐のみ multiplier 適用。

反証可能仮説:
- `spread_cost_multiplier=1.5` かつ margin 境界ケースで、現設計（`_exit_price` 一括 stress 化）だと kernel/Decimal の trade 列か exit_reason が不一致になる。

[Suggestion] 丸め規約は仕様に明記してください（対称性担保）。  
- `adj` は必ず非負の `spread_diff=(ask-bid)` から計算し、最後に long/short へ符号適用する形に固定（負数 `//` を使わない）。

**観点別**
1. 整数比 `num/den` 設計: **APPROVE**（上記丸め規約を明文化する前提）  
2. adverse 符号: **APPROVE**  
3. MTM への multiplier 適用要否: **REQUEST_CHANGES**（Critical）  
4. default 1.0 同一性: **INCONCLUSIVE**（3の確定後に parity regression で確証）  
5. `_exit_price` static→instance 波及: **APPROVE**  
6. `bid>ask` clamp: **APPROVE**  
7. config 伝搬/frozen 整合: **APPROVE**  
8. テスト網羅: **INCONCLUSIVE**（`m>1` の kernel-vs-decimal parity を必須追加）

**全体判定**
- **CHANGES_REQUESTED**