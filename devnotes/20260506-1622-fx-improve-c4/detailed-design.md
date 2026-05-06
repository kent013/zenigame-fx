# 詳細設計: Run 37 施策 (cycle 4)

## 概要

cycle 3 sidecar データで verified された **H1 (探索圧不整合)** に対する構造的介入。 当初想定の「fitness_pen に fold-aware penalty 追加」案は実装経路調査の結果、 archive→cache→GA selection の各段階での修正が必要で複雑化することが判明。

代わりに、 **IndividualCacheEntry の `selection_score` 9-tuple 化** で同等効果を達成する設計に切り替えた。 GA selection (tournament + elite 両方) は `_selection_key` 経由で selection_score を使うため、 selection_score への新しい lexicographic 要素追加だけで全 selection 経路に効く。

## 施策一覧

| # | 施策名 | 変更ファイル | target_metric |
|---|--------|------------|--------------|
| C1 | IndividualCacheEntry に fold_robust component 追加 (selection_score 8→9 要素) | `scripts/alpha_factory/run_ga.py` (IndividualCacheEntry / selection_score / _archive_row_to_cache_entry / _legacy_selection_score) + 設定 + tests | Stage B pass count、 pfre_mean 後期 |

---

## C1: IndividualCacheEntry に fold_robust component 追加

### target_metric / failure_mode / causal_path / falsification / success_criterion

- **target_metric**: Stage B pass > 0、 pfre_mean 後期 > 0.4
- **failure_mode**: cycle 3 sidecar で verified — fitness_pen +306% (gen 5-15→50-60) 一方 fold_sign_mean -20% で減少
- **causal_path**: GA selection が fitness_pen のみで進化 → fold robustness を考慮しない方向に偏る
- **falsification**: cycle 5 sidecar で「fitness_pen 上昇に同期して fold_sign / pfre が上昇」 が verified なら確証、 上昇しなければ別の構造的問題 (primitive / data / fold 設計)
- **success_criterion**: 主 KPI = Stage B pass > 0 (1 件以上)、 副 KPI = pfre_mean 後期 (gen 50-60) > 0.4

### 設計方針

`IndividualCacheEntry.selection_score` の lexicographic 8-tuple に `fold_robust` を追加して **9-tuple** 化。 fold_robust は `pfre >= threshold` の binary 値。

```python
# 現行 (run-36 まで)
selection_score: (feasible, -violation, stage_b_pass, stage_c_feasible, C_pass, B_pass, A_pass, fitness_pen)

# cycle 4 拡張 (run-37 から)
selection_score: (feasible, -violation, stage_b_pass, stage_c_feasible, C_pass, B_pass, A_pass, fold_robust, fitness_pen)
                                                                                                  ^^^^^^^^^^^^
                                                                                                  NEW (上から 8 要素目、 fitness_pen より上位)
```

### fold_robust の判定

```python
fold_robust = (
    1 if (
        pfre is not None
        and math.isfinite(pfre)
        and pfre >= fold_robust_threshold  # default 0.4
    )
    else 0
)
```

- Stage A 通過 + Stage B 評価済 + pfre >= 0.4: fold_robust=1 (有利)
- Stage A 通過 + Stage B 評価済 + pfre < 0.4: fold_robust=0
- Stage A 不通過 (pfre 未確定): fold_robust=0 (Stage A 不通過個体は selection_score 上位の他要素で既に下位、 fold_robust=0 で副作用なし)
- pfre が NaN/Inf: fold_robust=0 (保守的)

### threshold 値の根拠

- `fold_robust_threshold = 0.4` (default)
- Stage B 通過閾値 `positive_fold_ratio_min=0.6` の **67%** (中間ヘッドルーム)
- run-36 後期 (gen 50-60) Stage A 上位 20% 群 pfre_mean 0.296 → 全員 fold_robust=0
- 0.4 を超えるには真の WF robustness が必要 → GA 探索圧が「robust signal を見つける」 方向にシフト

### 変更箇所

#### 1. `scripts/alpha_factory/run_ga.py` の IndividualCacheEntry 拡張

**Before** (line 159-178):
```python
@dataclass(frozen=True)
class IndividualCacheEntry:
    """GA selection 用の cache entry (archive 由来)..."""

    generation: int
    fitness_pen: float
    stage_a_pass: bool
    stage_b_pass: bool
    stage_c_pass: bool
    feasible: bool = True
    violation_magnitude: float = 0.0
    stage_c_feasible: bool = True
```

