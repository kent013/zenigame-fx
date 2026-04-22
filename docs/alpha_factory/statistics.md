# Statistics

## 目的

DSR / PBO / Reality Check / SPA 等の統計検定の構造と、Phase 別実装スケジュールを一箇所に集約する。各関数 signature は別 TODO（`concepts/statistics-dsr-bootstrap.md`）で扱う。

## スコープ

- 各統計指標の定義（出典付き）
- block bootstrap CI の役割
- Phase 別の実装段階（必須 / 段階実装 / 後回し可）

実装関数 signature・パラメータ既定値は別 TODO に委ねる。

## 用語リンク

本ドキュメントで使用する用語: [DSR](terminology.md#dsr), [PBO](terminology.md#pbo), [Reality Check](terminology.md#reality-check), [SPA](terminology.md#spa), [CRN](terminology.md#crn), [Walk-Forward](terminology.md#walk-forward), [IS / OOS](terminology.md#is-oos)

## 主要定義

### Deflated Sharpe Ratio (DSR)

- 出典: Bailey & López de Prado (2014) "The Deflated Sharpe Ratio"
- 役割: 多数試行・skew/kurt 補正後の Sharpe 有意性
- Stage B の通過条件の一つ（Phase 2 monitor、Phase 3+ hard）

### Probability of Backtest Overfitting (PBO)

- 出典: Bailey, Borwein, López de Prado, Zhu (2014) "The Probability of Backtest Overfitting"
- 手法: Combinatorially Symmetric Cross-Validation (CSCV)
- 本プロジェクトでは **PBO-lite** を採用（top-M 候補に限定して S 分割）
- 移行トリガー判定の主要シグナル

### Block Bootstrap Sharpe CI

- 役割: 時系列依存を考慮した Sharpe の信頼区間
- block_size と n_bootstrap を持つ
- Phase 2 必須（archive に CI lower / upper を記録）

### Fold Sign Ratio

- 役割: WF の各 fold で OOS Sharpe が正の比率
- Stage B の複合通過条件の一つ
- Phase 2 必須

### Reality Check / SPA

- 出典: White (2000) "A Reality Check for Data Snooping" / Hansen (2005) "A Test for Superior Predictive Ability"
- 候補圧縮後（top-M）に実行
- Phase 4 で実装、Phase 6 で hard gate 化

### Common Random Numbers (CRN)

- 役割: 複数戦略を同じ乱数系列で比較してノイズ相殺
- 分散削減手法、ベンチマーク比較で利用

### Phase 別実装スケジュール

| Phase | 必須 | 段階実装 | 後回し可 |
|-------|------|---------|---------|
| 2 | DSR / fold sign ratio / block bootstrap CI | — | — |
| 3 | — | PBO-lite | — |
| 4 | — | — | RC / SPA |
| 6 | — | RC / SPA hard gate 化 | — |

## SSOT 参照

| 項目 | 参照キーパス（config/alpha_factory/default.yaml） |
|------|--------------------------------------------------|
| block bootstrap block_size | Phase 2I で `statistics.bootstrap.block_size` 追加予定（未定義） |
| block bootstrap n_bootstrap | Phase 2I で `statistics.bootstrap.n_bootstrap` 追加予定（未定義） |
| DSR n_trials の取得元 | Phase 2I で `statistics.dsr.n_trials_source` 追加予定（未定義） |
| PBO-lite top_M | Phase 3I で `statistics.pbo.top_m` 追加予定（未定義） |
| PBO-lite S 分割 | Phase 3I で `statistics.pbo.s_splits` 追加予定（未定義） |
| RC ブートストラップ B | Phase 4I で `statistics.reality_check.b` 追加予定（未定義） |

## 関連ドキュメント

- [stage-gates.md](stage-gates.md) — Stage B / C での利用
- [migration-triggers.md](migration-triggers.md) — DSR / PBO / RC の複合判定
- [concepts/statistics-dsr-bootstrap.md](concepts/statistics-dsr-bootstrap.md)

## 関連 TODO

- 未着手（Phase 2F: `src/alpha_factory/statistics.py`）
