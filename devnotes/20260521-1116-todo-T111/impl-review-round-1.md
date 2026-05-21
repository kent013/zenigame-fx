**レビュー結果（提示差分ベース）**

1. **[Warning] fold overlap 判定が境界重複を見逃す可能性**
- 対象: [pareto_features.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/pareto_features.py:156)
- `cur.period_end > nxt.period_start` だと、`period_end == next_start` のケースを許容します。  
  `period_end` を「最後の bar 時刻（実質 inclusive）」として保持しているため、同一 timestamp 重複が fold 間に混入しても検知できない可能性があります。
- T111 の「Stage B pooled OOS 軸の観測精度」に直結するため、`>=` 判定か、fold 本来の half-open period (`[start, end)`) を明示的に保持して検証した方が安全です。

2. **[Warning] fold period を bar 由来で再構成しており、設計意図の off-by-one 監査力が弱い**
- 対象: [stage_gate.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/stage_gate.py:1515)
- `period_start/end` を `_c_bars.points[0/-1].timestamp_utc` から作っており、fold 定義そのものではなく「変換後データ」に依存しています。
- 設計要点の「period 再フィルタ起因の落ちを避ける」「fold artifact 直消費」の観点では、fold 構造体側の test period をそのまま記録した方が契約が強くなります。

3. **[Suggestion] `pareto_axis_usable=True` 時の finite assert が不足**
- 対象: [diagnostics_collector.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/diagnostics_collector.py:363)
- 現状は `None` でないことのみ assert。設計文脈では「3 scalar finite」まで invariant にしたいので、`math.isfinite` も合わせて検証すると堅くなります。

---

**重点確認 (a)-(d)**

1. **(a) bit-exact 不変性**:  
`selection/gate/judgment/archive` への直接変更は見当たらず、概ね維持できています（LOG_ONLY 実装）。

2. **(b) MP 境界の重い配列漏れ**:  
`payload` には `ParetoFeaturesLite` の scalar のみで、配列漏れは見当たりません。

3. **(c) no-raise 隔離**:  
`try_build_pareto_lite_from_stage_b_fold_artifacts` が全例外捕捉して `unusable` に落とすため、隔離は成立しています。

4. **(d) pooled threshold 整合 / Stage B 完結性**:  
`derive_stage_b_thresholds` を利用しており方向性は整合。`mission_inf_gap` も `b_pooled_cf` 起点で Stage B 完結になっています。

---

**各ファイル判定**

1. [diagnostics_collector.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/diagnostics_collector.py): **Suggestionあり**
2. [diagnostics_sidecar.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/diagnostics_sidecar.py): **OK**
3. [pareto_features.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/pareto_features.py): **Warningあり**
4. [stage_gate.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/stage_gate.py): **Warningあり**
5. [swim_lane.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/swim_lane.py): **OK**
6. [test_diagnostics_collector.py](/Users/ishitoya/repository/zenigame-fx/tests/alpha_factory/test_diagnostics_collector.py): **OK**
7. [test_diagnostics_sidecar.py](/Users/ishitoya/repository/zenigame-fx/tests/alpha_factory/test_diagnostics_sidecar.py): **OK**
8. [test_pareto_features.py](/Users/ishitoya/repository/zenigame-fx/tests/alpha_factory/test_pareto_features.py): **OK（ただし境界重複ケースの追加推奨）**

---

**全体判定: `CHANGES_REQUESTED`**

主因は `pareto_features` の fold 境界判定と `stage_gate` の period 記録方法です。ここを修正すれば、T111 の観測品質と設計一致がかなり安定します。