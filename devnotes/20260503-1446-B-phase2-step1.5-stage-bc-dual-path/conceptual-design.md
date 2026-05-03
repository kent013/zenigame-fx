# 概念設計: B Phase 2 切替コミット step 1.5 — Stage B IS monitor / Stage C base に dual-path 拡張

**作成日時**: 2026-05-03 14:46 JST (Round 2 改訂: 2026-05-03 15:08 JST、 Round 3 改訂: 2026-05-03 15:18 JST)
**起源**: B Phase 2 切替コミット step 1 (= Stage A dual-path 配線、 main commit 9bc6a02) 完了後の段階的拡張
**性質**: step 1 で確立した dual-path helper / adapter を **Stage B IS monitor + Stage C base evaluation にも適用** (= main flow の **canonical_metrics 観測値生成範囲拡大のみ**)
**位置付け**: cascade port v2 Phase 2 切替コミット 7 step segmentation の **step 1.5** (= step 1 と step 2 の中間、 adapter 凍結のため stage_gate.py のみ拡張)
**status**: 概念設計 Round 3 (= Codex Round 2 CHANGES_REQUESTED 反映済、 Round 3 で APPROVED 目標)

---

## 0. 改訂サマリー (= Codex Round 1 + Round 2 指摘反映)

### Round 1 (CHANGES_REQUESTED) → Round 2 改訂

| Round 1 指摘 | 対応 | 反映先 |
|---|---|---|
| [Critical] step 2 前提主張過剰 | scope を「観測拡張」のみに limit。 step 2 前提条件達成は別 step (= per-fold / cross_pair) に切出 | § 1.3 / § 3 / § 6 |
| [Critical] smoke 5 は calibration 根拠不足 (C7) | smoke 5 を「健全性確認」に限定。 calibration data は実 GA Run (n>>30) で別途取得 | § 3 / § 6 |
| [Critical] メモリ制約評価甘い | peak RSS 概算 § 追加 (= Stage B 18m, BarEquitySeries / TradeRecord サイズ + worker 並列) | § 4.4 |
| [Warning] business_day vs session block ずれ | adapter 仕様表で UTC date 基準を明示 (DST/週跨ぎ含む) | § 4.5 |
| [Warning] regression 0 運用面未証明 | 「判定結果回帰 0」と「運用回帰検証」を分離 acceptance criterion 化 | § 5.4 |
| [Warning] B_IS diff を per-fold OOS 代理にしない | log 命名規約 § 追加 (B_IS / B_fold / C_base / C_cross_pair)、 collider bias 注記 | § 4.6 |
| [Warning] 前提表を 3 列に | Assumed / To Verify in step 1.5 / Out-of-scope の 3 列化 | § 5.1 |
| [Warning] thresholds 構築可能 ≠ 妥当 | acceptance criterion を 2 軸 (= 構築成功 + log での legacy 比較可能性) | § 5.4 |
| [Warning] rename と behavioral wiring 分離 | 実装は **2 commit に分離** (commit A: pure refactor rename / commit B: behavioral wiring) | § 4.1 |
| [Warning] C1 docs/devnotes 要約欠落 | 末尾に 「この設計に効く事実」要約を追加 | § 9 |
| [Suggestion] log 命名規約事前決定 | § 4.6 にログ命名規約 SSOT を明記 | § 4.6 |
| [Suggestion] mission 直接寄与は薄い明文化 | § 3.3 で「直接寄与なし、 falsification データ確保が目的」明記 | § 3.3 |

### Round 2 (CHANGES_REQUESTED) → Round 3 改訂

| Round 2 指摘 | 対応 | 反映先 |
|---|---|---|
| [Critical] Stage A 挙動変更 (= window_days を business day 基準化) は step 1.5 の B/C 観測拡張スコープを越える | Stage A 挙動変更を **撤回**。 全 Stage で step 1 と同じ calendar day 基準 (= `stage_a_window_days` / `stage_b_window_months * 30` / `stage_c_holdout_days`) 維持 | § 2.2 / § 2.3 / § 4.5 |
| (Round 1 [Warning] window_days = months*30 弱) を再評価 | step 1.5 では **defer**。 step 1 と同じ性質を維持 (= 全 Stage 統一の business day 基準化は別 step で扱う、 § 6 スコープ外に追記) | § 4.5 / § 6 |
| (Round 1 [Critical] A1 で canonical sidecar 数値変化検出されない指摘) | Stage A 挙動変更を撤回したため、 acceptance A1 の検出範囲問題は解消 (= Stage A 既存挙動完全不変、 canonical sidecar も Stage A は step 1 と同一) | § 5.4 |

---

## 1. 背景・課題

### 1.1 step 1 完了時点の状態

