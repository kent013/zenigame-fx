**全体判定: CHANGES_REQUESTED**

Round 2 の Critical 2 件は概念上は解消しています。設計の骨格は APPROVE 可能な水準に近いですが、Round 3 本文内に旧名残りと optional holdout の契約矛盾があり、このまま詳細設計へ進むと実装時に迷いが出ます。

**本分析の前提**
- 提供テキストのみを根拠にしています。
- ファイル読み込み・grep・git log・実コード確認は行っていません。
- C1 の一次確認は詳細設計フェーズの未完了条件として残ります。

**Facts**
- モジュール名は `stage_partition_guard.py`、例外は `StagePartitionLeakError` / `StagePartitionInputError` に変更されています。
- `stage_b_statistical_inconclusive` は `summary.json` へ伝搬する設計に変更されています。
- B-0 / B-1 / B-2 / B-3 / B-4 に分割され、入力健全性・partition 整合性・将来変更点・sampling pool 除外契約が分離されています。
- ただし成功条件 2 に旧名 `HoldoutLeakError` が残っています。

**Interpretations**
- Round 2 の主要懸念はほぼ解消済みです。
- B-0/B-1 の段階構成は理解しやすく、冗長ではありません。
- 残課題は設計思想ではなく、契約の明文化不足と本文内の不整合です。

**Critical**
- [Critical] B-0 で `holdout` を optional にする余地を残していますが、B-1 は `min(stage_holdout.bar_time)` を必須にしています。これは契約矛盾です。
  - 修正提案: 本 TODO では `holdout` を必須にするか、`validate_stage_partition(bundle, require_holdout: bool = True)` のように optional 時の検証条件を明文化してください。Alpha Factory の Stage C/holdout 保護を重視するなら、今回は必須に寄せる方が安全です。
- [Critical] 成功条件 2 に `HoldoutLeakError` が残っています。Round 3 の命名変更と矛盾しています。
  - 修正提案: `StagePartitionLeakError` に置換してください。テスト計画の「holdout 保護 guard」も「stage partition guard」に揃えるべきです。

**Warning**
- [Warning] `stage_b_statistical_inconclusive` の配置粒度がまだ曖昧です。run-level summary なのか、Stage B result block なのか、candidate/genome 単位なのかを明確にする必要があります。
  - 修正提案: `n_fold_effective` と同じ階層に置く、と明記してください。複数 candidate を扱うなら candidate ごとに必要です。
- [Warning] archive parquet schema に新規列を追加しない判断は概ね妥当ですが、「summary 側の bool フラグを正本」とすると archive 単体 consumer が誤読する余地が残ります。
  - 修正提案: archive consumer が `n_fold_effective` から同等判定できる契約を docs に明記してください。可能なら archive metadata に `bars_stage_b_excludes_stage_a` と `stage_gate_version` は必ず残す方針にしてください。
- [Warning] `bars_18m` rename は良い変更ですが、スコープがやや膨らみます。
  - 修正提案: 変更対象を `evaluate_stage_b` 周辺の semantic rename に限定し、無関係な historical naming cleanup は別 TODO に逃がせるようにしてください。

**Suggestion**
- [Suggestion] `StagePartitionLeakError` / `StagePartitionInputError` の 2 例外分離は妥当です。入力データ不正と partition contamination は復旧方針が違うため、attribute 付き 1 例外より運用ログで見分けやすいです。
- [Suggestion] B-3 の将来確率化への留保は適切です。実装時は境界条件と集合条件を別 helper に分けると、将来 `chronological=False` に切り替えやすくなります。
- [Suggestion] cross-pair / ii-lite は「確認必須」まで書けているので概念設計としては十分です。詳細設計で `stage_b` / `n_fold_effective` / `bars_stage_b` / `summary` の参照経路を grep 対象に含めればよいです。

**質問への回答**
- Round 2 Critical 2 件は実質解消済みです。ただし旧名残りと holdout optional 矛盾は新たな Critical として修正が必要です。
- B-0〜B-4 の構成は妥当です。むしろ責務分離が明確になっています。
- 2 例外分離は妥当です。実装では共通基底 `StagePartitionError` を置くと catch しやすくなります。
- 波及範囲は概ね足りています。追加で `summary` の階層、archive 単体 consumer、`bars_18m` の fixture/test 名が確認対象です。
- 概念設計は APPROVE 直前です。上記 2 Critical を本文修正すれば、詳細設計フェーズへ進めてよい水準です。