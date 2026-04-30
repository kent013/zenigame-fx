**前提検証 (C4) / Fact-Interpretation 分離 (C6)**  
- Fact: 現行 main には `epoch_manager.py` / `run_context.py` / `schema_contract.py` は未存在（`find`確認）。  
- Fact: 参照指定の既存実装は設計意図と整合。JSONL反復は [calibrate_state.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/calibrate_state.py:122)、atomic write は [fsp_updater.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/fsp_updater.py:180)、`flock` 利用は [calibrate_gate.py](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/calibrate_gate.py:28)、`DatasetConfig` 現状項目は [config.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/config.py:51)。  
- Interpretation: C1/C2 の観点で「未実装＝バグ」とは判定しない。Phase 1 分離方針自体は妥当。  
- Interpretation: ただし詳細設計内に、Phase 1 時点でも修正すべき整合性欠陥がある。

**施策1 `epoch_manager.py` — REQUEST_CHANGES**  
- [Critical] `run_id` を epoch 跨ぎで許容する設計と `mark_run_status` の全 epoch 先頭一致更新が衝突。  
  - Fact: `mark_run_status` は全 epoch を走査して最初に見つけた `run_id` を更新 ([detailed-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-2113-todo-T059-epoch-window-manager/detailed-design.md:325))。  
  - Fact: テスト計画は「異なる epoch では同じ run_id を許容」 ([detailed-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-2113-todo-T059-epoch-window-manager/detailed-design.md:600))。  
  - 修正案: `run_id` を全 epoch で一意必須にする、または `mark_run_status(run_id, epoch_index|dataset_epoch_id, ...)` に変更して対象を一意特定する。  
- [Critical] 「state 破損時の明示 reset」が自己矛盾。  
  - Fact: `reset()` 冒頭で `_load_state_no_init()` を呼び、破損時は `EpochStateCorruptError` を投げる設計 ([detailed-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-2113-todo-T059-epoch-window-manager/detailed-design.md:352), [detailed-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-2113-todo-T059-epoch-window-manager/detailed-design.md:409))。  
  - Interpretation: 破損回復のための reset 自体が失敗しうる。  
  - 修正案: `reset()` 内で破損例外を捕捉し、`previous_state_snapshot` に `null`/`{"corrupt": true, ...}` を記録して削除を継続する。  
- [Warning] `reset()` が lock 無しで `reserve_run_slot`/`mark_run_status` と競合しうる。  
  - 修正案: `reset()` 全体を `with self._file_lock():` で保護。  
- [Warning] `_compute_fingerprint(dataset_cfg)` が `dataset_cfg` を実質使っていない ([detailed-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-2113-todo-T059-epoch-window-manager/detailed-design.md:424))。  
  - 修正案: 引数を削除するか、`dataset_cfg.instrument` を照合して guard を追加。  
- [Suggestion] `make_epoch_id` が日付のみのため、時刻付き window を将来許容するなら衝突余地あり ([detailed-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-2113-todo-T059-epoch-window-manager/detailed-design.md:226))。時刻を契約上固定（00:00 UTC）と明記すると安全。

**施策2 `test_epoch_manager.py` — REQUEST_CHANGES**  
- [Warning] Critical 2件を防ぐテストが不足。  
  - Fact: 破損 state で `reset()` が回復可能かのテストがない ([detailed-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-2113-todo-T059-epoch-window-manager/detailed-design.md:612))。  
  - Fact: 同一 `run_id` を複数 epoch で持つ場合の `mark_run_status` 正当更新テストがない。  
  - 修正案: `test_reset_recovers_even_when_state_json_is_corrupt`、`test_mark_run_status_targets_latest_or_explicit_epoch_when_run_id_reused` を追加。  
- [Suggestion] lock timeout の multiprocessing テストは flaky リスク記載済みなので、`pytest.mark.flaky`/再試行制御を先に設計へ明記すると CI 安定化しやすい。

**施策3 `.gitignore` — APPROVE**  
- [Warning] 設計記載の ignore パターンが実装案の命名とズレる。  
  - Fact: lock は `.with_suffix(".lock")` なので `epoch_state.lock` 側 ([detailed-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-2113-todo-T059-epoch-window-manager/detailed-design.md:489))。  
  - Fact: 提案 ignore は `epoch_state.json.lock` ([detailed-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-2113-todo-T059-epoch-window-manager/detailed-design.md:637))。  
  - 修正案: ignore 名を実装に合わせるか、`.cache/` 既存無視ルールを根拠に追記自体を省略。  
- [Suggestion] 既存 `.gitignore` で `.cache/` 全体が既に無視済み ([.gitignore](/Users/ishitoya/repository/zenigame-fx/.gitignore:8))。冗長追記は避けてもよい。

**INCONCLUSIVE（第一級扱い）**  
- Phase 2 組込（`run_ga.py`/24m切替）の実運用影響は本PRスコープ外のため INCONCLUSIVE。現時点では「runtime非影響」という設計主張は妥当。

**総合判定**  
- **CHANGES_REQUESTED**（施策1の Critical 2件がマージブロッカー）。  

(C3/C7: 相関・因果 claim は本設計に存在せず N/A 判定)