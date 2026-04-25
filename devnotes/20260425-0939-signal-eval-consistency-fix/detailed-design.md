# 詳細設計: signal-eval-consistency-fix (無取引優位の選抜下位化)

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
- **バグ修正はテストファースト**: 再現最小テスト → FAIL 確認 → 修正 → PASS
- **全施策にテスト必須**
- **テスト命名**: 振る舞いを説明する汎用的な名前
- **uv 必須**: `uv run pytest tests/scripts/test_alpha_factory_run_ga.py`
- **ruff / mypy 通過**
- Python 3.13 + numpy + pandas

## 概念設計リファレンス

[devnotes/20260425-0939-signal-eval-consistency-fix/conceptual-design.md] (APPROVED Round 2)

## 施策一覧

| # | 施策名 | 変更ファイル | 優先度 |
|---|--------|------------|--------|
| 1 | `IndividualCacheEntry` に `feasible_trade` 追加 | `scripts/alpha_factory/run_ga.py` | Critical |
| 2 | `_update_cache` で archive `trade_count` から導出 | `scripts/alpha_factory/run_ga.py` | Critical |
| 3 | `selection_score` lex tuple 拡張 (5 要素) | `scripts/alpha_factory/run_ga.py` | Critical |
| 4 | summary `selection_score` 出力を 5 要素に拡張 | `scripts/alpha_factory/run_ga.py` | High |
| 5 | summary 既存テスト (4 要素 → 5 要素) を更新 | `tests/scripts/test_alpha_factory_run_ga.py` | Critical |
| 6 | 新規回帰テスト (selection 順序検証) | `tests/scripts/test_alpha_factory_run_ga.py` | Critical |
| 7 | docs / generate_run_report.py 説明文更新 + 新規 report テスト | `docs/alpha_factory/clause-architecture.md` / `scripts/alpha_factory/generate_run_report.py` / `tests/scripts/test_generate_run_report.py` (新規) | High |

---

## 施策 1+2+3: `IndividualCacheEntry` 拡張 + selection_score 拡張

### 変更箇所
- ファイル: `scripts/alpha_factory/run_ga.py`
- L100-118 (IndividualCacheEntry dataclass + selection_score property)
- L444-467 (_update_cache)

### 波及変更
- `AGENTS.md`: GA selection ロジックの説明箇所が無いため変更なし (確認済)
- `.claude/skills/zenigame-fx-*/SKILL.md`: 関連記述なし (確認済)
- `config/alpha_factory/default.yaml`: 変更なし
- `docs/alpha_factory/clause-architecture.md`: best 選抜の lex tuple 記述更新 (施策 7)
- `docs/alpha_factory/concepts/genome-archive-schema.md`: archive 不変なので変更なし

### 現行コード (L100-118)

```python
@dataclass(frozen=True)
class IndividualCacheEntry:
    """GA selection 用の cache entry (archive 由来)."""

    generation: int
    fitness_pen: float
    stage_a_pass: bool
    stage_b_pass: bool
    stage_c_pass: bool

    @property
    def selection_score(self) -> tuple[int, int, int, float]:
        """Lexicographic tuple: (C_pass, B_pass, A_pass, fitness_pen)."""
        return (
            int(self.stage_c_pass),
            int(self.stage_b_pass),
            int(self.stage_a_pass),
            float(self.fitness_pen),
        )
```

### 変更後コード (L100-120)

```python
@dataclass(frozen=True)
class IndividualCacheEntry:
    """GA selection 用の cache entry (archive 由来)."""

    generation: int
    fitness_pen: float
    stage_a_pass: bool
    stage_b_pass: bool
    stage_c_pass: bool
    feasible_trade: bool  # archive canonical trade_count >= 1

    @property
    def selection_score(self) -> tuple[int, int, int, int, float]:
        """Lexicographic tuple: (C_pass, B_pass, A_pass, feasible_trade, fitness_pen).

        Stage 全不通過個体間で、無取引 (trade_count=0) を取引した負 Sharpe より
        下位化するため `feasible_trade` を A_pass と fitness_pen の間に挿入する。
        archive canonical (`fitness_pen` / `total_pnl`) は不変。
        """
        return (
            int(self.stage_c_pass),
            int(self.stage_b_pass),
            int(self.stage_a_pass),
            int(self.feasible_trade),
            float(self.fitness_pen),
        )
```

