---
name: zenigame-fx-post-run-review
description: RUN 完了後にテーマ別の戦略的レビューを Claude Code Agent BG セッションで実行し、改善案を Codex と議論して設計・TODO 登録まで自動完結する (FX 5 review-theme: signal-quality / regime-awareness / cost-efficiency / robustness / risk-management)
argument-hint: "<review-theme> <run_id> --tmp_dir <path>"
user-invocable: true
---

# zenigame-fx Post-Run Review (テーマ別戦略レビュー)

improve-cycle Phase 1 (analyze-run) 完了直後に **fire-and-forget で BG Agent として起動**される、テーマ別の戦略レビュー skill。
analysis-claude.md / analysis-codex.md と直近 Run report を読み、Codex と議論して上位 0-3 案を `/zenigame-fx-alpha-design` → `/zenigame-fx-todo-add` まで自動完結させる。
ユーザー確認・介入は一切不要。完全自律動作。

## 引数

| 引数 | 必須 | 説明 |
|------|------|------|
| `review-theme` ($1) | Yes | 5 値固定 enum: `signal-quality` / `regime-awareness` / `cost-efficiency` / `robustness` / `risk-management` |
| `run_id` ($2) | Yes | 対象 Run ID (例: `run_20260424_093015`) |
| `--tmp_dir` | Yes | improve-cycle / analyze-run の tmp_dir。`analysis-claude.md` / `analysis-codex.md` の保存先 |

`--tmp_dir` 不在 / 値欠落は error exit 1。

## 使命・思考原則・禁止事項

`zenigame-fx-codex-review` SKILL.md で定義される使命・禁止事項・C1-C9 discipline を継承。重複記載しない。

**追加禁止事項 (本 skill 固有)**:
- **trade_count 削減を主効果とする提案禁止** (live_criteria.trade_count_min からの距離悪化は reject)。`zenigame-fx-improve-cycle` 禁止事項 #6 (取引回数削減で見かけ成績を上げる) に直接対応

## review-theme 仕様 (固定 enum + 短縮 code + TODO theme マッピング)

| review-theme (引数) | code (summary prefix) | TODO theme (`--theme`) | 主担当境界 |
|---------------------|---------------------|------------------------|-----------|
| `signal-quality`    | `sq` | `primitives`       | プリミティブ「単体」の予測力 |
| `regime-awareness`  | `ra` | `cross-pair`       | regime gate / cross-pair / global_gate |
| `cost-efficiency`   | `ce` | `ga-architecture`  | コストモデルの現実性 (spread / slippage / swap / session_close) |
| `robustness`        | `rb` | `statistics`       | DSR / PBO / WF-OOS / Sieve / Stage gate 通過率 |
| `risk-management`   | `rm` | `stage-gate`       | live_criteria 達成パス (max_pos / time_stop / max_dd) |

(マッピング以外の変換は許可しない。enum 値以外は error exit 1)

**summary prefix 規約**: post-run-review 経由 TODO は必ず `--summary "[r:{code}] {内容}"` 形式 (code 2 文字 → prefix `[r:xx] ` 7 文字固定 → 内容 23 文字残)。

---

## Phase 0: 引数解析 + 変数固定

```bash
THEME=""
RUN_ID=""
TMP_DIR=""

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
DEFERRED_FILE=".cache/alpha_factory/post-run-review-${THEME}-deferred.md"
```

---

## Phase 1-0: 早期スキップ判定

同 review-theme で Open TODO が 1 件以上あれば即終了:

```bash
if uv run python scripts/alpha_factory/todo_manager.py list \
  | awk -v c="$CODE" '/^## Open/{open=1;next} /^##/{open=0} open && index($0, "[r:" c "]"){found=1} END{exit !found}'; then
  echo "[SKIP] post-run-review $THEME: open todo exists"
  printf "%s: skipped / 0 / open todo exists\n" "$THEME" >> "$SUMMARY_FILE"
  exit 0
fi
```

awk 解析の堅牢性: `## Open (N)` ヘッダで open=1、次の `##` で open=0 に戻すことで Open セクション内の行のみを対象にする。`index()` を使い `CODE` を正規表現メタ文字としてではなく純文字列として検索する。

---

## Phase 1: コンテキスト読み込み

### 1-1. 分析成果物

`{TMP_DIR}/analysis-claude.md` / `{TMP_DIR}/analysis-codex.md` を `Read` する。
両方 / 片方不在: warning ログのみ、Run report のみで続行。

### 1-2. 直近 Run report

```bash
latest_n=$(uv run python scripts/alpha_factory/get_latest_run_number.py)
```

