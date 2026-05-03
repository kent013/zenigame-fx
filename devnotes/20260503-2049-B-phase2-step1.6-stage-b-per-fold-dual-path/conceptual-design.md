# 概念設計: B Phase 2 切替コミット step 1.6 — Stage B per-fold dual-path 拡張

**作成日時**: 2026-05-03 20:49 JST (Round 2 改訂: 2026-05-03 21:10 JST)
**起源**: B Phase 2 切替コミット step 1.5 (= Stage B IS / Stage C base dual-path 配線、 main commit 6276d58) 完了後の段階的拡張
**性質**: step 1.5 で確立した dual-path helper / adapter を **Stage B per-fold OOS (= 5 fold) にも適用** (= main flow の canonical_metrics 観測値生成範囲を per-fold 単位まで拡大)
**位置付け**: cascade port v2 Phase 2 切替コミット 7 step segmentation の **step 1.6** (= 任意・有益な観測拡張、 step 2 を block しない)
**status**: 概念設計 Round 2 (= Codex Round 1 CHANGES_REQUESTED 反映済)

---

## 0. Round 1 → Round 2 改訂対応マトリクス

| Round 1 指摘 | 対応 |
|---|---|
| § 1 [Critical] step 2 前提完全充足主張は過剰 (= Stage C cross_pair 未観測) | scope を「Stage B side calibration data 拡充」に下げる。 「step 2 前提を完全充足」 削除 |
| § 3 [Critical] dual-path が fold outer try 内にあり例外時に fold 判定干渉 | per-fold dual-path 配線を **legacy fold 計算 (= fold_sharpe / fold_reason 確定) の後** に **別 try ブロック** で分離。 canonical 失敗は WARN のみ、 fold_reason は不変 |
| § 8 [Critical] 前提表混在 (Verified / Unverified / False) | 前提表を 3 段階分解: (a) threshold 5 回構築 equality = Verified、 (b) wf_test_days への意味整合 = Unverified、 (c) step 2 全評価軸充足 = False / 未達 (= cross_pair 残) |
| § 4 [Warning] canonical / legacy gate は別物 (collider bias) | § 4.5 に明記、 解釈は run/genome 横断 n>30 後 |
| § 4 [Warning] C7 sample size | 「解釈単位は run 横断・genome 横断の集計で n>30 を満たした後」明記 |
| § 5 [Warning] log SSOT 識別子曖昧 | `stage='B_fold'` + `genome` + `fold` の 3 つで一意特定、 fold 欠落は bug 扱い |
| § 5 [Suggestion] 運用影響根拠が弱い | acceptance B3 を「dual-path log bytes / wall time / WARN 率」で監査可能化 |
| § 7 [Suggestion] メモリ概算楽観 | 「上限保証」 → 「低リスク仮説」 に文言を弱める |
| § 8 [Warning] B_fold 専用 test 不足 | acceptance に「`canonical_skipped=True` path / `fold` 欠落 / 5 fold 全件区別」 専用 test 3 本以上追記 |
| § 9 [Suggestion] 既存 approved 文書の制約引用不足 | § 9 で step 1.5 / handoff の制約をそのまま引用、 差分主張を最小化 |
| § 1 [Warning] handoff の step 2 推奨と緊張 | 「step 2 を block する必須 step」 ではなく 「任意だが有益な観測拡張 step」 に戻す |
| § 2 [Warning] 切替誘因の禁止事項 7-1 ガード | 「B_fold pass/fail だけで step 2 切替判断しない」「live_criteria/評価期間不変」を本文明文化 |

---

## 1. 背景・課題

### 1.1 step 1.5 完了時点の状態

step 1.5 (= main commit 6276d58) で:
- `evaluate_stage_a` (= Stage A 60d 評価窓) に dual-path 配線済 (step 1)
- `evaluate_stage_b` の **IS monitor 区画** (= bars_18m 全体 backtest) に dual-path 配線済 (step 1.5)
- `evaluate_stage_c` の **base evaluation 区画** (= bars_holdout 60d backtest) に dual-path 配線済 (step 1.5)
- canonical_metrics 経路は 3 評価点 (= A / B_IS / C_base) で観測値生成可能

**Stage B per-fold OOS は未配線**: `evaluate_stage_b` の per-fold 区画 (= stage_gate.py L892-L948 の 5 fold ループ) では各 fold の test 区間で legacy `BacktestMetrics` のみ生成され、 canonical 5 軸は計算されない。

