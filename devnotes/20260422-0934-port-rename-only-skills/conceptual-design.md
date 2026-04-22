# Conceptual Design: port-rename zenigame-* skills 4 件（rename 完了 + 実行可能性は別軸）

## 目的

zenigame-* skill のうち、名前空間・パス参照置換と zenigame-fx-codex-review への委任で zenigame-fx に持ち込める 4 個を移植する。これにより zenigame-fx 側で不足している運用補助スキル（セッション管理 / キャッシュ削除 / スナップショット / GA バッチ）を最小コストで揃える。

**重要**: 「移植完了 (rename done)」と「実行可能 (executable)」は別軸として扱う。本 TODO のスコープは前者のみ:

- **移植状態 (port_status)**:
  - `rename_done` — name / 参照置換 / 依存マトリクス記載 / 実行前提チェック節 が完了
- **実行可能性 (executable)** — 本 TODO 完了時点での実行可否:
  - `executable` — 依存 script + 関連 skill が現存し、即座に実行可能
  - `abort_only` — rename 済みだが依存未充足。skill 起動時に不足依存を列挙してアボート

本 TODO の完了条件は **4 skill すべての port_status = rename_done**。executable 状態への昇格は別 TODO (依存 script / 関連 skill の整備) に委ねる。現時点では 4 skill すべてが `abort_only` であり、これは設計上の意図であって矛盾ではない。

## スコープ

### 対象 4 skill

| 移植元 (zenigame) | 移植先 (zenigame-fx) | 役割 | port_status (本 TODO 完了時) | executable (本 TODO 完了時) |
|------------------|----------------------|------|------------------------------|------------------------------|
| zenigame-manage-sessions | zenigame-fx-manage-sessions | Claude セッションの一覧・ゾンビ掃除・完了マーク | rename_done | abort_only (script 未実装) |
| zenigame-clear-cache | zenigame-fx-clear-cache | namespace + 期間指定でキャッシュ削除 | rename_done | abort_only (script 未実装) |
| zenigame-snapshot | zenigame-fx-snapshot | Winners/Candidates/Config のスナップショット管理 | rename_done | abort_only (script + artifact 未実装) |
| zenigame-batch-ga | zenigame-fx-batch-ga | GA-Only バッチ N 回連続実行 | rename_done | abort_only (script + 関連 skill 群未実装) |

### 依存マトリクス

| skill | 必須 script | 必須 artifact | 必須 related skill | 充足状況 | 未充足時の skill 挙動 |
|-------|-------------|---------------|-------------------|----------|----------------------|
| zenigame-fx-manage-sessions | `scripts/cleanup_claude_sessions.py` | `.cache/alpha_factory/session-completed/`（自動生成） | なし | script 未実装 | 起動時 script 不在を検出してアボート、不足依存を明示 |
| zenigame-fx-clear-cache | `scripts/cache_manager.py` | `.cache/`（既存） | なし | script 未実装 | 起動時 script 不在を検出してアボート、不足依存を明示 |
| zenigame-fx-snapshot | `scripts/alpha_factory/snapshot_manager.py` | `.cache/alpha_factory/runs/winners_latest.json`、`candidates_latest.json`、`config/alpha_factory/default.yaml` | なし | script + artifact 未生成 | 起動時 script 不在を検出してアボート。skill としては「snapshot_manager.py が存在しない場合はアボート」一択。artifact 不足時の config-only 動作判定は scripts/alpha_factory/snapshot_manager.py 側の責務（本 skill の範疇外） |
| zenigame-fx-batch-ga | `scripts/alpha_factory/run_ga.py` (実在), `scripts/alpha_factory/extract_batch_metrics.py` (未実装), `scripts/alpha_factory/compare_batch_runs.py` (未実装), `scripts/alpha_factory/get_latest_run_number.py` (実在) | `.cache/alpha_factory/runs/winners_latest.json`, `.cache/alpha_factory/runs/candidates_latest.json`（参照依存・run_ga.py 側で判定） | `/zenigame-fx-snapshot`, `/zenigame-fx-calibrate-gate`, `/zenigame-fx-run-alpha-factory`, `/zenigame-fx-run-report` (※`/zenigame-fx-improve-cycle` と `/zenigame-fx-post-run-review` は batch 中スキップ・呼び出さないため依存ではない、注意のみ) | script 2 件と関連 skill 4 件が未実装 | 起動時に依存 script + 関連 skill SKILL.md ファイルの存在をチェックし、不足を列挙してアボート。executable 状態の精緻判定は将来 TODO で skill メタデータに `executable` フィールドを追加した上で実施 |

