# T021: skill port — zenigame-fx-run-report 概念設計

## 背景

cycle 24 において zenigame-fx Phase 3 skill content-adapt の一環として、zenigame 側 `zenigame-run-report` skill を zenigame-fx 環境に移植する。
T015 で archive Parquet schema (28 列) が整備されたことで、これまで summary.json ベースの早期 simple 版だった `scripts/alpha_factory/generate_run_report.py` を **archive Parquet ベースの深層レポート** に拡張する余地が生まれた。

## 目的

GA 1 RUN の結果（archive Parquet + summary.json + history.json）から、`reports/run-reports/run-{N}.md` 形式の運用レポートを生成する skill を提供する。

レポートは以下を満たす:
- 使命判定（live_criteria 各項目 ✅/❌）が冒頭で見える
- Best 個体の中身（fitness、Stage pass、シグナル指標）が分かる
- Lane 別 / Pair 別 / Stage 別の落下分布が見える
- cross-pair shadow 集計（ii_lite_pass）が見える
- active_clause / n_nodes / fold_sign_ratio / dsr の分布が見える
- 収束履歴（per-generation best fitness）が表で見える
- 既存 zenigame-fx-analyze-run の成果物（analysis-claude.md / analysis-codex.md）があれば末尾に統合される

## 非目的

- D* / mission_gap / adaptive_mission_score 等の zenigame 株版固有指標は対象外（FX 版は live_criteria + Stage gate がベース）
- Director / Sieve 関連は zenigame-fx に存在しないので対象外
- 個体ごとの ABCD 分解 / Clause 診断（T359）は zenigame-fx 未実装、対象外
- レポート生成と RUN 実行・TODO 遷移は分離（独立利用 YES）

## 入出力契約

### 入力

`scripts/alpha_factory/generate_run_report.py --run-number N [--analysis-md path]... [--analysis-dir dir]`

- `--run-number N` (必須、既存): `reports/run-reports/run-{N}/summary.json` を読みに行く
- `--analysis-md path` (任意、既存): 分析 md ファイルを末尾に取り込む。**`action="append"` で複数回指定可**。既存呼び出し（improve-cycle）の単一指定もそのまま動く
- `--analysis-dir dir` (新規、任意): 指定ディレクトリ内の `analysis-*.md` を全て自動収集（lexical sort 順）。zenigame-fx-analyze-run の `tmp_dir` 直結を想定
- archive Parquet パスは `summary["archive_parquet"]` から取得（無ければ skip、後述）
- **`--run-id` は採用しない**: Codex 指摘 #3 を受け、`run_number` ↔ `run_id` の二重指定リスクを回避。SSoT は `run_number → summary.json → archive_parquet` の一本鎖

**互換性**: 既存呼び出し元（`zenigame-fx-improve-cycle` SKILL.md L144-147）は `--run-number $next_n --analysis-md {tmp_dir}/analysis-claude.md` 形式。これを破壊しない（`action="append"` は単一指定でも値を受け取れる）。

### 分析 md 統合の優先順位

両系（`--analysis-md` 複数指定 / `--analysis-dir` 自動収集）を併用可。重複する path は dedup。出力レポートでは収集順に並べ、各ファイル先頭に `### {basename}` 見出しを差し込む。

### 出力

`reports/run-reports/run-{N}.md`（フラットパス、ブロック構成は採用しない）

レポート構成（必須セクション順）:
1. ヘッダ（run_id / run_number / generated_at / dataset）
2. 使命判定（live_criteria）
3. GA 設定 / Backtest 設定 / Stage Gate 設定 / Cross-pair 設定（テーブル）
4. Best 個体（summary.best ベース。archive がある場合のみ補足列を追加）
5. Stage 通過数（A / B / C 件数、A/B 通過率）
6. Lane 別落下分布（lane_id × Stage A→B→C 通過数）
7. Pair 別落下分布（instrument × Stage A→B→C 通過数）
8. active_clause / n_nodes 分布（基本統計量）
9. fold_sign_ratio / dsr 分布（Stage B/C 通過群）
10. cross-pair shadow 集計（ii_lite_pass: True / False / None）
11. graduated 件数
12. **archive Top-5 個体一覧**（archive 視点。Best とは別物。`fitness_pen` 降順、列: rank / name / generation / lane_id / instrument / fitness_pen / fitness_raw / stage_a/b/c_pass / trade_count / sharpe）
13. 収束履歴（per-generation best fitness）
14. 分析（analysis-claude.md / analysis-codex.md がある場合のみ）

> archive Top-5 セクション（#12）は「Best とは別物」を見出し直下で明記する（混同防止）。

