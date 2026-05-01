## 観察された事実 (Facts)

- 本分析の前提: 対象は `src/alpha_factory/stage_bc_evaluator.py` と `tests/alpha_factory/test_stage_bc_evaluator.py` の PR 1 範囲であり、詳細設計は `devnotes/20260430-0230-todo-T064-stage-bc-evaluator/detailed-design.md` を参照済み。
- `StagePassStatus` / `SampleSizeFlag` / `MissionFailReason` は 3 enum として実装され、値は設計通り `pass/fail/pending`、`ok/boundary/insufficient`、`live_criteria/cross_pair/stress` です。`src/alpha_factory/stage_bc_evaluator.py:105` `src/alpha_factory/stage_bc_evaluator.py:117` `src/alpha_factory/stage_bc_evaluator.py:130`
- `STAGE_C_LITE_NUM_WINDOWS` は `Final[int] = 3` として定義され、Follow-up の SSOT コメントも付与されています。`src/alpha_factory/stage_bc_evaluator.py:149`
- 指定 dataclass 群は実装されています: `PairBacktestBundle`、`StageBFoldResult`、`StageBResult`、`StageCLiteWindowResult`、`StageCLiteResult`、`StageCResult`、`PoolFoldedInput`、`BCEvaluationInput`、`BCEvaluationResult`。ただし列挙は 9 個で、prompt の「11 dataclass」は名前リスト上は 9 個です。`src/alpha_factory/stage_bc_evaluator.py:205` `src/alpha_factory/stage_bc_evaluator.py:257` `src/alpha_factory/stage_bc_evaluator.py:281` `src/alpha_factory/stage_bc_evaluator.py:304` `src/alpha_factory/stage_bc_evaluator.py:312` `src/alpha_factory/stage_bc_evaluator.py:360` `src/alpha_factory/stage_bc_evaluator.py:388` `src/alpha_factory/stage_bc_evaluator.py:408` `src/alpha_factory/stage_bc_evaluator.py:428`
- `StageCLiteResult` は `n_pass_windows: int` を持ち、`__post_init__` で `0 <= n_pass_windows <= STAGE_C_LITE_NUM_WINDOWS` と `n_pass_windows <= len(per_window_results)` を検証しています。`src/alpha_factory/stage_bc_evaluator.py:334` `src/alpha_factory/stage_bc_evaluator.py:341`
- `BCEvaluationResult` は `c_pass_depth: float` を持ちます。`src/alpha_factory/stage_bc_evaluator.py:442`
- `evaluate_stage_c_lite` は `n_pass_windows = sum(1 for w in per_window_results if w.cf_result.gate_pass)` で deterministic に計算しています。`src/alpha_factory/stage_bc_evaluator.py:858`
- `compute_c_pass_depth` は `n_pass_windows` 値域 guard、`PASS/PENDING/FAIL` の明示分岐、未知値 `ValueError`、`base = n_pass_windows * 0.25`、`base + bonus` を実装しています。`src/alpha_factory/stage_bc_evaluator.py:1243` `src/alpha_factory/stage_bc_evaluator.py:1287` `src/alpha_factory/stage_bc_evaluator.py:1292` `src/alpha_factory/stage_bc_evaluator.py:1293`
- `compute_c_pass_depth` の docstring は、pure function、IEEE 754 exact、未知値 raise、値域 guard、collider bias 独立性、holiday/DST/observability 非依存、stratified audit 非担当を明記しています。`src/alpha_factory/stage_bc_evaluator.py:1262` `src/alpha_factory/stage_bc_evaluator.py:1265` `src/alpha_factory/stage_bc_evaluator.py:1271`
- `evaluate_bc_for_a_pass` は `compute_c_pass_depth(c_lite_result, c_result)` を呼び、その値を `BCEvaluationResult.c_pass_depth` に注入しています。`src/alpha_factory/stage_bc_evaluator.py:1364` `src/alpha_factory/stage_bc_evaluator.py:1373`
- Stage C truth table は `LIVE_CRITERIA > CROSS_PAIR > STRESS` の順に `mission_fail_reason` を設定しています。`src/alpha_factory/stage_bc_evaluator.py:993`
- `filter_to_period` は trade を `period.start <= t.exit_time_utc < period.end`、bar を `period.start <= p.timestamp_utc < period.end` で半開区間フィルタしています。`src/alpha_factory/stage_bc_evaluator.py:587` `src/alpha_factory/stage_bc_evaluator.py:592`
- `build_pooled_oos_input` は `pooled_dd_per_fold_max = max(f.fold_max_dd for f in fold_results)` を計算しています。`src/alpha_factory/stage_bc_evaluator.py:787`
- `compute_gate_pass_excluding_dd` は `slack_sharpe/slack_pnl/slack_tc/slack_wr` の 4 軸だけを使い、`slack_dd` と `cf_result.max_dd` を参照していません。`src/alpha_factory/stage_bc_evaluator.py:1149`
- `compute_a_b_correlation` は `statistics.StatisticsError` を catch し、非有限 corr も含めて `(0.0, sample_size)` に正規化しています。`src/alpha_factory/stage_bc_evaluator.py:1117`
- `select_top_clite_forced_pass_indices` の `_status_rank` は `PASS` と `PENDING` のみ明示分岐し、それ以外は無条件に `2` を返します。`src/alpha_factory/stage_bc_evaluator.py:1215`
- テストは 97 件定義されています。`tests/alpha_factory/test_stage_bc_evaluator.py:347`
- Follow-up の `n_pass_windows` contract test は `dataclasses.fields(StageCLiteResult)` ベースで field 存在と型を確認しています。`tests/alpha_factory/test_stage_bc_evaluator.py:1348`
- Follow-up の `c_pass_depth` contract test は `dataclasses.fields(BCEvaluationResult)` ベースで field 存在と型を確認しています。`tests/alpha_factory/test_stage_bc_evaluator.py:1466`
- `compute_c_pass_depth` の 12 組合せテストは `3 status × 4 n` の二重 loop で実装されています。`tests/alpha_factory/test_stage_bc_evaluator.py:1502`
- `StageCLiteResult.__post_init__` の範囲外 raise と `n_pass_windows > len(per_window_results)` raise はテストされています。`tests/alpha_factory/test_stage_bc_evaluator.py:1390` `tests/alpha_factory/test_stage_bc_evaluator.py:1414`
- `compute_c_pass_depth` の未知 status raise と `n_pass_windows` bypass guard はテストされています。`tests/alpha_factory/test_stage_bc_evaluator.py:1523` `tests/alpha_factory/test_stage_bc_evaluator.py:1534`
- 詳細設計は truth table 優先順位衝突テストとして `live=False > cross_pair=FAIL` と `cross_pair > stress` の両方を追加対象にしています。`devnotes/20260430-0230-todo-T064-stage-bc-evaluator/detailed-design.md:35`
- 実テストには `live=False` と `cross_pair=FAIL` の衝突テストはありますが、`cross_pair=FAIL` と `stress=FAIL` の優先順位衝突を評価経路で検証するテストは見当たりません。`tests/alpha_factory/test_stage_bc_evaluator.py:924`
- `test_stage_c_stress_fail_yields_mission_fail_with_reason_stress` は `evaluate_stage_c` を通さず、`StageCResult` を直接構築して `mission_fail_reason=STRESS` を確認しています。`tests/alpha_factory/test_stage_bc_evaluator.py:875`