step 1 (= main commit 9bc6a02) で:
- `src/alpha_factory/canonical_adapter.py` 新規 (= broker.Trade ↔ TradeRecord / equity_curve ↔ BarEquitySeries 変換 SSOT、 step 1 で **凍結**)
- `_try_evaluate_canonical_five_safe(..., window_days, stage_label, ...)` helper (= 例外 safe wrapper)
- `_log_canonical_dual_path(stage_label=...)` helper (= 構造化 log 出力)
- `_build_stage_a_canonical_thresholds(live_criteria, window_days, baseline_dataset_days=730)` (= window scaling)
- `phase2_canonical_metrics_mode: Literal["log_only", "disabled"]` (StageGateConfig field)
- evaluate_stage_a に dual-path 配線済み (= 既存判定経路完全不変、 regression 0 = 判定結果回帰 0)

**Stage B / Stage C は未配線**: canonical_metrics 経路は Stage A 評価窓 (= 直近 60d) のみ観測可能。 Stage B IS monitor (= bars_18m, 18 ヶ月) / Stage C holdout (= bars_holdout, 60d) では legacy `BacktestMetrics` のみ生成され、 canonical 5 軸 (sr_session_worst_block_scale / net_pnl_after_cost / max_dd / trade_count / session_block_win_rate_worst) は計算されない。

### 1.2 課題

- **観測範囲不足**: synthesis § 6.4 の 5 軸 canonical 評価が Stage A 評価窓だけで観測可能、 後続 (= step 2) で評価判定を切替える際、 Stage B IS / Stage C base の **観測値が無い** (= calibration data の **一部** が欠落)
- **adapter 凍結検証未実施**: step 1 で凍結した `canonical_adapter.py` の helper (= `trade_to_trade_record` / `equity_curve_to_bar_equity_series` / `compute_business_day_universe_from_bars`) が Stage B (18 ヶ月、 数千 trade) / Stage C (60d, 数百 trade) でも **クラッシュなく動くかが未検証**

### 1.3 step 1.5 のスコープ確定 (= Round 1 反映で limit)

**step 1.5 では Stage B IS monitor + Stage C base evaluation の dual-path 観測拡張のみ**:
- adapter 改変禁止 (= step 1 で凍結、 同じ helper を再利用)
- Stage A と同型 pattern: **1 backtest → 1 canonical_sidecar → 1 dual-path log**
- 既存判定経路完全不変 (= 判定結果回帰 0、 archive Parquet schema 不変、 LOG_ONLY 維持)

**step 1.5 での未解決 (= 次 step で扱う)**:
- Stage B per-fold dual-path (= per-fold OOS の canonical 観測、 step 2 内 or step 1.6 で対応)
- Stage C stress / cross_pair (= live_criteria + ii-lite 評価軸の canonical 観測、 step 2 以降)
- step 2 (= stage_bc_evaluator main flow 統合) の前提条件達成 (= 全 Stage 全評価軸の canonical 観測が揃って初めて達成、 step 1.5 だけでは **不充足**)

= step 1.5 完了後の状態 (= 控えめ表現):
- main flow が canonical 5 metrics の観測値を **Stage A / Stage B IS / Stage C base の 3 評価点で生成可能** に
- adapter 凍結再利用が **Stage B 18 ヶ月期間 / Stage C 60d 期間で crash なく動くこと** が dual-path log で確認可能 (= step 2 calibration data の **partial 先行取得**)

---

## 2. 改善アイデア

### 2.1 helper rename + generic 化 (= 1 file 内、 minor、 commit A)

`_build_stage_a_canonical_thresholds(live_criteria, window_days, ...)` は既に `window_days` 引数で window scaling 済 (= step 1 で実装済)。 全 Stage 共通で再利用可能なため:

**Option A**: rename して generic 化 (推奨)
```python
def _build_canonical_thresholds_for_window(
    *,
    live_criteria: Mapping[str, float | int],
    window_days: int,
    baseline_dataset_days: int = 730,
) -> CanonicalFiveThresholds: ...
```

**Option B**: rename せず、 Stage A 専用名のまま全 Stage で呼出
- Stage 名と関数名のミスマッチが発生 (= 名前の責務違反)

**設計判断**: Option A 採用 (= 機能の名前に立ち返る原則)。 commit A (= pure refactor、 動作不変) で先行実施し、 commit B (= behavioral wiring) と分離する (Round 1 [Warning] 反映)。

### 2.2 Stage B IS monitor 配線 (commit B)

`evaluate_stage_b` の IS monitor 区画 (= stage_gate.py L824-L844、 `bars_18m` 全体 backtest) に Stage A と同型の dual-path 配線を追加:

