# 詳細設計: B Phase 2 切替コミット step 1.6 — Stage B per-fold dual-path 拡張

**作成日時**: 2026-05-03 21:20 JST (Round 2 改訂: 2026-05-03 21:30 JST、 表記整合 patch: 2026-05-03 21:38 JST)
**status**: **詳細設計 Round 2 APPROVED** (= Codex 詳細設計 Round 1 CHANGES_REQUESTED 反映済、 Round 2 で APPROVED 判定。 表記残存 Warning は patch 済)
**概念設計**: `devnotes/20260503-2049-B-phase2-step1.6-stage-b-per-fold-dual-path/conceptual-design.md` (Codex Round 2 APPROVED)

---

## 0. Round 1 → Round 2 改訂対応

| Round 1 指摘 | 対応 |
|---|---|
| [Critical] 5 fold 固定前提が誤り (= 実 fixture では 8 fold、 `compute_max_folds` 式に依存) | 全文の「5 fold」表記を **`n_fold` (動的)** に変更、 `0..4` → `0..n_fold-1`。 acceptance / 性能見積もりを `n_fold` 変数で記述 |
| [Critical] D3 test の helper 無条件 raise は B_IS 先行呼出と衝突 | monkeypatch を **`stage_label=="B_fold"` 限定 raise** に変更 (= wrapper helper、 B_IS 呼出は透過させる) |
| [Critical] 5 fold 固定の log content test fixture 不整合 | log content test も `n_fold` 動的検証に変更 (= `make_wf_folds(...)` で実 fold 数を取得して照合) |
| [Warning] D2 文言が実装案と不一致 (= `log_failed` も出す) | D2 を「`unexpected_failure` または `log_failed`」に更新 |
| [Warning] C5 専用 test 不足 | disabled mode で `stage='B_fold'` 全行に `fold=` kwargs 必須を検証する test を 8 番目に追加 |
| [Suggestion] 性能 / log 量見積もり 5 fold 固定 | 「追加 log 件数 = n_fold」「追加計算 = n_fold」と動的記述、 acceptance B3 で `n_fold` メトリクス併記 |

---

## 1. 使命・制約 (絶対遵守)

### zenigame-fx Alpha Factory 使命
live_criteria 全指標同時充足 + (ii-lite) 通過で使命達成。 絶対制約: イントラデイ / ロング・ショート両方向 / スワップ・スプレッド反映。

### 禁止事項
1. A・B・C 評価期間を根拠なしに延長
2. 見た目の数値改善
3. GA ハック
4. live_criteria 緩和
5. **過度な複雑化** ← 本 step で特に重要 (= 1 step 1 commit リズム維持)
6. 取引回数削減
7. オーバーナイト保有前提
8. ゲノム archive スキーマ変更時の値伝搬漏れ

### コーディングルール
- バグ修正はテストファースト (= 再現テスト → FAIL 確認 → 修正 → PASS)
- 全施策にテスト必須
- テスト命名: 振る舞いを説明する汎用的な名前
- テスト配置: 対象モジュール対応のテストファイル
- uv 必須: `uv run pytest tests/alpha_factory/`
- ruff / mypy 通過: `uv run ruff check src/ tests/` / `uv run mypy src/`

---

## 2. 概念設計リファレンス

`devnotes/20260503-2049-B-phase2-step1.6-stage-b-per-fold-dual-path/conceptual-design.md` (Round 2 APPROVED)

主要決定事項:
- **scope**: Stage B per-fold OOS (= `n_fold` 動的、 各 fold それぞれ) の dual-path 観測拡張のみ (= 任意・有益、 step 2 を block しない)
- **adapter / helper 凍結**: step 1 / 1.5 の helper を完全再利用、 `_log_canonical_dual_path` のみ optional kwarg `fold_index` 追加
- **per-fold thresholds**: per-fold 個別構築 (Option 1)、 同入力 → 同出力 deterministic
- **物理隔離**: dual-path を **legacy fold 計算後** の **別 try ブロック**、 `fold_sharpe` / `fold_reason` / `reason_counts` 完全不変
- **stage_label**: `"B_fold"` + `fold` kwargs key (= `0..n_fold-1` 動的) で n_fold 識別、 `fold_index=None` は ValueError
- **acceptance**: A (判定結果回帰 0) + B (運用回帰検証) + C (legacy 比較可能性 + 識別子契約) + D (例外隔離契約)

