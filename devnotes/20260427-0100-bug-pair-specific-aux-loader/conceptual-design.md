# 概念設計: pair_specific 用 aux data loader 整備

**起点監査**: [audit-codex.md §2 (16) §4](../20260427-0050-bug-hunt-audit/audit-codex.md) — partially_confirmed P2

## 仮説

pair_specific 12 primitive のうち 半数以上が aux_pair_bars / event_snapshot / vix_snapshot 不在で safe default (0.0 / 1.0 / 0.5) を返す状態。GA はこれら定数信号を含む genome を「常時開放 gate × directional」として悪用し、selection 圧が歪んでいる。production aux loader を整備して本来の機能に戻す。

## 検証済み事実

- [run_ga.py:872](../../scripts/alpha_factory/run_ga.py#L872): `RegistryEvaluator(pair=...)` で aux 全部 None
- pair_specific.py: 不在時 safe default、production fail-fast 経路は strict_aux_required で切替可能
- Run 20-22 観察: P9 (USD_CAD) / P4 (USD_JPY) が EUR_JPY Run で Stage A pass 率 45-48% (定数信号として悪用されている疑い)

## 解決方針

最小実装 (Phase 1):
- `data/raw/fred/` に DXY / VIX / Copper / Gold series を配置 (FRED API 経由、scripts/fetch_fred.py 既存利用)
- `src/alpha_factory/aux_loader.py` 新設で `EconomicEventSnapshot` / `VixSeriesSnapshot` / `aux_series` / `aux_pair_bars` を構築
- `run_ga.py` で `RegistryEvaluator` 生成時に loader 経由で aux を注入
- production yaml で aux source path 設定

Phase 2 以降で:
- 取得 series の自動化 (cron)
- 多通貨 cross-pair bars (GBP_USD, EUR_USD 等) の整備

## 成功判定

- aux 整備後、Run で primitive 選択頻度が変化 (定数信号悪用が減る)
- pair_specific 12 個の真の機能が観測される (各 primitive の signature が値分布として現れる)
- T039 の as_of_strict が production でも有効化できる状態

## 北極星制約

aux データは過去のみ (look-ahead bias 回避)、tz-aware enforcement、period filter で dataset 範囲外除外。fitness / selection への直接影響なし、ただし primitive 機能の本来の発現で間接的に GA 選抜質改善。
