# 概念設計 (skeleton): B Phase 2 切替コミット step 1 — canonical_metrics → main flow 統合

**作成日時**: 2026-05-03 10:30 JST
**起源**: T082 Obsoleted finding で 「TradeRecord 経路が main flow に未統合」 が判明、 B Phase 2 切替コミット の最初の step として canonical_metrics 統合を実施
**性質**: main flow (= run_backtest → compute_metrics → BacktestMetrics) と canonical_metrics 経路 (= evaluate_canonical_five → CanonicalFiveResult) の dual-path 配線
**位置付け**: cascade port v2 Phase 2 切替コミット 7 step segmentation の **step 1** (= canonical_metrics integration、 後続 step で stage_bc_evaluator / cpps_archive 等)
**status**: **skeleton (= 後続セッションで zenigame-fx-alpha-design による Codex review で詳細化、 dual-path → LOG_ONLY → FAIL_CLOSED の段階的切替設計 fence)**

---

## 1. 背景・課題

### 1.1 現状の main flow (= broker.Trade based)

```
swim_lane.py / stage_gate.py:
  evaluate_stage_a/b/c(genome, bars, ...) →
    run_backtest(bars, strategy, broker, config) → BacktestResult(trades=list[broker.Trade], equity_curve)
    compute_metrics(trades, equity_curve) → BacktestMetrics  # Decimal-based, bar-level Sharpe
  StageResult(stage="A/B/C", passed, metrics={"payload": {fitness_pen, sharpe_raw, ...}})
```

`compute_metrics` は `list[broker.Trade]` を直接消費し、 `BacktestMetrics` (= 16 field, Decimal-based, bar-level Sharpe + standard metrics) を生成。

### 1.2 cascade port v2 で完成済 library (= canonical_metrics)

```python
@dataclass(frozen=True)
class CanonicalFiveResult:
    sr_session_worst_block_scale: float        # 3 bucket SR block-scale の min (HAC Bartlett q=5)
    sr_session_worst_annual_estimate: float    # annual 換算
    net_pnl_after_cost: float
    max_dd: float                              # ratio [0, 1]
    trade_count: int
    session_block_win_rate_worst: float
    per_bucket_sr: dict[SessionBucket, float]
    per_bucket_wr: dict[SessionBucket, float]
    low_sample_buckets: frozenset[SessionBucket]
    slack_sharpe / slack_pnl / slack_dd / slack_tc / slack_wr: float  # signed
    gate_worst_gap: float
    gate_pass: bool
    log_pf_clip: float
    bucket_validator_version: str
    invariants: InvariantFlags
```

`evaluate_canonical_five(input, thresholds, ...)` は `BCEvaluationInput` (= TradeRecord tuple + BarEquitySeries + business_day_universe) を入力に取り、 session-block worst-aggregation で CanonicalFiveResult を生成。

### 1.3 評価哲学の差分

- `BacktestMetrics`: bar-level annualized Sharpe + standard metrics (= legacy 評価)
- `CanonicalFiveResult`: session-block (Tokyo / London / NY × business day) worst-aggregation の 5 軸 (= synthesis § 6.4)

**両者は数値も意味も異なる**。 単純な置換ではなく、 Stage A/B/C の評価判定ロジックも canonical 5 軸ベースに切替える必要がある。

### 1.4 step 1 のスコープ確定

**step 1 では canonical 5 軸の dual-path 配線のみ**:
- 既存 `compute_metrics(broker.Trade)` 経路は **不変** (= Stage A/B/C 判定継続使用)
- 新規 adapter で `broker.Trade → TradeRecord` / `equity_curve → BarEquitySeries` 変換
- `evaluate_canonical_five` を caller から呼出 (= sidecar 計算)
- 結果を log + sidecar JSON 出力 (= LOG_ONLY mode、 既存判定には影響しない)

