[Critical] `zenigame-fx-batch-ga` を「内容の修正がほぼ不要で名前空間とパス参照だけ直せば使える 4 件」に含める根拠が弱いです。設計本文の時点で `extract_batch_metrics.py`、`compare_batch_runs.py`、`zenigame-fx-run-alpha-factory`、`zenigame-fx-run-report`、`zenigame-fx-calibrate-gate`、`zenigame-fx-improve-cycle` が未実装と明記されており、実行可能性が他 3 件と大きく異なります。これは「port-rename-only」の定義から外れています。少なくとも `batch-ga` は別枠に落とし、今回の 4 件ではなく「rename 先行の予約ポート」として扱うか、完了基準から「実行可能性」を外した設計名に変えるべきです。

[Critical] 完了基準が「旧パス・旧参照の grep 0 件」に寄りすぎており、依存未実装でも完了扱いになってしまいます。今回の目的は単なる rename ではなく「zenigame-fx 側で不足している運用補助スキルを揃えること」と書かれているため、少なくとも各 skill ごとに「実行前提チェック」と「未実装依存がある場合の期待挙動」を完了基準に入れないと、使命に対して成果物の意味が薄いです。

[Warning] 優先度判断にズレがあります。`manage-sessions` と `clear-cache` は即効性がありますが、`snapshot` と `batch-ga` は Alpha Factory 実体や run 成果物に依存します。現状が「インフラ未整備」の初期段階なら、4 件を一括で同優先度に置くより、`即時有効な skill` と `将来整合のための予約 port` を分けた方がスコープ管理として明確です。

[Warning] 置換マトリクスは十分に見えますが、「参照名置換の完全性」を担保する監査観点が不足しています。現行案の grep 対象は一部の旧文字列に限定されており、本文中の自然文、使用例、エラーメッセージ、補助説明に残る `zenigame-*` / `trading` / `alpha-factory` / `codex-vscode` を取りこぼす余地があります。マトリクス自体よりも、「4 ファイル全文から旧 namespace 接頭辞 `zenigame-` を網羅的に監査する」ルールを追加した方が安全です。

[Warning] `snapshot` の「対象ファイル表は zenigame-fx 側のパスに（実は同じ）」という書き方は、存在保証と命名整合を曖昧にしています。現時点で `winners_latest.json` / `candidates_latest.json` は未生成と明記されている以上、skill の役割は「存在する成果物のスナップショット管理」なのか「成果物がない段階でも config-only snapshot を許容する」のかを定義した方がよいです。ここが曖昧だと、利用者が「skill はあるのに使えない」と誤解します。

[Warning] `clear-cache` の例示 namespace を FX 文脈に書き換える方針は妥当ですが、`http`, `alpha_factory/runs`, `alpha_factory/sessions`, `oanda` が実際の zenigame-fx の namespace 設計と一致するかが前提未検証です。例示が事実上の準仕様になるので、ここは「既存 namespace に合わせる」か「未定なら仮例として明示する」必要があります。

[Suggestion] 依存関係の記述を skill 単位の箇条書きではなく、「依存マトリクス」にした方がよいです。列は `skill / 必須 script / 必須 artifact / 必須 related skill / 未充足時の扱い` 程度で十分です。これにより、`rename-only` で成立するものと、成立しないものが一目で分かります。

[Suggestion] リスク対応の「依存スクリプトが未実装の場合は当該スクリプトの実装を先に行う」は正しいですが、skill 側の実行ガイドとしては弱いです。少なくとも「実行を中断して不足依存を明示する」「代替で zenigame 側を参照しない」を方針に加えた方が、独立コードベース原則と整合します。

[Suggestion] 使命・禁止事項の委任方針は概ね一貫しています。ただし、4 skill のうち `manage-sessions` と `clear-cache` は Alpha Factory の戦略改善判断より運用補助の比重が強いため、全てに同じ濃度で North Star を背負わせるより、「判断が絡む skill は `zenigame-fx-codex-review` を参照」「単純運用 skill は必要時のみ参照」と整理した方が、責務境界が明確になります。

全体判定: NEEDS_REVISION

修正の中心は 2 点です。`batch-ga` を今回スコープに残すなら「rename-only」ではなく「将来依存を含む予約移植」と定義を直すこと。もう 1 点は、完了基準を文字列置換完了ではなく「各 skill の実行前提と未充足時挙動が明示されていること」まで引き上げることです。これが入れば、目的・スコープ・リスクの整合性はかなり改善します。