```python
try:
    strategy = DslStrategy(genome, primitive_evaluator)
    broker = MockBroker(instrument_meta=meta)
    res = run_backtest(bars_18m, strategy, broker, backtest_config)
    bt = compute_metrics(...)
    is_full_sharpe = ...
    is_full_total_pnl = float(bt.total_pnl)
    is_full_trade_count = bt.trade_count

    # 新規: dual-path canonical 5 metrics (LOG_ONLY mode)
    # window_days は step 1 と同じ calendar day 基準 (= Round 2 [Critical] 反映で
    # Stage A 挙動変更撤回、 全 Stage 統一の business day 基準化は別 step)
    canonical_sidecar = _try_evaluate_canonical_five_safe(
        trades=res.trades,
        equity_curve=res.equity_curve,
        bars=bars_18m,
        live_criteria=stage_config.live_criteria,
        window_days=stage_config.stage_b_window_months * 30,  # 540 calendar days
        stage_label="B_IS",
        genome_name=genome.name,
        enabled=(stage_config.phase2_canonical_metrics_mode != "disabled"),
    )
    try:
        _log_canonical_dual_path(
            stage_label="B_IS",
            genome_name=genome.name,
            legacy=bt,
            canonical=canonical_sidecar,
        )
    except Exception as exc:
        logger.warning("stage_gate.canonical_five.log_failed", stage="B_IS", ...)
except Exception as exc:
    logger.warning("stage_b.is_monitor_failure", ...)
```

**stage_label="B_IS"** で Stage A (`stage="A"`) と区別 (= 同 stage 内で IS / per-fold が将来共存可能、 log filtering 可能)。

`window_days` は step 1 と同じ **calendar day 基準** (= `stage_b_window_months * 30 = 540` calendar days)。 Round 1 [Warning] で「`months*30` の calendar day 基準が DST/週跨ぎで実観測窓と乖離する」指摘があったが、 Round 2 [Critical] で「step 1.5 は Stage B/C 観測拡張のみ、 全 Stage の window_days 仕様変更は scope 越え」と判定されたため、 **defer** (= 別 step で全 Stage 統一の business day 基準化を検討、 § 6 スコープ外参照)。

### 2.3 Stage C base evaluation 配線 (commit B)

`evaluate_stage_c` の base evaluation 区画 (= stage_gate.py L1162-L1192、 `bars_holdout` で run_backtest) に Stage A と同型の dual-path 配線を追加:

```python
try:
    strategy = DslStrategy(genome, primitive_evaluator)
    broker = MockBroker(instrument_meta=meta)
    res = run_backtest(bars_holdout, strategy, broker, backtest_config)
    bt = compute_metrics(...)
    base_sharpe = ...
    base_total_pnl = float(bt.total_pnl)
    base_max_dd_frac = float(bt.max_drawdown_pct) / 100.0
    base_trade_count = bt.trade_count
    for t in res.trades:
        ...

    # 新規: dual-path canonical 5 metrics (LOG_ONLY mode)
    # window_days は step 1 と同じ calendar day 基準 (= Round 2 [Critical] 反映)
    canonical_sidecar = _try_evaluate_canonical_five_safe(
        trades=res.trades,
        equity_curve=res.equity_curve,
        bars=bars_holdout,
        live_criteria=stage_config.live_criteria,
        window_days=stage_config.stage_c_holdout_days,  # 60 calendar days (= 既存)
        stage_label="C_base",
        genome_name=genome.name,
        enabled=(stage_config.phase2_canonical_metrics_mode != "disabled"),
    )
    try:
        _log_canonical_dual_path(
            stage_label="C_base",
            genome_name=genome.name,
            legacy=bt,
            canonical=canonical_sidecar,
        )
    except Exception as exc:
        logger.warning("stage_gate.canonical_five.log_failed", stage="C_base", ...)
except Exception as exc:
    logger.warning("stage_c.base_failure", ...)
```

**stage_label="C_base"** (= Stage C は base evaluation 1 つのみ、 stress / cross_pair は dual-path 対象外、 step 1.5 スコープ外。 Round 1 [Suggestion] 反映で 4 系列ログ命名 (B_IS / B_fold / C_base / C_cross_pair) のうち **C_base** を採用)。

### 2.4 Stage B per-fold + Stage C stress / cross_pair はスコープ外

- **Stage B per-fold dual-path**: 5 fold それぞれで dual-path log は scope 拡張 (= log 量増加、 per-fold thresholds 構築方法の検討要)。 別 step (= step 1.6 or step 2 内で扱う)。
- **Stage C stress / cross_pair**: stress test (= spread_stress_multiplier 適用後 backtest) や cross_pair (= shadow only) は別軸で、 step 1.5 スコープ外。
- **重要**: B_IS diff を Stage B 合否や per-fold OOS 安定性の **代理指標として解釈しない** (= C3 collider bias 回避、 § 4.6 ログ規約に sentinel 注記)。

---

## 3. 期待効果 (= Round 1 反映で控えめ化)

