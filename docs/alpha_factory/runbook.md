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

[FRED](terminology.md#fred) の日足マクロ指標（VIX / DXY / Treasury yields / breakeven / Gold / WTI / Copper / commodity / SP500）を `macro_index_daily` テーブルへ取り込む。primitive M5 / P7-P12 等の前提データ。

#### T057 Phase 2 — aux データ pipeline

T057 Phase 2 で aux データの contract 化と一括取得を整備した。**本番 RUN 前に `scripts/fetch_aux_data.sh` を必ず実行**:

```bash
# 既定: 2024-08-01 〜 2026-04-30 (Stage B 18ヶ月 history を含む)
scripts/fetch_aux_data.sh

# 期間指定
scripts/fetch_aux_data.sh 2024-08-01 2026-04-30
```

wrapper は以下を順次実行:
1. **FRED 10 series**: VIXCLS, DTWEXBGS, DGS10, DGS2, T10YIE, GOLDPMGBD228NLBM, DCOILWTICO, PCOPPUSDM, PALLFNFINDEXM, SP500
2. **aux pair bars (M1)**: EUR_USD / USD_JPY (P5 cross-pair primitive 用)
3. **economic events**: `data/raw/calendar/events.csv` を DB upsert

run_ga.py 起動時に preflight check が走り、`hard_required` (VIXCLS / DTWEXBGS / EUR_USD_M1 / USD_JPY_M1) が不足していれば fail-closed で run を拒否する。dev / smoke test 用に `--allow-aux-missing` flag で override 可能。

#### effective_from_utc 契約 (T057 Phase 2)

`macro_index_daily.effective_from_utc` は **その値が利用可能になる UTC 時刻** を表す保守的タイムスタンプ:

- daily 系列 (VIXCLS / DTWEXBGS / SP500 など): `observation_date + 24h`
- 月次系列 (PCOPPUSDM / PALLFNFINDEXM): `observation_date + 35d` (改定遅延吸収)

primitive 側は `bar.bar_time >= effective_from_utc` を満たす obs しか forward-fill しない。これにより look-ahead bias 漏洩を構造的に防ぐ。

詳細: `devnotes/20260427-2234-aux-data-loader-phase2/` および `src/ingest/effective_from.py`.

#### hard_required / soft_required 運用

| 区分 | series / data | 不足時の挙動 |
|------|--------------|--------------|
| **HARD** | VIXCLS, DTWEXBGS (DXY), EUR_USD_M1, USD_JPY_M1 | preflight で fail-closed (override: `--allow-aux-missing`) |
| **SOFT** | GOLDPMGBD228NLBM (Gold), DCOILWTICO (WTI), PCOPPUSDM (Copper), PALLFNFINDEXM (commodity), SP500 | WARN log のみ、該当 primitive (P7/P8/P9/P12) は safe default 経路で動作 |

events (P10/M4) は **partial coverage** (手動 scaffold 33 件, FOMC/NFP/CPI/ECB/BoJ)。自動取得 (forex factory / OANDA Calendar API / FRED releases) は別 TODO。

#### 前提

- `.env` に `FRED_API_KEY` を設定（[FRED API key 発行](https://fred.stlouisfed.org/docs/api/api_key.html)）
- DB コンテナ稼働: `docker start zenigame-fx-db-1`
- `uv run alembic upgrade head` で migration 004 を適用 (effective_from_utc + source 列追加)

#### 通常運用（差分更新）

```bash
TODAY=$(date '+%Y-%m-%d')
YESTERDAY=$(date -v-1d '+%Y-%m-%d')  # macOS の場合
uv run python scripts/fetch_fred.py \
  --from "$YESTERDAY" --to "$TODAY"
# --series 省略時は DEFAULT_SERIES (10 件) が使われる
```

UPSERT のため重複日付は安全。effective_from_utc / source も同時に更新される。

#### 初期化（一括）

```bash
scripts/fetch_aux_data.sh 2024-08-01 2026-04-30
```

10 シリーズ × 約 1.7 年で 約 4,500 行 (FRED 部分は数秒、OANDA pair bars は数分)。

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

## OANDA 準拠の margin closeout 設計（既存実装の文書化、T056）

zenigame-fx の `MockBroker` は OANDA v20 / OANDA Japan の強制ロスカット仕様に準拠する。
本セクションは既存実装（`src/broker/mock.py::force_close_if_margin_call`）の挙動と、
T056 で追加した多層防御（保有 0 + cash マイナスでの新規 entry 抑止）の設計を文書化する。

### OANDA 仕様（参考: developer.oanda.com/rest-live-v20）

- `marginCloseoutPercent ≥ 1.0`（= 維持率 100% 以下）で margin closeout 発動
- 発動時は全保有 position を成行で順次強制決済
- OANDA Japan は JFSA 規制下で同等仕様（個人顧客レバレッジ上限 25 倍 / 維持率 100%）

### 本実装での対応（既存）

| 項目 | 実装 |
|------|------|
| 閾値 | `MockBroker.__init__(maintenance_margin_level_pct=Decimal("100"))`（デフォルト 100%） |
| 発動条件 | `margin_level_pct < maintenance_margin_level_pct`（**strict less-than**）。即ち維持率が 100% **未満** で発動。維持率がちょうど 100.0% の場合は発動しない（境界値）。OANDA 公式仕様の「100% 以下」とはわずかに異なるが、本 MockBroker では現行挙動を維持する |
| 発動経路 | `force_close_if_margin_call`（mock.py 内）を `engine.run_backtest` で per-bar 呼び出し |
| 発動時挙動 | `_close_all_internal(reason="margin_call")` で全 position close |
| 発注価格 | 当該 bar の bid/ask close（成行相当） |

### 多層防御の追加（T056）

「保有 0 + cash マイナス」状態で新規 entry が継続して発注される構造的バグを防ぐ
fail-closed gate を追加。OANDA の margin closeout 仕様（保有中 position に対する強制決済）
とは独立した防衛線として設計した。

- **L1**: `fill_pending` 冒頭で `pre_fill_equity` が非有限値（NaN / Infinity）または
  非正値（≤ 0）の場合、open 系 pending（`open_long` / `open_short`）を drop する。
  close 系（`close_position` / `close_all`）は通常実行（保有 close を妨げない conservative policy）。
- **L2**: `_open_position` で `equity_at_entry` が非有限 / 非正値の場合に
  `InsufficientEquityError`（`Exception` 直系）を raise。
  `fill_pending` ループ内で個別捕捉して drop counter に加算しループ継続。
  L1 を通り抜けた異常経路の最終防御。
- **counter**: `MockBroker._negative_equity_drop_count` に L1 + L2 の drop 件数を累計。
  `pop_negative_equity_drop_count()`（pop semantics）で取り出し、`backtest.finished` log の
  `negative_equity_drop_open_count` field に記録される。

### 別 TODO 候補（本 TODO スコープ外）

- `available_margin >= required_margin` gate（過大 notional の entry reject、保有あり時の防御）
- `maintenance_margin_level_pct` の config 化（現状 `MockBroker.__init__` のデフォルト値固定）
- per-trade `trade_return.invalid_equity_at_entry` warning の抑制（適切な量に収まれば不要）

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
