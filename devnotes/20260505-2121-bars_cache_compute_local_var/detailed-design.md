# 詳細設計: `_bars_cache._compute` Python loop 軽量化 (bid/ask local 化)

## 使命・制約 (絶対遵守)

### zenigame-fx Alpha Factory 使命
live_criteria 全指標同時充足 + (ii-lite) 通過。 絶対制約: イントラデイ / ロング・ショート両方向 / スワップ・スプレッド反映。

### 禁止事項 1-7
全項目に抵触なし (本施策は signal 値計算用 mid OHLC の生成軽量化、 取引執行・PnL に影響なし)。

### コーディングルール
- `uv run pytest tests/alpha_factory/primitives/`
- `uv run ruff check src/ tests/`、 `uv run mypy src/`
- Python 3.13 + numpy

## 概念設計リファレンス

[devnotes/20260505-2121-bars_cache_compute_local_var/conceptual-design.md] (Round 3 APPROVED)

## 施策一覧

| # | 施策名 | 変更ファイル | 優先度 |
|---|--------|------------|--------|
| 1 | `_compute` の bid/ask ローカル変数化 + 中間変数削除 | `src/alpha_factory/primitives/_bars_cache.py:59-84` | Medium |

## 施策 1: `_compute` Python loop 軽量化

### 変更箇所
- ファイル: `src/alpha_factory/primitives/_bars_cache.py` (line 59-84)

### 波及変更
- なし (内部実装変更、 出力同値、 caller インターフェース不変)

### 現行コード (line 59-84)

```python
def _compute(
    bars: Sequence[PriceBar],
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """mid OHLC (bid/ask 平均) を float64 配列で返す。cache 無しの pure compute。"""
    length = len(bars)
    o = np.empty(length, dtype=np.float64)
    h = np.empty(length, dtype=np.float64)
    low = np.empty(length, dtype=np.float64)
    c = np.empty(length, dtype=np.float64)
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
        h[i] = (bh + ah) * 0.5
        low[i] = (bl + al) * 0.5
        c[i] = (bc + ac) * 0.5
    return o, h, low, c
```

### 変更後コード

```python
def _compute(
    bars: Sequence[PriceBar],
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """mid OHLC (bid/ask 平均) を float64 配列で返す。cache 無しの pure compute。

    cycle 3 profile-optimize: bid/ask 属性アクセスを 1 bar あたり 1 回ずつ local 変数化、
    中間変数 (bo, bh, bl, bc, ao, ah, al, ac) を削除して直接 mid 計算。
    LOAD_ATTR 削減のみが目的、 演算順序・浮動小数点 cast 順序は完全同一。
    """
    length = len(bars)
    o = np.empty(length, dtype=np.float64)
    h = np.empty(length, dtype=np.float64)
    low = np.empty(length, dtype=np.float64)
    c = np.empty(length, dtype=np.float64)
    for i, b in enumerate(bars):
        bid = b.bid  # was: b.bid.open / b.bid.high / b.bid.low / b.bid.close で 4 回
        ask = b.ask  # was: 4 回
        o[i] = (float(bid.open) + float(ask.open)) * 0.5
        h[i] = (float(bid.high) + float(ask.high)) * 0.5
        low[i] = (float(bid.low) + float(ask.low)) * 0.5
        c[i] = (float(bid.close) + float(ask.close)) * 0.5
    return o, h, low, c
```

### ルックアヘッドバイアスチェック
- [x] 未来バー参照なし (各 bar 独立計算)
- [x] 当日確定値の先取りなし
- [x] 該当なし (mid OHLC は per-bar pure 計算、 rolling/cumsum なし)

### パフォーマンスチェック
- [x] 内側ループ内で NumPy 関数を呼んでいない (`np.empty` は外側のみ)
- [x] SoA プロパティ → 該当なし
- [x] cache hit は `bars_to_mid_ohlc` 側で既に実装済 (T030)、 本施策は `_compute` 自体の miss 時 cost 削減

### 数値同値性保証

- bid/ask の **演算順序完全同一**: `(float(bid.X) + float(ask.X)) * 0.5` で bid 先 ask 後 (現行と一致)
- 浮動小数点 cast 順序同一: `float()` を 8 回 (現行と同数)、 attribute access のみ削減
- 中間変数削除は CPython bytecode で `STORE_FAST` / `LOAD_FAST` の組を直接演算に集約、 数値結果不変
- 出力 ndarray dtype/shape/値 完全一致

### テスト計画

#### 既存テスト走破
- `tests/alpha_factory/primitives/test_bars_cache.py` 全 case (T030 で `_compute` 直呼び test 含む)

#### 新規テスト追加

- [ ] `test_compute_local_var_refactor_numerically_identical` — 軽量版が test 内 self-contained oracle (現行実装) と完全一致 (`np.array_equal` for non-NaN + `np.isnan` 同位置)、 cases:
  - 通常 case (10 bars 程度)
  - 1 bar (edge)
  - 異なる bid/ask 値の bar (open != high != low != close、 bid != ask)
  - NaN を含む bar (Decimal('NaN') が float() で nan に変換されることの確認)
- [ ] `test_compute_microbenchmark_non_regression` — 軽量版が現行 oracle 比で **遅くない** (median timing で軽量版 ≤ oracle × 1.10)、 望ましくは僅かに速い (Round 1 Codex Critical 反映: 必須 gate でなく観測)。 timing は perf_counter_ns で 25 回 median。

#### profile 再計測 (Phase 7 で実施)
- [ ] `_compute` tottime が 1.160s → 1.05s 以下 (10% 削減見込み first hypothesis)

### リスク
- **CPython bytecode 最適化挙動**: bid/ask local 化で `LOAD_ATTR` が `LOAD_FAST` に置換されるが、 CPython 3.13 の最適化次第で実効差は小さい可能性 (Codex Round 1 指摘の通り、 `float(Decimal)` が支配項)。 microbenchmark で実測確認
- **数値同値性**: 演算順序を維持していれば問題なし。 念のため `np.array_equal` で全 element 一致を assert
- **enumerate 維持**: Round 1 Codex Warning 対応で `range(len)` への変更は scope 外、 `Sequence[PriceBar]` 抽象境界維持

## 実装モード

| 項目 | 内容 |
|------|------|
| 推奨モード | **incremental** |
| 判断根拠 | 1 ファイル (`_bars_cache.py`) の 1 関数変更 + 既存 test 走破 + 新規 test 2 本。 cycle 1+2 と独立 |
| 競合リスク | なし |
| 想定実装時間 | 短 (30 分-1 時間、 軽微 refactor + parity test) |

## 実装順序

1. `_compute` 関数本体を bid/ask local 化 + 中間変数削除に書換 (現行式と数学的同値)
2. 新規テスト 2 本追加 (parity + microbenchmark non-regression)
3. 既存テスト走破: `uv run pytest tests/alpha_factory/primitives/test_bars_cache.py` + 関連
4. ruff / mypy 確認
5. profile 再走 (Phase 7) で `_compute` tottime 削減確認

## 全体使命チェック

| 禁止事項 | 抵触 | 根拠 |
|---|---|---|
| 1-7 | なし | 全項目影響なし (signal 値計算 + 出力完全同値) |

cycle 3/3 detailed-design は mission alignment OK。 出力完全同値、 attribute access 削減のみ。
