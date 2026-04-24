# 詳細設計: alpha-sieve OOS validation framework + skill port (T025)

**前提**: `conceptual-design.md` (本ディレクトリ) APPROVED-with-closure 済。
本ドキュメントは実装に直結する I/O / 関数 signature / テストケースを定義する。

---

## 1. ファイル / モジュール構成

```
scripts/alpha_factory/run_alpha_sieve.py     ← 新規 (~450 LoC)
.claude/skills/zenigame-fx-alpha-sieve/SKILL.md  ← 新規
tests/scripts/test_run_alpha_sieve.py        ← 新規
docs/alpha_factory/concepts/alpha-sieve.md   ← 既に新規作成済み
docs/alpha_factory/sieve.md                  ← 新規（運用ドキュメント）
docs/alpha_factory/terminology.md            ← Alpha Sieve / Sieve OOS Window 追加
```

---

## 2. `scripts/alpha_factory/run_alpha_sieve.py` 仕様

### 2.1 module docstring

```python
"""Alpha Sieve: Stage C 通過個体を別期間 OOS で再検証する追加ゲート (T025)。

Stage C 通過個体は holdout 60 日で live_criteria を満たした状態に過ぎないため、
holdout 直後 5 日のエンバーゴ + 90 日 OOS で再 backtest し、
sharpe > 0.5 AND trade_count >= 30 AND total_pnl > 0 を要求して true positive を絞る。

入力:
- archive Parquet: .cache/alpha_factory/runs/genomes_{run_id}.parquet
- summary.json:    reports/run-reports/run-{N}/summary.json (backtest_config 引き継ぎ用)
- DB:              src.db.connection.SessionLocal (PostgreSQL)

出力:
- reports/alpha-sieve/{yyyy-mm}/sieve-R{run_number}.md

設計根拠:
- docs/alpha_factory/concepts/alpha-sieve.md
- devnotes/20260424-1444-port-alpha-sieve/{conceptual,detailed}-design.md
- devnotes/20260421-1850-fx-skill-port/debate-synthesis.md §B / §E

学術引用:
- Bailey, D. H., Borwein, J. M., López de Prado, M., Zhu, Q. J. (2014).
  The Probability of Backtest Overfitting.
- López de Prado, M. (2018). Advances in Financial Machine Learning, Ch.7
  (Cross-Validation in Finance: purged/embargoed CV).
"""
```

### 2.2 主要 dataclass

```python
@dataclass(frozen=True)
class SieveConfig:
    sieve_window_days: int = 90
    sieve_embargo_days: int = 5
    sharpe_min: float = 0.5          # strict gt
    trade_count_min: int = 30        # >=
    total_pnl_min: float = 0.0       # strict gt

    def __post_init__(self) -> None:
        if self.sieve_window_days < 1:
            raise ValueError("sieve_window_days must be >= 1")
        if self.sieve_embargo_days < 0:
            raise ValueError("sieve_embargo_days must be >= 0")
        if self.trade_count_min < 1:
            raise ValueError("trade_count_min must be >= 1")


@dataclass(frozen=True)
class CandidateRow:
    """archive Parquet から取り出した Stage C 通過個体 1 行."""
    individual_name: str
    lane_id: str
    instrument: str
    generation: int
    genome_json: str               # → Genome 復元
    stage_c_sharpe: float | None
    stage_c_total_pnl: float
    stage_c_trade_count: int


@dataclass(frozen=True)
class SieveEvalResult:
    """1 個体の Sieve 評価結果."""
    candidate: CandidateRow
    status: Literal["evaluated", "no_data", "system_failure"]
    oos_sharpe: float | None
    oos_total_pnl: float
    oos_trade_count: int
    oos_max_drawdown_pct: float
    oos_dsr: float | None          # Phase 2: 恒常 None。Phase 4 で trial pool 連動で計算 (info only)
    passed: bool
    reason_codes: tuple[str, ...]  # 空タプル = 通過
```

### 2.3 関数 signature

