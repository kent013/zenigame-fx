# Conceptual Design: Stage A/B/C Gate 実装 (T014)

## 1. 目的

Alpha Factory の評価パイプラインの中核となる Stage A / B / C ゲートを
`src/alpha_factory/stage_gate.py` に実装する。Genome の生存判定の唯一の
正規ルートを置き、後続の swim-lane / archive / run-ga 統合の土台を作る。

仕様根拠:
- `docs/alpha_factory/stage-gates.md`
- `docs/alpha_factory/concepts/stage-gate-implementation.md`
- `devnotes/20260421-1850-fx-skill-port/debate-synthesis.md` §B/E

## 2. スコープ / 非スコープ

### スコープ
- 3 つのステージ評価関数 `evaluate_stage_a/b/c` の実装
- Walk-Forward fold 分割関数 `make_wf_folds` の実装
- Stage 設定 `StageGateConfig` / 評価結果 `StageResult` dataclass の定義
- `config/alpha_factory/default.yaml` に `stage_gate.*` セクション追加
- `tests/alpha_factory/test_stage_gate.py` 新規（境界値・WF 分割・metric）
- `docs/alpha_factory/stage-gates.md` / `terminology.md` への追記

### 非スコープ
- (ii-lite) cross-pair の **実評価** ロジック
  （本 TODO では `evaluate_stage_c` 内に呼び出し interface だけ確保。
   実装は別 TODO `cross-pair-evaluation-shadow`）
- swim-lane manager / GA runner からの呼び出し統合
  （本 TODO は pure function を提供するのみ。配線は別 TODO）
- archive 書き込み
- DSR の `n_trials` の registry-aware 推定
  （本 TODO では `n_trials = 1`、すなわち DSR は計算しない or 0 monitor 値で扱う。
   詳細は §6.3）
- Stage A の `α_A` の `n_eff` 連動キャリブレーション
  （本 TODO では `α_A = 0.03` 固定）
- ペナルティ後 fitness の archive 配列伝搬

## 3. 設計方針

### 3.1 Pure function + dataclass

各 Stage は **入力 (Genome, bars, meta, backtest_config, primitive_evaluator,
stage_config) のみに依存する pure function** とする。乱数を使うのは Stage B
内の DSR / bootstrap CI 計算（呼び出し元から `seed` を明示注入）。

副作用なし、I/O なし、ロギング以外の状態変化なし。これにより:
- swim-lane / archive / GA runner からの組み合わせが容易
- 並列化可能（GIL 解放を後続 TODO で目指す）
- テスト容易

### 3.2 `StageResult` 単一返却型

各 Stage 関数は `StageResult` を返す（unified return）。
- `stage`: "A" / "B" / "C"
- `passed`: bool
- `metrics`: dict（stage-specific payload。詳細設計でスキーマを確定）
- `reason_codes`: tuple[str, ...]（**list-based reason codes**、空タプル = 通過）
- `reason_if_failed`: str（property: `";".join(reason_codes)`、後方互換 / display 用）

**reason のリスト化 (CONCEPT-FIXED)**:
consumer 側 (archive / swim-lane) が文字列パースする悪手を避けるため、
reason は最初から `tuple[str, ...]` の **canonical reason code 列**として返す。
`reason_if_failed` は表示・log 用に `";".join(reason_codes)` で算出する property。

reason code の語彙 (Stage 横断 canonical):
- A: "system_failure", "metric_unavailable", "no_trades", "below_threshold"
- B: "no_folds", "insufficient_folds", "median_oos_sharpe<min",
     "positive_fold_ratio<min", "all_folds_unavailable"
- C: "live_criteria.sharpe<min", "live_criteria.total_pnl<min",
     "live_criteria.max_drawdown>max", "live_criteria.trade_count<min",
     "live_criteria.trade_count>max",
     "intraday_constraint_violation", "spread_stress_skipped",
     "spread_stress.trade_count<min", "spread_stress.total_pnl<min",
     "spread_stress.sharpe<min", "system_failure"

**metrics の最小契約 (CONCEPT-FIXED)**:
schema drift を避けるため、Stage 横断で以下の共通 envelope key を必須とする:
- `stage`: "A" | "B" | "C"
- `genome_name`: str (Genome.name の写し)
- `n_bars`: int (評価 bar 数)
- `wall_time_seconds`: float (評価所要時間、profile 用)

