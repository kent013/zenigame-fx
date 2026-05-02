**全体判定: CHANGES_REQUESTED**

提供テキスト上では Round 1 の主要 5 件は大半が解消されていますが、Round 2 の設計には新たに 1 件 Critical、1 件 Warning が残ります。特に `preflight_underfilled` 分岐の `continue` は、実装すると既存の Stage B diagnostics / archive collect 経路を飛ばす可能性があり、観測配線の範囲を超えた挙動変更になり得ます。

**前提**
- 仮説: T081 Step 1 は GA 挙動を変えず、AB divergence の観測値だけを追加するべき。
- 成功条件: 既存 Stage A/B/C 評価フローを不変に保ち、score source mixing を防ぎ、欠損・preflight・noop を観測可能にすること。
- 検証範囲: コマンド実行なし。提供された Round 2 テキストと抜粋コードのみをレビュー対象とします。
- C3 conditioning set: `A passed` かつ `real Stage B evaluated` かつ `finite score pair` の集合です。全 population の A/B 相関ではありません。

**Fact**
- `ab_score_pairs` は `dict` から `list[tuple[float, float]]` に変更され、key 衝突は設計上消えています。
- `ab_score_source` は `"fitness_pen+median_oos_sharpe_phase1"` / `"noop"` で識別され、run 内 mixing は `RuntimeError` で検出されます。
- `ab_b_evaluated_count` と `ab_excluded_preflight_count` が追加され、preflight 除外の可視化が設計されています。
- legacy / via_evaluator / noop の 3 経路に必須 4 キーを追加する方針です。
- テスト計画は 6 件から 13 件に拡張されています。

**Interpretation**
- key 衝突、最低限の経路 parity、preflight 除外の不可視性は Round 2 で実質解消されています。
- `fitness_pen` / `median_oos_sharpe` の Phase 1 採用は、SSOT 完全統一ではありませんが、source annotation と混在禁止があるなら Step 1 の観測用途としては許容可能です。
- ただし `preflight_underfilled` 分岐で `continue` する設計は、既存の Stage B 処理を短絡する危険があります。
- `ab_score_source` が log / summary のみで、`observability.json` または cross-run state に永続化されない場合、Step 6 で cross-run source mixing を防げません。

**Round 1 指摘の解消確認**
- [Critical] SSOT 乖離: `APPROVE_WITH_WARNING`。Stage A が canonical 5 を持たない前提なら Phase 1 は妥当。ただし `score_source` は log だけでなく永続化対象にしてください。
- [Critical] key 衝突: `APPROVE`。`list` 化で `genome_name` unique 性への依存が消えています。
- [Critical] legacy / via_evaluator 契約: `APPROVE_WITH_TEST`。3 経路への必須 4 キー追加と parity test 方針で十分です。
- [Warning] preflight 除外の不可視性: `APPROVE_WITH_WARNING`。count/log 追加は妥当ですが、既存 Stage B 処理を飛ばさない実装が必要です。
- [Warning] テスト不足: `APPROVE_WITH_SUGGESTION`。13 件は概ね十分です。stub constructor の互換性テストを追加すると安全です。

**Critical**
- [Critical] `preflight_underfilled` 分岐の `continue` は既存挙動を壊す可能性があります。  
  修正案: preflight 個体は AB pair 収集だけ除外し、既存の `_build_preflight_b_result` 後の archive collect / diagnostics record / `b_result.passed` 判定は維持してください。実装形は `should_collect_ab_pair = not preflight_underfilled` のような flag にし、早期 `continue` は使わない方が安全です。

**Warning**
- [Warning] `ab_score_source` は run 内 mixing 検出だけでは不十分です。  
  修正案: `observability.json` か Step 6 の `q-force-state.json` に `ab_score_source` を保存し、cross-run 集計時は source 不一致の過去 record を無視または別系列扱いにしてください。cross-run source 差分で現行 run を停止する必要はありません。
- [Warning] `RuntimeError` は run 内 mixing には妥当ですが、将来の source migration では fail-closed が過剰になる可能性があります。  
  修正案: run 内は `RuntimeError`、cross-run history は `source mismatch -> skip old record + warn` に分けてください。
- [Warning] `AB_MIN_ACTIONABLE_PAIRS=10` と C7 の `n<30` discipline は解釈上分離が必要です。  
  修正案: `10<=n<30` は計算 status `ok` でも、q_force 自動判断では causal / robust claim を避ける注記または追加 guard を Step 6 に入れてください。

**Suggestion**
- [Suggestion] stub default constructor 8 件の export は妥当です。既存 `build_stub_run_observability_report` が同じ JSON を返す golden/equality test を追加すると互換性を明確にできます。
- [Suggestion] `.get(default)` は移行期互換として妥当ですが、3 経路更新後は parity test で必須キー存在を強制してください。実運用コードで silent missing を許すと配線漏れに気づきにくくなります。
- [Suggestion] all lane inactive で `ab_score_source is None -> "noop"`、`n_pairs=0 -> insufficient_data` は妥当です。専用テストを 1 件足すと退行防止になります。
- [Suggestion] `math.isfinite(float(score))` は非数値型で例外になり得るため、payload が常に numeric である前提を test か helper で固定してください。

**個別論点判定**
- score_source mixing 検出: `APPROVE_WITH_WARNING`。run 内 fail-fast は妥当、cross-run は skip/warn に分離すべき。
- list ベース集約メモリ: `APPROVE`。想定規模では軽量で、10x でも問題なし。
- stub default constructor export: `APPROVE_WITH_TEST`。互換性 test を追加すれば安全。
- 必須 4 キー化: `APPROVE`。legacy / via_evaluator / noop の parity test 前提で妥当。
- `noop` 集約挙動: `APPROVE`。全 inactive run は `"noop"` log + insufficient data で自然です。
- Step 1 全体: `REQUEST_CHANGES`。preflight 分岐の早期 `continue` と source 永続化方針を直せば承認可能です。