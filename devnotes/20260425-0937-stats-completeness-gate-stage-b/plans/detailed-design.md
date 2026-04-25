# 詳細設計: Stage B 統計可観測性ハード契約 (Metric Completeness Gate)

## 使命・制約 (絶対遵守)

### zenigame-fx Alpha Factory 使命
live_criteria 全指標同時充足 + (ii-lite) 通過で使命達成。
絶対制約: イントラデイ / ロング・ショート両方向 / スワップ・スプレッド反映。

### 禁止事項
1. A・B・C 評価期間を根拠なしに延長
2. 見た目の数値改善
3. GA ハック
4. live_criteria 緩和
5. 過度な複雑化
6. 取引回数削減で成績を見せる
7. オーバーナイト保有前提

### コーディングルール
- バグ修正はテストファースト: 再現最小テスト → FAIL 確認 → 修正 → PASS
- 全施策にテスト必須
- テスト命名: 振る舞いを説明する汎用名 (Run 名・日付・session-id NG)
- `uv run pytest tests/alpha_factory/`
- `uv run ruff check src/ tests/` / `uv run mypy src/`
- Python 3.13 + numpy + pandas

## 概念設計リファレンス

`devnotes/20260425-0937-stats-completeness-gate-stage-b/conceptual-design.md` (Round 3 APPROVED)

## 施策一覧

| # | 施策名 | 変更ファイル | 優先度 |
|---|--------|------------|--------|
| 1 | `wf_min_unique_dates()` helper を `walk_forward.py` に切り出し | `src/alpha_factory/walk_forward.py` | High |
| 2 | LaneManager で観測日数充足検査 (skip-path) | `src/alpha_factory/swim_lane.py` | High |
| 3 | Stage B 観察可能性メトリクス追加 (monitor only) | `src/alpha_factory/stage_gate.py` | High |
| 4 | archive schema 拡張 (3 列追加) | `src/alpha_factory/archive.py` | High |
| 5 | run-report 強化 (世代別 reason histogram + 分布) | `scripts/alpha_factory/generate_run_report.py` | Medium |
| 6 | テスト追加 | `tests/alpha_factory/` 各所 | High |
| 7 | docs 更新 (`stage-gates.md`, `genome-archive-schema.md`) | `docs/alpha_factory/` | Medium |

## 施策 1: `wf_min_unique_dates()` helper 切り出し

### 変更箇所
- ファイル: `src/alpha_factory/walk_forward.py` (末尾に追加)

### 波及変更
- `AGENTS.md`: なし (内部 API、CLI 影響なし)
- `.claude/skills/`: なし
- `config/alpha_factory/default.yaml`: なし
- `docs/alpha_factory/`: `stage-gates.md` / `terminology.md` に helper 言及を追加 (**必須**。施策7と整合)

### 変更後コード (Round 2 改訂: 循環 import 回避のため `int` 引数版に変更)

```python
# src/alpha_factory/walk_forward.py 末尾に追加 (StageGateConfig import なし)

def wf_min_unique_dates(
    train_days: int, embargo_days: int, test_days: int
) -> int:
    """make_wf_folds の sufficiency 最小観測日数 (1 fold ぶん)。

    `make_wf_folds` は `train_days + embargo_days + test_days > n_unique_dates`
    のとき空 list を返す (walk_forward.py:85-88)。本関数はその閾値を
    上位レイヤから参照するための SSOT 共有 helper。

    `make_wf_folds` 内部の `fold_len` 計算もこの helper に置き換え、
    SSOT の二重化を避ける (Round 1 review #1 Warning 対応)。
    """
    return int(train_days) + int(embargo_days) + int(test_days)


def n_unique_dates(bars: "list[PriceBar]") -> int:
    """`bars` の bar_time から UTC date を抽出した unique 日数を返す。"""
    seen: set = set()
    for b in bars:
        seen.add(b.bar_time.date())
    return len(seen)
```

