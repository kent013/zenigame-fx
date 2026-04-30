## Verdict
APPROVED

## 前提 (C4)
- Round 3 本文のみを対象にレビューし、実コード・git 履歴・T058/T070/T071/T072 原文は未確認。
- T073 Phase 1 は純ライブラリで、runtime / archive / report 配線は Phase 2 以降という境界を前提にする。
- `standard_normal` null は Bailey 原著と同一視せず、Phase 1 の monitor-only placeholder null として扱う。
- Critical は「詳細設計に進む前に概念で閉じないと SSOT が崩れるもの」に限定する。

## Critical
- なし

## Warning
- [W1] `SCAFFOLD_SENTINEL_VALUE = Decimal("-1")` を `AuditDSRMetric.dsr_value` に使うのは妥当だが、`sharpe_ratio` / `skew` では `-1` が有効値になり得る。非 `ok` 時の moment 系 field は「解釈禁止」を invariant に明記し、可能なら `DSR_VALUE_SENTINEL` と `MOMENT_SENTINEL` を分ける。
- [W2] `unique canonical genome_id` は概念として正しいが、詳細設計で canonicalization の単位を必ず固定する必要がある。特に同一 genome の retry、cache hit、fold 別評価、seed 違い評価を raw / unique のどちらに入れるかを test case 化するべき。
- [W3] `n_trial_candidates_raw` が Phase 1 で取得不能な場合に備え、`raw >= unique` invariant だけでなく「raw unknown を許すか」を決める必要がある。`None` 禁止なら `raw = unique` を conservative lower-bound として `raw_count_status` を持つ案が安全。
- [W4] PBO/SPA scaffold から数値 field を消した判断は正しいが、Phase 2 で field 追加する場合は serialization consumer が unknown field を無視できることを前提にしない方がよい。`schema_version` check helper を同時に用意するのが安全。
- [W5] stratification の marginal default は妥当だが、caller responsibility だけでは弱い。API 側で `stratification_mode="marginal"` を default にし、interaction は allowlist 指定時だけ許可する設計にすると逸脱を防げる。

## Suggestion
- [S1] `AuditNullModel` に `trial_counting_policy_version = "canonical-genome-v1"` を追加すると、後で canonicalization 変更が起きても比較不能性を明示できる。
- [S2] `AuditDSRMetric` の非 `ok` field は、`dsr_value=-1`、`n_observations` は実測値、moment 系は `0` 固定など、field ごとに sentinel policy を分けて docstring 化すると読みやすい。
- [S3] `statistics.py` docstring 同期更新は別 PR に分けず T073 PR に含める方がよい。同じ PR でないと一時的に v1/v2 文脈の SSOT が割れる。
- [S4] C2 parallel-path grep は `deflated_sharpe_ratio`、`dsr`、`sharpe_calc_version`、`archive_role`、`RunObservabilityReport`、`audit` を最低限の検索語にするとよい。

## Round 1-2 から残置の最終確認
- Phase 1 境界は「純ライブラリ」で一貫し、Round 1 C1 は解消済み。
- `n_trials` の母集合は survivor 条件付けを避ける形に修正され、Round 1 C3 / Round 2 C1 は概念上解消済み。
- `AuditNullModel` は Phase 1 scope に閉じ、`archive_sample` を削除したため Round 2 C2 は解消済み。
- PBO/SPA scaffold は数値 field なしになり、Round 2 C4 は解消済み。
- `statistics.py` docstring 同期が DoD に入ったため、Round 2 C5 は詳細設計で検証可能な状態になった。

## 学術文献 (任意)
- Bailey & López de Prado の DSR は、trial 数と trial Sharpe 分布の仮定が値の意味を決めるため、`AuditNullModel` を明示した Round 3 設計は妥当。
- White Reality Check / Hansen SPA は benchmark 対比の loss differential と bootstrap が中心なので、T073 で scalar 値を先置きしない scaffold は適切。
- Bailey et al. PBO / CSCV は performance matrix 前提なので、Phase 1 で未実装タグに留める判断は synthesis §18.2 に整合する。
- Politis & White は SPA 実装時の dependent bootstrap / block length 選定で参照すればよく、T073 Phase 1 の必須要素ではない。

## 総評
Round 3 は詳細設計に進めてよい水準です。Round 1-2 の SSOT 不整合だった Phase 境界、DSR null provenance、trial 母集合、PBO/SPA scaffold、既存 `statistics.py` 文脈衝突はいずれも概念上解消されています。

残る論点は実装時の sentinel policy、canonical genome dedup、schema version helper、stratification API guard です。これらは概念差し戻しではなく、詳細設計の invariant / test case / DoD で潰せる範囲です。