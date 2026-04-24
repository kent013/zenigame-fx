## 判定
NEEDS_REVISION

## 前提（C4）
- `devnotes/20260424-1444-port-alpha-sieve/detailed-design.md:218-551` を本タスクの仕様ソースとして確認済み。設計レビュー closure で APPROVED 状態であることも同ファイルで検証済み。
- 既存再利用 API（`scripts/alpha_factory/run_ga.py` のヘルパ、`src/backtest/engine.py` の `BacktestConfig`）が本リポジトリ現行実装と一致していることを読み合わせで確認済み（`scripts/alpha_factory/run_ga.py:1-210`, `src/backtest/engine.py:1-120`）。
- 実装レビュー対象の `run_alpha_sieve.py` / テスト / skill ファイルは worktree 側最新版であり、ローカル dirty 変更はないことを `git status` で確認済み（出力は指示により割愛）。

## 観点別評価 (Fact / Interpretation 分離)

1. 設計実装一致性  
   Fact: `SieveConfig`/`CandidateRow`/`SieveEvalResult` のフィールド構成、`_build_oos_backtest_config` の YAML SSOT 方針、`_judge` の strict 条件、`_render_report` のセクション構成が詳細設計 §2 と一致する形で実装されている（`worktrees/todo-T025/scripts/alpha_factory/run_alpha_sieve.py:79-670`, `devnotes/20260424-1444-port-alpha-sieve/detailed-design.md:250-405`).  
   Interpretation: 設計で定義された I/O・データモデル・出力フォーマットは実装に反映されており、仕様逸脱は見当たらない。

2. 境界条件正確性  
   Fact: `_judge` は Sharpe/PNL を `>`、Trade count を `>=` で評価し、Sharpe None 時は明示的に失敗扱いする（`worktrees/todo-T025/scripts/alpha_factory/run_alpha_sieve.py:446-467`）。テスト側でも 0.5/0.0/29 といった境界ケースを網羅しており strict 判定が保持されている（`worktrees/todo-T025/tests/scripts/test_run_alpha_sieve.py:141-185`）。  
   Interpretation: 通過基準の比較演算子と Sharpe 欠損時のフォールバックが要求どおりに実装・検証されている。

3. defensive 経路  
   Fact: `main` は archive/summary 不在を exit=1、Stage C 通過 0 件を `status=no_candidates`、OOS bars 不在・ペア未登録を `status=no_data` で処理し、個体評価中の例外は `_evaluate_one` で `system_failure` に丸める（`worktrees/todo-T025/scripts/alpha_factory/run_alpha_sieve.py:693-799`, `worktrees/todo-T025/scripts/alpha_factory/run_alpha_sieve.py:384-423`）。  
   Interpretation: 指定された 4 defensive 経路（archive 無し / no_candidates / no_data / 個体例外）がコード上で網羅されており、期待どおり fail-soft になっている。

4. 既存モジュール再利用  
   Fact: `run_alpha_sieve.py` は `scripts/alpha_factory/run_ga` の `_bar_row_to_price_bar` / `_meta_from_pair` を import して DRY を維持し、バックテスト設定は `src/alpha_factory/config.load_config` から `BacktestSectionConfig` を再読み込みして `BacktestConfig` に変換している（`worktrees/todo-T025/scripts/alpha_factory/run_alpha_sieve.py:43-60`, `worktrees/todo-T025/scripts/alpha_factory/run_alpha_sieve.py:289-351`）。  
   Interpretation: 既存 SSOT を直接参照しており循環 import や設定乖離は発生していない。

5. テスト品質  
   Fact: 詳細設計 §3.2 はケース14として「実 backtest を 1 ケース実施して `_evaluate_one` が正常パスで Sharpe を取得できること」を明示要求している（`devnotes/20260424-1444-port-alpha-sieve/detailed-design.md:520-544`）。一方、現行テストは `_evaluate_one` に対して例外系（test_evaluate_one_handles_exception）と `bars=[]` の no_data しか用意されておらず、成功パスを検証するテストが存在しない（`worktrees/todo-T025/tests/scripts/test_run_alpha_sieve.py:307-410`）。  
   Interpretation: 設計で必須とされたカバレッジが欠落しており、実 backtest 経路の挙動がリグレッションで壊れても検知できないため修正が必要。

6. 使命/禁止事項適合  
   Fact: 通過基準は `sharpe > 0.5 AND trade_count >= 30 AND total_pnl > 0` をそのまま実装し（`worktrees/todo-T025/scripts/alpha_factory/run_alpha_sieve.py:446-467`）、BacktestConfig には YAML 由来の spread/holding cost・session close 設定を引き継いで intraday 制約とコスト反映を維持している（`worktrees/todo-T025/scripts/alpha_factory/run_alpha_sieve.py:289-351`; `src/backtest/engine.py:1-118`).  
   Interpretation: イントラデイ/スワップ/スプレッドの絶対制約や live_criteria 緩和禁止といった North Star 制約には抵触していない。

## 修正要求
- [ ] 詳細設計で必須とされている `_evaluate_one` 成功パスの統合テスト（`test_evaluate_one_success_with_real_backtest`）を `worktrees/todo-T025/tests/scripts/test_run_alpha_sieve.py` に追加し、実 bars + evaluator で `status="evaluated"` かつ `oos_sharpe` が浮動小数で得られることを検証してください（仕様参照: `devnotes/20260424-1444-port-alpha-sieve/detailed-design.md:520-544`）。これにより実 backtest 経路の回帰検知が可能になります。

## 推奨事項
- 現時点で追加の改善提案はありません（Phase 4 で予定されている DSR や複数窓拡張を待つ形で十分と判断）。