# 概念設計: statistics-dsr-bootstrap

## 1. 目的

zenigame-fx Alpha Factory の Stage Gate で必須となる統計検定の最小セットを `src/alpha_factory/statistics.py` に実装する。後続の `stage-gate-implementation` で利用される。

実装対象は次の 3 関数（NumPy のみ依存、純粋関数）:

1. `deflated_sharpe_ratio` — Bailey & López de Prado (2014) の DSR
2. `fold_sign_ratio` — Walk-Forward fold 間の Sharpe 符号反転比率
3. `block_bootstrap_sharpe_ci` — 時系列依存を考慮した Sharpe 信頼区間

## 2. 背景・先行研究

### 2.1 Deflated Sharpe Ratio (DSR)

- **出典**: Bailey, D. H. & López de Prado, M. M. (2014). "The Deflated Sharpe Ratio: Correcting for Selection Bias, Backtest Overfitting, and Non-Normality." *The Journal of Portfolio Management*, 40(5), 94–107.
- **狙い**: 多数の戦略候補から最良の Sharpe を選んだ場合に発生する選択バイアス（multiple testing inflation）と、リターン分布の歪度・尖度（skew / excess kurtosis）の影響を補正したうえで、観測 Sharpe が「null hypothesis（真の Sharpe = 0）」を有意に上回る確率を計算する。
- **役割（zenigame-fx 内）**: Stage B / C の通過条件の 1 つ。Phase 2 では monitor、Phase 3 以降で hard gate。

### 2.2 Block Bootstrap

- **出典**:
  - Künsch, H. R. (1989). "The Jackknife and the Bootstrap for General Stationary Observations." *Annals of Statistics*, 17(3), 1217–1241. — moving block bootstrap
  - Politis, D. N. & Romano, J. P. (1994). "The Stationary Bootstrap." *Journal of the American Statistical Association*, 89(428), 1303–1313. — stationary bootstrap
- **狙い**: 時系列の系列相関を保ったままリサンプリングする。i.i.d. ブートストラップは時系列依存を破壊するので Sharpe の標準誤差を過小評価する。
- **本実装での選択**: 移動ブロックブートストラップ（fixed block size）で十分。Politis-Romano の stationary 化（geometric block length）は Phase 後半で必要に応じ拡張。

### 2.3 Fold Sign Ratio

- 学術的命名は無いが、Walk-Forward 検証で fold 間の OOS Sharpe 符号一貫性を測る簡易指標。
- 隣接 fold で符号が反転する比率を返す。値が高いほど不安定 / 過学習疑い。

## 3. 公式仕様

### 3.1 DSR (Bailey & López de Prado 2014)

#### 3.1.1 Expected Maximum Sharpe (式 7)

`N` 個の独立試行から得られた Sharpe の最大値の期待値:

```
E[max SR_N] ≈ E_trials[SR] + std_trials[SR] * ((1 - γ) * Z⁻¹(1 - 1/N) + γ * Z⁻¹(1 - 1/(N*e)))
```

ここで:
- `γ ≈ 0.5772156649` (Euler-Mascheroni 定数)
- `e ≈ 2.71828182846`
- `Z⁻¹(p)` は標準正規分布の inverse CDF（quantile function）
- `E_trials[SR]`, `std_trials[SR]` は試行候補の Sharpe 分布の平均と標準偏差

> 実装メモ: scipy を使わずに `Z⁻¹` を計算するため Beasley-Springer-Moro / Acklam approximation のいずれかを採用。Acklam（1998）は double precision で誤差 1.15e-9 と高精度。本実装ではこちらを採用。

#### 3.1.2 DSR (式 9)

観測 Sharpe `SR_obs` に対する DSR:

```
DSR = Φ( ((SR_obs - E[max SR_N]) * sqrt(T - 1)) / sqrt(1 - skew * SR_obs + ((kurt - 1)/4) * SR_obs²) )
```

ここで:
- `Φ(z)` は標準正規 CDF
- `T` は観測 bar 数 (`n_observations`)
- `skew` はリターン分布の歪度（3 次中心モーメント / σ³）
- `kurt` は **excess kurtosis** ではなく "kurtosis"（4 次中心モーメント / σ⁴）。正規分布で 3.0。
  - 注: 論文の式は `kurt` を non-excess としている。実装でも非超過尖度を受け取り、正規分布デフォルト 3.0 とする。
