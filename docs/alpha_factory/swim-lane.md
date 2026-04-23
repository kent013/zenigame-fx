# Swim Lane

## 目的

スイムレーン（Tier 1 + Graduation lane）の構造と graduation 条件、およびレーンオーケストレータ `LaneManager` を一箇所に集約する。実装詳細は `concepts/swim-lane-manager.md` および `src/alpha_factory/swim_lane.py`（T017 実装）で扱う。

## スコープ

- Tier 1 = per-instrument GA の構造
- Graduation lane = 卒業個体集合での universal 探索
- Graduate 条件
- レーン間の個体フロー
- `LaneManager` の責務と公開 API
- archive への 4 段伝搬契約

数値（population_size、target ペアリスト）は SSOT 参照。

## 用語リンク

本ドキュメントで使用する用語: [SwimLane](terminology.md#swim-lane), [Tier1Lane](terminology.md#tier1-lane), [GraduationLane](terminology.md#graduation-lane), [LaneManager](terminology.md#lane-manager), [Graduation Criteria](terminology.md#graduation-criteria), [Tier](terminology.md#tier), [Lane](terminology.md#lane), [Graduation](terminology.md#graduation), [Stage C](terminology.md#stage-c), [(ii-lite)](terminology.md#ii-lite), [Anchor Pair](terminology.md#anchor-pair)

## 主要定義

### 実装 (T017)

本 docs で示す概念は `src/alpha_factory/swim_lane.py` で以下の形に実装されている。

- `SwimLane` (基底 dataclass): `lane_id` / `population: list[Genome]` / `generation_count: int` / `state: LaneStatus`
- `Tier1Lane(SwimLane)`: `instrument` / `bars_60d` / `bars_18m` / `bars_holdout` / `meta: InstrumentMeta | None`
- `GraduationLane(SwimLane)`: `seed_graduates: list[Genome]` / `pair_bars: dict[str, list[PriceBar]]` / `pair_meta: dict[str, InstrumentMeta]`
- `LaneStatus = Literal["active", "converged", "paused"]`
- `GRADUATION_LANE_ID = "graduation"` / `GRADUATION_INSTRUMENT_SENTINEL = "multi"`（archive row の Graduation lane sentinel）

lane_id 規約:
- Tier 1: `"tier1_{instrument}"`（例: `"tier1_EUR_JPY"`）
- Graduation: 固定文字列 `"graduation"`
- `LaneManager.__init__` は `tier1: dict[str, Tier1Lane]` の dict キーに `lane_id` を採用し、`lane.instrument == lane_id.removeprefix("tier1_")` を検証する

### Tier 1 — per-instrument GA

- 1 instrument につき 1 lane
- 各 lane が独立して population を保持し、generation を進める
- target instrument は `improve_cycle.target_priority`（別 TODO で導入）の順序で巡回
- archive には `instrument` カラムが必須（cross-pair 分析の前提）

### Graduation Lane — universal 探索

- Tier 1 から graduate した個体だけを集めた universal lane
- Phase 2（本 TODO）では評価実体は未実装、`LaneManager.run_generation("graduation")` は `NotImplementedError`
- cross-pair shadow の multi-pair データ SSOT（`pair_bars` / `pair_meta`）として Tier 1 lane と共有

### Graduate 条件

```
Graduate = (Stage C 通過) AND ((ii-lite) cross-pair 通過)
```

両条件を AND で満たした個体のみ Graduation lane に昇格する。`LaneManager.graduation_criteria(individual, stage_c_result, cross_pair_result)` で判定し、`cross_pair_result is None`（skipped / 例外 fallback）なら保守的に `False`。Phase 2 では cross-pair が 2 条件 AND（mean / min）縮退、Phase 4 で 3 条件に拡張されても本判定は変更不要。

### レーン間フロー

```
[Tier 1: EUR_USD] ─┐
[Tier 1: USD_JPY] ─┤
[Tier 1: EUR_JPY] ─┼─(graduate)──> [Graduation Lane (universal)]
[Tier 1: AUD_JPY] ─┤
[Tier 1: USD_CAD] ─┤
[Tier 1: USD_ZAR] ─┘
```

Tier 1 → Graduation の一方向（後退無し）。Graduation lane で再評価されない場合の rollback ポリシーは別 TODO。

## `LaneManager` interface

| メソッド | 概要 |
|---------|------|
| `__init__(tier1, graduation, stage_gate_config, cross_pair_config, primitive_evaluator, archive, backtest_config_factory, *, deferred_promotion=False)` | 構築時に tier1 dict の整合、graduation.lane_id、meta 非 None、backtest_config_factory の intraday 制約を validate |
| `tier1 / graduation` (property) | 保持 lane への read-only view |
| `get_all_lanes()` | tier1（挿入順）+ graduation の順で全 lane を返す |
| `run_generation(lane_id)` | 1 lane に 1 世代の評価を適用。state != "active" は NoOp summary。`GRADUATION_LANE_ID` は Phase 2 で `NotImplementedError` |
| `graduation_criteria(individual, stage_c_result, cross_pair_result)` | Stage C passed AND cross-pair passed の AND 判定（cp=None は保守的 False）|
| `promote_graduates()` | 累積 graduation 件数 getter。`deferred_promotion=True` 指定時は Phase 4 予約のため `NotImplementedError` |

constructor 契約:
- `backtest_config_factory: Callable[[str], BacktestConfig]` は instrument 名から BacktestConfig を生成する factory。返値は `session_close_utc_hours` 非空（intraday 絶対制約）と `holding_cost_per_day_bps >= 0` を満たすこと。`__init__` で tier1 の最初のキーを用いて試走検証する。

### archive 4 段伝搬契約

| Stage | 関数 | 必須引数 | 呼び出し条件 |
|-------|------|----------|-------------|
| Stage A | `collect_stage_a` | `instrument=` 必須 | 全個体（通過/不通過を問わず） |
| Stage B | `collect_stage_b` | `instrument=` 省略可 | Stage A 通過後のみ |
| Stage C | `collect_stage_c` | `instrument=` 省略可 | Stage B 通過後のみ |
| 4 段目 | `mark_graduated` | `(lane_id, generation, individual_name)` | Stage C + cross-pair 両通過時のみ（Tier 1 lane のみ） |

冪等性: `_mark_for_graduation` は in-memory set `_promoted_keys: set[tuple[str, int, str]]` で `(lane_id, generation, individual_name)` の重複昇格を抑止する。二重呼び出しは WARN ログ + skip。

### state 遷移 (Phase 2)

| state | `run_generation` の挙動 |
|-------|-------------------------|
| `active` | 通常評価、generation_count をインクリメント |
| `converged` / `paused` | NoOp summary（n_evaluated=0、generation_count 不変、archive 未更新） |

state 遷移ロジック（plateau detection / mutation_rate auto-bump）は別 TODO に委ねる。

## SSOT 参照

| 項目 | 参照キーパス（config/alpha_factory/default.yaml） | 実装反映先 |
|------|--------------------------------------------------|-----------|
| Tier 1 population 初期サイズ | `swim_lane.tier1.population_size` | Run-GA TODO で `Tier1Lane.population` 初期化に使用 |
| Tier 1 世代数 | `swim_lane.tier1.generations` | Run-GA TODO で上位ループ |
| Tier 1 GA rate | `swim_lane.tier1.{crossover_rate, mutation_rate, elite_count}` | GA operators（Run-GA TODO） |
| Graduation population 初期サイズ | `swim_lane.graduation.population_size` | 同上 |
| Graduation seed 戦略 | `swim_lane.graduation.seed_strategy` | promotion → seed 構築（Run-GA TODO） |
| graduation 判定 2 条件 | `swim_lane.graduation_criteria.{require_stage_c_pass, require_cross_pair_pass}` | `LaneManager.graduation_criteria`（default True で AND 判定に合致） |
| cross-pair / stage-gate / backtest | `cross_pair.*` / `stage_gate.*` / `backtest.*` | それぞれの Config dataclass に展開済（T016 / T014 / T009） |
| target instrument | `dataset.instrument`（現行は単一。Phase 2I で `dataset.instruments` 配列化予定） | LaneManager 構築側（Run-GA TODO） |
| improve_cycle.target_priority | Phase 2I で追加予定（未定義） | LaneManager 巡回順（Run-GA TODO） |

YAML loader / `SwimLaneConfig` dataclass は本 TODO では追加せず、`StageGateConfig` / `CrossPairConfig` と同じく Run-GA 統合 TODO で一括実装する。

## 関連ドキュメント

- [stage-gates.md](stage-gates.md) — Graduate 条件の片方、Stage A/B/C
- [cross-pair.md](cross-pair.md) — Graduate 条件のもう片方、(ii-lite) shadow
- [clause-architecture.md](clause-architecture.md) — 各 lane で扱うゲノム構造
- [concepts/swim-lane-manager.md](concepts/swim-lane-manager.md) — 概念設計 origin
- [concepts/genome-archive-schema.md](concepts/genome-archive-schema.md) — archive 4 段伝搬先

## 関連 TODO

- 完了: T017 — `src/alpha_factory/swim_lane.py`（本実装）
- 未着手: `run-ga-full-rewrite` — `scripts/alpha_factory/run_ga.py` を LaneManager driver に書き換え
- 未着手: Graduation Lane の Stage A/B/C 評価（cross-pair 集約 fitness evaluator）
- 未着手: 多通貨 bars / meta ローダ（oanda DB → in-memory）
- 未着手: lane state 遷移ロジック（plateau detection 等）