### 1.2 課題

- **観測範囲不足**: Stage B の **本質的な評価軸** (= per-fold OOS の median + positive_fold_ratio) で canonical 5 軸を観測できない
- **per-fold collider bias 抑止データ不足**: B_IS (= Stage B 18m 全体 IS) は per-fold OOS 集約結果と性質が異なるため、 B_IS diff を per-fold OOS の代理指標として解釈すると collider bias (= step 1.5 § 4.6 で警告済)。 per-fold 単位の dual-path 観測がないと、 Stage B side の calibration data が不完全

### 1.3 step 1.6 のスコープ確定

**step 1.6 では Stage B per-fold OOS の dual-path 観測拡張のみ** (= 任意だが有益な観測拡張、 step 2 を block しない):
- adapter 改変禁止 (= step 1 で凍結、 同じ helper を再利用)
- step 1.5 で確立した helper (`_try_evaluate_canonical_five_safe` / `_log_canonical_dual_path` / `_build_canonical_thresholds_for_window`) を完全再利用
- per-fold thresholds は **per-fold で個別構築** (= 同 live_criteria + 同 wf_test_days で同じ thresholds、 過度な複雑化禁止)
- stage_label="B_fold" + fold_index で B_IS と log 系列を分離 (= § 4.6 ログ命名規約 SSOT 準拠、 step 1.5 で commitment 済)
- 既存判定経路完全不変 (= regression 0、 archive Parquet schema 不変)
- **重要 (Round 1 [Critical] § 3 反映)**: per-fold dual-path 配線は **legacy fold 計算 (= fold_sharpe / fold_reason 確定) の後** に **別 try ブロック** で分離する (= dual-path 例外が fold 判定 (= n_fold_unavailable / oos_sharpes / median_oos_sharpe / positive_fold_ratio) に絶対干渉しない物理隔離)

= step 1.6 完了後の状態:
- main flow が canonical 5 metrics の観測値を **Stage A / Stage B IS / Stage B fold (5 fold) / Stage C base の 4 評価点** で生成可能 (= per-fold は 5 entry/genome なので合計 8 entry/genome 観測点)
- **Stage B side の calibration data 拡充** (= 注: step 2 前提を完全充足するわけではない、 Stage C cross_pair (ii-lite) は依然として未観測で残る)

### 1.4 切替誘因のガード (= Round 1 [Warning] § 2 反映)