**共通方針**: skill は zenigame 側スクリプトをフォールバック参照しない。zenigame-fx は独立コードベースとして扱う。

### Non-scope

- スクリプト本体（`scripts/cleanup_claude_sessions.py` 等）の zenigame-fx への移植は対象外。スキル側はパスを zenigame-fx 流に書き換えるが、**同名スクリプトが zenigame-fx 側で実装されていることを前提とする**。未実装スクリプトは別 TODO として切り出す。
- 関連スキル（`zenigame-fx-run-alpha-factory` / `zenigame-fx-run-report` / `zenigame-fx-calibrate-gate` / `zenigame-fx-post-run-review` / `zenigame-fx-improve-cycle`）はまだ存在しないが、本 TODO では参照名のみ書き換えて将来の整合性を確保する。
- zenigame 側のオリジナル skill ファイルは削除しない（参照保持）。

## 方針

1. zenigame 側のソースを Read → パス・参照を FX 側に置換 → zenigame-fx-* として Write
2. 使命・禁止事項は重複記載せず `zenigame-fx-codex-review` に一元化（既存の zenigame-fx-* skill と同じスタイル）
3. Codex 呼び出しは `scripts/codex` 経由（`~/.local/bin/codex-vscode` ではなく）
4. ディレクトリパスは zenigame-fx の実装に合わせる:
   - `docs/alpha-factory/` (ハイフン版) → `docs/alpha_factory/` (アンダースコア版)
   - `src/trading/alpha_factory/` → `src/alpha_factory/`（zenigame-fx は `src/` 直下に専用配置を想定。現状未実装）
   - `scripts/trading/run_alpha_factory.py` → `scripts/alpha_factory/run_ga.py`
   - `scripts/trading/snapshot_manager.py` → `scripts/alpha_factory/snapshot_manager.py`
   - `scripts/trading/extract_batch_metrics.py` → `scripts/alpha_factory/extract_batch_metrics.py`
   - `scripts/trading/compare_batch_runs.py` → `scripts/alpha_factory/compare_batch_runs.py`

## skill 別の差分概要

### 1. zenigame-fx-manage-sessions

**目的**: Claude セッション管理（status / cleanup / complete）

**主な変更点**:
- frontmatter: name を `zenigame-fx-manage-sessions` に
- description: "zenigame-fx Alpha Factory 用" を明示
- 内容: ロジックは元のまま。スクリプトパスは `scripts/cleanup_claude_sessions.py` のまま使用（zenigame-fx でも同名スクリプトを期待）
- 参照スキル: `improve-cycle` / `post-run-review` の言及を `zenigame-fx-improve-cycle` / `zenigame-fx-post-run-review` に書き換え
- 完了マーカーパス: `.cache/alpha_factory/session-completed/` (これはパス命名上 zenigame と同じ)

**依存（zenigame-fx 側で別途必要）**:
- `scripts/cleanup_claude_sessions.py`（未実装。本 TODO のスコープ外）

### 2. zenigame-fx-clear-cache

**目的**: namespace + 期間指定でキャッシュ削除

**主な変更点**:
- frontmatter: name を `zenigame-fx-clear-cache` に
- description: zenigame-fx 文脈に
- 内容: ロジック・コマンド形式は元のまま
- 使用例: zenigame の `mynavi` / `wikipedia` / `nikkei` / `jquants` 例は zenigame-fx に該当しないため、FX 文脈の例（`http`, `alpha_factory/runs`, `alpha_factory/sessions`, `oanda`）に書き換える
- スクリプトパス: `scripts/cache_manager.py` のまま（zenigame-fx 側に同名期待）

**依存（zenigame-fx 側で別途必要）**:
- `scripts/cache_manager.py`（未実装。本 TODO のスコープ外）

### 3. zenigame-fx-snapshot

