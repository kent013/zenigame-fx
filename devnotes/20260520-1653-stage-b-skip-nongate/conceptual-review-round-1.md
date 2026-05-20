**全体判定**

`CHANGES_REQUESTED`

**Fact**

- 本変更案は、`Stage B` の実行順を `IS-monitor/canonical -> fold gate` から `fold gate -> pass 個体のみ IS-monitor/canonical` に変え、`fold gate` 失敗個体では非ゲート observability をスキップする、という設計です。
- 設計書の根拠は主に、`stage_gate.py` の docstring / コメント / `reasons` 構築箇所の読解に基づいています。
- 期待効果の `~21%` は、Run 82 の一部世代の通過率と、`242k×2` vs `~115k` の概算コスト比から導いた推定です。
- 本レビューは、ユーザーの制約どおりコマンド実行なしで、貼付された概念設計本文だけを根拠にしています。コード本文の独立検証は未実施です。

**Interpretation**

- 方向性自体は妥当です。使命との整合もあります。`GA 結果不変` が本当に成立するなら、これは「探索加速のための wall-time 削減」であり、禁止事項の `数値改善` や `live_criteria 緩和` には当たりません。
- ただし現時点の設計書は、最重要論点である `GA 結果が本当に不変か` を証明するには不足しています。局所関数内で `非ゲート` に見えることと、全パイプラインで意味的に無関係であることは別です。
- したがって、今のままでは承認できません。特に `Q1` と `Q2` の falsification が足りません。

**観点別レビュー**

- `1. 使命との整合性`  
  `[Suggestion]` 整合しています。`live_criteria` そのものを緩めず、探索速度だけを改善するという位置づけは妥当です。  
  修正提案: 設計書に「本施策の成功条件は quality 不変 + wall-time 短縮であり、quality 改善は目的外」と明文化してください。

- `2. 禁止事項違反`  
  `[Warning]` 現状の書き方だと「結果が変わらない前提の最適化」です。前提が崩れると即 `GA ハック` 側に倒れます。  
  修正提案: 「差分許容範囲」を明文化してください。許容差分は `非ゲート shadow 列の skipped 表現のみ`、それ以外の `fitness / survivor / archive gate 列 / Stage C candidate` 差分は即 reject と定義すべきです。

- `3. 実現可能性`  
  `[Suggestion]` 実装自体は小さめです。順序変更と条件分岐、archive 出力の扱いが主です。  
  ただし「小変更だから安全」とは言えません。安全性の主戦場は実装難度ではなく依存経路の洗い出しです。

- `4. 期待効果の妥当性`  
  `[Warning]` `~21%` はまだ強い主張です。根拠は単一 run の単一世代寄りの概算で、`bar 数比例 = 時間比例` を暗黙に置いています。`C7` 的にも十分な裏付けとは言えません。  
  修正提案: `21%` は「仮説レンジ」に下げるべきです。表現は `0-25% の可能性、中心仮説は 10-20%` 程度が妥当です。さらに `Stage B` の `IS-monitor / canonical / fold` の内訳計測を先に要求してください。

- `5. リスク`  
  `[Critical]` 最大リスクは 2 つです。  
  1. `IS-monitor/canonical` の値そのものではなく、「実行したこと」による副作用依存。キャッシュ温め、lazy init、global state、乱数消費、例外経路、ログ順序依存があると、fold 結果や後段決定論が変わりえます。  
  2. `非ゲート` の確認が局所読解に留まっていて、下流 consumer の意味的依存が未検証です。  
  修正提案: 次を概念設計の必須前提に追加してください。  
  - `payload field` ごとの consumer inventory  
  - `IS-monitor/canonical` 実行有無で `fold metrics` が byte-exact に一致すること  
  - `survivor set / archive row count / Stage C candidate set` が一致すること

- `6. スコープの適切さ`  
  `[Suggestion]` スコープは概ね適切です。`Stage B` 内に閉じていて、期間・閾値・trade count に触れていません。  
  ただし archive / report / audit consumer はスコープ内として明示した方がいいです。そこをスコープ外に置くと安全性証明が崩れます。

