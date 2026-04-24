---
name: zenigame-fx-plan-and-design
description: zenigame-fx Alpha Factory 改善の計画策定（TODO 選定 + Codex 合議 + 分析マージ + 改善策合議 + 詳細設計 + Codex レビュー）
argument-hint: "<tmp_dir> [run_id] [--repeat] [--skip-todo] [--skip-consensus]"
---

# zenigame-fx Alpha Factory 改善計画策定

`zenigame-fx-analyze-run` が出力する `{tmp_dir}/analysis-claude.md` / `{tmp_dir}/analysis-codex.md` を起点に、何をどう改善するかを決定し、Codex 承認済み詳細設計まで仕上げる。autopilot / improve-cycle の中核となる skill。

## 引数

| 引数 | 必須 | 説明 |
|------|------|------|
| `tmp_dir` ($1) | Yes | 中間成果物の保存先（`zenigame-fx-analyze-run` の出力先と同一） |
| `run_id` ($2) | No | 分析対象の run_id。状態ファイルから自動取得も可 |
| `--repeat` | No | 繰り返しモード（improve-cycle から渡される）。合議ループ上限を **5** に拡張（通常は 3） |
| `--skip-todo` | No | TODO 実装スキップ。Phase A 全体と Phase C-0 を skip。`selected_todos = []`, `cycle_focus = "ga_improvements"` 固定 |
| `--skip-consensus` | No | Codex 合議スキップ。Phase B-2/B-3、Phase C-2/C-3 を skip |

## 入力 / 出力一覧

**入力**:
- `{tmp_dir}/analysis-claude.md` — `zenigame-fx-analyze-run` の Claude 自己分析
- `{tmp_dir}/analysis-codex.md` — `zenigame-fx-analyze-run` の Codex 独立分析
- `docs/alpha_factory/TODO.md` — TODO バックログ（Open / Conditional テーブル）

**出力**:
- `{tmp_dir}/todo-selection-codex.md` — TODO 選定の Codex 合議結果
- `{tmp_dir}/analysis-merged.md` — 分析マージ結果
- `{tmp_dir}/improvement-plan.md` — 最終改善計画
- `{tmp_dir}/detailed-design.md` — Codex 承認済み詳細設計
- `{tmp_dir}/consensus-round-{N}.md` — 改善策合議ラウンド記録
- `{tmp_dir}/design-review-round-{N}.md` — 設計レビュー記録

**独立利用**: 部分的 — `zenigame-fx-analyze-run` の出力が前提だが、設計だけやり直すことも可能。

## 責務境界

**本 skill が行うこと**:
- 改善計画策定（analyze-run 結果から次サイクルの施策確定）
- Codex 合議（todo-selection / consensus / design-review）
- 詳細設計レビュー
- TODO 選定（Open テーブル中の incremental TODO の今サイクル採用判断）

**本 skill が行わないこと**:
- GA Run 実行（`scripts/alpha_factory/run_ga.py` は呼ばない）
- TODO の実装（`zenigame-fx-implement` の責務）
- 新規 TODO の登録（`zenigame-fx-todo-add` の責務）
- TODO のクローズ（`zenigame-fx-todo-close` の責務）
- 概念設計・詳細設計の **新規作成**（`zenigame-fx-alpha-design` の責務。本 skill は採用 TODO の既存設計を読み込んで詳細設計書に統合するのみ）

## 呼び出し契約

### 現契約（manual）
```
User → /zenigame-fx-plan-and-design <tmp_dir> [run_id]
/zenigame-fx-plan-and-design → /zenigame-fx-codex-review  (Codex 合議規約)
                              → /zenigame-fx-codex-vscode  (codex 呼び出し規約)
```

### 将来契約（別 follow-up TODO で接続）
```
/zenigame-fx-improve-cycle Phase 2.5 → /zenigame-fx-plan-and-design
/zenigame-fx-autopilot                → /zenigame-fx-plan-and-design
```

**重要**: 現状 `zenigame-fx-improve-cycle` / `zenigame-fx-autopilot` は本 skill を呼ばない。skill 経由切替は本 TODO 範囲外。

## 使命・思考原則・禁止事項

`zenigame-fx-codex-review` SKILL.md で定義される **使命・絶対制約・禁止事項・C1-C9 discipline・思考原則・ツール使用制限・レビュー重点項目** を継承し、本 skill 内では **重複記載しない**。継承先必須節:

- §「使命・禁止事項（全 Codex 呼び出しに自動適用）」
- §「One-shot モード」
- §「セッションモード（合議ループ用）」
- §「session_label の命名規則」（本 skill は `todo-selection` / `consensus` / `design-review` を使用）

継承先がこれらの節名 / 節構造を変える場合、本 skill も波及変更対象として同期更新する。

**FX 固有の絶対制約（再掲、各 Phase 判断基準で再登場）**:
- イントラデイ前提（オーバーナイト保有を前提にする設計は避ける）
- ロング・ショート両方向許容
- スワップ・スプレッドを fitness に反映（見かけの PnL ではなく純利益）

## 思考原則（codex-review 継承、要点のみ再掲）

**まず仮説を立てろ。データに真摯に向き合え。先人の知恵を探せ。機能の名前に立ち返れ。仕組みが機能していない段階で値を弄るな。因果ループを切断するな。**

## 状態ファイル更新責務

`.cache/alpha_factory/current_cycle_state.json` に対し、本 skill が **書き込む** key:

| key | 書き込みタイミング | 値 |
|-----|------------------|-----|
| `skill` | Phase 開始時 | `"plan-and-design"` |
| `phase` | 各 Phase 開始時 | `"phase_A"` / `"phase_B"` / `"phase_C"` |
| `phase_detail` | 各 Step 開始時 | 現在の Step 名 |
| `tmp_dir` | Phase A 開始時 | 引数 `tmp_dir` |
| `cycle_focus` | Phase A 完了時 | `"ga_improvements"` / `"todos"` / `"mixed"` |
| `selected_todos` | Phase A 完了時 | 採用 TODO ID リスト |
| `skip_todos` | Phase A 完了時 | `[{id, reason}]` |
| `merge_candidates` | Phase A 完了時 | `[{ids, note}]` |
| `deferred_analyses` | Phase B-1 完了時（standalone サイクル時のみ） | `analysis-merged.md` パスを append |
| `improvement_plan` | Phase B-4 完了時 | `improvement-plan.md` のパス |
| `detailed_design` | Phase C-3 完了時 | `detailed-design.md` のパス |
| `last_updated` | 各書き込み時 | ISO8601 |

**読むのみで書き込まない** key（`zenigame-fx-improve-cycle` 管理）: `cycle_index` / `run_number` / `next_run_number` / `overrides` / `history` / `repeat_mode` / `observe_only` / `started_at`。

## 合議ループ収束ルール（全 Codex 合議に共通適用）

各 Round の Codex プロンプト末尾に以下を必ず含める:

```
【ループ収束ルール】
本ラウンドで以下のいずれかに収束させること:
1. APPROVED（全 Critical / Warning 解消）
2. 1 つの反証可能仮説 + 1 つの最小変更に絞り込み「次 Run で検証」と申し送る

ループは通常 3 ラウンド / 繰り返しモード（--repeat）5 ラウンドで強制終了。
終了時に未解決項目があれば「保留事項」として improvement-plan.md / detailed-design.md に記録する。
```

合議が長文化して文書整合性最適化（mission 逸脱）に陥ることを防止する。

## focus-theme.json fallback

`config/alpha_factory/focus-theme.json` が **未存在の場合**:
- `focus_theme = "general"` / `focus_policy = null` で固定
- A-2 Codex プロンプトの「【最優先】フォーカステーマ」セクションは「（focus-theme 未設定。一般原則に従う）」に置換
- Phase A 選定基準 0（フォーカステーマ優先）はスキップし、選定基準 1-4 のみ適用

将来 `zenigame-fx-set-focus` skill 移植時も同パス（`config/alpha_factory/focus-theme.json`）を SSoT として運用する。

---

## Phase A: TODO 選定 & Codex 議論

**`--skip-todo` 時は Phase A 全体をスキップ**して Phase B へ。`selected_todos = []`, `skip_todos = []`, `cycle_focus = "ga_improvements"` で固定。

### A-1. TODO リストの確認と選定

**Emergency Fix モード**（状態ファイル `emergency_fix.detected == true`）の場合: Phase A 全体を**スキップ**して Phase B へ。バグ修正が唯一の施策のため。

`scripts/alpha_factory/todo_manager.py` で Open / Conditional テーブルを取得:

```bash
open_table=$(uv run python scripts/alpha_factory/todo_manager.py list)
```

`list` subcommand は Open / Conditional 両方を返す。Conditional セクションは出力テキストから抽出する。

**TODO が 1 件もない場合**: Phase A をスキップして Phase B へ。

**TODO がある場合**: 選定の前に **滞留 TODO の棚卸し** を行う。

