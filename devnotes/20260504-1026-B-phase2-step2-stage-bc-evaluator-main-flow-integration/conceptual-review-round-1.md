**全体判定**  
`CHANGES_REQUESTED`

**方向性判断**  
推奨は `案B` です。`案C` の shadow LOG_ONLY 自体は妥当ですが、それを「step 2 完了」と定義するのは不適切です。実体としては `step 2.1` に相当し、`step 2.2 = 切替`、`step 2.3 = deprecation` までを含む段階分割として固定するべきです。`案A` は規模・回帰・レビュー可能性の観点で却下です。

**案C反証 (C9 Falsification-first)**

**Fact**
- 提示文面では、`stage_bc_evaluator.py` は実装済だが production caller が無く、main flow は依然として `stage_gate.py` 旧 API を使っています。
- T064 側の記述では、「置換は Phase 2 で main flow へ反映」とされており、step 2 は「統合本体」という位置付けです。
- 案Cの `3.3 live_criteria 達成への寄与` では、直接寄与は「なし」と明記されています。
- `BCEvaluationInput` 構築可能性、`shadow_pairs` 構築コスト、peak RSS はいずれも `To Verify` / `実測必須` です。
- shadow 結果は post-evaluation / archive に流さず、log-only に留める設計です。

**Interpretation**
- 以上から、案Cは「統合の準備段階」としては妥当でも、「Phase 2 切替コミット完了」と呼ぶには使命整合が弱すぎます。
- また、切替判断に必要な観測経路を作るだけで、mission 判定・GA fitness・archive 契約は何も前進しません。North Star に対する進捗の定義が曖昧になります。
- したがって、案C単独完結は不適切で、案Bとして step 2.1/2.2/2.3 を明示し、案Cの内容は 2.1 に格下げして扱うのが妥当です。

**観点別レビュー**

1. 使命との整合性  
[Critical] `step 2 = 案Cのみで完結` という定義は、North Star への直接進捗を生まないため不適切です。修正提案: `step 2` を `2.1 shadow / 2.2 switch / 2.3 deprecation` の3分割で正式化し、案Cの内容は `step 2.1` として再定義してください。  
[Warning] shadow log だけでは「切替判断に十分な証拠」が残る保証が弱いです。修正提案: `stage_bc_evaluator.shadow` に schema version と必須 field を定義し、切替判定で使う観測項目を事前固定してください。  
[Suggestion] `2.1 の成功条件` と `2.2 へ進む exit criteria` を分けて明記すると、使命への寄与が追跡しやすくなります。

2. 禁止事項違反  
[Critical] なし。  
[Warning] リスク緩和として書かれている「1/10 sampling」は、C3/C7 の観点で比較解釈を歪める可能性があります。修正提案: 本線 run 内 sampling ではなく、専用の shadow 検証 run を別建てにしてください。  
[Suggestion] 本設計は評価期間延長・live_criteria 緩和を行わない点を明示できており、この点は維持で良いです。

3. 実現可能性  
[Critical] `BCEvaluationInput` を main flow から組めるという核心前提がまだ未検証です。特に `trades / anchor_bundle / shadow_pairs` の構築で再 backtest が必要になるなら、24GB 制約下で成立しない可能性があります。修正提案: `builder は既存成果物を再利用し、追加の full backtest を禁止する` という設計制約を先に置いてください。  
[Warning] `parallel_eval` と `swim_lane` に同型 shadow 配線を足すと分岐重複が増えます。修正提案: caller 共通の wrapper を1か所に寄せてください。  
[Suggestion] 既にある `failure_handling.evaluate_bc_safe` を isolation boundary の中心に据える方が一貫しています。