---

## 3. 施策一覧

| # | 施策名 | 変更ファイル | 優先度 |
|---|---|---|---|
| 1 | `_log_canonical_dual_path` に optional kwarg `fold_index` 追加 + B_fold 必須契約 | src/alpha_factory/stage_gate.py | High |
| 2 | `evaluate_stage_b` per-fold OOS ループ内に dual-path 配線追加 (= 別 try で物理分離) | src/alpha_factory/stage_gate.py | High |
| 3 | per-fold dual-path test 追加 (= 9 ケース) + 既存 33 ケース後方互換確認 | tests/alpha_factory/test_stage_gate_canonical_dual_path.py | High |

---

## 4. 施策 1: `_log_canonical_dual_path` 拡張

### 4.1 変更箇所
- ファイル: `src/alpha_factory/stage_gate.py:169-225` (= `_log_canonical_dual_path` 関数定義)

### 4.2 波及変更
- `AGENTS.md`: なし
- `.claude/skills/zenigame-fx-*/SKILL.md`: なし
- `config/alpha_factory/default.yaml`: なし
- `docs/alpha_factory/*.md`: なし (= 内部 helper、 docs 露出なし)

### 4.3 現行コード (抜粋)

```python
def _log_canonical_dual_path(
    *,
    stage_label: str,
    genome_name: str,
    legacy: BacktestMetrics,
    canonical: CanonicalFiveResult | None,
) -> None:
    """dual-path 結果 (legacy + canonical) を構造化 log に出力. ..."""
    if canonical is None:
        logger.info(
            "stage_gate.canonical_five.dual_path",
            stage=stage_label,
            genome=genome_name,
            canonical_skipped=True,
        )
        return
    logger.info(
        "stage_gate.canonical_five.dual_path",
        stage=stage_label,
        genome=genome_name,
        flags_source="default_false",
        fail_fast_flags_comparable=False,
        legacy_total_pnl=str(legacy.total_pnl),
        ...
        interpretation_note="direction_monitoring_only",
    )
```

### 4.4 変更後コード

```python
def _log_canonical_dual_path(
    *,
    stage_label: str,
    genome_name: str,
    legacy: BacktestMetrics,
    canonical: CanonicalFiveResult | None,
    fold_index: int | None = None,  # 新規: B_fold で必須、 他 stage は None 許容
) -> None:
    """dual-path 結果 (legacy + canonical) を構造化 log に出力.

    Args:
        stage_label: § 4.7 ログ命名規約 SSOT (A / B_IS / B_fold / C_base / C_cross_pair)。
        genome_name: genome 識別子 (= logger kwargs key `genome`)。
        legacy: BacktestMetrics (= 既存判定経路)。
        canonical: CanonicalFiveResult or None (= helper 例外時 / disabled mode)。
        fold_index: per-fold 識別子 (= 0..n_fold-1)。 stage_label="B_fold" のとき必須、
            他 stage は None。 概念設計 § 4.7 / acceptance C4 / D5 で SSOT 化。

    Raises:
        ValueError: stage_label="B_fold" かつ fold_index is None
            (= acceptance D5、 識別子契約違反は fail-fast、 Round 2 [Warning] 反映)。

    解釈規約 (Codex Round 1 [Warning] 3 取込、 step 1.5 から継承):
    - dual-path log は **方向性監視** を目的とする (= 値一致や良し悪し判定ではない)
    - 解釈軸は (1) reason_code、 (2) gate_pass / canonical_invariants_feasible、
      (3) 主要指標の数値 diff (= 規模感の確認のみ)
    - 値の一致 / 不一致を理由に collider bias で判断しない
    """
    # 識別子契約 SSOT (= acceptance D5、 Round 2 [Warning] 反映)
    if stage_label == "B_fold" and fold_index is None:
        raise ValueError(
            "_log_canonical_dual_path(stage_label='B_fold') requires fold_index "
            "(= acceptance D5 / 識別子契約 SSOT)"
        )

    if canonical is None:
        log_kwargs: dict[str, object] = {
            "stage": stage_label,
            "genome": genome_name,
            "canonical_skipped": True,
        }
        if fold_index is not None:
            log_kwargs["fold"] = fold_index
        logger.info("stage_gate.canonical_five.dual_path", **log_kwargs)
        return

    log_kwargs = {
        "stage": stage_label,
        "genome": genome_name,
        "flags_source": "default_false",
        "fail_fast_flags_comparable": False,
        # legacy
        "legacy_total_pnl": str(legacy.total_pnl),
        "legacy_trade_count": legacy.trade_count,
        "legacy_max_dd_pct": str(legacy.max_drawdown_pct),
        "legacy_sharpe": str(legacy.sharpe) if legacy.sharpe is not None else None,
        # canonical
        "canonical_net_pnl": canonical.net_pnl_after_cost,
        "canonical_trade_count": canonical.trade_count,
        "canonical_max_dd": canonical.max_dd,
        "canonical_sr_worst_block": canonical.sr_session_worst_block_scale,
        "canonical_sr_worst_annual": canonical.sr_session_worst_annual_estimate,
        "canonical_wr_worst": canonical.session_block_win_rate_worst,
        "canonical_gate_pass": canonical.gate_pass,
        "canonical_gate_worst_gap": canonical.gate_worst_gap,
        "canonical_invariants_feasible": canonical.invariants.is_feasible,
        # diff
        "pnl_diff": float(legacy.total_pnl) - canonical.net_pnl_after_cost,
        "trade_count_diff": legacy.trade_count - canonical.trade_count,
        # 解釈規約 sentinel
        "interpretation_note": "direction_monitoring_only",
    }
    if fold_index is not None:
        log_kwargs["fold"] = fold_index
    logger.info("stage_gate.canonical_five.dual_path", **log_kwargs)
```

