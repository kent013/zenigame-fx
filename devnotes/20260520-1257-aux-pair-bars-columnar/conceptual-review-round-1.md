**全体判定: CHANGES_REQUESTED**

**Fact**
- 設計本文の前提整理では、`after_aux_bundle_built` で main RSS が `+2.6GB` 増えており、増分の主要因として `aux_pair_bars_index = dict[str, dict[datetime, PriceBar]]` が特定されています。
- 本文上、`aux_pair_bars` の実消費者は現状 `P5 CrossPairTriangulation` のみで、P5 は `bar_time` と `bid.close/ask.close` から計算する `mid close` しか使っていません。
- 改善案は、raw 保持を columnar 化し、さらに align 後も `aux_pair_mid: dict[str, np.ndarray]` に寄せる A1 と、値だけ軽量化する A2 を比較対象にしています。
- 禁止事項にある評価期間延長、live_criteria 緩和、GA ハック、取引回数削減、オーバーナイト導入は、本文上は行っていません。

**Interpretation**
- この施策は mission 直結の打ち手ではなく、OOM 回避の前提整備として筋が通っています。
- ただし、設計の成否は「どれだけメモリを削れるか」より先に、「primitive 契約変更で決定論・strict exact-match・look-ahead 非導入を壊さないか」で決まります。
- したがって、A1 自体は妥当ですが、契約境界と strict alignment 保全を詳細化しないまま実装に進むのは危険です。

1. 使命との整合性
- [Suggestion] 整合しています。live_criteria 直接寄与ではなく、`run 完走可能性の改善` に限定している点は適切です。
- [Suggestion] 設計書に「本施策単体では strategy quality は改善しない。改善するのは探索を最後まで回せる確率だけ」と一文を固定で入れると、後続の評価誤読を防げます。

2. 禁止事項違反
- [Suggestion] 本文上の違反は見当たりません。
- [Warning] `worker RSS 副次改善` を成果として強く語ると、mission 寄与を過大解釈しやすいです。
修正提案: worker RSS は「副次仮説」に格下げし、主 KPI は `after_aux_bundle_built` と `before_ga_loop` の RSS 差分に限定してください。

3. 実現可能性
- [Critical] A1/A2 を未確定のままにしている点が最大の不足です。この施策の目的が main/worker 両方の重いオブジェクトグラフ削減なら、A2 は弱すぎます。
修正提案: **Q1 は A1 を採用**してください。ただし `aux_pair_bars` の意味を変えて上書きするのではなく、**新契約 `aux_pair_mid` を追加し、P5 のみ移行、旧 `aux_pair_bars` は段階的に撤去**が安全です。
- [Warning] raw と align の両方を同時に変えるため、原因切り分けが甘くなる懸念はあります。
修正提案: phase marker を `after_raw_aux_index_built` と `after_aux_aligned_built` に分け、raw 側と align 側の効果を別々に観測してください。

4. 期待効果の妥当性
- [Suggestion] `after_aux_bundle_built` の 1GB 以上削減仮説は妥当です。ここは collider bias の懸念は薄く、直接計測で反証できます。
- [Warning] `worker RSS 副次改善` は本文の根拠だけでは強く言えません。pickle 縮小と RSS 縮小は一致しない可能性があります。
修正提案: worker 側は `n>=3` で別 KPI 化し、main RSS と切り分けて評価してください。
- [Warning] `bit-identical` は設計上の期待としては良いですが、まだ事実ではありません。
修正提案: H3 は「仮説」のまま維持し、`P5 出力配列の golden 比較` を一次判定、`GA best 一致` を二次判定にしてください。

5. リスク
- [Critical] `bar_time strict 一致` の fail-fast が曖昧なままです。ここを曖昧にすると silent NaN 化や将来の look-ahead 混入の温床になります。
修正提案: **Q3 は align 側 SSOT で保全**です。具体的には `raw epoch int64` に対し `searchsorted` で候補位置を出し、`raw_ts[pos] == target_ts` の exact-match 行だけ値を書き、不一致は NaN。さらに raw 構築時に `UTC / strict monotonic / unique` を fail-fast 検証してください。
- [Warning] primitive 契約変更は局所でも、将来の cross-pair primitive 追加時に再び崩れやすいです。
修正提案: フィールド名は用途依存の `aux_pair_mid` か `aux_pair_mid_close` にし、`bars` の名を流用しないでください。

6. スコープの適切さ
- [Critical] **A2 はこの施策の主目的に対してスコープ不足**です。datetime dict と align 後 list を残すなら、重いオブジェクトグラフのかなりの部分が残ります。
修正提案: スコープは **A1 に限定して採用**し、変更範囲も `aux loader / AuxBundle.align_to / P5 / 対応テスト` に閉じてください。lane や他 primitive へ拡張しないのが適切です。

7. メモリ制約
- [Suggestion] `24GB × 6 worker / 1 worker 3GB` 制約を考えると、A1 の方が整合的です。A2 は main RSS だけ少し改善しても、worker 側の object graph を十分には縮めない可能性が高いです。
- [Warning] 本文の acceptance table は main RSS には使えますが、worker 安全性の判定基準が未定義です。
修正提案: `worker init 後 RSS peak` を別 KPI として追加してください。

8. 前提検証 (C4)
- [Suggestion] 本文の verified/unverified 切り分けは良いです。
- [Warning] `唯一の消費者は P5` は現時点の fact ですが、将来拡張で破れやすい前提です。
修正提案: 詳細設計では「現時点では P5 only。新規 consumer 追加時は `aux_pair_mid` 契約を参照する」と明記してください。

9. Design-first (C1)
- [Suggestion] phase marker と consumer 特定から設計に入っているので方向は良いです。
- [Warning] 実装前に必要なのは「どこを SSOT にするか」の文章化です。現状は `strict 一致を align_to 側へ移す` までで、契約文がまだ弱いです。
修正提案: `align_to is the sole authority for exact timestamp matching` を明文化してください。

10. Falsification (C9)
- [Suggestion] `alignment +3.3GB が別要因なら本施策は限定効果` と明示しているのは良いです。
- [Warning] 反証条件に「メモリは減ったが P5 結果が一致しない」をもっと強く置くべきです。
修正提案: reject 条件の先頭を `P5 配列不一致 or strict-match 契約逸脱` に上げてください。

**Q1**
- **A1 を採用**が妥当です。
- 条件は、`aux_pair_bars` の意味を変えて残さないこと、`aux_pair_mid` を明示契約として導入すること、影響範囲を P5 周辺に閉じることです。
- A2 は非侵襲ですが、今回の目的に対しては削減効果が足りない可能性が高く、判断として弱いです。

**Q2**
- **`sorted int64 + searchsorted` を推奨**します。
- 理由は、memory goal と exact-match 契約の両立です。`dict[datetime, float]` は datetime object のオーバーヘッドを残し、今回の主戦場と噛み合いません。

**Q3**
- **strict 一致は `align_to` 側で保全**してください。
- raw 構築時に `UTC / monotonic / unique` を fail-fast。
- align 時は `searchsorted` の結果に対して `raw_ts[pos] == target_ts` の exact-match だけ採用。
- miss は NaN、内部不変条件違反は fail-fast。consumer 側では再計算しない、これが SSOT です。

設計の芯は良いですが、A1 採用の明確化と strict exact-match 契約の文章化がないと、OOM 改善と引き換えに決定論を壊すリスクが残ります。そこを詰めれば、概念設計としては前に進めます。