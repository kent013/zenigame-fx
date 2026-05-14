**前提検証 (C4)**
- Verified: 提示テキスト上で、`spawn` 採用、`_check_memory_budget` 現行式、`measure_peak_rss_mb` 呼び出し位置、`PriceBar/Ohlc` 定義、既存 L1/L2 決定論テストの存在は確認できました。
- Unverified: 最新 `main` 実体（config 値、git 履歴、grep 網羅痕跡、parquet 集計）は、あなたの制約（コマンド実行なし）に従い未検証です。ここは **INCONCLUSIVE** です。

**施策別判定**
1. 施策1（二層計測）: **REQUEST_CHANGES**  
[Critical]  
Fact: `schema_version 1.1→1.2 bump` と `--mem-profile 無効時は現行 schema 維持` が同時に書かれており整合しません。  
Interpretation: consumer 側で分岐不能になり、転記漏れ/互換性事故の起点になります。  
修正案: `schema_version` の扱いを一意に決める（常時1.2に統一、または `memory_profile_schema_version` を別キー追加）。テストもその方針に一本化。  

[Critical]  
Fact: `pool.map(_measure_worker_memory_task, [None] * max_workers)` は「全 worker 1回ずつ実行」を厳密保証しません。  
Interpretation: per-worker 内訳が欠損/重複し、Phase 1 レバー判定根拠が壊れます。  
修正案: 収集結果を `pid` でユニーク化し、`len(unique_pid)==len(pool_pids)` を満たすまで再試行する実装に変更。未達時は明示エラー。  

[Warning]  
Fact: `_recursive_sizeof` 方針だけだと `slots dataclass`・`numpy view`・shared ref の扱い漏れ余地があります。  
Interpretation: object bytes が過小/過大計上されるリスクがあります。  
修正案: `dataclasses.fields` と `__slots__` を明示走査、`ndarray.base` の重複参照回避テストを追加。  

2. 施策2（4項メモリモデル）: **APPROVE**  
[Warning]  
Fact: 暫定 `_MEM_PRIVATE_WORKER_MB` を大きく置く設計です。  
Interpretation: 24GB 環境で `max_workers=2` 推奨が常時警告化し、運用ノイズが増えます。  
修正案: `summary/meta` に `memory_model_inputs`（base/shared/private/headroom/recommended）を必ず出力し、Phase 0 後に自動再校正タスクを必須化。  

3. 施策3（Aux cache ライフサイクル）: **INCONCLUSIVE**  
[Warning]  
Fact: stage境界 eviction と LRU の比較方針はあるが、採否閾値（何%で有意）が未定義です。  
Interpretation: 判断が主観化しやすいです。  
修正案: 採否基準を数値化（例: worker USS 15%以上削減 かつ wall-time 劣化5%以内）。  

4. 施策4（`__slots__`）: **INCONCLUSIVE**  
[Warning]  
Fact: `__dict__`/動的属性依存なしを「grep確認予定」としており、現時点で実証がありません。  
Interpretation: 互換性破壊の残リスクがあります。  
修正案: 事前に `vars(`, `.__dict__`, `object.__setattr__`, 継承箇所を網羅grepした結果を設計書に貼り付け、未検出を証跡化。  

5. 施策5（mmap SoA）: **INCONCLUSIVE**  
[Critical]  
Fact: `PriceBar list` 境界維持案だと worker 内再構築が残り、メモリ目的達成が不確実です。  
Interpretation: 高コスト実装の割に効果不達の可能性が高いです。  
修正案: 着手前に「再構築なしで評価 hot path が SoA を直接消費できるか」の PoC を必須ゲート化。成立しなければ別タスク化。  

[Warning]  
Fact: Decimal 精度保持方式が未確定です。  
Interpretation: L1/L2 決定論破壊リスクがあります。  
修正案: `scale-int`（固定小数点）を第一候補に固定し、float64 案は不採用を明記。  

**全体判定**
- **CHANGES_REQUESTED**

**決定論契約 (L1/L2) 追加提案**
- [Warning]  
Fact: 現行 L1 は `best` 中心比較で、世代内選抜列全体の同一性を直接は見ません。  
Interpretation: 微小な選抜ドリフトを見逃す余地があります。  
修正案: 世代ごとの `selected_genome_names` 全量一致チェックを追加。  

**先人の知恵（参照）**
- David Goldberg (1991), *What Every Computer Scientist Should Know About Floating-Point Arithmetic*  
- Brendan Gregg (2018), *Systems Performance, 2nd Edition*  
- Giampaolo Rodola, *psutil documentation (memory_full_info / USS)*（年は要確認）