その内側に `payload`: dict として stage-specific metrics を入れる。
詳細設計で payload スキーマを stage 別に table 化して固定する。

### 3.3 Stage A — Fast Screen

**入力期間**: 直近 60 営業日 = 60 × 1440 bars (M1 前提)

**評価フロー**:
1. `evaluate_genome(genome, bars_60d, meta, backtest_config, evaluator,
   metric="sharpe")` を呼ぶ
2. fitness_raw = sharpe（年率、`-1e12` で system_failure / metric_unavailable）
3. complexity penalty を控除: `fitness_pen = fitness_raw - α_A × size_norm(genome)`
4. `passed = fitness_pen > stage_a_threshold`
   - **threshold は本 TODO では「0.0」固定**。`calibrate-gate` が観測通過率
     から閾値を後で動的調整する責務を持つ（別 TODO）。pure function 視点では
     `stage_config.stage_a_threshold` を引数に取り、デフォルト 0.0
5. metrics: `{ "fitness_raw": float, "size_norm": float, "fitness_pen": float,
   "alpha_a": float, "trade_count": int, "sharpe_raw": float|None }`

**`_FAILURE_FITNESS` の場合の reason 分岐 (canonical, fix-aligned)**:
`evaluate_genome` は `_FAILURE_FITNESS` を「system_failure」と「metric_unavailable」
の両方で返す。Stage A は呼び出し前後の状態から両者を分離する。
- system_failure: try/except で例外を捉えるため `evaluate_genome` 単独では分離
  不可能。本 TODO では Stage A 関数内で **再度 try/except を被せ**、例外は
  `reason_codes=("system_failure",)` で返す。
- evaluate_genome が `_FAILURE_FITNESS` を返したが例外が捕捉されなかった
  場合は `reason_codes=("metric_unavailable",)`。
- trade_count < 1 のときは `reason_codes=("no_trades",)`（fitness が
  -1e12 でなくても trade_count を別途確認）。
- 上記いずれでもなく `fitness_pen <= stage_a_threshold` なら
  `reason_codes=("below_threshold",)`。
- 通過時は `reason_codes=()`。

### 3.4 Stage B — WF-OOS Gate (+ IS monitor)

**責務名の修正 (CONCEPT-FIXED)**: debate-synthesis の "Full IS + WF-OOS" は
**Stage B が WF-OOS の hard gate** で、**18 ヶ月全体の IS metrics は monitor**
として並走する、という意味に固定する。本 TODO で実装する hard gate は
WF-OOS (3 通過基準) のみ。「IS フィット」は GA 側の責務（GA が遺伝的探索で
パラメータを fit、Stage B はその固定 Genome を WF-OOS で検定）。

**入力期間**: 過去 18 ヶ月（呼び出し側が窓を切って渡す）

**WF パラメータ**: train 120d / test 20d / step 20d / embargo 1d
（観測日インデックス基準、§3.6 参照）

**評価フロー**:
1. `make_wf_folds(bars_18m, train_days, test_days, step_days, embargo_days)`
   で fold 列 `[(train_bars_i, test_bars_i)]` を生成
2. 各 fold の **test 区間** で `evaluate_genome(metric="sharpe")` を実行し
   `oos_sharpe_i` を収集
3. **18 ヶ月全体 IS monitor (CONCEPT-FIXED)**:
   - 別途 `evaluate_genome(metric="sharpe")` を 18 ヶ月全体 bars で 1 回実行し、
     `is_full_sharpe`, `is_full_total_pnl`, `is_full_trade_count` を metrics に記録
     （hard gate には使わない。archive で IS-OOS 乖離を可視化するため）
4. **fold metric_unavailable policy (CONCEPT-FIXED, fail-closed)**:
   - `oos_sharpe_i is None` (no-trade / zero-vol) なる fold は **0 とみなす**
     （除外しない、negative-equivalent 扱い）
   - 理由: 「除外」運用は no-trade 個体を見かけ上 pass させてしまう。
     no-trade fold は「OOS でアルファを生まなかった fold」として
     positive 不成立側に入れる方が North Star と整合
   - `n_fold_unavailable` は monitor 用に metrics に記録