```python
def _parse_args(argv: list[str] | None = None) -> argparse.Namespace: ...

def _resolve_run(
    *,
    run_id: str | None,
    run_number: int | None,
) -> tuple[str, int, Path, Path]:
    """Returns (run_id, run_number, archive_parquet_path, summary_json_path)."""

def _load_stage_c_passers(parquet_path: Path) -> list[CandidateRow]: ...

def _load_oos_bars(
    instrument: str,
    sieve_start: datetime,
    sieve_end: datetime,
) -> tuple[list[PriceBar], InstrumentMeta | None]:
    """DB から OOS 期間 bars + meta を取得。bars 0 件なら ([], meta)。"""

def _evaluate_one(
    candidate: CandidateRow,
    bars: list[PriceBar],
    meta: InstrumentMeta,
    backtest_config: BacktestConfig,
    primitive_evaluator: PrimitiveEvaluator,
    sieve_config: SieveConfig,
) -> SieveEvalResult: ...

def _judge(
    sharpe: float | None,
    total_pnl: float,
    trade_count: int,
    sieve_config: SieveConfig,
) -> tuple[bool, tuple[str, ...]]:
    """通過判定。reason_codes は失敗理由 (empty tuple = pass)."""

def _render_report(
    *,
    status: Literal["ok", "no_candidates", "no_data"],
    run_id: str,
    run_number: int,
    archive_path: Path,
    instrument: str,
    holdout_end: datetime,
    sieve_config: SieveConfig,
    sieve_start: datetime,
    sieve_end: datetime,
    bars_loaded: int,
    backtest_config: BacktestConfig,
    candidates: list[CandidateRow],
    eval_results: list[SieveEvalResult],
    generated_at: datetime,
) -> str: ...

def main(argv: list[str] | None = None) -> int: ...
```

### 2.4 オーケストレーション (`main`)

```python
def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    sieve_config = SieveConfig(
        sieve_window_days=args.sieve_window_days,
        sieve_embargo_days=args.sieve_embargo_days,
    )

    # 1. run 解決
    run_id, run_number, archive_path, summary_path = _resolve_run(
        run_id=args.run_id, run_number=args.run_number
    )

    # 2. archive 不存在 → error (exit 1)
    if not archive_path.exists():
        print(f"ERROR: archive not found: {archive_path}", file=sys.stderr)
        return 1
    if not summary_path.exists():
        print(f"ERROR: summary.json not found: {summary_path}", file=sys.stderr)
        return 1

    # 3. summary から dataset / backtest_config を引き継ぎ
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    instrument = summary["dataset"]["instrument"]
    dataset_end = datetime.fromisoformat(summary["dataset"]["end"])
    stage_c_holdout_days = int(
        summary.get("stage_gate_config", {}).get("stage_c_holdout_days", 60)
    )
    holdout_end = dataset_end + timedelta(days=stage_c_holdout_days)
    sieve_start = holdout_end + timedelta(days=sieve_config.sieve_embargo_days)
    sieve_end = sieve_start + timedelta(days=sieve_config.sieve_window_days)
    backtest_config = _build_oos_backtest_config(
        instrument=instrument,
        summary=summary,
        sieve_start=sieve_start,
        sieve_end=sieve_end,
        config_path=args.config,
    )

    # 4. Stage C 通過個体抽出
    candidates = _load_stage_c_passers(archive_path)
    if not candidates:
        report = _render_report(
            status="no_candidates",
            run_id=run_id, run_number=run_number,
            archive_path=archive_path, instrument=instrument,
            holdout_end=holdout_end, sieve_config=sieve_config,
            sieve_start=sieve_start, sieve_end=sieve_end,
            bars_loaded=0, backtest_config=backtest_config,
            candidates=[], eval_results=[],
            generated_at=datetime.now(UTC),
        )
        _write_report(run_number, report)
        return 0

    # 5. OOS bars 取得
    bars, meta = _load_oos_bars(instrument, sieve_start, sieve_end)
    if not bars or meta is None:
        report = _render_report(
            status="no_data", ...
            candidates=candidates, eval_results=[],
            ...
        )
        _write_report(run_number, report)
        return 0

    # 6. 各個体評価
    ensure_registered()
    primitive_evaluator = RegistryEvaluator(pair=instrument)
    eval_results = [
        _evaluate_one(c, bars, meta, backtest_config, primitive_evaluator, sieve_config)
        for c in candidates
    ]

    # 7. レポート生成 + 出力
    report = _render_report(
        status="ok", ...
        eval_results=eval_results,
        bars_loaded=len(bars), ...
    )
    _write_report(run_number, report)
    return 0
```

