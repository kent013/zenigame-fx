**本分析の前提**
- [未検証] `docs/alpha_factory/`、`devnotes/`、`git log`、最新コードとの整合性。今回は提供テキストのみを対象にしており、C1/C4 の完全充足は確認できていません。
- [検証済み] レビュー対象 hypothesis は「per-bar snapshot cache + incremental margin により 70-80% 削減を達成しつつ、数値 bit-identical を保つ」です。
- [未検証] `MockBroker` 以外の `PaperBroker` / `LiveBroker` / live feed 系の snapshot 契約。
- [未検証] `Decimal` の演算順序変更が完全に無害であること。

**全体判定: CHANGES_REQUESTED**

**1. 使命との整合性**
**Facts**
- 本設計は live_criteria を直接改善せず、RUN 時間短縮による探索量増加を通じて間接的に寄与すると明記されています。
- Stage A/B/C 判定と `best_genome` 選択を不変に保つことを成功条件に含めています。

**Interpretations**
- 使命との方向性は整合しています。
- ただし、この種の最適化は「速くなる」より「選択結果が変わらない」の証明が優先です。ここが崩れると使命に逆行します。

- [Warning] 使命への寄与が間接であり、効果測定が「壁時計時間短縮」に偏っています。  
  修正提案: 成功基準の先頭を「同一 seed / 同一 config / 同一データで selection outcome が完全一致」に置き換え、その後に throughput 指標を置いてください。

**2. 禁止事項違反**
**Facts**
- 評価期間延長、閾値緩和、GA ハック、entry 抑制、オーバーナイト化は提案していません。
- スプレッド・スワップの挙動は変えない前提です。

**Interpretations**
- 明示的な禁止事項違反は見当たりません。
- ただし、bit-identical が崩れるなら実質的に fitness 歪曲と同義です。

- [Warning] `incremental margin` は一見安全ですが、数値同一性が未証明なまま入れると禁止事項 3 の迂回になり得ます。  
  修正提案: `margin_used` はまず「参照専用 shadow 値」として計測し、既存 `sum()` と全バー比較で一致が証明できた後に本番切替する二段階設計にしてください。

**3. 実現可能性**
**Facts**
- 変更対象は主に `MockBroker` に限定され、スコープは小さいです。
- invalidation トリガーとして、position 開閉、cash 変更、bar 進行が列挙されています。

**Interpretations**
- 実装自体は小規模で実現可能です。
- ただし、invalidating state の列挙が「十分条件」かは未証明です。

- [Critical] cache invalidation 契約が「position state 以外も含めて snapshot を変える全状態」を網羅しているとまだ言えません。  
  修正提案: `PortfolioSnapshot` の各フィールドごとに依存元を洗い出した依存マトリクスを先に作成してください。最低でも `cash`、`positions`、`entry_margin`、`bar prices`、`margin_level_pct`、強制ロスカット判定に使う派生値の全依存を表にする必要があります。
- [Critical] `force_close_if_margin_call(bar)` の内部で同一 bar 中に複数回 snapshot を参照・状態更新する場合、ループ途中で stale snapshot を再利用する反証が未潰しです。  
  修正提案: 「同一 bar 内で close が連鎖するケース」を専用テストに追加し、各 close 後に再計算されることを明示的に検証してください。
- [Warning] `PortfolioSnapshot` の `positions` が mutable 参照なら、cached snapshot 自体の観測結果が後から変わる可能性があります。  
  修正提案: cached object の不変条件を明文化し、必要なら positions を immutable view に固定してください。

**4. 期待効果の妥当性**
**Facts**
- 根拠プロファイルは `pop=8 gen=1 seed=42 14日 EUR_JPY` の単一計測です。
- 本番外挿は bar 数比例の線形換算です。

**Interpretations**
- 「その run では hotspot だった」は言えます。
- 「本番でも 70-80% 削減」はまだ observation ではなく仮説です。C7 的にも n=1 で一般化はできません。

- [Warning] 70-80% 削減は単一プロファイルからの外挿で、主張強度が高すぎます。  
  修正提案: 期待効果を「仮説レンジ」に格下げし、少なくとも複数 seed・複数 pair・複数 window で再計測する検証計画を成功基準に含めてください。
- [Suggestion] 効果指標を `_snapshot_at` の cumtime だけでなく、RUN 全体、1 bar あたり、1 genome あたりで分けてください。

