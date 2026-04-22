# Cross-pair Evaluation (ii-lite)

## 目的

(ii-lite) 評価の構造（target + アンカー 2 ペア、集約関数、通過基準、shadow / hard モード）を一箇所に集約する。実装詳細は `concepts/cross-pair-evaluation-shadow.md` および後続 TODO で扱う。

## スコープ

- target / アンカーの選び方（構造）
- 集約関数の構造（`mean - λ × std`）
- 通過基準は **3 条件 AND** という構造
- shadow / hard モード切替の構造

数値（λ、各閾値、アンカーペア固定割当）は SSOT 参照および `terminology.md` 経由で `migration-triggers.md` を参照。

## 用語リンク

本ドキュメントで使用する用語: [(ii-lite)](terminology.md#ii-lite), [Anchor Pair](terminology.md#anchor-pair), [Stage C](terminology.md#stage-c), [Graduation](terminology.md#graduation)

## 主要定義

### 評価構造

target ペア + アンカー 2 ペア = 計 3 ペアで同一ゲノムを評価。

### 主目的関数

```
F = mean(Sharpe_i) - λ × std(Sharpe_i)
```

- ペア間の平均パフォーマンスを取りつつ、ばらつきにペナルティ
- λ は SSOT 参照（小さければ平均寄り、大きければ最小値寄り）

### 監査関数（並走出力）

- `min(Sharpe_i)` — 最弱ペア
- 流動性重み付き mean — pair の取引可能性を加味

### 通過基準（3 条件 AND）

1. `Sharpe_target_cross / Sharpe_target_single ≥ 比率閾値`
2. `mean(Sharpe_i) ≥ 平均閾値`
3. `min(Sharpe_i) ≥ 最小閾値`

3 条件**すべて**を満たす必要がある（OR ではない）。

### Shadow / Hard モード

- **Shadow（Phase 2-5）**: 評価結果を archive に記録するのみ、Stage C 通過判定には影響しない
- **Hard（Phase 6 以降）**: 通過基準を満たさない個体は Stage C を通過させない
- Shadow → Hard の移行条件は [migration-triggers.md](migration-triggers.md)

### アンカー定義の構造

target ペアごとに 2 アンカーを**固定**割当（実行時に変動させない）。固定マッピング表は `default.yaml` の `ii_lite.anchors` キー（Phase 2I で追加予定）に保持する。

## SSOT 参照

| 項目 | 参照キーパス（config/alpha_factory/default.yaml） |
|------|--------------------------------------------------|
| 集約関数の λ | Phase 2I で `ii_lite.aggregation.lambda` 追加予定（未定義） |
| 通過基準 比率閾値 | Phase 2I で `ii_lite.pass_criteria.sharpe_target_cross_ratio_min` 追加予定（未定義） |
| 通過基準 平均閾値 | Phase 2I で `ii_lite.pass_criteria.mean_sharpe_cross_min` 追加予定（未定義） |
| 通過基準 最小閾値 | Phase 2I で `ii_lite.pass_criteria.min_sharpe_cross_min` 追加予定（未定義） |
| アンカーマッピング | Phase 2I で `ii_lite.anchors.<target>` 追加予定（未定義） |
| モード | Phase 2I で `ii_lite.mode`（shadow / hard）追加予定（未定義） |

## 関連ドキュメント

- [stage-gates.md](stage-gates.md) — Stage C 内での (ii-lite) 呼び出し
- [swim-lane.md](swim-lane.md) — Graduate 条件のもう片方
- [migration-triggers.md](migration-triggers.md) — Shadow → Hard 移行条件
- [concepts/cross-pair-evaluation-shadow.md](concepts/cross-pair-evaluation-shadow.md)

## 関連 TODO

- 未着手（Phase 2H: `src/alpha_factory/cross_pair.py`）
