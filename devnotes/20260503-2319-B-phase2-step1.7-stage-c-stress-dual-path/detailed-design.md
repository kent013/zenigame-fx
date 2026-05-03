# 詳細設計: B Phase 2 切替コミット step 1.7 — Stage C stress dual-path 拡張

**作成日時**: 2026-05-03 23:42 JST (Round 2 改訂: 2026-05-03 23:55 JST、 表記整合 patch: 2026-05-03 24:05 JST)
**status**: **詳細設計 Round 2 APPROVED** (= Codex 詳細設計 Round 1 CHANGES_REQUESTED 反映済、 Round 2 で APPROVED 判定)
**概念設計**: `devnotes/20260503-2319-B-phase2-step1.7-stage-c-stress-dual-path/conceptual-design.md` (Codex Round 2 APPROVED)

---

## 0. Round 1 → Round 2 改訂対応

| Round 1 指摘 | 対応 |
|---|---|
| 施策 3 [Critical] D2 反証 test 不足 (= test #2/#3 で `stage_c.stress_failure` 非出力 assert なし) | test #2 / #3 に `capsys` を加え、 `"stage_c.stress_failure"` が combined log に **含まれない** ことを明示 assert (= D2 直接反証) |
| 施策 3 [Warning] `run_backtest` 2 回目 raise 方式が脆い | call count 依存を廃止、 **`max_spread_bps` 値で分岐** (= base 値と stress 値で区別、 stress_config.max_spread_bps == new_max のとき raise) |
| 施策 3 [Suggestion] 概念設計の golden 1 ケース言及と SSOT 整合 | golden 1 ケースを詳細設計 § 6.2 に追加 (= test 8 ケース化、 acceptance A5 対応) |

---

## 1. 使命・制約 (絶対遵守)

### zenigame-fx Alpha Factory 使命
live_criteria 全指標同時充足 + (ii-lite) 通過で使命達成。 絶対制約: イントラデイ / ロング・ショート両方向 / スワップ・スプレッド反映。

### 禁止事項
1. A・B・C 評価期間延長
2. 数値見せかけ改善
3. GA ハック
4. live_criteria 緩和
5. **過度な複雑化** ← 本 step で特に重要
6. 取引回数削減
7. オーバーナイト保有前提
8. ゲノム archive スキーマ変更時の値伝搬漏れ

### コーディングルール
- バグ修正はテストファースト
- 全施策にテスト必須
- テスト命名: 振る舞い説明的、 汎用的
- テスト配置: 対象モジュール対応のテストファイル
- uv 必須: `uv run pytest tests/alpha_factory/`
- ruff / mypy 通過

---

## 2. 概念設計リファレンス

`devnotes/20260503-2319-B-phase2-step1.7-stage-c-stress-dual-path/conceptual-design.md` (Round 2 APPROVED)

主要決定:
- **scope**: Stage C stress 区画の dual-path canonical metric 観測追加のみ
- **descriptive observation only**: stress hard gate の shadow ではない、 cross-stage diff は dual-path log entry に含まれない (= 後段 join 必要)
- **adapter / helper 凍結**: step 1 / 1.5 / 1.6 で凍結、 改変なし
- **物理隔離**: stress backtest 完了後の別 try ブロック、 stress_payload / reasons に絶対干渉しない
- **skip 整合**: `max_spread_bps is None` / stress 例外時は dual_path / canonical_five.skipped event 両者 emit されない
- **disabled mode**: stress 成功時のみ canonical_skipped=True の dual_path event emit (= step 1.6 B_fold と同型)
- **acceptance**: A (判定結果回帰 0) + B (運用回帰検証) + C (legacy 比較可能性 + 識別子契約) + D (例外隔離契約)

---

## 3. 施策一覧

| # | 施策名 | 変更ファイル | 優先度 |
|---|---|---|---|
| 1 | `_log_canonical_dual_path` docstring に C_stress 追記 (= SSOT 整合) | src/alpha_factory/stage_gate.py | High |
| 2 | `evaluate_stage_c` stress 区画 dual-path 配線追加 (= 別 try で物理分離) | src/alpha_factory/stage_gate.py | High |
| 3 | C_stress dual-path test 追加 (= 8 ケース) + 既存 43 ケース後方互換確認 | tests/alpha_factory/test_stage_gate_canonical_dual_path.py | High |

---

## 4. 施策 1: `_log_canonical_dual_path` docstring に C_stress 追記

### 4.1 変更箇所
- ファイル: `src/alpha_factory/stage_gate.py:170-235` (= helper docstring)

### 4.2 波及変更
- なし (= docstring のみ、 動作不変)

### 4.3 現行 (step 1.6 後)

```python
def _log_canonical_dual_path(
    *,
    stage_label: str,
    genome_name: str,
    legacy: BacktestMetrics,
    canonical: CanonicalFiveResult | None,
    fold_index: int | None = None,
) -> None:
    """dual-path 結果 (legacy + canonical) を構造化 log に出力.

    Args:
        stage_label: § 4.7 ログ命名規約 SSOT (A / B_IS / B_fold / C_base / C_cross_pair)。
        ...
        fold_index: per-fold 識別子 (= 0..n_fold-1)。 stage_label="B_fold" のとき必須、
            他 stage は None。 step 1.6 detailed-design § 4.7 / acceptance C4 / D5
            で SSOT 化 (= B_fold log entry は (stage, genome, fold) で一意特定可能)。
    ...
    """
```

### 4.4 変更後

```python
def _log_canonical_dual_path(
    *,
    stage_label: str,
    genome_name: str,
    legacy: BacktestMetrics,
    canonical: CanonicalFiveResult | None,
    fold_index: int | None = None,
) -> None:
    """dual-path 結果 (legacy + canonical) を構造化 log に出力.

    Args:
        stage_label: § 4.7 ログ命名規約 SSOT
            (A / B_IS / B_fold / C_base / C_stress / C_cross_pair)。
            注: C_stress は step 1.7 で追加 (= Stage C spread stress backtest)。
        ...
        fold_index: per-fold 識別子 (= 0..n_fold-1)。 stage_label="B_fold" のとき必須、
            他 stage (= A / B_IS / C_base / C_stress / C_cross_pair) は None。
            step 1.6 detailed-design § 4.7 / acceptance C4 / D5 で SSOT 化。
    ...
    """
```

### 4.5 ルックアヘッドバイアスチェック
N/A (= docstring のみ)

### 4.6 パフォーマンスチェック
N/A

### 4.7 テスト計画
- 既存 43 ケース全 PASS で動作不変確認
- 新規 test 追加なし (= docstring のみ)

### 4.8 リスク
- なし (docstring のみ)

---

## 5. 施策 2: `evaluate_stage_c` stress 区画 dual-path 配線

### 5.1 変更箇所
- ファイル: `src/alpha_factory/stage_gate.py:1385-1442` (= stress 区画)

### 5.2 波及変更
- `AGENTS.md`: なし
- `.claude/skills/zenigame-fx-*/SKILL.md`: なし
- `config/alpha_factory/default.yaml`: なし
- `docs/alpha_factory/*.md`: 後続 step (= step 2) で C_stress を含む log 解釈ガイド追加予定。 step 1.7 では docs 変更なし

### 5.3 現行コード

```python
# src/alpha_factory/stage_gate.py:1385-1442 (stress 区画)
stress_payload: dict[str, object] = {
    "skipped": False,
    "sharpe": None,
    "total_pnl": 0.0,
    "max_drawdown_frac": 0.0,
    "trade_count": 0,
    "sharpe_degradation": None,
    "pnl_degradation": 0.0,
}
if backtest_config.max_spread_bps is None:
    stress_payload["skipped"] = True
    reasons.append("spread_stress_skipped")
else:
    base_max = Decimal(str(backtest_config.max_spread_bps))
    multiplier_dec = Decimal(str(stage_config.spread_stress_multiplier))
    new_max = base_max * multiplier_dec
    stress_config = replace(backtest_config, max_spread_bps=new_max)
    try:
        strategy = DslStrategy(genome, primitive_evaluator)
        broker = MockBroker(instrument_meta=meta)
        res = run_backtest(bars_holdout, strategy, broker, stress_config)
        bt = compute_metrics(
            res.trades, res.equity_curve,
            trade_count_min_for_sharpe=stage_config.trade_count_min_for_sharpe,
        )
        s_sharpe = (
            float(bt.trade_sharpe_raw) if bt.trade_sharpe_raw is not None else None
        )
        s_total_pnl = float(bt.total_pnl)
        s_trade_count = bt.trade_count
        stress_payload["sharpe"] = s_sharpe
        stress_payload["total_pnl"] = s_total_pnl
        stress_payload["max_drawdown_frac"] = float(bt.max_drawdown_pct) / 100.0
        stress_payload["trade_count"] = s_trade_count
        if base_sharpe is not None and s_sharpe is not None:
            stress_payload["sharpe_degradation"] = base_sharpe - s_sharpe
        stress_payload["pnl_degradation"] = base_total_pnl - s_total_pnl
        if s_trade_count < int(lc["trade_count_min"]):
            reasons.append("spread_stress.trade_count<min")
        if s_total_pnl < float(stage_config.spread_stress_min_total_pnl):
            reasons.append("spread_stress.total_pnl<min")
        if s_sharpe is None or s_sharpe < float(stage_config.spread_stress_min_sharpe):
            reasons.append("spread_stress.sharpe<min")
    except Exception as exc:
        logger.warning("stage_c.stress_failure", genome=genome.name, error=str(exc))
        stress_payload["skipped"] = True
        reasons.append("spread_stress_skipped")
```

### 5.4 変更後コード (= 物理隔離版、 概念設計 § 2.1 反映)

```python
stress_payload: dict[str, object] = {
    "skipped": False,
    "sharpe": None,
    "total_pnl": 0.0,
    "max_drawdown_frac": 0.0,
    "trade_count": 0,
    "sharpe_degradation": None,
    "pnl_degradation": 0.0,
}
if backtest_config.max_spread_bps is None:
    stress_payload["skipped"] = True
    reasons.append("spread_stress_skipped")
    # step 1.7: legacy stress skip → dual-path も skip (= 何も emit しない)
else:
    base_max = Decimal(str(backtest_config.max_spread_bps))
    multiplier_dec = Decimal(str(stage_config.spread_stress_multiplier))
    new_max = base_max * multiplier_dec
    stress_config = replace(backtest_config, max_spread_bps=new_max)

    # step 1.7: dual-path 経路用に legacy 結果を保持 (= 別 try に渡す、 物理隔離 D4)
    stress_bt: BacktestMetrics | None = None
    stress_trades: list[BrokerTrade] | None = None
    stress_equity: list[tuple[datetime, Decimal]] | None = None

    # === 既存 legacy stress 計算 (= stress_payload / reasons 確定、 完全不変) ===
    try:
        strategy = DslStrategy(genome, primitive_evaluator)
        broker = MockBroker(instrument_meta=meta)
        res = run_backtest(bars_holdout, strategy, broker, stress_config)
        bt = compute_metrics(
            res.trades, res.equity_curve,
            trade_count_min_for_sharpe=stage_config.trade_count_min_for_sharpe,
        )
        s_sharpe = (
            float(bt.trade_sharpe_raw) if bt.trade_sharpe_raw is not None else None
        )
        s_total_pnl = float(bt.total_pnl)
        s_trade_count = bt.trade_count
        stress_payload["sharpe"] = s_sharpe
        stress_payload["total_pnl"] = s_total_pnl
        stress_payload["max_drawdown_frac"] = float(bt.max_drawdown_pct) / 100.0
        stress_payload["trade_count"] = s_trade_count
        if base_sharpe is not None and s_sharpe is not None:
            stress_payload["sharpe_degradation"] = base_sharpe - s_sharpe
        stress_payload["pnl_degradation"] = base_total_pnl - s_total_pnl
        if s_trade_count < int(lc["trade_count_min"]):
            reasons.append("spread_stress.trade_count<min")
        if s_total_pnl < float(stage_config.spread_stress_min_total_pnl):
            reasons.append("spread_stress.total_pnl<min")
        if s_sharpe is None or s_sharpe < float(stage_config.spread_stress_min_sharpe):
            reasons.append("spread_stress.sharpe<min")
        # step 1.7: dual-path 用に legacy 結果を保持
        stress_bt = bt
        stress_trades = res.trades
        stress_equity = res.equity_curve
    except Exception as exc:
        logger.warning("stage_c.stress_failure", genome=genome.name, error=str(exc))
        stress_payload["skipped"] = True
        reasons.append("spread_stress_skipped")
        # step 1.7: stress 例外 → stress_bt は None のまま、 dual-path も skip

    # === step 1.7: stress dual-path (= 別 try で物理隔離、 acceptance D1-D4) ===
    # legacy stress 計算成功時のみ dual-path 観測 (= 失敗時 skip、
    # 既存 stress_failure WARN log で legacy 経路状態は記録済)。
    # stress_payload / reasons は dual-path で絶対書き換えない (= D4)。
    if (
        stress_bt is not None
        and stress_trades is not None
        and stress_equity is not None
    ):
        try:
            canonical_sidecar_c_stress = _try_evaluate_canonical_five_safe(
                trades=stress_trades,
                equity_curve=stress_equity,
                bars=bars_holdout,
                live_criteria=stage_config.live_criteria,
                window_days=stage_config.stage_c_holdout_days,
                stage_label="C_stress",
                genome_name=genome.name,
                enabled=(
                    stage_config.phase2_canonical_metrics_mode != "disabled"
                ),
            )
            try:
                _log_canonical_dual_path(
                    stage_label="C_stress",
                    genome_name=genome.name,
                    legacy=stress_bt,
                    canonical=canonical_sidecar_c_stress,
                    # fold_index=None default (= C_stress は fold key 不在)
                )
            except Exception as log_exc:
                logger.warning(
                    "stage_gate.canonical_five.log_failed",
                    stage="C_stress",
                    genome=genome.name,
                    error=str(log_exc),
                    error_type=type(log_exc).__name__,
                )
        except Exception as canonical_exc:
            # 想定外例外でも stress_payload / reasons は絶対変えない (= D1)
            logger.warning(
                "stage_gate.canonical_five.unexpected_failure",
                stage="C_stress",
                genome=genome.name,
                error=str(canonical_exc),
                error_type=type(canonical_exc).__name__,
            )
```

**重要設計判断** (= 概念設計 § 2.1 / acceptance D 反映):
- legacy stress 計算と dual-path 観測を **2 つの別 try ブロック** で物理分離 (= D4)
- legacy 計算成功時のみ dual-path 試行 (= `stress_bt is not None` ガード、 D1)
- dual-path の二重 try (= helper 例外 + log 例外) で多層防御 (= D2)
- `stress_payload` / `reasons` は legacy 計算 try 内のみで決定、 dual-path で絶対変えない (= D4)
- `max_spread_bps is None` ブランチでは dual-path 配線が呼ばれない (= 自動 skip)
- stress 例外時 (= `stress_bt = None` のまま) は dual-path 配線条件で skip (= 自動 skip)

### 5.5 helper 入力契約 (= step 1.5 § 5.5 / 1.6 § 5.5 と同型)

| 引数 | 契約 | step 1.7 C_stress で渡す値 |
|---|---|---|
| `trades` | UTC-aware exit_time | `stress_trades` (= stress backtest 出力) |
| `equity_curve` | 時系列順 / UTC-aware | `stress_equity` |
| `bars` | 評価窓全 bars / UTC-aware | `bars_holdout` (= 60d、 base と同じ holdout) |
| `live_criteria` | 必須キー 5 件 | `stage_config.live_criteria` |
| `window_days` | int (calendar day) | `stage_config.stage_c_holdout_days` (= 60、 base と同) |
| `stage_label` | str | `"C_stress"` |
| `genome_name` | str | `genome.name` |
| `enabled` | bool | `phase2_canonical_metrics_mode != "disabled"` |

### 5.6 ルックアヘッドバイアスチェック
N/A (= 観測 only、 fitness 計算経路に影響なし)

### 5.7 パフォーマンスチェック
- 計算量: Stage C で +1 回の canonical 5 metrics 計算 (= 数百 trade × O(N) 集約)
- メモリ: BarEquitySeries (= 60d holdout、 ~5-7 MB) + TradeRecord tuple (= <0.5 MB)、 step 1.5 Stage C base と同等規模
- per-stress 追加 RSS: base と同等オーダーで 3GB/worker を大きく下回る見込み (= 上限保証ではなく低リスク仮説)
- 6 worker 並列 worst case: 概算 ~36 MB / 全体 (= step 1.5 で同等規模を観測済)
- 実測検証: smoke 5 Run の `/usr/bin/time -l` (= acceptance B2)

### 5.8 テスト計画
- 新規 test 8 ケース (= § 6 で詳述)
- 既存 43 ケース全 PASS で後方互換確認 (= acceptance A4)

### 5.9 リスク
- stress 例外時に bt が無効値で dual-path に渡って adapter ValueError → outer try except で `stress_bt = None` のまま、 ガードで skip + helper 内部 try でも catch (= 多層)
- `max_spread_bps is None` のときに dual-path 行が誤って emit → `else` ブランチ内 + ガードで二重防御
- log volume 増加 (= 1 entry/genome) → structlog filter で運用切替可能

---

## 6. 施策 3: C_stress dual-path test 追加

### 6.1 変更箇所
- ファイル: `tests/alpha_factory/test_stage_gate_canonical_dual_path.py` (= 43 ケース、 step 1.7 で +8 ケース)

### 6.2 追加テストケース総数 (= 8 ケース、 Round 1 [Suggestion] 反映で +1 golden)

| # | テスト名 | 検証内容 | acceptance 対応 |
|---|---|---|---|
| 1 | `test_stage_c_stress_canonical_dual_path_log_only_preserves_legacy_payload` | legacy stress_payload + reasons 完全不変 | A1 |
| 2 | `test_stage_c_stress_canonical_log_isolation_when_canonical_raises` | helper raise 時 stress_payload / reasons 不変 (= deep equality) + `stage_c.stress_failure` 非出力 (= D2 反証) | D1, D2, D3 |
| 3 | `test_stage_c_stress_canonical_log_helper_isolation_when_log_raises` | log helper raise 時 stress_payload / reasons 不変 + `stage_c.stress_failure` 非出力 (= D2 反証) | D1, D2 |
| 4 | `test_stage_c_stress_canonical_disabled_mode_emits_skipped_log` | disabled mode で stress 成功時に canonical_skipped=True dual_path 1 entry emit、 fold key 不在 | C5 (disabled 経路) |
| 5 | `test_stage_c_stress_canonical_succeeds_for_60d_holdout` | log content 検証 (= stage='C_stress' / genome / interpretation_note / canonical_* / legacy_*、 fold key 不在) | B1, C1, C2, C3, C4 |
| 6 | `test_stage_c_stress_canonical_skipped_when_max_spread_bps_is_none` | max_spread_bps is None で C_stress event (= dual_path + canonical_five.skipped 両者) 0 件 | C5 |
| 7 | `test_stage_c_stress_canonical_skipped_when_stress_backtest_raises` | stress backtest 例外時 (= stage_c.stress_failure WARN) C_stress event 0 件、 `max_spread_bps` 値で stress 経路同定 (= call count 依存廃止) | C5 |
| 8 | `test_stage_c_stress_canonical_golden_first_evaluation_succeeds` | fixed seed × fixed fixture で C_stress canonical の主要 field が deterministic な期待値と一致 (= deterministic 性確認) | A5 |

### 6.3 主要 test コード (要点)

#### 6.2.1 regression 0 (= acceptance A1)

```python
def test_stage_c_stress_canonical_dual_path_log_only_preserves_legacy_payload() -> None:
    """LOG_ONLY mode と disabled mode で Stage C の StageResult 全体が完全一致
    (= regression 0、 acceptance A1。 stress dual-path 配線追加で
    stress_payload / reasons / cross_pair / live_criteria_pass 全件不変)."""
    bars = _make_continuous_bars(2, bars_per_day=4)
    ev = ConstantPrimitiveEvaluator(value=0.0)
    cfg = _backtest_config()
    log_only_cfg = StageGateConfig(phase2_canonical_metrics_mode="log_only")
    disabled_cfg = StageGateConfig(phase2_canonical_metrics_mode="disabled")
    res_log = evaluate_stage_c(
        _one_clause_genome("g_c_stress_legacy_unchanged"), bars, usd_jpy_meta(),
        cfg, ev, log_only_cfg,
    )
    res_dis = evaluate_stage_c(
        _one_clause_genome("g_c_stress_legacy_unchanged"), bars, usd_jpy_meta(),
        cfg, ev, disabled_cfg,
    )
    assert res_log.passed == res_dis.passed
    assert res_log.reason_codes == res_dis.reason_codes
    payload_log = dict(res_log.metrics["payload"])
    payload_dis = dict(res_dis.metrics["payload"])
    assert set(payload_log.keys()) == set(payload_dis.keys())
    for key in payload_log:
        assert payload_log[key] == payload_dis[key]
```

#### 6.2.2 log isolation: canonical raise (= acceptance D1, D2, D3、 Round 1 [Critical] 反映で D2 反証強化)

```python
def test_stage_c_stress_canonical_log_isolation_when_canonical_raises(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """`_try_evaluate_canonical_five_safe` が `stage_label='C_stress'` のときだけ
    raise しても stress_payload / reasons は完全不変、 かつ `stage_c.stress_failure`
    が **非出力** であることを直接 assert (= D2 反証、 Round 1 [Critical] 反映)。

    monkeypatch wrapper で C_stress 限定 raise (= C_base 透過)。"""
    from src.alpha_factory import stage_gate as sg

    original_helper = sg._try_evaluate_canonical_five_safe

    def _conditional_raise(**kwargs):  # type: ignore[no-untyped-def]
        if kwargs.get("stage_label") == "C_stress":
            raise RuntimeError("simulated C_stress canonical failure")
        return original_helper(**kwargs)

    monkeypatch.setattr(sg, "_try_evaluate_canonical_five_safe", _conditional_raise)
    bars = _make_continuous_bars(2, bars_per_day=4)
    ev = ConstantPrimitiveEvaluator(value=0.0)
    res_with_raise = evaluate_stage_c(
        _one_clause_genome("g_c_stress_canonical_fail"), bars, usd_jpy_meta(),
        _backtest_config(), ev, StageGateConfig(),
    )
    captured_with_raise = capsys.readouterr()
    monkeypatch.setattr(sg, "_try_evaluate_canonical_five_safe", original_helper)
    res_disabled = evaluate_stage_c(
        _one_clause_genome("g_c_stress_canonical_fail"), bars, usd_jpy_meta(),
        _backtest_config(), ev,
        StageGateConfig(phase2_canonical_metrics_mode="disabled"),
    )
    # passed / reason_codes / payload / n_bars 完全一致 (= wall_time_seconds 除外、 D1/D3)
    assert res_with_raise.passed == res_disabled.passed
    assert res_with_raise.reason_codes == res_disabled.reason_codes
    assert res_with_raise.metrics["n_bars"] == res_disabled.metrics["n_bars"]
    payload_raise = dict(res_with_raise.metrics["payload"])
    payload_dis = dict(res_disabled.metrics["payload"])
    assert set(payload_raise.keys()) == set(payload_dis.keys())
    for key in payload_raise:
        assert payload_raise[key] == payload_dis[key]
    # D2 反証: dual-path 例外で stage_c.stress_failure が誤って emit されないこと
    combined = captured_with_raise.out + captured_with_raise.err
    assert "stage_c.stress_failure" not in combined, (
        "D2 violation: dual-path canonical raise must not trigger stage_c.stress_failure"
    )
    # canonical 経路は unexpected_failure or log_failed の WARN のみ
    assert (
        "stage_gate.canonical_five.unexpected_failure" in combined
        or "stage_gate.canonical_five.log_failed" in combined
    )
```

#### 6.2.4 disabled mode で canonical_skipped event emit (= C5 disabled path)

```python
def test_stage_c_stress_canonical_disabled_mode_emits_skipped_log(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """phase2_canonical_metrics_mode='disabled' で stress 成功時に
    `stage='C_stress'` + `canonical_skipped=True` の dual_path log entry が
    1 entry / genome emit され、 `fold=` kwarg は含まれない
    (= C5 disabled path、 step 1.6 B_fold と同型)."""
    bars = _make_continuous_bars(2, bars_per_day=4)
    ev = ConstantPrimitiveEvaluator(value=0.0)
    cfg = _backtest_config()
    res = evaluate_stage_c(
        _one_clause_genome("g_c_stress_disabled"), bars, usd_jpy_meta(), cfg, ev,
        StageGateConfig(phase2_canonical_metrics_mode="disabled"),
    )
    assert res.stage == "C"
    captured = capsys.readouterr()
    combined = captured.out + captured.err
    c_stress_lines = [
        line for line in combined.splitlines()
        if "stage_gate.canonical_five.dual_path" in line and "stage=C_stress" in line
    ]
    # disabled mode でも stress 成功なら 1 entry / genome
    assert len(c_stress_lines) == 1
    # canonical_skipped=True を含む
    assert "canonical_skipped=True" in c_stress_lines[0]
    # fold= kwarg は含まれない (= 識別子契約 C4)
    assert "fold=" not in c_stress_lines[0]
```

#### 6.2.5 log content 検証 (= B1, C1-C4)

```python
def test_stage_c_stress_canonical_succeeds_for_60d_holdout(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Stage C stress dual-path log entry が `stage='C_stress'` で 1 entry / genome 出力、
    必須 kwargs (= genome / interpretation_note / canonical_* / legacy_*、 fold 不在)
    含有 (= acceptance B1, C1-C4)."""
    bars = _make_continuous_bars(2, bars_per_day=4)
    ev = ConstantPrimitiveEvaluator(value=0.0)
    res = evaluate_stage_c(
        _one_clause_genome("g_c_stress_log_check"), bars, usd_jpy_meta(),
        _backtest_config(), ev, StageGateConfig(),
    )
    assert res.stage == "C"
    captured = capsys.readouterr()
    combined = captured.out + captured.err
    c_stress_lines = [
        line for line in combined.splitlines()
        if "stage_gate.canonical_five.dual_path" in line and "stage=C_stress" in line
    ]
    assert len(c_stress_lines) == 1
    line = c_stress_lines[0]
    assert "genome=g_c_stress_log_check" in line
    assert "interpretation_note=direction_monitoring_only" in line
    assert "canonical_trade_count=" in line
    assert "legacy_trade_count=" in line
    # C4: C_stress 識別子契約 (= fold key 不在)
    assert "fold=" not in line
```

#### 6.2.6 max_spread_bps is None で C_stress 0 件 (= acceptance C5)

```python
def test_stage_c_stress_canonical_skipped_when_max_spread_bps_is_none(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """backtest_config.max_spread_bps is None のとき、
    `stage='C_stress'` の dual_path event と canonical_five.skipped event が
    両者 0 件 (= acceptance C5)."""
    from dataclasses import replace
    bars = _make_continuous_bars(2, bars_per_day=4)
    ev = ConstantPrimitiveEvaluator(value=0.0)
    cfg = replace(_backtest_config(), max_spread_bps=None)
    res = evaluate_stage_c(
        _one_clause_genome("g_c_stress_no_spread"), bars, usd_jpy_meta(),
        cfg, ev, StageGateConfig(),
    )
    assert res.stage == "C"
    # spread_stress_skipped reason は legacy 経路で出る
    assert "spread_stress_skipped" in res.reason_codes
    captured = capsys.readouterr()
    combined = captured.out + captured.err
    c_stress_lines = [
        line for line in combined.splitlines()
        if "stage=C_stress" in line
    ]
    # dual_path / canonical_five.skipped event 両者 0 件
    assert len(c_stress_lines) == 0
```

#### 6.2.7 stress 例外時 C_stress 0 件 (= acceptance C5、 Round 1 [Warning] 反映で max_spread_bps 分岐)

```python
def test_stage_c_stress_canonical_skipped_when_stress_backtest_raises(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """stress backtest が例外発生 → `stage_c.stress_failure` WARN 後、
    `stage='C_stress'` の event は 0 件 (= acceptance C5)。

    Round 1 [Warning] 反映: call count 依存を廃止し、 **`max_spread_bps` 値で
    stress 経路を同定** (= base 値と stress 値で区別)。 これにより将来
    base / stress 以外の run_backtest 呼出が追加されても test 安定性が保たれる。"""
    from dataclasses import replace as dc_replace
    from decimal import Decimal as _Decimal
    from src.alpha_factory import stage_gate as sg

    original_run = sg.run_backtest
    base_max_spread = _backtest_config().max_spread_bps
    assert base_max_spread is not None, "fixture must have max_spread_bps set"
    base_max_dec = _Decimal(str(base_max_spread))
    multiplier = _Decimal(str(StageGateConfig().spread_stress_multiplier))
    stress_max_dec = base_max_dec * multiplier  # stress 経路のみ一致する値

    def _conditional_run(bars, strategy, broker, config):  # type: ignore[no-untyped-def]
        # max_spread_bps が stress 値と一致するときだけ raise (= stress 経路同定)
        if config.max_spread_bps is not None:
            cur_dec = _Decimal(str(config.max_spread_bps))
            if cur_dec == stress_max_dec:
                raise RuntimeError("simulated stress backtest failure")
        return original_run(bars, strategy, broker, config)

    monkeypatch.setattr(sg, "run_backtest", _conditional_run)
    bars = _make_continuous_bars(2, bars_per_day=4)
    ev = ConstantPrimitiveEvaluator(value=0.0)
    res = evaluate_stage_c(
        _one_clause_genome("g_c_stress_raise"), bars, usd_jpy_meta(),
        _backtest_config(), ev, StageGateConfig(),
    )
    assert res.stage == "C"
    assert "spread_stress_skipped" in res.reason_codes
    captured = capsys.readouterr()
    combined = captured.out + captured.err
    # stage_c.stress_failure WARN は出る (legacy)
    assert "stage_c.stress_failure" in combined
    # ただし C_stress dual-path event は 0 件
    c_stress_lines = [
        line for line in combined.splitlines()
        if "stage=C_stress" in line and "stage_gate.canonical_five" in line
    ]
    assert len(c_stress_lines) == 0
```

#### 6.2.8 golden 値固定 (= acceptance A5、 Round 1 [Suggestion] 反映)

```python
def test_stage_c_stress_canonical_golden_first_evaluation_succeeds() -> None:
    """fixed seed × fixed fixture で C_stress canonical sidecar の主要 field が
    deterministic な期待値と一致 (= acceptance A5、 Round 1 [Suggestion] 反映)。

    現 fixture (= 50 trades + bars_60d + flat equity = 1M JPY) で C_stress も
    base と同じ deterministic 出力 (= 同じ trades / equity を canonical helper に
    渡す。 stress backtest は spread 増しで実 trade 数が変わるが、 helper 単体 test
    では C_stress label で base 同等 fixture を渡して deterministic 性のみ確認)。
    複数 entry での golden は overengineering (= 概念設計 scope)。"""
    base = datetime(2026, 1, 1, tzinfo=UTC)
    trades = []
    for i in range(50):
        entry = base + timedelta(days=i // 10, hours=11, minutes=30)
        exit = base + timedelta(days=i // 10, hours=12, minutes=i % 10)
        trades.append(_bt(pid=i, entry_time=entry, exit_time=exit))
    bars = _make_bars_60d()
    equity_curve = [(b.bar_time, Decimal("1000000")) for b in bars]
    result = _try_evaluate_canonical_five_safe(
        trades=trades, equity_curve=equity_curve, bars=bars,
        live_criteria=_make_default_live_criteria(),
        window_days=60,  # stage_c_holdout_days
        stage_label="C_stress", genome_name="g_c_stress_golden",
        enabled=True,
    )
    assert result is not None
    assert result.trade_count == 50
    assert result.net_pnl_after_cost == pytest.approx(5000.0, abs=1e-9)
    assert result.max_dd == pytest.approx(0.0, abs=1e-9)
    assert result.session_block_win_rate_worst == pytest.approx(0.5, abs=1e-9)
    assert result.gate_pass is False  # sharpe_min=1.0 を満たさない
    assert result.invariants.is_feasible is True
```

### 6.4 fixture
- 既存 `_make_continuous_bars(2, bars_per_day=4)` + `_backtest_config()` + `_one_clause_genome` を流用 (= step 1.5 / 1.6 と同等)

### 6.5 既存 43 ケースへの影響
- `_log_canonical_dual_path` の docstring のみ変更 (= 動作不変)
- 既存 caller (Stage A / B_IS / B_fold / C_base) は変更なし
- 既存 43 ケース全 PASS する想定 (= acceptance A4)

---

## 7. acceptance criterion (= 概念設計 § 5.3 反映)

### A. 判定結果回帰 0 (必須、 deep dict comparison)
- [A1] Stage C の `StageResult.passed` / `reason_codes` / `metrics["payload"]` (= base + stress + cross_pair 全件) が canonical 配線追加で 1 byte も変化しない (= log_only vs disabled 完全一致)
- [A2] archive Parquet schema 完全不変
- [A3] GA fitness 不変
- [A4] Stage A / Stage B IS / Stage B fold / Stage C base の dual-path log は step 1.6 と完全一致 (= 既存 43 ケース全 PASS で確認)

### B. 運用回帰検証
- [B1] dual-path log が Stage C stress で crash なく出力 (= max_spread_bps が None でない場合のみ)
- [B2] smoke 5 Run で peak RSS が worker 3 GB budget 内 (= base と同等規模、 低リスク仮説、 実測 必須)
- [B3] smoke 5 Run の所要時間が step 1.6 比 ±20% 以内
- [B4] dual-path log が legacy log (= stage_c.stress_failure) と独立出力

### C. legacy 比較可能性 + 識別子契約
- [C1] dual-path log の `stage` field が `"C_stress"` で正しく区別可能
- [C2] `legacy_*` / `canonical_*` field が同 log entry に共存
- [C3] `interpretation_note="direction_monitoring_only"` が継承
- [C4] **C_stress 識別子契約**: `(stage, genome)` 2 つの kwargs key で一意特定可能 (= 1 entry / genome、 fold key 不在)
- [C5] **skip 整合**: `max_spread_bps is None` または stress 例外時には `stage_gate.canonical_five.dual_path` event と `stage_gate.canonical_five.skipped` event の **両者** が `stage="C_stress"` で 0 件、 `stage_c.stress_failure` WARN log 出力時も C_stress dual-path 行は 0 件

### D. 例外隔離契約 (= 物理隔離保証)
- [D1] dual-path 経路で例外発生しても `stress_payload` (= sharpe / total_pnl / max_drawdown_frac / trade_count / sharpe_degradation / pnl_degradation / skipped) と `reasons` (= spread_stress.* reasons) 完全不変
- [D2] dual-path 経路の例外は `stage_gate.canonical_five.unexpected_failure` または `stage_gate.canonical_five.log_failed` の WARN log のみ、 既存 `stage_c.stress_failure` reason 経路は touch しない
- [D3] monkeypatch で `_try_evaluate_canonical_five_safe` を `stage_label="C_stress"` 限定 raise させても StageResult が disabled mode と一致 (= `passed` / `reason_codes` / `metrics["payload"]` / `n_bars` の deep comparison、 `wall_time_seconds` 除外)
- [D4] dual-path ブロック内では `stress_payload` / `reasons` を write しない (= 物理隔離契約、 D1/D3 snapshot deep equality 比較で実質担保)

---

## 8. 実装モード

| 項目 | 内容 |
|---|---|
| 推奨モード | **incremental** (= worktree todo/T085 で 1 commit、 main マージ no-ff) |
| 判断根拠 | step 1.6 と同型 pattern、 adapter / helper 凍結再利用、 stage_gate.py のみ拡張、 計算量 +1 calc/genome、 archive Parquet schema 不変、 既存 43 ケース PASS で後方互換保証 |
| 競合リスク | step 1.6 の続き、 他 worktree (= todo/T081) と独立、 競合なし |
| 想定実装時間 | **短〜中** (= 1 commit、 約 35 行追加 + 8 ケース test) |

### 8.1 commit 戦略

```
worktree todo/T085:
  commit: feat(B step 1.7): Stage C stress dual-path 配線追加 + helper docstring に C_stress 追記

main:
  no-ff merge → main に 1 commit を保持
```

step 1.5 は 2 commit (rename + wiring)、 step 1.6 は 1 commit、 step 1.7 も **1 commit で十分** (= rename / シグネチャ変更なし、 docstring のみ変更 + behavioral wiring)。

---

## 9. 確認事項 (= 実装前)

- [ ] 既存 43 ケース worktree で run、 全 PASS 確認
- [ ] worktree todo/T085 を main から作成
- [ ] commit 後、 既存 43 ケース + 新規 8 ケース = 51 ケース全 PASS 確認 (= acceptance A1, A4, C1-C5, D1-D4)
- [ ] ruff / mypy clean

---

## 10. 参考資料

- 概念設計 (Round 2 APPROVED): `devnotes/20260503-2319-B-phase2-step1.7-stage-c-stress-dual-path/conceptual-design.md`
- step 1.5 詳細設計: `devnotes/20260503-1446-B-phase2-step1.5-stage-bc-dual-path/detailed-design.md`
- step 1.6 詳細設計: `devnotes/20260503-2049-B-phase2-step1.6-stage-b-per-fold-dual-path/detailed-design.md` (= 物理隔離 pattern)
- step 1.6 完了 handoff: `devnotes/20260503-2155-B-step1.6-complete-handoff/handoff.md`
- step 1.6 main commit: `1dadc8b Merge branch 'todo/T084'`
- canonical_adapter.py (凍結): `src/alpha_factory/canonical_adapter.py`
- stage_gate.py (拡張対象): `src/alpha_factory/stage_gate.py:1385-1442` (stress 区画) + L170-235 (`_log_canonical_dual_path` docstring)
- 既存 test: `tests/alpha_factory/test_stage_gate_canonical_dual_path.py` (= 43 ケース、 step 1.7 で +8 ケース = 計 51 ケース)
