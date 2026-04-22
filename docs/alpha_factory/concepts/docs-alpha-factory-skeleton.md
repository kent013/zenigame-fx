# Concept: docs-alpha-factory-skeleton

## 目的

`docs/alpha_factory/` 配下に主要ドキュメントの骨格を整備する。autopilot / improve-cycle / codex-review など複数 skill が参照する前提。

## 作成対象

- `clause-architecture.md` — Clause 構造の仕様（directional × local_gate × weight、composite score）
- `stage-gates.md` — Stage A/B/C 仕様（期間、walk-forward、通過基準、ペナルティ α）
- `swim-lane.md` — Tier 1 + Graduation lane 設計、graduation 基準
- `primitives.md` — プリミティブ 32 個のカタログ（汎用 20 + ペア特化 12）
- `cross-pair.md` — (ii-lite) 評価、アンカーペア、集約関数、通過基準
- `statistics.md` — DSR / PBO / Reality Check 仕様
- `migration-triggers.md` — (b)×(i) → (ii) 移行条件
- `terminology.md` — 用語集
- `runbook.md` — 運用ガイド
- `codex-discipline.md` — Codex 合議 C1-C9

## 方針

- 各ドキュメント 30-80 行の骨格でよい（詳細は別 TODO で追記）
- `config/alpha_factory/default.yaml` が SSOT。値はハードコードせず参照する記法
- 用語は `terminology.md` で定義、他ドキュメントから参照

## 参照元

- `devnotes/20260421-1850-fx-skill-port/debate-synthesis.md`（3 ラウンド議論の確定仕様）
- `devnotes/20260421-1850-fx-skill-port/master-plan.md`

## 優先度・モード

- Priority: High
- Mode: incremental
- テーマ: infrastructure
