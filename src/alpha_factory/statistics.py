"""Stage Gate 用の統計検定最小セット。

- :func:`deflated_sharpe_ratio`  — Bailey & Lopez de Prado (2014)
- :func:`fold_sign_ratio`        — Walk-Forward fold 間の Sharpe 符号一貫性
- :func:`block_bootstrap_sharpe_ci` — Kunsch (1989) moving block bootstrap による Sharpe CI

純関数・NumPy のみ依存。SciPy は使用しない（標準正規 CDF / inverse CDF は内部で
近似実装）。

参考文献:
    - Bailey, D. H. & Lopez de Prado, M. M. (2014). "The Deflated Sharpe Ratio:
      Correcting for Selection Bias, Backtest Overfitting, and Non-Normality."
      Journal of Portfolio Management, 40(5), 94-107.
    - Bailey, D. H. & Lopez de Prado, M. M. (2012). "The Sharpe Ratio Efficient
      Frontier." Journal of Risk, 15(2), 3-44. (PSR 参照)
    - Kunsch, H. R. (1989). "The Jackknife and the Bootstrap for General
      Stationary Observations." Annals of Statistics, 17(3), 1217-1241.
    - Politis, D. N. & Romano, J. P. (1994). "The Stationary Bootstrap."
      Journal of the American Statistical Association, 89(428), 1303-1313.
    - Acklam, P. J. (1998). "An algorithm for computing the inverse normal
      cumulative distribution function."
"""

from __future__ import annotations

import math

import numpy as np

__all__ = [
    "block_bootstrap_sharpe_ci",
    "deflated_sharpe_ratio",
    "fold_sign_ratio",
]


# ---------------------------------------------------------------------------
# 内部: 標準正規 CDF / inverse CDF（NumPy のみ依存、SciPy 不使用）
# ---------------------------------------------------------------------------

_ACKLAM_A: tuple[float, float, float, float, float, float] = (
    -3.969683028665376e01,
    2.209460984245205e02,
    -2.759285104469687e02,
    1.383577518672690e02,
    -3.066479806614716e01,
    2.506628277459239e00,
)
_ACKLAM_B: tuple[float, float, float, float, float] = (
    -5.447609879822406e01,
    1.615858368580409e02,
    -1.556989798598866e02,
    6.680131188771972e01,
    -1.328068155288572e01,
)
_ACKLAM_C: tuple[float, float, float, float, float, float] = (
    -7.784894002430293e-03,
    -3.223964580411365e-01,
    -2.400758277161838e00,
    -2.549732539343734e00,
    4.374664141464968e00,
    2.938163982698783e00,
)
_ACKLAM_D: tuple[float, float, float, float] = (
    7.784695709041462e-03,
    3.224671290700398e-01,
    2.445134137142996e00,
    3.754408661907416e00,
)
_ACKLAM_P_LOW = 0.02425
_ACKLAM_P_HIGH = 1.0 - 0.02425
_NORM_PPF_EPS = 1e-15

_EULER_GAMMA = 0.5772156649015329


