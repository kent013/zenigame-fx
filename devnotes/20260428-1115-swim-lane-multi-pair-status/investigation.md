# Swim-lane multi-pair 対応状況の調査

## 背景

初期議論で「スイムレーンを作って複数の通貨ペアを処理させる + 複数通貨に対応した(universal alpha 探索の) Graduation レーンも作る」と合意した。
EUR_JPY のテスト RUN 中に、その実装状況を確認したい。

## 結論

**設計・骨組みは議論通り実装済みだが、RUN 実体は現状シングル通貨ペア (EUR_JPY) のみ稼働**。
multi-pair Tier1 と Graduation lane の評価実体は意図的に Phase 4 / `run-ga-full-rewrite` TODO に保留されている。
EUR_JPY テスト完了後にこの保留分を着手するのが自然な順序。

## 実装済み (骨格)

[src/alpha_factory/swim_lane.py](../../src/alpha_factory/swim_lane.py) で以下が実装済み:

- `SwimLane` / `Tier1Lane` / `GraduationLane` dataclass 階層
- `LaneManager`
  - `tier1: dict[str, Tier1Lane]` を受け取り複数 lane を保持できる API
  - `lane_id == "tier1_{instrument}"` の命名規約と suffix 整合 validation
  - `run_generation(lane_id)` で Stage A → B → C → cross-pair shadow → graduation 判定の 1 世代 orchestration
  - `archive` への 4 段伝搬 (`collect_stage_a/b/c` + `mark_graduated`)
  - graduation 判定の冪等性ガード (`(lane_id, generation, genome.name)` 重複防止)
- `GraduationLane.pair_bars` / `pair_meta` を Tier1 lane の cross-pair shadow 入力 SSOT として共有する経路 (`_build_cross_pair_args`)

仕様根拠:
- [devnotes/20260423-2112-swim-lane-manager/](../../devnotes/20260423-2112-swim-lane-manager/) (概念設計 / 詳細設計 / R2 design review)
- [docs/alpha_factory/swim-lane.md](../../docs/alpha_factory/swim-lane.md)

## 未稼働 (RUN への結線が無い)

### 1. RUN 実行側で Tier1 lane が 1 個しか作られない

[scripts/alpha_factory/run_ga.py:1239-1251](../../scripts/alpha_factory/run_ga.py#L1239-L1251):

```python
tier1_lane = Tier1Lane(
    lane_id=lane_id,
    instrument=cfg.dataset.instrument,   # ← config 単一値
    bars_60d=bundle.bars_stage_a,
    bars_18m=bundle.bars_stage_b,
    bars_holdout=bundle.bars_holdout,
    meta=bundle.meta,
)
graduation_lane = GraduationLane(
    lane_id=GRADUATION_LANE_ID,
    pair_bars={},   # ← 空
    pair_meta={},
)
...
lane_manager = LaneManager(
    tier1={lane_id: tier1_lane},   # ← 1 要素のみ
    ...
)
```

### 2. config も単一通貨ペア指定

[config/alpha_factory/default.yaml:8-10](../../config/alpha_factory/default.yaml#L8-L10):

```yaml
dataset:
  instrument: EUR_JPY
```

[config/alpha_factory/default.yaml:189-203](../../config/alpha_factory/default.yaml#L189-L203) の `swim_lane` セクションは
「tier1 は 6 通貨ペアに lane を張る想定」とコメントしつつも、SSOT としてパラメータを並べているだけで、
YAML loader / `SwimLaneConfig` dataclass は未実装 (`run-ga-full-rewrite` TODO 待ち)。

### 3. cross-pair shadow は常に skip

`graduation.pair_bars == {}` のため [run_ga.py:1252-1255](../../scripts/alpha_factory/run_ga.py#L1252-L1255):

```python
cross_pair_mode = (
    "enabled" if graduation_lane.pair_bars
    else "skipped_single_instrument"   # ← 常にこちら
)
```

[config/alpha_factory/default.yaml:176-182](../../config/alpha_factory/default.yaml#L176-L182) の
`cross_pair.anchors` (EUR_JPY → [EUR_USD, USD_JPY] 等の 6 ペア定義) は存在するが、
`pair_bars_map` を populate する経路が無いので Stage C cross-pair shadow は skip 扱い。

### 4. Graduation lane の評価実体は NotImplementedError

[src/alpha_factory/swim_lane.py:359-363](../../src/alpha_factory/swim_lane.py#L359-L363):

```python
if lane_id == GRADUATION_LANE_ID:
    raise NotImplementedError(
        "GraduationLane.run_generation is not implemented in Phase 2 "
        "(planned for run-ga-full-rewrite TODO)"
    )
```

Phase 2 では Tier1 から graduation された個体の受け皿 (`seed_graduates`) としてのみ機能し、
universal alpha 探索 GA ループは未実装。

## 保留が妥当な理由

EUR_JPY 単一ペアでも Stage A/B/C パイプライン・aux data loader・GA evaluator 並列化等の改善余地が
依然多く、今は単一ペアでの fitness 検証・データ品質確認・bug hunt サイクルが優先されている。
multi-pair に拡張する前に「単一ペアで本当に live_criteria を満たす個体が生まれるか」を見極めるのが
設計順序として正しい (探索空間を闇雲に広げない)。

## 戻ってきたときの着手項目 (memo)

EUR_JPY テスト完了後に multi-pair / graduation を稼働させるなら、概ね以下の作業:

1. **多通貨 bars ロード経路**
   - `_load_lane_bars` を pair list 受けに拡張 (現状 1 instrument 受け)
   - `graduation.pair_bars` / `pair_meta` を全アンカーペアで populate
2. **YAML loader / `SwimLaneConfig` dataclass**
   - `swim_lane.tier1.pairs: list[str]` 等の追加
   - `dataset.instrument` を `dataset.instruments: list[str]` に拡張 (or 併存)
3. **RUN ループの multi-lane 巡回**
   - `lane_manager.get_all_lanes()` を世代ごとに iterate
   - 各 Tier1 lane 独立 GA (selection / crossover / mutation) を回す
   - lane 間共有メモリ (provenance / archive) の整合確認
4. **Graduation lane の評価実体**
   - cross-pair 集約 fitness evaluator (mean - λ×std on multi-pair Sharpe)
   - Tier1 → Graduation seed 取り込み + Graduation 独自 GA
   - `mode='hard'` 切替 (現状 `shadow`)
5. **Codex 合議で設計レビュー**
   - cross-pair 評価の選抜介入を入れる timing (Phase 2 shadow → Phase 4 hard)
   - lane 並列実行の決定論性 (L1 / L2 row-order 保証)

## 関連ファイル

- 実装: [src/alpha_factory/swim_lane.py](../../src/alpha_factory/swim_lane.py)
- 実装: [src/alpha_factory/cross_pair.py](../../src/alpha_factory/cross_pair.py)
- RUN 結線: [scripts/alpha_factory/run_ga.py](../../scripts/alpha_factory/run_ga.py)
- config: [config/alpha_factory/default.yaml](../../config/alpha_factory/default.yaml)
- 設計: [devnotes/20260423-2112-swim-lane-manager/](../../devnotes/20260423-2112-swim-lane-manager/)
- 並列化設計: [devnotes/20260427-1114-ga-parallel-workers/](../../devnotes/20260427-1114-ga-parallel-workers/)
- docs: [docs/alpha_factory/swim-lane.md](../../docs/alpha_factory/swim-lane.md) / [docs/alpha_factory/cross-pair.md](../../docs/alpha_factory/cross-pair.md)
