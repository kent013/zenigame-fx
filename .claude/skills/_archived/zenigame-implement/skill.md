---
name: zenigame-implement
description: Alpha Factory TODO実装（worktreeで実装・テスト・Codexレビュー・コミット・TODOクローズ→mainマージ）。RUNは行わない
argument-hint: "<todo_id> [--tmp_dir path] [--skip-consensus] [--skip-todo]"
---

# Alpha Factory 実装（worktree分離）

詳細設計に基づき、**gitworktreeで分離した環境**でコード実装→テスト→Codexレビュー→ドキュメント更新→コミット→TODOクローズ→mainマージを行う。**RUNは行わない。**

## 引数

| 引数 | 必須 | 説明 |
|------|------|------|
| `todo` ($1) | Yes | TODO ID（例: T099）。TODO.mdから設計リンクを取得し、詳細設計を読み込んで実装 |
| `--tmp_dir` | No | 中間成果物の保存先ディレクトリ（plan-and-designの出力先と同一）。--todo時は自動生成 |
| `--skip-consensus` | No | Codex合議スキップモード。テスト通過をもって実装完了とみなす。**ユーザーから明示的に指定された場合のみ使用可。自動判断で付与してはならない** |
| `--skip-todo` | No | TODO遷移スキップモード。Phase C（TODO close/obsolete）をスキップ |

**入力**:
- TODO ID → 設計リンクから `detailed-design.md` を自動取得
- または `{tmp_dir}/detailed-design.md`（improve-cycle経由）

**出力**:
- mainブランチにマージ済みのコミット
- クローズ済みTODO

---

## 思考原則 — 全議論に適用

**まず仮説を立てろ。** 何を検証したいのか、なぜそう考えるのか、どうなれば成功と判断するのかを明確にしてから手を動かせ。仮説なき改善はただの試行錯誤であり、結果から学ぶことができない。

探索空間は広い。今いる場所が正しいのか、もう少し先に進むべきか、横に移動すべきか、戻って別の道を探るべきかは、これまでの試行と観察の蓄積からしか判断できない。

**データに真摯に向き合え。** 成果だけでなく、多様性の変化、構造の揺らぎ、想定外のパターン — 全てが判断材料になる。数値を見て即座に閾値を弄るな。何が起きているのかを理解し、なぜそうなったのかを考え、どの方向に進むべきかを判断してから手を動かせ。

**先人の知恵を探せ。** 自分たちだけで登る必要はない。乗るべき巨人の肩があるなら乗れ。

**機能の名前に立ち返れ。** 名前はその機能が果たすべき役割を示している。現在の設計がその役割を果たしているか、常に問え。

**仕組みが機能していない段階で値を弄るな。** 閾値チューニングやフィールド追加（KAIZEN）は、設計の方向性が正しいと確認できてから行え。方向性が間違っているなら、値をいくら調整しても意味はない。設計そのものを見直せ（INNOVATION）。成果が出なければ早期に見切り、次の仮説へ進め。

**因果ループを切断するな。** 「XはYに影響しない」という主張に出会ったら、間接経路を含む因果ループ全体を追え。このシステムは観測→判断→介入→GAの結果→観測…のフィードバックループで動いている。ループの一部を「直接影響しないから無関係」と切断する主張は、ほぼ常に間違いである。主張の真偽ではなく、**切断された経路が本当に存在しないか**を検証せよ。

### Bad / Nice 例

**Bad**: Directorのfallbackがactiveより良い結果 → 「抑圧下限を0.03→0.10にしよう」「max-clipを入れよう」
**Nice**: Directorのfallbackがactiveより良い結果 → 「Directorという名前は"方向を示す"という意味だ。今の設計は毎Runの重み計算機でしかない。方向を示すとはどういうことか？」→ Multi-Run実験計画 + メモリ + 非同期深掘り分析という本来の役割を再定義

**Bad**: BollingerRevertのB効果が負 → 重みを0.03に抑圧
**Nice**: BollingerRevertのB効果が負 → だがfallback時にC-PASS最強クラスタの核になっている → 単独B効果で判断する設計自体が組み合わせシナジーを殺している → Directorに渡す情報と判断基準の再設計が必要

**Bad**: 10 Runの結果を集計 → 「C-PASS平均: active=5.14 vs fallback=6.33、Directorはnet-negativeです」
**Nice**: 10 Runの結果を集計 → ゲノム系譜を追跡 → fallbackのC-PASS個体の半数はwarmstart経由でDirector-active期の構造を継承している → 「fallbackの好結果はDirector由来の揺らぎが伝播した結果かもしれない」→ 単純比較では因果関係を見誤る

