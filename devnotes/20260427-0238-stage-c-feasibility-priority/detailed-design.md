# 詳細設計: T045 Stage C Feasibility Priority Selection

## 背景

Run-20 (cycle 8) で Stage B 突破達成 (B pass=834)、しかし Stage C pass=0、best 個体 total_pnl=-16850 (損失) / sharpe=-0.19。

Codex 分析 (`devnotes/20260427-0232-fx-improve-c9/analysis-codex.md`) より:
- 「探索空間不足より選抜目的のミスマッチ」
- mission_score (T043) は soft 合算なので負 PnL 個体が生き残る
- selection_score の v2_feasibility (T031) は trade_count>=50 のみ要求、Sharpe/PnL 符号は無条件

## 解決方針

selection_score を v3 化 (8 要素): T031 feasibility の後に「stage_c feasibility」を追加。

新 selection_score: `(feasible_trade, -violation, **stage_c_feasible**, C_pass, B_pass, A_pass, fitness_pen)` ※ -violation の挿入位置は v2 と同じ

stage_c_feasible 定義: `archive.total_pnl > 0 AND archive.trade_sharpe_raw > 0`

これにより GA selection が Stage C 通過候補密度向上方向にバイアスされる。

## 施策一覧

| # | 施策 | 変更ファイル | 優先度 |
|---|------|------------|--------|
| 1 | StageGateConfig に `stage_c_feasibility_apply: bool = True` 追加 | `src/alpha_factory/stage_gate.py` | High |
| 2 | default.yaml に `stage_c.feasibility_apply: true` 追記 | `config/alpha_factory/default.yaml` | High |
| 3 | IndividualCacheEntry に `stage_c_feasible: bool = True` 追加 | `scripts/alpha_factory/run_ga.py` | Critical |
| 4 | selection_score 7 要素化 (v3): feasible 直後に stage_c_feasible 挿入 | `scripts/alpha_factory/run_ga.py` | Critical |
| 5 | _update_cache に stage_c_feasible 計算 (PnL>0 ∧ Sharpe>0) | `scripts/alpha_factory/run_ga.py` | Critical |
| 6 | summary 出力 7 要素化 + schema "v3_stage_c_feasibility" | `scripts/alpha_factory/run_ga.py` | High |
| 7 | run-report 説明文 v3 対応 | `scripts/alpha_factory/generate_run_report.py` | High |
| 8 | 既存テスト 6 要素期待値更新 + 新規 T045 テスト | `tests/scripts/`, `tests/alpha_factory/` | Critical |
| 9 | docs (clause-architecture / mission-score 連動部) 更新 | `docs/alpha_factory/` | Medium |

## 施策 1-2: config

### stage_gate.py
```python
# StageC 関連フィールドの近くに追加
stage_c_feasibility_apply: bool = True  # T045: GA selection で stage_c_feasible (PnL>0 ∧ Sharpe>0) を v3 selection_score に含める
```

### default.yaml
```yaml
stage_c:
  holdout_days: 60
  spread_stress_multiplier: 1.5
  spread_stress_min_total_pnl: 0.0
  spread_stress_min_sharpe: 0.0
  # T045: GA 選抜で PnL>0 ∧ Sharpe>0 個体を優先
  feasibility_apply: true
```

config.py loader にも追加。

## 施策 3-5: run_ga.py

### IndividualCacheEntry 拡張
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
    # T045
    stage_c_feasible: bool = True  # archive total_pnl>0 AND trade_sharpe_raw>0

    @property
    def selection_score(self) -> tuple[int, float, int, int, int, int, float]:
        """Lexicographic 7-tuple v3:
        (feasible, -violation, stage_c_feasible, C_pass, B_pass, A_pass, fitness_pen).

        T045: stage_c_feasible (PnL>0 ∧ Sharpe>0) を T031 feasibility 直後に挿入。
        """
        v = self.violation_magnitude
        v_norm = math.inf if not math.isfinite(v) else float(v)
        fp = self.fitness_pen
        fp_norm = -math.inf if not math.isfinite(fp) else float(fp)
        return (
            int(self.feasible),
            -v_norm,
            int(self.stage_c_feasible),
            int(self.stage_c_pass),
            int(self.stage_b_pass),
            int(self.stage_a_pass),
            fp_norm,
        )