**設計確定**: Round 1 review #1 Critical 対応で `StageGateConfig` を引数で受けず int 3 つで受ける形にする (循環 import 回避)。`make_wf_folds` 内部の既存 `fold_len = train_days + embargo_days + test_days` 行も同 helper を呼ぶように差し替える (SSOT 二重化防止)。

### ルックアヘッドバイアスチェック
- 該当なし (helper のみ、bar 計算なし)

### パフォーマンスチェック
- `n_unique_dates` は O(n_bars) の単純 set 構築。Stage B 呼び出し前に 1 回のみ実行。問題なし。

### テスト計画
- 新規: `tests/alpha_factory/test_walk_forward.py`
  - `test_wf_min_unique_dates_returns_train_plus_embargo_plus_test`
  - `test_n_unique_dates_counts_distinct_utc_dates`

### リスク
- 循環 import の懸念 → ローカル import で回避

---

## 施策 2: LaneManager で観測日数充足検査 (skip-path)

### 変更箇所
- ファイル: `src/alpha_factory/swim_lane.py` (`LaneManager.generate()` 内、Stage A pass 後 Stage B 評価前)

### 波及変更
- `AGENTS.md`: なし (内部実行フロー)
- `docs/alpha_factory/swim-lane.md`: Stage B skip-path の挙動を 2-3 行で追記
- `docs/alpha_factory/stage-gates.md`: Reason Code 語彙に `stage_b_window_underfilled` を canonical で追加

### 現行コード (swim_lane.py:483-503)
```python
            if not a_result.passed:
                continue
            stage_a_pass += 1
            # Stage B
            b_result = evaluate_stage_b(
                genome,
                lane.bars_18m,
                lane.meta,
                bt_cfg,
                self._primitive_evaluator,
                self._stage_gate_config,
            )
            self._archive.collect_stage_b(
                genome,
                lane.lane_id,
                lane.generation_count,
                b_result,
            )
```

### 変更後コード (Round 2 改訂)

**Round 1 review #2 Warning 対応**:
- `n_unique_dates(lane.bars_18m)` は **lane ごとに 1 回** ループ外で計算 (個体ごと再計算回避)
- underfilled payload の `is_full_*` を `None` に変更 (archive で誤上書きされない)

```python
        # ループ外、lane 単位で 1 回だけ
        lane_n_unique_dates = n_unique_dates(lane.bars_18m)
        wf_min_dates = wf_min_unique_dates(
            self._stage_gate_config.wf_train_days,
            self._stage_gate_config.wf_embargo_days,
            self._stage_gate_config.wf_test_days,
        )
        # ... (個体ループ)
            if not a_result.passed:
                continue
            stage_a_pass += 1
            # Stage B 入力窓充足契約 (observed-day SSOT)
            if lane_n_unique_dates < wf_min_dates:
                # skip-path: evaluate_stage_b を呼ばず underfilled で記録
                b_result = StageResult(
                    stage="B",
                    passed=False,
                    metrics={
                        "stage": "B",
                        "genome_name": genome.name,
                        "n_bars": len(lane.bars_18m),
                        "wall_time_seconds": 0.0,
                        "payload": {
                            "n_unique_dates": lane_n_unique_dates,
                            "wf_min_unique_dates": wf_min_dates,
                            "n_fold": 0,
                            "n_fold_unavailable": 0,
                            "n_fold_effective": 0,
                            "oos_sharpes": (),
                            "median_oos_sharpe": None,
                            "positive_fold_ratio": None,
                            "positive_fold_ratio_effective": None,
                            "dsr": None,
                            # Round 1 #2 Warning: 未評価を明示するため None に変更
                            "is_full_sharpe": None,
                            "is_full_total_pnl": None,
                            "is_full_trade_count": None,
                        },
                    },
                    reason_codes=("stage_b_window_underfilled",),
                )
            else:
                b_result = evaluate_stage_b(
                    genome,
                    lane.bars_18m,
                    lane.meta,
                    bt_cfg,
                    self._primitive_evaluator,
                    self._stage_gate_config,
                )
            self._archive.collect_stage_b(
                genome,
                lane.lane_id,
                lane.generation_count,
                b_result,
            )
```

