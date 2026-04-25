**前提検証 (C4)**
- Verified: Stage A payload は現状 `total_pnl` を持たない（[stage_gate.py:320](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/stage_gate.py:320)）
- Verified: archive schema は 28 カラム固定（[archive.py:54](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/archive.py:54)）
- Verified: `compute_metrics` は `total_pnl` を算出（[metrics.py:85](/Users/ishitoya/repository/zenigame-fx/src/backtest/metrics.py:85)）
- Verified: `run_generation` は現状 single-process 前提の直列実行（[swim_lane.py:308](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/swim_lane.py:308), [swim_lane.py:461](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/swim_lane.py:461)）

1. 施策1 DiagnosticsCollector: **REQUEST_CHANGES**  
[Critical] 設計コードの import が現行規約と不整合です（`alpha_factory.*` ではなく `src.alpha_factory.*` が正）。修正案: 新規モジュール含め `from src.alpha_factory...` に統一。  
[Warning] `metric_stage` は実質「到達段」ではなく「通過段」判定になっており、命名と解釈がずれる余地があります。修正案: 命名を `highest_passed_stage` に変更、または仕様に「pass-based」と明記。  
[Suggestion] メモリ見積もり 100 bytes/record は過小です。実測ベース（`sys.getsizeof`）に更新推奨。

2. 施策2 Stage A payload 追加: **REQUEST_CHANGES**  
[Warning] `exception_caught` 連動で `total_pnl=0` に落とすと、`size_norm` 側の例外でも PnL が失われます。修正案: backtest 部分と size_norm 部分の失敗フラグを分離し、`bt` 成功時は常に `total_pnl` を保持。  
[Suggestion] タイトルの「sharpe追加」は現状 `sharpe_raw` が既にあるため文言整理推奨（重複誤解防止）。

3. 施策3 swim_lane 連携: **REQUEST_CHANGES**  
[Critical] 提示コードの `self._generation_count` は現行実装に存在しません（正は `lane.generation_count`）。修正案: `_run_tier1_generation` 内で `lane.generation_count` を使用。  
[Warning] `run_generation` シグネチャ変更に伴う呼び出し元・テスト更新対象の列挙が不足。修正案: `tests/alpha_factory/test_swim_lane.py` と `tests/scripts/test_alpha_factory_run_ga.py` を明示的に更新対象へ追加。

4. 施策4 sidecar writer: **REQUEST_CHANGES**  
[Critical] `pandas` 依存を追加しているが、現行依存に未登録です（[pyproject.toml](/Users/ishitoya/repository/zenigame-fx/pyproject.toml)）。修正案: `pyarrow` のみで書く実装にするか、`pandas` + `uv.lock` 更新を設計に明記。  
[Warning] I/O エラーテストを権限エラー依存にすると環境依存で不安定です。修正案: `pq.write_table` を monkeypatch して例外注入。

5. 施策5 run_ga 統合: **REQUEST_CHANGES**  
[Critical] `--no-report` 契約違反リスクがあります。現行は report ディレクトリ非更新が契約（[run_ga.py:181](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py:181), [run_ga.py:864](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py:864)）だが、設計案は sidecar を常時 `reports/` に書く。修正案: `--no-report` 時は sidecar 出力も skip。  
[Critical] fail-open が end-to-end で未成立です。`collector.to_rows()` 側例外は現設計だと GA を止めます。修正案: `to_rows + write` 全体を `try/except` で包み `False` 返却。  
[Warning] パスを `Path("reports/run-reports")` 直書きすると `RUN_REPORTS_DIR` 差し替えテストと不整合。修正案: `run_dir / "diagnostics"` を使用。

6. 施策6 run-report 追加セクション: **REQUEST_CHANGES**  
[Warning] 既存スキルの「必須セクション検証コマンド」に新セクションが未反映だと運用 drift します（[SKILL.md:79](/Users/ishitoya/repository/zenigame-fx/.claude/skills/zenigame-fx-run-report/SKILL.md:79)）。修正案: grep 対象に `## Stage A Provenance 分布` を追加。  
[Warning] 現状 `generate_run_report.py` のテスト基盤が無いので回帰リスク高。修正案: `tests/scripts/test_alpha_factory_generate_run_report.py` を新設。

7. 施策7 テスト計画: **REQUEST_CHANGES**  
[Warning] 施策5の実変更に対するテストファイル指定が不足しています。修正案: `tests/scripts/test_alpha_factory_run_ga.py` に `diagnostics_sidecar` 成功/失敗/`--no-report` を追加。  
[Suggestion] NaN/Inf 伝播は collector だけでなく report 集計側（median/p25/p75）にも防御テストを追加推奨。

**横断観点**
- ルックアヘッドバイアス(9): primitive 変更が無く **N/A**。  
- メモリ制約(10): 実際のオブジェクトオーバーヘッドを見ても 3GB/worker 制約内に十分収まる見込み。  
- primitive性能(11): primitive非変更のため **N/A**。  
- 並行経路確認(13): 現行経路は直列で、並列経路の実装は未導入。  
- Collider bias/C7(14): 本設計は分布可視化中心で相関因果 claim がなく **N/A**（将来相関を出すなら conditioning set 明示が必要）。

**全体判定: CHANGES_REQUESTED**