def _norm_cdf(x: float) -> float:
    """標準正規分布 CDF Phi(x)。``math.erf`` ベース。"""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _norm_ppf(p: float) -> float:
    """標準正規分布の inverse CDF Phi^-1(p)。Acklam (1998) の有理関数近似。

    p=0 または p=1（および範囲外・NaN）は ``ValueError``。
    開区間 (0, 1) の内部点に対してのみ、数値安定のため
    ``[_NORM_PPF_EPS, 1 - _NORM_PPF_EPS]`` に clip してから計算する。
    誤差は倍精度で概ね 1.15e-9 級（Acklam 1998 の報告値）。
    """
    if not (isinstance(p, int | float) and math.isfinite(p) and 0.0 < p < 1.0):
        raise ValueError(f"p must be a finite number in open interval (0, 1); got {p}")
    p = min(max(p, _NORM_PPF_EPS), 1.0 - _NORM_PPF_EPS)
    if p < _ACKLAM_P_LOW:
        q = math.sqrt(-2.0 * math.log(p))
        num = (
            (
                (
                    (_ACKLAM_C[0] * q + _ACKLAM_C[1]) * q + _ACKLAM_C[2]
                ) * q + _ACKLAM_C[3]
            ) * q + _ACKLAM_C[4]
        ) * q + _ACKLAM_C[5]
        den = (
            (
                (_ACKLAM_D[0] * q + _ACKLAM_D[1]) * q + _ACKLAM_D[2]
            ) * q + _ACKLAM_D[3]
        ) * q + 1.0
        return num / den
    if p <= _ACKLAM_P_HIGH:
        q = p - 0.5
        r = q * q
        num = (
            (
                (
                    (_ACKLAM_A[0] * r + _ACKLAM_A[1]) * r + _ACKLAM_A[2]
                ) * r + _ACKLAM_A[3]
            ) * r + _ACKLAM_A[4]
        ) * r + _ACKLAM_A[5]
        den = (
            (
                (
                    (_ACKLAM_B[0] * r + _ACKLAM_B[1]) * r + _ACKLAM_B[2]
                ) * r + _ACKLAM_B[3]
            ) * r + _ACKLAM_B[4]
        ) * r + 1.0
        return q * num / den
    # upper tail
    q = math.sqrt(-2.0 * math.log(1.0 - p))
    num = (
        (
            (
                (_ACKLAM_C[0] * q + _ACKLAM_C[1]) * q + _ACKLAM_C[2]
            ) * q + _ACKLAM_C[3]
        ) * q + _ACKLAM_C[4]
    ) * q + _ACKLAM_C[5]
    den = (
        (
            (_ACKLAM_D[0] * q + _ACKLAM_D[1]) * q + _ACKLAM_D[2]
        ) * q + _ACKLAM_D[3]
    ) * q + 1.0
    return -num / den


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def deflated_sharpe_ratio(
    sharpe_ratio: float,
    n_trials: int,
    n_observations: int,
    skew: float,
    kurtosis: float,
    mean_sr_trials: float,
    std_sr_trials: float,
) -> float:
    """Bailey & Lopez de Prado (2014) の Deflated Sharpe Ratio。

    観測 Sharpe Ratio が、N 個の独立試行の最大値 (null hypothesis: 真の SR=0) を
    有意に上回る確率を返す。値域 [0, 1]。0.95 以上で 5% 水準で有意。

    NOTE (T-sharpe Phase 1A / T073 audit layer):
        Phase 1A: 本関数は v1 bar-level annualized Sharpe を入力前提、
        archive ``dsr`` field は v1 経路で計算済 (sharpe_calc_version v1)。
        Phase 1A で GA / Stage Gate / Alpha Sieve の Sharpe が
        ``trade_sharpe_raw`` (v2, annualize なし, trade-level) に切り替わったため、
        DSR の入力意味論が一致しなくなっており、 archive ``dsr`` 列は monitor only
        でゲート判定には使われていない.

        T073 audit layer (Phase 2 配線後): ``src/alpha_factory/audit.py`` の
        ``compute_audit_dsr_for_genome`` 経由で、 v2 SessionBlock pnl_net
        (= non-annualized) + ``AuditNullModel`` 駆動で本関数を呼出。 数式
        (Bailey & Lopez de Prado 2014 Eq.(7)/(9)) は不変、 入力尺度は
        ``AuditNullModel.sr_scale="session_block_non_annualized"`` SSOT で固定。

        archive ``dsr`` field の v1 → v2 切替は Phase 2 別 PR で
        sharpe_calc_version 同期 + ``dsr_v1`` rename + ``dsr_v2`` 追加
        (= 履歴比較互換) で行う。

    Args:
        sharpe_ratio: 観測 Sharpe Ratio ``SR_obs``。**bar 単位 (non-annualized)**。
            年率値を渡すと結果が歪む。呼び出し元で年率->bar 変換のこと。
        n_trials: 独立試行相当数 N (>= 2)。N=1 の場合は DSR ではなく
            PSR (Bailey & Lopez de Prado 2012) を使うこと。
        n_observations: 観測 bar 数 T (>= 2)。
        skew: リターン分布の歪度（3 次中心モーメント / sigma^3）。正規分布で 0。
        kurtosis: リターン分布の尖度（**non-excess**, 4 次中心モーメント / sigma^4）。
            正規分布で 3.0。excess kurtosis を渡さないこと。
        mean_sr_trials: 試行候補 SR 分布の平均。
        std_sr_trials: 試行候補 SR 分布の標準偏差 (> 0)。

    Returns:
        DSR ∈ [0, 1]。

    Raises:
        ValueError: ``n_trials < 2``, ``n_observations < 2``, ``std_sr_trials <= 0``,
            任意の float 引数が non-finite、または DSR 分母平方根の内側が非正。

    Notes:
        - 分母の SR 項には ``SR_obs`` を使う（Bailey & Lopez de Prado 2014 Eq.(9) 原著表記）。
        - Acklam (1998) の有理関数近似で inverse normal CDF を計算。

    Examples:
        >>> dsr = deflated_sharpe_ratio(
        ...     sharpe_ratio=0.05,
        ...     n_trials=10,
        ...     n_observations=1000,
        ...     skew=0.0,
        ...     kurtosis=3.0,
        ...     mean_sr_trials=0.0,
        ...     std_sr_trials=1.0,
        ... )
        >>> 0.0 <= dsr <= 1.0
        True
    """
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
        raise ValueError(
            f"n_trials must be >= 2 (got {n_trials}); use PSR for single trial."
        )
    if n_observations < 2:
        raise ValueError(f"n_observations must be >= 2 (got {n_observations}).")
    if std_sr_trials <= 0:
        raise ValueError(f"std_sr_trials must be > 0 (got {std_sr_trials}).")

    # Eq.(7): Expected Max SR
    q1 = _norm_ppf(1.0 - 1.0 / n_trials)
    q2 = _norm_ppf(1.0 - 1.0 / (n_trials * math.e))
    expected_max_sr = mean_sr_trials + std_sr_trials * (
        (1.0 - _EULER_GAMMA) * q1 + _EULER_GAMMA * q2
    )

    sr = float(sharpe_ratio)
    denom_sq = 1.0 - skew * sr + ((kurtosis - 1.0) / 4.0) * sr * sr
    if denom_sq <= 0.0:
        raise ValueError(
            f"DSR denominator radicand non-positive ({denom_sq}); "
            "check skew/kurtosis/SR inputs."
        )
    z = ((sr - expected_max_sr) * math.sqrt(n_observations - 1)) / math.sqrt(denom_sq)
    return _norm_cdf(z)


