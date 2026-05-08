# 詳細設計: Run 53 → Run 54 施策

**Generated**: 2026-05-09 07:35 JST
**改善計画**: `devnotes/20260509-0703-fx-improve/improvement-plan.md`

## 使命・制約 (絶対遵守、 codex-review 継承)

### FX 固有の絶対制約 (再掲)

- イントラデイ前提
- ロング・ショート両方向許容
- スワップ・スプレッドを fitness に反映 (見かけの PnL ではなく純利益)

## 施策一覧

| # | 施策名 | 変更ファイル | target_metric |
|---|---|---|---|
| C1 | T091 実装 (Stage B gate redesign Phase 1) — 既存 detailed design (commit 4624c7a) を流用 + 監視ポイント追加 | src/alpha_factory/{stage_gate.py、 archive.py、 stage_partition_guard.py、 run_context.py}、 scripts/alpha_factory/run_ga.py、 config/alpha_factory/default.yaml | Stage B pass 率、 Sharpe / PnL 必要条件充足率 |

---

## C1: T091 実装 (Stage B gate redesign Phase 1)

### 既存設計の参照

**SSOT**: `devnotes/20260508-1203-stage-b-gate-redesign/detailed-design.md` (v3 APPROVED at Codex Round 5)

本 cycle では既設計を **そのまま実装**。 plan-and-design Phase B の Codex consensus で APPROVE 確定済み (Round 1)。 追加要請は 2 点のみ:

1. 失格理由の分解ログ必須化 (詳細は §C1.1)
2. 5 監視ポイントの実装段階での観測 (詳細は §C1.2)

### target_metric / failure_mode / causal_path / falsification / success_criterion

(improvement-plan.md より転記、 Codex consensus Round 1 で APPROVED)

| 項目 | 内容 |
|---|---|
| target_metric | Stage B pass 率、 Sharpe / PnL 必要条件充足率 |
| failure_mode | run-53 で Stage A pass=1439 全員が `median_oos_sharpe<min` AND `positive_fold_ratio<min` で blocked、 graduate=0 |
| causal_path | Lo (2002) SE 公式から median_oos SE ≈ 0.10、 0.05 閾値が真値 SR=0.05 検出力 50%、 0.025 で 60% に拡張。 trade_count_full_dataset で selection 圧整合化。 stage_partition_guard で holdout 不整合顕在化 |
| falsification | run-52 archive replay で Stage B pass=0 継続なら H_A1' 仮説棄却 |
| success_criterion | Layer 1 archive replay で Stage B pass>=1、 Layer 2 RUN で trade_count_full_dataset>=50 + total_pnl>=50,000 個体 >=1 |

### C1.1: 失格理由分解ログの必須化 (Codex 追加要請、 Round 1 review 反映)

**現状**: `evaluate_stage_b` の reasons リストに `"median_oos_sharpe<min"` / `"positive_fold_ratio<min"` / `"all_folds_unavailable"` 等が append される。

**追加要請**: 各 RUN 完了後、 reasons の **single-condition vs multi-condition** 集計を `summary.json` に記録。 これにより「median のみで blocked」 vs 「median + pfre 両方で blocked」 を分離して観察可能にする。

**実装** (Codex Round 1 [Critical] [Warning] 反映):

`scripts/alpha_factory/run_ga.py` の RUN 完了時 summary 出力部に以下追加:

```python
def compute_reason_breakdown(archive_df):
    """Stage B failure reason の single vs multi 分解。

    Round 1 Codex review 修正:
    - [Critical] reasons=[] (空白/改行のみ) で multi_reason[""] 計上回避
    - [Warning] 非文字列入力で例外化を防止
    - [Suggestion] 重複 reason (a;a) を set で正規化
    """
    sb_fail = archive_df[(archive_df["stage_a_pass"]==True) & (archive_df["stage_b_pass"]==False)]
    breakdown = {
        "total_failures": len(sb_fail),
        "single_reason": {},
        "multi_reason": {},
    }
    for _, r in sb_fail.iterrows():
        reasons_str = r.get("stage_b_reason_codes")
        # [Warning] 非文字列入力ガード
        if not isinstance(reasons_str, str):
            continue
        if not reasons_str:
            continue
        # [Suggestion] set で重複正規化
        reasons = sorted({s.strip() for s in reasons_str.split(";") if s.strip()})
        # [Critical] reasons=[] (空白/改行のみ) は skip
        if len(reasons) == 0:
            continue
        if len(reasons) == 1:
            key = reasons[0]
            breakdown["single_reason"][key] = breakdown["single_reason"].get(key, 0) + 1
        else:
            key = "+".join(reasons)
            breakdown["multi_reason"][key] = breakdown["multi_reason"].get(key, 0) + 1
    return breakdown

# summary に記録
summary["stage_b_reason_breakdown"] = compute_reason_breakdown(archive_df)
```

