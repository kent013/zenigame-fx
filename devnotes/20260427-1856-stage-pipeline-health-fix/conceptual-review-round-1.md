**本レビューの前提**
- `verified` 与えられた埋め込みデータ上、`calibrate-gate` の履歴には `run_20260426_145502 -> new_threshold 0.0778`、`run_20260426_183119 -> new_threshold 0.1778` が記録されている。
- `verified` 与えられた埋め込みデータ上、run-24 では `stage_a_threshold: 0.0`、Stage B は 3745 個体すべて `all_folds_unavailable` 系 reason、`n_fold_effective=0` とされている。
- `verified` 与えられた埋め込みデータ上、現行環境は Python 3.11.15、Numba 0.65.1、NumPy 2.4.4、T053 は main 済みである。
- `unverified` レビュー対象は後半の「Stage A→B Pipeline Health Fix」概念設計であり、前半の T053 設計は背景文脈としてのみ含まれている。
- `unverified` `run_20260426_145502` と `run_20260426_183119` は、比較対象として十分に同一条件（コード、データ期間、設定、実行モード）である。
- `unverified` run summary の `stage_a_threshold` は「実際に評価で使われた閾値」を正しく表している。
- `unverified` `calibrate-gate` の伝搬経路は存在しない、または壊れている。存在するが未発火、別 source of truth、summary 表示ずれ、の可能性は未排除。
- `unverified` Stage B は実際に 18 ヶ月ぶんの bar を参照できており、「理論上 47 fold 組める」は実データでも成立する。
- `unverified` 本番 4 時間の支配コストは Stage B である。
- `unverified` `all_folds_unavailable` はコード回帰であり、データ境界条件や仕様変更の帰結ではない。

Round 1 の反証焦点は次の 3 点です。  
1. 「Stage B が 4 時間の支配コスト」という主張を崩せるか。  
2. 「calibrate 伝搬不全」という診断を別説明で置き換えられるか。  
3. 「突然の回帰」という解釈を、データ不足・表示ずれ・仕様変更で説明できるか。  

**全体判定: CHANGES_REQUESTED**

**1. 使命との整合性**
- `[Warning]`
  - Fact: Stage C 通過 0、Stage B 全 fold unavailable という観測は、評価 pipeline の健全性に重大な疑義を示している。
  - Interpretation: 「まず pipeline を機能させる」は使命整合的です。ただし「4 時間問題の支配コストが Stage B」という速度主張は未検証で、使命上の優先理由は速度ではなく「評価経路が閉じている疑い」に置くべきです。
  - 修正提案: 目的文を「性能改善」ではなく「Stage B evaluability の回復」に修正し、速度改善は副次仮説に格下げしてください。

**2. 禁止事項違反**
- `[Critical]`
  - Fact: 提案 A は `history.jsonl` の最新 `new_threshold` を `run_ga.py` 起動時に自動 override する方針です。
  - Interpretation: source of truth を確認せずにこれを入れると、設定ファイル、history、summary の三重管理になり得ます。これは実験再現性を壊し、結果として「GA の見せ方を変えるための threshold 操作」に近い副作用を持ちます。
  - 修正提案: 先に「threshold の正規 source of truth は何か」を設計で固定してください。`config` 永続反映型、`state file` 型、`runtime override` 型のどれか 1 つに絞るべきです。少なくとも `instrument / lane / config fingerprint / dataset fingerprint / applied_from_run_id` を record に持たない限り「最新 history を読む」は危険です。
- `[Suggestion]`
  - 施策 C の観測追加自体は禁止事項違反ではありませんが、A/B の原因特定前に入れるとスコープが膨らみます。後段に回すのが妥当です。

