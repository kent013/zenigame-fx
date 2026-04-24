# 概念設計: skill port — zenigame-fx-plan-and-design

## 0. 前提（Verified / Assumed / To verify）

| # | 前提 | 状態 | 出典 / 検証方法 |
|---|------|------|----------------|
| P1 | `zenigame-plan-and-design` SKILL.md 651 行が移植元 | Verified | `/Users/ishitoya/repository/zenigame/.claude/skills/zenigame-plan-and-design/SKILL.md` を Read 済 |
| P2 | T020 (`zenigame-fx-analyze-run`) / T021 (`zenigame-fx-run-report`) が SKILL.md ベースで先行 port 済 | Verified | `.claude/skills/zenigame-fx-analyze-run/SKILL.md` / `.claude/skills/zenigame-fx-run-report/SKILL.md` を Read 済 |
| P3 | `zenigame-fx-codex-review` SKILL.md が使命・禁止事項・C1-C9 discipline・セッションモード規約を SSoT 化済 | Verified | `.claude/skills/zenigame-fx-codex-review/SKILL.md` を Read 済 |
| P4 | `zenigame-fx-alpha-design` / `zenigame-fx-todo-add` が存在し、設計フローと TODO 登録の責務分離が成立 | Verified | `.claude/skills/zenigame-fx-alpha-design/SKILL.md` / `.claude/skills/zenigame-fx-todo-add/SKILL.md` を Read 済 |
| P5 | `scripts/codex` が動作する（exec / exec resume / -o / --json オプション） | Verified | `scripts/codex` shim Read、T020/T021 の skill から実用例あり |
| P6 | `scripts/alpha_factory/todo_manager.py` が `next-id / add / add-conditional / get / close / obsolete / list` の subcommand を提供 | Verified | `--help` 実行で確認済 |
| P7 | `docs/alpha_factory/TODO.md` 形式（Open / Conditional テーブル）がある | Verified | Read 済 |
| P8 | `.cache/alpha_factory/current_cycle_state.json` を `zenigame-fx-improve-cycle` が `phase / cycle_index / tmp_dir / overrides / history` 形式で管理 | Verified | `zenigame-fx-improve-cycle/SKILL.md` で確認 |
| P9 | `config/alpha_factory/focus-theme.json` は **未存在**（zenigame は `.cache/alpha_factory/focus-theme.json`） | Verified | `find /Users/ishitoya/repository/zenigame-fx/config -name "focus-theme*"` 結果 0 件 |
| P10 | `zenigame-fx-post-run-review` / `zenigame-fx-alpha-sieve` / `zenigame-fx-set-focus` は **未移植** | Verified | `ls .claude/skills/` 結果に該当 dir なし |
| P11 | 815 tests passing baseline | Assumed | タスク指示文の前提値（実測は本 PR 範囲外、md only のため変動しないことのみ担保） |
| P12 | `zenigame-fx-analyze-run` skill が成果物として `analysis-claude.md` / `analysis-codex.md` の両方を `{tmp_dir}` に出力する（前者は `analyze_run.py` 直接出力、後者は skill が `scripts/codex` 経由で生成） | Verified | `zenigame-fx-analyze-run` SKILL.md §Step 2/3 |
| P13 | `config/alpha_factory/focus-theme.json` が将来 SSoT になる（`zenigame-fx-set-focus` 移植時もこのパスに従う） | Assumed → 将来 Verified | `docs/alpha_factory/README.md` で `config/alpha_factory/` を運用パスとして示しており整合。本 skill 採用パスを SSoT 候補とする |

**To verify**: なし（本 skill は md only、ランタイム検証は不要）。

## 1. 背景・課題

zenigame には改善計画策定スキル `zenigame-plan-and-design` が存在し、analyze-run の出力（`analysis-claude.md`, `analysis-codex.md`）を起点に **TODO 選定 → Codex 合議 → 分析マージ → 改善策合議 → 詳細設計 → Codex レビュー** までを統合している。

zenigame-fx 側ではこのフェーズが未整備で、`zenigame-fx-improve-cycle` の Phase 2 calibrate（軽量パラメータ調整）と Phase 3 implement の間に **「次 Run で何をどう変えるか」を Codex 合議で決める段階** が欠落している。結果、改善策の使命整合チェック・禁止事項違反検知・詳細設計レビューが個別実行になり、品質ゲートが分散する。

