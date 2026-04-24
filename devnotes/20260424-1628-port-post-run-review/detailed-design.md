# 詳細設計: post-run-review skill port (T026)

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
- **本 TODO は md only**: skill md ファイル + ドキュメント md のみ。Python / scripts / tests への変更なし
- ruff / mypy / pytest 実行不要 (本 TODO 範囲ではコード変更ゼロ)
- 834 passed / 1 skip baseline 維持を成果物で保証

## 概念設計リファレンス

[devnotes/20260424-1628-port-post-run-review/conceptual-design.md](./conceptual-design.md)

## 施策一覧

| # | 施策名 | 変更ファイル | 優先度 |
|---|--------|------------|--------|
| 1 | post-run-review SKILL.md 新規作成 | `.claude/skills/zenigame-fx-post-run-review/SKILL.md` | High |
| 2 | improve-cycle hook 接続点の更新 (TODO コメント → 起動コメント + launched marker 仕様) | `.claude/skills/zenigame-fx-improve-cycle/SKILL.md` | High |
| 3 | analyze-run 注記の更新 (post-run-review 接続済表示) | `.claude/skills/zenigame-fx-analyze-run/SKILL.md` | High |
| 4 | concept stub 新規 | `docs/alpha_factory/concepts/post-run-review.md` | Medium |
| 5 | runbook に post-run-review 起動手順追記 | `docs/alpha_factory/runbook.md` | Medium |
| 6 | terminology に post-run-review / theme review 等を追加 | `docs/alpha_factory/terminology.md` | Medium |

---

## 施策 1: post-run-review SKILL.md 新規作成

### 変更箇所
- ファイル: `.claude/skills/zenigame-fx-post-run-review/SKILL.md` (新規)

### 波及変更
- `AGENTS.md`: なし (skill 一覧の網羅は別 TODO で集中対応)
- `.claude/skills/zenigame-fx-improve-cycle/SKILL.md`: 施策 2 で対応
- `.claude/skills/zenigame-fx-analyze-run/SKILL.md`: 施策 3 で対応
- `config/alpha_factory/default.yaml`: なし
- `docs/alpha_factory/*.md`: 施策 4-6 で対応

### skill 構造 (出力すべき SKILL.md の章立て)