`reports/run-reports/run-{N}.md` を直近 3 件 `Read` する (最新含む N, N-1, N-2)。
全件不在の場合: warning ログのみ、Codex 議論を skip して early-exit (summary に `failed / 0 / no run report` を追記)。

### 1-3. 既存 Open TODO 一覧 (重複チェック用)

```bash
uv run python scripts/alpha_factory/todo_manager.py list
```

Open テーブル全行を取得。同 review-theme でなくても**全件**を Codex プロンプトに渡し、横断重複チェック対象とする。

### 1-3b. 直近 Closed TODO 10 件 (実装済み重複チェック用)

`docs/alpha_factory/TODO-closed.md` を Read し、Closed テーブル末尾 10 行を取得 (現行 `todo_manager.py` には `list-closed-tail` サブコマンドが存在しないため、ファイル直接読みで代替)。
Codex プロンプトに「Closed TODO (直近 10 件、実装済み)」セクションとして渡す。
ファイル不在時は warning ログのみで続行 (Closed 一覧空)。

### 1-4. 前回申し送り

`{DEFERRED_FILE}` を `Read` する (存在時のみ)。Codex プロンプトに「前回保留候補」として渡す。

---

## Phase 2: Codex テーマ議論

**呼び出し責務**: 本 Phase は `zenigame-fx-codex-review` SKILL.md で定義される **One-shot モード** の規約に従う。
使命・禁止事項・C1-C9 の自動挿入は同 skill の責務であり、本 skill は「テーマ別 system prompt + コンテキスト user 部」だけを定義する。
プロンプトファイルを `{TMP_DIR}/.codex-prompt-theme-${THEME}.md` に Write で書き出してから `scripts/codex exec` を以下の規約で呼び出す:

- **model**: `gpt-5.3-codex`
- **reasoning**: `medium`
- **label**: `theme-{review-theme}`
- 出力ファイル: `{TMP_DIR}/post-review-codex-${THEME}.md`

```bash
# プロンプトファイル準備は呼び出し元の Claude Code (post-run-review skill 自身) が Write ツールで行う
scripts/codex exec --ephemeral --sandbox read-only -m gpt-5.3-codex \
  -c 'model_reasoning_effort="medium"' \
  -o "${TMP_DIR}/post-review-codex-${THEME}.md" \
  - < "${TMP_DIR}/.codex-prompt-theme-${THEME}.md"
```

### 2-1. テーマ別 system prompt

**全テーマ共通の追加禁止 + 出力形式**:

```
【追加禁止事項 — 全テーマ共通】
- trade_count 削減を主効果とする提案は禁止 (live_criteria.trade_count_min からの距離が悪化する案は reject)
- 取引回数削減で見かけの Sharpe / WR を上げる案は zenigame-fx 禁止事項 #6 違反

【改善ループとの役割分担 — 以下はこのセッションで提案しないこと】
このセッションは「複数 Run にわたって価値を持つ構造的改善」を担う。
以下は別の改善ループ (improve-cycle plan-and-design) が対処するため提案しない:
- 「今回 Run の X 指標に基づく Y パラメータ Z 変更」系の場当たり修正
- 特定 Run の結果から直接導かれる一過性の改善

【出力形式】
- 改善提案を「優先度: Critical / High / Medium」で 5-6 件
- 各提案に「テーマ固有の効果評価」「実装難易度 (低 / 中 / 高)」「実装規模 (短 / 中 / 大)」「trade_count 影響予測 (増 / 不変 / 減 — 減の場合は justify)」を明記
- 既存 Open TODO と重複しない提案
- 日本語
```

**theme=`signal-quality` (シグナル品質)**

```
あなたは zenigame-fx Alpha Factory のシグナル品質専門家です。
Alpha Factory (NSGA-II + Clause-based DSL ゲノム) のプリミティブ予測力を構造的に向上させる方法を提案してください。

【フォーカス】
- 既存 directional / gate プリミティブ (32 種) の品質診断
- ルックアヘッドバイアスの再点検 (compute / compute_all_bars / _compute_full の全パス)
- 死滅プリミティブの原因分析と改良案 / 撤退判断
- 新規プリミティブ提案 (FX イントラデイで予測力が期待できるもの、学術論文・実務知見の引用必須)
- プリミティブ間の相関・冗長性排除
- 正規化・スケーリング (ATR 正規化 / Z-score) の妥当性

【DSL ゲノム構造】
詳細: docs/alpha_factory/clause-architecture.md / primitives.md
```

**theme=`regime-awareness` (レジーム適応)**