### 2.5 `_load_stage_c_passers` 実装

```python
def _load_stage_c_passers(parquet_path: Path) -> list[CandidateRow]:
    table = GenomeArchive.load(parquet_path)
    df = table.to_pandas()  # pyarrow → pandas で filter （小規模行数想定）
    passers = df[df["stage_c_pass"] == True]  # noqa: E712
    rows: list[CandidateRow] = []
    for _, r in passers.iterrows():
        rows.append(CandidateRow(
            individual_name=str(r["individual_name"]),
            lane_id=str(r["lane_id"]),
            instrument=str(r["instrument"]),
            generation=int(r["generation"]),
            genome_json=str(r["genome_json"]),
            stage_c_sharpe=float(r["sharpe"]) if pd.notna(r["sharpe"]) else None,
            stage_c_total_pnl=float(r["total_pnl"]),
            stage_c_trade_count=int(r["trade_count"]),
        ))
    return rows
```

### 2.6 `_evaluate_one` 実装

```python
def _evaluate_one(
    candidate: CandidateRow,
    bars: list[PriceBar],
    meta: InstrumentMeta,
    backtest_config: BacktestConfig,
    primitive_evaluator: PrimitiveEvaluator,
    sieve_config: SieveConfig,
) -> SieveEvalResult:
    if not bars:
        return SieveEvalResult(
            candidate=candidate, status="no_data",
            oos_sharpe=None, oos_total_pnl=0.0, oos_trade_count=0,
            oos_max_drawdown_pct=0.0, oos_dsr=None, passed=False,
            reason_codes=("no_data",),
        )
    try:
        genome = genome_from_dict(json.loads(candidate.genome_json))
        strategy = DslStrategy(genome, primitive_evaluator)
        broker = MockBroker(instrument_meta=meta)
        result = run_backtest(bars, strategy, broker, backtest_config)
        bt = compute_metrics(result.trades, result.equity_curve)
        sharpe = float(bt.sharpe) if bt.sharpe is not None else None
        total_pnl = float(bt.total_pnl)
        trade_count = bt.trade_count
        max_dd_pct = float(bt.max_drawdown_pct)
    except Exception as exc:
        logger.warning(
            "alpha_sieve.eval_failure",
            individual=candidate.individual_name, error=str(exc),
        )
        return SieveEvalResult(
            candidate=candidate, status="system_failure",
            oos_sharpe=None, oos_total_pnl=0.0, oos_trade_count=0,
            oos_max_drawdown_pct=0.0, oos_dsr=None, passed=False,
            reason_codes=("system_failure",),
        )

    # DSR (Phase 2 では恒常 None。Phase 4 で trial pool 連動で計算する)
    oos_dsr = _compute_dsr_safe(sharpe=sharpe)

    passed, reason_codes = _judge(sharpe, total_pnl, trade_count, sieve_config)
    return SieveEvalResult(
        candidate=candidate, status="evaluated",
        oos_sharpe=sharpe, oos_total_pnl=total_pnl, oos_trade_count=trade_count,
        oos_max_drawdown_pct=max_dd_pct, oos_dsr=oos_dsr,
        passed=passed, reason_codes=reason_codes,
    )
```

### 2.7 `_judge` 実装

