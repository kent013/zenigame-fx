# Detailed Design: port-rename zenigame-* skills 4 件

本詳細設計は `conceptual-design.md` に従い、4 skill (`zenigame-fx-manage-sessions` / `zenigame-fx-clear-cache` / `zenigame-fx-snapshot` / `zenigame-fx-batch-ga`) の SKILL.md を作成する具体的な改修点を定義する。

---

## 共通テンプレート要素

全 4 skill に以下を共通して適用する。

### 1. frontmatter

- `name`: `zenigame-fx-{skill}` 形式
- `description`: zenigame-fx 文脈を明示（例: "zenigame-fx Alpha Factory 用..."）
- `argument-hint`: 元ファイルから踏襲（変更不要なら）
- `user-invocable`: 元ファイルから踏襲

### 2. 思考原則 / 使命 / 禁止事項の取り扱い

| skill | 取り扱い |
|-------|---------|
| zenigame-fx-manage-sessions | 「使命・禁止事項は呼び出し元スキルが必要に応じて `zenigame-fx-codex-review` を参照すること」と一行で言及 |
| zenigame-fx-clear-cache | 同上 |
| zenigame-fx-snapshot | 「使命・禁止事項は `zenigame-fx-codex-review` で定義される内容を適用」 |
| zenigame-fx-batch-ga | 「使命・禁止事項は `zenigame-fx-codex-review` で定義される内容を適用」 |

### 3. 実行前提チェック節（必須・統一テンプレート）

各 SKILL.md に「## 実行前提チェック」節を設け、以下 4 項目を **必ず** 列挙する（粒度を全 skill で統一）:

1. **script** — 必須スクリプト一覧（`scripts/...`）
2. **artifact** — 必須ファイル / ディレクトリ一覧（不在でも skill は abort せず scripts 側に判定を委ねるものは「参照依存」として明示）
3. **related skill** — 必須の関連 skill 一覧（`/zenigame-fx-...`）
4. **未充足時挙動** — 「不足依存を列挙してアボート」「zenigame 側スクリプトをフォールバック参照しない」

**実装ルール**:
- 各 skill の依存マトリクス（概念設計）と完全一致させる（artifact が「参照依存」のみでも明記）
- artifact が「skill が直接チェックしない」場合でも依存一覧には記載し、skill 内で「artifact チェックは scripts/{X}.py の責務」と但し書きを添える

### 4. パス置換マトリクス

| 旧 (zenigame) | 新 (zenigame-fx) |
|--------------|-----------------|
| `docs/alpha-factory/` | `docs/alpha_factory/` |
| `src/trading/alpha_factory/` | `src/alpha_factory/` |
| `scripts/trading/run_alpha_factory.py` | `scripts/alpha_factory/run_ga.py` |
| `scripts/trading/snapshot_manager.py` | `scripts/alpha_factory/snapshot_manager.py` |
| `scripts/trading/extract_batch_metrics.py` | `scripts/alpha_factory/extract_batch_metrics.py` |
| `scripts/trading/compare_batch_runs.py` | `scripts/alpha_factory/compare_batch_runs.py` |
| `~/.local/bin/codex-vscode` | `scripts/codex` |
| `/zenigame-codex-review` | `/zenigame-fx-codex-review` |
| `/zenigame-codex-vscode` | `/zenigame-fx-codex-vscode` |
| `/zenigame-snapshot` | `/zenigame-fx-snapshot` |
| `/zenigame-calibrate-gate` | `/zenigame-fx-calibrate-gate` |
| `/zenigame-run-alpha-factory` | `/zenigame-fx-run-alpha-factory` |
| `/zenigame-run-report` | `/zenigame-fx-run-report` |
| `/zenigame-improve-cycle` | `/zenigame-fx-improve-cycle` |
| `/zenigame-post-run-review` | `/zenigame-fx-post-run-review` |

---

## 1. zenigame-fx-manage-sessions

### 移植元

`/Users/ishitoya/repository/zenigame/.claude/skills/zenigame-manage-sessions/SKILL.md` (90 行)