5. metrics 集計:
   - `n_fold` = 生成された fold 総数（0 を含む全 fold）
   - `n_fold_unavailable` = `oos_sharpe_i is None` だった fold 数
   - `oos_sharpes_imputed` = None を 0.0 で埋めた fold sharpe 列
   - `median_oos_sharpe = median(oos_sharpes_imputed)`
     （n_fold == 0 時は計算せず None）
   - `positive_fold_ratio = (# fold s.t. oos_sharpes_imputed[i] > 0) / n_fold`
     （**分母は全 fold (n_fold)**、unavailable も母数に含める。
       no-trade を hide させない設計）
   - `dsr = None` (monitor、Phase 4 で hard 化、本 TODO 非対応理由は §6.3)
6. **fold ゼロ件 / 1 件の扱い**:
   - `n_fold == 0`: `passed=False`, `reason="no_folds"`
   - `n_fold == 1`: `passed=False`, `reason="insufficient_folds"`
     （n_fold >= 2 を WF-OOS の最小要件、Stage A→B 通過後の最低検定本数とする）
7. 通過判定（複合 AND, n_fold >= 2 のとき）:
   - `median_oos_sharpe >= median_oos_sharpe_min` (default 0.20)
   - `positive_fold_ratio >= positive_fold_min` (default 0.60)
   - `dsr` は monitor のため判定に含めない（Phase 2 monitor）

**reason_if_failed** は失敗条件を `;` 連結:
`"no_folds" | "insufficient_folds" | "median_oos_sharpe<min" |
"positive_fold_ratio<min"` （複数同時失敗時 `;` 連結）

### 3.5 Stage C — Live Criteria + Stress

**入力期間**: holdout 期間（呼び出し側が用意。debate-synthesis では明示日数なし、
本 TODO では `stage_c_holdout_days = 60` を default、呼び出し側が窓を切る）

**Drawdown unit canonicalization (CONCEPT-FIXED)**:
本 TODO 内では gate 比較を **fraction (0-1)** に統一する。
`BacktestMetrics.max_drawdown_pct` は percent (0-100) のため、Stage C 内で
`max_drawdown_frac = float(metrics.max_drawdown_pct) / 100` に正規化してから
config の `live_criteria.max_drawdown_max` (fraction) と比較する。
`metrics["max_drawdown_frac"]` を unified unit として metrics に格納する
（後段 archive / swim-lane も fraction で統一）。

**評価フロー**:
1. **base evaluation**: `run_backtest` を回し `compute_metrics` を取得
2. **live_criteria 判定**（AND）:
   - `sharpe >= sharpe_min` (config: 1.0)
   - `total_pnl >= total_pnl_min` (config: 50000)
   - `max_drawdown_frac <= max_drawdown_max` (config: 0.20)
   - `trade_count_min <= trade_count <= trade_count_max` (50 / 5000)
3. **イントラデイ遵守 (CONCEPT-FIXED, fail-closed)**:
   North Star のイントラデイ絶対制約を Stage C 出力レベルで証跡化する。
   - チェック方法: backtest 結果の `Trade.entry_time.date() ==
     Trade.exit_time.date()` を全 Trade で確認。
     違反 trade 数 = `overnight_violations`
   - `overnight_violations > 0` ならば `passed=False`,
     `reason="intraday_constraint_violation"`
   - metrics に `overnight_violations: int`, `intraday_compliant: bool` を必ず記録
   - 上記は engine 側の不変条件をさらに output 層で再確認する double-check 構造
4. **spread × 1.5 stress test (CONCEPT-FIXED, fail-closed)**:
   - 元の `BacktestConfig.max_spread_bps` を 1.5 倍した stress config で再 backtest
   - **hard gate (AND)** — 失敗時は **canonical reason code を個別に追加**
    （閾値は `stage_config.spread_stress_min_*` から取り、初期値は 0.0 だが
    一般化のため code は `<min` 形式で統一）:
     - `stress.trade_count >= trade_count_min` 違反 →
       `"spread_stress.trade_count<min"`
     - `stress.total_pnl >= spread_stress_min_total_pnl` 違反 →
       `"spread_stress.total_pnl<min"`
     - `stress.sharpe is not None and stress.sharpe >= spread_stress_min_sharpe`
       違反 → `"spread_stress.sharpe<min"`（None も violation 扱い）
   - `max_spread_bps=None` の取り扱い (CONCEPT-FIXED, fail-closed):
     - stress 評価不能のため `passed=False`,
       `reason_codes=("spread_stress_skipped",)` を追加して fail-closed
     - metrics に `stress.skipped=True`
     - Phase 2 では fail-closed を採用（運用上 max_spread_bps を設定する規律を強制）
   - degradation 幅は monitor 用に metrics に常時記録
     （`stress.sharpe_degradation = base.sharpe - stress.sharpe` 等）
