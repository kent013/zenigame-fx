## 判定
NEEDS_REVISION

## 前提（C4）
- 設計レビュー対象は [detailed-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260424-1444-port-alpha-sieve/detailed-design.md) の Round 2 版で、Round 1 指摘の根拠確認として [run_ga.py](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py#L617), [statistics.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/statistics.py#L148), [config.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/config.py#L68), [default.yaml](/Users/ishitoya/repository/zenigame-fx/config/alpha_factory/default.yaml#L14) を参照した。
- C6 に従い、以下は Fact（記載/実装事実）と Interpretation（評価）を分離して記述する。
- C8: 本レビューは設計文書整合性レビューであり、実コード実行結果までは未検証（INCONCLUSIVE）。

## 観点別評価
1. dataclass / 関数 signature: Fact: `SieveEvalResult.oos_dsr` を `float | None` 維持し、Phase 2 恒常 `None` 方針が本文で明示されている（§2.2, §2.8）。Interpretation: 妥当。
2. strict gt vs >=: Fact: `_judge` は `sharpe <= min` / `total_pnl <= min` を不通過、`trade_count < min` を不通過としている（§2.7）。Interpretation: 概念設計 §2.3 と一致。
3. DSR fail-soft: Fact: `deflated_sharpe_ratio` の実シグネチャを根拠に「Phase 2 は常に None」を明文化（§2.8）。Interpretation: Round 1 指摘は解消。ただし同一文書内の再利用一覧が旧方針 (`compute_dsr` best-effort) のまま残っており不整合（§5 表）。
4. backtest_config 引き継ぎ: Fact: summary の 3項目制約を明示し、YAML `load_config` + `BacktestSectionConfig` を SSOT 化（§2.9）。Interpretation: Round 1 指摘は解消。
5. private import: Fact: `run_ga` の private helper 越境 import を暫定容認し、Phase 4 抽出 TODO を維持（§5）。Interpretation: Phase 2 として許容。
6. テストカバレッジ: Fact: 14-18 が追加され、Round 1 で不足していた `_evaluate_one` 正常系 / DSR policy / `_build_oos_backtest_config` 整合性が埋まっている（§3.2）。Interpretation: 主要懸念は解消。ただし §3.3 のモック方針記述が §3.2 ケース14（real backtest）と矛盾している。

## 修正要求（NEEDS_REVISION の場合のみ、最小限で）
- [ ] §5「既存モジュール再利用一覧」の DSR 行を Phase 2 方針に合わせて更新（`compute_dsr` 参照を削除し、`_compute_dsr_safe -> None` 固定に統一）。
- [ ] §3.3 モック方針を §3.2 ケース14 と整合させる（「_evaluate_one は実 backtest も1ケース実施」等に修正）。

## 推奨事項
- `backtest_config` mismatch は警告のみだと再現性事故を見逃す可能性があるため、将来は `--strict-config-match` で fail-fast 可能にしておくと監査性が上がる。