# 概念設計: factor-shadow-plane (FSP) — single instrument 専用 diagnostic layer (Round 6 / APPROVED)

## 背景・課題 (観察事実)

- Run 7/8/9 すべての run_report に `cross_pair_runtime_mode: skipped_single_instrument` が記録されている (Fact)
- Stage A pass 数の variance はあるが (48/0/66 個体)、`ii_lite_pass: True=0, False=0, None=120` が常に観測 (Fact)
- `cross_pair_config.mode = shadow`, `aggregator_lambda = 0.5` だが、実行は skipped (Fact)
- T016 で実装された (ii-lite) cross-pair shadow は **複数通貨ペア同時実行時のみ有効**
- 結果: single instrument RUN では cross-pair 妥当性検証経路が **常に空転** (Interpretation)

**問題**: regime-awareness 観点で「ペアを跨ぐ共通因子で動いているのか / そのペア固有の癖で動いているのか」を判別する経路が、single instrument RUN 時には完全に欠落している。

## 改善アイデア — Phase 1: diagnostic-only exogenous shadow layer (single instrument fallback)

**注**: Phase 1 の実態は「plane」よりも「diagnostic layer」に近い。Phase 1 では選抜介入を一切行わず、計測のみを提供する。

### Dispatch matrix (Fact: 排他的に切り替える)

| RUN 形態 | `factor_shadow.enabled` | factor data | window 長 | `fsp_runtime_mode` 結果 |
|---------|-------------------------|-------------|-----------|--------------------------|
| multi-pair RUN | any | any | any | `skipped_multi_pair_run` |
| single instrument RUN | false | any | any | `skipped_disabled` |
| single instrument RUN | true | 欠損/取得不可 | any | `skipped_no_factor_data` |
| single instrument RUN | true | available | bars < window | `skipped_window_too_short` |
| single instrument RUN | true | available | bars >= window, 件数不一致 | `skipped_conditioning_mismatch` |
| single instrument RUN | true | available | bars >= window, 件数一致 | **`active`** |

注: `skipped_disabled`/`skipped_window_too_short` は Round 2 [Warning] 対応で追加。`skipped_conditioning_mismatch` は Round 3 [Warning] 対応で追加。FSP は single instrument 専用 fallback。multi-pair RUN では走らせない (T016 と排他)。

### Sampling granularity 修正 (Round 1 [Critical] 対応)

FRED の DXY/VIX は **日足密度**。これを M1 に補間しても当日中はほぼ定数となり、rolling Spearman は「日付ブロック」「営業日境界」を拾うだけになる。

修正: Phase 1 は **daily shadow plane** とする。
- 個体の戦略 PnL を日次集計 (UTC 0:00-24:00 単位)
- 因子も日次そのまま (補間なし、`factor_asof_lag=1` で前日終値を当日 base として使用 → 因果性確保)
- `fsp_sampling_mode = "daily"` を archive に明記
- intraday の高密度因子が必要になった場合は別 TODO で intraday proxy (例: 主要先物の M5 集約) を導入する

### Conditioning set 固定 (Round 1 [Critical] 対応)

`R²` の collider bias を回避するため:
- **被説明変数**: `daily_strategy_return = sum(pnl over UTC day)` (全日固定の bar grid 上で評価、ポジション保有日のみではない、survivor のみではない)
- **説明変数**: `daily_factor_return_{t} = (DXY_t - DXY_{t-1}) / DXY_{t-1}` (差分系列、stationary)
  - **時点整合 (Round 2 [Warning] 対応)**: `factor_asof_lag=1` により `DXY_t` は日付 t の前日終値 = `DXY_{t-1_close}` を指す。したがって被説明変数 `strategy_return_t` (UTC day t の PnL) と突合する因子は `factor_return_{t} = (DXY_{t-1_close} - DXY_{t-2_close}) / DXY_{t-2_close}`、すなわち "前日の DXY 変化率"。look-ahead bias なし。
- **conditioning set**: 戦略返り値は archive に書き込まれた個体すべてが対象 (Stage A 通過個体のみ等のフィルタは禁止)
- **禁止項目**:
  - 「ポジション保有中バーのみ」の R² 計測
  - 「survivor (Stage A 通過後) のみ」の R² 計測
  - archive 後段だけの集計