### 3.1 直接的

- main flow が canonical 5 metrics の観測値を **Stage A / Stage B IS / Stage C base の 3 評価点で生成可能** に
- adapter 凍結再利用 (= Stage B 18 ヶ月 / 数千 trade、 Stage C 60d / 数百 trade) が **クラッシュなく動くこと** が dual-path log で確認可能 (= 健全性確認のみ、 calibration 判定は別途)

### 3.2 間接的

- step 2 (= stage_bc_evaluator main flow 統合) の **partial 前提条件** (= 全 Stage の partial 観測点で adapter / helper が動くこと) を満たす
- evaluate_stage_b の per-fold dual-path 拡張 (= 別 step) でも同じ helper 再利用可能 (= 段階的価値最大化)

### 3.3 live_criteria 達成への寄与 (= 直接寄与なし)

- **直接寄与**: なし (= 観測のみ、 判定ロジック完全不変、 GA fitness 不変)
- **間接寄与**: step 2 以降の判定切替前に 「adapter / helper が動くか」 を falsification 可能 (= 数値計算 calibration とは別軸の健全性確認)

### 3.4 calibration data 取得計画 (= 別軸、 step 1.5 範囲外)

step 1.5 では **健全性確認** (= crash 0 / log 出力成功) のみが acceptance。 数値 diff の calibration 判定は別計画:
- smoke 5 Run: クラッシュ・log 生成確認のみ (= n=5 で C7 ガード遵守、 数値 calibration 判断には使わない)
- 実 GA Run (= n >> 30): step 2 着手前に別途実施し、 diff 分布の collider bias 抑止条件下で観測 (= 別 devnote / 別計画)

---

## 4. 実装方針 (概要)

### 4.1 変更ファイル候補 + commit 分離 (Round 1 反映)

**commit A** (= pure refactor、 動作不変):
1. `src/alpha_factory/stage_gate.py`:
   - `_build_stage_a_canonical_thresholds` → `_build_canonical_thresholds_for_window` rename + comment 修正
   - 既存 caller (Stage A 内 1 箇所) の更新

**commit B** (= behavioral wiring、 dual-path 配線追加):
1. `src/alpha_factory/stage_gate.py`:
   - `evaluate_stage_b` の IS monitor 区画に dual-path 配線追加 (= L824-L844 拡張、 `window_days=stage_b_window_months * 30`)
   - `evaluate_stage_c` の base evaluation 区画に dual-path 配線追加 (= L1162-L1192 拡張、 `window_days=stage_c_holdout_days`)
2. `tests/alpha_factory/test_stage_gate_canonical_dual_path.py` (= step 1 で作成済) に Stage B IS / Stage C 用 test 追加:
   - regression 0 (= legacy payload 完全不変) for B IS / C base
   - log isolation (= canonical 例外時 legacy 経路不変) for B IS / C base
   - propagation (= phase2_canonical_metrics_mode disabled で canonical skip) for B IS / C base
   - Stage B IS で 18 ヶ月期間の adapter / thresholds 構築が成功 (= crash なし)
   - Stage C で 60 日期間の adapter / thresholds 構築が成功 (= crash なし)

### 4.2 影響範囲

- stage_gate.py で **計算量 ~2x** (Stage B IS + Stage C base のみ、 LOG_ONLY mode)
- 既存 BacktestResult の trade / equity_curve がそのまま reuse されるため、 backtest 自体は 1 回のみ
- archive Parquet schema 不変 (= sidecar 非添付)
- StageGateConfig schema 不変 (= step 1 で `phase2_canonical_metrics_mode` 追加済、 step 1.5 で field 追加なし)

### 4.3 LOG_ONLY 維持

step 1.5 では LOG_ONLY 維持 (= 既存判定経路完全不変、 判定結果回帰 0)。 FAIL_CLOSED 切替は step 2 以降で判定切替時に検討。

### 4.4 メモリ制約 概算 (Round 1 [Critical] 反映)

**前提**:
- 環境: 24 GB メモリ × 6 ワーカー並列、 1 ワーカー 3 GB 上限
- M1 (1分足) bar 想定、 セッション内のみ

**bar 数概算 (M1 想定)**:
| Stage | 期間 | 最大 bar 数 (24h cont) | 営業日 trim 後 (~70%) |
|---|---|---|---|
| Stage A | 60d | 86,400 | ~60,000 |
| Stage B IS | 18m | 777,600 | ~544,000 |
| Stage C | 60d | 86,400 | ~60,000 |

