# zenigame-* スキル群の zenigame-fx への完全移植設計

**作成日時**: 2026-04-21 18:50 (JST)
**対象**: `.claude/skills/zenigame-*` 全 31 skill
**ゴール**: zenigame-fx プロジェクト向けに要否判定し、残すものは `zenigame-fx-*` 名前空間でリネーム＋内容適合させ、依存する基盤も FX 側に新設して完全移植する。

---

## 背景

- `zenigame`（日本株予測）で育った Alpha Factory / Codex 合議 / TODO 管理 / Sieve OOS 等の改善基盤を、`zenigame-fx`（FX 取引版）に移植する。
- 31 skill のうち多くは日本株固有インフラ（systemd ワーカー、Dramatiq/RabbitMQ、Discord 通知、J-Quants API、Stage A/B/C ゲート、プリミティブ registry など）に依存しており、素のリネームでは動かない。
- 前回の試作 (`.claude/skills/zenigame-fx-improve-cycle/`) は下請けスキル呼び出しを全て省略した縮小版で、本家の思想（合議・設計・OOS 検証）を取りこぼしている。これは Phase 3 で本家相当に置換する。

## FX プロジェクトの現状

**実装済み**:
- OANDA API からの価格取得、PostgreSQL 格納（`src/ingest/`, `src/db/`）
- シンプルな GA (`src/ga/runner.py`, `scripts/ga_run.py`)
- DSL（戦略表現）`src/dsl/`
- バックテストエンジン `src/backtest/`
- walk-forward (`scripts/walk_forward.py`)
- grid-search (`scripts/grid_search.py`)
- 6 通貨ペア × 3 年 × 1m バー

**未実装（本移植で新設する）**:
- Alpha Factory の Stage A/B/C ゲート
- ゲノム archive (Parquet)
- TODO 管理フロー（概念設計→詳細設計→TODO登録→worktree 実装）
- Codex 合議パイプライン（codex-vscode 経由）
- focus-theme.json によるテーマ駆動改善サイクル
- post-run-review BG セッション（Claude Code の local-agent BG で代替）
- Alpha Sieve（OOS 検証フレームワーク）
- FX プリミティブ registry（後回し検討）

**移植に含めない（DROP）**:
- Dramatiq/RabbitMQ ワーカー
- systemd サービス（zenigame-worker, zenigame-alert, zenigame-timer）
- J-Quants API（FX には不要、OANDA が該当）
- Discord 通知
- 日本株固有の primitive registry

---

## 31 skill の判定一覧

### DROP（7 個）— systemd/Dramatiq/Discord/J-Quants 依存で FX に該当インフラがない

| # | skill | 理由 |
|---|-------|------|
| 1 | zenigame-enqueue-task | Dramatiq + RabbitMQ 依存 |
| 2 | zenigame-manage-alert | Discord + systemd 依存 |
| 3 | zenigame-manage-timer | systemd timer 依存 |
| 4 | zenigame-restart-worker | systemd worker 依存 |
| 5 | zenigame-troubleshoot-worker | systemd worker 依存 |
| 6 | zenigame-primitive-ic-eval | J-Quants + プリミティブ registry 依存 |
| 7 | zenigame-primitive-ic-sync | J-Quants + プリミティブ registry 依存 |

→ `.claude/skills/_archived/` に退避して保管。将来 FX 用 primitive registry / task queue を整備した際に復活検討。

### RENAME-ONLY（9 個）— パス・参照の置換のみで移植可

| # | 旧 | 新 | 改修点 |
|---|----|----|--------|
| 1 | zenigame-codex-vscode | zenigame-fx-codex-vscode | 説明文のみ |
| 2 | zenigame-codex-review | zenigame-fx-codex-review | 使命・禁止事項を FX 版に差し替え |
| 3 | zenigame-manage-sessions | zenigame-fx-manage-sessions | そのまま |
| 4 | zenigame-clear-cache | zenigame-fx-clear-cache | namespace は `alpha_factory`, `http` 等 FX 側のもの |
| 5 | zenigame-snapshot | zenigame-fx-snapshot | winners/candidates は FX 用ディレクトリ |
| 6 | zenigame-batch-ga | zenigame-fx-batch-ga | GA パラメータ呼び出しを fx-run-ga にリダイレクト |
| 7 | zenigame-todo-close | zenigame-fx-todo-close | TODO.md のパス差し替え |
| 8 | zenigame-alpha-design | zenigame-fx-alpha-design | 使命・禁止事項を FX 版に差し替え |
| 9 | zenigame-update-docs | zenigame-fx-update-docs | ドキュメント対象パスを FX 版に差し替え |

### CONTENT-ADAPT（11 個）— 内容を FX 向けに書き換え

