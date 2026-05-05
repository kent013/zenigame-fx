# 詳細設計: Run 35 施策 (cycle 2 / 10) — Round 1 design-review 反映 refactor

Codex Round 1 で REQUEST_CHANGES。 主要指摘 (Critical):
- 既存 preflight (`compute_max_folds` observed-day SSOT) があり、 私の `bars_per_day` 式は SSOT 不整合
- per_generation 欠落 key は **schema 未定義** (writer 欠陥でない)
- Principled Parametric を主張するには SSOT 一致が必須

Codex 収束案を全面採用: **「1 仮説 = 有効 fold 不足が主因、 1 最小変更 = 既存 `compute_max_folds` 判定を起動時 fail-closed 化 + WF 値で fold>=5 を確保 (一体)」**。

## 使命・制約 (絶対遵守)

zenigame-fx-codex-review 継承。 FX 固有制約: イントラデイ前提 / ロング・ショート両方向許容 / スワップ・スプレッドを fitness に反映。

## 施策一覧 (cycle 2、 P4 / P2 は cycle 3 持ち越し)

| # | 施策 | 変更ファイル | target_metric |
|---|------|------------|--------------|
| **P1-1 (改良)** | `compute_max_folds` 起動時 fail-closed 化 | `scripts/alpha_factory/run_ga.py` (line 1493 周辺、 既存 preflight 計算後に判定追加) | Stage B fold 生成可能性 |
| **P1-2 (改良)** | WF 値変更で `compute_max_folds(...) >= 5` 達成 | `config/alpha_factory/default.yaml` | Stage B fold 生成可能性 |

## P4 / P2 持ち越し (cycle 3 以降)

| # | 元提案 | 持ち越し理由 | 引き継ぎ |
|---|------|----------|---------|
| P4 | per_generation observability | Codex Round 1 で schema 未定義と判明、 writer 補修でなく schema 拡張議論が必要 | cycle 3 で「追加観測項目の定義・算出式・保存先」を確定 |
| P2 | trade_count 層別監査 | INCONCLUSIVE 許容、 cycle 2 で 実行 必須でない | cycle 3 以降、 P3 (selection_score 監査) と統合 |

## P1-1 (改良): `compute_max_folds` 起動時 fail-closed 化

### 反証可能仮説 (cycle 2 単一仮説)

「Stage B 偽陽性 (pass 群 total_pnl mean=-14,303、 trade_count 急減) の主因は **有効 fold 不足** (現 RUN で `compute_max_folds=2`、 wf_min_folds_required=2 で境界 pass しているのみ、 statistical safety を欠く)」

### target_metric / failure_mode / causal_path / falsification / success_criterion

- **target_metric**: Stage B fold 生成可能性 (品質保証の前提)
- **failure_mode**: 現 RUN で `compute_max_folds(n_unique_dates_b, wf_train=60, wf_embargo=1, wf_test=10, wf_step=10) = 2`、 これが `wf_min_folds_required=2` に境界 pass。 結果として Stage B pass 群が 2 fold (=最小) で偽陽性
- **causal_path**: 現実装は preflight 計算 (run_ga.py:1493) 済だが、 `preflight_underfilled = lane_max_folds < wf_min_folds` の判定で graceful degrade (短絡 skip) のみ。 「最小 fold 境界での偽陽性」 を防げない
- **falsification**:
  - guard 実装後、 現 partition (B=97003 bars, n_unique_dates_b≈X) + 旧 WF 設定で `compute_max_folds < 5` → 起動時 fail-closed → 仮説 verify
  - WF 値変更後 (P1-2)、 同 partition で `compute_max_folds >= 5` → guard pass → cycle 2 RUN 続行
  - cycle 2 RUN 完了後の Stage B pass 群 total_pnl mean が non-negative → 偽陽性減少 verify
- **success_criterion**:
  - guard 実装、 起動 log に「`stage_b_fold_guard.{passed|failed} compute_max_folds=X min_safe_folds=Y wf_train=A wf_test=B wf_step=C wf_embargo=D wf_min_folds_required=N n_unique_dates_b=M`」 明示
  - 現 partition + 新 WF 値で fail-closed しない (compute_max_folds >= min_safe_folds=5)
  - cycle 2 RUN で n_fold_effective median ≥ 5、 Stage B pass 群 total_pnl mean ≥ 0 (or 中央値 ≥ 0)

