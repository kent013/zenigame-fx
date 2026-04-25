---
name: zenigame-fx-alpha-design
description: zenigame-fx Alpha Factory 改善の設計フロー（概念設計→Codex レビュー→詳細設計→Codex レビュー）。設計ファイル生成のみ、TODO 登録は行わない
argument-hint: "<topic> [conceptual_design_path]"
---

# zenigame-fx Alpha Factory 設計フロー

改善アイデアの議論が終わった後、**概念設計 → Codex 合議 → 詳細設計 → Codex 合議** の順で設計を完成させ、TODO への登録を案内する。

## 引数

| 引数 | 必須 | 説明 |
|------|------|------|
| `topic` ($1) | Yes | 設計トピック（ディレクトリ名に使用） |
| `conceptual_design_path` ($2) | No | 既存の概念設計ファイルのパス |

---

## 思考原則

- **まず仮説を立てろ**
- **データに真摯に向き合え**
- **先人の知恵を探せ**（zenigame の設計・学術論文を引用可）
- **機能の名前に立ち返れ**
- **仕組みが機能していない段階で値を弄るな**
- **因果ループを切断するな**

---

## 使命

> **zenigame-fx Alpha Factory の使命は「`config/alpha_factory/default.yaml` → `live_criteria` を全て満たす FX イントラデイ戦略ゲノム個体を 1 つ見つけ出すこと」である。**
>
> Stage C 通過は最低条件。live_criteria 全指標同時充足 + (ii-lite) 通過で使命達成。
> 絶対制約: イントラデイ / ロング・ショート両方向 / スワップ・スプレッド反映。

## 禁止事項

1. A・B・C 評価期間を強い根拠なしに延長する
2. 見た目の数値をよくしようとする改善
3. GA をハックしてステージを進めようとする
4. live_criteria 閾値をいたずらに緩和する
5. やたらに複雑な案を提案する
6. 取引回数を削減して見かけの成績を上げようとする
7. オーバーナイト保有前提の設計

---

## 重要原則

- **全ての成果物は `devnotes/{YYYYMMDD-HHMM-topic}/` に保存**
- **Codex との合議は「全 Critical と Warning が解消されるまで」繰り返す**（最大 5 ラウンド）
- 概念設計レビュー: `gpt-5.4`
- 詳細設計レビュー: `gpt-5.3-codex`

---

## Phase 1: 概念設計

### 1-1. 作業ディレクトリの作成

```bash
TZ=Asia/Tokyo date '+%Y%m%d-%H%M'
```

保存先: `devnotes/{YYYYMMDD-HHMM}-{topic}/`

### 1-2. 概念設計ファイルの準備

**`conceptual_design_path` が指定された場合**: Read → `devnotes/{dir}/conceptual-design.md` にコピー。

**省略時**: 会話内容から以下のフォーマットで作成:

```markdown
# 概念設計: {topic}

## 背景・課題
[なぜこの改善が必要か]

## 改善アイデア
[何をどう変えるか]

## 期待効果
- [live_criteria 達成への貢献]
- [具体的な改善見込み]

## 実装方針（概要）
[どのコンポーネントを、どう変えるか]

## 制約・前提
[既存アーキテクチャとの整合性]

## スコープ外
[今回扱わないこと]
```

### 1-3. Codex による概念設計レビュー

`zenigame-fx-codex-review` のセッションモード。

**model**: `gpt-5.4`
**reasoning**: `medium`
**label**: `conceptual-review`

**system**（使命・禁止事項は zenigame-fx-codex-review で自動挿入）:
```
あなたは zenigame-fx Alpha Factory の改善に関する概念設計レビュアーです。

【レビュー観点】
1. 使命との整合性: live_criteria 達成に本質的に貢献するか
2. 禁止事項違反
3. 実現可能性: 技術的・運用的に実現可能か
4. 期待効果の妥当性（C3 collider bias, C7 sample size を適用）
5. リスク: 重大な副作用・後退の可能性
6. スコープの適切さ
7. メモリ制約: 実行環境は 24GB マシン × 6 ワーカー（1 ワーカー最大約 3GB）
8. 前提検証（C4）: 前提条件が最新コード・設定と一致しているか
9. Design-first 原則（C1）: docs/alpha_factory/ / devnotes/ / git log 参照済みか

【出力形式】
- 全体判定: APPROVED / CHANGES_REQUESTED / INCONCLUSIVE
- 各観点ごとに [Critical] [Warning] [Suggestion] 分類
- Critical/Warning には修正提案を必ず添える
- 日本語で出力

【Fact / Interpretation 分離 (C6)】
観察された事実と解釈を明確に区別せよ。1 文で mix しない。
```

**user**: `## 概念設計\n{conceptual-design.md の内容}`

保存: `devnotes/{dir}/conceptual-review-round-1.md`