```
あなたは zenigame-fx Alpha Factory のレジーム適応専門家です。

【フォーカス】
- 時間帯別 (東京前場 / ロンドン / NY オーバーラップ等) のレジーム分岐
- ボラティリティ regime gate (ATRRegimeGate 等) の設計妥当性
- cross-pair (ii-lite) アンカーペア戦略の改善 (debate-synthesis.md §C 参照)
- common factor 補正 (USD 共通因子 / EUR-USD ペア相関等)
- ペア固有 GA vs universal GA のバランス

詳細: docs/alpha_factory/cross-pair.md / clause-architecture.md
```

**theme=`cost-efficiency` (コスト現実性)**

```
あなたは zenigame-fx Alpha Factory のコストモデル専門家です。

【フォーカス】
- spread モデルの現実性 (時間帯別 / 通貨ペア別 / イベント時拡大)
- slippage / market impact (約定モデル)
- swap / overnight cost の反映 (イントラデイクローズ前提との整合)
- session_close フィルタの妥当性 (NY クローズ / 週末ギャップ)
- live execution と backtest の乖離原因
```

**theme=`robustness` (過学習耐性)**

```
あなたは zenigame-fx Alpha Factory の過学習耐性専門家です。

【フォーカス】
- DSR (Deflated Sharpe Ratio) / PBO (Probability of Backtest Overfitting) の hard gate 化
- WF-OOS (Walk-Forward Out-of-Sample) 設計の改善
- Alpha Sieve (T025) との連携 / 通過基準の calibrate
- Stage A / B / C 通過率の構造的改善 (閾値緩和ではなく)
- レジーム持続リスクの検出と緩和

詳細: docs/alpha_factory/sieve.md / stage-gates.md / statistics.md
```

**theme=`risk-management` (リスク統制)**

```
あなたは zenigame-fx Alpha Factory のリスク統制専門家です。

【フォーカス】
- max_pos (ポジションサイジング) の動的調整
- time_stop (最大保有時間) の妥当性
- max_dd (最大ドローダウン) のリアルタイム制御
- live_criteria 達成パスの設計 (Sharpe / Total PnL / Max Drawdown / Trade Count を同時充足)
- レバレッジ・証拠金維持率の整合
```

### 2-2. user 部の内容

```
## 直近 3 Run report (run-N.md, run-{N-1}.md, run-{N-2}.md)
{1-2 で Read した全内容}

## 分析成果物
{1-1 で Read した analysis-claude.md / analysis-codex.md の全内容}

## 既存カバー済みトピック (重複禁止リスト)
以下はすでに Open TODO または直近 Closed の改善内容です。
これらと同じ問題・同じアプローチの提案は絶対に行わないこと。

### Open TODO
{1-3 で取得した Open テーブル全行}

## 前回申し送り候補 (存在する場合)
{1-4 で読み込んだ deferred ファイル全内容}

## 依頼
上記の最新 Run データと既存カバー済みトピックを踏まえ、{review-theme} の観点から最も有望な**新規**改善提案を 5-6 件列挙してください。

重要:
- 既存カバー済みトピックと実質的に同じ内容 (同一問題・同一アプローチ・上位互換・下位互換) の提案は不可
- 前回申し送り候補がある場合は、それも候補リストに含めて再評価し、優先度に従い他の提案と競合させること
- 優先度順にランク付けして出力すること (1 位が最優先)
```

### 2-3. Codex 失敗時

`scripts/codex exec` が非ゼロ終了した場合、30 秒待って 1 回リトライ。
2 回連続失敗の場合: skip して exit (summary に `failed / 0 / codex unavailable`)、Phase 3 に進まない。

---

## Phase 2-3: アイデアの選定

Codex 出力 (5-6 件) を上から順に確認し、**自分自身で**各候補に以下チェックを適用:

| チェック項目 | 確認内容 |
|------------|---------|
| 使命適合性 | live_criteria 達成パスへの本質寄与 |
| 禁止事項非該当 | 7 つの禁止事項 + trade_count 削減主効果禁止 |
| 重複なし (厳格) | Open TODO 全件 (テーマ横断) と照合、同一問題 / 上位互換 / 下位互換に該当しない |
| 実装済み不重複 | Closed TODO 直近 10 件と照合 |
| 実現可能性 | 現行コードベースで技術的に実装可能 |

**重複判定の基準**:
- 「同じファイルを変更する」だけでは重複ではない
- 「解決しようとしている問題が実質的に同じ」場合が重複
- 「アプローチが異なれば同じ問題でも新規」として扱う

通過候補を上から取り出し、以下に振り分け:

| カテゴリ | 件数 | 説明 |
|---------|------|------|
| 今回実施 | 0-3 件 | 全チェック通過した上位候補 |
| 申し送り | 残り全件 | チェック通過したが選外 / 次回再評価 / summary_too_long |
| 却下 | 0 件以上 | 重複・禁止事項違反・実現不可 (申し送りに含めない) |

**今回実施は 0 件で構わない**。十分な候補がなければ無理に立案せず申し送りのみとする。

各案に topic slug (英小文字・ハイフン区切り) を決定。例: `signal-momentum-roc-enhancement` / `slippage-model-realistic` / `risk-trailing-stop-adaptive`。

---

## Phase 3: 設計 + TODO 登録 (順次)

**今回実施が 0 件の場合**: このフェーズを skip し Phase 4 へ。

**今回実施 1-3 件を順番に処理**。1 件ずつ完了させてから次に進む (skill 内並列禁止、launcher 側 5 Agent 並列とは別軸)。

### 各案について

#### Step 1: 設計ファイル生成 (`/zenigame-fx-alpha-design`)

```
/zenigame-fx-alpha-design {topic-slug}
```

このスキルが自動実行する:
- Phase 1: 概念設計作成 → Codex (gpt-5.4) レビュー合議 → APPROVED
- Phase 2: 詳細設計作成 → Codex (gpt-5.3-codex) レビュー合議 → APPROVED

完了後、`devnotes/{YYYYMMDD-HHMM-topic}/conceptual-design.md` / `detailed-design.md` を確認。
失敗時: `{SUMMARY_FILE}` に `partial / N / alpha-design err on #M` を追記、2 件目以降は続行 (1 件目で全停止しない)。

#### Step 2: TODO 登録 (lockf 排他)

```bash
# 30 文字制約 fail-fast
SUMMARY="[r:${CODE}] ${SHORT_DESC}"
if [ ${#SUMMARY} -gt 30 ]; then
  echo "[error] summary length=${#SUMMARY} exceeds 30 chars: $SUMMARY" >&2
  # 申し送り (reason: summary_too_long) に残して次案へ
  continue
fi

# title / summary に | / 改行が含まれる場合は Markdown テーブル整合性のため事前サニタイズ
# (post-run-review 内で sed / python で置換)
TITLE_SAN=$(printf '%s' "$TITLE" | tr '\n|' ' /')
SUMMARY_SAN=$(printf '%s' "$SUMMARY" | tr '\n|' ' /')

# macOS 標準 lockf を使う (flock は macOS 標準では不在)
LOCK_BIN=/usr/bin/lockf
LOCK_FILE=/tmp/zenigame-fx-todo-add.lock
if [ ! -x "$LOCK_BIN" ]; then
  echo "[error] lockf not found at $LOCK_BIN" >&2
  exit 1
fi

# 環境変数経由で値を渡し、シェル内 ' エスケープを避ける
export PRR_TITLE="$TITLE_SAN"
export PRR_TODO_THEME="$TODO_THEME"   # マッピング表で変換済の TODO theme
export PRR_SUMMARY="$SUMMARY_SAN"
export PRR_PRIORITY="$PRIORITY"
export PRR_DEVNOTES_DIR="$DEVNOTES_DIR"
export PRR_TODAY=$(TZ=Asia/Tokyo date '+%Y-%m-%d %H:%M')

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
```

**重要**:
- `next-id` と `add` を必ず**同じ `lockf` 呼び出し内**で実行する (両者を別 lockf 呼び出しに分けると排他保証が壊れる)
- 値は環境変数経由で渡し、シェル内 `'` エスケープを避ける
- `lockf -k` で lock file を保持 (連続呼び出しで lock 取得を高速化)、`-s` silent、`-t 60` で 60 秒 lock wait timeout

3 件あれば 3 回繰り返し (skill 内シーケンシャル)。

---

## Phase 4: 申し送りファイル更新

残り候補を `{DEFERRED_FILE}` に `Write` で上書き保存。
0 件なら `rm -f "$DEFERRED_FILE"`。

申し送りエントリのフォーマット:

```markdown
# 申し送り候補: {review-theme}
生成: {run_id} / {YYYY-MM-DD HH:MM JST}

## 今回登録した TODO (効果確認用)
- {T0NN}: {topic-slug-1}
- {T0NN}: {topic-slug-2}

## 候補 1: {title}
- 概要: {要点}
- 優先度: High / Medium
- 見送り理由: {top-3-not-selected | summary_too_long | duplicate_open | dup_closed | banned}
- (summary_too_long の場合) 短縮再生成のヒント: {推奨短縮形式案}

## 候補 2: ...
```