T020/T021 で `analyze-run` / `run-report` の SSoT 出力が確定した今、そこに繋がる **計画策定 skill の port** が次の論理的ピース。

## 2. 使命への直結（mission-facing 設計）

本 skill は **「live_criteria 未達要因 → 改善策候補 → Codex 承認済み詳細設計」までを一本に繋げる** ことで、使命達成の中間 KPI に直接寄与する。

### 2-1. live_criteria 未達要因マッピング

Phase A（TODO 選定）と Phase B（改善策合議）で、各候補は以下を必須記入する:

| 必須項目 | 内容 |
|---------|------|
| `target_metric` | live_criteria のどの項目（Sharpe / Total PnL / Max Drawdown / Trade Count / Cross-pair ii-lite）の改善を狙うか |
| `failure_mode` | 直近 Run の analyze-claude / analyze-codex で観測された未達症状（例: 「Stage C 個体ゼロ」「ii-lite Anchor 落ち集中」「Trade Count 過少」） |
| `causal_path` | 仮説する因果経路（例: 「primitive A の signal 偏在 → directional clause の方向性逸脱 → Stage B fold_sign_ratio 低下」） |
| `falsification` | この施策が無効と判断する観測条件（C9 falsification-first） |
| `success_criterion` | この施策が有効と判断する次 Run での観測条件（mission KPI に紐付け） |

これにより、「品質改善 of 品質改善」（プロセスのみ良くなる）を防ぎ、各施策が直接 mission KPI に効くことを担保する。

### 2-2. 中間 KPI（本 skill 導入後に観測）

| KPI | 期待 |
|-----|------|
| TODO 選定棄却率（Codex `todo-selection` 合議で SKIP/MERGE 判定された比率） | 健全な議論が回っているかの指標 |
| 設計レビュー差し戻し率（Codex `design-review` で REQUEST_CHANGES → APPROVED に至るラウンド数の中央値） | 設計品質の経時改善 |
| 同一論点再発率（plan-and-design で議論した論点が次 Run の analyze-claude で再出現する比率） | 議論が実質的だったかの追跡 |
| Stage C 通過率の cycle 間変化 | mission 直結 |
| ii-lite cross-pair pass 率 | mission 直結 |

これら中間 KPI の収集自体は **本 skill のスコープ外**（別 follow-up）。本 skill は KPI 観測の素地（必須記入欄）のみ提供する。

## 3. 改善アイデア

`zenigame-plan-and-design` を **zenigame-fx 規約** に沿って移植し、`.claude/skills/zenigame-fx-plan-and-design/SKILL.md` を新設する。

### 3-1. 改修方針

| 観点 | 元 | 改修後 |
|------|----|--------|
| docs パス | `docs/alpha-factory/` | `docs/alpha_factory/` |
| Codex review skill | `/zenigame-codex-review` | `/zenigame-fx-codex-review` |
| Codex VSCode skill | `/zenigame-codex-vscode` | `/zenigame-fx-codex-vscode` |
| Alpha Design skill | `/zenigame-alpha-design` | `/zenigame-fx-alpha-design` |
| TODO 追加 skill | `/zenigame-todo-add` | `/zenigame-fx-todo-add` |
| Analyze 連携 | `/zenigame-analyze-run` | `/zenigame-fx-analyze-run` |
| 使命 | 日本株イントラデイ（ロングオンリー） | FX イントラデイ（ロング/ショート両方向、スワップ/スプレッド反映） |
| 禁止事項 | ショート禁止あり | ショート禁止削除（FX の性質）。ただし「ショート追加で見かけだけ改善していないか」は点検項目に追加 |
| focus theme 例 | director-evolution 等の株式テーマ | signal-quality / regime-awareness / cost-efficiency / cross-pair-robustness 等 FX テーマ |
| focus-theme JSON 読み先 | `.cache/alpha_factory/focus-theme.json` | `config/alpha_factory/focus-theme.json` |
| post-run-review 連携 | `/zenigame-post-run-review` を呼ぶ | **コメント化**（zenigame-fx-post-run-review 未移植）+「整備後に接続」を明記 |
| alpha-sieve 連携 | あれば呼び出す | **コメント化**（zenigame-fx-alpha-sieve 未移植）+「整備後に接続」を明記 |
| TODO manager | `bash scripts/todo_manager.sh ...` | `uv run python scripts/alpha_factory/todo_manager.py ...` |
| 状態ファイル | `.cache/alpha_factory/current_cycle_state.json` | 同（zenigame-fx も同パス使用、improve-cycle と整合） |
| 使命・禁止事項 | skill 内に直接記述 | `zenigame-fx-codex-review` SKILL.md 継承（重複記載なし）。継承点は §6 で固定 |
| 合議ループ上限 | 通常 3 / 繰り返し 10 | 通常 3 / 繰り返し 5（**短縮**：合議長文化のリスク低減） |
| 合議終結条件 | APPROVED まで | APPROVED **または** 「1 つの反証可能仮説 + 1 つの最小変更」に収束したら強制決着 |

