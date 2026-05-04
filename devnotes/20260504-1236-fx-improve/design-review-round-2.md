**前提検証**
- Verified: R1-Cr1 の設計意図である `max_clause<=1` 時の P3 N/A 化は採用されている。
- Verified: P2 閾値は `max(3, ceil(0.01*N_valid))` に変更され、母集団依存は改善されている。
- Verified: Run-27 観測値では P1 条件 `raw_max=0.001134 < 0.005` が成立する。
- Unverified: `max_clause_config` と `alpha` が Run-27 実行時の effective config 由来であること。

**施策判定**
- C1: **REQUEST_CHANGES**
- 理由: P3 N/A 化のロジック自体は正しいが、`max_clause_config` の取得元が未定義のままだと、現在の `config/alpha_factory/default.yaml` による過去 Run 診断汚染が起きうる。

**Q1: R1 指摘の解消状況**
- R1-Cr1: **概念上は解消、実装仕様としては未完了**。`max_clause_config<=1` で P3 を N/A にする方針は正しいが、その値は必ず Run 実行時 config から取得すべき。
- R1-W1: **解消**。`K >= max(3, ceil(0.01*N_valid))` は固定 `K>=5` より妥当。
- R1-W2: **ほぼ解消**。ただし `compute_valid_mask` は `trade_sharpe_raw` も `np.isfinite` で見るべきで、必須列存在チェックは mask 内ではなく schema validation で明示する方がよい。
- R1-Sg1/Sg2: **解消**。`confidence`、`falsification`、`plateau_length` 追加は Run-29 判断に有用。

**Critical**
- [Critical] `max_clause_config` の provenance が未定義。現在の `default.yaml` を読むと、Run-27 実行後の設定変更で P3 判定が変わる。  
  修正案: `summary.json` または run artifact の effective config から `max_clause` を読む。取得不能なら `P3` を `N/A: config_unavailable` とし、`confidence` を最大でも `medium` に落とす。

**Warning**
- [Warning] `alpha` も `size_norm` 逆算に使うため、現在 config ではなく run-effective alpha を使うべき。  
  修正案: `alpha_source` を JSON に出し、run-effective alpha 不明時は `size_norm` を参考値扱いにする。
- [Warning] `compute_valid_mask` は `trade_sharpe_raw.notna()` だけだと `inf` が残る。  
  修正案: `np.isfinite(df["fitness_pen"]) & np.isfinite(df["trade_sharpe_raw"])` を使う。
- [Warning] `compute_plateau_length` の `v == last_value` は浮動小数の完全一致依存。  
  修正案: `math.isclose(v, last_value, abs_tol=1e-12)` で判定する。

**Q2: Run-27 分類予測**
- `P1`, `confidence=high` は、`max_clause_config` と `alpha` が Run-27 effective config 由来である前提なら妥当。
- ただし厳密には `P3=N/A` は「P3を反証した」ではなく「P3を評価不能にした」なので、JSON では `evaluated_hypotheses=["P1","P2"]` のように明示するとよい。
- 追加で見るべき指標は `raw_positive_count`、`fitness_pen_positive_count`、`sentinel_by_generation`、`best_generation`、`plateau_start_generation`。

**Q3: 保留事項**
- `--baseline run_id` は別 TODO 切り出しでよい。
- sentinel 内訳は現 archive では分離不能のため、`total + note` で十分。
- 追加保留は「run-effective config snapshot がない場合の診断信頼度低下」。これは設計に明記すべき。

**全体判定**
- **CHANGES_REQUESTED**
- 反証可能仮説: 「current `default.yaml` を使うと、過去 Run の P3 N/A 判定が実行時 config と乖離する可能性がある」。
- 最小変更: `max_clause_config` と `alpha` の取得元を run-effective config に限定し、取得不能時は P3 を `config_unavailable` N/A、信頼度を最大 `medium` にする。