| # | 旧 | 新 | 主な改修点 |
|---|----|----|-----------|
| 1 | zenigame-run-alpha-factory | zenigame-fx-run-ga | Stage A/B/C フック削除→後に FX 用 Stage 追加。scripts/alpha_factory/run_ga.py を呼び出す |
| 2 | zenigame-run-report | zenigame-fx-run-report | adaptive_mission_pass → live_criteria pass、FX 指標追加 |
| 3 | zenigame-analyze-run | zenigame-fx-analyze-run | post-run-review BG 起動は local-agent 版に置換 |
| 4 | zenigame-analyze-genome-archive | zenigame-fx-analyze-genome-archive | ゲノム schema を FX 版に差し替え |
| 5 | zenigame-plan-and-design | zenigame-fx-plan-and-design | post-run-review 参照を local-agent 版に |
| 6 | zenigame-implement | zenigame-fx-implement | worktree 実装は同じ、テストは pytest, Alpha Factory schema 差し替え |
| 7 | zenigame-improve-cycle | zenigame-fx-improve-cycle | Phase 1-5 構成はそのまま、primitive-ic-sync 呼び出しは外す or FX 版条件付きに |
| 8 | zenigame-recent-trends | zenigame-fx-recent-trends | sieve 参照を FX 版 Sieve に、live_criteria は FX 版 |
| 9 | zenigame-set-focus | zenigame-fx-set-focus | テーマ定義を FX 向けに差し替え（下記） |
| 10 | zenigame-strategic-codex-debate | zenigame-fx-strategic-codex-debate | J-Quants 参照削除、FX 市場構造記述に差し替え |
| 11 | zenigame-todo-add | zenigame-fx-todo-add | TODO.md パス、テーマ定義 FX 版 |
| 12 | zenigame-profile-optimize | zenigame-fx-profile-optimize | プロファイル対象を fx-run-ga に |

※ 11 個と書いたが実際 12 個。表を優先する。

### INFRA-ADAPT（4 個）— FX 側に基盤新設が必要

| # | 旧 | 新 | 新設する FX 基盤 |
|---|----|----|-----------------|
| 1 | zenigame-calibrate-gate | zenigame-fx-calibrate-gate | Stage A/B/C ゲート相当（walk-forward ベースの OOS gate）を src/alpha_factory/ に新設 |
| 2 | zenigame-post-run-review | zenigame-fx-post-run-review | Claude Code の local-agent BG セッション launcher を新設 |
| 3 | zenigame-alpha-sieve | zenigame-fx-alpha-sieve | FX OOS Sieve（別期間バックテスト＋評価）を scripts/alpha_factory/ に新設 |
| 4 | （新設） | zenigame-fx-primitive-ic | FX 用 primitive（技術指標の予測力評価）を新設。優先度低、Phase 4 終盤 |

---

## FX Alpha Factory 基盤の新設事項

### A. Stage A/B/C ゲート

**設計**:
- **Stage A**: GA の IS フィットネス評価（現状の scripts/ga_run.py 相当）
- **Stage B**: 別期間での OOS 検証（walk_forward.py を使い、直近 N ヶ月で再評価）
- **Stage C**: live_criteria（sharpe, total_pnl, max_drawdown, trade_count）を満たすか判定

**実装場所**: `src/alpha_factory/stage_gate.py`
**設定**: `config/alpha_factory/default.yaml` に以下追加
```yaml
stage_gate:
  stage_b:
    enabled: true
    oos_window_days: 60  # IS 期間直後の OOS 期間
    min_trade_count: 10
    min_sharpe: 0.3
  stage_c:
    enabled: true
    # live_criteria に準拠
```

### B. ゲノム archive schema

**出力**: `.cache/alpha_factory/runs/genomes_{run_id}.parquet`
**カラム**:
- `run_id`, `generation`, `individual_name`
- `fitness`, `stage_a_pass`, `stage_b_pass`, `stage_c_pass`
- `trade_count`, `total_pnl`, `sharpe`, `sortino`, `max_drawdown_pct`, `profit_factor`
- `genome_json`（シリアライズ済み DSL）
- `parent_a`, `parent_b`（系譜追跡）

**実装場所**: `src/alpha_factory/archive.py`

### C. TODO 管理

**ファイル**:
- `docs/alpha_factory/TODO.md` — Open / In-Progress / Closed / Obsoleted セクション
- `scripts/alpha_factory/todo_manager.sh` — `add`, `close`, `obsolete`, `list` サブコマンド

**設計方針**: zenigame の設計をほぼそのまま踏襲。テーマ定義だけ FX 版に差し替え。

### D. focus-theme.json

