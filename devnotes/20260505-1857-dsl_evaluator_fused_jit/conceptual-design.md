# 概念設計: DSL composite all-bars fused JIT (T053 拡張)

## 背景・課題

profile-optimize cycle 1/3 で profile RUN (`profile_20260505_171107`、 pop=8/gen=1/dataset 6 ヶ月) を計測した結果、 以下のボトルネックが浮かんだ:

- `evaluator.evaluate_all_bars` cumtime 5.236s / 56 calls / **0.327s/eval** (eval 内 25%)
- profile 内の `compute_composite_at_bar_jit` (T053 で Numba 化済 per-bar fused kernel) は **per-bar dispatch** で呼ばれており、 N bars 分 dispatch overhead が積算

実 RUN 投影 (直近 RUN 102 分 baseline、 profile→実 RUN 295.9 倍): **1530s = 25.5 分 (12.5%)**。

zenigame パターン 7 (Numba dispatch overhead 削減、 clause-composite 46s→18s) と同様、 per-bar dispatch を **all-bars batch dispatch** に変換することで dispatch overhead を 1 / N に削減できる。

## 改善アイデア

既存の `compute_composite_at_bar_jit(idx, ...)` を per-bar 呼び出しから、 **新規 `compute_composite_all_bars_jit(n_bars, ...)`** で全 bar を 1 回の Numba dispatch で計算する。 既存 per-bar 関数は backward compat 用に残す。

**新関数のシグネチャ案**:
```python
@numba.njit(cache=True, fastmath=False)
def compute_composite_all_bars_jit(
    n_bars: int,
    clause_weights: np.ndarray,         # float64[n_clauses]
    dir_weights_flat: np.ndarray,       # float64[total_dir]
    dir_offsets: np.ndarray,            # int64[n_clauses+1]
    dir_signal_idx: np.ndarray,         # int64[total_dir]
    gate_offsets: np.ndarray,           # int64[n_clauses+1]
    gate_signal_idx: np.ndarray,        # int64[total_gate]
    unique_signal_matrix: np.ndarray,   # float64[n_unique, n_bars]
    out_clause_scores: np.ndarray,      # float64[n_bars, n_clauses] (per-bar buffer 拡張)
) -> np.ndarray:                         # float64[n_bars] composite score per bar
    """全 bar を 1 回の dispatch で計算。 内部は既存 per-bar ロジック × n_bars loop."""
    composite = np.zeros(n_bars, dtype=np.float64)
    for idx in range(n_bars):
        # 既存 per-bar logic (clause loop + dir/gate accumulator)
        ...
    return composite
```

呼び出し側 (`DslStrategy.prepare` or `evaluator.evaluate_all_bars` 経路) で per-bar Python loop を all-bars 1 回 dispatch に置き換え。

## 期待効果

- **DSL composite eval の dispatch overhead 削減**: 86400 bars × N clauses → 1 回 dispatch
- **本番 RUN 削減**: 25.5 分 → 12-15 分 (50-60% 削減見込み、 zenigame パターン 7 で 46s→18s 実証)
- **累積効果**: cycle 1/3 単独で **本番 RUN 100 分 → ~88-90 分 (12.5% 削減)**
- **副次効果**: cycle 2/3 (`_indicators` Numba) と組み合わせで累積 ~17%

## 実装方針 (概要)

### 変更コンポーネント

1. **`src/dsl/composite.py`**: `compute_composite_all_bars_jit` 関数新規追加 (既存 `compute_composite_at_bar_jit` は backward compat 維持)
2. **`src/dsl/strategy.py`** (または `evaluator.evaluate_all_bars` 周辺): per-bar dispatch を all-bars 1 回 dispatch に置き換え
3. **`src/alpha_factory/primitives/evaluator.py`**: `evaluate_all_bars` で composite kernel 呼び出し経路を変更

### 数値同値性保証

- 内部ロジック (clause loop + dir/gate accumulator + Σ|cw| 正規化) は **既存 per-bar 実装と完全同一**、 ループ範囲のみ拡張
- bit-identical 保証: per-bar と all-bars で同じ順序の演算 (clause loop 内側、 bar loop 外側)
- 数値テスト: `np.allclose(per_bar_result, all_bars_result, atol=1e-12)` で完全一致確認

### Stage A/B/C 評価結果の不変性

- Stage A pass count、 Stage B pass count、 Stage C pass count、 best fitness_pen が **完全に同一値** であることを既存テスト (test_archive, test_stage_gate) で確認
- 副作用なし、 純粋に dispatch overhead のみ削減

## 制約・前提

- **FX 絶対制約**: イントラデイ強制クローズ / ロング・ショート両方向 / swap・spread 反映 — DSL composite 計算は signal 値計算のみで取引執行に関わらず、 制約への影響なし
- **メモリ制約**: 24GB メモリ / 6 ワーカー / 1 ワーカー 3GB — `out_clause_scores` を `float64[n_bars, n_clauses]` に拡張する場合、 86400 × 32 (max_clauses) × 8 bytes ≈ 22 MB / lane → 6 worker × 22 MB = 132 MB で問題なし
- **既存テスト**: `tests/dsl/`、 `tests/alpha_factory/test_archive.py` 等が既存 per-bar 実装に依存していないこと (composite kernel の output のみ依存) を前提
- **Numba dispatch overhead 削減効果**: zenigame パターン 7 で実証済 (46s→18s、 60% 削減)、 但し composite kernel 内部の per-bar loop の Python overhead が無視できる規模 (2.7s/16 evals = 0.169s/eval) かは Codex レビューで検証

## スコープ外

- `_indicators.py` の wilder_smooth / rolling_max/min Numba 化 (cycle 2/3 で対応予定)
- broker mock 系の Decimal 演算改善 (Decimal 型故 Numba 不可、 cycle スコープ外)
- `evaluate_all_bars` の signal_matrix precompute 経路の変更 (本施策では composite kernel のみ変更、 primitive eval 経路は不変)
- `compute_composite_at_bar_jit` の削除 (backward compat 維持、 別 cycle で必要時に整理)

## 参考

- 既存実装: `src/dsl/composite.py:144 compute_composite_at_bar_jit` (T053)
- T053 詳細設計: `devnotes/20260427-1723-composite-numba-jit/detailed-design.md`
- zenigame パターン 7 実証: clause-composite 15-20 NumPy ops → 1 JIT call、 46s→18s
- profile データ: `.cache/alpha_factory/runs/profile/profile_20260505_171107.txt`
