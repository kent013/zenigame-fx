# Migration Triggers

## 目的

(b)×(i) → (ii) アーキテクチャ移行条件、(ii-lite) shadow → hard 化条件、hard → shadow rollback 条件を一箇所に集約する。各判定ロジックの実装は別 TODO で扱う。

## スコープ

- 3 種類の移行（forward / shadow→hard / rollback）の構造
- 各トリガーが参照する統計量
- 判定不能時のフォールバック方針

数値（連続回数・比率閾値）は SSOT 参照。

## 用語リンク

本ドキュメントで使用する用語: [DSR](terminology.md#dsr), [PBO](terminology.md#pbo), [Reality Check](terminology.md#reality-check), [(ii-lite)](terminology.md#ii-lite), [Walk-Forward](terminology.md#walk-forward)

## 主要定義

### A. (b)×(i) → (ii) Hard 移行

per-instrument GA から完全 universal GA へ切替えるトリガー。以下のいずれか:

- **条件 1**: `PBO > 閾値` AND (`DSR < 0` 連続 N 回 OR `fold 負比率 ≥ 閾値`)
- **条件 2**: `Reality Check p > 閾値` 連続 N 回 AND DSR 改善なし

両条件は**いずれも複合条件**。単一指標で発動しない構造。

### B. (ii-lite) Shadow → Hard 化

(ii-lite) を Stage C 通過判定に組み込むトリガー。**3 条件すべて**を満たす:

1. **ウォームアップ**: 累積 run 数 ≥ 閾値 AND target ごとの run 数 ≥ 閾値
2. **安定性**: 通過率 median が `[下限, 上限]` 範囲内 AND 標準偏差 ≤ 閾値
3. **予測力**: shadow 通過群の事後 OOS Sharpe 中央値が不通過群より差分 ≥ 閾値、検定 `p < 閾値`

### C. Hard → Shadow Rollback

hard 化後の急変で自動 shadow 戻し:

- hard 化後 N run 以内に target Sharpe が shadow 期基準比 R% 以上低下 × 連続 M 窓
- または通過率 < 下限 / > 上限が連続 M run

### D. 判定不能時

- N run 蓄積しても discrimination が成立しない場合: 永久 shadow 運用
- 数値を緩めて無理に hard 化しない（禁止事項 #2 / #4）

## SSOT 参照

| 項目 | 参照キーパス（config/alpha_factory/default.yaml） |
|------|--------------------------------------------------|
| (b)→(ii) PBO 閾値 | Phase 6I で `migration_triggers.forward.pbo_max` 追加予定（未定義） |
| (b)→(ii) DSR 連続 N | Phase 6I で `migration_triggers.forward.dsr_negative_streak` 追加予定（未定義） |
| (b)→(ii) fold 負比率 | Phase 6I で `migration_triggers.forward.fold_negative_ratio` 追加予定（未定義） |
| (b)→(ii) RC p 閾値 | Phase 6I で `migration_triggers.forward.rc_p_max` 追加予定（未定義） |
| Shadow→Hard ウォームアップ | Phase 6I で `migration_triggers.shadow_to_hard.warmup_*` 追加予定（未定義） |
| Shadow→Hard 安定性 | Phase 6I で `migration_triggers.shadow_to_hard.stability_*` 追加予定（未定義） |
| Shadow→Hard 予測力 | Phase 6I で `migration_triggers.shadow_to_hard.predictive_*` 追加予定（未定義） |
| Rollback Sharpe 低下率 | Phase 6I で `migration_triggers.rollback.sharpe_drop_*` 追加予定（未定義） |
| Rollback 通過率異常 | Phase 6I で `migration_triggers.rollback.pass_rate_*` 追加予定（未定義） |

## 関連ドキュメント

- [statistics.md](statistics.md) — 参照する統計指標の定義
- [cross-pair.md](cross-pair.md) — (ii-lite) shadow / hard モード
- [stage-gates.md](stage-gates.md) — Stage 通過率の崩壊検知

## 関連 TODO

- 未着手（Phase 6: 移行トリガー自動判定）
