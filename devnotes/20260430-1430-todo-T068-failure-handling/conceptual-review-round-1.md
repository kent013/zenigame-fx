[VERDICT] `CHANGES_REQUESTED`

[Critical]
1. `FailureSummary.n_failed` の定義が `len(records)` になっており、`FailureRecord` が「per-individual / per-stage」設計であることと整合していません。`§5.2` と `§9.1` では `failed_genome_ids` は集合化している一方、`n_failed` は record 数のままです。  
Fact: 同一 `genome_id` が複数 stage で失敗すると `n_failed` が個体数ではなく失敗イベント数になります。  
Interpretation: `n_succeeded`、`failure_rate`、`decide_run_abort()` が誤判定します。全 fail 判定は「失敗 record 数」ではなく「当該判定対象集合中の一意 failed genome 数」で行う必要があります。  
修正案: `n_failure_records` と `n_failed_genomes` を分離し、abort 判定は後者を使ってください。

2. 全 fail 判定の分母が stage-local で定義されておらず、`synthesis §7.7` の「全個体 fail → run abort」を downstream stage で正しく実装できません。`§1.1` は failure scope を stage 単位とし、`§4.2` の RuntimeError 文言も “stage X” 前提ですが、`§9.1-9.2` の API は per-Run summary しか持っていません。  
Fact: 例えば 100 個体中 10 個体だけが Stage B に進み、その 10 個体が全 crash した場合、`total_individuals=100` だと abort されません。  
Interpretation: これは `synthesis §7.7` の厳密準拠を外します。  
修正案: `aggregate_failures()` は stage ごとに `eligible_genome_ids` もしくは `eligible_count` を受ける形にするか、`FailureSummary` を stage 単位 summary にしてください。

3. degraded result の downstream 伝搬契約が未閉包です。`§7.2` では `constraint_violation=+inf` を返し、`§10.4` では「caller が finite cap 化」記述と「caller が T065 から除外」記述が併存し、`§13 R1` でも pending のままです。  
Fact: 現状の degraded `MissionGapResult` は T065 の finite-domain 契約にそのままは入れられません。  
Interpretation: T068 の中心責務が「degraded result で続行」なのに、degraded object 自体が downstream で poison pill になっています。R1 は詳細設計送りではなく概念設計で確定すべきです。  
修正案: `案A caller除外` をここで確定し、`FailureOutcome` 的な明示フラグ (`should_skip_downstream`) を API に入れて、呼び忘れで壊れない設計にしてください。

[Warning]
1. `failure_reason="contract_violation"` を dataclass に持たせ、テスト計画にも `ValueError` 分離がある一方、`§6.1` の wrapper 擬似コードは `except Exception as exc:` で全部 `exception_raised` に落としています。分類規約が未確定です。`ValueError` を契約違反として別 reason にするなら、ここで明文化が必要です。

2. `§8.1 validate_finite_canonical_five` の docstring では `trade_count` を検査対象に挙げていますが、擬似コードの `candidates` に入っていません。概念設計段階でも、検査対象 SSOT と例示コードは揃えておくべきです。

3. `stage` の型が wrapper API では `str`、`FailureRecord.stage` では `Literal[...]` です。observability の cardinality 崩れを防ぐためにも、概念設計時点で `Literal` か `Enum` に寄せた方が安全です。

4. `KeyboardInterrupt` だけ通す設計は弱いです。`R3` の pending は妥当ですが、少なくとも `SystemExit` をどう扱うかは概念設計に含めた方がよいです。`except Exception` なら通常 `SystemExit` は捕まえませんが、その意図を明記してください。

5. `FailureSummary.failure_rate = n_failed / max(total_individuals, 1)` は 0 除算回避としては動きますが、`total_individuals=0` を 0.0 とみなす意味づけが曖昧です。abort false は妥当でも、summary 意味論は注記した方がよいです。

[Suggestion]
1. `FailureSummary` に最低でも以下を分離すると設計が安定します。  
`n_failure_records` / `n_failed_genomes` / `eligible_individuals` / `all_failed: bool`

2. `FailureRecord` に `exception_fingerprint` か `root_cause_summary` を追加すると、同一例外の集約と T071 observability がやりやすくなります。`class + truncated message` だけだと dedupe が弱いです。

3. `validate_finite_bc_result` は top-level scalar だけでなく、nested sub-result をどこまで見るかを概念レベルで決めておいた方がよいです。ここが曖昧だと defense-in-depth が名目だけになります。

4. R2 の sentinel truth table は detailed design 送りでもよいですが、少なくとも `is_feasible` と `mission_signed_margin / mission_inf_gap / constraint_violation` の整合 invariant は概念設計に 1 行で固定した方がレビューしやすいです。

5. `zenigame core.py:1026-1095` 踏襲度は「例外 catch + full-fail abort」の骨格では概ね合っています。ただし zenigame 由来の単純な `+inf 化` を、FX 側で stage-local summary と immutable dataclass に落とす際の分母定義がまだ抜けています。ここが今回の主要差分です。

補足評価:
- `synthesis §7.7` への方向性自体は合っています。
- `FailureRecord` / `FailureSummary` の導入、`KeyboardInterrupt` 透過、`全 fail 時 raise は caller` という責務分離も基本方針は妥当です。
- `R4` と `R5` を pending のままにするのは許容範囲です。
- `R1` は pending 不可、`R2` は半確定ではなく invariant を先に固定、が今回の判断です。

結論として、この概念設計は骨格は良いですが、`abort 判定の単位` と `degraded 伝搬契約` が未確定のままでは T068 の中心責務を満たしません。ここを修正すれば Round 2 で `APPROVED` に寄せられます。