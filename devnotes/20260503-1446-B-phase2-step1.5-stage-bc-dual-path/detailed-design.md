# 詳細設計: B Phase 2 切替コミット step 1.5 — Stage B IS monitor / Stage C base に dual-path 拡張

**作成日時**: 2026-05-03 15:30 JST (Round 2 改訂: 2026-05-03 15:54 JST、 Round 3 改訂: 2026-05-03 16:08 JST、 Round 4 改訂: 2026-05-03 16:20 JST)
**status**: **詳細設計 Round 4 APPROVED** (= Codex 詳細設計 Round 3 CHANGES_REQUESTED 反映済、 Round 4 で APPROVED 判定)。 残 Warning は実装時の細部修正範囲
**概念設計**: `devnotes/20260503-1446-B-phase2-step1.5-stage-bc-dual-path/conceptual-design.md` (Codex Round 3 APPROVED)

---

## 0. Round 1 → Round 2 改訂対応マトリクス

| Round 1 指摘 | 対応 | 反映先 |
|---|---|---|
| 施策 1 [Critical] helper 入力契約明文化不足 | step 1 で凍結済 helper の docstring + 入力契約を § 4.4 / § 5.4 / § 6.4 で本設計書内に再掲 | § 4.4, § 5.4, § 6.4 |
| 施策 2 [Critical] 広域 except でログ欠落運用リスク | step 1 で確立した WARN log 構造 (= structlog stage / genome / error / error_type 必須キー) を § 5.4 / § 6.4 に明記。 失敗件数閾値ベースの fail-fast はサーキットブレーカは step 2 以降 (§ 12 follow-up) | § 5.4, § 6.4, § 12 |
| 施策 3 [Critical] ゴールデン比較対象不足 | acceptance A1 を「fixed seed × fixed fixture の deep dict comparison、 成功 / 失敗 / 境界の 3 群 + Stage A 単独非回帰スイート」に具体化 | § 8 / § 7.5 |
| 施策 5 [Critical] test 計画 10 ケース不足 | 契約 test / 異常系 / 並列ログ識別子 / 回帰ゴールデン を含む 16 ケースに拡充。 メモリ上限 test は smoke 5 Run の運用検証 (= acceptance B2) に分離 | § 7 |
| 施策 7 [Critical] archive/schema 伝搬漏れリスク (禁止事項 8) | step 1.5 では canonical_sidecar 非添付 (= archive Parquet schema 不変) を § 8 acceptance A2 で明記、 schema version 固定 + reader 後方互換 test の必要なし (= 変更ゼロ) を確認 | § 8 |
| 施策 1-7 [Warning] cost / 例外注入 / 並列ログ等 | step 1.5 では新規変更なし (= step 1 で完了済)。 follow-up (= 実装後の運用観測) として § 12 に列挙 | § 12 |
| 施策 4 [Warning] commit A pure 性検証 | commit A を機械的 rename + 既存 12 ケース PASS で動作不変保証 (= 公開 API シグネチャ差分ゼロを `git diff --stat` で確認、 § 9.1 に手順明記) | § 9.1 |
| 施策 6 [Warning] メモリ概算楽観性 | smoke 5 Run の `/usr/bin/time -l` 実測を acceptance B2 として固定。 設計時点で「+~50 MB / worker」は概念設計 § 4.4 推定値、 実測で確証 | § 8 / § 12 |

### Round 2 → Round 3 改訂

| Round 2 指摘 | 対応 |
|---|---|
| logger kwargs key 契約不一致 (= `genome_name` vs `genome`) | acceptance B5 等で必須キーを `genome` に統一 (= 既存 helper の logger kwargs と整合)。 helper 引数名 `genome_name` (= function arg) と logger kwargs key `genome` (= structlog 出力 field) を区別明記 (§ 8 / § 5.5 / § 6.5) |
| A1 と §7.5 の不一致 (= A1 で Stage A/B/C deep dict 要求 vs §7.5 で Stage B のみ golden) | A1 を「Stage B IS / Stage C base に対する deep dict comparison、 Stage A は step 1 で同等カバレッジ済」に明確化。 §7.5 は Stage B IS / Stage C base 両方に golden 3 群追加 (= 各 stage 3 群 = 6 ケース) |
| テストケース数の揺れ (10 / 16 / 18) | 全箇所で **21 ケース** (= Stage B IS 7 + Stage B IS golden 3 + Stage C base 7 + Stage C base golden 3 + 並列 log key 1) に統一 (§ 7.2 / § 7.3-7.6) |

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

`devnotes/20260503-1446-B-phase2-step1.5-stage-bc-dual-path/conceptual-design.md` (Round 3 APPROVED)

主要決定事項:
- **scope**: Stage B IS monitor + Stage C base evaluation のみ dual-path 配線追加 (= Stage A は step 1 から完全不変)
- **adapter 凍結**: `canonical_adapter.py` は変更なし (step 1 で凍結済)
- **window_days 仕様**: step 1 と同じ calendar day 基準維持 (= Stage A `stage_a_window_days` / Stage B IS `stage_b_window_months * 30` / Stage C `stage_c_holdout_days`)
- **commit 分離**: commit A (= rename pure refactor) + commit B (= behavioral wiring)
- **acceptance**: 判定結果回帰 0 (A) + 運用回帰検証 (B) + legacy 比較可能性 (C)

