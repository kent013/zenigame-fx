# 概念設計: zenigame-analyze-run skill を zenigame-fx に移植

## 背景・課題

zenigame-fx では Phase 2 基盤（Clause Genome / 32 primitive / Stage A/B/C / GenomeArchive / Cross-pair / LaneManager / run_ga.py）が T001-T019 で整備済み。
Run 完了後の深層分析を実行するスキル（`zenigame-analyze-run`）は zenigame 版のまま流用されており、zenigame-fx 固有のパス・用語・制約に整合していない。

本 TODO では **SKILL.md の text port のみ** を対象とする。Python 実装（`scripts/alpha_factory/analyze_run.py` の深層分析版拡張）は別 TODO で扱う。

## 反証起点（C9, falsification-first）

この移植が失敗する最短経路は以下 2 つ:

1. `zenigame-fx-analyze-run` という新名称だけ整えても、実際には旧 skill や未移植 hook に流れて分析運用が変わらないケース
2. archive path / schema / primitive source-of-truth を「zenigame と同じ」と仮定したまま skill に埋め込み、run 後の分析が誤読になるケース

これらを回避するため、「未検証前提の明示」「未移植 hook の契約定義」「旧 skill とのルーティング分離」を本設計に組み込む。

## 改善アイデア

`.claude/skills/zenigame-fx-analyze-run/SKILL.md` を新規作成し、以下の方針で zenigame 版を移植する:

1. **使命・禁止事項**: `zenigame-fx-codex-review` の定義を継承（ショート禁止を削除、FX イントラデイ / 両方向許容 / スワップ・スプレッド反映を明記）
2. **思考原則**: zenigame-fx 用途にリライト（日本株 → FX イントラデイ。TNV バイアス等 zenigame 固有の実例は未蓄積のため抽象化）
3. **パス**: `docs/alpha-factory/` → `docs/alpha_factory/`、`src/trading/alpha_factory/` → `src/alpha_factory/`
4. **primitive 参照の SSoT**: skill 内ではフル列挙せず、`docs/alpha_factory/primitives.md` を一次参照元と明記（F1-F14 Directional / M1-M6 Modulator / P1-P12 Pair-specific。カテゴリ名・一覧は参照先にリンク）
5. **Stage 説明**: Stage A (Fast Screen 60d) / Stage B (IS + WF OOS) / Stage C (live_criteria + (ii-lite) + stress) を `docs/alpha_factory/stage-gates.md` 参照で明記
6. **archive 参照 (shallow read 原則)**: skill 内では archive parquet の**shallow read のみ許可**（件数・最良 fitness・pass 率等の軽量集計に限定）。深い分析は **`zenigame-fx-analyze-genome-archive`（未移植）に委譲予定**と明記
7. **未移植 hook の暫定契約**:
   - `zenigame-fx-post-run-review`（未移植）: **自動起動しない**が、`analysis-claude.md` / `analysis-codex.md` の出力フォーマットは将来 `zenigame-fx-post-run-review` が読める前提で固定（Run 番号・best_fitness・pair 別集計・ボトルネック仮説セクション必須）。整備後に自動起動ブロックを復活させる
   - **artifact 名の SSoT 統一**: 全設計・既存 skill・将来 hook で `analysis-claude.md` / `analysis-codex.md` に統一。現行 `scripts/alpha_factory/analyze_run.py` は `analysis-claude.md` を出力しており、この命名に合わせる。`zenigame-fx-improve-cycle` SKILL.md に残存している `analyze-claude.md` 記述の修正は別 follow-up TODO（本 TODO のスコープ外だが FAQ に記録）
   - `zenigame-fx-analyze-genome-archive`（未移植）: analyze-run 内で shallow read のみ。deep archive analysis は整備後委譲
   - 命名は**全文書で `zenigame-fx-post-run-review` / `zenigame-fx-analyze-genome-archive` に統一**（略記禁止）
8. **Codex**: `gpt-5.3-codex` medium（分析用）。呼び出しは `scripts/codex` 経由（`zenigame-fx-codex-vscode` / `zenigame-fx-codex-review` 準拠）
9. **呼び出し元/呼び出し先の契約表**（skill 冒頭に配置）:
   ```
   [現契約]
   User / manual invocation → /zenigame-fx-analyze-run (standalone)
   /zenigame-fx-analyze-run → /zenigame-fx-codex-review  (Codex 独立分析)
                            → /zenigame-fx-codex-vscode  (codex 呼び出し規約)
                            × /zenigame-fx-manage-sessions (未接続。fx 用 cleanup 依存未整備)
                            × /zenigame-fx-post-run-review (未接続、整備後に接続)
                            × /zenigame-fx-analyze-genome-archive (未接続、shallow read のみ)

   [将来契約 (follow-up TODO で切替予定)]
   /zenigame-fx-improve-cycle → /zenigame-fx-analyze-run
   ```
   現状の `zenigame-fx-improve-cycle` は `scripts/alpha_factory/analyze_run.py` を直接呼んでおり、skill 経由には切り替わっていない。本 TODO ではその切替は行わない（別 follow-up TODO で対応）。
10. **既存 `zenigame-analyze-run` 保持**: 削除しない。ただし「**zenigame-fx 系からは旧 skill を参照しない。旧 skill は reference-only**」を概念設計・skill 双方に明記。`_archived/` 退避判定条件: improve-cycle 等 fx 系 skill の全参照が fx-* に切り替わった時点

