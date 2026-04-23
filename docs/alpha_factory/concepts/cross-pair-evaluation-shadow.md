# Concept: cross-pair-evaluation-shadow

## 目的

(ii-lite) cross-pair 評価を shadow mode で実装。Phase 4 で hard gate 化。

## 設計

### アンカーペア定義

| target | アンカー 2 ペア |
|--------|----------------|
| EUR_JPY | {EUR_USD, USD_JPY} |
| USD_JPY | {USD_CAD, EUR_JPY} |
| EUR_USD | {EUR_JPY, USD_CAD} |
| AUD_JPY | {USD_JPY, EUR_USD} |
| USD_CAD | {USD_JPY, EUR_USD} |
| USD_ZAR | {USD_CAD, USD_JPY} |

### 評価関数

`src/alpha_factory/cross_pair.py`:

```python
def evaluate_cross_pair(
    genome: Genome,
    target: str,
    anchor_pairs: list[str],
    start: datetime,
    end: datetime,
    backtest_config: BacktestConfig,
) -> CrossPairResult:
    """target + アンカー2ペアで backtest、集約 fitness を返す"""

@dataclass
class CrossPairResult:
    sharpe_per_pair: dict[str, float]
    mean_sharpe: float
    std_sharpe: float
    min_sharpe: float
    aggregate_fitness: float  # mean - 0.5*std
    pass_criteria: dict  # 3 条件の pass/fail
```

### 通過基準（hard gate 用、shadow では記録のみ）

- Sharpe_target_cross ≥ 0.8 × Sharpe_target_single
- mean Sharpe_cross ≥ 0.15
- min Sharpe_cross ≥ -0.20

### Shadow モード動作

- **Phase 2 (T016 で実装済)**: Stage C **実行個体すべてを観測対象**として cross-pair 評価し、`ii_lite_pass` カラムに記録。Stage C 判定には影響しない (shadow only)。後段分析で `stage_c_pass=True` 個体のみに絞った分布集計が可能。
- **Phase 4 (別 TODO)**: `mode='hard'` で Stage C 通過判定の AND 合成として動作 (= 「Stage C 通過後に必ず通過判定として参照される」状態)。
- archive に shadow_pass_rate / 予測力（shadow 通過群の事後 OOS）を集計するのは集計スクリプト側で別途実装。

## 実装範囲

- cross_pair.py 新設 (T016 実装済)
- Stage C hook に例外隔離 + skipped 伝搬を追加 (T016 実装済)
- config `cross_pair:` セクション追加（`mode: shadow`、アンカー定義、通過基準）。命名は `cross_pair` で SSOT 統一 (旧名 `ii_lite` の archive カラム `ii_lite_pass` のみ既存互換のため維持)。

## テスト

- synthetic genome で 3 ペア評価 → 集約 fitness が数式通り
- pass_criteria の境界値
- Shadow モードで Stage C に影響しない

## 優先度・モード

- Priority: Critical
- Mode: standalone
- テーマ: cross-pair
