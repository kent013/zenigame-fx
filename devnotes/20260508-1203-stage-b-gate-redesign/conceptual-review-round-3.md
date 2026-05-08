**Round 3 判定**

Round 2 の **Critical は概念設計レベルでは解消**されています。残る懸念は詳細設計で潰すべき Warning / Suggestion で、全体としては実装設計に進めてよい水準です。

1. DSR の `N=同一 RUN Stage A pass 個体数`

- **Fact**: DSR の説明は selection bias / multiple testing / non-normality 補正に修正されている。
- **Fact**: `N_trials` は「同一 RUN 内 Stage B 評価対象個体数」、つまり Stage A pass row count に固定された。
- **Interpretation**: Stage B gate の conditional selection bias を測る目的なら、この `N` は妥当な近似です。
- **Interpretation**: ただし Bailey & López de Prado の厳密な「全 strategy trial 数」ではありません。全探索空間の過剰試行補正ではなく、「Stage A 通過後の Stage B 比較集合に対する DSR」と明記すべきです。
- **Falsification**: `N=Stage A pass` と `N=全 archive row` で DSR の符号や順位が大きく変わるなら、Phase 2 の gate 化には使えません。
- **判定**: **Warning**
- **修正提案**: `dsr_method` に `conditional_stage_b` を含める。可能なら `dsr_n_trials_stage_b` と `dsr_n_trials_run_total` を両方記録し、Phase 1 では前者のみ monitor 指標として扱う。

2. `trade_count_full_dataset` の Stage B 1 pass 追加コスト

- **Fact**: fold 合算は禁止され、`Stage A unique + Stage B 全期間 1 pass unique` に定義が固定された。
- **Fact**: Stage A / Stage B は partition guard により時系列 disjoint である。
- **Interpretation**: canonical 定義として妥当です。Round 2 の重複カウント Critical は解消しています。
- **Interpretation**: コスト `~10%` は fold 数が概ね 10 前後で、Stage B full pass を Stage B 評価対象だけに限定するなら妥当な見積もりです。
- **Falsification**: 全個体・全世代に無条件で Stage B full pass を追加し、worker RSS が 3GB を超える、または wall time が 20%以上増えるならコスト仮説は棄却です。
- **判定**: **Suggestion**
- **修正提案**: 詳細設計で「計算対象は Stage B 評価対象個体のみ」「trade list は保持せず count 集計後に破棄」「RSS / wall time を log に出す」を明記してください。

3. 二重 opt-in escape hatch

- **Fact**: `--allow-holdout-short` と `ZENIGAME_FX_SMOKE_TEST=1` の二重 opt-in になった。
- **Fact**: archive marker、graduate 禁止、calibrate-gate history append 禁止、report prefix が追加された。
- **Interpretation**: production 誤発動リスクは大きく下がっています。
- **Interpretation**: 「完全に防げる」わけではありません。production 環境に env var が残る、wrapper が flag を渡す、という運用ミスは理論上残ります。
- **Falsification**: smoke override run が通常 report / graduate / history に混入できるなら、この guard は不十分です。
- **判定**: **Warning**
- **修正提案**: `run_mode=production` では override を拒否する条件を追加する。少なくとも `summary.json` と archive row の marker が無い場合は flush 失敗にしてください。

4. H_A1' / H_A3' / H_A4

- **Fact**: H_A1' は `pfre>=0.6` の 2 個体中 1 件以上 pass に修正された。
- **Fact**: H_A3' は single RUN ではなく archive replay top-K 比較に変更された。
- **Fact**: H_A4 は Stage B pass 個体の trade_count 中央値上昇を検証する仮説として追加された。
- **Interpretation**: H_A1' と H_A3' は反証可能性が成立しています。
- **Interpretation**: H_A4 は n が小さい場合、Mann-Whitney U test の有意性主張は弱いです。C7 により n<30 では因果解釈を避けるべきです。
- **Falsification**: H_A1' は 0 件 pass で反証。H_A3' は top-K over-trading 比率が 20%以上低下しなければ反証。H_A4 は中央値が 50 未満、または n<10 なら claim 禁止です。
- **判定**: **Warning**
- **修正提案**: H_A4 は「統計検定」ではなく「記述統計 + n 明示 + effect size」に格下げしてください。n<30 の場合は改善傾向までに留めるのが安全です。

**残懸念**

- **[Warning] DSR は conditional 指標として命名する必要があります。** `N=Stage A pass` は十分に実用的ですが、全探索 trial 補正ではないため、後続 Phase で hard gate 化する前に `N` 感度分析が必要です。
- **[Warning] smoke override は完全防止ではなく混入防止で担保すべきです。** graduate / calibrate / reportable run から構造的に除外できていれば許容です。
- **[Suggestion] H_A4 の検定表現は弱めるべきです。** sample size が小さい可能性が高く、C7 上は有意差 claim より分布観察が適切です。

**全体判定: APPROVED**

概念設計 v2 は Round 2 のブロッカーを解消しています。残る Warning は詳細設計での命名・記録・運用ガード・検証表現の精度問題であり、概念設計を止める理由にはなりません。