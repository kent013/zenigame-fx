# 概念設計: zenigame-fx-run-alpha-factory skill 移植

cycle 26 / Phase 3 / topic = port-run-alpha-factory

## 背景

zenigame 本家には `zenigame-run-alpha-factory` skill があり、`scripts/trading/run_alpha_factory.py` を「BG 起動 → ログ tail → 完了検出 → 結果確認 → 報告」という一連のオーケストレーションでラップしている。zenigame-fx 側にも同等の skill を整備し、既存の `zenigame-fx-improve-cycle` Phase 3 や、autopilot サイクルの GA 起動経路を統一したい。

T018 で `scripts/alpha_factory/run_ga.py`（810 行、Phase 2 完全統合済）が既に存在し、cycle 21 で実 DB smoke run の動作確認が済んでいる。その後 T019〜T022 で `analyze_run.py` / `generate_run_report.py` が拡張され、archive Parquet を中心とした出力契約が安定した。

## 目的（What）

- `.claude/skills/zenigame-fx-run-alpha-factory/SKILL.md` を新規作成し、
  `scripts/alpha_factory/run_ga.py` をバックグラウンド実行 → ログ監視 → 完了検出 → 結果確認 → 報告するラッパースキルを提供する。
- 単独呼び出し可能（ユーザーが `/zenigame-fx-run-alpha-factory --instrument USD_JPY ...` の形で起動）。
- 中長期的には `zenigame-fx-improve-cycle` Phase 3 がこの skill を呼ぶ形に置き換え可能（本 PR では improve-cycle 本体は変更しない＝最小スコープ）。

## 非目的（What NOT）

- run_ga.py 本体の挙動・CLI 改修は行わない（既に T018 で確定済の挙動を尊重）。
- improve-cycle の本体を切り替える作業は本 PR 範囲外（残課題として記録）。
- zenigame 本家の「LLM 変異 / Director / cost-stress / DSR / smoke-test / profile / validate-only / warmstart」など run_alpha_factory.py 固有のオプション群は移植しない（fx の run_ga.py は対応していない）。
- ゲノムアーカイブ深層分析（zenigame-analyze-genome-archive 相当）は未移植のため、本 skill からは呼び出さずコメントとして残す。

## 既存資産の整理

- `zenigame/.claude/skills/zenigame-run-alpha-factory/skill.md`: オリジナル（623 行）。
  ステップ 1〜8 + コンテキスト圧縮対策 + 状態ファイルポリシー + 大量の引数例。
- `zenigame-fx/scripts/alpha_factory/run_ga.py`:
  - CLI 引数（抜粋）: `--config`, `--run-id`, `--instrument`, `--start`, `--end`,
    `--population-size`, `--generations`, `--mutation-rate`, `--crossover-rate`,
    `--tournament-size`, `--elite-count`, `--max-depth`, `--fitness-metric`, `--seed`
  - 開始ログ: `logger.info("ga.run.start", ...)`
  - 完了ログ: `logger.info("ga.run.done", run_id=..., run_number=..., best_name=..., best_fitness=..., stage_c_pass=...)`
  - 完了 stdout: `[done] run_id={run_id} run_number={run_number} best={...} fitness_pen={...} stage_c={...} report={run_dir}`
  - 出力先: `reports/run-reports/run-{N}/summary.json`, `history.json`, `best_genome.json`, archive Parquet（`.cache/alpha_factory/runs/genomes_{run_id}.parquet`）, `.cache/alpha_factory/runs/{run_id}.json`
- `zenigame-fx/.claude/skills/zenigame-fx-improve-cycle/SKILL.md`: Phase 3 で `run_ga.py` を直叩きする構造。状態ファイルは `.cache/alpha_factory/current_cycle_state.json`。

## 前提（verified）

- `scripts/alpha_factory/run_ga.py` の `_parse_args` が `--run-id` を受け取り、
  `args.run_id or f"run_{now.strftime('%Y%m%d_%H%M%S')}"` で `run_id` を確定する（L720）。
