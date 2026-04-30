# T071 概念設計レビュー Round 1

## 0. 本レビューの前提 (C4)
- 本レビューは、提示された T071 概念設計本文のみを対象にした **conceptual-review** です。synthesis 原文そのものは未提示のため、「synthesis に厳密準拠しているか」の確認は、本文内で引用されている §8.7 / §10.1 / §18.2 の要約表現に対して行います。
- Falsification-first に従い、まず「壊れる経路」「転記漏れ」「条件付きでしか成立しない主張」を優先して指摘します。
- C3 に従い、A→B 乖離の `corr(A_proxy_score, B_pooled_score)` は **B 評価が走った個体集合に条件付けられた量** であり、因果的な意味づけは不可です。
- C8 に従い、synthesis 原文不在のため、一部は **INCONCLUSIVE** と明示します。

## 1. 結論
**NEEDS_REVISION**

## 2. Critical
- [C1] **Optional 契約が設計内で自己矛盾しています。**  
  Fact:  
  - `compute_ab_divergence()` は `ABDivergenceMetric` を返し、その中で `corr=None` を許容しています。  
  - 一方で `RunObservabilityReport.ab_divergence` は `ABDivergenceMetric | None` です。  
  - `archive_churn` も §3.4 では「Run 数 < 3 でも使用可能な Run 数で計算」とあり、§4.2 では「1 Run 目は None」とあります。  
  - `session_entropy` も §5.5 では `n_archive_members == 0` なら `entropy=0` を返す一方、タスク要件では「週次未到達なら None」です。  
  Interpretation:  
  「計算不能は `metric.corr=None` で表す」のか、「metric 自体を `None` にする」のかが統一されておらず、Phase 2 caller 契約が曖昧です。これは実装時の分岐漏れを誘発します。

- [C2] **A→B 乖離の conditioning set 記述が矛盾しており、C3 Collider bias の扱いが不十分です。**  
  Fact: §3.2 に「全個体 (= A pass / fail に関わらず)、ただし B 評価が走った個体のみ (= A pass を経由した個体)」とあります。  
  Interpretation:  
  これは両立しません。実際に相関を取るのは **B 評価済み個体のみ** です。したがって「A→B 乖離」は A 通過条件で切られた部分母集団の観測量であり、その前提を API / docstring / report 名称に明示しないと、下流で誤読されます。

- [C3] **`divergence_threshold = 0.30` は synthesis 厳密準拠ではなく、T071 ローカル仮説です。**  
  Fact: 本文自身が「synthesis では明示数値なし、T071 で SSOT 化」と述べています。  
  Interpretation:  
  よって §8.7 / §18.2 への「厳密準拠」を掲げるなら、この値は「synthesis の転記」ではなく「T071 設計判断」です。`restore_threshold = 0.50` と組にした hysteresis 自体は妥当ですが、**strict adherence claim** と混在させてはいけません。

- [C4] **`inflow / per_run_max / warmstart_share` の検証経路が API で閉じていません。**  
  Fact:  
  - §1 / §3.9 では `WarmstartReport + AdmissionReport + config` を用いて動作確認すると読めます。  
  - しかし §5.6 の `extract_warmstart_metrics()` は `WarmstartReport, config` しか受け取りません。  
  Interpretation:  
  `inflow` と `bypass` を含めて synthesis §10.1 の 7 件を揃えるなら、`AdmissionReport` 側の情報をどこで合流するかが未確定です。現状の API だと転記漏れの余地があります。

- [C5] **`session_entropy` の「週次」定義が API に落ちていません。**  
  Fact: §3.6 では「直近 7 Run の ArchiveState または週次累積 archive」とあり、§5.5 の API は `archive_members: Sequence[ArchiveMember]` だけです。  
  Interpretation:  
  この関数だけでは「週次未到達」を判定できません。週次集計の窓管理を caller に寄せるのか、T071 内で履歴を受けるのかを決めないと、`None` 経路も `weekly` 契約も成立しません。

- [C6] **上流 dataclass 依存の壊れ方に対する検出経路が弱すぎます。**  
  Fact: F11 の対処が「cross-PR review で検出」「DoD で grep」です。  
  Interpretation:  
  T065-T068 の field rename / semantic change を人手レビューだけで拾う前提は弱いです。T071 は consumer 集約点なので、ここが壊れると observability 全体が静かに欠損します。少なくとも「T065-T068 先行 merge 必須」は hard dependency として明文化が必要です。