```
---
name: zenigame-fx-post-run-review
description: RUN 完了後にテーマ別の戦略的レビューを実行し、改善アイデアを Codex と議論して設計・TODO 登録まで自動完結する (Claude Code Agent BG fire-and-forget)
argument-hint: "<review-theme> <run_id> --tmp_dir <path>"
user-invocable: true
---

# zenigame-fx Post-Run Review

## 引数
| 引数 | 必須 | 説明 |
|------|------|------|
| review-theme ($1) | Yes | signal-quality / regime-awareness / cost-efficiency / robustness / risk-management の 5 値固定 enum |
| run_id ($2) | Yes | 対象 Run ID (run_YYYYMMDD_HHMMSS) |
| --tmp_dir | Yes | analysis-claude.md / analysis-codex.md が保存されている improve-cycle の tmp_dir |

(--tmp_dir 不在は error exit 1)

## 使命・思考原則・禁止事項
zenigame-fx-codex-review SKILL.md で定義される使命・禁止事項・C1-C9 discipline を継承。重複記載しない。
追加禁止事項 (本 skill 固有): trade_count 削減を主効果とする提案禁止 (live_criteria.trade_count_min からの距離悪化は reject)。

## review-theme 仕様 (固定 enum + 短縮 code + TODO theme マッピング)

| review-theme (引数) | 短縮 code (summary prefix) | TODO theme (`--theme`) |
|---------------------|--------------------------|------------------------|
| signal-quality      | `sq` | primitives  |
| regime-awareness    | `ra` | cross-pair  |
| cost-efficiency     | `ce` | ga-architecture |
| robustness          | `rb` | statistics  |
| risk-management     | `rm` | stage-gate  |

(マッピング以外の変換は許可しない / enum 値以外は error exit 1)

**summary prefix 規約**: post-run-review 経由 TODO は必ず `--summary "[r:{code}] {内容}"` 形式 (code は 2 文字固定 → prefix 全体 7 文字 → 内容 23 文字残)。

## Phase 0: 引数バリデーション + 変数固定

argument 仕様: `<theme> <run_id> --tmp_dir <path>`
位置引数 2 個 + named flag `--tmp_dir`。シンプルに位置 + flag 解析する:

bash
THEME=""
RUN_ID=""
TMP_DIR=""

# 位置引数 + --tmp_dir flag を while で解析
while [ $# -gt 0 ]; do
  case "$1" in
    --tmp_dir)
      if [ $# -lt 2 ] || [ -z "$2" ] || [ "${2:0:2}" = "--" ]; then
        echo "[error] --tmp_dir requires a non-empty value" >&2
        exit 1
      fi
      TMP_DIR="$2"
      shift 2
      ;;
    --tmp_dir=*)
      TMP_DIR="${1#--tmp_dir=}"
      if [ -z "$TMP_DIR" ]; then
        echo "[error] --tmp_dir= requires a non-empty value" >&2
        exit 1
      fi
      shift
      ;;
    *)
      if [ -z "$THEME" ]; then
        THEME="$1"
      elif [ -z "$RUN_ID" ]; then
        RUN_ID="$1"
      else
        echo "[error] unexpected argument: $1" >&2
        exit 1
      fi
      shift
      ;;
  esac
done

if [ -z "$THEME" ] || [ -z "$RUN_ID" ] || [ -z "$TMP_DIR" ]; then
  echo "[error] usage: post-run-review <theme> <run_id> --tmp_dir <path>" >&2
  exit 1
fi

case "$THEME" in
  signal-quality) CODE=sq ;;
  regime-awareness) CODE=ra ;;
  cost-efficiency) CODE=ce ;;
  robustness) CODE=rb ;;
  risk-management) CODE=rm ;;
  *) echo "[error] invalid review-theme: $THEME" >&2; exit 1 ;;
esac

mkdir -p .cache/alpha_factory
SUMMARY_FILE=".cache/alpha_factory/post-run-review-summary-${RUN_ID}.md"

## Phase 1-0: 早期スキップ判定

同 review-theme で Open TODO が 1 件以上あれば即終了:

bash
if uv run python scripts/alpha_factory/todo_manager.py list \
  | awk -v c="$CODE" '/^## Open/{open=1;next} /^##/{open=0} open && index($0, "[r:" c "]"){found=1} END{exit !found}'; then
  echo "[SKIP] post-run-review $THEME: open todo exists"
  printf "%s: skipped / 0 / open todo exists\n" "$THEME" >> "$SUMMARY_FILE"
  exit 0
fi


## Phase 1: コンテキスト読み込み

1. {tmp_dir}/analysis-claude.md, {tmp_dir}/analysis-codex.md を Read (不在時は warning ログ + Run report のみで続行)
2. 直近 3 Run report (reports/run-reports/run-{N}.md) を Read
3. todo_manager.py list で全 Open TODO を取得 (重複チェック用)
4. 前回申し送り .cache/alpha_factory/post-run-review-{review-theme}-deferred.md を Read (存在時のみ)

## Phase 2: Codex テーマ議論

zenigame-fx-codex-review One-shot モード:
- model: gpt-5.3-codex
- reasoning: medium
- label: theme-{review-theme}
- system: テーマ別 system prompt (5 種、後述)
- user: 上記 Phase 1 で集めたコンテキスト + 既存 Open TODO 一覧 + 前回申し送り

Codex 出力 = 5-6 件の改善案 (優先度ランク付き)。

## Phase 2-3: アイデア選定

各候補に以下チェック:
- 使命適合性
- 禁止事項非該当 (特に trade_count 削減主効果禁止)
- 重複なし (テーマ横断で Open TODO 全件と照合、上位互換 / 下位互換含む)
- 実装済み不重複
- 実現可能性

通過した上位 0-3 件を選定。0 件で構わない (申し送りのみ)。

## Phase 3: 設計 + TODO 登録 (順次)

各案について:
1. /zenigame-fx-alpha-design {topic-slug} を実行 → conceptual-design.md / detailed-design.md 生成
2. **lockf 排他で /zenigame-fx-todo-add を実行**:

bash
# 30 文字制約 (fail-fast 強制): prefix [r:CODE] (7 文字固定) + 内容 ≦ 23 文字
SUMMARY="[r:${CODE}] ${SHORT_DESC}"
if [ ${#SUMMARY} -gt 30 ]; then
  echo "[error] summary length=${#SUMMARY} exceeds 30 chars: $SUMMARY" >&2
  # 短縮再生成 or skip して次案へ
  continue
fi

# macOS 標準 lockf を使う (flock は macOS 標準では不在)。-k で lock file 保持、-s で silent
# Linux にも lockf は移植されている版があるが、最小公約数として lockf を採用 (本 skill は macOS 限定運用前提)
LOCK_FILE=/tmp/zenigame-fx-todo-add.lock
LOCK_BIN=/usr/bin/lockf
if [ ! -x "$LOCK_BIN" ]; then
  echo "[error] lockf not found at $LOCK_BIN. Required on macOS for atomic next-id+add." >&2
  exit 1
fi

# 環境変数で値を渡し python -c でクォート安全に実行 (シェル内 ' エスケープを避ける)
export PRR_TITLE="$TITLE"
export PRR_TODO_THEME="$TODO_THEME"
export PRR_SUMMARY="$SUMMARY"
export PRR_PRIORITY="$PRIORITY"
export PRR_DEVNOTES_DIR="$DEVNOTES_DIR"
export PRR_TODAY="$TODAY"

"$LOCK_BIN" -k -s -t 60 "$LOCK_FILE" sh -c '
  next_id=$(uv run python scripts/alpha_factory/todo_manager.py next-id) || exit 1
  uv run python scripts/alpha_factory/todo_manager.py add \
    --id "$next_id" \
    --title "$PRR_TITLE" \
    --theme "$PRR_TODO_THEME" \
    --summary "$PRR_SUMMARY" \
    --priority "$PRR_PRIORITY" \
    --mode incremental \
    --design-link "[設計](devnotes/$PRR_DEVNOTES_DIR/)" \
    --added-at "$PRR_TODAY"
' || { echo "[error] todo-add failed (lock timeout or add error)" >&2; continue; }


**重要**:
- `next-id` と `add` を必ず**同じ `lockf` 呼び出し内**で実行する (両者を別 lockf 呼び出しに分けると排他保証が壊れる)
- 値は環境変数経由で渡し、シェル内 `'` エスケープを避ける (ユーザー入力にシングルクォートが含まれても壊れない)
- `lockf -k` で lock file を保持 (連続呼び出し時のロック取得高速化)、`-t 60` で 60 秒 lock wait timeout

