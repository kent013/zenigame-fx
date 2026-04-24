## 判定
NEEDS_REVISION

## 前提（C4）
- 現時点で参照できる一次情報は `conceptual-design.md` と `detailed-design.md` の 2026-04-24 版のみであり、実装ファイルの中身は確認していない（ユーザー制約によりコマンド実行不可）。
- Stage C → Sieve への移行条件および `live_criteria` は概念設計 §2.3 で定義されたとおり（sharpe > 0.5 / trade_count ≥ 30 / total_pnl > 0）。
- DSR は Phase 2 では情報表示のみで、ゲート判定には使わない。

## 観点別評価
1. dataclass / 関数 signature: Fact: `SieveConfig`, `CandidateRow`, `SieveEvalResult` は必要な閾値・Stage C メタ・OOS 評価結果をすべて保持しており、`_evaluate_one` での利用とも整合している。Interpretation: Phase 2 の I/O 要件を満たしており問題なし。
2. strict gt vs >=: Fact: `_judge` 実装サンプルでは Sharpe と PnL に `<=`、trade_count に `<` を用い、設計値 0.5 / 0 / 30 をそのまま適用している。Interpretation: 概念設計 §2.3 の境界仕様と一致している。
3. DSR fail-soft: Fact: §2.8 で `_compute_dsr_safe` は `statistics.compute_dsr` を呼び出す予定だが、「実 signature は実装時に確認」と明記されており、戻り値型や必要引数が定義されていない。Interpretation: 現状のままでは `oos_dsr: float | None` というフィールド設計およびレポート描画との整合が検証できず、実装段階で破綻するリスクが高い。詳細設計内で具体的な関数シグネチャ／戻り値の扱いまで確定させる必要がある。
4. backtest_config 引き継ぎ: Fact: `_build_oos_backtest_config` は `initial_cash`, `leverage`, `max_spread_bps`, `holding_cost_per_day_bps`, `session_close_utc_hours`, `bar_minutes` しかコピーせず、`config/alpha_factory/default.yaml` の既定値 `[23]/0/None` を根拠なく再掲している。一方で「summary から backtest_config を引き継ぐ」と記載されており、他のコスト・制約パラメータ（手数料、max_position_bars 等）が落ちる可能性がある。Interpretation: 引き継ぎ要件を満たす保証がないため、ここも再設計が必要。
5. private import: Fact: §5 で `scripts/alpha_factory/run_ga._bar_row_to_price_bar` を `_` 付きの私的関数として直接 import する方針が記載され、Phase 4 で共通モジュールに抽出する TODO が添えられている。Interpretation: 一時的措置としては許容できるが、依存が壊れた際に Sieve 側だけ気づけないため、抽出の期限や失敗時のフォールバックを設計段階で明示しておくと良い（推奨事項に留める）。
6. テストカバレッジ: Fact: 13 ケースの大半は `_judge` の境界、Stage C フィルタ、エラー系フローに集中しており、(a) 正常系 `_evaluate_one`（bars あり・通過/不通過両方）、(b) DSR fail-soft（`compute_dsr` が例外 or 未定義）の確認、(c) `_build_oos_backtest_config` が summary のカスタム値を引き継げているか、がテストされていない。Interpretation: フェイルソフト仕様と引き継ぎ要件を担保する肝心のケースが欠落しているため追加が必要。

## 修正要求
- [ ] `_compute_dsr_safe` と `statistics.compute_dsr` の実シグネチャ／戻り値型を詳細設計上で確定し、`SieveEvalResult.oos_dsr`・レポート表示と矛盾しないことを明示する（例: `compute_dsr(trades: list[Trade], sharpe: float) -> float` なのか、別データ構造を返すのかを定義）。
- [ ] `_build_oos_backtest_config` が GA 実行時の BacktestConfig を完全に再現できるよう、summary/backtest_config からどのフィールドをコピーするかを網羅的に列挙し、既定値を `config/alpha_factory/default.yaml` の該当キーに紐付けて根拠を示す（必要なら `BacktestSectionConfig` 再利用や YAML 直接ロードを設計に追加）。

## 推奨事項
- 共有ヘルパを `src/alpha_factory/bars_loader.py`（仮）に早期抽出し、`run_ga` と `run_alpha_sieve` からの私的 import 依存を Phase 2 のうちに解消しておくと将来のスクリプト分離が容易になる。