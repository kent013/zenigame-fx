## Verdict
NEEDS_REVISION

## 前提 (C4)
- 提供された概念設計本文と上位 SSOT 要約のみを根拠にレビューした。実コード・設計書原文・git 履歴は本レビューでは未確認なので、実装既存契約との最終一致は一部 `INCONCLUSIVE`。
- 上位 SSOT として、T058/T070/T071/T072、既存 `deflated_sharpe_ratio`、既存 archive `dsr` field の説明はユーザー提示どおり正しいと仮定する。
- Round 1 falsification-first として、「成立しうる設計」ではなく「このままでは監査値の意味が崩れる箇所」を優先して挙げる。
- C6 に従い、各指摘は `Fact` と `Interpretation` を分けて書く。

## Critical (必修正)
- [C1] Fact: `§0.4` は「RunObservabilityReport 拡張で archive / log / report に出力」と書いている一方、`§11 Phase 1` は「runtime 未組込」「T071 RunObservabilityReport 拡張なし」と書いている。Interpretation: Phase 1 の deliverable 境界が自己矛盾している。T073 PR を「純ライブラリ PR」か「observability 配線まで含む PR」かに一本化しないと、レビュー観点とテスト範囲が確定しない。
- [C2] Fact: 既存 DSR 実装を再利用しつつ、入力 SR を「v1 bar-level annualized Sharpe」から「v2 SessionBlock の非年率 SR」へ切り替える提案なのに、`mean_sr_trials=0 / std_sr_trials=1` を固定している。DSR は multiple testing と non-normality を補正する指標だが、その補正は観測 SR と trial 分布仮定が同じスケールで定義されていることを前提に読むべき指標である。Interpretation: 数式を変えなくても、入力尺度と null 尺度を同時に変えていないので、`0/1` 固定は未検証仮定になっている。Phase 1 の SSOT として `mean_sr_trials/std_sr_trials` の由来を固定しない限り、`audit_calc_version="v2"` は意味論的に未完成。 ([papers.ssrn.com](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2460551))
- [C3] Fact: `n_trials` の候補が `archive cardinality / Stage A 通過数 / 全 GA 評価数` のまま open question に残っている。DSR は trial 数を通じて selection bias を補正するので、どの集合を「試した戦略群」とみなすかが値そのものを動かす。Interpretation: ここを詳細設計送りにしてはいけない。audit が early gate でなくても、multiple-testing correction の母集合は SSOT で一意である必要がある。Round 1 の時点では、最も保守的で使命に整合するのは「その run で performance selection の対象になり得た全評価 genome」を第一候補に置くこと。archive や Stage A 通過数を使うと補正対象を survivor に条件付けて過少補正になる。 ([papers.ssrn.com](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2460551))
- [C4] Fact: `§0.2` では DSR 入力源を `pnl_net 列 (open_minutes > 0 / expected_bar_count > 0)` と書いているが、`§5` と `§6` の API/擬似コードは `open_minutes > 0` しか使っていない。Interpretation: T072 継承条件が invariant 化されていない。`expected_bar_count > 0` が broker/session 定義上の必須条件なら I11 に入れるべきで、不要なら TL;DR から削るべき。
- [C5] Fact: `RunAuditReport.per_genome_dsr` が `tuple[AuditDSRMetric, ...]` で、genome identifier を保持していない。Interpretation: archive/report/log へ配線した瞬間に「どの metric がどの genome のものか」を SSOT として復元できない。`per_genome` は `Mapping[genome_id, AuditDSRMetric]` か、`genome_id` を内包した record 型であるべき。
- [C6] Fact: `status!="ok"` の sentinel を `Decimal(NaN)` 想定で表現している。Interpretation: `Decimal("NaN")` は等値性・順序性・hash の扱いが素直でなく、`frozen=True` dataclass の比較・スナップショット・JSON round-trip の SSOT を壊しやすい。T071 の「status field 方式」は `None` 排除だけでなく、状態遷移の可観測性を安定化する意図のはずで、NaN sentinel は逆行している。
- [C7] Fact: `input_non_finite` を、`variance < 1e-20` と `deflated_sharpe_ratio` の `ValueError` をまとめて受ける status にしている。Interpretation: 非有限入力と退化分散は観察事実として別物であり、同じ status に潰すと observability が落ちる。少なくとも `degenerate_variance` は分けるべき。
- [C8] Fact: `per_genome_session_blocks` の source が未確定で、候補に「archive admission 時保存 / Run 末尾再計算」が並んでいる。Interpretation: T070 を SSOT とするなら、`SessionBlock` は `BacktestResult.session_blocks transport` から運ぶのか、別保存するのかを T073 概念設計で先に固定しないと、Phase 2 配線時に sessionization version / cost model version の二重計算ドリフトが起きる。ここは open question ではなく transport 契約の問題。