3 件あれば 3 回繰り返し (skill 内シーケンシャル、launcher (improve-cycle) 側の Agent 間並列とは別軸)。

## Phase 4: 申し送りファイル更新

残り候補を `.cache/alpha_factory/post-run-review-{review-theme}-deferred.md` に Write 上書き保存。
0 件なら削除。

**summary 30 文字超過で skip した案も申し送りに残す** (`reason: summary_too_long` を併記):
案の本質的価値と要約失敗は別問題のため、次回再要約のチャンスを残す。

申し送りエントリの推奨フォーマット:

```
## 候補 N: {title}
- 概要: {内容詳細}
- 優先度: {priority}
- 見送り理由: {top-3-not-selected | summary_too_long | duplicate_open | dup_closed | banned}
- (summary_too_long の場合) 短縮再生成のヒント: {推奨短縮形式案}
```

**TODO.md テーブル整合性**: `title` / `summary` に `|` または改行が含まれると Markdown テーブルが壊れるため、Phase 3 の todo-add 呼び出し前に Python 側で `s.replace("|", "/").replace("\n", " ")` 程度のサニタイズを行う (skill md 内に明記)。

## Phase 5: ログ & summary 行追記

.cache/alpha_factory/post-run-review-summary-${RUN_ID}.md に 1 行追記:
{review-theme}: {success|partial|failed|skipped} / {todos_added} / {note}

## 失敗時 defensive

(§2.7 の表に従い、すべての終了パスで summary 行を追記)

## エラーハンドリング

