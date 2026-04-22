## 本分析の前提
- 改訂後 `conceptual-design.md` の提示全文を対象にレビュー。
- Round 2 では提示テキストの整合性検証を主眼とし、実コード照合は未実施。

## Verdict: APPROVED_WITH_COMMENTS

## Facts (読み取った事実)
- Round 1 の 6 指摘に対し、設計文書上の修正は全て明示されている。
- spread 判定は「前バー close spread」に固定され、lookahead 回避方針が定義された。
- session close は warning から `ValueError` に昇格し、pending open drop を先行させる順序が明記された。
- `run_backtest` は据え置き、`primitive_evaluator` は `DslStrategy` bake-in に統一された。
- `swap_cost_per_day_bps` は `holding_cost_per_day_bps` に改名され、proxy であることが明確化された。
- 4 段伝搬契約（`config -> GaConfig -> BacktestConfig -> consumer`）のキーと責務が記述された。

## Interpretations (解釈)
- Round 1 の重大論点（契約矛盾、lookahead、pending open 抜け道、責務不整合）は概念レベルで解消できている。
- North Star を engine 不変条件に昇格した点は妥当。
- 残る論点は「厳密さの度合い」と「将来実装時の伝搬漏れ防止」で、概念設計の致命欠陥ではない。

## 反証を探した結果
- `session close bar で pending open が成立する` 経路は、先頭 drop + 後段 drop の二重抑止で閉じられている。
- `約定時点の未観測 spread を使う` 経路は、前バー close 採用で閉じられている。
- `run_backtest API の責務混線` は解消された。
- 反証として残るのは、`session_close_utc_hours` 空 + 単一日データの即 fail が、短時間検証用途には過剰制約になり得る点（設計方針としては成立）。

## 指摘事項（あれば番号付き）
1. `session_close_utc_hours` が「時（hour）」粒度のみだと、該当“時台”全体で open 抑止になるため強すぎる可能性があります。将来 `HH:MM` 粒度拡張の余地を設計メモに1行残すと安全です。
2. Phase 2I 実装時に旧キー `swap_cost_per_day_bps` からの移行（明示エラー or 互換読込）を決めておかないと、設定ミスが silent になり得ます。
3. 4 段伝搬は文書化済みですが、Phase 2I の受け入れ条件に「4 段すべての実配線テスト」を明記して固定化してください。

## 追加質問への回答
1. 「前バー close spread」採用で lookahead 懸念は実質解消です。事前判断材料としても最も整合的です。
2. 不変条件は North Star 担保として概ね十分です。唯一、短時間単日バックテストを常時禁止する点は運用上の硬さがあるため、意図的ポリシーとして明文化するとよいです。
3. `holding_cost_per_day_bps` 命名は妥当です。将来の実 rollover swap（`rollover_schedule` 等）と並立しやすい設計です。
4. 概念段階で 4 段契約を先に書く責務分離は妥当です。`run-ga-full-rewrite` への委譲先も明確です。