# Detailed Design R2 — run-ga-full-rewrite (T018)

**親**: `detailed-design.md` + `design-review-r1.md` (Codex 2026-04-23)

Codex R1 レビューの全指摘 10 件を反映した最終実装仕様の差分。本 R2 で固めた
内容で実装に進む (詳細設計 R2 ラウンドは実施しない = 指摘への直接応答で十分
具体的・rate-limit 警戒のため)。

## R1 ブロッカー 3 件への応答

### B1: `best_row` の世代不整合

**問題**: `best_name` は全世代 cache から選ばれるが、`best_row` は最終世代
固定で取得 → 別世代の best 選出時に `best.metrics` / `live_criteria` が空化。

**対応**: `IndividualCacheEntry` に `generation` フィールドを追加:

```python
@dataclass(frozen=True)
class IndividualCacheEntry:
    generation: int
    fitness_pen: float
    stage_a_pass: bool
    stage_b_pass: bool
    stage_c_pass: bool

    @property
    def selection_score(self) -> tuple[int, int, int, float]:
        return (
            int(self.stage_c_pass),
            int(self.stage_b_pass),
            int(self.stage_a_pass),
            float(self.fitness_pen),
        )
```

`_update_cache` は `generation=lane.generation_count - 1` を受け取って埋める。

`_select_best` / `main` は以下のように変更:

```python
best_name, best_entry = _select_best(cache)
best_row = archive.get_row_snapshot(lane_id, best_entry.generation, best_name)
best_genome = genomes_by_name[best_name]  # 全世代 accumulate dict
```

### B2: `-math.inf` の Decimal 破綻

**問題**: `str(-math.inf)` は `"-inf"` を返し、`Decimal("-inf")` は
`InvalidOperation` で既存 `analyze_run.py` / `generate_run_report.py` を壊す。

**対応**: 方針を以下に変更:

1. **`summary.best.fitness` / `history[*].best_fitness` は常に有限 Decimal 文字列** を保証する。
2. 有限値が存在しない (全個体 failure) 場合は `"0"` を出力し、別フィールド
   `best.fitness_finite: bool=False` で失敗を表現する。
3. `fitness_pen` が finite でない場合 (`-inf` / `nan`) は `_safe_finite(x)` で
   `0.0` にフォールバックし、`warnings` に記録:

```python
def _safe_finite(x: float) -> tuple[float, bool]:
    """有限でない値を 0.0 に丸める。(value, was_finite)."""
    if math.isfinite(x):
        return x, True
    return 0.0, False
```

`summary.best.fitness` / `history[*].best_fitness` はすべてこの helper を
通した値を `str()` 化する (`"0"` / `"1.23"`)。

`IndividualCacheEntry.fitness_pen` は内部選択用なので `-math.inf` のままで OK
(tournament / elite 比較に使う)。

### B3: `strict_for_graduation` が実昇格に効かない

**問題**: R2 設計では `cross_pair_integration.strict_for_graduation=False` が
summary 側の `effective_graduation_count` だけを嵩上げしており、実際の
`lane_manager.graduation_criteria` には効いていない。semantic drift。

**対応**:
- `effective_graduation_count` は**廃止**。
- LaneManager の `graduation_criteria` にオーバーライド経路を追加するのも
  T017 への侵襲が大きいため、**`cross_pair_integration.strict_for_graduation`
  という新設フラグ自体を廃止** し、代わりに既存 SSOT
  `default.yaml::swim_lane.graduation_criteria.require_cross_pair_pass`
  (既に定義済) を一次ソースとして尊重する:

```yaml
swim_lane:
  graduation_criteria:
    require_stage_c_pass: true
    require_cross_pair_pass: true  # SSOT
```

- Phase 2 単一 instrument mode の現実: `require_cross_pair_pass: true` (現状
  default) ならば cross-pair skipped により graduation は常に 0。これは T017
  の `graduation_criteria` 関数の仕様通り。**本 TODO では変更しない**。
- summary には `graduation_count` (lane_manager から取る累積件数) のみ出し、
  `effective_graduation_count` は出さない。
- cross-pair 状況は `cross_pair_runtime_mode: "skipped_single_instrument"`
  として summary に明示する (運用側で graduation=0 の理由がわかる)。

