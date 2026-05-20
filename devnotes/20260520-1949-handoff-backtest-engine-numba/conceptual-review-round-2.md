**全体判定: APPROVED**

概念設計としては承認可能です。Round 1 の Critical は、概念段階で決めるべき方針としては解消されています。  
ただし、詳細設計に入る前に 2 点だけ Warning として文言を補強してください。どちらも Critical ではありませんが、放置すると実装時に GA 不変性の検証漏れになります。

**Fact**

- 改訂版は `selection pressure を一切変更しない performance-only change` を 1 行契約として明記しています。
- `float64` は本線から外され、`scaled-int` のみを本番採用候補にしています。
- event ordering は `engine.py:147-199` 由来として 10 step に分解されています。
- golden parity は best 一致から、全 genome metrics / trade log / equity curve / constraint flags / selection input tensor へ拡張されています。
- 丸め契約表、event read/write state、corner case 期待動作、overflow 上界の具体値は詳細設計フェーズの成果物として残されています。
- 本レビューではコマンド実行をしていないため、提示された `file:line` の妥当性は本文上の claim として扱っています。

**Interpretation**

- 概念設計と詳細設計の切り分けは妥当です。概念段階では「scaled-int 限定」「float64 分離」「不変性を主契約にする」「event order を SoT から固定する」「golden 粒度を広げる」まで決まっていれば十分です。
- 丸め表や overflow 上界の具体値は、現行 Decimal 実装を読みながら作る詳細設計成果物なので、概念設計に全て書き切る必要はありません。
- 残る主要リスクは、broker 以外の入力変換、特に composite/signal の呼び出し形態変更が selection に触れる可能性です。

**観点別レビュー**

1. 使命との整合性  
[Suggestion] 問題ありません。wall 短縮によって同一予算で探索回数を増やす案であり、live_criteria 達成への間接貢献として筋が通っています。

2. 禁止事項違反  
[Suggestion] 明示的違反はありません。評価期間、閾値、trade_count 削減、worker 増加、Stage B skip に触れていないため、禁止事項との衝突は見えません。

3. 実現可能性  
[Warning] `Decimal 厳密性が要るのは broker のみ` という表現は少し強すぎます。Decimal 厳密性は broker に閉じる、という意味なら妥当ですが、selection 不変性は composite/signal vector にも依存します。  
修正提案: 「Decimal 丸め一致が必要なのは broker。selection parity は broker 入力である composite/signal vector も対象」と書き換えてください。

4. 期待効果の妥当性  
[Suggestion] `10〜数十×` の外挿を撤回し、複数 run の median wall reduction を KPI にした点は適切です。C7 対応として十分です。

5. リスク  
[Warning] golden parity に `composite vector / entry signal / exit signal / order intent` を明示追加した方が安全です。`selection input tensor` だけだと、上流の signal 差分が偶然 selection に出なかったケースを見逃します。  
修正提案: golden 比較項目に `per-bar composite value`, `entry/exit boolean`, `submitted order intent` を追加してください。

6. スコープ  
[Suggestion] `single pair / fixed config / single-thread reference parity` への限定は妥当です。初回実装の失敗面を十分に狭めています。

7. メモリ制約  
[Suggestion] 本件の主論点から外してよいです。T106/T107 済みという前提で問題ありません。

8. 前提検証  
[Suggestion] SoT 表を追加したことで C4 は概念段階では満たしています。ただし詳細設計では `verified` を再確認ログ付きにしてください。現レビューでは提示テキスト以上の検証はしていません。

9. Design-first  
[Suggestion] Round 1 で不足していた「何を不変とみなすか」はかなり明確になりました。詳細設計はまず `observable behavior contract` の仕様書から始めるのがよいです。

**重点論点**

A. 数値表現  
[Suggestion] `scaled-int` 本線、`float64` 別 branch は正しい判断です。複数スケール分離も妥当です。

B. njit kernel 実装可能性  
[Suggestion] 現時点では承認可能です。丸め表、overflow 上界、debug sentinel が詳細設計の承認条件に残っているため、実装前の安全弁があります。

C. path 依存ループ統合  
[Suggestion] event ordering と corner case 一覧が追加されたため、概念上は成立しています。詳細設計では各 step の `read/write state` と同一 bar 競合の期待動作を必ず固定してください。

**承認条件の扱い**

この切り分けで妥当です。概念設計は `APPROVED`。  
詳細設計に進む前の軽微な補強として、`composite/signal/order intent parity` を golden に追加し、`Decimal 厳密性は broker のみ` という表現を `Decimal 丸め一致は broker、selection parity は上流 signal も含む` に修正してください。