### frontmatter

```yaml
---
name: zenigame-fx-manage-sessions
description: zenigame-fx Alpha Factory 用 Claude セッション管理（status=一覧表示, cleanup=ゾンビ掃除, complete=完了マーク）
argument-hint: "<action> (status, cleanup, complete)"
user-invocable: true
---
```

### 改修ポイント

| 項目 | 改修前 | 改修後 |
|------|-------|-------|
| skill 名 (本文) | `# zenigame-manage-sessions` | `# zenigame-fx-manage-sessions` |
| 使い方の slash コマンド | `/zenigame-manage-sessions {action}` | `/zenigame-fx-manage-sessions {action}` |
| post-run-review 参照 | `### post-run-review 終了時` | `### zenigame-fx-post-run-review 終了時` |
| improve-cycle 参照 | `### improve-cycle 新セッション起動前` | `### zenigame-fx-improve-cycle 新セッション起動前` |
| improve-cycle ノート | `※ improve-cycleからの呼び出しはユーザー承認不要` | `※ zenigame-fx-improve-cycle からの呼び出しはユーザー承認不要` |
| スクリプトパス | `scripts/cleanup_claude_sessions.py` | 同じ（同名スクリプトを期待）|
| 完了マーカーパス | `.cache/alpha_factory/session-completed/` | 同じ（パス命名上一致）|

### 追加節: 実行前提チェック

skill 冒頭（使い方節の前）に以下を追加:

```markdown
## 実行前提チェック

### script (必須)
- `scripts/cleanup_claude_sessions.py`

### artifact (参照依存・skill では直接チェックしない)
- `.cache/alpha_factory/session-completed/` （`--complete` 実行時に自動生成。事前作成不要）

### related skill
- なし

### 未充足時挙動
script 不在を検出した時点でアボート、不足依存を列挙する。zenigame 側スクリプトをフォールバック参照しない。zenigame-fx は独立コードベースとして扱う。
```

### 追加節: 使命・禁止事項参照

冒頭近くに以下を 1 行追加:

```markdown
> 使命・禁止事項は呼び出し元スキルが必要に応じて `zenigame-fx-codex-review` を参照すること。本スキル自体は運用補助のため North Star を直接背負わない。
```

---

## 2. zenigame-fx-clear-cache

### 移植元

`/Users/ishitoya/repository/zenigame/.claude/skills/zenigame-clear-cache/SKILL.md` (172 行)

### frontmatter

```yaml
---
name: zenigame-fx-clear-cache
description: zenigame-fx 用キャッシュ削除（namespace + 期間指定）
argument-hint: "<namespace> <cache_type> <mode> [date_params]"
user-invocable: true
---
```

### 改修ポイント

| 項目 | 改修前 | 改修後 |
|------|-------|-------|
| ヘッダ | `# Zenigameキャッシュ削除` | `# zenigame-fx キャッシュ削除` |
| スクリプトパス | `scripts/cache_manager.py` | 同じ |
| 使用例（節） | mynavi/wikipedia/nikkei/jquants 4 例 | 削除し、FX 文脈の 4 例（`http`, `alpha_factory/runs`, `alpha_factory/sessions`, `oanda`）に書き換え |

### 新しい使用例（4 件）

```markdown
### 例1: HTTPキャッシュを2026年1月分削除

uv run python scripts/cache_manager.py clear-by-date \
  --namespace http \
  --cache-type http \
  --start-date 2026-01-01 \
  --end-date 2026-01-31

### 例2: alpha_factory/runs キャッシュを2026-01-20以前削除

uv run python scripts/cache_manager.py clear-by-date \
  --namespace alpha_factory/runs \
  --cache-type http \
  --before 2026-01-20

### 例3: alpha_factory/sessions キャッシュを2026-01-20以降削除

uv run python scripts/cache_manager.py clear-by-date \
  --namespace alpha_factory/sessions \
  --cache-type http \
  --after 2026-01-20

### 例4: OANDA HTTPキャッシュを全削除

uv run python scripts/cache_manager.py clear --namespace oanda --cache-type http
uv run python scripts/cache_manager.py clear --namespace oanda --cache-type http --force
```

