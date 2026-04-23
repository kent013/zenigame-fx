# 概念設計: swim-lane-manager (T017)

## 1. 目的

`src/alpha_factory/swim_lane.py` を新規作成し、Tier 1（通貨ペア × 1 lane = 6 lane）+ Graduation lane（卒業者集合）を一元管理する `LaneManager` を実装する。Stage A → B → C → cross-pair (ii-lite) shadow → graduation 判定の orchestration と、archive (`GenomeArchive`) への 4 段伝搬契約遵守を担保する。本 TODO では「lane の状態保持 + 1 generation の評価 orchestration + graduation 判定 + Tier1→Graduation 移送」までを実装し、**GA の世代生成 (selection / crossover / mutation) は呼び出し interface を整備するのみ** で実体は別 TODO (`run-ga-full-rewrite`) に委ねる。

## 2. 仮説

仮説 H1 (主): Tier 1 の per-instrument GA で Stage C を通過した個体のうち、cross-pair (ii-lite) でも基準を満たすものは「通貨ペア固有のノイズ捕捉ではない、相対的にロバストなゲノム」である可能性が高い。これらを Graduation lane に集約し、全 6 ペア横断の集約 fitness `mean(Sharpe_i) - λ × std(Sharpe_i)` で再評価することで、universal alpha 候補を抽出できる。

仮説 H2: Graduation lane は Tier 1 と同じ Stage 評価パイプラインで動かせる（評価関数 = cross-pair 集約 fitness）。lane の構造的差異は **fitness の定義と入力 bars の構成** だけに局所化できる。

検証: T017 では「lane が独立した population を保持する」「1 generation の Stage A/B/C 評価が決定論的に流れる」「graduation 判定と移送が仕様通り発火する」「archive に 4 段（Stage A/B/C + graduation flag）が漏れなく書かれる」までを担保。仮説 H1/H2 自体の検証は run-ga 統合後の実データに委ねる。

## 3. スコープ

### IN

- `src/alpha_factory/swim_lane.py` 新規
  - `SwimLane` (基底 dataclass: lane_id / population / generation_count / state)
  - `Tier1Lane` (instrument 固有: bars_60d / bars_18m / bars_holdout / meta)
  - `GraduationLane` (universal: seed_graduates / pair_bars / pair_meta)
  - `LaneManager` (tier1 dict + graduation 1 つ + 共通 config / evaluator / archive)
  - `LaneStatus = Literal["active", "converged", "paused"]`
- 1 lane × 1 generation の Stage 評価 orchestration (`run_generation`)
- graduation 判定 (`graduation_criteria`) と Tier1 → Graduation 移送 (`promote_graduates`)
- 全 lane 一覧取得 (`get_all_lanes`)
- archive への 4 段伝搬: `collect_stage_a` / `collect_stage_b` / `collect_stage_c` / `mark_graduated`
- `config/alpha_factory/default.yaml` に `swim_lane:` セクション追加 (SSOT のみ、loader は別 TODO)
- `tests/alpha_factory/test_swim_lane.py` (dataclass / 初期化 / run_generation / graduation_criteria / promote_graduates / archive collect 連動)
- `docs/alpha_factory/swim-lane.md` を実装に合わせて詳細化
- `docs/alpha_factory/terminology.md` に SwimLane / Tier1Lane / GraduationLane / LaneManager / Graduation Criteria 追加

### OUT (別 TODO)

- GA の selection / crossover / mutation を世代間で回す `run-ga-full-rewrite` (T018 以降想定)
- 並列実行 (lane × lane / generation × generation)
- 多通貨 bars / meta のロード経路 (oanda DB → in-memory 化)
- migration triggers (cross-pair shadow → hard 切替条件)
- Graduation lane → 本番デプロイ パイプライン

## 4. 主要設計判断

### 4.1 `SwimLane` 階層と dataclass 構造

