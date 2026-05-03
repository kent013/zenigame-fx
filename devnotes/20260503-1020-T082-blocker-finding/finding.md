# T082 Blocker Finding — TradeRecord 経路が main flow に未統合

**作成日時**: 2026-05-03 10:20 JST
**判定**: T082 は **現状 main 実装では実値配線不可能** (= TradeRecord 経路全体が run_ga.py / stage_gate.py の主要評価フローに未統合)
**T081 step 2-6 finding と同型**: `devnotes/20260503-0910-T081-step2-blocker-finding/finding.md`

---

## 1. Fact (調査結果、 grep ベース)

### 1.1 TradeRecord の構築箇所

```bash
find src -type f -name "*.py" -exec grep -l "TradeRecord(" {} \;
→ 結果: 0 file (= production code で構築箇所なし)

find tests -type f -name "*.py" -exec grep -l "TradeRecord(" {} \;
→ 結果: tests/alpha_factory/test_canonical_metrics.py /
        tests/alpha_factory/test_stage_bc_evaluator.py
        (= test fixtures でのみ構築)
```

### 1.2 main flow の trade 経路

```bash
# stage_gate.py の compute_metrics 呼出
grep -n "compute_metrics" src/alpha_factory/stage_gate.py
→ 5 箇所、 全て `compute_metrics(result.trades, ...)` で broker.Trade を直接消費
→ TradeRecord 経由ではない
```

`src/backtest/metrics.py:147 compute_metrics` の signature:
```python
def compute_metrics(
    trades: list[Trade],   # ← src.broker.orders.Trade (= broker.Trade)
    equity_curve: list[tuple[datetime, Decimal]],
    *,
    trade_count_min_for_sharpe: int = ...,
) -> BacktestMetrics:
    ...
```

= main flow は **broker.Trade を直接 BacktestMetrics に変換**、 TradeRecord 経由ではない。

### 1.3 stage_bc_evaluator (= TradeRecord を使う Phase 2 module) の呼出箇所

```bash
grep -rn "BCEvaluationInput\|evaluate_stage_b_pooled\|evaluate_stage_c_lite" src/ scripts/ | grep -v stage_bc_evaluator
→ 結果: 0 件 (= main flow から呼ばれていない)
```

= `stage_bc_evaluator.py` の関数群 (= `evaluate_stage_b_pooled` / `evaluate_stage_c_lite` / `apply_spread_stress` 等) は **library-only**、 run_ga.py / swim_lane.py / stage_gate.py の主要評価フローから呼ばれていない。

---

## 2. Interpretation (解釈)

### 2.1 T082 概念設計の前提誤認

T082 概念設計 (`devnotes/20260502-2300-todo-T082-spread-cost-propagation/conceptual-design.md`) は以下を前提としていた:

> 「`src/broker/orders.Trade` (= broker 経路、 Decimal 型、 spread_cost/holding_cost 値あり) から `src/alpha_factory/canonical_metrics.TradeRecord` (= alpha_factory 経路、 float 型、 spread_cost/holding_cost default 0.0) への **値伝搬** が必要」
>
> 「backtest engine 完了後、 `Trade(broker)` から `TradeRecord(alpha_factory)` を構築する箇所」

しかし grep の結果 **TradeRecord は src/ で 1 度も構築されていない**。 つまり 「broker Trade → TradeRecord 変換箇所」 自体が **存在しない**。

### 2.2 silent no-op の本質

T082 の元々の動機は「T078 で apply_spread_stress を正式実装したが、 spread_cost が default 0.0 のままで silent no-op」。 しかし実態は:

- `apply_spread_stress` 自体が main flow で呼ばれていない (= stage_bc_evaluator は library-only)
- 即ち silent no-op は **理論上の懸念**、 main flow では **そもそも spread stress 評価が動いていない**

これは T081 step 2-6 と同型の構造的問題: **Phase 1 で作られた library が Phase 2 統合を待っている状態**。

### 2.3 T078 で確立した「型差異の整合性」 は依然有効

T078 (= TradeRecord schema 拡張 + apply_spread_stress 正式実装) は **library 層の整合性確立** として完了している。 これは Phase 2 切替コミットで TradeRecord 経路が main flow に統合されるとき、 型差異 (broker Decimal vs alpha_factory float) の処理ロジックが既に存在することを意味する。

= T078 は無駄ではない。 ただし T082 (= 配線追加) は **配線先が無いため不可能**。

---

## 3. 影響と選択肢

### 3.1 T082 の選択肢

| option | 内容 | コスト | 取得価値 | 推奨 |
|---|---|---|---|---|
| A: T082 を obsolete (= 廃止) | T082 の前提が誤認だったため Open から削除、 Obsoleted 移動 | 小 | 過剰 TODO 整理 | ✅ **推奨** |
| B: T082 scope を再定義: 「stage_bc_evaluator caller 側 WARN ガード」 のみ | apply_spread_stress に on_zero_spread WARN ガード追加 (= caller が library 内のみだが将来統合時に効く) | 小 | 将来の Phase 2 切替時に役立つ | △ 価値薄 |
| C: T082 scope を拡大: stage_bc_evaluator を main flow に統合 | T081 step 2-6 と同様の上流統合 (= B Phase 2 切替コミット の前倒し) | 大 | 全体進展 | ⚠ 過大スコープ |