### 追加節: namespace の固定文

「## 重要ルール」直後に追加:

```markdown
> **namespace の source of truth**: 実 namespace は `scripts/cache_manager.py status` の出力を source of truth とすること。本ドキュメントの使用例は仮例である。
```

### 追加節: 実行前提チェック

skill 冒頭に以下を追加:

```markdown
## 実行前提チェック

### script (必須)
- `scripts/cache_manager.py`

### artifact (参照依存・skill では直接チェックしない)
- `.cache/` （既存。namespace 詳細は `scripts/cache_manager.py status` で確認）

### related skill
- なし

### 未充足時挙動
script 不在を検出した時点でアボート、不足依存を列挙する。zenigame 側スクリプトをフォールバック参照しない。

### 運用補足
namespace は `scripts/cache_manager.py status` の出力を source of truth とする。本ドキュメントの使用例は仮例であり、実 namespace は status コマンドで確認すること。
```

### 追加節: 使命・禁止事項参照

冒頭に 1 行:

```markdown
> 使命・禁止事項は呼び出し元スキルが必要に応じて `zenigame-fx-codex-review` を参照すること。本スキル自体は運用補助のため North Star を直接背負わない。
```

---

## 3. zenigame-fx-snapshot

### 移植元

`/Users/ishitoya/repository/zenigame/.claude/skills/zenigame-snapshot/SKILL.md` (87 行)

### frontmatter

```yaml
---
name: zenigame-fx-snapshot
description: zenigame-fx Alpha Factory の Winners/Candidates/Config スナップショット管理（create/restore/list/delete）
argument-hint: '<create|restore|list|delete> [name] [--description "..."]'
user-invocable: true
---
```

### 改修ポイント

| 項目 | 改修前 | 改修後 |
|------|-------|-------|
| ヘッダ | `# スナップショット管理` | `# zenigame-fx スナップショット管理` |
| 説明 | `Alpha Factoryの ...` | `zenigame-fx Alpha Factory の Winners/Candidates/Config のスナップショット...` |
| スクリプトパス | `scripts/trading/snapshot_manager.py` | `scripts/alpha_factory/snapshot_manager.py` |
| 対象ファイル表 (Winners) | `.cache/alpha_factory/runs/winners_latest.json` | 同じ |
| 対象ファイル表 (Candidates) | `.cache/alpha_factory/runs/candidates_latest.json` | 同じ |
| 対象ファイル表 (Config) | `config/alpha_factory/default.yaml` | 同じ |
| ストレージパス | `.cache/alpha_factory/snapshots/` | 同じ |
| restore 後の注意 | `次のGA実行で意図通りのseed` | 同じ |

### 追加節: 実行前提チェック

skill 冒頭に追加:

```markdown
## 実行前提チェック

### script (必須)
- `scripts/alpha_factory/snapshot_manager.py`

### artifact (参照依存・skill では直接チェックしない)
- `.cache/alpha_factory/runs/winners_latest.json`
- `.cache/alpha_factory/runs/candidates_latest.json`
- `config/alpha_factory/default.yaml`

### related skill
- なし

### 未充足時挙動
本 skill は `scripts/alpha_factory/snapshot_manager.py` の不在を検出した時点でアボートし、不足依存を明示する。

artifact (`winners_latest.json` 等) 不足時の挙動は `scripts/alpha_factory/snapshot_manager.py` 側の責務であり本 skill の範疇外。snapshot_manager.py が config-only モードを許容するか厳格に 3 ファイル必須とするかは scripts 側で判定する。

zenigame 側スクリプトをフォールバック参照しない。
```

### 追加節: 使命・禁止事項参照

```markdown
## 思考原則 / 使命 / 禁止事項

`zenigame-fx-codex-review` で定義される内容を適用する。
```

---

## 4. zenigame-fx-batch-ga

