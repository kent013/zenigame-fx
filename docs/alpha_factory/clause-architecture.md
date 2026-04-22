# Clause Architecture

## 目的

ゲノム内部構造（Clause）の構造・式・合成ルールを一箇所に集約する。実装詳細は `concepts/clause-genome-structure.md` および後続 TODO で扱う。

## スコープ

- Clause の構成要素（directional / local_gate / weight）
- composite score の合成式とヒステリシス
- max_clause の段階解放方針
- long/short 対称制御 / セッション制御 / コスト反映の構造的要件

数値（α ペナルティ・閾値など）は SSOT 参照。

## 用語リンク

本ドキュメントで使用する用語: [Clause](terminology.md#clause), [Composite Score](terminology.md#composite-score), [Directional](terminology.md#directional), [Local Gate](terminology.md#local-gate), [Modulator](terminology.md#modulator), [TC](terminology.md#tc)

## 主要定義

### 1 Clause の構造

```
Clause = directional × local_gate × weight
dir_score  = Σ(w_i × signal_i) / Σ|w_i|          # directional の加重和（正規化）
gate       = Π gate_fn(gate_signal_j)             # local_gate の積（[0, 1] 有界）
clause_score = dir_score × gate
```

### 複数 Clause の合成

```
composite = Σ(cw_k × clause_score_k) / Σ|cw_k|
```

### ヒステリシス

- エントリー閾値 `θ_on`
- エグジット閾値 `θ_off`
- **必ず `θ_on > θ_off`**（チャタリング抑止）

### max_clause 段階解放

- 初期: 1（Phase 2 MVP）
- 標準: 2（Phase 3）
- 上限: 3（昇格試験合格時のみ、Phase 3 以降）

### 必須構造要件

- long/short 対称制御（パラメータは分離可）
- session close / time_stop による min/max 保有時間
- spread / slippage / swap を fitness に反映（絶対制約）

## SSOT 参照

| 項目 | 参照キーパス（config/alpha_factory/default.yaml） |
|------|--------------------------------------------------|
| max_depth | `ga.max_depth`（現行。Phase 2I で Clause 用 `ga.max_depth_per_clause` / `ga.max_clause` に再設計予定） |
| ペナルティ α | Phase 2I で `ga.complexity_penalty.alpha_stage_a` / `alpha_stage_bc` 追加予定（未定義） |
| ヒステリシス閾値 | Phase 2I で `ga.entry_threshold` / `exit_threshold` 追加予定（未定義） |

## 関連ドキュメント

- [stage-gates.md](stage-gates.md) — α ペナルティの Stage 別運用
- [swim-lane.md](swim-lane.md) — Tier / Lane との関係
- [primitives.md](primitives.md) — directional / modulator の候補
- [concepts/clause-genome-structure.md](concepts/clause-genome-structure.md)
- [concepts/clause-ga-operators.md](concepts/clause-ga-operators.md)
- [concepts/clause-backtest-integration.md](concepts/clause-backtest-integration.md)

## 関連 TODO

- 未着手（Phase 2C: `src/dsl/` 再構築）