---

## 3. 施策一覧

| # | 施策名 | 変更ファイル | 優先度 | commit |
|---|---|---|---|---|
| 1 | helper rename (`_build_stage_a_canonical_thresholds` → `_build_canonical_thresholds_for_window`) | src/alpha_factory/stage_gate.py | High | commit A (pure refactor) |
| 2 | Stage B IS monitor dual-path 配線追加 | src/alpha_factory/stage_gate.py | High | commit B (behavioral wiring) |
| 3 | Stage C base evaluation dual-path 配線追加 | src/alpha_factory/stage_gate.py | High | commit B |
| 4 | dual-path test 追加 (Stage B IS / Stage C base) | tests/alpha_factory/test_stage_gate_canonical_dual_path.py | High | commit B |

**重要**: rename は commit A、 behavioral wiring は commit B (= worktree 内で 2 commit に分離)。 main マージ時は no-ff merge で履歴に 2 commit を保持。

---

## 4. 施策 1: helper rename (commit A、 pure refactor)

### 4.1 変更箇所
- ファイル: `src/alpha_factory/stage_gate.py:68-108` (= `_build_stage_a_canonical_thresholds` 関数定義) + L145 (= `_try_evaluate_canonical_five_safe` 内の呼出)

### 4.2 波及変更
- `AGENTS.md`: なし
- `.claude/skills/zenigame-fx-*/SKILL.md`: なし
- `config/alpha_factory/default.yaml`: なし
- `docs/alpha_factory/*.md`: なし (= 内部 helper、 docs 露出なし)

### 4.3 現行コード

```python
# stage_gate.py:68-108
def _build_stage_a_canonical_thresholds(
    *,
    live_criteria: Mapping[str, float | int],
    window_days: int,
    baseline_dataset_days: int = 730,
) -> CanonicalFiveThresholds:
    """Stage A 評価窓用 CanonicalFiveThresholds を構築.

    derive_stage_a_thresholds (= stage_a_evaluator) と異なり、
    live_criteria に win_rate_min が無くても _CANONICAL_DUAL_PATH_DEFAULT_WIN_RATE_MIN
    を default として使用 (= 既存 live_criteria 互換性維持、 step 1 範囲)。
    ...
    """
    ratio = window_days / baseline_dataset_days
    trade_min_window = max(1, math.ceil(live_criteria["trade_count_min"] * ratio))
    trade_max_window = max(
        trade_min_window,
        math.floor(live_criteria["trade_count_max"] * ratio),
    )
    return CanonicalFiveThresholds(...)
```

呼出箇所 (stage_gate.py:145):
```python
thresholds = _build_stage_a_canonical_thresholds(
    live_criteria=live_criteria,
    window_days=window_days,
)
```

### 4.4 変更後コード

```python
# stage_gate.py:68-108 (rename + comment 修正)
def _build_canonical_thresholds_for_window(
    *,
    live_criteria: Mapping[str, float | int],
    window_days: int,
    baseline_dataset_days: int = 730,
) -> CanonicalFiveThresholds:
    """評価窓用 CanonicalFiveThresholds を構築 (= 全 Stage 共通).

    Stage A (60d) / Stage B IS (540d) / Stage C base (60d) で再利用。
    derive_stage_a_thresholds (= stage_a_evaluator) と異なり、
    live_criteria に win_rate_min が無くても _CANONICAL_DUAL_PATH_DEFAULT_WIN_RATE_MIN
    を default として使用 (= 既存 live_criteria 互換性維持)。

    Args:
        live_criteria: stage_gate.live_criteria (= MappingProxyType[str, float|int])。
        window_days: 評価窓日数 (= calendar day 基準で step 1 と統一)。
        baseline_dataset_days: live_criteria の baseline 期間 (= 730d default)。

    Returns:
        CanonicalFiveThresholds: window scaling 後の thresholds。
    """
    # (関数本体は既存と完全に同じ、 動作不変)
    ratio = window_days / baseline_dataset_days
    trade_min_window = max(1, math.ceil(live_criteria["trade_count_min"] * ratio))
    trade_max_window = max(
        trade_min_window,
        math.floor(live_criteria["trade_count_max"] * ratio),
    )
    return CanonicalFiveThresholds(...)
```

呼出箇所 (stage_gate.py:145):
```python
thresholds = _build_canonical_thresholds_for_window(
    live_criteria=live_criteria,
    window_days=window_days,
)
```

### 4.5 ルックアヘッドバイアスチェック
N/A (= 純粋な rename、 算術ロジック変更なし)

### 4.6 パフォーマンスチェック
N/A (= 動作不変、 計算量同一)

### 4.7 テスト計画
- 既存テスト `tests/alpha_factory/test_stage_gate_canonical_dual_path.py` (= step 1 で 12 ケース追加済) が rename 後も全 PASS することで動作不変を確認
- 新規テスト追加なし (= pure refactor のため、 § 9.1 の手順で commit A 単独で test 全 PASS + 公開 API 差分ゼロを `git diff src/alpha_factory/__init__.py` で確認)

