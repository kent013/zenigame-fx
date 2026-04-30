## Verdict
NEEDS_REVISION

## 前提 (C4)
- Verified: 評価対象は提示された「概念 Round 3 SSOT」と「詳細設計本文」のみで、実コード・grep実行はツール制限により未検証（C8）。
- Verified: Round 1 falsification-firstとして、正常系より先に sentinel 経路、互換境界、責務境界（library vs caller）の反証を優先。
- Assumption: Phase 1 は純ライブラリ実装で、GA runner 本体の改修は同PRに含まれない。
- Assumption: `deflated_sharpe_ratio` は既存仕様通りで数式不変。

## Critical
- [C1] Fact: `_make_sentinel_metric(*, status, null_model, n_observations)` が keyword-only なのに、4.1 の各呼び出しが位置引数（例: `_make_sentinel_metric("insufficient_data", null_model, n)`）。Interpretation: sentinel 全分岐が実行時 `TypeError` になり得るため、詳細設計段階で修正必須。
- [C2] Fact: 4.1 Step0 で `insufficient_trials` 時に `n_observations=0` 固定。Interpretation: 3.3 の「`n_observations` 実測値」定義と整合せず、監査情報を欠落させる。

## Warning
- [W1] Fact: AuditNullModel の I-1→I-6 は列挙されているが、raise順序保証の実装規約・テスト観点が明文化されていない。Interpretation: 要件2の順序依存を回帰で壊すリスクが残る。
- [W2] Fact: AuditDSRMetric は 5値 status 前提だが、`_make_sentinel_metric` の `status` 型が詳細上で固定されていない。Interpretation: `not_implemented`（Scaffold専用）が誤流入する静的防止が弱い。
- [W3] Fact: schema helper は「MAJOR不一致=raise」「受信MINORが新しい=warning」のみ規定。Interpretation: `received minor < expected minor` と不正フォーマット（例 `1.a`）の扱いが未定義。
- [W4] Fact: F31-F35 は caller dedup を mock 検証とあるが、`cache hit を raw に含めない` の契約境界（入力面/責務面）が曖昧。Interpretation: SSOT 7/8 の担保が弱い。
- [W5] Fact: C2 grep語が6語固定。Interpretation: `sharpe_ratio`/`Sharpe`/`deflated` 等の表記差分経路を取りこぼす可能性がある。
- [W6] Fact: collider bias 対策が PR description テンプレート中心。Interpretation: T071/T058 連携時に検証可能な DoD になっておらず、運用依存が強い。

## Suggestion
- [S1] `compute_dsr_strata_with_allowlist` に将来拡張点（例: `schema_version`/`flag_namespace`）を先に置き、T058 archive経由へのAPI移行コストを下げる。
- [S2] `statistics.py` docstring同期は同PR維持しつつ、コミットを「doc同期」と「audit実装」で分けてレビュー衝突を減らす。
- [S3] `AuditDSRMetric` の hash/eq は仕様上問題ないが、運用上は metric 単体をキーにせず `genome_id` キーを原則化して衝突誤解を防ぐ。

## test_id 1:1 ギャップ
- F5-F12: invariant個別検証に加えて「失敗優先順位（I-1→I-6）」の順序テストが必要。
- F13-F22c: `_make_sentinel_metric` の keyword-only 呼び出し保証、`status="not_implemented"` 拒否ケースを明示追加すべき。
- F31-F35: `raw_count_status="unknown"` 経路と「cache hit 非加算」の明示アサーションを追加すべき。
- F36-F38: `received minor < expected minor`、不正フォーマット入力（`1`, `1.a`, `1.0.0.1`）の期待挙動テストが不足。
- F39-F40: `allowlist` 未指定時の interaction 非計算保証、`n<30` warning 発火の機械検証を追加すべき。
- F41-F42: grep語彙拡張版（`sharpe_ratio` 等）をDoDに追加すべき。

## C2 parallel-path grep DoD 確認
- 実grepは未実施（ツール制限のため INCONCLUSIVE）。
- DoD語彙は現行6語に加えて `sharpe_ratio`, `Sharpe`, `deflated`, `audit_calc_version`, `trial_counting_policy_version` を追加推奨。
- 「`audit.py` を src から import 0件（testsのみ）」は、実測ログ添付がない限り設計時点では未検証扱い。

## 学術文献 (任意)
- なし

## 総評
Round 3 SSOT の主要論点（W1-W5/S1-S4）は概ね詳細へ落ちていますが、現状は sentinel 経路の呼び出し仕様不整合（Critical）と観測値定義のズレ（Critical）が残っており、このままでは実装後に即時不具合化する可能性が高いです。まずは `_make_sentinel_metric` 呼び出し規約と `n_observations` の定義整合を先に収束させるべきです。

次点で、schema互換境界・dedup責務境界・collider bias の「検証可能性」をテスト/DoDに落とし込めば、C1-C9 discipline に沿った監査耐性はかなり高まります。現段階の判定は `NEEDS_REVISION` が妥当です。