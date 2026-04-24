# Cross-pair Evaluation (ii-lite)

## 目的

(ii-lite) 評価の構造（target + アンカー 2 ペア、集約関数、通過基準、shadow / hard モード）を一箇所に集約する。実装は `src/alpha_factory/cross_pair.py` (T016 実装済)。

**注**: Cross-pair (ii-lite) と [Alpha Sieve](sieve.md) は **独立した追加ゲート** である。
- Cross-pair: Stage C と同時実行、target + 2 アンカーで shadow 集約
- Alpha Sieve: Stage C **後** の OOS 期間 (holdout + 5d ~ +95d) で再 backtest、target ペア単独で再検証

両者は補完関係にあり、Phase 4 で hard gate 化と DSR 接続が完了した時点で「Stage C 通過 → cross-pair hard pass → Alpha Sieve pass → 卒業候補」という三段直列ゲートとなる。

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

target ペアごとに 2 アンカーを**固定**割当（実行時に変動させない）。固定マッピング表は **`src/alpha_factory/cross_pair.py::ANCHOR_PAIRS`** (Python SSOT) に保持し、`default.yaml` の `cross_pair.anchors` で再掲される (T016 で追加)。

### Phase 2 / Phase 4 の通過基準段階導入

| Phase | 通過基準 | 通過基準の合成 |
|-------|----------|----------------|
| Phase 2 (shadow, T016 実装) | mean / min の **2 条件 AND** | provider 未注入のため ratio 判定は skip。Stage C `passed` には影響しない (shadow) |
| Phase 4 (hard, 別 TODO) | sharpe_ratio / mean / min の **3 条件 AND** | provider が結束されて ratio が opt-in、Stage C `passed` への AND 合成 |

- `pass_criteria.all` は None を除外して AND を取る (= 全 None なら False)
- pair_failure (backtest 例外 / metric_unavailable) があれば fail-fast で `passed=False` (集約値が信頼できないため)

## SSOT 参照

| 項目 | 参照キーパス（config/alpha_factory/default.yaml） | 実装 |
|------|--------------------------------------------------|------|
| 集約関数の λ | `cross_pair.aggregator_lambda` (default 0.5) | `CrossPairConfig.aggregator_lambda` |
| 通過基準 比率閾値 | `cross_pair.pass_criteria.sharpe_target_cross_ratio_min` (default 0.8) | `CrossPairConfig.sharpe_target_cross_ratio_min` |
| 通過基準 平均閾値 | `cross_pair.pass_criteria.mean_sharpe_cross_min` (default 0.15) | `CrossPairConfig.mean_sharpe_cross_min` |
| 通過基準 最小閾値 | `cross_pair.pass_criteria.min_sharpe_cross_min` (default -0.20) | `CrossPairConfig.min_sharpe_cross_min` |
| アンカーマッピング | `cross_pair.anchors.<target>` | `cross_pair.py::ANCHOR_PAIRS` |
| モード | `cross_pair.mode` (shadow / hard) | `CrossPairConfig.mode` |

## 関連ドキュメント

- [stage-gates.md](stage-gates.md) — Stage C 内での (ii-lite) 呼び出し
- [swim-lane.md](swim-lane.md) — Graduate 条件のもう片方
- [migration-triggers.md](migration-triggers.md) — Shadow → Hard 移行条件
- [concepts/cross-pair-evaluation-shadow.md](concepts/cross-pair-evaluation-shadow.md)

## External Data 戦略（CFD 取得可否ベース）

primitive P7-P12 が要求する CFD 系データ (S&P 500 / WTI / Gold / Copper / 米国債 / 日経) の取得経路は OANDA CFD 疎通試験 (T005) の実測結果で確定する。

### 試験結果（2026-04-22 実測）

| 試験 instrument | verdict | candle_count |
|---|---|---|
| SPX500_USD | OK | 10 |
| WTICO_USD | OK | 10 |
| XAU_USD | OK | 10 |
| XCU_USD | OK | 10 |
| JP225_USD | OK | 10 |
| USB10Y_USD | OK | 10 |
| USB02Y_USD | OK | 10 |

**全 7 instrument が OANDA live 口座で M1 candles 取得可能**（仮説 H1「米国規制で 403」を REJECT、H2「全アクセス可能」を CONFIRM）。

### 戦略

| 状態 | 戦略 | 現状 |
|---|---|---|
| **全 OK** | OANDA で M1 candles を取り込み、FX と同じ ingest パイプラインを拡張 | **適用** |
| 部分 OK | OK 分は OANDA、不可分は FRED 日足代替 + FX 派生指標 | n/a |
| 全不可 | FRED + 自前計算 primitive 強化のみ | n/a |