### 4.8 リスク
- rename で他 caller に波及 → grep で全 caller を確認 + 同時更新。 1 internal helper のみ (`_` prefix) のため波及範囲は限定的 (= § 9.1 で `grep -rn "_build_stage_a_canonical_thresholds" src/ tests/` を pre-rename 確認手順に追加)。

---

## 5. 施策 2: Stage B IS monitor dual-path 配線追加 (commit B)

### 5.1 変更箇所
- ファイル: `src/alpha_factory/stage_gate.py:824-844` (= IS monitor 区画)

### 5.2 波及変更
- `AGENTS.md`: なし
- `.claude/skills/zenigame-fx-*/SKILL.md`: なし
- `config/alpha_factory/default.yaml`: なし (= step 1 で `phase2_canonical_metrics_mode` 既出)
- `docs/alpha_factory/*.md`: 後続 step (= step 2 設計時) に dual-path log 解釈ガイドを追加予定。 step 1.5 では docs 変更なし

### 5.3 現行コード

```python
# stage_gate.py:824-844
try:
    strategy = DslStrategy(genome, primitive_evaluator)
    broker = MockBroker(instrument_meta=meta)
    res = run_backtest(bars_18m, strategy, broker, backtest_config)
    bt = compute_metrics(
        res.trades,
        res.equity_curve,
        trade_count_min_for_sharpe=stage_config.trade_count_min_for_sharpe,
    )
    # T-sharpe Phase 1A: trade_sharpe_raw (v2) を使用
    is_full_sharpe = (
        float(bt.trade_sharpe_raw) if bt.trade_sharpe_raw is not None else None
    )
    is_full_total_pnl = float(bt.total_pnl)
    is_full_trade_count = bt.trade_count
except Exception as exc:
    logger.warning(
        "stage_b.is_monitor_failure",
        genome=genome.name,
        error=str(exc),
    )
```

### 5.4 変更後コード

```python
# stage_gate.py:824-862 (= 約 18 行追加)
try:
    strategy = DslStrategy(genome, primitive_evaluator)
    broker = MockBroker(instrument_meta=meta)
    res = run_backtest(bars_18m, strategy, broker, backtest_config)
    bt = compute_metrics(
        res.trades,
        res.equity_curve,
        trade_count_min_for_sharpe=stage_config.trade_count_min_for_sharpe,
    )
    # T-sharpe Phase 1A: trade_sharpe_raw (v2) を使用
    is_full_sharpe = (
        float(bt.trade_sharpe_raw) if bt.trade_sharpe_raw is not None else None
    )
    is_full_total_pnl = float(bt.total_pnl)
    is_full_trade_count = bt.trade_count
    # B Phase 2 切替コミット step 1.5: dual-path canonical 5 metrics (LOG_ONLY mode)
    # IS monitor (= bars_18m 全体 backtest) に対する dual-path 観測拡張。
    # window_days は step 1 と同じ calendar day 基準で stage_b_window_months * 30 を使用。
    # 既存 fitness 判定経路には影響させない (= regression 0、 sidecar 計算 + log のみ)。
    canonical_sidecar = _try_evaluate_canonical_five_safe(
        trades=res.trades,
        equity_curve=res.equity_curve,
        bars=bars_18m,
        live_criteria=stage_config.live_criteria,
        window_days=stage_config.stage_b_window_months * 30,
        stage_label="B_IS",
        genome_name=genome.name,
        enabled=(stage_config.phase2_canonical_metrics_mode != "disabled"),
    )
    # log 呼出も例外保護 (= step 1 と同型、 logger processor 異常時に
    # legacy 経路を巻き込まない、 完全隔離)
    try:
        _log_canonical_dual_path(
            stage_label="B_IS",
            genome_name=genome.name,
            legacy=bt,
            canonical=canonical_sidecar,
        )
    except Exception as exc:
        logger.warning(
            "stage_gate.canonical_five.log_failed",
            stage="B_IS",
            genome=genome.name,
            error=str(exc),
            error_type=type(exc).__name__,
        )
    # canonical_sidecar は payload 非添付 (= archive Parquet schema 不変、 step 1.5 範囲)
except Exception as exc:
    logger.warning(
        "stage_b.is_monitor_failure",
        genome=genome.name,
        error=str(exc),
    )
```

**重要設計判断**:
- `_try_evaluate_canonical_five_safe` / `_log_canonical_dual_path` は step 1 で確立した helper を **完全再利用** (= adapter 凍結 + helper 凍結)
- log 呼出も try/except で完全隔離 (= step 1 で Codex Round 1 [Warning] 反映済の pattern を踏襲)
- canonical_sidecar は Stage A 同様 payload 非添付 (= archive Parquet schema 不変)
- IS monitor 区画の outer try (= legacy 例外保護) はそのまま維持

### 5.5 helper 入力契約 (= step 1 で凍結済、 再掲) — Round 1 [Critical] 反映

