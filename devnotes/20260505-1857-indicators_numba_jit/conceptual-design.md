# 概念設計: `_indicators.py` の Python loop 関数を Numba JIT 化 (Round 2 修正版)

## 背景・課題

profile-optimize cycle 1/3 で `src/alpha_factory/primitives/_indicators.py` の以下 Python loop 関数が hot path:

| 関数 | profile tottime | 呼び出し回数 | 本番投影 (×295.9) |
|---|---|---|---|
| `_wilder_smooth` (line 214) | 1.000s | 28 | 296s = 4.9 分 |
| `rolling_max` (line 116) | 0.465s | 14 | 138s = 2.3 分 |
| `rolling_min` (line 137) | 0.463s | 14 | 137s = 2.3 分 |
| `ema` (line 191) | 0.262s | - | 78s = 1.3 分 |
| **合計** | **~2.2s** | | **~650s = 10.8 分** |

これらは再帰または monotonic deque で配列単位ベクトル化不可、 Numba JIT 化に最適。 zenigame パターン 2 実証 (parser._ema 76s→5s = 93%、 searchsorted 77s→5s = 93%) より類推。

## 期待効果 (Round 2 で段階化)

- **target 関数群 (関数局所)**: 50-70% 削減 (zenigame 類推)
- **RUN 全体 first hypothesis**: 3-6% 削減 (本番 100 分 → 94-97 分)
- **RUN 全体 upside**: 5-8% (zenigame 高水準実績の場合)

## 改善アイデア

`_indicators.py` の 3 関数 (まず) に `@numba.njit(cache=True, fastmath=False)` 追加。 シグネチャ・semantics 不変。

### 対象関数 (Round 2 確定)

1. **`rolling_max(values, n)`** (line 116): monotonic deque → fixed-size circular buffer (numpy ndarray) 置換
2. **`rolling_min(values, n)`** (line 137): 同上
3. **`_wilder_smooth(values, n)`** (line 214): NaN 契約 **現行互換維持** で Numba 化
4. (オプション) `ema` (line 191): 余裕あれば追加

### Round 1 Codex 指摘への対応

#### `_wilder_smooth` の NaN 契約現行互換維持 (Critical 対応)

現行 `_wilder_smooth` は:
- seed: `np.nanmean(values[:n])` if NaN を含む else `values[:n].mean()`
- 途中 NaN: 前値維持 (line 234 周辺)

これは `adx()` が `dx` の warmup 区間に NaN を含むまま `_wilder_smooth(dx, n)` を呼ぶ契約 (line 468-471) と整合。 `np.mean` への置換は **不可**。

→ Numba 内で **NaN check + mean を手動実装**:
```python
@numba.njit(cache=True, fastmath=False)
def _wilder_smooth(values: np.ndarray, n: int) -> np.ndarray:
    length = values.shape[0]
    out = np.full(length, np.nan, dtype=np.float64)
    if length < n:
        return out
    # seed: NaN check 付き mean (現行 np.nanmean 等価)
    has_nan = False
    s = 0.0
    cnt = 0
    for k in range(n):
        v = values[k]
        if v == v:  # not NaN
            s += v
            cnt += 1
        else:
            has_nan = True
    if cnt == 0:
        return out  # 全 NaN
    seed = s / cnt
    out[n - 1] = seed
    prev = seed
    inv_n = 1.0 / n
    for i in range(n, length):
        v = values[i]
        if v == v:  # not NaN
            cur = inv_n * v + (1.0 - inv_n) * prev
            out[i] = cur
            prev = cur
        else:
            # 途中 NaN: 前値維持 (現行契約)
            out[i] = prev
    return out
```

これで `adx()` 経由の NaN parity を維持。

#### `rolling_max` / `rolling_min` の comparator 文言修正 (Suggestion 対応)

現行 comparator は `<=` / `>=` で等値も drop。 「現行 comparator をそのまま再現」 と書く (「等値は残す」 を削除)。

bit-identical 主張は **numerically identical** に下げる (`np.testing.assert_array_equal` for non-NaN + 同位置 NaN 整合の parity test を採用)。

### Numba 化 注意点 (再掲)

- **`deque` 不可**: `collections.deque` 非対応 → `np.empty(n, dtype=np.int64)` + head/tail インデックスで再実装
- **NaN 伝播**: `_wilder_smooth` は手動 NaN check 維持 (上記)
- **warmup logic**: `out[i<n-1] = NaN` 不変
- **`cache=True`**: 2 回目以降即時、 初回 JIT 時間は benchmark 時除外

## 制約・前提

- **FX 絶対制約**: `_indicators.py` は signal 値計算で取引執行に関与しない
- **メモリ制約**: 24GB / 6 ワーカー — 追加 workspace は O(n)、 既存 deque より悪化しない見込み (Round 1 Suggestion 対応で文言修正)
- **既存契約**: `_wilder_smooth` の NaN seed/途中 NaN 前値維持 semantics 維持 (Critical 対応)

### 既存テスト参照 (Round 1 Warning 対応で path 修正)

- `tests/alpha_factory/primitives/test_indicators.py:77, 168, 261` (`atr` / `adx` / 各種 helper)
- `tests/alpha_factory/primitives/test_indicators_causality.py:84` (look-ahead bias test)
- 追加: `_wilder_smooth` の NaN parity 確認テスト 1 本 (現行 vs Numba 化版で `np.testing.assert_array_equal` + NaN 同位置確認)
- 追加: `adx` 経由の NaN parity 確認 (`_wilder_smooth` 単体だけでなく adx 全体)

## スコープ外

- broker mock 系 (Decimal 故 Numba 不可)
- DSL composite kernel 拡張 (前 cycle で Codex 指摘 reject 済)
- per-bar logging 削減 (cycle 3/3 候補)
- `_indicators.py` の他関数 (`rolling_corr`, `rolling_sum` 等) — hot path 外

## 参考

- profile data: `.cache/alpha_factory/runs/profile/profile_20260505_171107.txt`
- 既存実装: `src/alpha_factory/primitives/_indicators.py:116, 137, 214`
- 既存 Numba: `src/dsl/composite.py:144` (T053)、 `pyproject.toml` の `numba>=0.61`
- zenigame パターン 2: `parser._ema` 76s→5s
- 関連 reject: `devnotes/20260505-1857-dsl_evaluator_fused_jit/REJECTED.md`
- Round 1 review: `conceptual-review-round-1.md`