`reason: summary_too_long` 案も**完全 reject せず申し送りに残す** (案の本質価値と要約失敗は別問題のため、次回再要約のチャンスを残す)。

---

## Phase 5: ログ & summary 行追記

各 Phase 完了後 (どの終了パスでも) `{SUMMARY_FILE}` に 1 行追記:

```
{review-theme}: {success|partial|failed|skipped} / {todos_added} / {note}
```

| status | 条件 | note 例 |
|--------|------|---------|
| `success` | 全 Phase 正常完了 | `-` |
| `partial` | 一部 Phase でエラーだが 1 件以上 TODO 登録 | `alpha-design err on #2` |
| `failed` | TODO 登録ゼロかつエラー終了 | `codex unavailable` / `no run report` |
| `skipped` | early-exit | `open todo exists` |

---

## エラーハンドリング

| 状況 | 挙動 |
|------|------|
| `--tmp_dir` 不在 / 値欠落 | error exit 1 (Phase 0) |
| 分析成果物 (`analysis-claude.md` / `analysis-codex.md`) 不在 | warning ログ、Run report のみで続行 |
| Run report 全件不在 | warning ログ、Codex 議論を skip して exit (`failed / 0 / no run report`) |
| Codex 失敗 (2 回リトライ後) | skip して exit (`failed / 0 / codex unavailable`) |
| alpha-design 失敗 (1 件目) | エラーログ、2 件目以降は続行 (`partial / N / alpha-design err on #M`) |
| todo-add 失敗 (lockf timeout / add error) | エラーログ、次案へ続行 (`partial / N / todo-add err on #M`) |
| summary 30 文字超過 | 申し送りに `summary_too_long` 理由付きで残す、次案へ |
| 同 review-theme Open TODO 既存 | early-exit (exit 0)、申し送りも更新しない (`skipped / 0 / open todo exists`) |

---

## 起動方式

### 自動起動 (improve-cycle Phase 1 末尾)

`zenigame-fx-improve-cycle` Phase 1 末尾の launcher が、Agent ツール (`run_in_background: true`) で 5 review-theme を fire-and-forget で起動する。
launcher の二重起動防止 marker: `.cache/alpha_factory/post-run-review-launched-{run_id}.json`。
集約 summary: `.cache/alpha_factory/post-run-review-summary-{run_id}.md` (各 Agent が完了時に 1 行追記)。

### 手動起動 (analyze-run スタンドアロン後)

```
/zenigame-fx-post-run-review signal-quality run_20260424_093015 --tmp_dir devnotes/20260424-0930-analyze-run-XXXX
```

`--tmp_dir` には `analyze-run` が出力した `analysis-claude.md` / `analysis-codex.md` のあるディレクトリを指定。

---

## 注意事項

- 本 skill は **Claude Code 専用**。OS 常駐デーモンや別プロセスキューに頼る CLI 互換は提供しない
- `run-alpha-factory` (CLI 必須、heavy GA 放置) とはスコープを分離 — 本 skill は軽量 Codex 議論 + 設計 + TODO 登録のみで Claude Code Agent 内で完結
- 株版 zenigame の OS 常駐サービス / 外部タスクキュー依存はすべて削除 (Claude Code Agent 自体が独立プロセスとしてランタイム管理)
- launch owner は **`improve-cycle` Phase 1 末尾のみ**。analyze-run スタンドアロンでは自動起動しない (二重起動防止)
- `max_parallel_review_agents = 5` (固定)。実測ベースの cap は別 TODO

## 残課題 (本 skill スコープ外)

- 自動起動条件の決定ロジック (cooldown / theme rotation / トリガー) — 別 TODO
- `todo_manager.py add-auto` (lock + 重複 summary 検出を 1 命令に統合) — 別 TODO
- 5 BG Agent 並列上限の動的制御 — 別 TODO
- focus-theme.json 連動 — `set-focus` skill 整備後

---

## 使用例

### 例 1: improve-cycle から自動起動 (典型)

```
/zenigame-fx-improve-cycle
→ Phase 1 (analyze-run) 完了 → launcher が 5 review-theme を BG Agent で fire-and-forget 起動
→ improve-cycle 自身は Phase 2 (plan-and-design) に続行
```

### 例 2: analyze-run スタンドアロン後の手動起動

```
/zenigame-fx-analyze-run run_20260424_093015 --tmp_dir devnotes/20260424-0930-analyze-run-XXXX
# 完了後、特定テーマだけレビューしたい場合:
/zenigame-fx-post-run-review signal-quality run_20260424_093015 --tmp_dir devnotes/20260424-0930-analyze-run-XXXX
```
