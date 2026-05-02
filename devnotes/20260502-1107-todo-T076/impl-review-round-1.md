**指摘（falsification-first）**
- [Warning] [rationale.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260502-1001-todo-T076-synthesis-round-22/rationale.md) §7 の完了チェックと本文整合が弱いです。  
事実: §5.4 で「横断確認で実機検証」と記載、ユーザー提示の機械検証結果も PASS ですが、§7 では `13.1-13.8` 系が未チェック。  
解釈: 監査時に「未実施なのか、実施済みだが反映漏れなのか」が判別しづらく、証跡品質が下がります。
- [Suggestion] [synthesis.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260428-2300-cascade-port-debate/synthesis.md) §18.3 Per-run DoD 表の「関連 projection field」列に `SmokeOutcomeClassification.crashed`（projection ではない型）が含まれるため、列名を「関連参照 field/class」などへ寄せると SSOT 1:1 主張がより堅くなります。

**ファイルごと判定**
- [synthesis.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260428-2300-cascade-port-debate/synthesis.md): **APPROVED**  
8箇所改訂、5 anchor（`switching-strategy` / `risk-top-5` / `smoke-dod` / `discussion-history` / `clause-anchor-index`）は diff 上で重複なし・kebab-case ASCII。  
`inconclusive` の fail-closed は §12.4 と §18.3 で整合。dual-path 3+1（3 fail_closed + 1 fail_open/warning）も一貫。
- [rationale.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260502-1001-todo-T076-synthesis-round-22/rationale.md): **APPROVED（Warning あり）**  
要求の 7 章構造は満たしています。Round 21 同型の骨格も維持。上記チェック状態の明確化だけ推奨。

**全体判定**
- **APPROVED**（非ブロッカー Warning/Suggestion のみ）