## 設計方針

### 既存スクリプトの拡張方針

`scripts/alpha_factory/generate_run_report.py` を **拡張**する（新規ファイル分離はしない）。

理由:
- 既存呼び出し元（improve-cycle / runbook）の引数を変えずに済む
- summary.json 依存セクション（既存）と archive Parquet 依存セクション（新規）が同一レポート内に混在するため、コード分割しても結局合体させる必要がある
- 1 ファイルで完結する方が読み手にやさしい

### Defensive 動作（セクション粒度の劣化生成）

レポートはセクション単位で defensive 化する。**summary.json 自体が不在なら即エラー**だが、それ以外は欠落キーをセクションごとにスキップ／「未記録」表示にして部分生成を続行する。

| 入力欠落 | 動作 |
|---------|------|
| `summary.json` 自体不在 | exit 1（既存通り） |
| `summary["archive_parquet"]` キー欠落 or path 不在 | archive 依存セクション（Stage 通過数 / Lane 別 / Pair 別 / active_clause-n_nodes / fold_sign_ratio-dsr / cross-pair shadow / graduated / archive Top-N）をすべて **「archive Parquet なし、計算スキップ」** にして残す |
| archive Parquet **読取失敗**（破損 / schema 不一致） | warning ログ → 上と同じ扱いで劣化生成を継続。例外で落ちない |
| `summary["backtest_config"]` / `stage_gate_config` / `cross_pair_config` 欠落 | 該当セクションを **「未記録（旧 schema）」** とだけ表示 |
| `summary["live_criteria"]` 欠落 | 「使命判定: 未記録」と表示、exit はしない |
| `summary["per_generation"]` 欠落 | history.json から fallback、それも無ければ「収束履歴: 未記録」 |
| history.json fallback 自体が読取失敗 | warning ログ → 「収束履歴: 未記録（読取失敗）」 |
| `--analysis-md` 指定 path が不在 / 読取不可 / 非 UTF-8 | warning ログ → 該当ファイルだけスキップ、他は通常処理 |
| `--analysis-dir` 指定 dir が不在 / 読取不可 | warning ログ → 該当 dir からの収集だけスキップ、他は通常処理 |

理由:
- 旧 RUN (T015 以前 / config 拡張前) の summary.json には拡張キーが無い
- archive 生成失敗時でも summary.json があればレポートは作れる方が運用上マシ
- 部分情報でも出すことが「欠落の発見」につながる

### 集計実装

Parquet → 集計は `pyarrow` のみで実装（pandas を新規依存に追加しない）。
グループ集計は `pyarrow.compute` の `group_by + aggregate` を利用、表形式の小さい dict に変換してから markdown 出力。

集計対象列（T015 GENOMES_SCHEMA 28 列のうち利用するもの）:
- 必須: `lane_id`, `generation`, `individual_name`, `instrument`, `stage_a_pass`, `stage_b_pass`, `stage_c_pass`, `fitness_pen`, `fitness_raw`, `trade_count`, `sharpe`, `active_clause`, `n_nodes`, `fold_sign_ratio`, `dsr`, `ii_lite_pass`, `graduated`
- 参考: `sortino`, `calmar`, `max_drawdown_pct`, `total_pnl`, `bootstrap_ci_lower`, `bootstrap_ci_upper`

### Best 個体の決定（SSoT: summary.best）

**SSoT は `summary["best"]`** とする。`run_ga.py` は `(stage_c_pass, stage_b_pass, stage_a_pass, fitness_pen)` の辞書式最大で Best を選ぶ（`run_ga.py` L110/L461）。これを archive 集計の `fitness_pen` 最大で再現すると、Stage 通過状況が異なる個体を Best と誤判定し得る。

レポート Best セクションは:
1. summary.best から `name / generation / fitness / stage_a/b/c_pass / metrics / selection_score` を表示（既存互換）
2. archive Parquet がある場合、`(name, generation)` で archive 行を引いて補足情報（`lane_id`, `instrument`, `fold_sign_ratio`, `dsr`, `ii_lite_pass`, `n_nodes`, `active_clause`）を追加表示
3. archive 行が見つからない場合は「archive に該当行なし」を表示するに留め、エラーにしない（lane_id 不在等の整合性差異は設計通り起こり得るため WARN にしない）

archive 全体の `fitness_pen` Top-N は別セクション（archive 由来の Top 5 個体一覧）で出す。これは「archive 視点での観察事実」として出すだけで、Best と称さない。

### skill SKILL.md の構成

