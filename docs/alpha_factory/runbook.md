# Runbook

## 目的

zenigame-fx Alpha Factory の運用手順（autopilot / improve-cycle）を一箇所に集約する。各 skill 内部の詳細は SKILL.md を直接参照。

## スコープ

- autopilot / improve-cycle の起動方法とフェーズ構成
- 失敗時の復旧手順（簡略）
- 監査・チェックポイントの呼び出し点

各 skill 実装の細かいフラグ・パラメータは別 doc / SKILL.md。

## 用語リンク

本ドキュメントで使用する用語: [Stage A](terminology.md#stage-a), [Stage B](terminology.md#stage-b), [Stage C](terminology.md#stage-c), [Lane](terminology.md#lane)

## 主要定義

### 1. Autopilot — 自走ループ

```
/zenigame-fx-autopilot --repeat
```

フェーズ構成:

```
Phase 0 Survey → Phase 1 Design → Phase 2 TODO Add → Phase 3 Implement
                                                       ↓
                                                Phase 4 Checkpoint
                                                       ↓
                                       Phase 4A Evaluation (audit-interval ごと)
                                                       ↓
                                              Phase 0 に戻る
```

- Phase 4A は `audit-interval` サイクルごとに発火
- 各サイクルは `improve_cycle.max_cycle_seconds` を超過したら次フェーズへ強制遷移

### 2. Improve-cycle — RUN を含むサイクル

```
/zenigame-fx-improve-cycle
```

`analyze-run → plan-and-design → calibrate-gate → implement → run-ga → run-report → alpha-sieve` を順次起動。

### 2-1. Post-Run Review — テーマ別 BG レビュー (T026)

improve-cycle Phase 1 (analyze-run) 完了直後、5 つの review-theme について BG Agent (`run_in_background: true`) を fire-and-forget で起動する。

| review-theme | code | TODO theme | フォーカス |
|--------------|------|-----------|----------|
| signal-quality | sq | primitives | プリミティブ予測力 |
| regime-awareness | ra | cross-pair | レジーム適応 |
| cost-efficiency | ce | ga-architecture | コスト現実性 |
| robustness | rb | statistics | 過学習耐性 |
| risk-management | rm | stage-gate | リスク統制 |

post-run-review 由来の TODO は `--summary` 先頭に **`[r:{code}]`** prefix を必ず付与 (30 文字制約対応の短縮 code、prefix 7 文字固定 → 内容 23 文字残)。

- launch owner: `improve-cycle` Phase 1 末尾のみ (analyze-run スタンドアロンでは起動しない)
- 二重起動防止 marker: `.cache/alpha_factory/post-run-review-launched-{run_id}.json`
- 集約 summary: `.cache/alpha_factory/post-run-review-summary-{run_id}.md`
- 申し送り: `.cache/alpha_factory/post-run-review-{review-theme}-deferred.md` (テーマごと)

**手動起動** (analyze-run スタンドアロン実行後に改善案を出したい場合):

```
/zenigame-fx-post-run-review signal-quality run_YYYYMMDD_HHMMSS --tmp_dir devnotes/YYYYMMDD-HHMM-analyze-run-XXXX
```

`--tmp_dir` には `analyze-run` が出力した `analysis-claude.md` / `analysis-codex.md` のあるディレクトリを指定。

### 3. 失敗時の復旧

| 失敗箇所 | 一次対応 |
|---------|---------|
| Codex 呼び出し失敗 | 30 秒待って 1 回リトライ → だめなら Claude 単独で続行 |
| GA 実行中エラー | `.cache/alpha_factory/current_cycle_state.json` から再開 |
| Archive 書き込み失敗 | DB / Parquet 容量を確認、`/zenigame-fx-clear-cache` で部分クリア |
| TODO 重複 | `scripts/alpha_factory/todo_manager.py list` で現状確認 |

### 4. 監査・チェックポイント

- Phase 4 Checkpoint: 各サイクル末で archive 整合・統計指標を確認
- Phase 4A Evaluation: 多角監査（focus-theme 別）を起動
- 監査結果は `devnotes/{tmp_dir}/` に保存し、必要なら TODO 化

### 5. 主要 CLI

| コマンド | 用途 |
|---------|------|
| `uv run python scripts/alpha_factory/run_ga.py` | GA 1 サイクル実行 |
| `uv run python scripts/alpha_factory/analyze_run.py` | 直近 Run の深層分析 |
| `uv run python scripts/alpha_factory/generate_run_report.py` | Run レポート生成 |
| `uv run python scripts/alpha_factory/todo_manager.py {add,close,list,...}` | TODO 操作 |
| `uv run python scripts/fetch_fred.py --series ... --from ... --to ...` | FRED 日足マクロ指標取得 |

### 5-1. GA 並列実行 (T052)

`run_ga.py` の per-genome Stage A/B/C 評価を `multiprocessing.Pool` (spawn) で並列化できる。

**CLI**:

```bash
# canonical: --max-workers
uv run python scripts/alpha_factory/run_ga.py --max-workers 4

# alias: --workers (zenigame との表記互換)
uv run python scripts/alpha_factory/run_ga.py --workers 4

# 起動時 memory budget チェック (autopilot 推奨)
uv run python scripts/alpha_factory/run_ga.py --max-workers 4 --strict-memory-guard
```

**YAML** (`config/alpha_factory/default.yaml`):

```yaml
ga:
  max_workers: 2   # default. シーケンシャル実行は `--max-workers 1` で明示
```

**決定論性契約**:

- L1 selection: `best_name` / `fitness_pen` / `live_criteria_passed` が worker 数に依存しない
- L2 row-order: archive Parquet の数値 column が `(lane_id, generation, individual_name)` ソート下で完全一致
- L3 artifact bit equivalence は **保証外** (timestamp / wall_time_seconds 等を含むため)

**運用ガード** (1 worker = 約 400MB 保守的試算):

- `summary.json.max_rss_mb_per_worker` が **2.1GB (3GB の 70%)** を超えたら次回 RUN で `max_workers` を引き下げる
- `--strict-memory-guard` 指定時は `available_mem` ベースの推奨値を超えると起動時 fail-fast (autopilot 等で OOM 防止)
- multi-pair 化で 1 worker 試算が 2.1GB を超える時点で SharedBarStore (mmap 共有) タスクを起票

**⚠ プロファイル / 速度改善ループでは `--max-workers 1` を必ず指定**:

- `cProfile` は main process しか計測しないため、並列モード (default 2) で実行すると **worker 側の Stage A/B/C 評価コストが計測値から消える** (歪んだ profile になる)
- 速度改善ループ (`zenigame-fx-profile-optimize`) は per-genome 評価コストを最適化対象とするため、worker 並列を明示的に切って単一プロセスで全コストを cProfile に集約するのが必須前提
- 並列化の効果検証は本機能 (T052) の同値性テスト + wall-time 計測で別途実施 (cProfile の責務外)
- 同 skill は内部で `--max-workers 1` を強制付与する (ユーザー指定の `--max-workers N>1` は profile 整合性のため上書きされる)

**summary.json schema** (T052 で `1.0 → 1.1`):

- 既存 field は全て保持 (`run_id` / `dataset` / `best` / `live_criteria` 等)
- 追加 field (consumer は未知 field を無視する義務、`additionalProperties: true`):
  - top-level: `schema_version`, `parallel_config.{max_workers,mode}`, `max_rss_mb_per_worker`
  - `per_generation[*]`: `stage_{a,b,c}_seconds_total`, `stage_{a,b,c}_seconds_max`, `peak_main_rss_mb`, `peak_rss_mb_per_worker`, `peak_total_rss_mb`

設計詳細: `devnotes/20260427-1114-ga-parallel-workers/`

### 6. FRED 取得手順（macro_index_daily 補充）

[FRED](terminology.md#fred) の日足マクロ指標（VIX / DXY / Treasury yields / breakeven）を `macro_index_daily` テーブルへ取り込む。primitive M5 / P7 等の前提データ。

#### 前提

- `.env` に `FRED_API_KEY` を設定（[FRED API key 発行](https://fred.stlouisfed.org/docs/api/api_key.html)）
- DB コンテナ稼働: `docker start zenigame-fx-db-1`
- `uv run alembic upgrade head` で migration 003 を適用

#### 通常運用（差分更新）

```bash
TODAY=$(date '+%Y-%m-%d')
YESTERDAY=$(date -v-1d '+%Y-%m-%d')  # macOS の場合
uv run python scripts/fetch_fred.py --series VIXCLS,DTWEXBGS,DGS10,DGS2,T10YIE \
  --from "$YESTERDAY" --to "$TODAY"
```

UPSERT のため重複日付は安全。

#### 初期化（3 年分一括）

```bash
uv run python scripts/fetch_fred.py \
  --series VIXCLS,DTWEXBGS,DGS10,DGS2,T10YIE \
  --from 2023-04-23 --to 2026-04-21
```

5 シリーズ × 3 年で約 3,900 行（約 1 秒）。

#### 動作確認

```bash
docker exec zenigame-fx-db-1 psql -U zenigame_fx -d zenigame_fx -c \
  "SELECT series_id, COUNT(*) AS rows, COUNT(value) AS non_null, MIN(date), MAX(date)
   FROM macro_index_daily GROUP BY series_id ORDER BY series_id;"
```

#### 失敗時

| 失敗 | 対応 |
|------|------|
| Exit code 2 + `failed=[...]` | API key 不正 / 401-403 → `.env` の `FRED_API_KEY` を確認 |
| Exit code 2 + `empty=[...]` | series_id typo or 期間内に営業日なし → series 名や日付を見直す |
| 429 / 5xx | 自動で 3 試行までリトライ。継続する場合は時間を置いて再実行 |

#### Look-ahead 契約

`macro_index_daily.date=D` の値は **`D+1` 以降の primitive 判断にのみ利用する**（T+1 利用原則）。当日 intraday 使用は look-ahead bias を生むため禁止。詳細は `devnotes/20260422-1027-fred-ingest-implementation/conceptual-design.md` §3。

### 7. OANDA CFD instrument 疎通試験

CFD 系 instrument (SPX500/WTI/XAU/XCU/JP225/USB10Y/USB02Y) が現 OANDA live 口座から candles 取得できるかを試験する。primitive P7-P12 実装の前提情報。

#### 実行

```bash
uv run python scripts/oanda_cfd_probe.py
```

結果は `devnotes/20260422-1149-oanda-cfd-probe/probe-result.json` (生データ) と `probe-report.md` (整形レポート) に出力。stdout には各 instrument の verdict を逐次表示。

#### Verdict 仕様

| HTTP status | verdict | スクリプト挙動 |
|---|---|---|
| 200 | OK | 結果記録、続行 |
| 401 | (fatal) | **即 abort, exit 1**, JSON/MD は書かない |
| 403 | FORBIDDEN | 結果記録、続行 |
| 404 | NOT_FOUND | 結果記録、続行 |
| 5xx (retry 失敗後) / 429 / TransportError / その他 | OTHER | 結果記録、続行 |

#### 観測 vs 解釈

verdict は観測事実のみ。FORBIDDEN/NOT_FOUND は **現 live/account/environment での観測結果** であり、永久不可とは解釈しないこと。account 区分・契約状態・地域規制等の変更で結果が変わる可能性あり。

#### 実測結果（2026-04-22）

7 instrument すべて **verdict=OK, status=200, candle_count=10**（M1 candles 10 件取得成功）。仮説 H1「米国規制で 403」は **REJECT**、H2「全アクセス可能」が **CONFIRM**。

参照: `devnotes/20260422-1149-oanda-cfd-probe/probe-report.md` / `probe-result.json`

#### 失敗時

| 失敗 | 対応 |
|------|------|
| Exit 1 + `[fatal] OANDA 401` | `OANDA_API_TOKEN` を `.env` で再確認 |
| 全件 OTHER (5xx / TransportError) | 時間を置いて再実行 |

## SSOT 参照

| 項目 | 参照キーパス（config/alpha_factory/default.yaml） |
|------|--------------------------------------------------|
| max_cycle_seconds | `improve_cycle.max_cycle_seconds` |
| plateau_cycles | `improve_cycle.plateau_cycles` |
| plateau_mutation_bump | `improve_cycle.plateau_mutation_bump` |
| mutation_rate_max | `improve_cycle.mutation_rate_max` |
| audit-interval | Phase 2I で `improve_cycle.audit_interval` 追加予定（未定義） |

## 関連ドキュメント

- [stage-gates.md](stage-gates.md)
- [swim-lane.md](swim-lane.md)
- [codex-discipline.md](codex-discipline.md)
- `.claude/skills/zenigame-fx-autopilot/SKILL.md`
- `.claude/skills/zenigame-fx-improve-cycle/SKILL.md`

## 関連 TODO

- 未着手（運用手順は実装フェーズの完了に応じて随時追記）