- 列名: `fsp_explained_variance` (R² より limited な解釈)。`fsp_partial_corr` は Phase 1 スコープ外とし、schema には含めない (Round 5 [Warning] 対応: 未採用指標を設計から削除して転記漏れ防止)

### 計測内容

- 各個体について daily PnL 系列と DXY daily return の **rolling 60 日 Spearman correlation** (`fsp_rolling_corr_60d`)
- `fsp_explained_variance` = OLS R² (daily 系列、全 bar grid)
- `fsp_idio_ratio` = `1 - fsp_explained_variance`
- `fsp_factor_set` = ["DXY"] (Phase 1 は 1 因子のみ、原因分離のため)
- `fsp_runtime_mode` の許容値 (合計 6 値、以下がすべての valid enum):
  - `active`
  - `skipped_no_factor_data` (因子データ欠損)
  - `skipped_disabled` (config で無効化)
  - `skipped_multi_pair_run` (multi-pair RUN)
  - `skipped_window_too_short` (bars < window_days)
  - `skipped_conditioning_mismatch` (archive row 数 != FSP 対象個体数、Round 3 [Warning] 対応)
- この一覧が D6 (ログ出力) と D7 (テスト分岐) の参照先となる (Round 4 [Warning] 対応: enum 数不整合を防ぐ単一定義)

## 期待効果 (反証可能仮説、success/kill criteria 含む)

### Falsifiable success criteria (Phase 1 で検証する)

- **H1 (基盤)**: Run 10 の archive で `fsp_runtime_mode="active"` の row 比率 > 90%
  - 分母定義: `eligible_rows = [rows where single_instrument=True AND factor_shadow.enabled=True AND bars >= window_days AND factor_data_available]` (Round 3/4 [Warning] 対応: データ長不足・RUN 種別・enabled 設定が設計良否判定に混入しないよう分母を明示固定)
  - 単純 RUN 全体比率での測定は不可 (`skipped_*` 行が H1 を偽化しうるため)
- **H2 (識別性)**: factor-heavy ベースライン (DXY と完全相関する人工系列の個体) を test fixture として埋め込み、`fsp_idio_ratio < 0.2` と判定できること (識別性の単体検証)
- **H3 (run 間再現性)**: 同一 genome hash を持つ個体が 3 RUN 全てに出現する場合、その `fsp_idio_ratio` の標準偏差 < 0.1 (window=60 日の安定性)
  - **同一個体の識別キー**: `genome_hash` (遺伝子配列ハッシュ) を使用。同点の場合は `genome_hash` の辞書順最小を使用
  - **3 RUN 全てに出現しない場合**: INCONCLUSIVE とし FAIL とは区別する (H3 の検証は次の RUN セットへ持ち越し)
  - **長期 INCONCLUSIVE ルール (Round 3 [Warning] 対応)**: 5 RUN セット連続で INCONCLUSIVE が続いた場合、"genome_hash が3 RUN 全てに出現" という前提そのものを再検討し、識別戦略を再定義する
  - **best の定義**: Stage A fitness 最高個体 (`stage_a_fitness` 最大値、同点時は `genome_hash` 辞書順最小)

### Falsifiable kill criteria (Phase 1 で false なら方針見直し)

- **K1**: `fsp_runtime_mode="active"` 比率 < 50% (FSP が機能しない、設計欠陥)
- **K2**: H2 の factor-heavy ベースラインを `fsp_idio_ratio > 0.5` と誤判定する場合 (識別性ない)
- **K3**: 計測が GA RUN 全体時間を 2 倍以上に延ばす (運用上 unacceptable)

trade_count 影響予測: **不変** (条件付き — 下記 5 つの条件を満たす場合)

### trade_count 不変の必須条件 (Round 1 [Warning] 対応)
1. archive を immutable に確定後、別 task で FSP を計算
2. GA worker 内では FSP 計算を行わない
3. FSP 失敗時は `runtime_mode="skipped_*"` に倒し、archive 主データには影響させない
4. メモリ圧迫を起こさないよう因子系列は run ごとに 1 回だけ構築
5. 個体ごとの統計は streaming / vectorized に寄せる

## 実装方針 (概要)

1. **外生因子 loader**:
   - 既存 FRED data (T004 で実装、`data/raw/fred/`) から DXY (Phase 1 では DXY のみ) を読み込む
   - daily 系列のまま使用 (M1 補間なし、Round 1 [Critical] 対応)
   - `factor_asof_lag=1` で前日終値を当日 base に (因果性厳守)

