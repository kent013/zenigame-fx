# 概念設計: alpha-sieve OOS validation framework + skill port (T025)

**作成日時**: 2026-04-24 14:44 (JST)
**サイクル**: autopilot cycle 28 (port-alpha-sieve)
**前提**: T001-T024 マージ済 (`b303be6`)、815 tests passing / 1 skip

## 1. 課題と仮説

### 課題

Stage C 通過個体は「Stage C holdout 期間 (`dataset.end ~ +60d`) で `live_criteria` を全部満たした」状態に過ぎず、
**holdout 期間特有のレジーム** に過適合している可能性が排除できない。
zenigame では `Alpha Sieve` がさらに別期間で再検証して true positive を絞っていた。zenigame-fx でも同等の追加ゲートを設ける。

### 仮説

- **H1**: Stage C 通過個体を holdout 後 5 日エンバーゴ + 90 日 OOS で再評価し、`sharpe > 0.5 AND trade_count >= 30 AND total_pnl > 0` を要求すれば、
  「holdout 期間に偶然合致しただけの個体」を 1/2 ~ 1/3 に絞り込める（経験則 — 後 calibrate-gate で実測値で更新）。
- **H2**: 90 日というレンジは `stage_c_holdout_days=60` と非対称にし、間に 5 日エンバーゴを置くことで、Stage C と Sieve の境界依存（autocorrelation / レジーム持続）を緩和できる。
  なお「為替レジームが四半期スパンで持続」というリスクは時間的非重複だけでは排除できないため、Phase 4 で **複数非連続窓** (45d×2 等) 評価を追加する旨を仕様に明記する。
- **H3**: 通過基準 `sharpe > 0.5` は live_criteria の `sharpe_min=1.0` より緩い。
  Sieve 期間は OOS のため Sharpe degradation が許容される（デフォ +0.5 だが、calibrate-gate で実測連動に置換予定）。
  小標本 Sharpe バイアスは `trade_count_min=30` でひとまず軽減し、DSR は **レポート併記** とし当面ゲートには使わない（Phase 4 で hard gate 化）。

### 成功判定

- 実装後に cycle 21 run-3 (Stage C 通過 0 件) で `no_candidates` レポートが正常出力される
- Stage C 通過個体が 1 体以上ある Run（将来発生時）で OOS 通過個体一覧 + 統計が出力される
- 815 tests passing baseline 維持、追加テスト 5+ 件 passing

## 2. 全体設計

### 2.1 入出力契約

```
入力:
- archive Parquet     .cache/alpha_factory/runs/genomes_{run_id}.parquet
- summary.json        reports/run-reports/run-{N}/summary.json
- DB 接続             src.db.connection.SessionLocal (PostgreSQL)

処理:
- archive Parquet を pyarrow で読み、stage_c_pass=True 行を抽出
- 各個体について OOS 期間（holdout_end + sieve_embargo_days(=5) ~ +90d）で backtest 実行
- 通過基準（sharpe > 0.5 AND trade_count >= 30 AND total_pnl > 0）判定
- 通過個体一覧 + 統計を md に出力

出力:
- reports/alpha-sieve/{yyyy-mm}/sieve-R{run_number}.md
- 終了コード 0 (no_candidates 含む正常終了) / 1 (error)
```

### 2.2 OOS 期間定義

| 用語 | 定義 |
|------|------|
| `holdout_end` | `dataset.end + stage_c_holdout_days` (UTC) |
| `sieve_embargo_days` | 5（Stage C と Sieve の境界依存緩和、López de Prado 2018 Ch.7 の embargo 思想） |
| `sieve_start` | `holdout_end + sieve_embargo_days` (UTC, 0:00) |
| `sieve_end` | `sieve_start + sieve_window_days` (UTC, 0:00) |
| `sieve_window_days` | 90（暫定固定、Phase 4 calibrate-gate で動的化検討） |

**Phase 4 拡張予定**: 複数非連続窓（例: `45d × 2 with gap`）に拡張し、CSCV (Bailey et al. 2014) ベースの過学習確率推定へ接続する。
本 Phase 2 実装は CSCV の簡易版として **単一追加 OOS 窓** を先行導入する位置付け。

bars が DB に存在しない場合は **fail-fast せず `no_data` 理由でレポートに記録**（個体単位 skip）。
全 bars 不在時は run 全体を `no_data` レポート出力で終了。

### 2.3 通過基準

```python
PASS_CRITERIA = {
    "sharpe_min": 0.5,           # sharpe > 0.5  (strict greater-than)
    "trade_count_min": 30,       # trade_count >= 30
    "total_pnl_min": 0.0,        # total_pnl > 0  (strict greater-than)
}
```

判定: `sharpe > 0.5 AND trade_count >= 30 AND total_pnl > 0` を AND で合成。
1 つでも欠けば不通過。

### 2.4 通過基準の根拠（debate-synthesis.md §B / E + Codex Round 1 反映）