## 解釈・推論 (Interpretations)

- enum、主要 dataclass、Follow-up field、`compute_c_pass_depth`、Stage C truth table、半開区間、pooled DD、DD 除外 gate、A/B correlation の主要実装は詳細設計に概ね準拠しています。
- `compute_c_pass_depth` は正常入力ドメインでは no-raise で有限値を返し、契約違反入力では `ValueError` を raise する、という Round 2 で明確化された境界に合っています。
- `compute_c_pass_depth` は `n_pass_windows * 0.25 + {1.0, 0.5, 0.0}` のみなので、要求された `[0.0, 1.75]` の exact な数値計算になっています。
- `StageCLiteResult.n_pass_windows` と `compute_c_pass_depth` は `STAGE_C_LITE_NUM_WINDOWS` を参照しており、Follow-up で問題視された literal `3` の散在は主要ロジック上は回避されています。
- `select_top_clite_forced_pass_indices._status_rank` は、status field 方式の「3 値明示分岐 + 未知値 raise」規範を満たしていません。将来 enum 拡張や mock bypass 時に未知 status を silent FAIL 相当でランキングしてしまいます。
- truth table の実装自体は `LIVE_CRITERIA > CROSS_PAIR > STRESS` ですが、テストは `cross_pair > stress` の衝突を反証できていません。特に stress fail branch は `StageCResult` 直接構築で、`evaluate_stage_c` の分岐ロジックを検証していません。
- contract test は `__dataclass_fields__` そのものではなく `dataclasses.fields()` を使っています。dataclass field API としては妥当ですが、prompt の「__dataclass_fields__ ベース」に厳密一致はしていません。
- Phase 1 では `apply_spread_stress` が未実装で、`spread_stress_supported=True` の評価経路は `NotImplementedError` になります。この制約自体は設計通りですが、Stage C の PASS / STRESS FAIL / CROSS_PAIR vs STRESS 衝突を評価経路でテストするには monkeypatch 等が必要です。

