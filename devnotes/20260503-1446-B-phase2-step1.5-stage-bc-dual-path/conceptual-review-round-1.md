**全体判定**: `CHANGES_REQUESTED`

**前提 (C4)**
- 本レビューは、ユーザー提示テキストのみを根拠にした概念設計レビューです。
- `docs/alpha_factory/`、`devnotes/`、`git log`、実コード断片はこの場で独立検証していません。
- したがって、コード実在性や最新整合性に関する指摘は「未検証前提あり」です。

**Fact (C6)**
- 本設計の仮説は、「Stage B IS monitor と Stage C base evaluation に dual-path LOG_ONLY 配線を追加すれば、凍結済み adapter/helper を再利用したまま canonical_metrics 観測範囲を広げ、step 2 の calibration data を確保できる」です。
- スコープには `Stage B per-fold` と `Stage C stress/cross_pair` が含まれていません。
- `regression 0` は、既存判定経路不変・例外隔離・archive schema 不変を根拠に主張されています。
- Stage B 側の `window_days` 案は `stage_b_window_months * 30` です。
- 効果検証案として `smoke 5 Run` が挙げられています。

**Interpretation (C6)**
- 最も弱い点は、「step 2 に必要な calibration data がこれで十分に揃う」という主張です。
- 次に弱い点は、「regression 0」が機能回帰だけでなく運用回帰まで含めて rigorous に示されていないことです。
- 最後に、18 か月窓での threshold scaling と memory 上限が、現設計ではまだ実証不足です。

**観点別レビュー**

1. 使命との整合性
- [Critical] `step 2 の前提条件を満たす` という主張が強すぎます。Stage B の判定本体は per-fold OOS 側にあり、Stage C の使命達成には cross-pair(ii-lite) も含まれます。`B_IS + C_base` だけでは、判定切替に必要な calibration を十分に代表していない可能性があります。  
  修正提案: 本 step の到達点を「step 2 用 calibration data の一部を先行取得」に下げて明記してください。もし `step 2 前提条件` を維持したいなら、最小追加として `Stage B per-fold の集約ログ` か `Stage C cross-pair の軽量観測フック` のどちらかを含めるべきです。
- [Warning] live_criteria 達成への寄与が「間接的」と整理されている点は妥当ですが、成功条件が曖昧です。  
  修正提案: 本 step の成功条件を「各 stage で canonical sidecar が生成される」ではなく、「step 2 の判断に使える差分分布が取れる」に再定義し、そのために必要な観測粒度を明示してください。
- [Suggestion] 「mission への直接寄与は薄いが、判定切替の falsification データ確保が目的」と明文化すると、過大主張が減ります。

2. 禁止事項違反
- [Warning] 明示的な禁止事項違反は見当たりません。ただし `smoke 5 Run で diff 分布計測` を calibration 根拠に使い始めると、見た目の数値追いになりやすいです。  
  修正提案: `smoke 5` の用途を「クラッシュ確認・ログ生成確認」に限定し、calibration 判断には使わないと明記してください。
- [Suggestion] `LOG_ONLY` 維持と `live_criteria 非変更` を step 完了条件に含めてください。

3. 実現可能性
- [Warning] 配線自体は小さく、実装可能性は高いです。ただし `stage_b_window_months * 30` は threshold scaling の根拠として弱いです。18 か月の実バー期間・営業日数・セッション日数と乖離する可能性があります。  
  修正提案: `window_days` は設定月数の近似値ではなく、`bars` から導出した実観測窓に寄せてください。少なくとも「calendar day 基準なのか business day 基準なのか」を仕様で固定する必要があります。
- [Warning] FX の `business_day` と評価用 `session block` が同一とは限りません。60 日では露出しないずれが、18 か月では DST・週跨ぎで顕在化し得ます。  
  修正提案: adapter 凍結再利用の前提に、「UTC 日付」と「評価上の session 日」の関係を 1 つの表で追加してください。

4. 期待効果の妥当性
- [Critical] `smoke 5 Run` は C7 的に calibration 根拠として不十分です。n=5 は分布比較にも回帰主張にも使えません。  
  修正提案: `smoke 5` はあくまで健全性確認と位置付け、step 2 判定前に別途より大きいサンプルで diff 収集する計画を設計書に分離してください。
- [Warning] Stage B IS だけを見て canonical/legacy の差を論じると、Stage B pass/fail の実体である per-fold OOS と conditioning set がずれます。C3 collider bias の温床です。  
  修正提案: 解析計画に「B_IS diff は B_IS 専用。Stage B 合否や OOS 安定性の代理指標として解釈しない」と明記してください。
