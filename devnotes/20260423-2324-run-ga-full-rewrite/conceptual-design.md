# Conceptual Design — run-ga-full-rewrite (T018)

## 目的

`scripts/alpha_factory/run_ga.py` を Phase 2 で揃った基盤（Clause Genome + Stage A/B/C + Genome Archive + Cross-pair shadow + Swim Lane Manager）に完全統合する。現状 run_ga.py は Clause Genome → `src/ga/run_ga()` を直接叩くだけの単純版で、Stage ゲート・archive・cross-pair shadow は呼ばれていない。本 TODO で最終形に差し替える。

## ゴール（Phase 2 完結条件）

- CLI から単一 instrument で `pop × gen` GA を回し、各世代で Stage A/B/C + cross-pair shadow を実行
- Archive (GenomeArchive) を通して 1 run = 1 Parquet で genome ごとの評価結果を永続化
- Graduation 候補を swim_lane.LaneManager 経由で記録
- Run summary / history / best genome を reports/run-reports/run-{N}/ に書き出し
- 既存の `improve-cycle` / `analyze_run.py` / `generate_run_report.py` と互換の出力契約を維持

## Non-goal（別 TODO）

- Multi-instrument 並列実行（本 TODO は単一 instrument mode のみ、LaneManager は 1 lane で初期化するが並列実行はしない）
- Graduation lane 実 GA（LaneManager.run_generation の Graduation 部は Phase 2 では NotImplementedError のまま）
- Phase 4 hard cross-pair gate 切替
- 新しい fitness metric 追加

## 設計原則

1. **SSOT**: 設定は `config/alpha_factory/default.yaml` を単一ソースとし、CLI は override のみ
2. **dataclass loader 分離**: YAML → dataclass 変換は `src/alpha_factory/config.py`（新規モジュール）に閉じ込め、`run_ga.py` は orchestration に専念
3. **LaneManager を活用**: Stage A → B → C → archive 4段伝搬 + graduation 判定はすべて LaneManager に委譲。run_ga.py は世代 loop と population 生成だけ書く
4. **互換性**: 既存 summary.json / history.json / best_genome.json の top-level キーは維持し、新フィールド追加のみにとどめる
5. **評価 cost**: Stage B が 1 個体で 20 回以上 backtest するため、ランダム探索の population_size は 8〜30 想定。本 TODO ではテストは小構成（pop=5, gen=2）で完走のみ確認

## 全体フロー

```
main()
├── _parse_args()
├── _load_and_override_config()  # yaml + CLI override
├── AlphaFactoryConfig.from_dict() # dataclass 変換 (src/alpha_factory/config.py)
├── primitives.ensure_registered() # 32 primitive 一括登録
├── _load_lane_bars(instrument, ...) # DB から 60d/18m/holdout の 3 種 bars を取得
├── LaneManager 構築
│   ├── Tier1Lane(instrument=X, bars_60d, bars_18m, bars_holdout, meta)
│   ├── GraduationLane(pair_bars={X: bars_18m}, pair_meta={X: meta})  # 自分自身だけ入れる
│   ├── StageGateConfig / CrossPairConfig (yaml→dataclass)
│   ├── RegistryEvaluator(pair=X)
│   ├── GenomeArchive(run_id, run_number)
│   └── backtest_config_factory(inst) -> BacktestConfig
├── GA loop: for gen in range(generations):
│   ├── gen==0: population = [random_genome(...) for _ in range(pop_size)]
│   ├── gen>=1: population = _breed_next_gen(prev_individuals, ga_cfg)
│   │   - elitism: top elite_count をそのまま継承
│   │   - 残りは tournament × crossover × mutate
│   ├── lane.population = new_population
│   ├── summary_i = lane_manager.run_generation(lane_id)
│   │   - 内部で Stage A/B/C + archive collect + graduation判定
│   ├── stage_a_pass / b_pass / c_pass を summary に記録
│   └── individuals_cache[genome.name] = (fitness_pen, stage_a_payload)
│     # fitness は Stage A の fitness_pen を使う（下記 §5 参照）
├── archive.flush() → .cache/alpha_factory/runs/genomes_{run_id}.parquet
└── _write_reports(run_dir, ...)
    ├── summary.json: run_id, run_number, instrument, generations, stage pass counts,
    │                 best genome fitness/metrics, live_criteria, graduation_count
    ├── history.json: [{generation, best_fitness, stage_a_pass, stage_b_pass, stage_c_pass}]
    └── best_genome.json: serialized Genome
```

