# zenigame-fx Alpha Factory

FX イントラデイ戦略ゲノムを GA で進化させ、`live_criteria` を満たす個体を探索するシステム。

## 使命（North Star）

> `config/alpha_factory/default.yaml` → `live_criteria` を全て満たす FX イントラデイ戦略ゲノム個体を **1 つ** 見つけ出すこと。

使命達成 = live_criteria の全指標（Sharpe, Total PnL, Max Drawdown, Trade Count 範囲）を同時に満たし、Cross-pair (ii-lite) 評価も通過した個体の出現。
達成後は閾値を引き上げて次の水準を設定する（漸進的目標更新）。

## 絶対制約

- **イントラデイ前提**（オーバーナイト保有を前提にする設計は避ける）
- **ロング・ショート両方向許容**（FX の性質上）
- **スワップ・スプレッドを fitness に反映**（見かけの PnL ではなく純利益）

## アーキテクチャの 2 軸

### 軸 1: ゲノム内部構造 — Clause ベース合成

1-3 個の Clause × directional signal × local_gate の合成で composite score を出し、閾値で売買判定。zenigame 日本株 Alpha Factory の設計を踏襲。

詳細: [clause-architecture.md](clause-architecture.md)

### 軸 2: GA スコープ — Per-instrument + Universal shadow

銘柄（通貨ペア）ごとに独立した GA を Tier 1 スイムレーンで回し、graduate した個体を Graduation lane で universal 探索。`(ii-lite)` cross-pair 評価を Phase 2 から shadow、実測データ蓄積後に hard gate 化。

詳細: [swim-lane.md](swim-lane.md)

## 主要ドキュメント

| ファイル | 内容 |
|---------|------|
| [README.md](README.md) | 本ファイル |
| [clause-architecture.md](clause-architecture.md) | ゲノム内部構造（Clause / directional / local_gate / composite） |
| [stage-gates.md](stage-gates.md) | Stage A/B/C ゲート仕様、walk-forward、live_criteria |
| [swim-lane.md](swim-lane.md) | スイムレーン設計、Tier 1 / Graduation lane、graduation 基準 |
| [primitives.md](primitives.md) | プリミティブカタログ（32 個: 汎用 20 + ペア特化 12） |
| [cross-pair.md](cross-pair.md) | (ii-lite) 評価、アンカーペア、集約関数 |
| [statistics.md](statistics.md) | DSR / PBO / Reality Check 仕様 |
| [migration-triggers.md](migration-triggers.md) | (b)×(i) → (ii) 移行条件 |
| [terminology.md](terminology.md) | 用語集 |
| [runbook.md](runbook.md) | 運用ガイド |
| [codex-discipline.md](codex-discipline.md) | Codex 合議の原則（C1-C9） |
| [TODO.md](TODO.md) | Open タスク一覧 |
| [TODO-closed.md](TODO-closed.md) | Closed/Obsoleted アーカイブ |

## 主要パス

| パス | 内容 |
|------|------|
| `src/alpha_factory/` | コアロジック（stage_gate, archive, statistics, swim_lane, cross_pair） |
| `src/alpha_factory/primitives/` | プリミティブ実装 |
| `src/dsl/` | ゲノム表現（WhenConfig + HowConfig + Clause） |
| `src/ga/` | GA エンジン |
| `src/backtest/` | バックテストエンジン |
| `src/ingest/` | データ取り込み（OANDA, FRED） |
| `scripts/alpha_factory/` | CLI エントリポイント（run_ga, analyze_run, generate_run_report, todo_manager 等） |
| `config/alpha_factory/` | `default.yaml`, `focus-theme.json` |
| `reports/run-reports/` | Run レポート |
| `reports/alpha-sieve/` | Alpha Sieve OOS 検証レポート |
| `.cache/alpha_factory/` | ゲノム archive (Parquet)、state file |
| `devnotes/` | 設計・分析・監査の中間成果物 |

## 改善サイクル

`/zenigame-fx-autopilot --repeat` で自走:

```
Phase 0 Survey → Phase 1 Design → Phase 2 TODO Add → Phase 3 Implement
                                                       ↓
                                                     Phase 4 Checkpoint
                                                       ↓
                                           Phase 4A Evaluation (audit-interval ごと)
                                                       ↓
                                               Phase 0 に戻る
```

`/zenigame-fx-improve-cycle` は RUN を含む別オーケストレータ（analyze → GA → report → repeat）。

## 禁止事項（全フェーズ厳守）

1. A・B・C 評価期間を強い根拠なしに延長する
2. 見た目の数値をよくしようとする改善
3. GA をハックしてステージを進めようとする
4. live_criteria 閾値をいたずらに緩和する
5. やたらに複雑な案を提案する
6. 取引回数を削減して見かけの成績を上げようとする
7. オーバーナイト保有前提の設計
