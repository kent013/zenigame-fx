# 概念設計: archive `trade_sharpe_raw` 上書き bug 修正

**起点監査**: [audit-codex.md §2 (1)/(11)](../20260427-0050-bug-hunt-audit/audit-codex.md) — confirmed P2

## 仮説

archive 列 `trade_sharpe_raw` が Stage A → Stage B → Stage C で順に上書きされ、各 stage 評価値が分離保存されない。結果 fitness_pen (Stage A 値) と表示される `trade_sharpe_raw` (Stage B IS 値) が乖離し、監査時に矛盾観測される。

## 検証済み事実

- [archive.py:452-457](../../src/alpha_factory/archive.py#L452-L457): `collect_stage_b` が `is_full_sharpe` を `trade_sharpe_raw` に書き込む
- [stage_gate.py:607-617](../../src/alpha_factory/stage_gate.py#L607-L617): Stage B payload に `is_full_sharpe` を出力
- 観測: Run 20 で fitness_pen mean=0.067 vs trade_sharpe_raw mean=-0.19 (差分 0.23)、α×size_norm では説明不能

## 解決方針

archive スキーマに stage 別の sharpe 列を独立追加:
- `trade_sharpe_stage_a: float64 nullable` (Stage A backtest sharpe)
- `trade_sharpe_stage_b: float64 nullable` (Stage B is_full sharpe)
- `trade_sharpe_stage_c: float64 nullable` (Stage C base sharpe = T042 で導入済の trade_sharpe_annualized 関連)
- 既存 `trade_sharpe_raw` は **Stage A 値で固定** (selection 基準と整合させる)

## 成功判定

- archive で fitness_pen と trade_sharpe_raw が selection 計算規約 (= -α×size_norm) で説明できる
- Stage B IS 値は別列で観測可能
- 既存テスト全 pass (schema 拡張のみ、selection logic 不変)

## 北極星制約

archive スキーマ拡張は GENOMES_SCHEMA → _create_row_template → collect_stage_* → flush の 4 段伝搬規約 (Codex 既知パターン)。fitness / selection / live_criteria に影響しない (observability のみ)。