### 4.5 ルックアヘッドバイアスチェック
N/A (= 観測 only、 fitness 計算経路に影響なし)

### 4.6 パフォーマンスチェック
N/A (= log emit のみ、 算術なし)

### 4.7 テスト計画
- 既存 33 ケース全 PASS で後方互換確認 (= acceptance A4)
- 新規 test 1 件: `test_log_canonical_dual_path_rejects_b_fold_without_fold_index` (= ValueError raise 確認、 acceptance D5)

### 4.8 リスク
- 既存 caller (= Stage A / Stage B IS / Stage C base) の 3 箇所はすべて keyword 呼出で `fold_index` を渡さない → optional kwarg なので変更不要、 既存テスト全 PASS で確認

---

## 5. 施策 2: `evaluate_stage_b` per-fold dual-path 配線

### 5.1 変更箇所
- ファイル: `src/alpha_factory/stage_gate.py:892-948` (= per-fold OOS ループ内)

### 5.2 波及変更
- `AGENTS.md`: なし
- `.claude/skills/zenigame-fx-*/SKILL.md`: なし
- `config/alpha_factory/default.yaml`: なし
- `docs/alpha_factory/*.md`: 後続 step (= step 2) の dual-path log 解釈ガイドで `B_fold` を含める (= step 1.6 では docs 変更なし)

### 5.3 現行コード (抜粋)

```python
for i, (_train_bars, test_bars) in enumerate(folds):
    fold_sharpe: float | None = None
    fold_reason: FoldUnavailableReason | None = None
    try:
        if _aux_supports_with_aux:
            ...
        strategy = DslStrategy(genome, evaluator_for_fold)
        broker = MockBroker(instrument_meta=meta)
        res = run_backtest(test_bars, strategy, broker, backtest_config)
        bt = compute_metrics(res.trades, res.equity_curve, ...)
        fold_sharpe = (
            float(bt.trade_sharpe_raw) if bt.trade_sharpe_raw is not None else None
        )
        if fold_sharpe is None:
            fold_reason = _classify_fold_unavailable(...)
    except Exception as exc:
        logger.warning("stage_b.fold_failure", ...)
        fold_sharpe = None
        fold_reason = FoldUnavailableReason.FOLD_EXCEPTION
    if fold_sharpe is None:
        n_fold_unavailable += 1
        oos_sharpes_imputed.append(0.0)
        ...
```