**追加テスト** (Round 1 review 反映):
- `test_compute_reason_breakdown_empty_string` — 空文字列、 改行のみ、 空白のみ で skip (multi_reason[""] 不発)
- `test_compute_reason_breakdown_non_string_input` — None / NaN / int / list で skip (例外なし)
- `test_compute_reason_breakdown_duplicate_reasons` — `"median_oos_sharpe<min;median_oos_sharpe<min"` → single_reason に 1 計上 (set 正規化)

**期待効果**: 次 RUN 完了後の summary.json で
- run-52 (現行): single=`median_oos_sharpe<min`(?件) + multi=`median+pfre`(?件) を分離記録
- run-54 (T091 後): single 分布の変化を観測可能、 「median 緩和 → single fail が pfre のみに移行」 を verify

### C1.2: 5 監視ポイントの実装段階観測 (Codex 追加要請)

**監視 1**: Stage B 失格理由の分布 (single vs multi、 §C1.1 で実装)
**監視 2**: `n_fold_effective` 分布の世代推移
**監視 3**: `trade_count_full` 下限違反率 (= trade_count_full_dataset<50 の率)
**監視 4**: spread/swap 反映後の PnL 符号反転率 (Stage A pnl_raw vs pnl_after_costs の比率、 既存 stage_a_evaluator で計算済値を archive 経由で取得)
**監視 5**: Stage C への通過母数 (現状 0 張り付き)

**実装方針**:
- 監視 1: §C1.1 で確立
- 監視 2: 既存 archive `n_fold_effective` 列の世代別 quantile を summary.json に追加
- 監視 3: 新列 `trade_count_full_dataset` の集計 (count <50, count >=50 の比率) を summary.json に追加
- 監視 4: archive `total_pnl` (Stage A 値) と `total_pnl_stage_a` の符号比較は既存 sidecar で実装済 (T033) → 既存仕様の確認のみ
- 監視 5: 既存 summary.json に Stage C pass 数は記録済 → run-report 表示確認のみ

#### summary.json 拡張 (新キー追加、 Round 1 [Warning] 反映: schema versioning)

既存の `schema_version: "1.1"` (summary.json 既存 key) の bump で後方互換性を担保。 新キー追加は `schema_version: "1.2"` で識別:

```json
{
  "schema_version": "1.2",
  "stage_b_reason_breakdown": {
    "total_failures": 1439,
    "single_reason": {"median_oos_sharpe<min": 0, "positive_fold_ratio<min": 0},
    "multi_reason": {"median_oos_sharpe<min+positive_fold_ratio<min": 1439}
  },
  "n_fold_effective_by_generation": {
    "0": {"median": 10, "p25": 8, "p75": 10},
    "...": "..."
  },
  "trade_count_full_dataset_distribution": {
    "below_50": 358,
    "at_or_above_50": 7378,
    "below_rate": 0.041
  }
}
```

**後方互換性方針**: 既存 consumer (run-report 等) は schema_version を読み、 1.1 と 1.2 で分岐。 1.2 の新キーが欠落していても旧 consumer 経路で動作 (警告 log のみ)。 strict consumer (今後追加分) は schema_version >= 1.2 を要求。

### 変更箇所 / 波及変更 (既設計より転記、 変更なし)

参照: `devnotes/20260508-1203-stage-b-gate-redesign/detailed-design.md` の各施策 (1)(2)(3) セクション。

