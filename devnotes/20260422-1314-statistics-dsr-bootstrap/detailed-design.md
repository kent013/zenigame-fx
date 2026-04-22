# 詳細設計: statistics-dsr-bootstrap

概念設計: [conceptual-design.md](./conceptual-design.md)
Codex review log: [codex-review-log.md](./codex-review-log.md)

## 1. 実装対象

| パス | 種別 | 備考 |
|------|------|------|
| `src/alpha_factory/__init__.py` | 新規 | 空パッケージ。後続 TODO で `stage_gate.py` / `archive.py` / `cross_pair.py` 等が追加される |
| `src/alpha_factory/statistics.py` | 新規 | 3 関数 + 2 内部関数（Acklam inverse CDF, 標準正規 CDF） |
| `tests/alpha_factory/__init__.py` | 新規 | 空 |
| `tests/alpha_factory/test_statistics.py` | 新規 | テストファイル |
| `pyproject.toml` | 修正 | `numpy>=1.26` を `[project.dependencies]` に追加 |
| `docs/alpha_factory/statistics.md` | 修正 | DSR / block bootstrap セクション詳細化、関数 signature・使用例 |

## 2. `src/alpha_factory/__init__.py`

```python
"""zenigame-fx Alpha Factory パッケージ。

Phase 2 では統計検定 (`statistics`) のみ。Phase 3 以降で stage_gate / archive / cross_pair
などのモジュールが追加される。
"""
```

（空 docstring のみで十分。明示的な re-export は後続 TODO で段階追加。）

## 3. `src/alpha_factory/statistics.py`

### 3.1 ファイル頭のドキュメンテーション

```python
"""Stage Gate 用の統計検定最小セット。

- deflated_sharpe_ratio  — Bailey & López de Prado (2014)
- fold_sign_ratio        — Walk-Forward fold 間の Sharpe 符号一貫性
- block_bootstrap_sharpe_ci — Kunsch (1989) moving block bootstrap による Sharpe CI

純関数・NumPy のみ依存。SciPy は使用しない（標準正規 CDF / inverse CDF は内部で
近似実装）。

参考文献:
- Bailey, D. H. & López de Prado, M. M. (2014). "The Deflated Sharpe Ratio:
  Correcting for Selection Bias, Backtest Overfitting, and Non-Normality."
  Journal of Portfolio Management, 40(5), 94–107.
- Bailey, D. H. & López de Prado, M. M. (2012). "The Sharpe Ratio Efficient
  Frontier." Journal of Risk, 15(2), 3–44.  (PSR 参照)
- Kunsch, H. R. (1989). "The Jackknife and the Bootstrap for General Stationary
  Observations." Annals of Statistics, 17(3), 1217–1241.
- Politis, D. N. & Romano, J. P. (1994). "The Stationary Bootstrap."
  Journal of the American Statistical Association, 89(428), 1303–1313.
- Acklam, P. J. (1998). "An algorithm for computing the inverse normal
  cumulative distribution function." https://web.archive.org/.../Acklam.
"""
```

### 3.2 内部関数: 標準正規 CDF / inverse CDF

#### 3.2.1 標準正規 CDF `_norm_cdf`

`math.erf` を使って実装:

```python
import math

def _norm_cdf(x: float) -> float:
    """標準正規分布 CDF Φ(x)。math.erf ベース。"""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))
```

#### 3.2.2 標準正規 Inverse CDF `_norm_ppf`

Acklam (1998) の有理関数近似。`p` は `(1e-15, 1 - 1e-15)` に clip。