将来 `require_cross_pair_pass: false` 運用を許すか、hard gate 化するかは別 TODO
で検討。

## R1 非ブロッカー指摘への応答

### 設定整合 (default.yaml SSOT)

- 新設の `cross_pair_integration` ブロックは**廃止** (B3 対応の一部)。
- loader は既存 `swim_lane.graduation_criteria` セクションを読み飛ばす
  (本 TODO では使わない = LaneManager に渡さない)。
- `AlphaFactoryConfig` から `cross_pair_integration` フィールドも削除。

### Validation (`elite_count` / `fitness_metric`)

- `GAConfig.__post_init__` に `elite_count >= 0` を追加済 (原 detailed-design
  §2.2 で実装されていたが R1 は再確認)。再確認で OK。
- `fitness_metric` は `sharpe` のみ実装する (Stage A が sharpe ベースで
  `fitness_pen` を計算するため)。`total_pnl` / `calmar` を指定したら
  WARN ログで「現状は sharpe として処理」と明記し、拒否はしない (default.yaml
  との後方互換のため)。
- CLI `--fitness-metric` は保持 (warning 出すだけ)。

### Bars 分割 (holdout fallback)

- `stage_a_n_bars` の再利用は誤り。holdout fallback は独自計算:

```python
holdout_n_bars = stage_windows.stage_c_holdout_days * bars_per_day
if not bars_holdout:
    if stage_windows.allow_stage_c_fallback_slice:
        bars_holdout = bars_stage_b[-holdout_n_bars:] if holdout_n_bars <= len(bars_stage_b) else bars_stage_b
        logger.warning("run_ga.holdout_fallback_slice", n_bars=len(bars_holdout), ...)
    else:
        raise RuntimeError(...)
```

### 契約維持 (`population_size` top-level)

- 現行 summary.json の top-level `population_size` を復活させる:

```python
summary["population_size"] = len(prev_population)  # 最終世代 population size
```

`generate_run_report.py` が読んでいるかどうか確認 → 読んでないが、`analyze_run.py`
互換を担保するため既存キー維持。

### テスト妥当性 (DB mock stmt 判別)

- `SessionLocal` monkeypatch は `_MockSession` に `scalars(stmt)` で stmt の
  `selected_columns` を調べて分岐:

```python
class _MockSession:
    def __init__(self, pair_row, bars_map):
        self._pair = pair_row
        self._bars_map = bars_map  # (start, end) -> list[PriceBar]
        self._last_stmt = None

    def scalars(self, stmt):
        self._last_stmt = stmt
        return self

    def one_or_none(self):
        # CurrencyPair を想定
        return self._pair

    def all(self):
        # PriceBarM1 を想定。stmt の whereclause から start/end を抽出は複雑
        # なので、簡便的に (call 順) でも済むが、R1 指摘を受けて
        # stmt の `column_descriptions` or `.froms` で CurrencyPair vs PriceBarM1
        # を判別する。
        return self._bars_map_all()
```

実装簡素化として: **stmt の string 表現に "price_bars_m1" を含むか** を判定:

```python
def _is_bars_stmt(stmt) -> bool:
    return "price_bars_m1" in str(stmt)
```

テストでは holdout 呼び出しが **list を返す / 空を返す** を個別に検証する。
2 case テスト:
- `test_smoke_run_holdout_ok`: holdout 範囲に bars 有り → fallback flag 不要
- `test_smoke_run_holdout_fallback`: holdout 範囲空 + `allow_stage_c_fallback_slice=True`

### 後方互換 (provenance 回帰テスト)

- `tests/alpha_factory/test_swim_lane.py` に 1 件追加:
  `test_run_generation_propagates_provenance_to_archive`
  - Tier1Lane.provenance = {"g0_i0": ("p1", "p2")}
  - archive.collect_stage_a が parent_a="p1", parent_b="p2" で呼ばれることを検証。

### Registry bridge (slot_from_category 再利用推奨)

- `_category_to_random_gen` は廃止、代わりに:

```python
from src.alpha_factory.primitives._base import slot_from_category

def _category_to_random_gen(cat) -> Literal["directional", "modulator"]:
    slot = slot_from_category(cat)  # "directional" | "local_gate"
    return "modulator" if slot == "local_gate" else "directional"
```