### 5.4 変更後コード (= 物理隔離版、 概念設計 § 2.1 反映)

```python
for i, (_train_bars, test_bars) in enumerate(folds):
    fold_sharpe: float | None = None
    fold_reason: FoldUnavailableReason | None = None
    # dual-path 経路で参照する legacy 結果保持 (= 別 try に渡す、 物理隔離契約 D4)
    fold_bt: BacktestMetrics | None = None
    fold_trades: list[BrokerTrade] | None = None
    fold_equity: list[tuple[datetime, Decimal]] | None = None

    # === 既存 legacy fold 計算 (= fold_sharpe / fold_reason 確定、 完全不変) ===
    try:
        if _aux_supports_with_aux:
            aligned_for_fold = aux_bundle.align_to(test_bars)  # type: ignore[union-attr]
            evaluator_for_fold = primitive_evaluator.with_aux(  # type: ignore[attr-defined]
                **aligned_for_fold.as_evaluator_kwargs()
            )
        else:
            evaluator_for_fold = primitive_evaluator
        strategy = DslStrategy(genome, evaluator_for_fold)
        broker = MockBroker(instrument_meta=meta)
        res = run_backtest(test_bars, strategy, broker, backtest_config)
        bt = compute_metrics(
            res.trades,
            res.equity_curve,
            trade_count_min_for_sharpe=fold_min_trade_count,
        )
        fold_sharpe = (
            float(bt.trade_sharpe_raw)
            if bt.trade_sharpe_raw is not None
            else None
        )
        if fold_sharpe is None:
            fold_reason = _classify_fold_unavailable(
                trade_count=bt.trade_count,
                trade_count_min=fold_min_trade_count,
            )
        # dual-path 用に legacy 結果を保持
        fold_bt = bt
        fold_trades = res.trades
        fold_equity = res.equity_curve
    except Exception as exc:
        logger.warning(
            "stage_b.fold_failure",
            genome=genome.name,
            fold=i,
            error=str(exc),
            error_type=type(exc).__name__,
        )
        fold_sharpe = None
        fold_reason = FoldUnavailableReason.FOLD_EXCEPTION

    # === per-fold dual-path (= 別 try で完全分離、 acceptance D1-D5) ===
    # legacy fold 計算が成功した場合のみ dual-path 観測 (= 失敗時 skip、
    # 既存 fold_failure WARN で legacy 経路の状態は記録済)。
    # ここで fold_sharpe / fold_reason / reason_counts は絶対書き換えない (= D4)。
    if fold_bt is not None and fold_trades is not None and fold_equity is not None:
        try:
            canonical_sidecar_b_fold = _try_evaluate_canonical_five_safe(
                trades=fold_trades,
                equity_curve=fold_equity,
                bars=test_bars,
                live_criteria=stage_config.live_criteria,
                window_days=stage_config.wf_test_days,
                stage_label="B_fold",
                genome_name=genome.name,
                enabled=(stage_config.phase2_canonical_metrics_mode != "disabled"),
            )
            try:
                _log_canonical_dual_path(
                    stage_label="B_fold",
                    genome_name=genome.name,
                    legacy=fold_bt,
                    canonical=canonical_sidecar_b_fold,
                    fold_index=i,
                )
            except Exception as log_exc:
                logger.warning(
                    "stage_gate.canonical_five.log_failed",
                    stage="B_fold",
                    fold=i,
                    genome=genome.name,
                    error=str(log_exc),
                    error_type=type(log_exc).__name__,
                )
        except Exception as canonical_exc:
            # 想定外例外でも fold_sharpe / fold_reason は絶対変えない (= D1)
            logger.warning(
                "stage_gate.canonical_five.unexpected_failure",
                stage="B_fold",
                fold=i,
                genome=genome.name,
                error=str(canonical_exc),
                error_type=type(canonical_exc).__name__,
            )

    # === 既存 fold_sharpe / fold_reason ハンドリング (= 完全不変) ===
    if fold_sharpe is None:
        n_fold_unavailable += 1
        oos_sharpes_imputed.append(0.0)
        fold_was_unavailable.append(True)
        if fold_reason is None:
            fold_reason = FoldUnavailableReason.OTHER
        reason_counts[fold_reason] += 1
    else:
        oos_sharpes_imputed.append(fold_sharpe)
        fold_was_unavailable.append(False)
```