## 3. Warning
- [W1] **単一 module 集約の判断自体は妥当ですが、見積りが楽観的です。**  
  `9 dataclass + 8 関数` と書いていますが、本文に出てくる型は `QForceRecommendation`, `BypassRatioMetric`, `WarmstartConsistencyMetric`, `FailureMetricStage` も含まれており、実際はそれ以上です。LoC 200 を分割基準にするより、`ab / archive / selection / failure` の責務境界で split trigger を置く方が自然です。

- [W2] **q_force 補正は小標本で振れやすいです。**  
  `n<2` だけを除外すると、`n=2..29` でも recommendation が出ます。C7 上、「因果解釈禁止」は守れても、自動補正の入力としては不安定です。少なくとも `n_pairs` を必ず report/log に残す前提は必要です。

- [W3] **session entropy のパターン数記述に不整合があります。**  
  `log2(2^3 - 1) = log2(7)` としつつ「全 8 パターン」と書いています。正規化を今すぐ使わなくても、この不整合は次 PR で転記漏れを生みます。

- [W4] **`consecutive_divergent_runs` の責務分離は良いですが、 recommendation 出力への意味づけが弱いです。**  
  現仕様だと delta 判定自体には連続回数を使っておらず、caller が 1 Run ごとに関数を再適用する前提です。これは成立しますが、docstring でその適用モデルを明示した方が誤用を減らせます。

## 4. Suggestion
- [S1] **Optional 表現を 1 方式に統一してください。**  
  推奨は「metric は常に返し、`status: ok | insufficient_data | not_applicable` を持たせる」か、「計算不能は常に `None`」のどちらかです。混在は避けるべきです。

- [S2] **A→B 乖離は conditioning set を名前で固定してください。**  
  例: `corr_on_b_evaluated_population` のように、A pass 条件付きであることを API 名か field 名で明示すると C3 違反を防げます。

- [S3] **`divergence_threshold=0.30` は “synthesis 転記” ではなく “T071 仮説値” と明記してください。**  
  その上で hysteresis 採用理由を「0.30 で raise、0.50 で restore による振動防止」とだけ簡潔に残すのがよいです。

- [S4] **T065-T068 依存は merge order を hard gate にしてください。**  
  「T065-T068 先行 merge 必須。T071 単独 merge 不可」を Phase 1 申し送りに明示し、mock fixture 前提と本番 import 前提を分離した方が安全です。

## 5. Falsification-first 観察
- `archive_churn` は「1 Run 目でも値を返す」設計と「1 Run 目は None」設計が共存しており、このままだと caller 実装時にどちらかが破られます。
- `session_entropy` は「週次 metric」と言いながら API が単発 snapshot 入力なので、週次未到達 `None` を純関数として判定できません。
- `A→B corr` は B 評価済み個体に条件付けられているため、母集団相関として読むと誤りです。これは C3 上の主要な反証点です。
- `0.30 / 0.50` の hysteresis は振動防止としては筋が良いですが、`0.30` の根拠は synthesis 由来ではありません。strict adherence claim の反証になります。
- `inflow / per_run_max / warmstart_share` は設計目標には入っているものの、API シグネチャに十分反映されていません。ここは転記漏れ候補です。
- field rename 検出を review/grep に依存しており、T065-T068 の schema 変更時に T071 が静かに壊れる経路を完全には塞げていません。

## 6. 強み
- T071 を **pure function + library** に限定し、state 保持と適用責務を caller に分離した判断は良いです。
- `q_force` を T071 で直接 mutate せず、recommendation に留めている点は North Star と禁止事項に整合します。
- T065-T068 からの consumer inventory を先に明示しているのは Design-first として良い進め方です。
- `warn-only` 観測と T073 audit layer の責務分離も妥当です。

## 7. 次 Round への申し送り (NEEDS_REVISION 時のみ)
- Optional 契約を統一すること。特に `ab_divergence / archive_churn / session_entropy` の `None` 条件を 1 箇所で固定すること。
- A→B 乖離の conditioning set を明記し、「A pass / fail に関わらず」の文言を削除すること。
- `divergence_threshold=0.30` を synthesis 準拠と表現しないこと。T071 仮説値として位置付け直すこと。
- `session_entropy` の weekly 窓を caller 管理にするのか、T071 に履歴入力を持たせるのかを決めること。
- `extract_warmstart_metrics()` に `AdmissionReport` を含めるか、別関数で `inflow/per_run_max/warmstart_share` を合流させる設計に直すこと。
- T065-T068 先行 merge 必須を hard dependency として明文化し、field 変更検出の契約を review 以外でも補強すること。