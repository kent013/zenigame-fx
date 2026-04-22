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
