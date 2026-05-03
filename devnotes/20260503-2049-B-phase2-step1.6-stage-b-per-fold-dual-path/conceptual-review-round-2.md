**全体判定**

APPROVED

Round 1 の Critical 3 件は概念設計レベルでは解消されています。step 2 前提の過剰主張を撤回し、dual-path を legacy fold 判定から物理分離し、前提表も Verified / Unverified / False に分けられています。残件は実装・詳細設計で潰せる Warning / Suggestion です。

**C9 反証結果**
- [Critical] なし。
- [Warning] `D3` の「StageResult 全体が disabled mode と完全一致」は `wall_time_seconds` を含むと不安定です。修正提案: `passed` / `reason_codes` / `metrics["payload"]` / `n_bars` までの deep comparison に限定し、時間 field は除外してください。
- [Warning] `fold` 欠落を bug 扱いにするなら、`_log_canonical_dual_path(stage_label="B_fold", fold_index=None)` を helper 内で明示的に拒否する契約が必要です。修正提案: `stage_label == "B_fold" and fold_index is None` は `ValueError` か WARN ではなく test failure になる形で固定してください。
- [Suggestion] `Stage B 全 4 評価点 (= IS monitor + 5 fold)` は数え方が曖昧です。修正案: 「Stage B の 2 系列、B_IS 1 entry + B_fold 5 entries」に書き換えると誤読が減ります。

**観点別レビュー**
- [Suggestion] 使命との整合性: 観測 only / Stage B side calibration data 拡充に scope が下がり、North Star への間接寄与として妥当です。直接 live_criteria 達成を主張していない点も適切です。
- [Suggestion] 禁止事項: live_criteria・評価期間・GA fitness を変えないガードが明記され、Round 1 の切替誘因リスクは十分に下がっています。
- [Warning] 実現可能性: 物理隔離方針は妥当ですが、実装時に dual-path try を legacy try の外へ置くことが必須です。修正提案: 詳細設計で「dual-path ブロック内では `fold_sharpe` / `fold_reason` / `reason_counts` を write しない」を明文化してください。
- [Warning] 期待効果の妥当性: canonical / legacy gate が別物という注記は十分です。修正提案: run/genome 横断 n>30 は「解釈開始の最低条件」であり、因果結論の十分条件ではないと一文足してください。
- [Suggestion] メモリ制約: 「低リスク仮説」への修正で十分です。smoke 5 Run で peak RSS / wall time / log bytes / WARN 率を見る acceptance も妥当です。
- [Suggestion] Design-first: step 1.5 approved 文書と handoff の制約を取り込めています。Round 2 は既存設計史との整合が取れています。

**承認条件**

概念設計としては APPROVED でよいです。詳細設計または実装前に、`D3` の比較対象から `wall_time_seconds` を除外すること、`B_fold` の `fold_index` 必須契約を helper/test で強制することだけ反映してください。