**重要設計判断** (= 概念設計 § 2.1 / acceptance D 反映):
- legacy fold 計算と dual-path 観測を **2 つの別 try ブロック** で物理分離 (= D1)
- legacy 計算成功時のみ dual-path 試行、 失敗時は既存 fold_failure WARN のみ (= D2)
- dual-path の二重 try (= helper 例外 + log 例外) で多層防御
- `fold_sharpe` / `fold_reason` / `reason_counts` は legacy 計算 try 内のみで決定、 dual-path で絶対変えない (= D4)

### 5.5 helper 入力契約 (= step 1.5 § 5.5 / 6.5 と同型、 再掲)

| 引数 | 契約 | step 1.6 per-fold で渡す値 |
|---|---|---|
| `trades` | UTC-aware exit_time | `fold_trades` (= run_backtest 出力) |
| `equity_curve` | 時系列順 / UTC-aware | `fold_equity` |
| `bars` | 評価窓全 bars / UTC-aware | `test_bars` (= 当該 fold の test 区間) |
| `live_criteria` | 必須キー 5 件 | `stage_config.live_criteria` |
| `window_days` | int (calendar day) | `stage_config.wf_test_days` (= default 20) |
| `stage_label` | str | `"B_fold"` |
| `genome_name` | str | `genome.name` |
| `enabled` | bool | `phase2_canonical_metrics_mode != "disabled"` |

### 5.6 ルックアヘッドバイアスチェック
N/A (= 観測 only、 fitness 計算経路に影響なし)

### 5.7 パフォーマンスチェック (= Round 1 [Suggestion] 反映で動的化)
- 計算量: per-fold で +1 回の canonical 5 metrics 計算 (= **n_fold × 1 計算追加**、 `n_fold` は `compute_max_folds` 式で動的決定)
- 追加 log 件数: **n_fold entries / genome / Stage B 評価**
- メモリ: BarEquitySeries (~20K bars × ~80 byte ≈ 1.6 MB/fold) + TradeRecord tuple (= <0.5 MB/fold)、 sequential 実行で n_fold 同時保持しない
- per-fold 追加 RSS: ~2 MB/fold (= 概算、 上限保証ではない、 低リスク仮説)
- 6 worker 並列: ~12 MB/全体 (= step 1.5 +50 MB より小さい、 n_fold に依存しない peak)

### 5.8 テスト計画
- 新規 test 9 ケース (= § 7 で詳述):
  1. regression 0 (= legacy payload 完全不変)
  2. log isolation (= helper raise 時 fold 判定不変)
  3. log helper isolation (= log raise 時 fold 判定不変)
  4. propagation (= disabled mode で skip)
  5. log content (= stage='B_fold' + fold=0..n の n_fold entries 出力)
  6. fold_index=None で B_fold は ValueError (= D5)
  7. golden 値固定 (= 1 ケース、 acceptance A5 同型、 ただし複数 fold で代表 1 fold 確認)
  8. 既存 caller (= Stage A / B_IS / C_base) の出力が変化しない後方互換 (= A4)

### 5.9 リスク
- per-fold dual-path 例外で legacy fold 経路を巻き込む → § 5.4 の物理隔離 + acceptance D1-D5 で完全防御
- log volume は **n_fold entries / genome 増加** (= 動的、 fixture 依存) → structlog filter で観測 only run / production run で出力レベル切替可能、 acceptance B3 で n_fold / bytes / WARN 率 を併記

---

## 6. 施策 3: per-fold dual-path test 追加

### 6.1 変更箇所
- ファイル: `tests/alpha_factory/test_stage_gate_canonical_dual_path.py` (= step 1 + step 1.5 で 33 ケース)

### 6.2 追加テストケース (= 9 ケース、 Round 1 [Warning] 反映で +1 ケース C5 専用)

#### 6.2.1 regression 0 (= acceptance A1, deep dict comparison)

