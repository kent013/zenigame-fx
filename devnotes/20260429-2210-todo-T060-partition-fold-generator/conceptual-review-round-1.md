全体判定: `CHANGES_REQUESTED`

**観察事実**
- T060 は 24m=104w の canonical partition と、B 62w 内の 5 fold を deterministic に生成する設計です。[conceptual-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-2210-todo-T060-partition-fold-generator/conceptual-design.md#L5)
- Stage A を時系列上で Stage B の後ろに置く設計は、T060 文書でも明示されています。[conceptual-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-2210-todo-T060-partition-fold-generator/conceptual-design.md#L23)
- ただし current HEAD の実装はまだ旧 Stage B 契約で、`StageGateConfig` は `stage_b_window_months` と `wf_*_days` を持ち、`evaluate_stage_b()` は `make_wf_folds()` を直接呼んでいます。[stage_gate.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/stage_gate.py#L133) [stage_gate.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/stage_gate.py#L560)
- さらに preflight も `compute_max_folds()` / `wf_min_unique_dates()` に依存しており、`swim_lane.py` と `run_ga.py` で現役です。[swim_lane.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/swim_lane.py#L465) [run_ga.py](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py#L1260) [walk_forward.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/walk_forward.py#L27)
- T060 の不変条件チェックは `(end - start).days // 7` に依存しています。[conceptual-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-2210-todo-T060-partition-fold-generator/conceptual-design.md#L57) [conceptual-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-2210-todo-T060-partition-fold-generator/conceptual-design.md#L121) [conceptual-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-2210-todo-T060-partition-fold-generator/conceptual-design.md#L198)
- T059 詳細設計は window 境界を `00:00 UTC` 固定、`_compute_window()` も `timedelta(weeks=104)` で作る前提です。[detailed-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-2113-todo-T059-epoch-window-manager/detailed-design.md#L237) [detailed-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-2113-todo-T059-epoch-window-manager/detailed-design.md#L430)

**解釈**
- 使命との整合性はあります。T060 自体は live_criteria を直接改善する施策ではなく、T061-T064 が正しく動くための基盤固定です。
- 禁止事項違反は見当たりません。期間延長も閾値緩和もしていません。
- ただし Phase 2 申し送りが不十分で、このままだと将来の置換時に旧 preflight 契約が残り、Partition/Fold 設計と現行 runtime の整合が崩れます。
- C3/C7 については、この TODO は統計的主張を新規導入していないため基本 N/A です。期待効果は「精度向上」ではなく「評価期間の canonical 化」と書くのが妥当です。
- メモリ制約は T060 単体では問題ありません。重いのは T070 以降で bar slice をどう保持するかです。

[Critical]
- Phase 2 の置換対象が `make_wf_folds` だけでは足りません。  
Fact: T060 文書は Phase 2 で `walk_forward.py:make_wf_folds` を置換すると書いていますが、current HEAD は `swim_lane.py` と `run_ga.py` の preflight でも `compute_max_folds()` / `wf_min_unique_dates()` を使っています。[conceptual-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-2210-todo-T060-partition-fold-generator/conceptual-design.md#L270) [swim_lane.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/swim_lane.py#L465) [run_ga.py](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py#L1260)  
Interpretation: T061-T064 で FoldGenerator へ移行しても、旧 preflight が残ると underfilled 判定や `wf_min_folds_required` が旧 observed-day 契約のまま走り、誤 reject の温床になります。  
修正提案: Phase 2 申し送りを「`make_wf_folds` 置換」ではなく「`walk_forward.py` 契約の廃止または再定義、`stage_gate.py` / `swim_lane.py` / `run_ga.py` / `docs/alpha_factory/stage-gates.md` / config loader の同時更新」に広げて明記してください。

[Warning]
- C4 の前提検証で「現行 `walk_forward.py` は 6m 用」という記述は current HEAD と一致していません。  
Fact: T060 文書は `walk_forward.py` を「現行 6m 用 fold logic」と書いていますが、実際の current HEAD は `stage_b_window_months=18` と `bars_18m` を前提に動いています。[conceptual-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-2210-todo-T060-partition-fold-generator/conceptual-design.md#L34) [stage_gate.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/stage_gate.py#L134) [stage_gate.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/stage_gate.py#L562)  
Interpretation: ここを誤記したままだと、置換影響範囲の見積もりを誤ります。C1/C4 的には直した方がいいです。  
修正提案: 「現行 observed-day index ベースの WF helper。Stage B 18m 契約と preflight に使用中」と書き換えてください。

[Warning]
- 長さ不変条件の検証が floor division 依存で、壊れた境界を静かに通す余地があります。  
Fact: `length_weeks` と mismatch check はどちらも `.days // 7` を使っています。[conceptual-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-2210-todo-T060-partition-fold-generator/conceptual-design.md#L57) [conceptual-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-2210-todo-T060-partition-fold-generator/conceptual-design.md#L121) [conceptual-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-2210-todo-T060-partition-fold-generator/conceptual-design.md#L198)  
Interpretation: T059 前提では本来 00:00 UTC の週境界ですが、設計としては `104w + 6d` のような壊れた window を 104w と誤認し得ます。  
修正提案: `timedelta(weeks=104)` 等との厳密一致で検証し、`Period.__post_init__` で `UTC-aware`、`end > start`、`(end - start)` が期待単位に一致することを明示してください。加えて `cursor == window.end` の assert も入れるべきです。

[Suggestion]
- `Period.label` は命名自体は妥当ですが、raw string を downstream 契約にしない方が安全です。  
Fact: `FoldGenerator` は `stage_b.label == "stage_b"` に直接依存しています。[conceptual-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-2210-todo-T060-partition-fold-generator/conceptual-design.md#L193)  
Interpretation: T061-T064 が string literal 依存で増えると typo で壊れやすくなります。  
修正提案: `PeriodLabel` の `StrEnum` か module-level constants に寄せてください。命名案自体は `stage_b` / `stage_a` / `stage_c_lite_1..3` / `stage_c` / `embargo_after_*` で問題ありません。

[Suggestion]
- 半開区間 `[start, end)` はこの方針で良いです。  
Fact: T060 は engine 側消費を `start <= bar.timestamp < end` と明示しています。[conceptual-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-2210-todo-T060-partition-fold-generator/conceptual-design.md#L229)  
Interpretation: leakage 回避と連続境界の監査性の両方で最も無難です。  
修正提案: T070 handoff に「比較は必ず UTC 正規化済み timestamp で行う」を 1 行足してください。

[Suggestion]
- bar 数換算は参考値に留め、T060 の invariant に入れない方がいいです。  
Fact: 文書は `1 week = 10080 bars` を置いています。[conceptual-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-2210-todo-T060-partition-fold-generator/conceptual-design.md#L237)  
Interpretation: 現状の 24/7 fill 契約とは整合しますが、将来の欠損補修や feed 異常まで T060 が責任を持つべきではありません。  
修正提案: 「bar count は engine 側の slice 結果に従い、T060 テストでは datetime 境界のみ検証」と明記してください。

質問への回答を短くまとめると、1 は「概ね Yes だが厳密 timedelta 検証に直すべき」、2 は「Yes」、3 は「Yes」、4 は「T060 単独では触らない方針でよいが Phase 2 handoff を拡張必須」、5 は「命名はよいが string 契約は避けるべき」、6 は「見落としは旧 preflight 契約、config/docs SSOT の廃止計画、bar count を invariant に入れないこと」です。 Design-first の参照は実施済みですが、T058-T060 devnotes は現時点で未追跡なので git 履歴監査はまだ効いていません。