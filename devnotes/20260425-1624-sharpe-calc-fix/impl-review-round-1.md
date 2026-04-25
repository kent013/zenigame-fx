**前提（C4）**
- 事実ベースは、提示された「詳細設計全文」と「git diff本文」のみです（追加のファイル読込・コマンド実行なし）。
- 以下は C1/C2/C6/C9 を意識し、まず不一致・破綻リスクの反証観点から確認した結果です。

**S1 `equity_at_entry` 伝搬**
- [Critical] なし
- [Warning] 設計で明記された `tests/broker/test_mock.py` 系の追加が差分に見当たらず、same-bar 複数 fill の `equity_at_entry` 同値性テストの実在を確認できません。
- [Suggestion] [mock.py](/Users/ishitoya/repository/zenigame-fx/src/broker/mock.py):196 と [orders.py](/Users/ishitoya/repository/zenigame-fx/src/broker/orders.py):27 に対応する broker テストを明示追加してください。

**S2 `trade_sharpe_raw` 計算**
- [Critical] なし
- [Warning] [test_metrics.py](/Users/ishitoya/repository/zenigame-fx/tests/backtest/test_metrics.py):90 の正常系が「非 NaN」確認中心で、設計の「期待値との照合（式の厳密検証）」が弱いです。
- [Suggestion] 固定 returns に対し mean/std を手計算し、`_trade_sharpe_raw` の期待値一致を assert するテストを追加してください。

**S3 GA fitness 切替**
- [Critical] なし
- [Warning] なし（`metric="sharpe"` が `trade_sharpe_raw` を参照する点は差分上で一致）
- [Suggestion] [fitness.py](/Users/ishitoya/repository/zenigame-fx/src/ga/fitness.py):76 の `compute_metrics` 呼び出し側でも `trade_count_min_for_sharpe` を明示注入する形に寄せると、S11 と整合します。

**S4 Stage Gate 切替**
- [Critical] なし
- [Warning] なし（A/B/C の参照切替と A/C payload key rename は整合）
- [Suggestion] [stage_gate.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/stage_gate.py):619 付近の stress payload に残る `"sharpe"` 名は将来混乱しやすいため、命名方針コメントを追加すると安全です。

**S5 cross_pair 切替**
- [Critical] [cross_pair.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/cross_pair.py):143 の `compute_metrics(...)` で `trade_count_min_for_sharpe` が明示渡しされておらず、S11 の「全 consumer 明示渡し」要件と不一致です。
- [Warning] `metric_unavailable -> 0.0` の fail-fast は設計通りですが、欠測増加時に aggregate を過度に押し下げる運用リスクがあります。
- [Suggestion] `trade_count_min_for_sharpe` を呼び出し元設定から受け取り、ログに unavailable 件数を出してください。

**S6 calibrate_gate 切替**
- [Critical] なし
- [Warning] [calibrate_gate.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/calibrate_gate.py):408 が accessor 非経由の直接参照で、v1/v2 判定ロジックが他 consumer と重複しています。
- [Suggestion] 変換ヘルパ（version正規化 + finite判定）を共通化し、判定分岐の重複を削減してください。

**S7 Alpha Sieve 切替**
- [Critical] [run_alpha_sieve.py](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_alpha_sieve.py):413 の `compute_metrics(...)` で `trade_count_min_for_sharpe` 未明示。S11 要件との不一致です。
- [Warning] [run_alpha_sieve.py](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_alpha_sieve.py):226 の v1 行無効化は妥当ですが、スキップ件数の可観測性が不足しています。
- [Suggestion] v1/unknown/version-mismatch の件数を warning ログで出してください。

**S8 run_ga live_criteria 切替**
- [Critical] なし
- [Warning] [run_ga.py](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py):509 で unknown version も実質 `None` 扱いですが、warning がなく監査性が弱いです。
- [Suggestion] `version not in {v1,v2}` の集計 warning を追加してください。

**S9 archive schema/accessor**
- [Critical] なし（schema/template/collect の追加は差分上で確認）
- [Warning] accessor 実装は追加済みですが、consumer 側が全面 accessor 経由にはなっておらず（S6/S8/S7）、v1/v2 境界の実装一貫性に揺れが残ります。
- [Suggestion] 「比較系は `get_trade_sharpe` 必須、閲覧系のみ `get_legacy_bar_sharpe`」を lint/規約化してください。

**S10 DSR コメント**
- [Critical] なし
- [Warning] [statistics.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/statistics.py):159 の追記は有用ですが、同 docstring 内で annualized/non-annualized の説明が混在し解釈誤りリスクがあります。
- [Suggestion] 入力前提（単位・年率化有無）を 1 箇所に統一してください。

**S11 config `trade_count_min_for_sharpe`**
- [Critical] S11 の「compute_metrics 全 consumer 明示渡し」は未充足（少なくとも S5/S7 で未対応）。
- [Warning] `config -> GaConfig/StageGateConfig -> consumer` の完全4段接続は、提示差分だけでは確認しきれません。
- [Suggestion] `run_ga` 側で設定値読込を単一ソース化し、fitness/cross_pair/sieve/stage_gate へ明示注入してください。

**S12 テスト網羅**
- [Critical] なし
- [Warning] 設計要件に対し、S1 broker 伝搬テストと S2 計算式厳密照合テストが弱い/未確認です。
- [Suggestion] 既存の archive 互換テストは良好なので、上記2点を補強すれば回帰耐性は十分高まります。

**全体判定: CHANGES_REQUESTED**