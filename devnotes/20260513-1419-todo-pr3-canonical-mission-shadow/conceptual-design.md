# PR3: canonical_metrics / mission_inf_gap shadow 配線 (audit only)

## 背景

cascade port v2 Phase 2 配線で **T061 canonical_metrics** (= canonical 5 metric 同時計算) と **T062 mission_inf_gap** (= GA Pareto f3 用 mission gap) は Phase 1 単体実装が完了 (`88b2eb8` / `4ddfa9b`)、 main flow への dual-path 配線も B Phase 2 step 1 で完了 (= `_try_evaluate_canonical_five_safe` が `stage_gate.py` の Stage A / Stage B IS / Stage B fold / Stage C base / Stage C stress / Stage C cross_pair の **全 6 経路で呼出 + LOG_ONLY mode で sidecar 計算結果を log 出力**) されている。

しかし sidecar 値は **archive Parquet に永続化されていない** (= step 1 範囲では payload 非添付 / 既存 schema 不変が明示的な制約):

```python
# stage_gate.py:826
# canonical_sidecar は payload 非添付 (= archive Parquet schema 不変、 step 1 範囲)
```

= cascade port v2 Phase 2 切替コミット 7-step segmentation の step 1 完了、 step 2 (= archive 列拡張で shadow audit 可能化) が PR3 の対象。

## 目的

Stage B IS monitor (18 ヶ月 backtest) と Stage C base 評価 (60 日 holdout) で算出した `CanonicalFiveResult` と、 そこから `evaluate_mission_inf_gap` で導出される `MissionGapResult` の主要 field を archive に **shadow 列**として書き出す。

- selection / fitness / gate 判定への影響なし (= **完全行動不変**)
- 30 ラウンド Codex 議論で確立した方針: **行動変更 PR (PR4 以降) より先に観測基盤を整える**
- canonical 5 軸ベース判定 (= LOG_ONLY → FAIL_CLOSED 切替) は後続 TODO (B Phase 2 step 3+) で扱う。 PR3 は **観測のみ**。

## 範囲

| 経路 | 既存 sidecar 変数 | PR3 で archive 列化 |
|---|---|---|
| Stage A (60 日) | `canonical_sidecar` | **対象外** (= Stage A は selection 用 fitness_pen と密結合、 観測列拡張は別 TODO で検討) |
| Stage B IS (18 ヶ月) | `canonical_sidecar_b_is` | **対象** (= Stage B 観察可能性の中核) |
| Stage B fold (per fold) | `canonical_sidecar_b_fold` | **対象外** (= fold 数分の列拡張は schema 肥大化、 fold 集約は後続 TODO で検討) |
| Stage C base (60 日 holdout) | `canonical_sidecar_c_base` | **対象** (= mission 達成性の中核) |
| Stage C stress | `canonical_sidecar_c_stress` | **対象外** (= stress 経路の比較は別 TODO で検討) |
| Stage C cross_pair (per pair) | `canonical_sidecar_cp` | **対象外** (= pair 数分の列拡張は schema 肥大化、 別 TODO で検討) |

PR3 = Stage B IS + Stage C base のみ。 残り 4 経路は後続 PR で必要に応じて拡張。

## 期待効果

### 直接的

- 既存 Stage B/C pass 個体について canonical 5 軸での評価結果が archive に永続化される
- archive 横断分析で「legacy pass vs canonical pass」 の diff を計測可能 (= cluster artifact 検出強化)
- mission_inf_gap の分布を archive で確認可能 (= 12 段 TODO 5 の docs/progress_criteria 明文化に使う実数値の根拠)

### 間接的

- PR4 (= legacy_pnl_smoke fitness 切替) で baseline 比較の指標として shadow 値を使える (= 1 RUN smoke の事前判定根拠)
- PR5 (= Stage B gate pfr_only opt-in A/B) で gate 切替前後の canonical 判定の安定性確認
- T076 synthesis Round 22 改訂 で「canonical 判定の archive 実測」 を data 根拠として明示可能

### live_criteria 達成への寄与

- **直接的**: 薄い (= 観測のみ、 判定ロジックは不変)
- **間接的**: 後続 PR (PR4 / PR5) で「canonical pass 個体が実 live_criteria でどう振る舞うか」 を archive 履歴から検証可能

## スコープ縮小判断

元案 (Codex Z Round 5) では「canonical 5 軸 全 field + mission 全 field を Stage 全経路で shadow」 だったが、 archive schema 肥大化リスク + 列維持コスト を考慮して PR3 は **最小 6 列追加**:

| 列名 | 型 | 意味 |
|---|---|---|
| `canonical_gate_pass_b_shadow` | bool nullable | Stage B IS canonical gate_pass (= 4 metric 全達成かつ invariants feasible) |
| `mission_inf_gap_b_shadow` | float nullable | Stage B IS から導出した mission_inf_gap (= 0 で達成、 正値で未達) |
| `mission_signed_margin_b_shadow` | float nullable | Stage B IS から導出した mission_signed_margin (= 任意実数、 ≥0 で達成、 archive CA #5 ordering SSOT) |
| `canonical_gate_pass_c_shadow` | bool nullable | Stage C base canonical gate_pass |
| `mission_inf_gap_c_shadow` | float nullable | Stage C base から導出した mission_inf_gap |
| `mission_signed_margin_c_shadow` | float nullable | Stage C base から導出した mission_signed_margin |

= archive Parquet schema 52 → 58 列 (= PR2 で 51 → 52 列化済から +6)。

### 削った field の根拠

- `canonical_invariants_feasible_*`: `canonical_gate_pass_*` が False のとき invariants 起因か thresholds 起因か曖昧になるが、 PR3 では `mission_inf_gap_*` の値 (= ±inf vs 有限値) で間接的に推定可能。 必要なら後続 PR で追加。
- `canonical_net_pnl_*` / `canonical_max_dd_*` / `canonical_sr_session_worst_*`: 既に `total_pnl` / `max_drawdown_pct` / `trade_sharpe_stage_b/c` が legacy 経路で記録されており、 数値差分は dual-path log で確認可能 (= 重複永続化を避ける)。
- `per_metric_shortfall`: dict / list 構造は archive 列化が複雑、 必要なら後続 PR で扱う。

## ±inf 取り扱い

`MissionGapResult.mission_inf_gap` は `[0, +inf)`、 `mission_signed_margin` は `{-inf} ∪ ℝ` を取り得る (= invariants infeasible 時の sentinel)。

PR3 では Parquet float64 互換のため、 **±inf を `None` に正規化して archive に書き込む**:

- `mission_inf_gap == +inf` → `None` (= slack=-inf 由来の極端な不足、 audit 用途では「計算不能」 同等)
- `mission_signed_margin == -inf` → `None` (= invariants infeasible の sentinel)
- canonical_sidecar が `None` (= skip / 例外 fallback) → 3 列すべて `None`

`canonical_gate_pass_*_shadow` で sentinel 起因の skip と invariants 起因の False を区別できないことは PR3 では許容 (= 必要になったら `canonical_invariants_feasible_*_shadow` を追加 PR で導入)。

## データフロー

```
stage_gate.py
  evaluate_stage_b()
    canonical_sidecar_b_is = _try_evaluate_canonical_five_safe(...)
    [PR3 新規] mission_b_is = evaluate_mission_inf_gap(canonical_sidecar_b_is) if canonical_sidecar_b_is else None
    [PR3 新規] payload["canonical_shadow_b_is"] = {
        "gate_pass": canonical_sidecar_b_is.gate_pass if canonical_sidecar_b_is else None,
        "mission_inf_gap": mission_b_is.mission_inf_gap if mission_b_is else None,
        "mission_signed_margin": mission_b_is.mission_signed_margin if mission_b_is else None,
    }
    return StageResult(payload=payload, ...)

archive.py
  collect_stage_b(stage_result)
    payload = stage_result.metrics["payload"]
    [PR3 新規] shadow_b = payload.get("canonical_shadow_b_is", {}) or {}
    [PR3 新規] row["canonical_gate_pass_b_shadow"] = shadow_b.get("gate_pass")  # bool | None
    [PR3 新規] row["mission_inf_gap_b_shadow"] = _finite_or_none(shadow_b.get("mission_inf_gap"))
    [PR3 新規] row["mission_signed_margin_b_shadow"] = _finite_or_none(shadow_b.get("mission_signed_margin"))
```

Stage C も対称な構造。 helper `_finite_or_none(x)` で `None` / `NaN` / `±inf` を `None` に正規化。

## 非目的

- canonical 5 軸ベース selection / gate 切替 (= step 3+: stage_bc_evaluator main flow 統合)
- Stage A / fold / stress / cross_pair の canonical shadow 列拡張 (= 別 PR で必要時に)
- mission_score 列との統合 / 廃止 (= mission_score は Stage C 評価後の legacy 経路 soft score、 PR3 では共存)
- canonical_invariants_feasible / per_metric_shortfall / sr_session_worst の永続化 (= 別 PR)

## 関連 TODO (12 段)

| 順 | TODO | 状態 |
|---|---|---|
| 1 | PR1: source_stage 値入力 | Completed (`e81dc85`) |
| 2 | PR2: persistence_score_shadow 列追加 | Completed (`c18551e`) |
| 3 | **PR3: canonical_metrics / mission_inf_gap shadow 配線** | **本 TODO** |
| 4 | PR4: legacy_pnl_smoke opt-in + anti-luck guard (= 行動変更) | 未着手 |
| 5 | PR5: Stage B gate pfr_only opt-in A/B (= 行動変更) | 未着手 |
| 6 | docs: progress_criteria 明文化 | 未着手 |
| 7 | scripts: out-of-cluster audit | 未着手 |
| 8 | PR6: F6/F10/F4/F7 grammar soft downweight opt-in | 未着手 |
| 9 | Stage C stratified allocation | 未着手 |
| 10 | Run 71/63 系統 warmstart 検討 | 未着手 |
| 11 | Phase 2 統合 Step 3-7 | 未着手 |
| 12 | primitive 拡張 | 将来 |

詳細議論: `devnotes/20260513-1402-handoff-pr1-pr2-postdebate/handoff.md` (= 30 Codex 議論 + 4 回監査の結論)

## リスク

| リスク | 影響 | 緩和 |
|---|---|---|
| stage_gate.py で payload 添付追加 → 既存 collect_* で KeyError 等 regression | 低 | 全 collect_* 経路で `.get(...)` 経由参照、 defensive (空 dict / None 容認) |
| ±inf 値が Parquet float64 で書き出し失敗 | 低 | `_finite_or_none` helper で事前に `None` 正規化、 unit test で検証 |
| canonical_sidecar が False (gate_pass) のときの invariants 起因 / thresholds 起因が曖昧 | 中 | PR3 では許容、 必要時に invariants_feasible 列を追加 PR で導入 |
| schema 52 → 58 で既存 Parquet (= 過去 RUN 累積) の互換性 | 低 | nullable 列追加のみで、 旧 archive の読み込み時には新列は欠損として扱える (pa.unify_schemas) |
| stage_gate.py の `metrics_envelope` を経由する経路で payload key 衝突 | 低 | 新 key `canonical_shadow_b_is` / `canonical_shadow_c_base` は既存 key と命名空間隔離 |

## 検証戦略

- pytest 全件 pass (= 既存テスト + 新規テスト)
- 既存 `test_end_to_end_writes_v2_summary_json` の既存失敗 1 件は PR3 と無関係 (= T092 fold guard fixture 問題、 handoff § 既存問題参照)
- shadow 列が null 多数になることが期待 (= 個体の多くは Stage A で fail し Stage B/C に進まない、 ただし stage_b_pass / stage_c_pass 個体で必ず populated されること)
- 1 RUN smoke は **不要** (= 完全行動不変、 archive Parquet 列追加のみで GA / 評価ロジック touch しない)

## 参考資料

- `src/alpha_factory/canonical_metrics.py` (T061 = `CanonicalFiveResult`)
- `src/alpha_factory/mission_inf_gap.py` (T062 = `MissionGapResult` / `evaluate_mission_inf_gap`)
- `src/alpha_factory/stage_gate.py:798-826` (Stage A canonical sidecar)
- `src/alpha_factory/stage_gate.py:1024-1051` (Stage B IS canonical sidecar)
- `src/alpha_factory/stage_gate.py:1493-1519` (Stage C base canonical sidecar)
- `src/alpha_factory/archive.py:64-165` (GENOMES_SCHEMA)
- `src/alpha_factory/archive.py:521-619` (collect_stage_b)
- `src/alpha_factory/archive.py:621-690` (collect_stage_c)
- `devnotes/20260513-1402-handoff-pr1-pr2-postdebate/handoff.md` (= 30 Codex 議論 + 4 回監査の結論、 PR3 推奨)
- `devnotes/20260513-1223-todo-pr2-persistence-score-shadow/` (= PR2 同型パターン)
- `devnotes/20260503-1024-B-phase2-step1-canonical-metrics/` (= 7-step segmentation の step 1 完了経緯)