#### 滞留 TODO 判断

Open TODO の追加日時を確認し、Closed テーブル直近 5 件の完了日時と比較する（`docs/alpha_factory/TODO-closed.md` を Read）。直近 5 件の完了日時よりも追加日時が古い TODO は複数 Run にわたって実装されずに滞留している。

滞留 TODO ごとに概念設計を Read して以下を判断:

| 判断 | 条件 | アクション |
|------|------|----------|
| **優先度を上げて実装** | 問題が依然として存在し、設計も概ね有効 | 今回の選定で優先採用 |
| **post-run-review に委ねる** | 設計が古く現コードと乖離している可能性が高い | 今回の選定から除外、post-run-review の再評価を待つ <!-- TODO(post-run-review-port): zenigame-fx-post-run-review 整備後に「再評価で post-run-review 起動」を接続。現時点では no-op、保留扱い --> |

判断結果を `analysis-claude.md` に追記:
```markdown
## 滞留 TODO 判断
| ID | タイトル | 追加日時 | 滞留 Run 数 | 判断 | 理由 |
|----|---------|--------|----------|------|------|
```

#### Conditional 自動昇格チェック

棚卸し後、Conditional テーブルのトリガー条件を評価する。

```bash
# list 出力から Conditional セクションを抽出
conditional_table=$(uv run python scripts/alpha_factory/todo_manager.py list)
```

**Conditional が 0 件**: スキップ。

**Conditional がある場合**: 各項目のトリガー条件を直近 Run 結果（`analysis-claude.md`, `analysis-codex.md`）から評価。

| 評価結果 | アクション |
|---------|----------|
| **条件成立** | 手動で TODO.md の Conditional → Open 移動を案内（自動昇格 subcommand は未提供）。昇格項目は今回の選定候補に含める |
| **条件未成立** | 何もしない（次サイクルで再評価） |
| **条件が陳腐化** | `obsolete` で廃止 |

```bash
# 条件成立時の昇格案内
echo "Conditional TODO {id} のトリガー条件成立。"
echo "TODO.md を編集し Open テーブルへ移動してください（次回の todo_manager.py 拡張で自動化予定）。"

# 陳腐化時
uv run python scripts/alpha_factory/todo_manager.py obsolete "{todo_id}" \
  --obsoleted-at "$(TZ=Asia/Tokyo date '+%Y-%m-%d %H:%M')" \
  --reason "trigger stale in plan-and-design"
```

昇格結果を `analysis-claude.md` に追記:
```markdown
## Conditional 昇格チェック
| ID | タイトル | トリガー条件 | 評価結果 | 理由 |
|----|---------|-------------|---------|------|
```

#### standalone タスクの確認（最優先）

Open テーブルに `standalone` モードのタスクが **1 件でも存在する場合**:
- 優先度が最も高い `standalone` タスクを **1 件だけ** 選定
- `incremental` タスクは今回のサイクルでは選定しない（混在禁止）
- Phase B-1（分析マージ）は通常通り実行
- B-1 完了後、`analysis-merged.md` のパスを状態ファイルの `deferred_analyses` リストに追記
- Phase B-2/B-3（改善策合議）は「詳細設計に問題がないか」の最終確認のみ
- Phase C 以降は TODO 由来の詳細設計を直接使用

#### incremental 選定基準（standalone が 0 件の場合）

最大 3 件を選定:

0. **フォーカステーマ優先**: `config/alpha_factory/focus-theme.json` のテーマに該当する TODO を最優先（不在時は §focus-theme fallback）
1. **モード**: `incremental` のみ
2. **優先度**: Critical → High → Medium → Low
3. **関連性**: 直近 Run 分析で浮かび上がったボトルネックと同一コンポーネント
4. **競合なし**: GA 分析由来の改善施策と同一ファイル・同一関数を変更しない

#### 候補の必須記入欄（mission-facing）

選定候補ごとに以下を `analysis-claude.md` に必ず記入する:

| 必須項目 | 内容 |
|---------|------|
| `target_metric` | live_criteria のどの項目（Sharpe / Total PnL / Max Drawdown / Trade Count / Cross-pair ii-lite）の改善を狙うか |
| `failure_mode` | 直近 Run の analyze-claude / analyze-codex で観測された未達症状 |
| `causal_path` | 仮説する因果経路 |
| `falsification` | 無効と判断する観測条件（C9 falsification-first） |
| `success_criterion` | 有効と判断する次 Run での観測条件 |