2. **daily PnL 集計**:
   - 既存 backtest result (trades) から UTC daily 単位で集計
   - 全 bar grid (ポジション無しの日も含む) で再構築

3. **rolling correlation + R² 計算**:
   - daily 系列に対して rolling 60 日 Spearman correlation
   - 全期間 OLS で `R²` (= explained_variance), `1 - R²` (= idio_ratio)
   - **conditioning set は固定、ポジション保有日フィルタや survivor フィルタは禁止**

4. **archive schema 拡張**:
   - 新規列 (すべて nullable):
     - `fsp_runtime_mode: string` (enum 文字列集合は config で固定)
     - `fsp_sampling_mode: string` ("daily")
     - `fsp_factor_set: list[string]` (Phase 1 は ["DXY"])
     - `fsp_rolling_corr_60d: list[float]` (時系列、archive 列 1 つに array で格納)
     - `fsp_explained_variance: float`
     - `fsp_idio_ratio: float`

5. **schema 互換テスト** (Round 1 [Warning] 対応):
   - `old archive only` (新列なし)、`new archive only`、`old+new mixed read` の 3 ケース
   - 既存 reader (`src/alpha_factory/archive.py`) で新列追加が破綻しないことを確認

5b. **conditioning set 件数整合チェックとキー結合** (Round 2/5 [Warning/Critical] 対応):
   - post-RUN FSP updater は `genome_hash` でキー結合して archive 行と FSP 計算値を突合する (件数一致のみでは順序ずれによる誤マッピングが発生しうるため)
   - `missing / duplicate / unmatched` が検出された場合は `runtime_mode="skipped_conditioning_mismatch"` に設定して警告ログを出力後、Parquet に書き戻して終了 (後段への影響なし)
   - **注意**: `assert` 文は使用しない。`assert` はフォールバック前に停止し graceful degradation と矛盾するため (Round 4 [Critical] 対応)
   - `skipped_conditioning_mismatch` はデータ欠損系の `skipped_no_factor_data` とは区別する (Round 3 [Warning] 対応: 原因追跡の明確化)

6. **config 追加**:
   - `config/alpha_factory/default.yaml` に以下を追加:
     - `factor_shadow.enabled: false` (default 安全)
     - `factor_shadow.factors: ["DXY"]`
     - `factor_shadow.sampling_mode: "daily"`
     - `factor_shadow.window_days: 60`
     - `factor_shadow.factor_asof_lag: 1`
     - `factor_shadow.conditioning_set: "all_bars_all_individuals"` (collider bias 再発防止のため config レベルで固定、Round 5 [Warning] 対応)
   - 詳細は詳細設計時に loader 実装 (`src/alpha_factory/config.py`) と整合

7. **post-RUN 一括計算と Parquet 書き戻し**:
   - GA RUN 完了後、archive Parquet 確定後の独立 task として実行
   - Parquet 書き戻し方針 (Round 5 [Critical] 対応): `tmp ファイル書き出し → fsync → atomic rename` で原子的置換。部分書き込み failure 時は tmp を削除して終了（元 Parquet は汚染しない）
   - 再実行時の冪等性: `fsp_runtime_mode` 列が既に `active` の行は再計算対象外（または上書き可、詳細設計で確定）
   - 失敗時は graceful degradation (`runtime_mode="skipped_*"`) で main RUN に影響なし

## 制約・前提

### Fact
- T004 (FRED ingest) で DXY/VIX/金利日足が `data/raw/fred/` に存在
- T016 で (ii-lite) cross-pair shadow が実装済、`cross_pair_runtime_mode` 列が archive に存在
- archive は Parquet schema、既存読み込みは `src/alpha_factory/archive.py`

### Interpretation
- daily 解像度なら計算量は許容範囲 (DXY 60 日 × 個体数 × O(1) OLS)
- factor 1 本で始めれば原因分離可能

