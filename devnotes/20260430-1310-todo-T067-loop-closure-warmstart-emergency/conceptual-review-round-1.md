[VERDICT] CHANGES_REQUESTED

[Critical]
1. `§5.5 / §6 / §11.2` の emergency 設計が、「1 run のみ動作」という採用方針を表現できていません。事実として、`compute_warmstart_share_and_ratio(..., is_emergency=True)` は `mode=="emergency"` の間ずっと `25% + 1:1` を返し、`update_emergency_state` に「boost を 1 回だけ消費した」状態がありません。解釈として、このまま詳細化すると採用案 1 ではなく「解除まで毎 Run emergency 配分」が実装されます。`mode` と `boost_consumed_for_run` を分離しない限り、§8.5 厳密準拠にはなりません。

2. `§5.1 / §7 / §11.2 / §13 R4` の `WarmstartState` では `rolling=10 Run` を実装できません。事実として、保持しているのは `reuse_count` と `last_used_run_index` だけで、過去 10 Run 内で何回使ったかを再構成できません。`test_update_warmstart_state_rolling_window_drops_old_records` も現行 dataclass では定義不能です。解釈として、`max_reuse=3` が lifetime 制約に化けるので、synthesis §8.4 の rolling 契約から外れます。

3. `§9.1 / §9.2 / §17` で、emergency 判定に使う指標の SSOT が崩れています。事実として、本文は `best_margin_inf = max(mission_signed_margin)` と書く一方、`ArchiveCandidate.margin_inf=mission_inf_gap` を格納し、`§1.2` では `mission_inf_gap` も計算源と書いています。符号も `mission_inf_gap` と `mission_signed_margin` で逆転の可能性があります。解釈として、このままだと MA3/MA6 の比較が「大が良い」前提で統一されず、trigger/release の判定が実装者依存になります。ここは詳細設計送りではなく、概念設計で metric 名と符号を一本化すべきです。

4. `§10.1 / §4.2` の `admit_warmstart_to_da` は、T066 側の archive 不変条件を壊す可能性があります。事実として、この helper は `archive_target="DA"` への upsert だけ行い、`DA capacity` 超過時の eviction を「別途処理」としていますが、`§4.2` のフローにはその直後の eviction 呼出がありません。解釈として、戻り値の `ArchiveState` が一時的にでも不正状態になり得ます。T066 の契約が「常に capacity 内」を前提にするなら、この API 境界は成立していません。

[Warning]
1. `§4.2` の emergency 判定入力が `AdmissionReport.n_admitted_*` なのか、Run 全体の `BCEvaluationResult.*_pass` 集計なのかが未確定です。archive admission 後の件数を使うと、capacity や CA/DA 方針の影響で「mission_pass=0 3連続」が歪みます。synthesis §8.5 の文言に照らすと、まずは Run 産出物ベースを疑うべきです。

2. `§7.2 / §13 R5` の ranking 契約が曖昧です。`WarmstartCandidate.rank_score` は 1 つしかないのに、本文では CA は `mission_signed_margin`、DA は `novelty` で並べると書いています。片方を caller 計算済みに寄せるなら、`ca_rank_score` / `da_rank_score` を分けるか、選抜関数側で role 別 sort key を明示する必要があります。

3. `§7.4` の epoch filter API は `prev_epoch` と `epoch_age>=2` を同時に扱うには弱いです。`dataset_epoch_id != new_dataset_epoch_id` だけでは「直前 epoch」と「2 epoch 以上前」が区別できません。本文では別 helper 送りですが、SSOT の関数シグネチャに epoch age の情報源がありません。

4. `§13 R7` の緩和倍率 `×2` は、現時点では INCONCLUSIVE のまま SSOT 手前に入り込みすぎています。緩和順だけ確定し、倍率は詳細設計または smoke 後確定に留めた方が安全です。

5. 依頼観点 14 の `C2 parallel-path 5 段階 grep DoD` が本文では具体化されていません。Phase 2 の grep 言及はありますが、「どの経路をどう潰したら完了か」の監査手順としては不足です。

[Suggestion]
1. emergency は少なくとも 2 変数に分けてください。`mode` は監視状態、`boost_for_next_run` あるいは `boost_consumed_run_id` は 25%/1:1 の one-shot 制御です。これで R2 の二重解釈を明示的に切れます。

2. `WarmstartReuseRecord` は `recent_use_run_indices: tuple[int, ...]` を持つ形にした方がよいです。`cooldown=2`、`max_reuse=3`、`rolling=10` をすべて導出できます。

3. metric 名は整理してください。emergency 用は `best_mission_signed_margin` のように「何を max したか」を名前に出し、`margin_inf` は percentile 計算用なら別用途として分離した方が誤読を防げます。

4. `admit_warmstart_to_da` は「不変条件を壊さない pure helper」に寄せる方がよいです。少なくとも `archive_evict_da` まで含めて 1 API にするか、「返り値は transient で次の 1 関数以外に渡してはいけない」と契約化してください。

5. Round 1 の結論としては、R1 と R2 と R4 は相互依存なので詳細設計送りにせず、概念設計で先に潰した方がよいです。特に R2 と R4 は dataclass 形状そのものを変えます。

現状は「方向性は合っているが、状態表現が足りず SSOT がまだ閉じていない」です。上の 4 つの Critical を解消すれば、Round 2 で APPROVED に寄せられます。