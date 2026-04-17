# Phase 4g 詳細設計 — DSL ゲノムの最小 GA

**作成**: 2026-04-18 02:00 JST
**前提**: Phase 4f DSL 済
**状態**: DRAFT

---

## 1. 目的

DSL で表現した戦略ゲノムを、**遺伝的アルゴリズムで自動探索**する最小ループを構築する。MVP は単目的（PnL）。NSGA-II 多目的や LLM ガイドは Phase 4h 以降。

---

## 2. スコープ

**含む**:
- ランダムゲノム生成（grammar-based、深さ制限）
- 遺伝的操作: 式単位の crossover（`entry_long` などを親間で交換）、expression 単位の mutation（新しいランダム式へ置換 + 定数摂動 + 窓幅摂動）
- Tournament selection（サイズ可変）
- 単目的適応度（total_pnl or sharpe、選択可）
- シンプル GA ループ: Elitism（ベスト K を次世代に持ち越し）
- 実行中断に強い構造（Ctrl-C → 現在までの best を返す）
- ランダム初期化の seed 固定（再現性）
- テストとランナー CLI

**含まない（Phase 4h 以降）**:
- NSGA-II / 多目的最適化
- ゲノムアーカイブ（Parquet）
- LLM-Guided Mutation
- Stage gate（A/B/C 評価）
- MetaArchive / FailureMemory
- 交叉時のサブツリー互換性チェック（今回は式単位の全体交換のみ）

---

## 3. ランダム式生成

### 3.1 使うプリミティブ

- `PRICE_VARS = ["close", "open", "high", "low"]`
- `MULTIPLIER_CONSTS = [0.25, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0]`
- `INDICATOR_NAMES = ["sma", "ema", "stddev", "rsi"]`
- `WINDOWS = [5, 10, 14, 20, 30, 50]`

### 3.2 文法（簡易）

```
cond  := Compare(op, num, num) | Logical(and/or, (cond, cond)) | Logical(not, (cond,))
num   := Var(price) | Const(multiplier) | Indicator(name, win, num) | BinOp(op, num, num)
```

深さ上限で必ず終端に収束させる。

### 3.3 `random_genome(rng, max_depth, units, name)`

4 つの `cond` を生成して Genome を返す。

---

## 4. 遺伝的操作

### 4.1 Crossover（式単位）

2 親から、4 つの式（entry_long/short, exit_long/short）のうちランダムな 1 つを選び入れ替えて 2 子を生成。

### 4.2 Mutation（式単位）

確率 `mutation_rate` で:
- (a) 4 式のうち 1 つを**完全に新規ランダム式に置換**
- (b) ランダム `Const` を ±20% 摂動
- (c) ランダム `Indicator.window` を WINDOWS 内で隣接に変更

(a)/(b)/(c) のどれを選ぶかは一様ランダム。(b)/(c) は対象が存在しないと (a) にフォールバック。

---

## 5. 選択・適応度

- Tournament selection: `tournament_size` 個をランダム抽出して最良を返す
- 適応度: `total_pnl`（デフォルト）または `sharpe`。Sharpe が None の個体は最低評価

### 5.1 失敗個体の扱い

DslStrategy の `on_bar` で例外（ゼロ除算は evaluate 側で 0 を返すので発生しないが、念のため）が発生した場合: fitness = `Decimal("-1e18")`。試行中は warning ログ。

---

## 6. GA ループ

```
rng = Random(seed)
population = [random_genome(rng, ...) for _ in range(pop_size)]
fitnesses = [evaluate(g) for g in population]
for gen in 1..generations:
    elites = top_k(population, fitnesses, k=elite_k)
    new_pop = list(elites)
    while len(new_pop) < pop_size:
        p1 = tournament(population, fitnesses, rng, k=tour_k)
        p2 = tournament(population, fitnesses, rng, k=tour_k)
        if rng.random() < crossover_rate:
            c1, c2 = crossover(p1, p2, rng)
        else:
            c1, c2 = p1, p2
        c1 = mutate(c1, rng, mutation_rate)
        c2 = mutate(c2, rng, mutation_rate)
        new_pop.append(c1)
        if len(new_pop) < pop_size:
            new_pop.append(c2)
    population = new_pop
    fitnesses = [evaluate(g) for g in population]
    log gen best
return best_overall
```

並列化は後回し（MVP は sequential）。

---

## 7. データモデル

```python
@dataclass(frozen=True)
class GaConfig:
    population_size: int = 50
    generations: int = 20
    crossover_rate: float = 0.7
    mutation_rate: float = 0.3
    tournament_size: int = 3
    elite_count: int = 2
    max_depth: int = 4
    units: int = 10000
    fitness_metric: str = "total_pnl"   # or "sharpe"
    seed: int | None = None

@dataclass
class Individual:
    genome: Genome
    fitness: Decimal

@dataclass
class GaResult:
    config: GaConfig
    best: Individual
    history: list[tuple[int, Decimal]]   # (generation, best_fitness)
    final_population: list[Individual]
```

---

## 8. ディレクトリ構成追加

```
src/ga/
├── __init__.py
├── random_gen.py         # ランダム式/ゲノム生成
├── operators.py          # crossover / mutation
├── fitness.py            # backtest 実行 & 指標抽出
├── runner.py             # GaConfig, run_ga
└── archive.py            # Phase 4h 用プレースホルダ（将来の parquet 保存）
tests/ga/
├── __init__.py
├── test_random_gen.py
├── test_operators.py
└── test_runner.py
scripts/
└── ga_run.py             # CLI
reports/ga-runs/          # 生成物（.gitignore）
```

---

## 9. CLI

```
uv run python scripts/ga_run.py \
    --instrument USD_JPY \
    --from 2025-11-01 --to 2026-04-01 \
    --initial-cash 1000000 \
    --leverage 10 \
    --population 30 \
    --generations 10 \
    --seed 42 \
    --fitness-metric total_pnl
```

ベストゲノムは `reports/ga-runs/ga-YYYYMMDD-HHMMSS/best_genome.json` に保存、サマリは `summary.md`。

---

## 10. テスト戦略

- 随時ランダム生成が型整合している（生成 → evaluate で例外なし）
- Crossover は親のどちらか一方由来の式で構成される
- Mutation で Genome が実際に変化する（少なくとも 1 つの式が変わる）
- GA ループが適応度を改善する傾向を持つ（合成データでデモ）

---

## 11. 完了判定

1. `uv run pytest` green
2. `uv run ruff check` green
3. CLI 実行でレポートが生成される（bars が DB 前提）

---

## 12. 先送り

- NSGA-II 多目的
- ゲノムアーカイブ永続化（Parquet）
- LLM ガイド変異
- warm-start（前 Run の best を seed 集団に投入）
- 並列評価（ProcessPool）
- Stage gate 評価
