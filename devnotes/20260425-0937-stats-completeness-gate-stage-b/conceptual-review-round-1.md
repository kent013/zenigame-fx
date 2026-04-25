全体判定: **CHANGES_REQUESTED**

Design-first 参照済み:
[docs/alpha_factory/stage-gates.md](/Users/ishitoya/repository/zenigame-fx/docs/alpha_factory/stage-gates.md#L104), [docs/alpha_factory/statistics.md](/Users/ishitoya/repository/zenigame-fx/docs/alpha_factory/statistics.md#L115), [docs/alpha_factory/concepts/genome-archive-schema.md](/Users/ishitoya/repository/zenigame-fx/docs/alpha_factory/concepts/genome-archive-schema.md#L15), [devnotes/20260423-1540-stage-gate-implementation/conceptual-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260423-1540-stage-gate-implementation/conceptual-design.md#L136), [src/alpha_factory/stage_gate.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/stage_gate.py#L348), [src/alpha_factory/archive.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/archive.py#L348), [scripts/alpha_factory/generate_run_report.py](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/generate_run_report.py#L406), [scripts/alpha_factory/run_ga.py](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py#L250)。  
git log 参照済み: `0f7aa06` (T014), `39619ec` (T015), `efaf365` (T018), `ad925d0` (T021)。

**1. 使命との整合性**
Facts:
- Stage B は現行でも `no_folds` / `insufficient_folds` / `all_folds_unavailable` で fail-closed です。[stage_gate.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/stage_gate.py#L428)
- Stage B は Stage A 通過個体にしか実行されません。[swim_lane.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/swim_lane.py#L483)
- Run 7/8 は Stage A pass が 48/66 ある一方で Stage B pass は 0、Run 9 は Stage A pass 自体が 0 です。[run-7.md](/Users/ishitoya/repository/zenigame-fx/reports/run-reports/run-7.md#L55), [run-8.md](/Users/ishitoya/repository/zenigame-fx/reports/run-reports/run-8.md#L55), [run-9.md](/Users/ishitoya/repository/zenigame-fx/reports/run-reports/run-9.md#L55)

Interpretations:
- 本案の核である「fail-open → fail-closed 反転」は、現行コードの主要欠陥ではありません。
- live_criteria への本質的貢献は「新ゲート追加」より「Stage B が十分な窓を受け取っているかの契約化」と「失敗理由の可観測化」です。

- [Critical] 問題定義が現行実装とずれています。  
修正提案: 本案を「Stage B 統計可観測性」単独ではなく「Stage B 入力窓の充足検証 + 失敗理由の永続化」に再定義してください。

**2. 禁止事項違反**
Facts:
- 現行 `fold_sign_ratio` は「正 fold 比率」ではなく「隣接 fold 間の符号反転比率」です。[statistics.md](/Users/ishitoya/repository/zenigame-fx/docs/alpha_factory/statistics.md#L115), [statistics.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/statistics.py#L234)
- archive の `fold_sign_ratio` 列もその意味で SSOT 化されています。[genome-archive-schema.md](/Users/ishitoya/repository/zenigame-fx/docs/alpha_factory/concepts/genome-archive-schema.md#L43)

Interpretations:
- 提案の `fold_sign_ratio = 正 fold 数 / 有効 fold 数` への再定義は、名前と機能の対応を壊します。
- 既存 archive/report の意味論を無言で変更するので危険です。

- [Critical] `fold_sign_ratio` の意味変更は不可です。  
修正提案: 新指標は `positive_fold_ratio_effective` など別名で追加し、既存 `fold_sign_ratio` は維持してください。

**3. 実現可能性**
Facts:
- 提案文の `src/alpha_factory/genome_archive.py` は現行には存在せず、実装箇所は [archive.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/archive.py#L348) です。
- archive には既に `fold_sign_ratio` / `dsr` 列があります。[archive.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/archive.py#L54)
- run-report も既に `fold_sign_ratio / dsr` 分布を出しています。[generate_run_report.py](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/generate_run_report.py#L406)

Interpretations:
- 実装差分の見積もりが最新コードと一致していません。
- 本当に足りないのは「列の新設」より `n_fold_effective` と reason 可視化です。

- [Warning] 実装対象の認識が古いです。  
修正提案: 変更対象を `stage_gate.py`, `archive.py`, `generate_run_report.py` に絞り、追加差分を `n_fold_effective` と `stage_b_reason_codes` 相当に限定してください。

**4. 期待効果の妥当性**
Facts:
- Run 8 の summary では `stage_b_window_months=18` に対し `bars_stage_b=14351`、期間は 2026-03-01 から 2026-03-15 です。[run-8/summary.json](/Users/ishitoya/repository/zenigame-fx/reports/run-reports/run-8/summary.json#L5)
- 現行 runner は Stage B bars を `dataset.start/end` 全体として読み込みます。[run_ga.py](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py#L257)
- Run 7/8/9 の `fold_sign_ratio: n=0` は観測されています。[run-7.md](/Users/ishitoya/repository/zenigame-fx/reports/run-reports/run-7.md#L79), [run-8.md](/Users/ishitoya/repository/zenigame-fx/reports/run-reports/run-8.md#L79), [run-9.md](/Users/ishitoya/repository/zenigame-fx/reports/run-reports/run-9.md#L79)

Interpretations:
- `n=0` の主因は「統計契約が緩い」より「Stage B に 18 ヶ月相当が供給されていない」可能性が高いです。
- Run 7-9 の 3 run 観測だけで gate semantics を主因認定するのは C7/C4 的に弱いです。

- [Critical] 効果主張の因果が立っていません。  
修正提案: まず `bars_stage_b` が WF 最小要件を満たさない場合に `stage_b_window_underfilled` で fail-fast する案を先行させ、その上で統計欠損監査を追加してください。
- [Warning] `stage_b_min_effective_folds=3` は値追加先行です。  
修正提案: 先に monitor-only で `n_fold_effective` 分布を記録し、実測後に hard gate 化してください。

**5. リスク**
Facts:
- 現行 canonical reason code には `all_folds_unavailable` が既にあります。[stage-gates.md](/Users/ishitoya/repository/zenigame-fx/docs/alpha_factory/stage-gates.md#L119)
- 提案はこれを `stats_unavailable` に統合します。

Interpretations:
- umbrella code への統合だけだと、既存の診断粒度を落とします。
- 問題が「fold 0 件」「1 件しかない」「全 unavailable」で区別しづらくなります。

- [Warning] reason code の統合は監査性を下げます。  
修正提案: `no_folds` / `insufficient_folds` / `all_folds_unavailable` は維持し、必要なら補助タグとして `stats_unavailable` を追加してください。

**6. スコープの適切さ**
Facts:
- 本案は gate semantics、archive schema、report、test を同時に触ります。
- 一方で upstream の `run_ga` 入力窓契約が未解決です。[run_ga.py](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py#L250)

Interpretations:
- 先に直すべきボトルネックは Stage B の入力窓契約です。
- その前に schema/report を広げると、原因分離が悪くなります。

- [Warning] スコープ順序が逆です。  
修正提案: TODO を 2 本に分割してください。1 本目は `run_ga` の Stage B window sufficiency 契約、2 本目は Stage B observability 強化です。

**7. メモリ制約**
Facts:
- `int/float` 数列の追加自体は軽微です。

Interpretations:
- メモリ制約には抵触しません。

- [Suggestion] メモリ面は概ね妥当です。`reason_codes` 永続化をするなら可変長文字列より compact な flat カラムを優先してください。

**8. 前提検証 (C4)**
Facts:
- 提案文の「archive に `fold_sign_ratio` が無い」「run-report 側に無い」「fail-open がある」は、現行 HEAD と一致しません。[archive.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/archive.py#L386), [generate_run_report.py](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/generate_run_report.py#L406), [stage_gate.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/stage_gate.py#L428)

Interpretations:
- Verified 前提が不足しています。
- 現時点では提案の中心仮説が未検証です。

- [Critical] C4 未充足です。  
修正提案: 概念設計の冒頭に「前提表」を追加し、各前提に `Verified/Unverified` と参照ファイルを付けてください。

**9. Design-first 原則 (C1)**
Facts:
- T014/T015/T018/T021 で Stage gate, archive, run_ga, run-report は既に統合済みです。
- 特に T018 の run_ga は Stage B 窓を `dataset` 契約で供給する設計です。[config.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/config.py#L142), [run_ga.py](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py#L250)

Interpretations:
- 今回の提案は Stage B の現象を gate 単体に帰属しすぎで、runner 契約まで読めていません。

- [Warning] C1 の証跡が不足しています。  
修正提案: `docs/alpha_factory/stage-gates.md`, `concepts/genome-archive-schema.md`, `statistics.md`, `devnotes/20260423-2324-run-ga-full-rewrite/*`, `git log` を参照済み一覧として設計ノートに明記してください。

最小修正方針はこれです。

- `fold_sign_ratio` は現義のまま維持する
- 新規列は `n_fold_effective` と `positive_fold_ratio_effective` に分ける
- `stats_unavailable` は既存 reason の置換ではなく補助タグにする
- 先に `run_ga` 側で `bars_stage_b` 充足性を検証し、不足時は明示 reason で落とす
- report 強化は「世代別 Stage B failure reason 集計」を主眼にする

この修正が入れば再レビューで `APPROVED` に寄せられます。