```python
_ACKLAM_A = (
    -3.969683028665376e+01,
     2.209460984245205e+02,
    -2.759285104469687e+02,
     1.383577518672690e+02,
    -3.066479806614716e+01,
     2.506628277459239e+00,
)
_ACKLAM_B = (
    -5.447609879822406e+01,
     1.615858368580409e+02,
    -1.556989798598866e+02,
     6.680131188771972e+01,
    -1.328068155288572e+01,
)
_ACKLAM_C = (
    -7.784894002430293e-03,
    -3.223964580411365e-01,
    -2.400758277161838e+00,
    -2.549732539343734e+00,
     4.374664141464968e+00,
     2.938163982698783e+00,
)
_ACKLAM_D = (
     7.784695709041462e-03,
     3.224671290700398e-01,
     2.445134137142996e+00,
     3.754408661907416e+00,
)
_ACKLAM_P_LOW = 0.02425
_ACKLAM_P_HIGH = 1.0 - 0.02425
_NORM_PPF_EPS = 1e-15


def _norm_ppf(p: float) -> float:
    """標準正規分布の inverse CDF Φ⁻¹(p)。Acklam (1998) の有理関数近似。

    p=0 または p=1（および範囲外・NaN）は `ValueError`。
    開区間 (0, 1) の内部点に対してのみ、数値安定のため
    `[_NORM_PPF_EPS, 1 - _NORM_PPF_EPS]` に clip してから計算する。
    誤差は倍精度で概ね 1.15e-9 級（Acklam 1998 の報告値）。
    """
    if not (isinstance(p, (int, float)) and math.isfinite(p) and 0.0 < p < 1.0):
        raise ValueError(f"p must be a finite number in open interval (0, 1); got {p}")
    # 内部点のみ clip（0/1 は既に弾いている）
    p = min(max(p, _NORM_PPF_EPS), 1.0 - _NORM_PPF_EPS)
    if p < _ACKLAM_P_LOW:
        q = math.sqrt(-2.0 * math.log(p))
        num = ((((_ACKLAM_C[0]*q + _ACKLAM_C[1])*q + _ACKLAM_C[2])*q + _ACKLAM_C[3])*q + _ACKLAM_C[4])*q + _ACKLAM_C[5]
        den = (((_ACKLAM_D[0]*q + _ACKLAM_D[1])*q + _ACKLAM_D[2])*q + _ACKLAM_D[3])*q + 1.0
        return num / den
    if p <= _ACKLAM_P_HIGH:
        q = p - 0.5
        r = q * q
        num = ((((_ACKLAM_A[0]*r + _ACKLAM_A[1])*r + _ACKLAM_A[2])*r + _ACKLAM_A[3])*r + _ACKLAM_A[4])*r + _ACKLAM_A[5]
        den = ((((_ACKLAM_B[0]*r + _ACKLAM_B[1])*r + _ACKLAM_B[2])*r + _ACKLAM_B[3])*r + _ACKLAM_B[4])*r + 1.0
        return q * num / den
    # upper tail
    q = math.sqrt(-2.0 * math.log(1.0 - p))
    num = ((((_ACKLAM_C[0]*q + _ACKLAM_C[1])*q + _ACKLAM_C[2])*q + _ACKLAM_C[3])*q + _ACKLAM_C[4])*q + _ACKLAM_C[5]
    den = (((_ACKLAM_D[0]*q + _ACKLAM_D[1])*q + _ACKLAM_D[2])*q + _ACKLAM_D[3])*q + 1.0
    return -num / den
```

### 3.3 `deflated_sharpe_ratio`