**3. 実現可能性**
- `[Critical]`
  - Fact: `history.jsonl` に threshold 更新記録があり、summary は 0.0 を示しています。
  - Interpretation: これは「伝搬経路が無い」ことの証明ではありません。少なくとも 4 通りあります。`1)` 経路なし、`2)` 経路ありだが条件未充足、`3)` 実適用済みだが summary 表示が 0.0、`4)` 別 source of truth が優先。
  - 修正提案: 実装前 deliverable として V0 を追加してください。
    - V0-A: threshold source-of-truth 図
    - V0-B: `run_ga` 起動時に使われた effective threshold の実測ログ
    - V0-C: summary field が effective threshold を表すかの確認
- `[Critical]`
  - Fact: 設計は「18 ヶ月なら理論上 47 fold」としています。
  - Interpretation: 実際に Stage B が 18 ヶ月の bar を取得できていることは未検証です。提示テキストには別箇所で `dataset.start=2025-10-01`, `dataset.end=2026-04-01` の 6 ヶ月設定もあり、これと整合していません。ここが false なら `all_folds_unavailable` は単なるデータ不足で説明できます。
  - 修正提案: Git diff より先に、両 run で Stage B に渡った実 bar 期間を出してください。比較項目は `bars_stage_b[0].time`, `bars_stage_b[-1].time`, `len(bars_stage_b)`, `constructed_fold_count`, `invalid_fold_count_by_reason` です。
- `[Warning]`
  - Fact: run-24 で全 3745 個体が同一 reason code です。
  - Interpretation: これは強い異常信号ですが、直ちに単一 commit 回帰とは言えません。データ regime、入力バー不足、fold validity 仕様変更でも起こります。
  - 修正提案: `git diff` 調査は必要ですが、その前提に「同一条件再現」を追加してください。

**4. 期待効果の妥当性**
- `[Critical]`
  - Fact: Stage 別の wall-clock profile は提示されていません。
  - Interpretation: `4h -> 1.5-2.5h` は根拠が弱いです。むしろ Stage B が今「早く失敗」しているだけなら、正常化後に runtime が増える可能性もあります。A で通過率を下げれば減る、B で fold が実際に回り始めれば増える、の両方向があり、現状では符号すら確定していません。
  - 修正提案: 期待効果を二分してください。
    - 機能目標: `all_folds_unavailable` 一色を解消する
    - 性能目標: 修正後に stage-wise timing を再計測してから設定する
- `[Warning]`
  - Fact: 「突然変わった」の根拠は実質 `834 -> 0` の境目 1 点です。
  - Interpretation: 強い回帰シグナルではありますが、C7 的には「単一切替点」断定はまだ早いです。
  - 修正提案: 少なくとも前後 3-5 run の同一指標列を並べ、コード差分ではなくまず現象差分を固定してください。
- `[Critical]`
  - Fact: V2 は `pop=8, gen=2` の小規模 run で `stage_a_pass_rate ≈ target_pass_rate` を合格基準にしています。
  - Interpretation: これは 24 eval 程度で、`min_sample_size: 30` 未満になり得ます。C7 に反します。
  - 修正提案: V2 から pass-rate 近似判定を外してください。代わりに「override が読まれた」「effective threshold が期待値」「reason code が単色でない」を見るべきです。pass-rate 検証は `n>=30` か複数 seed で行ってください。

**5. リスク**
- `[Critical]`
  - Fact: V4 は「T053 後 archive Parquet と本修正後 archive Parquet で per-genome 指標が allclose」を要求しています。
  - Interpretation: これは acceptance test として不適切です。今回の修正は Stage A threshold 適用と Stage B fold validity に触れるため、stage gate 出力が変わるのはむしろ正常です。バグ基準の archive と一致しないこと自体は失敗条件になりません。
  - 修正提案: 同値性対象を「影響を受けない下位層」に限定してください。例えば同一 genome・同一 bars に対する backtest summary、または T053 の composite/backtest 数値契約は固定。Stage A/B 判定値は新 oracle で別検証です。
- `[Warning]`
  - Fact: `history.jsonl` には run_id はありますが、埋め込みテキスト上は config fingerprint や dataset fingerprint は見えません。
  - Interpretation: 最新 record 自動適用は cross-run contamination の危険があります。
  - 修正提案: record に少なくとも `config_hash`, `dataset_span`, `instrument`, `stage_gate_version` を追加し、不一致なら適用しないでください。

