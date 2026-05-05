**全体判定: CHANGES_REQUESTED**

Round 1 の主要 Critical は概ね解消されています。ただし Round 2 で新たに、`HoldoutLeakError` / `holdout_guard` という名前と実際の責務がズレている点、`n_fold_effective < 3` 注記を report minor 変更として入れるには archive / summary / cross-pair との扱いが曖昧な点が残っています。承認前にここを詰めるべきです。

**本分析の前提**
- 提供テキストのみを根拠にしています。コマンド実行・ファイル読み込み・git 確認は行っていません。
- `docs/alpha_factory/`・`devnotes/`・`git log` の一次確認は未実施です。
- `run_ga.py` / `stage_gate.py` / `generate_run_report.py` の実装詳細は未検証です。
- よって C1 は未完了であり、最終承認は詳細設計フェーズの一次確認後です。

**Facts**
- Round 2 では `max_bar_time < dataset.end` のみの guard から、A/B/Holdout の境界 3 条件と集合重複 3 条件へ拡張されています。
- `9→2 fold` の統計的弱さは「受け入れる副作用」として明記されています。
- 成功判定は数値改善ではなく、disjoint 性・fail-closed・退行ゼロ・ログ可観測性に変更されています。
- `LaneBarsBundle.bars_stage_b` の意味変更に対する波及範囲テーブルが追加されています。

**Interpretations**
- Round 1 の Critical 4 件は、概念設計レベルではほぼ解消されています。
- ただし B-1 は「holdout 保護」ではなく「stage partition integrity guard」です。名前が holdout に寄りすぎると、A/B disjoint 契約の重要性が将来の読者に伝わりにくいです。
- `n_fold_effective < 3` 注記は入れる価値がありますが、report だけに閉じると downstream consumer が誤読します。

**Critical**
- [Critical] `holdout_guard.py` / `HoldoutLeakError` の名前が責務を狭く見せています。実際には A/B/Holdout の三者 disjoint と時系列順序を検証しており、holdout 侵入検知だけではありません。
  - 修正提案: モジュール名は `stage_partition_guard.py` または `partition_guard.py`、例外名は `StagePartitionLeakError` か `StagePartitionError` を検討してください。zenigame `_holdout.py` 相当であることは docstring に残せば十分です。
- [Critical] `n_fold_effective < 3` の INCONCLUSIVE 注記を report だけに入れる設計は不足です。評価指標の信頼度に関わるため、summary/archive/cross-pair 側で無視されると「表示だけ注意喚起」になります。
  - 修正提案: スコープ内に入れるなら `summary.json` に `stage_b_statistical_inconclusive: true` 相当を追加してください。実装が重いなら本 TODO から外し、report 注記も別 TODO に切り出す方が一貫します。

**Warning**
- [Warning] B-1 の 6 条件は冗長ですが、設計上は許容できます。境界条件は順序違反を検出し、集合条件は同一 timestamp 混入を検出するため、目的が異なります。
  - 修正提案: 冗長性を明示して、「境界条件は chronological partition、集合条件は exact timestamp contamination を検出」と書いてください。
- [Warning] B-1 には前提検査が不足しています。`min/max` 前に各 stage が non-empty、`bar_time` が UTC-aware、null なし、単調増加、少なくとも stage 内 timestamp 重複なし、を確認すべきです。
  - 修正提案: B-1 の前に「B-0 入力健全性」として `non_empty` / `timezone` / `not_null` / `monotonic` / `unique within stage` を追加してください。
- [Warning] `max(stage_b) < min(stage_a)` は Stage B が必ず Stage A より前にある設計を固定します。今回の設計では正しいですが、将来 Stage A 位置を確率化する TODO と衝突します。
  - 修正提案: 「本 TODO では Stage A 末尾固定を前提に chronological order を検証する。Stage A 確率化時は disjoint-only guard に再設計する」と明記してください。
- [Warning] 波及範囲に cross-pair / ii-lite が明示されていません。Stage B 指標の意味が変わるなら、cross-pair 評価が Stage B summary を参照する経路があるか確認対象に含めるべきです。
  - 修正提案: 波及範囲テーブルに `cross_pair / ii-lite` 行を追加し、「Stage B 指標を入力に使うなら inconclusive flag と disjoint flag の伝搬を確認」と書いてください。

**Suggestion**
- [Suggestion] `stage_gate_version` bump は妥当です。むしろ「原則実施」ではなく「実施」に寄せてよいです。Stage B 指標の意味が変わるため、過去 history と混ぜない方が安全です。
- [Suggestion] `bars_stage_b_disjoint: true` はよいですが、より誤読を避けるなら `bars_stage_b_excludes_stage_a: true` の方が意味が直接的です。
- [Suggestion] `evaluate_stage_b(bars_18m, ...)` の引数名変更は小さく見えて呼び出し元影響が出ます。実装時は関数シグネチャ変更だけでなく、ログ・docstring・テスト名まで同時に確認してください。
- [Suggestion] archive schema 影響なしという判断は保留が安全です。bar 数を記録していなくても、Stage B 指標の意味が変わるため、archive metadata に `stage_gate_version` と `bars_stage_b_excludes_stage_a` が残るか確認してください。

**質問への回答**
- Round 1 Critical 4 件は、概念設計としては概ね解消済みです。ただし `n_fold_effective < 3` の扱いだけは report 表示に閉じるなら未解消寄りです。
- B-1 の 6 条件は冗長ですが妥当です。追加で B-0 入力健全性を入れるべきです。
- `n_fold_effective < 3` は、summary まで伝搬するならスコープ内でよいです。report 注記だけなら別 TODO に切り出すべきです。
- 波及範囲は `cross_pair / ii-lite`、archive metadata、`evaluate_stage_b` 呼び出し元、report generator の条件表示が要追加確認です。
- 新たな問題は命名のズレです。`holdout_guard` ではなく stage partition 全体の integrity guard として設計名を揃える方が安全です。