### 移植元

`/Users/ishitoya/repository/zenigame/.claude/skills/zenigame-batch-ga/SKILL.md` (278 行)

### frontmatter

```yaml
---
name: zenigame-fx-batch-ga
description: zenigame-fx Alpha Factory の GA-Only バッチ N 回連続実行（分析BG、クロスラン統計）
argument-hint: '[--n 10] [--calibrate] [--label baseline] [--snapshot-before name] [--run-args "..."] [--resume batch_id]'
user-invocable: true
---
```

### 改修ポイント

| 項目 | 改修前 | 改修後 |
|------|-------|-------|
| トリガー条件文 | `/zenigame-improve-cycle` | `/zenigame-fx-improve-cycle` |
| Phase 0-2 snapshot 呼び出し | `/zenigame-snapshot create` | `/zenigame-fx-snapshot create` |
| Phase 0-3 run_args 取得 | `scripts/alpha_factory/get_latest_run_number.py` | 同じ（既存）|
| Phase 1-2 calibrate 呼び出し | `/zenigame-calibrate-gate {prev_run_id}` | `/zenigame-fx-calibrate-gate {prev_run_id}` |
| Phase 1-3 GA 実行 | `/zenigame-run-alpha-factory` 参照 | `/zenigame-fx-run-alpha-factory` 参照 |
| Phase 1-3 GA 実行スクリプト | `scripts/trading/run_alpha_factory.py` | `scripts/alpha_factory/run_ga.py` |
| Phase 1-4 軽量メトリクス抽出 | `scripts/trading/extract_batch_metrics.py` | `scripts/alpha_factory/extract_batch_metrics.py` |
| Phase 1-5 レポート生成 | `/zenigame-run-report` | `/zenigame-fx-run-report` |
| Phase 2-1 集計レポート | `scripts/trading/compare_batch_runs.py` | `scripts/alpha_factory/compare_batch_runs.py` |
| Before/After ワークフロー (Step 1) | `/zenigame-batch-ga` | `/zenigame-fx-batch-ga` |
| Before/After ワークフロー (Step 5) | `/zenigame-snapshot restore` | `/zenigame-fx-snapshot restore` |
| Before/After Step 4 | `scripts/trading/compare_batch_runs.py` | `scripts/alpha_factory/compare_batch_runs.py` |
| 注意事項: post-run-review | `**post-run-reviewはバッチ中全スキップ**` | `**zenigame-fx-post-run-review はバッチ中全スキップ**` |
| 注意事項: improve-cycle | `**improve-cycleは呼び出さない**` | `**zenigame-fx-improve-cycle は呼び出さない**` |
| ロックファイル | `alpha_factory.lock` | 同じ |
| ストレージパス (.cache/alpha_factory/batch/) | 同じ | 同じ |
| current_run_state.json / batch_state.json 等 | 同じ | 同じ |

### 追加節: 実行前提チェック

skill 冒頭の「トリガー条件」直後に追加:

```markdown
## 実行前提チェック

本スキルは依存 script + 関連 skill の充足が必要。起動時に以下を確認し、不足時は列挙してアボート。

### script (必須)

- `scripts/alpha_factory/run_ga.py`
- `scripts/alpha_factory/extract_batch_metrics.py`
- `scripts/alpha_factory/compare_batch_runs.py`
- `scripts/alpha_factory/get_latest_run_number.py`

各 script は `ls scripts/alpha_factory/{script_name}` でファイル存在を確認。不在なら不足リストに追加。

### artifact (参照依存・skill では直接チェックしない)

- `.cache/alpha_factory/runs/winners_latest.json`
- `.cache/alpha_factory/runs/candidates_latest.json`

これらは Phase 0-3 で run_args 構築時に参照されるが、`run_ga.py` 起動時に存在チェックされる責務。本 skill では事前存在を必須とせず、`run_ga.py` のエラーを尊重する。

### related skill (必須)

- `/zenigame-fx-snapshot`
- `/zenigame-fx-calibrate-gate`
- `/zenigame-fx-run-alpha-factory`
- `/zenigame-fx-run-report`

各 related skill は `ls .claude/skills/{skill_name}/SKILL.md` でファイル存在を確認。不在なら不足リストに追加。

#### executable 状態の判定方針

理想的には各 related skill が `executable=executable` であることを確認したいが、現時点では skill メタデータに executable 状態を保持する仕組みは存在しない。本 skill では暫定的に **「`SKILL.md` ファイルが存在 = 利用可能」** として扱う。

related skill 内で更にその skill の依存が abort される場合、その時点で連鎖的に batch-ga も停止する（ベストエフォート）。将来的に skill メタデータに `executable` フィールドを追加する別 TODO で精緻化する。

### 注意（依存ではない）

- `/zenigame-fx-improve-cycle` は本 skill から呼び出さない（コード凍結が前提）。**依存リストに含めない**
- `/zenigame-fx-post-run-review` はバッチ中スキップ対象であり、依存ではない（スキル不在でも batch-ga は動作可能）

zenigame 側スクリプト・skill をフォールバック参照しない。
```

### 追加節: 使命・禁止事項参照

冒頭に追加:

```markdown
## 思考原則 / 使命 / 禁止事項

`zenigame-fx-codex-review` で定義される内容を適用する。
```

---

## 出力ファイル

実装フェーズ (Phase C) で以下を Write:

1. `.claude/skills/zenigame-fx-manage-sessions/SKILL.md`
2. `.claude/skills/zenigame-fx-clear-cache/SKILL.md`
3. `.claude/skills/zenigame-fx-snapshot/SKILL.md`
4. `.claude/skills/zenigame-fx-batch-ga/SKILL.md`

---

## 検証手順 (Phase D)

```bash
# 1. frontmatter YAML validity
for f in .claude/skills/zenigame-fx-{manage-sessions,clear-cache,snapshot,batch-ga}/SKILL.md; do
  python3 -c "import yaml,sys; doc=open('$f').read().split('---')[1]; yaml.safe_load(doc); print('OK $f')"
done

# 2. 旧パス残存チェック (拡大版)
grep -E "docs/alpha-factory|src/trading|scripts/trading|/zenigame-codex|/zenigame-snapshot|/zenigame-calibrate-gate|/zenigame-run-alpha-factory|/zenigame-run-report|/zenigame-improve-cycle|/zenigame-post-run-review|~/.local/bin/codex-vscode" \
  .claude/skills/zenigame-fx-{manage-sessions,clear-cache,snapshot,batch-ga}/SKILL.md
# → 0 件であること

# 3. 旧 namespace `zenigame-` 全文 grep（zenigame-fx- 以外の hit が 0 件）
# PCRE 負の先読みを使用（grep -P）
grep -P "zenigame-(?!fx-)" .claude/skills/zenigame-fx-{manage-sessions,clear-cache,snapshot,batch-ga}/SKILL.md
# → 0 件であること
#
# grep -P が使えない環境用フォールバック:
# grep -E "zenigame-" .claude/skills/zenigame-fx-{manage-sessions,clear-cache,snapshot,batch-ga}/SKILL.md \
#   | grep -vE "zenigame-fx-"
# → 0 件であること

# 4. description が zenigame-fx 文脈
grep -E "^description:.*(zenigame-fx)" .claude/skills/zenigame-fx-{manage-sessions,clear-cache,snapshot,batch-ga}/SKILL.md
# → 4 件 hit
```

---

## リスク対応

| リスク | 対応 |
|-------|------|
| 旧 namespace `zenigame-` の取りこぼし | 検証手順 3 で全文 grep |
| 実行前提チェック節の記述漏れ | 各 skill にテンプレート文を必ず含める |
| description フォーマット揺れ | 「zenigame-fx」を必ず先頭に含める |
| 既存 zenigame-fx-codex-review との参照スタイル不整合 | 既存 zenigame-fx-implement と同じ「`zenigame-fx-codex-review` で定義される内容を適用」フォーマット |