### 変更箇所 (実装フェーズで Read 必須)

`scripts/alpha_factory/run_ga.py` line 1493 周辺の preflight 計算後、 以下のロジックを追加:

```python
# 既存 (line 1493 周辺):
lane_max_folds = compute_max_folds(
    lane_n_unique_dates,
    cfg.stage_gate.wf_train_days,
    cfg.stage_gate.wf_embargo_days,
    cfg.stage_gate.wf_test_days,
    cfg.stage_gate.wf_step_days,
)
wf_min_folds = cfg.stage_gate.wf_min_folds_required
preflight_underfilled = lane_max_folds < wf_min_folds

# cycle 2 (improve-cycle): 追加 — fold 不足の境界 pass による偽陽性を防ぐ guard
# 既存 wf_min_folds_required は worker 短絡判定用 (graceful degrade)、
# min_safe_folds は起動時 fail-closed 用 (statistical safety floor)
min_safe_folds = cfg.stage_gate.wf_min_safe_folds  # 新規 yaml key、 default=5
log.info(
    "stage_b_fold_guard.evaluating",
    compute_max_folds=lane_max_folds,
    min_safe_folds=min_safe_folds,
    wf_train_days=cfg.stage_gate.wf_train_days,
    wf_test_days=cfg.stage_gate.wf_test_days,
    wf_step_days=cfg.stage_gate.wf_step_days,
    wf_embargo_days=cfg.stage_gate.wf_embargo_days,
    wf_min_folds_required=wf_min_folds,
    n_unique_dates_b=lane_n_unique_dates,
    lane_id=lane_id,
)
if lane_max_folds < min_safe_folds:
    raise RuntimeError(
        f"Stage B fold guard failed: compute_max_folds={lane_max_folds} "
        f"< min_safe_folds={min_safe_folds} (n_unique_dates_b={lane_n_unique_dates}, "
        f"wf_train={cfg.stage_gate.wf_train_days}d, wf_test={cfg.stage_gate.wf_test_days}d, "
        f"wf_step={cfg.stage_gate.wf_step_days}d, wf_embargo={cfg.stage_gate.wf_embargo_days}d). "
        f"Stage B 偽陽性回避のため fail-closed。 WF 値変更 or partition 拡張で対応。"
    )
log.info("stage_b_fold_guard.passed", lane_id=lane_id)
```

`min_safe_folds` は新規 yaml key:

```yaml
# config/alpha_factory/default.yaml (P1-2 と同時更新)
stage_gate:
  stage_b:
    wf_min_safe_folds: 5  # cycle 2 (improve-cycle): 偽陽性回避用 statistical safety floor
```

### 波及変更

- `docs/alpha_factory/stage-gates.md` § "Stage B fold guard (T087+)" 節追加
- `docs/alpha_factory/runbook.md` § fail-closed 表に本 guard 追加
- `src/alpha_factory/config.py` (もしあれば) で `wf_min_safe_folds` を StageGateConfig に追加
- `swim_lane.py` の同 preflight 計算は legacy 経路、 修正対象外 (run_ga.py 経路で十分。 ただし将来的に SSOT 化要)

### テスト計画

- [ ] 既存 preflight テスト走破 (`tests/alpha_factory/test_walk_forward.py` の `compute_max_folds` テスト)
- [ ] 新規テスト 2 本:
  - `test_stage_b_fold_guard_passes_with_sufficient_folds`: compute_max_folds=5 + min_safe_folds=5 で no-op
  - `test_stage_b_fold_guard_fails_with_insufficient_folds`: compute_max_folds=4 + min_safe_folds=5 で RuntimeError
- [ ] integration: cycle 2 RUN で起動 log に `stage_b_fold_guard.passed` が出ること

### ルックアヘッドバイアスチェック

guard は計算前メタ検証、 評価ロジック不変:
- [x] 未来バー参照なし
- [x] 当日確定値の先取りなし
- [x] WF window 不変 (P1-1 単独では)

### リスク

