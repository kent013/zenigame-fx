[VERDICT] CHANGES_REQUESTED

[Critical] (修正必須)
- [conceptual-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-2300-todo-T061-canonical-five-engine/conceptual-design.md) の `signed slack` 定義が [synthesis.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260428-2300-cascade-port-debate/synthesis.md) §6.1 と厳密一致していません。`slack_sharpe/pnl/dd/wr` の分母 floor を `1e-6` 系から独自値 (`1.0/0.05/0.10`) に変更し、`slack_tc` も式形が変わっています。これは「§6厳密準拠」に反します。
- 同ファイル内で「SR annual 換算は呼出側」と「T061内 const 756 で換算」の記述が併存しており、責務が矛盾しています。`gate_worst_gap` を T061 で返す以上、換算責務は単一化が必須です。
- `C7` で「Newey-West 1987 により block>=30 必須」と断定していますが、これは根拠として不正確です。さらに `n<30 => SR=-inf` は synthesis §6 の仕様追加で、ゲート挙動を実質変更します。仕様合意なしに hard fail を入れるべきではありません。
- 学術引用で「DSR が HAC補正後 SR を入力に取る」と読める記述は根拠が弱いです。Bailey & López de Prado (2014) はその形を明示要件としていないため、「要確認」明記か記述削除が必要です。

[Warning] (修正推奨)
- 入力契約で `exit_time_utc` と `session_bucket/business_day_index` を同時受領するのに、一致性 invariant が未定義です。T070 側の転記漏れ時に静かに誤集計するリスクがあります。
- `BarEquityPoint` は `timestamp_utc` 単調増加が前提と書きつつ、fail-fast 条件に含めていません。`sort済み/重複なし/tz-aware` を invariant 化しないと `max_dd` が不定になります。
- Phase 1 の C2 チェックが `grep import` だけだと不十分です。再エクスポート、別名 import、呼出側ラッパ経由の runtime 配線漏れ検出ができません。
- Phase 1/2 分離方針は妥当ですが、T060で起きた「周辺 consumer 漏れ」と同型リスク（config→GaConfig→meta→consumer）に対するチェックリストが T061案に不足しています。

[Suggestion] (任意改善)
- §6.1〜§6.4 について「synthesis式」「T061実装式」「差分理由」の3列表を追加し、差分ゼロを機械的に確認できる形にしてください。
- `evaluate_canonical_five` の戻り値に `infeasible_reason_codes`（`session_close_drop`, `negative_equity_drop_open`, `invalid_bar_series` など）を入れると、T063/T064 統合時の診断が安定します。
- 学術引用は次の粒度で明記すると監査しやすいです。Lo (2002)=serial correlation 問題提起、Newey-West (1987)=Bartlett HAC 推定量、DSR (2014)=別目的（選択バイアス/過剰最適化補正）で「HAC必須」とは書かない。