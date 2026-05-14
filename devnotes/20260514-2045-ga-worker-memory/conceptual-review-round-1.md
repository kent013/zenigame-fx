**全体判定**  
CHANGES_REQUESTED

**Fact**
- 提示設計は、live_criteria の緩和や評価期間延長ではなく、GA 並列実行のメモリ圧迫を下げる基盤改善として整理されている。
- Phase 0 は `tracemalloc` または `sys.getsizeof` 系の計測を中核案としている。
- このレビューでは、ユーザー指定の制約によりコマンド実行と実ファイル読取を行っていない。したがって `docs/alpha_factory/`、`devnotes/20260427-1114-ga-parallel-workers/`、`git log`、対象コードの最新実体との照合は未実施である。

**Interpretation**
- 禁止事項への明示的な抵触は現時点では見えない。
- ただし、Phase 0 の計測設計と C1/C4 を満たす検証段取りが不足している。ここが曖昧なままでは、後段のレバー選択根拠が弱く、承認できない。

1. 使命との整合性  
[Warning] 使命への寄与が「探索基盤の安定化」に留まっており、成功条件が live_criteria 探索能力へどう接続されるかが弱いです。  
修正提案: 成功条件を「同一 seed・同一 dataset で評価結果不変」「swap/OOM なし」「1 run あたり wall-clock 改善」「pair 拡張時も完走可能」の4本で明文化してください。

2. 禁止事項違反  
[Suggestion] 提示案自体に、期間延長・閾値緩和・見かけの数値操作は見当たりません。  
[Suggestion] Phase 1-C に進む条件として「live_criteria / stage gate / dataset window は不変更」を設計本文に明記すると、禁止事項との境界がさらに明確になります。

3. 実現可能性  
[Critical] Phase 0 の計測手段として `tracemalloc` / `sys.getsizeof` を主軸に置くのは不十分です。これらは OS 観点の実メモリ圧迫、pickle 複製、allocator 断片化、共有ページ差分を直接表しません。今回の主題は RSS 実害なので、ここを外すとレバー選択を誤ります。  
修正提案: Phase 0 は OS レベルの `RSS` と可能なら `USS/PSS` を主指標にし、補助としてオブジェクト内訳を取る二層構成へ変更してください。成果物も「resident bytes」と「Python object bytes」を分けて出すべきです。  
[Warning] `spawn -> fork` は候補に残っていますが、macOS と依存ライブラリの fork safety 未検証のままでは危険です。  
修正提案: `fork` は本線ではなく「要件を満たした場合のみの実験枝」に降格し、優先順位は `cache lifecycle` と `shared store` を先にしてください。

4. 期待効果の妥当性  
[Warning] `__slots__` は妥当な軽量化策ですが、14〜22倍乖離を主に埋めるレバーと読むのは楽観的です。  
修正提案: Phase 0 の結果で `PriceBar/Ohlc` 自体の占有比率が高い場合のみ B を採用する、と優先順位を明記してください。  
[Warning] 直近 10 run の実測は「異常の存在」を示すには十分ですが、pair・期間・aux 構成をまたいだ sizing 根拠としては狭いです。  
修正提案: 少なくとも「対象 pair 代表例 × aux あり/なし × 1/2 worker」の計測マトリクスを追加してください。

5. リスク  
[Critical] 決定論・評価正しさに関する受け入れ基準が不足しています。メモリ改善で row-order、aux alignment、stage 判定が少しでも揺れると、使命達成に使う探索結果の信頼性が崩れます。  
修正提案: 実装前に「同一 seed / 同一 config / 同一 data / max_workers=1,2 で genome ranking・stage pass/fail・live_criteria 判定・cross-pair 判定が完全一致」を必須ゲートにしてください。  
[Warning] `_PROC_AUX_CACHE` の世代境界リセットは、メモリ改善の代わりに CPU 時間を悪化させる可能性があります。  
修正提案: 全消去ではなく、まずは cache size 計測を入れ、必要なら LRU もしくは stage 単位の bounded eviction を比較検討してください。

6. スコープの適切さ  
[Suggestion] 「まず計測、その後に独立レバーを段階適用」という切り方は適切です。  
[Suggestion] ただし Phase 1-C は別タスク起票前提に寄せた方が安全です。本設計に残すなら、着手条件をもっと厳密に書くべきです。

7. メモリ制約  
[Critical] 「per-worker メモリ前提の一本化」は必要ですが、shared store を導入する経路では線形な `worker_budget_mb // X` モデル自体が壊れます。`main + shared + private_per_worker * N` に分離しないと、再び誤った上限推奨を生みます。  
修正提案: `_check_memory_budget` は単一係数モデルではなく、`base_main_mb`、`shared_mb`、`private_worker_mb`、`headroom_mb` の4項モデルへ改める前提で設計してください。

8. 前提検証（C4）  
[Critical] 設計本文に、最新コード・設定・ドキュメントとの照合チェックリストがありません。今回の false-positive 防止 discipline ではここは必須です。  
修正提案: 実装開始条件として「spawn 採用理由」「決定論契約」「`PriceBar` の利用境界」「`AuxAlignmentCache` の寿命」「`_check_memory_budget` の現行式」を docs/devnotes/git log で再確認する Phase -1 を明記してください。

9. Design-first（C1）  
[Warning] このレビュー時点では `docs/devnotes/git log` 実読が未実施なので、最新整合性の確認は未了です。  
修正提案: 次のレビューでは、まず関連 docs/devnotes/git 履歴の確認結果を先頭に列挙し、その後で設計修正版を再提示してください。

設計の骨子自体は悪くありません。止めているのは「何を測れば今回の実害を説明できるか」と「最新実装前提の検証手順」がまだ甘い点です。Phase 0 を RSS 主体の計測設計に修正し、Phase -1 の確認手順と決定論ゲートを明文化すれば、再レビュー対象としては十分です。