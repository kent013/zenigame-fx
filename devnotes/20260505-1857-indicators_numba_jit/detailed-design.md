# 詳細設計: `_indicators.py` Python loop 関数の Numba JIT 化

## 使命・制約 (絶対遵守)

### zenigame-fx Alpha Factory 使命
live_criteria 全指標同時充足 + (ii-lite) 通過で使命達成。
絶対制約: イントラデイ / ロング・ショート両方向 / スワップ・スプレッド反映。

### 禁止事項
1. A・B・C 評価期間を根拠なしに延長
2. 見た目の数値改善
3. GA ハック
4. live_criteria 緩和
5. 過度な複雑化
6. 取引回数削減で成績を見せる
7. オーバーナイト保有前提

### コーディングルール
- `uv run pytest tests/alpha_factory/primitives/` 走破
- `uv run ruff check src/ tests/` 通過
- Python 3.13 + numpy + numba (既に `pyproject.toml` に `numba>=0.61` あり、 `src/dsl/composite.py:144` 既存使用例あり)

## 概念設計リファレンス

[devnotes/20260505-1857-indicators_numba_jit/conceptual-design.md] (Round 2 APPROVED)

## 施策一覧

| # | 施策名 | 変更ファイル | 優先度 |
|---|--------|------------|--------|
| 1 | `rolling_max` Numba JIT 化 (deque → circular buffer) | `src/alpha_factory/primitives/_indicators.py:116` | High |
| 2 | `rolling_min` Numba JIT 化 (deque → circular buffer) | `src/alpha_factory/primitives/_indicators.py:137` | High |
| 3 | `_wilder_smooth` Numba JIT 化 (NaN 契約現行互換維持) | `src/alpha_factory/primitives/_indicators.py:214` | High |

(オプション 4 = `ema` line 191 は今回のスコープから外し、 余裕があれば cycle 後で追加)

## 施策 1: `rolling_max` Numba JIT 化

### 変更箇所
- ファイル: `src/alpha_factory/primitives/_indicators.py` (line 116-134)

### 波及変更
- `AGENTS.md`: なし (内部実装変更)
- `.claude/skills/zenigame-fx-*/SKILL.md`: なし
- `config/alpha_factory/default.yaml`: なし
- `docs/alpha_factory/*.md`: なし (動作不変、 速度のみ向上)

### 現行コード

```python
from collections import deque

def rolling_max(values: np.ndarray, n: int) -> np.ndarray:
    """Monotonic deque による O(N) rolling max。warmup (i<n-1) は NaN。"""
    if n <= 0:
        raise ValueError(f"n must be >= 1, got {n}")
    values = np.asarray(values, dtype=np.float64)
    length = len(values)
    out = np.full(length, np.nan, dtype=np.float64)
    dq: deque[int] = deque()
    for i in range(length):
        # ウィンドウ外になった index を左から drop
        while dq and dq[0] <= i - n:
            dq.popleft()
        # 小さい値を右から drop (strict: >= なら drop; 等値は残しておく)
        while dq and values[dq[-1]] <= values[i]:
            dq.pop()
        dq.append(i)
        if i >= n - 1:
            out[i] = values[dq[0]]
    return out
```

### 変更後コード