### 前提制約 (Verified / Assumed / Out-of-scope)
- メモリ (Verified): daily 集計で 1 instrument あたり **60 日** (= rolling window) × 120 個体 × 2 列 = 14,400 cells ≈ 115KB / RUN。以前の見積もり (30日×120個体=60KB) は rolling window 長と不整合だったため修正 (Round 2 [Warning] 対応)
- 並列性 (Assumed): post-RUN 独立 task で run RUN プロセスとは分離
- 後方互換 (Verified 必須): 3 ケース schema 互換テストを実装
- 因果性 (Verified): `factor_asof_lag=1` で前日終値、daily 集計は UTC 確定境界後
- collider bias (Verified): 全 bar grid + 全個体 + 固定 conditioning set

## スコープ外 (Phase 1)

- 選抜介入 (factor-adjusted fitness, factor 寄与に応じた penalty) → Phase 2 別 TODO
- intraday 高頻度因子 (5 分足以下) → Phase 2 別 TODO (intraday proxy 設計時)
- 多因子 (VIX, 金利差) → Phase 2 別 TODO (Phase 1 は DXY 単独)
- 因子の動的選択 (PCA / Factor Discovery) → Phase 2 別 TODO
- T025 (alpha-sieve OOS) との連携 → 別 TODO
- 既存 ii-lite shadow との統合評価 (multi-pair RUN で両方走らせる構成) → Phase 2 別 TODO
- M1 への因子補間 (= Round 1 [Critical] で却下されたため Phase 1 ではやらない)

## 実装 DoD チェックリスト (Round 2 [Warning] 対応: 4段接続漏れ防止)

実装完了条件として以下をすべて確認する:

| # | チェック項目 | 確認方法 |
|---|------------|---------|
| D1 | `config/alpha_factory/default.yaml` に `factor_shadow.*` 定義 | grep |
| D2 | `src/alpha_factory/config.py` の `FspConfig` クラスに全パラメータ読み込み | grep |
| D3 | `genome.meta` に `fsp_runtime_mode` 等の FSP 列が注入される経路 | grep / unit test |
| D4a | `GENOMES_SCHEMA` に FSP 新規列 (fsp_runtime_mode 等 6 列) が定義されている | grep |
| D4b | `_create_row_template` で FSP 新規列の初期値が `null/None` で設定されている (GA worker 内では初期化のみ) | grep / unit test |
| D4c | post-RUN FSP updater が archive Parquet を読み込み FSP 計算値で上書き書き戻ししている (`collect_stage_*` は null 初期化のみで値埋め不要) | unit test |
| D4d | `flush`/書き戻し後の Parquet に FSP 列が含まれる | unit test |
| D5 | FSP updater 起動前に `genome_hash` キー結合チェック（missing/duplicate/unmatched は `skipped_conditioning_mismatch` に倒す、`assert` 不使用） | unit test |
| D5b | `factor_shadow.conditioning_set` config キーが `FspConfig` に読み込まれ、updater が参照している | grep / unit test |
| D6 | `fsp_runtime_mode` の全 enum 値 (active + skipped_* 5種 = 計 6 値) にログ出力がある | grep |
| D7 | dispatch matrix の全分岐 (`active`/`skipped_*` 5種 = 計 6 パス) が unit test で網羅されている | pytest coverage |

注: D4a〜D4d は転記漏れが繰り返し発生した「4点セット」に対応 (Round 3 [Critical] 対応)。
**FSP ライフサイクル明確化 (Round 4 [Critical] 対応)**: `collect_stage_*` (GA worker 内) は FSP 列を `null` 初期化するのみ。値埋めは post-RUN FSP updater のみが行う。これにより GA worker 外原則と D4c が整合する。

## リスクと対策

- **R1**: 外生因子データ欠損時 → `factor_shadow.enabled=false` 既定 + `runtime_mode="skipped_no_factor_data"` で graceful degradation
- **R2**: factor / idio 分解が過適合 → window=60 日を最低条件、bars < window では `runtime_mode="skipped_window_too_short"`
- **R3**: archive Parquet schema 互換性 → 3 ケース互換テスト必須
- **R4**: 計算量増で RUN 時間が長期化 → post-RUN 独立 task、GA worker 内では一切動かない
- **R5**: collider bias 再発 → conditioning set を config レベルでも固定 (`factor_shadow.conditioning_set="all_bars_all_individuals"` 等) し、変更には設計レビュー必須化
- **R6**: T016 (ii-lite) との dispatch 重複 → dispatch matrix を運用ドキュメント化、`runtime_mode` で互いの非起動を明示
