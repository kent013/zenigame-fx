# 詳細設計: zenigame-fx-improve-cycle full version (Phase 2 architecture)

## 変更対象

`.claude/skills/zenigame-fx-improve-cycle/SKILL.md` を **完全書き換え**（既存 214 行の縮小版を破棄、約 500 行の full orchestrator に rewrite）。

## 最終 SKILL.md 草案

```markdown
---
name: zenigame-fx-improve-cycle
description: zenigame-fx Alpha Factory 改善サイクル（analyze → plan-and-design → implement → run → report）のオーケストレータ。Phase 2 architecture（Stage A/B/C / GenomeArchive / cross-pair shadow / swim-lane / 32 primitive）対応 full version
argument-hint: "[run_id] [--repeat] [--max-cycles N] [--skip-todo] [--skip-consensus] [--observe-only] [run_args...]"
---

# zenigame-fx Alpha Factory 改善サイクル（オーケストレータ）

Workflow skill を順次呼び出して、前 Run の分析 → 計画 → 実装 → RUN 実行 → レポート生成の全フローを自動化する。

**自身では Codex 呼び出し・ファイル実装・TODO 操作・GA 実行を一切行わない。** 調整・状態管理・エラーハンドリング・ユーザー報告のみを担当する。

```
zenigame-fx-improve-cycle (orchestrator)
│
├─ Step 0: 初期化（tmp_dir / run_id / run_number / state file）
│   bootstrap 分岐: archive Parquet 0 件なら Phase 1/2/3 を skip し Phase 4→5 で初回 SoT Run を生成
│
├─ Phase 1: /zenigame-fx-analyze-run {run_id} --tmp_dir {tmp_dir}
│   → analysis-claude.md, analysis-codex.md
│   <!-- TODO(post-run-review-port): zenigame-fx-post-run-review 整備後に BG 起動を追加。現時点では no-op -->
│
├─ [Phase 1.5 未移植] IC Sync
│   <!-- TODO(primitive-ic-port): FX には primitive-ic 未整備。整備後に zenigame-fx-primitive-ic-sync を接続 -->
│
├─ [--observe-only でない場合]
│   ├─ Phase 2: /zenigame-fx-plan-and-design {tmp_dir} {run_id} {--repeat} {--skip-todo} {--skip-consensus}
│   │   → improvement-plan.md, detailed-design.md
│   │
│   ├─ [Phase 2.5 未移植] Calibrate Gate
│   │   <!-- TODO(calibrate-gate-port): zenigame-fx-calibrate-gate 整備後に接続 -->
│   │
│   ├─ Phase 3: /zenigame-fx-implement {todo_id} --tmp_dir {tmp_dir} {--skip-consensus}（selected_todos ごと）
│   │
│   ├─ Phase 4: /zenigame-fx-run-alpha-factory {run_args}
│   │   → run-alpha-factory state + summary.json から SoT 取り直し
│   │
│   └─ Phase 5: /zenigame-fx-run-report {run_number} --analysis-dir {tmp_dir}
│       (run_number は Phase 4 完了後に取り直した SoT を使用)
│
├─ [--observe-only の場合]
│   ├─ Emergency Fix 検出時のみ: バグ修正 → テスト → コミット
│   ├─ Phase 4: /zenigame-fx-run-alpha-factory
│   └─ Phase 5: /zenigame-fx-run-report
│
├─ [Phase 5.5 未移植] Alpha Sieve 評価
│   <!-- TODO(alpha-sieve-port): zenigame-fx-alpha-sieve 整備後に接続 -->
│
└─ Phase 6: 繰り返し判定 → --repeat & --max-cycles 未達 → state リセット → Phase 1 へ
```

---

## 引数

| 引数 | 必須 | 説明 |
|------|------|------|
| `run_id` ($1) | No | 分析対象の run_id（例: `run_20260424_093015`）。省略時は最新 Run を自動検出 |
| `run_args` | No | RUN 実行時の引数（省略時は前 Run と同一設定） |
| `--repeat` | No | 繰り返しモード。1 サイクル完了後に自動で次サイクル開始。**ユーザーへの問い合わせは一切行わない**（全判断を自律的に行う） |
| `--max-cycles N` | No | 最大サイクル数（`--repeat` なし → 1、あり省略 → 無制限） |
| `--skip-todo` | No | TODO 実装スキップ。Phase 2 の TODO 選定・Phase 3 の implement 全体を skip。GA 分析由来改善のみで進行 |
| `--skip-consensus` | No | Codex 合議スキップ。**ユーザー明示指定時のみ使用可。自動判断で付与してはならない** |
| `--observe-only` | No | 観測のみ。Phase 2/3 を skip し analyze → run → report に直行。Emergency Fix 検出時のみ修正実施。`--skip-todo` / `--skip-consensus` を暗黙的に含む |

## 動作モード

| モード | トリガー | 振る舞い |
|--------|---------|----------|
| Single | 引数なし or `--max-cycles 1` | 1 サイクル実行して終了 |
| Repeat | `--repeat` | `--max-cycles` まで（または無制限）連続実行。ユーザー問い合わせなし |
| Observe-only | `--observe-only` | Phase 2/3 skip。Emergency Fix のみ実施。analyze → run → report に直行 |
| Skip-todo | `--skip-todo` | TODO 関連 step を全 skip。GA 分析由来改善のみ |
| Skip-consensus | `--skip-consensus` | Codex 合議を全 skip。Claude 単独で計画・設計・実装 |

---

## 使命（North Star）— 絶対遵守

> **zenigame-fx Alpha Factory の使命は「`config/alpha_factory/default.yaml` → `live_criteria` を全て満たす FX イントラデイ戦略個体を 1 つ見つけ出すこと」である。**
>
> Stage C 通過は最低条件。使命達成 = `live_criteria` の全指標を同時に満たす個体の出現。
> 達成後は `live_criteria` の各閾値を**引き上げて**次の水準を設定する（漸進的目標更新）。**緩和は禁止**。

### FX 固有の絶対制約

- **イントラデイ前提**: オーバーナイト保有を前提にする設計を避ける
- **ロング・ショート両方向許容**: FX の性質上、両方向取引を許容（ただしコスト控除後の純利益で評価）
- **スワップ・スプレッドを fitness に反映**: 見かけの PnL ではなく純利益

## 禁止事項（全 Workflow に継承）

| # | 禁止事項 |
|---|---------|
| 1 | A・B・C 評価期間を強い根拠なしに延長する |
| 2 | 見た目の数値をよくしようとする改善 |
| 3 | GA をハックしてステージを進めようとする |
| 4 | 閾値をいたずらに緩和してステージを飛ばす |
| 5 | やたらに複雑な案を提案する |
| 6 | 取引回数を削減して見かけの成績を上げようとする |
| 7 | オーバーナイト保有前提の設計 |

> 注: zenigame 版にあった「ショート禁止」は FX 版では**削除**（FX はロング・ショート両方向許容）。ただしショート追加で見かけだけ改善している兆候がないかは codex-review 側で常に点検対象。

---

## 思考原則 — 全議論に適用

**まず仮説を立てろ。** 何を検証したいのか、なぜそう考えるのか、どうなれば成功と判断するのかを明確にしてから手を動かせ。

**データに真摯に向き合え。** 成果だけでなく、多様性の変化、構造の揺らぎ、想定外のパターン — 全てが判断材料になる。数値を見て即座に閾値を弄るな。何が起きているのかを理解し、なぜそうなったのかを考え、どの方向に進むべきかを判断してから手を動かせ。

**先人の知恵を探せ。** 自分たちだけで登る必要はない。乗るべき巨人の肩があるなら乗れ。

**機能の名前に立ち返れ。** 名前はその機能が果たすべき役割を示している。現在の設計がその役割を果たしているか、常に問え。

**仕組みが機能していない段階で値を弄るな。** 閾値チューニングやフィールド追加は、設計の方向性が正しいと確認できてから行え。

**因果ループを切断するな。** 「X は Y に影響しない」という主張に出会ったら、間接経路を含む因果ループ全体を追え。

---

## コンテキスト圧縮対策

状態ファイル `.cache/alpha_factory/current_cycle_state.json` を各フェーズの開始・完了時に更新する。

**圧縮復帰手順**: コンテキスト圧縮後に状態が不明になった場合、まずこのファイルを `Read` して現在の状態を復元し、`completed_phases` から未完了の最初のフェーズから再開する。`tmp_dir` 内の中間成果物も `Read` して把握。

### 状態ファイルのフォーマット

```json
{
  "skill": "zenigame-fx-improve-cycle",
  "phase": "analyze-run",
  "phase_detail": null,
  "cycle_index": 1,
  "run_id": "run_20260424_093015",
  "run_number": 5,
  "next_run_number": 6,
  "tmp_dir": "devnotes/20260424-1326-fx-improve",
  "repeat_mode": true,
  "max_cycles": null,
  "skip_todo": false,
  "skip_consensus": false,
  "observe_only": false,
  "run_args": "--instrument USD_JPY --population-size 48 --generations 20",
  "completed_phases": [],
  "selected_todos": [],
  "skip_todos": [],
  "merge_candidates": [],
  "cycle_focus": null,
  "improvement_plan": null,
  "detailed_design": null,
  "emergency_fix": null,
  "history": [
    {"cycle": 1, "run_number": 5, "best_fitness": 0.81, "live_pass": false}
  ],
  "started_at": "2026-04-24T13:26:00+09:00",
  "last_updated": "2026-04-24T13:26:00+09:00"
}
```

**書き込みは Write ツール経由**（Bash の `echo > json` は使わない）。

### 状態ファイルの責務分離

| key | 書き込み主体 | 読み取り主体 |
|-----|------------|------------|
| `skill` / `phase` / `phase_detail` / `cycle_index` / `run_id` / `run_number` / `next_run_number` / `tmp_dir` / `repeat_mode` / `max_cycles` / `skip_todo` / `skip_consensus` / `observe_only` / `run_args` / `completed_phases` / `history` / `started_at` / `last_updated` | improve-cycle | improve-cycle / plan-and-design |
| `cycle_focus` / `selected_todos` / `skip_todos` / `merge_candidates` / `improvement_plan` / `detailed_design` | plan-and-design | improve-cycle / implement |
| `emergency_fix` | analyze-run（producer 整備時）／ improve-cycle 復旧時 | improve-cycle / plan-and-design |

`zenigame-fx-run-alpha-factory` は **絶対に書き換えない**（別 state file `run_alpha_factory_state.json` を持つ）。

---

## 重要原則

- **全ての中間成果物は `devnotes/{YYYYMMDD-HHMM}-fx-improve/` に保存**する
- **各フェーズの完了時にユーザーに進捗報告**する
- **繰り返しモード**:
  - Phase 5 完了後に自動で次のサイクルを継続
  - **ユーザーへの問い合わせは一切行わない**
  - Codex API 失敗時は Codex なしで自動続行
  - テスト失敗が解消しない施策は revert してスキップ
  - 各フェーズの報告はログとして出力するが、ユーザーの応答を待たずに次フェーズへ進む

---

## Step 0: 初期化

### 0-1. tmp_dir の作成

```bash
TZ=Asia/Tokyo date '+%Y%m%d-%H%M'
```
で `devnotes/{YYYYMMDD-HHMM}-fx-improve/` を作成:
```bash
mkdir -p devnotes/{YYYYMMDD-HHMM}-fx-improve
```

### 0-2. run_id の特定（bootstrap 分岐含む）

`run_id` 引数が省略された場合は最新 archive Parquet を自動検出:
```bash
ls -lt .cache/alpha_factory/runs/genomes_*.parquet 2>/dev/null | head -1
```

**archive Parquet が 1 件もない場合（bootstrap cycle）**:
plan-and-design は analysis-* を入力前提とするため、Phase 1 / 2 / 3 を全て skip し、**Phase 4 → Phase 5 で初回 SoT Run を生成する**。次サイクル以降は通常の Phase 1→2→3 フローへ復帰する。

bootstrap cycle の遷移:
- `phase: "bootstrap"` を state file に記録
- `completed_phases` に `"bootstrap-skip-1-2-3"` を追加
- Phase 4 (`/zenigame-fx-run-alpha-factory {run_args}`) を実行
- Phase 4 完了後の SoT 取り直し（後述）
- Phase 5 (`/zenigame-fx-run-report {run_number} --analysis-dir {tmp_dir}`) — analysis-dir 内に analysis-*.md がなくても run-report は warning ログのみで部分生成する仕様（run-report SKILL.md エラーハンドリング節準拠）
- `--repeat` 指定時は次サイクル先頭 (Phase 1) で `run_id` を最新 SoT に設定して通常フロー継続

これにより既存 sub-skill 契約を崩さず、初回停止リスクを解消する。

### 0-3. run_number の特定

```bash
latest_n=$(uv run python scripts/alpha_factory/get_latest_run_number.py) || latest_n=0
next_n=$((latest_n + 1))
```
`next_run_number = next_n` を仮置き（Phase 4 完了後に summary.json から SoT 取り直し）。

### 0-4. 状態ファイル初期化

`.cache/alpha_factory/current_cycle_state.json` を **Write ツール**で作成。
- `cycle_index: 1`
- `phase: "initializing"`（bootstrap 時は `"bootstrap"`）
- `completed_phases: []`
- `history: []`
- `started_at` / `last_updated`: ISO8601 JST

---

## Phase 1: 深層分析（analyze-run）

```
/zenigame-fx-analyze-run {run_id} --tmp_dir {tmp_dir}
```

**完了後の確認**:
- `{tmp_dir}/analysis-claude.md` が存在
- `{tmp_dir}/analysis-codex.md` が存在（Codex API エラー時は「Codex 失敗」記録のみ）
- 状態ファイルの `emergency_fix` を確認

**Emergency Fix モードの検出**:
状態ファイルに `emergency_fix.detected == true` が記録されている場合（producer 整備時のみ発火可能）:
1. Phase 2（plan-and-design）では改善策合議の代わりに「バグの根本原因特定」を Codex と議論する
2. Phase 3（implement）ではバグ修正のみを実装する

> **producer 不在の fail-soft 設計**: 現状 `zenigame-fx-analyze-run` には `emergency_fix` 書き込み契約がない（key は常に null）。consumer 側（improve-cycle）はキー存在時のみ尊重するフェイルソフトで実装。「壊れはしないが、現状では発火しない（=検証不能）」状態であり、producer 整備は別 TODO の責務。

<!-- TODO(post-run-review-port): zenigame-fx-post-run-review 整備後、Phase 1 完了直後に BG 起動するブロックを追加 -->

**状態ファイル更新**: `completed_phases` に `"analyze-run"` を追加、`phase` を `"plan-and-design"` に更新。

**ユーザー報告**:
```
## Phase 1 完了: 深層分析
→ Phase 2 に進みます（計画策定 & 詳細設計）
```

---

## Phase 1.5: IC Sync（未移植・コメント化）

<!-- TODO(primitive-ic-port): FX には primitive-ic 未整備。整備後に以下を有効化:

`.cache/alpha_factory/primitive_ic/latest_summary.json` が存在する場合のみ実行:
/zenigame-fx-primitive-ic-sync

**`--skip-todo` 時はスキップ**（IC Sync は TODO/プリミティブ管理に関連するため）。

実行モード: improve-cycle から呼ばれた場合、ic-sync は以下の動作をする:
- RETIRE 候補がある場合 → 変更案を提示し、ユーザーに確認を求める
- ユーザーが承認 → 変更を適用してコミット後、Phase 2 へ進む
- ユーザーが拒否 or IC summary 未存在 → スキップして Phase 2 へ進む（IC sync は improve-cycle をブロックしない）
-->

---

## Phase 2: 計画策定 & 詳細設計（plan-and-design）

**`--observe-only` 時は Phase 2 全体をスキップ**して Phase 4 へ。ただし `emergency_fix.detected == true` の場合はバグ修正のため Phase 2/3 を Emergency Fix モードで実行する。

```
/zenigame-fx-plan-and-design {tmp_dir} {run_id} [--repeat] [--skip-todo] [--skip-consensus]
```

**完了後の確認**:
- `{tmp_dir}/improvement-plan.md` が存在
- `{tmp_dir}/detailed-design.md` が存在
- 状態ファイルの `selected_todos`, `skip_todos`, `cycle_focus` が plan-and-design により書き込まれている

**状態ファイル更新**: `completed_phases` に `"plan-and-design"` を追加、`phase` を `"implement"` に更新。

> 補足: GA パラメータ介入が必要な場合、`improvement-plan.md` / `detailed-design.md` 内に人間 / Codex 判断として記載される。**自動更新する skill は現存しない**（calibrate-gate 整備までは手動 / Codex 合議経由）。

**ユーザー報告**:
```
## Phase 2 完了: 計画策定 & 詳細設計
- cycle_focus: {ga_improvements / todos / mixed}
- selected_todos: {N} 件
→ Phase 3 に進みます（実装）
```

---

## Phase 2.5: Gate キャリブレーション（未移植・コメント化）

<!-- TODO(calibrate-gate-port): zenigame-fx-calibrate-gate 整備後に以下を有効化:

前 Run の gate_stats に基づいて `stage_a_gate_stage_b_ratio` を自動調整する。

/zenigame-fx-calibrate-gate {run_id}

**実行条件**: Stage A Gate が有効（`stage_a_gate: true`）の場合のみ実行。無効の場合はスキップ。

**完了後の確認**:
- `config/alpha_factory/default.yaml` の `stage_a_gate_stage_b_ratio` が適切に更新されたこと（または変更不要の報告）

**状態ファイル更新**: `completed_phases` に `"calibrate-gate"` を追加。

整備されるまで GA パラメータ自動調整経路は存在しない。介入が必要な場合は plan-and-design 内で記載される。
-->

---

## Phase 3: 実装（implement）

**`--observe-only` 時（Emergency Fix なし）**: Phase 3 をスキップし、Phase 4（RUN 実行）へ直行する。

**`--skip-todo` 時**: `selected_todos` は空のため Phase 3 全体をスキップし、Phase 4 へ。

plan-and-design で選定された TODO（`selected_todos`）ごとに `/zenigame-fx-implement` を呼び出す:

```
/zenigame-fx-implement {todo_id} --tmp_dir {tmp_dir} [--skip-consensus]
```

**複数 TODO がある場合**: 依存関係がなければ並列実行可能（各 TODO が別 worktree で動作するため競合しない）。ただしマージ時のコンフリクトに注意。

**完了後の確認**:
- 各 TODO のコミットが main にマージされていること
- TODO がクローズされていること

**状態ファイル更新**: `completed_phases` に `"implement"` を追加、`phase` を `"run-alpha-factory"` に更新。

---

## Phase 4: RUN 実行

```
/zenigame-fx-run-alpha-factory {run_args}
```

このスキルが以下を自動実行する:
- バックグラウンドで GA 実行（`scripts/alpha_factory/run_ga.py`）
- ログ監視ループ
- 完了検出（4 点整合: ga.run.done log + archive Parquet + [done] stdout + summary.json run_id 一致）
- 結果確認

`run-alpha-factory` skill は **`current_cycle_state.json` を絶対に書き換えない**（別 state file `run_alpha_factory_state.json` を持つ）。

### Phase 4 完了後の SoT 取り直し（必須）

run-alpha-factory skill 完了直後に improve-cycle が以下を実行（**順序厳守**）:

1. `.cache/alpha_factory/run_alpha_factory_state.json` を Read
   - `status == "completed"` を確認（`failed` / `stale` の場合は Phase 4 失敗扱い）
   - `summary_path` を取得
2. `summary_path` (= `reports/run-reports/run-{N}/summary.json`) を Read
   - `run_id` と `run_number` を取得（**これらが SoT、事前計算 `next_run_number` は使わない**）
   - `best.fitness`（または `best.fitness_pen`）を取得
   - `live_pass`（または summary 内の live_criteria 判定相当）を取得（key 不在時は `null`）
3. `.cache/alpha_factory/current_cycle_state.json` を **Write ツールで原子的に更新**:
   - `run_id ← summary.run_id`
   - `run_number ← summary.run_number`
   - `next_run_number ← summary.run_number + 1`（次サイクル用に再計算）
   - `history` に `{cycle: cycle_index, run_number, best_fitness, live_pass}` を append
   - `completed_phases` に `"run-alpha-factory"` を追加
   - `phase ← "report"`
   - `last_updated ← TZ=Asia/Tokyo date -Iseconds`

この規約により `--repeat` 時の旧 Run 再分析・別 Run の `run_number` 誤参照を防ぐ。

---

## Phase 5: Run レポート作成

```
/zenigame-fx-run-report {run_number} --analysis-dir {tmp_dir}
```

**`run_number` は Phase 4 完了後に取り直した SoT を使用**（事前計算 `next_run_number` は使わない）。

このスキルがレポート作成を自動実行する。

**完了後の確認**:
- `reports/run-reports/run-{run_number}.md` が存在すること

**状態ファイル更新**: `completed_phases` に `"report"` を追加、`phase` を `"completed"` に更新。

**ユーザー報告**:
```
## サイクル {cycle_index} 完了: Run {run_number}
- best_fitness: {value}
- live_pass: {true/false}
- report: reports/run-reports/run-{run_number}.md
- 成果物: {tmp_dir}/
```

---

## Phase 5.5: Alpha Sieve 評価（未移植・コメント化）

<!-- TODO(alpha-sieve-port): zenigame-fx-alpha-sieve 整備後に以下を有効化:

GA Run 完了後、adaptive_mission_pass 個体が存在する場合に Alpha Sieve OOS 評価を自動実行する。

### 実行条件
当該 Run に GA evaluation で adaptive_mission_pass=True の個体が 1 体以上存在すること。
（archive Parquet から adaptive_mission_pass カラムを読んで集計）

### 実行
adaptive_mission_pass 個体が存在する場合:
/zenigame-fx-alpha-sieve --run-id {run_id}
（または scripts/trading/run_alpha_sieve.py 整備後）

### 完了後の確認
- Sieve 結果 Parquet: .cache/alpha_sieve/{run_id}/
- Run 単位レポート: reports/alpha-sieve/{yyyy-mm}/sieve-R{run_number}.md
- サマリー更新: reports/alpha-sieve/sieve-metrics-summary.md

### スキップ条件
- adaptive_mission_pass 個体がない場合はスキップ（ログのみ）
- Sieve 処理失敗は non-critical（improve-cycle 全体は続行）

**状態ファイル更新**: completed_phases に "alpha-sieve" を追加、phase を "completed" に更新。
-->

---

## Phase 6: 繰り返し判定

### `--repeat` が指定されかつ `--max-cycles` 未達の場合

Phase 5 完了後に自動で次のサイクルを開始:
1. 状態ファイルを部分リセット:
   - `cycle_index += 1`
   - `phase: "analyze-run"` / `phase_detail: null` / `completed_phases: []`
   - `selected_todos: []` / `skip_todos: []` / `merge_candidates: []`
   - `cycle_focus: null` / `improvement_plan: null` / `detailed_design: null`
   - `emergency_fix: null`
   - `tmp_dir`: 新規作成（`devnotes/{YYYYMMDD-HHMM}-fx-improve/`）
   - `run_id`: Phase 4 で取り直した最新 `run_id` を引き継ぐ（次サイクルの分析対象）
   - `history` は維持（追記型）
2. Phase 1 から再開

### `--repeat` が未指定 / `--max-cycles` 到達の場合

最終報告を出力して終了:
```
## 改善サイクル完了