**テーマ定義（FX 版）**:
```json
{
  "themes": {
    "signal-quality": {"description": "エントリーシグナルの的中率・期待値"},
    "speed": {"description": "スリッページ・約定遅延を考慮した現実的 fitness"},
    "technical-strength": {"description": "テクニカル指標の組み合わせと頑健性"},
    "robustness": {"description": "多通貨ペア・多期間での安定性"},
    "cost-efficiency": {"description": "スワップ・スプレッドを含めた純利益最大化"},
    "risk-management": {"description": "ドローダウン・Kelly・ポジションサイズ制御"}
  },
  "current_focus": null
}
```

**実装場所**: `config/alpha_factory/focus-theme.json`

### E. Alpha Factory ドキュメント体系

**ディレクトリ**: `docs/alpha_factory/`
- `README.md` — Alpha Factory FX の設計思想、使命、Stage A/B/C、改善サイクル
- `TODO.md` — TODO 管理
- `terminology.md` — 用語集（FX 市場 + Alpha Factory 概念）
- `runbook.md` — 運用ガイド（improve-cycle の回し方、troubleshooting）
- `codex-discipline.md` — Codex 合議で守るべき原則（C1-C9）

### F. Post-run-review BG セッション

**設計**: zenigame では systemd + Dramatiq で BG ジョブ化していたが、FX では Claude Code の **local-agent BG** を使う。

**呼び出し**:
- post-run-review skill 内で `Agent({run_in_background: true, subagent_type: "general-purpose", prompt: "テーマ X の分析..."})` を起動
- 分析結果は `devnotes/{tmp_dir}/post-run-review-{theme}.md` に書き込み
- manage-sessions で生存監視

**実装**: skill SKILL.md に手順を記述。scripts は不要。

### G. Alpha Sieve OOS フレームワーク

**設計**:
- Stage C を通過したゲノムのみ対象
- さらに別期間（例: IS+OOS の後の 3 ヶ月）でバックテスト
- 通過条件: `sharpe > 0.5` かつ `trade_count > 10` かつ `total_pnl > 0`
- 通過ゲノムは `reports/alpha-sieve/{yyyy-mm}/sieve-R{run_number}.md` に記録

**実装場所**: `scripts/alpha_factory/run_alpha_sieve.py`

### H. FX プリミティブ registry（Phase 4 終盤）

**設計**:
- FX 用の primitive = 単一の技術指標（RSI, MACD, Bollinger, ATR, EMA cross など）
- 各 primitive を過去 N 日のリターンと比較し IC（Information Coefficient）算出
- `primitive_ic_summary.json` に書き出し、IC が低い primitive を RETIRE 候補に

**実装場所**: `src/alpha_factory/primitives/` + `scripts/alpha_factory/primitive_ic_eval.py`

---

## Skill 依存グラフ

```
improve-cycle（オーケストレータ）
├─ analyze-run
│  └─ post-run-review（BG 起動）
│     └─ alpha-design → todo-add
├─ plan-and-design
│  ├─ codex-review（合議）
│  └─ alpha-design → todo-add
├─ calibrate-gate
├─ implement（複数 TODO 並列）
│  ├─ codex-review（実装レビュー）
│  └─ todo-close
├─ run-ga（旧 run-alpha-factory）
│  └─ analyze-genome-archive
├─ run-report
│  └─ update-run-metrics（廃止 or 統合）
└─ alpha-sieve

batch-ga（独立）
├─ snapshot
├─ calibrate-gate
├─ run-ga
└─ run-report

profile-optimize（独立ループ）
├─ run-ga --profile
├─ alpha-design → todo-add
└─ implement

汎用基盤:
- codex-vscode / codex-review（全スキルから参照）
- manage-sessions（BG セッション管理）
- clear-cache / snapshot / set-focus（状態管理）
- recent-trends / strategic-codex-debate / update-docs（横断分析・ドキュメント）
```

---

## 実行順序

### Phase 0: DROP 退避（5 分）

7 skill を `.claude/skills/_archived/` に移動。

### Phase 1: 基盤 skill RENAME-ONLY（30 分）

依存の少ない順に:
1. `zenigame-fx-codex-vscode`
2. `zenigame-fx-codex-review`（codex-vscode 依存）
3. `zenigame-fx-manage-sessions`
4. `zenigame-fx-clear-cache`
5. `zenigame-fx-snapshot`

### Phase 2: FX 基盤構築（2-3 時間）

並列可能タスク:
- `docs/alpha_factory/` 骨格（README, TODO, terminology, runbook, codex-discipline）
- `scripts/alpha_factory/todo_manager.sh`
- `config/alpha_factory/focus-theme.json`
- `config/alpha_factory/default.yaml` に stage_gate セクション追加
- `src/alpha_factory/__init__.py`, `stage_gate.py`, `archive.py`

