## Verdict
NEEDS_REVISION

## 前提 (C4)
- `verified`: Round 1 の主要 Critical は概ね潰れている。特に SSOT 再定義の抑制、DoD 二層化、threshold-free 化、classify/decide 分離は方向として妥当。
- `verified`: 提示本文上、T075 は `evidence collection only` に寄せており、runtime 切替・自動 rollback・数値閾値確定を Phase 2 / 別 TODO に逃がしている。
- `unverified`: synthesis §12 / §16 / §18.3 / §11.2 の原文は未提示のため、条文準拠そのものは断定しない。
- `falsification`: Round 2 新設 API の型矛盾、責務境界、将来 caller への SSOT 漏れを中心に反証した。

## Critical
- [C1] `EvidenceClass` と `Severity` の型体系が不整合。  
  Fact: `EvidenceClass` は `inconclusive` を含むが、`Severity = Literal["hard_fail", "warning", "ok"]` には含まれない。`classify_smoke_outcome` は `severity = max(...)` としている。  
  Interpretation: `inconclusive` を分類結果にどう伝搬するかが未定義。C8 の中核なので、`Severity` に `inconclusive` を含めるか、`EvidenceClass -> Severity` の変換表を明記する必要がある。

- [C2] `decide_release_action` が `inconclusive` を扱えない。  
  Fact: 分岐は `ok` / `warning` / `hard_fail` のみ。  
  Interpretation: smoke で最も重要な「データ不足は正当な結論」が release hint に反映されない。`inconclusive -> manual_review` または `delay` を明示しないと、実装時に caller ごとの解釈差が出る。

- [C3] `caller が T071 metric → EvidenceClass マッピングを実装` の SSOT 境界がまだ弱い。  
  Fact: T075 は threshold-free だが、どの EvidenceClass を返すかは caller 実装に依存する設計に読める。  
  Interpretation: 数値閾値を避けた代わりに、分類規約が caller 側で分岐するリスクがある。T075 は閾値を持たなくてよいが、`EvidenceClassifierProtocol`、入力 provenance、許容される分類根拠、未対応時は `inconclusive` という規範は SSOT として必要。

## Warning
- [W1] DoD 二層化は妥当だが、`DoD8 だけ cross-run` の根拠を manifest 化した方がよい。  
  synthesis §18.3 の各 DoD に `scope = per_run | cross_run` を持たせると、将来 `5 Run pop_size 一貫性` のような派生 DoD が増えても破綻しにくい。

- [W2] `ReleaseActionRecommendation.recommended_action = "proceed"` は誤読リスクが残る。  
  `hint only` と書いても、名前が強い。`recommended_action` より `review_hint`、値も `candidate_proceed` / `hold_for_review` などに弱める方が安全。

- [W3] `DeletionTarget.source_clause` は同期負債になりやすい。  
  synthesis bullet の引用文字列を持つなら、改訂時に stale になる。`source_anchor` と `source_excerpt_hash`、または `source_clause_id` の方が SSOT として堅い。

- [W4] `RemovalMode = yaml_value_replace` は cleanup の意味から外れやすい。  
  削除対象 manifest なのに value replace を許すと、旧 path 削除ではなく移行変換が混ざる。必要なら `cleanup_action` に改名するか、replace は別 manifest に分けるべき。

- [W5] dual-path enforce は AST grep だけでは弱い。  
  runtime 到達性は import 以外に CLI entrypoint、config key、script path、dynamic import、環境変数、ドキュメント手順から復活する。grep DoD は `source`, `config`, `scripts`, `docs/runbook` を対象に分ける必要がある。

- [W6] typed projection の 4 metric が DoD / FM と 1 対 1 か未確定。  
  `ab_divergence`, `bypass_ratio`, `session_entropy`, `warmstart_shortfall` は FM1/FM3/FM4/FM5 には対応しそうだが、FM2 は `dataset_epoch_id_present` だけでは弱い。epoch 伝搬漏れ検知は `epoch_consistency_class` として明示した方がよい。

## Suggestion
- [S1] `EvidenceClass` の順序を明文化する。  
  例: `hard_fail > warning > inconclusive > ok` なのか、`inconclusive` は順序外で manual review 固定なのかを invariant にする。

- [S2] `SmokeDoDItem` に `scope` を追加する。  
  `dod_id` だけで per-run / cross-run を推論せず、`scope: Literal["per_run", "cross_run"]` を持たせると詳細設計で検証しやすい。

- [S3] `observed_fms` は `observed_failure_modes` に寄せる。  
  略語より役割名にした方が `rollback_relevant_failure_modes` との対比が明確。

- [S4] Round 22 が長期化するなら T075 は pending 推奨。  
  evidence-only mode の先 merge は可能だが、切替 PR の最終 TODO という位置づけと矛盾しやすい。先 merge するなら `runtime unreachable` と `no release decision authority` を CI / tests で固定する必要がある。

## Round 1 から残置の最終確認
- C1/C2/C3/C4/C5/C6 の方向修正は受理可能。ただし Round 2 で `inconclusive` の型落ちと caller 分類規約の漏れが新 Critical として残る。
- W1/W2/W3/W4/W5/W6 は概ね解消。ただし `hint only` の命名、dual-path enforce、FM2 projection は詳細設計前に補強した方がよい。
- S1-S5 は概ね反映済み。特に `classify` / `decide` 分離は良い修正。

## 学術文献 (任意)
- Bailey CSCV / Lo Sharpe は T075 本文では主役にしない方がよい。少数 smoke から性能改善を主張しないための補助規範として置く程度が適切。
- rollback は学術より release engineering / SRE の文脈が近い。`automatic approval 禁止`、`manual review gate`、`runtime reachability check` を運用規範として書く方が実効性が高い。

## 総評
Round 2 は大きく改善されています。Round 1 の最大問題だった「T075 が親 SSOT を再定義する」「数値閾値で smoke 前に判断する」「DoD8 が per-run に混ざる」は、設計方針としてほぼ解消されています。

ただし最終承認には、`inconclusive` の扱いを型・アルゴリズム・release hint の全てで閉じる必要があります。加えて、threshold-free 化した結果として EvidenceClass 分類責務が caller に漏れているため、T075 は数値閾値ではなく「分類規約の SSOT」を持つ形に修正するのが安全です。