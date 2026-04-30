## Verdict
NEEDS_REVISION

## 前提 (C4)
- `verified`: Round 2 の Critical はほぼ反映され、型・命名・manifest・dual-path enforce はかなり整理された。
- `verified`: T075 は引き続き `evidence collection only`、`hint only`、`runtime unreachable` を前提にしている。
- `unverified`: synthesis 原文・T071-T074 原文は未提示のため、条文準拠そのものは断定しない。
- `falsification`: Round 3 では主に `inconclusive` の集約で情報が落ちるか、caller 規約が実装時に破れるかを見た。

## Critical
- [C1] `max` 集約だと `inconclusive` が `warning` に隠れる。  
  Fact: 順序は `hard_fail > warning > inconclusive > ok`。`warning + inconclusive` が混在すると aggregate は `warning` になり、`decide_release_action` は `hold_for_delay` へ進む。  
  Interpretation: C8 の「データ不足は正当な結論」が消える。`overall_severity` とは別に `has_inconclusive: bool` / `inconclusive_reasons` を持つか、decision 側で `any_inconclusive` を優先して `hold_for_review` に倒す必要がある。

## Warning
- [W1] `EvidenceClassifierProtocol` だけでは「未対応 metric_name は inconclusive」を構造的に強制できない。  
  Protocol は型だけなので、実装が `ok` を返しても検出できない。`supported_metric_names()`、metric registry、または conformance test fixture が必要。

- [W2] `epoch_consistency_class` と DoD8 の責務が重なりやすい。  
  FM2 の per-run 伝搬確認と、DoD8 の 5-run epoch 汚染確認は別物。`epoch_consistency_class` は per-run、`cross_run_epoch_pollution_class` は CrossRun 側、のように名前で分離した方が安全。

- [W3] `source_clause_id` は synthesis 側に anchor 体系がないと成立しない。  
  既存 synthesis に安定 ID がないなら、Round 22 改訂候補に `stable clause anchor` を追加した方がよい。bullet 番号だけだと改訂で壊れやすい。

- [W4] `DeletionTarget` と `MigrationTarget` の複合 case には grouping が必要。  
  旧 key 削除と新 key 置換が同一論理変更なら、`change_group_id` や `supersedes` がないと順序・重複判定が曖昧になる。

- [W5] `candidate_proceed` はまだ強い。  
  hint only なら `no_blocker_observed` の方が誤承認されにくい。少なくとも `requires_manual_review=True` を全ケース固定にする案も検討価値がある。

## Suggestion
- [S1] 集約は `max` 単独ではなく、`AggregateEvidence(severity, has_inconclusive, reasons)` にする。  
  これで `warning + inconclusive` を `severity=warning, has_inconclusive=True` として保持できる。

- [S2] `decide_release_action` は `has_inconclusive` を FM より前、または hard_fail の次に評価する。  
  例: `hard_fail -> hold_for_review`, `has_inconclusive -> hold_for_review`, `FM observed -> hold_for_review`, `warning -> hold_for_delay`, `ok -> candidate_proceed`。

- [S3] dual-path enforce は 4 経路に加えて allowlist を持つ。  
  `docs` の historical note や devnotes の設計記録まで fail にすると運用しづらいので、`docs/runbook` は warning、runtime 経路は fail のように severity を分けるとよい。

- [S4] `observed_failure_modes` と将来の `rollback_relevant_failure_modes` は join 関数名を先に予約する。  
  例: `select_rollback_relevant_failure_modes(observed, policy)`。T075 本体では未実装でよいが、Phase 2 の接続点が明確になる。

## Round 1-2 から残置の最終確認
- Round 1 の大問題だった SSOT 再定義、閾値先行、DoD8 混線、自由形式 Mapping は解消済み。
- Round 2 の型落ちはかなり改善されたが、`inconclusive` が `warning` に隠れる集約問題だけが残っている。
- ここを直せば、概念設計としては APPROVED に近い。

## 学術文献 (任意)
- Bailey / Lo は引き続き補助参照で十分。T075 では性能主張ではなく、少数 smoke から過剰解釈しないための guardrail として置くのが適切。
- release engineering 側は「自動承認しない」「unknown を安全側に倒す」規範を明文化する方が実務的。

## 総評
Round 3 はかなり良い状態です。設計の大枠、責務分離、SSOT への態度、cleanup/migration 分離、dual-path enforce は詳細設計に進める粒度まで来ています。

ただし `warning + inconclusive` の混在で未知情報が落ちる点は、T075 の安全性に直結します。`max` 集約をやめるか、少なくとも `has_inconclusive` を別軸で保持すれば、この概念設計は承認可能です。