選定したTODOの詳細設計ファイルを `Read`（各候補 TODO の「詳細設計」列のリンク先）。

選定結果を `analysis-claude.md` 末尾に追記:

```markdown
## TODO 由来の改善候補

| ID | タイトル | 優先度 | target_metric | failure_mode | causal_path | falsification | success_criterion | 判定 | 理由 |
|----|---------|--------|--------------|-------------|------------|---------------|-------------------|------|------|
```

**状態ファイル更新（仮）**: `selected_todos` に候補リストを記録。

### A-2. Codex と実装候補を議論

**トリガー**: Open TODO が 1 件以上。0 件はスキップ。

`zenigame-fx-codex-review` の **One-shot モード** に従い、プロンプトファイルを作成して Codex に依頼。

**model**: `gpt-5.3-codex`
**reasoning**: `medium`
**label**: `todo-selection`

使命・禁止事項は `zenigame-fx-codex-review` により自動挿入される（重複記載なし）。

**system**:
```
あなたは zenigame-fx Alpha Factory の GA 改善を支援する Codex です。最新の Run 分析結果と TODO リスト全体を踏まえて、今回の改善サイクルで実装すべき施策を議論してください。

（使命・禁止事項・C1-C9 は zenigame-fx-codex-review により自動挿入済み）

【FX 固有の絶対制約 — 各判断で再確認】
- イントラデイ前提
- ロング・ショート両方向許容
- スワップ・スプレッドを fitness に反映（見かけの PnL ではなく純利益）

【rejection rule（禁止事項に基づく即 REJECT）】
- 取引回数を削減して見かけ成績を上げる施策（禁止事項 6）
- 評価期間延長で過学習を隠す施策（禁止事項 1）
- live_criteria を緩和してステージを飛ばす施策（禁止事項 4）
- 見た目の数値だけ良くする施策（禁止事項 2）
- オーバーナイト保有前提の設計（禁止事項 7）
- ショート追加で見かけだけ改善している兆候があれば指摘（FX で許容されているが、コスト控除後の純利益で評価）

【判断基準 — 実装候補選定】
0. 【最優先】フォーカステーマ「{focus_theme}」の TODO（focus-theme 未設定時は「（一般原則に従う）」）
{focus_policy が null でない場合: 【フォーカスポリシー】「{focus_policy}」}
1. 今回の Run 分析で浮かび上がった問題に直接対処する TODO を優先
2. Run 由来の改善施策と競合しない TODO を選ぶ
3. 1 サイクルで並走可能な TODO 数（最大 3 件）を守る
4. 優先度を尊重しつつ、Run 文脈との関連性も考慮

【メタ過学習ガード — GA ハイパーパラメータ変更の分類（必須）】
default.yaml の date_pool は限定された期間。同一データに対するハイパーパラメータの繰り返し調整はメタ過学習。
GA ハイパーパラメータの数値変更を推薦する場合、各施策に分類を明記:
- Structural: 新機能 / 新ガードの追加 → APPROVE 可
- Principled Parametric: 理論に基づく数値設定（根拠明示必須） → APPROVE 可
- Reactive Parametric: 「直近 Run で X が悪かったから Y を調整」→ 原則 REJECT、構造的対策に変換を促す

【分析観点 — TODO 全体の関係整理】
1. 重複・統合候補
2. 陳腐化（解決済み / 不要になった Open TODO）
3. 依存スキップ（A 実装で B 不要化）
4. 相性（並走相乗効果 or 相性悪い組み合わせ）

【出力形式】
- Section A: 実装候補の判定（各候補に target_metric / failure_mode / causal_path / falsification / success_criterion を再確認、APPROVE / MODIFY / REJECT）
- Section B: TODO 全体の関係分析
- Section C: 総合推薦
- Section D: TODO vs GA 改善のバランス判断（ga_improvements / todos / mixed）

日本語で出力。

【ループ収束ルール】
本ラウンドで APPROVED または「1 つの反証可能仮説 + 1 つの最小変更」に絞り込むこと。
ループは通常 3 / 繰り返し 5 ラウンドで強制終了。未解決は保留事項として improvement-plan.md に記録。
```

