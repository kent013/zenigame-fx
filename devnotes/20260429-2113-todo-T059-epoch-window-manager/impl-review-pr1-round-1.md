本分析の前提（C4）
- Verified: 設計先行で [conceptual-design.md](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T059-pr1/devnotes/20260429-2113-todo-T059-epoch-window-manager/conceptual-design.md) と [detailed-design.md](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T059-pr1/devnotes/20260429-2113-todo-T059-epoch-window-manager/detailed-design.md) を先読しました。
- Verified: 実装は [epoch_manager.py](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T059-pr1/src/alpha_factory/epoch_manager.py)、[run_ga.py](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T059-pr1/scripts/alpha_factory/run_ga.py)、関連テストを読んで確認しました。
- Verified: 本レビューは静的読解ベースです（`pytest/ruff/mypy` 実行による再検証は未実施）。

**主要 findings（重大度順）**
1. **Blocker**: epoch advance 後に `dataset_cfg` と新 window の再照合がなく、旧 window の `cfg.dataset` で新 epoch へ予約できてしまいます（H4 は反証できず）。
- 事実: `reserve_run_slot` は advance 前にのみ `_verify_dataset_match` を呼びます（[epoch_manager.py#L266](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T059-pr1/src/alpha_factory/epoch_manager.py#L266)）、その後 advance して新 epoch に書き込みます（[epoch_manager.py#L270](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T059-pr1/src/alpha_factory/epoch_manager.py#L270), [epoch_manager.py#L299](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T059-pr1/src/alpha_factory/epoch_manager.py#L299)）。
- 事実: テスト側もこの挙動を前提化しています（[test_epoch_manager.py#L221](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T059-pr1/tests/alpha_factory/test_epoch_manager.py#L221), [test_epoch_manager.py#L380](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T059-pr1/tests/alpha_factory/test_epoch_manager.py#L380)）。
- 解釈: Phase 2 で runtime 組込時に `dataset_epoch_id` と実データ window の整合性リスクになります。
- 修正案: advance 後に `current_epoch_index` で window を再計算し `_verify_dataset_match` を再実行する。合わせて該当テスト期待値を更新する。

**反証仮説 H1-H5（C9）**
| 仮説 | 判定 | 根拠 |
|---|---|---|
| H1 二重提供で SSOT 崩壊 | PASS | module-level 実装を instance method が thin wrapper で委譲（[epoch_manager.py#L146](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T059-pr1/src/alpha_factory/epoch_manager.py#L146), [epoch_manager.py#L220](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T059-pr1/src/alpha_factory/epoch_manager.py#L220)）。 |
| H2 fallback が silent regression | NIT | warning ログは出るため完全 silent ではない（[run_ga.py#L1146](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T059-pr1/scripts/alpha_factory/run_ga.py#L1146)）。ただし `except Exception` は広い。 |
| H3 hard-code でテスト脆弱化 | NIT | 期待値固定は契約明示として妥当だが fixture 変更追随コストは増える（[test_run_ga_parallel.py#L237](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T059-pr1/tests/scripts/test_run_ga_parallel.py#L237), [test_t058_integration.py#L469](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T059-pr1/tests/alpha_factory/test_t058_integration.py#L469)）。 |
| H4 advance 後 mismatch 未検知 | FAIL | 上記 Blocker の通り。 |
| H5 `current_window()` が state を作らない | PASS | 仕様として明示済み（[epoch_manager.py#L227](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T059-pr1/src/alpha_factory/epoch_manager.py#L227), [detailed-design.md#L248](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T059-pr1/devnotes/20260429-2113-todo-T059-epoch-window-manager/detailed-design.md#L248)）。 |

| 観点 | 判定 | 根拠 |
|---|---|---|
| A1 | PASS | `EpochWindow(frozen)` + `end > start` 検証あり。 |
| A2 | PASS | `epoch_YYYYMMDD_YYYYMMDD` は grammar 適合。 |
| A3 | PASS | `_compute_window` は `anchor + stride*index` で決定論的。 |
| A4 | **FAIL** | advance 後の dataset 再照合欠如（Blocker）。 |
| A5 | PASS | `Z`/`+00:00` 正規化あり。 |
| A6 | PASS | 全 epoch 走査で `run_id` 重複拒否。 |
| A7 | PASS | 破損 state を reset で捕捉し監査記録。 |
| A8 | PASS | `reset` 全体が lock 保護。 |
| A9 | PASS | `_init_state` で instrument guard。 |
| A10 | PASS | 非 Windows 前提は設計に明記（[detailed-design.md#L617](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T059-pr1/devnotes/20260429-2113-todo-T059-epoch-window-manager/detailed-design.md#L617)）。 |
| B1 | PASS | 38 テスト実装済み。 |
| B2 | PASS | `spawn` + skip + join/terminate で安定化配慮。 |
| B3 | PASS | Round1 Critical 2件の検証テストあり。 |
| B4 | PASS | 命名は振る舞いベース。 |
| B5 | PASS | `tmp_path`/`monkeypatch` 利用で isolation 良好。 |
| C1 | NIT | fallback で互換維持。ただし catch が広い。 |
| C2 | PASS | 同 `start/end` で deterministic。 |
| C3 | PASS | fallback 時のみ warning、主経路は既存 log に載る。 |
| C4 | PASS | `dataset_epoch_id: str` 契約は維持。 |
| C5 | PASS | Phase2 申し送りコメント明示あり。 |
| D1 | PASS | T058 規範との整合は維持。 |
| D2 | PASS | `schema_version: "1.1"` 契約は非変更。 |
| D3 | NIT | 想定外の untracked 生成物が作業木に存在。 |
| E1 | PASS | module-level 化 + wrapper 併存は意図整合。 |
| E2 | PASS | `run_ga.py` 変更はユーザー指示で妥当。 |
| F1 | NIT | 期待6ファイル以外に untracked artifact があるため、コミット対象の明確化推奨。 |
| F2 | PASS | ついでリファクタ混入は見当たらない。 |
| G1 | PASS | dev server 起動痕跡なし。 |
| G2 | PASS | テスト名は規約適合。 |
| G3 | PASS | テスト isolation は遵守。 |
| G4 | NIT | `ruff/mypy` の実行結果は本レビューでは未確認。 |

**修正が必要な項目**
1. `reserve_run_slot` で epoch advance 後の window に対して `dataset_cfg` 再検証を追加。
2. それに合わせて advance 系テスト（特に `cfg_e0` で 7 回目予約を許容している箇所）を更新。
3. PR 化時に untracked artifact（`devnotes` 内 `.codex-*`、`reports/*`）をコミット対象から除外。

[REQUEST_CHANGES]