```python
_EULER_GAMMA = 0.5772156649015329

def deflated_sharpe_ratio(
    sharpe_ratio: float,
    n_trials: int,
    n_observations: int,
    skew: float,
    kurtosis: float,
    mean_sr_trials: float,
    std_sr_trials: float,
) -> float:
    """Bailey & López de Prado (2014) の Deflated Sharpe Ratio。

    観測 Sharpe Ratio が、N 個の独立試行の最大値 (null hypothesis: 真の SR=0) を
    有意に上回る確率を返す。0..1 の範囲。0.95 以上で 5% 水準で有意。

    Args:
        sharpe_ratio: 観測 Sharpe Ratio SR_obs。**bar 単位 (non-annualized)**。
            年率値を渡すと結果が歪む。呼び出し元で年率→bar 変換のこと。
        n_trials: 独立試行相当数 N (>= 2)。N=1 の場合は DSR ではなく
            PSR (Bailey & López de Prado 2012) を使うこと。
        n_observations: 観測 bar 数 T (>= 2)。
        skew: リターン分布の歪度（3 次中心モーメント / σ³）。正規分布で 0。
        kurtosis: リターン分布の尖度（non-excess、4 次中心モーメント / σ⁴）。
            正規分布で 3.0。excess kurtosis を渡さないこと。
        mean_sr_trials: 試行候補 SR 分布の平均。
        std_sr_trials: 試行候補 SR 分布の標準偏差 (> 0)。

    Returns:
        DSR ∈ [0, 1]。

    Raises:
        ValueError: n_trials < 2, n_observations < 2, std_sr_trials <= 0,
            または DSR 分母平方根の内側が非正。

    Notes:
        - 分母の SR 項には SR_obs を使う（Bailey & López de Prado 2014 Eq.(9) 原著表記）。
        - Acklam (1998) の有理関数近似で inverse normal CDF を計算。
    """
    # float 引数の有限値ガード（nan/inf を弾く）
    for name, val in (
        ("sharpe_ratio", sharpe_ratio),
        ("skew", skew),
        ("kurtosis", kurtosis),
        ("mean_sr_trials", mean_sr_trials),
        ("std_sr_trials", std_sr_trials),
    ):
        if not math.isfinite(float(val)):
            raise ValueError(f"{name} must be finite (got {val}).")
    if n_trials < 2:
        raise ValueError(f"n_trials must be >= 2 (got {n_trials}); use PSR for single trial.")
    if n_observations < 2:
        raise ValueError(f"n_observations must be >= 2 (got {n_observations}).")
    if std_sr_trials <= 0:
        raise ValueError(f"std_sr_trials must be > 0 (got {std_sr_trials}).")

    # Eq.(7): Expected Max SR
    q1 = _norm_ppf(1.0 - 1.0 / n_trials)
    q2 = _norm_ppf(1.0 - 1.0 / (n_trials * math.e))
    expected_max_sr = mean_sr_trials + std_sr_trials * ((1.0 - _EULER_GAMMA) * q1 + _EULER_GAMMA * q2)

    sr = float(sharpe_ratio)
    T = n_observations
    denom_sq = 1.0 - skew * sr + ((kurtosis - 1.0) / 4.0) * sr * sr
    if denom_sq <= 0.0:
        raise ValueError(
            f"DSR denominator radicand non-positive ({denom_sq}); check skew/kurtosis/SR inputs."
        )
    z = ((sr - expected_max_sr) * math.sqrt(T - 1)) / math.sqrt(denom_sq)
    return _norm_cdf(z)
```

### 3.4 `fold_sign_ratio`

```python
def fold_sign_ratio(fold_sharpes: list[float]) -> float:
    """Walk-forward fold 間の Sharpe 符号反転比率（0..1）。

    ゼロは符号なしとして扱い、直前の非ゼロ符号と比較する（carry-forward）。
    反転 = 直前 fold の非ゼロ符号と現 fold の非ゼロ符号が異なる。

    例:
        [+1, -1, +1, -1] → 1.0 (3 回反転 / 3)
        [+1, +1, +1]    → 0.0
        [+1, 0, -1]     → 0.5 (1 回反転 / 2)
        [0, 0, +1]      → 0.0 (符号カウント対象なし)
        []              → 0.0
        [1.0]           → 0.0

    Args:
        fold_sharpes: fold ごとの Sharpe のリスト。

    Returns:
        符号反転比率 ∈ [0, 1]。
    """
    n = len(fold_sharpes)
    if n < 2:
        return 0.0
    prev_sign = 0  # 0 = 未確定 (まだ非ゼロ符号が出ていない)
    sign_changes = 0
    for i, s in enumerate(fold_sharpes):
        curr = 0
        if s > 0:
            curr = 1
        elif s < 0:
            curr = -1
        # 反転判定は非ゼロ同士でのみ
        if i > 0 and curr != 0 and prev_sign != 0 and curr != prev_sign:
            sign_changes += 1
        if curr != 0:
            prev_sign = curr
    return sign_changes / (n - 1)
```

### 3.5 `block_bootstrap_sharpe_ci`