**user**:
```
## 最新 Run 分析サマリー
{analysis-claude.md の「観察事実」「解釈」「次サイクル候補」セクション}

## 論理バグ探索結果
{analyze-run で発見したバグ候補、または「疑わしい箇所なし」}

## 最近クローズされた TODO（直近 5 件）
{TODO-closed.md の Closed テーブル末尾 5 行}

## Open TODO 全件
{TODO.md の Open テーブル全体}

## Conditional TODO 全件
{TODO.md の Conditional テーブル全体（0 件の場合は「なし」）}

## 候補として選定した TODO の詳細設計サマリー
{各候補 TODO の詳細設計ファイルから「目的」「変更内容の概要」「期待効果」を抜粋}

## 質問
### A. 実装候補の確定（target_metric / failure_mode / causal_path / falsification / success_criterion 含む）
### B. TODO 全体の関係分析
### C. 総合推薦
### D. TODO vs GA 改善のバランス判断
```

#### 合議結果の反映

| Codex の判定 | 対応 |
|-------------|------|
| 今回実装を推薦 | `selected_todos` に追加 |
| 次回以降を推薦 | 理由を精査。同意すれば見送り |
| Run 問題と競合 | 見送り |
| 廃止推薦（陳腐化） | `skip_todos` に `{id, reason: "design stale: {詳細}"}` 形式で追加 |
| 統合推薦 | `merge_candidates` に `{ids, note}` で追加 |
| 依存スキップ | `skip_todos` に `{id, reason: "superseded by {他 ID}"}` で追加 |

Section D の結果を反映:

| Codex 推薦 | 対応 |
|-----------|------|
| `ga_improvements` | `selected_todos` を空にし、GA 分析由来の改善のみで計画 |
| `todos` | 改善計画を最小化し、TODO 実装を中心に |
| `mixed` | 両方を組み合わせる（合計 3 件以内） |

`cycle_focus` を状態ファイルに記録。Codex の議論結果を `{tmp_dir}/todo-selection-codex.md` に保存。

---

## Phase B: 分析マージ & 改善策合議

### B-1. 分析結果のマージ

`analysis-claude.md` と `analysis-codex.md` を読み込み、以下を統合:

1. **共通する発見**: 両者が一致している問題点 → 高確度
2. **独自の発見**: 片方のみ指摘した問題点 → 検証要
3. **矛盾する見解**: 異なる結論が出た点 → 合議で解決

マージ結果を `{tmp_dir}/analysis-merged.md` に保存。

**standalone サイクルの場合**: `analysis-merged.md` 作成後、状態ファイルの `deferred_analyses` リストにこのパスを追記（append）。

フォーマット:
```markdown
# マージ分析: Run {N}

## 合意事項（両者一致）
## Claude 独自の発見
## Codex 独自の発見
## 矛盾・要議論
## 統合改善提案（優先度順）
| # | 提案 | 優先度 | 出所 | target_metric | failure_mode | 期待効果 |
|---|------|--------|------|--------------|-------------|---------|
```

### B-2. Codex と改善策の合議

**`--skip-consensus` 時は B-2 / B-3 / B-4 をスキップ**。B-1 のマージ結果から Claude 単独で改善計画を確定し、`improvement-plan.md` を直接作成して Phase C へ。

`zenigame-fx-codex-review` の **セッションモード** に従い、プロンプトファイルを作成。

**model**: `gpt-5.3-codex`
**reasoning**: `medium`
**label**: `consensus`

**system**:
```
あなたは zenigame-fx Alpha Factory の改善について Claude と合議している Codex です。以下のマージ分析に基づいて、最終的な改善計画を策定してください。

（使命・禁止事項・C1-C9 は zenigame-fx-codex-review により自動挿入済み）

【FX 固有の絶対制約 — 各判断で再確認】
- イントラデイ前提
- ロング・ショート両方向許容
- スワップ・スプレッドを fitness に反映

【rejection rule（禁止事項に基づく即 REJECT）】
- 禁止事項 1（期間延長）/ 2（見栄え改善）/ 4（live_criteria 緩和）/ 6（取引回数削減）/ 7（オーバーナイト）
- ショート追加で見かけだけ改善していないか点検

【improve-cycle の守備範囲】
- TODO 消化、GA パラメータ軽量調整、バグ修正
- GA 設定変更ルール（AGENTS.md / config/alpha_factory/default.yaml 厳守）
- プリミティブ新規設計・大幅改良は post-run-review 担当（未移植：当面は本 skill から提案のみ、実装は別レーン）

【メタ過学習ガード — GA ハイパーパラメータ変更の分類（必須）】
date_pool は限定された期間。同じデータに対してハイパーパラメータを繰り返し調整するのはメタ過学習。
GA ハイパーパラメータ（regime_penalty_weight 等の数値）を変更する施策には以下分類を必ず明記:

| 分類 | 定義 | 判定 |
|------|------|------|
| Structural | 新機能・新ガード・新プリミティブの追加 | APPROVE 可 |
| Principled Parametric | 一般原則・理論に基づく数値設定（根拠明示） | APPROVE 可 |
| Reactive Parametric | 「直近 Run で X が悪かったから Y を調整」 | 原則 REJECT、構造的対策に変換を促す |

Reactive 例: 「Run N で月次 Sharpe バラつきが大きい → regime_penalty_weight 0.5→1.0」— 同じデータへの当てはめ。代わりに「なぜバラつきが大きいか」の構造的原因（特定 primitive の季節依存性、データカバレッジ不足等）に対処する施策を推薦。

【合議ルール】
- 各提案に APPROVE / MODIFY / REJECT で判定
- MODIFY は具体的な修正案を提示
- REJECT は理由を明記
- 各提案に target_metric / failure_mode / causal_path / falsification / success_criterion を必須化
- 日本語で出力

【ループ収束ルール】
本ラウンドで APPROVED または「1 つの反証可能仮説 + 1 つの最小変更」に絞り込むこと。
ループは通常 3 / 繰り返し 5 ラウンドで強制終了。未解決は保留事項として improvement-plan.md に記録。
```

