**指摘（重大度順）**
1. [Critical] `flock` 前提が環境不整合です。設計は `flock` を必須化していますが、現環境で `command -v flock` は未検出（exit=1）でした。該当: [`detailed-design.md:153`](/Users/ishitoya/repository/zenigame-fx/devnotes/20260424-1628-port-post-run-review/detailed-design.md:153), [`detailed-design.md:167`](/Users/ishitoya/repository/zenigame-fx/devnotes/20260424-1628-port-post-run-review/detailed-design.md:167)  
修正案: `macOS` 標準の `lockf` に置換（例: `/usr/bin/lockf -s /tmp/zenigame-fx-todo-add.lock sh -c 'next-id && add'`）し、コマンド存在チェックを明記してください。

2. [Critical] 「接続済」の根拠がコメント書き換えのみで、実起動手順が不十分です。施策2はコメント更新中心で、実際の launcher 手順（marker 検査→5テーマ起動→marker書込→失敗時処理）が Phase 手順として定義されていません。該当: [`detailed-design.md:257`](/Users/ishitoya/repository/zenigame-fx/devnotes/20260424-1628-port-post-run-review/detailed-design.md:257), [`detailed-design.md:270`](/Users/ishitoya/repository/zenigame-fx/devnotes/20260424-1628-port-post-run-review/detailed-design.md:270), 現行 [`zenigame-fx-improve-cycle/SKILL.md:265`](/Users/ishitoya/repository/zenigame-fx/.claude/skills/zenigame-fx-improve-cycle/SKILL.md:265)  
修正案: improve-cycle の Phase 1 本文に「実行ステップ」として明文化してください（C2 の launch owner 単一化を実装可能な粒度まで）。

3. [Warning] 変数名不整合があります。早期スキップ例で `RUN_ID` が未定義のまま summary 出力に使われています。該当: [`detailed-design.md:109`](/Users/ishitoya/repository/zenigame-fx/devnotes/20260424-1628-port-post-run-review/detailed-design.md:109)  
修正案: `RUN_ID="$2"` を冒頭で固定し、全フェーズで同一変数を使う規約に統一。

4. [Warning] `summary` 30文字制約が設計上は要求される一方、追加コマンド側に強制バリデーションがありません。`todo_manager.py add` は長さ制限を持たず、`todo-add` も「警告」止まりです。該当: [`detailed-design.md:89`](/Users/ishitoya/repository/zenigame-fx/devnotes/20260424-1628-port-post-run-review/detailed-design.md:89), [`todo-add/SKILL.md:78`](/Users/ishitoya/repository/zenigame-fx/.claude/skills/zenigame-fx-todo-add/SKILL.md:78), [`todo_manager.py:171`](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/todo_manager.py:171)  
修正案: post-run-review 内で `len(summary) <= 30` を fail-fast で強制（超過時は短縮再生成または skip）。

5. [Warning] シェル引数クォートが脆弱です。`TITLE/SUMMARY` を単引用符で直接埋め込みしており、`'` を含むと壊れます。該当: [`detailed-design.md:157`](/Users/ishitoya/repository/zenigame-fx/devnotes/20260424-1628-port-post-run-review/detailed-design.md:157)  
修正案: 安全な受け渡し方式（環境変数+python、または厳密エスケープ）に変更。

6. [Warning] C2 観点でドキュメント間の経路表現が衝突しています。concept stub は `improve-cycle / analyze-run` 両方 hook 起動と読めます。該当: [`post-run-review.md:29`](/Users/ishitoya/repository/zenigame-fx/docs/alpha_factory/concepts/post-run-review.md:29)  
修正案: 「launch owner は improve-cycle のみ、analyze-run は手動起動のみ」に統一記述。

7. [Warning] メモリ制約（24GB/6worker）に対する運用ガードが未定義です。5 BG agent が Phase 4 と重なる場合の上限制御が詳細設計にありません。  
修正案: `max_parallel_review_agents` と timeout/cancel 方針を明記（未測定なら C8 として INCONCLUSIVE 宣言）。

8. [Suggestion] レビュー観点2の文言が旧prefix (`[review:THEME]`) のままです。該当: [`detailed-design.md:436`](/Users/ishitoya/repository/zenigame-fx/devnotes/20260424-1628-port-post-run-review/detailed-design.md:436)  
修正案: `[r:{code}]` に修正。

**施策別判定**
1. 施策1（post-run-review SKILL 新規）: REQUEST_CHANGES  
2. 施策2（improve-cycle hook 更新）: REQUEST_CHANGES  
3. 施策3（analyze-run 注記更新）: APPROVE  
4. 施策4（concept stub 新規）: REQUEST_CHANGES  
5. 施策5（runbook 追記）: APPROVE  
6. 施策6（terminology 追記）: APPROVE  

**C4 前提検証**
- Fact: `todo_manager.py list` 出力は `## Open (N)` 形式で、`awk` 方針自体は適合。  
- Fact: `flock` は現環境で未検出、`lockf` は存在。  
- Interpretation: 排他戦略は「考え方は正しい」が「実行手段が環境不適合」。  

**C3/C7/C8**
- 相関・予測の因果 claim は本詳細設計には実質なし。  
- 「5倍化」等の効果は測定計画未定義のため INCONCLUSIVE 扱いが妥当。  

**全体判定**
CHANGES_REQUESTED