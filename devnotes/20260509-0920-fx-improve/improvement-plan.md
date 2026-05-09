# 最終改善計画: Run 54 → Run 55 (cycle 2)

**Generated**: 2026-05-09 09:35 JST
**run_id**: `run_20260508_224819` (run-54)
**next run**: Run 55

## 合議ステータス

**CONSENSUS REACHED (cycle 2 簡略化)** — cycle 1 で Codex consensus Round 1 APPROVED 済の T091 段階 2/3 を本 cycle で実装する継続作業のため、 plan-and-design Phase B-2/3 を簡略化。 ただし新規発見 (Layer 1 archive replay の median_oos_sharpe 値取得不可) を反映し、 archive 列拡張を併設。

## 確定施策一覧

| # | 施策名 | 内容 | 変更対象 | 優先度 | 変更分類 | target_metric | failure_mode | causal_path | falsification | success_criterion | 合議結果 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | **T091 段階 2 (trade_count_full_dataset)** + **median_oos_sharpe archive 列追加** | (a) trade_count_stage_a / trade_count_stage_b / trade_count_full_dataset の 3 列追加 + Stage B 全期間 1 pass backtest 追加 + selection feasibility 切替 + _coerce_optional_int helper、 (b) median_oos_sharpe 列追加 (Layer 1 検証用、 cycle 1 で発見した archive 不在問題への対応) | src/alpha_factory/{archive.py、 stage_gate.py、 run_context.py}、 scripts/alpha_factory/run_ga.py | High | Structural | selection 圧整合化 + Layer 1 検証可能化 | run-54 で selection 圧が Stage A 60d 高頻度バイアス、 archive に median 値不在 | Stage A unique + Stage B 1 pass unique で feasibility 整合化、 median_oos_sharpe 列で Layer 1 検証可能化 | run-55 archive で `median_oos_sharpe` / `trade_count_full_dataset` 列が non-null、 selection ranking 変化観察可能 | Layer 1 検証で g70_i9/g83_i12 (run-52 archive) の median 値が判明、 0.025-0.05 区間なら段階 1 効果 verify、 <0.025 なら別根因再調査 | **APPROVE** |
| 2 | **T091 段階 3 (stage_partition_guard) + 二重 opt-in** | holdout_days 検証 + RunContext SSOT 伝搬 + archive flush 全 row 一致 + graduate/calibrate/report marker 直接受け取り + 二重 opt-in (`--allow-holdout-short` + `ZENIGAME_FX_SMOKE_TEST=1`) | src/alpha_factory/{stage_partition_guard.py、 run_context.py、 archive.py}、 scripts/alpha_factory/run_ga.py | Medium | Structural | 設計 vs 実態の不整合検出 | config holdout=60 vs 実態 14 の構造的問題 | 起動時 fail-closed で表面化、 smoke override で開発継続可能 | 既存 RUN は smoke override なしでは起動失敗、 二重 opt-in で smoke override 経路確保 | run-55 を smoke override (二重 opt-in) で実行成功、 archive marker 全 row 一致、 graduate / calibrate / report に SMOKE prefix | **APPROVE** |

## 既存 detailed-design.md (commit 4624c7a) からの追加変更

cycle 1 で実装済の段階 1 (median 0.05 → 0.025) はそのまま維持。 段階 2/3 で以下を追加:

### 段階 2 追加: median_oos_sharpe archive 列

GENOMES_SCHEMA:
```python
pa.field("median_oos_sharpe", pa.float64(), nullable=True),
```

template:
```python
"median_oos_sharpe": None,
```

`evaluate_stage_b` の payload で既に `"median_oos_sharpe": median_oos` (line 1265) として出力済。 collect_stage_b で archive 行に書き込みを追加:
```python
mos = _opt_float(payload, "median_oos_sharpe")
if mos is not None:
    row["median_oos_sharpe"] = mos
```

→ 後続の Layer 1 検証 (run-52 を再 RUN するか、 archive 拡張 backfill) で個体単位 median 値が取得可能。

## 次 RUN 戦略

- **run-55 を smoke override で実行**:
  - `ZENIGAME_FX_SMOKE_TEST=1 uv run python scripts/alpha_factory/run_ga.py --allow-holdout-short --run-id run_<TIMESTAMP> --instrument EUR_JPY --population-size 96 --generations 60 --mutation-rate 0.5 --seed 100 --max-workers 2`
- Smoke RUN なので:
  - graduate 判定強制 SKIP
  - calibrate-gate history append 強制 SKIP
  - report 名 `SMOKE-run-55.md`
- 検証目標:
  - archive 新列 (trade_count_full_dataset / median_oos_sharpe / etc) が non-null
  - selection ranking が前 RUN と異なる個体を上位化するか (段階 2 効果)
  - holdout_short_override marker が全 row True、 archive flush 検証通過

## 保留事項

| # | 仮説 | 最小変更案 | 検証条件 |
|---|---|---|---|
| H_layer1 | T091 段階 1 が g70_i9 / g83_i12 を Stage B pass させるか | run-52 archive を **再 RUN** で median_oos_sharpe を archive 出力させる、 または別の archive backfill タスク | 段階 2 完了後の独立タスク (本 cycle 範囲外) |

## 次フェーズ申し送り

### Phase C (詳細設計) で確認すべき事項

1. **既存 detailed-design.md (cycle 1 commit) は段階 2/3 部分そのまま流用可能**
2. **追加変更**: median_oos_sharpe 列追加 (4 段伝搬: GENOMES_SCHEMA + template + collect_stage_b + 新規 consumer は不要)
3. **smoke RUN の実行手順を runbook に明記** (`docs/alpha_factory/runbook.md` 更新)

### 改善計画の使命整合性

- ✅ live_criteria 全指標は維持
- ✅ 取引回数削減なし
- ✅ オーバーナイト保有なし
- ✅ archive 値伝搬漏れ防止 (4 段伝搬契約遵守)
- ✅ Reactive 兆候なし (cycle 1 verified を踏襲、 段階 2/3 は元設計通り)

### 重要な期待設定

- **run-55 (smoke) で graduate=0 が継続するのは設計通り**: smoke override で graduate 判定強制 SKIP のため
- 真の Layer 1 検証は段階 2 完了後の独立タスク (run-52 archive backfill or run-52 再 RUN)
- 真の Layer 2 検証は段階 2/3 完了後 + non-smoke の本 RUN (= dataset 延長 or holdout=14d 整合化が前提) で実施