- `SR_obs` は観測 Sharpe（**bar 単位**, non-annualized）。年率値が入力される場合は `n_periods_per_year` で除して bar 単位に変換する必要がある。

> **分母の SR 表記ゆれに関する固定方針**: 論文/解説で DSR 分母の `SR` に `SR_obs` を使う読みと `SR_0 (= E[max SR_N])` を使う読みの 2 通りがある。本実装は **`SR_obs` を使う**仕様に固定（Bailey & López de Prado (2014) Eq.(9) の原著表記に従う）。将来の実装者が誤って置換しないよう docstring と conceptual-design に明記する。

> **実装メモ**: signature は「年率 SR を受け取り、内部で bar 単位に変換する」と「bar 単位 SR を受け取る」の 2 通りある。本実装は **bar 単位 SR を受け取る**仕様にする（呼び出し元で年率→bar 変換）。これは Bailey の式が bar 単位を前提としているため、誤りを避けやすい。docstring に明示。

> **入力域ガード**:
> - `n_trials >= 2` を必須（`n_trials = 1` では `Φ⁻¹(1 - 1/N) = Φ⁻¹(0) = -∞` となり式が破綻）。`n_trials = 1` 相当の検定は DSR ではなく PSR (Bailey & López de Prado 2012) を使う。
> - `n_observations >= 2` を必須。
> - `std_sr_trials > 0` を必須（DEFAULT 値を持たせず、呼び出し元で必ず指定）。
> - Acklam の inverse CDF は `p ∈ (ε, 1-ε)` に clip してから呼ぶ。`ε = 1e-15`。
> - 分母 `1 - skew*SR_obs + ((kurt-1)/4)*SR_obs²` が非正になったら `ValueError`（通常の分布では発生しないが防御）。

#### 3.1.3 解釈

- DSR ≥ 0.95 → null hypothesis を 95% 有意で棄却可（観測 SR は max under null よりも有意に大きい）
- DSR < 0.5 → 観測 SR は max under null と同等または下回る → 有意性なし

### 3.2 Fold Sign Ratio

#### 3.2.1 仕様（ゼロ符号の carry-forward）

ゼロは「符号変化なし」として扱い、**直前の非ゼロ符号を保持（carry-forward）して比較する**。これにより「[+ , 0 , -]」は 1 回反転（`+` と `-` の比較）、「[0 , 0 , +]」は 0 回反転として扱える。

```
denom = n - 1  （n < 2 は 0.0 を返す）
prev_sign = 0
sign_changes = 0
for i in range(n):
    curr = sign(fold_sharpes[i])     # +1 / 0 / -1
    if i > 0 and curr != 0 and prev_sign != 0 and curr != prev_sign:
        sign_changes += 1
    if curr != 0:
        prev_sign = curr
return sign_changes / denom
```

#### 3.2.2 期待挙動

| 入力 | sign_changes | denom | 出力 |
|------|-------------|-------|------|
| `[+1, -1, +1, -1]` | 3 | 3 | 1.0 |
| `[+1, +1, +1]` | 0 | 2 | 0.0 |
| `[+1, 0, -1]` | 1 | 2 | 0.5 |
| `[0, 0, +1]` | 0 | 2 | 0.0 |
| `[-1, 0, 0, -1]` | 0 | 3 | 0.0 |
| `[]` | - | - | 0.0（エッジケース） |
| `[1.0]` | - | - | 0.0（エッジケース） |

> 注: carry-forward 方式を明示採用。「signs[i] * signs[i-1] < 0」方式は [+,0,-] を 0 回と数えるため採用しない。

### 3.3 Block Bootstrap Sharpe CI

#### 3.3.1 アルゴリズム（moving block bootstrap）

入力: `returns: np.ndarray` (1D, length T), `block_size: int`（必須、default なし）, `n_bootstrap: int = 1000`, `alpha: float = 0.05`, `seed: int | None = None`

