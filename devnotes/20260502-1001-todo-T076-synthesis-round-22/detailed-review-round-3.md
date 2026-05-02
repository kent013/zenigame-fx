**全体判定**
- `CHANGES_REQUESTED`
- Round 2 の主要 10 件のうち、検証 shell / rationale / pipefail / PR title は概ね解消しています。
- ただし、Round 3 で追加提示された §C-7 により、§6.3 の DoD 表が `SmokeObservabilityProjection` の実 field と一致していないことが確定しました。これは T075 SSOT 1:1 整合の中核なので修正必須です。

**反証・弱点**
- [Critical] §6.3 の DoD2-DoD7 が参照する `SmokeObservabilityProjection.a_pass_only_b_eval` / `parent_selection_metric_class` / `archive_epoch_id_completeness` / `inflow_config_match` / `ca_da_split_match` / `invariant_fail_fast_active` は、§C-7 の `SmokeObservabilityProjection` に存在しません。修正案: 表の SSOT 列を実在 field に置換するか、DoD 判定は `SmokeDoDItem` 側 SSOT であり `SmokeObservabilityProjection` field 直結ではない、と明記して field 名を削除。
- [Warning] §13.3 は `PerRunSmokeDoDResult` / `CrossRunSmokeDoDResult` / DoD1-DoD8 は検証しますが、§6.3 表の SSOT field 名が smoke.py に存在するかは検証しません。今回の field mismatch を機械検証で捕捉できないため、DoD 表検証が不足しています。
- [Warning] §9.3 が 2 回出ています。`### 9.3 anchor 未付与対象...` と `### 9.3 anchor 命名規則` が重複しているため、後者は `### 9.4` に修正が必要です。
- [Warning] 「残り 18 章」の算定はまだ曖昧です。§12.4 / §18.3 は subsection anchor であり、top-level §12 / §18 全体に anchor が付いたわけではありません。修正案: 「章」ではなく「anchorable clause unit」と定義するか、§12 / §18 の未付与範囲を明示。
- [Warning] §F-4 の §22.2 修正文が実質提示されていません。§9.3 の修正は確認できますが、§22 Anchor Index 側の同期は本文証拠不足です。
- [Suggestion] §13.1 の dual-path 検証は語句存在の AND であり、`source_import/scripts/config_yaml => fail_closed` と `docs_runbook => fail_open` の対応関係までは厳密検証していません。設計本文は正しいためブロッカーではありませんが、同一行または小範囲で対応関係を grep するとより堅いです。

**Fact**
- §13.7 は Round 21 同型の 7 章 loop 検証に修正されています。
- §13.0-13.8 は固定 `sed` line range を廃止し、`awk` heading 抽出、個別 `grep -q`、`set -euo pipefail`、`mktemp` + `if` 判定に変更されています。
- §4.4 は `config/**/*.yaml` と `config/**/*.yml` の 2 globs を明記しています。
- §6.3 は完走判定を item-level fail-closed に修正しています。
- §C-7 の `SmokeObservabilityProjection` 実 field は `ab_divergence_class` / `epoch_consistency_class` / `warmstart_shortfall_class` / `bypass_ratio_class` / `session_entropy_class` / `dataset_epoch_id_present` / `report_ref` です。

**Interpretation**
- Round 2 の shell 検証上の Critical は大部分解消しています。
- しかし、§C-7 によって新たに DoD 表の SSOT field 不一致が確認されたため、T076 の「smoke.py SSOT と完全 1:1 整合」という中核条件はまだ満たしていません。
- この不一致は docs-only でも後続実装者を誤誘導するため、`APPROVED` にはできません。

**Round 2 指摘別**
- [Critical] 1 §13.7 rationale.md セクション不一致: `解消`。7 章 loop 検証は §12.2 / Round 21 前例と一致。
- [Critical] 2 固定 line range drift: `解消`。`awk` heading 抽出への変更で主因は解消。
- [Critical] 3 OR grep false positive: `解消`。主要 grep は個別 AND 検証に修正済み。
- [Critical] 4 pipe exit code 消失: `解消`。`mktemp` + `if ! command` で exit code を保持。
- [Critical] 13 / C2 並行経路確認不足: `部分解消`。スコープ限定の説明は妥当。ただし他 docs cross-ref の実検証はしない方針なので、リスク表に明記した現状で許容判断。
- [Warning] G item-level inconclusive: `部分解消`。完走判定は item-level に直っていますが、DoD 表の SSOT field 不一致が残存。
- [Warning] H config_yaml `.yml` 漏れ: `解消`。§4.4 と §13.1 に `.yml` が追加済み。
- [Warning] J 残り章数 / anchor 矛盾: `部分解消`。17→18 の説明は改善しましたが、subsection anchor と top-level 章の算定が混在し、§9.3 重複も残ります。
- [Warning] cross-run overall 誤読: `解消`。`CrossRunSmokeDoDResult.item.status` 単独判定に修正済み。
- [Suggestion] PR title: `解消`。`(Phase 2 切替前提)` が入り、順序保証は明確です。

**必須修正**
- §6.3 の DoD 表から存在しない `SmokeObservabilityProjection.*` field 名を除去または実 field に置換してください。
- §13.3 に DoD 表の SSOT field 検証を追加するか、field 名を表から消して検証対象外であることを明記してください。
- §9.3 重複を `§9.3` / `§9.4` に修正してください。
- §22.2 の実際の修正文を詳細設計に提示し、§9.3 と同期していることを確認可能にしてください。