```python
import numba

def rolling_max(values: np.ndarray, n: int) -> np.ndarray:
    """Monotonic deque による O(N) rolling max。warmup (i<n-1) は NaN。

    Numba JIT 化 (cycle 2 profile-optimize): collections.deque を fixed-size
    int64 circular buffer (head/tail インデックス) に置換。 現行 comparator
    (`<=` で右から drop) をそのまま再現、 数値出力は現行と numerically identical。
    """
    if n <= 0:
        raise ValueError(f"n must be >= 1, got {n}")
    values = np.asarray(values, dtype=np.float64)
    return _rolling_max_jit(values, n)


@numba.njit(cache=True, fastmath=False)
def _rolling_max_jit(values: np.ndarray, n: int) -> np.ndarray:
    length = values.shape[0]
    out = np.full(length, np.nan, dtype=np.float64)
    # circular buffer: 最大 n 個保持 (window 外を drop するので n より長くならない)
    dq = np.empty(n, dtype=np.int64)
    head = 0  # buffer の先頭 index (front)
    tail = 0  # buffer の末尾 index (back exclusive)
    size = 0
    for i in range(length):
        # window 外を front から drop
        while size > 0 and dq[head] <= i - n:
            head = (head + 1) % n
            size -= 1
        # 小さい値を back から drop (strict: <= で drop = 等値も drop = 現行と一致)
        while size > 0:
            back_idx = (tail - 1 + n) % n
            if values[dq[back_idx]] <= values[i]:
                tail = back_idx
                size -= 1
            else:
                break
        # back に追加
        dq[tail] = i
        tail = (tail + 1) % n
        size += 1
        if i >= n - 1:
            out[i] = values[dq[head]]
    return out
```

### ルックアヘッドバイアスチェック (primitive 関連)
- [x] 未来バー参照なし (i のみ参照、 i+k 参照しない)
- [x] 当日確定値の先取りなし
- [x] rolling window 方向が過去方向 (window = `[i-n+1, i]`)
- [x] 正規化 → 該当なし (max のみ)
- [x] バケット / グループ平均が因果的 → 該当なし
- [x] cumsum/accumulate が因果的方向 → 該当なし

### パフォーマンスチェック
- [x] `compute_all_bars()` 経由 → 該当なし (本関数は indicator helper、 primitive 側で呼ばれる)
- [x] 内側ループ内で NumPy 関数を呼んでいない (現行も Numba 化後も pure scalar arithmetic)
- [x] SoA プロパティ → 該当なし
- [x] 同一配列のキャッシュ → 該当なし

### テスト計画
- [x] 既存テスト走破: `tests/alpha_factory/primitives/test_indicators.py:77` 周辺の rolling_max test
- [x] 既存 causality test 走破: `tests/alpha_factory/primitives/test_indicators_causality.py:84`
- [ ] 新規テスト: `test_rolling_max_numerically_identical_after_numba_jit` — Numba 化後の出力が test 内 self-contained oracle (手動 deque 実装) と完全一致 (`np.testing.assert_array_equal` for non-NaN + NaN 同位置確認)
  - cases: 通常入力 / `n=1` (edge) / 重複値が連続する系列 (comparator 契約 strict 確認)

### リスク
- circular buffer の head/tail/size 管理ミスで indexing バグ → 既存 test + 新規 parity test で検出
- `cache=True` で初回コンパイル時間 (1 回限り、 RUN 全体 < 10 秒)
- Numba JIT エラー (型推論失敗) → numpy ndarray 入出力 + scalar arithmetic で発生確率低

## 施策 2: `rolling_min` Numba JIT 化

施策 1 と完全対称。 comparator 「`>=` で右から drop」 のみ違い、 他は同一。

### 変更箇所
- ファイル: `src/alpha_factory/primitives/_indicators.py` (line 137-153)

### 変更後コード

```python
def rolling_min(values: np.ndarray, n: int) -> np.ndarray:
    """Monotonic deque による O(N) rolling min。warmup (i<n-1) は NaN。

    Numba JIT 化 (cycle 2 profile-optimize): rolling_max と完全対称、
    comparator が `>=` で右から drop の違いのみ。
    """
    if n <= 0:
        raise ValueError(f"n must be >= 1, got {n}")
    values = np.asarray(values, dtype=np.float64)
    return _rolling_min_jit(values, n)


@numba.njit(cache=True, fastmath=False)
def _rolling_min_jit(values: np.ndarray, n: int) -> np.ndarray:
    length = values.shape[0]
    out = np.full(length, np.nan, dtype=np.float64)
    dq = np.empty(n, dtype=np.int64)
    head = 0
    tail = 0
    size = 0
    for i in range(length):
        while size > 0 and dq[head] <= i - n:
            head = (head + 1) % n
            size -= 1
        while size > 0:
            back_idx = (tail - 1 + n) % n
            if values[dq[back_idx]] >= values[i]:  # rolling_max と違い >=
                tail = back_idx
                size -= 1
            else:
                break
        dq[tail] = i
        tail = (tail + 1) % n
        size += 1
        if i >= n - 1:
            out[i] = values[dq[head]]
    return out
```