- **`sharpe > 0.5`**: live_criteria は `sharpe_min=1.0` だが OOS は劣化を見越して 0.5。
  Stage B `median_oos_sharpe ≥ 0.20` より厳しく、live より緩い中間値。
  小標本ノイズ対策は `trade_count_min=30` 側で担保。
- **`trade_count >= 30`**: Stage C `trade_count_min=50 / 60d` に対し Sieve 90 d で `30 / 90d ≒ 0.33 件/日` の最低ライン。
  Codex Round 1 指摘（`>10` は約 0.11 件/日でサンプル不足）を受けて 30 に引き上げ。
  「`max(30, ceil(0.5 * stage_c_trade_count))` の相対基準」案は Phase 4 calibrate-gate で実測値に基づき判断する。
- **`total_pnl > 0`**: 純利益方向（イントラデイ + コスト反映後）。

**Deflated Sharpe Ratio (DSR)**: 当面はゲート判定には使わず、レポートに併記のみ（`statistics-dsr-bootstrap` モジュール再利用、可能な範囲）。
Phase 4 で `DSR > 0` を hard gate 化する候補とする。

### 2.5 出力仕様

```
# Alpha Sieve Report — run_{run_id} (Run #{run_number})

- status: ok | no_candidates | no_data | error
- generated_at: 2026-04-24T14:44:00+09:00
- run_id: run_20260423_195917
- archive_path: .cache/alpha_factory/runs/genomes_run_20260423_195917.parquet
- instrument: EUR_JPY
- holdout_end: 2026-05-21T00:00:00Z
- sieve_embargo_days: 5
- sieve_window: [2026-05-26T00:00:00Z, 2026-08-24T00:00:00Z) — 90 days
- bars_loaded: 129600 (or 0 if no_data)

## criteria_snapshot

- sharpe_min: 0.5 (strict gt)
- trade_count_min: 30 (>=)
- total_pnl_min: 0.0 (strict gt)

## cost_model

- spread_filter (max_spread_bps): 引き継ぎ (run summary.backtest_config 参照)
- holding_cost_per_day_bps: 引き継ぎ
- session_close_utc_hours: 引き継ぎ
- イントラデイ強制クローズ: ON (engine 既定)

## 結果サマリー

- Stage C 通過個体数: 0
- Sieve 評価可能個体数: 0  (no_data 等で除外された数: 0)
- Sieve 通過個体数: 0
- pass 率: -- (n/a)
- mean OOS Sharpe (通過個体): --
- mean OOS Sharpe (全体): --

## 通過個体一覧

| 個体名 | lane_id | OOS Sharpe | OOS PnL | OOS Trade | Stage C Sharpe | Stage C PnL | Stage C Trade | DSR (info) |
|--------|---------|------------|---------|-----------|----------------|-------------|---------------|------------|
| (該当なし) | | | | | | | | |

## 不通過個体（理由付き）

| 個体名 | lane_id | OOS Sharpe | OOS PnL | OOS Trade | 理由 |
|--------|---------|------------|---------|-----------|------|
| (該当なし) | | | | | |

## no_data 詳細

- (該当なし)
- 不足の場合は instrument / 必要 bar 範囲 / 実 bar 数 を列挙

## ノート

- {{ no_candidates の場合: "Stage C 通過個体が 0 体のため Sieve 評価をスキップしました。" }}
- {{ no_data の場合: "OOS 期間の bars が DB に存在しないため Sieve 評価をスキップしました。" }}
```

**status 仕様**:
- `ok`: 1 個体以上を評価し終えた（通過 0 体含む正常終了）
- `no_candidates`: Stage C 通過個体が 0 体
- `no_data`: OOS 期間の bars が DB に 0 件、または評価可能個体が全 no_data
- `error`: archive Parquet / summary.json 不存在等の構成エラー（exit 1）

### 2.6 失敗時の defensive 仕様

| 状況 | 挙動 |
|------|------|
| archive Parquet 不存在 | error (exit 1) |
| summary.json 不存在 | error (exit 1) |
| Stage C 通過 0 件 | no-op で `no_candidates` レポート出力 (exit 0) |
| OOS 期間の bars が DB に 0 件 | `no_data` レポート出力 (exit 0) |
| 個体単位の backtest 例外 | reason="system_failure" で不通過扱い、続行 |
| 評価可能個体が 0 件 (全 no_data) | `no_data` 理由で全件不通過、レポート出力 (exit 0) |

## 3. モジュール分割

```
scripts/alpha_factory/run_alpha_sieve.py   (CLI エントリ + 全実装、~400 LoC)
  ├─ _parse_args                          (argparse)
  ├─ _resolve_run                         (run_id → archive Parquet path / summary path 解決)
  ├─ _load_stage_c_passers                (pyarrow で Parquet を読み stage_c_pass=True 行抽出)
  ├─ _load_oos_bars                       (DB から OOS 期間 bars 取得)
  ├─ _evaluate_one                        (個体 1 体の OOS backtest)
  ├─ _judge                               (通過基準判定)
  ├─ _render_report                       (Markdown レポート生成)
  └─ main                                 (orchestration)

.claude/skills/zenigame-fx-alpha-sieve/SKILL.md   (skill 定義 — CLI ラップ)

tests/scripts/test_run_alpha_sieve.py    (5+ tests)
```