- **Round 1 design-review 指摘の二重基準**: `wf_min_folds_required` (worker 短絡判定) と `wf_min_safe_folds` (起動時 fail-closed) が共存する。 これは設計上の意図的分離 (短絡判定は graceful degrade、 fail-closed は statistical safety) と明示する必要あり、 docs に区別を記載
- 起動時 RuntimeError は cycle 2 RUN を **完全停止** させる、 P1-2 (WF 値変更) と一体運用必須

---

## P1-2 (改良): WF 値変更で `compute_max_folds(...) >= 5` 達成

### 反証可能仮説

「現 yaml WF 値 (`wf_train=60d/wf_test=10d/wf_step=10d/wf_embargo=1d`) は新 partition (n_unique_dates_b≈Y 日 [実値は実装フェーズで実測]) で `compute_max_folds=2` 構造的必然。 値を変更して `compute_max_folds >= 5` を確保しないと P1-1 guard で fail-closed」

### target_metric / failure_mode / causal_path / falsification / success_criterion

- target_metric: Stage B fold 生成可能性 + Stage B pass 群品質
- failure_mode: 現 yaml で n_fold_effective max=2、 偽陽性量産
- causal_path: `compute_max_folds = (n_unique_dates - (wf_train + wf_embargo + wf_test)) // wf_step + 1`、 現実装で = (約 67 - 71) // 10 + 1 = 0 (or 負) → 0 or 1。 archive 観測値 max=2 とのズレは observed-day と暦日の cadence 差で説明可能 (実装フェーズで n_unique_dates 実測要)
- falsification:
  - 新 yaml 値 (例: wf_train=20d, wf_test=5d, wf_step=5d, wf_embargo=1d) で compute_max_folds(67, 20, 1, 5, 5) = (67 - 26) // 5 + 1 = 9 → 5 以上達成 verify
  - cycle 2 RUN で n_fold_effective median が新 compute_max_folds 値に整合するか観察
- success_criterion:
  - `compute_max_folds(actual_n_unique_dates, new_wf_*) >= 5`
  - cycle 2 RUN で n_fold_effective median ≥ 5
  - Stage B pass 群 total_pnl mean ≥ 0 (or 中央値 ≥ 0)

### 変更箇所

実装フェーズで:
1. `n_unique_dates(bundle.bars_stage_b)` を **実測** (24/5 cadence で 67 日 vs 24/7 で別値、 実 dataset から計算)
2. 実測値を踏まえて `compute_max_folds(n_unique_dates_actual, train, embargo, test, step) >= 5` を満たす最小値を **algebraic に算出** (Codex 提示の出発点 train=20/test=5/step=5 はあくまで 67d 想定)
3. `config/alpha_factory/default.yaml` で更新:

```yaml
stage_gate:
  stage_b:
    wf_train_days: <実測値で算出>  # 旧 60
    wf_test_days: <実測値で算出>   # 旧 10
    wf_step_days: <実測値で算出>   # 旧 10
    wf_embargo_days: 1             # 不変
    wf_min_folds_required: 2        # 不変 (worker 短絡判定用)
    wf_min_safe_folds: 5            # 新規 (P1-1 起動時 fail-closed 用)
```

### 波及変更

- `docs/alpha_factory/stage-gates.md` § "WF 窓の幾何制約 (cycle 2 で SSOT 一致 algebraic 算出)" 節追加
- AGENTS.md の T-shape WF 節 (もしあれば) 更新

### テスト計画

- [ ] config 読み込みテスト走破
- [ ] integration: cycle 2 RUN で `stage_b_fold_guard.passed` が log に出る + n_fold_effective median ≥ 5
- [ ] (RUN 後分析) Stage B pass 群 total_pnl mean / median を archive で確認

### ルックアヘッドバイアスチェック

WF window 短縮は look-ahead を変えない:
- [x] 未来バー参照なし
- [x] 当日確定値の先取りなし
- [x] rolling window 方向が過去方向 (不変)

### Principled Parametric の根拠 (禁止事項 4「閾値緩和」 回避)

Codex Round 1 で「Principled Parametric は SSOT 一致 + 事前定義反証条件が必須」 と指摘。 本施策で:
- **SSOT 一致**: 既存 `compute_max_folds` (observed-day) を **そのまま使う**、 自前 bars_per_day 式不採用
- **事前定義反証条件**: 「`compute_max_folds(actual_n_unique_dates, new_wf_*) >= 5`」 が確認されることを実装フェーズで verify
- **閾値 (Sharpe / positive_fold) を緩めていない**: median_oos_sharpe_min=0.05 / positive_fold_min=0.6 / dsr_min=0.0 / fold_trade_count_min=10 は **不変**
- 窓短縮は通過難易度に影響するが、 「fold 生成 enabled / disabled」 の二値 (geometry) を変えるだけで、 「合格基準」 は不変

