全体判定: **CHANGES_REQUESTED**

前提検証 (C4)  
Fact: 今回の判定は、提示された設計説明テキストを根拠にしたレビューです。  
Fact: 指定ファイル本体（例: [detailed-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260427-1114-ga-parallel-workers/detailed-design.md), [swim_lane.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/swim_lane.py)）の実コード断片はこの場で直接照合できていません。  
Interpretation: C4厳守の観点で、一部は **INCONCLUSIVE** 判定にしています。

1. 決定論性 L1/L2 保証、initializer 一括 broadcast、LaneEvalContext tuple frozen  
判定: **REQUEST_CHANGES**  
Fact: `tuple` 化は浅い不変化であり、内部に `dict/list/numpy.ndarray` があれば可変です。  
Fact: `initializer` は初期状態共有であり、worker 内の後続ミューテーション自体は防ぎません。  
Interpretation: 「構造的に排除」は主張が強すぎます。  
[Critical] worker 内で文脈オブジェクトが変化しうる経路が残ると、L1/L2 の再現性主張が崩れます。  
修正案: `LaneEvalContext` を deep-immutable 化（`MappingProxyType`/tuple化済み構造）し、worker 側で防御的コピー禁止ルールを追加。`random`/`numpy.random` の seed を `(lane_id, generation, population_index)` 由来で固定。worker数 1/2/6 で同一入力の反復一致テストを必須化。

2. `_collect_results_in_population_order` と preflight_underfilled 偽結果生成  
判定: **REQUEST_CHANGES**  
Fact: 現説明のままだと worker が `preflight_underfilled` を知らず、不要な Stage B を実行しうるとされています。  
Interpretation: 選択肢は (a) が妥当で、(b) は無駄計算と例外面の揺らぎを増やします。  
[Critical] preflight確定時に Stage B を実行すると、計算コストだけでなく例外分類・診断ログの一貫性が崩れるリスクがあります。  
修正案: `preflight_underfilled` を `LaneEvalContext` に含め、workerで Stage B を短絡スキップ。偽 `StageResult` 生成は main/worker の二重実装を避け、共通ファクトリ1箇所に集約。

3. graduation 判定と `lane.generation_count` pre/post increment 順序  
判定: **REQUEST_CHANGES**  
Fact: 現行は `mark_graduated` 呼び出し後に generation を increment する運用です。  
Interpretation: 並列化後も「世代番号スナップショット」を固定しないと将来改修で破綻しやすいです。  
[Warning] collect ループ中に可変参照を直接読む設計は後退リスクがあります。  
修正案: ループ前に `generation_index = lane.generation_count` をローカル固定し、評価・graduation・archive 記録すべてこの値を使用。テストで population順と世代番号一致を assert。

4. `pool.map` 入力順保持と `chunksize`  
判定: **APPROVE**  
Fact: `Pool.map` は仕様上、入力順で結果リストを返します。  
Interpretation: 順序保証目的で `chunksize=1` を強制する必要は通常ありません。  
[Suggestion] `chunksize` は決定論性ではなく性能調整として扱い、順序保証は `map` 利用自体で満たすと設計書に明記。

5. `RegistryEvaluator` の pickle 可否  
判定: **INCONCLUSIVE**  
Fact: 将来 `aux_pair_bars` 等に複雑型が入る可能性が提示されています。  
Interpretation: 現在空dict/None前提でも、将来拡張で破綻しうる境界です。  
[Warning] pickle不能型混入の予防策がないと、並列化時に実運用で突然失敗します。  
修正案: `RegistryEvaluator` の picklability テストを追加（空/非空 aux、numpy view 含むケース）。必要なら `__getstate__/__setstate__` で正規化。

6. summary.json per-stage timing（sum/max/mean）  
判定: **APPROVE**  
Fact: worker wall time 集計は並列度依存です。  
Interpretation: L3 非保証方針と整合するため仕様としては許容可能です。  
[Suggestion] 運用価値は `sum`（総計算量）と `max`（ボトルネック）併記が高いです。`mean` 単独は誤読されやすいです。

7. `_classify_exception` 網羅性  
判定: **REQUEST_CHANGES**  
Fact: 現在5分類では pandas/sqlalchemy 系の主要例外が未整理とされています。  
Interpretation: worker責務境界を超えた例外は「出ない想定」だけでは弱いです。  
[Warning] 例外の未分類増加は triage 品質低下を招きます。  
修正案: 「workerで発生しうる例外集合」を設計書で明示し、未分類は `external_io_unexpected` などへ正規化。`pandas.errors.EmptyDataError`、`sqlalchemy.exc.*`、`ArrowInvalid` は「到達不能なら理由と検知テスト」を追加。

8. ルックアヘッドバイアス顕在化リスク（評価順序変更）  
判定: **INCONCLUSIVE**  
Fact: primitive内部未変更でも、評価順序変更で潜在リークが表面化する可能性は理論上あります。  
Interpretation: 否定には比較テストが必要です。  
[Suggestion] 1worker直列と6worker並列で同一genome集合の特徴量・シグナル・PnL一致テストを追加し、順序依存副作用を検出。

9. メモリ制約と性能（24GB / 6 workers）  
判定: **INCONCLUSIVE**  
Fact: 1worker約3GB想定だと worker合計18GB、親プロセス・OS余力は約6GBです。  
Interpretation: pickle転送量次第で圧迫リスクがあります。  
[Warning] initializerで大きな bars/context を複製すると常時メモリ上限に近づきます。  
修正案: 設計書に「1worker RSS上限」「起動時/世代中のピーク測定項目」「max_workers 自動抑制条件」を追加。

10. 波及変更網羅（run_ga/skills/config/docs, 4点セット転記）  
判定: **INCONCLUSIVE**  
Fact: `--max-workers` の skill 透過可否は SKILL.md 実体確認が必要です。  
Interpretation: 現時点では網羅性を断定できません。  
[Suggestion] 変更チェックリストを設計書に固定化: `config定義→GAConfig→consumer`, `SCHEMA→template→collect→flush`, `呼び出し元引数`, `logger出力` を PR テンプレに組み込む。

以上より、主要な反証点（preflight短絡、決定論性主張の強度、世代番号固定、例外正規化）に未解消点があるため **CHANGES_REQUESTED** です。