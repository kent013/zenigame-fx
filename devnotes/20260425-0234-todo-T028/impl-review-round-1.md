**前提（C4）**
- 提示された差分・テスト内容が実ファイルと一致している前提で判定します。

**Findings（重大度順）**
- [Critical] なし
- [Warning] なし
- [Suggestion] [tests/alpha_factory/test_stage_gate_selection_invariance.py](/Users/ishitoya/repository/zenigame-fx/tests/alpha_factory/test_stage_gate_selection_invariance.py): `_snapshot_at_no_cache` が本体ロジックの複製だと将来ドリフト余地があるため、任意で `MockBroker` 側に計算本体を切り出して共用すると保守性が上がります。

**ファイルごとの判定**
1. [src/broker/mock.py](/Users/ishitoya/repository/zenigame-fx/src/broker/mock.py): APPROVED  
`bar is cache[0]` の identity key、cache miss 時の既存演算順序維持、`deposit`/`apply_bar_holding_cost`/`_open_position`/`_close_one` での invalidate が設計と一致。`_close_one` 連鎖経由の invalidation 方針も妥当。
2. [src/broker/orders.py](/Users/ishitoya/repository/zenigame-fx/src/broker/orders.py): APPROVED  
`Position` の `@dataclass(frozen=True)` 化は stale risk 抑止として妥当。提示テスト方針とも整合。
3. [tests/broker/test_mock_snapshot_cache.py](/Users/ishitoya/repository/zenigame-fx/tests/broker/test_mock_snapshot_cache.py): APPROVED  
cache hit/miss、long/short、duplicate timestamp、object identity、chained close、bit-identical 比較を押さえており、施策 1/2 の検証として十分。
4. [tests/broker/test_mock_snapshot_invariance.py](/Users/ishitoya/repository/zenigame-fx/tests/broker/test_mock_snapshot_invariance.py): APPROVED  
frozen 化の副作用検出（`FrozenInstanceError`）と value equality 確認が施策 0/3 に対応。
5. [tests/alpha_factory/test_stage_gate_selection_invariance.py](/Users/ishitoya/repository/zenigame-fx/tests/alpha_factory/test_stage_gate_selection_invariance.py): APPROVED  
cache on/off の Stage A 結果（`passed`、`fitness_pen`、`sharpe_raw`、`trade_count` 等）同一性を直接検証しており、selection outcome invariance の確認として有効。

**全体判定**
- APPROVED

