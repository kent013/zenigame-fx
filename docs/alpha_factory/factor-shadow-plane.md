# Factor Shadow Plane (FSP) — Single Instrument Diagnostic Layer

**TODO**: T036 (Phase 0 Critical / 概念設計 Round 6 APPROVED)
**実装**: [`src/alpha_factory/fsp_updater.py`](../../src/alpha_factory/fsp_updater.py)
**Config**: [`src/alpha_factory/config.py`](../../src/alpha_factory/config.py) `FspConfig`
**起点監査**: Run 7/8/9 すべての run_report に `cross_pair_runtime_mode: skipped_single_instrument` が記録されていた事実 (`ii_lite_pass: True=0, False=0, None=120`)。single instrument RUN では cross-pair 妥当性検証経路が完全に空転する問題への対応。

## 目的

single instrument RUN では cross-pair (T016) が無効化される (`skipped_single_instrument`) ため、「ペアを跨ぐ共通因子で動いているのか / そのペア固有の癖で動いているのか」を判別する経路が完全に欠落していた。FSP は **外生因子 (DXY 等) との相関で個体ごとの「共通因子帯への依存度」を測る observability layer** を提供する。

**重要**: Phase 1 は **diagnostic-only** (選抜介入なし)。GA fitness や `stage_*.passed` には一切影響しない。post-RUN で archive Parquet を in-place 更新するだけ。

## Dispatch Matrix

`fsp_runtime_mode` は以下 6 値のいずれかを取る:

| RUN 形態 | enabled | factor data | bars | mode |
|---------|---------|------------|------|------|
| multi-pair RUN | any | any | any | `skipped_multi_pair_run` (T016 と排他) |
| single instrument RUN | false | any | any | `skipped_disabled` |
| single instrument RUN | true | 不在 | any | `skipped_no_factor_data` |
| single instrument RUN | true | available | bars < window | `skipped_window_too_short` |
| single instrument RUN | true | available | bars >= window, キー不一致 | `skipped_conditioning_mismatch` |
| single instrument RUN | true | available | bars >= window, キー一致 | **`active`** |

dispatch 順序は SSOT として [`_decide_runtime_mode`](../../src/alpha_factory/fsp_updater.py) に記述。

## 計測内容（Phase 1）

| Archive 列 | 型 | 説明 |
|-----------|---|------|
| `fsp_runtime_mode` | string | dispatch 結果（6 値 enum） |
| `fsp_sampling_mode` | string | `"daily"` 固定 (Phase 1) |
| `fsp_factor_set` | list[string] | `["DXY"]` (Phase 1 は 1 因子のみ) |
| `fsp_rolling_corr_60d` | list[float64] | rolling 60d Spearman (窓内 rank-Pearson 近似) |
| `fsp_explained_variance` | float64 | 全期間 OLS R² (unclipped、R²<0 も記録) |
| `fsp_idio_ratio` | float64 | `1 - R²` (unclipped) |

## 換算式 / 前提

### Sampling
- **daily**: PnL は UTC 日次境界で集計、因子も日次そのまま (FRED の DXY/VIX は日足密度のため intraday 補間しない)
- `factor_asof_lag=1`: 当日 t に対する factor return は前日の pct_change (look-ahead bias 回避)

### Conditioning Set
- 戦略リターン: archive に書き込まれた個体すべて (Stage A 通過のみ等のフィルタ禁止)
- Bar grid: 全 bar 上で評価 (ポジション保有日のみではない、survivor 限定ではない)

### Statistics
- rolling Spearman: 各窓内で `rank()` を取り Pearson 相関 (Phase 1 近似、`pandas.Rolling.corr` に Spearman メソッドが無いため)
- OLS R²: numpy `lstsq` で β を解いて `1 - SSres/SStot`、unclipped (R² < 0 も記録)
- `fsp_idio_ratio = 1 - R²` (R²<0 では 1 を超える可能性あり、Phase 1 はそのまま記録)

学術引用:
- Fama, E. F., & French, K. R. (1993). Common risk factors in the returns on stocks and bonds. _Journal of Financial Economics_, 33(1), 3-56. (factor model 文脈の出発点)

## 北極星制約・禁止事項チェック

| 禁止事項 | 該当性 |
|---------|------|
| 1. 評価期間延長 | 該当なし (post-RUN observability) |
| 2. 見た目の数値改善 | 該当なし (archive 観測のみ追加) |
| 3. GA hack | 該当なし (fitness / selection に影響無) |
| 4. live_criteria 緩和 | 該当なし |
| 5. 過剰な複雑化 | Phase 1 は 1 因子・diagnostic only に限定 |
| 6. 取引回数削減 | 該当なし |
| 7. オーバーナイト前提 | 該当なし |
| 8. archive スキーマ伝搬漏れ | 6 列を `GENOMES_SCHEMA` / `_create_row_template` の 4 段で完備 |

## H1 評価クエリ

dispatch 健全性と整合性失敗を分離して観測:

- `evaluate_h1(rows)`: eligible (`active` + `skipped_conditioning_mismatch`) のうち `active` 比率
- `evaluate_key_integrity_failure_rate(rows)`: eligible のうち `skipped_conditioning_mismatch` 比率

`H1_NON_ELIGIBLE_MODES = {skipped_multi_pair_run, skipped_disabled, skipped_no_factor_data, skipped_window_too_short}` は eligible から除外。

## 冪等性

- `fsp_runtime_mode` が null の行のみ再計算 (`force_recalculate=False` 既定)
- POSIX atomic write (tmp → fsync → rename → fsync(parent dir)) でクラッシュ耐性
- 全行既処理時は `active` を return (`rows_processed=0` を log で no-op として識別可能)

## Phase 1 制限事項

- **trade ledger 統合は別 TODO で実施**: 現時点では PnL 系列の取得経路が未整備のため、`active` dispatch でも `fsp_results` が空 dict となり下流で `skipped_conditioning_mismatch` を返す (詳細設計 §11 注記参照)
- データ準備: `data/raw/fred/DXY.csv` (close 列必須) を別途整備すること (`scripts/fetch_fred.py` を参照)
- 多因子 (VIX / 金利差) は Phase 2 で導入
- `fsp_partial_corr` は Phase 1 不要

## 変更履歴

- 2026-04-26: T036 Phase 1 初期実装。yaml + FspConfig + GENOMES_SCHEMA 6 列 + fsp_updater モジュール + dispatch matrix + atomic write + 単体/統合テスト 36 件。trade ledger 統合は次フェーズへ申し送り。
