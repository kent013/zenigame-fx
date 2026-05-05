# 詳細設計: Run 35 施策 (cycle 1 / 10)

Round 1 design-review で REQUEST_CHANGES。 Codex 収束案 (1 仮説 + 1 最小変更) を全面採用し、 cycle 1 を **C2 H1/M1 のみ** に絞り込み。 C1/W3 は cycle 2 以降に保留 (improvement-plan.md 保留事項に追記)。

## 使命・制約 (絶対遵守)

zenigame-fx-codex-review 継承。 FX 固有制約再掲:
- イントラデイ前提
- ロング・ショート両方向許容
- スワップ・スプレッドを fitness に反映

cycle 1 = 計測経路 bug の最小修正 + 回帰テスト 1 本。 GA / stage gate threshold は不変。

## 施策一覧

| # | 施策名 | 変更ファイル | target_metric |
|---|--------|------------|--------------|
| **C2 (絞り込み版)** | `collect_stage_a` で `total_pnl` を archive に伝搬 | `src/alpha_factory/archive.py` (collect_stage_a, line 409 〜) + 回帰テスト 1 本 | total_pnl_min=50000 判定の正当性 |

## C1, W3 の取り扱い: cycle 1 では実施しない (持ち越し)

Codex Round 1 design-review より:

### C1 (partition 監査) — 持ち越し
- run-34 summary.json は T087 出力契約 (`bars_stage_b_excludes_stage_a` / `stage_b`) を持たず、 旧 schema 経路の可能性大
- run-34 を直接 T087 監査の根拠に使えない
- cycle 1 RUN 自体を新 schema で取り直してから監査するべき
- holdout `60日 ≒ 86400 bars` 前提も 24/7 仮定で過剰、 24/5 cadence で再算出要

→ **cycle 2 で artifact 互換性確認 + holdout coverage guard 強化**として再エントリ

### W3 (observability) — 持ち越し
- `archive_role/source_stage/fsp_*` は **現行契約上 nullable** (後段更新前提)、 success criterion 違反
- `median_fitness_pen / population_diversity / stage_X_pass_count` は **現行 per_generation schema に存在しない**、 観測対象定義がズレ
- `dsr` は Stage B payload で明示的に None (Phase 4 予定)、 NaN/None を即欠陥扱いにしない

→ **cycle 2 以降で per_generation schema 拡張提案 + 観測対象再定義**として再エントリ

## C2 (絞り込み版): collect_stage_a で total_pnl を archive に伝搬

### 反証可能仮説 (Codex 収束案 H1)

「`total_pnl=0` は Stage A payload→archive 伝搬欠落が原因。 sidecar には記録されているが archive Parquet にない、 故に summary writer が `"0"` にフォールバックしている」

### target_metric / failure_mode / causal_path / falsification / success_criterion

- **target_metric**: `total_pnl_min=50000` 判定の正当性
- **failure_mode**: best 個体 g54_i35 で trade_count=67, sharpe=0.24 (positive) なのに total_pnl=0.0
- **causal_path**:
  - sidecar (`diagnostics_collector.py:117`): `total_pnl_stage_a=total_pnl` で正しく記録 (Codex が g54_i35 sidecar `total_pnl_stage_a=50360.0` を確認済み)
  - archive (`archive.py:409 collect_stage_a`): stage_result の `total_pnl` を archive に保存していない
  - summary writer (`run_ga.py:766 _make_metrics_row`): `row.get("total_pnl", "0")` で row に値がなければ "0" にフォールバック
  - → 結果として archive Parquet 列 `total_pnl` がほぼ全行 0、 summary best metrics も 0
- **falsification**: archive.py の `collect_stage_a` を修正して `total_pnl` を保存し、 既存の sidecar 値と archive 値が一致 (g54_i35 で両者 50360.0) すれば仮説 verify。 不一致なら別経路の伝搬欠落
- **success_criterion**:
  - sidecar `total_pnl_stage_a` と archive `total_pnl` が **Stage A 時点の同一個体行** で一致 (Stage B/C で更新されている個体は対象外、 判定ぶれ防止)
  - 修正後の cycle 2 RUN で best 個体 `total_pnl > 0`
  - 回帰テストで `collect_stage_a` 経路の `total_pnl` 伝搬を assert

### 変更箇所

#### Before (推測 — 実装フェーズで Read で確認)

`src/alpha_factory/archive.py:409` 〜 `collect_stage_a`:
```python
def collect_stage_a(
    self,
    genome: Genome,
    lane_id: str,
    generation: int,
    stage_result: StageResult,
    *,
    instrument: str,
    parent_a: str | None = None,
    parent_b: str | None = None,
) -> None:
    """Stage A 評価結果を archive に取り込む。"""
    if stage_result.stage != "A":
        raise ValueError(f"collect_stage_a expected stage='A', got {stage_result.stage!r}")
    # ... archive row 構築 ...
    # 推測: stage_result.metrics から total_pnl を抜き出して row に渡す処理が欠落 or 別 key 名
```

#### After (実装フェーズで具体的修正)

実装で確定する変更:
1. `stage_result.metrics["total_pnl"]` (or 同等経路) を archive row の `total_pnl` field に設定
2. 既に経路がある場合、 「なぜ Stage A 評価 row には反映されず Stage B/C 行に反映されているか」 を切り分け
3. archive row 構築の per-stage 分岐で Stage A 経路だけ抜けがあるなら、 共通経路に集約

