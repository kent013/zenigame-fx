**全体判定**

`CHANGES_REQUESTED`

**前提検証（C4）**

- Fact: 提示された材料は概念設計テキストのみで、実際の [`SKILL.md`](/Users/ishitoya/repository/zenigame-fx/.claude/skills/zenigame-fx-analyze-run/SKILL.md)、関連 skill、`improve-cycle` 側の呼び出し定義、archive parquet 実体は未確認です。
- Fact: したがって本レビューは「概念設計としての整合性レビュー」であり、実装済み IF や実ファイル整合の最終確認ではありません。
- Interpretation: この条件下では、設計の方向性は概ね妥当ですが、前提未検証のまま skill 間 IF と分析対象を固定している箇所は修正が必要です。

**反証起点（C9, falsification-first）**

- Fact: この移植が失敗する最短経路は、`zenigame-fx-analyze-run` という新しい名前だけ整えても、実際には旧 skill や未移植 hook に流れて分析運用が変わらないケースです。
- Fact: 次に大きい失敗経路は、archive path / schema / primitive source-of-truth を「zenigame と同じ」と仮定したまま skill に埋め込み、run 後の分析が誤読になるケースです。
- Interpretation: したがって、今回の設計は「文言移植」だけでなく、「未検証前提の明示」「未移植 hook の契約定義」「旧 skill とのルーティング分離」まで入れて初めて安全です。

**観点1 使命との整合性**

- Fact: 設計は `live_criteria / (ii-lite) / Cross-pair` を分析対象として明示しており、Run 完了後分析を FX 文脈に寄せる意図があります。
- Interpretation: 方向性は使命に整合しています。特に「run 完了後の深層分析を FX イントラデイ文脈で正しく読む」こと自体は、live_criteria 到達に向けた改善ループの前提です。
- [Warning] 現状の記述だと「深層分析フローが単体・improve-cycle から呼べる」と期待効果に書かれている一方、深層分析本体の Python 拡張は別 TODO であり、実際にどこまで有効化されるかが曖昧です。期待効果が先行し、仕組み未整備の段階で運用が進んだように見えるリスクがあります。  
  修正案: 期待効果を「FX 文脈に沿った分析 runbook の整備」に限定し、「分析深度は現行 `analyze_run.py` の機能上限に従う」「深層分析の自動化は別 TODO 完了後に有効化」と明記してください。
- [Suggestion] skill の冒頭に「この skill の目的は live_criteria 未達の原因を、Stage A/B/C・コスト・Cross-pair 観点で誤読なく切り分けること」と一文で置くと、使命との接続がさらに明確になります。

**観点2 禁止事項違反**

- Fact: 「ショート禁止除外」「FX はロング・ショート両方向許容」と明記されています。
- Fact: `post-run-review` は未移植のためコメント化する案です。
- Interpretation: ショート禁止削除の方向自体は妥当です。むしろ FX でショートを禁じる文言が残る方が使命違反です。
- [Critical] `post-run-review` を単にコメント化すると、改善ループの末端で「分析結果を次の設計・TODO 化へ接続する責務」が曖昧になります。これは live_criteria 達成のための因果ループを弱めます。  
  修正案: コメント化ではなく、`zenigame-fx-post-run-review` 未整備時の暫定契約を明記してください。例: 「現時点では自動起動しないが、分析結果の出力フォーマットは将来の `zenigame-fx-post-run-review` が読む前提で固定する」「未整備時は no-op ではなく TODO を残す」。
- [Warning] 禁止事項への言及が「ショート禁止削除」に寄っていますが、FX 固有の禁止事項である「オーバーナイト保有前提」「スワップ・スプレッド無視」が分析観点に十分落ちていません。  
  修正案: skill の分析チェック項目に「保有時間分布」「セッション跨ぎ比率」「spread/swap が fitness にどう効いたか」を明示し、イントラデイ逸脱を検知する文言を追加してください。
- [Suggestion] 「ショートを許容する」だけでなく、「ロング偏重/ショート偏重が特定 pair・特定 session の構造由来かを確認する」と書くと、FX らしい分析になります。

**観点3 スコープの適切さ**

- Fact: スコープは `SKILL.md` の text port のみに限定され、`scripts/alpha_factory/analyze_run.py` の拡張は別 TODO とされています。
- Interpretation: 切り分け自体は妥当です。skill の概念整備と Python 実装拡張を分離する判断は、変更の因果を保ちやすいです。
- [Warning] ただし「archive parquet を Read / Python で直接読む指示」を skill に入れると、実質的に Python 実装仕様へ踏み込んでおり、text port only の境界が少し曖昧です。  
  修正案: 「現行 Python 実装が提供する read-only capabilities の範囲で archive を参照する」と表現を下げ、具体的な読取ロジックや深掘り手順は別 TODO に委譲してください。
- [Suggestion] スコープ外に「分析ロジックの精度改善」「新規メトリクス追加」も明記すると、今回が本当に文言移植だけだとさらに明確になります。

**観点4 移植方針の抜け漏れ**

- Fact: パス置換、旧 skill 名置換、primitive 置換、archive 参照、session 管理への整合を意識しています。
- Interpretation: 論点の洗い出しは良いですが、IF の固定点がまだ不足しています。
- [Critical] `fx-post-run-review` と `zenigame-fx-post-run-review` の命名が設計文中で揺れています。skill 名の揺れはそのまま呼び出し不能・将来移植時の誤接続につながります。  
  修正案: 未移植 skill 名を文書全体で `zenigame-fx-post-run-review` に統一し、将来の placeholder 名も同一に固定してください。