### テスト計画
- [x] 既存 rolling_min test
- [x] 既存 causality test
- [ ] 新規 parity test: `test_rolling_min_numerically_identical_after_numba_jit` — test 内 self-contained oracle (手動 deque 実装)、 通常 / `n=1` / 重複値連続 cases

### リスク
施策 1 と同等。

## 施策 3: `_wilder_smooth` Numba JIT 化 (NaN 契約現行互換維持)

### 変更箇所
- ファイル: `src/alpha_factory/primitives/_indicators.py` (line 214-241)

### 波及変更
- なし (内部実装変更、 動作完全互換)

### 現行コード

```python
def _wilder_smooth(values: np.ndarray, n: int) -> np.ndarray:
    """Wilder smoothing: seed = mean(values[:n]), α = 1/n.
    warmup: out[i<n-1] = NaN。途中 NaN は前値維持。
    """
    if n <= 0:
        raise ValueError(f"n must be >= 1, got {n}")
    values = np.asarray(values, dtype=np.float64)
    length = len(values)
    out = np.full(length, np.nan, dtype=np.float64)
    if length < n:
        return out
    seed = float(np.nanmean(values[:n])) if np.any(np.isnan(values[:n])) else float(values[:n].mean())
    out[n - 1] = seed
    prev = seed
    for i in range(n, length):
        v = values[i]
        if np.isnan(v):
            out[i] = prev
            continue
        cur = (prev * (n - 1) + v) / n
        out[i] = cur
        prev = cur
    return out
```

### 変更後コード (Round 1 Critical 反映: seed 計算は Python 側維持、 recurrence のみ JIT 化)

Codex Round 1 で manual seed 計算 (`s/cnt`) と `np.nanmean` で微小差 (~4.26e-14) → exact parity 違反指摘。 修正案: seed は現行どおり Python 側で `np.nanmean/mean` を維持、 recurrence loop のみ Numba JIT 化。

```python
def _wilder_smooth(values: np.ndarray, n: int) -> np.ndarray:
    """Wilder smoothing: seed = mean(values[:n]), α = 1/n.
    warmup: out[i<n-1] = NaN。途中 NaN は前値維持 (現行契約)。

    cycle 1 profile-optimize: recurrence loop のみ Numba JIT 化、 seed は
    現行 np.nanmean/mean を維持して exact parity を保証 (Codex Round 1 指摘)。
    """
    if n <= 0:
        raise ValueError(f"n must be >= 1, got {n}")
    values = np.asarray(values, dtype=np.float64)
    length = len(values)
    out = np.full(length, np.nan, dtype=np.float64)
    if length < n:
        return out
    # seed: 現行と完全に同一の演算順序で計算 (exact parity 保証)
    seed = float(np.nanmean(values[:n])) if np.any(np.isnan(values[:n])) else float(values[:n].mean())
    if not np.isfinite(seed):
        # 全 NaN 等で seed = NaN → out は全区間 NaN のまま return (現行と整合)
        return out
    out[n - 1] = seed
    # recurrence loop のみ Numba JIT 化 (途中 NaN 前値維持の semantics 維持)
    _wilder_smooth_recurrence_jit(values, out, n, seed)
    return out


@numba.njit(cache=True, fastmath=False)
def _wilder_smooth_recurrence_jit(
    values: np.ndarray,
    out: np.ndarray,
    n: int,
    seed: float,
) -> None:
    """In-place: out[n:length] を recurrence で埋める。 out[n-1]=seed は呼び出し側で設定済。"""
    length = values.shape[0]
    prev = seed
    inv_n_m1 = float(n - 1)
    inv_n = float(n)
    for i in range(n, length):
        v = values[i]
        if v == v:  # not NaN
            cur = (prev * inv_n_m1 + v) / inv_n
            out[i] = cur
            prev = cur
        else:
            # 途中 NaN は前値維持 (現行契約、 adx() の NaN parity)
            out[i] = prev
```