**user**: マージ分析の内容

### B-3. 合議ループ

Codex の回答を精査し以下を繰り返す。**セッション再開**: `zenigame-fx-codex-review` のセッションモード（Round N）に従い、同じ SESSION_ID で `scripts/codex exec resume` を実行。Round 2 以降のプロンプトには対応内容・修正案のみ記載（使命・禁止事項の再挿入は不要）。

1. Codex の判定に **同意** する項目はそのまま採用
2. **異議がある** 項目は根拠を添えて再議論
3. **全提案の判定が確定するまで** ループ（通常: 最大 3 / 繰り返し: 最大 5）
4. **各イテレーションで使命チェック**: 使命から逸脱した提案は即座に REJECT

各ラウンドの会話を `{tmp_dir}/consensus-round-{N}.md` に保存。

### B-4. 最終改善計画の確定

合議結果を `{tmp_dir}/improvement-plan.md` に保存。

フォーマット:
```markdown
# 最終改善計画: Run {N} → Run {N+1}

## 合議ステータス: CONSENSUS REACHED (Round {N})  または  PARTIAL（保留事項あり）

## 確定施策一覧
| # | 施策名 | 内容 | 変更対象 | 優先度 | 変更分類 | target_metric | failure_mode | causal_path | falsification | success_criterion | 合議結果 |
|---|--------|------|---------|--------|---------|--------------|-------------|------------|---------------|-------------------|---------|

## 却下された提案
| # | 提案 | 却下理由 |
|---|------|---------|

## 保留事項（合議収束ルールにより次 Run 検証申し送り）
| # | 仮説 | 最小変更案 | 検証条件 |
|---|------|----------|---------|

## 次フェーズへの申し送り
```

**使命・禁止事項チェック**: 最終改善計画の確定前に、全施策が使命・禁止事項に違反していないか精査。

### B-5. ユーザー報告

```
## Phase B 完了: 改善策合議

### 確定施策
1. [施策名] - [概要]（合議: APPROVED）

### 却下された提案

### 保留事項

→ Phase C に進みます（詳細設計 & Codex レビュー）
```

---

## Phase C: 詳細設計 & Codex レビュー合議

### C-0. TODO 由来施策の詳細設計読み込み

**`--skip-todo` 時はスキップ**（`selected_todos` は空のため）。

`selected_todos` に記録された採用 TODO がある場合に実行。0 件ならスキップ。

採用 TODO ごとに:

1. `docs/alpha_factory/TODO.md` の当該行から「詳細設計」リンク先を取得
2. `Read` ツールで詳細設計ファイルを読み込む
3. 変更対象ファイルと変更内容の概要を把握
4. 変更対象ファイルを `Read` して現行コードと整合性を確認

#### 競合チェック

- Phase B で確定した GA 分析由来の施策と同一ファイル・同一関数を変更する場合は「競合あり」として報告
- 競合がある場合、TODO 施策の組み込みを見送り、`improvement-plan.md` にコメント記録

整合性が確認できた TODO 由来施策は、C-1 の詳細設計書に組み込む:
- 施策番号を `T{todo_id}` プレフィックスで区別
- 既存の詳細設計ファイルをそのまま転記
- C-2 の Codex レビュー対象に含める