### 波及変更 (AGENTS.md / skill / config / docs)

- 新規 docs 追加なし (bug fix 性質)
- AGENTS.md 修正なし
- 既存 docs: `docs/alpha_factory/architecture.md` (もしあれば) の archive schema 節で `total_pnl` フィールドの伝搬経路を 1 行明示

### 現行コード参照 (実装フェーズで Read 必須)

- `src/alpha_factory/archive.py:409 〜` (collect_stage_a 定義)
- `src/alpha_factory/archive.py:176` (archive_role / source_stage の field schema)
- `src/alpha_factory/diagnostics_collector.py:117 / :183` (sidecar の total_pnl_stage_a 記録、 比較対象)
- `src/alpha_factory/swim_lane.py:597 / :783` (collect_stage_a 呼び出し点)
- `scripts/alpha_factory/run_ga.py:766` (summary writer `_make_metrics_row`、 row.get fallback)
- `src/backtest/metrics.py:156` (compute_metrics、 total_pnl 計算源)

### ルックアヘッドバイアスチェック

bug 修正は計測経路の伝搬のみで evaluation logic 不変:
- [x] 未来バー参照なし
- [x] 当日確定値の先取りなし
- [x] rolling window 不変
- [x] 正規化不変
- [x] cumsum 不変

### パフォーマンスチェック

archive row 構築に float 1 個追加するだけ:
- [x] compute_all_bars() は変更しない
- [x] 内側ループ不変
- [x] SoA プロパティ不変
- [x] cache 影響なし

### テスト計画

#### 既存テスト走破

- `tests/alpha_factory/test_archive.py` 全 case
- 関連 fixture (collect_stage_a のテスト)

#### 追加テスト 1 本 (回帰テスト)

`tests/alpha_factory/test_archive.py` に追加:

```python
def test_collect_stage_a_propagates_total_pnl():
    """C2 (cycle 1): collect_stage_a が stage_result の total_pnl を archive に伝搬することを保証する回帰テスト。

    background: cycle 1 で run-34 best 個体 g54_i35 が
        sidecar total_pnl_stage_a=50360.0 / archive total_pnl=0.0 と乖離していた。
        Stage A 行で archive total_pnl が 0 にフォールバックしていたため。
    """
    archive = Archive(...)  # fixture
    stage_result = StageResult(stage="A", metrics={"total_pnl": 50360.0, ...})
    archive.collect_stage_a(
        genome=fake_genome,
        lane_id="tier1_EUR_JPY",
        generation=54,
        stage_result=stage_result,
        instrument="EUR_JPY",
    )
    rows = archive.flush()
    assert rows[-1]["total_pnl"] == 50360.0
```

具体的な fixture / API 名は実装フェーズで `tests/alpha_factory/test_archive.py` を Read して合わせる。

### リスク

- **Stage A だけ修正したら Stage B/C 集計の `total_pnl` 経路と矛盾**する可能性 — 実装時に collect_stage_b / collect_stage_c も同経路を確認し、 共通化が必要なら抽象化を検討 (ただし「複雑案禁止」を意識して最小変更に留める)
- **過去 RUN との比較性**: 過去 archive Parquet (run-1 〜 run-34) の `total_pnl` 列が 0 のままなので、 cycle 2 以降の RUN との比較で前後関係に注意 (cycle 1 修正前は計測欠陥、 cycle 2 以降は正常)
- **再現テスト fixture**: collect_stage_a を呼ぶための fixture 整備に時間を要する可能性

## Run 35 実行パラメータ

| パラメータ | 値 | R34 からの変更 |
|-----------|-----|--------------|
| population_size | 96 | 不変 |
| generations | 60 | 不変 |
| mutation_rate | 0.5 | 不変 |
| seed | 23 | 不変 (deterministic 再現で計測 bug 修正後の値が同設定で算出されるか確認) |
| max_clause | 1 | 不変 |
| instrument | EUR_JPY | 不変 |
| stage_a.threshold | -0.0172 | 不変 |
| stage_a.calibrate.enabled | false | 不変 |

cycle 1 RUN の意図: collect_stage_a 修正後、 同設定 RUN で best 個体 `total_pnl > 0` を確認。 改善されれば仮説 H1 verify、 改善されなければ別経路の伝搬欠落 (cycle 2 で深掘り)。

## 全体使命チェック

| 禁止事項 | 抵触有無 | 根拠 |
|---------|---------|------|
| 1. 評価期間延長 | なし | 期間変更なし |
| 2. 見た目数値改善 | なし | 計測経路 bug 修正のみ |
| 3. GA ハック | なし | GA 設定不変 |
| 4. 閾値緩和でステージ飛ばし | なし | threshold 不変 |
| 5. 複雑案 | なし | 1 file (archive.py) + 回帰テスト 1 本 |
| 6. 取引回数削減で見かけ改善 | なし | trade 不変 |
| 7. オーバーナイト保有前提 | なし | 戦略不変 |

cycle 1 detailed-design (絞り込み版) は mission alignment OK。 「1 反証可能仮説 + 最小変更」 原則完全遵守。
