# 概念設計: `_bars_cache._compute` Python loop 軽量化 (bid/ask local 化)

## 背景・課題

profile-optimize cycle 3/3 で profile RUN (`profile_20260505_211017`、 cycle 2/3 後 baseline) を計測した結果:

| 関数 | profile tottime | 呼び出し回数 | per-call | 本番投影 (×295.9) |
|---|---|---|---|---|
| `_compute` (line 59) | 1.160s | 15 | **77ms/call** | 343s = 5.7 分 |

実 RUN baseline 102 分 (cycle 1+2 後 ~94 分) に対して **5.7 分 = 5.7%** の hot path。

現実装 (line 59-84):
```python
for i, b in enumerate(bars):
    bo = float(b.bid.open)
    bh = float(b.bid.high)
    bl = float(b.bid.low)
    bc = float(b.bid.close)
    ao = float(b.ask.open)
    ah = float(b.ask.high)
    al = float(b.ask.low)
    ac = float(b.ask.close)
    o[i] = (bo + ao) * 0.5
    ...
```

`b.bid` / `b.ask` の attribute access が 1 bar あたり 8 回発生 (`bid.open` / `bid.high` / ... 各 1 回)。 86,400 bars × 8 access × 15 calls = **10.4M attribute access** が hot loop 内で発生。

## 改善アイデア

`b.bid` / `b.ask` を **1 bar あたり 1 回ずつローカル変数化** して attribute access を削減:

```python
for i, b in enumerate(bars):
    bid = b.bid  # 1 access
    ask = b.ask  # 1 access
    o[i] = (float(bid.open) + float(ask.open)) * 0.5
    h[i] = (float(bid.high) + float(ask.high)) * 0.5
    low[i] = (float(bid.low) + float(ask.low)) * 0.5
    c[i] = (float(bid.close) + float(ask.close)) * 0.5
```

attribute access: 8 → 2 (per bar)。 86,400 × 6 access × 15 calls = **7.8M access 削減**。

scope 純化 (Round 1 Codex Critical 反映):
- 中間変数 `bo, bh, bl, bc, ao, ah, al, ac` 削除 (compute 直接化、 直接 mid 計算)
- **`enumerate(bars)` 維持** (`range(len(bars))` は別最適化で混ぜない、 `Sequence[PriceBar]` 抽象境界遵守)

## 期待効果 (Round 1 Codex Critical 反映: 保守化)

主因は `float(Decimal)` 8 回 + ndarray 代入 4 回が大半を占め、 bid/ask local 化で削れるのは `LOAD_ATTR` のみ。 支配項は丸ごと潰せないため:

- `_compute` per-call 77ms → 65-73ms (**5-15% 削減、 first hypothesis**)
- profile tottime 1.160s → 0.99-1.10s
- **本番 RUN 削減 first hypothesis**: 0.5-1.5% (target 1.5% は upside)
- 反証可能仮説: 「主因は `float(Decimal)` 8 回であり、 bid/ask local 化の局所改善は 5-15% (低 teens 以下) に留まる」

DoD (Round 1 修正): `microbenchmark で非退行 + 改善確認` + `profile 再計測で _compute tottime が減ること`。 ratio<0.85 必須 gate は外す。

## 実装方針 (概要)

### 変更コンポーネント

1. **`src/alpha_factory/primitives/_bars_cache.py:59-84`**:
   - `_compute` 関数本体の Python loop を bid/ask ローカル変数化
   - 中間変数削除で直接 mid 計算に
   - 数値同値性: 出力 4 つの ndarray が現行と完全一致 (`np.array_equal`)

### Numba 不要

`b.bid` / `b.ask` は Decimal 経由なので Numba JIT 不可 (cycle 1/3 broker mock と同じ理由)。 純 Python の最適化のみ。

### 数値同値性保証

- 演算順序完全同一 (`(bid_open + ask_open) * 0.5` の bid 先 ask 後)
- 浮動小数点キャスト順序同一 (`float(bid.open)` の前段で `bid = b.bid` だけが追加)
- 出力 ndarray dtype/shape/値 完全一致
- 既存 test (`tests/alpha_factory/primitives/test_bars_cache.py`) 全 pass

## 制約・前提

- **FX 絶対制約**: bid/ask mid 計算は signal 値計算用、 取引執行・PnL 計算とは別経路で **影響なし**
- **メモリ制約**: 影響なし (Round 1 Suggestion: stack 軽量化は微差で意思決定論点から外す)
- **既存契約**: read-only ndarray 返却契約 (T030 設計、 caller の in-place 変更禁止) 維持
- **cycle 1+2 累積効果**: cycle 1/3 で `_indicators.py` Numba 化 (T088, ~7.7% 削減)、 cycle 2/3 で `compute_bucket_for_bar` lookup table (T089, ~1.7% 削減) → cycle 3/3 で 1.5-3% 追加なら累積 ~10-12%
- **microbenchmark**: 概念上の attribute access 削減効果は CPython 実装依存、 microbenchmark で **非退行 + 改善確認** (現行 oracle vs 軽量版で軽量版が遅くないこと、 望ましくは僅かに速いこと)。 必須 gate ではなく観測。 加えて profile 再計測で `_compute` tottime が下がることを確認

## スコープ外

- broker mock Decimal → float64 変換 (大規模型変更、 swap/spread 数値精度懸念、 別 cycle で検討)
- DSL composite kernel 拡張 (前 cycle で reject 済)
- per-bar logging 削減 (profile 上 hot path 外、 zenigame パターン 6 は本 RUN 効果なし)
- bars 構造そのものの変更 (Decimal → float64 移行は別 cycle)
- `bars_to_mid_ohlc` cache logic (T030 で既に実装済、 incremental 化困難)

## 参考

- profile data: `.cache/alpha_factory/runs/profile/profile_20260505_211017.txt`
- 既存実装: `src/alpha_factory/primitives/_bars_cache.py:59-84` (T030)
- T030 詳細設計: `devnotes/20260427-1xxx-T030-*` (もしあれば)
- cycle 1+2 完了パターン: T088 / T089
- cycle 1+2 改善累積: ~10% (本番 102 分 → 92 分)
