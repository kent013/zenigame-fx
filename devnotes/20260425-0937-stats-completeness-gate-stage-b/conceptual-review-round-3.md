全体判定: **APPROVED**

**Fact**
- Round 2 の 3 Critical は、Round 3 の改訂でいずれも設計上は解消されています。`run-report` 用の reason 永続化欠落は [archive.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/archive.py#L348) の拡張で埋められる形になり、underfilled 判定は [walk_forward.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/walk_forward.py#L22) の observed-day 契約に揃えられ、P13 も同ファイル読解で Verified 化されています。Stage B の実行点が [swim_lane.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/swim_lane.py#L487) であることとも整合しています。
- ただし、P14 の「15観測日 Verified」は提示根拠だけではまだ弱いです。また、run-report の reason histogram の分母定義と、underfilled skip 時の payload 既定値は設計本文で明示し切れていません。

**Interpretation**
- 実装に進んでよい水準です。残件は仕様の明確化であって、Round 2 のようなブロッカーではありません。

1. **使命との整合性**  
Fact: Round 2 の「問題定義ずれ」は解消です。現行 Stage B はすでに fail-closed で、Round 3 は「gate semantics 変更」ではなく「入力窓契約 + 監査性追加」に主語を固定できています。[stage_gate.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/stage_gate.py#L348)  
Interpretation: 使命との整合は十分です。  
[Critical] なし  
[Warning] なし  
[Suggestion] 背景・課題の主語を最後まで「Stage B への入力契約と可観測性」に統一するとさらに読みやすいです。

2. **禁止事項違反**  
Fact: Round 2 の `fold_sign_ratio` 意味変更問題は解消です。既存 `fold_sign_ratio` は維持し、別指標 `positive_fold_ratio_effective` を追加する設計になっています。既存 reason code も置換しません。[statistics.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/statistics.py#L234)  
Interpretation: 既存意味論の破壊はありません。  
[Critical] なし  
[Warning] なし  
[Suggestion] `stage-gates.md` だけでなく用語集側にも新指標名を追加すると監査が楽です。

3. **実現可能性**  
Fact: Round 2 Critical 1「reason 集計のデータ経路欠落」は解消です。現状 `collect_stage_b()` は `fold_sign_ratio` / `dsr` しか永続化しておらず、Round 3 の `stage_b_reason_codes` 追加はこの欠落を直接埋めます。[archive.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/archive.py#L348) [generate_run_report.py](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/generate_run_report.py#L406)  
Interpretation: 実装経路は成立しています。  
[Critical] なし  
[Warning] reason histogram の `n_total` が「全 archive 行」なのか「Stage B 評価対象行」なのか未定義です。Stage A fail 行を分母に混ぜると解釈がぶれます。修正提案: `n_stage_b_evaluated` か `n_stage_a_pass` を分母として明記してください。  
[Suggestion] `stage_b_reason_codes` は `";".join(...)` で十分ですが、report 側で multi-label をどう数えるかも 1 行定義しておくと安全です。

4. **期待効果の妥当性 (C3, C7)**  
Fact: Round 2 Critical 2「underfilled 判定式の SSOT 不一致」は解消です。現行 WF sufficiency は observed-day ベースで、`train + embargo + test > n_unique_dates` なら空 fold です。[walk_forward.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/walk_forward.py#L22) Run 7/8 は Stage A pass がある一方で `fold_sign_ratio: n=0` です。[run-7.md](/Users/ishitoya/repository/zenigame-fx/reports/run-reports/run-7.md#L58) [run-7.md](/Users/ishitoya/repository/zenigame-fx/reports/run-reports/run-7.md#L81)  
Interpretation: 効果主張は「window 不足を他要因から分離可能にする」に留まっており、C3/C7 に概ね準拠です。  
[Critical] なし  
[Warning] なし  
[Suggestion] 期待効果の文言は「機械的原因を観測可能化」までに留める今の方針で維持してください。

5. **リスク**  
Fact: Round 2 の taxonomy 二層化懸念は解消です。`stage_b_window_underfilled` を独立 canonical code と明示し、`no_folds` とは意味を分離しています。  
Interpretation: 監査軸の曖昧さはかなり減っています。  
[Critical] なし  
[Warning] なし  
[Suggestion] report の `other` は「既知列に入らなかった code の合計」と明記してください。ここが曖昧だと新 code 追加時の監査が鈍ります。

6. **スコープの適切さ**  
Fact: Round 2 の実装順序 Warning は解消です。`契約判定 → 永続化 → 可視化` の 3 段分解は妥当です。  
Interpretation: 実装の依存順は整理されました。  
[Critical] なし  
[Warning] underfilled skip 時の `StageResult.metrics.payload` の最小契約が未確定です。`n_fold_effective` を分布監視したいなら skip 行でも `0` を入れるか、意図的に `null` にするかを決める必要があります。修正提案: skip-path payload のキー集合を明記してください。少なくとも `n_unique_dates`, `n_fold=0`, `n_fold_unavailable=0`, `n_fold_effective=0` の扱いは固定した方がよいです。  
[Suggestion] この TODO の受け入れ条件に「underfilled 行が report で欠落しないこと」を 1 行追加すると良いです。

7. **メモリ制約**  
Fact: 追加 3 列のコストは軽微です。現行 archive のサイズ感から見ても問題ありません。[archive.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/archive.py#L51)  
Interpretation: メモリは論点ではありません。  
[Critical] なし  
[Warning] なし  
[Suggestion] むしろ Parquet schema 変更後の report 読み出し互換を優先監視すべきです。

8. **前提検証 (C4)**  
Fact: Round 2 Critical 3「P13 未検証」は解消です。`make_wf_folds` の sufficiency 契約はコード上で明確に読めます。[walk_forward.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/walk_forward.py#L57)  
Interpretation: 中核前提は Verified 化できています。  
[Critical] なし  
[Warning] 新規 P14 の「Run 7-9 = 15観測日 Verified」は、提示された run report からはまだ直接は言えません。そこから読めるのは期間幅と bar 数であって、`n_unique_dates` そのものではありません。修正提案: P14 は「15日幅の dataset で、141観測日要件を大幅に下回ることは確実」に言い換えるか、実 bars から `n_unique_dates` を数えて Verified 化してください。  
[Suggestion] C4 的には、P14 を exact count ではなく upper-bound claim に落とすだけでも十分です。

9. **Design-first 原則 (C1)**  
Fact: Round 2 の C1 不足は解消寄りです。今回の核となる [walk_forward.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/walk_forward.py#L22) と [swim-lane.md](/Users/ishitoya/repository/zenigame-fx/docs/alpha_factory/swim-lane.md#L92) が参照済みに入り、Stage 実行責務の位置も正しく押さえています。  
Interpretation: Design-first の読み順は妥当です。  
[Critical] なし  
[Warning] archive schema の SSOT は [genome-archive-schema.md](/Users/ishitoya/repository/zenigame-fx/docs/alpha_factory/concepts/genome-archive-schema.md) ですが、実装順序表にこの更新が入っていません。修正提案: `docs/alpha_factory/concepts/genome-archive-schema.md` を更新対象に追加してください。  
[Suggestion] `stage-gates.md` に加えて schema SSOT 更新も TODO に入れると、次の detailed design で迷いません。

Round 2 Critical の解消状況だけ要約すると、`stage_b_reason_codes` 永続化は解消、`wf_min_unique_dates()` による SSOT 共有も解消、P13 Verified 化も解消です。残る修正は P14 の表現精度と report / skip-path の仕様明記で、いずれも Warning 止まりです。