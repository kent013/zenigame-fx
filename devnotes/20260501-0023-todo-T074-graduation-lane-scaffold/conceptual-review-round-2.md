## Verdict
NEEDS_REVISION

## 前提 (C4)
- [Fact] Round 2 は提示本文のみを SSOT としてレビューしています。ローカル設計書・実コード・git 履歴は確認していません。
- [Fact] T074 Phase 1 は純ライブラリ scaffold で、既存 `swim_lane` / `archive` / `cross_pair` を import しない前提です。
- [Interpretation] Round 1 の主要論点は概ね解消されていますが、新設 `GraduationEpochSummary` と empty archive 契約に副作用があります。

## Critical
- [C1] `has_mission_pass == bool(contributing_run_ids)` は意味論が壊れています。`contributing_run_ids` が「その epoch の run 全体」なら mission fail epoch でも非空になり `has_mission_pass=False` と矛盾します。逆に「mission pass した run」だけなら名前が不正確です。修正案は `mission_pass_run_ids` に rename して `has_mission_pass == bool(mission_pass_run_ids)` にするか、`observed_run_ids` と `mission_pass_run_ids` を分けることです。
- [C2] `archive_epoch_id_active ∈ distinct_dataset_epoch_ids` は、archive 空や epoch 0 件を通常の `insufficient_epochs` ではなく contract violation にしてしまいます。初期状態・空 snapshot・再構築直後は業務不足状態として扱うべきなので、`archive_epoch_id_active: str | None` にするか、`distinct_dataset_epoch_ids` 非空時のみ invariant を適用してください。
- [C3] `recent_epoch_summaries` の「run order 降順 epoch 単位重複除去後 tail」という表現は危険です。本文では `recent[0] == active` なので recent-first の `head N` が正です。`tail` という語を残すと oldest N を取る実装が生まれ、trigger が反転します。

## Warning
- [W1] `recent_epochs_with_mission_pass_required` の caller 引数化は妥当ですが、Phase 2 では config missing 時に fail-closed する必要があります。暗黙 default を置くと Round 1 [C1] の数値固定が復活します。
- [W2] `GraduationTriggerEvaluation.has_recent_mission_pass` は、優先順位で早期 return した場合でも「実際に直近 N epoch が pass したか」を表すのか、「今回 status 判定で評価済みか」を表すのか曖昧です。audit 用なら status と独立に計算するか、`None` を許容する設計にしてください。
- [W3] graduates の snapshot count は妥当ですが、Phase 2 adapter は同一 transaction / 同一 archive snapshot から `n_graduates` と epoch summary を構築する必要があります。連続 read の揺らぎは T074 ではなく adapter contract violation と明記した方がよいです。
- [W4] robust 系集約は Phase 4 候補としては有益ですが、`MultiPairAggregationKind` の SSOT は当面 `worst_pair | mean` に閉じるべきです。robust 系は「synthesis 再確認後に追加候補」と明記してください。

## Suggestion
- [S1] `GraduationEpochSummary` は `dataset_epoch_id`, `observed_run_ids`, `mission_pass_run_ids` の3 field にすると、観測済みだが mission fail の epoch を自然に表現できます。
- [S2] `recent_epoch_summaries` の contract は「active/current から古い順、epoch 単位 unique、`[0]` が active」と明文化してください。
- [S3] T074 module の grep DoD は `archive`, `swim_lane`, `cross_pair`, `ANCHOR_PAIRS`, `holiday`, `DST`, `observability_flags` あたりを明示すると C2/T072 の監査がしやすいです。
- [S4] T064 との集合等価 test は production module で import せず、test 側だけで T064 constants を import して `GRADUATION_BATCH_PAIRS == frozenset({...})` を確認する方針で十分です。

## Round 1 から残置の最終確認
- `直近 N Run` から `直近 N epoch` への修正は方向として正しいです。
- `GRADUATION_BATCH_PAIRS = frozenset(...)` による順序非依存 SSOT は妥当です。
- `GraduationBatchInput` / `GraduationBatchReport` を Phase 4 に送った判断は妥当です。
- 入力異常を `ValueError`、業務不足を status に分ける方針は妥当ですが、empty archive は業務不足側に残すべきです。
- collider bias を T074 で判定せず Phase 2/T071 に送る責務境界は妥当です。

## 学術文献 (任意)
- Phase 4 では White の Reality Check、Hansen の SPA test、Bailey / López de Prado 系の PBO、robust portfolio optimization、CVaR portfolio optimization を候補に置くとよいです。
- ただし T074 Phase 1 の SSOT には入れず、multi-pair aggregation 実装 TODO の参考文献扱いに留めるのが安全です。

## 総評
Round 1 の Critical はほぼ正しく潰れています。特に epoch 基準化、caller 引数化、順序非依存 pair SSOT、batch dataclass の Phase 4 送りは改善として妥当です。

残る必修正は小さいですが重要です。`contributing_run_ids` の意味論と empty archive 契約を直さないと、scaffold の最初の単体テストで「mission fail epoch」と「初期 archive」を正しく表現できません。この2点と `tail/head` 表記を修正すれば、T074 概念設計は APPROVED にかなり近いです。