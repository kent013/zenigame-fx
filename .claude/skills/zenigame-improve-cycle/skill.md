---
name: zenigame-improve-cycle
description: Alpha Factory改善サイクルのオーケストレータ（analyze-run → plan-and-design → implement → run → report を順次呼び出す）
argument-hint: "[run_id] [--repeat] [--skip-todo] [--skip-consensus] [--observe-only] [run_args...]"
---

# Alpha Factory 改善サイクル（オーケストレータ）

Workflowスキルを順次呼び出して、前回Runの分析→計画→実装→RUN実行の全フローを自動化する。

**自身ではCodex呼び出し・ファイル実装・TODO操作を一切行わない。** 調整・状態管理・エラーハンドリング・ユーザー報告のみを担当する。

## 引数

| 引数 | 必須 | 説明 |
|------|------|------|
| `run_id` ($1) | No | 分析対象のrun_id（例: run_20260219_212426）。省略時は最新Runを自動検出 |
| `run_args` | No | RUN実行時の引数（省略時は前回Runと同一設定） |
| `--repeat` | No | 繰り返しモード。サイクル完了後に自動で次のサイクルを開始する |
| `--skip-todo` | No | TODO実装スキップモード。TODO選定・Codex合議・TODO遷移など全てのTODO関連ステップをスキップし、GA分析由来の改善のみで進行する |
| `--skip-consensus` | No | Codex合議スキップモード。plan-and-designの改善策合議（B-2/B-3）・設計レビュー合議（C-2/C-3）、implementの実装レビュー合議（A-2/A-3）を全てスキップし、Claude単独で計画・設計・実装を進める。**ユーザーから明示的に指定された場合のみ使用可。自動判断で付与してはならない** |
| `--observe-only` | No | 観測のみモード。コード変更・GAパラメータチューニングを行わず、分析→calibrate-gate→RUN→レポートに直行する。ただしEmergency Fix（バグ）検出時のみ修正を実施する。--skip-todo と --skip-consensus を暗黙的に含む |

```
improve-cycle (orchestrator)
│
├─ 初期化: state file作成, devnotesディレクトリ作成
│
├─ /analyze-run {run_id} --tmp_dir {tmp_dir}
│   → analysis-claude.md, analysis-codex.md, post-run-review BG起動
│
├─ [--observe-only でない場合]
│   ├─ /primitive-ic-sync （オプション: IC summary存在時のみ、--skip-todo時はスキップ）
│   │   → RETIRE候補のschema変更（ユーザー承認後）
│   │
│   ├─ /plan-and-design --tmp_dir {tmp_dir} {--repeat} {--skip-todo} {--skip-consensus}
│   │   → analysis-merged.md, improvement-plan.md, detailed-design.md
│   │
│   ├─ /calibrate-gate {run_id}
│   │   → default.yaml の stage_a_gate_stage_b_ratio 更新
│   │
│   ├─ /implement {todo_ids} --tmp_dir {tmp_dir} {--skip-consensus}
│   │   → worktreeで実装・テスト・コミット・TODOクローズ・mainマージ
│   │
│   ├─ /run-alpha-factory {run_args}
│   │   → バックグラウンドGA実行・ログ監視・完了検出・ゲノム分析
│   │
│   └─ /run-report --run_id {run_id} --run_number {N+1}
│       → reports/run-reports/run-{block}/run-{N+1}.md
│
├─ [--observe-only の場合]
│   ├─ Emergency Fix 検出時のみ: バグ修正→テスト→コミット
│   ├─ /calibrate-gate {run_id}
│   ├─ /run-alpha-factory {run_args}
│   └─ /run-report --run_id {run_id} --run_number {N+1}
│
└─ repeat判定 → YES → ループ先頭へ
```

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

**絶対的な制約（イントラデイ）**: スイングトレード（オーバーナイト保有）は行わない。

## 禁止事項（全Workflowに継承）

| # | 禁止事項 |
|---|---------|
| 1 | ショート（空売り）売買の導入 |
| 2 | A・B・C評価期間を強い根拠なしに延長する |
| 3 | 見た目の数値をよくしようとする改善 |
| 4 | GAをハックしてステージを進めようとする |
| 5 | 閾値をいたずらに緩和してステージを飛ばす |
| 6 | やたらに複雑な案を提案する |
| 7 | 取引回数を削減して見かけの成績を上げようとする |

