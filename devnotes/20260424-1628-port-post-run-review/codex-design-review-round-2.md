**再判定**
1. 施策1 `post-run-review SKILL.md`: REQUEST_CHANGES  
2. 施策2 `improve-cycle hook`: APPROVE  
3. 施策3 `analyze-run 注記`: APPROVE  
4. 施策4 `concept stub`: APPROVE  
5. 施策5 `runbook 追記`: APPROVE  
6. 施策6 `terminology 追記`: APPROVE  

**全体判定**: CHANGES_REQUESTED

**残件（重大度順）**
1. [Warning] `--tmp_dir` の引数取り回しが不整合です。`TMP_DIR="$3"` だと、呼び出し例 `... <run_id> --tmp_dir <path>` では `$3` は `--tmp_dir` になります。  
該当: [detailed-design.md:96](/Users/ishitoya/repository/zenigame-fx/devnotes/20260424-1628-port-post-run-review/detailed-design.md:96)  
修正案: `"$3" == "--tmp_dir"` を検証し、`TMP_DIR="$4"` を採用するか、`while` でオプション解析してください。

2. [Suggestion] 文言の残存不整合があります（実装は `lockf` なのに説明が `flock`）。  
該当: [detailed-design.md:161](/Users/ishitoya/repository/zenigame-fx/devnotes/20260424-1628-port-post-run-review/detailed-design.md:161), [detailed-design.md:533](/Users/ishitoya/repository/zenigame-fx/devnotes/20260424-1628-port-post-run-review/detailed-design.md:533)  
修正案: `flock` 表記を `lockf` に統一。

---

ご指定4点への回答です。

1. `lockf -k -s -t 60` は妥当か  
妥当です。`man lockf` 上も `-k`（lock file保持）、`-s`（silent）、`-t`（待機秒）が定義されています。  
実運用の落とし穴は「timeout時に静かに失敗する」点なので、現在のように `|| { ... }` で明示エラー化しているのは正しいです。必要なら将来 `-w` 追加（特殊FS向け）を検討で十分です。

2. 環境変数経由で `'` `"` `$` `\` を含んでも安全か  
シェルインジェクション観点では、現方式（環境変数 + `"$PRR_*"` 展開）で安全です。  
ただし別問題として、`|` や改行を含むと `TODO.md` テーブルが壊れるため、`title/summary` の Markdownテーブル用サニタイズは別途必要です。

3. `run_in_background: true` と `sleep 1` の stagger は効くか  
効きます。起動呼び出しを逐次実行し、各呼び出し間で `sleep 1` すれば、launch時刻の分散は制御できます。  
注意点は「並列ツール一括起動を使わないこと」です（それをすると stagger は無効化されます）。

4. summary 30文字超過で skip した案の扱い  
完全 reject より「Phase 4 申し送りに残す」を推奨します。  
理由は、案の本質価値と要約失敗は別問題だからです。`deferred` に `reason=summary_too_long` を付けて次回再要約が最も運用上安全です。