## 期待効果（限定明記）

- **FX 文脈に沿った分析 runbook の整備**（fx 用語・パス・禁止事項で動く）
- archive Parquet 28 カラムを shallow read で読む観点整備（Top 個体 / Stage 別 pass 率 / pair 別偏在 / lane 別落下）
- 将来の `zenigame-fx-post-run-review` / `zenigame-fx-analyze-genome-archive` 整備時に skill 名・入出力契約で接続できる hook を用意

**分析深度は現行 `scripts/alpha_factory/analyze_run.py` の機能上限に従う**。深層分析の自動化は別 TODO 完了後に有効化する。

## FX 固有分析観点（禁止事項違反検知）

skill の分析チェック項目に以下を必須化:

- **保有時間分布**（イントラデイ逸脱検知）
- **セッション跨ぎ比率**（オーバーナイト保有禁止違反）
- **spread / swap が fitness にどう効いたか**（見かけの PnL でなく純利益）
- **ロング/ショート偏重**（特定 pair・特定 session の構造由来か確認）
- **pair 間の勝ち負け偏在**（特定 pair 依存）
- **lane 別落下分布**（Tier1 / Graduation のどこで止まったか）

## 実装方針（概要）

### 成果物

- `.claude/skills/zenigame-fx-analyze-run/SKILL.md`（新規）
- `devnotes/20260424-0711-port-analyze-run/conceptual-design.md`（本ファイル）
- `devnotes/20260424-0711-port-analyze-run/detailed-design.md`

### 変更方針

- `zenigame-analyze-run/SKILL.md` を base として以下を一括置換・改修:
  | 旧 | 新 |
  |---|---|
  | `docs/alpha-factory/` | `docs/alpha_factory/` |
  | `src/trading/alpha_factory/` | `src/alpha_factory/` |
  | `/zenigame-codex-review` | `/zenigame-fx-codex-review` |
  | `/zenigame-analyze-genome-archive` | コメント化 + 委譲先明記 |
  | post-run-review 起動ブロック | コメント化 + 暫定契約明記 |
  | ショート禁止記述 | 削除（FX 両方向許容を代替明記） |
  | primitive A/B/C/D category | `docs/alpha_factory/primitives.md` 参照 |
  | `scripts/cleanup_claude_sessions.py` | コメント化（fx 用 cleanup スクリプト未整備。post-run-review 自動起動も未接続なので cleanup 必要性なし） |
  | `~/.local/bin/codex-vscode` / `claude-vscode` | コメント化（fx 用自動起動は post-run-review 整備後） |

### 前提条件

#### Verified（本設計着手時に確認済）
- `scripts/codex` 存在・`zenigame-fx-codex-review` / `zenigame-fx-codex-vscode` の呼び出し規約
- `docs/alpha_factory/` snake_case のドキュメント 10 本存在
- `src/alpha_factory/archive.py` `GENOMES_SCHEMA` 28 列定義（`run_id / run_number / generation / individual_name / instrument / lane_id / parent_a / parent_b / genome_json / fitness_raw / fitness_pen / stage_a_pass / stage_b_pass / stage_c_pass / trade_count / total_pnl / sharpe / sortino / calmar / max_drawdown_pct / active_clause / n_nodes / bootstrap_ci_lower / bootstrap_ci_upper / fold_sign_ratio / dsr / ii_lite_pass / graduated`）
- `scripts/alpha_factory/analyze_run.py` 存在（summary.json ベース簡易版）
- `docs/alpha_factory/primitives.md` に F1-F14 / M1-M6 記載（P1-P12 は T013 でペア特化追加済）
- `.claude/skills/zenigame-fx-codex-review/SKILL.md`、`zenigame-fx-manage-sessions/SKILL.md` 存在

#### To verify before merge
- archive parquet 実ファイルが `.cache/alpha_factory/runs/genomes_*.parquet` に出力されていること（T015 で schema 確定、実行環境で出力実績あるかは要確認）
- `scripts/alpha_factory/analyze_run.py` が `run-N/summary.json` を前提にしており、skill が呼び出す I/F に矛盾がないこと
- `test_health` 815 passed / 1 skipped（baseline）を skill 追加後も維持

**skill 本文への反映**: 「前提が崩れていた場合は分析を継続せず、前提差分を first finding として報告する」を Step 0 に明記。

### スコープ外

- `scripts/alpha_factory/analyze_run.py` の深層分析版拡張（別 TODO）
- 分析ロジックの精度改善・新規メトリクス追加
- `zenigame-fx-analyze-genome-archive` / `zenigame-fx-post-run-review` 等の未移植 skill の新規整備（別 TODO）
- `zenigame-analyze-run` の削除・`_archived/` 退避（別 TODO。参照保持）

## 制約・前提（前提区分の分離）

上記「前提条件」セクションに `Verified` / `To verify before merge` で分離記載。

- `zenigame-fx-codex-review` の使命・禁止事項・C1-C9 discipline を継承
- `zenigame-fx-codex-vscode` の呼び出し規約（`scripts/codex exec --ephemeral --sandbox read-only ...`）準拠
- 本 TODO は Markdown 編集のみ。Python コード変更なし、テストは skill 内容の sanity check のみ（旧パス残存 grep チェック）
- 815 passed baseline を維持（skill 追加は test 影響なし）

## スコープ外

- analyze_run.py の深層分析実装
- post-run-review テーマ設計
- zenigame-analyze-run の削除