```python
def _judge(
    sharpe: float | None,
    total_pnl: float,
    trade_count: int,
    sieve_config: SieveConfig,
) -> tuple[bool, tuple[str, ...]]:
    reasons: list[str] = []
    if sharpe is None:
        reasons.append("sharpe_unavailable")
    elif sharpe <= sieve_config.sharpe_min:  # strict gt
        reasons.append(f"sharpe<={sieve_config.sharpe_min}")
    if trade_count < sieve_config.trade_count_min:
        reasons.append(f"trade_count<{sieve_config.trade_count_min}")
    if total_pnl <= sieve_config.total_pnl_min:  # strict gt
        reasons.append("total_pnl<=0")
    return (len(reasons) == 0), tuple(reasons)
```

### 2.8 DSR 取り扱い (Phase 2 = 計算スキップ、フィールドのみ保持)

**仕様確定**: `src.alpha_factory.statistics.deflated_sharpe_ratio` の実シグネチャは:

```python
def deflated_sharpe_ratio(
    sharpe_ratio: float,        # bar 単位 non-annualized
    n_trials: int,              # >= 2  ← Sieve 単一個体評価では不定
    n_observations: int,        # >= 2
    skew: float,                # リターン分布の歪度
    kurtosis: float,            # non-excess (正規分布で 3.0)
    mean_sr_trials: float,      # 試行候補 SR 分布の平均
    std_sr_trials: float,       # 試行候補 SR 分布の標準偏差 (>0)
) -> float
```

DSR は **複数試行 (n_trials>=2)** の選択バイアス補正指標であり、Sieve は「Stage C 通過個体 1 体ごとに 1 回」評価するため、
本来 DSR が要求する "trial pool" の統計量 (`mean_sr_trials` / `std_sr_trials`) を Sieve 単独では構成できない。

→ **Phase 2 結論**: `oos_dsr` フィールドは dataclass に残しつつ **常に `None` を格納**し、レポートでは `--` 表示。
Phase 4 で「Stage C 通過個体プール全体の SR 分布」を `mean_sr_trials` / `std_sr_trials` として与える形で正式接続する
（その時点で `compute_oos_dsr_from_pool(...)` 等のヘルパを `src/alpha_factory/statistics.py` に追加）。

```python
def _compute_dsr_safe(*, sharpe: float | None) -> None:
    """Phase 2: 常に None を返す (DSR の trial pool が単一個体評価では構成不能)。

    Phase 4 で Stage C 通過個体プール全体の SR 分布を入力に、
    deflated_sharpe_ratio() を呼び出すヘルパへ置換する。
    """
    return None
```

**SieveEvalResult.oos_dsr** の field 型は `float | None` のまま据え置き、Phase 2 では恒常 None。
レポート `DSR (info)` カラムは `--` 固定表示。

### 2.9 `_build_oos_backtest_config` — 完全 SSOT 化

**観察事実 (Codex review C1 適用)**:
- `scripts/alpha_factory/run_ga.py` の summary.json 出力 (L617-621) は **`backtest_config` に `initial_cash` / `leverage` / `units` の 3 フィールドしか書き出さない**
- `BacktestConfig` 実体 (`src/backtest/engine.py`) は他に `max_spread_bps`, `holding_cost_per_day_bps`, `session_close_utc_hours`, `bar_minutes` を持つ
- これらの値は GA 実行時に `BacktestSectionConfig` (config.py) → `_make_bt_factory` で挿入されている
- つまり **summary 単独では BacktestConfig を完全再現できない**

**結論**: Sieve は `config/alpha_factory/default.yaml` を **YAML loader 経由で再ロード** し、`BacktestSectionConfig` を SSOT として活用する。
summary.json の値とは **整合性チェック** のみ行う（不一致なら警告ログ）。

