[VERDICT] `CHANGES_REQUESTED`

[Critical]
- **API 契約が文書内で再び不整合です（実装時の誤読リスクが高い）**。  
  - `§3.1` の `select_survivors(..., rng: random.Random)` は、`§11.2` の「rng 不要」と矛盾。  
  - `§3.1` の `constrained_dominates(..., p_violation, q_violation)` は、`§11.2` の `p_feasible/q_feasible` 付き定義と矛盾。  
  - `§3.1` の `binary_tournament(..., evaluations, rng)` は、`§11.2` / `§9.1` の `sort_keys` 版と矛盾。  
  - `§9.2` の `select_parent_pair` 擬似コードも `binary_tournament(..., evaluations, rng)` 呼び出しのままで、`§9.1` と不一致。  
  このままだと Phase 1 の SSOT が崩れます。`§11.2` に一本化し、他節を完全同期してください。

[Warning]
- `§12.5` の `test_binary_tournament_constrained_domination_chooses_winner` は、`§9.1` の「tournament は crowded-comparison operator のみ」と整合しません。テスト名/期待値を更新しないと誤実装を誘発します。
- `§7.1` の `stage_a_pass=False AND bc_result is not None` を warning 扱いにしていますが、契約違反の検知としては fail-fast (`ValueError`) の方が運用上安全です（default-deny で結果汚染は防げても upstream 異常を見逃しやすい）。

[Suggestion]
- seed payload `f"{run_id}|{gen_no}|selection"` は実用上ほぼ問題ありませんが、将来の仕様変更耐性を上げるなら長さ付き/構造化シリアライズ（例: `json.dumps([run_id, gen_no, "selection"], separators=(",", ":"))`）の方が堅牢です。

Round 1 の主要 Critical（`hash()` 排除、`+inf` 防御、non-finite 軸防御）は狙い通り改善されています。残件は主に「文書内契約の一意化」です。