### 3.2 推奨: option A (= obsolete + 廃止)

理由:
1. **概念設計の前提誤認を honest に認識**: 「broker Trade → TradeRecord 変換箇所」 は存在しない
2. **T078 で library 層の整合性は既に確立済**: T082 不要 (= Phase 2 切替時に T078 の整合性ロジックがそのまま効く)
3. **過剰 TODO 整理**: 価値薄 TODO を残すと優先順位判断のノイズになる
4. **B Phase 2 切替コミット 完了時に再検討**: もし spread_cost 伝搬で問題があれば新規 TODO で対応

---

## 4. 推奨次アクション

### 4.1 即時 (本セッション残)

1. ✅ 本 finding を commit
2. T082 を **obsolete** マーク (= TODO.md → TODO-closed.md Obsoleted、 reason="TradeRecord 経路が main flow に未統合のため前提が成立せず、 B Phase 2 切替コミット完了後に再検討")
3. handoff を更新して T082 obsolete と次主作業 (= B Phase 2 切替コミット) を明記

### 4.2 後続セッション

**B Phase 2 切替コミット** が次の主作業:
- T063 stage_a_evaluator 統合
- T064 session_pass_pattern 経路 (= archive Parquet schema or sidecar)
- T065 NSGA-II selection 統合 (= run_ga.py の `_breed_next_gen` 置換)
- T066 cpps_archive.archive_admit 統合
- T067 loop_closure / warmstart 統合
- T068 failure_handling 統合
- **T082 相当 = TradeRecord 経路を main flow に統合** (= compute_metrics → TradeRecord 変換 + canonical_metrics の利用配線)

---

## 5. 構造的観察 — Phase 1 / Phase 2 の整理

### 5.1 Phase 1 で完了した library 群

| module | 状態 | 統合時期 |
|---|---|---|
| canonical_metrics (TradeRecord, BarEquitySeries, CanonicalFiveResult) | ✅ library OK、 ❌ main 未統合 | B Phase 2 切替 |
| cpps_archive (ArchiveState, ArchiveCandidate, archive_admit, AdmissionReport) | ✅ library OK、 ❌ main 未統合 | B Phase 2 切替 |
| nsga2_selection (GenerationSelectionResult, select_next_generation) | ✅ library OK、 ❌ main 未統合 | B Phase 2 切替 |
| loop_closure (WarmstartReport, warmstart_apply, eviction) | ✅ library OK、 ❌ main 未統合 | B Phase 2 切替 |
| failure_handling (RunFailureSummary, FailureSummary) | ✅ library OK、 ❌ main 未統合 | B Phase 2 切替 |
| stage_a_evaluator (T063 StageAControllerState) | ✅ library OK、 ❌ main 未統合 | B Phase 2 切替 |
| stage_bc_evaluator (BCEvaluationInput, evaluate_stage_b_pooled, evaluate_stage_c_lite, apply_spread_stress) | ✅ library OK、 ❌ main 未統合 | B Phase 2 切替 |
| observability (T071 RunObservabilityReport + 9 metric algorithm) | ✅ library OK、 ✅ stub builder で main 統合 (T080a)、 ⚠ ABDivergence のみ実値配線 (T081 step 1) | 残 8 metric は B Phase 2 切替後 |

### 5.2 main flow の現状 SSOT

main flow (= run_ga.py / stage_gate.py / swim_lane.py / archive.py / backtest/metrics.py) は:
- broker.Trade ベースの compute_metrics で評価
- elite + crossover/mutate ベースの GA selection
- GenomeArchive (Parquet) ベースの archive
- StageResult (= stage_gate.py の wrapper) を返す Stage A/B/C 評価

= 「Phase 1 完成形」 と 「Phase 2 配線完了形」 の間に **大きな gap** があり、 T081 step 2-6 / T082 はこの gap を埋める作業の一部。 個別 TODO で対応するのは構造的に困難で、 まとまった Phase 2 切替コミット として実施すべき。

---

## 6. 参考資料

- T078 完了 commit: `857eb82` (= TradeRecord schema 拡張 + apply_spread_stress 正式実装)
- T081 step 2-6 blocker finding (= 同型問題): `devnotes/20260503-0910-T081-step2-blocker-finding/finding.md`
- T082 概念・詳細設計: `devnotes/20260502-2300-todo-T082-spread-cost-propagation/`
- 前 handoff (= T081 close): `devnotes/20260503-0918-T081-closed-handoff/handoff.md`

---

## 7. Codex / human review 観点

本 finding は観察事実 (Fact、 § 1) と解釈 (Interpretation、 § 2) を分離 (C6 規範)。
- T082 判定: **REJECTED** / **OBSOLETED** (= 前提誤認、 main 統合待ちで個別 TODO としては不要)
- 推奨次アクション: option A (= T082 obsolete + 廃止、 B Phase 2 切替コミット を次主作業として再構成)
