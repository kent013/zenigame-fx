**全体判定: APPROVED**

前提: 提示された `detailed-design.md` 抜粋・diff・テスト結果のみでレビュー（コマンド未実行）。

**[src/alpha_factory/stage_gate.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/stage_gate.py)**
- [Critical] なし
- [Warning] [stage_gate.py:323](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/stage_gate.py:323) 付近の `_canonical_shadow_summary` が `evaluate_mission_inf_gap` の `ValueError` のみ捕捉です。現状実装では問題化しにくいですが、「行動不変」を将来変更にも強く担保するなら shadow 経路の想定外例外も隔離する方が安全です（gate判定経路への波及防止）。
- [Suggestion] `_canonical_shadow_summary` の `ValueError` 分岐を直接検証するテストを1件追加すると、NaN混入時の「gate_passのみ保持」契約が固定化できます。

**[src/alpha_factory/archive.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/archive.py)**
- [Critical] なし
- [Warning] なし
- [Suggestion] なし（4点セットは満たしています: `GENOMES_SCHEMA` → `_create_row_template` → `collect_stage_b/c` → `flush`）。

**[tests/alpha_factory/test_archive.py](/Users/ishitoya/repository/zenigame-fx/tests/alpha_factory/test_archive.py)**
- [Critical] なし
- [Warning] なし
- [Suggestion] なし（`±inf/NaN/bool/None`、欠損key、非Mapping、Parquet永続化まで網羅できています）。

**[tests/alpha_factory/test_stage_gate_canonical_dual_path.py](/Users/ishitoya/repository/zenigame-fx/tests/alpha_factory/test_stage_gate_canonical_dual_path.py)**
- [Critical] なし
- [Warning] なし
- [Suggestion] なし（LOG_ONLY vs DISABLED 差分を `canonical_shadow_*` のみに限定しており、既存dual-path不変契約の検証として妥当）。

**契約確認（要点）**
- 行動不変: GA selection / fitness / gate判定ロジックへの直接変更は見当たらず、観測列追加に留まっています。
- データフロー整合: `canonical_shadow_b_is` / `canonical_shadow_c_base` の key 名は stage_gate と archive で一致。
- PR2同型性: `shadow` 列追加・payload抽出・archive書込のパターンは一貫。
- 既存lint/type: ruff clean、mypy 1件は提示どおり既存起因でPR3新規問題は確認できません。