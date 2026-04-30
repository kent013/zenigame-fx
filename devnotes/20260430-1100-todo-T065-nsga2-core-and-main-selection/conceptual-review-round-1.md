[VERDICT] `CHANGES_REQUESTED`

[Critical]

1. RNG seed 規約が現状のままだと非決定的です。事実: `§11.2` / `§13.5` で `seed = hash(run_id, generation_no, "selection")` を例示しています。Python の `hash()` は process ごとに salt されるため、run を跨ぐ再現性がありません。解釈: `test_run_generation_selection_same_seed_same_result_byte_for_byte` と矛盾します。`SHA-256` や `blake2b` から固定長整数を作る stable seed 規約へ修正が必要です。

2. `effective_constraint_violation` の scalar 合成は、`constraint_violation` が `+inf` を取り得る契約と整合していません。事実: `§1.3` とレビュー観点 8 で `constraint_violation` は `+inf` あり得る前提、`§5.2` では `constraint_violation + 1.0e6 * invariant_count` を採用しています。`+inf + 1.0e6 * N = +inf` なので invariant 件数差が消えます。解釈: 「invariant 1 件で slack を圧倒する」という根拠が `+inf` ケースでは成立していません。`+inf` を禁止して finite に閉じるか、infeasible ordering を scalar ではなく明示的な lex 規約にするか、どちらかを先に確定すべきです。

3. crowding distance が非有限軸で破綻します。事実: `§6` で `mission_inf_gap` は `[0, +inf)`、`§10` で「全 infeasible 個体ゼロではない」ケースも通常処理対象です。すると front 内で `inf - inf` が発生し得ます。解釈: `§8.3` の「軸範囲 0 なら 0 寄与」だけでは不十分で、NaN が出る経路が残っています。`crowding_distance` 入力軸は finite 必須にするか、非有限 front では crowding を使わず `violation -> genome_hash` に退避する規約が必要です。

[Warning]

1. `stage_a_pass=True and bc_result is None` を通常の `excluded` に含めていますが、`§7.1` 自身が「a_pass でも skip 可能?」と未確定です。T064 契約上ここが異常系なら、単なる除外ではなく warning か fail-fast に寄せるべきです。

2. `parent_pairs` の長さ定義が揺れています。`§4.2` では `pop_size` ペア、注記では `2*pop` ペアの可能性も残しています。Phase 2 の breeding API を汚すので、`pair 数` と `offspring 数` をここで固定した方がよいです。

3. `select_survivors` のシグネチャが `§3.1` と `§11.2` で不一致です。小さいですが、Phase 1 の pure API としては早めに閉じるべきです。

4. `eligible < 10 / 30` を C7 と結びつけるのは弱いです。C7 は相関解釈の規律で、選抜アルゴリズムの operational guard とは別です。使うなら「運用 warning」として独立根拠にした方が筋が通ります。

5. front size が 1 または 2 の crowding 規約が未明示です。実装差分を避けるなら、両方とも全員 `inf` を明文化した方が安全です。

[Suggestion]

1. tournament は survivor 抽出後なら `constrained-domination` 再評価より `rank -> crowding -> genome_hash` の crowded-comparison operator を正面から書いた方が仕様が簡潔です。

2. `INVARIANT_VIOLATION_PENALTY=1.0e6` は `INCONCLUSIVE` 扱いで問題ありませんが、smoke 観測条件に「all-infeasible front でも数値安定」「finite violation 域で単調 ordering」を追加した方がよいです。

3. `f2` が `pooled_dd_per_fold_max` である点は明確です。DoD に `b_pooled_cf.max_dd` を誤用したら落ちる negative test を 1 本足すと退行耐性が上がります。

設計全体としては、`B-pooled` を SSOT に据えた軸定義、A-fail/B-invariant-fail の除外、Phase 1/2 分離は概ね妥当です。ですが上の 3 点は NSGA-II core の数値契約と再現性そのものに関わるため、Round 1 時点では `APPROVED` にはできません。修正後は再レビューでよいです。