ファイル変更:
- `config/alpha_factory/default.yaml` (median 0.025、 max_cycle_seconds 18000)
- `src/alpha_factory/stage_gate.py` (StageGateConfig、 evaluate_stage_b で trade_count_stage_b 計算)
- `src/alpha_factory/archive.py` (3 列追加 + holdout_short_override)
- `src/alpha_factory/stage_partition_guard.py` (holdout_days 検証)
- `src/alpha_factory/run_context.py` (holdout_short_override / smoke_test_mode field)
- `scripts/alpha_factory/run_ga.py` (二重 opt-in、 IndividualCacheEntry 拡張、 summary 拡張)

波及変更:
- `AGENTS.md`: smoke test 運用 + archive 列定義の説明追加
- `docs/alpha_factory/runbook.md`: smoke test 運用ガイド + Phase 1 後想定 RUN 時間 4-5 時間
- `docs/alpha_factory/stage-gates.md`: trade_count_full_dataset 定義 + holdout_short_override 契約
- `docs/alpha_factory/sharpe-rescale.md`: 検出力 60% 計算明記

### ルックアヘッドバイアスチェック

primitive 変更を含まないため該当なし。

### パフォーマンスチェック

- 施策 1: 性能影響なし (閾値変更のみ)
- 施策 2: Stage B 1 pass 追加で +37% wall-time (180min → 247min)。 24GB / 6 worker 制約は worker 数に影響なし。 trade list 即破棄で RSS 影響軽減
- 施策 3: holdout 検証 = O(1)、 性能影響なし

### テスト計画 (既設計より転記 + 監視テスト追加)

参照: `devnotes/20260508-1203-stage-b-gate-redesign/detailed-design.md` の各施策テスト計画 + 統合テスト。

**追加テスト** (本 cycle の C1.1 / C1.2 対応):
- `test_compute_reason_breakdown_single_and_multi` — single_reason / multi_reason の分離計算
- `test_summary_json_records_n_fold_effective_by_generation` — 世代別 quantile が non-empty
- `test_summary_json_records_trade_count_full_distribution` — below_50 / at_or_above_50 の集計

### リスク

- **副作用**: 既存 RUN は holdout=14 日で動作していたため、 本変更後の最初の RUN は **fail-closed 起動失敗**する。 これは intentional (= F6 構造的問題の表面化)
- **緊急回避**: 二重 opt-in (`--allow-holdout-short` + `ZENIGAME_FX_SMOKE_TEST=1`) で smoke test 経路を確保
- **後退リスク**: 施策 2 の Stage B 1 pass で例外 → trade_count_full_dataset=None → 後方互換 fallback (Stage A trade_count) → 旧 selection と同等動作
- **マージ衝突**: 施策 1-3 は別 worktree で実装し、 順次 main マージ。 selection_score schema bump (v3_4) は施策 2 で確定、 提案 2 (n_fold_effective=0 ガード) の v3_5 とは別 cycle で分離

### 実装モード

- **incremental** (3 段階分割実装、 worktree 分離)
- 順序: 施策 1 (median 0.025) → 施策 2 (trade_count_full_dataset) → 施策 3 (partition guard)
- 各段階で archive replay 検証 + tests pass + Codex impl-review APPROVED → main マージ

---

## 並行新規 TODO 登録 (今 cycle 概念設計のみ、 実装は次 cycle)

### C2: n_fold_effective=0 上位化ガード (新規 TODO)

**Codex consensus Round 1 で MODIFY**: 今 cycle 概念設計のみ。 実装は次 cycle。

**設計範囲**:
- selection_score に「評価可能性ペナルティ」 1 要素を追加
- IndividualCacheEntry field 追加は **回避** (スキーマ衝突リスク)
- T091 同時期の schema bump 競合は高リスク → `v3_4_full_dataset_feasibility` (T091) と `v3_5_eval_capability_priority` (本 TODO) を別 cycle で分離

**Phase D 申し送り**: 本 cycle 完了後、 `/zenigame-fx-alpha-design n_fold_effective_zero_guard` で正規フロー (概念設計 → Codex review → 詳細設計 → Codex review) を別 devnotes で実施。 TODO 登録は次 cycle で `/zenigame-fx-todo-add` 経由。

---

## Run 54 実行パラメータ