`_try_evaluate_canonical_five_safe` の docstring (stage_gate.py:111-167) で明文化された入力契約を再掲:

| 引数 | 契約 | step 1.5 Stage B IS で渡す値 |
|---|---|---|
| `trades` | `list[BrokerTrade]` (= UTC-aware exit_time) | `res.trades` (= run_backtest 出力、 既存契約で UTC-aware) |
| `equity_curve` | `list[tuple[datetime, Decimal]]` (= 時系列順、 重複なし、 UTC-aware) | `res.equity_curve` (= 既存契約で UTC-aware) |
| `bars` | `list[PriceBar]` (= 評価窓全 bars、 UTC-aware) | `bars_18m` (= aux pipeline 入力契約で UTC-aware) |
| `live_criteria` | `Mapping[str, float\|int]` (= 必須キー 5 件) | `stage_config.live_criteria` (= MappingProxyType frozen) |
| `window_days` | `int` (= 評価窓 calendar day) | `stage_config.stage_b_window_months * 30 = 540` |
| `stage_label` | `str` (= log identifier) | `"B_IS"` |
| `genome_name` | `str` | `genome.name` |
| `enabled` | `bool` (= disabled mode で計算 skip) | `phase2_canonical_metrics_mode != "disabled"` |

**戻り値契約**: `CanonicalFiveResult \| None` — None は (a) `enabled=False` または (b) helper 内部で例外発生時 (= adapter / thresholds / evaluate_canonical_five 全件 try 内 catch、 WARN log のみ)。

**例外伝播契約**: `_try_evaluate_canonical_five_safe` は内部で全例外を catch + WARN log + None 返り (= 呼出側に raise しない)。 ただし caller 側の `_log_canonical_dual_path` は logger processor 異常で raise する可能性あり、 caller で try/except 必須 (= step 1 で確立、 § 5.4 コードに反映)。

### 5.6 ルックアヘッドバイアスチェック
N/A (= 観測のみ、 fitness 計算経路に影響なし)

### 5.7 パフォーマンスチェック
- 計算量: Stage B IS monitor で +1 回の canonical 5 metrics 計算 (= 数千 trade × O(N) 集約)
- メモリ: BarEquitySeries (~544K bars × ~80 byte ≈ 44 MB) + TradeRecord tuple (= <3 MB) の一時オブジェクト確保
- 概念設計 § 4.4 のメモリ概算: peak RSS +~50 MB / worker (= worker budget 3 GB の 2% 未満、 許容範囲内)
- **実測検証**: smoke 5 Run の `/usr/bin/time -l` で worst-case pair (= USD_JPY 18m など) の peak RSS を確認 (= acceptance B2)

### 5.8 テスト計画
- 既存 `test_stage_gate_canonical_dual_path.py` に Stage B 用テストケース追加 (= 7 ケース、 § 7 で詳述)
- 既存テストが PASS し続けることで Stage A の挙動不変を確認 (= acceptance A4)

### 5.9 リスク
- IS monitor で例外発生 → step 1 helper の `_try_evaluate_canonical_five_safe` の try/except で legacy 経路完全隔離 (= 例外注入 test で確認)
- 18m bars + dual-path で peak RSS 超過 → smoke 5 Run の `/usr/bin/time -l` で実測 (= acceptance B2)

---

## 6. 施策 3: Stage C base evaluation dual-path 配線追加 (commit B)

### 6.1 変更箇所
- ファイル: `src/alpha_factory/stage_gate.py:1162-1192` (= base evaluation 区画)

### 6.2 波及変更
- 施策 2 と同様 (= 5.2 参照)

### 6.3 現行コード

```python
# stage_gate.py:1162-1192
try:
    strategy = DslStrategy(genome, primitive_evaluator)
    broker = MockBroker(instrument_meta=meta)
    res = run_backtest(bars_holdout, strategy, broker, backtest_config)
    bt = compute_metrics(
        res.trades,
        res.equity_curve,
        trade_count_min_for_sharpe=stage_config.trade_count_min_for_sharpe,
    )
    # T-sharpe Phase 1A: trade_sharpe_raw (v2) を使用
    base_sharpe = (
        float(bt.trade_sharpe_raw) if bt.trade_sharpe_raw is not None else None
    )
    base_total_pnl = float(bt.total_pnl)
    base_max_dd_frac = float(bt.max_drawdown_pct) / 100.0
    base_trade_count = bt.trade_count
    for t in res.trades:
        if t.entry_time.date() != t.exit_time.date():
            overnight_violations += 1
except Exception as exc:
    logger.warning(
        "stage_c.base_failure",
        genome=genome.name,
        error=str(exc),
        error_type=type(exc).__name__,
    )
    base_failed = True
    reasons.append("system_failure")
```

### 6.4 変更後コード

