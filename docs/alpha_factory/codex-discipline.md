# Codex Discipline (C1-C9)

## 目的

Codex 合議で適用される C1-C9 discipline の運用ガイド。原則本体の **SSOT は `AGENTS.md` L42-66**。本 doc は転載 + 各原則の運用解説。

## スコープ

- C1-C9 各原則の意図と典型的な発動シーン
- レビュアー / 実装者から見た「いつ呼び出すか」の指針
- Codex 呼び出し前の準備（プロンプト先頭への挿入）

各原則の文言を改変する場合は AGENTS.md 側を更新する（本 doc は追従）。

## 用語リンク

本ドキュメントで使用する用語: なし（原則名 C1-C9 は本 doc 内で完結）

## 主要定義

### C1. Design-first 原則

- **意図**: code grep 先行 → 設計 doc 未読のまま bug claim する false-positive を防ぐ
- **発動**: 「バグかも」と思った瞬間、まず `docs/alpha_factory/` と `devnotes/` を読む
- **失敗例**: grep で「変数が無い」だけでバグ判定 → 別経路で計算されているのを見逃す

### C2. 「X が無い = バグ」禁止ルール

- **意図**: 単一関数のローカル視野での bug 判定を禁ずる
- **発動**: 関数 Y に識別子 X が無いと言う前に、`git log -S "X"` / 全リポジトリ grep で広く検索
- **失敗例**: refactor 後に呼び出し元が改名されているのに気付かず「未使用」と誤判定

### C3. Collider bias 必須チェック

- **意図**: フィルタ連鎖の中間集団での相関を因果解釈しない
- **発動**: 2 変数 A, B の相関を report する時、Conditioning set と collider の有無を必ず明記
- **失敗例**: Stage A 通過個体の中で Sharpe と n_clauses の負相関を見て「複雑度が悪い」と結論 → 実は通過条件が collider

### C4. 前提明示ルール

- **意図**: claim を出す前に前提を bullet で並べ、各前提が verified であることを示す
- **発動**: prompt の先頭で「本分析の前提」を必ずリスト化
- **失敗例**: 暗黙の前提（データ期間・対象 instrument・スプレッドモデル）が違っていて結論ごと無効

### C5. 並列 sub-agent の framing 独立性チェック

- **意図**: 同じ framing の sub-agent N 個 = 1 つの誤読の N 倍冗長実行
- **発動**: 並列レビュー設計時、framing が独立かを確認
- **失敗例**: 同じプロンプトテンプレで 3 並列 → 全員同じ見落とし

### C6. Fact / Interpretation 分離ルール

- **意図**: 観察事実と解釈・推論を 1 文で混ぜない
- **発動**: report / 設計 doc で Facts / Interpretations を別セクションに
- **失敗例**: 「Sharpe が下がった（事実） → 過学習（解釈）が原因」を 1 文で書き、後で別解釈の余地が残らない

### C7. Sample size ガード

- **意図**: 小サンプル相関の因果解釈を防ぐ
- **発動**: `n < 30` は因果解釈を避ける、`n < 10` は相関 claim 自体禁止
- **失敗例**: 5 Run の差分で「mutation_rate を上げると改善」と結論

### C8. INCONCLUSIVE を第一級 verdict に

- **意図**: データ不足を正当な結論として認める
- **発動**: CONFIRMED / REJECTED / INCONCLUSIVE の三値を許容
- **失敗例**: 結論が出ないことを嫌って、無理に CONFIRMED に寄せる

### C9. Falsification-first プロンプト

- **意図**: confirmation bias を強制しない
- **発動**: Round 1 は「この仮説の反証を探せ」から始める
- **失敗例**: 最初から「この設計を承認するか」を聞き、Codex も承認寄りに引きずられる

## いつ呼び出すか

| シーン | 強く意識する原則 |
|--------|----------------|
| 新規概念設計レビュー | C9, C4, C8 |
| 既存コードの監査 | C1, C2, C6 |
| 多通貨 / 多 Run 横断分析 | C3, C5, C7 |
| 改善策合議 | C9, C8, C6 |
| 設計の最終承認段階 | C4, C6, C8 |

## SSOT 参照

| 項目 | 参照元 |
|------|-------|
| C1-C9 の原文 | `AGENTS.md` L42-66 |
| Codex 呼び出し規約 | `.claude/skills/zenigame-fx-codex-review/SKILL.md` |

## 関連ドキュメント

- `AGENTS.md`
- `.claude/skills/zenigame-fx-codex-review/SKILL.md`
- [runbook.md](runbook.md)

## 関連 TODO

- 未着手（C1-C9 運用ガイドの拡充は監査結果に応じて）