**6. スコープの適切さ**
- `[Warning]`
  - Fact: 施策 C は `run_report` と observation template 更新まで含みます。
  - Interpretation: A/B の root cause 未確定段階では scope creep です。悪い変更ではありませんが、blocking issue ではない。
  - 修正提案: TODO を分離してください。今回の Done 条件からは C を外し、A/B 修正後の follow-up に回すのが適切です。
- `[Suggestion]`
  - 進行順序の `B -> A` は妥当です。ただし評価は `B 単独で固定 candidate set`, `A 単独で threshold 反映`, `A+B end-to-end` の 3 段に分けた方が切り分けやすいです。

**7. メモリ制約**
- `[Suggestion]`
  - Fact: 今回の設計は T053 のような新しい大規模 ndarray 導入ではなく、主に control-flow と stage-gate 観測の修正です。
  - Interpretation: 24GB / 6 worker / 1 worker 3GB の制約に対する新規メモリリスクは、この設計単体では高くありません。
  - 提案: ただし Stage B 調査で fold ごとの詳細 trace を保持する場合は、debug mode 限定にし、archive へ恒久保存しない方がよいです。

**8. 前提検証 (C4)**
- `[Critical]`
  - Fact: 設計文中に verified / unverified の明示表がありません。
  - Interpretation: 本件は前提依存が強く、ここが曖昧なまま実装に入ると誤修正の確率が高いです。
  - 修正提案: 設計本文に前提表を追加してください。最低限以下は分けるべきです。
    - verified: `history` に threshold 記録がある
    - verified: run-24 は `n_fold_effective=0`
    - unverified: summary threshold は effective threshold を表す
    - unverified: Stage B は 18 ヶ月データを見ている
    - unverified: `all_folds_unavailable` は code regression
    - unverified: Stage B が runtime 支配
- `[Warning]`
  - Fact: 設計は `[stage_gate.py:614](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/stage_gate.py#L614)` の reason code 追加行を根拠の一部にしています。
  - Interpretation: C1/C2 の観点では、その行の存在だけで bug claim はできません。fold 生成、bar slicing、invalidation 理由の集計まで見ないと危険です。
  - 修正提案: 調査対象を `[stage_gate.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/stage_gate.py)`, `[walk_forward.py](/Users/ishitoya/repository/zenigame-fx/src/backtest/walk_forward.py)`, `[run_ga.py](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py)` の 3 点セットで固定してください。

**9. Design-first 原則 (C1)**
- `[Warning]`
  - Fact: 現時点の設計は raw データと仮説を持っており、方向性はよいです。
  - Interpretation: ただし fix 方針が一歩早いです。特に施策 A の startup hook は、設計より先に実装案が固まっています。
  - 修正提案: 実装前成果物として `investigation note` を 1 枚入れてください。必要なのは「どう直すか」ではなく、まず「どこが source of truth で、何が壊れたのか」です。

**総括**
- Fact: `calibrate-gate` の記録値と summary の閾値表示は食い違っており、run-24 の Stage B は全個体 `all_folds_unavailable` です。
- Interpretation: 「pipeline health を最優先で直す」という判断自体は妥当です。ただし、現設計は root cause の切り分け前に fix を具体化しすぎており、性能効果も過大に見積もっています。

**最低限の修正要求**
1. 目的を「速度改善」ではなく「Stage B evaluability 回復」に修正する。  
2. 施策 A は source-of-truth 確定前の `history.jsonl` 自動 override 案を保留し、調査 deliverable を先に置く。  
3. 施策 B は Git diff 前に、実 bar 期間と fold 構築数の実測を入れる。  
4. V2 の pass-rate 判定と V4 の archive 同値性判定を差し替える。  
5. 施策 C は別 TODO に分離する。  

この 5 点が入れば、設計は「実装してよい仮説検証計画」に近づきます。現状のままでは、原因を取り違えた修正を入れるリスクが高いです。