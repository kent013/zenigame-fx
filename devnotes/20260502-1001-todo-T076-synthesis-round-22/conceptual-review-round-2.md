**全体判定: CHANGES_REQUESTED**

**本分析の前提**
- `Round 2 inline` を検証対象とする。実ファイルの read / grep / git log は実行していない。
- §B の `smoke.py` 抜粋、§C の synthesis Round 21 原文、§E の対応表、§F の切替 checklist は inline 上で確認済み。
- §D は「全文 inline」とされているが、本文中に「中略部分は省略」「詳細は概念設計本体参照」とあり、実際には全文ではない。
- 相関分析・標本数に基づく主張はないため、C3 collider bias / C7 sample size は今回は実質非該当。

**Round 1: 反証 / 弱点**
- [Critical] §E の grep 5 件は、改訂 #1-4 について主に `smoke.py` 側 SSOT の存在確認であり、docs-only PR の本体である `synthesis.md` が正しく改訂されたことを直接検証できない。  
  修正提案: 各改訂に「synthesis 側 grep/diff」と「smoke.py 側 SSOT grep」の 2 系統を持たせる。
- [Critical] §F-1 の「T075 `DUAL_PATH_ENFORCE_TARGETS` 4 経路が fail_closed」は、§B の `docs_runbook` が `parser_failure_mode="fail_open"`, `severity="warning"` である事実と矛盾する。  
  修正提案: 「source/scripts/config は fail_closed、docs_runbook は warning/fail_open」と書き分けるか、設計上 4 経路 fail_closed が必要なら `smoke.py` 側 SSOT を変更対象の別 TODO として明示する。
- [Critical] `inconclusive` を「fail-closed」と扱う意味が曖昧。`unsupported metric_name は inconclusive 必須 (= fail-closed)` は、`inconclusive` が切替をブロックする集約規則まで明記されないと安全側とは言えない。  
  修正提案: §16 / §18.3 / §F に「`inconclusive` は smoke pass として扱わず、Phase 2 切替をブロックする」と明記する。
- [Warning] 「5 改訂候補は論理的に分離不可」はやや強すぎる。#5 anchor 体系は synthesis 内部 SSOT であり、#1-4 の T075 smoke SSOT 同期とは性質が違う。  
  修正提案: 「論理的に分離不可」ではなく「同一 PR で atomic に扱うのが妥当な consistency boundary」と表現する。

**Facts**
- §A-1 の 4 段因果列は、T076 が live_criteria に直接寄与しないことを明示している。
- §A-2 は禁止事項 1-8 への該当性を全件 negation している。
- §A-7 は「実装 → 設計の逆同期」ではなく「T075 詳細設計 SSOT → 実装 → 上位設計 SSOT 復元」と位置付けを補正している。
- §E の grep 対応表では、改訂 #1-4 の検証コマンドが `src/alpha_factory/smoke.py` 側に偏っている。
- §B では `docs_runbook` の parser failure mode が `fail_open`、severity が `warning` と記載されている。

**Interpretations**
- T076 の方向性は妥当で、Phase 2 切替前に synthesis SSOT を復元する位置付けは成立している。
- ただし docs-only PR の検証設計としては、現在の §E では「synthesis が正しく変わったこと」の機械検証が不足している。
- §F の fail-closed 条件は、実装 SSOT と文言が食い違っており、このまま切替 commit の前提にするとレビュー時に再び deadlock する可能性がある。

**観点 1-9**
| 観点 | 判定 | コメント |
|---|---|---|
| 1. 使命との整合性 | [Suggestion] 解消 | §A-1 の rung 2 としての位置付けは妥当。直接探索ではなく切替条件の SSOT 整備として整理できている。 |
| 2. 禁止事項違反 | [Suggestion] 解消 | §A-2 の negation は概ね十分。特に期間延長・criteria 緩和・取引回数削減に触れていない点は明確。 |
| 3. 実現可能性 | [Warning] 部分解消 | docs-only / 切替 commit / 別 TODO の境界は良いが、§F の fail_closed 文言が `smoke.py` 抜粋と矛盾する。 |
| 4. 期待効果 | [Warning] 部分解消 | Facts / Interpretations 分離は良いが、Facts の検証コマンドが synthesis 側を十分に直接検証していない。 |
| 5. リスク | [Critical] 未解消 | `docs_runbook fail_open` と「4 経路 fail_closed」の矛盾、`inconclusive` の blocking semantics 不明確さが残る。 |
| 6. スコープ | [Warning] 部分解消 | anchor 最小化は良いが、「論理的に分離不可」は過剰主張。atomic PR 境界として説明すべき。 |
| 7. メモリ制約 | [Suggestion] 解消 | docs-only なので 24GB / 6 worker 制約への影響はない。 |
| 8. 前提検証 | [Warning] 部分解消 | §B で T075 SSOT は確認可能。ただし §D が全文でないため、実際の conceptual-design 反映は未確認。 |
| 9. Design-first | [Warning] 部分解消 | §B / §C の inline 提示で大部分は満たすが、git log と概念設計全文は未提示。 |

**特殊観点 A-F**
| 観点 | 判定 | コメント |
|---|---|---|
| A. 5 改訂候補の一貫性 | [Warning] 部分解消 | #1-4 は T075 SSOT 同期として一貫。#5 は docs 内部 SSOT なので「同時実施が妥当」までが適切。 |
| B. stable clause anchor | [Suggestion] 解消 | 5 anchor 最小導入、残り 17 章と lint を後続 TODO に切る方針は妥当。 |
| C. retroactive_anchor_grant | [Suggestion] 解消 | 旧 round md 不変保持 + anchor index 経由参照で十分という結論は妥当。既存文書の retroactive 書換禁止も正しい。 |
| D. T075 docstring との同期方向 | [Warning] 部分解消 | §A-7 の補正で概念は解消。ただし実際の `conceptual-design.md` に同じ表現を反映する必要がある。 |
| E. Phase 2 切替前提 | [Critical] 未解消 | dual-path / FAIL_CLOSED / 旧実装削除の 3 軸は良いが、fail_closed 定義と `inconclusive` blocking 条件が不足。 |
| F. grep 5 件の網羅性 | [Critical] 未解消 | smoke.py 側確認だけでは docs-only 改訂の検証にならない。synthesis 側 grep を各改訂に追加すべき。 |

**必要修正**
- §E を 2 段検証に変更する。各改訂 #1-4 について、`synthesis.md` 側の新文言存在・旧文言不在と、`smoke.py` 側 SSOT 存在を別々に検証する。
- §F-1 を `source_import` / `scripts` / `config_yaml` は fail_closed、`docs_runbook` は warning/fail_open と明記する。
- §F-2 に「`inconclusive` は smoke pass ではなく、Phase 2 切替をブロックする」を追加する。
- §A-7 の補正文言を実際の `conceptual-design.md` 本体に反映し、「実装 SSOT への逆同期」という読め方を消す。
- 「5 改訂候補は論理的に分離不可」を「同一 synthesis SSOT の atomic consistency boundary として同時改訂が妥当」に弱める。

上記を直せば、T076 の方向性自体は `APPROVED` に近いです。現状は設計の狙いではなく、検証手順と fail-closed 文言の精度で差し戻しです。