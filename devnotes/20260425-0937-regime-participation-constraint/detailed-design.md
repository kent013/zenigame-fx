# 詳細設計: regime-participation-constraint (RPC) Phase 1

## 使命・制約（絶対遵守）

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
- バグ修正はテストファースト
- 全施策にテスト必須
- uv 必須: `uv run pytest tests/alpha_factory/ tests/scripts/`
- ruff / mypy 通過: `uv run ruff check src/ tests/ scripts/` / `uv run mypy src/`
- Python 3.13 + numpy + pandas

## 概念設計リファレンス

`devnotes/20260425-0937-regime-participation-constraint/conceptual-design.md`

## 施策一覧

| # | 施策名 | 変更ファイル | 優先度 |
|---|--------|------------|--------|
| 1 | GAFeasibilityConfig dataclass 追加 | `src/alpha_factory/config.py` | High |
| 2 | default.yaml に ga.feasibility section 追加 | `config/alpha_factory/default.yaml` | High |
| 3 | IndividualCacheEntry に feasibility/violation 追加 + selection_score 6 要素化 | `scripts/alpha_factory/run_ga.py` | Critical |
| 4 | _update_cache() で feasibility 計算 | `scripts/alpha_factory/run_ga.py` | Critical |
| 5 | summary.json.selection_score 出力 6 要素対応 | `scripts/alpha_factory/run_ga.py` | High |
| 6 | run-report 説明文の 6 要素更新 + tc=0 比率追加 | `scripts/alpha_factory/generate_run_report.py` | High |
| 7 | 既存 smoke test の 6 要素期待値更新 + 新規 RPC test | `tests/scripts/test_alpha_factory_run_ga.py` + 新規 | Critical |

## 施策 1: GAFeasibilityConfig dataclass 追加

### 変更箇所
- ファイル: `src/alpha_factory/config.py` L100-143 周辺 (`GAConfig` 定義の直後)

### 波及変更
- `AGENTS.md`: なし (実行コマンドは無変更)
- `.claude/skills/zenigame-fx-*/SKILL.md`: なし
- `config/alpha_factory/default.yaml`: 施策 2 で対応
- `docs/alpha_factory/*.md`: なし (動作変更は run-report 変更で説明)

### 変更後コード
```python
@dataclass(frozen=True)
class GAFeasibilityConfig:
    """GA selection 用 feasibility 制約 (Phase 1: trade_count=0 淘汰のみ)."""

    entry_count_min: int = 1
    apply_from_generation: int = 0
    enable_fallback_when_all_infeasible: bool = True
    # 安全上限 (極端値で violation が inf 化するのを防ぐ)
    entry_count_min_hard_cap: int = 10000

    def __post_init__(self) -> None:
        if self.entry_count_min < 0:
            raise ValueError("ga.feasibility.entry_count_min must be >= 0")
        if self.entry_count_min > self.entry_count_min_hard_cap:
            raise ValueError(
                f"ga.feasibility.entry_count_min ({self.entry_count_min}) "
                f"exceeds hard cap ({self.entry_count_min_hard_cap})"
            )
        if self.apply_from_generation < 0:
            raise ValueError("ga.feasibility.apply_from_generation must be >= 0")


def _strict_bool(value: Any, default: bool) -> bool:
    """文字列 'false' を True 扱いする `bool(...)` の罠を回避."""
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        v = value.strip().lower()
        if v in ("true", "yes", "1", "on"):
            return True
        if v in ("false", "no", "0", "off"):
            return False
        raise ValueError(f"invalid bool string: {value!r}")
    if isinstance(value, (int, float)):
        return bool(value)
    raise ValueError(f"unsupported bool type: {type(value).__name__}")
```

そして `GAConfig` に新フィールド追加 (`field` を `dataclasses` から import 必要):
```python
from dataclasses import dataclass, field  # field を追加 import

@dataclass(frozen=True)
class GAConfig:
    # ... 既存フィールド ...
    n_edit_max: int = 3
    feasibility: GAFeasibilityConfig = field(default_factory=GAFeasibilityConfig)
```

`_build_ga` (L243) を更新 (`_strict_bool` で 'false' 文字列を正しく解釈):
```python
def _build_ga(raw: Mapping[str, Any]) -> GAConfig:
    feas_raw = raw.get("feasibility") or {}
    apply_from_gen = int(feas_raw.get("apply_from_generation", 0))
    generations = int(raw.get("generations", 15))
    if apply_from_gen > generations:
        raise ValueError(
            f"ga.feasibility.apply_from_generation ({apply_from_gen}) "
            f"must be <= ga.generations ({generations})"
        )
    feasibility = GAFeasibilityConfig(
        entry_count_min=int(feas_raw.get("entry_count_min", 1)),
        apply_from_generation=apply_from_gen,
        enable_fallback_when_all_infeasible=_strict_bool(
            feas_raw.get("enable_fallback_when_all_infeasible"), default=True
        ),
    )
    return GAConfig(
        # ... 既存パラメータ ...
        feasibility=feasibility,
    )
```