## Warning (要検討、 詳細設計で解消可)
- [W1] `AUDIT_DSR_MIN_OBSERVATIONS = 30` は C7 の governance threshold としては理解できるが、DSR 原著から直接出る閾値ではない。`30` を採るなら「統計理論上の必要条件」ではなく「運用上の最低観測数」と明記した方がよい。 ([papers.ssrn.com](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2460551))
- [W2] `archive.dsr` を T073 では触らない方針自体は妥当だが、Phase 2 で同名 field を v2 意味に上書きすると履歴比較が壊れる。`dsr_v1`/`dsr_v2` 併存、または `dsr` + `sharpe_calc_version` の厳格運用のどちらかを先に決めた方がよい。
- [W3] `N=1` のときに PSR fallback を入れる案は、親 SSOT の「DSR 先行実装」と既存 `n_trials<2` invariant を濁す。Round 1 では fallback を足さず、`insufficient_data` か `insufficient_trials` に倒す方が安全。
- [W4] collider bias 規範は方向として正しいが、「stratified audit を caller が担う」だけでは弱い。最低でも stratification key の候補を 1 行でも固定しないと、後段実装で `holiday_markets` 単独 drop と実質同じことが起こりうる。
- [W5] PBO/SPA scaffold は「未実装タグ」の要求に合っているが、Phase 2 以降で必要になる入力が未宣言。特に PBO は CSCV 前提の loss/performance matrix、SPA は benchmark 対比の loss differential と依存系列 bootstrap 設計が必要になるので、field 追加余地を見込んだ schema comment が欲しい。PBO は CSCV による backtest overfitting 推定として提案され、SPA は Reality Check より強力で irrelevant alternatives に鈍感になるよう設計されている。 ([papers.ssrn.com](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2326253))

## Suggestion (改善案)
- [S1] `RunAuditReport` は `per_genome: tuple[AuditGenomeRecord, ...]` にし、`AuditGenomeRecord` に `genome_id`, `archive_role`, `source_stage`, `dsr_metric` を持たせる。T058 と join しやすくなる。
- [S2] `AuditNullModel` もしくは `AuditRunContext` を分離し、`n_trials`, `mean_sr_trials`, `std_sr_trials`, `trial_source`, `null_model_kind` をまとめて provenance 付きで持たせる。DSR 値そのものより先に「どういう null で計算したか」を SSOT 化する。
- [S3] status は最低でも `ok / insufficient_data / insufficient_trials / degenerate_variance / input_non_finite / not_implemented` に分ける。`status_reason` を文字列で追加してもよい。
- [S4] Phase 1 は「`audit.py` と unit test のみ、runtime surface なし」に絞るなら、TL;DR から report/archive/log 出力文言を外す。逆に observability まで入れるなら Phase 1 のテスト計画を integration 含みに書き換える。
- [S5] `§10.2` の synthesis 文言は、次回改訂で「audit は early gate ではない。ただし DSR 入力は v2 SessionBlock cascade port を使う」と 1 行追記すると、v1/v2 混線を防げる。
- [S6] scaffold metric の sentinel 値はやめ、`status="not_implemented"` のとき値フィールドを `Decimal("0")` 固定にして「解釈禁止」を invariant で縛る方が、NaN より運用が安定する。

## Approved 部分
- `audit (DSR/PBO/SPA) は archive / report 層であり、early gate ではない` という大方針は synthesis SSOT に整合している。
- PBO/SPA を Phase 1 で schema scaffold のみに留め、`NotImplementedError` を投げない方針は T071 の status-field 方式と整合している。
- `holiday_markets` 単独 drop を禁止し、collider bias を audit 層でも明示した点は正しい。
- T073 PR で既存 archive `dsr` field を即時に触らない分離方針は、v1/v2 semantic drift を避ける意味で慎重でよい。

## 学術文献 (任意)
- Bailey & López de Prado (2014): DSR は multiple testing 下の selection bias と non-normal returns を補正する目的で導入されている。したがって `n_trials` と null 分布パラメータは「後で決める補助情報」ではなく、指標の意味そのもの。 ([papers.ssrn.com](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2460551))
- Bailey, Borwein, López de Prado, Zhu (2015): PBO は CSCV によって推定する枠組みとして提案されている。scaffold 段階でも、将来必要な単位が「単一スカラー」ではなく「分割可能な performance matrix」である点を意識した schema にしておくべき。 ([papers.ssrn.com](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2326253))
- Hansen (2005): SPA は White の Reality Check より power が高く、poor / irrelevant alternatives への感度を下げる方向の検定として位置付けられている。将来実装時は dependent bootstrap 設計が論点になり、Politis & White (2004) は dependent bootstrap 法と block size 推定の整理として参照価値が高い。 ([papers.ssrn.com](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=264569&utm_source=openai))

## 総評
設計の方向性自体は悪くありません。特に「T073 は新規数式導入ではなく、既存 DSR を v2 audit 文脈へ載せ替える」「PBO/SPA は未実装 scaffold に留める」「early gate を触らない」という骨格は、上位 SSOT にかなり忠実です。

ただし、このままでは DSR の値が何を意味するのかが固定されていません。致命点は `n_trials` と null 仮定、そして v1 annualized SR から v2 non-annualized session-block SR へ移るときの尺度整合です。ここを曖昧にしたまま実装へ進むと、コードは動いても audit 値が監査不能になります。Round 1 の結論は「却下ではないが、SSOT を 3 点だけ先に閉じる必要がある」です。具体的には、`n_trials の母集合`、`null model の provenance`、`RunAuditReport の keying` を概念設計で確定してから詳細設計に進むべきです。