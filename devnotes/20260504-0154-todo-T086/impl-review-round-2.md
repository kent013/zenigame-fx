**全体判定: CHANGES_REQUESTED**

**Critical**
- `scripts/smoke/aggregate_step1.8_memory.py:167`  
  B3 が常に `INCONCLUSIVE` のままですが、`main()` は `B2 == PASS` なら exit 0 になります。詳細設計 §12.3 は B2/B3 を merge gate としているため、wall time の step 1.7 比 ±20% 未検証でも smoke が成功扱いになり、Round 1 の「運用 gate SSOT」未充足です。これは採用不可の根拠になります。
- `scripts/smoke/aggregate_step1.8_memory.py:155`  
  `sampled_tree is None` でも `sampled_worker < 3GB` なら B2 `PASS` になります。設計では `sampled_process_tree_rss_max < 18GB` は補助条件として明記されており、sampler 出力が欠損している状態を PASS に寄せるのは「sampling 失敗時は INCONCLUSIVE」の方針と不整合です。

**Warning**
- `scripts/smoke/sample_worker_rss.py:33`  
  root process を「cmdline一致の最古プロセス」で選ぶため、既存の別 `run_ga` が残っているとそちらを捕捉します。Round 5 suggestion には合っていますが、smoke 計測の反証観点では cross-run contamination guard が弱いです。sampler 起動時刻以後の process に限定する方が安全です。
- `src/alpha_factory/stage_gate.py:219`  
  `fold_index` non-`B_fold` 拒否の対称化は rigorous です。ただし既存 caller に `fold_index=None` 以外を渡す隠れ経路がないことは、提示テスト結果に依存します。差分上の helper 互換テストは妥当です。
- `docs/alpha_factory/stage-gates.md:780`  
  SSOT セクションは必要事項を概ね含みますが、smoke B3 が未実装なのに「merge gate」と読める構成です。コード実態と docs がズレます。

**Suggestion**
- `scripts/smoke/aggregate_step1.8_memory.py:141`  
  baseline path を引数化し、`reports/smoke/step1.7/` から `wall_time_mean_seconds` を読み、B3 を `PASS/FAIL/INCONCLUSIVE` で実判定するのが最小修正です。
- `scripts/smoke/measure_step1.8_memory.sh:24`  
  sampler 起動後に `run_ga` を起動する構造はよいですが、sampler が別プロセスを掴まないよう run ごとの marker/env を cmdline に含められるとさらに堅いです。

**Fact / Interpretation**
- Fact: Round 1 の B_IS test、#26a/#26b 分離、smoke 3ファイル、docs 追加、`fold_index` 対称化は差分上確認できます。
- Interpretation: コア実装とテスト追加は採用可能水準ですが、smoke merge gate が B3 未検証を成功扱いにできるため、運用受け入れ条件を満たしていません。

**結論**
- `CHANGES_REQUESTED`
- 修正必須は `aggregate_step1.8_memory.py` の B3 実判定と、sampler欠損時の B2 `INCONCLUSIVE` 徹底です。