### 現行コード (L437-467, `_update_cache` function)

```python
def _update_cache(
    cache: dict[str, IndividualCacheEntry],
    population: Sequence[Genome],
    archive: GenomeArchive,
    lane_id: str,
    generation: int,
) -> None:
    """archive の row から fitness_pen / stage pass を取り出し cache 更新."""
    for g in population:
        row = archive.get_row_snapshot(lane_id, generation, g.name)
        if row is None:
            cache[g.name] = IndividualCacheEntry(
                generation=generation,
                fitness_pen=-math.inf,
                stage_a_pass=False,
                stage_b_pass=False,
                stage_c_pass=False,
            )
            continue
        fp_raw = row.get("fitness_pen")
        try:
            fp = float(fp_raw) if fp_raw is not None else -math.inf
        except (TypeError, ValueError):
            fp = -math.inf
        cache[g.name] = IndividualCacheEntry(
            generation=generation,
            fitness_pen=fp,
            stage_a_pass=bool(row.get("stage_a_pass", False)),
            stage_b_pass=bool(row.get("stage_b_pass", False)),
            stage_c_pass=bool(row.get("stage_c_pass", False)),
        )
```

### 変更後コード

```python
def _update_cache(
    cache: dict[str, IndividualCacheEntry],
    population: Sequence[Genome],
    archive: GenomeArchive,
    lane_id: str,
    generation: int,
) -> None:
    """archive の row から fitness_pen / stage pass / feasible_trade を取り出し cache 更新.

    feasible_trade は archive canonical `trade_count >= 1` から導出する。
    意味は「その row の canonical trade_count が 1 以上」(ever-traded ではない)。
    archive row 不在の個体は feasible_trade=False (取引未到達)。
    """
    for g in population:
        row = archive.get_row_snapshot(lane_id, generation, g.name)
        if row is None:
            cache[g.name] = IndividualCacheEntry(
                generation=generation,
                fitness_pen=-math.inf,
                stage_a_pass=False,
                stage_b_pass=False,
                stage_c_pass=False,
                feasible_trade=False,
            )
            continue
        fp_raw = row.get("fitness_pen")
        try:
            fp = float(fp_raw) if fp_raw is not None else -math.inf
        except (TypeError, ValueError):
            fp = -math.inf
        # NaN / +inf を -inf に正規化 (selection 比較の決定性確保)
        if not math.isfinite(fp):
            fp = -math.inf
        # canonical trade_count から feasible_trade を導出
        tc_raw = row.get("trade_count")
        try:
            tc = int(tc_raw) if tc_raw is not None else 0
        except (TypeError, ValueError):
            tc = 0
        cache[g.name] = IndividualCacheEntry(
            generation=generation,
            fitness_pen=fp,
            stage_a_pass=bool(row.get("stage_a_pass", False)),
            stage_b_pass=bool(row.get("stage_b_pass", False)),
            stage_c_pass=bool(row.get("stage_c_pass", False)),
            feasible_trade=(tc >= 1),
        )
```

### ルックアヘッドバイアスチェック
- [x] N/A (primitive 変更ではない)

### パフォーマンスチェック
- [x] N/A (selection cache の 1 entry あたり bool 1 つ追加のみ)

### テスト計画 (テストファースト)

#### 新規回帰テスト (`tests/scripts/test_alpha_factory_run_ga.py`)

