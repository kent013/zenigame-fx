# 詳細設計: pair_specific aux data loader Phase 1

親: [conceptual-design.md](conceptual-design.md)

## 変更箇所

| ファイル | 変更 |
|---------|------|
| `data/raw/fred/DXY.csv` | FRED 経由取得 (date, close 列) |
| `data/raw/fred/VIX.csv` | 同上 |
| `data/raw/fred/copper.csv` | 同上 |
| `data/raw/fred/gold.csv` | 同上 |
| `src/alpha_factory/aux_loader.py` | 新規モジュール (load_dxy / load_vix / load_event_snapshot / load_aux_series) |
| `scripts/alpha_factory/run_ga.py` | RegistryEvaluator 生成時に aux loader 経由で snapshot/aux_series を注入 |
| `config/alpha_factory/default.yaml` | `aux.fred_data_dir` / `aux.event_calendar` 等の path 設定 |
| `tests/alpha_factory/test_aux_loader.py` | 新規 (CSV → snapshot 構築の round-trip) |

## 連動 TODO

- T039 (event_snapshot as_of_strict) の production toggle が本 TODO 完了で有効化可能
- T036 (FSP) の DXY 連動部分が active 経路に乗る (現在 skipped_no_factor_data)
- bug-p10-strict-aux: 本 TODO 完了後に strict default true 化

## DoD

- [ ] DXY/VIX/Copper/Gold の最小データを `data/raw/fred/` に整備 (Phase 1 は手動取得 OK)
- [ ] aux_loader が production runner 経由で primitive に snapshot 注入
- [ ] Run で pair_specific の出力分布が定数 (0/1/0.5) から実値へ変化することを確認
- [ ] T039 / T036 / bug-p10 の連動効果が Run report で観測可能

## 反証

- 反証仮説 1: 「FRED data は遅延で過去から後で更新される (vintage 問題)」 → 取得時点の vintage を loader で記録し、as_of_strict で過去のみ参照
- 反証仮説 2: 「VIX は intraday 更新無く daily series で intraday primitive に意味薄い」 → M5 VIXRegimeGate は publication_ts < bar_time の bisect_left で扱う既存設計が合致
