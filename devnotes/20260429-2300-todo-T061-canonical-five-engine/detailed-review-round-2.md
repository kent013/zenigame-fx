[VERDICT] CHANGES_REQUESTED

[Critical] (修正必須)
- **WR neutral 0.5 が top-level 経路で実質無効**
  - Fact: `evaluate_canonical_five` は `compute_session_blocks(trades)` を使い、同関数は `trade>=1` の block しか生成しない設計です。
  - Interpretation: `compute_session_block_win_rate_worst` の「trade=0 -> 0.5 neutral」規約が本流で適用されず、synthesis §6.3 の厳密一致を満たしません。`Period×Session` の空blockを明示入力する契約に直す必要があります。
- **「top-level は raw exception を伝播しない」契約が設計上未保証**
  - Fact: `_validate_utc_aware` は基底 `CanonicalMetricsInputError` を直接送出し、`provider` 側例外の reason code 変換規約も未定義です。
  - Interpretation: `evaluate_canonical_five` の deterministic 契約（常に `gate_pass=False + reason_codes`）が破れる経路が残っています。例外→reason code の網羅マップと catch 境界を明文化すべきです。
- **`compute_max_dd` の数値安定性と値域契約に矛盾**
  - Fact: 設計は「equity は正でなくても可」としつつ、`max_dd = 1 - equity/running_max` をそのまま使い「0<=max_dd<=1」と記述しています。
  - Interpretation: `running_max==0` でゼロ除算、または負 equity 混在で `max_dd>1` が発生し得ます。分母floor/特例処理/値域定義のいずれかを固定してください。

[Warning] (修正推奨)
- **例外階層の一貫性不足**
  - Fact: `TradeRecordInvalidError`/`BarEquityInvalidError` を定義している一方、UTC違反は基底例外で返る設計です。
  - Interpretation: 呼出側の reason code 分岐が不安定になります。`__post_init__` では派生例外に正規化した方が安全です。
- **計算量説明が実装想定と不一致**
  - Fact: 本文は `O(N+B+3*Q)` と記載しつつ、HAC自己共分散ループ前提です。
  - Interpretation: 厳密には bucketごと `O(n_b*Q)`（合計 `O(N + Σ n_b*Q + B)`）です。性能見積の根拠を修正してください。
- **DoD記述の不整合**
  - Fact: 「Enum + 4 dataclass」とあるが、設計上は `TradeRecord/BarEquityPoint/BarEquitySeries/SessionBlockSummary/CanonicalFiveThresholds/InvariantFlags/CanonicalFiveResult` の複数dataclassです。
  - Interpretation: レビュー/実装完了判定で誤解を生みます。
- **C2 grep DoD の検出漏れリスク**
  - Fact: 4段階は有効ですが、import path揺れ・文字列経由動的参照は取りこぼします。
  - Interpretation: T060同型漏れ予防としては補助的で、最終的に runtime wiring の smoke を1本追加した方が堅いです。
- **学術引用の粒度不足**
  - Fact: `Newey-West 1987` への言及はあるが、著者・年・タイトルの明記が不十分です。
  - Interpretation: AGENTS方針（著者・年・タイトル明記）に合わせ、正式書誌を追記してください。

[Suggestion] (任意改善)
- `infeasible_reason_codes` を文字列直書きではなく `StrEnum` 化し、prefix規約を型で強制する。
- `evaluate_canonical_five` に「例外注入テスト（providerが例外送出）」を追加し、no-raise契約を固定する。
- `compute_max_dd` について「許容値域（>1許容か、clipするか）」を docs と test 名に明記して将来の解釈揺れを防ぐ。