```
1. RNG = np.random.default_rng(seed)
2. n_blocks = ceil(T / block_size)
3. for b in range(n_bootstrap):
     # block の開始位置を [0, T - block_size] からランダムに n_blocks 個サンプル
     starts = RNG.integers(0, T - block_size + 1, size=n_blocks)
     # block を結合して T に切り詰める
     resampled = concatenate([returns[s:s+block_size] for s in starts])[:T]
     sr_b = mean(resampled) / std(resampled, ddof=1)  # bar 単位 Sharpe
     bootstrap_sharpes.append(sr_b)
4. lower = percentile(bootstrap_sharpes, alpha/2 * 100)
5. upper = percentile(bootstrap_sharpes, (1 - alpha/2) * 100)
6. return (lower, upper)
```

#### 3.3.2 設計判断

- **bar 単位 Sharpe を返す**（年率化は呼び出し元）。理由は DSR と同じ（誤りを避けやすい）。
- **stationary bootstrap (Politis-Romano 1994) は採用しない**。Phase 2 は **monitor 用 CI** の位置付けで moving block bootstrap で十分。Hard gate 化や block length の自動選択（Politis & White 2004）は後続 TODO で扱う。
- **block_size は必須引数**（default なし）。呼び出し元で時系列の自己相関減衰スケールに合わせて指定する。1 分足 FX リターンで 20 bar 程度は暫定的な目安だが、frequency / 通貨ペア / セッションで適正値は変わるため、関数側で default を決め打ちしない。
- **n_bootstrap = 1000** は default。CI の安定性とコストのトレードオフ。
- **エッジケース**:
  - `len(returns) < 2` → ValueError（Sharpe 計算不能）
  - `block_size < 1` → ValueError
  - `len(returns) < block_size` → ValueError
  - `std(returns, ddof=1) == 0` → ValueError（Sharpe 未定義）
  - `alpha <= 0` または `alpha >= 1` → ValueError
  - bootstrap 標本で `std == 0` となった場合（退化リサンプル）はその試行のみスキップし、全試行スキップ時は ValueError。
- **再現性**: `seed: int | None` を受け取り `np.random.default_rng(seed)` で固定。

## 4. 関数 signature（最終版）

```python
import numpy as np

def deflated_sharpe_ratio(
    sharpe_ratio: float,           # 観測 SR_obs（bar 単位、non-annualized）
    n_trials: int,                 # 独立試行相当数 N (effective trials, >=2)
    n_observations: int,           # 観測 bar 数 T (>=2)
    skew: float,                   # リターン分布の歪度（必須）
    kurtosis: float,               # リターン分布の尖度（non-excess、正規=3.0、必須）
    mean_sr_trials: float,         # 試行候補 SR 分布の平均（必須）
    std_sr_trials: float,          # 試行候補 SR 分布の標準偏差 > 0（必須、default なし）
) -> float:
    """Bailey & López de Prado (2014) の Deflated Sharpe Ratio。

    観測 Sharpe SR_obs が「多数試行の最良値 max under null」を上回る確率 Φ(DSR_z) を返す。
    0..1 の範囲。0.95 以上で 5% 有意。

    Raises:
        ValueError: n_trials < 2, n_observations < 2, std_sr_trials <= 0,
            または分母平方根の内側が負になる場合。

    Notes:
        - 分母補正項は SR_obs を使う（Bailey & López de Prado 2014 Eq.(9) 表記）。
          SR_0 や (SR_obs - SR_0) ではない点に注意。
        - n_trials=1 の場合は DSR ではなく PSR (Probabilistic Sharpe Ratio) を使うこと。
    """

def fold_sign_ratio(fold_sharpes: list[float]) -> float:
    """Walk-forward fold 間の Sharpe 符号反転比率（0..1）。

    ゼロは符号なしとして扱い、直前の非ゼロ符号と比較する（carry-forward）。
    len(fold_sharpes) < 2 は 0.0。
    """

def block_bootstrap_sharpe_ci(
    returns: np.ndarray,
    block_size: int,                # 必須（auto 選択は Phase 後半で別途）
    n_bootstrap: int = 1000,
    alpha: float = 0.05,
    *,
    seed: int,                      # 必須 (int)。pure function 契約を明示するため None は許容しない
) -> tuple[float, float]:
    """Moving block bootstrap で bar 単位 Sharpe の (lower, upper) CI を返す (Phase 2 monitor 用)。

    Kunsch (1989) の moving block bootstrap。block_size は呼び出し元で時系列の
    自己相関減衰スケールに合わせて指定すること（1 分足で 20 bar は暫定値の一例）。
    Hard gate 用途は stationary bootstrap (Politis-Romano 1994) 拡張を別 TODO で検討。

    Raises:
        ValueError: len(returns) < 2, len(returns) < block_size, block_size < 1,
            std(returns) == 0, alpha が (0, 1) 外。
    """
```

