**前提**
- `C1 Design-first` に従い、レビュー対象は設計本文 [conceptual-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260423-1423-primitives-pair-specific/conceptual-design.md) のみです。実コード・テスト実装・validator 実装は未確認なので、そこに依存する点は `INCONCLUSIVE` と明記します。
- 反証優先 (`C9`) で見ています。つまり「この設計が使命に届かない/誤作動しうる箇所」を先に挙げます。
- 効果検証の実測データはまだ無いため、「12 primitive が GA 改善に効く」は現時点では仮説であり、`INCONCLUSIVE` です。

**主要 Findings**
1. **P10 は現仕様だと “Surprise” ではなく、M4 の局所版に見えます。**
   - Fact: 本文では P10 は `event_snapshot` を使い、「`event.event_time` のみ参照、actual 不参照」と明記されています。
   - Interpretation: それは surprise ではなく proximity/time-window gate です。名前が役割を表していませんし、`M4 とほぼ同形` という懸念は妥当です。`機能の名前に立ち返れ` の原則にも反します。
   - Impact: 冗長 primitive を 1 本増やすだけになり、GA 探索空間だけ増えて改善仮説に寄与しない可能性があります。

2. **P5 の符号規約が “MEAN_REVERT” と整合していません。**
   - Fact: L2 では「乖離の符号反転を狙う」と書かれていますが、L4 では `residual = mid_EURJPY - mid_EURUSD * mid_USDJPY をそのまま返す` とあります。
   - Interpretation: そのまま返すなら、自然符号は divergence の方向です。mean reversion を primitive 名・category に持つなら、自然符号は `-normalized_residual` 側であるべきです。ここを `weight 符号で吸収` に寄せると、primitive 名と役割の対応が崩れます。
   - Impact: GA が負 weight を学習すれば動く、という逃がし方はできますが、pair-specific edge を「直接表現する」という目的から一段後退します。

3. **P5 の時刻整合 contract は自己矛盾しています。**
   - Fact: 本文は「loader 側で前方 forward-fill する場合もある」と書く一方で、primitive 側では `aux_pair_bars[k][i].bar_time == bars[i].bar_time` を bar ごとに assert するとしています。
   - Interpretation: forward-fill された“元バー”をそのまま保持するなら、通常は `bar_time` は一致しません。両立させるには「aligned synthetic bar を作る」か、「source_ts と effective_ts を分離する」か、「`<= current bar_time` + staleness cap` を許容する」かのどれかが必要です。
   - Impact: 現状のままでは、P5 は強すぎる assert で実運用データを弾くか、逆に loader が時刻を書き換えて provenance を失うかの二択になります。

4. **safe default が “伝搬漏れの隠蔽” になりうる点に、設計上の歯止めがまだ足りません。**
   - Fact: directional は欠損時 `warning + 0.0`、P10 は `1.0`、P6/P11 は `0.5`。起動時 verify は「別 TODO の helper」に委ねています。
   - Interpretation: これはテストや他ペア graceful degrade には有効ですが、選択された primitive の required data が本番 backtest で未注入でも、静かに性能劣化したまま走れる設計です。特に P5/P7-P12 は aux 依存が本質なので、ここが死ぬと「実装したが効いていない」を見逃します。
   - Impact: 使命である `live_criteria` 到達に対し、非機能状態を warning だけで流すのは危険です。

5. **MVP 範囲は過大です。**
   - Fact: 12 本のうち、価格だけで閉じるのは P1/P2/P3/P4/P6 程度で、P5/P7/P8/P9/P10/P11/P12 は新しい aux 契約または snapshot 契約に依存します。しかも ingest / loader / preflight verify は別 TODO です。
   - Interpretation: “primitive ロジックだけ先に実装” はユニットテストには乗りますが、Alpha Factory 全体の改善仮説検証にはまだつながりません。今回の TODO が大きすぎて、成功判定 1-4 も「登録された」「API が通る」に寄りすぎています。
   - Impact: 実装量の割に、使命への前進が不確実です。禁止事項 5 の「やたらに複雑な案」に近づきます。

6. **P7/P11 の二経路設計は、consumer 視点ではまだ十分に robust ではありません。**
   - Fact: P7 は `vix_snapshot + aux_series["macro.spx500"]`、P11 は `vix_snapshot + aux_series["macro.dxy"]` を組み合わせます。VIX は publication-based、SPX/DXY は bar-aligned forward-fill 想定です。
   - Interpretation: タイミングモデルが異なる 2 系統を 1 primitive 内で混ぜるなら、少なくとも freshness/staleness 上限が必要です。特に FX intraday では、US 指数・商品が休場/時間外の間に stale 値を長く抱えます。本文でも stale 上限は `Should-consider` に留まっていますが、P7/P11 の実用性には本質です。
   - Impact: “robust” というより、“欠損しなければ動く” に留まっています。

**Must-fix**
- P10 を **rename するか、真に surprise を扱う仕様へ修正**してください。現仕様のままなら `NADataProximityGate` 等が自然です。加えて、M4 との差分を「対象通貨フィルタ」「時間窓」「抑制/加速の意味」のどこに置くかを明文化すべきです。
- P5 は **mean-revert として自然符号を返す**仕様に直してください。`residual` そのままではなく、少なくとも設計上は `-normalized_residual` を基準に置くべきです。
- P5 の alignment contract を **1 つに決めてください**。`完全同時刻一致` を要求するなら forward-fill 方針は外すべきです。forward-fill を許すなら `effective bar_time` と `source timestamp` の扱い、または staleness cap を設計に入れてください。
- aux 欠損の safe default を採るなら、**selected primitive の required_data 未充足は evaluator/run 起動時に fail-fast** と明記してください。別 TODO に逃がすのではなく、この設計の不変条件に入れるべきです。
- MVP は **段階分割**した方がよいです。少なくとも Phase 1 を `P1/P2/P3/P4/P6`、Phase 2 を `P5/P7-P12 + aux loader/preflight` に分けないと、今回 merge の成功が使命への前進を意味しません。
- P7/P11 には **freshness/staleness の上限**を必須条件として入れてください。`Should-consider` では弱いです。

**Should-consider**
- `RequiredDataKey Literal` の拡張は `_base.py` だけでは完結しない可能性があります。existing validate ロジック、registry bootstrap、docs 生成、runner の事前検証が列挙型を前提にしていないかは `INCONCLUSIVE` なので、設計に「監査対象一覧」を明記した方がよいです。
- `pair_specific が他ペアで crash しない` は妥当ですが、探索空間を無意味に広げる副作用があります。`preferred_pairs` や `pair_affinity` のような弱いメタデータを後続 TODO で持たせると、GA の探索効率が上がります。
- 成功判定に「登録数」「API」「後方互換」だけでなく、**改善仮説の falsification 条件**を 1 つ入れた方がよいです。例としては「固定 seed・同一 budget で pair-specific 有無を比較し、Stage A 通過率か純利益分布に差が無ければ仮説 reject 候補」といった形です。
- `使命との整合` では、P6/P10/P11 が単に取引回数を減らして見かけ成績を上げる方向に流れない監視が必要です。trade count / holding time / overnight exposure を acceptance に追加するとよいです。

**総評**
設計の良い点は明確です。仮説は書けており、`aux_pair_bars` と `aux_series` の用途分離も方向としては正しいですし、look-ahead を明示的に論点化している点も良いです。

ただし、現時点では `P10 の役割不一致`、`P5 の符号と alignment の矛盾`、`safe default に対する fail-fast 設計不足`、`12 本一括の過大スコープ` が強く、概念設計としてまだ閉じていません。

**Verdict: NEEDS_REVISION**