**Bad**: Codexと11ラウンド議論 → 閾値・スキーマ・ガードレールの詳細設計で合意
**Nice**: 「そもそもDirectorにメモリがないのはおかしくないか？選択→結果→学習→次の選択のループがない」→ 機能の本質的な欠陥を指摘してから設計を議論

---

## 使命（North Star）— 絶対遵守

> **Alpha Factoryの使命は「`config/alpha_factory/default.yaml` → `live_criteria` を全て満たすイントラデイ戦略個体を1つ見つけ出すこと」である。**
>
> Stage C通過は最低条件。使命達成 = `live_criteria` の全指標を同時に満たすC-PASS個体の出現。
> 達成後は `live_criteria` の各閾値を引き上げて次の水準を設定する（漸進的目標更新）。

## 禁止事項（自分・Codex双方に適用）

| # | 禁止事項 | 理由 |
|---|---------|------|
| 1 | **ショート（空売り）売買の導入** | 対象外 |
| 2 | **A・B・C評価期間を強い根拠なしに延長する** | 過学習の隠蔽 |
| 3 | **見た目の数値をよくしようとする改善** | 無意味 |
| 4 | **GAをハックしてステージを進めようとする** | 歪曲 |
| 5 | **閾値をいたずらに緩和してステージを飛ばす** | 安易な緩和 |
| 6 | **やたらに複雑な案を提案する** | コスト不適合 |
| 7 | **取引回数を削減して見かけの成績を上げようとする** | 使命に反する |

---

## Phase W: Worktree準備

### W-1. TODO情報の取得（--todo モード）

1. `scripts/todo_manager.sh` で対象行を1行取得:
   ```bash
   row=$(bash scripts/todo_manager.sh get "{todo}")
   ```
2. 見つからない場合（exit code 1）はエラー終了
3. `row` のパイプ区切り7列目から「設計」列のリンク先を取得し、詳細設計ファイルパスを構成
4. 詳細設計ファイルを `Read` する
5. 概念設計もリンクがあれば `Read` して背景を把握

### W-2. tmp_dir の準備

`tmp_dir` が未指定の場合:
```bash
date '+%Y%m%d-%H%M'
```
で `devnotes/{YYYYMMDD-HHMM}-todo-{todo_id}/` を作成。

### W-3. Worktree作成

```bash
# ブランチ名: todo/{todo_id}（例: todo/T318）
git worktree add ./worktrees/todo-{todo_id} -b todo/{todo_id}
```

以降の全作業は **worktree内** で行う:
```bash
cd ./worktrees/todo-{todo_id}
```

### W-4. Worktree内の依存関係セットアップ

```bash
cd ./worktrees/todo-{todo_id} && uv sync
```

---

## Phase A: 実装 & Codex実装レビュー合議

### A-1. 実装

詳細設計書に従い、コードを実装する。

**重要**: 全ファイルパスはworktreeのルート（`./worktrees/todo-{todo_id}/`）基準で操作する。

**実装ルール**:
1. 施策ごとに順番に実装（依存関係がある場合は先行施策から）
2. **プリミティブ（`primitives.py`）を変更・追加する施策は、実装前後に `docs/alpha-factory/primitives.md`「ルックアヘッドバイアスチェック」7項目 + 「パフォーマンスチェック」4項目を全パス確認すること**。チェック結果をコミットメッセージまたはRunレポートに記録する
3. **各施策には必ずテストを書く**（テストのない施策は実装完了とみなさない）
   - ロジック変更 → 単体テストで Before/After を検証
   - パラメータ範囲変更 → 境界値テスト
   - 新機能追加 → 正常系・異常系テスト
   - **テスト命名・配置ルール**（AGENTS.md準拠）:
     - テスト名は**振る舞いを説明する汎用的な名前**にする
     - Run名・日付・セッション固有の識別子をテスト名に含めない
     - テストは対象モジュールに対応するテストファイルに配置する
     - 既存のテストファイルがあればそこに追加する
4. 各施策の実装後に `cd ./worktrees/todo-{todo_id} && uv run pytest tests/alpha_factory/` を実行してテスト通過を確認
5. **テストが失敗した場合はテスト駆動で修正**:
   - まずエラーを再現する最小テストケースを書く
   - テストがFAILすることを確認
   - コードを修正してテストがPASSすることを確認
6. 全施策の実装完了後に全テスト実行: `cd ./worktrees/todo-{todo_id} && uv run pytest tests/alpha_factory/ -x`

### A-2. Codexによる実装レビュー

**`--skip-consensus` 時は A-2/A-3 をスキップ**。テスト全通過をもって実装完了とみなし、Phase B へ進む。