```python
# stage_gate.py:1162-1209 (= 約 22 行追加)
try:
    strategy = DslStrategy(genome, primitive_evaluator)
    broker = MockBroker(instrument_meta=meta)
    res = run_backtest(bars_holdout, strategy, broker, backtest_config)
    bt = compute_metrics(
        res.trades,
        res.equity_curve,
        trade_count_min_for_sharpe=stage_config.trade_count_min_for_sharpe,
    )
    # T-sharpe Phase 1A: trade_sharpe_raw (v2) を使用
    base_sharpe = (
        float(bt.trade_sharpe_raw) if bt.trade_sharpe_raw is not None else None
    )
    base_total_pnl = float(bt.total_pnl)
    base_max_dd_frac = float(bt.max_drawdown_pct) / 100.0
    base_trade_count = bt.trade_count
    for t in res.trades:
        if t.entry_time.date() != t.exit_time.date():
            overnight_violations += 1
    # B Phase 2 切替コミット step 1.5: dual-path canonical 5 metrics (LOG_ONLY mode)
    # base evaluation (= bars_holdout 60d backtest) に対する dual-path 観測拡張。
    # window_days は step 1 と同じ calendar day 基準で stage_c_holdout_days を使用。
    # stress / cross_pair は別軸で step 1.5 スコープ外 (= 別 log で混入なし)。
    canonical_sidecar = _try_evaluate_canonical_five_safe(
        trades=res.trades,
        equity_curve=res.equity_curve,
        bars=bars_holdout,
        live_criteria=stage_config.live_criteria,
        window_days=stage_config.stage_c_holdout_days,
        stage_label="C_base",
        genome_name=genome.name,
        enabled=(stage_config.phase2_canonical_metrics_mode != "disabled"),
    )
    # log 呼出も例外保護 (= step 1 と同型)
    try:
        _log_canonical_dual_path(
            stage_label="C_base",
            genome_name=genome.name,
            legacy=bt,
            canonical=canonical_sidecar,
        )
    except Exception as exc:
        logger.warning(
            "stage_gate.canonical_five.log_failed",
            stage="C_base",
            genome=genome.name,
            error=str(exc),
            error_type=type(exc).__name__,
        )
    # canonical_sidecar は payload 非添付 (= archive Parquet schema 不変、 step 1.5 範囲)
except Exception as exc:
    logger.warning(
        "stage_c.base_failure",
        genome=genome.name,
        error=str(exc),
        error_type=type(exc).__name__,
    )
    base_failed = True
    reasons.append("system_failure")
```

**重要設計判断** (= 施策 2 と同型):
- helper 完全再利用、 log try/except で完全隔離、 payload 非添付。
- stage_label="C_base" は § 4.6 ログ命名規約 SSOT 準拠。

### 6.5 ルックアヘッドバイアスチェック
N/A

### 6.6 パフォーマンスチェック
- 計算量: Stage C base で +1 回の canonical 5 metrics 計算 (= 数百 trade × O(N) 集約)
- メモリ: BarEquitySeries (~60K bars × ~80 byte ≈ 5 MB) + TradeRecord tuple (= <1 MB)、 Stage A と同等規模

### 6.7 テスト計画
- 既存 `test_stage_gate_canonical_dual_path.py` に Stage C 用テストケース追加 (= 5 ケース、 § 7 で詳述)

### 6.8 リスク
- 施策 2 と同様。 worker RSS budget は Stage B より小さい (= 60d holdout)。

---

## 6.5 helper 入力契約 (= step 1 で凍結済、 再掲) — Round 1 [Critical] 反映

§ 5.5 と同型 (= Stage C base で渡す値):
- `trades` ← `res.trades` (= bars_holdout backtest 出力、 UTC-aware 既存契約)
- `equity_curve` ← `res.equity_curve` (= UTC-aware 既存契約)
- `bars` ← `bars_holdout` (= aux pipeline 入力契約で UTC-aware)
- `live_criteria` ← `stage_config.live_criteria`
- `window_days` ← `stage_config.stage_c_holdout_days = 60`
- `stage_label` ← `"C_base"`
- `genome_name` ← `genome.name`
- `enabled` ← `stage_config.phase2_canonical_metrics_mode != "disabled"`

戻り値・例外伝播は § 5.5 と同一。

---

## 7. 施策 4: dual-path test 追加 (commit B)

### 7.1 変更箇所
- ファイル: `tests/alpha_factory/test_stage_gate_canonical_dual_path.py` (= step 1 で作成済、 12 ケース)

### 7.2 追加テストケース総数 (= Round 3 改訂で 21 ケースに統一)

| Stage / 種別 | regression 0 (deep dict) | log isolation (canonical 例外) | log isolation (log helper 例外) | propagation (disabled) | 入力契約 (crash なし) | 異常系 (空 trades) | 異常系 (単一 trade) | golden 成功 | golden 失敗 | golden 境界 | 並列 log key 一意性 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Stage B IS | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | (共通) |
| Stage C base | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | (共通) |
| 共通 | - | - | - | - | - | - | - | - | - | - | 1 |

**合計 21 ケース** (= Stage B IS 10 + Stage C base 10 + 共通 1)

**重要**: Stage A の 12 ケースは step 1 で完了済 (= 既存)。 commit B では step 1.5 用に **+21 ケース** 追加。

### 7.3 Stage B IS 用テストケース (7 ケース)

