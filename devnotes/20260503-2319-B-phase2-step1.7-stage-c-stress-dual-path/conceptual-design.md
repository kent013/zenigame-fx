# 概念設計: B Phase 2 切替コミット step 1.7 — Stage C stress dual-path 拡張

**作成日時**: 2026-05-03 23:19 JST (Round 2 改訂: 2026-05-03 23:35 JST)
**起源**: B Phase 2 切替コミット step 1.6 (= Stage B per-fold dual-path 配線、 main commit 1dadc8b) 完了後の段階的拡張
**性質**: step 1 / 1.5 / 1.6 で確立した dual-path helper / adapter を **Stage C stress 区画 (= spread 増し backtest) にも適用** (= descriptive observation のみ、 stress hard gate の shadow ではない)
**位置付け**: cascade port v2 Phase 2 切替コミット 7 step segmentation の **step 1.7** (= 任意・有益な観測拡張、 step 2 を block しない optional observability step)
**status**: **概念設計 Round 2 APPROVED** (= Codex Round 1 CHANGES_REQUESTED 反映済、 Round 2 で APPROVED 判定)。 残 Warning 2 件 (= disabled mode log 契約明文化 / リスク表に § 2.5 参照) は本 patch で反映済

---

## 0. Round 1 → Round 2 改訂対応マトリクス

| Round 1 指摘 | 対応 |
|---|---|
| § 1 [Critical] step 2 calibration 充足表現過大、 C_stress canonical は stress hard gate の shadow ではない | 「step 2 calibration 完成度」 表現を全削除、 「Stage C stress canonical metric 観測追加」 に下げる。 § 1.4 切替誘因ガードに「C_stress canonical_gate_pass は mission 判定にも切替判定にも使わない」 追加 |
| § 4 [Critical] C_base/C_stress diff 比較データ・sharpe_degradation の canonical 版表現は事実と不一致 | dual-path log は同 stage 内 legacy - canonical のみ (= cross-stage diff は出さない) を明記、 「比較は後段集計で `(genome, stage)` join が必要」 に下げる。 「canonical 版 sharpe_degradation」 削除 |
| § 5 [Warning] 前提表 Verified に `C_stress fold_index=None 出力` 早すぎ | `Inferred / To Verify` に移動、 acceptance に C_stress no-fold log 契約追加 |
| § 5 [Warning] skip 経路検証で `canonical_five.skipped` event も非出力 | acceptance C5 を「`dual_path` + `canonical_five.skipped` の両 event 非出力」 に強化 |
| § 7 [Warning] メモリ概算粗い | 60d ≒ 86,400 bars (M1) に修正、 「上限保証ではなく低リスク仮説」 表現に統一、 acceptance B2 実測前提を強調 |
| § 9 [Warning] sharpe 意味系 3 種類切り分け不足 | § 2.5 sharpe 読み替え表追加 (= legacy_sharpe = bar-level annualized / stress_payload.sharpe = trade_sharpe_raw / canonical_* = canonical 5 output) |
| § 6 [Warning] 「base + stress まで充実」 表現過大 | 「partial 拡充」 統一、 「step 2 を block しない optional observability step」 に寄せる |
| § 3 [Warning] D4 物理隔離契約は runtime test 困難 | 「D1/D3 snapshot 比較で実質担保」 と明文化 |
| § 5 [Suggestion] stress 例外時に C_stress log 0 件 assert | acceptance C5 に追記 |

---

## 1. 背景・課題

### 1.1 step 1.6 完了時点の状態

step 1.6 (= main commit 1dadc8b) で:
- Stage A / Stage B IS / Stage B fold (= n_fold 動的) / Stage C base の 4 系列で dual-path 観測点を確立
- helper (`_try_evaluate_canonical_five_safe` / `_log_canonical_dual_path`) は凍結
- step 1.6 で `_log_canonical_dual_path` に optional kwarg `fold_index: int | None = None` 追加 (= B_fold で必須、 他 stage は None)

**Stage C stress 区画は未配線**: `evaluate_stage_c` の stress 区画 (= stage_gate.py:1385-1442、 spread × `spread_stress_multiplier=1.5` で再 backtest) では legacy `BacktestMetrics` のみ生成され、 canonical 5 軸は計算されない。

### 1.2 課題