### 1-4. 概念設計レビュー合議ループ

- [Critical] 必ず対応
- [Warning] 対応検討
- [Suggestion] 任意
- APPROVED になるまで繰り返し（最大 5 ラウンド）

各ラウンド: `devnotes/{dir}/conceptual-review-round-{N}.md`

### 1-5. ユーザー報告

```
## Phase 1 完了: 概念設計 APPROVED (Round {N})

### 概念設計サマリー
- 改善内容: [1-2 行]
- 期待効果: [箇条書き]
- スコープ: [変更コンポーネント]

→ Phase 2 に進みます（詳細設計 & Codex レビュー）
```

---

## Phase 2: 詳細設計

### 2-1. 関連コードの読み込み

概念設計で示した変更対象ファイルを Read。

### 2-2. 詳細設計書の作成

> **⚠ 波及変更チェック**: Alpha Factory のインターフェース変更（GA 引数、CLI オプション、公開 API）が発生する場合、以下も**変更対象として施策に明示**:
> - `AGENTS.md` — 運用手順・コマンド例
> - `.claude/skills/zenigame-fx-*/SKILL.md` — スキル定義
> - 変更されたインターフェースを参照するドキュメント・設定

詳細設計書テンプレート:

```markdown
# 詳細設計: {topic}

## 使命・制約（絶対遵守）

### zenigame-fx Alpha Factory 使命
live_criteria 全指標同時充足 + (ii-lite) 通過で使命達成。
絶対制約: イントラデイ / ロング・ショート両方向 / スワップ・スプレッド反映。

### 禁止事項
1. A・B・C 評価期間を根拠なしに延長
2. 見た目の数値改善
3. GA ハック
4. live_criteria 緩和
5. 過度な複雑化
6. 取引回数削減で成績を見せる
7. オーバーナイト保有前提

### コーディングルール
- **バグ修正はテストファースト**: 再現最小テスト → FAIL 確認 → 修正 → PASS
- **全施策にテスト必須**（テストなしは実装完了としない）
- **テスト命名**: 振る舞いを説明する汎用的な名前（Run 名・日付・セッション固有の識別子 NG）
- **テスト配置**: 対象モジュールに対応するテストファイル
- **uv 必須**: `uv run pytest tests/alpha_factory/`
- **ruff / mypy 通過**: `uv run ruff check src/ tests/` / `uv run mypy src/`
- Python 3.13 + numpy + pandas 環境

## 概念設計リファレンス

[devnotes/{dir}/conceptual-design.md]

## 施策一覧

| # | 施策名 | 変更ファイル | 優先度 |
|---|--------|------------|--------|

## {施策名}

### 変更箇所
- ファイル: `src/alpha_factory/.../xxx.py` (L100-120)

### 波及変更
- `AGENTS.md`: [変更箇所 or 「なし」]
- `.claude/skills/zenigame-fx-{skill}/SKILL.md`: [変更箇所 or 「なし」]
- `config/alpha_factory/default.yaml`: [変更箇所 or 「なし」]
- `docs/alpha_factory/*.md`: [変更箇所 or 「なし」]

### 現行コード
```python
# 現在の実装
```

### 変更後コード
```python
# 変更後の実装
```

### ルックアヘッドバイアスチェック（primitive 変更時は必須）
- [ ] 未来バー参照なし
- [ ] 当日確定値の先取りなし
- [ ] rolling window 方向が過去方向
- [ ] 正規化にローカル window or rolling 関数を使用
- [ ] バケット / グループ平均が因果的
- [ ] cumsum/accumulate が因果的方向

### パフォーマンスチェック（primitive 変更時は必須）
- [ ] `compute_all_bars()` が実装されている
- [ ] 内側ループ内で NumPy 関数を呼んでいない
- [ ] SoA プロパティ使用
- [ ] 同一配列のキャッシュ

### テスト計画
- [ ] バグ修正なら再現テストを先に書く
- [ ] 既存テスト更新
- [ ] 新規テスト: {テスト名} — {検証内容}

### リスク
- {副作用・後退の可能性}

## 実装モード

| 項目 | 内容 |
|------|------|
| 推奨モード | incremental / standalone |
| 判断根拠 | [理由] |
| 競合リスク | [他施策との干渉] |
| 想定実装時間 | [短/中/長] |
```

保存: `devnotes/{dir}/detailed-design.md`

### 2-3. Codex による詳細設計レビュー

`zenigame-fx-codex-review` のセッションモード。

**model**: `gpt-5.3-codex`
**reasoning**: `high`
**label**: `design-review`

**system**:
```
あなたは経験豊富なクオンツ・システムアーキテクトです。zenigame-fx Alpha Factory 改善の詳細設計をレビューしてください。

（C1-C9 は自動挿入済み。特に C1 Design-first / C2 parallel-path / C3 collider bias / C4 前提検証 / C6 fact-interpretation 分離 / C8 INCONCLUSIVE 第一級扱いを厳守）

【前提環境】
- Python 3.13 + numpy + pandas
- FX イントラデイ戦略の GA 最適化
- DSL ベースの戦略表現: Clause ベース合成（directional × local_gate × weight）
- 実行環境: macOS, 24GB メモリ, 6 ワーカー並列（1 ワーカー最大約 3GB）
- 通貨ペア: AUD_JPY, EUR_JPY, USD_JPY, EUR_USD, USD_CAD, USD_ZAR

【レビュー観点】
1. コードの正確性（ロジックエラー、エッジケース、off-by-one、NaN 伝播）
2. 既存コードとの整合性
3. パフォーマンスへの影響
4. テスト計画の網羅性（各施策にテストが含まれているか必ず確認）
5. 副作用・後退リスク
6. 考慮漏れ
7. 実装モードの妥当性
8. 波及変更の網羅性（AGENTS.md / skill ファイル / config / docs の変更が含まれているか）
9. **ルックアヘッドバイアス**（primitive 変更時は必須）: 未来参照・当日確定値先取り・全期間統計量使用がないか
10. **メモリ制約**: 24GB / 6 ワーカー / 1 ワーカー 3GB に収まるか
11. **パフォーマンス**（primitive 変更時は必須）: compute_all_bars / prefix-sum 活用 / SoA / キャッシュ
12. **前提検証 (C4)**: config 値 / code snippet / parquet 集計が最新 main と一致
13. **並行計算経路の確認 (C2)**: 「X が無いのでバグ」主張時に広く grep した痕跡があるか
14. **相関・予測 claim の collider bias 検証 (C3 / C7)**

【出力形式】
- 各施策ごとに判定: APPROVE / REQUEST_CHANGES / INCONCLUSIVE (C8)
- 指摘は [Critical] [Warning] [Suggestion]
- Critical/Warning には修正案
- 全体判定: APPROVED / CHANGES_REQUESTED / INCONCLUSIVE
- 日本語
```

**user**: `## 詳細設計書\n{detailed-design.md}\n\n## 関連する現行コード\n{変更対象ファイル抜粋}`

保存: `devnotes/{dir}/detailed-review-round-1.md`

### 2-4. 詳細設計レビュー合議ループ

- [Critical] 必ず対応
- [Warning] 対応検討
- APPROVED になるまで繰り返し（最大 5 ラウンド）

各ラウンド: `devnotes/{dir}/detailed-review-round-{N}.md`
最終確定版: `devnotes/{dir}/detailed-design.md`（上書き更新）

### 2-5. 最終確認

- 全施策が使命に寄与するか
- 禁止事項に違反していないか
- コーディングルールが反映されているか

---

## Phase 3: 完了報告 & TODO 登録案内

### 3-1. 最終報告

```
## 設計フロー完了

### 成果物
- 概念設計: devnotes/{dir}/conceptual-design.md
- 詳細設計: devnotes/{dir}/detailed-design.md （APPROVED）

### サマリー
- 改善内容: [1-2 行]
- 変更ファイル: [一覧]
- 推奨実装モード: {incremental / standalone}（理由: [判断根拠]）
```

### 3-2. TODO 登録の案内

詳細設計から以下を推定:
- `{theme}`: `ga-architecture` / `primitives` / `stage-gate` / `cross-pair` / `statistics` / `data-ingest` / `swim-lane` / `skill-port` / `infrastructure` / `general` から最適なもの
- `{summary}`: 30 文字以内
- `{priority}` / `{mode}`: 詳細設計書の「実装モード」セクションから

```
### TODO 登録

以下のコマンドで TODO リストに登録してください:

/zenigame-fx-todo-add "{topic}" {theme} "{summary}" devnotes/{dir} {priority} {mode}
```

**注意**: このスキルは TODO.md を直接変更しない。TODO 登録は `/zenigame-fx-todo-add` の責務。autopilot / improve-cycle 等が自動 TODO 登録を行う場合は、呼び出し元が `/zenigame-fx-todo-add` を呼ぶ。

---

## エラーハンドリング

### Codex API エラー
- 30 秒待って 1 回リトライ
- 2 回連続失敗でユーザーに報告し Codex なしで続行するか確認

### 既存コードの読み込みエラー
- 正しいパスを確認する

---

## 使用例

### 例 1: 議論後に概念設計を新規作成
```
/zenigame-fx-alpha-design clause-architecture-foundation
→ 会話内容から概念設計を作成 → レビュー → 詳細設計
```

### 例 2: 既存の概念設計から詳細設計へ
```
/zenigame-fx-alpha-design clause-arch devnotes/20260421-2100-clause-arch/conceptual-design.md
→ 既存概念設計を読み込んでレビュー → 詳細設計
```