## 5. 依存関係

- NumPy のみ（scipy は使わない）
- 標準正規 inverse CDF / CDF は本モジュール内に純 NumPy 実装（Acklam 1998 / `math.erf` 経由）

## 6. テスト戦略（概略）

詳細設計で具体化するが、概念設計時点での骨子:

1. **Acklam inverse CDF（内部関数）**:
   - 既知点 `p ∈ {0.001, 0.025, 0.5, 0.975, 0.999}` に対する値を `scipy.stats.norm.ppf` 不要で検証（ハードコードされた期待値: `p=0.5 → 0`, `p=0.975 → 1.959963984540054`, `p=0.025 → -1.959963984540054`, `p=0.001 → -3.090232306167813`, `p=0.999 → 3.090232306167813`）
   - tolerance 1e-6
2. **標準正規 CDF（内部関数）**:
   - `Φ(0) = 0.5`, `Φ(1.96) ≈ 0.975`, `Φ(-1.96) ≈ 0.025` を tolerance 1e-6 で検証
3. **DSR**:
   - 既知入力で単調性確認: SR を 0.01→0.10 に増やすと DSR が単調増加
   - n_trials 増加で DSR 低下（2→100 で DSR が下がる）
   - skew=0, kurt=3, mean_sr_trials=0 条件で固定した既知値（数値を実装で pin）
   - `n_trials=1` で `ValueError`
   - `n_observations=1` で `ValueError`
   - `std_sr_trials<=0` で `ValueError`
   - skew=0, kurt=3 と skew<0, kurt>3（fat-tail left-skew）で DSR が下がる方向性確認
4. **fold_sign_ratio**:
   - `[+1,-1,+1,-1]` → 1.0
   - `[+1,+1,+1]` → 0.0
   - `[]` → 0.0
   - `[+1]` → 0.0
   - `[+1, 0, -1]` → 0.5 (carry-forward で 1 反転 / denom=2)
   - `[0, 0, +1]` → 0.0 (carry-forward で 0 反転)
   - `[-1, 0, 0, -1]` → 0.0
5. **block_bootstrap_sharpe_ci**:
   - 独立正規分布 returns（μ=0.0001, σ=0.01, n=10000, seed 固定）で解析的 bar Sharpe（μ/σ ≈ 0.01）が CI に含まれる
   - seed 固定で再現性（同じ seed → 同じ `(lower, upper)`）
   - block_size 異なる値で ValueError なく動作、CI の点推定が適切に動く
   - `len(returns) < block_size` で ValueError
   - `std(returns) == 0` で ValueError
   - `alpha=0.0` / `alpha=1.0` で ValueError

## 7. 後続 TODO

- PBO-lite（CSCV、top-M に限定） — 別 TODO
- Reality Check (White 2000) / SPA (Hansen 2005) — 別 TODO
- Stationary block bootstrap (Politis-Romano) 拡張 — 必要になれば

## 8. リスク・要確認事項

- **R1**: numpy が現状の pyproject.toml に未追加。本 TODO で `numpy>=1.26` を `[project.dependencies]` に追加する必要あり（実装着手時に対応）。
- **R2**: Bailey 論文の DSR 公式は **bar 単位 SR** 前提。年率 SR を渡すと結果が歪む。docstring と関数名で明示し、呼び出し元での誤用を防ぐ。
- **R3**: skew / kurtosis の母集団推定値は不偏推定量を使う前提（Fisher G1 歪度・G2 尖度など）。サンプル数が小さいと推定分散が大きく DSR precision を悪化させる。呼び出し元で適切な推定量を選び、Phase 2 では DSR は monitor 指標として扱う。本関数は受け取った skew / kurtosis をそのまま使うので、推定量の選択責任は呼び出し元にある（docstring で明記）。
