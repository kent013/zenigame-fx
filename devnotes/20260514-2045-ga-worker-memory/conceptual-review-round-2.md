**全体判定: APPROVED**

ただし条件付きです。Round 1 の Critical 4 件は、概念設計レベルでは解消されています。一方で、Phase -1 の出典事実はこのレビューでは実ファイル照合していないため、「提示された前提が正しいなら APPROVED」です。実装前レビューでは、該当 docs/devnotes/git log の再確認が必要です。

**Fact**
- Phase 0 は RSS/USS を主指標、Python object bytes を補助指標に分離された。
- 決定論ゲートは `max_workers=1/2`、同一 seed/config/data、ranking・stage 判定・live_criteria・cross-pair 判定の一致まで拡張された。
- `_check_memory_budget` は単一 per-worker 係数ではなく、`base_main_mb + shared_mb + private_worker_mb*N + headroom_mb` の4項モデルへ修正された。
- Phase -1 に docs/devnotes/git log 由来の前提検証結果が追加された。

**Interpretation**
- 設計の方向性は、値いじりではなく「メモリ圧迫の構造把握と探索基盤の安定化」に寄っており、North Star と矛盾しない。
- SharedBarStore 起票条件を原設計自身の 2.1GB guard に結びつけた点は妥当。
- 残るリスクは、計測結果の読み違いと、実装時に決定論ゲートが「代表ケースだけ」になってしまうこと。

**観点別レビュー**

1. 使命との整合性  
[Suggestion] live_criteria を直接改善する設計ではないが、探索実行の安定化として整合している。成功条件に「評価不変」「swap/OOM 解消」「pair 拡張前提」が入ったため、Round 1 の懸念は概ね解消。

2. 禁止事項違反  
[Suggestion] stage window、live_criteria、stage gate 閾値を変更しない制約が明記されており、禁止事項への抵触は見当たらない。

3. 実現可能性  
[Warning] Phase 0 の二層計測は妥当。ただし「resident bytes を要素別に分解する」と読める箇所は注意が必要。RSS/USS は原則プロセス単位で、要素別分解は Python object bytes 側の推定になる。  
修正提案: 成果物の表を「プロセス単位 RSS/USS」と「要素別 object bytes」に分け、resident の要素別帰属は差分実験で推定すると明記してください。

4. 期待効果の妥当性  
[Warning] 「wall-clock 非劣化」は強すぎます。cache eviction や shared mmap 化では CPU とメモリの trade-off があり、swap 回避により実運用上は改善しても、短縮 run では同等未満に見える可能性があります。  
修正提案: 成功条件を「swap 回避後の総実行時間が悪化しない」または「CPU-only 比較で許容範囲内、実運用 wall-clock は改善」に分けると判断を誤りにくいです。

5. リスク  
[Warning] 決定論ゲートは十分に強いが、比較対象に「改善前後」と「worker 数差分」の両方を明示した方がよいです。現文でも読めますが、実装時に片方だけになりやすい。  
修正提案: `baseline max_workers=1/2` と `changed max_workers=1/2` の4条件比較にし、各条件で同一 artifact を比較する、と明文化してください。

6. スコープの適切さ  
[Suggestion] A→B→C の段階性、fork の実験枝降格、1-C 着手条件の明文化により適切。SharedBarStore は起票条件充足済みだが、Phase 0 後に着手する制御が残っているため過剰スコープには見えない。

7. メモリ制約  
[Suggestion] 4項モデルは妥当。特に shared store 導入後に `private_worker_mb * N` と `shared_mb` を分離する判断は正しい。  
[Warning] `headroom_mb` の決め方が未定義です。24GB マシンでは OS、DB、ログ、同時プロセスの余白が実害に直結します。  
修正提案: `headroom_mb` は固定値ではなく、最低 4GB または物理メモリの一定割合など、初期ルールを Phase 0 後に決めるとしてください。

8. 前提検証（C4）  
[Suggestion] Phase -1 の項目は C4 を満たす構成になっています。spawn 採用理由、決定論契約、原設計メモリ試算、現行式、cache 寿命、T057 差分が揃っており、設計判断に必要な前提は列挙されています。  
[Warning] このレビューでは実ファイル照合をしていないため、Fact の真正性は未検証です。  
修正提案: 実装タスク化時に、Phase -1 の各出典へ実際の行番号または commit hash を付けて固定してください。

9. Design-first（C1）  
[Suggestion] Round 1 の欠落は設計本文上は解消されています。特に「原設計自身の SharedBarStore 起票条件」を根拠にした点は、grep ベースの思いつきではなく設計履歴に基づく判断になっています。

**結論**
Round 2 は概念設計として承認可能です。実装前に直すべき主な点は、RSS/USS と object bytes の帰属を混同しない表現、4条件の決定論比較、`headroom_mb` の決め方です。これらは設計の方向性を変えるものではなく、実装時の誤読を防ぐ補強です。