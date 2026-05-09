# 詳細設計: Run 54 → Run 55 施策 (cycle 2)

**Generated**: 2026-05-09 09:38 JST
**改善計画**: `devnotes/20260509-0920-fx-improve/improvement-plan.md`

## 既設計の流用

**SSOT**: `devnotes/20260508-1203-stage-b-gate-redesign/detailed-design.md` (v3 Codex APPROVED at Round 5、 cycle 1 で段階 1 のみ実装済)

cycle 2 では段階 2/3 を実装。 cycle 1 の `devnotes/20260509-0703-fx-improve/detailed-design.md` (Codex design-review Round 2 APPROVED) も継承。

## 本 cycle で追加する変更 (cycle 1 既設計に対する差分)

### 追加施策: median_oos_sharpe archive 列追加

cycle 2 analyze-run で発見した「archive に median_oos_sharpe 値不在」 問題への対応。 段階 2 (archive 列拡張) と併せて以下を追加:

#### archive 4 段伝搬

**(1) GENOMES_SCHEMA**:
```python
# src/alpha_factory/archive.py
pa.field("median_oos_sharpe", pa.float64(), nullable=True),
```

**(2) _create_row_template**:
```python
"median_oos_sharpe": None,
```

**(3) collect_stage_b**:
```python
# evaluate_stage_b の payload に既に "median_oos_sharpe": median_oos が出力されている (stage_gate.py:1265)
# collect_stage_b で archive 行に書き込みを追加
mos = _opt_float(payload, "median_oos_sharpe")
if mos is not None:
    row["median_oos_sharpe"] = mos
```

**(4) consumer (Phase 1 Layer 1 検証用)**:
- 段階 2 完了後の Layer 1 verification スクリプトで使用
- 当面 run-report に表示は不要 (発展タスク)

#### テスト

- `test_archive_persists_median_oos_sharpe_per_genome` — collect_stage_b が payload median_oos_sharpe → archive 行に non-null 書き込み
- `test_legacy_archive_compat_median_oos_null` — 旧 archive (新列なし) で読み込み null 許容

## 段階 2: trade_count_full_dataset (cycle 1 既設計を流用)

参照: `devnotes/20260509-0703-fx-improve/detailed-design.md` の C1 セクション内「施策 2: trade_count_full_dataset」。

主要内容 (再掲):
- 3 列追加: `trade_count_stage_a` / `trade_count_stage_b` / `trade_count_full_dataset`
- Stage B 全期間 1 pass backtest 追加 (+37% wall-time 推定、 200d 評価が 67d 評価に増加)
- selection_score の feasibility 切替 (`trade_count_full_dataset >= entry_count_min`)
- _coerce_optional_int helper (NaN/pd.NA/np.bool_/負数/非整数 拒否)
- T044 「Stage A 値固定」 契約遵守 (collect_stage_b で `row["trade_count"] = tc` 上書き分岐削除)
- IndividualCacheEntry に `trade_count_full_dataset` field 追加

cycle 2 で追加: median_oos_sharpe 列追加 (上述)

## 段階 3: stage_partition_guard + 二重 opt-in (cycle 1 既設計を流用)

参照: `devnotes/20260509-0703-fx-improve/detailed-design.md` の C1 セクション内「施策 3: stage_partition_guard holdout_days 検証 + 二重 opt-in」。

主要内容 (再掲):
- holdout_days 検証 (calendar 日数で expected_days * 0.8 未満なら fail)
- 二重 opt-in escape hatch (`--allow-holdout-short` + `ZENIGAME_FX_SMOKE_TEST=1`)
- RunContext SSOT 伝搬 (`holdout_short_override` / `smoke_test_mode` field 追加)
- archive flush で全 row marker 完全一致要求 + 二重 opt-in 厳格化 (final_allow = AND)
- graduate / calibrate / report で marker 直接受け取り (SSOT)
- `_testing_smoke_test_override` のリネーム (test 専用)
- np.bool_ 正規化 (isinstance check)

## 統合実装ステップ

1. **施策 2 実装** (worktree `worktrees/todo-T091-stage2`)
   - archive 列追加 (trade_count_stage_a/b/full_dataset + median_oos_sharpe = 計 4 列)
   - Stage B 全期間 1 pass backtest 追加 (evaluate_stage_b)
   - selection_score feasibility 切替 + _coerce_optional_int helper
   - T044 上書き分岐削除
   - tests + ruff + mypy
   - Codex impl-review APPROVED → main マージ

2. **施策 3 実装** (worktree `worktrees/todo-T091-stage3`)
   - stage_partition_guard holdout_days 検証
   - RunContext SSOT field 追加
   - 二重 opt-in (CLI + env var)
   - archive flush 全 row marker 検証
   - graduate / calibrate / report で marker 直接受け取り
   - tests + ruff + mypy
   - Codex impl-review APPROVED → main マージ

3. **smoke RUN-55 実行**:
   ```bash
   ZENIGAME_FX_SMOKE_TEST=1 uv run python scripts/alpha_factory/run_ga.py \
     --allow-holdout-short \
     --run-id run_<TIMESTAMP> \
     --instrument EUR_JPY --population-size 96 --generations 60 \
     --mutation-rate 0.5 --seed 100 --max-workers 2
   ```

## 全体テスト戦略

- 単体: 各施策の helper / config / archive 機能
- 統合: archive 4 段伝搬 + 二重 opt-in 経路 + RunContext SSOT
- E2E: smoke RUN で全段階の協調動作 verify

## 全体リスク

- **Stage B 1 pass backtest の追加で wall-time +37%** (180min → 247min)、 RAM 制約 24GB / 6 worker (1 worker 3GB) は影響なし
- **next RUN は smoke override で実行**、 graduate / calibrate / report は smoke として処理 (production 経路と分離)
- **Layer 1 検証は本 cycle では未完**: run-52 archive backfill または再 RUN が独立タスク

## 使命・禁止事項チェック

- ✅ 禁止事項 1 (期間延長): 段階 3 で holdout 期間を延長せず、 整合性検証のみ
- ✅ 禁止事項 4 (live_criteria 緩和): 不変
- ✅ 禁止事項 8 (値伝搬漏れ): 4 段伝搬契約遵守、 median_oos_sharpe 列も同様

## Codex review

cycle 1 の Codex design-review Round 2 で APPROVED 済の設計を流用。 本 cycle 追加分 (median_oos_sharpe 列) は 4 段伝搬の最小拡張で、 Codex review は impl-review 段階で実施。
