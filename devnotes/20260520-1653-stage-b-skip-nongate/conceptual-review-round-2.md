**全体判定: CHANGES_REQUESTED**

**Fact**

- `Stage C` は Stage B pass 個体のみ実行されます。この点は設計書の主張どおりです。[swim_lane.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/swim_lane.py:665)
- ただし `is_full_trade_count` は archive で `trade_count_stage_b` と `trade_count_full_dataset` に転記されます。[archive.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/archive.py:702)
- `trade_count_full_dataset` は `_update_cache` で selection feasibility に使われます。[run_ga.py](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py:935)
- `selection_score` は `feasible` / `violation_magnitude` を最上位に持つため、Stage B 失敗個体でも feasibility が変われば selection ranking が変わりえます。[run_ga.py](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py:194)

**Interpretation**

[Critical] Q1 の「GA 結果不変」証明はまだ不十分です。consumer inventory が `is_full_* -> archive shadow/offline only` で止まっていますが、実際には `is_full_trade_count -> trade_count_full_dataset -> _update_cache -> selection_score` という GA 決定経路があります。これは `Stage C 候補にならないから安全` では切れません。Stage B fail 個体も親選抜・best fallback の候補であり、特に pass 個体が infeasible の場合や世代全体の feasibility 分布次第で順位が変わります。

[Critical] 修正案は、少なくとも `trade_count_full_dataset` を baseline と完全一致させることです。現設計のまま IS monitor 全体をスキップするのは不可です。安全側に寄せるなら、B fail 個体でも full IS backtest は実行して `is_full_trade_count` だけは従来どおり確定し、`canonical_shadow_b_is` だけをスキップする設計に落とすべきです。これだと削減幅は下がりますが、GA 不変性の主張はかなり強くなります。

[Warning] `b_is_shadow_status` の 3 値設計自体は妥当です。ただし設計書内で `b_is_shadow_status` を新設すると書いた後に、「既存 except sentinel と同じ sentinel 値を流用」「新規 sentinel 不要」と残っています。[conceptual-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260520-1653-stage-b-skip-nongate/conceptual-design.md:66) [conceptual-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260520-1653-stage-b-skip-nongate/conceptual-design.md:130) ここは設計上の矛盾なので、`computed / skipped_fold_gate_fail / error` を SSOT にしてください。

[Warning] consumer inventory の「offline 監査のみ」は `trade_count_full_dataset` の派生 consumer を漏らしています。[conceptual-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260520-1653-stage-b-skip-nongate/conceptual-design.md:19) 直接 grep だけでなく、`archive derived column` まで inventory 対象に含める必要があります。

[Suggestion] `b_is_shadow_status` という名前は canonical shadow だけに見えます。`b_is_monitor_status` または `stage_b_is_monitor_status` の方が、`is_full_*` と canonical の両方を覆う名前として明確です。

**質問への回答**

1. 十分ではありません。`is_full_trade_count -> trade_count_full_dataset -> selection feasibility -> selection_score` が見落とし経路です。これは GA 結果に逆流します。
2. 3 値設計は妥当です。ただし `skip` と `error` を sentinel 値だけで表現せず、明示 status 列として持つ方針に統一してください。
3. 残存 Critical ありです。現設計は `GA 結果不変` を満たせない可能性があるため、まだ `APPROVED` にはできません。

検証は読み取りのみで実施し、ファイル変更・テスト実行はしていません。