## 主要な設計決定

### 1. `src/alpha_factory/config.py` の構成

```python
@dataclass(frozen=True)
class DatasetConfig:
    instrument: str
    start: datetime
    end: datetime

@dataclass(frozen=True)
class GAConfig:
    population_size: int
    generations: int
    crossover_rate: float
    mutation_rate: float
    tournament_size: int
    elite_count: int
    max_depth: int
    max_clause: int
    fitness_metric: Literal["total_pnl","sharpe","calmar"]
    seed: int | None

@dataclass(frozen=True)
class BacktestSectionConfig:
    initial_cash: Decimal
    leverage: int
    units: int
    max_spread_bps: Decimal | None
    holding_cost_per_day_bps: Decimal
    session_close_utc_hours: frozenset[int]

@dataclass(frozen=True)
class AlphaFactoryConfig:
    dataset: DatasetConfig
    ga: GAConfig
    backtest: BacktestSectionConfig
    stage_gate: StageGateConfig          # re-export from stage_gate
    cross_pair: CrossPairConfig          # re-export from cross_pair
    swim_lane: SwimLaneConfig            # 新規、lane 共通 GA param を保持
    live_criteria: Mapping[str, float|int]

def load_config(path: Path, overrides: dict | None = None) -> AlphaFactoryConfig: ...
```

- YAML の各セクションを対応する dataclass にマップする
- `stage_gate` / `cross_pair` の既存 dataclass を再利用（`StageGateConfig`, `CrossPairConfig`）
- `SwimLaneConfig` は本 TODO で新設（tier1 の population_size / generations / crossover_rate / mutation_rate / elite_count を保持、graduation は当座 placeholder）
- CLI override は `overrides` 引数に dict で渡し、YAML 展開後に deep-merge
- validation: live_criteria 必須キー、GA 範囲、tier1 ⇄ top-level GA の整合

### 2. Bars のロード戦略

- Stage A (60d) / Stage B (18m = 540d) / Stage C (holdout 60d) の 3 種類を **別々に DB から取得**
- CLI `--start / --end` を受け付けた場合は **それを Stage B の bars 範囲と解釈**し、Stage A は末尾 60 観測日、holdout は bars 範囲の末尾外 60 観測日
- YAML `dataset.start / end` は Stage B の期間を示す（意味論変更、旧版は全体範囲）
- 簡素化のため当面は以下の rule:
  - Stage B bars = [dataset.start, dataset.end)
  - Stage A bars = Stage B bars の末尾 `stage_a_window_days` 営業日相当
  - Stage C holdout bars = dataset.end から後続の `stage_c_holdout_days` 営業日相当を別途 DB から取得（DB に無い場合は Stage B bars の末尾を流用し WARN）
- 本 TODO の最小目標は「コード path 完走」なので、Stage A/C が Stage B の slice でもテストは通る設計にする

### 3. Population 生成と fitness 連携

- 初代は `random_genome(rng, name=f"g0_i{i}", ...)` × population_size
- 以降は LaneManager の run_generation が評価した後に、archive から読み出すと重いので、run_ga.py 側で `_evaluate_via_lane` が返した `{genome.name: (fitness_pen_from_stage_a, stage_passed_flags)}` を cache し、tournament / crossover / mutate に使う
- **fitness の定義**: Stage A の `fitness_pen`（sharpe - α·size_norm）を使う。Stage B/C 通過個体は大きな boost を与える案もあるが、本 TODO は簡素化のため以下の lexicographic fitness:
  - `effective_fitness = fitness_pen + 1000 * stage_a_pass + 10000 * stage_b_pass + 100000 * stage_c_pass`
  - → Stage C 通過個体は確実に next-gen elite 枠 / tournament 上位に残る
- 単純で単調なので tournament / elitism と整合しやすい

### 4. LaneManager との統合

- `Tier1Lane.population` は `list[Genome]`
- run_ga.py が各世代で `lane.population = new_population` を代入してから `lane_manager.run_generation(lane_id)` を呼ぶ
- LaneManager は population を in-place 評価し、archive に 4段伝搬する
- cross-pair shadow は GraduationLane.pair_bars に target instrument を入れておくことで有効化（単一 instrument でも自分自身と照合できる。archive の payload に skipped=False で入る）
- ただし Phase 2 では multi-instrument bars が無いため cross-pair の pass_criteria は実質 monitor only。archive.ii_lite_pass は None（skipped）で記録される想定

