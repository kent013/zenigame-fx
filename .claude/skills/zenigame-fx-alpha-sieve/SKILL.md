---
name: zenigame-fx-alpha-sieve
description: Alpha Sieve（OOS検証）の実行・結果分析を行う（Stage C 通過個体を別期間 OOS で再検証）
user-invocable: true
argument-hint: "[run_id] | --run-number <N>"
---

# Alpha Sieve 実行 skill (zenigame-fx)

`scripts/alpha_factory/run_alpha_sieve.py` を呼び出し、Stage C 通過個体を **holdout 後 5 日エンバーゴ + 90 日 OOS** で再検証する追加ゲート。

## 使い方

```
/zenigame-fx-alpha-sieve <run_id>           # run_id 指定 (例: run_20260423_195917)
/zenigame-fx-alpha-sieve --run-number 3     # run number 指定
```

## 実行フロー

### Step 1: コマンド実行

```bash
uv run python scripts/alpha_factory/run_alpha_sieve.py --run-id <run_id>
# または
uv run python scripts/alpha_factory/run_alpha_sieve.py --run-number <N>
```

### Step 2: 結果取得

- exit code 確認
- stderr に error があれば user に報告して終了
- stdout の `sieve report written: <path> (...)` から出力 path を取得

### Step 3: レポート読み込み + サマリー報告

`reports/alpha-sieve/{yyyy-mm}/sieve-R{run_number}.md` を Read し、以下を抽出:

- `status` (ok / no_candidates / no_data)
- Stage C 通過個体数 / Sieve 評価可能個体数 / Sieve 通過個体数
- pass 率
- 通過個体上位 3 体の OOS Sharpe / PnL / Trade
- 不通過理由分布

### Step 4: ユーザ報告

```
✅ Alpha Sieve 完了

run: {run_id} (Run #{run_number})
status: {status}
instrument: {instrument}
sieve window: {sieve_start} ~ {sieve_end}

結果:
- Stage C 通過個体: {n_candidates}
- Sieve 評価可能: {n_evaluable}
- Sieve 通過: {n_pass} ({pass_rate})
- mean OOS Sharpe (通過): {mean_pass_sharpe}

通過個体上位:
1. {top1_name}: Sharpe={s1}, PnL={p1}, Trade={t1}
2. ...

レポート: reports/alpha-sieve/{yyyy-mm}/sieve-R{run_number}.md
```

## 通過基準

- `sharpe > 0.5 AND trade_count >= 30 AND total_pnl > 0`

## OOS 期間

- `holdout_end + 5 日 (embargo) ~ + 90 日`
- Stage C との境界依存緩和のため 5 日 embargo
- 90 日窓は CSCV (Bailey et al. 2014) の簡易版として単一追加 OOS 窓を先行導入
- Phase 4 で複数非連続窓へ拡張予定

## エラーハンドリング

| 状況 | 挙動 | exit code |
|------|------|-----------|
| archive Parquet 不存在 | stderr に ERROR を出して終了 | 1 |
| summary.json 不存在 | stderr に ERROR を出して終了 | 1 |
| Stage C 通過 0 件 | `no_candidates` レポート生成 | 0 |
| OOS bars 不存在 | `no_data` レポート生成 | 0 |
| 個体単位 backtest 例外 | reason="system_failure" で不通過扱い、続行 | 0 |

## 関連ドキュメント

- 概念: [docs/alpha_factory/concepts/alpha-sieve.md](../../../docs/alpha_factory/concepts/alpha-sieve.md)
- 運用: [docs/alpha_factory/sieve.md](../../../docs/alpha_factory/sieve.md)
- 用語: [docs/alpha_factory/terminology.md](../../../docs/alpha_factory/terminology.md)

## 注意事項

- `--config config/alpha_factory/default.yaml` が SSOT。summary.json の backtest_config は整合性チェックのみ
- DSR は Phase 2 では恒常 `--` 表示（trial pool 構成不能のため、Phase 4 で接続）
- レポートは JST yyyy-mm のブロックに書き出される
