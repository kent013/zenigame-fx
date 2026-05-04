**全体判定: CHANGES_REQUESTED**

**Critical**
- `scripts/smoke/aggregate_step1.8_memory.py:83`  
  sampler 欠損を完全には検出できません。`run-*.log` が5本あって `sample-*.jsonl` が1本だけ存在する場合でも、`n_samplers_succeeded > 0` かつ RSS 値ありなら B2 が `PASS` になります。`sample-N.jsonl` が未生成の run は `sampler_failed_runs` に入らないため、「sampling 失敗時は B2 INCONCLUSIVE / merge不可」のSSOTを破れます。
- `scripts/smoke/aggregate_step1.8_memory.py:184`  
  B2 health guard が `n_samplers_succeeded > 0` だけなので、全 run の sampling 成功を要求していません。B2 は `n_samplers_succeeded == n_runs`、かつ各 `run-N.log` に対応する `sample-N.jsonl` が非空であることを条件にすべきです。

**Warning**
- `scripts/smoke/sample_worker_rss.py:55`  
  `sampler_start_time` guard は既存プロセス捕捉を防げますが、同時刻以後に別 `run_ga` が起動した場合は依然として最古一致を掴みます。通常の単独 smoke では許容ですが、`--extra-marker` が measure 側で未使用のため、並列 smoke はまだ非対応です。
- `docs/alpha_factory/stage-gates.md:840`  
  docs は「sampling 失敗時は B2 INCONCLUSIVE」と書いていますが、現行 aggregate は missing sample file を失敗扱いしないため実装とまだズレがあります。

**Fact / Interpretation**
- Fact: B3 実判定、`--baseline-dir`、`--b3-tolerance`、exit code 厳格化は差分上実装されています。
- Fact: `sampled_worker` と `sampled_tree` の片方欠損を INCONCLUSIVE にする修正も入っています。
- Interpretation: Round 2 の主要問題はかなり解消されていますが、「一部 run だけ sampling 成功」を PASS にできる穴が残っており、B2 SSOT として採用できません。

**修正案**
- `aggregate()` で `run-*.log` の番号集合と `sample-*.jsonl` の番号集合を突合し、missing sample を `sampler_failed_runs` に追加。
- `evaluate_gates()` で `n_samplers_succeeded == n_runs` かつ `n_samplers_failed == 0` を B2 判定の前提にする。
- 必要なら `summary` に `expected_sample_files` / `missing_sample_files` を出して、失敗理由を JSON に残す。