### ルックアヘッドバイアスチェック
- [x] 未来バー参照なし (recurrence で過去方向のみ)
- [x] 当日確定値の先取りなし
- [x] rolling window → 該当なし (recurrence)

### パフォーマンスチェック
- [x] 内側ループ内で NumPy 関数を呼んでいない
- [x] cache=True で 2 回目以降即時

### テスト計画
- [x] 既存 ATR test 走破: `tests/alpha_factory/primitives/test_indicators.py:168`
- [x] 既存 ADX test 走破: `tests/alpha_factory/primitives/test_indicators.py:261`
- [x] 既存 causality test 走破
- [ ] 新規 parity test: `test_wilder_smooth_numerically_identical_after_numba_jit` — 現行 oracle 実装 (test 内 plain Python) と Numba 化版で:
  - 全ての non-NaN entry で `assert_array_equal` (bit-identical 保証)
  - NaN 同位置 (`np.isnan(out)` 一致)
  - 入力 cases: (a) 全 finite (b) 先頭 n 個に NaN 1 個 (c) 途中に NaN 1 個 (d) 全 NaN (e) length < n
- [ ] 新規 parity test: `test_adx_via_wilder_smooth_numba_parity` — adx() 全体で出力が現行と一致 (warmup NaN 含む)

### リスク
- `n - 1` 等の int → float64 cast 精度: `(prev * inv_n_m1 + v) / inv_n` 形で現行 Python 式と等価
- `seed = NaN` (全 NaN seed) 時の挙動: 現行 `np.nanmean` は warning 出して NaN 返す → out 全 NaN。 Round 2 修正版は **`np.isfinite(seed)` で early return** で同一挙動 + warning は維持 (Python 側計算なので)
- recurrence loop の prev 更新は in-place、 out array が呼び出し側のリファレンス書き込み

## 実装モード

| 項目 | 内容 |
|------|------|
| 推奨モード | **incremental** |
| 判断根拠 | 単一ファイル (`_indicators.py`) の 3 関数 + 既存 test 走破で完結。 他 cycle (cycle 2/3, 3/3) と競合しない |
| 競合リスク | なし (`_indicators.py` 内のみ、 他施策 (broker mock, DSL composite) と独立) |
| 想定実装時間 | 中 (各関数 + parity test で 1-2 時間) |

## 実装順序 (TODO 化時)

1. parity test 先行作成 (現行 oracle 実装を test 内に保持) → FAIL 確認 (Numba 版未実装)
2. `_rolling_max_jit` / `_rolling_min_jit` 実装 → 該当 parity test PASS 確認
3. `_wilder_smooth_jit` 実装 → adx parity test PASS 確認
4. `import numba` 追加 + 既存 wrapper 関数を JIT delegating に書換
5. 全テスト走破 (`uv run pytest tests/alpha_factory/primitives/`) + ruff check + mypy check
6. profile 再走 (Phase 7) で削減効果確認

## 全体使命チェック

| 禁止事項 | 抵触 | 根拠 |
|---|---|---|
| 1. 評価期間延長 | なし | 不変 |
| 2. 見た目数値改善 | なし | 数値出力 numerically identical |
| 3. GA ハック | なし | 不変 |
| 4. 閾値緩和 | なし | 不変 |
| 5. 過度な複雑化 | **微注意** | 1 ファイル 3 関数の Numba 化、 既存 deque を circular buffer に置換 (1 層追加)、 「3 層以上」 の警告 (zenigame skill ガイド) には該当しない (本 repo の Numba 採用は composite.py のみで合計 2 層) |
| 6. 取引回数削減 | なし | 不変 |
| 7. オーバーナイト保有 | なし | 不変 |

cycle 1/3 detailed-design は mission alignment OK。 既存 NaN 契約完全互換。