- 確定した `run_id` は以下の全成果物に**同一値で伝搬**される:
  - `logger.info("ga.run.start", run_id=...)` / `logger.info("ga.run.done", run_id=...)`
  - `archive = GenomeArchive(run_id=run_id, run_number=run_number)` → archive Parquet ファイル名は `genomes_{run_id}.parquet`（src/alpha_factory/archive.py:492）
  - `summary["run_id"] = run_id`（reports/run-reports/run-{N}/summary.json）
  - `.cache/alpha_factory/runs/{run_id}.json` のメタファイル
- `run_number` は run_ga.py 内部で `get_latest_run_number()+1` 確定（L721）。skill 起動時点では `_estimate` のみ保持し、完了後に summary.json から確定値で上書きする。

これにより skill 側で `--run-id` を生成して渡せば、log・archive Parquet・summary・runs/{run_id}.json の **4 点で run_id 整合チェックが可能**になる。

## 削除する zenigame 由来要素の分類

| 要素 | 区分 | 理由 |
|------|------|------|
| LLM 変異（Anthropic API） | 不要 | run_ga.py 未対応。fx 側 GA は Phase 2 完成時点で random_gen + crossover/mutate のみ。Phase 4 以降に検討対象 |
| Director（プリミティブ重み制御） | deferred | fx 側未実装。将来 Director 相当が入った時点で別 TODO |
| cost-stress / DSR / entry-delay-test / volume-participation-check | deferred | Stage C 後処理の充実は Phase 3-4 後半の課題 |
| smoke-test モード | deferred | run_ga.py に smoke 専用フラグ無し。短い --generations / --population-size で代替可 |
| --profile（cProfile） | deferred | パフォーマンス問題が顕在化したら検討 |
| warmstart-auto | deferred | アーカイブ Parquet からの seed 注入は Phase 4 候補 |
| --validate-only | deferred | Stage C 通過個体の validation 専用パスは未整備 |
| /zenigame-analyze-genome-archive | deferred | fx 用 analyze-genome-archive skill が未移植。将来 Step 6.5 として hook 予定。本 skill の残課題に明記 |
| ショート禁止ルール | 不要 | fx は両方向許容（絶対制約） |
| /zenigame-improve-cycle 自動連鎖 | 不要 | fx 側は improve-cycle 側が主、本 skill は wrapper のため逆方向の依存は持たない |

「不要」= fx の North Star に照らして移植する必要がない。
「deferred」= 将来必要になりうる。本 PR では実装しないが、残課題として記録する。

## 改修方針（zenigame → zenigame-fx）

| 項目 | zenigame | zenigame-fx |
|------|----------|------------|
| パス | `docs/alpha-factory/` | `docs/alpha_factory/` |
| GA スクリプト | `scripts/trading/run_alpha_factory.py` | `scripts/alpha_factory/run_ga.py` |
| 完了サイン | `"GA complete:"` / `"=== Step 5: ..."` | `"ga.run.done"` log line + `[done] ` stdout |
| 完了確認の二次ソース | summary.json | summary.json + archive Parquet（T015 schema） |
| 状態ファイル | `.cache/alpha_factory/current_run_state.json` | 同パス（skill 単独実行用に新規作成。improve-cycle の `current_cycle_state.json` とは別ファイルで衝突回避） |
| ログ場所 | `.cache/alpha_factory/runs/{run_id}.log` | 同パス（run_ga.py は自前ログを書かないので skill 側で `nohup ... > {log} 2>&1 &` のリダイレクト経路でファイル化） |
| LLM 変異 | デフォルト ON（自動付与） | 該当オプションなし → 削除 |
| Director / cost-stress / DSR / warmstart / profile / smoke-test / validate-only | 多数 | 全て削除（run_ga.py 未対応） |
| 関連 skill: `/zenigame-codex-review` | あり | `/zenigame-fx-codex-review` に置換 |
| 関連 skill: `/zenigame-analyze-genome-archive` | 自動呼び出し | 未移植のためコメント化（将来 hook） |
| 関連 skill: `/zenigame-improve-cycle` | repeat 連携あり | improve-cycle 側からは呼ぶがこの skill から呼び返しはしない（疎結合） |
| ショート禁止 | あり（株式版） | 削除（FX はロング・ショート両方向許容） |
| 使命 | 日本株 | FX イントラデイ |

