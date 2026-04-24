# Alpha Sieve — 運用ドキュメント

## 概要

**Alpha Sieve** は、GA Run の Stage C 通過個体を **別期間 OOS で再検証** する追加ゲート。
holdout 直後の 5 日 embargo + 90 日 OOS で再 backtest し、
`sharpe > 0.5 AND trade_count >= 30 AND total_pnl > 0` を要求して true positive を絞る。

詳細な概念定義: [concepts/alpha-sieve.md](concepts/alpha-sieve.md)
用語: [terminology.md](terminology.md) — `Alpha Sieve` / `Sieve OOS Window` / `Sieve Embargo`

---

## 実行方法

### CLI

```bash
# run_id 指定
uv run python scripts/alpha_factory/run_alpha_sieve.py --run-id run_20260423_195917

# run number 指定（後方互換）
uv run python scripts/alpha_factory/run_alpha_sieve.py --run-number 3

# 設定 override
uv run python scripts/alpha_factory/run_alpha_sieve.py --run-id run_xxx \
  --sieve-window-days 90 --sieve-embargo-days 5 \
  --config config/alpha_factory/default.yaml
```

### Skill

```
/zenigame-fx-alpha-sieve <run_id>
/zenigame-fx-alpha-sieve --run-number <N>
```

`SKILL.md`: `.claude/skills/zenigame-fx-alpha-sieve/SKILL.md`

---

## OOS 期間定義

| 用語 | 定義 |
|------|------|
| `holdout_end` | `dataset.end + stage_c_holdout_days` (UTC) |
| `sieve_embargo_days` | デフォ 5（Stage C と Sieve の境界依存緩和） |
| `sieve_start` | `holdout_end + sieve_embargo_days` (UTC, 0:00) |
| `sieve_end` | `sieve_start + sieve_window_days` (UTC, 0:00) |
| `sieve_window_days` | デフォ 90 |

**学術背景**:
- López de Prado (2018) Ch.7 — purged/embargoed cross-validation
- Bailey, Borwein, López de Prado, Zhu (2014) — Probability of Backtest Overfitting (CSCV)

Phase 2 実装は CSCV の **簡易版として単一追加 OOS 窓** を先行導入する位置付け。
Phase 4 で複数非連続窓（例: 45d × 2 with gap）に拡張し、過学習確率推定へ接続予定。

---

## 通過基準

```
sharpe > 0.5  (strict greater-than)
AND trade_count >= 30
AND total_pnl > 0  (strict greater-than)
```

| 指標 | 基準 | 根拠 |
|------|------|------|
| Sharpe | `> 0.5` | live_criteria sharpe_min=1.0 と Stage B median 0.20 の中間。OOS 劣化を見越す |
| Trade count | `>= 30` | 30 / 90d ≒ 0.33 件/日。小標本 Sharpe バイアス対策 |
| Total PnL | `> 0` | 純利益方向（イントラデイ + コスト反映後） |

Phase 4 calibrate-gate で実測値ベースに更新予定。

---

## 入出力

### 入力

| 種別 | パス |
|------|------|
| archive Parquet | `.cache/alpha_factory/runs/genomes_{run_id}.parquet` |
| summary.json | `reports/run-reports/run-{N}/summary.json` |
| YAML 設定 | `config/alpha_factory/default.yaml`（BacktestSectionConfig SSOT） |
| DB | `src.db.connection.SessionLocal` (PostgreSQL) — OOS 期間の price_bars_m1 |

### 出力

| 種別 | パス |
|------|------|
| Sieve レポート | `reports/alpha-sieve/{yyyy-mm}/sieve-R{run_number}.md`（JST 年月ブロック） |

### レポート構成

```
# Alpha Sieve Report — {run_id} (Run #{run_number})

- status: ok | no_candidates | no_data | error
- generated_at / run_id / archive_path / instrument
- holdout_end / sieve_embargo_days / sieve_window / bars_loaded

## criteria_snapshot           — 通過基準のスナップショット
## cost_model                  — backtest コスト設定（spread / holding cost / session_close）
## 結果サマリー                  — Stage C 通過数 / Sieve 通過数 / pass 率 / mean Sharpe
## 通過個体一覧                  — OOS Sharpe / PnL / Trade + Stage C 値対照
## 不通過個体（理由付き）        — reason_codes
## no_data 詳細                — 不足 instrument / 期間
## ノート                       — status 別注記、system_failure 件数
```

---

## defensive 経路（exit code）

| 状況 | 挙動 | exit |
|------|------|------|
| archive Parquet 不存在 | stderr ERROR | 1 |
| summary.json 不存在 | stderr ERROR | 1 |
| Stage C 通過 0 件 | `no_candidates` レポート出力 | 0 |
| OOS bars 不存在 (DB) | `no_data` レポート出力 | 0 |
| 個体 backtest 例外 | `system_failure` 不通過扱い、続行 | 0 |

`status: ok` でも `system_failure` 個体が混在する場合あり（個別 logger.warning 'alpha_sieve.eval_failure' を確認）。

---

## BacktestConfig 引き継ぎ (SSOT 戦略)

`run_ga.py` の summary.json は `initial_cash / leverage / units` の 3 フィールドのみ書き出すため、
`max_spread_bps` / `holding_cost_per_day_bps` / `session_close_utc_hours` は YAML config から再ロードする。

`_build_oos_backtest_config(...)`:
1. `load_config(config_path)` → `BacktestSectionConfig` （SSOT）
2. summary.json の 3 フィールドと整合性チェック → 不一致なら `logger.warning("alpha_sieve.backtest_config_mismatch")`
3. `BacktestSectionConfig` 値で `BacktestConfig` を構築

---

## DSR 取り扱い

Phase 2 では恒常 `None`（レポート上 `--` 表示）。
理由: `src.alpha_factory.statistics.deflated_sharpe_ratio` は `n_trials >= 2 / mean_sr_trials / std_sr_trials` の trial pool 統計量を要求するため、Sieve 単一個体評価では構成不能。

Phase 4 で「Stage C 通過個体プール全体の SR 分布」を入力に正式接続予定。

---

## Phase 4 ロードマップ

| 項目 | 概要 |
|------|------|
| 複数非連続 OOS 窓 | `45d × 2 with gap` 等で CSCV 過学習確率推定へ |
| DSR hard gate | trial pool 統計量を組んで `DSR > 0` を通過要件に |
| 通過基準 calibrate | 実測 Run データで `sharpe_min` / `trade_count_min` を動的化 |
| 取引発生日数下限 | 例 `non_zero_trade_days >= 15` で偏在抑制 |
| Sieve warmstart | 通過個体を archive 化 → 次 Run の seed 注入（zenigame T439 相当） |
| Score bypass 経路 | adaptive_pass=0 継続時の救済路（zenigame T479 相当） |
| DB 化 | `alpha_sieve_runs` テーブル化、レジーム別集計 |

---

## 関連ドキュメント

- [concepts/alpha-sieve.md](concepts/alpha-sieve.md) — 概念 SSOT
- [stage-gates.md](stage-gates.md) — Stage A/B/C
- [cross-pair.md](cross-pair.md) — (ii-lite) 評価（Sieve とは独立した追加ゲート）
- [terminology.md](terminology.md) — 用語集
- 設計ノート: `devnotes/20260424-1444-port-alpha-sieve/`
