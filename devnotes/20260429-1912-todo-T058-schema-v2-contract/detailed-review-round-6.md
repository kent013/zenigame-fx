1. [Critical] `load_calibrated_threshold` の「既存シグネチャ完全維持」が未達です。  
Fact: 施策6の新シグネチャが `threshold_floor` / `threshold_ceiling` を必須化しており default が消えています（[detailed-design.md:1058](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-1912-todo-T058-schema-v2-contract/detailed-design.md:1058)）。さらに `run_ga` 例が `cfg.stage_gate.stage_a.threshold_floor` を参照していますが、現行 `StageGateConfig` はこの階層を持ちません（[detailed-design.md:1103](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-1912-todo-T058-schema-v2-contract/detailed-design.md:1103), [stage_gate.py:113](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/stage_gate.py:113), [run_ga.py:1078](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py:1078)）。  
Interpretation: 「既存 caller パターン変更なし」という Round 6 目的と矛盾し、実装時に互換破壊/参照エラーを招きます。  
修正案: 施策6を以下に統一。  
- 既存 defaults 維持: `threshold_floor: float = -100.0`, `threshold_ceiling: float = 100.0`。  
- `run_ga` 側は現行同様、`history_path/base_config_hash/dataset_span/instrument/stage_gate_version` + `dataset_epoch_id` のみ追加。`threshold_*` の明示渡しは削除。

2. [Warning] API 契約マトリクスの `load_calibrated_threshold` 行がまだ現行実装を完全記述できていません。  
Fact: 行93は `history_path` と `threshold_*` が落ちた短縮形です（[detailed-design.md:93](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-1912-todo-T058-schema-v2-contract/detailed-design.md:93)）。  
Interpretation: 実装時の参照元としては曖昧さが残ります。  
修正案: マトリクス行93を「現行完全シグネチャ + `dataset_epoch_id` 追加」に更新。

3. [Warning] `GenomeArchive.load` 表記は有効セクションでは整合しましたが、擬似コード本文に `load(...)` 単体表記が残っています。  
Fact: 施策4コード例は `def load(...)` 表記（[detailed-design.md:815](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-1912-todo-T058-schema-v2-contract/detailed-design.md:815)）、施策10/マトリクスは `GenomeArchive.load`（[detailed-design.md:89](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-1912-todo-T058-schema-v2-contract/detailed-design.md:89), [detailed-design.md:1409](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-1912-todo-T058-schema-v2-contract/detailed-design.md:1409)）。  
Interpretation: 読み手によって module 関数化と誤読する余地があります。  
修正案: 施策4の `load` 例を `@staticmethod GenomeArchive.load(...)` で明示。

施策別判定:
1. 施策1: APPROVE  
2. 施策2: APPROVE  
3. 施策3: APPROVE  
4. 施策4: APPROVE  
5. 施策5: APPROVE  
6. 施策6: REQUEST_CHANGES  
7. 施策7: APPROVE  
8. 施策8: APPROVE  
9. 施策9: REQUEST_CHANGES  
10. 施策10: APPROVE  
11. 施策11: APPROVE  
12. 施策12: APPROVE

確認結果（ご指定4点）:
- `load_calibrated_threshold` の既存 caller 完全維持: 未達（上記 Critical）。  
- `GenomeArchive.load` 文書一貫性: ほぼ達成、擬似コード1箇所のみ要明示化。  
- tuple 受取 run_alpha_sieve 単独: 達成（有効セクションで確認）。  
- FSP caller list 現行経路のみ: 達成（run_ga 経路削除済み）。

全体判定: CHANGES_REQUESTED