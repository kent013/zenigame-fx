# Concept: run-ga-full-rewrite

## 目的

`scripts/alpha_factory/run_ga.py` を Clause Genome + Stage A/B/C + archive + (ii-lite) shadow 対応に全面改修。

## 前提

以下が完了していること:
- clause-genome-structure
- clause-backtest-integration
- clause-ga-operators
- primitives-directional-generic
- primitives-modulator-generic
- primitives-registry
- stage-gate-implementation
- genome-archive-schema
- statistics-dsr-bootstrap
- swim-lane-manager
- cross-pair-evaluation-shadow

## 設計

### CLI

```bash
uv run python scripts/alpha_factory/run_ga.py \
  --instrument EUR_USD \
  [--lane tier1|graduation] \
  [--population-size 30] \
  [--generations 15] \
  [--config config/alpha_factory/default.yaml]
```

### フロー

1. config 読み込み + override
2. instrument に対応する Tier1Lane 初期化
3. 各世代:
   a. population 生成（初代はランダム、以降は crossover/mutate）
   b. Stage A 評価 → 通過率チェック → ペナルティ適用
   c. Stage B（通過個体のみ walk-forward OOS 評価）
   d. Stage C（Stage B 通過のみ live_criteria + spread stress）
   e. (ii-lite) shadow 評価（Stage C 通過全員）
   f. archive に世代全員の row 書き込み
   g. graduate 判定
4. 全世代終了後、graduate を GraduationLane に送出（別実行で）
5. run summary 書き出し

### 出力

- `.cache/alpha_factory/runs/genomes_{run_id}.parquet`（全世代の archive）
- `reports/run-reports/run-{N}/summary.json`
- `reports/run-reports/run-{N}/history.json`
- `reports/run-reports/run-{N}/best_genome.json`

## テスト

- small run（pop=5, gen=2）が例外なく完走
- archive Parquet が GENOMES_SCHEMA 準拠
- Stage A/B/C の通過数が妥当（初代から全員 Stage C 通過は異常）
- (ii-lite) shadow record が書き込まれる

## 優先度・モード

- Priority: Critical
- Mode: standalone
- テーマ: ga-architecture
