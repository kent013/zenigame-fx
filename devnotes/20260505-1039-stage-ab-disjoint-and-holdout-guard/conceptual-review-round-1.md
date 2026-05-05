- 本分析の前提
  - `docs/alpha_factory/`・`devnotes/`・`git log` の実ファイル確認は未実施です。理由は、今回の指示でコマンド実行を禁止されており、提示テキストのみを根拠にしているためです。
  - したがって C1 Design-first は「提示文中の引用内容を参照した」という限定付きであり、一次確認は **未検証** です。
  - `run_ga.py`・`stage_gate.py` の具体的実装詳細、`dataset.end` の厳密な意味、`wf_min_folds_required` の現行挙動は **未検証** です。
  - 以上を踏まえ、今回の判定は「概念設計レビュー」であり、コード監査の確定判定ではありません。

**全体判定: CHANGES_REQUESTED**

**Facts**
- 提示された設計は、`Stage A` が `Stage B` 末尾の部分集合であることを問題視し、`Stage B` から `Stage A` 期間を除外して時系列 disjoint にする案です。
- 提示文では、`Stage B` fold 評価は `test_bars` のみで再評価され、fold ごとの `train_bars` は未使用と主張されています。
- 提示文の数値では、6か月相当データで `Stage B` は 83 trading days になり、`train=60, embargo=1, test=10, step=10` だと effective fold は 2 です。
- 提示設計の holdout guard は、`bars_stage_a` / `bars_stage_b` の `bar_time < dataset.end` を起動時に fail-closed で検証する案です。

**Interpretations**
- `Stage A` と `Stage B` test 区間の重複が事実なら、「Stage B が独立 OOS になっていない」という問題提起自体は妥当です。
- ただし、そこから即「今回の 2 点修正だけで Stage B が十分に信頼できる評価になる」とまでは言えません。
- 最大の反証点は、`Stage B` が 2 fold に縮むと、`median_oos_sharpe` と `positive_fold_ratio` の統計的意味がかなり弱くなることです。ここを放置すると、汚染除去は正しい一方で、ゲートとしての判断力が落ちる可能性があります。

**1. 使命との整合性**
- [Warning] `Stage A/B disjoint 化` 自体は、live_criteria 達成の前提条件としては整合的です。独立 OOS でない Stage B を放置するより方向性は正しいです。
  - 修正提案: 「本変更の成功条件」を `Stage B の独立性回復` に限定し、「Stage B→C 通過率改善」は期待効果ではなく観測項目へ格下げしてください。現状の文章は、効果の主張が一段強すぎます。
- [Suggestion] 使命との接続をより明確にするなら、「live_criteria 達成に直接効く変更ではなく、偽陽性を減らして改善ループを正常化する変更」と明記した方がよいです。

**2. 禁止事項違反**
- [Suggestion] 明示的な禁止事項違反は見当たりません。
- [Warning] ただし「Stage B pass 個体数の急減を観測」は自然な結果であり得る一方、これをもって改善成功とみなすと「数値を良く/悪く見せる」議論に寄りやすいです。
  - 修正提案: 成功判定を「Stage B test と Stage A のバー重複が 0」「holdout 侵入時に fail-closed」など構造条件に置いてください。

**3. 実現可能性**
- [Warning] 実装スコープは小さく、24GB×6 ワーカー制約にも十分収まると考えられます。
  - 修正提案: ただし `LaneBarsBundle.bars_stage_b` の意味変更は波及範囲があるため、利用箇所一覧を概念設計に 1 行追加してください。少なくとも `summary`, `stage gate`, `report`, `logger` の4系統を対象に明記すべきです。
- [Critical] holdout guard の設計が弱いです。`max_bar_time < dataset.end` だけでは、今回の主問題である `Stage A` と `Stage B` の重複を検出できません。
  - 修正提案: guard は最低でも以下を別々に検証してください。
    - `max(stage_a.bar_time) < min(stage_holdout.bar_time)`
    - `max(stage_b.bar_time) < min(stage_holdout.bar_time)`
    - `set(stage_a.bar_time) ∩ set(stage_b_fold_test.bar_time) = ∅` または、それと等価な時系列境界条件
  - 修正提案: 参照実装に寄せるなら、「holdout 侵入検知」と「OOS/holdout を sampling pool から除外する保護」は別契約として分離してください。

**4. 期待効果の妥当性**
- [Critical] `9→2 fold への縮小は見せかけ機能の表面化に過ぎない` という主張は、提示文だけでは言い切れません。2 fold では `median` も `positive_fold_ratio` も安定した統計とは言い難いです。
  - 修正提案: 本設計に「Stage B の判定力低下を認める」一文を追加してください。具体的には「2 fold での median / positive_fold_ratio は探索上の暫定ゲートに留まり、強い統計的解釈はしない」と明記すべきです。