5. **(ii-lite) shadow hook (CONCEPT-FIXED, hard-gate-ready interface)**:
   - 本 TODO では呼び出し interface のみ用意し、shadow 評価としてのみ実行
   - `CrossPairEvaluator` Protocol の戻り値は **`CrossPairResult` dataclass**
     (passed: bool / metrics: dict / reason_if_failed: str / target_pair: str /
     anchor_pairs: tuple[str, ...] / aggregator_name: str / window: tuple[datetime, datetime])
     で StageResult と整合する（将来 hard gate 化時に評価値を passed に折り込み可能）
   - 入力は `pair_bars_map: Mapping[str, list[PriceBar]]` + `target_pair: str` +
     `meta_map: Mapping[str, InstrumentMeta]` + `backtest_config: BacktestConfig`
     を取る形にして、anchor 群・bars 窓・meta を明示
   - Phase 2 (本 TODO 含む) では `cross_pair_evaluator=None` 許容かつ
     **shadow only** (`passed_hard` には影響させない)
   - metrics に `cross_pair: {"skipped": bool, "result": CrossPairResult|None}` を記録

**metrics**:
```
{
  "sharpe": float|None, "total_pnl": float, "max_drawdown_frac": float,
  "trade_count": int,
  "live_criteria_pass": dict[str, bool],  # sharpe / total_pnl / max_drawdown / trade_count_range
  "intraday_compliant": bool,
  "overnight_violations": int,
  "stress": {
    "skipped": bool,
    "sharpe": float|None, "total_pnl": float, "max_drawdown_frac": float,
    "trade_count": int,
    "sharpe_degradation": float|None,  # base.sharpe - stress.sharpe
    "pnl_degradation": float,
  },
  "cross_pair": {"skipped": bool, "result": CrossPairResult|None}
}
```

### 3.6 Walk-Forward 分割 (CONCEPT-FIXED, observed-day index ONLY)

`make_wf_folds(bars, train_days, test_days, step_days, embargo_days)` を新設。

**配置**: `src/alpha_factory/walk_forward.py` 新規モジュール。
（`src/backtest/walk_forward.py` は既存実装があるため別ファイル化。
詳細設計で既存実装との関係を確認し、共通化可能か検討）

**時間軸の定義**: 全パラメータは **観測日 (observed UTC date) インデックス
の本数** として解釈する。「暦日加算」は使わない（カレンダー gap / 祝日 / 週末
に対し robust にする唯一の方法）。

**算法 (observed-day index ベース)**:
1. 入力 `bars` を `bar_time` 昇順前提（呼び出し側が保証、関数内で assert）
2. `sorted_dates` = ソート済み `bar.bar_time.date()` のユニーク列
   （bar_time は UTC、24/5 FX 環境で「観測日」として扱う）
3. `n_days = len(sorted_dates)`
4. **必要最小 fold 長**: `train_days + embargo_days + test_days <= n_days`
   なら少なくとも 1 fold 生成可能、未満なら空 list を返す
5. fold k (k = 0, 1, ...):
   - `train_start_idx = step_days * k`
   - `train_end_idx_exclusive = train_start_idx + train_days`
     （train 区間 = `sorted_dates[train_start_idx : train_end_idx_exclusive]`、
       長さ `train_days` 日）
   - `embargo_end_idx_exclusive = train_end_idx_exclusive + embargo_days`
   - `test_start_idx = embargo_end_idx_exclusive`
   - `test_end_idx_exclusive = test_start_idx + test_days`
   - `test_end_idx_exclusive > n_days` なら fold 生成停止
6. 各 fold の date set に bar.date が含まれる bars を train_bars / test_bars
   に分配して `(train_bars, test_bars)` を append
7. embargo 区間の bars はどちらにも含めない（leak 防止）