**After**:
```python
@dataclass(frozen=True)
class IndividualCacheEntry:
    """GA selection 用の cache entry (archive 由来).

    cycle 4: ``fold_robust`` を追加し selection_score を 8→9 要素化。
    GA 探索圧を fold robustness 方向にシフトする (devnotes/20260506-1622-fx-improve-c4/)。
    """

    generation: int
    fitness_pen: float
    stage_a_pass: bool
    stage_b_pass: bool
    stage_c_pass: bool
    feasible: bool = True
    violation_magnitude: float = 0.0
    stage_c_feasible: bool = True
    fold_robust: bool = False  # cycle 4: pfre >= fold_robust_threshold (default 0.4)
```

**selection_score 拡張** (現 line 181-206):
```python
@property
def selection_score(self) -> tuple[int, float, int, int, int, int, int, int, float]:
    """Lexicographic 9-tuple v3.2:
    ``(feasible, -violation, stage_b_pass, stage_c_feasible, C_pass, B_pass, A_pass, fold_robust, fitness_pen)``.

    cycle 4: fold_robust (8 要素目) を fitness_pen より上位に配置。
    GA 進化中に「Stage B 閾値到達可能性」 を考慮した selection を実現。

    非有限値 (NaN/inf) は順序比較を破壊するため finite guard で正規化。
    """
    v = self.violation_magnitude
    v_norm = math.inf if not math.isfinite(v) else float(v)
    fp = self.fitness_pen
    fp_norm = -math.inf if not math.isfinite(fp) else float(fp)
    return (
        int(self.feasible),
        -v_norm,
        int(self.stage_b_pass),
        int(self.stage_c_feasible),
        int(self.stage_c_pass),
        int(self.stage_b_pass),
        int(self.stage_a_pass),
        int(self.fold_robust),  # cycle 4 新要素
        fp_norm,
    )
```

注: `_legacy_selection_score` (4 要素) は変更しない (fallback 専用、 全体 infeasible 時のみ使用、 fold_robust は通常 infeasible 個体には意味がない)。

#### 2. `_archive_row_to_cache_entry` で fold_robust を archive から計算

archive の `positive_fold_ratio_effective` 列を読み、 threshold 比較で fold_robust を計算:

**Before** (現 line 651-714 周辺):
```python
def _archive_row_to_cache_entry(row: dict, ...) -> IndividualCacheEntry:
    # ... fitness_pen, stage_X_pass を読む ...
    return IndividualCacheEntry(
        generation=...,
        fitness_pen=fp,
        stage_a_pass=...,
        # ...
    )
```

**After**:
```python
def _archive_row_to_cache_entry(row: dict, ..., fold_robust_threshold: float = 0.4) -> IndividualCacheEntry:
    # ... 既存ロジック ...
    pfre = row.get("positive_fold_ratio_effective")
    fold_robust = bool(
        pfre is not None
        and math.isfinite(float(pfre)) if pfre is not None else False
        and float(pfre) >= fold_robust_threshold
    ) if pfre is not None and math.isfinite(float(pfre) if pfre is not None else 0) else False
    # 簡潔版:
    try:
        pfre_val = float(pfre) if pfre is not None else None
    except (TypeError, ValueError):
        pfre_val = None
    fold_robust_flag = (
        pfre_val is not None
        and math.isfinite(pfre_val)
        and pfre_val >= fold_robust_threshold
    )
    return IndividualCacheEntry(
        # ... 既存 ...
        fold_robust=fold_robust_flag,
    )
```

**呼び出し側**: `_archive_row_to_cache_entry` を呼ぶ箇所で `fold_robust_threshold=cfg.stage_gate.fold_robust_threshold` を渡す (新設定値、 default 0.4)。

#### 3. 設定追加: `cfg.stage_gate.fold_robust_threshold`

`src/alpha_factory/config.py` または同等の設定 dataclass に追加:

```python
@dataclass
class StageGateConfig:
    # ... 既存 ...
    # cycle 4: GA selection の fold_robust 判定閾値 (positive_fold_ratio_effective >= threshold)
    # default 0.4 = Stage B 閾値 0.6 の 67% (中間ヘッドルーム)
    # @ref: devnotes/20260506-1622-fx-improve-c4/detailed-design.md
    fold_robust_threshold: float = 0.4
```

YAML 設定 (`config/alpha_factory/default.yaml`) には**追加しない** (default で 0.4 のまま、 必要なら後 cycle で追加検討)。

#### 4. テスト