- `7. メモリ制約`  
  `[Warning]` CPU 削減案ですが、メモリ検証がありません。fold を先に回した後に IS-monitor を後置きすると、オブジェクト寿命やキャッシュ保持で peak RSS が変わる可能性があります。  
  修正提案: `wall` だけでなく `peak RSS` と `per-worker RSS` を成功条件に追加してください。少なくとも「悪化しない」を確認対象にすべきです。

- `8. 前提検証 (C4)`  
  `[Critical]` `IS-monitor 非ゲート` の主張は、設計書の引用範囲では `局所的にはもっともらしい` ですが、`コードと一致するか` の観点では未達です。`Q1` の本丸です。  
  修正提案: 前提表を次の粒度まで拡張してください。  
  - `gate decision 参照 field`  
  - `fitness / selection / archive serialization / Stage C promotion / cross-pair aggregation / report generation` の各 consumer  
  - 各 consumer で `is_full_*` / `canonical_*` が `read されるか / read されても意味的に非決定か`

- `9. Design-first (C1)`  
  `[Warning]` 局所コード行と docstring を起点にしている点は良いです。  
  ただし `design-first` としては、設計契約の読み込みがまだ足りません。コメント 1 本では弱いです。`docs/alpha_factory/stage-gates.md` や archive schema 契約、run report 契約まで落とし込む必要があります。  
  修正提案: `設計契約 -> 実装 -> consumer` の順で証拠を並べ直してください。

- `10. Falsification (C9)`  
  `[Critical]` いまの falsification は「削減幅が小さいかも」「audit 要件に触れるかも」止まりで、最重要仮説の反証設計が弱いです。  
  修正提案: 反証条件を先頭に置いてください。  
  - 同 seed で `Stage B pass/fail vector` が 1 件でも変わったら reject  
  - `fitness ranking` が 1 件でも変わったら reject  
  - `Stage C candidate set` が変わったら reject  
  - `archive gate 列` が変わったら reject  
  - `shadow 列以外` に差分が出たら reject

**Q1 への回答**

`「IS-monitor + canonical_five は非ゲートなので fold-gate 失敗個体でスキップしても GA 結果不変」` は、現時点では **妥当そうだが未証明** です。私はこのままでは認めません。

不足している確認は次です。

- `is_full_sharpe`, `is_full_total_pnl`, `canonical_shadow_b_is` 系の全 consumer を洗うこと
- `archive gate 列` だけでなく、`archive から後段が読む非 gate 列` の存在を確認すること
- `Stage C` 候補選抜、cross-pair 集計、best genome tie-break、report / audit 生成がそれらを参照しないこと
- 値参照だけでなく、`IS-monitor を実行したこと` 自体の副作用が無いことを確認すること

要するに、`「非ゲートだから安全」` ではなく、`「どこにも意味的依存が無い」` を示す必要があります。

**Q2 への回答**

順序変更の決定論は、`backtest/evaluator が純粋関数に近い` なら維持できますが、そこが未検証です。したがって **条件付きでのみ妥当** です。

既存テストへの影響はかなりありえます。

- `log 順序` が変わる
- `shadow 列` の期待値が変わる
- 例外 sentinel の扱いが変わる
- timing 系テストがあれば壊れる

必要なのは unit test よりむしろ golden test です。`同一 seed / 同一 config / 同一 dataset` で、`Stage A/B/C の決定結果と fitness 系` が不変であることを先に押さえるべきです。

**Q3 への回答**

`失敗個体で sentinel` 自体は許容余地がありますが、**既存 except sentinel の再利用だけは非推奨** です。

理由は単純で、`skip by design` と `compute failed` が同じ表現になるからです。これは observability を下げます。監査上も悪いです。

許容するなら最低でも次が必要です。

- `shadow_status = "computed" | "skipped_fold_gate_fail" | "error"` の明示
- 既存 sentinel 値とは別に status を持つこと
- report / audit 側で `skipped` と `error` を分離表示すること

失敗個体の IS shadow が常に必要とは思いません。ただし「不要だから潰してよい」ではなく、「不要だが skipped と error は区別すべき」です。

**結論**

この設計は、発想としては良いです。使命にも反していません。  
ただし承認には、`非ゲート` の局所主張を `全経路の不変性証明` に引き上げる必要があります。特に `Q1` はまだ未達です。次版では、`consumer inventory`、`副作用否定`、`skip/error の区別`、`reject 条件の明文化` を追加してください。