```python
def _build_oos_backtest_config(
    *,
    instrument: str,
    summary: dict[str, Any],
    sieve_start: datetime,
    sieve_end: datetime,
    config_path: Path,
) -> BacktestConfig:
    """OOS backtest 用 BacktestConfig を組み立てる。

    SSOT 戦略:
      1. config/alpha_factory/default.yaml から BacktestSectionConfig を再ロード
         （summary に含まれない max_spread_bps / holding_cost / session_close を取得）
      2. summary.json の backtest_config (initial_cash / leverage / units) と
         整合性チェック → 不一致なら logger.warning
      3. BacktestSectionConfig 値で BacktestConfig を構築
    """
    cfg = load_config(config_path, overrides={})
    bt_section: BacktestSectionConfig = cfg.backtest

    # 整合性チェック (summary 由来の 3 フィールド)
    summary_bt = summary.get("backtest_config", {})
    if summary_bt:
        if summary_bt.get("initial_cash") and Decimal(str(summary_bt["initial_cash"])) != bt_section.initial_cash:
            logger.warning(
                "alpha_sieve.backtest_config_mismatch",
                field="initial_cash",
                summary=summary_bt["initial_cash"],
                config=str(bt_section.initial_cash),
            )
        if summary_bt.get("leverage") and int(summary_bt["leverage"]) != bt_section.leverage:
            logger.warning(
                "alpha_sieve.backtest_config_mismatch",
                field="leverage",
                summary=summary_bt["leverage"],
                config=bt_section.leverage,
            )
        # units は BacktestConfig には載らないが整合性のみチェック
        if summary_bt.get("units") and int(summary_bt["units"]) != bt_section.units:
            logger.warning(
                "alpha_sieve.backtest_config_mismatch",
                field="units",
                summary=summary_bt["units"],
                config=bt_section.units,
            )

    return BacktestConfig(
        instrument=instrument,
        start=sieve_start,
        end=sieve_end,
        initial_cash=bt_section.initial_cash,
        leverage=bt_section.leverage,
        max_spread_bps=bt_section.max_spread_bps,
        holding_cost_per_day_bps=bt_section.holding_cost_per_day_bps,
        session_close_utc_hours=frozenset(bt_section.session_close_utc_hours),
        bar_minutes=1,  # M1 fixed (run_ga と同じ)
    )
```

**フィールド対応表（網羅的）**:

| BacktestConfig field | source | Sieve での扱い |
|----------------------|--------|---------------|
| `instrument` | summary.dataset.instrument | 引き継ぎ |
| `start` | computed (sieve_start) | OOS 期間先頭 |
| `end` | computed (sieve_end) | OOS 期間末尾 |
| `initial_cash` | YAML config.backtest.initial_cash (SSOT) | summary と整合性チェック |
| `leverage` | YAML config.backtest.leverage (SSOT) | summary と整合性チェック |
| `max_spread_bps` | YAML config.backtest.max_spread_bps | YAML SSOT (summary に未出力) |
| `holding_cost_per_day_bps` | YAML config.backtest.holding_cost_per_day_bps | YAML SSOT |
| `session_close_utc_hours` | YAML config.backtest.session_close_utc_hours | YAML SSOT |
| `bar_minutes` | 固定 1 | M1 前提 |

**未対応フィールド**: 現時点で `BacktestConfig` に上記以外のフィールドは存在しない（手数料 / max_position_bars 等は未実装）。
将来追加された場合は `BacktestSectionConfig` 経由で自動継承される（SSOT 化の利点）。

**CLI 拡張**: `--config` 引数を追加し、デフォルトは `config/alpha_factory/default.yaml`。

### 2.10 出力レポート

`_write_report(run_number, report)` は以下に書き出す:
```
reports/alpha-sieve/{generated_at の yyyy-mm}/sieve-R{run_number}.md
```

`{yyyy-mm}` は **書き込み時の JST 年月** (zenigame と同じ慣習)。

### 2.11 CLI

```python
def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Alpha Sieve: Stage C 通過個体を OOS で再検証")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--run-id", default=None)
    g.add_argument("--run-number", type=int, default=None)
    p.add_argument("--sieve-window-days", type=int, default=90)
    p.add_argument("--sieve-embargo-days", type=int, default=5)
    p.add_argument(
        "--config",
        type=Path,
        default=Path("config/alpha_factory/default.yaml"),
        help="BacktestSectionConfig SSOT として再ロードする YAML パス",
    )
    return p.parse_args(argv)
```