### 3-2. 期待効果（mission-facing）

- **Stage C 通過率の押し上げ**: 各 TODO に target_metric / causal_path 必須化により、Stage C 阻害要因に直接対処する施策を優先選定
- **cross-pair ii-lite pass 率の改善**: failure_mode に「ii-lite Anchor 落ち」を明示する仕組み
- **コスト控除後 PnL 悪化要因の特定**: スワップ・スプレッド反映を Phase B プロンプトの判定基準に固定
- **改善ループの短時間化**: 合議終結条件強化により、文書整合性最適化への陥り防止

副次効果（プロセス品質、mission 寄与は間接）:
- autopilot / improve-cycle の Codex 品質ゲート復活
- TODO 選定の自動化
- 詳細設計の波及変更漏れ検知

## 4. 実装方針（概要）

### 4-1. 構成（T020/T021 スタイル踏襲）

```
.claude/skills/zenigame-fx-plan-and-design/SKILL.md
```

YAML フロントマター:
```yaml
---
name: zenigame-fx-plan-and-design
description: zenigame-fx Alpha Factory 改善の計画策定（TODO 選定 + Codex 合議 + 分析マージ + 改善策合議 + 詳細設計 + Codex レビュー）
argument-hint: "<tmp_dir> [run_id] [--repeat] [--skip-todo] [--skip-consensus]"
---
```

### 4-2. セクション構造（最終 SKILL.md の章立て）

1. タイトル + 目的
2. 引数表
3. 入力 / 出力一覧 — `{tmp_dir}/analysis-claude.md`, `analysis-codex.md`, `docs/alpha_factory/TODO.md` を入力、`improvement-plan.md`, `detailed-design.md` 等を出力
4. **責務境界の明示**:
   - **本 skill が行うこと**: 改善計画策定 / Codex 合議 / 詳細設計レビュー / TODO 選定（incremental の選定のみ）
   - **本 skill が行わないこと**: GA Run 実行 / TODO 実装 / 新規 TODO 登録（追加は `zenigame-fx-todo-add` の責務）
5. 呼び出し契約（現状 manual + 将来 improve-cycle / autopilot から）
6. 使命・思考原則・禁止事項（codex-review SSoT 継承宣言、FX 固有制約のみ再掲、**継承先必須節名固定リスト**を明記）
7. Phase A: TODO 選定 & Codex 議論
8. Phase B: 分析マージ & 改善策合議
9. Phase C: 詳細設計 & Codex レビュー合議
10. 状態ファイル更新仕様（**本 skill が更新する key を明記**）
11. エラーハンドリング
12. 使用例
13. 未接続 hook（整備後に起動）

### 4-3. 継承先 `zenigame-fx-codex-review` の必須節名固定

本 skill は以下の節を SSoT として参照する。継承先がこの節名を変更する場合、本 skill も同期更新する（波及変更チェック対象）:

- §「使命・禁止事項（全 Codex 呼び出しに自動適用）」（思考原則 / 使命 / 絶対制約 / 禁止事項 / ツール使用制限 / レビュー重点項目 / C1-C9 discipline）
- §「One-shot モード」（exec --ephemeral）
- §「セッションモード」（exec / exec resume / SESSION_ID 抽出方法）
- §「session_label の命名規則」（`consensus` / `design-review` / `conceptual-review` / `impl-review` / `todo-selection`）

### 4-4. 状態ファイル更新責務

`.cache/alpha_factory/current_cycle_state.json` に対し、本 skill は **読み書き両方** を行う。更新する key と書き込みタイミング:

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
| `improvement_plan` | Phase B-4 完了時 | `improvement-plan.md` のパス |
| `detailed_design` | Phase C-3 完了時 | `detailed-design.md` のパス |
| `last_updated` | 各書き込み時 | ISO8601 |