**目的**: Winners/Candidates/Config スナップショット管理

**主な変更点**:
- frontmatter: name を `zenigame-fx-snapshot` に
- description: zenigame-fx 文脈に
- 対象ファイル表は zenigame-fx 側のパスに（実は同じ）:
  - Winners: `.cache/alpha_factory/runs/winners_latest.json`
  - Candidates: `.cache/alpha_factory/runs/candidates_latest.json`
  - Config: `config/alpha_factory/default.yaml`
- スクリプトパス: `scripts/trading/snapshot_manager.py` → `scripts/alpha_factory/snapshot_manager.py`
- ストレージパス: `.cache/alpha_factory/snapshots/` のまま

**依存（zenigame-fx 側で別途必要）**:
- `scripts/alpha_factory/snapshot_manager.py`（未実装。本 TODO のスコープ外）
- 現時点で `winners_latest.json` / `candidates_latest.json` は zenigame-fx に未生成だが、将来 GA が走れば生成される

### 4. zenigame-fx-batch-ga

**目的**: GA-Only バッチ N 回連続実行

**主な変更点**:
- frontmatter: name を `zenigame-fx-batch-ga` に
- description: zenigame-fx 文脈に
- スクリプトパス:
  - `scripts/trading/run_alpha_factory.py` → `scripts/alpha_factory/run_ga.py` ✓ (実在)
  - `scripts/trading/extract_batch_metrics.py` → `scripts/alpha_factory/extract_batch_metrics.py`
  - `scripts/trading/compare_batch_runs.py` → `scripts/alpha_factory/compare_batch_runs.py`
  - `scripts/alpha_factory/get_latest_run_number.py` ✓ (実在)
- 参照スキル:
  - `/zenigame-snapshot` → `/zenigame-fx-snapshot`
  - `/zenigame-calibrate-gate` → `/zenigame-fx-calibrate-gate`
  - `/zenigame-run-alpha-factory` → `/zenigame-fx-run-alpha-factory`
  - `/zenigame-run-report` → `/zenigame-fx-run-report`
  - `/zenigame-improve-cycle` → `/zenigame-fx-improve-cycle`
- ロックファイル名: `alpha_factory.lock` のまま
- 残り（バッチ flow / state json schema / Before/After ワークフロー等）はそのまま

**依存（zenigame-fx 側で別途必要）**:
- `scripts/alpha_factory/extract_batch_metrics.py`（未実装）
- `scripts/alpha_factory/compare_batch_runs.py`（未実装）
- 関連 skill 群（zenigame-fx-run-alpha-factory / zenigame-fx-run-report / zenigame-fx-calibrate-gate / zenigame-fx-improve-cycle）の整備（別 TODO）

## 統一ルール

### 名前空間置換マトリクス

| 旧 | 新 |
|----|----|
| `zenigame-manage-sessions` | `zenigame-fx-manage-sessions` |
| `zenigame-clear-cache` | `zenigame-fx-clear-cache` |
| `zenigame-snapshot` | `zenigame-fx-snapshot` |
| `zenigame-batch-ga` | `zenigame-fx-batch-ga` |
| `/zenigame-codex-review` | `/zenigame-fx-codex-review` |
| `/zenigame-codex-vscode` | `/zenigame-fx-codex-vscode` |
| `/zenigame-snapshot` | `/zenigame-fx-snapshot` |
| `/zenigame-calibrate-gate` | `/zenigame-fx-calibrate-gate` |
| `/zenigame-run-alpha-factory` | `/zenigame-fx-run-alpha-factory` |
| `/zenigame-run-report` | `/zenigame-fx-run-report` |
| `/zenigame-improve-cycle` | `/zenigame-fx-improve-cycle` |
| `/zenigame-post-run-review` | `/zenigame-fx-post-run-review` |
| `~/.local/bin/codex-vscode` | `scripts/codex` |
| `docs/alpha-factory/` | `docs/alpha_factory/` |
| `src/trading/alpha_factory/` | `src/alpha_factory/` |
| `scripts/trading/snapshot_manager.py` | `scripts/alpha_factory/snapshot_manager.py` |
| `scripts/trading/extract_batch_metrics.py` | `scripts/alpha_factory/extract_batch_metrics.py` |
| `scripts/trading/compare_batch_runs.py` | `scripts/alpha_factory/compare_batch_runs.py` |
| `scripts/trading/run_alpha_factory.py` | `scripts/alpha_factory/run_ga.py` |