**1 stage 評価あたり追加メモリ概算 (= LOG_ONLY mode)**:
- `BarEquitySeries` (= tuple of `BarEquityPoint(datetime, float)`): ~80 byte/point (object overhead 込) → Stage B IS 544K bars で **~44 MB**
- `TradeRecord` tuple (= datetime ×2 / float ×4 / SessionBucket / int / bool ×2): ~250 byte/trade → 数千 trade で **<3 MB**
- `business_day_universe` (= dict[bucket, frozenset[int]]): 3 bucket × ~400 business days × 28 byte (set entry) → **<35 KB**
- `CanonicalFiveResult` (= per_bucket dict + slack 値 × 5 + invariants 等): **<10 KB**

**Stage B IS の peak 追加 RSS = ~47 MB / worker / 評価**

**6 worker 並列 worst case**: 6 × ~47 MB ≈ **~282 MB** (= 全 worker が同時に Stage B IS 評価中の場合)

**budget 余裕**: 1 worker 3 GB 上限に対し、 既存 backtest engine が hold する `equity_curve` (= list[(datetime, Decimal)]、 Decimal は object で重い) が同等以上 (~50-80 MB) で、 step 1.5 dual-path はその一時コピー (= float 化) を新たに保持。 RSS 最大 **+~50 MB / worker** 程度の増加と推定 = budget 内 (3 GB の 2% 未満)。

**acceptance criterion** (= § 5.4 と整合):
- worst-case pair (= USD_JPY 18m など最 trade 多発 pair) で peak RSS ≤ worker 予算 (= 3 GB)
- smoke 5 Run の peak RSS observable (= profile or `/usr/bin/time -l`) で実測

### 4.5 window_days 仕様: step 1 と同じ calendar day 基準維持 (Round 2 [Critical] 反映)

**Round 1 → Round 2 の judgement 経緯**:
- Round 1 [Warning]: 「`stage_b_window_months * 30` (= 540 calendar day) は DST/週跨ぎ/祝日で実観測窓と乖離」と指摘
- Round 1 改訂案: `_count_business_days_from_bars(bars)` で business day 基準化 (= Stage A 含めて全 Stage 統一)
- Round 2 [Critical]: 「Stage A 挙動変更は step 1.5 の B/C 観測拡張スコープを越える」 「A1 regression test (= legacy payload) では canonical sidecar / log の threshold 変化を検出できない」 と判定
- Round 3 改訂: Stage A 挙動変更を **撤回**、 全 Stage で step 1 と同じ calendar day 基準維持 (= scope を Stage B IS + Stage C base の dual-path 配線追加のみに limit)

**確定仕様** (= step 1 と完全互換):
- Stage A: `window_days = stage_a_window_days` (= 60、 既存) — **step 1 から変更なし**
- Stage B IS: `window_days = stage_b_window_months * 30` (= 540 calendar days) — step 1 と同じ calendar day 基準
- Stage C base: `window_days = stage_c_holdout_days` (= 60、 既存) — step 1 と同じ calendar day 基準

**残課題 (= 別 step で扱う、 § 6 スコープ外参照)**:
- 全 Stage 統一の business day 基準化 (= calendar day → business day) は単独 step として別途設計判断 (= 全 Stage で挙動変化が伴うため独立 commit、 acceptance criterion で canonical sidecar 数値変化を明示的に観測する設計が必要)

**注記**: step 1.5 では step 1 と同じ性質 (= calendar day 基準で DST/週跨ぎ吸収しない) を維持する選択肢が「過度な複雑化禁止」原則と整合。 Stage A 60d / Stage C 60d は誤差小、 Stage B 18m では誤差 ~30% (= weekend) があり得るが、 step 1.5 では「crash なく動く」健全性確認のみが acceptance のため数値妥当性は判定範囲外。

### 4.6 ログ命名規約 SSOT (Round 1 [Suggestion] 反映)

dual-path log の `stage` field 値は以下 4 系列に固定する (= 後の誤読を減らす):

| stage_label | 評価対象 | step | collider 注意点 |
|---|---|---|---|
| `A` | Stage A 評価窓 (60d) | step 1 完了 | (Stage A は単一窓、 collider なし) |
| `B_IS` | Stage B 18m 全体 IS monitor | step 1.5 | **B_IS diff は Stage B 合否や per-fold OOS の代理指標ではない** (= per-fold は別評価軸、 conditioning set が異なる) |
| `B_fold` | Stage B per-fold OOS | step 2 以降 | per-fold thresholds 構築方法は別途検討 |
| `C_base` | Stage C base evaluation (holdout 60d) | step 1.5 | stress / cross_pair は別 log で混入なし |
| `C_cross_pair` | Stage C cross-pair (ii-lite) shadow | step 2 以降 | mission 必須評価軸、 別 log 系列 |

各 dual-path log には `interpretation_note="direction_monitoring_only"` (= step 1 で導入済) を継承し、 値の一致 / 不一致を理由に collider bias で判断しないことを明示。

---

## 5. 制約・前提

