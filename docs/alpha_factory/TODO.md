# Alpha Factory TODO

zenigame-fx Alpha Factory の改善タスク一覧。

## Open

| ID | タイトル | テーマ | 概要 | 優先度 | 実装モード | 設計 | 追加日時 |
|----|---------|-------|------|-------|----------|------|---------|
| T058 | T058-schema-v2-contract | infrastructure | Schema v2 + dataset_epoch_id 全経路必須 | Critical | incremental | [設計](devnotes/20260429-1912-todo-T058-schema-v2-contract/) | 2026-04-29 21:12 |
| T059 | T059-epoch-window-manager | infrastructure | EpochManager (24m rolling, atomic reserv) | Critical | incremental | [設計](devnotes/20260429-2113-todo-T059-epoch-window-manager/) | 2026-04-29 22:10 |
| T060 | T060-partition-fold-generator | stage-gate | Partition (10 領域) + Fold (5 folds) generator | Critical | incremental | [設計](devnotes/20260429-2210-todo-T060-partition-fold-generator/) | 2026-04-29 22:44 |
| T061 | T061-canonical-five-engine | stage-gate | canonical 5 engine: HAC Bartlett q=5 SR + session block win rate + slack_to_range + log_pf_clip + invariant fail-fast | Critical | incremental | [設計](devnotes/20260429-2300-todo-T061-canonical-five-engine/) | 2026-04-30 00:00 |
| T062 | T062-mission-inf-gap-engine | ga-architecture | mission_inf_gap engine: 4 指標 (sharpe/pnl/dd/tc) inf-norm shortfall + constraint_violation + mission_signed_margin (Pareto f3 / Deb 2000 用) | Critical | incremental | [設計](devnotes/20260430-0030-todo-T062-mission-inf-gap-engine/) | 2026-04-30 00:42 |
| T063 | T063-stage-a-evaluator | stage-gate | Stage A evaluator: T061 + q_force 動的計算 + A→B 乖離自動引き上げ + 世代内 top q_force% 選抜 (state-immutable pure function) | Critical | incremental | [設計](devnotes/20260430-0130-todo-T063-stage-a-evaluator/) | 2026-04-30 09:41 |
| T064 | T064-stage-bc-evaluator | stage-gate | Stage B + C-lite + C evaluator: 5 fold pooled OOS / 3 disjoint windows × 15 cells worst / 12w + spread stress + cross-pair shadow (5/5) | Critical | incremental | [設計](devnotes/20260430-0230-todo-T064-stage-bc-evaluator/) | 2026-04-30 10:20 |
| T065 | T065-nsga2-core-and-main-selection | ga-architecture | NSGA-II core + 主選抜 (B-pooled): constrained-domination (Deb 2000) + non-dominated sort + crowding distance + crowded-comparison binary tournament + deterministic tie-break (rank/-crowding/genome_hash/index) + blake2b stable seed + A-fail/B-invariant-fail Pareto 圧除外 + Phase 2 統合 9 箇所申し送り | Critical | incremental | [設計](devnotes/20260430-1100-todo-T065-nsga2-core-and-main-selection/) | 2026-04-30 11:51 |

## Conditional

| ID | タイトル | テーマ | 概要 | トリガー条件 | 昇格時優先度 | 実装モード | 設計 | 追加日時 |
|----|---------|-------|------|------------|------------|----------|------|---------|