### 使命・禁止事項の取り扱い

- 各 SKILL.md には使命・禁止事項を**重複記載しない**
- 戦略判断が絡む skill (`snapshot`, `batch-ga`): 「思考原則 / 使命 / 禁止事項は `zenigame-fx-codex-review` で定義される内容を適用」と明記（既存の zenigame-fx-implement と同じスタイル）
- 単純運用 skill (`manage-sessions`, `clear-cache`): 必要時のみ `zenigame-fx-codex-review` を参照する旨に留め、運用補助としての責務境界を明確化

## 完了基準

### 必須 (機械検証可能)

1. `.claude/skills/zenigame-fx-{manage-sessions,clear-cache,snapshot,batch-ga}/SKILL.md` の 4 ファイルが存在
2. 各 SKILL.md が valid YAML frontmatter を持つ
3. grep 検証（拡大版）: 以下のいずれもヒット 0 件
   - `docs/alpha-factory/`（ハイフン版）
   - `src/trading/`
   - `scripts/trading/`
   - `~/.local/bin/codex-vscode`
   - 4 ファイル全文を `zenigame-` で grep し、`zenigame-fx-` 以外の hit が 0 件（旧 namespace 残存検出）
4. 各 SKILL.md の description が zenigame-fx 文脈（zenigame-fx Alpha Factory 等の語を含む）に書き換わっている

### 必須 (内容観点)

5. 各 SKILL.md に「実行前提チェック」セクションがあり、未充足時は skill が中断する旨を明示
6. 各 SKILL.md の依存マトリクス（必須 script / artifact / 関連 skill）が、本概念設計の依存マトリクスと一致
7. 使命・禁止事項は重複記載せず、`zenigame-fx-codex-review` への参照に統一
8. zenigame 側スクリプトをフォールバック参照しない（独立コードベース原則）

### プロセス

9. 概念設計・詳細設計が Codex レビュー APPROVED

### 例示 namespace について（clear-cache）

`clear-cache` の使用例として `http`, `alpha_factory/runs`, `alpha_factory/sessions`, `oanda` を採用するが、これらは **zenigame-fx 側で確立された namespace ではなく、実装時に scripts/cache_manager.py の namespace 設計と一致させる仮例**。skill には固定文として以下を明記する:

> 実 namespace は `scripts/cache_manager.py status` の出力を source of truth とすること。本ドキュメントの例は仮例である。

## リスクと対応

| リスク | 対応 |
|-------|------|
| 参照スクリプト未実装でスキルが実行不可 | skill 起動時に「実行前提チェック」を行い、不足依存を列挙してアボート。zenigame 側スクリプトをフォールバック参照しない |
| 関連スキル（zenigame-fx-run-alpha-factory 等）未実装 | 参照名は zenigame-fx-* に統一しておくが、batch-ga 等は実行前提チェックで関連 skill 不在を検出してアボート。実体は別 TODO で整備 |
| zenigame 側スクリプトとの差異（FX 固有の概念） | 本 TODO ではパス置換のみ。FX 固有の挙動修正は別 TODO |
| `clear-cache` の例示 namespace が実 namespace と乖離 | 仮例である旨を skill 内に明記。確定時に skill を更新 |
| `snapshot` の対象 artifact (`winners_latest.json` 等) が未生成段階で skill 起動 | snapshot_manager.py 側で artifact 不在時は config-only モード or アボートを判定する旨を skill に明記 |

## アウトプット

- `devnotes/20260422-0934-port-rename-only-skills/conceptual-design.md`（本ファイル）
- `devnotes/20260422-0934-port-rename-only-skills/detailed-design.md`
- `.claude/skills/zenigame-fx-manage-sessions/SKILL.md`
- `.claude/skills/zenigame-fx-clear-cache/SKILL.md`
- `.claude/skills/zenigame-fx-snapshot/SKILL.md`
- `.claude/skills/zenigame-fx-batch-ga/SKILL.md`