- **観測範囲不足**: Stage C の **stress test 経路** (= spread 増し backtest) で canonical 5 軸を観測できない
- **後段 join 用データ不足**: step 1.6 までで Stage C base のみ canonical 観測、 stress 適用後の canonical 5 metrics は未観測。 base / stress を比較するには、 後段集計で `(genome, stage)` の cross-stage join が必要 (= 単一 dual-path log entry には同 stage 内の `legacy - canonical` diff のみ含まれる、 cross-stage diff は含まない)
- **Stage C side calibration data の partial 拡充**: Stage C 全評価軸 (= base + stress + cross_pair) のうち base のみ観測済、 stress 不在で Stage C side calibration data が partial

### 1.3 step 1.7 のスコープ確定

**step 1.7 では Stage C stress 区画の dual-path canonical metric 観測追加のみ** (= 任意・有益な observability 拡張、 step 2 を block しない optional step):
- adapter / helper 改変禁止 (= step 1 / 1.5 / 1.6 で凍結、 同じ helper を再利用)
- step 1.6 で確立した `_log_canonical_dual_path(..., fold_index=None default)` をそのまま再利用
- stage_label="C_stress" で C_base と log 系列を分離 (= § 4.6 ログ命名規約 SSOT 準拠、 step 1.5 で commitment 済)
- 既存判定経路完全不変 (= regression 0、 archive Parquet schema 不変、 LOG_ONLY 維持)
- 物理隔離: stress backtest 完了後 (= bt 算出後) の **別 try ブロック** で dual-path、 既存 stress_payload / spread_stress reasons に絶対干渉しない
- skip 経路一致 (legacy 計算 skip 系): `max_spread_bps is None` または stress 例外時は dual-path log (= `dual_path` event + `canonical_five.skipped` event) **両者** が emit されない (= 既存 `stress_payload["skipped"]=True` 経路と整合、 helper 自体が呼ばれない)
- **disabled mode の挙動** (= Round 2 [Warning] 反映): `phase2_canonical_metrics_mode='disabled'` のとき、 stress 成功時は `_try_evaluate_canonical_five_safe(enabled=False)` で None 即返り、 `_log_canonical_dual_path(canonical=None, stage='C_stress')` 経由で **`canonical_skipped=True` の `dual_path` event は emit される** (= stress 成功時のみ、 step 1.6 B_fold disabled mode と同型)。 stress skip / 例外時は dual_path event 自体が emit されない。

**重要 (Round 1 [Critical] § 1 反映)**: C_stress dual-path canonical は **既存 stress hard gate (= `spread_stress_min_total_pnl` / `spread_stress_min_sharpe` / `trade_count_min`) の shadow ではない**:
- canonical 側 threshold は `live_criteria` ベース (= 60d window scaling)、 stress hard gate とは異なる軸を見ている
- canonical の `gate_pass` を stress hard gate calibration 根拠に使ってはならない
- stress hard gate との対応付け / calibration は step 2 か別 step で扱う

### 1.4 Stage C cross_pair (ii-lite) はスコープ外

step 1.7 では cross_pair は対象外:
- mission 必須軸 (= ii-lite) のため、 設計が複雑になる可能性 (= 単独 step として扱う)
- step 1.8 (= 新設、 cross_pair 単独) で後続対応
- step 1.7 では stress のみで「ゆっくり・確実に」リズム維持

### 1.5 切替誘因のガード

