**全体判定: CHANGES_REQUESTED**

**Critical**
- `scripts/smoke/measure_step1.8_memory.sh:17`  
  `LOG_DIR="reports/smoke/step1.8"` を再利用しますが、開始時に既存の `run-*.log` / `sample-*.jsonl` を消していません。現在 run の sampler が失敗して `sample-N.jsonl` を生成しない場合でも、過去 run の同名 `sample-N.jsonl` が残っていれば `aggregate()` は成功 sample と誤認できます。Round 4 の missing sample 検出は「ファイル不在」には効きますが、「同名 stale file」には効かないため、B2 SSOT を破れます。
- `scripts/smoke/aggregate_step1.8_memory.py:102`  
  番号突合は rigorous ですが、sample が現在の `run-N.log` と同じ実行に属する証明がありません。過去の matching pair が残ると `n_samplers_succeeded == n_runs` を満たし得るため、merge gate が stale data contamination を許します。

**Warning**
- `scripts/smoke/sample_worker_rss.py:55`  
  `create_time < sampler_start_time` は方向性として妥当ですが、OS/psutil の時刻解像度次第で「sampler 起動直後に起動した run_ga」が同秒丸めで除外されるリスクがあります。`sampler_start_time - 1.0` 程度の grace を置くと false negative が減ります。
- `scripts/smoke/aggregate_step1.8_memory.py:65`  
  JSON decode error を無視し、1行でも valid entry があれば sample 成功扱いです。SSOT計測なら malformed line がある時点でその sample は failed に寄せる方が一貫します。

**修正案**
- `measure_step1.8_memory.sh` の開始時に `rm -f "$LOG_DIR"/run-*.log "$LOG_DIR"/sample-*.jsonl` を入れる、または `reports/smoke/step1.8/<timestamp>/` の一意ディレクトリに出力する。
- より堅くするなら sampler JSONL に `run_index` / `started_at` / `root_pid` を出し、aggregate で `run-N.log` と対応検証する。
- JSONL parse で `JSONDecodeError` を検出した sample は failed 扱いにする。

**Fact / Interpretation**
- Fact: Round 3 の missing sample 検出と `n_samplers_succeeded == n_runs` guard は差分上実装されています。
- Interpretation: ただし stale file contamination が残っているため、B2/B3 smoke を merge gate SSOT として採用するにはまだ不十分です。