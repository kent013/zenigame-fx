[Critical] `margin_call` の cross-multiply 式にスケール変換が欠落しています（詳細設計 §2-2, §5）  
Fact: 提案式 `equity*100*leverage < maint*units*entry_price` は、`equity` が `CASH_SCALE=1e8`、`entry_price` が `PRICE_SCALE=1e5` のまま直接比較されています。  
Interpretation: しきい値が実質 1000 倍ずれ、マージンコールが遅延し、GA 選抜不変契約を破ります。  
修正案: 比較式を次のどちらかに統一してください。  
- `equity_scaled * 100 * leverage * maint_den < maint_num * units * entry_price_scaled * (CASH_SCALE/PRICE_SCALE)`  
- または `entry_price_cash_scaled = entry_price_scaled * 1000` を保持して比較。  

[Critical] same-bar `fill` 後の `margin_call` 判定で equity 再計算が仕様上不明確です（詳細設計 §3 pseudocode, [engine.py](/Users/ishitoya/repository/zenigame-fx/src/backtest/engine.py:147)）  
Fact: 擬似コードは step3 で計算した `equity` を step6 でも使う読みに見えます。  
Interpretation: 現行は `fill_pending`→`mark_to_market`→`force_close_if_margin_call` の順で、同一 bar の新規建玉を含めて判定するため、ここがズレると分岐が変わります。  
修正案: step6 直前で `equity_now = cash + unrealized(close価格基準)` を必ず再計算し、その値のみで margin 判定。  

[Warning] `margin_used` 二段丸めに対する「gap 10^-14 vs Decimal 10^-28」論拠は条件付きでのみ成立します（詳細設計 §2-2, [mock.py](/Users/ishitoya/repository/zenigame-fx/src/broker/mock.py:502)）  
Fact: 現行は `required_margin = notional/leverage` と `margin_level = equity/margin_used*100` の2段です。  
Interpretation: `required_margin` に quantize/丸めが入る実装だと、notional 直接 cross-multiply は一致保証を失います。  
修正案: `margin.py` 実装を確定検証し、quantize があるなら「実際に保存した entry_margin」を基準に比較式を組むか、該当ケースを Decimal 経路へフォールバック。  

[Warning] `pending_kind` 単値化は現行の複数 signal submit ループと契約差分の可能性があります（[engine.py](/Users/ishitoya/repository/zenigame-fx/src/backtest/engine.py:173)）  
Fact: 現行は `for signal in signals: broker.submit(signal)` で複数投入可能です。  
Interpretation: kernel が 1 件のみ保持すると、将来の strategy 変更で挙動差分が出ます。  
修正案: kernel 前に `len(signals)<=1` 等の不変条件を assert するか、queue セマンティクスを現行同等で実装。  

[Warning] composite 全bar一括化の bit 同一性は未決着です（詳細設計 §8-1）  
Fact: 設計書自身が unresolved としています。  
Interpretation: この状態では「selection-invariant performance-only」の承認条件未達です。  
修正案: 初版は per-index 同一 njit 関数呼び出しのみ許容し、`fastmath=False`/`parallel=False` 固定で golden 合格後に段階最適化。  

[Warning] overflow 評価は scale 補正後と分母付き閾値で再計算が必要です（詳細設計 §5）  
Fact: 現行上界計算は margin 右辺を `3e13` としていますが、scale整合後は `~3e16` オーダーです。  
Interpretation: int64 余裕はまだありますが、`maint_den/max_spread_den` 導入時の乗算順で余裕が縮みます。  
修正案: 起動時 preflight で `max(abs(price_scaled))` と係数から厳密上界を検証し、危険時は Decimal 経路へ fail-safe。  

---

**施策別判定**  
1. 施策1（columnar 変換）: **APPROVE**  
2. 施策2（njit kernel）: **REQUEST_CHANGES**  
3. 施策3（run_backtest 差し替え）: **REQUEST_CHANGES**  
4. 施策4（golden parity）: **APPROVE**  
5. 施策5（holding_cost/unprepared fallback）: **APPROVE**

---

**重点項目への回答（要点）**  
9. 数値正確性: **INCONCLUSIVE**。spread はほぼ妥当ですが、margin は scale 欠落と二段丸め前提未確定のため反証成立余地あり。  
10. overflow: **REQUEST_CHANGES**。scale補正後の式で再評価必須。  
11. 前提検証 C4: **INCONCLUSIVE**。F2 は提示抜粋で整合、F4/F5 は最新全体コードの直接検証が未完。  
12. ルックアヘッド: **概ね整合**。前bar spread・entry_delay=1・`composite[i]` 当barは設計上一致。  

A. composite 一括化: **INCONCLUSIVE**（未解決事項のまま）。  
B. event ordering/corner case: **REQUEST_CHANGES**（same-bar margin 判定と pending 複数件の表現が不足）。  
C. holding_cost>0 fallback: **APPROVE**（使命毀損はない。性能適用範囲の明示は必要）。  

---

**全体判定**: **CHANGES_REQUESTED**