### サイクルサマリー
- 実行サイクル数: {cycle_index}
- 総 Run 数: {history.length}
- 最終 best_fitness: {value}
- 使命達成（live_criteria 全達成）: {YES/NO}
- 成果物: 各サイクルの devnotes/{YYYYMMDD-HHMM}-fx-improve/
- レポート: reports/run-reports/run-{A}..{B}.md
```

---

## エラーハンドリング

### Workflow 失敗

各 Workflow skill が失敗した場合の振る舞い:

| sub-skill | 失敗時挙動 | improve-cycle 側の処理 |
|-----------|----------|---------------------|
| analyze-run | `analysis-claude.md` 出力されない | Phase 1 失敗報告、Phase 2 移行不可 |
| plan-and-design | `improvement-plan.md` / `detailed-design.md` 出力されない | Phase 2 失敗報告、Phase 3 移行不可 |
| implement | TODO 実装失敗 | 該当 TODO のみ skip、他 TODO は続行 |
| run-alpha-factory | `status=failed` / `stale` | Phase 4 失敗報告、サイクル中断（手動 run-id で再開可能） |
| run-report | レポート生成失敗 | warning ログのみ、サイクル続行（次サイクルへ） |

### モード別

- **通常モード**: 致命的失敗時はユーザーに報告し、対応を確認
- **繰り返しモード**: エラーをログに記録し、可能であれば次のフェーズに進む。致命的エラー（state file 破損 / Phase 4 完全失敗等）の場合のみ停止

### コンテキスト圧縮からの復帰

1. `.cache/alpha_factory/current_cycle_state.json` を `Read`
2. `completed_phases` を確認し、未完了の最初のフェーズから再開
3. `tmp_dir` 内の中間成果物を `Read` して状態を把握
4. Phase 4 完了済みなら `run_alpha_factory_state.json` も併読して SoT 整合性確認

---

## TodoWrite 連携

各フェーズの開始時に TodoWrite で進捗管理する:

```
Phase 1: 深層分析（/zenigame-fx-analyze-run）
[Phase 1.5: IC Sync — 未移植、整備後に接続]
Phase 2: 計画策定 & 詳細設計（/zenigame-fx-plan-and-design）
[Phase 2.5: Gate キャリブレーション — 未移植、整備後に接続]
Phase 3: 実装（/zenigame-fx-implement）
Phase 4: RUN 実行（/zenigame-fx-run-alpha-factory）+ SoT 取り直し
Phase 5: レポート作成（/zenigame-fx-run-report）
[Phase 5.5: Alpha Sieve 評価 — 未移植、整備後に接続]
Phase 6: 繰り返し判定
```

---

## 残課題（整備時の hook 復活）

| hook | 整備後の接続点 | 復活時の作業 |
|------|--------------|------------|
| `zenigame-fx-post-run-review` | Phase 1 末尾 | `<!-- TODO(post-run-review-port) -->` コメント解除 + BG 起動ブロック追加 |
| `zenigame-fx-primitive-ic-sync` | Phase 1.5 全体 | `<!-- TODO(primitive-ic-port) -->` コメントブロック解除 |
| `zenigame-fx-calibrate-gate` | Phase 2.5 全体 | `<!-- TODO(calibrate-gate-port) -->` コメントブロック解除 |
| `zenigame-fx-alpha-sieve` | Phase 5.5 全体 | `<!-- TODO(alpha-sieve-port) -->` コメントブロック解除 |
| `zenigame-fx-set-focus` | plan-and-design 側で focus-theme.json 利用 | improve-cycle SKILL.md の参照記載更新（focus-theme fallback 解消） |
| `zenigame-fx-analyze-genome-archive` | Phase 1 内（analyze-run 側で深層分析委譲） | analyze-run SKILL.md の修正で対応、improve-cycle 側は変更不要 |
| analyze-run の emergency_fix producer 機構 | Phase 1 完了時 | analyze-run / post-run-review 拡張時に producer を実装 |

---

## 使用例

### 例 1: 最新 Run から改善サイクル実行（1 サイクル）
```
/zenigame-fx-improve-cycle
```

### 例 2: 特定 Run から改善サイクル実行
```
/zenigame-fx-improve-cycle run_20260424_093015
```

### 例 3: RUN 引数を明示
```
/zenigame-fx-improve-cycle run_20260424_093015 --instrument USD_JPY --population-size 48 --generations 20
```

### 例 4: 繰り返しモード（無制限、autopilot から呼ばれる想定）
```
/zenigame-fx-improve-cycle --repeat
```

### 例 5: 繰り返しモード（最大 5 サイクル）
```
/zenigame-fx-improve-cycle --repeat --max-cycles 5
```

### 例 6: 観測のみモード
```
/zenigame-fx-improve-cycle --observe-only
```

### 例 7: TODO スキップ + Codex 合議スキップ（高速モード）
```
/zenigame-fx-improve-cycle --skip-todo --skip-consensus
```
```

---

## 検証

実装完了後に以下のコマンドで grep 検証:

```bash
grep -cE "docs/alpha-factory|src/trading|/zenigame-codex|~/.local/bin/codex-vscode|/zenigame-analyze-genome-archive|/zenigame-codex-review|/zenigame-analyze-run|/zenigame-plan-and-design|/zenigame-run-report|/zenigame-run-alpha-factory|/zenigame-implement|/zenigame-todo-close|/zenigame-improve-cycle" .claude/skills/zenigame-fx-improve-cycle/SKILL.md
```
→ **0 件** が必須（zenigame-fx-* prefix で全置換済み）

---

## 想定行数

- before: 214 行（縮小版）
- after: 約 480-520 行（zenigame 版 476 行とほぼ同等。FX 固有制約 + SoT 取り直し規約 + 未移植 hook コメントブロック）
