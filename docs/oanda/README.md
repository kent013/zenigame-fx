# OANDA API ドキュメント ローカルミラー

`wget --mirror` で取得した OANDA 公式ドキュメントのオフラインコピー。Git にはサイズ削減のため入れず、必要時に `scripts/mirror_oanda_docs.sh` 相当で再取得する運用を想定（現状はスクリプト未作成）。

## 構成

- `jp-v1/` — https://developer.oanda.com/docs/jp/ のミラー（**v1 API、日本語**）
  - v1 API は legacy だが、日本語で一通りの説明があるので通読用途に最適
  - 現在 zenigame-fx が使うのは v20 なので、API 仕様そのものはこちらを参照しない
- `v20/` — https://developer.oanda.com/rest-live-v20/ のミラー（**v20 API、英語のみ**）
  - zenigame-fx の [src/api/oanda/](../../src/api/oanda/) はこちらに準拠
  - `introduction/` `best-practices/` `development-guide/` と、エンドポイント定義（`*-ep/`）／データフォーマット定義（`*-df/`）の各セクション
- `shared/` — 共通 CSS/JS/画像

## 閲覧方法

```bash
open docs/oanda/v20/introduction/index.html
open docs/oanda/jp-v1/v1/best-practices/index.html
```

ブラウザで開けば相対リンクで各ページを行き来できる（`wget --convert-links` 済）。

## 主要エントリポイント

| 目的 | URL（ローカル） |
|---|---|
| v20 全体像 | `v20/introduction/` |
| v20 レートリミット・Keep-Alive | `v20/best-practices/` |
| v20 Candles エンドポイント | `v20/instrument-ep/` |
| v20 Pricing エンドポイント | `v20/pricing-ep/` |
| v20 Order エンドポイント | `v20/order-ep/` |
| v1 日本語 ベストプラクティス | `jp-v1/v1/best-practices/` |
| v1 日本語 ストリーミング | `jp-v1/v1/stream/` |

## レートリミットまとめ

[RATE_LIMITS.md](./RATE_LIMITS.md) を参照。
