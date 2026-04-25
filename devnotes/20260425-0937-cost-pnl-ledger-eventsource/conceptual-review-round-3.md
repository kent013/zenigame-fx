全体判定: **CHANGES_REQUESTED**

1. Round 2 Critical の解消
- [Suggestion] Round 2 の Critical だった「archive schema extension と後方互換矛盾」は解消しています。28 カラム fixed schema を触らない方針は現行契約と整合しています。[archive.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/archive.py#L54) [genome-archive-schema.md](/Users/ishitoya/repository/zenigame-fx/docs/alpha_factory/concepts/genome-archive-schema.md#L12)
- [Critical] ただし、現行コードフローでは「GA 完了後に sidecar writer が payload を読んで出力」はそのままでは成立しません。`run_generation()` が返すのは集計値だけで、個体ごとの Stage A payload は保持されません。さらに `GenomeArchive.get_row_snapshot()` は `_max_stage_seen` を落とします。[swim_lane.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/swim_lane.py#L446) [run_ga.py](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py#L814) [archive.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/archive.py#L522)
- [Critical] `metric_stage` を Stage A payload に入れる案も不整合です。`stage_b_evaluated` / `stage_c_evaluated` は Stage A 時点では未確定です。[stage_gate.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/stage_gate.py#L320)
- [Suggestion] 修正提案: Phase A に「generation 実行中に diagnostics collector を別途蓄積し、最後に flush する」経路を明記してください。`metric_stage` は collector 側で最終確定する方が自然です。

2. sidecar 方式の成立性
- [Suggestion] sidecar 不在時の後方互換と書き込みコストは現実的です。既存 consumer は extra key を無視できる作りで、optional 読み込みにも寄せやすいです。[run_ga.py](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py#L16) [generate_run_report.py](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/generate_run_report.py#L286)
- [Warning] sidecar のキーを `genome_id` 単独にするのは弱いです。既存 archive の複合主キー `(lane_id, generation, individual_name)` に合わせるべきです。[genome-archive-schema.md](/Users/ishitoya/repository/zenigame-fx/docs/alpha_factory/concepts/genome-archive-schema.md#L14)

3. Phase A への絞り込み
- [Suggestion] Round 2 よりかなり良く、Phase B/C を将来 TODO に退避した判断は妥当です。
- [Warning] ただし `metric_stage` を Stage A payload に入れる記述だけは、後段結果の逆流を含むので Phase A 単独としてはまだ少し濁っています。payload 拡張は `total_pnl` / `sharpe` までに留める方が素直です。

4. `summary.json` optional field 追加
- [Suggestion] `diagnostics_sidecar` 1 個の追加は許容範囲です。現行出力契約も「追加キーのみ」は許容しています。[run_ga.py](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py#L16)
- [Suggestion] fail-open を徹底するなら、この field は sidecar 書き込み成功時のみ出す、と明記してください。

5. fail-open 原則
- [Suggestion] 「warning のみで GA は止めない」「Medium に格下げ」は妥当です。
- [Warning] run-report 側は現状 skill 文書で必須セクションを固定しているので、`section 省略` より「optional 追加セクション、不在時は not available」と書く方が契約ぶれを避けられます。[SKILL.md](/Users/ishitoya/repository/zenigame-fx/.claude/skills/zenigame-fx-run-report/SKILL.md#L40)

要するに、**Round 2 の archive schema 問題そのものは解消**しています。ただし **sidecar へ何をどう渡して最終 `metric_stage` を確定するか** のデータフローがまだ 1 段足りないので、そこを明文化してから通すのが妥当です。