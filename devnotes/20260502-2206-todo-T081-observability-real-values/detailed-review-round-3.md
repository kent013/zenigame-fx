**全体判定: CHANGES_REQUESTED**

Round 3 で Round 2 の Critical は解消されています。残る実質的な修正要求は 1 点だけで、`isinstance(score, (int, float))` は numpy/pandas 経由の数値型を取りこぼす可能性があるため、`numbers.Real` ベースに変えるべきです。

**Round 1 指摘**
- R1-C1 SSOT 乖離: `APPROVE`。Phase 1 source を明示し、run 内 mixing を禁止するなら観測用途として許容できます。
- R1-C2 key 衝突: `APPROVE`。`list[tuple[float, float]]` 化で解消済みです。
- R1-C3 legacy / via_evaluator 契約: `APPROVE`。必須 4 キー + parity test で妥当です。
- R1-W4 preflight 除外の不可視性: `APPROVE`。count/log/test で十分に可視化されています。
- R1-W5 テスト不足: `APPROVE`。17 件は過剰ではなく、観測配線の退行防止として妥当です。

**Round 2 指摘**
- R2-C1 early `continue`: `APPROVE`。`should_collect_ab_pair` flag 化で既存 `archive.collect_stage_b` / `diagnostics.record_stage_b` を保持できています。
- R2-W1 score source 永続化: `APPROVE_WITH_SCOPE_NOTE`。Step 1 は log のみで許容、Step 6 では `q-force-state.json` に source 保存を必須条件にしてください。
- R2-W2 cross-run RuntimeError 過剰: `APPROVE`。run 内は fail-fast、cross-run は skip old record + warn で妥当です。
- R2-W3 C7 n<30 discipline: `APPROVE`。Step 1 は計算のみ、Step 6 で causal claim を避ける分離は妥当です。
- R2-Suggestions: `APPROVE`。test 14-17 の追加で十分です。

**Critical**
- なし。

**Warning**
- [Warning] `isinstance(score, (int, float))` は numpy 型の取りこぼしリスクがあります。`np.float64` は環境によって `float` 判定されることがありますが、`np.float32` や `np.int64` まで含めるなら前提にしない方が安全です。  
  修正案: `import numbers` し、`isinstance(score, numbers.Real) and not isinstance(score, bool)` に変更してください。`math.isfinite(float(score))` はその後で実行すれば十分です。

**Suggestion**
- test 14 の spy は `wraps=` を使って実処理を通しつつ call count を見る形が安全です。preflight 個体数が 1 の fixture なら `== 1` で十分です。
- stub builder 互換性 test は JSON byte-for-byte equality で妥当です。constructor 分解後も serialize 結果が一致すれば互換性を保証できます。
- test 4 と test 15 は重複ではありません。test 4 は run_ga 集約時の欠損/NaN 除外、test 15 は swim_lane payload 型ガードなので層が違います。
- all-inactive run は `score_source="noop"`、`n_pairs=0`、`status="insufficient_data"` で妥当です。Step 1 の期待挙動として明確です。