`zenigame-fx-improve-cycle` 側の key（`cycle_index` / `run_number` / `next_run_number` / `overrides` / `history` / `repeat_mode` / `observe_only` / `started_at`）は **書き込まない**（読むのみ）。

### 4-5. focus-theme.json fallback

`config/alpha_factory/focus-theme.json` が **未存在の場合**:

- `focus_theme = "general"` / `focus_policy = null` で固定
- A-2 Codex プロンプトの「【最優先】フォーカステーマ」セクションは「（focus-theme 未設定。一般原則に従う）」に置換
- Phase A 選定基準 0（フォーカステーマ優先）はスキップし、選定基準 1-4 のみ適用

### 4-6. FX 固有 Codex プロンプト改修

| 元プロンプト | 改修 |
|-----------|------|
| director-evolution / BollingerRevert 等の株式固有名 | FX 中立例に置換（具体的 primitive 名は記載せず、Clause 構造のみ言及） |
| Run 79 で TNV ルックアヘッド修正後... | 削除（zenigame-fx には無い歴史） |
| ProhibitionMask + Clause 合成 | zenigame-fx の Clause 構造（directional × local_gate × weight）に置換 |
| 6 ワーカー並列 | macOS / 24GB / 6 ワーカー並列（1 ワーカー約 3GB）と明示 |
| ロングオンリー | 削除、「ロング/ショート両方向、スワップ・スプレッド反映」に置換 |
| - | **追加**: 禁止事項 1 (期間延長) / 2 (見栄え改善) / 4 (live_criteria 緩和) / 6 (取引回数削減) / 7 (オーバーナイト) を Phase A/B プロンプトに rejection rule として明記 |
| - | **追加**: 「ショート追加で見かけだけ改善していないか」を Phase B 点検項目に追加 |

### 4-7. 合議ループ収束強化

各 Round の Codex プロンプトに次を追加:

```
【ループ収束ルール】
本ラウンドで以下のいずれかに収束させること:
1. APPROVED（全 Critical/Warning 解消）
2. 1 つの反証可能仮説 + 1 つの最小変更に絞り込み「次 Run で検証」と申し送る
ループは通常 3 ラウンド / 繰り返しモード 5 ラウンドで強制終了。終了時に未解決項目があれば「保留事項」として improvement-plan.md に記録する。
```

### 4-8. 検証

```bash
grep -cE "docs/alpha-factory|src/trading|/zenigame-codex|~/.local/bin/codex-vscode|/zenigame-alpha-design|/zenigame-todo-add|/zenigame-analyze-run|/zenigame-post-run-review" .claude/skills/zenigame-fx-plan-and-design/SKILL.md
```

→ **0 件**

### 4-9. 未接続 hook の契約

| hook | skill 内記述 | 不在時の挙動 |
|------|------------|-----------|
| `zenigame-fx-post-run-review` | A-1 滞留 TODO 棚卸し「post-run-review に委ねる」分岐 / Phase D 後段の自動起動 | **no-op、成果物要求なし**。「整備後に接続」コメント |
| `zenigame-fx-alpha-sieve` | cycle_focus 判定や次サイクル候補での参照 | **no-op、成果物要求なし**。「整備後に接続」コメント |
| `zenigame-fx-set-focus` | focus-theme.json の更新 | **no-op**。focus-theme.json 不在時は §4-5 fallback |

`improve-cycle` / `autopilot` 側は **未移植 hook の成果物を期待しない**（unblock）。

## 5. 制約・前提

- 既存の `zenigame-fx-codex-review` / `zenigame-fx-codex-vscode` が使命・禁止事項を一元管理しており、本 skill は重複記述しない
- `scripts/codex` / `scripts/alpha_factory/todo_manager.py` が動作することが前提（Verified §0-P5/P6）
- `config/alpha_factory/focus-theme.json` は本 TODO の範囲では新設しない（fallback §4-5 を明記）
- `.cache/alpha_factory/current_cycle_state.json` 形式は zenigame-fx-improve-cycle と整合させる（§4-4）

## 6. スコープ外

- `zenigame-fx-post-run-review` の port（別 TODO）
- `zenigame-fx-alpha-sieve` の port（別 TODO）
- `zenigame-fx-set-focus` / `focus-theme.json` 自動生成（別 TODO）
- `zenigame-fx-improve-cycle` 本体の改造（plan-and-design を呼ぶ経路接続は follow-up TODO）
- `zenigame-fx-autopilot` 本体の改造（同上）
- 中間 KPI（§2-2）の自動収集
- TODO.md に登録される具体的な施策の合議実行（本 skill は frame 提供、運用は別サイクル）
- GA Run 実行 / TODO 実装 / 新規 TODO 登録