### 5.1 前提表 (= Round 1 [Warning] 反映で 3 列分類)

| 前提 | 状態 | 検証方法 / Out-of-scope 理由 |
|---|---|---|
| `canonical_adapter.py` の helper が UTC-aware datetime 契約に依存 | **Assumed** | step 1 で実装・テスト済 (= 21 ケース PASS) |
| `BUSINESS_DAY_EPOCH 1970-01-01` 基準の encoding は期間長さに依存しない | **Assumed** | step 1 詳細設計 § 4.1 + business_day_index < 0 ガード |
| Stage B 18 ヶ月 / Stage C 60d の bars が UTC-aware | **Assumed** | aux data pipeline (= T057 Phase 2) の入力契約で保証 |
| Stage B 18m, Stage C 60d で adapter / thresholds が **crash なく動く** | **To Verify in step 1.5** | smoke 5 Run の log で確認、 acceptance test (= dual-path test) |
| Stage A の挙動 (= window_days / canonical sidecar 数値) が step 1 と完全に同一 | **Assumed** | step 1.5 では Stage A 触らない (= Round 2 [Critical] 反映で挙動変更撤回)、 commit A は pure refactor (rename のみ、 動作不変) |
| Stage B 18m で peak RSS が worker 3 GB budget 内 | **To Verify in step 1.5** | smoke 5 Run の `/usr/bin/time -l` (= peak RSS) 観測 |
| canonical 5 metrics の数値が legacy と calibration 整合 (= 統計的に妥当な diff 分布) | **Out-of-scope** | step 1.5 では健全性確認のみ。 calibration 判定は別 step (= n>>30 実 GA Run、 collider bias 抑止条件下) |
| 全 Stage 統一の window_days business day 基準化 | **Out-of-scope** | 別 step で全 Stage 挙動変化を伴う独立 commit として扱う |
| Stage B per-fold canonical 観測 | **Out-of-scope** | step 1.6 or step 2 内で対応 |
| Stage C cross_pair (ii-lite) canonical 観測 | **Out-of-scope** | step 2 以降 (= mission 必須評価軸、 別観測軸) |

### 5.2 制約