```python
def test_stage_b_per_fold_canonical_dual_path_log_only_preserves_legacy_payload() -> None:
    """LOG_ONLY mode と disabled mode で Stage B の StageResult が完全一致
    (= per-fold dual-path 配線追加で oos_sharpes / median_oos_sharpe /
    positive_fold_ratio / unavailable_reason_counts / 他全 payload 完全不変)."""
    # ... (複数 fold 生成可能な fixture で evaluate_stage_b を呼出、 n_fold は make_wf_folds で動的取得)
```

#### 6.2.2 log isolation: canonical raise (= acceptance D1, D3、 Round 1 [Critical] 反映で B_fold 限定 raise)

```python
def test_stage_b_per_fold_canonical_log_isolation_when_canonical_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`_try_evaluate_canonical_five_safe` が **stage_label='B_fold' のときだけ** raise
    する wrapper で置換し、 per-fold legacy 判定が完全不変であることを確認。

    Round 1 [Critical] 反映: helper を無条件 raise させると同じ helper が B_IS でも
    呼ばれ、 is_full_* が変わって disabled 比較が崩れる。 monkeypatch を
    stage_label 限定 raise の wrapper に変更し、 B_IS 呼出は元 helper に透過させる。

    比較: passed / reason_codes / metrics["payload"] / n_bars (= wall_time_seconds 除外)
    で disabled mode と deep equality。"""
    from src.alpha_factory import stage_gate as sg

    original_helper = sg._try_evaluate_canonical_five_safe

    def _conditional_raise(**kwargs):  # type: ignore[no-untyped-def]
        if kwargs.get("stage_label") == "B_fold":
            raise RuntimeError("simulated B_fold canonical failure")
        return original_helper(**kwargs)

    monkeypatch.setattr(sg, "_try_evaluate_canonical_five_safe", _conditional_raise)
    # ... (evaluate_stage_b 呼出 + disabled mode と deep comparison)
```

#### 6.2.3 log isolation: log helper raise (= acceptance D1, D2)

```python
def test_stage_b_per_fold_canonical_log_helper_isolation_when_log_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """_log_canonical_dual_path が raise しても per-fold legacy 判定は完全不変。"""
```

#### 6.2.4 propagation: disabled mode

```python
def test_stage_b_per_fold_canonical_disabled_mode_skips_calculation() -> None:
    """phase2_canonical_metrics_mode='disabled' で per-fold canonical 計算 skip。"""
```

#### 6.2.5 log content: n_fold 別 entry 出力 (= acceptance C1, C4、 Round 1 [Critical] 反映)

```python
def test_stage_b_per_fold_dual_path_emits_one_entry_per_fold(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """各 fold で dual-path log entry が `stage='B_fold'` + `fold=<0..n_fold-1>` で出力。
    (stage, genome, fold) で一意特定可能 (= 識別子契約 SSOT)。

    Round 1 [Critical] 反映: n_fold は `make_wf_folds(...)` 式で動的決定なので、
    fixture から n_fold を取得して照合する (= 5 fold hard-code しない)。"""
    from src.alpha_factory.walk_forward import make_wf_folds
    bars = _make_continuous_bars(20, bars_per_day=4)
    cfg = _stage_b_small_cfg()
    n_fold_expected = len(make_wf_folds(
        bars,
        train_days=cfg.wf_train_days,
        test_days=cfg.wf_test_days,
        step_days=cfg.wf_step_days,
        embargo_days=cfg.wf_embargo_days,
    ))
    # ... (evaluate_stage_b 呼出 + capsys で stage='B_fold' 行を全件取得)
    # 行数 == n_fold_expected を assert
    # 各行に fold=0, 1, ..., n_fold-1 が含まれることを assert (set 比較)
```

#### 6.2.6 fold_index=None で B_fold は ValueError (= acceptance D5)

```python
def test_log_canonical_dual_path_rejects_b_fold_without_fold_index() -> None:
    """_log_canonical_dual_path(stage_label='B_fold', fold_index=None) は ValueError raise
    (= 識別子契約 fail-fast、 Round 2 [Warning] 反映)."""
    with pytest.raises(ValueError, match="fold_index"):
        _log_canonical_dual_path(
            stage_label="B_fold",
            genome_name="g_test",
            legacy=_dummy_legacy(),
            canonical=None,
            fold_index=None,
        )
```

#### 6.2.7 golden 値固定 (= acceptance A5 同型、 1 fold 代表)