### C-1. 詳細設計書の作成

`improvement-plan.md` の確定施策に基づき、詳細設計書を作成。各施策について以下を記載:

- **変更ファイルと行番号**: 具体的な変更箇所
- **Before/After**: 変更前後のコード
- **テスト計画**: 既存テストへの影響と追加テスト
- **リスク**: 副作用・後退の可能性

> **波及変更チェック（必須）**: インターフェース変更（GA 引数 / CLI オプション / 公開 API）が発生する場合、`AGENTS.md` および `.claude/skills/zenigame-fx-*/SKILL.md` も変更対象として施策に明示すること。

保存先: `{tmp_dir}/detailed-design.md`

フォーマット:
```markdown
# 詳細設計: Run {N+1} 施策

## 使命・制約（絶対遵守）
（codex-review 継承の宣言、FX 固有制約のみ再掲）

## 施策一覧
| # | 施策名 | 変更ファイル | target_metric |
|---|--------|------------|--------------|

## C1: {施策名}

### target_metric / failure_mode / causal_path / falsification / success_criterion

### 変更箇所
### 波及変更（AGENTS.md / skill / config / docs）
### 現行コード
### 変更後コード
### ルックアヘッドバイアスチェック（primitive 変更時は必須）
- [ ] 未来バー参照なし
- [ ] 当日確定値の先取りなし
- [ ] rolling window 方向が過去方向
- [ ] 正規化にローカル window or rolling 関数を使用
- [ ] バケット / グループ平均が因果的
- [ ] cumsum/accumulate が因果的方向

### パフォーマンスチェック（primitive 変更時は必須）
- [ ] compute_all_bars() 実装
- [ ] 内側ループ内で NumPy 関数を呼んでいない
- [ ] SoA プロパティ使用
- [ ] 同一配列のキャッシュ

### テスト計画
- [ ] バグ修正なら再現テストを先に書く
- [ ] 既存テスト更新
- [ ] 新規テスト: {テスト名} — {検証内容}

### リスク

## Run {N+1} 実行パラメータ
| パラメータ | 値 | R{N} からの変更 |
|-----------|-----|--------------|
```

### C-2. Codex による詳細設計レビュー

**`--skip-consensus` 時は C-2 / C-3 をスキップ**。C-1 の詳細設計書をそのまま最終版として確定し、Phase C-4 へ。

`zenigame-fx-codex-review` の **セッションモード** に従い、プロンプトファイルを作成。

**model**: `gpt-5.3-codex`
**reasoning**: `high`
**label**: `design-review`

**system**:
```
あなたは経験豊富なクオンツ・システムアーキテクトです。zenigame-fx Alpha Factory 改善の詳細設計をレビューしてください。

（使命・禁止事項・C1-C9 は zenigame-fx-codex-review により自動挿入済み）

【前提環境】
- Python 3.13 + numpy + pandas + multiprocessing
- FX イントラデイ戦略の GA 最適化
- DSL ベースの戦略表現: Clause ベース合成（directional × local_gate × weight）
- 実行環境: macOS, 24GB メモリ, 6 ワーカー並列(1 ワーカー約 3GB）
- 通貨ペア: AUD_JPY, EUR_JPY, USD_JPY, EUR_USD, USD_CAD, USD_ZAR

【FX 固有の絶対制約 — 各判断で再確認】
- イントラデイ前提
- ロング・ショート両方向許容
- スワップ・スプレッドを fitness に反映

【レビュー観点】
1. コードの正確性（ロジックエラー、エッジケース、off-by-one、NaN 伝播）
2. 既存コードとの整合性
3. パフォーマンスへの影響
4. テスト計画の網羅性
5. 副作用・後退リスク
6. 考慮漏れ
7. 波及変更の網羅性（AGENTS.md / skill / config / docs）
8. ルックアヘッドバイアス（primitive 変更時必須）
9. メモリ制約（24GB / 6 ワーカー / 1 ワーカー 3GB）
10. パフォーマンス（compute_all_bars / SoA / キャッシュ）
11. 前提検証 (C4)
12. 並行計算経路の確認 (C2)
13. 相関・予測 claim の collider bias (C3 / C7)

【出力形式】
- 各施策ごとに判定: APPROVE / REQUEST_CHANGES / INCONCLUSIVE (C8)
- 指摘は [Critical] [Warning] [Suggestion]
- Critical/Warning には修正案
- 全体判定: APPROVED / CHANGES_REQUESTED / INCONCLUSIVE
- 日本語

【ループ収束ルール】
本ラウンドで APPROVED または「1 つの反証可能仮説 + 1 つの最小変更」に絞り込むこと。
ループは通常 3 / 繰り返し 5 ラウンドで強制終了。未解決は保留事項として detailed-design.md に記録。
```