---

## 3. テスト設計 (`tests/scripts/test_run_alpha_sieve.py`)

### 3.1 共通 fixture

```python
@pytest.fixture
def tmp_run_files(tmp_path, monkeypatch):
    """Mock archive Parquet + summary.json を tmp に作る."""
    archive_dir = tmp_path / ".cache/alpha_factory/runs"
    archive_dir.mkdir(parents=True)
    reports_dir = tmp_path / "reports/run-reports/run-99"
    reports_dir.mkdir(parents=True)
    out_dir = tmp_path / "reports/alpha-sieve"
    monkeypatch.setattr(run_alpha_sieve, "ARCHIVE_DIR", archive_dir)
    monkeypatch.setattr(run_alpha_sieve, "RUN_REPORTS_DIR", tmp_path / "reports/run-reports")
    monkeypatch.setattr(run_alpha_sieve, "OUTPUT_DIR", out_dir)
    return SimpleNamespace(archive_dir=archive_dir, reports_dir=reports_dir, out_dir=out_dir)
```

### 3.2 テストケース

| # | テスト名 | 内容 | 期待 |
|---|---------|------|------|
| 1 | `test_judge_pass` | `sharpe=0.6, trades=30, pnl=1.0` | passed=True, reasons=() |
| 2 | `test_judge_sharpe_fail` | `sharpe=0.5, trades=30, pnl=1.0` (boundary, strict gt) | passed=False, reasons contains sharpe |
| 3 | `test_judge_trade_count_fail` | `sharpe=0.6, trades=29, pnl=1.0` | passed=False, reasons contains trade_count |
| 4 | `test_judge_pnl_fail` | `sharpe=0.6, trades=30, pnl=0.0` (boundary) | passed=False, reasons contains total_pnl |
| 5 | `test_judge_sharpe_none` | `sharpe=None, trades=30, pnl=1.0` | passed=False, reasons contains sharpe_unavailable |
| 6 | `test_load_stage_c_passers_filters_correctly` | mock parquet (3 行: pass / fail / pass) | 2 行返却 |
| 7 | `test_load_stage_c_passers_empty` | mock parquet (Stage C 通過 0 件) | 空 list |
| 8 | `test_main_no_archive_returns_1` | archive 不存在 | exit 1 + stderr error |
| 9 | `test_main_no_candidates_writes_report` | archive あり、Stage C 通過 0 件 | exit 0 + `status: no_candidates` レポート |
| 10 | `test_main_no_oos_bars_writes_report` | archive あり Stage C 通過 1 件、DB bars 0 件 (mock) | exit 0 + `status: no_data` |
| 11 | `test_evaluate_one_handles_exception` | genome_from_dict が raise (壊れた JSON) | status="system_failure", reasons=("system_failure",) |
| 12 | `test_render_report_includes_criteria_snapshot_and_status` | render → 文字列に `status:` `criteria_snapshot` `cost_model` を含む |
| 13 | `test_sieve_config_validates_negative_embargo` | `SieveConfig(sieve_embargo_days=-1)` | ValueError |
| 14 | `test_evaluate_one_success_with_real_backtest` | mock primitives + 短い bars list で実 backtest 通過 | status="evaluated", oos_sharpe is float |
| 15 | `test_evaluate_one_returns_no_data_for_empty_bars` | `bars=[]` を渡す | status="no_data", reasons contains "no_data" |
| 16 | `test_compute_dsr_safe_returns_none_in_phase2` | sharpe=0.6 の値を渡す | None (恒常 None policy 検証) |
| 17 | `test_build_oos_backtest_config_uses_yaml_ssot` | summary.backtest_config と config YAML が一致するケース | BacktestConfig.max_spread_bps == YAML 値 |
| 18 | `test_build_oos_backtest_config_warns_on_mismatch` | summary.initial_cash != YAML | WARN ログ発行 + YAML 値が反映 |