`tests/alpha_factory/test_run_ga_individual_cache_entry.py` (または既存 test ファイルに追加):

- test_selection_score_9_tuple_with_fold_robust_high: pfre 0.5 → fold_robust=1 → selection_score 内 8 番目要素 = 1
- test_selection_score_9_tuple_with_fold_robust_low: pfre 0.3 → fold_robust=0
- test_selection_score_9_tuple_with_pfre_nan: pfre=NaN → fold_robust=0
- test_selection_score_9_tuple_stage_a_fail_no_pfre: stage_a_pass=False, pfre=None → fold_robust=0
- test_selection_score_lexicographic_order: 同 fitness_pen で fold_robust が選別軸として機能
- test_archive_row_to_cache_entry_extracts_fold_robust: archive row→cache entry で fold_robust 正しく計算
- test_legacy_selection_score_unchanged: legacy 4-tuple は不変 (互換性確認)

合計 7 件。

### 波及変更

| ファイル | 変更 | 理由 |
|---------|------|------|
| `scripts/alpha_factory/run_ga.py` | IndividualCacheEntry + selection_score + _archive_row_to_cache_entry の 3 箇所 | 主体実装 |
| `src/alpha_factory/config.py` | StageGateConfig に fold_robust_threshold: float = 0.4 追加 | 設定 |
| `tests/alpha_factory/test_run_ga_individual_cache_entry.py` または既存 tests | 7 件 | テスト |
| `AGENTS.md` | 不要 | 公開 API / CLI 変更なし |
| `.claude/skills/zenigame-fx-*/SKILL.md` | 不要 | skill 契約変更なし |
| `config/alpha_factory/default.yaml` | 不要 (default で動作) | 必要なら後 cycle で追加 |

### ルックアヘッドバイアスチェック (primitive 変更時必須)
- [x] 該当しない: GA selection ロジック変更のみ、 primitive / 評価経路に触れない

### パフォーマンスチェック
- [x] selection_score tuple が 8→9 要素に拡大 (1 int 追加)。 pop=96 × gen=60 で 5760 個体 × tuple 1 要素 ≈ 6KB の memory 追加。 影響なし

### テスト計画

- [x] 既存テスト更新: IndividualCacheEntry を使う既存 test (もしあれば) で 9 要素 tuple に対応
- [x] 新規テスト 7 件 (上記)

### リスク

| リスク | 評価 | 緩和策 |
|---|---|---|
| selection_score 形状変更で既存 test 破壊 | 中 (lexicographic 比較は形状依存) | 既存 test に 1 要素追加で対応、 default value False で挙動温存 |
| 既存 archive (旧 RUN) で positive_fold_ratio_effective 列 不在 | 低 (column 不在チェック付き、 None で fold_robust=False) | _archive_row_to_cache_entry で defensive check |
| GA selection の予測不能な変化 | 中 (本意の介入だが過剰 selection 圧の懸念) | threshold 0.4 は Stage B 閾値 0.6 の 67%、 過厳格でない。 実 RUN で観察 |
| 副作用: best 個体の trade_count / PnL 劣化 | 中 (見栄え改善 vs 構造改善のトレードオフ) | analyze で trade_count 分布、 total_pnl 分布も観察 |

### 禁止事項チェック

- ✅ 1 期間延長: dataset 不変
- ✅ 2 見栄え改善: GA selection 構造的拡張、 数値弄りではない
- ✅ 3 GA ハック: 該当なし
- ✅ 4 閾値緩和: 既存閾値不変、 むしろ selection を厳格化
- ✅ 5 複雑化: 1 int 追加のみ、 lexicographic interpretation は明確
- ✅ 6 取引回数削減: pfre は trade_count 直接介入ではない、 cycle 4 後 trade_count 分布を観察
- ✅ 7 オーバーナイト: 該当なし
- ✅ メタ過学習ガード: Structural (新 selection 軸の追加)

---

## Run 37 実行パラメータ

| パラメータ | 値 | R36 からの変更 |
|-----------|-----|--------------|
| instrument | EUR_JPY | 不変 |
| population_size | 96 | 不変 |
| generations | 60 | 不変 |
| mutation_rate | 0.5 | 不変 |
| seed | 23 | 不変 |
| max_workers | 2 | 不変 |
| max_clause | 2 | 不変 (cycle 5 以降で再評価) |
| **fold_robust_threshold** | **0.4** | **新規 (default)** |
| Stage A threshold | -0.0172 | 不変 |
| live_criteria | sharpe>=1.0 / pnl>=50000 | 不変 |