### 3.1 既存モジュール再利用

- `src.db.connection.SessionLocal` — DB セッション
- `src.db.models.{CurrencyPair, PriceBarM1}` — テーブルモデル
- `src.alpha_factory.archive.GenomeArchive.load` — Parquet 読み戻し
- `scripts.alpha_factory.run_ga._bar_row_to_price_bar / _meta_from_pair` — bars 変換ヘルパは複製しない方針 (DRY)
  - run_ga.py から **そのまま import**（私的 API ではあるが Phase 2 では SSOT を 1 箇所に保つ）
- `src.alpha_factory.config.{BacktestSectionConfig, load_config}` — backtest 設定継承
- `src.alpha_factory.primitives.{RegistryEvaluator, ensure_registered}` — primitive 評価器
- `src.dsl.genome.Genome` / `src.dsl.serialize.dict_to_genome` — genome_json 復元
- `src.dsl.strategy.DslStrategy` — strategy ラップ
- `src.broker.mock.MockBroker` — backtest broker
- `src.backtest.engine.{run_backtest, BacktestConfig}` / `compute_metrics` — backtest 実行

## 4. CLI 仕様

```
uv run python scripts/alpha_factory/run_alpha_sieve.py \
  --run-id run_20260423_195917 \
  [--sieve-window-days 90]   # default 90
  [--config config/alpha_factory/default.yaml]   # default
  [--output-dir reports/alpha-sieve]   # default
```

または `--run-number 3`（archive Parquet を逆引き）。

## 5. 反証検討（C9 Falsification-first）

- **反証1**: 「Stage C で `live_criteria` を満たしているなら追加 OOS は冗長では？」
  → No: holdout 60 日は単一連続区間で、レジーム偏重を排除できない。Sieve は「直後 90 日でも持続するか」の confirmation。

- **反証2**: 「sharpe > 0.5 は厳しすぎ／緩すぎでは？」
  → 暫定: live (1.0) と Stage B median (0.20) の中間。calibrate-gate で実測連動に置換予定（明示的に Phase 4 deferred）。

- **反証3**: 「90 日は短いのでは？」
  → Phase 2 段階では Stage C 60 日との非対称性を確保する目的が主。Phase 4 で Sieve window と通過基準を実測ベースで再校正する。

- **反証4**: 「個体ごとに backtest を独立実行するとコストが高いのでは？」
  → 通過個体は実質 0~数個体規模なので Phase 2 では問題なし。preload 共通化は将来の最適化。

- **反証5（Codex Round 1）**: 「holdout 直後 90 日 = レジーム持続時の独立性が弱い」
  → 5 日エンバーゴで境界依存を緩和、複数非連続窓は Phase 4 で追加。

- **反証6（Codex Round 1）**: 「`trade_count > 10` は約 0.11 件/日でサンプル不足」
  → `>= 30 / 90d` (~0.33 件/日) に引き上げ済。Phase 4 で `max(30, ceil(0.5 * stage_c_trade_count))` 相対基準を検討。

- **反証7（Codex Round 1）**: 「Sharpe>0.5 でも小標本では有意でない」
  → DSR を **レポート併記** で観測、Phase 4 で hard gate 化候補。trade_count 引き上げで一次対応。

## 6. スコープ外（明示）

- **Sieve warmstart 機構**（zenigame T439 相当の archive 注入）— Phase 4 別 TODO
- **Score bypass 経路**（zenigame T479 相当）— Phase 4 別 TODO
- **DB テーブル化**（`alpha_sieve_runs` 等）— Phase 4 別 TODO（現状 md レポートのみ）
- **レジーム別集計**（zenigame の 6 レジーム別テーブル）— FX のレジーム定義が未確定のため Phase 4 以降
- **adaptive vs non-adaptive 比較**（zenigame compare モード）— 未実装

## 7. 残課題（実装後に決まる）

- 通過基準の calibrate（実測 Run でのデータが揃ってから）
- レジーム別集計の追加（FX レジーム定義 TODO 完了後）
- score bypass 経路の必要性判断（Stage C 通過 0 体が連続したら検討）

---

## レビュー観点（Codex conceptual-review 用）

1. **OOS 期間の妥当性** — `holdout_end + 5d embargo + 90d` 設計は Stage C との重複排除と境界依存緩和として妥当か？
2. **通過基準の妥当性** — `sharpe > 0.5 AND trade_count >= 30 AND total_pnl > 0` は debate-synthesis.md の方向性と整合するか？
3. **defensive 設計** — Stage C 通過 0 件 / no_data の no-op フォールバックは適切か？
4. **学術引用** — Bailey (2014) PBO / López de Prado (2018) Ch.7 を引用した OOS validation 二段化（CSCV 簡易版として単一追加 OOS 窓）の justification は妥当か？
