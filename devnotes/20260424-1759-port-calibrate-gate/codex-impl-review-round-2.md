## 判定: REVISE

## 対応マトリクス
| # | 前回指摘 | 対応箇所 | 評価 |
|---|---|---|---|
| 1 | `total_pnl` / `max_drawdown_pct` / `trade_count` の null/NaN未検知により `compute_monitoring` で異常終了余地 | `REQUIRED_NON_NULL_COLS` 追加、`_NAN_CHECK_FLOAT_COLS` 拡張、`compute_monitoring` の `None` フィルタ、`exit 8` テスト追加 | **部分対応**（`trade_count` の NaN 検知が未担保） |
| 2 | `calibrate_gate.applied` が書き込み時のみ emit | 書き込み時 `applied=true`、非書き込み時 `applied=false`、`reason` 付与、関連テスト3件 | **対応完了** |

## 全体所感
前回の主論点に対して実装意図は概ね正しく、特に `applied` 常時 emit は要件を満たしています。  
ただし #1 は「3列すべての null/NaN を入口で正規化して `SchemaMismatchError -> exit 8`」という観点で、`trade_count` の NaN 経路が残っています。

## 必須修正点 (REVISE のみ)
1. `trade_count` の NaN を `validate_schema` で明示的に弾いてください。  
   例: NaN 検査対象に `trade_count` を含める、または数値列共通で `isfinite` 検証を入れる。  
   現状の `compute_monitoring` は `None` だけ除外しており、`trade_count=NaN` だと `int(np.nan)` 系で `SchemaMismatchError` 以外に逸脱する余地があります。