```python
import numpy as np

def block_bootstrap_sharpe_ci(
    returns: np.ndarray,
    block_size: int,
    n_bootstrap: int = 1000,
    alpha: float = 0.05,
    *,
    seed: int,
) -> tuple[float, float]:
    """Moving block bootstrap による bar 単位 Sharpe Ratio の (lower, upper) CI。

    Kunsch (1989) の moving block bootstrap。時系列依存を保ったままリサンプリング
    し、Sharpe の信頼区間を返す。Phase 2 では monitor 用 CI。Hard gate 化や
    block length 自動選択は後続 TODO（stationary bootstrap, Politis & White 2004）
    で扱う。

    Args:
        returns: 1 次元リターン系列（bar 単位、length T）。
        block_size: ブロック長（>= 1, <= T）。呼び出し元で時系列の自己相関減衰
            スケールに合わせて指定する（default なし、必須）。
        n_bootstrap: bootstrap 標本数。default 1000。
        alpha: 両側有意水準 (0, 1)。default 0.05 で 95% CI。
        seed: 乱数シード（必須）。決定論性を保証するため int を必ず渡す。
            `None` を許容しない（同一入力で出力が変わる non-pure 呼び出しを禁止）。

    Notes on purity:
        本関数は `seed` が int のときに pure function として振る舞う（同一入力→同一出力）。
        OS エントロピー源には触れない。テスト・retrieve reproducibility のため
        seed は呼び出し側が明示的に管理する責任を持つ。

    Returns:
        (lower, upper) — bar 単位 Sharpe の (1-alpha) 信頼区間の両端。
        呼び出し元で年率化 (× sqrt(periods_per_year)) すること。

    Raises:
        ValueError: returns のサイズ・block_size・alpha・std が不正、returns に
            nan/inf が含まれる、または全 bootstrap 標本で std=0 (退化) のとき。
        TypeError: seed が int でないとき。
    """
    arr = np.asarray(returns, dtype=np.float64).ravel()
    T = arr.size
    if T < 2:
        raise ValueError(f"returns must have length >= 2 (got {T}).")
    if not np.isfinite(arr).all():
        raise ValueError("returns contains non-finite values (nan/inf).")
    if block_size < 1:
        raise ValueError(f"block_size must be >= 1 (got {block_size}).")
    if block_size > T:
        raise ValueError(f"block_size ({block_size}) must be <= len(returns) ({T}).")
    if not (0.0 < alpha < 1.0):
        raise ValueError(f"alpha must be in (0, 1) (got {alpha}).")
    if n_bootstrap < 1:
        raise ValueError(f"n_bootstrap must be >= 1 (got {n_bootstrap}).")
    if float(np.std(arr, ddof=1)) == 0.0:
        raise ValueError("returns has zero variance; Sharpe is undefined.")

    if not isinstance(seed, int):
        raise TypeError(f"seed must be an int (got {type(seed).__name__}).")
    rng = np.random.default_rng(seed)
    n_blocks = int(np.ceil(T / block_size))
    n_starts = T - block_size + 1  # 有効な開始位置数

    bootstrap_sharpes: list[float] = []
    for _ in range(n_bootstrap):
        starts = rng.integers(0, n_starts, size=n_blocks)
        # block を結合して T に切り詰める
        # vectorized: 各開始位置から block_size 分取り出してスタック
        idx = starts[:, None] + np.arange(block_size)[None, :]
        resampled = arr[idx].ravel()[:T]
        mu = resampled.mean()
        sigma = resampled.std(ddof=1)
        if sigma == 0.0:
            continue  # 退化リサンプル（同一値だけ）はスキップ
        bootstrap_sharpes.append(mu / sigma)

    if not bootstrap_sharpes:
        raise ValueError("All bootstrap samples degenerated (std=0); cannot compute CI.")

    arr_sr = np.asarray(bootstrap_sharpes)
    lower = float(np.percentile(arr_sr, 100.0 * alpha / 2.0))
    upper = float(np.percentile(arr_sr, 100.0 * (1.0 - alpha / 2.0)))
    return (lower, upper)
```

### 3.6 `__all__`

```python
__all__ = [
    "deflated_sharpe_ratio",
    "fold_sign_ratio",
    "block_bootstrap_sharpe_ci",
]
```