- [Suggestion] `B_IS`, `B_fold`, `C_base`, `C_cross_pair` を別系列として扱うログ命名規約を今の段階で決めておくと、後の誤読を減らせます。

5. リスク
- [Critical] メモリ制約 24GB / 6 workers 観点が甘いです。18 か月 minute bars に対して `equity_curve -> BarEquitySeries` と trade 変換を追加すると、1 worker 3GB 上限に近づく恐れがあります。設計は計算量しか述べておらず、peak RSS の見積りがありません。  
  修正提案: step 1.5 の受け入れ条件に「Stage B IS worst-case pair で peak RSS が worker 予算内」を追加してください。設計上は、`disabled` を逃げ道にするのではなく、既定モード・対象 stage・ログ粒度のどこで budget を守るかを先に決めるべきです。
- [Warning] `regression 0` は機能面では近いですが、運用面では未証明です。ログ serialization、例外時の warning 発火、sidecar 生成時の一時オブジェクト確保は既存経路に副作用を与え得ます。  
  修正提案: `regression 0` を「判定結果回帰 0」と「運用回帰 0」に分け、後者は別途検証対象に落としてください。
- [Warning] rename は小さい変更ですが、step 1.5 の本質ではありません。  
  修正提案: rename を同一 commit に入れるなら「pure refactor」と「behavioral wiring」をレビュー上分離してください。`1 step 1 commit` を守るなら commit を分ける方が明快です。

6. スコープの適切さ
- [Warning] 全体としては小さめですが、現状の説明だと「観測拡張」と「step 2 前提確立」を同時に背負いすぎています。  
  修正提案: 本 step の責務を「観測拡張」だけに限定し、step 2 前提の充足判定は別ノートに切り出してください。
- [Suggestion] `Stage B per-fold は scope 外` 自体は妥当です。ただし、その代わりに何が未解決として残るかを 1 行で明記した方がよいです。

7. メモリ制約
- [Critical] 24GB × 6 workers 制約に対し、設計は「計算量 ~2x」としか書いておらず、メモリの複製コストを評価していません。ここは要件違反リスクがあります。  
  修正提案: 設計書に少なくとも次を追加してください。`BarEquitySeries` の長さ、trade record 数、stage ごとの追加常駐オブジェクト、worst-case worker 同時実行時の概算。
- [Suggestion] Stage B だけ `log_only` を既定無効にする案はありますが、それは mission 整合より運用都合が勝つので、まず budget 実測前提の設計にした方がよいです。

8. 前提検証 (C4)
- [Warning] `adapter が Stage B/C でも問題なく動く` は、現時点では前提であって verified ではありません。  
  修正提案: 前提表を `Assumed / To Verify in step 1.5 / Out of scope` の3列に分けてください。今の書き方だと前提と結論が近すぎます。
- [Warning] `thresholds 構築可能` と `thresholds が妥当` は別です。前者だけ満たしても step 2 の calibration 価値は保証されません。  
  修正提案: 「構築成功」と「legacy との比較可能性」を別 acceptance criterion にしてください。

9. Design-first (C1)
- [Warning] 設計書内で `docs/devnotes/handoff/commit` は参照されていますが、レビュー材料として要点抜粋がありません。C1 を満たしたと主張するには弱いです。  
  修正提案: 本ノート末尾に、各参照元から 3-5 行の「この設計に効く事実」を引用ではなく要約で付けてください。特に `step 1 handoff` と `stage_gate 現行構造` の要約は必要です。

**反証結果まとめ (C9)**
- 反証 1: `B_IS + C_base で step 2 前提が満たせる` は現状では反証寄りです。判定実体の `B per-fold` と mission 必須の `C cross-pair` が抜けています。
- 反証 2: `adapter 凍結再利用がそのまま成立する` は未反証でも未確認です。特に `window_days=months*30` と `business_day/session` の整合が弱いです。
- 反証 3: `regression 0` は判定経路については概ね妥当ですが、運用回帰まで含めると未証明です。
- 反証 4: `最小限・段階的価値最大化` は大筋で守られています。ただし rename と前提確立の主張を同時に載せたことで、少し膨らんでいます。

**結論**
この設計は方向としては妥当ですが、現状のままでは「step 2 前提確立」と「regression 0」を言い切るには根拠が足りません。特に `B_IS だけで calibration を代表できるのか`、`18 か月窓の threshold scaling と memory budget が成立するのか`、`smoke 5 をどう位置付けるのか` の3点は修正が必要です。これらを設計文面で狭めれば、次ラウンドで `APPROVED` に近づきます。