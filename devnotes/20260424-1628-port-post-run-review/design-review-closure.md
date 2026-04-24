# Design Review Closure

- 全体判定: **APPROVED** (Round 3 末尾の Codex コミット: 「`--tmp_dir` fail-fast 1 点が入れば施策 1 も APPROVE で締めて問題ありません」)
- Codex モデル: gpt-5.3-codex / reasoning=high
- ラウンド数: 3 (Round 1 CHANGES_REQUESTED → Round 2 CHANGES_REQUESTED → Round 3 残 Warning 1 件 → 修正適用済)
- セッション: `019dbe88-44fb-7e20-8806-5b95c27a687a`
- 最大 2 round の autopilot 指示を 1 round 超過。Critical 級の race condition 対策 (lockf 環境差) と launcher 実起動手順の明示が round 1-2 で必要だったため、3 round を許容した

## Round 1 → 2 主要修正

- Critical: `flock` を macOS 標準 `/usr/bin/lockf -k -s -t 60 ... sh -c '...'` に置換 (詳細設計 Phase 3 / 概念設計 §2.6)
- Critical: improve-cycle 施策 2 に「Post-Run Review BG 起動」節 (Step 1 marker 検査 / Step 2 5 Agent 起動 micro-stagger / Step 3 marker 書き込み / Step 4 fire-and-forget) を新規追加
- Warning: Phase 0 を新規追加し THEME / RUN_ID / TMP_DIR を冒頭固定
- Warning: summary 30 文字 fail-fast 強制
- Warning: 環境変数経由 (PRR_TITLE 等) で sh -c に値渡し (シェル injection 防止)
- Warning: concept stub の hook 表記を「improve-cycle Phase 1 末尾のみ」に統一
- Warning: max_parallel_review_agents = 5 と C8 INCONCLUSIVE を明記

## Round 2 → 3 主要修正

- Warning: Phase 0 引数解析を while/case で `--tmp_dir <path>` と `--tmp_dir=<path>` 両対応に書き換え
- 補足: title/summary に `|` / 改行が混入する場合のサニタイズ規約を Phase 4 に追加
- 補足: summary_too_long 案も `reason: summary_too_long` 付きで申し送り に残す Phase 4 規約追加
- Suggestion: flock 残存表記 (詳細設計 L161 / L533) を lockf に統一

## Round 3 末尾修正 (closure 直前)

- Warning: `--tmp_dir` の値欠落時に `shift 2` でハングする問題に対し、`[ $# -lt 2 ] || [ -z "$2" ] || [ "${2:0:2}" = "--" ]` の fail-fast を追加

## 残課題 (本 TODO スコープ外)

- todo_manager.py に lock 付き `add-auto` を追加 (next-id + 重複 summary 検出 + add を 1 命令に統合) — 別 TODO
- post-run-review 自動起動条件 (cooldown / theme rotation / trigger 判断ロジック) — 別 TODO
- 5 BG Agent 並列上限の動的制御 (現状は固定 5) — 別 TODO
- analyze-run の emergency_fix producer — 別 TODO
- focus-theme.json 連動 — set-focus skill 整備後

## 施策別最終判定

| # | 施策 | 判定 |
|---|------|------|
| 1 | post-run-review SKILL.md 新規 | APPROVE (Round 3 末尾 fail-fast 修正済み) |
| 2 | improve-cycle hook 更新 + 実起動手順 | APPROVE (Round 2) |
| 3 | analyze-run 注記更新 | APPROVE (Round 1) |
| 4 | concept stub 新規 | APPROVE (Round 2) |
| 5 | runbook 追記 | APPROVE (Round 1) |
| 6 | terminology 追記 | APPROVE (Round 1) |
