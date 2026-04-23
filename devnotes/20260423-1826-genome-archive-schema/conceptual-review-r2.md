**Verdict**

`NEEDS_REVISION`

1. `fold_sign_ratio` の意味乖離がまだ残っています。概念設計は Stage B で `positive_fold_ratio` を `fold_sign_ratio` 列へ暫定保存する前提ですが、これは列名の意味と一致しません。[conceptual-design.md#L112](/Users/ishitoya/repository/zenigame-fx/devnotes/20260423-1826-genome-archive-schema/conceptual-design.md#L112) しかも Stage B payload には `oos_sharpes` が既にあり、既存の `fold_sign_ratio()` で実値を計算できます。[stage_gate.py#L457](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/stage_gate.py#L457) [statistics.py#L234](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/statistics.py#L234) この状態で詳細設計へ進むと、archive 利用側が列を誤読します。

2. 複合キー修正は主旨として入っていますが、4段伝搬契約に旧記述が残っています。Section D では `self._rows[(generation, individual_name)]` なのに、伝搬図はまだ `self._rows[individual_name]` です。[conceptual-design.md#L69](/Users/ishitoya/repository/zenigame-fx/devnotes/20260423-1826-genome-archive-schema/conceptual-design.md#L69) [conceptual-design.md#L144](/Users/ishitoya/repository/zenigame-fx/devnotes/20260423-1826-genome-archive-schema/conceptual-design.md#L144) 実装者にとっては十分に危険な不整合なので、ここは文面も完全一致させるべきです。

3. 公開 docs 側の schema 定義が Round 2 修正をまだ反映していません。`active_clause` は依然として「実際に発火した clause 数」とだけ書かれており placeholder 0 方針が見えず、`fold_sign_ratio` も説明なしです。[genome-archive-schema.md#L31](/Users/ishitoya/repository/zenigame-fx/docs/alpha_factory/concepts/genome-archive-schema.md#L31) [genome-archive-schema.md#L35](/Users/ishitoya/repository/zenigame-fx/docs/alpha_factory/concepts/genome-archive-schema.md#L35) 概念設計本文では意味乖離を認識しているので、参照 docs をこのまま放置すると SSOT が割れます。

**Open Questions**

- `fold_sign_ratio` は archive collector 側で `oos_sharpes` から計算する前提に寄せますか。それとも列名自体を `positive_fold_ratio` に改めますか。
- `docs/alpha_factory/concepts/genome-archive-schema.md` と `devnotes/.../conceptual-design.md` のどちらを列意味論の SSOT にするか、明示が必要です。

**Summary**

Round 1 で指摘した `ii_lite_pass` の SSOT 統一と monotonic enrich の方向性は解消できています。今回の残課題は「列意味論を本当に揃え切れたか」に集約されるので、上の 3 点を閉じれば `APPROVED` でよいです。