## 4. `tests/alpha_factory/test_statistics.py`

### 4.1 フィクスチャ

- 通常用 seed: `42`

### 4.2 内部関数テスト（private だが公開 API の土台）

`from src.alpha_factory.statistics import _norm_cdf, _norm_ppf` をテスト側でのみ import。

| テスト | 入力 | 期待値 | tolerance |
|--------|------|--------|-----------|
| `test_norm_cdf_known_points` | 0.0 / 1.96 / -1.96 | 0.5 / ≈0.9750021 / ≈0.0249979 | 1e-6 |
| `test_norm_ppf_known_points` | 0.5 / 0.975 / 0.025 / 0.001 / 0.999 | 0 / 1.95996398... / -1.95996398... / -3.09023231... / 3.09023231... | 1e-6 |
| `test_norm_ppf_clip_bounds` | p=0, p=1 | ValueError | — |

### 4.3 `deflated_sharpe_ratio` テスト

| テスト | 内容 |
|--------|------|
| `test_dsr_monotonic_in_sharpe` | skew=0, kurt=3, mean_trials=0, std_trials=1, n_trials=10, T=1000 固定で SR=0.01 → 0.10 を増やすと DSR 単調増加 |
| `test_dsr_decreases_with_more_trials` | 同条件で n_trials=2 → 100 で DSR が下がる（より厳しい補正） |
| `test_dsr_pinned_value_normal_case` | skew=0, kurt=3, mean_trials=0, std_trials=1, n_trials=10, T=1000, SR=0.05 の DSR を実装で pin（再現性確認、将来回帰検知） |
| `test_dsr_matches_independent_calculation_n_trials_2` | 独立計算値との照合。skew=0, kurt=3, mean_trials=0, std_trials=1, n_trials=2, T=1000, SR=0.05 で、test 側で Eq.(7)/(9) を素朴に再展開（`_norm_ppf` / `math.erf` を直接呼んで組み立てる）し、`deflated_sharpe_ratio` 返り値と 1e-6 tolerance で比較 |
| `test_dsr_matches_independent_calculation_n_trials_10` | 同上を `n_trials=10` で実施。`q1 = Φ⁻¹(0.9)` と `q2 = Φ⁻¹(1 - 1/(10e))` の両方が効くケース（Round 2 reviewer 提案: n_trials=2 では q1=0 になるため両項が効く条件も検証） |
| `test_dsr_negative_skew_fat_tail_reduces_dsr` | skew=0, kurt=3 と skew=-1, kurt=9 で、後者のほうが DSR が低い（分母補正項が大） |
| `test_dsr_raises_on_n_trials_below_2` | n_trials=1 → ValueError |
| `test_dsr_raises_on_n_observations_below_2` | n_observations=1 → ValueError |
| `test_dsr_raises_on_non_positive_std_sr_trials` | std_sr_trials=0 / -1 → ValueError |

Notes:
- Bailey 論文 Table 1 の数値例は original paper の完全な Table を手元で再現できないため、本実装では「実装で pin した値」を回帰テスト用途で使う。DSR の正しさは monotonicity / 入力域ガードの組み合わせで保証する。

### 4.4 `fold_sign_ratio` テスト

| ケース | 入力 | 期待値 |
|--------|------|--------|
| 完全反転 | `[1.0, -1.0, 1.0, -1.0]` | 1.0 |
| 全同符号 | `[1.0, 1.0, 1.0]` | 0.0 |
| 空 | `[]` | 0.0 |
| 単一要素 | `[1.0]` | 0.0 |
| ゼロ挟みで反転 | `[1.0, 0.0, -1.0]` | 0.5 |
| ゼロ先頭 | `[0.0, 0.0, 1.0]` | 0.0 |
| ゼロ挟みで反転なし | `[-1.0, 0.0, 0.0, -1.0]` | 0.0 |
| 一部反転 | `[1.0, 1.0, -1.0]` | 0.5 |

### 4.5 `block_bootstrap_sharpe_ci` テスト