### 5. run_ga.py 本体の責務

- argparse / yaml ロード / override / run_id 採番
- LaneManager 構築
- population 生成 + 世代 loop（`_breed_next_gen`）
- fitness cache (name → effective_fitness) の保持
- archive.flush() と reports 書き出し
- 既存 `backtest_run.py` / `ga_run.py` のコード再利用は **しない**（Clause 非対応だと判定、本ファイルに閉じる）
- 現行 `run_ga.py` は最終的に丸ごと置換。`_legacy_run_ga.py` として残すのは git 履歴だけで十分（新規ファイルは作らない）

### 6. エラー処理

- DB 取得失敗 → fail-fast（RuntimeError）
- primitive registry 空 → RuntimeError (ensure_registered が動いていない証拠)
- Stage 評価中の genome 固有例外は既存 stage_gate 側で吸収済み
- archive.flush の schema mismatch は test で検出、production では ValueError raise

### 7. 出力仕様

```json
// summary.json
{
  "run_id": "run_20260423_234500",
  "run_number": 3,
  "generated_at": "...",
  "instrument": "EUR_USD",
  "lane_id": "tier1_EUR_USD",
  "dataset": { "start": "...", "end": "...", "bars_60d": 120, "bars_18m": 3000, "bars_holdout": 120 },
  "ga_config": {...},
  "backtest_config": {...},
  "stage_gate_config": {...},
  "cross_pair_config": {...},
  "per_generation": [
    {"generation": 0, "n_evaluated": 30, "stage_a_pass": 5, "stage_b_pass": 2, "stage_c_pass": 0, "graduation_count": 0, "best_fitness": "0.12"},
    ...
  ],
  "best": {"name": "g5_i0", "fitness": "1.23", "stage_a_pass": true, "stage_b_pass": true, "stage_c_pass": true, "metrics": {...}},
  "live_criteria": {...},
  "graduation_count": 1,
  "archive_parquet": ".cache/alpha_factory/runs/genomes_run_20260423_234500.parquet"
}
```

```json
// history.json
[
  {"generation": 0, "best_fitness": "0.12", "stage_a_pass": 5, "stage_b_pass": 2, "stage_c_pass": 0},
  ...
]
```

```json
// best_genome.json
{<Genome serialized via src.dsl.serialize.genome_to_dict>}
```

- `population.jsonl` は廃止候補（情報は archive Parquet に入る）。本 TODO では互換維持のため簡素版を残す（name + effective_fitness）

### 8. テスト戦略

`tests/scripts/test_alpha_factory_run_ga.py`:

- `test_load_config_from_yaml`: default.yaml を読み込んで各 dataclass が期待値で構築されるか
- `test_config_cli_overrides`: CLI override dict が反映されるか
- `test_smoke_run_with_mocked_db`: SessionLocal を monkeypatch して dummy bars を返させ、pop=5 gen=2 の run が完走し archive.parquet + summary.json が生成されるか
- `test_run_id_generation`: run_id / run_number の採番規則（既存 run が 2 件あれば 3 が振られる）

## 残タスク（Phase 後続）

- Multi-instrument mode（`--instrument EUR_USD,USD_JPY`）での LaneManager 並列実行
- Graduation lane の実 GA 実装（別 TODO）
- fitness metric の拡張（例: Stage C 通過時のみ sharpe_stress を使う）
- Multi-pair bars 事前ロード → cross-pair shadow の実データ評価

## 判断確認項目（レビュー焦点）

1. **fitness の lexicographic 合成 (§3)** — この設計で tournament / elitism が期待動作するか
2. **Bars の 3 区間分割 (§2)** — dataset.start/end を「Stage B 期間」と解釈する意味論変更で既存 config との後方互換が崩れないか
3. **`src/alpha_factory/config.py` の新設** — `stage_gate.py` / `cross_pair.py` にある既存 dataclass を再エクスポートするか、独立させるか
4. **LaneManager との責務分離** — run_ga.py の population ライフサイクル管理を lane 外に置く設計で archive への collect が漏れないか