### 注記（観測 vs 解釈）

verdict は観測事実のみ。account 区分・契約状態・地域規制等の変更で結果が変わる可能性がある。本戦略採用時も再走行で結果が変動した場合は別経路へ切り替える前提で設計する。

実測レポート: `devnotes/20260422-1149-oanda-cfd-probe/probe-report.md`

## 実装メモ (T016)

`src/alpha_factory/cross_pair.py` の主要 API:

- `evaluate_cross_pair(genome, target, pair_bars, pair_meta, backtest_config, primitive_evaluator, cross_pair_config, *, sharpe_target_single=None, anchor_pairs=None) -> CrossPairResult`
- `StageCRunCrossPairEvaluator` — T014 `CrossPairEvaluator` Protocol 実装。Stage C `evaluate_stage_c(cross_pair_evaluator=...)` に注入する thin adapter。

戻り値の型は T014 で定義済の `CrossPairResult` を再利用 (`stage_gate.py` の SSOT 維持)。詳細値は `metrics` 辞書に canonical key 集合で格納:

```
sharpe_per_pair / mean_sharpe / std_sharpe / min_sharpe /
aggregate_fitness / aggregator_lambda / sharpe_target_single /
sharpe_target_cross / sharpe_target_cross_ratio /
liquidity_weighted_mean / pass_criteria / skipped /
skip_reason / mode
```

Stage C hook (`stage_gate.py::evaluate_stage_c`) は cross-pair evaluator 例外を try/except で隔離し、`payload.cross_pair.skipped=True` + `payload.cross_pair.error_type` (audit) を記録する。archive `_extract_cross_pair` は `payload.cross_pair.skipped` を見て `ii_lite_pass=None` を返す契約。

**Phase 2 構造的制約 — 非 JPY-quote の backtest 完走制約は T019 で解消**:

旧実装では `MockBroker` が `quote != JPY` (home=JPY 固定) で `NotImplementedError` を raise していたため、ANCHOR_PAIRS 定義 6 target すべてで少なくとも 1 つの非 JPY-quote anchor が含まれる現状では、実 backtest 経由での意味ある shadow 統計が取れなかった。T019 で MockBroker に **per-pair home モード** (default: `home_currency=meta.quote_currency`) を導入し、非 JPY-quote ペアでも backtest が完走するようになった。これにより cross-pair shadow は全 6 target で意味ある `mean_sharpe / std_sharpe / pair_failure` 統計を archive に残せる。

**T019 で解消した範囲（限定）**:
- 非 JPY-quote ペア (EUR_USD / USD_CAD 等) の backtest 完走制約
- cross-pair shadow の構造的 pair_failure:NotImplementedError

**T019 で解消されない範囲（Phase 4 TODO）**:
- `home != quote` (例: JPY 口座で EUR_USD を JPY 建てで評価) の真の quote→home 換算
- 複数通貨建て cash の統合会計（graduation lane マルチ pair 統合口座など）

**Sharpe 集約の解釈**: per-pair home Sharpe 集約であり、各 pair は独自の home currency (= quote currency) 建ての equity curve で評価される。Sharpe は無次元 (return mean / return std) で scale 不変性が保証される (T019 の `tests/broker/test_mock_multi_currency.py` で `initial_cash × units` 同時 10 倍スケール下の Sharpe 不変性 + equity returns 要素一致を直接検証済)。したがって pair 間で home 通貨が異なっても集約は統計的に健全。

Phase 4 の真の quote→home 換算が必要になった場合は、MockBroker に `fx_rate_provider` 引数を追加する設計を予約済 (devnotes/20260424-0517-mock-broker-multi-currency/conceptual-design.md §8)。

## 関連 TODO

- T016 実装済: `src/alpha_factory/cross_pair.py` 新設、Stage C hook 修正、config 追加
- T019 実装済 (2026-04-24): MockBroker 非 JPY-quote 対応 (per-pair home モード、`InstrumentMeta` に pip_size / display_precision 追加)
- 後続 (別 TODO):
  - swim-lane / run-ga 統合 (多通貨 bars/meta ロード経路 + provider bind)
  - archive スキーマ拡張 (`cross_pair_error_type` / `pair_failure_count` 列追加)
  - `liquidity_weighted_mean` 実装 (流動性データソース確定後)
  - Phase 4 hard 化 (`mode='hard'` で Stage C `passed` への AND 合成)
  - Phase 4 quote→home 換算 (MockBroker に `fx_rate_provider` 引数追加)
  - config YAML loader (StageGateConfig と一括で)
  - migration-triggers.md の shadow → hard 切替条件具体化
  - OANDA CFD ingest pipeline 拡張 (T005 実測結果に基づく別 TODO)
