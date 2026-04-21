---
name: zenigame-fx-codex-review
description: scripts/codex exec を使った Codex レビュー・分析の共通呼び出しスキル（zenigame-fx 用。使命・禁止事項の一元管理、セッション管理を含む）
user-invocable: false
---

# Codex CLI レビュー呼び出し規約（zenigame-fx）

Codex へのレビュー・分析依頼はリポジトリ同梱の `scripts/codex`（VSCode 拡張の native codex バイナリを起動するラッパー）経由で実行する。リポジトリルートから相対パスで呼び出すこと。

---

## 使命・禁止事項（全 Codex 呼び出しに自動適用）

以下のテキストを全ての Codex プロンプトの**先頭**に挿入すること。呼び出し元スキルの system 部にはこの内容を重複記載しない。

```
【思考原則 — 全議論に適用】
まず仮説を立てろ。何を検証したいのか、なぜそう考えるのか、どうなれば成功と判断するのかを明確にしてから手を動かせ。

データに真摯に向き合え。数値を見て即座に閾値を弄るな。何が起きているのかを理解し、なぜそうなったのかを考え、どの方向に進むべきかを判断してから手を動かせ。

先人の知恵を探せ。学術論文・実務文献の引用を歓迎する（著者・年・タイトルを明記。記憶が曖昧なら「要確認」と明記）。

機能の名前に立ち返れ。名前はその機能が果たすべき役割を示している。

仕組みが機能していない段階で値を弄るな。設計の方向性が正しいと確認できてから値を弄れ。

因果ループを切断するな。「XはYに影響しない」という主張に出会ったら、間接経路を含む因果ループ全体を追え。

【使命（North Star）— 絶対遵守】
zenigame-fx Alpha Factory の使命は「config/alpha_factory/default.yaml → live_criteria を全て満たす FX イントラデイ戦略ゲノム個体を 1 つ見つけ出すこと」。
Stage C 通過は最低条件。使命達成 = live_criteria の全指標（Sharpe, Total PnL, Max Drawdown, Trade Count 範囲）を同時に満たし、Cross-pair (ii-lite) 評価も通過した個体の出現。
達成後は閾値を引き上げて次の水準を設定する（漸進的目標更新）。

【絶対制約】
- イントラデイ前提（オーバーナイト保有を前提にする設計は避ける）
- ロング・ショート両方向許容（FX の性質上）
- スワップ・スプレッドを fitness に反映（見かけの PnL ではなく純利益）

【禁止事項】
1. A・B・C 評価期間を強い根拠なしに延長する（過学習の隠蔽）
2. 見た目の数値をよくしようとする改善（Sharpe / WR 等の数値操作）
3. GA をハックしてステージを進めようとする（fitness 関数の歪曲等）
4. live_criteria 閾値をいたずらに緩和してステージを飛ばす
5. やたらに複雑な案を提案する（大規模リファクタリング、新フレームワーク導入等）
6. 取引回数を削減して見かけの成績を上げようとする（entry_threshold 過剰引き上げ等）
7. オーバーナイト保有前提の設計（スイングトレード化）
8. ゲノム archive スキーマ変更時の値伝搬漏れ（config → GaConfig → meta → consumer の 4 段接続漏れ）

【ツール使用制限】
コマンド実行・ファイル書き込みは一切行わず、提供されたテキストの分析に集中すること。ファイル読み込みは許可。

【レビュー重点項目 — 転記漏れパターン】
zenigame（姉妹プロジェクト）では「値の転記漏れ・伝搬漏れ・記録漏れ」が繰り返し発生した。zenigame-fx でも以下を重点的にチェックすること:
1. 新規パラメータ/カラム追加時: config 定義→GaConfig 読み込み→genome.meta 注入→consumer 参照の 4 段階が全て接続されているか
2. archive 記録: GENOMES_SCHEMA にフィールド定義→_create_row_template 初期値→collect_stage_* 書き込み→flush 出力の 4 点セット
3. 関数パラメータ: 新規パラメータ追加時に全呼び出し元で引数が渡されているか
4. ログ出力: 新規の値伝搬に対応する logger 出力が追加されているか

【監査・レビュー時の必須チェック — False-positive 再発防止】
以下の discipline を全レビュー・監査で遵守すること。

### C1. Design-first 原則 (code grep より先に docs を読む)
コードの bug / 設計欠陥について claim を出す前に、以下を verify:
- docs/alpha_factory/ 配下の該当セクション（stage-gates.md / clause-architecture.md 等）を Read で確認
- devnotes/ 配下の関連 T-number（関数コメントや git log に出てくる T-xxx）を ls devnotes/ | grep T{xxx} で探して読む
- git log --all -S "識別子" で該当 code の変更履歴を辿る
- 該当機能と並行計算される可能性のある経路を grep で広く検索

### C2. 「X が無い = バグ」禁止ルール
関数 Y の signature / body に識別子 X が無いことを根拠に bug 判定してはならない。別経路での計算を grep で広く検索してから。

### C3. Collider bias 必須チェック（相関分析時）
2 つの変数 A, B の相関を計算して report する場合、Conditioning set と collider の有無を必ず明記。

### C4. 前提明示ルール
Claim / verdict を出す前に、prompt の先頭に「本分析の前提」を bullet でリスト化し、各前提が verified であることを明示。

### C5. 並列 sub-agent の framing 独立性チェック
独立検証のつもりで同じ framing の sub-agent を N 個回しても、それは 1 つの誤読の N 倍冗長実行。

### C6. Fact / Interpretation 分離ルール
「観察された事実 (Facts)」と「解釈・推論 (Interpretations)」を明確に区別する。1 文で mix しない。

### C7. Sample size ガード
n < 30 の相関 claim は明示的に因果解釈を避ける。n < 10 は相関 claim 禁止（observation のみ許可）。

### C8. INCONCLUSIVE を第一級 verdict に
INCONCLUSIVE は CONFIRMED / REJECTED と同格の選択肢。データ不足は正当な結論。

### C9. Falsification-first プロンプト
Round 1 は「この hypothesis の反証を探せ」という指示を先に書く。confirmation bias を強制しない。
```