### テスト計画
- `tests/alpha_factory/test_config.py` に追加:
  - `test_ga_feasibility_default_values`: 既存 default.yaml 読み込みで `entry_count_min=1`, `apply_from_generation=0` になること
  - `test_ga_feasibility_invalid_negative`: `entry_count_min=-1` で `ValueError`
  - `test_ga_feasibility_missing_section_uses_default`: `ga` に `feasibility` 欠落時に default で復元

### リスク
- `frozen=True` の dataclass で `field(default_factory=...)` は Python 3.13 で互換動作 (mutable default 経由ではない)
- 既存テストが `GAConfig` を直接生成している場合、`feasibility` パラメータが必須化されるリスク → `default_factory` で吸収済 (新規パラメータは optional)

## 施策 2: default.yaml に ga.feasibility section 追加

### 変更箇所
- ファイル: `config/alpha_factory/default.yaml` の `ga:` セクション末尾

### 変更後コード (yaml 抜粋、既存値変更なし、追記のみ)
現行 `default.yaml` (population_size: 40 / generations: 15) は無変更のまま、`ga:` セクションの末尾に **追記のみ**:
```yaml
ga:
  # ... 既存値 (population_size: 40, generations: 15 等) はそのまま ...
  n_edit_max: 3
  feasibility:
    entry_count_min: 1                       # Phase 1: trade_count >= 1 を feasible 条件
    apply_from_generation: 0                 # 0 世代目から制約適用
    enable_fallback_when_all_infeasible: true  # 全個体 infeasible で旧 4 要素にフォールバック
```

### テスト計画
- `tests/alpha_factory/test_config.py` の `test_default_yaml_loadable` で feasibility が正しく読み込まれること

### リスク
- なし (新規 section の追加のみ、既存値変更なし)

## 施策 3: IndividualCacheEntry 拡張 + selection_score 6 要素化

### 変更箇所
- ファイル: `scripts/alpha_factory/run_ga.py` L100-118

### 現行コード
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

### 変更後コード
```python
@dataclass(frozen=True)
class IndividualCacheEntry:
    generation: int
    fitness_pen: float
    stage_a_pass: bool
    stage_b_pass: bool
    stage_c_pass: bool
    feasible: bool = True
    violation_magnitude: float = 0.0

    @property
    def selection_score(self) -> tuple[int, float, int, int, int, float]:
        """Lexicographic 6-tuple: (feasible_int, -violation, C_pass, B_pass, A_pass, fitness_pen).

        非有限値 (NaN/inf) は順序比較を破壊するため finite guard で正規化:
        - violation: 非有限なら +inf 扱い (= -inf を二要素目に置く → 確実に最下位)
        - fitness_pen: 既存と同じく非有限は -inf として比較最下位扱い
        """
        v = self.violation_magnitude
        if not math.isfinite(v):
            v_norm = math.inf  # 非有限 violation は最大とみなす
        else:
            v_norm = float(v)
        fp = self.fitness_pen
        if not math.isfinite(fp):
            fp_norm = -math.inf
        else:
            fp_norm = float(fp)
        return (
            int(self.feasible),
            -v_norm,
            int(self.stage_c_pass),
            int(self.stage_b_pass),
            int(self.stage_a_pass),
            fp_norm,
        )
```

### 波及変更
- `scripts/alpha_factory/run_ga.py` 内の以下ヶ所:
  - L380-396 (sort key): `selection_score` 経由なので変更不要
  - L475 (best 選択): `selection_score` 経由なので変更不要
  - L370 tournament: 同上
  - L653 summary 出力: 施策 5 で対応

### リスク
- `feasible=True` を default にすることで、cache entry 直接生成箇所 (L448 の archive 不在 fallback) は無変更で動作する (既存個体は全 feasible 扱い)
- ただし archive 不在 = `fitness_pen=-math.inf` の場合、無条件で feasible=True にすると評価不能個体が無駄に上位にくる懸念 → fallback 個体は `feasible=False, violation_magnitude=math.inf` に修正すべき (詳細は施策 4)

## 施策 4: _update_cache() で feasibility 計算

