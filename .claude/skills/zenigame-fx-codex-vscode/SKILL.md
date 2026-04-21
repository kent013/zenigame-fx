---
name: zenigame-fx-codex-vscode
description: scripts/codex exec を使った OpenAI モデル呼び出しの共通規約（zenigame-fx 用）
user-invocable: false
---

# codex 呼び出し規約（zenigame-fx）

OpenAI モデルへの問い合わせはリポジトリ同梱の `scripts/codex`（VSCode 拡張の native codex バイナリを起動するラッパー）経由で実行する。リポジトリルートから相対パスで呼び出すこと。

---

## 基本コマンド（One-shot）

```bash
scripts/codex exec --ephemeral --sandbox read-only -m {model} \
  -c 'model_reasoning_effort="{reasoning}"' \
  -o {出力ファイル} - < {プロンプトファイル}
```

**必須オプション**:
- `--ephemeral`: セッションファイルを永続化しない
- `--sandbox read-only`: コマンド実行・ファイル書き込みを禁止（ファイル読み込みは許可）
- `-m {model}`: モデルを指定
- `-c 'model_reasoning_effort="{reasoning}"'`: reasoning effort を指定（グローバル設定を上書き）
- `-o {出力ファイル}`: 結果をファイルに保存
- `- < {プロンプトファイル}`: プロンプトを stdin 経由で渡す

---

## 利用可能モデル

| モデル | 用途 |
|--------|------|
| `gpt-5.3-codex` | デフォルト。コード分析・レビュー・技術設計 |
| `gpt-5.4` | 自然言語中心の議論・概念設計 |

---

## Reasoning Effort

`-c 'model_reasoning_effort="{reasoning}"'` で推論の深さを制御する。
`~/.codex/config.toml` のグローバル設定（`model_reasoning_effort`）はモデルとの互換性問題を起こす場合があるため、**常にコマンドラインで明示指定すること**。

| レベル | 対応モデル | 用途 |
|--------|-----------|------|
| `low` | 全モデル | 高速・軽量な応答 |
| `medium` | 全モデル | 議論・分析・ブレスト用（デフォルト推奨） |
| `high` | 全モデル | コードレビュー・安全性判定用 |
| `xhigh` | `gpt-5.3-codex`, `gpt-5.4` のみ | 最大の推論深度 |

---

## プロンプトの渡し方

1. **Write ツール**でプロンプトファイルを作成（`{tmp_dir}/.codex-prompt-{label}.md`）
2. **stdin 経由**で `scripts/codex exec` に渡す（`- < {ファイルパス}`）
3. 結果は `-o` で指定したファイルに出力される
4. **シェル引数でプロンプトを渡してはならない**（エスケープ・長さ制限回避）

---

## セッション管理（文脈保持が必要な場合）

複数ラウンドの会話で文脈を維持する場合は `zenigame-fx-codex-review` スキルのセッションモードを参照。

---

## エラーハンドリング

- `codex-vscode exec` が非ゼロ終了コードを返した場合、30 秒待って 1 回リトライ
- 2 回連続失敗時は呼び出し元の規定に従う