---

## コンテキスト圧縮対策

状態ファイル `.cache/alpha_factory/current_cycle_state.json` を各フェーズの開始・完了時に更新する。

**圧縮復帰手順**: コンテキスト圧縮後に状態が不明になった場合、まずこのファイルを `Read` して現在の状態を復元し、中断したWorkflowから再開する。

**状態ファイルのフォーマット**:
```json
{
  "skill": "improve-cycle",
  "phase": "analyze-run",
  "run_id": "run_YYYYMMDD_HHMMSS",
  "run_number": 45,
  "next_run_number": 46,
  "tmp_dir": "devnotes/20260219-2100-alpha-improve",
  "repeat_mode": true,
  "skip_todo": true,
  "skip_consensus": true,
  "observe_only": false,
  "run_args": "--pop-size 96 --generations 60 ...",
  "completed_phases": ["analyze-run"],
  "emergency_fix": null,
  "started_at": "2026-02-19T21:00:00",
  "last_updated": "2026-02-19T22:30:00"
}
```

**Writeツールで更新**する（Bashのechoは使わない）。

---

## 重要原則

- **全ての中間成果物は `devnotes/{YYYYMMDD-HHMM-topic}/` に保存**する
- **各フェーズの完了時にユーザーに進捗報告**する
- **繰り返しモード**: 引数に `--repeat` が含まれている場合、以下の自律動作ルールが適用される:
  - Phase 3のRUN完了後に自動で次の改善サイクルを継続する
  - **ユーザーへの問い合わせは一切行わない**（全判断を自律的に行う）
  - Codex API失敗時はCodexなしで自動続行
  - テスト失敗が解消しない施策はrevertしてスキップ
  - 各フェーズの報告はログとして出力するが、ユーザーの応答を待たずに次フェーズへ進む

---

## Step 0: 初期化

### 0-1. tmp_dir の作成

```bash
date '+%Y%m%d-%H%M'
```
で `devnotes/{YYYYMMDD-HHMM}-alpha-improve/` を作成:
```bash
mkdir -p devnotes/{YYYYMMDD-HHMM}-alpha-improve
```

### 0-2. run_id の特定

`run_id` 引数が省略された場合は最新のgenomes parquetを自動検出:
```bash
ls -lt .cache/alpha_factory/runs/genomes_*.parquet | head -1
```

### 0-3. run_number の特定

```bash
latest_n=$(uv run python scripts/alpha_factory/get_latest_run_number.py) || exit 1
```
最新のRun番号から `next_run_number = latest_n + 1` とする。

### 0-4. 状態ファイル初期化

`.cache/alpha_factory/current_cycle_state.json` を作成:
```json
{
  "skill": "improve-cycle",
  "phase": "initializing",
  "run_id": "{run_id}",
  "run_number": {run_number},
  "next_run_number": {next_run_number},
  "tmp_dir": "{tmp_dir}",
  "repeat_mode": {true/false},
  "run_args": "{run_args}",
  "completed_phases": [],
  "emergency_fix": null,
  "started_at": "{ISO8601}",
  "last_updated": "{ISO8601}"
}
```

---

## Phase 1: 深層分析（analyze-run）

```
/zenigame-analyze-run {run_id} --tmp_dir {tmp_dir}
```

**完了後の確認**:
- `{tmp_dir}/analysis-claude.md` が存在すること
- `{tmp_dir}/analysis-codex.md` が存在すること（Codex APIエラーの場合はスキップ記録あり）
- 状態ファイルの `emergency_fix` を確認

**Emergency Fix モードの検出**:
状態ファイルに `emergency_fix.detected == true` が記録されている場合:
1. Phase 2（plan-and-design）では改善策合議の代わりに「バグの根本原因特定」を Codex と議論する
2. Phase 3（implement）ではバグ修正のみを実装する

**状態ファイル更新**: `completed_phases` に `"analyze-run"` を追加、`phase` を `"plan-and-design"` に更新。