`slot_from_category` は primitives 側 canonical 実装 → 将来 category 追加でも
drift しない。

## 最終的な AlphaFactoryConfig フィールド (R1/R2 統合版)

```python
@dataclass(frozen=True)
class AlphaFactoryConfig:
    dataset: DatasetConfig
    backtest: BacktestSectionConfig
    ga: GAConfig
    stage_gate: StageGateConfig
    cross_pair: CrossPairConfig
    stage_windows: StageWindowsConfig
    # cross_pair_integration は廃止 (B3 対応)

    @property
    def live_criteria(self) -> Mapping[str, float | int]:
        return self.stage_gate.live_criteria
```

## 最終的な summary.json スキーマ (R1/R2 統合版)

既存互換キー:
- `run_id`, `run_number`, `generated_at`
- `dataset.instrument`, `dataset.start`, `dataset.end`, `dataset.bars`
- `ga_config.*`
- `backtest_config.initial_cash/leverage/units`
- `best.name`, `best.fitness` (Decimal 文字列; 有限値保証)
- `best.metrics` (BacktestMetrics-like dict)
- `live_criteria.checks`, `live_criteria.all_pass`
- `population_size` (top-level; 最終世代 size)

追加キー:
- `dataset.bars_stage_a`, `dataset.bars_stage_b`, `dataset.bars_holdout`
- `stage_gate_config.*` (簡易 dict)
- `cross_pair_config.mode`, `cross_pair_config.aggregator_lambda`
- `cross_pair_runtime_mode` ("skipped_single_instrument" | "enabled")
- `per_generation[]` (世代別 stage pass counts + best_fitness_pen)
- `best.stage_a_pass/stage_b_pass/stage_c_pass`
- `best.generation` (cache から)
- `best.fitness_finite` (bool)
- `best.selection_score` (list; 可視化用)
- `graduation_count` (lane_manager.promote_graduates; SSOT)
- `archive_parquet` (path string)

廃止:
- `cross_pair_integration.*` (R1 B3 対応)
- `effective_graduation_count` (R1 B3 対応)

## 最終的な history.json スキーマ

```json
[
  {
    "generation": 0,
    "best_fitness": "0.12",   // 既存互換: fitness_pen を Decimal 文字列
                              // 非有限値は "0" にフォールバック
    "stage_a_pass": 2,        // 追加
    "stage_b_pass": 0,        // 追加
    "stage_c_pass": 0,        // 追加
    "graduation_count": 0     // 追加
  },
  ...
]
```

## 実装順序の更新

1. `src/alpha_factory/archive.py::get_row_snapshot` 追加
2. `src/alpha_factory/swim_lane.py::Tier1Lane.provenance` 追加 + `_run_tier1_generation` で parent 伝搬
3. `src/alpha_factory/config.py` 新規 (cross_pair_integration 無し)
4. `src/alpha_factory/_registry_bridge.py` 新規 (`slot_from_category` 使用)
5. `scripts/alpha_factory/run_ga.py` 全面書換
   - `IndividualCacheEntry.generation` 追加
   - `_safe_finite` で `fitness_pen` 有限化
   - `best_row = archive.get_row_snapshot(lane_id, best_entry.generation, best_name)` 生成世代追跡
   - `summary["population_size"]` 復活
   - `effective_graduation_count` / `cross_pair_integration` 関連削除
6. `tests/scripts/test_alpha_factory_run_ga.py` 新規 (5 case; holdout ok/fallback 分離)
7. `tests/alpha_factory/test_swim_lane.py` に provenance 伝搬テスト 1 件追加
8. mypy / ruff / pytest

## 検証クライテリア (R2 追加)

- [ ] summary.best.fitness が常に `Decimal(s)` で parse 可能 (`-inf` / `nan` 禁止)
- [ ] summary の top-level `population_size` が存在
- [ ] history.best_fitness が非有限にならない
- [ ] best_row が best_name と同じ generation で lookup される
- [ ] swim_lane の provenance 伝搬テスト pass
- [ ] DB mock がスキーマ判別で pair/bars 振り分け
- [ ] holdout fallback のバー数が `stage_c_holdout_days` 計算に対応