```python
LaneStatus = Literal["active", "converged", "paused"]

@dataclass
class SwimLane:
    """全 lane の共通基底。"""
    lane_id: str                         # Tier 1: "tier1_EUR_JPY" / Graduation: "graduation"
    population: list[Genome]             # 現世代の個体集合 (in-place 更新可能)
    generation_count: int = 0
    state: LaneStatus = "active"

@dataclass
class Tier1Lane(SwimLane):
    instrument: str = ""                                  # "EUR_JPY" 等
    bars_60d: list[PriceBar] = field(default_factory=list)
    bars_18m: list[PriceBar] = field(default_factory=list)
    bars_holdout: list[PriceBar] = field(default_factory=list)
    meta: InstrumentMeta | None = None

@dataclass
class GraduationLane(SwimLane):
    """Universal alpha 探索: 全ペアで cross-pair 評価。"""
    seed_graduates: list[Genome] = field(default_factory=list)  # promotion 履歴 (重複可)
    pair_bars: dict[str, list[PriceBar]] = field(default_factory=dict)
    pair_meta: dict[str, InstrumentMeta] = field(default_factory=dict)
```

**判断ポイント**:
- `SwimLane` は `@dataclass`（frozen ではない）。population と generation_count を世代ごとに更新するため。lane_id だけは外部から書き換えるユースケースが無いが、簡潔さのため frozen にしない。
- `Tier1Lane.meta` は `InstrumentMeta | None`。dataclass デフォルト規約で None 許容。`run_generation` 開始時に non-None を assert。
- `GraduationLane.seed_graduates` は **昇格された個体の累積履歴**（population とは独立）。promote 時に `.append()` し、次世代生成時に `population` の seed として使う（実体は run-ga TODO で参照）。

### 4.2 `LaneManager` の責務分離

```python
class LaneManager:
    def __init__(
        self,
        tier1: dict[str, Tier1Lane],            # instrument -> lane
        graduation: GraduationLane,
        stage_gate_config: StageGateConfig,
        cross_pair_config: CrossPairConfig,
        primitive_evaluator: PrimitiveEvaluator,
        archive: GenomeArchive,
        backtest_config_factory: Callable[[str], BacktestConfig],  # instrument → config
    ) -> None: ...
```

**責務リスト**:
1. 各 lane の population に対して Stage A/B/C を順次実行する orchestration
2. archive に 4 段伝搬 (`collect_stage_a/b/c` + `mark_graduated`)
3. cross-pair (ii-lite) shadow を Stage C 内で evaluator として注入する
4. Stage C 通過 + cross-pair 通過の AND で graduation 判定
5. Graduation 判定された個体を `GraduationLane.seed_graduates` に追加
6. lane 一覧 / 状態管理 (`get_all_lanes`, `state` 更新)

**責務外**:
- 世代間 (selection / crossover / mutation): 別 TODO
- 多通貨 bars / meta のロード: 構築側 (factory) の責務
- 並列実行: Phase 2 では順次のみ

### 4.3 `run_generation(lane_id)` のフロー

```python
def run_generation(self, lane_id: str) -> dict[str, object]:
    """1 lane の 1 世代を Stage A → B → C で評価する。

    Returns: 集計サマリー (n_evaluated / stage_a_pass / stage_b_pass /
        stage_c_pass / graduation_count / wall_time_seconds)。
    """
```

Tier1Lane の処理フロー (graduation lane も同等、ただし fitness 計算源が cross-pair 集約):

```
for genome in lane.population:
    # Stage A
    a_result = evaluate_stage_a(genome, lane.bars_60d, lane.meta, bt_cfg, evaluator, stage_cfg)
    archive.collect_stage_a(genome, lane.lane_id, lane.generation_count, a_result, instrument=lane.instrument)
    if not a_result.passed: continue
    # Stage B
    b_result = evaluate_stage_b(genome, lane.bars_18m, lane.meta, bt_cfg, evaluator, stage_cfg)
    archive.collect_stage_b(genome, lane.lane_id, lane.generation_count, b_result)
    if not b_result.passed: continue
    # Stage C (cross-pair adapter は内部で構築)
    cp_evaluator, cp_inputs = self._build_cross_pair_args(lane, genome)
    c_result = evaluate_stage_c(
        genome, lane.bars_holdout, lane.meta, bt_cfg, evaluator, stage_cfg,
        cross_pair_evaluator=cp_evaluator, cross_pair_inputs=cp_inputs,
    )
    archive.collect_stage_c(genome, lane.lane_id, lane.generation_count, c_result)
    # Graduation 判定 (Tier1 lane のみ)
    if isinstance(lane, Tier1Lane):
        if self.graduation_criteria(genome, c_result, _extract_cross_pair_result(c_result)):
            self._mark_for_graduation(lane, genome)
lane.generation_count += 1
```

