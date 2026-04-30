## Verdict
NEEDS_REVISION

## 前提 (C4)
- [Fact] このレビューは、提示された T074 概念設計本文と上位 SSOT 要約のみを事実ソースとして扱っています。今回の制約上、ローカルの `synthesis` 本文・既存コード・git 履歴は直接確認していません。
- [Fact] 上位 SSOT として明示された `T058 / T064 / T071 / T072 / T073 / 既存 swim_lane / archive / cross_pair.py:63` は、T074 では non-touch が前提です。
- [Interpretation] したがって今回は「提示本文の内部整合」と「提示された親条文要約との整合」を中心に、反証優先で見ています。

## Critical (必修正)
- [C1] `GRADUATION_RECENT_RUNS_WITH_MISSION_PASS = 2` は、現状の書き方だと SSOT ではなく設計者都合の仮置き値です。しかも `smoke 後再校正` という文言が入っており、今回の禁止事項である「数値操作」「仕組みが機能していない段階で値を弄るな」に抵触します。T074 Phase 1 では数値確定をやめ、`recent_consecutive_mission_pass_requirement` を未確定論点として残すか、親条文に数値があるならその原文に厳密従属させるべきです。
- [C2] `synthesis §11.1` の「直近 epoch で mission_pass が連続観測」を、T074 が「直近 N Run」に読み替えて SSOT 化している点は危険です。`run_id` 降順 tail N は、同一 `dataset_epoch_id` 上の複数 run で簡単に歪みます。これだと「epoch 連続」は満たしていないのに `ready` になる偽陽性、逆に epoch では満たしているのに `no_recent_mission_pass` になる偽陰性が出ます。ここは `recent_epoch_summaries` ベースに修正しない限り、親条文整合を主張できません。
- [C3] `GraduationBatchInput.anchor_pairs == GRADUATION_ANCHOR_PAIRS` の「順序含む厳密一致」は、集合 SSOT を順序 SSOT にすり替えています。親条文で重要なのは 6 pair の membership であり、tuple order ではないはずです。順序まで invariant 化すると、Phase 4 実装や caller 側 canonicalization で不要な破壊的差分が出ます。`frozenset` 等価を SSOT にし、tuple は決定的反復順序の実装詳細に落とすべきです。

## Warning (要検討、 詳細設計で解消可)
- [W1] `GraduationArchiveSummary.archive_epoch_id_active` は dataclass にあるのに、提示アルゴリズムでは意味を持っていません。使わないなら Phase 1 から外す、使うなら「recent epoch 判定の基準点」として明示しないと、epoch-aware に見えて実際は未使用という設計ノイズになります。
- [W2] `GraduationArchiveSummary` を caller responsibility にする方針自体は純ライブラリ化の観点で妥当です。ただし Phase 2 で `run_ga.py` / report builder / archive reader のどこが SSOT adapter になるのかを決めないと、`n_graduates`・`distinct_dataset_epoch_ids`・`recent mission pass` の集計規則が複数化します。
- [W3] `GraduationTriggerStatus` の 4 値は「業務上の不足状態」としては十分です。一方で `recent_run_summaries` 未ソート、`archive_epoch_id_active` 不整合、epoch 重複 contract violation のような入力異常は status 追加ではなく例外に分けるべきです。ここを曖昧にすると C6 の Fact / Interpretation が崩れます。
- [W4] `MultiPairAggregationSketch(status="not_implemented", 数値 field なし)` は T073 継承として妥当です。ただし将来 field 追加時の互換性戦略は「1.1.0 で optional field 追加」「旧 reader は status のみ見る」を明文化した方が安全です。
- [W5] `GraduationBatchInput` は Phase 1 では caller 不在で死蔵しやすいです。保持するなら「Phase 4 入力契約の先行固定」が目的だと明記し、これを使う invariant test を持たないと存在理由が薄いです。
- [W6] `graduates` を archive snapshot 上の `graduated=True` 件数とみなすのは自然ですが、単調増加量として扱う前提は置かない方がよいです。rollback や再構築があり得るなら、「評価時点 snapshot count」であることを SSOT に入れるべきです。
- [W7] `cross_pair.py:63 ANCHOR_PAIRS` との衝突は、flat tuple と mapping の意味差だけでは少し弱いです。読み手は名前で誤読します。命名分離は追加した方が安全です。
- [W8] collider bias については、T074 trigger 自体に stratified audit を抱え込む必要はありません。ただし「T074 は bias 防止を判定しない、Phase 2 で T071 observability 経由に送る」という責務境界は本文に 1 文で固定した方がよいです。