| パラメータ | 値 | R53 からの変更 |
|---|---|---|
| seed | 100 | 同一 (baseline 維持で因果同定優先) |
| generations | 60 | 同一 |
| population_size | 96 | 同一 |
| mutation_rate | 0.5 | 同一 |
| crossover_rate | 0.7 | 同一 |
| tournament_size | 3 | 同一 |
| max_clause | 2 | 同一 |
| **stage_b_median_oos_sharpe_min** | **0.025** | 0.05 → 0.025 (T091 施策 1) |
| **trade_count_full_dataset 列** | 新規 | T091 施策 2 |
| **stage_partition_guard.holdout_days** | 60 (config 値変更なし) | 検証ロジック追加 (T091 施策 3) |
| **improve_cycle.max_cycle_seconds** | 18000 | 3600 → 18000 (T091 +37% コスト対応) |

## 全体テスト戦略

- 単体テスト: 各施策の helper / config / archive 機能
- 統合テスト: archive replay (run-52 fixture) で施策 1 (median 緩和) の効果検証
- E2E: smoke test (`ZENIGAME_FX_SMOKE_TEST=1` + `--allow-holdout-short` + `--generations 5`) で全段階の協調動作 verify
- 監視テスト: §C1.2 の 5 監視ポイントが summary.json に記録されることを verify

## 全体リスク

- **使命達成への寄与**: T091 単独では使命達成 (Stage C pass + cross-pair ii-lite + live_criteria 全充足) には到達しない。 必要条件 (Stage B pass + trade>=50 個体出現) のみ満たす
- **Layer 1 検証先行**: 次 RUN 前に run-52 archive replay で T091 の有効性を verify、 0 件 pass なら Layer 2 RUN は実施せず別根因を再調査
- **後退観測**: 施策 1-3 を入れた最初の RUN は holdout 不整合で fail-closed 起動失敗する → smoke override で一時継続 or Phase 2 で dataset 延長を先行

---

## 実装時 Reminder (Codex design-review Round 2 [Warning] [Suggestion] 反映)

実装フェーズで以下を遵守:

### R1. max_cycle_seconds の literal grep 限界 ([Warning])

`max_cycle_seconds` の literal grep で no-op verified だが、 関連参照 (`timeout` / `deadline` / `cycle_seconds`) の見落とし余地が残る。 実装前チェックリスト 1 行追加:

```
- [ ] `improve_cycle.max_cycle_seconds` を直接参照しない関連 keyword (timeout / deadline / cycle_seconds) を grep で全リポジトリ検索し、 動的 config 参照経路がないことを verify
```

### R2. schema_version の string 比較禁止 ([Suggestion])

`schema_version >= "1.2"` を文字列比較で実装しない (= `"1.10"` 問題)。 tuple parse または enum を使う:

```python
def _parse_schema_version(s: str) -> tuple[int, int]:
    parts = s.split(".")
    return (int(parts[0]), int(parts[1]) if len(parts) > 1 else 0)

# 比較
if _parse_schema_version(summary["schema_version"]) >= (1, 2):
    # 1.2 以降の処理
    ...
```

### R3. canonical key 整合性 ([Suggestion])

`stage_b_reason_codes` の区切り順を `sorted(set(...))` に固定した点は consumer 側でも同じ canonical key を前提にする。 run-report / replay コードで `multi_reason["x+y"]` に対応する key 順序が `sorted(set(...))` で取得されることを verify。

---

## 使命・禁止事項チェック

- ✅ 禁止事項 1 (期間延長): Stage B window / wf 構造は変更せず閾値のみ
- ✅ 禁止事項 2 (見栄え): Lo 2002 SE 公式に基づく noise-floor 整合化、 数値操作ではない
- ✅ 禁止事項 3 (GA ハック): selection_score の構造変更は feasibility 整合化のためで GA メカニズム自体は不変
- ✅ 禁止事項 4 (live_criteria 緩和): live_criteria.sharpe_min / trade_count_min は不変、 Stage B 内部閾値のみ
- ✅ 禁止事項 5 (過度に複雑): NSGA-II 等は Phase 3 範囲、 本 cycle は incremental 最小スコープ
- ✅ 禁止事項 6 (取引回数削減): trade_count_full_dataset で全期間 trade 数を要求、 削減方向ではない
- ✅ 禁止事項 7 (オーバーナイト): intraday 前提維持
- ✅ 禁止事項 8 (値伝搬漏れ): 4 段伝搬契約遵守の設計