step 1.6 完了後、 観測 only の B_fold dual-path log を切替判断の根拠にしないこと:
- B_fold pass/fail 分布だけで step 2 (= 判定切替) のタイミングを決めない
- live_criteria 不変 (= 禁止事項 #4)、 評価期間 (= wf_test_days / wf_train_days) 不変 (= 禁止事項 #1)
- 解釈単位は **run 横断 / genome 横断の集計で n>30 を満たした後** のみ (= C7 sample size guard、 ただし n>30 は **解釈開始の最低条件であり、 因果結論の十分条件ではない**、 Round 2 [Warning] 反映)
- canonical / legacy gate は同じものを見ていない (= § 4.5 で詳述)、 直接比較は collider bias を踏む

---

## 2. 改善アイデア

### 2.1 per-fold dual-path 配線 (= 物理隔離版、 Round 1 [Critical] § 3 反映)

`evaluate_stage_b` の per-fold OOS 区画 (= stage_gate.py L892-L948) の `for i, (_train_bars, test_bars) in enumerate(folds)` ループ内に dual-path 配線を追加するが、 **legacy fold 計算 (= fold_sharpe / fold_reason 確定) の後** に **別 try ブロック** で分離する。 これにより dual-path 例外が **絶対に** legacy fold 判定を変えない物理隔離を実現:

```python
for i, (_train_bars, test_bars) in enumerate(folds):
    fold_sharpe: float | None = None
    fold_reason: FoldUnavailableReason | None = None
    # legacy fold 評価用に保持 (dual-path 経路で参照)
    fold_bt: BacktestMetrics | None = None
    fold_trades: list[BrokerTrade] | None = None
    fold_equity: list[tuple[datetime, Decimal]] | None = None

    # === 既存 legacy fold 計算 (= fold_sharpe / fold_reason 確定、 完全不変) ===
    try:
        if _aux_supports_with_aux:
            aligned_for_fold = aux_bundle.align_to(test_bars)
            evaluator_for_fold = primitive_evaluator.with_aux(...)
        else:
            evaluator_for_fold = primitive_evaluator
        strategy = DslStrategy(genome, evaluator_for_fold)
        broker = MockBroker(instrument_meta=meta)
        res = run_backtest(test_bars, strategy, broker, backtest_config)
        bt = compute_metrics(
            res.trades, res.equity_curve,
            trade_count_min_for_sharpe=fold_min_trade_count,
        )
        fold_sharpe = (
            float(bt.trade_sharpe_raw) if bt.trade_sharpe_raw is not None else None
        )
        if fold_sharpe is None:
            fold_reason = _classify_fold_unavailable(...)
        # dual-path 用に legacy 結果を保持 (= 別 try に渡す)
        fold_bt = bt
        fold_trades = res.trades
        fold_equity = res.equity_curve
    except Exception as exc:
        logger.warning(
            "stage_b.fold_failure", genome=genome.name, fold=i,
            error=str(exc), error_type=type(exc).__name__,
        )
        fold_sharpe = None
        fold_reason = FoldUnavailableReason.FOLD_EXCEPTION

    # === 新規 per-fold dual-path (= 別 try で完全分離、 fold_sharpe / fold_reason に絶対干渉しない) ===
    # legacy fold 計算が成功した場合のみ dual-path 観測を試みる (= 失敗時は skip、
    # 既存 fold_failure WARN log で legacy 経路の状態は記録済)
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
                    stage="B_fold", fold=i, genome=genome.name,
                    error=str(log_exc), error_type=type(log_exc).__name__,
                )
        except Exception as canonical_exc:
            # _try_evaluate_canonical_five_safe は本来 no-raise だが、
            # 想定外例外 (= signature 不整合 / monkeypatch / etc) で raise しても
            # ここで catch、 fold_sharpe / fold_reason は絶対変えない
            logger.warning(
                "stage_gate.canonical_five.unexpected_failure",
                stage="B_fold", fold=i, genome=genome.name,
                error=str(canonical_exc), error_type=type(canonical_exc).__name__,
            )
    # ... (以降 既存 fold_sharpe / fold_reason ハンドリング、 完全不変)
```

**重要設計判断** (= Round 1 [Critical] § 3 反映):
- legacy fold 計算と dual-path 観測を **2 つの別 try ブロック** で分離
- legacy fold 計算成功時のみ dual-path を試みる (= 失敗時は legacy WARN log のみ)
- dual-path の二重 try (= helper 例外 + log 例外) で多層防御
- `fold_sharpe` / `fold_reason` は legacy 計算の try 内のみで決定、 dual-path で絶対変えない

### 2.2 per-fold thresholds 構築方法 (= per-fold 個別構築 採用)

**Option 比較**:

| Option | 内容 | pros | cons |
|---|---|---|---|
| **Option 1 (採用)**: per-fold 個別構築 | 各 fold で `_build_canonical_thresholds_for_window(live_criteria, window_days=wf_test_days)` を呼出 | helper 再利用、 過度な複雑化禁止、 値レベルで完全一致保証 (= 同入力 → 同出力、 算術 deterministic) | 計算重複 (= 5 fold で 5 回 thresholds 構築、 ただし算術 4 行で軽量) |
| Option 2: pooled で 1 つ構築 | per-fold ループ外で 1 回構築、 全 fold で共用 | 計算重複なし | helper シグネチャ変更必要、 「過度な複雑化禁止」抵触 |

**設計判断**: **Option 1 採用**。 同 live_criteria + 同 wf_test_days で thresholds は値レベル完全一致 (= deterministic)、 計算重複は軽量 (= 5 fold × 4 行)、 helper 再利用が SSOT 維持の rationale。

**rationale 限定** (= Round 1 [Warning] § 4 反映):
- Option 1 採用の根拠は「**deterministic equality + SSOT 再利用**」のみ
- 「**各 fold の実窓 (= observed-day fold) への意味整合**」は **未検証前提**。 fold 分割は observed-day ベース、 threshold scaling は `window_days=wf_test_days` の線形倍率で、 両者の意味整合は別軸検討
- step 1.6 では Option 1 で「観測値が deterministic に出る」までを達成、 「観測値が legacy fold gate と同じ意味で解釈できる」かは別 step

### 2.3 _log_canonical_dual_path への fold_index 追加

step 1.5 まで `_log_canonical_dual_path(stage_label, genome_name, legacy, canonical)` で 4 引数。 step 1.6 では per-fold 識別のため `fold_index: int | None = None` を追加 (= optional kwarg、 既存 caller 互換性維持):

```python
def _log_canonical_dual_path(
    *,
    stage_label: str,
    genome_name: str,
    legacy: BacktestMetrics,
    canonical: CanonicalFiveResult | None,
    fold_index: int | None = None,  # 新規: per-fold dual-path 用
) -> None:
    """dual-path 結果 (legacy + canonical) を構造化 log に出力.

    fold_index が指定された場合は logger kwargs key `fold` に追加。
    Stage A / Stage B IS / Stage C base では None (= log に fold key なし)。
    Stage B fold では fold_index=i (= 5 fold 別 entry の一意特定用)。
    """
    ...
    if fold_index is not None:
        log_kwargs["fold"] = fold_index
    logger.info("stage_gate.canonical_five.dual_path", **log_kwargs)
```

→ helper 改変は **後方互換** (= optional kwarg 追加のみ、 既存 Stage A / Stage B IS / Stage C base caller は変更不要)。

### 2.4 Stage B per-fold dual-path のスコープ整理

- **対象**: per-fold OOS の各 fold (= 5 fold それぞれ) で独立 dual-path 観測
- **対象外**: 
  - per-fold thresholds の **fold 間統一構築** (= Option 2、 step 1.6 で採用しない)
  - per-fold 結果の集約レイヤーで canonical 値計算 (= 既存 oos_sharpes / median_oos / positive_fold_ratio とは独立、 各 fold 単位の観測のみ)

---

## 3. 期待効果

### 3.1 直接的 (= descriptive observation only、 Round 1 [Warning] § 4 反映)

- main flow が canonical 5 metrics の **観測値を per-fold (= Stage B 5 fold それぞれ) で descriptive に生成可能** に
- step 1.5 で警告した B_IS diff の collider bias を、 per-fold 単位の直接観測で「diff 観測手段としては」抑止可能 (= ただし legacy / canonical gate の意味整合は § 4.5 で別軸)
- Stage B の **2 系列 (= B_IS 1 entry + B_fold 5 entries)** で adapter / helper の凍結検証が完了 (= crash しないこと、 値が deterministic に出ること、 Round 2 [Suggestion] 反映で表現明確化)

### 3.2 間接的 (= 主張を最小化、 Round 1 [Critical] § 1 反映)

- **Stage B side calibration data 拡充** (= step 2 前提を「完全充足」 ではなく 「partial 拡充」)
- per-fold thresholds 構築方法 (Option 1) の crash テストデータが取れる
- step 2 着手前により充実した観測 data が揃う (= ただし Stage C cross_pair (ii-lite) は依然として未観測で残る、 step 1.6 単独では step 2 前提を block しない)

### 3.3 live_criteria 達成への寄与

- **直接寄与**: なし (= 観測のみ、 判定ロジック完全不変、 GA fitness 不変)
- **間接寄与**: 弱い (= per-fold 観測 data が取れるが、 step 2 切替判断には他要素 (Stage C cross_pair) も必要)

### 3.4 calibration data 取得計画

step 1.6 完了後の観測点 (per-genome):
- Stage A: 1 entry
- Stage B IS: 1 entry
- Stage B fold: 5 entries (= step 1.6 で追加)
- Stage C base: 1 entry
- **合計**: 8 entries / genome

GA Run 30 generations × 50 individuals × 6 pairs = 9000 genomes/Run → 72,000 dual-path log entries/Run。 structlog で stage / fold key で filtering 可能、 観測 only mode で問題なし。

---

## 4. 実装方針 (概要)

### 4.1 変更ファイル候補

1. `src/alpha_factory/stage_gate.py`:
   - `_log_canonical_dual_path` に `fold_index: int | None = None` 引数追加 (= 後方互換)
   - `evaluate_stage_b` の per-fold OOS ループ内 (= L892-L948) に dual-path 配線追加
2. `tests/alpha_factory/test_stage_gate_canonical_dual_path.py` に Stage B per-fold 用 test 追加:
   - regression 0 (= legacy payload 完全不変、 5 fold すべての oos_sharpes / reason_counts が log_only vs disabled で完全一致)
   - log isolation (= canonical 例外時 / log helper 例外時 legacy 経路不変)
   - propagation (= disabled mode で canonical skip)
   - log content (= stage='B_fold' + fold=0..4 で 5 entry 出力確認、 § 4.6 ログ命名規約 SSOT)
   - ゴールデン回帰 (= 各 fold で fixture-locked 値一致、 1 entry 程度の代表 fold で確認)
   - 後方互換 (= 既存 _log_canonical_dual_path caller (Stage A / B_IS / C_base) が引き続き動作)

### 4.2 影響範囲

- stage_gate.py で計算量 ~2x in per-fold loop (= 5 fold × 1 canonical 計算)
- 既存 `bt = compute_metrics(...)` の `res.trades` / `res.equity_curve` / `test_bars` をそのまま reuse、 backtest 自体は 1 回のみ
- archive Parquet schema 不変 (= sidecar 非添付)
- StageGateConfig schema 不変
- helper シグネチャ変更は **後方互換** (= optional kwarg 追加のみ、 既存 caller 改変不要)

### 4.3 LOG_ONLY 維持

step 1.6 では LOG_ONLY 維持 (= 既存判定経路完全不変、 判定結果回帰 0)。 FAIL_CLOSED 切替は step 2 以降。

### 4.4 メモリ制約 概算

per-fold の bars は test_bars (= wf_test_days=20 日 × M1 想定 = 28800 bars max、 セッション内 trim ~70% = ~20000 bars):

- `BarEquitySeries` per fold: ~80 byte/point × ~20000 = **~1.6 MB/fold**
- `TradeRecord` tuple: ~250 byte/trade × 数百 trade = **<0.5 MB/fold**
- `business_day_universe`: 3 bucket × ~14 business days × 28 byte = **<2 KB/fold**
- `CanonicalFiveResult`: <10 KB/fold

**1 fold あたり追加メモリ ~2 MB / worker**。 5 fold 連続実行で peak は ~2 MB (= GC で fold 間 release)、 同時保持しない。

**6 worker 並列 worst case**: 6 × ~2 MB ≈ **~12 MB**。 step 1.5 (Stage B IS 18m, +~50 MB / worker) より遥かに小さい。 budget 余裕大。

### 4.5 canonical / legacy gate は別物 (= collider bias 注記、 Round 1 [Warning] § 4 反映)

**Fact**: canonical 側 trade_count threshold は `live_criteria.trade_count_min × (wf_test_days / 730)` で window scaling される (= 20/730 で大幅に縮小)。 legacy 側の fold-Sharpe 可用性 guard は `stage_b_fold_trade_count_min=10` で別軸の閾値。

**Interpretation (collider bias 警告)**:
- **canonical fold gate** (= window-scaled trade_count + canonical 5 軸) と **legacy fold gate** (= fold_sharpe + median_oos / positive_fold_ratio) は **同じものを見ていない**
- per-fold dual-path log で出る「canonical pass/fail」と「legacy fold_sharpe」 は **意味が別**
- これらの差を「threshold 妥当性」「切替準備完了」と因果解釈すると collider bias を踏む
- step 1.6 の B_fold dual-path log は **descriptive observation only**、 解釈側で run/genome 横断 n>30 を満たした後の集計でのみ評価する

### 4.7 Stage B per-fold log 命名規約 (= 識別子 SSOT、 Round 1 [Warning] § 5 反映)

step 1.5 § 4.6 ログ命名規約 SSOT に従い:

| stage_label | 評価対象 | step | 補足 |
|---|---|---|---|
| `A` | Stage A 評価窓 (60d) | step 1 | 単一窓 |
| `B_IS` | Stage B 18m 全体 IS monitor | step 1.5 | 全体 IS の方向性監視 |
| `B_fold` (本) | Stage B per-fold OOS | step 1.6 | + `fold` kwargs key で 5 fold 識別 |
| `C_base` | Stage C base evaluation (holdout 60d) | step 1.5 | base のみ |
| `C_cross_pair` | Stage C cross-pair (ii-lite) shadow | step 2 以降 | mission 必須軸 |

各 dual-path log には `interpretation_note="direction_monitoring_only"` を継承 (= step 1 で導入済)。

**識別子契約 SSOT** (= Round 1 [Warning] § 5 反映):
- `B_fold` log entry は `stage="B_fold"` + `genome=<genome.name>` + `fold=<int 0..4>` の **3 つの kwargs key** で一意特定可能でなければならない
- `fold` 欠落は **bug 扱い** (= acceptance test で fail させる)
- downstream の grep / 集計は `(stage, genome, fold)` を key として使う契約

---

## 5. 制約・前提

### 5.1 前提表 (= Round 1 [Critical] § 8 反映で 3 段階分解)

| 前提 | 状態 | 検証方法 / Out-of-scope 理由 |
|---|---|---|
| **(a) Verified** | | |
| `canonical_adapter.py` の helper が UTC-aware datetime 契約に依存 | **Verified** | step 1 で実装・テスト済 (= 既存 21 + 21 = 42 ケース PASS) |
| `_try_evaluate_canonical_five_safe` / `_build_canonical_thresholds_for_window` は全 Stage 横断使用可能 | **Verified** | step 1.5 で Stage B IS / Stage C base で再利用済 |
| 同 live_criteria + 同 wf_test_days で thresholds は 5 fold で値レベル一致 | **Verified** | `_build_canonical_thresholds_for_window` は pure 算術 helper、 同入力 → 同出力 deterministic |
| **(b) Unverified — step 1.6 で検証** | | |
| `_log_canonical_dual_path` への `fold_index` optional kwarg 追加が既存 33 caller を壊さない | **To Verify in step 1.6** | acceptance A4 (= 既存テスト全 PASS で確認、 既存 caller は keyword 呼び出しのみ) |
| Stage B per-fold (wf_test_days=20) で adapter / thresholds が **crash なく動く** | **To Verify in step 1.6** | acceptance test (= per-fold dual-path test) |
| Stage B per-fold で peak RSS が worker 3 GB budget 内 | **To Verify in step 1.6** (低リスク仮説) | per-fold は ~2 MB/fold (= 概算、 上限保証ではない、 Round 1 [Suggestion] § 7 反映で文言を弱めた) |
| **(b') Unverified — 別 step で扱う** | | |
| 各 fold の実窓 (= observed-day fold) と `window_days=wf_test_days` 線形 scaling の意味整合 | **Unverified** | 「deterministic equality」は満たすが「意味整合」は別軸。 step 2 以降の calibration で観測する |
| canonical 5 metrics の数値が legacy と意味的に整合 | **Unverified** | canonical / legacy gate は別物 (= § 4.5)、 直接比較は collider bias を踏む |
| **(c) False — step 1.6 では達成しない (= scope 外)** | | |
| step 2 の前提条件「全 Stage 全評価軸の canonical 観測」 | **False / 未達** | Stage C cross_pair (ii-lite) は依然として未観測、 step 1.6 単独では step 2 を block しない |
| Stage C cross_pair (ii-lite) canonical 観測 | **Out-of-scope** | step 2 以降、 mission 必須軸 |
| canonical 5 metrics の数値が legacy と calibration 整合 | **Out-of-scope** | step 1.6 では健全性確認のみ。 calibration 判定は別 step |

### 5.2 制約

- adapter 改変禁止 (= step 1 で凍結、 SSOT 維持)
- 既存 `evaluate_stage_b` の戻り `StageResult` schema 不変 (= archive 互換、 oos_sharpes / unavailable_reason_counts 等 既存 payload 全件不変)
- canonical sidecar は payload 非添付 (= archive Parquet schema 不変、 step 1 / 1.5 と同様)
- LOG_ONLY mode で既存判定完全不変 (= 判定結果回帰 0)
- live_criteria 不変 (= 禁止事項 #4 ガード)
- `_log_canonical_dual_path` の signature 変更は **後方互換のみ** (= 既存 caller を壊さない)

### 5.3 Acceptance Criteria

**A. 判定結果回帰 0 (必須、 deep dict comparison)**
- [A1] Stage B の `StageResult.passed` / `reason_codes` / `metrics["payload"]` (= n_fold / oos_sharpes / median_oos_sharpe / positive_fold_ratio / unavailable_reason_counts / 他全件) が canonical 配線追加で 1 byte も変化しない (= phase2_canonical_metrics_mode `log_only` vs `disabled` で完全一致、 fixed seed × fixed fixture)
- [A2] archive Parquet schema 完全不変
- [A3] GA fitness 不変
- [A4] Stage A / Stage B IS / Stage C base の dual-path log は step 1.5 と完全一致 (= `_log_canonical_dual_path` への optional kwarg 追加が既存 caller の出力を変えない)

**B. 運用回帰検証** (= Round 1 [Suggestion] § 5 反映で監査可能化)
- [B1] dual-path log が Stage B 5 fold それぞれで crash なく出力 (= log isolation test で確認)
- [B2] smoke 5 Run で peak RSS が worker 3 GB budget 内 (= 概算 +~12 MB / worker、 上限保証ではなく低リスク仮説)
- [B3] smoke 5 Run の所要時間が step 1.5 比 ±20% 以内 + dual-path log の bytes / WARN 率 を計測
- [B4] dual-path log が legacy log (= stage_b.fold_failure) と独立出力

**C. legacy 比較可能性** (= Round 1 [Warning] § 5 反映で識別子契約厳格化)
- [C1] dual-path log の `stage` field が `"B_fold"` で正しく区別可能、 `fold` kwargs key (= 0..4) で fold 識別可能
- [C2] `legacy_*` / `canonical_*` field が同 log entry に共存
- [C3] `interpretation_note="direction_monitoring_only"` が継承
- [C4] **識別子契約 SSOT**: `B_fold` log entry は `(stage, genome, fold)` 3 つの kwargs key で一意特定可能。 `fold` 欠落は bug 扱い (= acceptance test で fail)
- [C5] `canonical_skipped=True` path (= helper が None 返り、 enabled=False or canonical 例外) でも `fold` kwargs key は必須

**D. 例外隔離契約** (= Round 1 [Critical] § 3 反映で物理隔離保証)
- [D1] dual-path 経路で例外が発生しても `fold_sharpe` / `fold_reason` / `oos_sharpes_imputed` / `n_fold_unavailable` / `reason_counts` は完全不変
- [D2] dual-path 経路の例外は `stage_gate.canonical_five.unexpected_failure` WARN log のみ、 既存 `stage_b.fold_failure` reason 経路は touch しない
- [D3] monkeypatch で `_try_evaluate_canonical_five_safe` を raise させても evaluate_stage_b の StageResult が disabled mode と一致 (= **`passed` / `reason_codes` / `metrics["payload"]` / `n_bars` の deep comparison、 `wall_time_seconds` は除外**、 Round 2 [Warning] 反映)
- [D4] **dual-path ブロック内では `fold_sharpe` / `fold_reason` / `reason_counts` を write しない** (= 物理隔離契約、 Round 2 [Warning] 反映で詳細設計に明文化)
- [D5] `_log_canonical_dual_path(stage_label="B_fold", fold_index=None)` は **helper 内で `ValueError` raise** (= fold 欠落 bug を fail-fast 化、 Round 2 [Warning] 反映)

---

## 6. スコープ外

1. **Stage C cross_pair (ii-lite) dual-path**: stress test / shadow cross_pair は別軸、 step 1.6 範囲外 (= step 2 以降、 mission 必須軸)
2. **canonical 5 軸ベース判定** (= LOG_ONLY → FAIL_CLOSED 切替): step 2 以降
3. **stage_bc_evaluator (canonical 5 軸 caller) の main flow 統合**: B Phase 2 step 2
4. **archive Parquet schema 拡張** (= canonical metrics 永続化): 後続別 step
5. **per-fold thresholds の pooled 化** (= Option 2): 過度な複雑化禁止で却下
6. **per-fold canonical 結果の median / positive_fold_ratio 集約**: 既存 legacy 集約 (= oos_sharpes 集約) と独立、 集約は step 2 以降
7. **calibration data 数値整合判定**: step 1.6 では「crash なく動く」のみ確認、 別計画

---

## 7. リスク

| リスク | 影響 | 緩和 |
|---|---|---|
| `_log_canonical_dual_path` への `fold_index` 追加で既存 caller 出力変化 | 中 | acceptance A4 (= step 1.5 既存 33 ケース全 PASS) で動作不変保証。 optional kwarg なので signature 変更は後方互換 |
| per-fold dual-path で例外発生 → fold OOS 経路を巻き込む | 高 | step 1 で確立した `_try_evaluate_canonical_five_safe` + log try/except による完全隔離 (= 同 helper 再利用、 例外注入 test で確認) |
| per-fold thresholds 構築の重複計算で時間 overhead | 低 | 算術 4 行で軽量、 5 fold × ~4μs = 微小、 acceptance B3 (smoke 5 ±20%) でガード |
| log volume 5x 増加 (= 5 fold × 1 entry) で log file 肥大 | 低 | structlog の filtering 可能、 stage='B_fold' で観測 only run / production run で出力レベル切替可能 |
| per-fold で wf_test_days=20 という短期間で thresholds がほぼ全て pass しない | 中 (= 観測の解釈側) | step 1.6 では数値妥当性判定しない (= 「crash なく動く」のみ acceptance)。 calibration は別計画 |

---

## 8. 7 step segmentation 全体俯瞰 (= 進捗反映)

| step | 内容 | 統合先 module | 状態 |
|---|---|---|---|
| step 1 ✨ | canonical_metrics → main flow (= Stage A dual-path LOG_ONLY) | canonical_metrics | **完了** |
| step 1.5 ✨ | Stage B IS monitor + Stage C base dual-path 拡張 | (stage_gate.py のみ) | **完了** |
| **step 1.6 (本)** | Stage B per-fold dual-path 拡張 (5 fold × 1 entry) | (stage_gate.py のみ) | **設計 Round 1 中** |
| step 2 | stage_bc_evaluator → main flow | stage_bc_evaluator | 次 |
| step 3-7 | (詳細はハンドオフ § 4) | ... | 後続 |

---

## 9. この設計に効く事実 (= docs/devnotes 要点要約)

### 9.1 step 1.5 完了 handoff (`devnotes/20260503-1652-B-step1.5-complete-handoff/handoff.md`)
- step 1.5 で dual-path 観測点が 3 軸 (A / B_IS / C_base) で揃った
- step 1.5 § 4.6 で B_fold stage_label を将来拡張用に予約済
- step 1.6 を選択肢 A (= 規模 中、 1 step 1 commit リズム維持) として明示

### 9.2 step 1.5 詳細設計 (`devnotes/20260503-1446-B-phase2-step1.5-stage-bc-dual-path/detailed-design.md`)
- helper 入力契約 (§ 5.5 / § 6.5) で `_try_evaluate_canonical_five_safe` の引数仕様明記、 step 1.6 でも同型再利用
- ログ命名規約 SSOT (§ 4.6) で B_fold が将来予約済

### 9.3 stage_gate.py 現行構造 (= 着手前調査)
- evaluate_stage_b per-fold OOS 区画 (L892-L948) は `for i, (_train_bars, test_bars) in enumerate(folds)` で iterate
- 各 fold で独立 backtest → compute_metrics → fold_sharpe 算出
- 入力: test_bars (= wf_test_days 区間)、 res.trades / res.equity_curve、 fold_min_trade_count
- 既存例外ハンドリング (= stage_b.fold_failure) で fold 単位独立隔離あり

### 9.4 canonical_metrics の API
- step 1 / 1.5 で凍結済 helper / adapter は signature 変更なし
- step 1.6 では `_log_canonical_dual_path` に `fold_index: int | None = None` optional kwarg 追加のみ (= 後方互換)

### 9.5 git log の関連
- `6276d58 Merge branch 'todo/T083'` (= step 1.5 main commit)
- `1f85f4e feat(B step 1.5): Stage B IS monitor + Stage C base に dual-path 配線追加`
- `15a9803 refactor(B step 1.5): rename _build_stage_a_canonical_thresholds → _build_canonical_thresholds_for_window`

---

## 10. 参考資料

- step 1 概念設計: `devnotes/20260503-1024-B-phase2-step1-canonical-metrics/conceptual-design.md`
- step 1.5 概念設計: `devnotes/20260503-1446-B-phase2-step1.5-stage-bc-dual-path/conceptual-design.md` (Codex Round 3 APPROVED)
- step 1.5 詳細設計: `devnotes/20260503-1446-B-phase2-step1.5-stage-bc-dual-path/detailed-design.md` (Codex Round 4 APPROVED)
- step 1.5 完了 handoff: `devnotes/20260503-1652-B-step1.5-complete-handoff/handoff.md`
- step 1.5 main commit: `6276d58 Merge branch 'todo/T083'`
- canonical_adapter.py (凍結): `src/alpha_factory/canonical_adapter.py`
- stage_gate.py (拡張対象): `src/alpha_factory/stage_gate.py:892-948`
