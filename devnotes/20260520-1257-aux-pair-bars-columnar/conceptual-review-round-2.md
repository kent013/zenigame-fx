**全体判定: APPROVED**

提示された改訂内容ベースでは、Round 1 の Critical 3 件は解消されています。A1 採用、`aux_pair_mid_close` 新契約、`align_to` を exact timestamp matching の SSOT にする方針は、OOM 回避インフラ改善として妥当です。

**Fact**
- A1 に確定し、`aux_pair_bars` の意味を流用せず `aux_pair_mid_close` を新設している。
- raw は `sorted int64 + float64`、align は `searchsorted + raw_ts[pos] == target_ts` の exact-match のみ採用、miss は NaN と定義している。
- 主 KPI を main RSS に限定し、worker RSS は副次 KPI に下げている。
- 成果判定に P5 golden 一致を入れ、GA best 一致は二次判定に下げている。

**Interpretation**
- `aux_pair_bars` の重量級オブジェクトを削る目的と A1 は整合しています。
- `align_to` SSOT 化により、P5 側で bar_time を再検証しない設計でも、責務境界は明確です。
- live_criteria 直接改善ではなく、探索を完走させるための前提整備としてスコープが閉じています。

**残存指摘**
- [Warning] `ts_epoch: int64` の単位を明文化してください。`epoch_ns` / `epoch_us` / `epoch_ms` の揺れは false miss や golden 不一致の原因になります。修正提案: フィールド名を `ts_epoch_ns` のように単位込みにし、target 側も同じ変換関数だけを使う契約にしてください。
- [Warning] `aux_pair_mid_close` の ndarray は read-only にする方が安全です。修正提案: align 後に `setflags(write=False)` を適用し、primitive が入力配列を破壊できないようにしてください。
- [Suggestion] strict-match 契約のテストは、正常一致だけでなく `duplicate raw ts`、`non-monotonic raw ts`、`timezone naive`、`target miss -> NaN` を最低限入れるとよいです。

**確認点への回答**
1. **A1 + `aux_pair_mid_close` + 旧経路撤去で Critical は解消**しています。P5 only 前提が verified なら本 PR で撤去してよいです。
2. **align_to SSOT の strict 一致保全は十分**です。ただし epoch 単位の固定と read-only 配列化は入れてください。
3. 残存 Critical はありません。上記 Warning 2 件は詳細設計・実装時に反映すればよく、概念設計としては **APPROVED** です。