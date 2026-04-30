# 詳細設計: archive `trade_sharpe_raw` 上書き bug 修正

親: [conceptual-design.md](conceptual-design.md)

## 変更箇所

| ファイル | 変更 |
|---------|------|
| `src/alpha_factory/archive.py` | GENOMES_SCHEMA に 2 列追加 (`trade_sharpe_stage_b`, `trade_sharpe_stage_c`)、`_create_row_template` に None 初期化 |
| `src/alpha_factory/archive.py` | `collect_stage_b` で `is_full_sharpe` を `trade_sharpe_stage_b` に書き、**`trade_sharpe_raw` は触らない** |
| `src/alpha_factory/archive.py` | `collect_stage_c` で base_sharpe を `trade_sharpe_stage_c` に書く (既存の trade_sharpe_raw 上書き path も削除) |
| `tests/alpha_factory/test_archive.py` | schema 列数 40→42、collect 経路の値伝搬テスト |
| `scripts/alpha_factory/generate_run_report.py` | report に Stage A/B/C sharpe 比較表セクション追加 (差分監視) |
| `docs/alpha_factory/clause-architecture.md` | sharpe 列の SSoT 記述更新 |

## 不変条件

- `trade_sharpe_raw` = Stage A backtest 結果 (selection 用、変更不可)
- `fitness_pen = trade_sharpe_raw - α × size_norm` が archive 上で常に成立
- Stage B 通過群を観察した時 `trade_sharpe_stage_b` が表示され、Stage A との乖離 (= IS 期間で性能変動) を切り分け可能

## 反証

- 反証仮説 1: 「Stage B の `is_full_sharpe` を残すことで何か downstream consumer が壊れる」 → grep で is_full_sharpe / trade_sharpe_raw を読む箇所を全列挙し、影響無いことを確認
- 反証仮説 2: 「列追加で archive サイズが大幅増」 → 各 nullable float64 で +16 bytes/row × 5856 行 ≈ 91 KB = 無視可

## DoD

- [ ] 2 新列 `trade_sharpe_stage_b`/`stage_c` を schema + template + collect 4 段伝搬
- [ ] `trade_sharpe_raw` 上書き経路を撤廃 (Stage A 値固定)
- [ ] 既存テスト全 pass + 新規 4 件追加 (collect 順 / 上書き無し / fitness_pen 整合 / schema 拡張)
- [ ] run-report で 3 stage sharpe 比較セクション追加
- [ ] Codex impl-review APPROVED