## Suggestion (改善案)
- [S1] `GraduationRunSummary` を中心に据えるのをやめ、`GraduationEpochSummary(dataset_epoch_id, has_mission_pass, contributing_run_ids)` に置き換える方が安全です。trigger は「直近 N epoch 連続」を判定し、run_id は監査用 payload にだけ残す形がきれいです。
- [S2] `GRADUATION_ANCHOR_PAIRS` は `GRADUATION_BATCH_PAIRS` か `GRADUATION_EVAL_PAIRS` に改名した方がよいです。`cross_pair.ANCHOR_PAIRS` との C2 誤読を減らせます。
- [S3] `archive_epoch_id_active` を残すなら、`recent_epoch_summaries[0].dataset_epoch_id == archive_epoch_id_active` のような入力契約を追加し、違反時は `ValueError` にしてください。
- [S4] Phase 1 で本当に必要なのは `GraduationBatchReport` より `evaluate_graduation_trigger()` の SSOT 固定です。batch 系 dataclass は Phase 4 直前まで遅延させる選択も妥当です。
- [S5] Phase 4 の multi-pair aggregation 候補としては、`worst_pair` と `mean` だけでなく、頑健性を重視するなら min-max / worst-case risk 系、安定性を重視するなら CVaR 系の集約も比較対象に置く価値があります。堅牢最適化・worst-case mean-CVaR・PBO/CSCV は参照価値があります。 ([link.springer.com](https://link.springer.com/article/10.1007/s10957-013-0329-1?utm_source=openai))

## Approved 部分
- Phase 1 を `src/alpha_factory/graduation.py` の純ライブラリ + 単体テストに限定し、既存 `swim_lane / archive / promote_graduates / mark_graduated` を触らない方針は妥当です。
- `early gate ではない / read-only / selection 経路 touch しない` は、T074 の責務切り分けとして良いです。
- `MultiPairAggregationSketch` を T073 同様の scaffold に止め、`NotImplementedError` ではなく status field を返す設計は、T071/T073 との一貫性があります。
- `LANE_PARALLELISM=1` を明示 invariant に置く判断は、§11.2 の scaffold 範囲を逸脱しないために有効です。

## 学術文献 (任意)
- worst-case 集約の理論背景として、robust portfolio / worst-case optimization の整理は Kim, Kim, Fabozzi の survey が入口として良いです。 ([link.springer.com](https://link.springer.com/article/10.1007/s10957-013-0329-1?utm_source=openai))
- 為替を含む国際ポートフォリオで worst-case mean-CVaR を扱う文献は、「通貨要因込みで保守的集約をどう置くか」の参考になります。 ([sciencedirect.com](https://www.sciencedirect.com/science/article/pii/S0377221722002181?utm_source=openai))
- 多数戦略・多数市場での過学習管理という観点では、Bailey らの PBO / CSCV は Phase 4 以降の graduation 判定品質管理に相性が良いです。 ([papers.ssrn.com](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2326253&utm_source=openai))
- FX で複数通貨ペア・多数ルールを横断評価した研究として、30 通貨・21,000 超ルールの大規模検証や、22 通貨・113,148 ルールで data-snooping を補正した研究があります。single-pair ではなく cross-pair 頑健性を見る設計動機として使えます。 ([sciencedirect.com](https://www.sciencedirect.com/science/article/abs/pii/S0022199616300472?utm_source=openai))

## 総評
現案は、「既存 lane を壊さず、Phase 1 を純ライブラリ scaffold に閉じる」という大枠は正しいです。問題は trigger SSOT の最重要部分で、親条文の「直近 epoch」を「直近 run」に読み替えた点と、`=2` を設計判断で先に埋めた点です。ここは falsification-first で見ると、最初に壊れる場所です。

したがって結論は `NEEDS_REVISION` です。修正方針は大きくありません。`run` 基準を `epoch` 基準に戻すこと、`2` を SSOT から外すこと、anchor pair の順序依存 invariant を弱めること。この3点を直せば、T074 は scaffold としてかなり筋が良くなります。