新規 import:
```python
from src.alpha_factory.walk_forward import wf_min_unique_dates, n_unique_dates
from src.alpha_factory.stage_gate import StageResult  # 既存 import
```

### skip-path payload 規約 (Round 3 review #6 Warning 対応)
underfilled skip 時の payload は以下のキーを **必ず** 含める:
- `n_unique_dates: int` (観測日数の実測値)
- `wf_min_unique_dates: int` (要件閾値)
- `n_fold=0`, `n_fold_unavailable=0`, `n_fold_effective=0`
- `oos_sharpes=()`
- 他の数値メトリクスは `None` または `0.0` (上記コード通り)

### テスト計画
- 新規 in `tests/alpha_factory/test_swim_lane.py`:
  - `test_stage_b_skipped_when_unique_dates_below_minimum` — Stage A pass 個体に対し observed days < min で `evaluate_stage_b` が呼ばれず archive に `stage_b_window_underfilled` が記録される
  - `test_stage_b_evaluated_when_unique_dates_meet_minimum` — 既存挙動が壊れていない
- **既存テスト更新** (Round 1 review #2 Warning):
  - 既存 `test_swim_lane.py:511` 周辺の Stage B 呼び出し回数を期待する fixture を「十分な unique days を持つ bars」に変更
  - もしくは既存 fixture を維持しつつ、新規テストで両分岐を確認する形

### リスク
- LaneManager の他経路で同様の `evaluate_stage_b` 呼び出しがある場合 (graduation 等) は同等処理を当てる必要 → 実装時に grep `evaluate_stage_b` で確認

---

## 施策 3: Stage B 観察可能性メトリクス追加

### 変更箇所
- ファイル: `src/alpha_factory/stage_gate.py:443-465` (`evaluate_stage_b` の集計部 + metrics_envelope)

### 波及変更
- `docs/alpha_factory/stage-gates.md`: Stage B metrics.payload キーに追記
- `docs/alpha_factory/terminology.md`: `n_fold_effective`, `positive_fold_ratio_effective` 用語追加

### 変更後コード抜粋
```python
    # 集計と判定
    n_fold_effective = n_fold - n_fold_unavailable
    median_oos: float | None = None
    positive_ratio: float | None = None
    positive_ratio_effective: float | None = None
    if n_fold == 0:
        reasons.append("no_folds")
    elif n_fold == 1:
        reasons.append("insufficient_folds")
        median_oos = float(oos_sharpes_imputed[0])
        positive_ratio = 1.0 if oos_sharpes_imputed[0] > 0 else 0.0
        if n_fold_effective >= 1:
            # 有効 fold のみで再計算 (effective)
            # _fold_was_unavailable は fold 評価ループで index ベースの list[bool] として保持
            # (Round 2 review #1 Warning 対応: 確定式に統一)
            effective_oos = [
                s for i, s in enumerate(oos_sharpes_imputed)
                if not _fold_was_unavailable[i]
            ]
            positive_ratio_effective = (
                sum(1 for s in effective_oos if s > 0) / len(effective_oos)
                if effective_oos else None
            )
    else:
        median_oos = float(_stats.median(oos_sharpes_imputed))
        positive_ratio = sum(1 for s in oos_sharpes_imputed if s > 0) / n_fold
        if n_fold_effective > 0:
            # 有効 fold だけで positive ratio を再計算
            # _fold_was_unavailable は fold 評価ループで `unavailable_folds.append(i)` 形式で記録し、
            # 以下のように確定した式で算出する (Round 2 review #1 Warning 対応)
            effective_oos = [
                s for i, s in enumerate(oos_sharpes_imputed)
                if not _fold_was_unavailable[i]
            ]
            positive_ratio_effective = (
                sum(1 for s in effective_oos if s > 0) / len(effective_oos)
                if effective_oos else None
            )
        if median_oos < stage_config.stage_b_median_oos_sharpe_min:
            reasons.append("median_oos_sharpe<min")
        if positive_ratio < stage_config.stage_b_positive_fold_min:
            reasons.append("positive_fold_ratio<min")

    # ...

    metrics_envelope: dict[str, object] = {
        # ...
        "payload": {
            "n_fold": n_fold,
            "n_fold_unavailable": n_fold_unavailable,
            "n_fold_effective": n_fold_effective,  # NEW
            "oos_sharpes": tuple(oos_sharpes_imputed),
            "median_oos_sharpe": median_oos,
            "positive_fold_ratio": positive_ratio,
            "positive_fold_ratio_effective": positive_ratio_effective,  # NEW
            "dsr": None,
            # ... (既存)
        },
    }
```

**実装確定**: fold 評価ループで `_fold_was_unavailable: list[bool]` (index i = fold i の unavailable フラグ) を保持し、`effective_oos = [s for i, s in enumerate(oos_sharpes_imputed) if not _fold_was_unavailable[i]]` で確定的に算出する (Round 2 review #1 Warning 対応)。

### `passed` 判定への影響
**なし** — monitor only。新メトリクスは payload にのみ追加し、`reasons.append()` しない。

### テスト計画
- 新規 in `tests/alpha_factory/test_stage_gate.py`:
  - `test_stage_b_metrics_payload_contains_n_fold_effective`
  - `test_stage_b_n_fold_effective_equals_total_minus_unavailable`
  - `test_stage_b_positive_fold_ratio_effective_uses_only_available_folds`
  - `test_stage_b_passed_unchanged_with_new_metrics` (regression)

### リスク
- 既存テスト (もしあれば) が payload キー全集合を hard-coded で比較している場合に壊れる → 実装時に grep で確認

---

## 施策 4: archive schema 拡張

### 変更箇所
- ファイル: `src/alpha_factory/archive.py:74-85` (`GENOMES_SCHEMA`), `src/alpha_factory/archive.py:101-138` (`_create_row_template`), `src/alpha_factory/archive.py:374-403` (`collect_stage_b`)

### 波及変更
- `docs/alpha_factory/concepts/genome-archive-schema.md`: 新列 3 件を SSOT に追記 (Round 3 review #9 対応)

### schema 追加列
```python
# GENOMES_SCHEMA 末尾に追加
        pa.field("n_fold_effective", pa.int64(), nullable=True),
        pa.field("positive_fold_ratio_effective", pa.float64(), nullable=True),
        pa.field("stage_b_reason_codes", pa.string(), nullable=True),
```

### `_create_row_template` 追加
```python
        "n_fold_effective": None,
        "positive_fold_ratio_effective": None,
        "stage_b_reason_codes": None,
```

### `collect_stage_b` 改修
```python
    def collect_stage_b(self, genome, lane_id, generation, stage_result):
        # ... 既存処理 ...
        payload = _extract_payload(stage_result)
        row["stage_b_pass"] = bool(stage_result.passed)
        oos = _extract_oos_sharpes(payload)
        if oos is None or len(oos) == 0:
            row["fold_sign_ratio"] = None
        else:
            row["fold_sign_ratio"] = float(fold_sign_ratio(oos))
        row["dsr"] = _opt_float(payload, "dsr")
        # NEW
        row["n_fold_effective"] = _opt_int(payload, "n_fold_effective")
        row["positive_fold_ratio_effective"] = _opt_float(
            payload, "positive_fold_ratio_effective"
        )
        # reason_codes 永続化 (空タプルなら None)
        rc = stage_result.reason_codes
        row["stage_b_reason_codes"] = ";".join(rc) if rc else None
        # 既存続き
        is_sharpe = _opt_float(payload, "is_full_sharpe")
        # ...
```

### Parquet 後方互換性
- 追加列はすべて `nullable=True` で旧 row は自然に `None` に default
- 既存の `_create_row_template` 呼び出し経路を変更しないため、Stage A only / Stage A fail 行も問題なし

### テスト計画
- 新規 in `tests/alpha_factory/test_archive.py`:
  - `test_genomes_schema_contains_n_fold_effective_column`
  - `test_genomes_schema_contains_stage_b_reason_codes_column`
  - `test_collect_stage_b_writes_reason_codes_string`
  - `test_collect_stage_b_writes_none_reason_codes_when_passed`
- **既存テスト更新** (Round 1 review #4 Warning):
  - `tests/alpha_factory/test_archive.py:163` 周辺の 28 列固定検査を 31 列 (新 3 列追加) に更新
  - expected schema set / nullable set を更新
- **後方互換テスト** (Round 1 review #4 Warning):
  - `test_archive_load_old_schema_parquet_returns_none_for_new_columns` — 旧 schema (28 列) parquet ファイル fixture を `tests/data/` に置き、`GenomeArchive.load()` が新列で `None` を返すか確認

### リスク
- 既存 archive parquet を読む coupling 箇所 (sieve など) が schema strict reader だと旧 schema を拒否する可能性 → 実装時に Parquet reader 側の `coerce_schema=True` 等を確認 (typically pyarrow は前方互換)
- INCONCLUSIVE 解消は上記の互換テストで確保

---

## 施策 5: run-report 強化

### 変更箇所
- ファイル: `scripts/alpha_factory/generate_run_report.py:406-415` (Stage B 分布セクション周辺)

### 波及変更
- `AGENTS.md`: なし (出力フォーマット拡張のみ)

### 追加内容
1. **世代別 Stage B reason histogram**:
```markdown
## Stage B failure reason 集計 (世代別)

| gen | n_evaluated | n_pass | no_folds | insufficient_folds | all_folds_unavailable | stage_b_window_underfilled | other |
|-----|-------------|--------|----------|--------------------|-----------------------|----------------------------|-------|
| 0   | 20          | 0      | 20       | 0                  | 0                     | 0                          | 0     |
```

- **`n_evaluated` 定義** (Round 3 review #3 Warning 対応): `n_evaluated = stage_a_pass 個体数` (= Stage B 評価対象行数)
- **`other` 定義** (Round 3 review #5 Suggestion 対応): 既知列 (`no_folds` / `insufficient_folds` / `all_folds_unavailable` / `stage_b_window_underfilled`) に分類されない reason の合計。
- **multi-label 規約 (Round 1 review #5 Warning 対応)**:
  - **2 系列で出力** する:
    1. `primary_reason` 表 (先頭 reason のみで集計、5 category 合計が `n_evaluated - n_pass` と必ず一致)
    2. `any_reason incidence` 表 (`;` split した全 reason をカウント、合計は failures 件数より大きくなり得る)
  - 過少計上 / 過大集計の双方を可視化
- **欠損値 (旧 archive) 規約 (Round 1 review #5 Warning 対応)**:
  - `stage_b_reason_codes is null` かつ `stage_b_pass=False` の行は `unknown_reason` カテゴリで集計し、`primary_reason` 表に独立カラムを追加
  - 5 category + `unknown_reason` + `other` の合計が `n_evaluated - n_pass` と必ず一致

2. **`n_fold_effective` 分布** (existing fold_sign_ratio 行の隣に追加):
```python
fe = _basic_stats([r.get("n_fold_effective") for r in archive_rows if r.get("stage_a_pass")])
prfe = _basic_stats([r.get("positive_fold_ratio_effective") for r in archive_rows if r.get("stage_a_pass")])
lines.append(f"- n_fold_effective: {_fmt_stats(fe)}")
lines.append(f"- positive_fold_ratio_effective: {_fmt_stats(prfe)}")
```

### テスト計画
- 新規 in `tests/scripts/test_generate_run_report.py` (or 同等):
  - `test_run_report_contains_stage_b_reason_histogram`
  - `test_run_report_reason_histogram_other_excludes_known_codes`
  - `test_run_report_primary_reason_categories_sum_equals_failures`
  - `test_run_report_any_reason_incidence_can_exceed_failures`
  - `test_run_report_unknown_reason_for_legacy_archive_rows`

### 波及変更追加 (Round 1 #5 Suggestion 対応)
- `.claude/skills/zenigame-fx-run-report/SKILL.md`: 新セクション (Stage B reason histogram) の存在を skill 仕様に追記

### リスク
- 既存 fixture が新列を持たない → fixture 更新

---

## 施策 6: テスト追加 (集約)

各施策の個別テストはそれぞれの節に記載済み。**Round 1 review #6 Warning 対応** として、追加テストと既存テスト更新を以下の表に集約:

| 種別 | パス | テスト名 | 関連施策 |
|------|------|---------|---------|
| 新規 | `tests/alpha_factory/test_walk_forward.py` | `test_wf_min_unique_dates_returns_train_plus_embargo_plus_test` | 1 |
| 新規 | `tests/alpha_factory/test_walk_forward.py` | `test_n_unique_dates_counts_distinct_utc_dates` | 1 |
| 新規 | `tests/alpha_factory/test_swim_lane.py` | `test_stage_b_skipped_when_unique_dates_below_minimum` | 2 |
| 新規 | `tests/alpha_factory/test_swim_lane.py` | `test_stage_b_evaluated_when_unique_dates_meet_minimum` | 2 |
| 新規 | `tests/alpha_factory/test_stage_gate.py` | `test_stage_b_metrics_payload_contains_n_fold_effective` | 3 |
| 新規 | `tests/alpha_factory/test_stage_gate.py` | `test_stage_b_n_fold_effective_equals_total_minus_unavailable` | 3 |
| 新規 | `tests/alpha_factory/test_stage_gate.py` | `test_stage_b_positive_fold_ratio_effective_uses_only_available_folds` | 3 |
| 新規 | `tests/alpha_factory/test_stage_gate.py` | `test_stage_b_passed_unchanged_with_new_metrics` | 3 |
| 新規 | `tests/alpha_factory/test_archive.py` | `test_genomes_schema_contains_n_fold_effective_column` | 4 |
| 新規 | `tests/alpha_factory/test_archive.py` | `test_genomes_schema_contains_stage_b_reason_codes_column` | 4 |
| 新規 | `tests/alpha_factory/test_archive.py` | `test_collect_stage_b_writes_reason_codes_string` | 4 |
| 新規 | `tests/alpha_factory/test_archive.py` | `test_collect_stage_b_writes_none_reason_codes_when_passed` | 4 |
| 新規 | `tests/alpha_factory/test_archive.py` | `test_archive_load_old_schema_parquet_returns_none_for_new_columns` | 4 |
| 新規 | `tests/scripts/test_generate_run_report.py` | `test_run_report_contains_stage_b_reason_histogram` | 5 |
| 新規 | `tests/scripts/test_generate_run_report.py` | `test_run_report_reason_histogram_other_excludes_known_codes` | 5 |
| 新規 | `tests/scripts/test_generate_run_report.py` | `test_run_report_primary_reason_categories_sum_equals_failures` | 5 |
| 新規 | `tests/scripts/test_generate_run_report.py` | `test_run_report_any_reason_incidence_can_exceed_failures` | 5 |
| 新規 | `tests/scripts/test_generate_run_report.py` | `test_run_report_unknown_reason_for_legacy_archive_rows` | 5 |
| **更新** | `tests/alpha_factory/test_archive.py:163` 周辺 | 28 列固定検査を 31 列に更新 (expected schema set / nullable set) | 4 |
| **更新** | `tests/alpha_factory/test_swim_lane.py:511` 周辺 | Stage B 呼び出し回数を期待する fixture を「十分な unique days を持つ bars」に変更 (もしくは両分岐を新規テストで覆う) | 2 |

`uv run pytest tests/alpha_factory/ -k stage_b` で関連テストを横断確認できること。

---

## 施策 7: docs 更新

### 変更箇所
- `docs/alpha_factory/stage-gates.md`: Reason Code 語彙に追加
  ```
  | `stage_b_window_underfilled` | LaneManager が Stage B 評価前に観測日数 < (train+embargo+test) を検出 (skip-path) |
  ```
- `docs/alpha_factory/concepts/genome-archive-schema.md`: 新列 3 件 (`n_fold_effective`, `positive_fold_ratio_effective`, `stage_b_reason_codes`) を SSOT に追記
- `docs/alpha_factory/swim-lane.md`: Stage B skip-path (`evaluate_stage_b` を呼ばず underfilled 記録) を 2-3 行で追記
- `docs/alpha_factory/terminology.md`: `n_fold_effective`, `positive_fold_ratio_effective`, `wf_min_unique_dates`, `stage_b_window_underfilled` を用語集に **必須** 追加 (Round 1 #7 Suggestion 対応 — 任意 → 必須に格上げ)
- `docs/alpha_factory/stage-gates.md`: Stage B metrics.payload に `n_fold_effective`, `positive_fold_ratio_effective`, `n_unique_dates`, `wf_min_unique_dates` を追記し、「effective 指標は条件付き母集団であり、因果解釈・閾値化は実測 n>=30 の収集後」と明記 (Round 1 #3 Suggestion 対応)
- `.claude/skills/zenigame-fx-run-report/SKILL.md`: 新セクション (Stage B reason histogram) の存在を skill 仕様に追記

---

## 受け入れ条件

- [ ] `uv run pytest tests/alpha_factory/` 全 PASS
- [ ] `uv run pytest tests/scripts/` 全 PASS (Round 1 #6 Suggestion 対応)
- [ ] `uv run ruff check src/ tests/ scripts/` 通過
- [ ] `uv run mypy src/` 通過
- [ ] underfilled 行が run-report の reason histogram で欠落しない
- [ ] 既存 archive parquet (旧 schema 行) が新 reader で読める (互換テストで保証)
- [ ] 既存 Stage B `passed` 判定が新メトリクス追加で変わらない (regression テスト)
- [ ] `wf_min_unique_dates(train, embargo, test)` が `make_wf_folds` の `fold_len` と完全一致 (= `make_wf_folds` 内部で同 helper を使用)
- [ ] `n_unique_dates` 計算が lane ループ外で 1 回のみ実行されている
- [ ] archive 4段接続 (`GENOMES_SCHEMA` 定義 → `_create_row_template` 初期値 → `collect_stage_b` 書き込み → `flush`→Parquet 書出→`GenomeArchive.load` 再読み込み) で新 3 列が保全されること (Round 2 review #3 Warning 対応: `test_archive_load_old_schema_parquet_returns_none_for_new_columns` で flush→reload を含む 4 段を一貫検証)

## 実装モード

| 項目 | 内容 |
|------|------|
| 推奨モード | incremental |
| 判断根拠 | 既存 schema・既存 reason code を破壊せず追加のみ。circular import 懸念のため walk_forward.py の helper は段階的に切り出し可能。 |
| 競合リスク | archive schema を触る他施策 (T028/T029/T030 はクローズ済み、現在 Open は 0) が無いため低い |
| 想定実装時間 | 中 (3-5 時間: 5 ファイル + 6 テストファイル + 4 docs) |