**判断ポイント**:
- Stage A 失敗で B/C は skip (短絡評価)。短絡された stage は archive に記録しない (`stage_a_pass=False` の row のみ残る)。これは archive の monotonic enrich ポリシーと整合。
- Stage C の `cross_pair_inputs` は `_build_cross_pair_args` ヘルパーで Tier1Lane なら `{target_pair: lane.instrument, pair_bars_map: graduation.pair_bars (利用可なら) or {}, meta_map: ...}` を組み立てる。pair_bars が空 dict なら cross-pair は skipped 扱い (詳細設計で具体化)。
- `_mark_for_graduation` は **当該世代の評価ループ完了後にまとめて promote** するか、**即座に GraduationLane.seed_graduates に append** するかの 2 案。**本 TODO は「即座に append + archive.mark_graduated」を採用**。理由: 1 世代内の archive 整合性を最優先 (graduation flag が flush 時に欠落しないため)。

### 4.4 `graduation_criteria` の判定ロジック

```python
def graduation_criteria(
    self,
    individual: Genome,
    stage_c_result: StageResult,
    cross_pair_result: CrossPairResult | None,
) -> bool:
    """Stage C 通過 AND (ii-lite) shadow 通過の AND 判定。

    ii-lite 通過の定義: `cross_pair_result is not None and cross_pair_result.passed`
    cross_pair_result が None (skipped / 評価未実行) の場合は **conservative に False**。
    Phase 2 では cross-pair が provider 未注入で 2 条件 AND (mean / min) 縮退となるが、
    本判定は `cross_pair_result.passed` の bool 値だけを参照する (3 条件 / 2 条件の差は cross_pair 実装側に隠蔽)。
    """
    if not stage_c_result.passed:
        return False
    if cross_pair_result is None:
        return False
    return bool(cross_pair_result.passed)
```

**判断ポイント**:
- 「Stage C 通過 AND (ii-lite) shadow の通過基準を 3 条件満たす」というタスク仕様について、Phase 2 では cross-pair shadow が `pass_criteria.sharpe_ratio = None` で **2 条件 AND** に縮退している (T016 詳細設計 §4.6)。本判定では `cross_pair_result.passed` をそのまま使うため、Phase 4 で 3 条件に拡張された際も**本コード変更なし**で対応可能。
- `cross_pair_result is None` (skipped / 例外で payload.cross_pair.skipped=True) の場合は**保守的に False**。これは仕様の「3 条件満たす」という文言と整合（条件確認できなければ通過を主張しない）。
- Graduation Lane 自体の lane の個体は本関数の対象外（Graduation lane は Stage C 通過 = 本番候補とみなす設計、本 TODO 範囲では呼び出さない）。

### 4.5 cross-pair adapter の組み立て (`_build_cross_pair_args`)

Tier1Lane の Stage C 評価では cross-pair shadow を有効化する。組み立てロジック:

```python
def _build_cross_pair_args(self, lane, genome):
    if not isinstance(lane, Tier1Lane):
        return None, None  # Graduation lane は cross-pair shadow 対象外
    # pair_bars / pair_meta は graduation lane のものを共有 (= multi-pair データの SSOT)
    pair_bars = self.graduation.pair_bars
    pair_meta = self.graduation.pair_meta
    if not pair_bars or lane.instrument not in pair_bars:
        return None, None  # データ未ロード時は cross-pair なしで Stage C 実行
    cp_evaluator = StageCRunCrossPairEvaluator(
        primitive_evaluator=self._primitive_evaluator,
        cross_pair_config=self._cross_pair_config,
    )
    cp_inputs = {
        "target_pair": lane.instrument,
        "pair_bars_map": pair_bars,
        "meta_map": pair_meta,
    }
    return cp_evaluator, cp_inputs
```