全施策の実装完了・テスト通過後、git diffでコード差分を取得し、Codexにレビューを依頼する。

**差分の取得**（worktree内で実行）:
```bash
cd ./worktrees/todo-{todo_id}
git add -N src/trading/alpha_factory/ tests/alpha_factory/
git diff HEAD --no-color -- src/trading/alpha_factory/ tests/alpha_factory/
```

`zenigame-codex-review` スキルの**セッションモード**に従い、プロンプトファイルを作成してCodexに依頼する（レビューループのため文脈維持）。

**model**: `gpt-5.3-codex`
**reasoning**: `high`
**label**: `impl-review`

使命・禁止事項は zenigame-codex-review により自動挿入。system部には役割・タスク固有の指示のみ記載。

- **system**: コードレビュアーとしてAlpha Factoryの改善実装をレビュー。レビュー観点（設計との一致性、正確性、パフォーマンス、一貫性、テスト網羅性）、出力形式（ファイルごとに判定、Critical/Warning/Suggestion分類、全体判定APPROVED/CHANGES_REQUESTED）を含める（禁止事項は自動挿入済みのため個別チェック指示は不要）
- **転記漏れ・伝搬漏れ・記録漏れの重点チェック**:
  - config→GAConfig→genome.meta→parser/selection/fitnessの全伝搬チェーン
  - StageResult→genome.meta→genome_archiveの全フィールド転記
  - GENOMES_SCHEMAの全カラムに書き込みコードがあるか
  - enforce_consistency/mutate/crossoverの全呼び出し箇所で引数が揃っているか
  - 新規カラム追加時はスキーマ定義+初期値+書き込み+読み取りの4点セットを確認
  - **値を書き込む全箇所にlogger.debug/infoを追加すること**
- **user**: `## 詳細設計書\n{detailed-design.md}\n\n## 実装差分（git diff）\n{diff出力}\n\n## テスト結果\n{pytest出力サマリー}`

### A-3. 実装レビュー合議ループ

1. **[Critical]** は必ず修正
2. **[Warning]** は検討して対応
3. 修正後に再度テスト実行
4. 修正差分を再度Codexに送信

**合議終了条件**: Codexの全体判定が **APPROVED** になるまで。最大3ラウンド。

**セッション再開**: `zenigame-codex-review` スキルのセッションモード（Round N）に従い、同じ SESSION_ID で `codex-vscode exec resume` を実行する。Round 2以降のプロンプトには修正差分のみ記載（使命・禁止事項の再挿入は不要）。

レビュー結果を保存:
```
{tmp_dir}/impl-review-round-{N}.md
```

### A-4. ユーザー報告

```
## Phase A 完了: 実装 & レビュー

### 実装完了
- ブランチ: todo/{todo_id}
- 変更ファイル: N files
- テスト: XXX passed, 0 failed

### Codex実装レビュー: APPROVED (Round {N})

→ Phase Bに進みます（コミット & ドキュメント更新）
```

---

## Phase B: ドキュメント更新 & コミット（worktree内）

### B-1. ドキュメント更新

以下のドキュメントを**worktree内で**更新する:

#### `docs/alpha-factory.md` — メインドキュメント

更新箇所（明示的に指定）:

1. **パラメータ説明**（変更があった場合）
   - 変更されたパラメータの説明を更新

2. **新機能セクション**（新機能を追加した場合）
   - 新しいサブセクションを追加

> **注意**: Run履歴テーブルへの行追加はRUN実行後に行う（このスキルでは行わない）。

#### `docs/alpha-factory/primitives.md` — プリミティブ変更がある場合

- 新規プリミティブの仕様追記
- 変更されたプリミティブの更新

#### その他

- 施策内容に応じて関連ドキュメントを更新

### B-2. コミット（worktree内）

Phase Aの実装・テスト変更とPhase B-1のドキュメント更新をまとめてコミットする。

