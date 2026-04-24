# Concept: post-run-review (BG テーマ別レビュー)

## 位置づけ

`zenigame-fx-improve-cycle` Phase 1 (analyze-run) 完了直後に **fire-and-forget** で起動する、テーマ別の戦略レビュー skill。
analyze-run が「直近 1 Run の事実集計」までを担うのに対し、post-run-review は **複数 Run 横断 + 改善設計 + TODO 登録までを 1 セッション内で完結**させる。

## 目的

- RUN 完了後にユーザー介入なしで「次の改善」を生成し、改善ループの回転を加速する
- analyze-run と同じ Run データを別系統で深掘りし、テーマ別の盲点を埋める
- Codex と議論して上位 2-3 件を `/zenigame-fx-alpha-design` → `/zenigame-fx-todo-add` まで自動完結させる

## テーマ (FX 版・暫定 5 テーマ)

| theme | 焦点 |
|-------|------|
| `signal-quality` | プリミティブ予測力・ルックアヘッド再点検・新規プリミティブ |
| `regime-awareness` | セッション/ボラ/レジーム分岐、cross-pair 共通因子 |
| `cost-efficiency` | スプレッド・スリッページ・スワップ・session_close フィルタ |
| `robustness` | DSR / PBO / WF-OOS / Sieve 整合・Stage gate 突破率 |
| `risk-management` | max_pos / time_stop / max_dd / live_criteria 達成パス |

> 株版固有テーマ（director-evolution / japan-market 等）は除外。
> ショート禁止条項は **削除**（FX はロング・ショート両方向許容）。

## 起動方式 (Claude Code Agent + run_in_background)

- **launch owner = `zenigame-fx-improve-cycle` Phase 1 末尾のみ**。analyze-run スタンドアロン実行時には自動起動しない (二重起動防止)
- analyze-run スタンドアロン実行後に手動でレビューを起動したい場合は runbook の「手動起動」コマンドを使う
- launcher は **テーマごとに 1 つの Agent** を `run_in_background: true` で起動
- 親 skill は launched marker (`.cache/alpha_factory/post-run-review-launched-{run_id}.json`) を書いて完了、結果待ちは行わない（fire-and-forget）
- 各 Agent は完全に独立（zenigame の systemd / Dramatiq / nohup は使わない）

## 1 セッションの責務 (テーマあたり)

1. 当該テーマで Open TODO が既にある → 即終了 (early-skip)
2. analysis-claude.md / analysis-codex.md / 直近 3 Run report を読む
3. テーマ専用 system prompt で Codex (gpt-5.3-codex medium) に 5-6 件の改善案を出させる
4. 重複・禁止事項・実現性チェックで上位 2-3 件に絞る
5. 各案について `/zenigame-fx-alpha-design` → `/zenigame-fx-todo-add` を**順次**実行
6. 残り候補を `.cache/alpha_factory/post-run-review-{theme}-deferred.md` に申し送り

## 成果物

- 設計ファイル群: `devnotes/{ts}-{topic}/conceptual-design.md` / `detailed-design.md`
- 新規 TODO 行（`docs/alpha_factory/TODO.md`）
- 申し送りメモ: `.cache/alpha_factory/post-run-review-{theme}-deferred.md`
- 実行ログ: `.cache/alpha_factory/post-run-review-{theme}-{run_id}.log`

## スコープ外（明示）

- GA パラメータの自動調整（→ `calibrate-gate` 整備後の責務）
- プリミティブ IC 同期（→ `primitive-ic-sync` 整備後の責務）
- Alpha Sieve 評価（→ `alpha-sieve` の責務）
- Run の起動・レポート生成（→ `run-alpha-factory` / `run-report` の責務）

## 関連 skill

- 上流: `zenigame-fx-analyze-run`, `zenigame-fx-improve-cycle`
- 下流: `zenigame-fx-alpha-design`, `zenigame-fx-todo-add`
- 共通規約: `zenigame-fx-codex-review`