- [Warning] C7 の観点では、fold 数 2 は相関議論以前に、安定性評価としてかなり弱いです。
  - 修正提案: 本変更と同時に閾値変更は不要ですが、`n_fold_effective < 3` を検知したら report 上で `INCONCLUSIVE` 相当の明示を出す設計を追加候補にしてください。
- [Suggestion] López de Prado 参照は方向として妥当です。ただし本件は「purged CV の完全導入」ではなく、「最低限の disjoint 化」であると位置づけた方が過大主張を避けられます。

**5. リスク**
- [Critical] `Stage B` が 2 fold になると、ゲートが偽陽性を減らす代わりに、偽陰性や高分散判定を増やす可能性があります。改善ループ全体の学習速度低下が起こり得ます。
  - 修正提案: 本設計書に「受け入れる副作用」として、`Stage B verdict の分散増大` を明記してください。併せて、次段の別 TODO 候補を `dataset 延長 / Stage A 短縮 / gate再設計` の3択で整理するとよいです。
- [Warning] `bars_stage_b` の意味変更により、既存の運用者が `Stage B IS monitor` を従来と同じ意味で読む誤解が起こり得ます。
  - 修正提案: ログ名または summary key に「ex_stage_a」など意味を示す接尾辞を入れる案を検討してください。単なる値変更だけでは運用事故になります。

**6. スコープの適切さ**
- [Suggestion] スコープは概ね適切です。大規模変更に広げていない点はよいです。
- [Warning] ただし、提示文自身が「fold で `train_bars` を使わない問題」をスコープ外に置いています。もしこの観察が事実なら、`Stage B` を walk-forward と呼び続けること自体が誤解を生みます。
  - 修正提案: 今回のスコープ外でよいですが、設計本文に「現状の Stage B は strict な意味での walk-forward ではない可能性がある」と留保を書いてください。

**7. メモリ制約**
- [Suggestion] この変更でメモリ圧迫が悪化する要素は見当たりません。むしろ `bars_stage_b` 短縮で微減の方向です。

**8. 前提検証（C4）**
- [Critical] `dataset 6m では Stage A 73d + Stage B 83d が境界条件` という主張は、提示文内部でも「`stage_a_window_days` 60 が実 trading 73 日になる」前提に依存しています。この換算契約が未固定のまま境界条件として扱うのは危険です。
  - 修正提案: 前提を分離してください。
    - 前提A: `stage_a_window_days=60` が現実には約73 trading days相当になる
    - 前提B: `dataset 6m` が約156 trading days を提供する
    - 前提C: `make_wf_folds` の必要日数式が提示通りである
  - 修正提案: その上で「前提A-Cが成り立つなら境界条件」という条件付き表現に落としてください。
- [Warning] `calibrate-gate history` への影響は示されていますが、`stage_gate_version` を変えるべきかはこの変更単独では未確定です。
  - 修正提案: 「必要なら変更」ではなく、判定基準を設計に書いてください。例えば「Stage B 指標の意味が変わるため version bump を原則実施」など。

**9. Design-first（C1）**
- [Warning] 提示文は `zenigame` 参照実装と現行コードへの参照を含んでおり、設計意図としては C1 に沿っています。
  - 修正提案: ただし本レビュー時点では、こちらで docs/devnotes/git 履歴の一次確認ができていません。最終承認前に、少なくとも以下の確認を必須条件にしてください。
    - `docs/alpha_factory/` に Stage A/B/C 契約が明文化されているか
    - devnotes に `Stage B` の本来の意味が残っているか
    - `git log -S` 相当で `bars_stage_b` の歴史的意味変更がないか

**Round 1 反証結果**
- `Stage A IS と Stage B fold OOS の重複は構造的問題か`
  - Facts: 提示文の観察が正しければ、重複はあります。
  - Interpretation: その場合、独立 OOS という意味では構造的問題です。
  - 留保: ただし「fold ごとの `train_bars` 未使用」が未検証なので、`Stage B` の設計意図まで断定するには一次確認が必要です。
- `Stage B fold 数 9→2 は見せかけ機能の表面化に過ぎないか`
  - Facts: fold 数 2 だと評価母数はかなり乏しいです。
  - Interpretation: 「見せかけ機能の表面化」という説明は部分的には正しいですが、それだけでは足りません。判定力そのものも落ちます。ここは設計文が楽観的すぎます。
- `dataset 6m では Stage A 73d + Stage B 83d が境界条件という主張に矛盾はないか`
  - Facts: 提示された算術自体には大きな矛盾はありません。
  - Interpretation: ただし `60日設定が73 trading日になる契約` が曖昧なので、境界条件の主張は条件付きにすべきです。確定事実として書くのは早いです。

**結論**
この概念設計の核である「Stage A/B disjoint 化」は妥当です。ここは進める価値があります。  
ただし、`holdout guard` の検証条件が弱いこと、`Stage B 2 fold` の統計的弱さを設計が十分に認めていないこと、この2点は概念設計のまま通すには不足です。そこを補強すれば、再レビューで `APPROVED` に近づきます。