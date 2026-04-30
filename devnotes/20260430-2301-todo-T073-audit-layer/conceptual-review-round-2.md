## Verdict
NEEDS_REVISION

## 前提 (C4)
- Round 2 本文のみを対象に、実コード・設計書原文・git 履歴は未確認。
- T073 Phase 1 は純ライブラリ PR、runtime / archive / report 配線なしという境界は正しい前提として扱う。
- `deflated_sharpe_ratio` の既存 docstring が v1 / Phase 1A monitor only 文脈を持つ、という提示内容を前提にする。
- DSR は early gate ではなく audit 指標なので、保守的すぎる値自体は許容されるが、意味論の SSOT 不明瞭さは許容しない。

## Critical
- [C1] Fact: `n_trials = run_evaluated_genomes` は方向性として正しいが、「全評価 genome 数」が canonical unique genome 数なのか、再評価・retry・fold 別評価・cache hit を含む evaluation attempt 数なのか未定義。Interpretation: DSR の補正量が直接変わるため、概念で `trial_counting_policy` を固定すべき。推奨は「selection に投入され得た canonical genome_id の unique count」で、同一 genome の retry / retry-only / cache replay は別 trial にしない。
- [C2] Fact: `AuditNullModelKind = ["standard_normal", "archive_sample"]` だが、`AuditTrialSource = ["run_evaluated_genomes"]` のみで、`archive_sample` の母集団・期間・filter 条件が表現できない。Interpretation: Phase 1 で `archive_sample` を Literal に入れると未実装の意味論だけが API に露出する。Phase 1 は `standard_normal` のみに絞るか、`archive_sample` を `not_implemented` 相当として明示的に reject する invariant が必要。
- [C3] Fact: `standard_normal` null は provenance として明示されたが、Bailey 原著の「trial SR 分布の mean/std を用いて expected max SR を補正する」文脈と同一ではない。Interpretation: `standard_normal` は「Bailey 準拠の既定 null」ではなく「Phase 1 monitor-only の保守的 placeholder null」と明記すべき。特に v2 non-annualized SessionBlock SR では、`std_sr_trials=1` が尺度として妥当かは未検証。
- [C4] Fact: PBO / SPA scaffold の sentinel が `Decimal("0")` で、PBO でも SPA p-value でも 0 は実装後に意味を持つ有効値になり得る。Interpretation: status check 漏れ時に「非常に良い値」と誤読される。T916 は「未実装タグ schema scaffold」を要求しているだけなので、数値 field を持たない scaffold にするか、持つなら `Decimal("-1")` など値域外 sentinel にする方が fail-closed。
- [C5] Fact: 既存 `deflated_sharpe_ratio` の docstring が v1 / Phase 1A monitor only 前提のままなら、T073 が v2 audit 文脈で呼ぶ時点で documentation SSOT が衝突する。Interpretation: Phase 1 純ライブラリ PR でも、`statistics.py` docstring 更新または `audit.py` 側 wrapper docstring で「数式は汎用、v1/v2 の尺度は caller が null_model で固定」と明文化する必要がある。

## Warning
- [W1] `stratification key` の任意組合せは sparse strata を量産し、C7 の `n >= 30` にほぼ到達しない可能性が高い。既定は 3 軸の marginal 集計のみ、interaction は事前登録した少数のみ、という制約を入れるべき。
- [W2] `AuditGenomeRecord` は T058 join には十分寄っているが、audit 再現性には `session_block_schema_version`、`sessionization_version`、`cost_model_version`、`pnl_net_calc_version` のいずれかが run-level か per-genome-level に必要になり得る。
- [W3] `GenomeAuditInput.session_blocks: Sequence[SessionBlock]` は Phase 1 の in-memory transport としてはよいが、「archive admission 時保存」は Phase 2 persistence 設計なので、概念上は「保存形式は Phase 2」と分離した方がよい。
- [W4] `AuditMetricStatus` に `not_implemented` を共通 status として入れると、DSR にも型上は `not_implemented` が入る。実害は小さいが、DSR 用 status と scaffold 用 status を分ける方が invariant は強い。
- [W5] PBO / SPA に Phase 2 field を追加するなら `AUDIT_REPORT_SCHEMA_VERSION = 1.0.0` からの schema bump 規約が必要。field 追加が breaking か minor かを本 PR で決めておくと後続が迷わない。

## Suggestion
- [S1] `AuditNullModel` に `sr_scale = "session_block_non_annualized"` または `return_unit = "session_block"` を追加すると、v1 annualized SR との混線をさらに防げる。
- [S2] `n_trials` と別に `n_trial_candidates_raw` / `n_trial_candidates_unique` を report に持たせると、重複除外の監査が可能になる。
- [S3] scaffold は `status="not_implemented"` と `audit_calc_version` だけにして、`pbo_value` / `spa_value` は実装 PR で追加する設計が最も安全。
- [S4] C2 parallel-path 確認は詳細設計に「既存 archive `dsr` 経路は T073 を import しない」「`audit.py` は runtime から import されない」を grep と import test で確認する項目として入れる。

## Round 1 から残置の最終確認
- C1 / S4 の Phase 1 境界矛盾は解消済み。
- C4 の `expected_bar_count > 0` 混入は解消済み。
- C5 / S1 の per-genome key 欠落は `AuditGenomeRecord` で概ね解消済み。
- C6 の NaN sentinel 問題は解消方向だが、`0` sentinel は PBO/SPA で新しい誤読 risk を作っている。
- C7 の `degenerate_variance` 分離は妥当。
- C8 の SessionBlock transport 方針は方向性妥当だが、Phase 1 in-memory と Phase 2 persistence の境界をもう少し分けるべき。

## 学術文献 (任意)
- Bailey & López de Prado の DSR では、trial 数と trial SR 分布の mean/std が補正の中核なので、`AuditNullModel` の導入は正しい。ただし `standard_normal` は原著そのものというより Phase 1 の暫定 null として扱うべき。
- Bailey et al. の PBO / CSCV は performance matrix 前提なので、現在の scalar scaffold は「未実装タグ」としてのみ妥当。
- Hansen SPA と White Reality Check は loss differential と dependent bootstrap が中心なので、SPA scaffold に scalar p-value だけを先置きしすぎない方がよい。
- Politis & White は block bootstrap 設計時の参照候補として妥当だが、T073 Phase 1 では実装範囲外でよい。

## 総評
Round 1 の主要な構造欠陥はかなり解消されています。特に Phase 1 を純ライブラリに限定したこと、`AuditNullModel` で DSR の provenance を明示したこと、`AuditGenomeRecord` で genome key を持たせたことは前進です。

ただし、Round 2 で新しく導入した `standard_normal` null、`run_evaluated_genomes`、`Decimal("0")` sentinel がまだ監査値の意味論を揺らしています。詳細設計に進む前に、`n_trials` の数え方、Phase 1 null の位置付け、PBO/SPA sentinel の fail-closed 化、既存 `statistics.py` docstring との整合だけは概念側で閉じるべきです。