**「観測日」の保証**:
入力 bars の bar_time の UTC date 列をそのまま観測日列として使う。週末・
祝日で bar が無い日は `sorted_dates` に出現しない。よって train/test/embargo
は常に「実際に観測された営業日 N 本分」になる。「暦日 N 日後」とは異なる。

**embargo の意味**:
train と test の間に `embargo_days` 観測日分の bars を **どちらにも含めない**
gap を入れる。lookahead leak / autocorrelation contamination の緩和
（López de Prado 2018, Advances in Financial ML, Ch.7）。

**前提仕様の例**:
- 18 ヶ月 ≈ FX 24/5 で 約 18 × 22 ≈ 396 観測日 (週末除く、祝日でさらに減)
  - **CONCEPT NOTE**: 概念設計 §9 の "540 営業日" は誤り。FX 24/5 で
    実観測日は 22 日/月オーダー。詳細設計で正規化する。
- train 120 / embargo 1 / test 20 / step 20 → fold 数
  ≈ floor((396 - 120 - 1 - 20) / 20) + 1 ≈ 13-14 fold

### 3.7 設定統合

`config/alpha_factory/default.yaml` に追加:
```yaml
stage_gate:
  stage_a:
    window_days: 60
    target_pass_rate: 0.15      # monitor_only (calibrate-gate が使う将来予約)
    alpha: 0.03
    threshold: 0.0              # 暫定固定 (calibrate-gate TODO で動的化)
  stage_b:
    window_months: 18
    wf_train_days: 120
    wf_test_days: 20
    wf_step_days: 20
    wf_embargo_days: 1
    median_oos_sharpe_min: 0.20
    positive_fold_min: 0.60
    dsr_min: 0.0                # monitor_only in Phase 2 (Phase 4 で hard 化)
  stage_c:
    holdout_days: 60
    spread_stress_multiplier: 1.5
    # 1.5x stress 後の hard gate 下限 (live_criteria.* を流用しないため別定義)
    spread_stress_min_total_pnl: 0.0
    spread_stress_min_sharpe: 0.0
```

**死に設定の明示 (CONCEPT-FIXED)**:
- `stage_a.target_pass_rate`: calibrate-gate TODO 用の予約値。本 TODO の
  `evaluate_stage_a` は読まない。コメントで `# monitor_only` を明示。
- `stage_a.threshold`: 本 TODO は 0.0 固定で読み取る。calibrate-gate が
  observed pass rate に応じて上下させる将来運用を docs に明記。
- `stage_b.dsr_min`: 本 TODO は読まない (monitor)。Phase 4 hard 化時に
  使うフィールドの先取り定義。コメントで `# monitor_only` を明示。

既存 `live_criteria` セクションは **そのまま再利用**（重複定義しない）。
`StageGateConfig` の `live_criteria` フィールドはこの既存ブロックを
そのまま受ける。

## 4. 公開 API

```python
from typing import Protocol
from datetime import datetime

@dataclass(frozen=True)
class StageGateConfig: ...

@dataclass(frozen=True)
class CrossPairResult:
    target_pair: str
    anchor_pairs: tuple[str, ...]
    aggregator_name: str             # "mean_minus_half_std" 等
    window: tuple[datetime, datetime]
    passed: bool                     # 将来 hard gate 化用 (本 TODO は monitor)
    metrics: dict                    # mean_sharpe / std_sharpe / per_pair_sharpe 等
    reason_codes: tuple[str, ...]

class CrossPairEvaluator(Protocol):
    def evaluate(
        self,
        genome,
        target_pair: str,
        pair_bars_map: Mapping[str, list[PriceBar]],
        meta_map: Mapping[str, InstrumentMeta],
        backtest_config: BacktestConfig,
    ) -> CrossPairResult: ...

@dataclass(frozen=True)
class StageResult:
    stage: Literal["A", "B", "C"]
    passed: bool
    metrics: dict                    # 共通 envelope + payload (§3.2 参照)
    reason_codes: tuple[str, ...] = ()

    @property
    def reason_if_failed(self) -> str:
        return ";".join(self.reason_codes)

def evaluate_stage_a(
    genome, bars_60d, meta, backtest_config,
    primitive_evaluator, stage_config,
) -> StageResult: ...

def evaluate_stage_b(
    genome, bars_18m, meta, backtest_config,
    primitive_evaluator, stage_config,
) -> StageResult: ...

def evaluate_stage_c(
    genome, bars_holdout, meta, backtest_config,
    primitive_evaluator, stage_config,
    *,
    cross_pair_evaluator: CrossPairEvaluator | None = None,
    cross_pair_inputs: Mapping[str, object] | None = None,
    # cross_pair_inputs は target_pair / pair_bars_map / meta_map を含む辞書。
    # cross_pair_evaluator が非 None のとき必須、None のとき無視。
    # 詳細設計で TypedDict として正規化する
) -> StageResult: ...

# walk_forward.py
def make_wf_folds(
    bars: list[PriceBar],
    train_days: int,
    test_days: int,
    step_days: int,
    embargo_days: int,
) -> list[tuple[list[PriceBar], list[PriceBar]]]:
    """observed-day index ベースで (train, test) bars 列を返す (§3.6 参照)."""
```

