**全体判定: CHANGES_REQUESTED**

Round 1 の主要指摘はほぼ反映されています。`B-1 attribution` 先行、`scaled-int` の格下げ、`recycle` 比較、`fixed-point` 契約の枠組みは概念設計として妥当です。残る問題は **運用 RSS 予算の前提値** です。

**Fact**
- [devnotes/20260520-1358-backtest-decimal-churn-broker/conceptual-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260520-1358-backtest-decimal-churn-broker/conceptual-design.md:1) は `max_workers=2` を前提に再設計されています。
- [config/alpha_factory/default.yaml](/Users/ishitoya/repository/zenigame-fx/config/alpha_factory/default.yaml:68) でも `max_workers: 2` は確認できました。
- Run 82 summary では `peak_rss_mb_per_worker=9501.84375` と同時に、同世代の `peak_main_rss_mb=6468.1875`, `peak_total_rss_mb=23657.359375` が記録されています。
- 設計本文は運用予算を `main=2.3GB + worker×2 ≤ 20GB` として、`worker ≤8.8GB` を最低ラインにしています。

**Interpretation**
- 設計の方向性は承認可能に近いです。ただし `main=2.3GB` が `before_ga_loop` marker 由来なら、worker と同時稼働する GA loop 中の peak main RSS 予算としては弱いです。
- Run 82 の同時観測に近い値を使うなら、20GB 予算では `6.5GB + worker×2 ≤20GB` となり、worker 上限は約 `6.7GB` です。つまり現行の `≤8.8GB` 成功条件は、実際の peak main RSS が 6GB 台に戻るなら運用可能域ではありません。

**観点別**
- [Critical] 運用予算の算出に使う `main RSS` を再定義してください。`before_ga_loop=2.3GB` ではなく、`GA loop 中に worker と同時存在する peak main RSS` を基準にする必要があります。修正案: `main_budget_source` を明記し、同一 smoke/run の `peak_main_rss_mb`, `peak_rss_mb_per_worker`, `peak_total_rss_mb` で成功条件を判定する。
- [Warning] `worker ≤8.8GB` は「T107 後も GA 中 main が 2.3GB 近辺に留まる」ことが verified の場合だけ成立します。未確認なら最低ラインは `≤6.7GB` 近辺、望ましいラインは `≤6GB` 程度に寄せるべきです。
- [Suggestion] `B0.5: 3-arm` は概念として妥当ですが、手順名は少し混線しています。`B0.5` は baseline/recycle の低リスク比較、`B0` で scaled-int proto を加えた比較、と分けると実行順が明確です。

**質問への回答**
1. `B-1 → B0.5 → B0 → B1` は妥当です。特に retained 支配なら scaled-int に進まない判定は正しいです。
2. `max_workers=2` は妥当です。ただし `worker ≤8.8GB` は保留です。GA 中 peak main RSS を再測定してから再算出してください。
3. scaled-int 厳密性契約の枠は概念段階として十分です。詳細設計で scale、丸め、overflow、境界変換、golden case を確定すればよいです。

この 1 点、RSS 予算の基準を同時稼働 peak に修正すれば、概念設計は `APPROVED` にできます。