**ユーザー報告**:
```
## Phase 1 完了: 深層分析

→ IC Syncチェック後、Phase 2に進みます（計画策定 & 詳細設計）
```

---

## Phase 1.5: IC Sync（オプション）

**`--skip-todo` 時はスキップ**（IC SyncはTODO/プリミティブ管理に関連するため）。

`.cache/alpha_factory/primitive_ic/latest_summary.json` が存在する場合のみ実行:

```
/zenigame-primitive-ic-sync
```

**実行モード**: improve-cycleから呼ばれた場合、ic-syncは以下の動作をする:
- RETIRE候補がある場合 → 変更案を提示し、ユーザーに確認を求める
- ユーザーが承認 → 変更を適用してコミット後、Phase 2へ進む
- ユーザーが拒否 or IC summary未存在 → スキップしてPhase 2へ進む
  （IC syncはimprove-cycleをブロックしない）

**注意**: IC syncはGA改善サイクルの補助ステップ。
IC evalはimprove-cycleとは独立して実行する（`/zenigame-primitive-ic-eval`）。

---

## Phase 2: 計画策定 & 詳細設計（plan-and-design）

**`--observe-only` 時は Phase 2 全体をスキップ**。ただし `emergency_fix.detected == true` の場合はバグ修正のため Phase 2/3 を Emergency Fix モードで実行する。

```
/zenigame-plan-and-design --tmp_dir {tmp_dir} {--repeat（繰り返しモード時）}
```

**完了後の確認**:
- `{tmp_dir}/improvement-plan.md` が存在すること
- `{tmp_dir}/detailed-design.md` が存在すること
- 状態ファイルの `selected_todos`, `skip_todos`, `cycle_focus` を取得

**状態ファイル更新**: `completed_phases` に `"plan-and-design"` を追加、`phase` を `"implement"` に更新。

**ユーザー報告**:
```
## Phase 2 完了: 計画策定 & 詳細設計

→ Gate キャリブレーション後、Phase 3に進みます（実装 & RUN実行）
```

---

## Phase 2.5: Gate キャリブレーション

前回Runのgate_statsに基づいて `stage_a_gate_stage_b_ratio` を自動調整する。

```
/zenigame-calibrate-gate {run_id}
```

**実行条件**: Stage A Gate が有効（`stage_a_gate: true`）の場合のみ実行。無効の場合はスキップ。

**完了後の確認**:
- `config/alpha_factory/default.yaml` の `stage_a_gate_stage_b_ratio` が適切に更新されたこと（または変更不要の報告）

**状態ファイル更新**: `completed_phases` に `"calibrate-gate"` を追加。

---

## Phase 3: 実装（implement）

**`--observe-only` 時（Emergency Fix なし）**: Phase 3 をスキップし、Phase 4（RUN実行）へ直行する。

plan-and-designで選定されたTODO（`selected_todos`）ごとに `/zenigame-implement` を呼び出す。

```
/zenigame-implement {todo_id} --tmp_dir {tmp_dir} {--skip-consensus（Codexスキップ時）}
```

**複数TODOがある場合**: 依存関係がなければ並列実行可能（各TODOが別worktreeで動作するため競合しない）。ただしマージ時のコンフリクトに注意。

**完了後の確認**:
- 各TODOのコミットがmainにマージされていること
- TODOがクローズされていること

**状態ファイル更新**: `completed_phases` に `"implement"` を追加、`phase` を `"run"` に更新。

---

## Phase 4: RUN実行

**`/zenigame-run-alpha-factory` スキルを呼び出す**。

引数 `run_args` が指定されていればそれを使用。省略時は前回Runと同一設定。

```
/zenigame-run-alpha-factory {run_args}
```

このスキルが以下を自動実行する:
- バックグラウンドでGA実行
- ログ監視ループ
- 完了検出
- 結果確認
- ゲノムアーカイブ分析（`/zenigame-analyze-genome-archive`）

**状態ファイル更新**: `completed_phases` に `"run"` を追加。

---

## Phase 5: Runレポート作成

**`/zenigame-run-report` スキルを呼び出す**。

```
/zenigame-run-report --run_id {run_id} --run_number {N+1}
```

このスキルがレポート作成とコミットを自動実行する。