## 指摘事項

### Critical (修正必須)

- 該当なし。

### Warning (修正推奨)

- `select_top_clite_forced_pass_indices._status_rank` が未知 `StagePassStatus` を silent FAIL 相当に扱います。`src/alpha_factory/stage_bc_evaluator.py:1215`  
  修正提案: `FAIL` も明示分岐し、`else: raise ValueError("unknown StagePassStatus...")` を追加してください。併せて mock bypass test を追加してください。

- `cross_pair > stress` の truth table 優先順位衝突テストが欠落しています。`devnotes/20260430-0230-todo-T064-stage-bc-evaluator/detailed-design.md:35` `tests/alpha_factory/test_stage_bc_evaluator.py:924`  
  修正提案: `apply_spread_stress` を monkeypatch して `spread_stress_supported=True` 経路を通し、`live=True, cross_pair=FAIL, stress=FAIL` で `mission_fail_reason == CROSS_PAIR` を確認してください。

- `stress=FAIL` の reason test が `evaluate_stage_c` の分岐ではなく `StageCResult` 直接構築になっています。`tests/alpha_factory/test_stage_bc_evaluator.py:875`  
  修正提案: monkeypatch で stress branch を実行し、`live=True, cross_pair=PASS, stress=FAIL` が `MissionFailReason.STRESS` になることを評価経路で確認してください。

### Suggestion (改善余地)

- contract test のコメントは「`__dataclass_fields__` ベース」と書いていますが、実装は `dataclasses.fields()` です。`tests/alpha_factory/test_stage_bc_evaluator.py:1349` `tests/alpha_factory/test_stage_bc_evaluator.py:1467`  
  修正提案: prompt 厳密準拠を優先するなら `StageCLiteResult.__dataclass_fields__` / `BCEvaluationResult.__dataclass_fields__` に寄せるか、コメントを `dataclasses.fields()` ベースに修正してください。

- prompt の「11 dataclass」と列挙名の 9 dataclass が不整合です。実装は列挙された 9 名と一致しているため、レビュー基準側の数を 9 に修正するのが妥当です。

## Verdict

**NEEDS CHANGES** — 主要実装は設計に概ね準拠していますが、`_status_rank` の未知 status silent handling と `cross_pair > stress` 評価経路テスト欠落が、規範継承と truth table 網羅性の観点で修正対象です。