4. 期待効果の妥当性  
[Critical] `(genome, individual_index)` だけでは後段 join 契約として弱いです。`individual_index` は run/generation/lane を跨いで安定とは限りません。修正提案: `run_id + generation + genome_hash(or digest) + individual_index` を最低契約にしてください。  
[Warning] 「shadow 観測 data の蓄積で切替判断可能」は方向として正しいですが、どの差分を見て何を falsify するかが未固定です。修正提案: `mission_pass 差分率`, `B gate pass 差分率`, `C pass depth 分布差`, `RSS`, `wall-clock overhead` を事前に固定してください。  
[Suggestion] 新旧結果を別イベント join で後から合わせるより、同一イベントに旧 API 要約と新 API 要約を並べる方が解釈が安定します。

5. リスク  
[Critical] メモリ超過リスクはこの設計の最大論点ですが、現状は「実測必須」で止まっています。修正提案: `shadow_enabled=True` は当面 default off に加え、`専用検証 run / 低 worker 数` を前提にしてください。通常 run へ載せるのは B4 達成後です。  
[Warning] 例外隔離は書かれていますが、log volume / I/O backpressure のリスクは未整理です。修正提案: shadow event は最小 field に絞り、1 genome 1 event の上限を明示してください。  
[Suggestion] 切替不能だった場合の rollback ではなく、`2.1 継続` を正規状態として認める基準も置くと運用が安定します。

6. スコープの適切さ  
[Critical] 「step 2 本丸」と「案C最小完結」が同居しており、スコープ定義が自己矛盾しています。修正提案: step 2 の名称を `Phase 2 integration program` に変え、その配下に `2.1/2.2/2.3` を置いてください。  
[Warning] `Phase 2 切替コミット` という言葉は `2.2` 完了時にのみ使うべきです。修正提案: 2.1 では `shadow integration` と呼称を分離してください。  
[Suggestion] 2.3 deprecation は 2.2 後の安定観測を経てからで十分です。

7. メモリ制約  
[Critical] 現状の概算では `step 1.8 の 5-10x` という自己評価が出ており、6 worker / 3GB 制約に対して楽観できません。修正提案: acceptance に `worker 数別の RSS 計測表` を追加し、`1, 2, 4, 6 workers` で確認してください。  
[Warning] `shadow_pairs` をコピーで持つ前提だと設計時点で危険です。修正提案: 参照共有・lazy materialization を原則にしてください。  
[Suggestion] メモリ budget は RSS だけでなく wall-clock 悪化率も併記した方が切替判断に有効です。

8. 前提検証 (C4)  
[Critical] `stage_c_lite_periods / stage_c_period` の source of truth が未確定です。`新規 config 必要?` のままでは設計前提が閉じていません。修正提案: 既存 config 再利用か新設かを先に確定してください。  
[Warning] `bc_result=None` 経路が常に走っている「可能性」は示されていますが、ここはまだ Fact ではありません。修正提案: 次 round では `Fact` と `Interpretation` を厳密に分離して記述してください。  
[Suggestion] 前提表の構造自体は良いです。未検証項目を step 2.1 の exit criteria に直結させるとさらに良くなります。

9. Design-first (C1)  
[Critical] なし。  
[Warning] 提示内容の範囲では docs/devnotes/git log を踏まえた整理はできていますが、T064/T065 と今回の `step 2/3` の対応表が不足しています。修正提案: 「既存計画上の名称」と「今回 segmentation 名称」の対応表を1つ追加してください。  
[Suggestion] 設計文書としては、`何を保持し、何をまだ切り替えないか` の境界が明確で、この点は良いです。

**結論**  
設計のコア発想自体は妥当です。特に `旧判定経路を不変に保った shadow 観測` という進め方は、Aより明確に優れています。ただし、`案Cを step 2 完了と呼ぶこと`、`join 契約の弱さ`、`メモリ前提未確定` はそのままでは通せません。  
修正後の推奨は次の一文です。`step 2 は案Bで固定し、今回の設計対象は step 2.1 shadow integration のみと明記する。2.2 切替と 2.3 deprecation への exit criteria を同時に定義する。`