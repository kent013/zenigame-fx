**全体判定: APPROVED**

**Critical**
- なし。採用すべきでない根拠は見つかりません。

**Warning**
- `scripts/smoke/aggregate_step1.8_memory.py:55`  
  header は「1行目」と設計されていますが、実装は header が途中にあっても受理します。実運用上は sampler が必ず先頭に書くため問題化しにくいですが、SSOTをさらに厳密にするなら最初の非空行が header でない場合は `header_missing` に寄せるとよいです。
- `scripts/smoke/sample_worker_rss.py:57`  
  `sampler_start_time - 1.0` grace は false negative 防止として妥当です。一方、同秒付近で別 `run_ga` が起動した場合の混入余地は残りますが、単独 smoke 前提 + `rm -f` + header検証により merge gate の主要リスクではありません。

**Fact**
- `scripts/smoke/measure_step1.8_memory.sh:22` で stale `run-*.log` / `sample-*.jsonl` の初期化が入り、過去ファイル混入の主要反証は解消されています。
- `scripts/smoke/sample_worker_rss.py:151` で header が出力され、`scripts/smoke/aggregate_step1.8_memory.py:143` で `run_index` 検証されるため、sample と run の対応付けは成立しています。
- `scripts/smoke/aggregate_step1.8_memory.py:66` で JSON decode error、`header_missing`、`no_data_samples`、`run_index_mismatch` が failed 扱いになり、B2 INCONCLUSIVE へ落ちる経路はSSOTと整合しています。
- `scripts/smoke/aggregate_step1.8_memory.py:272` の exit code は B2/B3 両方 PASS のみ `0` で、merge gate と整合しています。

**Suggestion**
- smoke helper の unit test が未提示なので、別タスクで `missing sample` / `stale header mismatch` / `json_decode_error` / `B3 baseline missing` の小さいテストを追加すると、将来の退行防止が強くなります。