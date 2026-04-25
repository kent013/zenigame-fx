全体判定: **CHANGES_REQUESTED**

**1. 使命との整合性**
- Round 1 指摘 1「問題定義が現行実装とずれ」は **概ね解消** です。
- Facts:
- 現行 Stage B はすでに `no_folds` / `insufficient_folds` / `all_folds_unavailable` で fail-closed です。[stage_gate.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/stage_gate.py#L428)
- Round 2 案は「fail-open 反転」ではなく「入力契約 + 可観測性」に問題定義を修正しています。
- Interpretations:
- 使命への寄与軸は Round 1 より明確になりました。
- [Suggestion] この観点では現方針維持でよいです。問題文の主語は「Stage B semantics」ではなく「Stage B への入力窓契約と監査性」に固定してください。

**2. 禁止事項違反**
- Round 1 指摘 2「`fold_sign_ratio` の意味変更不可」は **解消** です。
- Round 1 指摘 6「reason code 統合は監査性低下」は **概ね解消** です。
- Facts:
- Round 2 案は `fold_sign_ratio` を維持し、別名で `positive_fold_ratio_effective` を追加しています。
- 既存 `no_folds` / `insufficient_folds` / `all_folds_unavailable` も維持方針です。
- Interpretations:
- 既存意味論の破壊は避けられています。
- [Suggestion] `stage-gates.md` の canonical reason code 追加は 1 件に絞り、既存 code の置換はしない方針を明文化してください。

**3. 実現可能性**
- Round 1 指摘 5「実装対象パスが古い」は **解消** です。
- Round 1 指摘 7「先に runner 入力窓契約」は **部分解消** です。
- Facts:
- Stage B 実行箇所は `run_ga.py` ではなく `LaneManager` 内です。[swim_lane.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/swim_lane.py#L487)
- `run_ga.py` は `bars_stage_b` を `Tier1Lane.bars_18m` に載せるだけです。[run_ga.py](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py#L755)
- 現行 archive / report には Stage B の `reason_codes` 永続化経路がありません。[archive.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/archive.py#L383) [generate_run_report.py](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/generate_run_report.py#L406)
- Interpretations:
- 提案 D「世代別 Stage B failure reason 集計」は、提案 C のままでは生成不能です。
- 提案 A も `run_ga.py` 単独変更では完結しません。
- [Critical] `run-report` の世代別 reason 集計に必要なデータ経路が設計にありません。  
修正提案: `archive` に `stage_b_reason_codes` 相当を追加するか、`summary.per_generation` に reason histogram を永続化してください。
- [Warning] `stage_b_window_underfilled` を返す責務の置き場が不完全です。  
修正提案: `swim_lane.py` 側で underfilled 用 `StageResult` を組み立てるか、`Tier1Lane` に sufficiency 判定結果を持たせて `LaneManager` が消費する契約にしてください。

**4. 期待効果の妥当性 (C3, C7)**
- Round 1 指摘 3「因果が立っていない」は **部分解消** です。
- Facts:
- `make_wf_folds` の sufficiency 条件は `bars` 本数ではなく `n_unique_dates` です。[walk_forward.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/walk_forward.py#L85)
- 1 fold 最小は `120 + 1 + 20 = 141` 観測日、2 fold 最小は `161` 観測日です。
- Run 7-9 は `bars_stage_b=14351`、期間は 2026-03-01 から 2026-03-15 で、Stage B pass は 0 です。[run-7.md](/Users/ishitoya/repository/zenigame-fx/reports/run-reports/run-7.md#L4) [run-8.md](/Users/ishitoya/repository/zenigame-fx/reports/run-reports/run-8.md#L4) [run-9.md](/Users/ishitoya/repository/zenigame-fx/reports/run-reports/run-9.md#L4)
- Round 2 案の underfilled 判定は `bars_stage_b` 長と `bars_per_day` に基づく近似式です。
- Interpretations:
- 「window 不足が主因らしい」という方向性は妥当です。
- ただし hard 契約の判定式を `bar count` ベースにすると、SSOT の `make_wf_folds` とズレます。
- [Critical] underfilled 判定式が現行 WF 契約と一致していません。  
修正提案: `stage_b_window_months` や `bars_per_day` 逆算ではなく、`make_wf_folds` と同じ observed-day 契約で `n_unique_dates` を使って判定してください。最も安全なのは sufficiency helper を `walk_forward.py` に切り出して両者で共有することです。
- [Warning] 期待効果の文言にまだ「主因」寄りの含みがあります。  
修正提案: 効果表現は「window 不足を他要因から分離可能にする」に留め、因果断定は避けてください。

**5. リスク**
- Round 1 指摘 6 は **概ね解消** です。
- Facts:
- 既存 canonical reason は `no_folds` / `insufficient_folds` / `all_folds_unavailable` で分かれています。[stage-gates.md](/Users/ishitoya/repository/zenigame-fx/docs/alpha_factory/stage-gates.md#L111)
- 新規 reason として `stage_b_window_underfilled` を追加する案です。
- Interpretations:
- 既存粒度は守られています。
- ただし underfilled を runner 側で別 reason にすると、同じ現象が「Stage B 内 reason」と「runner reason」に二重化するリスクがあります。
- [Warning] reason taxonomy が二層化する恐れがあります。  
修正提案: `stage_b_window_underfilled` を `no_folds` / `insufficient_folds` の upstream alias と位置づけるのか、独立 canonical code とするのかを明記してください。曖昧なままだと監査軸が増えます。

**6. スコープの適切さ**
- Round 1 指摘 7 は **部分解消** です。
- Facts:
- Round 2 案は A を runner 契約、B/C/D/E を observability として並べています。
- ただし D は reason 永続化なしでは成立しません。
- Interpretations:
- 順序は改善しましたが、実際の依存順はまだ整理不足です。
- [Warning] 実装順序は `A(入力契約) -> reason 永続化 -> report` に再分解すべきです。  
修正提案: TODO を 2 本ではなく 3 段に切ってください。`契約判定`、`永続化`、`可視化` の順が安全です。

**7. メモリ制約**
- Round 1 から懸念はなく、この観点は **問題なし** です。
- Facts:
- 追加列 2 本のメモリ増分自体は軽微です。
- Interpretations:
- ボトルネックにはなりません。
- [Suggestion] むしろメモリより Parquet schema 追加と report 集計コストの整合を気にすべきです。

**8. 前提検証 (C4)**
- Round 1 指摘 4「C4 前提検証不足」は **大きく改善** しましたが、**未完了** です。
- Facts:
- Round 2 案には前提表が追加されています。
- ただし中核前提 P10/P13 は Unverified のままです。
- `make_wf_folds` を読めば、少なくとも sufficiency の数式自体は現時点で Verified 化できます。[walk_forward.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/walk_forward.py#L86)
- Interpretations:
- C4 への姿勢は改善しています。
- しかし hard 契約を導入する設計で中核前提を Unverified のまま残すのは弱いです。
- [Critical] underfilled 導入の根拠前提が未検証のままです。  
修正提案: P13 を「可能性」ではなく、`n_unique_dates` と `wf_*` から exact に Verified 化してください。P10 は観測値からの推論なので Unverified 維持で構いません。

**9. Design-first 原則 (C1)**
- Round 1 指摘 8「設計参照証跡不足」は **解消** 寄りです。
- Facts:
- docs / devnotes / 実装 / git log の参照一覧は十分に改善されています。
- ただし今回の新論点に直接効く SSOT は `walk_forward.py` と `swim-lane.md` です。
- Interpretations:
- C1 の姿勢は通っています。
- 追加変更の核が upstream contract になった以上、参照集合もそこに寄せるべきです。
- [Suggestion] 参照済み一覧に [walk_forward.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/walk_forward.py#L22) と [swim-lane.md](/Users/ishitoya/repository/zenigame-fx/docs/alpha_factory/swim-lane.md#L87) を追加してください。

主な結論は 3 点です。Round 1 の「問題定義ずれ」「`fold_sign_ratio` 意味変更」「C1/C4 不足」はかなり改善しました。一方で、`stage_b_window_underfilled` の判定式が現行 WF 契約と一致していないこと、そして世代別 failure reason 集計の永続化経路が設計に無いことは、まだ Critical です。この 2 点を直せば、次ラウンドでは `APPROVED` に寄せられます。