---

## プロンプト構成ルール

1. **プロンプトはファイルに書き出し、stdin 経由で渡す**（シェル引数では渡さない）
2. Write ツールでプロンプトファイルを作成 → stdin リダイレクトで `scripts/codex exec` に渡す
3. プロンプトの構成順序:

```
{使命・禁止事項・ツール使用制限}  ← 本スキルの正規定義をそのまま挿入
{system 部: 役割・タスク固有の指示}  ← 呼び出し元スキルが定義
---
{user 部: データ・質問}              ← 呼び出し元スキルが定義
```

4. プロンプトファイルの配置先: `{tmp_dir}/.codex-prompt-{label}.md`
   - `label` は呼び出し元が指定する識別子（例: `analysis`, `consensus`, `design-review`, `conceptual-review`, `impl-review`）

---

## One-shot モード

セッションを保持しない単発呼び出し。

```bash
scripts/codex exec --ephemeral --sandbox read-only -m {model} \
  -c 'model_reasoning_effort="{reasoning}"' \
  -o {出力ファイル} - < {tmp_dir}/.codex-prompt-{label}.md
```

---

## セッションモード（合議ループ用）

### Round 1: セッション作成

```bash
scripts/codex exec --sandbox read-only -m {model} \
  -c 'model_reasoning_effort="{reasoning}"' --json \
  -o {出力ファイル}-round-1.md \
  - < {tmp_dir}/.codex-prompt-{label}.md \
  > {tmp_dir}/.codex-session-{label}.jsonl

SESSION_ID=$(head -1 {tmp_dir}/.codex-session-{label}.jsonl \
  | python3 -c "import sys,json; print(json.loads(sys.stdin.read())['thread_id'])")
```

- `--ephemeral` を付けない（セッションを永続化）
- `--json` で JSONL イベントを stdout に出力 → ファイルに保存
- 1 行目の `thread.started` イベントから `thread_id` を抽出

### Round N (N≥2): セッション再開

```bash
scripts/codex exec resume "$SESSION_ID" --json \
  -o {出力ファイル}-round-{N}.md \
  - < {tmp_dir}/.codex-prompt-{label}-round-{N}.md \
  >> {tmp_dir}/.codex-session-{label}.jsonl
```

- `exec resume {SESSION_ID}` で前回セッション再開（文脈維持）
- Round N のプロンプトには対応マトリクス・修正内容のみ記載（使命・禁止事項の再挿入は不要）
- JSONL は追記（`>>`）

### session_label の命名規則

並列実行時の衝突を避けるため、呼び出し元が一意な `label` を指定:
- `consensus` — 改善策合議
- `design-review` — 詳細設計レビュー（alpha-design 2-3/2-4）
- `conceptual-review` — 概念設計レビュー（alpha-design 1-3/1-4）
- `impl-review` — 実装レビュー（implement A-2/A-3）

---

## エラーハンドリング

### 共通（全モード）
- `scripts/codex exec` / `scripts/codex exec resume` が非ゼロ終了コードを返した場合、30 秒待って 1 回リトライ
- 2 回連続失敗時の挙動は呼び出し元スキルの規定に従う

### セッションモード固有
- **Round 1 で失敗**: リトライ時も新規セッション作成（SESSION_ID は更新）
- **Round N (N≥2) で失敗**: 同じ SESSION_ID でリトライ
- **SESSION_ID 取得失敗**（JSONL パースエラー等）: one-shot モードにフォールバック（`--ephemeral` で再実行）
