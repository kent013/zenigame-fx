**Fact**
- PnL の単一積は `max_abs_price <= INT64_MAX // pnl_factor` で一括安全証明されています。
- `cash + unreal` / `cash += pnl` / equity 記録の加算には `_add_overflows` が入りました。
- PnL factor overflow と price overflow の直接テストも追加されています。
- コマンド実行制限に従い、今回も提示差分ベースの静的レビューです。

**Interpretation**
- Round 2 の主指摘である PnL/equity 経路はほぼ閉じています。
- ただし、`units` 由来の別係数 `margin_rhs_factor` が guard 前に計算され、かつ `maint_num * units * scale_ratio` の overflow guard が不足しています。これは margin call gate に逆流し得るため、まだ Warning です。

**ファイル別判定**

[src/backtest/_sim_kernel.py](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T108/src/backtest/_sim_kernel.py)  
判定: **Warning あり**

[Warning] `margin_rhs_factor` が `units` guard より前に計算され、`maint_num * units * scale_ratio` の overflow が未証明です。

該当:
```python
margin_rhs_factor = np.int64(maint_num) * np.int64(units) * np.int64(scale_ratio)

if units <= 0 or np.int64(units) > _INT64_MAX // np.int64(scale_ratio):
    return (STATUS_OVERFLOW, 0, 0, 0, 0)
pnl_factor = np.int64(units) * np.int64(scale_ratio)
```

`units <= INT64_MAX // scale_ratio` でも、`maint_num * units * scale_ratio` は overflow し得ます。`maint_num=100` なら、`units > INT64_MAX // (100 * scale_ratio)` が危険域です。

修正案:
```python
if units <= 0 or np.int64(units) > _INT64_MAX // np.int64(scale_ratio):
    return (STATUS_OVERFLOW, 0, 0, 0, 0)

pnl_factor = np.int64(units) * np.int64(scale_ratio)

if maint_num <= 0 or np.int64(maint_num) > _INT64_MAX // pnl_factor:
    return (STATUS_OVERFLOW, 0, 0, 0, 0)

margin_rhs_factor = np.int64(maint_num) * pnl_factor
```

同じ方針で、完全に閉じるなら `margin_lhs_factor = 100 * leverage * maint_den` も計算前 guard に寄せるとよいです。engine 側 preflight では通常 `leverage=3 / maint_den=1` なので実害は薄いですが、kernel 単体契約としては計算順を揃える価値があります。

[tests/backtest/test_sim_kernel.py](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T108/tests/backtest/test_sim_kernel.py)  
判定: **Warning 対応テスト不足**

[Warning] `pnl_factor` overflow はテストされていますが、`margin_rhs_factor` overflow 境界が未検証です。

追加テスト案:
```python
def test_simulate_overflow_on_margin_rhs_factor() -> None:
    units = _INT64_MAX // (1000 * 100) + 1
    status, *_ = _call(bid_c_val=15_400_000, ask_h_val=15_401_000, units=units)
    assert status == STATUS_OVERFLOW
```

**全体判定**
**CHANGES_REQUESTED**

Critical はありません。Round 2 の PnL/equity 指摘はほぼ解消済みですが、`margin_rhs_factor` の overflow guard が残っています。margin call は約定数に逆流する gate なので、ここを閉じれば APPROVED 判定でよい状態です。