```python
def test_selection_score_prefers_traded_over_no_trade_when_all_stage_fail() -> None:
    """Stage 全不通過の個体間で、取引した負 Sharpe が無取引 fitness=0 より上位."""
    no_trade = IndividualCacheEntry(
        generation=0, fitness_pen=0.0,
        stage_a_pass=False, stage_b_pass=False, stage_c_pass=False,
        feasible_trade=False,
    )
    traded_loss = IndividualCacheEntry(
        generation=0, fitness_pen=-5.0,
        stage_a_pass=False, stage_b_pass=False, stage_c_pass=False,
        feasible_trade=True,
    )
    assert traded_loss.selection_score > no_trade.selection_score


def test_selection_score_stage_b_pass_no_trade_beats_stage_a_pass_traded() -> None:
    """Stage tier が feasible_trade / fitness_pen に優先する。

    Stage B pass + feasible_trade=False (無取引) > Stage A pass + feasible_trade=True
    である (Stage 通過数が辞書式で先頭に来るため)。
    """
    stage_b_no_trade = IndividualCacheEntry(
        generation=0, fitness_pen=0.0,
        stage_a_pass=True, stage_b_pass=True, stage_c_pass=False,
        feasible_trade=False,
    )
    stage_a_traded = IndividualCacheEntry(
        generation=0, fitness_pen=-5.0,
        stage_a_pass=True, stage_b_pass=False, stage_c_pass=False,
        feasible_trade=True,
    )
    assert stage_b_no_trade.selection_score > stage_a_traded.selection_score


def test_selection_score_stage_a_pass_dominates_no_stage_pass() -> None:
    """Stage A pass は feasible_trade / fitness_pen が下でも非通過個体より優先."""
    stage_a_traded = IndividualCacheEntry(
        generation=0, fitness_pen=-5.0,
        stage_a_pass=True, stage_b_pass=False, stage_c_pass=False,
        feasible_trade=True,
    )
    no_stage_traded_better = IndividualCacheEntry(
        generation=0, fitness_pen=10.0,
        stage_a_pass=False, stage_b_pass=False, stage_c_pass=False,
        feasible_trade=True,
    )
    assert stage_a_traded.selection_score > no_stage_traded_better.selection_score


def test_selection_score_within_feasible_orders_by_fitness_pen() -> None:
    """feasible_trade 同値の場合、fitness_pen で順序."""
    higher = IndividualCacheEntry(
        generation=0, fitness_pen=-3.0,
        stage_a_pass=False, stage_b_pass=False, stage_c_pass=False,
        feasible_trade=True,
    )
    lower = IndividualCacheEntry(
        generation=0, fitness_pen=-5.0,
        stage_a_pass=False, stage_b_pass=False, stage_c_pass=False,
        feasible_trade=True,
    )
    assert higher.selection_score > lower.selection_score


def test_selection_score_tuple_length_is_five() -> None:
    """selection_score が 5 要素 (C, B, A, feasible_trade, fitness_pen)."""
    e = IndividualCacheEntry(
        generation=0, fitness_pen=0.0,
        stage_a_pass=False, stage_b_pass=False, stage_c_pass=False,
        feasible_trade=False,
    )
    assert len(e.selection_score) == 5


def test_update_cache_derives_feasible_trade_from_archive_trade_count() -> None:
    """archive row.trade_count >= 1 → feasible_trade=True / 0 → False。

    GenomeArchive を実体生成し collect_stage_a で 2 個体 (取引あり / 取引なし)
    を入れ、`_update_cache` 経由で cache に反映される feasible_trade を検証。
    """
    archive = GenomeArchive(run_id="run_test", run_number=99)

    # 個体 g_traded: trade_count=5 (Stage A pass)
    g_traded = _make_genome("g_traded")
    sa_pass = StageResult(
        stage="A", passed=True,
        metrics={"payload": {
            "fitness_raw": 1.5, "fitness_pen": 1.4,
            "size_norm": 0.1, "alpha_a": 1.0, "threshold": 0.5,
            "trade_count": 5, "sharpe_raw": 1.5,
        }},
        reason_codes=(),
    )
    archive.collect_stage_a(
        g_traded, "tier1_EUR_JPY", 0, sa_pass, instrument="EUR_JPY",
    )

    # 個体 g_no_trade: trade_count=0 (Stage A fail = no_trades)
    g_no_trade = _make_genome("g_no_trade")
    sa_fail = StageResult(
        stage="A", passed=False,
        metrics={"payload": {
            "fitness_raw": None, "fitness_pen": None,
            "size_norm": 0.1, "alpha_a": 1.0, "threshold": 0.5,
            "trade_count": 0, "sharpe_raw": None,
        }},
        reason_codes=("no_trades",),
    )
    archive.collect_stage_a(
        g_no_trade, "tier1_EUR_JPY", 0, sa_fail, instrument="EUR_JPY",
    )

    cache: dict[str, IndividualCacheEntry] = {}
    _update_cache(cache, [g_traded, g_no_trade], archive, "tier1_EUR_JPY", 0)

    assert cache["g_traded"].feasible_trade is True
    assert cache["g_no_trade"].feasible_trade is False


def test_update_cache_missing_row_sets_feasible_false() -> None:
    """archive row 不在 → feasible_trade=False (取引未到達)."""
    archive = GenomeArchive(run_id="run_test_empty", run_number=99)
    g_unknown = _make_genome("g_unknown")
    cache: dict[str, IndividualCacheEntry] = {}
    _update_cache(cache, [g_unknown], archive, "tier1_EUR_JPY", 0)

    assert cache["g_unknown"].feasible_trade is False
    assert cache["g_unknown"].fitness_pen == -math.inf


def test_update_cache_normalizes_non_finite_fitness_pen() -> None:
    """fitness_pen が NaN / +inf の場合は -inf に正規化される。

    selection_score 比較における NaN 伝播を防ぐ防御的処理 (新規追加)。
    """
    archive = GenomeArchive(run_id="run_test_nan", run_number=99)
    g = _make_genome("g_nan")
    sa = StageResult(
        stage="A", passed=True,
        metrics={"payload": {
            "fitness_raw": float("nan"), "fitness_pen": float("nan"),
            "size_norm": 0.1, "alpha_a": 1.0, "threshold": 0.5,
            "trade_count": 5, "sharpe_raw": float("nan"),
        }},
        reason_codes=(),
    )
    archive.collect_stage_a(g, "tier1_EUR_JPY", 0, sa, instrument="EUR_JPY")

    cache: dict[str, IndividualCacheEntry] = {}
    _update_cache(cache, [g], archive, "tier1_EUR_JPY", 0)

    # NaN は -inf に正規化 (selection 比較の決定性確保)
    assert cache["g_nan"].fitness_pen == -math.inf


def test_update_cache_normalizes_positive_infinity_fitness_pen() -> None:
    """fitness_pen が +inf の場合も -inf に正規化される。"""
    archive = GenomeArchive(run_id="run_test_inf", run_number=99)
    g = _make_genome("g_inf")
    sa = StageResult(
        stage="A", passed=True,
        metrics={"payload": {
            "fitness_raw": float("inf"), "fitness_pen": float("inf"),
            "size_norm": 0.1, "alpha_a": 1.0, "threshold": 0.5,
            "trade_count": 5, "sharpe_raw": float("inf"),
        }},
        reason_codes=(),
    )
    archive.collect_stage_a(g, "tier1_EUR_JPY", 0, sa, instrument="EUR_JPY")

    cache: dict[str, IndividualCacheEntry] = {}
    _update_cache(cache, [g], archive, "tier1_EUR_JPY", 0)

    assert cache["g_inf"].fitness_pen == -math.inf
```

