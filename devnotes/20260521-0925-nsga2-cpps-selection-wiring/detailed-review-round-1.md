**前提検証 (C4)**
- Fact:
  - 提示された `mission_inf_gap.py` 断片では、`evaluate_mission_inf_gap` は `slacks: Mapping[str, float]` を受けて `float` を返す契約に見えます。
  - 提示された `nsga2_selection.py` 断片では、`run_generation_selection` は `IndividualEvaluation`（`bc_result`, `mission_gap`, `invariant_flags` を含む）を必須契約にしています。
  - 提示された `diagnostics_collector.py` 断片では、`record_stage_b` は現状 `passed` しか受けません。
- Interpretation:
  - 詳細設計の「verified 前提」とコード断片に契約齟齬があるため、そのまま実装すると P3/P5a で contract 破綻リスクがあります。

## P3: ParetoFeaturesLite sidecar
**判定: REQUEST_CHANGES**

- [Critical] `evaluate_mission_inf_gap(b_pooled_cf_result)` の契約が不明確です。断片上は `slacks` 入力なので、`CanonicalFiveResult` 直渡しは不整合の可能性があります。  
  修正案: [`/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/mission_inf_gap.py`] に `compute_stage_b_mission_inf_gap(cf_result)` の専用関数を新設し、内部で Stage B のみから slacks を導出して `mission_inf_gap` を返す形で型・経路を固定してください。
- [Warning] schema bump 後方互換の方針が「guard を緩く」のみで不十分です。既存 Parquet reader が strict schema の場合に壊れます。  
  修正案: 旧版読み込みテストを追加し、欠損列を `null` 補完する reader を [`/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/diagnostics_sidecar.py`] 側で明示実装してください。
- [Suggestion] `source_stage` を列として明示 (`"B"` 固定) すると逆流監査が機械化できます。

## P5a: NSGA-II only selection
**判定: REQUEST_CHANGES**

- [Critical] `run_generation_selection(IndividualEvaluation)` に対し scalar-only から擬似 `IndividualEvaluation` を作る案は contract 違反リスクが高いです（`bc_result`/`mission_gap` の意味を偽装しやすい）。  
  修正案: [`/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/nsga2_selection.py`] で `ParetoFeaturesLite` 専用の入口を追加するか、低レベル `non_dominated_sort`/`crowding_distance` 直呼び経路を `run_ga.py` 側で明示してください。私は「専用入口追加」を推奨します。
- [Warning] 目的関数の向き（`f1` 最大、`f2/f3` 最小）の正規化規約が設計に明文化されていません。  
  修正案: 3軸を dominance 比較へ渡す直前で符号統一し、向き回帰テストを追加してください。
- [Warning] `eligible < 2` 時の `parent_pairs` 生成規約が未定義に近いです。  
  修正案: deterministic self-mating fallback と warning 発火条件を仕様化し、固定シード回帰を追加してください。

## P5b: CPPS only injection
**判定: REQUEST_CHANGES**

- [Critical] T101 warmstart と CPPS injection の「枠競合 guard」が `sum<=1.0` だけでは不足です。アンカー個体上書き・丸め誤差・重複注入が未防止です。  
  修正案: 初期枠配分を `anchor -> warmstart -> cpps -> breed` の固定順で整数スロット確定し、`genome_hash` 重複排除後に不足枠を breed 補充する deterministic 規約を入れてください。
- [Warning] `update_archive_per_run` を世代ループで呼ぶ設計は API 意味論と不一致の可能性があります。  
  修正案: per-generation 用 API を分離するか、呼び出し頻度契約をドキュメント化してテストで固定してください。
- [Warning] 「admission/eviction は Stage B 限定」の機構化が抽象的です。  
  修正案: archive 入力 DTO から Stage C/holdout フィールドを型レベルで排除し、参照不能にしてください。

## 重点質問への回答
- P3 source_stage=B 限定: **条件付きで成立**。`mission_inf_gap` 計算が本当に Stage B `b_pooled_cf_result` のみから導出される実装なら成立します。現状は関数契約齟齬があるため、上記 Critical 修正が必要です。
- P5a scalar から `IndividualEvaluation` 構築: **現契約では非推奨**。低レベル NSGA 呼び出し、または lite 専用 API 追加が妥当です。
- P5b CPPS vs warmstart: **現設計の guard は不十分**。スロット優先順位・整数化・重複排除の規約が必要です。
- schema version bump 後方互換: **INCONCLUSIVE**（reader 実装未提示）。互換 reader と旧データ回帰テストがあれば APPROVE 可能です。

## 全体判定
**REQUEST_CHANGES**

設計の方向性自体は妥当ですが、契約整合（特に `mission_inf_gap` 入力契約と NSGA 入口契約）を先に確定しないと、C1/C2/C4 違反で実装時に破綻します。最優先は P3/P5a の型・API 固定、その次に P5b の初期枠競合を deterministic に閉じることです。