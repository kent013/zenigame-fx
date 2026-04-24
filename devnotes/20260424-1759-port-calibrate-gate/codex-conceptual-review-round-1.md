## 判定: REVISE

## 全体所感
Phase 2 で `LLM` ではなく deterministic に寄せる判断自体は妥当です。  
ただし現状案は「Stage A 通過率を合わせること」が強く前面に出ており、North Star である `live_criteria を満たす Stage C 通過個体を 1 つ見つける` との従属関係がまだ弱いです。加えて、集計単位と制御則の説明に不整合があり、このままだと実装時に別物になりやすいです。

## 観点別評価
1. 使命との整合:
   事実: 本設計が直接制御するのは `stage_a.threshold` で、最適化対象は `target_pass_rate=0.15` です。  
   解釈: Phase 2 の局所制御としては成立しますが、現文面だと `target_pass_rate 達成` が半ば目的化しています。これは禁止 #2/#3 に近づくリスクがあります。`target_pass_rate は探索圧の健全性指標であり、使命そのものではない` と明記し、少なくとも `Stage B/C 到達数` や `live_criteria までのギャップ` を監視指標として併記すべきです。

2. アルゴリズムの妥当性:
   事実: 制御則は `dead-band` の外に出たら `q_target` へスナップし、`max_delta` で 1 Run あたりの変化量だけを制限する形です。  
   解釈: これは「PID-like の P 項」というより、`bounded quantile tracking with hysteresis` です。外れた瞬間に誤差量ではなく分位点へ飛ぶので、P 制御と呼ぶのは不正確です。制御そのものは成立し得ますが、他の適応機構や run-to-run 分布変化があると overshoot / oscillation の余地があります。少なくとも名称修正と、振動抑制の前提条件を明文化すべきです。

3. failure mode 網羅性:
   現状は不足です。`archive 0 件`、`n<10 かつ全 fail`、`yaml IO 失敗` はありますが、少なくとも以下が未整理です。  
   `全 fail かつ n>=10`、`全 pass`、`fitness_pen が全同値 / IQR≈0`、`NaN / 欠損列 / schema mismatch`、`Parquet は読めるが対象 run の lane/generation が偏っている`。  
   特にゼロ分散時は quantile-snap が意味を失います。

4. deterministic vs LLM の選択:
   正しいです。Phase 2 の責務は「pass rate 制御の再現可能な自動化」で十分で、ここで判断自由度を増やす必要はありません。`LLM` を別 TODO に分離した判断は妥当です。

5. dead-band の根拠:
   根拠が弱いです。`2700 評価だから ±135 個体` は単なる個数換算で、独立試行性も世代内相関も考慮していません。  
   `±5pt` を暫定既定値として置くのはよいですが、「ノイズだから」ではなく、`generation 単位のばらつき`、もしくは `過去 Run の実測変動幅` を根拠に置くべきです。現状説明では恣意的に見えます。

6. survivor bias 対処:
   ここは設計の中核で、現状のままでは弱いです。  
   事実: 本文では `actual = 全行平均` と定義しつつ、背景節では「中央値ベースで判断」と書いています。  
   解釈: 指標定義が二重化しています。また、全世代平均は初期探索世代を重く数え、後半の選抜後分布を薄めます。次 Run の threshold 更新に使う推定量としては、`last_k generations`、`generation-weighted mean`、`EWMA` のいずれかを今の TODO に含めるべきです。これは別 TODO 送りにしてよい性質ではありません。

7. 他の自動調整機構との衝突:
   未記述で不十分です。`plateau_mutation_bump` などが同じ Run 近傍で探索圧を変えるなら、`threshold` 変更との合成で因果が読めなくなります。  
   少なくとも `適用順序`、`同一 Run で複数アクチュエータが変化した場合のログ`、`片方が動いた直後は片方を凍結するか` の方針が必要です。

8. SSOT 整合:
   階層自体は概ね妥当です。`stage_gate.stage_a.calibrate.*` は自然です。  
   ただしキー名は少し曖昧です。`tolerance_band` は何の単位か不明瞭なので、`pass_rate_tolerance_abs` のようにした方が安全です。`max_delta` も `threshold_delta_abs_max` の方が誤読が減ります。加えて、集計方式を SSOT に載せるなら `aggregation_mode` か `generation_window` も必要です。

9. Out of scope 切り分け:
   `LLM 判断` と `per-lane 化` を別 TODO に分けるのは正しいです。  
   ただし `generation 横断平均の扱い` まで out of scope に置くのは切り分けミスです。これは v2 機能ではなく、今回の推定量の正しさに直結します。

## 必須修正点（REVISE のみ）
- `target_pass_rate` を使命そのものとして扱わないことを明文化し、`Stage B/C 到達数` か `live_criteria gap` を従属監視指標として設計本文に追加すること。
- `actual` の定義を一本化すること。本文中の「中央値ベース」と「全行平均」が矛盾しているため、どちらを採るか明示し、推奨は `generation-aware aggregation` に修正すること。
- `survivor bias` 対策を別 TODO から本 TODO に引き戻すこと。最低でも `last_k generations` か `generation-weighted mean / EWMA` のいずれかを今回の設計に含めること。
- 制御則の説明を `PID-like P` から修正し、`quantile-snap + hysteresis + delta clamp` として記述し直すこと。加えて、他の自動調整機構との相互作用ルールを追加すること。
- failure mode を拡張すること。少なくとも `全 fail n>=10`、`全 pass`、`ゼロ分散`、`NaN / schema mismatch`、`atomic yaml update` を明示すること。
- `calibrate` 配下のキー名を単位が分かる形に寄せること。特に `tolerance_band` と `max_delta` は曖昧です。

## 推奨改善点（任意）
- `dead-band=±5pt` は「既定値」ではなく「仮説値」と位置づけ、将来の見直し条件を先に書いておくと設計が締まります。
- 構造化ログに `generation別 pass rate` と `used aggregation scope` を入れると、後で因果を追いやすいです。
- `q_prev_pass ≒ prev` は ties や clamp の影響で崩れるので、整合確認用として使うなら「参考値」であることを明記した方が安全です。