- adapter 改変禁止 (= step 1 で凍結、 SSOT 維持)
- 既存 `evaluate_stage_b` / `evaluate_stage_c` の戻り `StageResult` schema 不変 (= archive 互換)
- canonical sidecar は payload 非添付 (= archive Parquet schema 不変、 step 1 と同様)
- LOG_ONLY mode で既存判定完全不変 (= 判定結果回帰 0)
- live_criteria 不変 (= 禁止事項 #4 ガード)

### 5.3 前提検証 (C4)

- 着手前調査済 (= ハンドオフ § 3 着手前調査結果):
  - evaluate_stage_b: stage_gate.py:778-989 に存在、 IS monitor + per-fold OOS の 2 段構造
  - evaluate_stage_c: stage_gate.py:1123-1377 に存在、 base + stress + cross_pair の 3 軸
  - `_build_stage_a_canonical_thresholds` は `window_days` 引数で generic 化済
  - `_try_evaluate_canonical_five_safe` は `window_days` / `stage_label` 引数で全 Stage 横断使用可
  - `_log_canonical_dual_path` は `stage_label` 引数で全 Stage 対応済

### 5.4 Acceptance Criteria (= Round 1 [Warning] 反映で 2 軸分離)

**A. 判定結果回帰 0** (= 必須):
- A1: Stage A/B/C の `StageResult.passed` / `StageResult.reason_codes` / `StageResult.metrics["payload"]` (= legacy field 全件) が step 1 commit 9bc6a02 と完全一致 (= test fixture / regression test で確認)
- A2: archive Parquet schema 不変 (= 既存 28+ カラム fixed schema 尊重)
- A3: GA fitness 不変 (= test_stage_gate_canonical_dual_path.py の payload 完全比較で確認、 step 1 と同型)
- A4: Stage A の canonical sidecar (= dual-path log の `canonical_*` field) が step 1 commit 9bc6a02 と完全一致 (= Round 2 [Critical] 反映で Stage A 挙動変更撤回、 commit A の rename は pure refactor で動作不変であることを test で確認)

**B. 運用回帰検証** (= 別軸、 partial verification):
- B1: dual-path log が Stage B IS / Stage C base で **crash なく出力** される (= log isolation test で確認)
- B2: smoke 5 Run で peak RSS が worker 3 GB budget 内 (= `/usr/bin/time -l` で実測)
- B3: smoke 5 Run の所要時間が step 1 比 ±20% 以内 (= 計算 overhead が想定通り)
- B4: dual-path log が legacy log (= 既存 stage_b.is_monitor_failure / stage_c.base_failure) と独立して出力 (= log mixing なし)

**C. legacy 比較可能性** (= step 2 calibration の partial 前提):
- C1: dual-path log の `stage_label` field が `B_IS` / `C_base` で正しく区別可能
- C2: `legacy_*` / `canonical_*` field が同 log entry に共存 (= per-genome diff 分析可能)
- C3: `interpretation_note="direction_monitoring_only"` が継承

**重要**: C は **構築可能性のみ** (= log で legacy / canonical を per-genome 比較可能)。 数値が **妥当か** (= calibration 整合) は step 1.5 では検証しない (= Round 1 [Warning] 反映、 別軸別計画)。

---

## 6. スコープ外 (= Round 1 反映で明確化)

1. **Stage B per-fold dual-path**: 5 fold それぞれで dual-path log は別 step (= step 1.6 or step 2 内)、 per-fold thresholds 構築方法 (= per-fold or pooled) も別途検討
2. **Stage C stress / cross_pair の dual-path**: stress test / shadow cross_pair は別軸、 step 1.5 範囲外 (= cross_pair は mission 必須軸 ii-lite だが step 2 以降で扱う)
3. **canonical 5 軸ベース判定** (= LOG_ONLY → FAIL_CLOSED 切替): step 2 以降
4. **stage_bc_evaluator (canonical 5 軸 caller) の main flow 統合**: B Phase 2 step 2
5. **archive Parquet schema 拡張** (= canonical metrics 永続化): 後続別 step
6. **sidecar JSON 永続化**: 後続別 step (= report 経路改修)
7. **calibration data 数値整合判定** (= n>>30 実 GA Run での diff 分布分析): 別計画 (= step 1.5 では「crash なく動く」のみ確認)
8. **全 Stage 統一の window_days business day 基準化** (= calendar day → business day): Round 2 [Critical] 反映で step 1.5 から撤回。 全 Stage で挙動変化を伴うため独立 commit として別 step で扱う (= acceptance criterion で canonical sidecar 数値変化を明示的に観測する設計が必要)
9. **Stage A の window_days 厳密性向上** (= ratio scaling の最適化): 別軸検討事項、 step 1 と同じ calendar day 基準維持

---

## 7. リスク

| リスク | 影響 | 緩和 |
|---|---|---|
| Stage B 18 ヶ月期間 (= 数千 trade) で adapter / thresholds 構築が legacy より遅い (= dual-path overhead 過大) | 中 | LOG_ONLY mode で計算 overhead 観測、 必要なら disabled mode で skip 可能 (= step 1 で既に `phase2_canonical_metrics_mode` flag あり)。 acceptance B3 (smoke 5 ±20%) でガード |
| Stage B IS monitor で例外発生 → legacy 経路を巻き込む | 高 | step 1 で確立した `_try_evaluate_canonical_five_safe` + log try/except による完全隔離 (= 同 helper 再利用、 acceptance B1 でガード) |
| Stage C base evaluation で stress / cross_pair が dual-path log を上書き | 低 | stage_label="C_base" は base evaluation のみ、 stress / cross_pair は別 log で混入なし (= step 1.5 スコープ外、 § 4.6 ログ規約 SSOT) |
| numerical diff (legacy vs canonical) が Stage B/C で予想以上に大きい | 中 | step 1.5 では数値妥当性判定しない (= Round 1 [Critical] 反映)。 step 2 calibration 計画 (= 別軸 n>>30 実 GA Run) で diff 分布分析 |
| `_build_stage_a_canonical_thresholds` rename で他 caller に波及 | 低 | rename 対象は 1 internal helper のみ (= `_` prefix で external API なし)、 commit A で全 caller を grep + 同時更新、 commit B から完全分離。 commit A は pure refactor (動作不変) で acceptance A4 (= Stage A canonical sidecar 完全一致 test) で確認 |
| 18m bars + dual-path で peak RSS が worker 予算超過 | 高 | acceptance B2 (= `/usr/bin/time -l` で実測) で worst-case pair 確認、 超過時は disabled mode へ落とすか Stage B 内 sub-sampling 検討 |
| B_IS diff を per-fold OOS の代理指標として誤解釈 | 中 | § 4.6 ログ規約 SSOT で sentinel 注記 (= `interpretation_note="direction_monitoring_only"` 継承)、 conditioning set が異なる旨を docs (= 後続 step 2 設計時 docs/alpha_factory/canonical-metrics.md) に記載 |

---

## 8. 7 step segmentation 全体俯瞰 (= 進捗反映)

| step | 内容 | 統合先 module | 状態 |
|---|---|---|---|
| step 1 ✨ | canonical_metrics → main flow (= Stage A dual-path LOG_ONLY) | canonical_metrics | **完了** |
| **step 1.5 (本)** | Stage B IS monitor + Stage C base dual-path 拡張 (adapter 凍結再利用) | (stage_gate.py のみ) | **設計 Round 2 中** |
| step 1.6 | Stage B per-fold dual-path (= per-fold thresholds 構築方法検討) | (stage_gate.py + canonical_metrics 連携) | 後続 |
| step 2 | stage_bc_evaluator → main flow (= evaluate_stage_b_pooled / evaluate_stage_c_lite 運用) | stage_bc_evaluator | 次次 |
| step 3 | cpps_archive → main flow (= archive_admit / AdmissionReport 経路) | cpps_archive | 後続 |
| step 4-7 | (詳細はハンドオフ § 4) | ... | 後続 |

---

## 9. この設計に効く事実 (= Round 1 [Warning] C1 反映、 docs/devnotes/git log 要点要約)

### 9.1 step 1 完了 handoff (`devnotes/20260503-1414-B-step1-complete-handoff/handoff.md`)
- step 1 で `canonical_adapter.py` SSOT 凍結。 helper は `trade_to_trade_record` / `equity_curve_to_bar_equity_series` / `compute_business_day_universe_from_bars` の 3 つ。
- step 1 詳細設計 Codex Round 2 APPROVED、 実装 Codex Round 3 APPROVED の 4 round 議論を経て確定。
- regression 0 (= 判定結果回帰 0) は step 1 で test 21 ケース全 PASS で確認済。 main commit 9bc6a02 で main マージ。

### 9.2 step 1 詳細設計 (`devnotes/20260503-1024-B-phase2-step1-canonical-metrics/detailed-design.md`)
- LOG_ONLY mode で「既存判定経路完全不変、 sidecar 計算 + log のみ」が core 原則。
- `_try_evaluate_canonical_five_safe` の例外 fallback は **adapter / thresholds / evaluate_canonical_five 全件 try 内** で legacy 経路完全隔離。
- log helper も try/except で完全隔離 (= logger processor 異常時に legacy 経路を巻き込まない)。
- payload / archive Parquet schema 不変 (= canonical_sidecar 非添付)。

### 9.3 stage_gate.py 現行構造 (= ハンドオフ § 3 着手前調査)
- evaluate_stage_a (L567-740): backtest → compute_metrics → dual-path 配線済 (step 1 完了)。
- evaluate_stage_b (L778-989): IS monitor (L824-844, bars_18m 全体) + per-fold OOS (L859-913) の 2 段構造。 per-fold は WF folds × test_bars。
- evaluate_stage_c (L1123-1378): base evaluation (L1162-L1192, bars_holdout) + stress test (L1238-1285) + cross_pair (L1295-1334) の 3 軸。 base のみ step 1.5 配線対象。
- `StageGateConfig` (L292-455): `phase2_canonical_metrics_mode` field が step 1 で追加済 (Literal["log_only", "disabled"])。 step 1.5 で field 追加なし。

### 9.4 canonical_metrics.py の context (= 当該設計で参照する API)
- `TradeRecord`: UTC-aware datetime ×2 / float ×4 / SessionBucket / int / bool ×2。 invariant fail-fast (= 不正値は raise)。
- `BarEquitySeries`: tuple of `BarEquityPoint`, sorted / no-dup / UTC-aware / finite invariant。
- `evaluate_canonical_five(trades, bars, thresholds, universe)`: no-raise 契約 (= 異常時 reason field で encoded)、 ただし adapter / thresholds 構築段階で raise 可能性あり (= step 1 で `_try_evaluate_canonical_five_safe` で catch 済)。

### 9.5 git log の関連
- `9bc6a02 Merge branch 'todo/B-step1'` (= step 1 main commit)
- `a07f883 feat(B step 1): canonical_metrics → main flow 統合 (Codex impl-review Round 3 APPROVED)`
- `5e47278 docs(B-phase2-step1): detailed design Round 2 改訂 + Codex review APPROVED`

---

## 10. 参考資料

- step 1 概念設計: `devnotes/20260503-1024-B-phase2-step1-canonical-metrics/conceptual-design.md`
- step 1 詳細設計: `devnotes/20260503-1024-B-phase2-step1-canonical-metrics/detailed-design.md` (Codex Round 2 APPROVED)
- step 1 完了 handoff: `devnotes/20260503-1414-B-step1-complete-handoff/handoff.md`
- step 1 main commit: `9bc6a02 Merge branch 'todo/B-step1'` (= worktree commit `a07f883`)
- canonical_adapter.py (凍結): `src/alpha_factory/canonical_adapter.py`
- stage_gate.py (拡張対象): `src/alpha_factory/stage_gate.py:567-1378`
- canonical_metrics.py (= TradeRecord / BarEquitySeries / evaluate_canonical_five): `src/alpha_factory/canonical_metrics.py`
- Codex Round 1 conceptual review: `conceptual-review-round-1.md` (= 同フォルダ)