```python
def test_stage_b_per_fold_canonical_golden_first_fold() -> None:
    """fixed seed × fixed fixture で 1 fold (= 代表) の canonical sidecar が
    fixture-locked 期待値と一致 (= net_pnl_after_cost / max_dd /
    sr_session_worst_block_scale / session_block_win_rate_worst / gate_pass / etc)。

    複数 fold での golden は overengineering で却下 (= 概念設計 scope)。"""
```

#### 6.2.8 後方互換: 既存 33 ケース全 PASS (= acceptance A4)

これは追加 test ではなく既存 test の継続実行で確認。 § 4 の `_log_canonical_dual_path` 変更が optional kwarg のみで既存 caller の動作を変えないことを保証。

#### 6.2.9 disabled mode で B_fold は出るが fold 必須 (= acceptance C5、 Round 1 [Warning] 反映)

```python
def test_stage_b_per_fold_canonical_skipped_path_includes_fold_kwargs(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """phase2_canonical_metrics_mode='disabled' (= canonical_skipped=True path) でも、
    `stage='B_fold'` log entry が出る場合は **すべての行に `fold=` kwargs key が含まれる**
    ことを確認 (= acceptance C5、 Round 1 [Warning] 反映)。

    注: disabled mode では _try_evaluate_canonical_five_safe が None を返し、
    _log_canonical_dual_path の canonical_skipped=True 分岐に入る。
    その分岐でも fold kwarg は必須出力でなければならない (= 識別子契約 SSOT)。"""
    # ... (disabled cfg で evaluate_stage_b、 stage='B_fold' 全行に fold key が含まれる)
```

### 6.3 fixture
- `bars_b_test_window`: 複数 fold 生成可能な bars (= 既存 `_make_continuous_bars(20, bars_per_day=4)` + `_stage_b_small_cfg(wf_train_days=3, wf_test_days=2, wf_step_days=2)` で複数 fold 生成、 step 1.5 fixture 流用)。 n_fold は `make_wf_folds(...)` で動的取得 (= ~8 fold 想定だが test では値に依存しない)

### 6.4 既存 33 ケースへの影響
- `_log_canonical_dual_path` のシグネチャ変更は **optional kwarg 追加のみ** (= 後方互換)
- 既存 Stage A / Stage B IS / Stage C base の caller は `fold_index` を渡さない (= None default で動作)
- 既存 33 ケースは全 PASS する想定 (= acceptance A4 で確認)

---

## 7. acceptance criterion (= 概念設計 § 5.3 反映)

### A. 判定結果回帰 0 (必須、 deep dict comparison)
- [A1] Stage B の `StageResult.passed` / `reason_codes` / `metrics["payload"]` が canonical 配線追加で 1 byte も変化しない (= phase2_canonical_metrics_mode `log_only` vs `disabled` で完全一致、 fixed seed × fixed fixture)
- [A2] archive Parquet schema 完全不変 (= canonical sidecar 非添付)
- [A3] GA fitness 不変
- [A4] Stage A / Stage B IS / Stage C base の dual-path log は step 1.5 と完全一致 (= `_log_canonical_dual_path` への optional kwarg 追加が既存 caller の出力を変えない、 既存 33 ケース全 PASS で確認)
- [A5] Stage B per-fold canonical sidecar (= 1 fold 代表) が fixture-locked 期待値と一致 (= deterministic 性確認)

### B. 運用回帰検証
- [B1] dual-path log が Stage B の各 fold (= n_fold 個、 動的) で crash なく出力
- [B2] smoke 5 Run で peak RSS が worker 3 GB budget 内 (= 概算 +~12 MB / worker、 上限保証ではなく低リスク仮説)
- [B3] smoke 5 Run の所要時間が step 1.5 比 ±20% 以内 + dual-path log の bytes / WARN 率 + **`n_fold` per genome** を計測 (= Round 1 [Suggestion] 反映)
- [B4] dual-path log が legacy log (= stage_b.fold_failure) と独立出力

