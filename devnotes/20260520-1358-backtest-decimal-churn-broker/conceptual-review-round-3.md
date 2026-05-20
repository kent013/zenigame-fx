**全体判定: APPROVED（軽微な Warning あり）**

Round 2 の [Critical] は解消しています。`primary metric = peak_total_rss_mb ≤ 20GB` にしたことで、`before_ga_loop=2.3GB` を運用予算の主基準にしてしまう問題は切れています。B-1 で同一 run の `peak_main / peak_worker / peak_total` を取り直して worker 目標を確定する方針も妥当です。

**Fact**
- [conceptual-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260520-1358-backtest-decimal-churn-broker/conceptual-design.md:27) で `peak_total_rss_mb ≤ 20GB` が primary metric になっています。
- [conceptual-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260520-1358-backtest-decimal-churn-broker/conceptual-design.md:32) で Run 82 の `peak_main=6468MB / peak_worker=9502MB / peak_total=23657MB` と、T106/T107 後の GA loop 中 peak main が未測定であることが明記されています。
- [conceptual-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260520-1358-backtest-decimal-churn-broker/conceptual-design.md:110) の Step B 合格条件も `median peak_total_rss_mb ≤ 20GB (n≥3)` に変更されています。

**Interpretation**
- 成功基準を同時稼働 peak total に寄せたため、運用可能性の判定はかなり堅くなりました。
- `worker ≤8.5GB / ≤6.7GB` は補助的な内訳目安としてなら適切です。最終ゲートを `peak_total` にしたので、main と worker の寄与を誤って足し合わせるリスクは下がっています。
- `B-1 → B0.5 → B0 → B1` の順序も妥当です。特に、B-1 で retained 支配なら scaled-int に進まない判断が入っている点は重要です。

**残存 Warning**
- [Warning] 前提表に古い表現が残っています。[conceptual-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260520-1358-backtest-decimal-churn-broker/conceptual-design.md:10) の `現状ピーク = main 2.3GB + worker 9.5GB×2 = ~21.3GB` は、Round 3 の方針と矛盾します。修正案: `T106/T107 後の before_ga_loop 下限参考値。GA loop 中 peak_total は B-1 で再測定` に置き換える。
- [Warning] H2 がまだ `worker per-worker RSS ≤8.8GB / ≤7GB` 中心の表現です。[conceptual-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260520-1358-backtest-decimal-churn-broker/conceptual-design.md:99) は `median peak_total_rss_mb ≤20GB` を主語にし、worker 目標は B-1 後に確定する補助指標として書く方が一貫します。
- [Suggestion] 検証計画の `B0.5: 3-arm` は、本文の `B0.5=2-arm / B0=scaled-int 追加` と少しズレています。[conceptual-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260520-1358-backtest-decimal-churn-broker/conceptual-design.md:145) を `B0.5: baseline/recycle短縮の2-arm、B0: scaled-int proto を加えた3-arm` に直すと読み手が迷いません。

結論として、設計判断は `APPROVED` です。残りは概念の否認理由ではなく、後続実装者が古い `2.3GB` 前提を誤用しないための文面整合修正です。