**user**: 詳細設計書の内容 + 関連する現行コードの抜粋

### C-3. レビュー合議ループ

セッション再開で `scripts/codex exec resume` を実行。

1. **[Critical]** は必ず対応
2. **[Warning]** は対応を検討
3. **[Suggestion]** は任意で採用

対応マトリクス:
```markdown
| # | 指摘 | 重要度 | 対応 | 詳細 |
|---|------|--------|------|------|
```

各イテレーションで使命チェック。合議終了条件: 全体判定 APPROVED（Critical/Warning = 0）または収束ルールでの強制終結。通常: 最大 3、繰り返し: 最大 5。

各ラウンドの結果: `{tmp_dir}/design-review-round-{N}.md`
最終確定版を上書き: `{tmp_dir}/detailed-design.md`

**使命・禁止事項の最終チェック**: 最終確定版の設計全体が使命・禁止事項に違反していないか精査。

### C-4. ユーザー報告

```
## Phase C 完了: 詳細設計合議

### 合議結果: APPROVED (Round {N})  または  PARTIAL（保留事項あり）

### 施策一覧
1. C1: [施策名] - [変更ファイル]

### Codex からの主要指摘と対応

### 保留事項

→ 詳細設計が確定しました。/zenigame-fx-implement で実装に進みます。
```

---

## エラーハンドリング

### Codex CLI エラー

`zenigame-fx-codex-review` のエラーハンドリング規定に従う:
- `scripts/codex exec` / `exec resume` が非ゼロ終了 → 30 秒待って 1 回リトライ
- 通常モード: 2 回連続失敗でユーザーに報告し Codex なしで続行するか確認
- 繰り返しモード: 2 回連続失敗で自動で Codex なしで続行

セッションモード固有:
- Round 1 失敗時はリトライで新規セッション作成（SESSION_ID 更新）
- Round N (N≥2) 失敗時は同じ SESSION_ID でリトライ
- SESSION_ID 取得失敗時は one-shot モードへフォールバック

### TODO.md 不在 / 形式不正

Phase A をスキップし `cycle_focus = "ga_improvements"` で続行、ユーザーに警告。

### analysis-claude.md / analysis-codex.md 不在

`zenigame-fx-analyze-run` を実行するよう案内し、本 skill を停止。

---

## 未接続 hook（整備後に起動）

| hook | 本 skill での扱い | 不在時挙動 | 整備後の接続点 |
|------|------------------|----------|--------------|
| `zenigame-fx-post-run-review` | A-1 滞留 TODO 棚卸しの「post-run-review に委ねる」分岐 / Phase D 後段の自動起動 | **no-op、成果物要求なし** | A-1 で `Read` 可能になり次第、滞留 TODO の再評価を委譲 |
| `zenigame-fx-alpha-sieve` | cycle_focus 判定や次サイクル候補列挙での参照 | **no-op、成果物要求なし** | 整備後、Phase B-1 のマージで OOS 検証結果を取り込み |
| `zenigame-fx-set-focus` | `config/alpha_factory/focus-theme.json` の更新 | **no-op**、§focus-theme fallback 適用 | 整備後、focus-theme JSON が SSoT として運用される |

`zenigame-fx-improve-cycle` / `zenigame-fx-autopilot` 側は **未移植 hook の成果物を期待しない** 設計（unblock）。

---

## 使用例

### 例 1: 通常呼び出し（manual、analyze-run 完了後）
```
/zenigame-fx-plan-and-design devnotes/20260424-1138-fx-improve
```

### 例 2: run_id 明示（特定 Run の分析からやり直し）
```
/zenigame-fx-plan-and-design devnotes/20260424-1138-fx-improve run_20260424_093015
```

### 例 3: TODO 選定スキップ（GA 改善のみで計画）
```
/zenigame-fx-plan-and-design devnotes/20260424-1138-fx-improve --skip-todo
```

### 例 4: Codex 合議スキップ（高速モード、品質ゲートなし）
```
/zenigame-fx-plan-and-design devnotes/20260424-1138-fx-improve --skip-consensus
```

### 例 5: 繰り返しモード（improve-cycle から、合議ループ上限 5）
```
/zenigame-fx-plan-and-design devnotes/20260424-1138-fx-improve --repeat
```