### 変更箇所
- ファイル: `scripts/alpha_factory/run_ga.py` L437-467

### 変更後コード
```python
def _update_cache(
    cache: dict[str, IndividualCacheEntry],
    population: list[Genome],
    archive: GenomeArchive,
    lane_id: str,
    generation: int,
    feasibility_cfg: GAFeasibilityConfig,
) -> None:
    """archive の row から fitness_pen / stage pass / feasibility を取り出し cache 更新."""
    apply = generation >= feasibility_cfg.apply_from_generation
    entry_min = feasibility_cfg.entry_count_min
    for g in population:
        row = archive.get_row_snapshot(lane_id, generation, g.name)
        if row is None:
            # archive 不在 (評価失敗) は明確に infeasible として violation を最大化
            cache[g.name] = IndividualCacheEntry(
                generation=generation,
                fitness_pen=-math.inf,
                stage_a_pass=False,
                stage_b_pass=False,
                stage_c_pass=False,
                feasible=False if apply else True,
                violation_magnitude=float(entry_min) if apply else 0.0,
            )
            continue
        fp_raw = row.get("fitness_pen")
        try:
            fp = float(fp_raw) if fp_raw is not None else -math.inf
        except (TypeError, ValueError):
            fp = -math.inf
        # trade_count を archive 列から取得
        tc_raw = row.get("trade_count")
        try:
            trade_count = int(tc_raw) if tc_raw is not None else 0
        except (TypeError, ValueError):
            trade_count = 0
        if apply:
            feasible = trade_count >= entry_min
            violation = max(0.0, float(entry_min - trade_count))
        else:
            feasible = True
            violation = 0.0
        cache[g.name] = IndividualCacheEntry(
            generation=generation,
            fitness_pen=fp,
            stage_a_pass=bool(row.get("stage_a_pass", False)),
            stage_b_pass=bool(row.get("stage_b_pass", False)),
            stage_c_pass=bool(row.get("stage_c_pass", False)),
            feasible=feasible,
            violation_magnitude=violation,
        )
```

呼び出し側 (callsite): `_update_cache(...)` の引数に `feasibility_cfg` を追加 (L390 周辺、`ga_cfg.feasibility` を渡す)。

### Fallback ロジック (R2 緩和) — 共通化必須
`enable_fallback_when_all_infeasible=True` 時、`_tournament` / `_breed_next_gen` (elite 選抜) / `_select_best` の **3 ヶ所すべて** で同一ロジックを適用しなければ規則不整合が発生する。

そのため共通スコア関数を定義:
```python
def _selection_key(
    entry: IndividualCacheEntry,
    fallback_active: bool,
) -> tuple:
    """fallback_active=True (全 infeasible) の場合は旧 4 要素にフォールバック."""
    if fallback_active:
        fp = entry.fitness_pen if math.isfinite(entry.fitness_pen) else -math.inf
        return (
            int(entry.stage_c_pass),
            int(entry.stage_b_pass),
            int(entry.stage_a_pass),
            fp,
        )
    return entry.selection_score


def _is_all_infeasible(
    entries: Iterable[IndividualCacheEntry],
    feasibility_cfg: GAFeasibilityConfig,
) -> bool:
    if not feasibility_cfg.enable_fallback_when_all_infeasible:
        return False
    return not any(e.feasible for e in entries)
```

そして `_tournament`, `_breed_next_gen` の `sorted()` (L382), `_select_best` の 3 箇所すべてで:
```python
fallback = _is_all_infeasible(cache.values(), feasibility_cfg)
key_fn = lambda kv: _selection_key(kv[1], fallback)
# tournament の場合は sample 内のみで判定 (sample 局所 fallback)
```

**重要**: `_tournament` の sample が局所的に全 infeasible でも、cache 全体に feasible 個体がいれば fallback 不要。fallback 判定は cache 全体スコープで行うこと (sample 局所判定は局所最適化を歪める)。

### テスト計画
- `tests/scripts/test_alpha_factory_run_ga_feasibility.py` (新規):
  - `test_feasible_individual_wins_over_infeasible`: feasible=True, fitness_pen=-1 vs feasible=False, fitness_pen=0 で feasible=True が選ばれる
  - `test_violation_magnitude_orders_infeasible`: 両方 infeasible で violation=2 vs violation=5 → violation=2 が勝つ
  - `test_apply_from_generation_disables_pre_threshold`: apply_from_generation=2, generation=1 で全 feasible=True (制約無効)
  - `test_fallback_when_all_infeasible_uses_legacy_score`: 全 feasible=False で旧 4 要素比較に切り替わる
  - `test_archive_missing_treated_as_infeasible`: archive row=None で feasible=False, violation=entry_count_min

