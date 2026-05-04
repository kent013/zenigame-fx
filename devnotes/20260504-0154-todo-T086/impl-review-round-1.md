**前提**
- 提示された差分テキストのみを根拠にレビューしています（実行検証なし）。
- C1/C4/C6/C9に従い、まず事実と解釈を分離して記載します。

**ファイルごとの判定**

[stage_gate.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/stage_gate.py)  
判定: **APPROVED_WITH_WARNING**
- [Fact] `_PairSidecarInputs` の配置、`CrossPairResult._shadow_sidecar_inputs=field(default_factory=dict, repr=False, compare=False)`、`evaluate_stage_c` の cross_pair 区画 `try/finally sanitize` は設計意図と整合。
- [Fact] `_log_canonical_dual_path` の `pair_label` 契約（None/空/空白/前後空白/non-C stage拒否）は実装済み。
- [Warning] `pair_label` は厳格化されましたが、`fold_index` の non-`B_fold` 拒否は未導入のため、識別子契約をさらに厳密化する余地があります。

[cross_pair.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/cross_pair.py)  
判定: **APPROVED**
- [Fact] `_run_pair_sharpe` の3-tuple化、`metric_unavailable` 時の sidecar 保持、`exception` 時のみ sidecar `None` は設計SSOT（dual-path skip条件）と一致。
- [Fact] `evaluate_cross_pair` で sidecar を `CrossPairResult` に集約し、既存 aggregate 計算に非干渉の構造は妥当。

[test_cross_pair.py](/Users/ishitoya/repository/zenigame-fx/tests/alpha_factory/test_cross_pair.py)  
判定: **CHANGES_REQUESTED**
- [Critical] 設計で必須化された acceptance 群（A1-A5/B1-B4/C1-C6/D1-D5/E1-E7）に対し、差分上は未実装/未確認項目が残ります。特に「既存 caller 互換5本（A/B_IS/B_fold/C_base/C_stress）」のうち `B_IS` ケースが差分中で確認できません。
- [Warning] Round 5で明示された #26a/#26b 分割（helperのNone返却検証とcanonical_skipped emit検証の責務分離）が差分上で明確に確認できません。

未変更（設計上は必須）  
判定: **CHANGES_REQUESTED**
- [Critical] 以下が差分に存在せず、設計 §11.1/§12.3 の merge gate 要件未達です。  
[scripts/smoke/measure_step1.8_memory.sh](/Users/ishitoya/repository/zenigame-fx/scripts/smoke/measure_step1.8_memory.sh)  
[scripts/smoke/sample_worker_rss.py](/Users/ishitoya/repository/zenigame-fx/scripts/smoke/sample_worker_rss.py)  
[scripts/smoke/aggregate_step1.8_memory.py](/Users/ishitoya/repository/zenigame-fx/scripts/smoke/aggregate_step1.8_memory.py)  
[docs/alpha_factory/stage-gates.md](/Users/ishitoya/repository/zenigame-fx/docs/alpha_factory/stage-gates.md)

**全体判定**
- **CHANGES_REQUESTED**

主理由は「コア実装は良いが、設計で必須とされた検証・運用ファイルと一部テスト受け入れ条件が未充足」です。