# T071 概念設計レビュー Round 2

## 0. 本レビューの前提 (C4)
- 提示された Round 2 改訂本文のみをレビュー対象とする。
- synthesis 原文は未提示のため、本文内の synthesis 引用・確定値記述を前提に準拠性を確認する。
- Round 1 の Critical 6 件が PR ブロッカーとして解消されたかを最優先で見る。
- C3 に従い、A→B corr は B 評価対象個体集合に条件付けられた観測量であり、母集団相関や因果としては扱わない。
- C8 に従い、synthesis 原文で未確認の値は「T071 仮説値」として扱われていれば許容する。

## 1. 結論
**APPROVED**

Round 1 の Critical 6 件は、概念設計レベルでは解消されています。残る指摘は実装前の整合性修正であり、PR ブロッカーではありません。

## 2. Critical
なし。

## 3. Warning
- [W1] §3.1 / §4.1 / §6.2 に旧名が残っています。`compute_ab_divergence`, `extract_warmstart_metrics`, `WarmstartConsistencyMetric` は Round 2 の新名 `compute_ab_divergence_on_b_evaluated`, `extract_inflow_consistency`, `InflowConsistencyMetric` に統一してください。
- [W2] §7 F1 / F2 / F10 が旧 Optional 契約のままです。`corr=None` や `None field` ではなく、`status="insufficient_data"`, `status="zero_variance"`, metric 常時存在に修正してください。
- [W3] q_force の「+0.02 / 連続乖離 Run」という synthesis 表現と「consecutive_divergent_runs は delta 判定に使わない」の関係は、実装時に誤読されやすいです。Round 2 の解釈では「連続回数で増分を乗算しない。1 Run ごとに最大 +0.02」と明文化されているため許容します。
- [W4] `ArchiveChurnMetric` の `total_admissions=0` は `churn_rate=0` sentinel ですが、`status` は `ok` になり得ます。必要なら `zero_admissions` status を追加する余地がありますが、観測用途なら現設計でもブロッカーではありません。

## 4. Suggestion
- [S1] `status` field は各 metric ごとに Literal を定義し、`corr=0 sentinel` と有効な `corr=0` を必ず `status` で区別してください。
- [S2] `InflowConsistencyMetric` の `config: WarmstartConfig | InflowConfig` は実装時に曖昧になりやすいため、必要 field を持つ専用 config dataclass か Protocol を検討してください。
- [S3] `n_pairs` は q_force recommendation log にも含め、低サンプル時の過信を避ける運用にしてください。

## 5. Falsification-first 観察
- Round 1 [C1] の Optional 自己矛盾は、metric 常時存在 + `status` 方式に統一され、PR ブロッカーではなくなっています。
- Round 1 [C2] の conditioning 矛盾は、関数名・docstring・解釈範囲で B 評価対象集合に固定され、C3 collider bias への配慮が入っています。
- Round 1 [C3] の threshold 問題は、synthesis 確定値と T071 仮説値が分離され、厳密準拠 claim の混同が解消されています。
- Round 1 [C4] の inflow API 未閉鎖は、`WarmstartReport + AdmissionReport + config` を受ける `extract_inflow_consistency` に統合され、経路が閉じています。
- Round 1 [C5] の weekly entropy 問題は、caller が `n_runs_aggregated` を渡し、T071 が `status` 判定する契約になり解消されています。
- Round 1 [C6] の上流依存検出は、T065-T068 先行 merge 必須・単独 merge 不可・commit hash 記載に格上げされ、概念設計として十分です。

## 6. 強み
- 観測 layer を pure function に限定し、q_force 適用・履歴保持・state 永続化を caller に分離している点が良いです。
- `status` 方式への統一により、Phase 2 caller の契約が明確になりました。
- synthesis 確定値と T071 仮説値の分離により、見た目の数値調整ではなく検証可能な仮説として扱えています。
- A→B corr の conditioning set を関数名に入れたことで、将来の誤読リスクが大きく下がっています。