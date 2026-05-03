**全体判定**  
`CHANGES_REQUESTED`

**前提検証 (C4)**
- `verified (提示テキスト内)`: Stage A のみ dual-path、legacy 判定不変、`compute_bucket_for_trade` 再利用、`derive_stage_a_thresholds` 利用方針。
- `unverified (実ファイル未読のため)`: `canonical_metrics` の §6.3/§6.6 の厳密契約、`equity_curve` の時系列粒度、`fail_closed` の既存実装整合。

**指摘（Fact / Interpretation 分離）**
1. `[Critical] business_day_universe を trades 由来で作る設計`
- Fact: `compute_business_day_universe_from_trades` は「約定があった (bucket, day)」のみを universe に入れる設計です。
- Interpretation: 空ブロックを 0.5 中立で数える前提（§6.3）と衝突する可能性が高く、WR 系が活動量依存で上振れします。
- 修正案: universe は `trades` ではなく `評価窓の全バー時刻`（または `評価期間カレンダー`）から構築し、非約定ブロックを必ず含める実装に変更してください。

2. `[Warning] fail-fast 2フラグを常に False`
- Fact: `is_session_close_drop` / `is_negative_equity_drop_open` が step 1 で固定 False です。
- Interpretation: §6.6 の戦略的 fail-fast 観測が欠落し、canonical 側の「差分解釈」が歪みます（特に dual-path diff の原因分解が不能）。
- 修正案: 当面は `unknown` 扱いをログに明示（例: `flags_source=default_false`）し、fail-fast 指標を parity 判定対象から除外。step 2 までに broker 側由来の伝搬 TODO を必須化してください。

3. `[Warning] thresholds の意味空間ずれ`
- Fact: canonical は `derive_stage_a_thresholds(live_criteria, window scaling)`、legacy は既存 `fitness_pen vs threshold` 系です。
- Interpretation: LOG_ONLY では許容可能ですが、数値差を「良し悪し」と解釈すると collider bias を招きます。
- 修正案: dual-path ログに「比較は値一致ではなく方向性監視」と明記し、判定軸を `reason_code`・`pass/fail`・`差分分解` に限定してください。

4. `[Warning] `fail_closed` モードの契約が曖昧`
- Fact: 例示コードの safe wrapper は例外時に常に warning で握りつぶす挙動です。
- Interpretation: config に `fail_closed` を露出すると、将来の誤運用リスクが残ります。
- 修正案: step 1 では config 許容値を `log_only/disabled` に限定するか、`fail_closed` 指定時は `raise` する分岐だけ先に入れて契約を固定してください。

5. `[Warning] テスト計画の不足`
- Fact: 12ケースは基礎変換と fallback をカバーしていますが、§6.3/§6.6/モード契約の境界検証が不足しています。
- Interpretation: 主要リスクに対する反証テストが足りず、C9（falsification-first）に未達です。
- 修正案: 最低4件追加。`universe includes empty blocks`、`flags default_false is logged as unknown`、`fail_closed raises`、`payload/archive schema unchanged`。

6. `[Warning] smoke 5 Run の統計解釈`
- Fact: n=5 想定です。
- Interpretation: C7 観点で因果的主張は不可。性能差や品質差は「傾向観測」止まりです。
- 修正案: 事前に成功基準を「記述統計のみ」に限定（p50/p95 runtime、OOM 0件、legacy 判定変化 0件）。有意差主張は禁止。

7. `[Suggestion] Stage A 限定スコープの境界定義`
- Fact: Stage B/C を別 step に分離する方針です。
- Interpretation: 過度な複雑化回避として妥当です。
- 修正案: step 1.5 と step 2 の境界を明文化してください。step 1.5 は「adapter API 凍結と再利用テスト追加」、step 2 は「B/C 配線のみ（adapter改変禁止）」に固定。

8. `[Suggestion] C1/C2 順守状況`
- Fact: 欠損関数を即バグ扱いせず、`compute_bucket_for_trade` と自前 day index で代替しています。
- Interpretation: C1/C2 には概ね整合しています。
- 修正案: 代替経路の設計根拠を詳細設計に1段落で固定し、将来レビューで誤読されないようにしてください。