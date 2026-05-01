**本分析の前提**
- 前提1: C1準拠で、先に設計/DoD/docs/SKILLを読んでからテスト実装を確認しました（[detailed-design.md:1509](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T058-pr7/devnotes/20260429-1912-todo-T058-schema-v2-contract/detailed-design.md#L1509)）。
- 前提2: 実行再検証は行わず、提出テキストの整合監査です（DoD表の自己申告は静的照合）。
- 前提3: PR1-6 実装は参照のみ（非変更）として扱っています。

**反証仮説 (C9)**
| 仮説 | 判定 | 根拠 |
|---|---|---|
| H1 冗長でE2E追加なし | PASS | PR7は archive/calibrate/fail_closed/Tier2連結を追加し、PR5のsummary系単体補強と役割が分かれています（[test_t058_integration.py:151](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T058-pr7/tests/alpha_factory/test_t058_integration.py#L151), [test_run_ga_parallel.py:237](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T058-pr7/tests/scripts/test_run_ga_parallel.py#L237)）。 |
| H2 `_rows`空文字上書きは乖離 | PASS | fallback分岐の直接検証として成立。加えて「空/Noneのみ補完・stub維持」逆分岐も別テストで担保（[test_t058_integration.py:183](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T058-pr7/tests/alpha_factory/test_t058_integration.py#L183), [test_t058_integration.py:213](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T058-pr7/tests/alpha_factory/test_t058_integration.py#L213), [archive.py:679](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T058-pr7/src/alpha_factory/archive.py#L679)）。 |
| H3 docs/SKILLがtransitional設計と矛盾 | PASS | `dataset_span + dataset_epoch_id` ANDの記述は実装と整合（[stage-gates.md:290](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T058-pr7/docs/alpha_factory/stage-gates.md#L290), [SKILL.md:116](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T058-pr7/.claude/skills/zenigame-fx-calibrate-gate/SKILL.md#L116), [calibrate_state.py:177](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T058-pr7/src/alpha_factory/calibrate_state.py#L177)）。 |
| H4 DoD表PASSが未実行/条件不一致 | FAIL | 反証不足。例: 「全12施策mainマージ済」をPR7未マージ段階でPASS表記、行1532相当「warningなし」はテストで直接assertなし（[dod-verification-pr7.md:14](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T058-pr7/devnotes/20260429-1912-todo-T058-schema-v2-contract/dod-verification-pr7.md#L14), [dod-verification-pr7.md:46](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T058-pr7/devnotes/20260429-1912-todo-T058-schema-v2-contract/dod-verification-pr7.md#L46), [test_t058_integration.py:151](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T058-pr7/tests/alpha_factory/test_t058_integration.py#L151)）。 |

| 観点 | 判定 | コメント |
|---|---|---|
| A1 | PASS | 必須4ケースは実装済み（archive/calibrate/summary/Tier2）。 |
| A2 | NIT | RunContext一気通貫は archive+diagnostics は確認、calibrateは値確認中心で同一RunContext連結までは未検証。 |
| A3 | PASS | fail_closedでv1 archive rejectを機械化（[test_t058_integration.py:251](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T058-pr7/tests/alpha_factory/test_t058_integration.py#L251)）。 |
| A4 | PASS | Tier2 warning「出ない」をassertしており意図どおり（[test_t058_integration.py:655](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T058-pr7/tests/alpha_factory/test_t058_integration.py#L655)）。 |
| A5 | PASS | `run_ga.main`経路でsummary検証。 |
| B1 | NIT | 詳細設計コードDoDは15項目（1514-1528）で、ユーザー記載16との齟齬あり。 |
| B2 | NIT | 1534 fail_closedはOK。1532「warningなし」は現テストで直接検証していない。 |
| B3 | NIT | docs/SKILL更新は概ね良いが、T067文言の3点統一は未達（E3参照）。 |
| C1 | PASS | `schema_version`(str) と `cascade_contract_version`(int) 型分離を明示assert。 |
| C2 | PASS | fixtureのepoch_idは `[a-z0-9_]+` 準拠。 |
| C3 | PASS | `genome_entry_schema_version=2` / `calibrate_history_schema_version=2` を明示検証。 |
| D1 | PASS | PR5と一部重複はあるが、層の異なる冗長性として妥当。 |
| E1 | NIT | AND結合説明は実装一致。ただしdocsの「guard=calibrate_history_schema_version」は実装の`schema_version`判定と不一致。 |
| E2 | PASS | SKILLのv1 skip説明は `HistoryRecord.from_dict_or_none` と整合。 |
| E3 | FAIL | T067の3点セット（`dataset_span`撤廃、`dataset_epoch_id`単独化、`log_only→fail_closed`）が3文書で統一されていない。docsは3点記載、SKILL/DoDは不足。 |
| F1 | NIT | 主要touch範囲は遵守。ただしスコープ外untracked artifact（`reports/...`, `.codex-*`）が存在。 |
| F2 | PASS | ついで対応のリファクタ混入は見当たらない。 |
| G1 | PASS | devサーバー起動痕跡なし。 |
| G2 | PASS | テスト命名は振る舞い説明型。 |
| G3 | NIT | `tmp_path`運用は良好。ただしrun_ga smokeはrepo-root history参照で完全独立ではない。 |

**修正必須 (blocker)**
- `docs/SKILL/DoD` の T067 移行文言を3点セットで統一する。  
  1) `enforcement_mode: log_only -> fail_closed`  
  2) `dataset_span` 完全撤廃  
  3) `dataset_epoch_id` 単独 scope key 化  
  参照: [stage-gates.md:295](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T058-pr7/docs/alpha_factory/stage-gates.md#L295), [SKILL.md:116](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T058-pr7/.claude/skills/zenigame-fx-calibrate-gate/SKILL.md#L116), [dod-verification-pr7.md:56](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T058-pr7/devnotes/20260429-1912-todo-T058-schema-v2-contract/dod-verification-pr7.md#L56)
- DoD report の条件表現を検証実態に合わせる。  
  `#1` の「全12施策mainマージ済」表現、`#17` の「warningなし」主張は現記述のままだと過大。

[REQUEST_CHANGES]