```python
def test_stage_b_is_canonical_dual_path_log_only_preserves_legacy_payload():
    """LOG_ONLY mode で Stage B IS の legacy payload (= n_fold / oos_sharpes /
    median_oos_sharpe / is_full_sharpe / is_full_total_pnl / is_full_trade_count
    / unavailable_reason_counts / 他 payload 全件) が canonical 配線追加で
    1 byte も変化しないことを確認 (= acceptance A1、 deep dict comparison)。

    比較方法: phase2_canonical_metrics_mode="log_only" と "disabled" で
    StageResult 全体 (= passed / reason_codes / metrics["payload"]) が完全一致。
    """

def test_stage_b_is_canonical_log_isolation_when_canonical_raises(monkeypatch):
    """_try_evaluate_canonical_five_safe が internal で raise しても、
    Stage B IS の legacy 結果が変化しないことを確認。
    monkeypatch で `_try_evaluate_canonical_five_safe` を例外 raise する
    実装に置換 → StageResult が non-monkeypatch 版と一致。"""

def test_stage_b_is_canonical_log_helper_isolation_when_log_raises(monkeypatch):
    """_log_canonical_dual_path が raise しても (= logger processor 異常時)
    Stage B IS の legacy 結果が変化しないこと + caller 側で
    'stage_gate.canonical_five.log_failed' WARN log が出力されることを確認。"""

def test_stage_b_is_canonical_disabled_mode_skips_calculation(monkeypatch):
    """phase2_canonical_metrics_mode='disabled' で _try_evaluate_canonical_five_safe が
    None 即返り、 計算 overhead 0 を確認。 monkeypatch で
    evaluate_canonical_five 呼出が起きていないことを assert。"""

def test_stage_b_is_canonical_succeeds_for_18m_window():
    """18m 期間の bars + 数千 trade で adapter / thresholds 構築が crash なく完了し、
    dual-path log entry の `canonical_*` field が non-None で出力されることを確認
    (= acceptance B1 / C1 / C2)。 structlog capture で stage='B_IS' を指定。"""

def test_stage_b_is_canonical_handles_empty_trades_gracefully():
    """trades=[] (= 該当 genome が 1 trade も生成しない場合) でも
    helper が None or 非 raise で動作し、 legacy 結果が変化しないことを確認
    (= 異常系)。"""

def test_stage_b_is_canonical_handles_single_trade():
    """trades=[1 trade] (= 境界条件) でも crash なく動作し、
    canonical_sidecar の `trade_count == 1` であることを確認。"""
```

### 7.4 Stage C base 用テストケース (7 ケース、 Stage B IS と同型)

```python
def test_stage_c_base_canonical_dual_path_log_only_preserves_legacy_payload(): ...
def test_stage_c_base_canonical_log_isolation_when_canonical_raises(monkeypatch): ...
def test_stage_c_base_canonical_log_helper_isolation_when_log_raises(monkeypatch): ...
def test_stage_c_base_canonical_disabled_mode_skips_calculation(monkeypatch): ...
def test_stage_c_base_canonical_succeeds_for_60d_holdout(): ...
def test_stage_c_base_canonical_handles_empty_trades_gracefully(): ...
def test_stage_c_base_canonical_handles_single_trade(): ...
```

### 7.5 ゴールデン回帰 test (= Stage B IS / Stage C base 各 3 群 = 6 ケース、 Round 2 [Critical] 反映で Stage 整合)

#### Stage B IS 3 群

```python
def test_stage_b_is_canonical_golden_regression_success_genome():
    """既知の成功 genome (= bars_18m で多数 trade を生成、 IS Sharpe>0) で
    canonical_sidecar の値 (= net_pnl_after_cost / max_dd / trade_count /
    sr_session_worst_block_scale / session_block_win_rate_worst) が
    fixture-locked 期待値と一致することを確認 (= 成功群 baseline)。"""

def test_stage_b_is_canonical_golden_regression_failure_genome():
    """既知の失敗 genome (= bars_18m で 0 trade or 極小 trade) で
    canonical_sidecar が None or feasibility=False で返ることを確認
    (= 失敗群 baseline)。"""

def test_stage_b_is_canonical_golden_regression_boundary_genome():
    """境界条件 genome (= trade_count_min ちょうど境界) で
    canonical_sidecar の `gate_pass` 判定が期待 boolean と一致することを確認
    (= 境界群 baseline)。"""
```

#### Stage C base 3 群

```python
def test_stage_c_base_canonical_golden_regression_success_genome(): ...
def test_stage_c_base_canonical_golden_regression_failure_genome(): ...
def test_stage_c_base_canonical_golden_regression_boundary_genome(): ...
```

**重要**: Stage A の同等ゴールデン回帰は step 1 で実装済 (= 12 ケース内)。 Stage B IS / Stage C base は acceptance A1 (= 各 stage で 成功 / 失敗 / 境界 3 群 deep dict comparison) を満たすため両方に追加。

### 7.6 並列 log key 一意性 test (= 1 ケース、 Round 1 [Warning] 反映)

