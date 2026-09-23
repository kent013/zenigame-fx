**指摘**
- [Critical] `system_fail` 判定条件が狭すぎ、並列実行時の `worker_error` を `unknown` に誤分類するリスクがあります。  
Fact: 設計は「Stage C payload に分類に必要な全データがある」を前提にしていますが、並列経路の Stage C 失敗代替 `StageResult` は `payload.worker_error_*` のみで `live_criteria_pass` 等を持ちません（[detailed-design.md:25](/Users/ishitoya/repository/zenigame-fx/devnotes/20260520-2340-fx-improve/detailed-design.md:25), [swim_lane.py:864](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/swim_lane.py:864), [swim_lane.py:878](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/swim_lane.py:878)）。一方、`_derive_stage_c_gap` 案の優先順位1は `system_failure` のみです（[detailed-design.md:97](/Users/ishitoya/repository/zenigame-fx/devnotes/20260520-2340-fx-improve/detailed-design.md:97)）。  
Interpretation: `worker_error` が `unknown` に寄ると、診断目的（B→C 汎化ギャップの主因分解）にノイズが入り、`unknown` の意味が「payload不整合」と「実行時障害」で混ざります。  
修正案: 最小変更として、優先順位1を `("system_failure" in reasons) or ("worker_error" in reasons)` で `system_fail` に統合し、`worker_error` sentinel 用の unit test を1件追加してください。

**施策ごと判定**
- C1-(1) `diagnostics_collector.py`: `REQUEST_CHANGES`
- C1-(2) `diagnostics_sidecar.py`: `APPROVE`
- C1-(3) `swim_lane.py`: `APPROVE`

**全体判定**
- `CHANGES_REQUESTED`

**1つの反証可能仮説 + 1つの最小変更**
- 反証可能仮説: 「R83で `worker_error` が発生した場合、現設計のままだと `stage_c_gap_class=unknown` が増え、`system_fail` 比率が過小に出る」  
- 最小変更: `_derive_stage_c_gap` の優先順位1に `worker_error` を追加して `system_fail` に寄せる（ロジック1行 + テスト1件）。