**`_make_genome` ヘルパー**: 既存テストで使われている genome 構築ヘルパーを再利用。なければ test 内で minimal Genome を構築 (1 clause / 1 directional)。

#### 既存テスト更新

```python
# tests/scripts/test_alpha_factory_run_ga.py L394-395
# 変更前
assert len(summary["best"]["selection_score"]) == 4

# 変更後
assert len(summary["best"]["selection_score"]) == 5
```

### リスク

- **GA collision**: 同時並行で `run_ga.py` を改修する別 TODO があれば衝突。現状無し
- **selection 順序の変化が既存 winner snapshot に影響**: スナップショット resume/restore 機能 (`zenigame-fx-snapshot` skill) で過去 winner と現 winner の比較対象が変わる可能性 → 過去 archive を読み戻す際は `feasible_trade=False` (新 field 不在ゆえ default) として扱う仕様で互換性確保

---

## 施策 4: summary `selection_score` 出力 5 要素化

### 変更箇所
- ファイル: `scripts/alpha_factory/run_ga.py` L653-658

### 現行コード

```python
"selection_score": [
    int(best_entry.stage_c_pass),
    int(best_entry.stage_b_pass),
    int(best_entry.stage_a_pass),
    float(best_fitness_val),
],
```

### 変更後コード

```python
"selection_score": [
    int(best_entry.stage_c_pass),
    int(best_entry.stage_b_pass),
    int(best_entry.stage_a_pass),
    int(best_entry.feasible_trade),
    float(best_fitness_val),
],
```

### テスト計画
- 既存テスト `test_alpha_factory_run_ga.py:L395` を `len == 5` に更新済 (施策 5)

### リスク
- 下流の summary 解析ツール (analyze-run / generate-run-report) が `selection_score` 4 要素を hard-code している場合に壊れる → 全箇所 grep で確認 (該当なら修正)

---

## 施策 7: docs / report 説明文更新

### 変更箇所