**判断ポイント**:
- `GraduationLane.pair_bars` を **multi-pair データの SSOT** として再利用する（重複ロード防止）。Graduation lane が初期化されていれば cross-pair 評価が有効化、空なら skipped。
- `StageCRunCrossPairEvaluator` は per-call で構築（lightweight、state なし）。
- `sharpe_target_single_provider` は本 TODO では bind しない（Phase 2 仕様、ratio 判定 skip）。

### 4.6 `promote_graduates` の役割

```python
def promote_graduates(self) -> int:
    """Tier 1 で graduate flag された個体を Graduation lane の seed に追加。

    `_mark_for_graduation` が即時 append + archive.mark_graduated を行うため、
    本メソッドは「未 archive 反映分の補助 batch 処理」として provide。
    Phase 2 default 実装は `_mark_for_graduation` で完結するため、本メソッドは
    no-op + 累積 graduation 件数 (= GraduationLane.seed_graduates の長さ) を返す
    形で **interface 整合性確保のみ** とする。

    Returns:
        累積 promotion 件数 (= len(graduation.seed_graduates))。
    """
    return len(self.graduation.seed_graduates)
```

**判断ポイント**:
- 仕様 (タスク定義) では `promote_graduates` を独立メソッドとして要求。設計判断は次の 2 案:
  - **案 A**: `run_generation` 内では graduation 判定だけ行い、別 step で `promote_graduates()` を呼んで実際の seed 追加 + archive.mark_graduated を行う (deferred)
  - **案 B**: `run_generation` で即時 promote、`promote_graduates()` は累積件数 getter として軽量化
- **本 TODO は案 B を採用**。理由:
  - 1 世代内の archive 整合性が最も厳しい requirement (mark_graduated 漏れが致命的)
  - 案 A だと「run_generation 後 / promote_graduates 前に archive.flush() を呼ばれる」リスクがある
  - 案 B のほうが side-effect の局所化と test 容易性が高い
- Run-GA 統合 TODO で「複数 lane の generation 並列 → 一括 promote」が必要になった場合、案 A への移行コストは低い (内部 state を変えるだけ。`deferred_promotion: bool` flag を `LaneManager.__init__` に追加して挙動を切り替える設計余地を残す)。

