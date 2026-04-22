# Statistics

## 目的

DSR / PBO / Reality Check / SPA 等の統計検定の構造と、Phase 別実装スケジュールを一箇所に集約する。各関数 signature は別 TODO（`concepts/statistics-dsr-bootstrap.md`）で扱う。

## スコープ

- 各統計指標の定義（出典付き）
- block bootstrap CI の役割
- Phase 別の実装段階（必須 / 段階実装 / 後回し可）

実装関数 signature・パラメータ既定値は別 TODO に委ねる。

## 用語リンク

本ドキュメントで使用する用語: [DSR](terminology.md#dsr), [PBO](terminology.md#pbo), [Reality Check](terminology.md#reality-check), [SPA](terminology.md#spa), [CRN](terminology.md#crn), [Walk-Forward](terminology.md#walk-forward), [IS / OOS](terminology.md#is-oos)

## 主要定義

### Deflated Sharpe Ratio (DSR)

- 出典: Bailey & López de Prado (2014) "The Deflated Sharpe Ratio: Correcting for Selection Bias, Backtest Overfitting, and Non-Normality." *Journal of Portfolio Management*, 40(5), 94–107.
- 役割: 多数試行・skew/kurt 補正後の Sharpe 有意性
- Stage B の通過条件の一つ（Phase 2 monitor、Phase 3+ hard）

**実装**: `src/alpha_factory/statistics.py::deflated_sharpe_ratio`

```python
def deflated_sharpe_ratio(
    sharpe_ratio: float,
    n_trials: int,
    n_observations: int,
    skew: float,
    kurtosis: float,
    mean_sr_trials: float,
    std_sr_trials: float,
) -> float: ...
```

- `sharpe_ratio`: 観測 SR **bar 単位 (non-annualized)**
- `n_trials >= 2` 必須（N=1 は PSR を使う）
- `kurtosis` は **non-excess**（正規分布で 3.0）
- `std_sr_trials > 0` 必須（default なし）
- 返り値は `[0, 1]` の確率。0.95 以上で 5% 水準有意

使用例:

```python
from src.alpha_factory.statistics import deflated_sharpe_ratio

dsr = deflated_sharpe_ratio(
    sharpe_ratio=0.05,       # bar 単位 Sharpe
    n_trials=50,             # GA で評価した候補数
    n_observations=1000,     # 観測 bar 数
    skew=-0.3,
    kurtosis=4.5,
    mean_sr_trials=0.02,     # 候補 SR 分布の平均
    std_sr_trials=0.04,      # 候補 SR 分布の標準偏差
)
if dsr >= 0.95:
    # 有意
    ...
```

### Probability of Backtest Overfitting (PBO)

- 出典: Bailey, Borwein, López de Prado, Zhu (2014) "The Probability of Backtest Overfitting"
- 手法: Combinatorially Symmetric Cross-Validation (CSCV)
- 本プロジェクトでは **PBO-lite** を採用（top-M 候補に限定して S 分割）
- 移行トリガー判定の主要シグナル

### Block Bootstrap Sharpe CI

- 出典:
  - Künsch, H. R. (1989). "The Jackknife and the Bootstrap for General Stationary Observations." *Annals of Statistics*, 17(3), 1217–1241. — moving block bootstrap
  - Politis, D. N. & Romano, J. P. (1994). "The Stationary Bootstrap." *Journal of the American Statistical Association*, 89(428), 1303–1313. — stationary bootstrap（Phase 2 では不使用）
- 役割: 時系列依存を考慮した Sharpe の信頼区間
- block_size と n_bootstrap を持つ
- Phase 2 必須（archive に CI lower / upper を記録）、monitor 用途。Hard gate 化は後続 TODO

**実装**: `src/alpha_factory/statistics.py::block_bootstrap_sharpe_ci`

```python
def block_bootstrap_sharpe_ci(
    returns: np.ndarray,
    block_size: int,
    n_bootstrap: int = 1000,
    alpha: float = 0.05,
    *,
    seed: int,
) -> tuple[float, float]: ...
```

- `returns`: 1D リターン系列（bar 単位、nan/inf 不可）
- `block_size`: ブロック長（default なし）。呼び出し元で自己相関減衰スケールに合わせて設定
- `seed`: **keyword-only int 必須**（再現性を強制）
- 返り値は `(lower, upper)` bar 単位 Sharpe の CI（年率化は呼び出し元で `* sqrt(periods_per_year)`）

使用例:

```python
import numpy as np
from src.alpha_factory.statistics import block_bootstrap_sharpe_ci

rng = np.random.default_rng(0)
returns = rng.normal(0.0001, 0.01, size=10000)

lower, upper = block_bootstrap_sharpe_ci(
    returns,
    block_size=20,          # 1 分足 FX で 20 分スケール、要 domain tuning
    n_bootstrap=1000,
    alpha=0.05,
    seed=42,
)
# lower, upper は bar 単位。年率化する場合は * sqrt(252*24*60 or 適切な periods_per_year)
```

### Fold Sign Ratio

- 役割: Walk-Forward の隣接 fold 間で OOS Sharpe の符号が反転した比率
- Stage B の複合通過条件の一つ
- Phase 2 必須

**実装**: `src/alpha_factory/statistics.py::fold_sign_ratio`

```python
def fold_sign_ratio(fold_sharpes: list[float]) -> float: ...
```

- ゼロは符号なしとして扱い、直前の非ゼロ符号と比較する（carry-forward）
- 例:
  - `[+1, -1, +1, -1]` → 1.0（完全反転）
  - `[+1, +1, +1]` → 0.0
  - `[+1, 0, -1]` → 0.5（ゼロ挟みで 1 反転）
  - `[0, 0, +1]` → 0.0
  - `[]`, `[x]` → 0.0（エッジケース）
- 値が高いほど fold 間 Sharpe 符号が不安定 → 過学習疑い

### Reality Check / SPA

- 出典: White (2000) "A Reality Check for Data Snooping" / Hansen (2005) "A Test for Superior Predictive Ability"
- 候補圧縮後（top-M）に実行
- Phase 4 で実装、Phase 6 で hard gate 化

### Common Random Numbers (CRN)

- 役割: 複数戦略を同じ乱数系列で比較してノイズ相殺
- 分散削減手法、ベンチマーク比較で利用

### Phase 別実装スケジュール

| Phase | 必須 | 段階実装 | 後回し可 |
|-------|------|---------|---------|
| 2 | DSR / fold sign ratio / block bootstrap CI | — | — |
| 3 | — | PBO-lite | — |
| 4 | — | — | RC / SPA |
| 6 | — | RC / SPA hard gate 化 | — |

## SSOT 参照

| 項目 | 参照キーパス（config/alpha_factory/default.yaml） |
|------|--------------------------------------------------|
| block bootstrap block_size | Phase 2I で `statistics.bootstrap.block_size` 追加予定（未定義） |
| block bootstrap n_bootstrap | Phase 2I で `statistics.bootstrap.n_bootstrap` 追加予定（未定義） |
| DSR n_trials の取得元 | Phase 2I で `statistics.dsr.n_trials_source` 追加予定（未定義） |
| PBO-lite top_M | Phase 3I で `statistics.pbo.top_m` 追加予定（未定義） |
| PBO-lite S 分割 | Phase 3I で `statistics.pbo.s_splits` 追加予定（未定義） |
| RC ブートストラップ B | Phase 4I で `statistics.reality_check.b` 追加予定（未定義） |

## 関連ドキュメント

- [stage-gates.md](stage-gates.md) — Stage B / C での利用
- [migration-triggers.md](migration-triggers.md) — DSR / PBO / RC の複合判定
- [concepts/statistics-dsr-bootstrap.md](concepts/statistics-dsr-bootstrap.md)

## 関連 TODO

- **T006 (Closed)**: Phase 2F 統計検定最小セット実装。`src/alpha_factory/statistics.py` に `deflated_sharpe_ratio` / `fold_sign_ratio` / `block_bootstrap_sharpe_ci` を実装。設計: [`devnotes/20260422-1314-statistics-dsr-bootstrap/`](../../devnotes/20260422-1314-statistics-dsr-bootstrap/)
- Phase 3+: PBO-lite（CSCV top-M）— 別 TODO
- Phase 4+: Reality Check (White 2000) / SPA (Hansen 2005) — 別 TODO
- 拡張: stationary block bootstrap (Politis-Romano 1994) — 必要に応じて別 TODO