| テスト | 内容 |
|--------|------|
| `test_bootstrap_ci_covers_analytic_bar_sharpe` | `rng.normal(loc=0.0001, scale=0.01, size=10000)` で `block_size=20, n_bootstrap=1000, seed=42`。解析的 bar Sharpe ≈ μ/σ = 0.01 が (lower, upper) に含まれる |
| `test_bootstrap_ci_reproducible_with_seed` | 同じ `returns, seed` で 2 回呼ぶと同じ `(lower, upper)` |
| `test_bootstrap_ci_different_seeds_differ` | 異なる seed で `(lower, upper)` が変わる |
| `test_bootstrap_ci_block_size_variants` | block_size=5, 20, 50 で ValueError なし、lower < upper |
| `test_bootstrap_raises_on_short_returns` | len(returns)=1 → ValueError |
| `test_bootstrap_raises_on_block_size_gt_length` | len=10, block_size=20 → ValueError |
| `test_bootstrap_raises_on_zero_variance` | 全て同じ値の returns → ValueError |
| `test_bootstrap_raises_on_invalid_alpha` | alpha=0.0 / 1.0 / -0.1 / 1.5 → ValueError |

> 注: 「解析値が CI に含まれる」テストは確率的なので seed 固定必須。テストは決定論的に pass する（pre-seed で確認した pin 値を使う）。万一 flaky なら seed を変えるか、許容幅を明示。

### 4.6 テストファイル構造

```python
import math

import numpy as np
import pytest

from src.alpha_factory.statistics import (
    block_bootstrap_sharpe_ci,
    deflated_sharpe_ratio,
    fold_sign_ratio,
)
from src.alpha_factory.statistics import _norm_cdf, _norm_ppf  # noqa: PLC2701 internal

# ... テストクラスまたは関数を論理グループで分割
```

## 5. pyproject.toml 更新

```toml
[project]
...
dependencies = [
    "sqlalchemy>=2.0",
    "alembic",
    "psycopg[binary]>=3.1",
    "httpx",
    "tenacity",
    "diskcache",
    "pydantic>=2",
    "pydantic-settings",
    "structlog",
    "pyyaml>=6.0.3",
    "numpy>=1.26",
]
```

`uv sync` で lock 更新。

## 6. docs/alpha_factory/statistics.md 更新

既存ファイルに以下を追記:

### 6.1 `deflated_sharpe_ratio` セクション詳細化

signature / 引数説明 / 使用例（bar 単位 SR の計算方法含む）を記載。

### 6.2 `block_bootstrap_sharpe_ci` セクション詳細化

Kunsch (1989) 参照、signature、使用例を記載。

### 6.3 `fold_sign_ratio` セクション追加

carry-forward 方式の説明と例。

### 6.4 関連 TODO の更新

「未着手」を T006 完了済みへ（close 時）。

## 7. 動作確認コマンド

```bash
cd ./worktrees/todo-T006
uv run pytest tests/alpha_factory/test_statistics.py -v
uv run mypy src/alpha_factory/
uv run ruff check src/alpha_factory/ tests/alpha_factory/
```

## 8. 検証ポイント（Codex design-review 向け）

- [ ] DSR 式の転記（Eq.7 / Eq.9）が conceptual-design と一致
- [ ] Acklam 近似の有理関数係数が Acklam 1998 の原著値と一致
- [ ] block bootstrap の vectorized 実装が正しくブロックを結合している（`arr[idx].ravel()[:T]`）
- [ ] 全関数が純粋（副作用なし、グローバル状態なし、seed 経由のみ RNG）
- [ ] エッジケースが Raises セクションで docstring 化されている
- [ ] numpy 以外の外部依存がない（math モジュールと numpy のみ）

## 9. 実装順序

1. pyproject.toml に numpy 追加、`uv sync`
2. `src/alpha_factory/__init__.py` を作成
3. `src/alpha_factory/statistics.py` を実装
4. `tests/alpha_factory/__init__.py` を作成
5. `tests/alpha_factory/test_statistics.py` を実装
6. `uv run pytest` 緑、`uv run mypy`、`uv run ruff check` 緑
7. `docs/alpha_factory/statistics.md` 更新
8. Codex impl-review
9. コミット → TODO close → main マージ