= step 1 完了後の状態: main flow が canonical_metrics の **観測値を生成可能**、 ただし判定には未使用 (= 後続 step で判定ロジック切替)。

---

## 2. 改善アイデア (= 7 step segmentation の step 1)

### Step 1.1: broker.Trade → TradeRecord adapter

`src/alpha_factory/canonical_adapter.py` (新規) に変換 helper:

```python
def trade_to_trade_record(
    broker_trade: broker.Trade,
    *,
    session_bucket: SessionBucket,
    business_day_index: int,
) -> TradeRecord:
    return TradeRecord(
        entry_time_utc=broker_trade.entry_time,  # UTC-aware 確認
        exit_time_utc=broker_trade.exit_time,
        pnl_net=float(broker_trade.pnl),  # Decimal → float
        session_bucket=session_bucket,
        business_day_index=business_day_index,
        is_session_close_drop=...,  # broker side flag (T070 経路から取得)
        is_negative_equity_drop_open=...,
        spread_cost=float(broker_trade.spread_cost),  # T078 で追加済
        holding_cost=float(broker_trade.holding_cost),
    )
```

session_bucket / business_day_index は **T070 calendar.py** から計算 (= 既存実装あり)。

### Step 1.2: equity_curve → BarEquitySeries adapter

```python
def equity_curve_to_bar_equity_series(
    equity_curve: list[tuple[datetime, Decimal]],
) -> BarEquitySeries:
    points = tuple(
        BarEquityPoint(timestamp_utc=ts, equity=float(eq))
        for ts, eq in equity_curve
    )
    return BarEquitySeries(points=points)
```

### Step 1.3: business_day_universe 計算

T070 calendar.py の `compute_business_day_universe` (= 既存) を使って Stage A/B/C 期間内の (bucket, business_day_index) ペア集合を計算。

### Step 1.4: stage_gate.py に dual-path 配線

`evaluate_stage_a` / `evaluate_stage_b` / `evaluate_stage_c` で:

```python
# 既存 (= 不変)
result = run_backtest(bars, strategy, broker, backtest_config)
bt = compute_metrics(result.trades, result.equity_curve, ...)

# 新規追加 (= dual-path、 LOG_ONLY mode)
canonical_result = _try_evaluate_canonical_five_safe(
    result.trades, result.equity_curve, bars, ...
)  # 例外時は None で fall through
if canonical_result is not None:
    logger.info(
        "stage_gate.canonical_five.dual_path",
        stage="A",
        genome=genome.name,
        # legacy
        legacy_total_pnl=str(bt.total_pnl),
        legacy_trade_count=bt.trade_count,
        legacy_max_dd_pct=str(bt.max_drawdown_pct),
        # canonical
        canonical_net_pnl=canonical_result.net_pnl_after_cost,
        canonical_trade_count=canonical_result.trade_count,
        canonical_max_dd=canonical_result.max_dd,
        canonical_gate_pass=canonical_result.gate_pass,
        # diff
        pnl_diff=float(bt.total_pnl) - canonical_result.net_pnl_after_cost,
    )
    # payload に sidecar 添付 (= archive Parquet には書かない、 in-memory only)
    payload["canonical_five_sidecar"] = canonical_result
```

### Step 1.5: feature flag (= LOG_ONLY 切替)

`config/alpha_factory/default.yaml`:
```yaml
phase2:
  canonical_metrics_mode: log_only  # log_only / fail_closed / disabled
```

`disabled` mode で完全 skip (= regression リスク回避)、 `log_only` で sidecar 出力、 `fail_closed` (= 後続 step で導入) で判定切替。

### Step 1.6: sidecar JSON output (Optional、 後続 step か?)

step 1 では log のみで、 sidecar JSON 出力は後続 step (= report 経路改修) で対応。

---

## 3. 期待効果

### 3.1 直接的