**完了後の確認**:
- `reports/run-reports/**/run-{next_run_number}.md`（ブロック配下）が存在すること（`find reports/run-reports -maxdepth 2 -name "run-${next_run_number}.md"` で確認）

**状態ファイル更新**: `completed_phases` に `"report"` を追加。

---

## Phase 5.5: Alpha Sieve評価（自動）

GA Run完了後、adaptive_mission_pass個体が存在する場合にAlpha Sieve OOS評価を自動実行する。

### 実行条件

当該RunにGA evaluationでadaptive_mission_pass=Trueの個体が1体以上存在すること。

確認方法:
```bash
uv run python -c "
import pandas as pd
df = pd.read_parquet('.cache/alpha_factory/runs/genomes_{run_id}.parquet', columns=['adaptive_mission_pass'])
n = int(df['adaptive_mission_pass'].fillna(False).sum())
print(f'adaptive_mission_pass: {n}')
"
```

### 実行

adaptive_mission_pass個体が存在する場合:
```bash
uv run python scripts/trading/run_alpha_sieve.py --run-id {run_id} --direct
```

### 完了後の確認

- Sieve結果Parquet: `.cache/alpha_sieve/{run_id}/`
- Run単位レポート: `reports/alpha-sieve/{yyyy-mm}/sieve-R{run_number}.md`（年月ブロック配下）
- サマリー更新: `reports/alpha-sieve/sieve-metrics-summary.md`

### スキップ条件

- adaptive_mission_pass個体がない場合はスキップ（ログのみ）
- Sieve処理失敗はnon-critical（improve-cycle全体は続行）

**状態ファイル更新**: `completed_phases` に `"alpha-sieve"` を追加、`phase` を `"completed"` に更新。

---

## Phase 6: 繰り返し判定

### `--repeat` が指定されている場合

Phase 5.5完了後に自動で次のサイクルを開始する:
1. 状態ファイルをリセット（新しいtmp_dir、updated run_id）
2. Phase 1（analyze-run）から再開

### `--repeat` が指定されていない場合

最終報告を出力して終了:
```
## 改善サイクル完了

### サイクルサマリー
- 分析対象: Run {run_number} ({run_id})
- 成果物ディレクトリ: {tmp_dir}

### Run {next_run_number} 結果
- Stage C: {winners}
- Stage B: {candidates}
- Best B-Sharpe: {value}
- 判定: {SUCCESS/MARGINAL/FAIL}
```

---

## エラーハンドリング

### Workflow失敗

各Workflowスキルが失敗した場合:
- **通常モード**: ユーザーに報告し、対応を確認
- **繰り返しモード**: エラーをログに記録し、可能であれば次のフェーズに進む。致命的エラー（状態ファイル破損等）の場合のみ停止

### コンテキスト圧縮からの復帰

1. `.cache/alpha_factory/current_cycle_state.json` を `Read`
2. `completed_phases` を確認し、未完了の最初のフェーズから再開
3. `tmp_dir` 内の中間成果物を `Read` して状態を把握

---

## TodoWrite連携

各フェーズの開始時にTodoWriteで進捗管理する:

```
Phase 1: 深層分析（/analyze-run）
Phase 2: 計画策定 & 詳細設計（/plan-and-design）
Phase 2.5: Gate キャリブレーション（/calibrate-gate）
Phase 3: 実装（/implement）
Phase 4: RUN実行（/run-alpha-factory）
Phase 5: レポート作成（/run-report）
Phase 5.5: Alpha Sieve評価
```

---

## 使用例

### 例1: 最新Runから改善サイクル実行
```
User: /zenigame-improve-cycle
```

### 例2: 特定Runから改善サイクル実行
```
User: /zenigame-improve-cycle run_20260219_212426
```

### 例3: RUN引数を明示
```
User: /zenigame-improve-cycle run_20260219_212426 --pop-size 96 --generations 60 --stochastic-eval --date-pool 2025-01-06:2026-02-14 --is-dates 2025-01-06:2025-12-31 --oos-dates 2026-01-05:2026-02-14 --workers 6
```

### 例4: 繰り返しモード
```
User: /zenigame-improve-cycle --repeat
```
