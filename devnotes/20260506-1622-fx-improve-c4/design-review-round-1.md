**レビュー結果（先に結論）**

全体判定: **CHANGES_REQUESTED**

最小修正で収束可能です。主な修正要求は3点です。  
1. `selection_score` 9要素化に合わせて、レポート契約と説明文の更新を必須化  
2. `fold_robust_threshold=0.4` の根拠記述を修正（`mean=0.296 ⇒ 全員0` は成立しない）  
3. 設定の置き場所と公開性を明確化（`StageGateConfig` は `stage_gate.py` 側）

**主要根拠（Fact）**
- 現行 `selection_score` は8要素で `v3_1_stage_b_priority` 固定: [run_ga.py](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py:181), [run_ga.py](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py:1023)
- `generate_run_report.py` は `v3_1_stage_b_priority` までしか分岐せず、新スキーマは legacy note に落ちる: [generate_run_report.py](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/generate_run_report.py:772)
- テストも8要素固定: [test_alpha_factory_run_ga.py](/Users/ishitoya/repository/zenigame-fx/tests/scripts/test_alpha_factory_run_ga.py:595)
- `StageGateConfig` 定義は `stage_gate.py` 側: [stage_gate.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/stage_gate.py:374)
- run-36実データでは `stage_a_pass` 個体の `pfre>=0.4` が 77/1900（約4.05%）でゼロではない（実測）

---

1. **設計妥当性**: **APPROVE（条件付き）**  
`fitness_pen` plumbing より `selection_score` 追加の方が局所的で安全です。  
ただし「`run_ga` 本体 + report note + schema名 +関連テスト」を同時更新することが条件です。

2. **fold_robust の binary 化**: **APPROVE**  
この段階では boolean で十分です。lexicographic で `fold_robust=1` を `0` より上位に置くのは、H1への構造介入として一貫しています。

3. **threshold 0.4 の妥当性**: **REQUEST_CHANGES**  
値自体は妥当レンジですが、根拠文の一部が不正確です（`mean 0.296` から「全員0」は導けない）。  
「実測で `>=0.4` が何%いるか」を根拠に置き換えてください。

4. **legacy_selection_score 不変**: **APPROVE**  
fallback は「全体 infeasible」の非常時規則なので、不変でよいです。

5. **テスト網羅性（7件）**: **REQUEST_CHANGES**  
7件に加えて最低2件必要です。  
- `summary.best.selection_score_schema` と要素長（9）の契約テスト  
- `generate_run_report` の新schema note分岐テスト（現状未対応）

---

**禁止事項チェック（出力必須）**
1. 期間延長: **抵触なし**  
2. 見栄え改善: **抵触なし**  
3. GAハック: **抵触なし**（selection規則の構造変更）  
4. 閾値緩和: **抵触なし**（既存ゲート閾値は不変）  
5. 複雑化: **軽微、許容**（1軸追加）  
6. 取引回数削減: **意図的介入なし**（要観測）  
7. オーバーナイト: **抵触なし**  
メタ過学習ガード: **Structural**（主分類）。閾値0.4は補助的パラメトリック要素だが主眼は構造変更。