### リスク
- `archive.get_row_snapshot` 戻り値の `trade_count` 列が常に存在することを前提とする → 既存 archive schema 確認: `trade_count` は `src/alpha_factory/archive.py` L70 周辺で標準列。Verified
- `tc_raw` が NaN のとき `int(nan) → ValueError`: try/except で 0 にフォールバック済 (entry_min=1 なら infeasible 扱い、妥当)

## 施策 5: summary.json.selection_score 出力対応

### 変更箇所
- ファイル: `scripts/alpha_factory/run_ga.py` L653 周辺

### 現行コード (推定)
```python
"selection_score": [
    int(best_entry.stage_c_pass),
    int(best_entry.stage_b_pass),
    int(best_entry.stage_a_pass),
    float(best_entry.fitness_pen),
],
```

### 変更後コード
非有限値の伝入を防ぐため、現行の `best_fitness_val` (`_safe_finite` 経由で有限化済み) を使用:
```python
# 現行 L576-577: best_fitness_val, best_finite = _safe_finite(best_entry.fitness_pen)
# 同様に violation_magnitude も有限化
best_violation_val, _ = _safe_finite(best_entry.violation_magnitude)

"selection_score": [
    int(best_entry.feasible),
    -float(best_violation_val),
    int(best_entry.stage_c_pass),
    int(best_entry.stage_b_pass),
    int(best_entry.stage_a_pass),
    float(best_fitness_val),  # 既存と同じ有限化済値
],
"selection_score_schema": "v2_feasibility",  # 新規 schema バージョン明示
```

加えて per_generation 集計に `feasible_count` を追加。**重要**: 現行の `sanitized_per_generation` (L583 周辺) はホワイトリスト方式でキーを絞っているため、`feasible_count` を明示的にコピーしないと脱落する:
```python
# generation ごとに feasible 個体数をカウント
for g in range(generations + 1):
    feasible_count = sum(
        1 for e in cache.values()
        if e.feasible and e.generation == g
    )
    no_trade_count = sum(
        1 for e in cache.values()
        if e.generation == g  # trade_count は archive row 側参照、別途算出
    )
    pg["feasible_count"] = feasible_count
    pg["no_trade_ratio"] = ...

# sanitized_per_generation のホワイトリストに feasible_count, no_trade_ratio を追加
SANITIZED_KEYS = {..., "feasible_count", "no_trade_ratio"}
```

### テスト計画
- `tests/scripts/test_alpha_factory_run_ga.py` smoke test:
  - `summary.json` の `selection_score` 配列長が 6 であること
  - `selection_score_schema == "v2_feasibility"` であること
  - `per_generation[].feasible_count` が int であること

### リスク
- summary.json を読む下流ツール (run-report, post-run-review skill) が旧 4 要素を仮定している場合 break する → 施策 6 で run-report 側を更新

## 施策 6: run-report 説明文 + tc=0 比率追加

### 変更箇所
- ファイル: `scripts/alpha_factory/generate_run_report.py` L451 周辺 (selection_score 説明文)

### 変更後コード (snippet)
注記文 (L451 周辺):
```python
# 旧 (L453 付近):
# "Best は (stage_c_pass, stage_b_pass, stage_a_pass, fitness_pen) の辞書式。"
# 新 (selection_score_schema 値で分岐):
schema = summary.get("selection_score_schema", "v1_legacy")
if schema == "v2_feasibility":
    note = "Best は (feasible, -violation, stage_c_pass, stage_b_pass, stage_a_pass, fitness_pen) の辞書式 (v2_feasibility)。"
else:
    note = "Best は (stage_c_pass, stage_b_pass, stage_a_pass, fitness_pen) の辞書式 (v1_legacy)。"
```

加えて新セクションを生成。`generate_run_report.py` のスコープに合わせ `summary["best"]` と `archive_rows` を利用 (`best_entry` 等のローカル変数は存在しないため):
```python
best = summary.get("best") or {}
selection_score = summary.get("selection_score") or []
schema = summary.get("selection_score_schema", "v1_legacy")
# v2_feasibility の場合 selection_score[0] が feasible_int (0 or 1)
if schema == "v2_feasibility" and len(selection_score) >= 2:
    best_feasible = bool(selection_score[0])
else:
    best_feasible = True  # v1 互換時は表示を ✅ に固定

best_trade_count = int(best.get("trade_count", 0))

no_trade_count = sum(
    1 for r in archive_rows if int(r.get("trade_count", 0) or 0) == 0
)
no_trade_ratio = no_trade_count / max(1, len(archive_rows))

lines.append("\n## Feasibility 集計\n")
lines.append(f"- trade_count=0 個体比率: {no_trade_ratio:.1%} ({no_trade_count}/{len(archive_rows)})")
lines.append(f"- best 個体 trade_count: {best_trade_count}")
lines.append(f"- best 個体 feasibility: {'✅' if best_feasible else '❌'}")
```

