# Archived Skills

zenigame（日本株 Alpha Factory）から流用した skill 群のうち、以下のいずれかの理由で `_archived/` に退避している:

1. zenigame 固有インフラ（systemd / Dramatiq / Discord / J-Quants）依存で zenigame-fx 環境では動作しない
2. zenigame-fx-* 版に既に移植済みで、zenigame 版は reference のみ

`_archived/` プレフィックスは Claude Code の skill 候補一覧から除外される（実地検証: 2026-04-21）。

## 退避された skill 一覧（合計 21 件）

### A. インフラ依存で動作不可 (7 件、cycle 1 / T001 で archive)

| skill | 退避理由 | 復活条件 |
|-------|---------|---------|
| `zenigame-enqueue-task` | Dramatiq + RabbitMQ ワーカー依存 | zenigame-fx に Dramatiq/RabbitMQ ベースのキュー基盤を整備した時 |
| `zenigame-manage-alert` | systemd + Discord 通知依存 | zenigame-fx に Discord 通知 + systemd サービス整備した時 |
| `zenigame-manage-timer` | systemd timer 依存 | systemd サービス整備した時 |
| `zenigame-restart-worker` | systemd worker 依存 | systemd ワーカー整備した時 |
| `zenigame-troubleshoot-worker` | systemd worker 依存 | 同上 |
| `zenigame-primitive-ic-eval` | J-Quants API + 日本株プリミティブ registry 依存 | zenigame-fx 用 primitive registry 整備 + IC 評価再設計 |
| `zenigame-primitive-ic-sync` | J-Quants + プリミティブ registry 依存 | 同上 |

### B. zenigame-fx-* 版あり、reference 保持目的 (14 件、cycle 23 以降で archive)

| zenigame-* skill | zenigame-fx-* 版 | port 完了 cycle |
|------------------|------------------|----------------|
| `zenigame-alpha-design` | `zenigame-fx-alpha-design` | T003 (cycle 3) |
| `zenigame-analyze-run` | `zenigame-fx-analyze-run` | T020 (cycle 23) |
| `zenigame-batch-ga` | `zenigame-fx-batch-ga` | T003 |
| `zenigame-clear-cache` | `zenigame-fx-clear-cache` | T003 |
| `zenigame-codex-review` | `zenigame-fx-codex-review` | T003 |
| `zenigame-codex-vscode` | `zenigame-fx-codex-vscode` | T003 |
| `zenigame-implement` | `zenigame-fx-implement` | T003 |
| `zenigame-improve-cycle` | `zenigame-fx-improve-cycle` | (縮小版、T018 統合の上位 wrapper として再構築予定) |
| `zenigame-manage-sessions` | `zenigame-fx-manage-sessions` | T003 |
| `zenigame-profile-optimize` | `zenigame-fx-profile-optimize` | 2026-04-25 |
| `zenigame-snapshot` | `zenigame-fx-snapshot` | T003 |
| `zenigame-todo-add` | `zenigame-fx-todo-add` | T003 |
| `zenigame-todo-close` | `zenigame-fx-todo-close` | T003 |
| `zenigame-update-docs` | `zenigame-fx-update-docs` | T003 |

## まだ port されていない zenigame-* skill（残存、reference 兼）

以下は zenigame-fx 版が**未整備**のため `.claude/skills/zenigame-{name}/` に残存。Claude Code 候補一覧には現れる:

| skill | 整備優先度 | 備考 |
|-------|-----------|------|
| `zenigame-analyze-genome-archive` | High | 深層 archive 分析（T020 で shallow read のみ implement） |
| `zenigame-plan-and-design` | High | TODO 選定 + Codex 合議 |
| `zenigame-run-report` | High | run-reports/run-N.md 生成 |
| `zenigame-run-alpha-factory` | High | GA 実行 wrapper（fx-run-ga.py 既実装、wrapper として整備可） |
| `zenigame-recent-trends` | Medium | 横断観測レポート |
| `zenigame-strategic-codex-debate` | Medium | 多段 Codex 議論 |
| `zenigame-calibrate-gate` | Medium | Stage A threshold 動的調整 (Phase 4) |
| `zenigame-update-run-metrics` | Medium | run-metrics-summary.md 更新 |
| `zenigame-post-run-review` | Medium | テーマ別レビュー (Phase 4) |
| `zenigame-set-focus` | Low | focus-theme 切替 |
| `zenigame-alpha-sieve` | Low | OOS Sieve (Phase 4) |

## 復活手順

A の場合（インフラ依存）:
1. zenigame-fx 側に対応インフラ整備（系統的な別 TODO）
2. `_archived/{skill}` を `.claude/skills/zenigame-fx-{skill_short}/` に **新規作成**として port（古い skill を直接 mv しない）
3. fx 環境向けに使命・禁止事項・パス・依存パッケージを書換
4. 動作確認

B の場合（reference 保持）:
- 通常は **復活しない**（fx-* 版が active）。zenigame 側 implementation を参照したいだけなら `_archived/{skill}/SKILL.md` を直接 Read

## 注意

- A の skill は **そのままでは zenigame-fx 環境で動かない**
- B の skill は zenigame-fx-* 版が SSoT、zenigame-* は変更禁止（reference のみ）
- 設計パターンの参考としてのみ参照可
- 本番運用で archived skill を呼び出してはならない
