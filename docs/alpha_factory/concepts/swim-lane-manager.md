# Concept: swim-lane-manager

## 目的

Tier 1（通貨ペアごとのスイムレーン）+ Graduation lane（卒業者集合）を管理する `src/alpha_factory/swim_lane.py` を実装。

## 設計

### SwimLane（基底）

```python
@dataclass
class SwimLane:
    lane_id: str
    population: list[Genome]
    generation_count: int
    state: Literal["active", "converged", "paused"]
```

### Tier1Lane — 通貨ペア特化 GA

- 1 lane = 1 instrument（6 ペア → 6 lane）
- 各 lane 独自の population, GA パラメータ
- Stage C 通過 + (ii-lite) shadow 通過で graduate

### GraduationLane — Universal alpha 探索

- seed = ∪ Tier 1 graduate
- pop_size は設定可
- 全ペアで評価、fitness = `mean(Sharpe_i) - 0.5*std(Sharpe_i)`
- Stage C 通過で本番候補

### LaneManager

```python
class LaneManager:
    tier1: dict[str, Tier1Lane]  # instrument → lane
    graduation: GraduationLane

    def run_generation(self, lane_id: str): ...
    def promote_graduates(self): ...
    def get_all_lanes(self) -> list[SwimLane]: ...
```

### Graduation 条件

- Stage C 通過 AND (ii-lite) shadow の通過基準を 3 条件満たす
- Tier 1 ↔ Graduation の個体移動履歴を archive に記録

## 実装範囲

- swim_lane.py 新設
- run_ga.py との統合は別 TODO（`run-ga-full-rewrite`）

## テスト

- Tier 1 で graduate 条件を満たす個体が Graduation lane の seed に入る
- LaneManager の dispatch が正しい
- 状態遷移のイベントが archive に記録される

## 優先度・モード

- Priority: High
- Mode: standalone
- テーマ: swim-lane
