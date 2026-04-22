# Concept: fix-oanda-credentials-validation

## 目的

`tests/api/test_oanda_credentials.py` の 2 件 fail を解消。空文字列の OANDA_API_TOKEN / OANDA_ACCOUNT_ID で `ValueError` が raise される仕様に修正。

## 現状

- `Settings()` (pydantic_settings BaseSettings) は default `""` を許容
- テスト側は空文字で raise を期待
- 監査起因 (audit-cycle-5)

## 方針

- **Option A**: `Settings` 側で `@field_validator` を追加し、空文字を reject
- **Option B**: 別ヘルパー `validate_oanda_settings()` を作って、ingest/api 利用直前で呼ぶ
- B のほうが「ingest 文脈でだけ厳格、テスト等の文脈では default 許容」の使い分けが効く

推奨: **Option B**

## 実装範囲

- `src/api/oanda.py`（or 新設 `src/api/oanda_client.py`）に `validate_credentials()` 関数
- 既存 `src/api/` 下の OANDA 呼び出し箇所で呼び出し
- 既存テスト 2 件が pass

## 優先度・モード

- Priority: Medium
- Mode: incremental
- テーマ: infrastructure