def fold_sign_ratio(fold_sharpes: list[float]) -> float:
    """Walk-forward fold 間の Sharpe 符号反転比率（0..1）。

    ゼロは符号なしとして扱い、直前の非ゼロ符号と比較する（carry-forward）。
    反転 = 直前 fold の非ゼロ符号と現 fold の非ゼロ符号が異なる。

    Examples:
        >>> fold_sign_ratio([1.0, -1.0, 1.0, -1.0])
        1.0
        >>> fold_sign_ratio([1.0, 1.0, 1.0])
        0.0
        >>> fold_sign_ratio([1.0, 0.0, -1.0])
        0.5
        >>> fold_sign_ratio([0.0, 0.0, 1.0])
        0.0
        >>> fold_sign_ratio([])
        0.0
        >>> fold_sign_ratio([1.0])
        0.0

    Args:
        fold_sharpes: fold ごとの Sharpe のリスト。

    Returns:
        符号反転比率 ∈ [0, 1]。``len(fold_sharpes) < 2`` のときは 0.0。
    """
    n = len(fold_sharpes)
    if n < 2:
        return 0.0
    prev_sign = 0  # 0 = 未確定（まだ非ゼロ符号が出ていない）
    sign_changes = 0
    for i, s in enumerate(fold_sharpes):
        if s > 0:
            curr = 1
        elif s < 0:
            curr = -1
        else:
            curr = 0
        if i > 0 and curr != 0 and prev_sign != 0 and curr != prev_sign:
            sign_changes += 1
        if curr != 0:
            prev_sign = curr
    return sign_changes / (n - 1)


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
    し、Sharpe の信頼区間を返す。**Phase 2 では monitor 用 CI**。Hard gate 化や
    block length 自動選択は後続 TODO（stationary bootstrap, Politis & White 2004）
    で扱う。

    Args:
        returns: 1 次元リターン系列（bar 単位、length T）。nan/inf を含まないこと。
        block_size: ブロック長（>= 1, <= T）。呼び出し元で時系列の自己相関減衰
            スケールに合わせて指定する（default なし、必須）。
        n_bootstrap: bootstrap 標本数。default 1000。
        alpha: 両側有意水準 (0, 1)。default 0.05 で 95% CI。
        seed: 乱数シード（必須）。決定論性を保証するため int を必ず渡す。
            ``None`` を許容しない（同一入力で出力が変わる non-pure 呼び出しを禁止）。

    Returns:
        ``(lower, upper)`` — bar 単位 Sharpe の ``(1 - alpha)`` 信頼区間の両端。
        呼び出し元で年率化（``* sqrt(periods_per_year)``）すること。

    Raises:
        ValueError: ``returns`` のサイズ・``block_size``・``alpha``・std が不正、
            ``returns`` に nan/inf が含まれる、または全 bootstrap 標本で std=0
            （退化）のとき。
        TypeError: ``seed`` が int でないとき。

    Notes on purity:
        ``seed`` が int のときに pure function として振る舞う（同一入力->同一出力）。
        OS エントロピー源には触れない。テスト・reproducibility のため seed は
        呼び出し側が明示的に管理する責任を持つ。

    Examples:
        >>> import numpy as np
        >>> rng = np.random.default_rng(0)
        >>> returns = rng.normal(0.0001, 0.01, size=10000)
        >>> lower, upper = block_bootstrap_sharpe_ci(
        ...     returns, block_size=20, n_bootstrap=500, alpha=0.05, seed=42
        ... )
        >>> lower < upper
        True
    """
    if not isinstance(seed, int) or isinstance(seed, bool):
        raise TypeError(f"seed must be an int (got {type(seed).__name__}).")

    arr = np.asarray(returns, dtype=np.float64).ravel()
    t_size = arr.size
    if t_size < 2:
        raise ValueError(f"returns must have length >= 2 (got {t_size}).")
    if not np.isfinite(arr).all():
        raise ValueError("returns contains non-finite values (nan/inf).")
    if block_size < 1:
        raise ValueError(f"block_size must be >= 1 (got {block_size}).")
    if block_size > t_size:
        raise ValueError(
            f"block_size ({block_size}) must be <= len(returns) ({t_size})."
        )
    if not (0.0 < alpha < 1.0):
        raise ValueError(f"alpha must be in (0, 1) (got {alpha}).")
    if n_bootstrap < 1:
        raise ValueError(f"n_bootstrap must be >= 1 (got {n_bootstrap}).")
    if float(np.std(arr, ddof=1)) == 0.0:
        raise ValueError("returns has zero variance; Sharpe is undefined.")

    rng = np.random.default_rng(seed)
    n_blocks = int(np.ceil(t_size / block_size))
    n_starts = t_size - block_size + 1  # 有効な開始位置数

    bootstrap_sharpes: list[float] = []
    offsets = np.arange(block_size)
    for _ in range(n_bootstrap):
        starts = rng.integers(0, n_starts, size=n_blocks)
        idx = starts[:, None] + offsets[None, :]
        resampled = arr[idx].ravel()[:t_size]
        mu = float(resampled.mean())
        sigma = float(resampled.std(ddof=1))
        if sigma == 0.0:
            continue  # 退化リサンプル（同一値のみ）はスキップ
        bootstrap_sharpes.append(mu / sigma)

    if not bootstrap_sharpes:
        raise ValueError(
            "All bootstrap samples degenerated (std=0); cannot compute CI."
        )

    arr_sr = np.asarray(bootstrap_sharpes)
    lower = float(np.percentile(arr_sr, 100.0 * alpha / 2.0))
    upper = float(np.percentile(arr_sr, 100.0 * (1.0 - alpha / 2.0)))
    return (lower, upper)