### C. legacy 比較可能性 + 識別子契約
- [C1] dual-path log の `stage` field が `"B_fold"` で正しく区別可能、 `fold` kwargs key (= 0..n_fold-1) で fold 識別可能
- [C2] `legacy_*` / `canonical_*` field が同 log entry に共存
- [C3] `interpretation_note="direction_monitoring_only"` が継承
- [C4] **識別子契約 SSOT**: `B_fold` log entry は `(stage, genome, fold)` 3 つの kwargs key で一意特定可能。 `fold` 欠落は bug 扱い
- [C5] `canonical_skipped=True` path でも `fold` kwargs key は必須

### D. 例外隔離契約 (= 物理隔離保証)
- [D1] dual-path 経路で例外発生しても `fold_sharpe` / `fold_reason` / `oos_sharpes_imputed` / `n_fold_unavailable` / `reason_counts` 完全不変
- [D2] dual-path 経路の例外は `stage_gate.canonical_five.unexpected_failure` **または** `stage_gate.canonical_five.log_failed` の WARN log のみ (= 二重 try で多層、 Round 1 [Warning] 反映で文言更新)、 既存 `stage_b.fold_failure` reason 経路は touch しない
- [D3] monkeypatch で raise しても StageResult が disabled mode と一致 (= `passed` / `reason_codes` / `metrics["payload"]` / `n_bars` の deep comparison、 `wall_time_seconds` 除外、 Round 2 [Warning] 反映)
- [D4] dual-path ブロック内では `fold_sharpe` / `fold_reason` / `reason_counts` を write しない (= 物理隔離契約)
- [D5] `_log_canonical_dual_path(stage_label="B_fold", fold_index=None)` は `ValueError` raise (= 識別子契約 fail-fast)

---

## 8. 実装モード

| 項目 | 内容 |
|---|---|
| 推奨モード | **incremental** (= worktree todo/T084 で 1 commit、 main マージ no-ff) |
| 判断根拠 | step 1.5 と同じ pattern、 adapter / helper 凍結再利用、 stage_gate.py のみ拡張、 計算量 +n_fold calc/genome (= 動的)、 archive Parquet schema 不変、 既存 33 ケース PASS で後方互換保証 |
| 競合リスク | step 1.5 の続き、 他 worktree (= todo/T081) と独立、 競合なし |
| 想定実装時間 | **短〜中** (= 1 commit、 約 50 行追加 + 9 ケース test) |

### 8.1 commit 戦略

```
worktree todo/T084:
  commit: feat(B step 1.6): Stage B per-fold dual-path 配線追加 + _log_canonical_dual_path に fold_index optional kwarg

main:
  no-ff merge → main に 1 commit を保持
```

step 1.5 は 2 commit 分離 (rename refactor + behavioral wiring) だったが、 step 1.6 は **1 commit で十分** (= rename なし、 behavioral wiring のみ)。

---

## 9. 確認事項 (= 実装前)

- [ ] 既存 33 ケースを worktree で run して全 PASS 確認
- [ ] worktree todo/T084 を main から作成
- [ ] commit 後、 既存 33 ケース + 新規 9 ケース = 42 ケース全 PASS 確認 (= acceptance A1, A4, A5, C1-C5, D1-D5)
- [ ] ruff / mypy clean

---

## 10. 参考資料

- 概念設計 (Round 2 APPROVED): `devnotes/20260503-2049-B-phase2-step1.6-stage-b-per-fold-dual-path/conceptual-design.md`
- step 1.5 詳細設計: `devnotes/20260503-1446-B-phase2-step1.5-stage-bc-dual-path/detailed-design.md`
- step 1.5 完了 handoff: `devnotes/20260503-1652-B-step1.5-complete-handoff/handoff.md`
- step 1.5 main commit: `6276d58 Merge branch 'todo/T083'`
- canonical_adapter.py (凍結): `src/alpha_factory/canonical_adapter.py`
- stage_gate.py (拡張対象): `src/alpha_factory/stage_gate.py:892-948` (per-fold OOS) + L169-225 (`_log_canonical_dual_path`)
- 既存 test: `tests/alpha_factory/test_stage_gate_canonical_dual_path.py` (= 33 ケース、 step 1.6 で +9 ケース追加 = 計 42 ケース)
- walk_forward.py: `src/alpha_factory/walk_forward.py:66 compute_max_folds` (= n_fold 動的決定式)