`.claude/skills/zenigame-fx-run-report/SKILL.md` を新規作成。
zenigame-fx-codex-review の使命・禁止事項・C1-C9 を継承（重複記載しない）。

引数:
- `run_number` ($1) — 必須、レポート対象 run の番号
- `--analysis-md` — 任意、分析 md があれば取り込む（複数回指定可）
- `--analysis-dir` — 任意、ディレクトリ内の `analysis-*.md` を自動収集

呼び出し契約:
- マニュアル: `/zenigame-fx-run-report 3`
- improve-cycle Phase 4 から呼ばれる経路は将来切替（本 TODO 範囲外、既存通り `scripts/alpha_factory/generate_run_report.py` を直接呼ぶ）

skill 内容: Step 1 入力検証 → Step 2 generate_run_report.py 実行 → Step 3 出力検証（grep ベースで必須セクション存在確認）→ Step 4 報告。

## 思考原則の適用

- **C1 Design-first**: 既存 generate_run_report.py の設計を読み、互換性ポイント（呼び出し元 improve-cycle）を特定済み
- **C2**: 「summary.json に X が無い」だけで bug 判定しない。`summary["best"]` と archive Top-N の内容差は **設計通りの正常動作**として WARN 出さない（Best 選定が `(c, b, a, fitness_pen)` 辞書式なのに対し archive Top-N は `fitness_pen` 単独で並ぶため）
- **C4 前提検証**: archive Parquet 不在 / 読取失敗 / summary.json 不在のフォールバックを明示
- **C6 Fact/Interpretation 分離**: レポート本体は事実のみ。解釈は analysis-{claude,codex}.md セクションに委譲

### WARN 出力ポリシー（明確化）

**WARN を出す**: archive Parquet 不在、archive 読取失敗、summary 拡張キー欠落、`--analysis-md` 指定 path 不在 / 読取失敗、`--analysis-dir` 不在、history.json fallback 失敗。
**WARN を出さない**: `summary.best` と archive Top-N の内容差、archive 行 lookup 失敗（Best の補足情報）。これらは設計通りに発生し得る情報差。

## リスクと対応

| リスク | 対応 |
|--------|------|
| 既存呼び出し元（improve-cycle）が壊れる | `--run-number` 必須・`--analysis-md` 任意は維持。`action="append"` 化は単一指定でも互換 |
| 旧 summary.json に `archive_parquet` キーが無い | キー欠落時は archive 集計セクション全体をスキップ（warning 表示） |
| pyarrow group_by 集計の API 差異 | `pyarrow.Table.group_by(...).aggregate(...)` の戻り値を pylist に変換、それ以上のオペレーションはしない |
| 大規模 archive で OOM | T015 schema は 1 RUN 最大数千行想定。OOM リスクは現状低い。将来 streaming が必要なら別 TODO |
| skill 内 grep 検証の脆さ | 「必須見出し」リストを SKILL.md に列挙し、レポート出力側の見出しと厳密一致させる |
| 相対/絶対パス混在 / symlink で同一 analysis-md が二重取り込み | `Path.resolve()` で正規化してから set 化 dedup |

## 受け入れ基準

1. `scripts/alpha_factory/generate_run_report.py --run-number 3` が `reports/run-reports/run-3.md` を生成
2. レポートに必須セクション（使命判定 / Best 個体 / Stage 通過数 / Lane 別落下分布 / Pair 別落下分布 / active_clause-n_nodes 分布 / cross-pair shadow / **archive Top-5 個体一覧** / 収束履歴）がすべて存在
3. archive Parquet 不在時も summary.json があればレポートが生成される（archive 依存セクションは「計算スキップ」表示）
4. archive Parquet **読取失敗時**（破損 / schema 不整合）も例外で落ちず、summary ベースで部分生成される（warning ログのみ）
5. summary.json の拡張キー（`backtest_config` / `stage_gate_config` / `cross_pair_config` / `live_criteria` / `per_generation`）欠落時もセクション単位で「未記録」表示で部分生成される
6. `summary["best"]` と archive 集計（archive Top-N）がズレても **WARN を出さない**（設計通り起こり得る）
7. `--analysis-md` 0 / 1 / 複数指定、`--analysis-dir` 指定、両方併用、すべて動作（dedup 済）
8. 既存呼び出し元（improve-cycle 経路）の `--run-number N --analysis-md path` 単一指定が壊れない（既存テスト + 手動確認）
9. mypy / ruff グリーン
10. 815 passed baseline 維持/拡大

## TODO

| ID | タスク |
|----|--------|
| T021 | この skill 移植 + script 拡張 + テスト |
