## 前提（本レビューの前提条件）
- 本レビューは提示された Round 2 文書のみを対象にした**設計レビュー**であり、実装コード・実測ログは未検証です。
- 判定は「文書上の整合性・反証可能性・運用時の実装漏れリスク」に基づきます。
- C1/C4/C6/C8 を適用し、**Fact** と **Interpretation** を分離して記載します。
- 「未定義・未記述」はバグ断定ではなく、原則 **INCONCLUSIVE またはリスク指摘**として扱います。

## Critical（対応必須）
1. **H3 が現状では厳密に falsifiable ではない**
- Facts: H3 は「異なる seed の 3 RUN で**同一 best 個体**の `fsp_idio_ratio` 標準偏差 < 0.1」と定義。
- Interpretation: seed が異なると top 個体が一致しない可能性が高く、「同一 best 個体」の同定規則（genome hash / tie-break / 不成立時の扱い）が未定義のため、判定不能ケースが発生します。
- 必須修正:
  - 同一個体の識別キー（例: `genome_hash`）を明記。
  - 「3 RUN 全てに出現しない場合」の verdict ルール（FAIL か INCONCLUSIVE か）を明記。
  - best の定義指標（fitness のどれか、同点時規則）を固定。

## Warning（対応推奨）
1. **Dispatch matrix が runtime_mode 全体を網羅していない**
- Facts: 表は 4 行だが、`fsp_runtime_mode` には `skipped_disabled` と `skipped_window_too_short` が含まれる。
- Interpretation: 実行状態遷移の完全性が文書上で不足し、想定外分岐が実装時に漏れるリスクがあります。

2. **conditioning set の実装担保が弱い**
- Facts: 「全 bar grid + 全個体」を要求しているが、実行は post-RUN archive 後段。
- Interpretation: archive 側の保存方針次第で母集団欠損が起きうるため、件数整合チェック（評価個体数=FSP対象個体数）が DoD に必要です。

3. **因果時点整合の記述が曖昧**
- Facts: `factor_asof_lag=1` を明記しつつ、説明変数式は `DXY_t - DXY_{t-1}`。
- Interpretation: `strategy_return_t` とどの `factor_return` を突合するか（t-1 なのか t なのか）を明文化しないと、look-ahead 疑義が再発します。

4. **メモリ見積もり前提の不整合**
- Facts: 前提に「30日×120個体」、一方で rolling window は 60 日。
- Interpretation: 見積もり条件が window と一致しておらず、K3（計算コスト）評価の信頼性が弱まります。

5. **転記漏れ防止の4段接続・ログ要件が DoD 化されていない**
- Facts: config 追加はあるが、`config → GaConfig → genome.meta → consumer` と logger 追跡の完了条件が明示されていない。
- Interpretation: 既知の再発パターン（値伝搬漏れ）に対する設計上の防波堤が不足しています。

## Suggestion（任意改善）
1. `runtime_mode` の状態遷移表を 1 枚に統合（入力条件: run形態/enable/data/window）。
2. H2/H3 用に「診断専用固定 fixture-run」を設け、再現試験を本番 RUN と分離。
3. `fsp_conditioning_set_audit`（対象個体数、ゼロPnL日含有率、欠損率）を archive に追記。
4. 4段接続チェックリストを設計書末尾に固定テンプレ化（転記漏れ監査用）。

## Round 1 指摘の解消状況
| 指摘 | 状態 | コメント |
|---|---|---|
| DXY/VIX を M1 補間していた問題 | 解消 | daily 化 + `fsp_sampling_mode="daily"` + `factor_asof_lag=1` を明記。 |
| R² の collider bias | 部分解消 | conditioning set 方針は適切。実装担保（件数監査）が未記述。 |
| success criteria が non-null のみ | 部分解消 | H1/H2/K群は改善。H3 の同一個体定義不足で判定不能リスク。 |
| T016 との dispatch matrix 明文化 | 部分解消 | 4行は有用だが runtime_mode 全状態を網羅していない。 |
| schema 3ケース互換テスト追加 | 解消 | old/new/mixed の3ケースが明記されている。 |
| trade_count 不変条件の明記 | 解消 | 5条件は妥当で、Phase 1 diagnostic-only と整合。 |
| メモリ・計算量見積もり | 部分解消 | 見積もり提示は前進。ただし 30日前提と60日windowの整合が不足。 |

## 総評と判定
**NEEDS_REVISION**

理由: Critical が 1 件（H3 の反証可能性不足）あり、加えて運用実装時に再発しやすい Warning（状態遷移網羅、条件集合担保、時点整合、4段伝搬DoD）が残っています。設計方向性自体は良く、Round 1 の主要論点は大半が改善されています。