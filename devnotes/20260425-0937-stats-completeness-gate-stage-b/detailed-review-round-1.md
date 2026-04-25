**前提検証 (C4/C2/C6)**  
**Fact**
- Stage B 本評価の実行経路は実コード上 `LaneManager._run_tier1_generation()` の 1 箇所です（[swim_lane.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/swim_lane.py:487)）。
- `make_wf_folds` の sufficiency 条件は `train + embargo + test > n_unique_dates` です（[walk_forward.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/walk_forward.py:89)）。
- archive schema は現状 28 列前提テストが存在します（[test_archive.py](/Users/ishitoya/repository/zenigame-fx/tests/alpha_factory/test_archive.py:163)）。

**Interpretation**
- 施策の方向性（観測可能性強化・monitor-only追加）は妥当です。
- ただし、実装案のままだと import 循環と既存テスト破綻のリスクが高いです。

1. 施策1 `wf_min_unique_dates` 切り出し: **REQUEST_CHANGES**
- [Critical] 提示コードの `walk_forward.py` で `StageGateConfig` を module import すると循環します（`stage_gate -> walk_forward` 既存依存あり、[stage_gate.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/stage_gate.py:35)）。  
  修正案: `StageGateConfig` 依存を消し、`wf_min_unique_dates(train_days, embargo_days, test_days)` か `Protocol` + `TYPE_CHECKING` に変更。
- [Warning] SSOT二重化で将来ドリフトしやすい。  
  修正案: `fold_len` 算出を共通内部関数化して `make_wf_folds` と helper で共有。

2. 施策2 LaneManager skip-path: **REQUEST_CHANGES**
- [Warning] `n_unique_dates(lane.bars_18m)` を個体ごとに計算すると無駄が大きい。  
  修正案: laneごとに1回だけ計算してループ外で再利用。
- [Warning] underfilled payload の `is_full_total_pnl=0.0`, `is_full_trade_count=0` は archive 側で実測値として上書きされます（[archive.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/archive.py:392)）。  
  修正案: underfilled時は `None` を入れ、未評価を明示。
- [Warning] 既存 `test_swim_lane` の fixture は `bars_18m` が短く、既存の「Stage B呼び出し回数」期待が崩れます（[test_swim_lane.py](/Users/ishitoya/repository/zenigame-fx/tests/alpha_factory/test_swim_lane.py:511)）。  
  修正案: Stage B通過経路を検証するテストでは十分な unique days の fixture を用意。

3. 施策3 Stage B観測メトリクス追加: **APPROVE**
- [Suggestion] `positive_fold_ratio_effective` は foldごとの unavailable mask を明示保持して算出（設計メモ通り）し、順序依存バグを防止。
- [Suggestion] C3/C7対応として docs に「effective 指標は条件付き母集団であり、因果解釈・閾値化は n>=30 の実測後」と明記。

4. 施策4 archive schema拡張: **INCONCLUSIVE**
- [Warning] 設計自体は追加-onlyで妥当。ただし後方互換は「外部 consumer まで含めると未検証」。  
  修正案: 旧 parquet 実ファイルを使う互換テスト（`GenomeArchive.load`→主要スクリプト読取）を1本追加。
- [Warning] 既存の 28 列固定テスト更新が設計に明示されていません。  
  修正案: 既存テストの列数・expected set・nullable setを 31 列へ更新。

5. 施策5 run-report強化: **REQUEST_CHANGES**
- [Warning] multi-label を「先頭reasonのみ集計」は `all_folds_unavailable` などの発生実態を過少計上し得ます。  
  修正案: `primary_reason` 表に加えて `any_reason incidence` も併記。
- [Warning] 旧archive（`stage_b_reason_codes` 無し）時の扱いが不明瞭。  
  修正案: 欠損時は `unknown_reason` カラムに明示集計し、`n_evaluated` との差分を出す。
- [Suggestion] `zenigame-fx-run-report` skill のセクション定義にも新セクションを追記し docs/skill 整合を保つ（[SKILL.md](/Users/ishitoya/repository/zenigame-fx/.claude/skills/zenigame-fx-run-report/SKILL.md)）。

6. 施策6 テスト追加: **REQUEST_CHANGES**
- [Warning] 新規テスト追加だけでは不足。既存回帰テスト更新（schema固定、swim_lane呼出回数）を計画に明示すべき。  
  修正案: 「追加 + 既存修正」のテスト一覧を施策6に追記。
- [Suggestion] 受け入れ条件に `tests/scripts/`（run-report）も含める。

7. 施策7 docs更新: **APPROVE**
- [Suggestion] `terminology.md` の追加項目を「任意」ではなく必須にし、語彙ドリフトを防止。

**全体判定**: **CHANGES_REQUESTED**

補足:
- ルックアヘッドバイアス: 本件は primitive/特徴量変更ではないため新規導入は見当たりません。
- メモリ制約: 3列追加の増分は軽微で 24GB/6worker 制約に実質影響なし。
- 性能: underfilled skip 自体は有効。ただし unique-date計算の位置は最適化必須。