→ 「閾値緩和でステージ飛ばし (禁止事項 4)」 ではなく、 **WF 計算の幾何前提を実 partition に整合させる構造修正**。

### リスク

- **train_days 短縮で 1 fold あたりサンプル数減少**: variance 増加で OOS Sharpe 不安定化の可能性。 これは positive_fold_ratio min=0.6 で部分的 absorb。 cycle 3 以降で variance 観察
- **過去 RUN との比較性破棄**: WF 値変更後は前 RUN との Stage B pass 数比較が無意味。 cycle 2 history note に明示
- **実測値依存**: 実装フェーズで n_unique_dates(bars_stage_b) を取得し algebraic 算出が必要

---

## Run 35 実行パラメータ

| パラメータ | 値 | R34 (新) からの変更 |
|-----------|-----|--------------|
| population_size | 96 | 不変 |
| generations | 60 | 不変 |
| mutation_rate | 0.5 | 不変 |
| seed | 23 | 不変 |
| instrument | EUR_JPY | 不変 |
| stage_a.threshold | -0.0172 | 不変 |
| stage_a.calibrate.enabled | false | 不変 |
| **stage_b.wf_train_days** | (実測算出) | 60 → ? (P1-2) |
| **stage_b.wf_test_days** | (実測算出) | 10 → ? (P1-2) |
| **stage_b.wf_step_days** | (実測算出) | 10 → ? (P1-2) |
| stage_b.wf_embargo_days | 1 | 不変 |
| stage_b.wf_min_folds_required | 2 | 不変 |
| **stage_b.wf_min_safe_folds** | 5 | **新規 key (P1-1)** |
| 他 stage_b パラメータ | 不変 | (sharpe_min / positive_fold_min / dsr_min / fold_trade_count_min) |

cycle 2 RUN で観察 (success criteria):
- 起動 log に `stage_b_fold_guard.passed` 出現
- n_fold_effective median ≥ 5
- Stage B pass 群 total_pnl mean / median ≥ 0

## 全体使命チェック

| 禁止事項 | 抵触有無 | 根拠 |
|---|---|---|
| 1. 評価期間延長 | なし | partition 不変 |
| 2. 見た目数値改善 | なし | 構造修正、 SSOT 一致 |
| 3. GA ハック | なし | GA 設定不変 |
| 4. 閾値緩和でステージ飛ばし | **回避明示** | sharpe_min / positive_fold_min / dsr_min / fold_trade_count_min は **不変**、 変えるのは WF 計算の幾何前提のみ |
| 5. 複雑案 | なし | guard 1 関数 + yaml 4 key 修正 + 1 新規 key (合計 < 50 行変更) |
| 6. 取引回数削減で見かけ改善 | **対策側** | Stage B 偽陽性 (取引回数削減で fold が偶然 pass する個体) を構造的に削減 |
| 7. オーバーナイト保有前提 | なし | 戦略不変 |

cycle 2 detailed-design (refactor 後) は mission alignment OK、 Codex Round 1 指摘 (SSOT 不一致 / schema 未定義 / 二重基準) を全面解消。

## 重要な順序 (実装フェーズ guidance)

P1-1 と P1-2 は **一体運用** で実装:
1. 新 yaml key `wf_min_safe_folds: 5` を default.yaml に追加 (P1-1 用)
2. config.py の StageGateConfig に key 追加
3. run_ga.py に guard logic 追加
4. **テスト走破**
5. n_unique_dates(bars_stage_b) を local 確認 (実測)
6. compute_max_folds の算出で fold>=5 を満たす最小 WF 値を algebraic 算出
7. yaml で WF 値を更新
8. テスト走破 (再)
9. cycle 2 RUN
10. 結果分析 (n_fold_effective median, Stage B pass 群 PnL)

順序を守らないと、 1-3 完了時点で旧 WF 値で起動 → fail-closed → RUN 不能になるため P1-2 と一体実装必須。