```bash
cd ./worktrees/todo-{todo_id}
git add src/trading/alpha_factory/ tests/alpha_factory/ docs/
git commit -m "$(cat <<'EOF'
feat: {todo_id} {施策タイトル}

施策:
- S1: {施策名}
- S2: {施策名}

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Phase C: TODOクローズ & mainマージ

### C-1. TODOクローズ

**`--skip-todo` 時はスキップ**。

**mainブランチに戻って**TODOクローズを実行する（TODO.mdはmainで管理）:

```bash
cd /Users/ishitoya/repository/zenigame  # mainに戻る
```

**`/zenigame-todo-close` スキルを呼び出す**:
```
/zenigame-todo-close {todo_id}
```

#### skip_todos の振り分け（improve-cycle経由時）

状態ファイルの `skip_todos` リストに記録されたTODO（実装スキップ）がある場合、**skip理由に応じて `/zenigame-todo-close` を呼び出して振り分ける**。

| reason に含まれるキーワード | アクション |
|---------------------------|----------|
| `superseded by` | `/zenigame-todo-close {id}` （Closedへ移動） |
| `design stale` / `陳腐化` / `re-design` / `post-run-review委任` | `/zenigame-todo-close {id} --action obsolete --reason "{reason}"` （Obsoletedへ移動） |
| 上記いずれにも該当しない | `/zenigame-todo-close {id} --action obsolete --reason "{reason}"` （デフォルトはObsoleted） |

**注意**: TODO.mdへの直接Edit操作は行わない。必ず `/zenigame-todo-close` スキル経由で操作する（ドキュメント所有権ルール）。

### C-2. mainへマージ

```bash
cd /Users/ishitoya/repository/zenigame
git merge todo/{todo_id} --no-ff -m "$(cat <<'EOF'
Merge branch 'todo/{todo_id}'

{todo_id}: {施策タイトル}

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
)"
```

### C-3. コンフリクト解消

マージでコンフリクトが発生した場合:

1. `git diff --name-only --diff-filter=U` でコンフリクトファイルを特定
2. 各ファイルのコンフリクトマーカー（`<<<<<<<`, `=======`, `>>>>>>>`）を確認
3. **解消方針**:
   - **同一関数内の変更**: 両方の変更を論理的に統合する。worktree側の新機能とmain側の変更を共存させる
   - **import文・テスト追加**: 通常は両方を保持（重複除去）
   - **設定値・パラメータ**: main側（より新しい）を優先し、worktree側の新規追加分を追加
   - **TODO.md等のドキュメント**: main側を優先（ドキュメント所有権ルール）
4. コンフリクト解消後にテストを実行して整合性を確認:
   ```bash
   uv run pytest tests/alpha_factory/ -x
   ```
5. テスト通過を確認してからコミット:
   ```bash
   git add -A
   git commit --no-edit
   ```
6. テストが失敗した場合:
   - コンフリクト解消の誤りを修正
   - 再度テスト実行 → 通過するまで繰り返す
   - 3回修正しても通らない場合はユーザーに報告

### C-4. Worktreeクリーンアップ

```bash
git worktree remove ./worktrees/todo-{todo_id}
git branch -d todo/{todo_id}
```

### C-5. 最終報告

```
## 実装完了: {todo_id} {施策タイトル}

### サマリー
- ブランチ: todo/{todo_id} → main にマージ済み
- 変更ファイル: N files
- テスト: XXX passed, 0 failed
- Codexレビュー: APPROVED / SKIPPED
- TODOクローズ: 完了 / スキップ
- コンフリクト: なし / 解消済み（N files）

### コミット
- 実装: {commit_hash}
- マージ: {merge_commit_hash}
```

---

## 状態ファイル更新

各ステップの開始・完了時に `.cache/alpha_factory/current_cycle_state.json` を更新する:

```json
{
  "skill": "implement",
  "phase": "{phase_W / phase_A / phase_B / phase_C}",
  "phase_detail": "{現在のステップ}",
  "todo_id": "{todo_id}",
  "tmp_dir": "{tmp_dir}",
  "worktree_path": "./worktrees/todo-{todo_id}",
  "worktree_branch": "todo/{todo_id}",
  "selected_todos": ["{todo_id}"],
  "skip_todos": [],
  "last_updated": "{ISO8601}"
}
```

---

## エラーハンドリング

### Codex CLIエラー
- `codex-vscode exec` が非ゼロ終了コードを返した場合、30秒待って1回リトライ
- 2回連続失敗でユーザーに報告しCodexなしで続行するか確認

### テスト失敗
- **テスト駆動で修正**する
- 3回修正しても通らない場合、ユーザーに報告

### Worktreeエラー
- ブランチ名が既に存在する場合: `git worktree remove` + `git branch -D` してから再作成
- worktree作成失敗: エラーメッセージを報告

### マージコンフリクト
- Phase C-3 のコンフリクト解消手順に従う
- 解消不能な場合はマージを中断（`git merge --abort`）してユーザーに報告

---

## 使用例

### 例1: standalone TODO実装
```
/zenigame-implement T318
```

### 例2: Codexレビューをスキップ
```
/zenigame-implement T318 --skip-consensus
```

### 例3: improve-cycleからの呼び出し（内部用）
```
/zenigame-implement T099 --tmp_dir devnotes/20260315-0200-alpha-improve
```