- main flow から canonical 5 metrics の **観測値が取得可能** に
- 既存 vs canonical の数値 diff を **smoke 5 Run で計測可能** (= Phase 2 切替の calibration data)
- T081 step 2-6 の前提条件の 1 つ (= TradeRecord 経路の存在) を満たす

### 3.2 間接的

- 後続 step (= stage_bc_evaluator / cpps_archive) の統合が **同じ TradeRecord SSOT に乗る**
- Phase 2 完了形 (= canonical 5 軸ベース判定) への足場確立
- adapter 関数を 1 module に隔離 = 統合範囲の局所化 + test 容易性

### 3.3 live_criteria 達成への寄与

直接的: **薄い** (= 観測のみ、 判定ロジックは不変)
間接的: 後続 step で canonical 5 軸ベース判定 (= synthesis SSOT) に切替えると、 評価精度向上 + session-block 安定性確認可能

---

## 4. 実装方針 (概要)

### 4.1 変更ファイル候補

1. `src/alpha_factory/canonical_adapter.py` (新規): broker.Trade ↔ TradeRecord / equity_curve ↔ BarEquitySeries 変換 + business_day_universe 計算 helper
2. `src/alpha_factory/stage_gate.py`: evaluate_stage_a/b/c に dual-path 計算追加 (LOG_ONLY mode)
3. `config/alpha_factory/default.yaml`: phase2.canonical_metrics_mode field 追加 (`log_only` default)
4. `src/alpha_factory/config.py`: AlphaFactoryConfig に Phase2Config 追加
5. tests/: adapter unit test + dual-path integration test (= legacy + canonical 両方の path が走り、 期待 diff が log される)

### 4.2 影響範囲

- stage_gate.py の Stage A/B/C 評価で **計算量 ~2x** (= legacy + canonical 並走、 LOG_ONLY mode)
- 既存 BacktestResult の trade / equity_curve がそのまま reuse されるため、 backtest 自体は 1 回のみ (= 計算 overhead は metrics 計算層のみ、 軽量)
- archive Parquet schema は不変 (= sidecar は in-memory only)

### 4.3 LOG_ONLY → FAIL_CLOSED 切替戦略

step 1: LOG_ONLY 導入 (= 本 TODO スコープ)
step 2-7 の後: smoke 5 Run で diff 計測 → calibration → FAIL_CLOSED 切替 (= 旧 BacktestMetrics 経路削除) は別 TODO (= 「B Phase 2 切替完了 commit」)

---

## 5. 制約・前提

### 5.1 前提

- T070 calendar.py の `compute_business_day_universe` / `assign_session_bucket_and_business_day_index` 関数が動作する (= 既存実装、 grep で確認要)
- broker.Trade の `entry_time` / `exit_time` が **UTC-aware** で `utcoffset() == 0` (= TradeRecord __post_init__ invariant)
- broker.Trade の `pnl` を `float()` 変換しても relative 1e-9 以内 (= T078 broker 等価性 test で確認済)
- equity_curve の timestamps が strict monotone increasing (= BarEquitySeries invariant)

### 5.2 制約

- 既存 evaluate_stage_a/b/c の戻り `StageResult` schema は **不変** (= archive 互換)
- canonical sidecar は payload 内 in-memory only (= archive Parquet schema 不変)
- LOG_ONLY mode で既存判定は **完全に不変** (= regression 0)

---

## 6. スコープ外

1. **canonical 5 軸ベース判定** (= LOG_ONLY → FAIL_CLOSED 切替): 後続別 TODO
2. **stage_bc_evaluator (canonical 5 軸 caller) の main flow 統合**: B Phase 2 step 2
3. **archive Parquet schema 拡張** (= canonical metrics 永続化): 後続別 TODO
4. **CanonicalFiveThresholds の caller 側計算** (= live_criteria → window scale で thresholds 構築): B Phase 2 step 2
5. **sidecar JSON 永続化**: 後続別 TODO (= report 経路改修)

---

## 7. リスク