```python
def test_stage_b_is_and_c_base_log_keys_are_distinguishable(structlog_capture):
    """Stage B IS と Stage C base が同 worker / 同 genome で連続実行された場合、
    structlog 出力に stage='B_IS' と stage='C_base' が独立 entry として
    記録され、 logger kwargs key (`genome` + `stage`) で一意特定可能であることを確認。
    (= 並列 worker でも genome (= genome.name 値) で一意化、 § 4.6 ログ命名規約 SSOT 準拠。
     注: helper 引数名は `genome_name` だが logger kwargs key は `genome` で統一)
    """
```

### 7.7 acceptance A4 (= Stage A 不変) test
既存 12 ケース (= step 1 で追加) が引き続き PASS することで commit A の rename が pure refactor (動作不変) であることを保証。 追加 test 不要。

### 7.8 fixture
- `bars_18m`: 18 ヶ月分の合成 PriceBar (= 既存 fixture or 新規生成、 概念上 ~544K bars だが test fixture では小規模 (= ~5K bars) で OK、 trade 生成数の最低保証はあり)
- `bars_holdout`: 60d 分の PriceBar (= 既存 fixture 流用)
- 各 fixture は UTC-aware datetime + 適切な session bucket カバレッジ

---

## 8. acceptance criterion (= 概念設計 § 5.4 反映 + Round 1/2 [Critical] 反映)

### A. 判定結果回帰 0 (必須、 deep dict comparison)
- [A1] Stage B IS / Stage C base の **legacy `StageResult`** (= `passed` / `reason_codes` / `metrics["payload"]`) が canonical 配線追加で 1 byte も変化しないこと (= phase2_canonical_metrics_mode `log_only` vs `disabled` で `StageResult` 完全一致)。 § 7.3-7.4 の各 stage 7 ケース内 1 番目 (= regression 0 deep dict) で確認。 Stage A 同等の legacy 回帰 test は step 1 で完了済 (= 既存 12 ケース)、 step 1.5 で再実装不要
- [A2] archive Parquet schema **完全不変** (= canonical_sidecar 非添付、 既存 28+ カラム fixed schema 尊重、 schema version 変更不要、 reader 後方互換 test 不要)
- [A3] GA fitness 不変 (= test_stage_gate_canonical_dual_path.py の payload 完全比較、 step 1 と同型)
- [A4] Stage A の canonical sidecar (= dual-path log の `canonical_*` field) が step 1 と完全一致 (= commit A の rename が pure refactor 動作不変、 § 9.1 で `git diff src/alpha_factory/__init__.py` 公開 API 差分ゼロ確認)
- [A5] Stage B IS / Stage C base の **canonical sidecar** (= dual-path log の `canonical_*` field) が fixture-locked 期待値と一致 (= **§ 7.5 ゴールデン回帰 test、 各 stage 成功群 / 失敗群 / 境界群 3 群 = 計 6 ケース** で確認)。 注: A1 が legacy `StageResult` の不変、 A5 が canonical sidecar の値固定で **別軸** (= step 1.5 で同時に検証、 ただし target は異なる)

### B. 運用回帰検証 (= 別軸 partial verification)
- [B1] dual-path log が Stage B IS / Stage C base で crash なく出力 (= § 7.3 log isolation test で確認)
- [B2] smoke 5 Run で peak RSS が worker 3 GB budget 内 (= `/usr/bin/time -l` で実測、 worst-case pair (USD_JPY 18m) で確認)
- [B3] smoke 5 Run の所要時間が step 1 比 ±20% 以内
- [B4] dual-path log が legacy log (= stage_b.is_monitor_failure / stage_c.base_failure) と独立出力 (= § 7.6 並列 log key 一意性 test で確認)
- [B5] log 失敗時の WARN log (= `stage_gate.canonical_five.log_failed`) が必須 structlog kwargs key `stage` / `genome` / `error` / `error_type` を含む (= 診断不能を防止、 Round 1 [Critical] 反映)。 注: helper 引数名は `genome_name` だが logger に渡す kwargs key は `genome` で統一 (= step 1 既存実装 stage_gate.py:160-165 と整合)

### C. legacy 比較可能性 (= step 2 calibration の partial 前提)
- [C1] dual-path log の `stage` field が `"B_IS"` / `"C_base"` で正しく区別可能 (= § 4.6 ログ命名規約 SSOT)
- [C2] `legacy_*` / `canonical_*` field が同 log entry に共存
- [C3] `interpretation_note="direction_monitoring_only"` が継承

---

## 9. 実装モード

| 項目 | 内容 |
|---|---|
| 推奨モード | **incremental** (= worktree todo/B-step1.5 で 2 commit、 main マージ no-ff) |
| 判断根拠 | step 1 と同じ pattern (= adapter 凍結再利用、 stage_gate.py のみ拡張)。 計算量 ~2x のみ、 archive Parquet schema 不変。 既存 12 ケースが PASS し続けることで Stage A 不変保証 |
| 競合リスク | step 1 と独立 (= step 1 は完了済 commit 9bc6a02)、 他 worktree との競合なし |
| 想定実装時間 | **短〜中** (= 2 commit、 約 40 行追加 + 21 ケース test) |

### 9.1 commit 戦略 + commit A pure 性検証手順 (Round 1 [Warning] 反映)