- Codex API 失敗: 30 秒待って 1 リトライ → ダメなら skip して exit
- alpha-design 失敗: エラーログ、2 件目以降は続行
- todo-add 失敗: エラーログ、その案を申し送り (`reason: todo-add-failed`) に残して**次案へ続行** (continue)。複数案ある場合は他案の登録を試みる

## テーマ別 system prompt (5 種)

以下 5 種を skill md 内に列挙:

### theme=signal-quality
あなたは zenigame-fx Alpha Factory のシグナル品質専門家です。
[フォーカス: directional/gate プリミティブの実効性、ルックアヘッド、新規プリミティブ提案、死滅プリミティブ原因究明]

### theme=regime-awareness
あなたは zenigame-fx Alpha Factory のレジーム適応専門家です。
[フォーカス: セッション帯、ボラ regime、cross-pair common factor、ペア固有 vs universal]

### theme=cost-efficiency
あなたは zenigame-fx Alpha Factory のコスト現実性専門家です。
[フォーカス: spread / slippage / swap / session_close / market impact / live execution 整合性]

### theme=robustness
あなたは zenigame-fx Alpha Factory の過学習耐性専門家です。
[フォーカス: DSR / PBO / WF-OOS / Sieve、Stage gate 突破率、サンプル外性能]

### theme=risk-management
あなたは zenigame-fx Alpha Factory のリスク統制専門家です。
[フォーカス: max_pos / time_stop / max_dd / live_criteria 達成パス / ポジションサイジング]

(各 system prompt 末尾に共通追加禁止: trade_count 削減主効果 ban、出力形式: 5-6 件 + trade_count 影響予測明記)

## 使用例

# improve-cycle Phase 1 末尾の launcher から fire-and-forget で起動 (5 テーマ並列)
# 親 skill が Agent ツール run_in_background: true で起動