### 3.3 モック方針

- `_load_oos_bars` は monkeypatch で fake bars / meta を返す（DB 接続を回避）
- `_evaluate_one` のテスト方針:
  - **ケース 14 (`test_evaluate_one_success_with_real_backtest`)**: 短い実 bars + 既存 primitive evaluator で **実 backtest を 1 ケース実施** → status="evaluated" / oos_sharpe が float 値であることを検証
  - **ケース 15 (`test_evaluate_one_returns_no_data_for_empty_bars`)**: `bars=[]` の早期 return パスを検証（実 backtest 不要）
  - **ケース 11 (`test_evaluate_one_handles_exception`)**: 壊れた `genome_json` で `genome_from_dict` を例外化 → status="system_failure"
  - その他の `_judge` 単体テスト (1-5) は backtest を経由せず直接 `_judge(...)` を呼ぶ
- main の no_data / no_candidates 経路は `_load_oos_bars` を空 list 返却にモックしてテスト
- DSR fail-soft (ケース 16): `_compute_dsr_safe(sharpe=...)` を直接呼んで `None` 戻り値を assert（Phase 2 policy 検証）
- `_build_oos_backtest_config` テスト (17-18): tmp YAML config + tmp summary.json を fixture で組み合わせる
  - 17: summary と YAML が一致 → BacktestConfig フィールドが YAML 値を反映
  - 18: summary.initial_cash が YAML と異なる → caplog で WARN 発行を検出 + BacktestConfig は YAML 値

---

## 4. skill SKILL.md 草案

```markdown
---
name: zenigame-fx-alpha-sieve
description: Alpha Sieve（OOS検証）の実行・結果分析を行う（Stage C 通過個体を別期間 OOS で再検証）
user-invocable: true
---

# Alpha Sieve 実行 skill (zenigame-fx)

`scripts/alpha_factory/run_alpha_sieve.py` を呼び出し、Stage C 通過個体を holdout 後 5 日エンバーゴ + 90 日 OOS で再検証する。

## 使い方

\`\`\`
/zenigame-fx-alpha-sieve <run_id>           # run_id 指定
/zenigame-fx-alpha-sieve --run-number 3     # run number 指定（後方互換）
\`\`\`

## 実行フロー

1. `uv run python scripts/alpha_factory/run_alpha_sieve.py --run-id <run_id>` を実行
2. exit code を確認、stderr に error があれば user に報告
3. 出力レポート path (`reports/alpha-sieve/{yyyy-mm}/sieve-R{run_number}.md`) を Read
4. 以下を抽出して報告:
   - status (ok / no_candidates / no_data / error)
   - sieve 通過個体数 / Stage C 通過個体数 / pass 率
   - 通過個体上位 3 体の OOS Sharpe / PnL / Trade
   - 不通過理由分布

## レポート出力先

- `reports/alpha-sieve/{yyyy-mm}/sieve-R{run_number}.md`

## 通過基準

- `sharpe > 0.5 AND trade_count >= 30 AND total_pnl > 0`

## OOS 期間

- `holdout_end + 5 日 (embargo) ~ + 90 日`

## エラーハンドリング

- archive Parquet / summary.json 不存在 → exit 1 + error 報告
- Stage C 通過 0 件 → exit 0 + `no_candidates` レポート出力
- OOS bars 不存在 → exit 0 + `no_data` レポート出力

## 関連ドキュメント

- `docs/alpha_factory/concepts/alpha-sieve.md`
- `docs/alpha_factory/sieve.md`
\`\`\`
```

---

## 5. 既存モジュール再利用一覧