**5. リスク**
**Facts**
- 本設計は `sum(entry_margin)` を incremental 更新に置き換えます。
- bit-identical を強く要求しています。
- `Decimal` 最適化案は本スコープ外です。

**Interpretations**
- 最も大きい反証点は performance ではなく数値同一性です。
- 特に「毎回再集計」と「ライフサイクル累積」は演算順序が異なります。

- [Critical] `Decimal` の演算順序変更により bit-identical が壊れる反証が未解消です。  
  修正提案: `incremental margin` を採用するなら、`Decimal context` と quantization 前提を固定し、既存 `sum()` 結果との全バー一致テストを入れてください。不一致が 1 件でも出るならこの案は却下し、cache のみに縮小すべきです。
- [Critical] partial close / position resize / 手数料相殺など、`entry_margin` の減算が単純な逆演算で済まない経路が存在すると累積値が壊れます。本文ではその不存在が証明されていません。  
  修正提案: 「position lifecycle 上、`entry_margin` は open 時確定・close 時全額解放のみ」という不変条件を先に設計文書へ明記し、未保証なら incremental margin をスコープ外へ戻してください。
- [Warning] live feed / paper trading / `LiveBroker` への影響調査が未実施です。  
  修正提案: 少なくとも「共通 broker interface 上の snapshot 契約は不変」「今回の変更は `MockBroker` 実装詳細に閉じる」を文書化してください。

**6. スコープの適切さ**
**Facts**
- `MockBroker` 限定で、engine loop や dataclass 変更はスコープ外です。

**Interpretations**
- スコープは概ね適切です。
- ただし、`cache + incremental margin` を一度に入れると原因分離が難しくなります。

- [Warning] 2 つの最適化を同時投入すると、差分検証で失敗時の切り分けができません。  
  修正提案: Phase 1 を per-bar cache のみ、Phase 2 を incremental margin に分けて、各段階で bit-identical を確認してください。
- [Suggestion] stretch の `_unrealized_pnl` 最適化は現時点で切り離した判断が妥当です。

**7. メモリ制約**
**Facts**
- cache 追加は broker ごとに snapshot 1 個相当で、設計上は軽量です。

**Interpretations**
- メモリ面の懸念は小さいです。

- [Suggestion] 実装後に broker インスタンス数 × cache サイズの概算だけは残してください。24GB 制約下では「小さいはず」の明文化が有効です。

**8. 前提検証（C4）**
**Facts**
- 本文の前提検証には「HEAD 時点コードを基準」「`PortfolioSnapshot` frozen」「既存 broker tests が structured」などが書かれています。
- それらは本文中で verify されていません。

**Interpretations**
- 前提は列挙されていますが、検証済み前提にはなっていません。
- C4 は未充足です。

- [Critical] 前提が「列挙」止まりで、「verified」になっていません。  
  修正提案: 概念設計の冒頭に前提表を追加し、各項目に `Verified / Unverified / To verify in detailed design` を付けてください。未検証前提に依存する主張は弱める必要があります。

**9. Design-first（C1）**
**Facts**
- 本文には profile とコード位置の記述はありますが、`docs/alpha_factory/`、`devnotes/`、`git log` の参照結果が載っていません。

**Interpretations**
- C1 の要求に対する証跡が不足しています。
- この状態では「既存設計との非整合がない」とは言えません。

- [Critical] Design-first の証跡が欠落しています。  
  修正提案: 少なくとも次を概念設計に追記してください。`docs/alpha_factory` の参照箇所、関連 devnote/T-number、該当識別子の変更履歴要約、別経路探索の結果。
- [Warning] `MockBroker` 以外の broker 実装との差分整理がないため、「共通仕様に対する逸脱」が判定できません。  
  修正提案: broker interface 契約と `MockBroker` のローカル最適化境界を 5 行程度で明文化してください。

**結論**
主な問題は 3 点です。  
1. stale cache を防ぐ invalidation 契約がまだ弱い。  
2. `incremental margin` が bit-identical を壊さない証明がない。  
3. C1/C4 の証跡が不足している。  

したがって現時点では `APPROVED` ではなく `CHANGES_REQUESTED` です。最小修正方針としては、まず `per-bar cache のみ` を独立案として再定義し、`incremental margin` は shadow 検証付きの別段階へ分離するのが妥当です。