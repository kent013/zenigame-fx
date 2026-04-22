# Concept: statistics-dsr-bootstrap

## 目的

Stage Gate で使う統計検定の最小セットを `src/alpha_factory/statistics.py` に実装。

## 実装対象（Phase 2 最小セット）

### 1. DSR (Deflated Sharpe Ratio)

Bailey & López de Prado (2014) に基づく。

```python
def deflated_sharpe_ratio(
    sharpe_ratio: float,
    n_trials: int,
    n_observations: int,
    skew: float = 0.0,
    kurtosis: float = 3.0,
    mean_sr_trials: float = 0.0,
    std_sr_trials: float = 1.0,
) -> float:
    """DSR を返す（0 未満は non-significant）"""
```

### 2. Fold Sign Reversal Ratio

```python
def fold_sign_ratio(fold_sharpes: list[float]) -> float:
    """Walk-forward の fold 間で Sharpe の符号が反転した比率"""
```

### 3. Block Bootstrap Sharpe CI

```python
def block_bootstrap_sharpe_ci(
    returns: np.ndarray,
    block_size: int = 20,
    n_bootstrap: int = 1000,
    alpha: float = 0.05,
) -> tuple[float, float]:
    """Block bootstrap で Sharpe の (lower, upper) CI を返す"""
```

## テスト

- DSR: known input で論文の数値と一致（tolerance 0.01）
- fold_sign_ratio: [+, -, +, -] で 0.5
- block_bootstrap: 正規分布データで 95% CI が Sharpe の解析値を含む

## 後続（Phase 3+）

- PBO-lite（top-20 候補で CSCV S=6-8）— 別 TODO
- Reality Check / SPA — 別 TODO

## 優先度・モード

- Priority: Critical
- Mode: incremental
- テーマ: statistics