#### `docs/alpha_factory/clause-architecture.md`

現状本ファイルには `selection_score` の lex tuple 記述が**無い** (grep 確認済)。
本 TODO で「best 選抜の lex tuple 記述」セクションを **新規追加** する。
追加先: §「Stage gate / fitness」付近 (現状 fitness_pen の記述がある L201, L358 周辺) に新規 H3 追加:

```markdown
### Best 選抜の lex tuple

GA が世代ごとに「best 個体」を決めるとき、archive 由来の `IndividualCacheEntry`
を以下の辞書式 5 要素タプルで比較する:

`(stage_c_pass, stage_b_pass, stage_a_pass, feasible_trade, fitness_pen)`

- `stage_*_pass` (bool→int): Stage 通過数で粗ソート
- `feasible_trade` (bool→int): canonical `trade_count >= 1`。Stage 全不通過の個体間で
  「無取引 (`fitness_pen=0` だが取引していない)」を「取引したが負 Sharpe」より
  下位化するための tie-break tier
- `fitness_pen` (float): 同 tier 内で fitness 順

archive canonical (`fitness_pen` / `total_pnl`) は不変。`feasible_trade` は selection
cache 上の派生フィールドで archive には書き込まれない。
```

#### `scripts/alpha_factory/generate_run_report.py` L452-454

```python
# 変更前
"> Best とは別物です。`fitness_pen` 単独降順。"
"Best は (stage_c_pass, stage_b_pass, stage_a_pass, fitness_pen) の辞書式。"

# 変更後
"> Best とは別物です。`fitness_pen` 単独降順。"
"Best は (stage_c_pass, stage_b_pass, stage_a_pass, feasible_trade, fitness_pen) の辞書式。"
```

### テスト計画

- **新規テスト** `tests/scripts/test_generate_run_report.py`:
  - `test_best_legend_mentions_feasible_trade_in_lex_tuple()`: 生成 run report の
    archive Top-5 の凡例文字列が新 5 要素 tuple 表記を含むことを確認
  - 既存 generate_run_report.py のテストファイルが無いため、本 TODO で新規作成
- ドキュメント (`clause-architecture.md`) は文章のため自動テスト対象外だが、
  追加記述が他セクションと矛盾しないことを目視レビュー

---

## 実装モード

| 項目 | 内容 |
|------|------|
| 推奨モード | incremental |
| 判断根拠 | 単一 production ファイル (`run_ga.py`) の小範囲変更。archive / stage_gate / calibrate-gate に影響なし。テスト追加でカバー |
| 競合リスク | 同時並行で `run_ga.py` を改修する別 TODO があれば衝突。現状無し |
| 想定実装時間 | 短〜中 (production ~50 LOC + テスト ~150 LOC) |

---

## ルックアヘッドバイアス再点検

本 TODO は primitive 変更ではないため対象外。selection cache の lex tuple のみを変更する。

## メモリ制約

`IndividualCacheEntry` に bool 1 つ追加。1 個体当たり ~1 byte 増。120 個体で ~120 byte 増 → 影響なし

## 並行計算経路の確認 (C2)

`selection_score` を読む箇所を grep で確認:
- `scripts/alpha_factory/run_ga.py:370` `max(sample, key=lambda g: cache[g.name].selection_score)` — selection (tournament)
- `scripts/alpha_factory/run_ga.py:384` 同上 — selection (best)
- `scripts/alpha_factory/run_ga.py:475` `_select_best` — final best
- `scripts/alpha_factory/run_ga.py:653` summary 出力

すべて `IndividualCacheEntry.selection_score` を経由しており、property 経由なので tuple 長変更は透過。
summary 出力箇所 (L653) のみ手動で 5 要素 list を構築しているため、ここは直接修正が必要 (施策 4)。

## 全体判定基準

- 本 TODO の APPROVED 条件:
  - `tests/scripts/test_alpha_factory_run_ga.py` の全テスト pass
  - `uv run mypy src/ scripts/` / `uv run ruff check src/ scripts/ tests/` 通過
  - smoke run (population_size=20, generations=2) で archive parquet 生成、summary `selection_score` が 5 要素

- Run 10 で観測する成功条件 (本 TODO スコープ外):
  - `feasible_trade=True` 個体が母集団に存在する run で best が `trade_count > 0`
  - `tc=0` 比率の低下 (75% → < 50% smoke target)