```

### _update_cache 拡張
```python
def _update_cache(
    cache: dict[str, IndividualCacheEntry],
    population: list[Genome],
    archive: GenomeArchive,
    lane_id: str,
    generation: int,
    feasibility_cfg: GAFeasibilityConfig,
    stage_c_feasibility_apply: bool = True,
) -> None:
    # ... 既存 trade_count feasibility 計算 ...
    # T045: stage_c_feasibility 計算
    if stage_c_feasibility_apply:
        pnl = float(row.get("total_pnl") or 0.0)
        sharpe_raw = row.get("trade_sharpe_raw")
        try:
            sharpe = float(sharpe_raw) if sharpe_raw is not None else 0.0
        except (TypeError, ValueError):
            sharpe = 0.0
        stage_c_feasible = (pnl > 0.0) and (sharpe > 0.0)
    else:
        stage_c_feasible = True
    cache[g.name] = IndividualCacheEntry(
        ...,
        stage_c_feasible=stage_c_feasible,
    )
```

呼び出し側: `cfg.stage_gate.stage_c_feasibility_apply` を渡す。

### summary 出力
```python
"selection_score": [
    int(best_entry.feasible),
    -float(...),
    int(best_entry.stage_c_feasible),  # NEW
    int(best_entry.stage_c_pass),
    int(best_entry.stage_b_pass),
    int(best_entry.stage_a_pass),
    float(best_fitness_val),
],
"selection_score_schema": "v3_stage_c_feasibility",
```

## 施策 7: run-report

generate_run_report.py の note 文と Feasibility 集計:
```python
schema = best.get("selection_score_schema", "v1_legacy")
if schema == "v3_stage_c_feasibility":
    note = "Best は (feasible, -violation, stage_c_feasible, stage_c_pass, stage_b_pass, stage_a_pass, fitness_pen) の辞書式 (v3)。"
elif schema == "v2_feasibility":
    note = "Best は (feasible, -violation, stage_c_pass, stage_b_pass, stage_a_pass, fitness_pen) の辞書式 (v2)。"
else:
    note = "Best は (stage_c_pass, stage_b_pass, stage_a_pass, fitness_pen) の辞書式 (v1_legacy)。"
```

加えて Feasibility セクションに新行:
```
- best 個体 stage_c_feasible (PnL>0 ∧ Sharpe>0): ✅ / ❌
- archive 内 stage_c_feasible 比率: X% (M/N)
```

## 施策 8: テスト

| ファイル | テスト | 内容 |
|---------|--------|------|
| test_alpha_factory_run_ga_feasibility.py | test_v3_selection_includes_stage_c_feasible | 7-tuple 構造 |
| test_alpha_factory_run_ga_feasibility.py | test_stage_c_feasible_wins_over_infeasible_when_other_equal | feasible=True 同条件で stage_c_feasible=True が勝つ |
| test_alpha_factory_run_ga_feasibility.py | test_update_cache_marks_negative_pnl_infeasible_for_c | PnL<=0 で stage_c_feasible=False |
| test_alpha_factory_run_ga_feasibility.py | test_update_cache_marks_negative_sharpe_infeasible_for_c | sharpe<=0 で stage_c_feasible=False |
| test_alpha_factory_run_ga_feasibility.py | test_stage_c_feasibility_disabled_in_config_keeps_true | config で false なら全 True |
| test_alpha_factory_run_ga.py | test_smoke_run_holdout_ok | selection_score 7要素 + schema v3 期待値更新 |

## 施策 9: docs
- `docs/alpha_factory/clause-architecture.md` の selection_score 説明に v3 追記
- `.claude/skills/zenigame-fx-run-report/SKILL.md` の selection_score note に v3 追加

## ルックアヘッドバイアス
該当なし (archive row の集計値参照のみ、未来データ非参照)。

## パフォーマンス
- selection_score 7-tuple → 6-tuple から 1 要素追加で大差なし
- _update_cache に PnL/sharpe 取り出し追加 (1 row あたり数 ns)

## リスク
- 全個体 stage_c_feasible=False の状況: T031 fallback 経路と同様に enable_fallback_when_all_stage_c_infeasible で legacy 6 要素フォールバック検討 → Phase 1 では skip、リスクは「全個体 PnL<=0 ∨ sharpe<=0 で T031 feasibility のみで序列化される」 = current 動作と同じ
- 既存テスト: selection_score 6要素を hard-coded で検査するテストは更新

## 実装モード: incremental
影響範囲: stage_gate.py + run_ga.py + generate_run_report.py + tests + docs。schema 拡張のみで既存契約破壊なし。