## 7. リスク

| リスク | 対策 |
|-------|------|
| 合議長文化により実験速度ではなく文書整合性が最適化される（mission 逸脱） | §4-7 ループ収束強化（強制終結ルール）+ 上限ラウンド数短縮（10 → 5） |
| 継承先 `zenigame-fx-codex-review` の更新で本 skill の挙動が暗黙に変わる | §4-3 継承先必須節名固定 + 波及変更チェック対象に明示 |
| focus-theme.json 不在時に一般論へ流れる | §4-5 fallback で「general」固定し、選定基準 0 を skip（明示的縮退） |
| skip_todos 判定が `design stale` で大量発生し TODO が枯渇 | post-run-review 整備後にリビルドする旨をコメント化（本 skill 範囲外） |
| zenigame-fx-improve-cycle が本 skill の出力を期待していない（未接続） | 呼び出し契約「現状 manual / 将来 improve-cycle」を明記、follow-up TODO 化 |

## 8. 受け入れ基準

1. `.claude/skills/zenigame-fx-plan-and-design/SKILL.md` が新規作成される
2. zenigame 側の URL / パス / skill 名が **0 件** （§4-8 grep）
3. 使命・禁止事項は `zenigame-fx-codex-review` 継承宣言のみで、重複記述なし
4. 未移植 hook（post-run-review / alpha-sieve / set-focus）はコメント化 + 「no-op、成果物要求なし、整備後に接続」を明記
5. T020 / T021 と同等の章立て（呼び出し契約 / 入出力一覧 / 使命継承宣言 / エラーハンドリング / 使用例）
6. 継承先 `zenigame-fx-codex-review` の必須節名（§4-3）が SKILL.md 内で参照されている
7. Phase A / B 各 Codex プロンプトに、TODO の `target_metric` / `failure_mode` / `causal_path` / `falsification` / `success_criterion` 必須記入が明記される
8. 合議ループ収束ルール（§4-7）が SKILL.md 内に記載される
9. 状態ファイル更新責務（§4-4）が SKILL.md 内に記載される
10. focus-theme fallback（§4-5）が SKILL.md 内に記載される
11. 既存テストが影響を受けない（md only、現行テスト baseline を非悪化に維持）

## 9. 参照ドキュメント / コード（Design-first 証拠）

本概念設計策定時に参照済:

- `/Users/ishitoya/repository/zenigame/.claude/skills/zenigame-plan-and-design/SKILL.md`（移植元 651 行）
- `/Users/ishitoya/repository/zenigame-fx/.claude/skills/zenigame-fx-codex-review/SKILL.md`（使命 SSoT）
- `/Users/ishitoya/repository/zenigame-fx/.claude/skills/zenigame-fx-codex-vscode/SKILL.md`（呼び出し規約）
- `/Users/ishitoya/repository/zenigame-fx/.claude/skills/zenigame-fx-analyze-run/SKILL.md`（T020 port 例）
- `/Users/ishitoya/repository/zenigame-fx/.claude/skills/zenigame-fx-run-report/SKILL.md`（T021 port 例）
- `/Users/ishitoya/repository/zenigame-fx/.claude/skills/zenigame-fx-alpha-design/SKILL.md`（責務分離: 設計と TODO 登録）
- `/Users/ishitoya/repository/zenigame-fx/.claude/skills/zenigame-fx-todo-add/SKILL.md`（責務分離: TODO 追加）
- `/Users/ishitoya/repository/zenigame-fx/.claude/skills/zenigame-fx-improve-cycle/SKILL.md`（state file schema）
- `/Users/ishitoya/repository/zenigame-fx/scripts/codex`（Codex CLI shim）
- `/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/todo_manager.py`（subcommand 確認）
- `/Users/ishitoya/repository/zenigame-fx/docs/alpha_factory/TODO.md`（テーブル形式確認）
- `/Users/ishitoya/repository/zenigame/.cache/alpha_factory/focus-theme.json`（zenigame 側形式の参考）
- `git log` 直近 5 コミット（`0922e28` ... `f76d65b`、本 skill 移植と直接の競合なし）