直列タスク:
- `scripts/alpha_factory/run_ga.py` を Stage A/B/C + ゲノム archive 対応に拡張
- `scripts/alpha_factory/get_latest_run_number.py` は既存のまま
- `scripts/alpha_factory/analyze_run.py`, `generate_run_report.py` を FX 基盤対応に拡張

### Phase 3: CONTENT-ADAPT 12 個 + RENAME 残り 4 個（3-4 時間）

| 順 | skill | 依存 |
|----|-------|------|
| 1 | fx-run-ga | 基盤完了後 |
| 2 | fx-run-report | fx-run-ga |
| 3 | fx-analyze-genome-archive | fx-run-ga |
| 4 | fx-analyze-run | fx-analyze-genome-archive |
| 5 | fx-todo-add / fx-todo-close | TODO 管理 |
| 6 | fx-alpha-design | codex-review |
| 7 | fx-plan-and-design | fx-analyze-run, alpha-design, todo-add |
| 8 | fx-implement | todo-close, codex-review |
| 9 | fx-batch-ga | fx-run-ga, fx-run-report |
| 10 | fx-profile-optimize | fx-run-ga, alpha-design, implement |
| 11 | fx-recent-trends | fx-run-report（alpha-sieve は Phase 4 後） |
| 12 | fx-set-focus | focus-theme.json |
| 13 | fx-strategic-codex-debate | codex-review |
| 14 | fx-update-docs | docs/alpha_factory/ |
| 15 | fx-improve-cycle | 上記すべて |

### Phase 4: INFRA-ADAPT 4 個（4-6 時間）

| 順 | skill | 新設する基盤 |
|----|-------|-------------|
| 1 | fx-calibrate-gate | Stage A/B/C gate tuner（stage_b_ratio 調整ロジック） |
| 2 | fx-alpha-sieve | `scripts/alpha_factory/run_alpha_sieve.py` |
| 3 | fx-post-run-review | local-agent BG セッション launcher（skill 内 Agent 呼び出し） |
| 4 | fx-primitive-ic（オプション） | `src/alpha_factory/primitives/` + IC eval |

### Phase 5: 通し動作確認（30 分）

小構成（EUR_JPY, 2 週間, pop=12, gen=3）で fx-improve-cycle を 1 サイクル dry-run。
全 skill が連携して動くことを確認。

---

## 移植時の共通指針

1. **使命文書の差し替え**: 各 skill の「使命」セクションは zenigame（日本株、ロングオンリー）から FX（両方向、イントラデイ、スワップ考慮）に書き換える。
2. **禁止事項の再定義**: ショート禁止は FX に該当せず削除。代わりに「オーバーナイト保有を前提にしない」「スワップコストを fitness から差し引く」等を追加。
3. **パス・コマンドの一括置換**:
   - `.claude/skills/zenigame-*` → `.claude/skills/zenigame-fx-*`
   - `/zenigame-*` → `/zenigame-fx-*`
   - `scripts/alpha_factory/` はそのまま（FX でも同パスを使う）
   - `docs/alpha_factory/` はそのまま
4. **J-Quants/primitive 参照の削除**: 該当記述がある場合はコメントアウトせず削除。
5. **systemd/Dramatiq 参照の削除**: 該当記述は local-agent BG で代替するか削除。
6. **CLAUDE.md / AGENTS.md 更新**: 移植完了後、「zenigame-* skill は archived」「zenigame-fx-* skill が正」と明記。

---

## リスクと対策

| リスク | 対策 |
|--------|------|
| 全 31 skill 移植で 1 セッションに収まらない | Phase 単位でコミット、中断しても state file で再開可能に |
| skill 間参照の不整合（`/zenigame-*` が残る） | Phase 完了時に `grep -r "zenigame-" .claude/skills/zenigame-fx-*` で検証 |
| Stage A/B/C の設計決定ミス | walk_forward.py の既存実装を踏襲、独自実装は避ける |
| FX 固有挙動（スワップ、スプレッド）の考慮漏れ | Phase 2 で backtest engine / metrics の FX 対応を確認、必要なら追加改修 |
| Codex API 失敗 | 本家同様、失敗時は Claude 単独で続行するフォールバックを各 skill に組み込む |

---

## 次のステップ

1. この設計に対するユーザーレビュー（特に DROP / INFRA-ADAPT の判定、実行順序の妥当性）
2. 承認後、Phase 0 から順次着手
3. Phase 完了毎に `devnotes/20260421-1850-fx-skill-port/phase-N-report.md` で進捗記録
4. 最終的に AGENTS.md / CLAUDE.md を更新し、`.claude/skills/zenigame-*` は archived、`zenigame-fx-*` が正として運用