| 用途 | モジュール |
|------|-----------|
| DB session | `src.db.connection.SessionLocal` |
| DB models | `src.db.models.{CurrencyPair, PriceBarM1}` |
| Parquet load | `src.alpha_factory.archive.GenomeArchive.load` |
| bars 変換 | `scripts.alpha_factory.run_ga._bar_row_to_price_bar / _meta_from_pair`（DRY 維持で import） |
| backtest | `src.backtest.engine.{run_backtest, BacktestConfig}` / `compute_metrics` |
| broker | `src.broker.mock.MockBroker` / `InstrumentMeta` |
| strategy | `src.dsl.strategy.DslStrategy` |
| primitives | `src.alpha_factory.primitives.{RegistryEvaluator, ensure_registered}` |
| Genome | `src.dsl.genome.Genome` / `src.dsl.serialize.genome_from_dict` |
| YAML loader | `src.alpha_factory.config.{load_config, BacktestSectionConfig}`（OOS BacktestConfig SSOT） |
| DSR (Phase 2 stub) | `_compute_dsr_safe(*, sharpe) -> None` 内部固定。Phase 4 で `src.alpha_factory.statistics.deflated_sharpe_ratio` に trial pool 統計量と共に接続 |

`scripts/alpha_factory/run_ga._bar_row_to_price_bar` は **module private (`_` prefix)** だが、Phase 2 では SSOT を 1 箇所に保つ目的で**そのまま import**する。Phase 4 で `src.alpha_factory.bars_loader` に括り出す TODO を分離する。

---

## 6. mypy / ruff チェック方針

- `scripts/alpha_factory/run_alpha_sieve.py` は既存 run_ga.py / analyze_run.py と同じ tier のスクリプト → `src/` と同じ型厳格度
- `mypy: --strict` で通る粒度
- ruff: `E`, `F`, `I` 既定 + 既存設定
- pyarrow / pandas import の型は run_ga.py と同じ pattern

---

## 7. 動作確認 (smoke test)

```bash
uv run pytest tests/scripts/test_run_alpha_sieve.py -v
uv run mypy src/ scripts/alpha_factory/run_alpha_sieve.py
uv run ruff check src/ tests/ scripts/

# cycle 21 run-3 (Stage C 通過 0 件) で smoke
uv run python scripts/alpha_factory/run_alpha_sieve.py --run-id run_20260423_195917
# 期待: exit 0、reports/alpha-sieve/2026-04/sieve-R3.md が生成され status: no_candidates
```

---

## 8. ドキュメント更新計画

- `docs/alpha_factory/concepts/alpha-sieve.md` — 既に新規作成済み
- `docs/alpha_factory/sieve.md` — 新規作成（運用ドキュメント）
- `docs/alpha_factory/terminology.md` — `Alpha Sieve` / `Sieve OOS Window` / `Sieve Embargo` を追加
- `docs/alpha_factory/cross-pair.md` — Sieve は cross-pair と独立した追加ゲートである旨を冒頭/末尾で明示

---

## 9. 残課題（実装後・Phase 4 で対応）

- 取引発生日数下限 (`>=15`) の実装
- DSR の hard gate 化
- 複数非連続 OOS 窓 (CSCV ベース)
- レポート ↔ DB 同期
- 通過基準 calibrate（実測連動）
- Sieve warmstart / score bypass

---

## レビュー観点（Codex design-review 用）

1. **dataclass / 関数 signature** — `SieveConfig` / `CandidateRow` / `SieveEvalResult` の field 構成は妥当か？
2. **strict greater-than vs `>=`** — `_judge` の boundary 仕様（sharpe / pnl は strict gt、trade_count は `>=`）は仕様 §2.3 と一致しているか？
3. **DSR fail-soft** — Phase 2 で DSR を `None` にフォールバックしてもレポート整合性は保たれるか？
4. **backtest_config 引き継ぎ** — `_build_oos_backtest_config` のフォールバック値（`[23]` / `0` / `None`）は GA 既定と整合するか？
5. **既存 module private import** — `run_ga._bar_row_to_price_bar` を script 越境で import する妥協は容認されるか？
6. **テストカバレッジ** — 13 ケースは defensive/通過/反転境界をカバーしているか？追加すべき edge case はあるか？