## skill 全体フロー（概念）

```
[args validation]
  ↓
[Step 1: 前提検証]
  - reports/run-reports/ ディレクトリ書込権限
  - DB 接続（任意・skip 可）
  ↓
[Step 2: BG 起動]
  nohup uv run python scripts/alpha_factory/run_ga.py {args} \
    > .cache/alpha_factory/runs/{run_id}.log 2>&1 &
  - run_id は事前生成（`run_$(TZ=UTC date +%Y%m%d_%H%M%S)`）して --run-id 引数で渡す
  - PID を取得し state file に記録
  ↓
[Step 3: ログ監視ループ]
  - 30 秒間隔で:
    a) tail -n 50 {log} | grep -E 'ERROR|Traceback|Exception' → 異常なら抽出
    b) grep -q 'ga.run.done' {log} → 完了
    c) ps -p {pid} > /dev/null → プロセス生存確認
  - 上限: 既定 60 分（CLI で `--timeout-min N` 指定可）
  ↓
[Step 4: 完了検出 — run_id 整合まで含めた 3 点確認]
  (a) ログに `ga.run.done` が出現し、その行に skill 側で生成した run_id が含まれる（grep -F で確認）
  (b) `.cache/alpha_factory/runs/genomes_{run_id}.parquet` が存在する（ファイル名で run_id バインド）
  (c) **summary.json パスは `[done] ... report={run_dir}` 行から取得**:
      - ログ末尾の `[done]` stdout 行を tail/grep で抽出し `report=` 以降を切り出す
      - そのパス配下の `summary.json` を読み、JSON の `run_id` が skill 側 run_id と一致することを確認
      - 並行 run / 他経路起動があっても run_dir はプロセス自身が出力した値なので誤認しない
  - (a)(b)(c) 全て満たして初めて「完了」。古い成果物との取り違えを防ぐ
  - `run_number` の確定は (c) で読んだ summary の `summary["run_number"]` を SoT とする（起動時点の `_estimate` は破棄）
  ↓
[Step 5: 結果確認]
  - Step 4 (c) で確定した summary.json をパースし
    best_fitness / stage_a_pass / stage_b_pass / stage_c_pass / graduation_count / run_number を取得
  ↓
[Step 6: 報告]
  - run_id / run_number / log path / archive path / Stage 通過数 / best fitness / live_pass を箇条書きで出力
  ↓
[Step 7: 失敗時の経路]
  - log から ERROR/Traceback を最大 50 行抽出
  - state file の status を `failed` 更新
  - exit code 非 0 で帰る
```

## 状態ファイルの責務境界

skill / orchestrator それぞれの state を分離する:

| ファイル | 責務 | source-of-truth |
|---------|------|----------------|
| `.cache/alpha_factory/current_cycle_state.json` | improve-cycle の **orchestration state**（cycle_index / phase / history / overrides） | improve-cycle skill |
| `.cache/alpha_factory/run_alpha_factory_state.json` | run-alpha-factory の **single run execution state**（PID / run_id / log path / args / status） | 本 skill |

- improve-cycle が将来本 skill を呼び出すように切り替えた際:
  - improve-cycle 側は `phase` と `cycle_index` を保持
  - 本 skill 側は `pid` と `run_id` を保持
  - 復旧時は **両ファイルを併読**し、本 skill 側 state を「現在進行中の run の SoT」、improve-cycle 側を「サイクル全体の SoT」として扱う
- 本 skill が単独実行された場合は本 skill 側 state のみ更新（improve-cycle 側 state は触らない）

ファイル: `.cache/alpha_factory/run_alpha_factory_state.json`

```json
{
  "skill": "zenigame-fx-run-alpha-factory",
  "step": "monitor",
  "pid": 12345,
  "run_id": "run_20260424_123600",
  "run_number_estimate": 6,
  "log_file": ".cache/alpha_factory/runs/run_20260424_123600.log",
  "args": ["--instrument", "USD_JPY", "--population-size", "48"],
  "started_at": "2026-04-24T12:36:00+09:00",
  "last_updated": "..."
}
```