加えて、波及変更として `.claude/skills/zenigame-fx-run-report/SKILL.md` L120 の旧 4 要素記述を v1/v2 両対応の説明に更新する。

### テスト計画
- `tests/scripts/test_generate_run_report.py` (既存があれば):
  - `report` に `Feasibility 集計` セクションが含まれること
  - `trade_count=0 個体比率` 行が含まれること
- なければ新規追加

### リスク
- 既存 run-9.md は「Best とは別物です」のような注記があるため、注記更新を忘れると誤読 → 注記も同時更新

## 施策 7: 既存 smoke test の更新 + 新規 RPC test

### 変更箇所
- ファイル: `tests/scripts/test_alpha_factory_run_ga.py` L394 (selection_score 期待値)
- 新規: `tests/scripts/test_alpha_factory_run_ga_feasibility.py`

### 変更後 (smoke test)
```python
# tests/scripts/test_alpha_factory_run_ga.py L394-395 周辺:
# 旧 (現行):
# assert summary["selection_score"] == [int(c), int(b), int(a), fp]
# 新:
assert summary["selection_score_schema"] == "v2_feasibility"
assert len(summary["selection_score"]) == 6
assert summary["selection_score"][0] in (0, 1)  # feasible_int
```

### 新規 test (施策 4 と同じリスト + elite 選抜整合 + run-report 互換)
- `test_feasible_individual_wins_over_infeasible`
- `test_violation_magnitude_orders_infeasible`
- `test_apply_from_generation_disables_pre_threshold`
- `test_fallback_when_all_infeasible_uses_legacy_score`
- `test_archive_missing_treated_as_infeasible`
- **追加**: `test_elite_selection_consistent_with_tournament_under_fallback` (`_breed_next_gen` の sorted_pop が tournament/select_best と同じ規則で動くこと)
- **追加**: `test_tournament_sample_local_all_infeasible_uses_global_check` (sample 局所では全 infeasible でも global feasible が存在する場合 fallback 不発動)

### 新規ファイル: `tests/scripts/test_generate_run_report.py`
- `test_run_report_v1_legacy_compat`: `selection_score_schema=="v1_legacy"` 時の出力に旧 4 要素説明文があること
- `test_run_report_v2_feasibility_section`: `selection_score_schema=="v2_feasibility"` 時に「Feasibility 集計」セクションと `trade_count=0 個体比率` 行が出ること

### リスク
- 既存 smoke test が「selection_score == 旧形式の 4 要素」を厳密一致でチェックしていれば必ず fail → 必ず更新する

## 実装モード

| 項目 | 内容 |
|------|------|
| 推奨モード | incremental |
| 判断根拠 | 既存 selection_score 構造を保ち、tuple 拡張のみで NSGA-II 化なし。テストファースト + 段階的に施策 1→2→3→4→5→6→7 の順で実装可能 |
| 競合リスク | 同時並行で `run_ga.py` を変更する他 TODO がない (Open=0) ため低 |
| 想定実装時間 | 中 (config dataclass + selection_score 拡張 + 4 ファイルの追従 + 5 つの新規テスト) |

## 全体リスクサマリー

- **構造変更の影響範囲**: `run_ga.py` 中核 + config + report + test の連鎖。ただしすべて selection_score の data flow に集約するため見通しは良い
- **後退リスク**: feasibility 適用で「現状の見かけ best」(trade_count=0 個体) が選ばれなくなり、Run 10 の best_fitness が一時的に低下する可能性 → これは設計通りの効果 (no-trade attractor を破壊するため)
- **計測ノイズ**: H1 検証で `trade_count>0 ∧ total_pnl=0` が併存すると効果が見えにくくなる → run-report の Feasibility セクションで両方並記して観察

## 検証計画

Phase 1 完了後の Run 10 で以下を確認:
1. `summary.json.selection_score_schema == "v2_feasibility"` (smoke)
2. archive で `trade_count=0` 比率 < 50% (success criterion, 統計的有意性は主張しない)
3. best 個体の `trade_count > 0` (H2)
4. Stage A pass 数 > 0 (副次効果の観察)

3-5 seed の再現確認は次段検証計画 (Phase 2 設計時に組み込み)。
