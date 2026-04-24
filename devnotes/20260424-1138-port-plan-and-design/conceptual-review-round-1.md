**全体判定**

CHANGES_REQUESTED

実ファイル・docs・git 履歴を確認せず、提示テキストのみで判定しています。その前提でも、方向性は概ね妥当ですが、C1 Design-first と C4 前提検証の充足が弱く、さらに「使命への効き方」が運用プロセス改善の説明に寄りすぎています。承認前に、使命直結の選定規律と前提確認手順を設計に明記すべきです。

**Fact**

- 提案は `zenigame-plan-and-design` を FX 向けに port し、`zenigame-fx-plan-and-design` を新設するものです。
- 差分は主に、skill 名、docs パス、todo manager 呼び出し、focus-theme パス、FX 固有の制約反映、未移植 hook のコメント化です。
- 3 Phase 構成で、TODO 選定、分析マージと合議、詳細設計とレビュー合議を定義しています。
- 使命・禁止事項は `zenigame-fx-codex-review` に集約し、本 skill では継承宣言のみとする方針です。
- 受け入れ基準には `grep` 0 件、未移植 hook のコメント化、`815 passed baseline 維持` が含まれています。

**Interpretation**

- port 方針自体は自然で、T020/T021 に揃える意図も理解できます。
- ただし、現状の文面では「計画策定 skill を整備すると live_criteria 達成にどう近づくか」がプロセス品質の言葉に留まっており、使命への因果接続が弱いです。
- また、存在確認されていないパス・スクリプト・状態ファイル契約を前提にしており、C1/C4 の観点では未確定事項が多いです。

**観点別レビュー**

1. 使命との整合性
- [Critical] TODO 選定基準が「live_criteria 未達のどの失敗モードを潰すか」に結びついていません。現状だと、レビュー品質や文書品質を上げる設計には見えますが、Sharpe / Total PnL / Max Drawdown / Trade Count / cross-pair を同時達成する個体探索への寄与が明文化されていません。  
修正提案: Phase A に「各 TODO は live_criteria の未達項目、想定因果経路、反証条件、成功判定」を必須記入させてください。
- [Warning] 期待効果が「品質ゲート復活」「設計品質の底上げ」に寄っており、使命 KPI ではありません。  
修正提案: 期待効果を「mission-facing KPI」に言い換え、例えば「Stage C 通過率」「cross-pair 落ち要因の削減」「コスト控除後 PnL 悪化要因の特定率」などに接続してください。
- [Suggestion] FX 固有制約として、イントラデイ、両方向、スワップ・スプレッド反映を各 Phase の判断基準に再登場させると、継承依存が強すぎず実務でぶれにくいです。

2. 禁止事項違反
- [Warning] 禁止事項は継承前提ですが、TODO 選定と改善策合議のプロンプト側に「見かけの成績改善」「取引回数削減による見栄え改善」「A/B/C 期間延長」排除規則が明示されていません。  
修正提案: Phase A/B の Codex プロンプトに、禁止事項 1,2,4,6,7 を rejection rule として明記してください。
- [Suggestion] 「ロングオンリー削除」は妥当です。代わりに「ショート追加で見かけだけ改善していないか」を点検項目に入れるとよいです。

3. 実現可能性
- [Critical] `scripts/codex`、`scripts/alpha_factory/todo_manager.py`、`config/alpha_factory/focus-theme.json`、`.cache/alpha_factory/current_cycle_state.json` の存在・I/F が本文中で未検証です。  
修正提案: 実装前提チェックを設け、「存在」「呼び出し方法」「入出力契約」「未存在時の fallback」を列挙してください。
- [Warning] 未移植 hook をコメント化する方針は妥当ですが、不在時に improve-cycle/autopilot 側が何を期待するかが未定義です。  
修正提案: 「hook 未接続時は no-op、成果物要求なし」と明文化してください。
- [Warning] `815 passed baseline 維持` は本文だけでは現行 zenigame-fx の最新ベースラインと一致するか不明です。  
修正提案: この受け入れ基準は「現行テストベースラインを悪化させない」に抽象化するか、具体値の出典を明記してください。

4. 期待効果の妥当性
- [Warning] 「Codex 合議を増やせば設計品質が上がる」はあり得ますが、mission 改善への因果は未証明です。  
修正提案: 「この skill 導入後に観測したい中間指標」を追加してください。例: TODO の棄却率、設計レビュー差し戻し率、run 後に同一論点が再発する比率。
- [Suggestion] 「分析マージの質が上がる」より、「仮説の重複・矛盾を減らす」と書く方が、改善対象が明確です。

5. リスク
- [Critical] 合議ループが長文化すると、実験速度ではなく文書整合性を最適化する危険があります。これは使命からの逸脱です。  
修正提案: B/C のループ回数上限と打ち切り条件を設定し、各ループで必ず「1つの反証可能仮説」と「1つの最小変更」に収束させてください。
- [Warning] `codex-review` への使命集約は保守上はよい一方、依存先更新でこの skill の挙動が暗黙に変わるリスクがあります。  
修正提案: 継承先の必須節名または必須 assertion を明記し、参照契約を固定してください。
- [Suggestion] focus-theme fallback が曖昧だと、テーマ不在時に一般論へ流れて TODO 品質が下がる恐れがあります。

6. スコープの適切さ
- [Warning] state file 更新仕様まで含める一方で、improve-cycle/autopilot 側改造はスコープ外としており、契約責任の境界がやや曖昧です。  
修正提案: 本 skill は「state file を読むだけ」なのか「更新も責務に含む」のかを明確化してください。更新するなら schema 出典を示してください。
- [Suggestion] scope は全体として過大ではありません。むしろ「run 実行はしない」「TODO 実装はしない」を明記するとさらに締まります。

7. 前提検証 (C4)
- [Critical] 「T020/T021 スタイル踏襲」「同パス使用」「fallback 動作」など、前提が verified と示されていません。  
修正提案: 設計冒頭に前提一覧を追加し、各前提を `Verified / Assumed / To verify` で分類してください。
- [Warning] `focus-theme.json は本 TODO 範囲では新設しない` としつつ、その読み先を変える設計です。  
修正提案: 「未存在時はどのテーマ集合を使うか」を固定文言で書いてください。

8. Design-first (C1)
- [Critical] docs/alpha_factory、devnotes、git log を参照済みという証拠が本文にありません。レビュー観点上、ここは未充足です。  
修正提案: 少なくとも「参照した文書名・設計ノート名・移植元/移植先の比較対象」を列挙してください。
- [Warning] `grep 0 件` は lint としては有効ですが、設計の正しさ証明にはなりません。  
修正提案: 受け入れ基準に「T020/T021 と同等の章立て・契約整合」「継承先 skill との参照整合」を追加してください。

**結論**

この設計は「port の方向」としては妥当です。ただし現時点では、使命への接続が弱く、未検証前提の上に組み立てられているため、そのまま承認はできません。  
承認ラインは明確で、次の 3 点を入れれば再レビュー可能です。

- TODO 選定を live_criteria 未達要因に直結させる
- 前提を `Verified / Assumed / To verify` で明示する
- 未移植 hook / state file / focus-theme 不在時の契約を固定する

この 3 点が入れば、APPROVED に近づきます。