| リスク | 影響 | 緩和 |
|---|---|---|
| broker.Trade の entry_time / exit_time が UTC-aware でない | 中 | adapter で `_validate_utc_aware` 呼出、 不適合なら fail-closed (= LOG_ONLY mode で WARN log + skip canonical 計算) |
| business_day_universe 計算が Stage A/B/C 期間で空集合になる | 中 | T070 既存実装の test を信頼、 空集合検出時は `INPUT_BUSINESS_DAY_UNIVERSE_MISMATCH` reason で skip |
| canonical 計算が legacy より遅い (= 2x 以上) | 中 | smoke 5 Run で profile、 worst-case 30% 増を想定、 必要なら `disabled` mode で skip 可能 |
| dual-path で例外が発生して legacy 経路も巻き込む | 高 | `_try_evaluate_canonical_five_safe` で例外を catch + WARN log のみ (= 既存経路は touch しない) |
| numerical diff (legacy vs canonical) が予想以上に大きい | 中 | smoke 5 Run で diff 分布計測、 calibration data 取得後に判定切替前に整合確認 |

---

## 8. 7 step segmentation 全体俯瞰

| step | 内容 | 統合先 module |
|---|---|---|
| **step 1 (本)** | canonical_metrics → main flow (= TradeRecord / BarEquitySeries adapter + dual-path LOG_ONLY) | canonical_metrics |
| step 2 | stage_bc_evaluator → main flow (= evaluate_stage_b_pooled / evaluate_stage_c_lite 運用) | stage_bc_evaluator |
| step 3 | cpps_archive → main flow (= archive_admit / AdmissionReport 経路) | cpps_archive |
| step 4 | stage_a_evaluator (T063) → main flow (= StageAControllerState 永続化) | stage_a_evaluator |
| step 5 | nsga2_selection → main flow (= _breed_next_gen 置換) | nsga2_selection |
| step 6 | loop_closure (warmstart) → main flow | loop_closure |
| step 7 | failure_handling → main flow | failure_handling |

各 step:
- 1 worktree commit、 Codex 設計 + 実装 review、 dual-path LOG_ONLY 維持 (= 既存判定不変)
- 完了後に T081 step 2-6 を順次再開可能 (= 観測 9 metric 全実値化)

---

## 9. skeleton から本格設計への昇格手順

1. zenigame-fx-alpha-design skill 起動 (= topic="B-phase2-step1-canonical-metrics")
2. T070 calendar.py の `compute_business_day_universe` / session bucket 関数 grep + Read で全件特定
3. broker.Trade の field 全件確認 (= entry_time / exit_time / pnl / spread_cost / holding_cost / position_id 等)
4. `_try_evaluate_canonical_five_safe` の例外 fallback ロジック詳細化
5. `phase2.canonical_metrics_mode` config の loader / propagation 確認
6. Codex 概念 + 詳細設計レビュー → APPROVED まで
7. zenigame-fx-implement で worktree todo/B-step1 で実装
8. main マージ → step 2 へ続く

---

## 10. 参考資料

- T078 完了 commit: `857eb82` (= TradeRecord schema 拡張 + apply_spread_stress 正式実装)
- T081 step 2-6 blocker finding: `devnotes/20260503-0910-T081-step2-blocker-finding/finding.md`
- T082 Obsoleted finding: `devnotes/20260503-1020-T082-blocker-finding/finding.md`
- 前 handoff (= B Phase 2 切替コミット 提案): `devnotes/20260503-1023-T082-obsolete-phase2-handoff/handoff.md`
- canonical_metrics: `src/alpha_factory/canonical_metrics.py` (= 1100+ 行、 TradeRecord / BarEquitySeries / CanonicalFiveResult / evaluate_canonical_five)
- backtest metrics: `src/backtest/metrics.py:147 compute_metrics`
- stage_gate caller: `src/alpha_factory/stage_gate.py:381-1154`
