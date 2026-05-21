**前提検証（C4）**
- `Verified`: 提示差分・提示テスト結果・提示設計要点に基づいて判定。
- `Unverified`: `devnotes/20260521-0925-nsga2-cpps-selection-wiring/detailed-design.md` 本文そのものとの逐条照合は未実施（入力未提示のため）。

**Findings（重大度順）**
1. [Warning] OFF経路の bit-exact 回帰検知テストが不十分。  
Fact: [`test_alpha_factory_run_ga_nsga2.py`](/Users/ishitoya/repository/zenigame-fx/tests/scripts/test_alpha_factory_run_ga_nsga2.py) の `test_off_path_is_deterministic_and_unaffected_by_pareto` は `g.name` のみ比較。  
Interpretation: `g.name` は `g{gen}_i{idx}` で再採番されるため、親選抜や遺伝子内容が変わっても同一になり得る。OFF完全互換の担保として弱い。

2. [Suggestion] payload→archive→cache→breed の4段伝搬を1本で検証するE2E系ユニットテストを追加した方がよい。  
Fact: スキーマ列存在・lite選抜・`_cache_entry_to_pareto_lite` は個別テストあり。  
Interpretation: キー名変更や抽出条件変更の配線断を早期検知しにくい。

**各ファイル判定**
- [`scripts/alpha_factory/run_ga.py`](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py): APPROVED（設計要点と整合、fallback/決定論配線あり）
- [`src/alpha_factory/archive.py`](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/archive.py): APPROVED（additive nullable で4列伝搬追加、後方互換パターン）
- [`src/alpha_factory/config.py`](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/config.py): APPROVED（default OFF）
- [`src/alpha_factory/nsga2_selection.py`](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/nsga2_selection.py): APPROVED（eligible定義・parent_pairs長契約・deterministic RNG受け口は妥当）
- [`tests/alpha_factory/test_archive.py`](/Users/ishitoya/repository/zenigame-fx/tests/alpha_factory/test_archive.py): APPROVED
- [`tests/alpha_factory/test_diagnostics_collector.py`](/Users/ishitoya/repository/zenigame-fx/tests/alpha_factory/test_diagnostics_collector.py): APPROVED
- [`tests/alpha_factory/test_nsga2_pareto_features_selection.py`](/Users/ishitoya/repository/zenigame-fx/tests/alpha_factory/test_nsga2_pareto_features_selection.py): APPROVED
- [`tests/scripts/test_alpha_factory_run_ga_nsga2.py`](/Users/ishitoya/repository/zenigame-fx/tests/scripts/test_alpha_factory_run_ga_nsga2.py): CHANGES_REQUESTED（Warning 1）

**観点別（a-e）**
1. (a) OFF互換:  
Fact: `nsga2_selection_enabled` で分岐し、False時は従来経路にフォールスルー。  
Interpretation: 実装上は維持。ただしテスト証明が弱く、監査観点では未充足。
2. (b) 次世代頭数:  
Fact: `select_from_pareto_features(... offspring_count=population_size)` かつ parent_pairs長契約あり。  
Interpretation: 常に `pop_size` 生成の設計を満たす。
3. (c) 4段伝搬漏れ:  
Fact: `GENOMES_SCHEMA` / `_create_row_template` / `collect_stage_b` / `_update_cache` の接続は実装済み。  
Interpretation: 明白な配線漏れは見当たらない。
4. (d) RNG決定論:  
Fact: 親選抜は `make_selection_seed(run_id, gen)`、交叉突然変異は主RNG。  
Interpretation: 同一 `run_id, gen` で決定論。`run_id` が変われば結果も変わる設計。
5. (e) eligible 0 fallback:  
Fact: `parent_pairs` 空なら `_breed_nsga2` が `None` を返し legacy tournament にフォールバック。  
Interpretation: 安全側動作で問題なし。

**全体判定**
- **CHANGES_REQUESTED**（理由: OFF bit-exact 担保のテストが要件に対して十分でないため）