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

## 関連

- 親概念: [stage-gates.md](../stage-gates.md)
- 実装: `scripts/alpha_factory/calibrate_gate.py`
- skill: `.claude/skills/zenigame-fx-calibrate-gate/SKILL.md`
- 接続: `improve-cycle` Phase 2.5