**冪等性ガード** (concept review #4):
- `_mark_for_graduation` は同一 `(lane_id, generation, individual_name)` に対して 2 回目以降の呼び出しを **skip** する (in-memory set `_promoted_keys` で管理)。これにより `seed_graduates.append` の重複と `archive.mark_graduated` の重複呼び出しを防ぐ。
- `seed_graduates` 自体は **append-only history** として重複を許容しても良い設計だが、Phase 2 では「同一個体の二重昇格を防ぐ」を優先 (downstream の `len(seed_graduates) == unique 卒業件数` 期待を満たすため)。

### 4.6.1 値の転記表 (config → consumer / archive 4 段)

reviewer #2 指摘対応。本 TODO で値の転記漏れを防ぐため、`swim_lane:` キーの SSOT → 各 consumer を表で固定する。

| SSOT (yaml) | データ型 | 経由 | 終点 |
|-------------|---------|------|------|
| `swim_lane.tier1.population_size` | int | (Run-GA TODO で `SwimLaneConfig` に展開) | `Tier1Lane.population` 初期化サイズ |
| `swim_lane.tier1.generations` | int | 同上 | `LaneManager` 上位ループ (本 TODO 範囲外) |
| `swim_lane.tier1.{crossover_rate, mutation_rate, elite_count}` | float/int | 同上 | GA operators (本 TODO 範囲外) |
| `swim_lane.graduation.population_size` | int | 同上 | `GraduationLane.population` 初期化サイズ |
| `swim_lane.graduation.seed_strategy` | str | 同上 | promotion → seed 構築ロジック (本 TODO 範囲外) |
| `swim_lane.graduation_criteria.require_stage_c_pass` | bool | 同上 | `LaneManager.graduation_criteria` (default True) |
| `swim_lane.graduation_criteria.require_cross_pair_pass` | bool | 同上 | `LaneManager.graduation_criteria` (default True) |
| `cross_pair.*` | — | `CrossPairConfig` (T016) | `StageCRunCrossPairEvaluator` に注入 |
| `stage_gate.*` | — | `StageGateConfig` (T014) | `evaluate_stage_*` に注入 |
| `backtest.*` | — | `BacktestConfig` (T009) | `backtest_config_factory(instrument)` で生成 |
| (各 stage 結果) | StageResult | `archive.collect_stage_*` | `genomes_*.parquet` 各カラム |
| graduation flag | bool | `archive.mark_graduated` | `genomes_*.parquet.graduated` |

本 TODO では `swim_lane:` セクションの **読み込み (loader)** は実装しない (`SwimLaneConfig` dataclass も Run-GA TODO で導入)。本 TODO は **YAML SSOT としての記載と値伝搬契約の明文化のみ**。

### 4.6.2 backtest_config_factory の絶対制約契約

reviewer #7 指摘対応。`backtest_config_factory: Callable[[str], BacktestConfig]` が返す `BacktestConfig` は以下の絶対制約を満たすこと:

1. **イントラデイ強制**: `session_close_utc_hours` が非空、または bars が複数 UTC date に跨る (T009 で engine が ValueError raise する設計と整合)
2. **スワップ・スプレッド反映**: `holding_cost_per_day_bps` が定義され、`max_spread_bps` が None または非負

`LaneManager.__init__` で **factory が EUR_JPY を引数に呼び出して試走** し、上記を assert する health-check を実装 (詳細設計で具体化)。失敗時は `ValueError("backtest_config_factory violates intraday constraint")` 相当を raise。

### 4.7 archive 4 段伝搬契約

archive (`GenomeArchive`) は monotonic enrich (Stage A → B → C) を強制し、`mark_graduated` は graduated flag を立てる 4 段目。`run_generation` の各 stage 通過時に **必ず collect を呼ぶ**。

| Stage | 関数 | 必須引数 | 失敗時 |
|-------|------|----------|--------|
| Stage A | `collect_stage_a` | `instrument=` 必須 (新規行作成時) | 通過/不通過を問わず必ず呼ぶ |
| Stage B | `collect_stage_b` | `instrument=` は default None (既存 row enrich 想定) | A 通過後のみ呼ぶ |
| Stage C | `collect_stage_c` | 同上 | B 通過後のみ呼ぶ |
| mark | `mark_graduated` | (lane_id, generation, individual_name) | C 通過 + graduation_criteria True 時 |

**判断ポイント**:
- Stage A は **全個体に対して必ず呼ぶ**（落選個体も `stage_a_pass=False` で記録、Run-GA の analysis に必要）。
- Stage B/C は短絡（A/B 不通過なら呼ばない）。これは archive の monotonic enrich を破らない（後段が呼ばれないだけ、前段が enrich される設計と矛盾しない）。
- `mark_graduated` は Stage C 通過 + cross-pair 通過の AND で初めて呼ぶ。Tier1Lane のみ対象（Graduation lane の個体には呼ばない）。
- Graduation Lane の `run_generation` でも archive collect は同等に行う **設計予約** だが、本 TODO では §4.8 のとおり `NotImplementedError` を raise するため archive collect は呼ばれない (reviewer #1 整合性指摘対応)。Graduation lane で archive collect が呼ばれるようになる Run-GA 統合 TODO 時点で `lane_id="graduation"` / `instrument="multi"` (sentinel 文字列) を採用する。`"multi"` sentinel の互換契約は次の通り (reviewer #3 対応):
  - `instrument="multi"` の row では `genome_json` に評価対象 6 ペア + λ + 集約方式が embed される (Run-GA TODO で具体化、本 TODO では予約のみ)
  - 下流分析 (`scripts/alpha_factory/analyze_run.py` 等) は `instrument == "multi"` を「lane 集約 row」として fork 処理する
  - Tier 1 row との混在 query では `WHERE instrument != 'multi'` で per-pair 分析、`WHERE instrument == 'multi'` で universal 分析を分離可能

### 4.8 Graduation Lane の評価フロー (簡易版 / 詳細は別 TODO)

Graduation Lane の Stage A/B/C は本 TODO ではどう扱うかを明記する:

**判断ポイント**:
- 仕様には「Graduation Lane は全ペアで評価、fitness = mean(Sharpe_i) - 0.5*std(Sharpe_i)」とある。
- Stage A/B/C は **per-instrument の bars** を前提に設計されているため、Graduation lane の評価には **専用の集約 fitness 計算路** が必要。
- これは **Run-GA 統合 TODO** で完成させるべきスコープ (本 TODO では interface 整備のみ)。
- **本 TODO の決定**: `LaneManager.run_generation("graduation")` は **Phase 2 では NotImplementedError を raise する**。理由:
  - Stage A/B/C のスペックは per-instrument bars を要求する。Graduation lane の評価機構を本 TODO で full-fledged 実装すると **scope creep**
  - 仕様文書の「fitness = mean - 0.5*std」は cross-pair 集約と完全一致 → Run-GA 統合 TODO で **Graduation lane の Stage A/B/C を「全 6 ペアで cross-pair 集約」に置換する evaluator** を追加する設計余地を残す
  - ただし本 TODO のテストでは `LaneManager` が GraduationLane を保持できる、`get_all_lanes` で含まれる、`promote_graduates` が seed_graduates に追加する、までは検証する。

### 4.9 `LaneManager` の constructor 受け取り戦略

```python
def __init__(
    self,
    tier1: dict[str, Tier1Lane],
    graduation: GraduationLane,
    stage_gate_config: StageGateConfig,
    cross_pair_config: CrossPairConfig,
    primitive_evaluator: PrimitiveEvaluator,
    archive: GenomeArchive,
    backtest_config_factory: Callable[[str], BacktestConfig],
) -> None:
```

**判断ポイント**:
- `backtest_config_factory: Callable[[str], BacktestConfig]` は instrument 名から BacktestConfig を生成する。Tier1Lane と Graduation Lane の両方で「instrument 別 config」が必要 (instrument 名が違えば spread / margin 等が変わる) ため、factory pattern で抽象化。
- DI (dependency injection) を徹底し、test でモックしやすい設計にする。
- `primitive_evaluator` は全 lane 共通（PrimitiveEvaluator は state-less）。
- 構築時バリデーション: `tier1` は空でない / 各 Tier1Lane の `instrument == key` 一致 / `graduation.lane_id == "graduation"` 等を `__init__` で assert。

### 4.9.1 stage_gate_config の参照規約 (reviewer #5 対応)

`LaneManager.__init__(stage_gate_config: StageGateConfig)` で受け取った単一 `StageGateConfig` を **全 stage / 全 lane で共有**する。Stage A/B/C 別の config 切り替えはしない (T014 が単一 `StageGateConfig` で 3 stage を駆動する設計と整合)。

擬似コード中の `stage_cfg` 表記はすべて `self._stage_gate_config` を指す。

### 4.10 lane state 遷移 (`active` / `converged` / `paused`)

| state | 意味 | 遷移条件 (本 TODO 範囲) |
|-------|------|-----------------------|
| `active` | デフォルト、`run_generation` で進行 | 初期値 |
| `converged` | 改善停滞、generation 進行 stop | (本 TODO では遷移ロジック未実装、外部からの set のみ受付) |
| `paused` | 一時停止 | 同上 |

**判断ポイント**:
- 本 TODO では state 遷移ロジック (plateau detection 等) は実装しない。lane.state を読み取り、`active` 以外の lane は `run_generation` で **NoOp** + summary に `state="converged"` 等を返す。
- 状態遷移ロジックは Run-GA TODO に委ねる。

**NoOp 仕様契約** (reviewer #9 対応):
- `state != "active"` のとき `run_generation` は以下を必ず満たす:
  - `generation_count` を **インクリメントしない**
  - archive への collect_stage_* / mark_graduated を **呼ばない**
  - 戻り値 dict に `{"state": lane.state, "n_evaluated": 0, "stage_a_pass": 0, "stage_b_pass": 0, "stage_c_pass": 0, "graduation_count": 0, "wall_time_seconds": <elapsed>}` を含める
- テスト 15 で各 state (`converged` / `paused`) について上記を検証する。

## 5. 失敗モード分析

| モード | 検出 | 対処 |
|--------|------|------|
| Tier1Lane.meta = None | `run_generation` 開始時 assert | `ValueError("meta must be set for Tier1Lane: lane_id={...}")` |
| `lane_id` 不在の `run_generation` 呼び出し | dict lookup | `KeyError` を上位に伝播（呼び出し側の bug） |
| Stage A/B/C 内部例外 | stage_gate.py 内部で吸収済 (StageResult.reason_codes) | 通常通り archive collect、後段 stage は短絡 |
| cross-pair 例外 | T016 で例外隔離済 (Stage C hook 内 try/except) | shadow 影響なし、payload.cross_pair.skipped=True |
| graduation criteria が cross_pair_result is None で常に False | Phase 2 で pair_bars 未注入時に発生 | 設計通り (skip = False は保守的)、test で覆う |
| GraduationLane.run_generation 呼び出し | `NotImplementedError` raise | Phase 2 想定、別 TODO で実装 |
| archive 重複 collect (同一 stage 再呼び出し) | T015 monotonic enrich で WARN + 上書き | 本 TODO では呼び出しは Stage 1 回ずつのため発生しない想定 |
| population 中の Genome.name 重複 | archive (lane_id, generation, name) 主キー衝突 | T015 same_stage_recollect で WARN（呼び出し元の責務、本 TODO では検証しない） |

## 6. テスト設計 (概要)

`tests/alpha_factory/test_swim_lane.py`:

1. **dataclass 構造**: `SwimLane` / `Tier1Lane` / `GraduationLane` の field, default 値, mutability
2. **LaneStatus literal**: `"active" / "converged" / "paused"` の 3 値のみ
3. **LaneManager 初期化**: tier1 dict + graduation + 各 config を受け取り、`get_all_lanes()` で 6+1=7 lane が返る
4. **LaneManager 初期化バリデーション**: 空 tier1 / instrument-key 不一致 / graduation.lane_id != "graduation" → ValueError
5. **run_generation (Tier1Lane, Stage A 失敗)**: archive に Stage A row のみ書かれる、Stage B/C は呼ばれない
6. **run_generation (Tier1Lane, Stage A→B 通過, Stage C 失敗)**: archive に Stage A/B/C row が書かれる、graduation flag は False
7. **run_generation (Tier1Lane, Stage C 通過 + cross-pair 通過)**: graduation flag True、`graduation.seed_graduates` に追加
8. **run_generation (Tier1Lane, Stage C 通過 + cross-pair 失敗)**: graduation flag False、`seed_graduates` に追加されない
9. **run_generation (Tier1Lane, Stage C 通過 + cross-pair skipped)**: graduation flag False (保守的)
10. **graduation_criteria 境界**: (passed=False, cp=None) / (passed=True, cp=None) / (passed=True, cp.passed=False) / (passed=True, cp.passed=True) の 4 ケース
11. **promote_graduates**: 累積件数を返す、副作用無し
12. **run_generation (GraduationLane)**: `NotImplementedError` raise (Phase 2)
13. **run_generation lane_id 不在**: `KeyError`
14. **run_generation 後 generation_count インクリメント**: 1 → 2 → 3
15. **state="converged" / "paused" の lane**: `run_generation` が NoOp + summary 返す
16. **meta=None Tier1Lane**: `ValueError` 即座に
17. **archive collect 順序検証**: monkeypatch で collect_stage_a → b → c → mark_graduated の順序を検証 (Stage 通過パスのみ)
18. **cross-pair adapter 構築 (pair_bars 未注入)**: Stage C は cross_pair_evaluator=None で呼ばれる
19. **cross-pair adapter 構築 (pair_bars 注入)**: Stage C に StageCRunCrossPairEvaluator が渡される
20. **冪等性: 二重 graduation 抑止** (reviewer #4): 同一 (lane_id, generation, individual_name) で `_mark_for_graduation` を 2 回呼んでも `seed_graduates` は 1 件、`archive.mark_graduated` は 1 回しか呼ばれない
21. **backtest_config_factory 健全性** (reviewer #7): factory が `session_close_utc_hours` 空かつ単日 bars (= イントラデイ違反) BacktestConfig を返す mock の場合、`LaneManager.__init__` が `ValueError` を raise
22. **cross-pair skipped contract** (reviewer #6): `_build_cross_pair_args` が `(None, None)` を返す lane の Stage C 評価結果で `payload["cross_pair"]["skipped"] is True` （T014 既存契約と整合）

ダミー primitive evaluator + 小さな bars + monkeypatch で Stage A/B/C を高速に回す。

## 7. 設定統合

`config/alpha_factory/default.yaml` に追記:

```yaml
swim_lane:
  tier1:
    population_size: 30
    generations: 15
    crossover_rate: 0.7
    mutation_rate: 0.3
    elite_count: 2
  graduation:
    population_size: 40
    seed_strategy: "union_of_tier1_graduates"
  graduation_criteria:
    require_stage_c_pass: true
    require_cross_pair_pass: true
```

YAML loader は本 TODO では追加しない（StageGateConfig / CrossPairConfig と同じ方針、Run-GA 統合 TODO でまとめて実装）。SSOT としての記載のみ。

## 8. 命名 SSOT

- `SwimLane` (基底) / `Tier1Lane` / `GraduationLane`
- `LaneStatus = Literal["active", "converged", "paused"]`
- `LaneManager` (集約 manager)
- `lane_id`: Tier1 では `"tier1_{instrument}"` (例: `"tier1_EUR_JPY"`)、Graduation では `"graduation"` (固定文字列)
- archive `instrument` カラム: Tier1 では実 instrument、Graduation では `"multi"` (sentinel)

## 9. 関連ドキュメント

- `docs/alpha_factory/swim-lane.md` (本実装で詳細化)
- `docs/alpha_factory/terminology.md` (SwimLane / Tier1Lane / GraduationLane / LaneManager / Graduation Criteria 追加)
- `docs/alpha_factory/concepts/swim-lane-manager.md` (本概念設計の origin)
- `docs/alpha_factory/stage-gates.md` / `cross-pair.md` / `clause-architecture.md` (依存)

## 10. 残課題 (本 TODO 範囲外、別 TODO に積む想定)

1. **Run-GA 統合 (`run-ga-full-rewrite`)**: GA の selection / crossover / mutation 世代生成、scripts/alpha_factory/run_ga.py の書き換え
2. **Graduation Lane の Stage A/B/C 実装**: cross-pair 集約 fitness で評価する evaluator
3. **多通貨 bars / meta のロード経路**: oanda DB → in-memory dict 化、`improve_cycle.target_priority` 巡回
4. **lane state 遷移ロジック**: plateau detection / mutation_rate auto-bump
5. **並列実行**: lane × lane / generation × generation 並列
6. **YAML loader**: `swim_lane:` セクションを SwimLaneConfig dataclass に変換
7. **rollback ポリシー**: Graduation lane で再評価不可の個体の Tier 1 戻し（現状なし、必要性は要検討）
8. **lane 間 individual id 衝突防止**: 同名 Genome が複数 lane に出る場合の lane_id prefix ルール強化