```
worktree todo/B-step1.5:
  commit A: refactor(B step 1.5): rename _build_stage_a_canonical_thresholds
            → _build_canonical_thresholds_for_window (pure refactor)
  commit B: feat(B step 1.5): Stage B IS monitor + Stage C base に dual-path 配線追加

main:
  no-ff merge → main に 2 commit を保持
```

**commit A の pure 性検証手順** (= 動作不変保証):
1. pre-rename 確認: `grep -rn "_build_stage_a_canonical_thresholds" src/ tests/` で全 caller を列挙、 期待 1 caller (= stage_gate.py:145) のみ
2. rename 実施: `_build_stage_a_canonical_thresholds` → `_build_canonical_thresholds_for_window` (= 関数定義 + 1 caller のみ更新、 docstring も generic 化)
3. post-rename 確認:
   - `git diff --stat` で変更が `src/alpha_factory/stage_gate.py` 1 ファイルのみ
   - `git diff src/alpha_factory/__init__.py` (= __all__ 公開 API)、 `__init__.py` の export 不変
   - 既存テスト全 PASS: `uv run pytest tests/alpha_factory/test_stage_gate_canonical_dual_path.py` で step 1 の 12 ケース全 PASS
   - `uv run mypy src/alpha_factory/stage_gate.py` clean
   - `uv run ruff check src/alpha_factory/ tests/alpha_factory/` clean
4. commit A 単独で worktree に commit。 commit B (= behavioral wiring) と完全分離。

---

## 10. 確認事項 (= 実装前)

- [ ] step 1 detailed-design.md の 9881abe / a07f883 を再読 (= adapter / helper の前提確認)
- [ ] 既存 test (= test_stage_gate_canonical_dual_path.py の 12 ケース) を run して全 PASS 確認
- [ ] worktree todo/B-step1.5 を作成 (= main から branch off)
- [ ] commit A の rename + 既存 12 ケース PASS を確認 (= pure refactor 動作不変)
- [ ] commit B の dual-path 配線追加 + 新規 21 ケース PASS を確認 (= § 7.2 表に従い Stage B IS 10 + Stage C base 10 + 並列 log key 1)

---

## 12. follow-up (= step 1.5 スコープ外、 step 2 以降で扱う、 Round 1 反映)

step 1.5 では以下を実装しない (= scope を limit、 過度な複雑化禁止)。 ただし運用観測の文脈で記録:

1. **canonical 失敗件数閾値ベースの fail-fast サーキットブレーカ** (= Round 1 施策 2 [Critical] 部分対応): 連続 N 回 canonical 計算が失敗したら GA Run を fail-fast で停止する仕組み。 step 1.5 では WARN log のみ、 サーキットブレーカは step 2 以降の運用観測後に必要性を判断
2. **Stage A/B/C 例外注入の同型性 test** (= Round 1 施策 2 [Warning]): 同 input fixture で A/B/C 全てで例外注入し出力同型性を比較する meta-test。 step 1 と step 1.5 の test ケースで分散カバレッジ済 (= 各 stage 個別 isolation test)、 統合 meta-test は別 step
3. **CI メモリ閾値ガード** (= Round 1 施策 3 [Warning]): smoke 5 Run の peak RSS / wall time を CI で監視し、 閾値超過時に fail。 step 1.5 では手動実測 (= acceptance B2)、 CI 自動化は別 step
4. **helper Protocol 化 + ASTベース rename 検査** (= Round 1 施策 1 / 4 [Suggestion]): 静的検知の強化。 step 1.5 では grep + git diff で十分、 Protocol 化は別 step (= 過度な複雑化禁止)
5. **canonical sidecar archive Parquet schema 拡張**: 永続化層への canonical 値書き込み (= step 3 cpps_archive 統合と合わせて検討)
6. **per-fold dual-path 拡張**: Stage B 5 fold それぞれで dual-path log (= step 1.6 or step 2 内)
7. **Stage C stress / cross_pair (ii-lite) dual-path**: stress test / shadow cross_pair の dual-path log (= step 2 以降、 mission 必須軸)

---

## 11. 参考資料

- 概念設計 (Round 3 APPROVED): `devnotes/20260503-1446-B-phase2-step1.5-stage-bc-dual-path/conceptual-design.md`
- step 1 詳細設計: `devnotes/20260503-1024-B-phase2-step1-canonical-metrics/detailed-design.md`
- step 1 完了 handoff: `devnotes/20260503-1414-B-step1-complete-handoff/handoff.md`
- step 1 main commit: `9bc6a02 Merge branch 'todo/B-step1'`
- canonical_adapter.py (凍結): `src/alpha_factory/canonical_adapter.py`
- stage_gate.py (拡張対象): `src/alpha_factory/stage_gate.py:567-1378`
- canonical_metrics.py: `src/alpha_factory/canonical_metrics.py` (= TradeRecord / BarEquitySeries / evaluate_canonical_five)
- step 1 test: `tests/alpha_factory/test_stage_gate_canonical_dual_path.py` (= 12 ケース、 step 1.5 で +10 ケース追加)
