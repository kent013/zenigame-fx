# GA 並列ワーカー指定機能 — 概念設計 (v2)

- 作成: 2026-04-27 11:14 JST
- 更新: 2026-04-27 11:40 JST (Round 1 Codex review 反映)
- 更新: 2026-04-27 12:00 JST (Round 2 Codex review 反映 — initializer 一括 broadcast / 例外決定表 / pool 寿命整理 / RSS 運用ガード)
- 対象: zenigame-fx Alpha Factory (`scripts/alpha_factory/run_ga.py` + `src/alpha_factory/swim_lane.py`)
- 参考: zenigame `src/trading/alpha_factory/ga/parallel_eval.py` / `nsga2/config.py:max_workers`

## 0. 前提とその検証状態 (C4)

| 前提 | ステータス | 根拠 / 補足 |
|---|---|---|
| 現行 GA 評価は `LaneManager._run_tier1_generation` の直列ループで実施 | Verified | swim_lane.py:458-625 を確認済 |
| GA RNG (`random.Random(cfg.ga.seed)`) は main process のみで使用 | Verified | run_ga.py:964 で生成、worker には渡さない |
| `archive` (`GenomeArchive`) は mutable / file write を持つ | Verified | src/alpha_factory/archive.py:flush 経路 |
| `diagnostics` (`DiagnosticsCollector`) は mutable | Verified | src/alpha_factory/diagnostics_collector.py |
| Phase 2 では `graduation.pair_bars` が空で cross-pair は常時 skip | Verified | run_ga.py:944-948 で空 dict 注入 |
| `StageResult` には `wall_time_seconds` が含まれる | Verified | swim_lane.py:534 / stage_gate.py の payload で実時間値が入る |
| `summary.json` は generated_at / wall_time_seconds 等の非決定 field を含む | Verified | run_ga.py:_write_reports 経路 |
| `BacktestConfig` / `StageGateConfig` / `CrossPairConfig` / `RegistryEvaluator` は pickle 可 | Unverified (実装時に確認) | `RegistryEvaluator.aux_pair_bars` に閉路がないかは詳細設計で確認 |
| primitive registry は `ensure_registered()` で冪等再構築可能 | Verified | src/alpha_factory/primitives/_registry.py:118 |
| Parquet writer (pyarrow) の出力 byte 列がプロセス起動順に依存しない | Unverified / 不採用 | bit 一致は要件から外す（後述§4.0） |
| `_bars_cache` は process-local LRU で worker safe | Verified | src/alpha_factory/primitives/_bars_cache.py:23-26 のコメント |
| 24GB マシン × 6 worker × 1 worker 3GB は **GA process の worker 数上限** を意味する | Verified (本ドキュメント定義) | autopilot 等で同時走行する別 process は別予算 |

## 1. 目的 / Why

zenigame-fx の GA RUN は現状 1 process 1 core でシーケンシャル評価しているため、
- 1 世代 = `population_size` 個の Stage A + 通過個体の Stage B + さらに通過個体の Stage C を直列実行
- core 数を増やしても wall-time が短縮されない

