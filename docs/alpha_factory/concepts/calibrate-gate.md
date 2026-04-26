# Concept: calibrate-gate

Stage A の `threshold` を archive Parquet 由来の実 pass rate から動的に調整する。

## 目的

`stage_gate.stage_a.target_pass_rate` を「設計目標として実際に成立させる」ための
フィードバックループ。Run 終了後に自動実行され、次 Run の `threshold` を yaml に
書き戻す。

## 入出力

- 入力: `.cache/alpha_factory/runs/genomes_{run_id}.parquet` (`stage_a_pass` カラム)
- 入力: `config/alpha_factory/default.yaml::stage_gate.stage_a` (target / threshold / calibrate)
- 出力: 同 yaml の `stage_gate.stage_a.threshold` 更新（dry-run なら更新せず提案のみ）
- 出力: 構造化ログ + ユーザー報告（表形式）

## 判断アルゴリズム

dead-band 付き P 項のみの PID-like。

1. `actual = stage_a_pass_count / total_count`
2. `actual ∈ [target - tol, target + tol]` → 変更なし (`in_band`)
3. それ以外 → `quantile(fitness_pen, 1 - target)` を仮想 threshold として目標化
4. 変更幅は `max_delta` でクランプ（暴走防止）
5. 結果は `[threshold_floor, threshold_ceiling]` でクランプ

詳細は `devnotes/20260424-1759-port-calibrate-gate/conceptual-design.md` を参照。

## 安全装置

- **dead-band**: ノイズ性変動で yaml を弄らない
- **max_delta clamp**: 1 Run の暴走を抑制
- **floor/ceiling**: 極端な fitness_pen 分布の outlier 対策
- **calibrate.enabled = false**: 完全停止可能（手動チューニング期間用）
- **dry-run**: 提案のみで yaml 不変

## drift 監視 (T040 Phase 1)

calibrate-gate 実行ごとに `reports/calibrate-gate/history.jsonl` へ JSONL 1 行
追記する (fail-open)。直近 N Run の drift 集計 + アラート判定 CLI:

```bash
uv run python scripts/alpha_factory/calibrate_gate_drift.py --last 5
```

### JSONL schema (1 record / 1 line)

```json
{
  "run_id": "run_20260426_001234",
  "applied_at": "2026-04-26T00:12:34+09:00",
  "n_rows_total": 96,
  "n_rows_used": 80,
  "aggregation_mode": "last_k_generations",
  "aggregation_window": 5,
  "actual_pass_rate": 0.123,
  "target_pass_rate": 0.15,
  "tol": 0.05,
  "prev_threshold": 0.0977,
  "new_threshold": 0.0934,
  "delta": -0.0043,
  "decision": "loosen",
  "var_fitness_pen": 1.23e-2,
  "clamped_by_delta": false,
  "clamped_by_floor_or_ceiling": false,
  "stage_b_pass_count": 2,
  "stage_c_pass_count": 0,
  "live_criteria_gap": {"sharpe": 0.45, "total_pnl": 8000.0}
}
```

主キー: `(run_id, applied_at)`。SSoT は `src/alpha_factory/calibrate_gate_history.py`
の `HistoryRecord` dataclass。

### drift 判定ルール (Phase 1 conservative)

| ルール | 既定閾値 (絶対回数) | 意味 |
|--------|------------------|------|
| `monotone_tighten` | tighten 回数 >= 4 (CLI `--monotone-threshold`) | tighten 連発 = target が高すぎる可能性 |
| `monotone_loosen` | loosen 回数 >= 4 (同上) | loosen 連発 = target が低すぎる可能性 |
| `threshold_clamp` | clamp 回数 >= 3 (CLI `--clamp-threshold`) | floor/ceiling 貼り付き = control law 飽和 |
| `pass_rate_band_excess` | `\|actual - target\| > 2 × tol` (CLI `--band-multiplier`) | actual と target の累積逸脱 |

**注**: 閾値は **絶対回数** で評価する (Codex round-1 [Suggestion] 反映)。`--last N` を変えても判定回数は固定なので、N を増やすと相対的にアラートしにくくなる。

CLI exit code: `0` no alert / `10` drift detected (warning) / `2` invalid arg / `3` history 不在。

**判断主体は人間**。本機構は記録・集計のみで calibrate-gate 制御則
(上記 "判断アルゴリズム") は変更しない (C3 collider bias 回避)。

## 関連

- 親概念: [stage-gates.md](../stage-gates.md)
- 実装: `scripts/alpha_factory/calibrate_gate.py` / `calibrate_gate_drift.py`
- 永続化: `src/alpha_factory/calibrate_gate_history.py`
- skill: `.claude/skills/zenigame-fx-calibrate-gate/SKILL.md`
- 接続: `improve-cycle` Phase 2.5