- [Warning] primitive の置換先は列挙されていますが、「その一覧の source-of-truth がどこか」が書かれていません。skill が primitive 名を内包すると、将来の定義更新で陳腐化しやすいです。  
  修正案: `SKILL.md` に primitive 群の一次参照先を明記し、skill 本文ではフル列挙より「Directional/Modulator/Pair-specific をその定義元に従って参照」と寄せてください。
- [Warning] session 管理について「zenigame-fx-manage-sessions 等との整合」を観点に挙げていますが、実装方針の本文では具体名・呼び出し規約が出ていません。  
  修正案: `zenigame-fx-codex-review`、`zenigame-fx-codex-vscode`、`zenigame-fx-manage-sessions` の 3 つを明示し、どの step でどの skill に依存するかを書いてください。
- [Suggestion] `run_ga.py` の成果物名、run directory、GenomeArchive の参照位置を 1 行で固定しておくと、将来の skill port でも再利用しやすくなります。

**観点5 zenigame-fx 固有事情の反映**

- Fact: Clause Genome / 32 primitive / Stage A/B/C / GenomeArchive / Cross-pair / LaneManager / `run_ga.py` が本文に入っています。
- Interpretation: 主要な Phase 2 基盤を意識できています。
- [Warning] ただし FX 固有事情のうち、「Cross-pair をどう分析の主軸に据えるか」がまだ弱いです。単に対象語を置換するだけでは、株版の単一市場発想を引きずる恐れがあります。  
  修正案: Stage B/C の分析観点に「pair 間の勝ち負けの偏在」「特定 pair 依存」「pair ごとのロング/ショート非対称」を追加してください。
- [Suggestion] LaneManager は用語差し替えだけでなく、「どの lane で落ちたか」を分析出力の標準軸に入れると有効です。

**観点6 skill 間 IF の一貫性**

- Fact: `zenigame-fx-codex-review` と `zenigame-fx-codex-vscode` 準拠を宣言しています。
- Interpretation: 方針は正しいですが、IF 契約がまだ宣言レベルです。
- [Critical] `improve-cycle` からの呼び出し先、`codex-review` への依存、未移植 skill へのフォールバックが文章上で未定義です。この状態だと「新 skill を作ったが既存オーケストレーションは旧 skill を呼ぶ」事故を防げません。  
  修正案: 概念設計に「呼び出し元/呼び出し先の契約表」を 5 行程度で追加してください。少なくとも `improve-cycle -> zenigame-fx-analyze-run -> zenigame-fx-codex-review -> zenigame-fx-codex-vscode`、`post-run-review は未接続` を固定すべきです。
- [Warning] `zenigame-analyze-genome-archive` をコメント化する案は、将来の `zenigame-fx-analyze-genome-archive` との IF を空白のまま残します。  
  修正案: 「現時点では analyze-run 内で archive の shallow read のみ許可し、deep archive analysis は `zenigame-fx-analyze-genome-archive` に委譲予定」と責務分界を書いてください。
- [Suggestion] session 管理は「長時間分析時のみ利用」「通常は不要」など運用基準も 1 行あると整合が取りやすいです。

**観点7 削除しない判断の妥当性**

- Fact: 既存 `zenigame-analyze-run` は削除せず、参照保持とする案です。
- Interpretation: 現段階では妥当です。移植初期に reference implementation を消さない判断は保守的でよいです。
- [Warning] ただし残置するなら、「どちらがデフォルトか」を明示しないと誤起動リスクがあります。  
  修正案: 概念設計に「zenigame-fx 系からは旧 skill を参照しない。旧 skill は reference-only」と明記してください。
- [Suggestion] 将来 `_archived/` 退避の判定条件を 1 行だけ書いておくと、残置が恒久化しません。例: `improve-cycle` と関連 skill の参照が全て fx 系へ切り替わった時点で退避検討。

**観点8 前提検証（C4）**

- Fact: 設計には「archive parquet のパス・スキーマは zenigame 版と揃っている」「28 列」「815 passed baseline を維持」などの前提があります。
- Interpretation: これらは設計の成立に重要ですが、本文上は verified / unverified の区別がありません。
- [Critical] 未検証前提が skill の設計根拠として使われています。特に archive schema 同一性と baseline 維持は、今回の text port の正当性を支える前提なので、未検証のまま断定するのは危険です。  
  修正案: 概念設計の「制約・前提」を `Verified` / `To verify before merge` に分けてください。最低でも `archive path/schema`, `関連 skill 名`, `improve-cycle 呼び出し先`, `baseline 815 passed` は分離が必要です。
- [Suggestion] skill 自体にも「前提が崩れていた場合は分析を継続せず、前提差分を first finding として報告する」と入れておくと C4 に強くなります。

**要約**

この設計は、「株版の analyze-run を FX 文脈に合わせて text port する」という骨子自体は妥当です。特に、ショート禁止の除去、Stage A/B/C・Cross-pair・GenomeArchive への言及、Python 実装を別 TODO に切る判断は良いです。

一方で、今のままだと 3 点が弱いです。`1)` 未検証前提の断定、`2)` 未移植 hook と skill 名の IF 不整合、`3)` 旧 skill 残置時のデフォルト経路不明です。ここを直せば、概念設計としては `APPROVED` に近づきます。