`run_number` は run_ga.py 内部で `get_latest_run_number()+1` 確定するため、skill 起動時点では `_estimate` のみ保持し、完了後に **`[done] ... report={run_dir}` 行から run_dir を確定 → summary.json をパース → `summary["run_number"]` を SoT として上書き**する。

> **重要**: 並行 run（multi-pair / 別セッション）が走っている場合、`get_latest_run_number()+1` の値は競合し得る。よって skill 起動時の `_estimate` は **「ログメッセージ用の参考値」** に過ぎず、summary.json 配置先 (`reports/run-reports/run-{N}/`) を `_estimate` 値で予測してはならない。必ず `[done]` stdout 行から取得する。

## 設計判断 / トレードオフ

1. **--run-id を skill 側で生成して渡す** — run_ga.py 任せにすると stdout から sed で抽出が必要になりタイミング依存になる。skill 側で先に決めて log path / state file を即時に確定したい。run_ga.py の `--run-id` CLI はその目的で既に存在する。
2. **`nohup ... &` を採用、内製の `run_in_background=True` には依存しない** — Claude Code 環境固有の機能に依存させると CLI 直叩き互換が失われる。Bash で素直に BG 起動できる方が AGENTS.md の「dev サーバーは立ち上げない」運用とも整合的。
3. **archive Parquet 生成を完了サインの第二ソースに採用** — `ga.run.done` ログだけだと structlog 出力フォーマット変更に弱い。Parquet 生成は T015 schema で固定されており完了の hard signal。
4. **improve-cycle 本体は変更しない** — 本 PR は md only / 最小スコープ。improve-cycle の Phase 3 を skill 経由に切り替えるのは別 TODO（残課題）。
5. **「状態ファイル衝突」回避** — improve-cycle の state とパスを分離。両者が並走しても上書きしない。
6. **`--instrument` 等の引数は run_ga.py に passthrough** — skill 自身は意味解釈しない。`--timeout-min` のみ skill 自身の引数。

## 検証 (acceptance) と検証手段の限界

### 検証項目（本 PR で確認）

1. SKILL.md ファイルが `.claude/skills/zenigame-fx-run-alpha-factory/SKILL.md` に存在する。
2. 以下 grep が 0 件:
   ```
   grep -cE "docs/alpha-factory|src/trading|/zenigame-codex|~/.local/bin/codex-vscode|/zenigame-analyze-genome-archive|/zenigame-codex-review" .claude/skills/zenigame-fx-run-alpha-factory/SKILL.md
   ```
3. `AGENTS.md` の skill 一覧に新 skill が追加されている。
4. SKILL.md 内に `scripts/alpha_factory/run_ga.py` への呼び出しが含まれる。
5. SKILL.md 内に「状態ファイル `.cache/alpha_factory/run_alpha_factory_state.json`」への言及がある。
6. SKILL.md 内に **run_id 3 点整合**（log / archive Parquet / summary.json）の記述がある。

### 検証手段の限界（明示）

- 上記検証は **「skill ドキュメントの構造妥当性」** と **「完了検出経路のロバスト性」** を smoke でチェックするものである。
- **「実 GA run の内容妥当性」**（best fitness の意味解釈、live_criteria の達成判定の正しさ等）は本 skill のスコープ外であり、`zenigame-fx-analyze-run` / `zenigame-fx-run-report` 側で別途検証される。
- E2E smoke run（実 DB に対する 1 cycle 実行）は本 PR では行わず（cycle 21 で実施済）、本 PR は md only。

## 残課題（優先度順）

1. **improve-cycle Phase 3 切替** (P1) — 改善ループ統一の本丸。本 skill を呼び出すように改修し state file 二重管理を整理。
2. **zenigame-fx-analyze-genome-archive 移植** (P2) — Step 6 直後にチェイン呼び出し。改善示唆の解像度向上。
3. **multi-pair 並行 GA 起動対応** (P3) — state file の pid バインド、ロックファイル。複数通貨ペア探索の段階で必要。

優先度判断の根拠: 現在の North Star は「live_criteria を満たす個体を 1 つ見つけ出す」改善ループの確立。1 → 2 → 3 の順がこれに沿う。