step 1.7 完了後、 観測 only の C_stress dual-path log を切替判断の根拠にしないこと:
- **C_stress canonical_gate_pass は mission 判定にも切替判定にも使わない** (= Round 1 [Critical] / [Suggestion] 反映)
- C_stress pass/fail 分布だけで step 2 (= 判定切替) のタイミングを決めない
- live_criteria 不変 (= 禁止事項 #4)、 評価期間 (= stage_c_holdout_days) 不変 (= 禁止事項 #1)
- 解釈単位は run 横断 / genome 横断の集計で n>30 を満たした後のみ (= C7、 ただし n>30 は解釈開始の最低条件、 因果結論の十分条件ではない)
- canonical / legacy gate は同じものを見ていない (= § 4.5 step 1.6 同型注記、 直接比較は collider bias)
- C_base / C_stress の比較は **後段集計で `(genome, stage)` を join した descriptive analysis のみ** (= dual-path log には cross-stage diff が含まれない)

= step 1.7 完了後の状態:
- main flow が canonical 5 metrics の観測値を **Stage A / Stage B IS / Stage B fold / Stage C base / Stage C stress の 5 評価点** で生成可能
- Stage C side calibration data が base + stress まで **partial 拡充** (= 完全充足ではない、 cross_pair 未観測)
- Stage C cross_pair は依然未観測 (= step 1.8 以降で対応、 mission 必須軸として残る)

---

## 2. 改善アイデア

### 2.1 stress 区画 dual-path 配線 (= 物理隔離版)

`evaluate_stage_c` の stress 区画 (= stage_gate.py:1385-1442) の `bt = compute_metrics(...)` 直後、 既存 `stress_payload` への代入処理の **後** に **別 try ブロック** で dual-path 配線を追加する:

```python
if backtest_config.max_spread_bps is None:
    stress_payload["skipped"] = True
    reasons.append("spread_stress_skipped")
    # step 1.7: stress 計算 skip → dual-path も skip (= log emit しない)
else:
    base_max = Decimal(str(backtest_config.max_spread_bps))
    multiplier_dec = Decimal(str(stage_config.spread_stress_multiplier))
    new_max = base_max * multiplier_dec
    stress_config = replace(backtest_config, max_spread_bps=new_max)

    # dual-path 経路用に legacy 結果を保持 (= 別 try に渡す、 物理隔離)
    stress_bt: BacktestMetrics | None = None
    stress_trades: list[BrokerTrade] | None = None
    stress_equity: list[tuple[datetime, Decimal]] | None = None

    # === 既存 legacy stress 計算 (= stress_payload / reasons 確定、 完全不変) ===
    try:
        strategy = DslStrategy(genome, primitive_evaluator)
        broker = MockBroker(instrument_meta=meta)
        res = run_backtest(bars_holdout, strategy, broker, stress_config)
        bt = compute_metrics(...)
        s_sharpe = ...
        s_total_pnl = ...
        s_trade_count = ...
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
        # dual-path 用に legacy 結果を保持
        stress_bt = bt
        stress_trades = res.trades
        stress_equity = res.equity_curve
    except Exception as exc:
        logger.warning("stage_c.stress_failure", ...)
        stress_payload["skipped"] = True
        reasons.append("spread_stress_skipped")

    # === 新規 dual-path (= 別 try で物理隔離、 stress_payload / reasons に絶対干渉しない) ===
    # legacy stress 計算が成功した場合のみ dual-path 観測 (= 失敗時 skip、
    # 既存 stress_failure WARN log で legacy 経路の状態は記録済)。
    if stress_bt is not None and stress_trades is not None and stress_equity is not None:
        try:
            canonical_sidecar_c_stress = _try_evaluate_canonical_five_safe(
                trades=stress_trades,
                equity_curve=stress_equity,
                bars=bars_holdout,
                live_criteria=stage_config.live_criteria,
                window_days=stage_config.stage_c_holdout_days,
                stage_label="C_stress",
                genome_name=genome.name,
                enabled=(stage_config.phase2_canonical_metrics_mode != "disabled"),
            )
            try:
                _log_canonical_dual_path(
                    stage_label="C_stress",
                    genome_name=genome.name,
                    legacy=stress_bt,
                    canonical=canonical_sidecar_c_stress,
                )
            except Exception as log_exc:
                logger.warning(
                    "stage_gate.canonical_five.log_failed",
                    stage="C_stress", genome=genome.name,
                    error=str(log_exc), error_type=type(log_exc).__name__,
                )
        except Exception as canonical_exc:
            logger.warning(
                "stage_gate.canonical_five.unexpected_failure",
                stage="C_stress", genome=genome.name,
                error=str(canonical_exc), error_type=type(canonical_exc).__name__,
            )
```

**重要設計判断** (= step 1.6 と同型 物理隔離):
- legacy stress 計算と dual-path 観測を **2 つの別 try ブロック** で物理分離
- legacy 計算成功時のみ dual-path 試行 (= `stress_bt is not None` ガード)
- dual-path の二重 try (= helper 例外 + log 例外) で多層防御
- `stress_payload` / `reasons` (= spread_stress.* reasons) は legacy 計算 try 内のみで決定、 dual-path で絶対変えない

### 2.2 max_spread_bps is None / stress 例外時の skip 整合

既存 `stress_payload["skipped"]=True` 経路:
1. `max_spread_bps is None` (= 設定で stress 無効化): legacy 計算自体を skip
2. stress backtest 中に例外発生: `stage_c.stress_failure` WARN + `stress_payload["skipped"]=True` + `spread_stress_skipped` reason

step 1.7 では:
- ケース 1: `else` ブランチに入らないので dual-path 配線は呼ばれない (= 自動 skip)
- ケース 2: outer try の except 句で `stress_bt = None` のまま、 dual-path 配線条件 (`stress_bt is not None`) で skip

→ 両ケースとも legacy skipped 経路と完全整合。 dual-path log は emit されない。

### 2.3 stage_label / 識別子契約

| stage_label | 評価対象 | step | fold_index |
|---|---|---|---|
| `A` | Stage A 評価窓 (60d) | step 1 | None |
| `B_IS` | Stage B 18m 全体 IS | step 1.5 | None |
| `B_fold` | Stage B per-fold OOS | step 1.6 | 必須 (0..n_fold-1) |
| `C_base` | Stage C base evaluation (holdout 60d) | step 1.5 | None |
| **`C_stress` (本)** | Stage C spread stress backtest (holdout 60d × spread_multiplier) | **step 1.7** | None |
| `C_cross_pair` | Stage C cross-pair (ii-lite) shadow | step 1.8 以降 | None |

各 dual-path log には `interpretation_note="direction_monitoring_only"` を継承 (= step 1 で導入済)。

C_stress log entry の識別子契約: `(stage="C_stress", genome=<genome.name>)` の 2 つで一意特定可能 (= 1 genome × 1 entry / Stage C 評価)。

### 2.4 canonical / legacy gate の意味整合 (collider bias 注記)

**Fact**:
- Stage C base の canonical 計算入力: `bars_holdout` + `res.trades` (= base backtest の trade)
- Stage C stress の canonical 計算入力: `bars_holdout` + `res.trades` (= stress backtest の trade、 spread 増しで trade 数 / pnl が異なる)
- 両者は **同じ評価窓 (= holdout 60d)** だが **異なる trades / equity_curve** で集計される
- canonical 側 threshold は両者で同じ (= `live_criteria` ベース、 60d window scaling)
- 既存 stress hard gate (= `spread_stress_min_total_pnl` / `spread_stress_min_sharpe` / `trade_count_min`) は canonical threshold とは異なる軸

**Interpretation (collider bias 警告)**:
- C_base diff と C_stress diff は **異なる input set** から派生する別の観測点
- C_stress の canonical pass/fail を「stress 耐性が高い」と因果解釈すると collider bias を踏む可能性
- C_stress の canonical pass/fail を既存 stress hard gate の代理指標と解釈してはならない (= 別ゲート観測)
- step 1.7 の C_stress dual-path log は **descriptive observation only**、 解釈側で run/genome 横断 n>30 を満たした後の集計でのみ評価する (= C7 sample size guard)
- C_base / C_stress 比較は **後段集計で `(genome, stage)` を join した descriptive analysis のみ** (= 単一 dual-path log entry には同 stage 内の `legacy - canonical` diff のみ、 cross-stage diff は含まない)

### 2.5 sharpe 読み替え表 (= Round 1 [Warning] § 9 反映)

Stage C 内には sharpe を表す異なる量が 3 系列存在し、 dual-path log の解釈時に混同しないこと:

| 量 | 意味 | 出力先 |
|---|---|---|
| `legacy_sharpe` (dual-path log kwarg) | `BacktestMetrics.sharpe` (= **bar-level annualized**) | `_log_canonical_dual_path` の `legacy_sharpe` field |
| `stress_payload["sharpe"]` | `bt.trade_sharpe_raw` (= **trade-level Sharpe v2**) | `StageResult.metrics["payload"]["stress"]["sharpe"]` |
| live_criteria 判定 sharpe (Stage C base) | `_annualize_trade_sharpe(base_sharpe, ...)` (= **trade-level → annualized 換算**、 T042 Phase 0) | `payload["trade_sharpe_annualized"]` |
| `canonical_sr_worst_block` / `canonical_sr_worst_annual` (dual-path log kwarg) | canonical 5 metrics の session-block worst-aggregation Sharpe | `_log_canonical_dual_path` の `canonical_sr_*` fields |

→ 解釈時にどの sharpe を見ているか SSOT で確認すること。 dual-path log の `legacy_sharpe` と `stress_payload.sharpe` は **異なるスケール**。

---

## 3. 期待効果 (= descriptive observation only)

### 3.1 直接的 (= descriptive observation only)

- main flow が canonical 5 metrics の **観測値を Stage C stress で descriptive に生成可能** に (= 1 entry / genome の単独観測、 cross-stage diff は dual-path log に含まれない)
- step 1.7 完了後の観測点: 5 系列 (= A / B_IS / B_fold / C_base / C_stress)
- C_base / C_stress 比較は **後段集計で `(genome, stage)` を join した descriptive analysis のみ可能** (= dual-path log には cross-stage diff が含まれない、 単一 entry は同 stage 内 legacy-canonical diff のみ)

### 3.2 間接的 (= partial 拡充、 主張を最小化)

- **Stage C side calibration data partial 拡充** (= step 2 前提を「完全充足」 ではなく 「partial 拡充」、 Round 1 [Warning] 反映)
- step 1.6 と同型 pattern で物理隔離が rigorous に機能することの再確認
- step 2 着手前により Stage C 観測 data が一段拡張される (= ただし cross_pair は依然未観測)

### 3.3 live_criteria 達成への寄与

- **直接寄与**: なし (= 観測のみ、 判定ロジック完全不変、 GA fitness 不変)
- **間接寄与**: 弱い (= Stage C stress 観測 data が取れるが、 step 2 切替判断には他要素 (cross_pair / legacy gate calibration) も必要)
- **C_stress canonical_gate_pass** は mission 判定にも切替判定にも使わない (= § 1.5 切替誘因ガード)

---

## 4. 実装方針 (概要)

### 4.1 変更ファイル候補

1. `src/alpha_factory/stage_gate.py`:
   - `evaluate_stage_c` の stress 区画 (= L1385-1442) に dual-path 配線追加 (= 別 try で物理分離、 約 35 行追加)
2. `tests/alpha_factory/test_stage_gate_canonical_dual_path.py` (= 43 ケース) に Stage C stress 用 test 追加:
   - regression 0 (= 既存 stress_payload / reasons 完全不変)
   - log isolation (= canonical raise / log helper raise 時 stress 経路不変)
   - propagation (= disabled mode で skip)
   - log content (= stage='C_stress' で 1 entry / genome、 fold key 不在)
   - max_spread_bps is None で C_stress entry が emit されない (= skip 整合)
   - stress 例外時に C_stress entry が emit されない
   - golden 値固定 (= 1 ケース)

### 4.2 影響範囲

- stage_gate.py で計算量 +1 calc/genome (= Stage C stress 区画で canonical 計算 1 回)
- 既存 BacktestResult の trade / equity_curve がそのまま reuse される (= stress backtest は 1 回のみ)
- archive Parquet schema 不変 (= sidecar 非添付)
- helper シグネチャ変更なし (= step 1.6 で確立した optional kwarg `fold_index=None` をそのまま使う、 C_stress では None default)

### 4.3 LOG_ONLY 維持

step 1.7 では LOG_ONLY 維持 (= 既存判定経路完全不変、 判定結果回帰 0)。 FAIL_CLOSED 切替は step 2 以降。

### 4.4 メモリ概算 (= 低リスク仮説、 上限保証ではない)

stress backtest は **base と同じ holdout 60d** の bars (= M1 で最大 86,400 bars、 セッション内 trim 後 ~60K bars 想定)。 step 1.5 Stage C base と同等規模:
- BarEquitySeries: ~5-7 MB (object overhead 込)
- TradeRecord tuple: <0.5 MB
- business_day_universe / CanonicalFiveResult 派生オブジェクト: <50 KB
- per-stress 追加 RSS: **base と同等オーダーで 3GB/worker を大きく下回る見込み** (= 上限保証ではなく低リスク仮説、 Round 1 [Warning] § 7 反映)
- 6 worker 並列 worst case: 概算 ~36 MB / 全体 (= step 1.5 で同等規模を観測済)
- **実測判断**: acceptance B2 (= smoke 5 Run の `/usr/bin/time -l`) で確証 (= 設計時点の概算は楽観的可能性、 実測結果を本判断に使う)

### 4.5 stage_label 命名

`"C_stress"` で C_base と区別。 § 4.6 ログ命名規約 SSOT に追記:

| 評価対象 | stage_label | step |
|---|---|---|
| Stage C base evaluation | `C_base` | step 1.5 |
| **Stage C spread stress backtest (本)** | **`C_stress`** | **step 1.7** |
| Stage C cross-pair (ii-lite) shadow | `C_cross_pair` | step 1.8 以降 |

---

## 5. 制約・前提

### 5.1 前提表 (= 4 段階分解、 step 1.6 と同型)

| 前提 | 状態 | 検証方法 / Out-of-scope 理由 |
|---|---|---|
| **(a) Verified — 既存コード / テストで固定済** | | |
| `canonical_adapter.py` の helper が UTC-aware datetime 契約に依存 | **Verified** | step 1 / 1.5 / 1.6 で実装・テスト済 (= 既存 43 ケース PASS) |
| `_try_evaluate_canonical_five_safe` / `_log_canonical_dual_path` は Stage A / B_IS / B_fold / C_base で正常動作 | **Verified** | step 1.5 / 1.6 で再利用済、 既存 43 ケース PASS |
| `_log_canonical_dual_path` は `fold_index=None default` で動作 (Stage A / B_IS / C_base 既存 caller) | **Verified** | step 1.6 で optional kwarg + None default、 既存 caller で動作確認済 |
| **(b) Inferred — 同型 pattern からの推論、 step 1.7 で実証検証必要** | | |
| `_log_canonical_dual_path(stage_label="C_stress", fold_index=None)` で C_stress entry を SSOT 上正式に出力可能 | **To Verify in step 1.7** | Round 1 [Warning] § 8 反映で `Verified` から降格。 helper docstring に C_stress を追記し、 acceptance test で no-fold log 契約確認 |
| **(c) Unverified — step 1.7 で検証** | | |
| Stage C stress 区画で adapter / thresholds が **crash なく動く** | **To Verify in step 1.7** | acceptance test (= C_stress dual-path test) |
| stress 例外時 / max_spread_bps is None で C_stress dual-path 行が emit されない (= `dual_path` event + `canonical_five.skipped` event 両者) | **To Verify in step 1.7** | skip 整合 acceptance test (C5) |
| 物理隔離が rigorous (= dual-path 例外で stress_payload / reasons 不変) | **To Verify in step 1.7** | log isolation test (= deep equality 比較、 D1/D3) |
| **(d) False / Out-of-scope — step 1.7 では達成しない** | | |
| step 2 の前提条件「全 Stage 全評価軸の canonical 観測」 | **False / 未達** | Stage C cross_pair (ii-lite) は依然として未観測、 step 1.7 単独では step 2 を block しない |
| Stage C cross_pair (ii-lite) canonical 観測 | **Out-of-scope** | step 1.8 以降、 mission 必須軸 |
| canonical 5 metrics の数値が legacy / stress hard gate と calibration 整合 | **Out-of-scope** | step 1.7 では健全性確認のみ。 stress hard gate との対応付けは step 2 か別 step |
| C_base 対 C_stress の cross-stage diff (= sharpe_degradation の canonical 版) を dual-path log entry 単独で観測 | **False / 未達** | dual-path log は同 stage 内 `legacy - canonical` のみ、 cross-stage 比較は後段 join が必要 |

### 5.2 制約

- adapter 改変禁止 (= step 1 で凍結)
- helper シグネチャ変更なし (= step 1.6 で確立した `fold_index=None` default を再利用)
- 既存 `evaluate_stage_c` の戻り `StageResult` schema 不変 (= archive 互換、 stress_payload 全件不変)
- canonical sidecar は payload 非添付 (= archive Parquet schema 不変)
- LOG_ONLY mode で既存判定完全不変
- live_criteria 不変

### 5.3 Acceptance Criteria

**A. 判定結果回帰 0 (必須、 deep dict comparison)**
- [A1] Stage C の `StageResult.passed` / `reason_codes` / `metrics["payload"]` (= base + stress + cross_pair 全件) が canonical 配線追加で 1 byte も変化しない (= phase2_canonical_metrics_mode `log_only` vs `disabled` で完全一致)
- [A2] archive Parquet schema 完全不変
- [A3] GA fitness 不変
- [A4] Stage A / Stage B IS / Stage B fold / Stage C base の dual-path log は step 1.6 と完全一致 (= 既存 43 ケース全 PASS で確認)

**B. 運用回帰検証**
- [B1] dual-path log が Stage C stress で crash なく出力 (= max_spread_bps is None でない場合のみ)
- [B2] smoke 5 Run で peak RSS が worker 3 GB budget 内 (= Stage C base と同等規模、 低リスク仮説)
- [B3] smoke 5 Run の所要時間が step 1.6 比 ±20% 以内
- [B4] dual-path log が legacy log (= stage_c.stress_failure) と独立出力

**C. legacy 比較可能性 + 識別子契約**
- [C1] dual-path log の `stage` field が `"C_stress"` で正しく区別可能
- [C2] `legacy_*` / `canonical_*` field が同 log entry に共存
- [C3] `interpretation_note="direction_monitoring_only"` が継承
- [C4] **C_stress 識別子契約**: `(stage, genome)` 2 つの kwargs key で一意特定可能 (= 1 entry / genome、 fold key 不在)
- [C5] C_stress log は `max_spread_bps is None` または stress 例外時には emit されない (= **`stage_gate.canonical_five.dual_path` event と `stage_gate.canonical_five.skipped` event の両者** が `stage="C_stress"` で 0 件、 `stage_c.stress_failure` WARN log 出力時も C_stress dual-path 行は 0 件、 Round 1 [Warning] § 5 反映で強化)

**D. 例外隔離契約 (= 物理隔離保証)**
- [D1] dual-path 経路で例外発生しても `stress_payload` (= sharpe / total_pnl / max_drawdown_frac / trade_count / sharpe_degradation / pnl_degradation / skipped) と `reasons` (= spread_stress.* reasons) 完全不変
- [D2] dual-path 経路の例外は `stage_gate.canonical_five.unexpected_failure` または `stage_gate.canonical_five.log_failed` の WARN log のみ、 既存 `stage_c.stress_failure` reason 経路は touch しない
- [D3] monkeypatch で `_try_evaluate_canonical_five_safe` を `stage_label="C_stress"` 限定 raise させても evaluate_stage_c の StageResult が disabled mode と一致 (= `passed` / `reason_codes` / `metrics["payload"]` / `n_bars` の deep comparison、 `wall_time_seconds` 除外)
- [D4] dual-path ブロック内では `stress_payload` / `reasons` を write しない (= 物理隔離契約、 **runtime test では直接検証困難なため D1/D3 の snapshot deep equality 比較で実質担保**、 Round 1 [Warning] § 3 反映)

---

## 6. スコープ外

1. **Stage C cross_pair (ii-lite) dual-path**: mission 必須軸、 step 1.8 以降で扱う
2. **canonical 5 軸ベース判定** (= LOG_ONLY → FAIL_CLOSED 切替): step 2 以降
3. **stage_bc_evaluator 統合**: B Phase 2 step 2
4. **archive Parquet schema 拡張**: 後続別 step
5. **C_base / C_stress diff の calibration 解釈**: 別計画 (= run/genome 横断 n>30 後)
6. **canonical 5 metrics の数値妥当性判定**: step 1.7 では「crash なく動く」のみ確認

---

## 7. リスク

| リスク | 影響 | 緩和 |
|---|---|---|
| dual-path 経路の例外で stress_payload / reasons を巻き込む | 高 | step 1.6 と同型 物理隔離 (= 別 try ブロック)、 acceptance D1-D4 で完全防御 |
| `max_spread_bps is None` のときに dual-path 行が誤って emit される | 中 | dual-path 配線を `else` ブランチ内 + `stress_bt is not None` ガードで二重防御、 acceptance C5 で確認 |
| stress 例外時に bt が無効値で dual-path に渡って adapter ValueError | 高 | outer try の except 句で `stress_bt = None` のまま、 `stress_bt is not None` ガードで dual-path skip、 helper 内部 try でも catch (= 多層) |
| log volume 増加 (1 entry/genome) で log file 肥大 | 低 | structlog filter で観測 only run / production run で出力レベル切替可能、 acceptance B3 で計測 |
| C_stress diff を C_base 代理指標と誤解釈 | 中 | § 2.4 collider bias 注記 + § 2.5 sharpe 読み替え表 (= 3 種 sharpe の混同防止)、 解釈は run/genome 横断 n>30 後 |

---

## 8. 7 step segmentation 全体俯瞰 (= 進捗反映)

| step | 内容 | 統合先 module | 状態 |
|---|---|---|---|
| step 1 ✨ | canonical_metrics → main flow (= Stage A dual-path) | canonical_metrics | **完了** (commit 9bc6a02) |
| step 1.5 ✨ | Stage B IS + Stage C base dual-path | (stage_gate.py のみ) | **完了** (commit 6276d58) |
| step 1.6 ✨ | Stage B per-fold dual-path | (stage_gate.py のみ) | **完了** (commit 1dadc8b) |
| **step 1.7 (本)** | Stage C stress dual-path 拡張 | (stage_gate.py のみ) | **概念設計 Round 2 APPROVED、 詳細設計着手中** |
| step 1.8 | Stage C cross_pair (ii-lite) dual-path | (stage_gate.py + cross_pair) | 後続 (mission 必須軸) |
| step 2 | stage_bc_evaluator → main flow | stage_bc_evaluator | 後続 |
| step 3-7 | (詳細はハンドオフ § 4) | ... | 後続 |

---

## 9. この設計に効く事実 (= docs/devnotes 要点要約)

### 9.1 step 1.6 完了 handoff (`devnotes/20260503-2155-B-step1.6-complete-handoff/handoff.md`)
- step 1.6 で 4 系列 (A / B_IS / B_fold / C_base) の dual-path 観測点を確立
- 「ゆっくり・確実に」原則で step 2 (規模 大) より先に観測拡張を優先
- C_stress / C_cross_pair は step 1.5 § 4.6 で将来予約済

### 9.2 step 1.5 詳細設計 (`devnotes/20260503-1446-B-phase2-step1.5-stage-bc-dual-path/detailed-design.md`)
- 物理隔離 pattern (= 別 try ブロック) は step 1.6 で同型成立
- stage_label SSOT は § 4.6 で明文化、 C_stress / C_cross_pair が step 1.5 で予約済

### 9.3 step 1.6 詳細設計 (`devnotes/20260503-2049-B-phase2-step1.6-stage-b-per-fold-dual-path/detailed-design.md`)
- 物理隔離 (= legacy 計算と dual-path を別 try) で例外時に既存 payload を絶対変えない
- `_log_canonical_dual_path(fold_index: int | None = None)` で全 stage 横断使用可能
- B_fold で fold_index 必須 (= ValueError fail-fast)、 他 stage は None default

### 9.4 stage_gate.py 現行構造 (= 着手前調査)
- evaluate_stage_c stress 区画: stage_gate.py:1385-1442
- stress backtest: `bars_holdout` + `stress_config = replace(backtest_config, max_spread_bps=new_max)` で再 backtest
- `bt = compute_metrics(...)` 後に `s_sharpe` / `s_total_pnl` / `s_trade_count` 算出
- skip 経路: `max_spread_bps is None` (= legacy skip) と stress 例外時 (= `stress_payload["skipped"]=True` + `spread_stress_skipped` reason)

### 9.5 git log の関連
- `1dadc8b Merge branch 'todo/T084'` (= step 1.6 main commit)
- `7c9c06d feat(B step 1.6): Stage B per-fold dual-path 配線追加`
- `6276d58 Merge branch 'todo/T083'` (= step 1.5 main commit)

---

## 10. 参考資料

- step 1.5 概念設計 (Round 3 APPROVED): `devnotes/20260503-1446-B-phase2-step1.5-stage-bc-dual-path/conceptual-design.md`
- step 1.5 詳細設計 (Round 4 APPROVED): `devnotes/20260503-1446-B-phase2-step1.5-stage-bc-dual-path/detailed-design.md`
- step 1.6 概念設計 (Round 2 APPROVED): `devnotes/20260503-2049-B-phase2-step1.6-stage-b-per-fold-dual-path/conceptual-design.md`
- step 1.6 詳細設計 (Round 2 APPROVED): `devnotes/20260503-2049-B-phase2-step1.6-stage-b-per-fold-dual-path/detailed-design.md`
- step 1.6 完了 handoff: `devnotes/20260503-2155-B-step1.6-complete-handoff/handoff.md`
- step 1.6 main commit: `1dadc8b Merge branch 'todo/T084'`
- canonical_adapter.py (凍結): `src/alpha_factory/canonical_adapter.py`
- stage_gate.py (拡張対象): `src/alpha_factory/stage_gate.py:1385-1442` (stress 区画)
- 既存 test: `tests/alpha_factory/test_stage_gate_canonical_dual_path.py` (= 43 ケース、 step 1.7 で +n ケース追加予定)
