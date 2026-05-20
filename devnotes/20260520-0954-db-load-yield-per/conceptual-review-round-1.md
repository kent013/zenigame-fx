**全体判定: CHANGES_REQUESTED**

以下は**貼付された概念設計文面のみ**を根拠にしたレビューです。  
`docs/devnotes/git log/最新コード` の直接照合は未実施なので、**C1 Design-first / C4 前提検証は保守的評価**にしています。

**前提確認 (C4)**
- `verified`: Run 82 で worker RSS 9.5GB、本日 smoke で main peak 10.7GB、施策 C は `yield_per` によるロード時ピーク削減が狙い、という主張。
- `unverified`: 実コードが本当に `.all()` で全件 materialize していること、`order_by(bar_time.asc())` の現実装、SQLAlchemy/psycopg 側で server-side cursor が有効化される条件、Session の寿命と identity map の残り方。

**観察された事実**
- main RSS が GA 開始前に 9.8GB まで上がるという観察がある。
- 設計書自身が「本施策では steady-state RSS は下がらない」と明記している。
- 設計書の試算でも、施策後は `main 8〜9GB + worker 9.5GB × 2 = 約27GB` である。

**解釈**
- 施策 C は**使命達成の前提条件としては妥当**です。
- ただし、**24GB 制約を満たす十分条件ではない**です。
- 技術的な成否は、`yield_per` の使い方ではなく、**「本当に全件バッファを避けられる実装契約を固定できるか」**に依存します。

## 観点別レビュー

1. **使命との整合性: [Warning]**
- Fact: 本施策は live_criteria に直接効かず、OOM 回避の前提整備として位置づけられている。
- Interpretation: 方向性は妥当です。ただし「OOM 余裕を確保する一歩目」と「使命達成に十分」は別です。
- 修正提案: 成功条件を「main のロード時 peak RSS を下げ、Run 完走可能性を上げる」に限定してください。`24GB×6 worker を満たす` とは書かない方がよいです。

2. **禁止事項違反: [Suggestion]**
- Fact: 評価期間延長、live_criteria 緩和、GA ハック、取引回数削減狙いは提案されていない。
- Interpretation: 明示的な禁止事項違反は見当たりません。

3. **実現可能性: [Critical]**
- Fact: 設計は `yield_per=N` と `partitions(N)` の二案を併記しており、`stream_results`、ORM entity か列タプルか、Session/identity map の扱いが未確定。
- Interpretation: ここが未固定だと、**client-side buffering が残る**、または **Session が ORM row を保持し続けて効果が出ない**経路が残ります。`partitions(N)` だけでは不十分な可能性があります。
- 修正提案: 詳細設計で次を固定してください。  
  `select(必要列のみ)` を `execution_options(stream_results=True, yield_per=N)` で実行し、**ORM entity ではなく列結果から PriceBar を組み立てる**。  
  ORM entity を使う場合は、**短命 Session** と **batch ごとの expunge/参照切断**まで契約化してください。

4. **期待効果の妥当性: [Warning]**
- Fact: 1〜2GB 削減見込みは、`n=1 smoke + n=1 本番 run + 1KB/bar 仮定 + コード読み仮説` に依存している。
- Interpretation: **C3/C7 の観点では強い causal claim には足りません**。 plausibility はあるが、証明ではありません。
- 修正提案: 「1〜2GB削減」を**仮説レンジ**に格下げしてください。判定基準は `before/after` の peak RSS とロード区間の滞在時間にし、**<1GB なら INCONCLUSIVE or REJECTED** を明記すべきです。

5. **リスク: [Critical]**
- Fact: 設計書は `L3 artifact bit equivalence: 保証` としている。
- Interpretation: これは現時点では**言い過ぎ**です。順序保持だけでは「artifact bit-identical」までは保証できません。加えて `yield_per` は SQLAlchemy 側の実装細部で挙動差が出やすいです。
- 修正提案: 保証レベルを**semantic equivalence**に下げてください。検証は「bar 数」「先頭/末尾時刻」「各 lane/aux の `(bar_time, OHLC, volume)` チェックサム一致」「Stage partition 結果一致」に置き換えるのが妥当です。

6. **スコープの適切さ: [Warning]**
- Fact: A/B/D/E を切って C のみに絞っている。
- Interpretation: **falsification-first の一手目としては妥当**です。ただし、設計書自身の試算でも C 単独では 24GB 制約を満たしません。
- 修正提案: 「C で transient double-hold 仮説をまず反証する。失敗または効果不足なら A か E に直行する」と stop/go 条件を明文化してください。batch size 調整を延々と回すのは避けるべきです。

7. **メモリ制約適合: [Warning]**
- Fact: 設計後試算でも約27GBで、24GB マシン制約を超えています。
- Interpretation: この文面のままだと「制約対応」と「部分緩和」が混線しています。
- 修正提案: 成果指標を二段化してください。  
  `Step C 合格`: main peak の削減。  
  `本番投入合格`: 想定 worker 数で総RSSが 24GB 枠内。  
  この二つは分けて書くべきです。

8. **前提検証 (C4): [Warning]**
- Fact: 実コード・設定・driver 条件の引用がない。
- Interpretation: 「`.all()` が主因」「server-side cursor で round-trip 影響は限定的」は、現時点では未検証前提です。
- 修正提案: 詳細設計の先頭に前提表を置いてください。最低でも  
  `実クエリ形` / `order_by` / `Session の生存範囲` / `driver の streaming 条件`  
  の4点を `verified/unverified` 付きで固定すべきです。

9. **Design-first (C1): [Suggestion]**
- Fact: 先行 devnotes への参照はある。
- Interpretation: 完全ではないが、設計の連続性はあります。
- 修正提案: 先行施策が**なぜ main pre-GA peak を下げなかったか**を 3 行で要約すると、設計の必然性がさらに明確になります。

10. **Falsification (C9): [Warning]**
- Fact: 「効果の限界」は書かれているが、「この施策で改善しない具体シナリオ」の列挙が薄い。
- Interpretation: まだ falsification-first としては弱いです。
- 修正提案: 少なくとも次を明記してください。  
  `aux_pair_bars_index の live size が主因なら効かない`  
  `Session/driver が全件保持するなら効かない`  
  `Decimal 断片化が主因なら効かない`  
  `holdout/aux/main の同時生存が支配的なら効かない`

**結論**
施策 C は**方向性としては妥当**です。  
ただし現状の文面は、**実装契約が甘い**ことと、**効果見込み・保証レベルが強すぎる**ことが問題です。  
修正すべき本質は 2 点です。

- `yield_per` ではなく、**「本当にストリーム化される実装契約」**を固定すること
- `1〜2GB削減` と `bit-identical保証` を、**検証可能な仮説と semantic equivalence** に言い換えること

この 2 点が入れば、概念設計としては `APPROVED` に近づきます。