## 5. テスト方針

`tests/alpha_factory/test_stage_gate.py`:
- **make_wf_folds**:
  - 単純 100 日 bars で fold 数・サイズ検証
  - embargo 0 / 1 / 5 で gap 検証
  - 短すぎる入力で空 list 返却
  - 不規則日付（祝日抜け）で UTC date ベース切り出しの正しさ
- **evaluate_stage_a**:
  - 通過 synthetic genome（高 sharpe → 通過）
  - α_A による降下で不通過になる境界
  - no_trades / metric_unavailable の reason 検証
- **evaluate_stage_b**:
  - 全 fold positive sharpe → 通過
  - median 不足で不通過 (`median_oos_sharpe<min`)
  - positive_fold_ratio 不足で不通過
  - fold ゼロ → no_folds、fold 1 → insufficient_folds
- **evaluate_stage_c**:
  - 全 live_criteria 境界値（境界一致は通過、わずかに下回ると不通過、
    各 violation で正確な canonical reason code が出る）
  - trade_count 範囲外（<min, >max）で reason `live_criteria.trade_count<min`
    / `live_criteria.trade_count>max`
  - max_drawdown_frac 境界値 (0.20 ちょうど通過、0.21 不通過、reason
    `live_criteria.max_drawdown>max`)
  - イントラデイ違反 trade を含む synthetic 結果で
    `intraday_constraint_violation` 不通過
  - spread stress 後 trade_count 不足で `spread_stress.trade_count<min` 不通過
  - spread stress 後 total_pnl 負で `spread_stress.total_pnl<min` 不通過
  - spread stress 後 sharpe 負 / None で `spread_stress.sharpe<min` 不通過
  - **`max_spread_bps=None` のとき `passed=False` かつ `reason_codes` に
    `spread_stress_skipped` が含まれることを assert** (fail-closed の検証)
  - `cross_pair_evaluator=None` で `metrics.cross_pair.skipped=True` だが
    passed には影響しない (Phase 2 shadow only)
  - 複数 violation 同時発生で `reason_codes` に複数 code が並ぶ
- **StageResult.metrics 共通 envelope**: 各 Stage で `stage` /
  `genome_name` / `n_bars` / `wall_time_seconds` キーが含まれることを assert
- **StageResult.reason_codes 型**: `tuple[str, ...]` であること、要素は
  Stage 別 canonical 語彙のみであることを assert

## 6. 設計上の判断点（Codex レビュー必須項目）

### 6.1 Stage A 閾値の固定
本 TODO では `stage_a_threshold = 0.0` 固定。`calibrate-gate` 連動は別 TODO。
**反論**: 全 Genome 通過 / 全 Genome 不通過のリスク。**応答**: GA 初期世代では
ほぼ random Genome で fitness_pen <= 0 が大多数 → 自然に絞り込まれる想定。
通過率は metrics として monitor 可能。calibrate-gate がその後微調整。

### 6.2 Stage B IS 学習なし
本 TODO の Stage B は OOS 検定のみで、IS 学習（パラメータ調整）は GA 側の責務。
**反論**: WF の本来の意味（再学習）から逸脱。**応答**: Alpha Factory アーキ
チャでは Genome は GA でのみ生成され、Stage B は **固定 Genome の WF-OOS
検証** が責務。debate-synthesis の "Full IS + WF-OOS" は IS フィット結果
（GA 出力）の OOS 評価を意味する。