zenigame 側は `ga.max_workers` を YAML/CLI で指定し、`multiprocessing.Pool` で個体評価を並列化する設計
（[zenigame:nsga2/config.py:104](../../../zenigame/src/trading/alpha_factory/ga/nsga2/config.py#L104)、
[zenigame:ga/parallel_eval.py](../../../zenigame/src/trading/alpha_factory/ga/parallel_eval.py)）が既に運用されている。

**仮説**: zenigame-fx でも同等の `max_workers` を導入すれば、4-8 core マシンで RUN wall-time が短縮され、改善サイクル (`improve-cycle`) の回転速度を上げられる。
(具体倍率は性能観測フェーズで実測 — Round 1 指摘により定量予測は事前 claim から外す)

**位置付け**: 本機能は **副次目標 (運用効率改善)** であり、live_criteria 達成 (= North Star) を直接前進させるものではない。
ただし以下の経路で間接的に寄与する:
- 1 RUN の wall-time 短縮 → 改善サイクルの試行回数増 → live_criteria 探索空間の被覆率向上
- 並列化の前提として「評価関数の純粋性」を強制 → 既存の隠れた副作用を可視化

**成功条件 (再定義)**:
1. `--max-workers N` (alias `--workers N`) または `ga.max_workers: N` で指定した process 数で評価が並列実行される
2. **Selection determinism (Level 1 / 必須)**: `max_workers=1` と `max_workers=N` で、同一 seed・同一 config 下において:
   - `cache[name].fitness_pen` (genome 単位の評価値) が完全一致
   - `_select_best` が返す `best_name` が一致
   - `live_criteria` 判定 (`live_criteria_passed: bool`) が一致
3. **Row-order determinism (Level 2 / 必須)**: archive Parquet を `(lane_id, generation, genome_name)` でソートしたとき、評価値 column が完全一致
4. **Artifact bit equivalence (Level 3 / 非保証)**: `summary.json` / `archive.parquet` の生 byte 列の一致は **保証しない** (timestamp / wall-time / Parquet writer metadata 等の非決定 field を含むため)
5. `max_workers=1` 時の **動作経路は現行と同一** (regression: 既存テストがそのまま pass)

## 2. スコープ / Out of scope

### in scope
- `LaneManager._run_tier1_generation` 内 per-genome Stage A/B/C 評価ループの並列化
- `ga.max_workers` config 追加 (YAML + CLI override)
- `run_ga.py` への `--max-workers N` flag (canonical) と `--workers N` (alias)
- 並列モード/シーケンシャルモードの分岐は `LaneManager` 内に閉じる
- worker module は将来の差し替え可能性を見越し、**task transport 層** (pool 起動・broadcast・map) と **evaluation 層** (Stage A/B/C を呼ぶ純粋関数) を別オブジェクトに分離

### out of scope (別タスク)
- zenigame の SharedBarStore (mmap) や HistStats 事前計算 — 初版は pickle broadcast で十分かを評価。差し替え可能な境界 (§4.6) を確保する形で将来導入余地を残す
- `run_alpha_sieve.py` / `compare_batch_runs.py` の並列化 — GA RUN とは bottleneck が異なる
- Graduation lane / multi-pair の並列化 — Phase 2 では Tier1 single-instrument のみ active
- `improve-cycle` / `autopilot` skill の default max_workers 自動調整 — 既定値は **1 で固定**、明示指定時のみ並列化

## 3. 現状把握 (Fact)

### 3.1 評価フローの構造
[run_ga.py:970-1031](../../scripts/alpha_factory/run_ga.py#L970-L1031) の世代ループ:
1. main process が `random_genome` / `_breed_next_gen` で `population` を生成
2. `lane_manager.run_generation(lane_id)` を呼ぶ
3. [swim_lane.py:490-616](../../src/alpha_factory/swim_lane.py#L490-L616) で `for genome in lane.population:` を直列実行
   - Stage A → 通過なら Stage B → 通過なら Stage C (cross-pair shadow 含む)
   - 各 stage 後に `archive.collect_stage_*` と `diagnostics.record_stage_*` を呼んで副作用蓄積
4. 戻り値で `(stage_a_pass, stage_b_pass, stage_c_pass, graduation_count)` を集計

### 3.2 worker に渡せる/渡せないものの分類
| 種別 | 中身 | pickle 可否 | 備考 |
|---|---|---|---|
| `lane.bars_60d / bars_18m / bars_holdout` | `list[PriceBar]` | ◯ | 世代間で不変、broadcast 1 回で十分 |
| `lane.meta` | `InstrumentMeta` (frozen dc) | ◯ | |
| `bt_cfg` (`BacktestConfig`) | frozen dataclass | ◯ | factory closure でなく値そのものを送る |
| `stage_gate_config` / `cross_pair_config` | frozen dc | ◯ | |
| `primitive_evaluator` (`RegistryEvaluator`) | state-less + aux dict | ◯ (要詳細設計確認) | aux 全て pickle 可かは詳細設計でテスト |
| `archive` (`GenomeArchive`) | mutable, ファイル書き出し | ✗ | **main process 専用** |
| `diagnostics` (`DiagnosticsCollector`) | mutable | ✗ | **main process 専用** |
| primitive registry (`_PRIMITIVES`) | module-global dict | ✗ (要再構築) | worker init で `ensure_registered()` を呼ぶ |
| `_bars_cache._CACHE` | module-global LRU | — | worker 内 process-local で OK (世代内 hit 期待) |

### 3.3 決定性の所在
- GA RNG (`random.Random(cfg.ga.seed)`) は main loop の random_genome / breed のみ使用 → worker 数に非依存
- Stage A/B/C 評価は genome 単位で **数値的に純粋** (副作用は archive/diagnostics への書き出しのみ。`StageResult.metrics["wall_time_seconds"]` 等の **非数値 metadata は wall time に依存** するため Level 3 (bit 一致) では除外する)
- 結果の collect 順序は archive Parquet の行順を決めるが、これを **population 順 (= genome.name の生成順) に固定** すれば Level 2 (row-order) は worker 完了順に左右されない

## 4. 設計方針 / How

### 4.0 決定論性の三段階定義 (Round 1 反映)
| Level | 内容 | 本機能での扱い |
|---|---|---|
| L1 selection determinism | 数値評価 (`fitness_pen` / `live_criteria` 判定 / `best_name`) が seed 固定下で worker 数に依存しない | **必須保証** / 同値性テストで verify |
| L2 row-order determinism | archive Parquet を `(lane_id, generation, genome_name)` でソートしたとき、評価値 column が完全一致 | **必須保証** / 同値性テストで verify |
| L3 artifact bit equivalence | `summary.json` / `archive.parquet` の生 byte 列が一致 | **保証しない** / 除外 field を§4.7 に明記 |

### 4.1 副作用と評価の分離 (核となる設計判断)
worker は **数値評価のみ** を行う純粋関数。**副作用 (archive / diagnostics 書き込み) は main process** が一手に持つ:

```python
@dataclass(frozen=True)
class GenomeStageResult:
    genome_name: str
    stage_a: StageResult
    stage_b: StageResult | None      # Stage A fail なら None
    stage_c: StageResult | None      # Stage B fail なら None
    cross_pair: CrossPairResult | None
    error: GenomeEvalError | None    # worker 内例外時のみ
```

```python
@dataclass(frozen=True)
class GenomeEvalError:
    """worker 例外を deterministic な構造体に正規化する。
    生 traceback は logger 専用。artifact には含めない。"""
    stage: Literal["A", "B", "C"]
    error_code: str        # 決定表 (§4.6.1) で定義された fixed enum
    fixed_message: str     # 決定表に対応する固定文 (例外文面の自由文取り込みは禁止)
```

main process が evaluator pool に population を投げ → 結果 list を **population 順に並べ直して** `archive.collect_*` / `diagnostics.record_*` / graduation 判定を行う。

これにより:
- archive / diagnostics は worker から触らない
- L2 (row-order) は worker 完了順に依存しない
- 既存の `_run_tier1_generation` の **副作用部分のロジックを変えない** (リファクタが小さい)

### 4.2 並列実行レイヤの構造 — 二層分離 (Round 1 反映)

```
┌──────────────────────────────────────────────────┐
│  evaluation 層: parallel_eval.evaluate_genome    │
│  - 純粋関数 (genome + ctx → GenomeStageResult)    │
│  - 直列モード/並列モード共通、副作用なし            │
│  - 単体テスト容易                                 │
├──────────────────────────────────────────────────┤
│  task transport 層: ParallelEvaluator             │
│  - multiprocessing.Pool 起動・寿命管理             │
│  - lane context broadcast                         │
│  - main↔worker 間 task 投入と結果回収              │
│  - 将来 SharedBarStore / HistStats 導入時に差し替え│
└──────────────────────────────────────────────────┘
```

**API 境界**:
- evaluation 層 = `evaluate_genome(genome, lane_ctx, gate_cfg, cp_cfg, prim_evaluator) -> GenomeStageResult`
- task transport 層 = `ParallelEvaluator.evaluate_population(lane_id, generation, population) -> list[GenomeStageResult]` (population 順)

`LaneManager` は task transport 層を 1 個保持し、`max_workers=1` でも常に同じ API で呼ぶ (`_SequentialEvaluator` で in-process 実行)。

### 4.3 並列モードの context 配布 — initializer 一括 broadcast (Round 2 反映)

zenigame と同じ `multiprocessing.Pool` (spawn context) を採用。`ProcessPoolExecutor` は不採用。

**Round 2 指摘への対応**: `pool.map([args]*N)` は work-stealing のため全 worker への一意割当を保証しない (特定 worker が旧 context のまま残る経路あり)。
これを避けるため、**lane context は initializer 引数として 1 度だけ渡し、worker module-global は immutable** にする。

zenigame-fx Phase 2 の構造的前提:
- single-pair / single-lane (Tier1 1 個 + Graduation 空) で RUN を完結
- `bars_60d / bars_18m / bars_holdout / meta` は dataset から決定論的に算出され、RUN 中不変
- `cp_inputs` も RUN 中不変 (Phase 2 では常に None)

→ **lane context は RUN 開始時に確定** しているため、Pool initializer に全部渡せば mutable update 自体が不要。

```python
class ParallelEvaluator:
    def __init__(
        self,
        max_workers: int,
        stage_gate_cfg: StageGateConfig,
        cross_pair_cfg: CrossPairConfig,
        prim_evaluator: RegistryEvaluator,
        lane_contexts: Mapping[str, LaneEvalContext],  # lane_id → ctx (RUN 中 immutable)
    ):
        if max_workers <= 1:
            self._pool = None
            self._lane_contexts = lane_contexts  # in-process direct
            return
        ctx = multiprocessing.get_context("spawn")
        self._pool = ctx.Pool(
            processes=max_workers,
            initializer=_init_worker,
            initargs=(stage_gate_cfg, cross_pair_cfg, prim_evaluator, dict(lane_contexts)),
        )

    def evaluate_population(
        self, lane_id: str, generation: int, population: list[Genome]
    ) -> list[GenomeStageResult]:
        args = [(lane_id, generation, g) for g in population]
        if self._pool is None:
            return [_evaluate_genome_inproc(a, ...) for a in args]
        results = self._pool.map(_eval_genome_worker, args)
        return results  # pool.map は入力順保持 → population 順

# worker module
_STAGE_GATE_CFG: StageGateConfig | None = None
_CROSS_PAIR_CFG: CrossPairConfig | None = None
_PRIM_EVALUATOR: RegistryEvaluator | None = None
_LANE_CONTEXTS: dict[str, LaneEvalContext] = {}

def _init_worker(stage_gate_cfg, cross_pair_cfg, prim_evaluator, lane_contexts):
    global _STAGE_GATE_CFG, _CROSS_PAIR_CFG, _PRIM_EVALUATOR, _LANE_CONTEXTS
    ensure_registered()
    _STAGE_GATE_CFG = stage_gate_cfg
    _CROSS_PAIR_CFG = cross_pair_cfg
    _PRIM_EVALUATOR = prim_evaluator
    _LANE_CONTEXTS = lane_contexts  # spawn 経由で deep copy 済 → immutable 扱い

def _eval_genome_worker(args):
    lane_id, generation, genome = args
    ctx = _LANE_CONTEXTS[lane_id]
    return evaluate_genome(genome, ctx, _STAGE_GATE_CFG, _CROSS_PAIR_CFG, _PRIM_EVALUATOR)
```

**設計上の制約 (明文化)**:
- `lane_contexts` は `ParallelEvaluator.__init__` で確定し、Pool 寿命中は変更不可 (`mutable update API は提供しない`)
- 将来 multi-lane / 動的 lane 追加が必要になったら、Pool を作り直す (= LaneManager を再構築)。これは別 TODO のスコープ
- これにより worker 間の context 不整合経路を構造的に排除

### 4.3.1 LaneEvalContext

```python
@dataclass(frozen=True)
class LaneEvalContext:
    """RUN 中 immutable な lane 評価用コンテキスト。
    Pool initializer 経由で worker に配布される。"""
    lane_id: str
    bars_a: tuple[PriceBar, ...]    # tuple 化で frozen 保証
    bars_b: tuple[PriceBar, ...]
    bars_holdout: tuple[PriceBar, ...]
    meta: InstrumentMeta
    bt_cfg: BacktestConfig
    cp_inputs: CrossPairInputs | None  # Phase 2 では常に None
```

### 4.4 cross-pair shadow 引数
`StageCRunCrossPairEvaluator` は `(primitive_evaluator, cross_pair_config)` から組み立てる stateless adapter。worker 側 `_eval_genome_worker` 内で都度生成する。`cp_inputs` (target_pair / pair_bars_map / meta_map) は `set_lane_context` で lane と一緒に broadcast。

**Phase 2 では `graduation.pair_bars` が空のため `cp_inputs=None` で skip される** — Stage C 内で `cross_pair_skipped` reason が記録される現行と同じ挙動 (詳細設計で fixture テスト)。

cross-pair adapter 内部の純粋性 (logger 副作用 / cache の有無) は詳細設計で grep verify。

### 4.5 設定の追加

YAML:
```yaml
ga:
  population_size: 40
  generations: 15
  ...
  # 並列ワーカー数 (1 = シーケンシャル, 2 以上で multiprocessing.Pool)
  # @why: GA 評価の wall-time 短縮 (副次目標)。L1 selection / L2 row-order の
  #       決定論性を保証 (L3 bit equivalence は非保証)。
  # @default: 1 (CI / local 既定)。autopilot/improve-cycle は既定値を変更しない。
  # @upper_bound: 物理コア数 / 24GB ÷ 1worker_3GB の min。
  max_workers: 1
```

CLI:
```
--max-workers N    # canonical
--workers N        # alias (zenigame との表記互換 / 短縮)
```

`config.py` 側は `GAConfig.max_workers: int = 1` を追加。validation: `>= 1`。

### 4.6 fallback / failure handling
- worker 内例外 → `GenomeEvalError(stage, error_code, fixed_message)` に正規化して `GenomeStageResult.error` に格納。生 traceback は worker 側 logger に WARNING で出力 (artifact には含めない → L1/L2 決定論性を保つ)
- main process は `error` が non-None の `GenomeStageResult` を fail-closed StageResult (passed=False, reason_codes=("worker_error",)) に変換して archive に collect
- `max_workers > os.cpu_count()` → main process で起動前に warning ログ + 続行
- pool 起動失敗 → `RuntimeError` で fail-fast (silent fallback はしない)
- pool 寿命 (Round 2 反映):
  - **正常終了**: `LaneManager.close()` (= context manager `__exit__`) で `pool.close()` + `pool.join()` (graceful shutdown、既に dispatch 済 task の完了を待つ)
  - **異常終了 (例外伝播時)**: `pool.terminate()` + `pool.join()` (即時停止)
  - `__del__` には依存しない (GC タイミング非決定なので diagnostics flush と競合しうる)

### 4.6.1 例外正規化決定表 (Round 2 反映)

worker 内で raise される例外は以下の決定表に従って正規化する。**自由文の取り込みは禁止** (例外 instance の `str(e)` を `fixed_message` に流すのは NG):

| 例外型 | error_code | fixed_message | 対象 stage |
|---|---|---|---|
| `numpy.linalg.LinAlgError` | `BACKTEST_LINALG_ERROR` | "linalg numerical error" | A/B/C |
| `RuntimeError` (msg に "primitive" 含む) | `PRIMITIVE_LOOKUP_FAIL` | "primitive registry lookup failed" | A/B/C |
| `ValueError` (msg に "stage_b" / "wf" 含む) | `STAGE_B_FOLD_INVALID` | "walk-forward fold invalid" | B |
| `MemoryError` | `WORKER_OOM` | "worker out of memory" | A/B/C |
| `KeyboardInterrupt` / `SystemExit` | (re-raise; 正規化しない) | — | — |
| その他 `Exception` | `WORKER_UNCLASSIFIED` | "unclassified worker exception" | A/B/C |

このマッピングは `parallel_eval._classify_exception(exc, stage)` に実装する。
**型ベース判定を優先し、文字列 substring 判定は最終フォールバック** (Round 3 Warning 反映)。
将来は stage 側から専用例外型 (`StageBFoldInvalidError` 等) を送出し、文字列判定を段階的に排除 (別 TODO)。
分類条件は将来変更しうるため、テストで既知パターンを pin する。

### 4.6.2 運用ルール (Round 3 Suggestion 反映)
- `run_ga.py main()` では `ParallelEvaluator` を必ず `with` 文で利用する (close 漏れ防止)
- `LaneEvalContext` 生成時に `bars_*` を tuple 化 (リストの後段変更を構造的に防ぐ)
- `lane_contexts` Mapping は `types.MappingProxyType` で wrap して `__init__` に渡す

### 4.7 L3 (bit equivalence) 非保証の根拠 — 除外 field 一覧
以下は worker 数に依存して変動するため bit 一致を要求しない:
- `summary.json.generated_at` / `summary.json.run_id` (timestamp ベース)
- `summary.json.per_generation[*].wall_time_seconds`
- `summary.json.best.metrics.wall_time_seconds`
- `archive.parquet` の Parquet writer metadata (created_by / pyarrow version / row group ordering 等は writer 都合で揺れる可能性)
- `StageResult.metrics["wall_time_seconds"]` (各 stage 評価の実時間)
- `diagnostics.parquet` の logger 由来 timestamp 系 column

**L1/L2 で守るのは数値評価 column** (`fitness`, `fitness_pen`, `sharpe`, `total_pnl`, `max_drawdown`, `trade_count`, `live_criteria_passed`, `stage_a_passed`, `stage_b_passed`, `stage_c_passed`, `cross_pair_passed`)。

## 5. 検証 / Verification

### 5.1 同値性テスト (新規)
`tests/scripts/test_run_ga_parallel.py`:
1. 小さな fixture (population=8, generations=2, seed=42) で `--max-workers 1` と `--max-workers 4` を実行
2. `archive.parquet` を pandas で読み込み、`(lane_id, generation, genome_name)` でソート
3. **L1 assert**: `cache[name].fitness_pen`, `summary.json.best.name`, `summary.json.best.metrics.fitness_pen`, `live_criteria_passed` が完全一致
4. **L2 assert**: archive 数値 column 一覧 (上記§4.7) が `pandas.testing.assert_frame_equal` で一致
5. **L3 は assert しない** (artifact bit 一致は要件外)

### 5.2 単体テスト
- `LaneManager(max_workers=1)` の動作が変わらない (既存 swim_lane test 群が pass)
- `LaneManager(max_workers=2)` で `_run_tier1_generation` の戻り値集計が一致 (mock primitive evaluator で StageResult を制御)
- worker 内例外が `GenomeEvalError` 経由で fail-closed StageResult に変換される
- `set_lane_context` の memo 機構: 同一 bars id を 2 連続で渡したとき pool.map が 1 回しか呼ばれない (mock 検証)
- `evaluate_genome` (evaluation 層) が in-process で純粋関数として動作する単体テスト (副作用なし証明)

### 5.3 性能観測 (informative; speedup claim は事前に書かない)
- EUR_JPY 6ヶ月、population=40 generations=15 を `--max-workers 1 / 2 / 4 / 6` で 1 RUN ずつ
- 計測項目を **stage 単位に分解** (Round 1 反映):
  - `stage_a_seconds_total` / `stage_b_seconds_total` / `stage_c_seconds_total`
  - `stage_a_pass_rate` / `stage_b_pass_rate` / `stage_c_pass_rate`
  - `wall_time_seconds_total` / `max_rss_mb`
- 上記を `summary.json` に **追加 field** として記録 (既存契約は保持)
- 観測結果は `devnotes/{dir}/observation.md` に追記してから speedup を語る (事前 claim はしない)

## 6. リスク / 不確実性

| リスク | 影響 | 緩和策 |
|---|---|---|
| pickle overhead (bars 18m × N worker) | メモリ +N×raw_bars_size、世代開始ラグ | 世代間で bars 不変なら lane_id memo (set_lane_context 内 skip) |
| メモリ試算が楽観的 (Round 1 Critical) | 24GB 制約超過リスク | §6.1 で保守的試算。default=1 固定、autopilot 自動増加禁止 |
| primitive registry の冪等再構築コスト | worker init 時 数 ms × N | 1 worker あたり 1 回のみなので無視可能 |
| structlog logger が worker 側で別 stream | INFO/WARNING ログが main から見えにくい | worker 側は WARNING 以上のみ stderr へ。詳細 log は archive に記録済 |
| `_bars_cache` が worker 毎に重複 | 各 worker で初回 mid OHLC 変換が走る | LRU は世代内継続なので genome 数分の hit が発生し overhead を相殺 |
| macOS spawn 起動の `__main__` ガード | run_ga.py 直下で main() 呼ぶ既存形は OK | 新 `parallel_eval.py` はモジュールレベルに worker fn を置けば spawn 安全 |
| Stage A 通過率が低い世代で並列化恩恵が薄い | Stage A だけ 40 genome 並列、B/C は数個のみ | §5.3 で stage 別 timing を計測してから判断 (事前断定しない) |
| cross-pair adapter の隠れた副作用 | L1/L2 決定論性違反 | 詳細設計で grep verify。未達なら INCONCLUSIVE で別タスク化 |
| Parquet writer metadata の非決定性 | L3 bit 一致不可 | L3 は要件外と明示 (§4.0, §4.7) |

### 6.1 メモリ試算 (Round 1 反映: 保守的上限)

**運用ガード (Round 2 Suggestion 反映)**: `runbook.md` に以下を追記する:
- 1 RUN 完了時 `summary.json.max_rss_mb_per_worker` が **3GB の 70% (= 2.1GB)** を超えていたら、次回 RUN で `max_workers` を下げる
- multi-pair 化で raw bars が膨張した場合、1 worker 試算が 2.1GB を超える時点で SharedBarStore タスクを起票


EUR_JPY 6ヶ月 M1 ≈ 260,000 bars を前提に、**1 worker あたり** の memory footprint を分解:

| 項目 | サイズ概算 | 根拠 |
|---|---|---|
| raw bars (Stage B 18m, list[PriceBar]) | ~50-100 MB | PriceBar object overhead (Python obj header + 9 fields × Decimal/float) ≈ 200-400 bytes/bar × 260k bars |
| raw bars (Stage A 60d) | ~17 MB | 60d × 1440 bars × 200 bytes |
| raw bars (Stage C holdout 60d) | ~17 MB | 同上 |
| `_bars_cache` derived ndarray (3 区間 × 4 array OHLC × float64) | ~25 MB | 260k × 4 × 8 bytes × 3 区間 |
| primitive_evaluator + aux dict | ~10 MB | aux series が空ならごく僅か。pair_bars が後で追加されるとここが膨らむ |
| Python interpreter / numpy / pandas | ~150 MB | spawn process の base footprint |
| その他 (cp_inputs / cfg / 局所バッファ) | ~50 MB | 安全マージン |
| **合計 / worker** | **~320-370 MB** | 保守的上限 |

24GB / 1 worker 3GB 制約に対して **十分な余裕** (1 worker あたり 3GB の 12% 程度)。
ただし以下に注意:
- main process も同等の footprint を持つので、合計 = `(N+1) × 370MB` ≈ 6 worker で 2.6GB
- `improve-cycle` で同時走行する別 process (Codex / 分析 BG) と合わせて 24GB を超えないよう、autopilot 側で同時走行 GA process は 1 個に限定
- 将来 multi-pair (6 通貨ペア × 18m bars) になったら ~6 倍に膨らむため、SharedBarStore 導入を再検討

## 7. 影響範囲 (ファイル一覧)

- 新規: `src/alpha_factory/parallel_eval.py` (evaluation 層 + ParallelEvaluator + SequentialEvaluator)
- 修正: `src/alpha_factory/swim_lane.py` (`LaneManager.__init__` に `max_workers` 引数 / `_run_tier1_generation` を evaluator API 経由に切り替え)
- 修正: `src/alpha_factory/config.py` (`GAConfig.max_workers` 追加 + `_build_ga` で読み込み)
- 修正: `config/alpha_factory/default.yaml` (`ga.max_workers: 1` + コメント)
- 修正: `scripts/alpha_factory/run_ga.py` (`--max-workers N` / `--workers N` CLI flag + override 経路 + `LaneManager` への伝搬)
- 新規: `tests/scripts/test_run_ga_parallel.py` (L1/L2 同値性テスト)
- 修正: `tests/alpha_factory/test_swim_lane.py` (max_workers=2 mock case)
- 新規: `tests/alpha_factory/test_parallel_eval.py` (evaluation 層 / set_lane_context memo / GenomeEvalError 経路)
- 修正: `docs/alpha_factory/runbook.md` または `swim-lane.md` (CLI/YAML 追記、`update-docs` skill で巡回)
- 修正: `AGENTS.md` (運用コマンド例に `--max-workers` を追記するか確認)

## 8. 次のステップ

1. 本概念設計 v2 を Round 2 で再 review
2. APPROVED 後、詳細設計 (`detailed-design.md`) で:
   - `LaneEvalContext` / `GenomeStageResult` / `GenomeEvalError` の dataclass を pseudo-code レベルまで具体化
   - `ParallelEvaluator` / `SequentialEvaluator` の class 図と sequence diagram (テキスト)
   - `_run_tier1_generation` の if-branch 構造を before/after 比較
   - `RegistryEvaluator.aux_pair_bars` の pickle 検証手順
   - cross-pair adapter の純粋性 grep verify 手順
   - test fixture のサイズと assert 仕様
   - `summary.json` への追加 field schema
3. `technical-design-review` skill で Codex レビュー
4. レビュー反映後、TODO 登録 (`zenigame-fx-todo-add`) → 実装 (`zenigame-fx-implement`)