# analyze-run スタンドアロン時の手動起動 (runbook 参照):
/zenigame-fx-post-run-review signal-quality run_20260424_093015 --tmp_dir devnotes/20260424-0930-analyze-run-XXXX
```

(skill md の実装行数目安: 約 350-450 行)

### ルックアヘッドバイアスチェック (primitive 変更時は必須)
- (本 TODO は primitive 変更を含まないため非該当)

### パフォーマンスチェック (primitive 変更時は必須)
- (本 TODO は primitive 変更を含まないため非該当)

### テスト計画
- 本 TODO は md only のため**新規テストなし**
- 既存 834 passed / 1 skip baseline は変更なしで維持

### リスク
- skill 引数 enum (5 値) を間違えた場合の検出: Phase 0 で `case "$THEME" in ... *) error exit 1 ;; esac` で守る (上記 Phase 0 ブロック)
- summary 30 文字超過: Phase 3 内で `[ ${#SUMMARY} -gt 30 ]` を fail-fast 強制 (todo_manager.py 側は警告止まりのため)
- launcher 二重起動: `.cache/alpha_factory/post-run-review-launched-{run_id}.json` で防止 (improve-cycle 側責務、施策 2 で実装)
- メモリ・並列負荷: 5 BG Agent が GA Phase 4 と時間重複する可能性。本 skill 自身は軽量 (Codex 議論 + alpha-design + todo-add) で 1 ワーカー 3GB 制約には影響しない。**`max_parallel_review_agents = 5` (デフォルト固定値)** を概念設計 §2.7 に明記。実測ベースの cap 適用機構は別 TODO (現時点ではトークン消費・I/O 負荷の実測なし → C8 INCONCLUSIVE 扱い)
- シェル injection: TITLE / SUMMARY 等は `'` を含み得るため、`lockf` 内 `sh -c` への値渡しは**環境変数経由**で行う (Phase 3 のコード参照)

---

## 施策 2: improve-cycle SKILL.md hook 更新 (実起動手順を含む)

### 変更箇所
- `.claude/skills/zenigame-fx-improve-cycle/SKILL.md`:
  - L21 (Phase 1 説明ブロック内コメント) — コメント書き換え
  - L265 (Phase 1 詳細セクション末尾) — **コメント書き換え + 実起動手順節を新規追加**
  - L543 (残課題テーブル) — 「接続済」へ更新

### 実起動手順 (L265 直後に新規節として追加)

L265 のコメントを書き換え後、その直下に以下を新規節として追加する (改善案 hook の launcher 仕様):

```markdown
### Post-Run Review BG 起動 (新規 — T026)

Phase 1 完了直後、5 review-theme について BG Agent を fire-and-forget で起動する。

**Step 1: 二重起動防止 marker 検査**

bash
LAUNCHED_MARKER=".cache/alpha_factory/post-run-review-launched-${run_id}.json"
if [ -f "$LAUNCHED_MARKER" ]; then
  echo "[INFO] post-run-review already launched for ${run_id}, skipping"
  # marker が既存 → skip (improve-cycle Phase 2 へ続行)
  return 0
fi

**Step 2: 5 review-theme を BG Agent で起動 (micro-stagger)**

各 review-theme について以下を Agent ツールで実行 (run_in_background: true):

- Agent プロンプト: `/zenigame-fx-post-run-review {review-theme} {run_id} --tmp_dir {tmp_dir}`
- 起動順序: signal-quality → regime-awareness → cost-efficiency → robustness → risk-management
- 各起動の間に 1 秒 sleep (`sleep 1` 等) を挟んで micro-stagger
- max_parallel_review_agents = 5 (固定。実測ベースの cap は別 TODO)

**Step 3: marker 書き込み (起動直後)**

bash
mkdir -p .cache/alpha_factory
cat > "$LAUNCHED_MARKER" <<EOF
{
  "run_id": "${run_id}",
  "tmp_dir": "${tmp_dir}",
  "launched_at": "$(TZ=Asia/Tokyo date -Iseconds)",
  "themes": ["signal-quality", "regime-awareness", "cost-efficiency", "robustness", "risk-management"]
}
EOF

**Step 4: improve-cycle 自身は完了を待たず Phase 2 へ続行**

各 BG Agent は完了時に `.cache/alpha_factory/post-run-review-summary-${run_id}.md` に 1 行追記する (Agent 自身の責務)。
improve-cycle 側はこの summary を待たない。次サイクルの Phase 1-2 (post-run-review が起動された側) で重複チェックに利用される。

**失敗時**:

- 5 Agent のうち一部が起動失敗しても improve-cycle は続行 (fire-and-forget)
- summary が空 / 部分的でも Phase 2 のブロック条件にしない
```

(実起動コードブロックは improve-cycle SKILL.md の Phase 1 末尾に新規追加。analyze-run には起動コードを追加しない)


### 現行コード (L21)
```
│   <!-- TODO(post-run-review-port): zenigame-fx-post-run-review 整備後に BG 起動を追加。現時点では no-op -->
```

### 変更後コード (L21)
```
│   <!-- post-run-review hook: 5 review-theme を BG Agent (run_in_background: true) で fire-and-forget 起動 (launch owner = 本フェーズ単一)
│        marker: .cache/alpha_factory/post-run-review-launched-{run_id}.json で二重起動防止
│        cooldown / theme rotation / trigger 判断ロジックは別 TODO -->
```

### 現行コード (L265)
```
<!-- TODO(post-run-review-port): zenigame-fx-post-run-review 整備後、Phase 1 完了直後に BG 起動するブロックを追加 -->
```

### 変更後コード (L265)
```
<!-- post-run-review hook (接続済): Phase 1 完了直後に 5 review-theme を BG Agent で fire-and-forget 起動。
     marker: .cache/alpha_factory/post-run-review-launched-{run_id}.json
     起動条件 (cooldown / theme rotation / trigger) の判断ロジックは別 TODO で詳細化。
     現時点では「marker 不在なら毎 Phase 1 完了で起動」のシンプル実装でよい。
     summary: .cache/alpha_factory/post-run-review-summary-{run_id}.md で各 Agent の launched/failed/skipped/success を 1 行ずつ集約。 -->
```

### 波及変更
- 残課題テーブル (L543) の `zenigame-fx-post-run-review` 行を「接続済」に更新

### 現行コード (L543)
```
| `zenigame-fx-post-run-review` | Phase 1 末尾 | `<!-- TODO(post-run-review-port) -->` コメント解除 + BG 起動ブロック追加 |
```

### 変更後コード (L543)
```
| `zenigame-fx-post-run-review` | Phase 1 末尾 | **接続済** (T026)。自動起動条件 (cooldown / rotation / trigger 判断) は別 TODO に分離 |
```

### テスト計画
- skill md 変更のみ。テスト追加なし

---

## 施策 3: analyze-run SKILL.md 注記更新

### 変更箇所
- `.claude/skills/zenigame-fx-analyze-run/SKILL.md` の 3 箇所:
  - L29 (現契約ブロック内)
  - L220 (未接続 hook サマリ)
  - L242 (注意事項)

### 現行コード (L29)
```
                         × /zenigame-fx-post-run-review        (未移植、整備後に接続)
```

### 変更後コード (L29)
```
                         → /zenigame-fx-post-run-review        (改善案 hook の標準起動点は improve-cycle Phase 1 末尾。analyze-run スタンドアロン実行時は起動しない)
```

### 現行コード (L220)
```
- zenigame-fx-post-run-review: 未移植
```

### 変更後コード (L220)
```
- zenigame-fx-post-run-review: 接続済 (improve-cycle Phase 1 末尾の launcher で起動。analyze-run スタンドアロンでは起動しない)
```

### 現行コード (L242)
```
- `zenigame-fx-post-run-review`（未移植）整備後に、Step 4 末尾に自動起動ブロックを追加する（follow-up TODO）
```

### 変更後コード (L242)
```
- `zenigame-fx-post-run-review` の起動 owner は **improve-cycle Phase 1 末尾のみ**。analyze-run スタンドアロン実行時に hook を発火させない (二重起動防止のため)。手動起動は runbook 参照
```

### テスト計画
- skill md 変更のみ。テスト追加なし

---

## 施策 4: concepts/post-run-review.md 新規作成

### 変更箇所
- `docs/alpha_factory/concepts/post-run-review.md` (新規、本 TODO で既に作成済 — 詳細設計レビュー前にレビュー対象として読める状態にしてある)

### 内容
本 skill の位置づけ・テーマ・起動方式・責務・成果物・スコープ外を簡潔記述 (約 50 行)。

### テスト計画
- 設計 md。テスト不要

---

## 施策 5: runbook.md に post-run-review 起動手順追記

### 変更箇所
- `docs/alpha_factory/runbook.md`

### 追記内容 (主要定義「2. Improve-cycle」の後ろに新セクション)

```markdown
### 2-1. Post-Run Review — テーマ別 BG レビュー

improve-cycle Phase 1 (analyze-run) 完了直後、5 つの review-theme について BG Agent (`run_in_background: true`) を fire-and-forget で起動する。

| review-theme | code | TODO theme | フォーカス |
|--------------|------|-----------|----------|
| signal-quality | sq | primitives | プリミティブ予測力 |
| regime-awareness | ra | cross-pair | レジーム適応 |
| cost-efficiency | ce | ga-architecture | コスト現実性 |
| robustness | rb | statistics | 過学習耐性 |
| risk-management | rm | stage-gate | リスク統制 |

post-run-review 由来の TODO は `--summary` 先頭に **`[r:{code}]`** prefix を必ず付与 (30 文字制約対応の短縮 code、prefix 7 文字固定 → 内容 23 文字残)。

- launch owner: `improve-cycle` Phase 1 末尾のみ (analyze-run スタンドアロンでは起動しない)
- 二重起動防止 marker: `.cache/alpha_factory/post-run-review-launched-{run_id}.json`
- 集約 summary: `.cache/alpha_factory/post-run-review-summary-{run_id}.md`
- 申し送り: `.cache/alpha_factory/post-run-review-{review-theme}-deferred.md` (テーマごと)

**手動起動** (analyze-run スタンドアロン実行後に改善案を出したい場合):

```
/zenigame-fx-post-run-review signal-quality run_YYYYMMDD_HHMMSS --tmp_dir devnotes/YYYYMMDD-HHMM-analyze-run-XXXX
```

`--tmp_dir` には `analyze-run` が出力した `analysis-claude.md` / `analysis-codex.md` のあるディレクトリを指定。
```

### テスト計画
- ドキュメント追記。テスト不要

---

## 施策 6: terminology.md に post-run-review / theme review 用語追加

### 変更箇所
- `docs/alpha_factory/terminology.md`

### 追記内容 (主要定義の末尾に追加)

```markdown
### Post-Run Review

`<a id="post-run-review"></a>` Post-Run Review — improve-cycle Phase 1 完了直後に launcher が fire-and-forget で起動する、テーマ別の戦略レビュー BG Agent 群。Codex (`gpt-5.3-codex` medium) と議論して上位 0-3 案を `/zenigame-fx-alpha-design` → `/zenigame-fx-todo-add` まで自動完結させる。launch owner は **improve-cycle Phase 1 末尾のみ** に固定。

### Review Theme

`<a id="review-theme"></a>` Review Theme — post-run-review の引数として渡される 5 値固定 enum (`signal-quality` / `regime-awareness` / `cost-efficiency` / `robustness` / `risk-management`)。各 review-theme には 2 文字の短縮 code (`sq` / `ra` / `ce` / `rb` / `rm`) が紐付き、`zenigame-fx-todo-add` の TODO theme (10 種) とは別空間で、内部で固定マッピング表を介して TODO theme へ変換される。post-run-review 由来の TODO は `--summary` 先頭に `[r:{code}]` prefix を付与する規約 (30 文字制約対応で短縮 code を採用)。

### Launched Marker

`<a id="launched-marker"></a>` Launched Marker — `.cache/alpha_factory/post-run-review-launched-{run_id}.json`。同一 run_id の post-run-review BG Agent 群を二重起動しないための排他 marker。improve-cycle Phase 1 末尾 launcher が起動前にチェックし、起動直後に書き込む。

### Review Summary

`<a id="review-summary"></a>` Review Summary — `.cache/alpha_factory/post-run-review-summary-{run_id}.md`。各 review-theme Agent が完了時に 1 行追記する集約ログ (`{theme}: {status} / {todos_added} / {note}`)。silent failure 防止と次 cycle 観測用。
```

### テスト計画
- ドキュメント追記。テスト不要

---

## 実装モード

| 項目 | 内容 |
|------|------|
| 推奨モード | incremental |
| 判断根拠 | md only / 単一コンポーネント (skill 群 + ドキュメント) / 既存挙動への副作用なし (improve-cycle / analyze-run はコメント書き換えのみ) |
| 競合リスク | 低 (他施策との file 重複なし) |
| 想定実装時間 | 短 (md only、約 350-450 行の skill md + 3 ファイルの軽微な追記) |

---

## レビュー観点 (Codex design-review 用)

1. **lockf 設計の正確性**: `/usr/bin/lockf -k -s -t 60 /tmp/zenigame-fx-todo-add.lock sh -c "next-id && add"` を 1 命令で実行する記述は、現行 `todo_manager.py` 非改修の制約下で排他保証として正確か？
2. **awk grep の堅牢性**: `## Open` セクションを抽出して `[r:{code}]` (短縮 code 2 文字) を検出する awk スクリプトは、`todo_manager.py list` の出力フォーマット (`## Open (N)` ヘッダ + テーブル行) に対して堅牢か？
3. **summary 30 文字制約**: 短縮 code (`sq`/`ra`/`ce`/`rb`/`rm`) で `[r:{code}]` prefix を 7 文字固定にし、内容に 23 文字残す設計は妥当か？ (元案の `[review:{review-theme}]` だと `regime-awareness` 等で内容 5 文字未満になる問題を回避)
4. **launch owner 単一化と marker**: improve-cycle 単独 launcher + `.cache/.../launched-{run_id}.json` で二重起動を防げるか？ Phase 1 を analyze-run スタンドアロン側でも経由する設計はないか？
5. **波及変更の網羅**: improve-cycle / analyze-run / runbook / terminology / concept stub / 新 skill md の 6 ファイルで網羅できているか？ AGENTS.md 更新は不要か？
6. **テスト不在の妥当性**: md only のため pytest 追加なしの判断は妥当か？ 834 baseline 維持は確かに保証できるか？
7. **施策 1 skill md の章立て**: 350-450 行の skill md として、Phase 構成 (1-0 / 1 / 2 / 2-3 / 3 / 4 / 5) と error handling / system prompt 5 種の網羅は十分か？