### 6.3 DSR 計算の保留
本 TODO では DSR を計算せず monitor 用 `dsr=None`。
**反論**: debate-synthesis Phase 2 必須リストに DSR が入っている。
**応答**: `n_trials >= 2` が DSR の数学的前提（statistics.py の docstring 参照）。
本 TODO の Stage B は **単一 Genome の WF 評価** であり `n_trials = 1`。
複数 Genome の集団全体に対する DSR 計算は **GA runner / archive 統合 TODO**
の責務（trial 数 = 評価された Genome 数を runner が把握する）。
詳細設計で `dsr` フィールドの placeholder 形（None / 0.0 / "deferred"）を確定。

### 6.4 Stage C 失敗時の stress test スキップ可否
**判断**: live_criteria 失敗時も stress test は実行する。理由: stress 後の
metrics は archive 用に常に欲しい（劣化幅の monitor）。pure function の
予測可能性も担保。

### 6.5 cross_pair_evaluator の interface
本 TODO では `Protocol` + `CrossPairResult` dataclass で定義のみ。詳細は §4 公開 API
に記載。Round 2 で hard-gate-ready 化済み（`pair_bars_map` / `meta_map` /
`target_pair` 入力、`CrossPairResult` 戻り）。実装本体は
`cross-pair-evaluation-shadow` TODO。

## 7. 実装順序

1. `src/alpha_factory/walk_forward.py` 新規 + `make_wf_folds` 実装
2. `src/alpha_factory/stage_gate.py` 新規 + dataclass / Stage A
3. Stage B（make_wf_folds 依存）
4. Stage C
5. `config/alpha_factory/default.yaml` 更新
6. `tests/alpha_factory/test_stage_gate.py` 一式
7. `docs/alpha_factory/stage-gates.md` 詳細化 + terminology.md 追記

## 8. 影響範囲

- 新規モジュール: `src/alpha_factory/stage_gate.py`,
  `src/alpha_factory/walk_forward.py`
- 変更モジュール: `config/alpha_factory/default.yaml` のみ
  （既存コード変更なし）
- 新規テスト: `tests/alpha_factory/test_stage_gate.py`
- ドキュメント更新: `docs/alpha_factory/stage-gates.md`,
  `docs/alpha_factory/terminology.md`

既存 633 tests への影響: なし（新規モジュールのみ）

## 9. リスクと緩和

- **リスク**: M1 で 60 観測日 ≈ 60 × 1440 ≈ 86,400 bars (FX 24/5)。Stage A の
  evaluate_genome が遅いと GA loop で律速。
  **緩和**: Stage A は最も評価頻度が高いので、最低限の sharpe + complexity
  のみで判定。run_backtest の重さは別途 profile して別 TODO。
- **リスク**: WF fold 数が大きくなるとメモリ・時間爆発。
  18 ヶ月 ≈ 18 × 22 ≈ 396 観測日 (FX 24/5、週末除く、祝日でさらに減)、
  step 20d → fold 数 ≈ floor((396 - 120 - 1 - 20) / 20) + 1 ≈ 13-14 fold。許容範囲。
- **リスク**: stress test で再 backtest = Stage C の評価コスト 2 倍。
  **緩和**: Stage C は通過率最低なので絶対評価数は少ない。
- **リスク**: max_drawdown unit の取り違え (% vs fraction)。
  **緩和**: §3.5 で fraction 統一を CONCEPT-FIXED。Stage C 内で 1 回だけ
  `/100` 換算する。metrics は `max_drawdown_frac` で統一。
- **リスク**: cross-pair shadow → hard 移行時の interface 互換性。
  **緩和**: §3.5 で `CrossPairResult` dataclass + Protocol 入力 schema を
  CONCEPT-FIXED。passed フラグは将来 hard gate で StageResult.passed に AND
  で合成可能な構造。

## 10. 完了判定

- 全テスト pass (633 + 新規 N tests / 1 skip)
- mypy clean (`uv run mypy src/alpha_factory/`)
- ruff clean (`uv run ruff check src/ tests/`)
- Codex impl-review APPROVED
- ドキュメント更新完了
- TODO T014 close + main merge
