# Conceptual Design: OANDA CFD Instrument Probe (T005)

## 1. 目的

OANDA の現行 FX **ライブ口座（OANDA_ENV=live, https://api-fxtrade.oanda.com）** において、以下 7 件の CFD 系 instrument に candles エンドポイント経由でアクセスできるかを試験する。

| Instrument | 用途 | 関連 Primitive |
|---|---|---|
| SPX500_USD | S&P 500 連動 | P7 RiskOnOffProxy |
| WTICO_USD | WTI 原油 | P9 OilPriceInverseFlow |
| XAU_USD | 金 (gold) | P12 GoldCorrelationBias |
| XCU_USD | 銅 (copper) | P8 CommodityFlowBias |
| JP225_USD | 日経 225 | 補助指標 |
| USB10Y_USD | 米 10 年債 CFD | 金利感応度 |
| USB02Y_USD | 米 2 年債 CFD | 金利感応度 |

これは **後続 primitive (P7-P12) 実装の戦略を分岐させる「重要な分岐点」**。

- 全 OK → OANDA で M1 candle 取り込み (FX と同じパイプライン拡張)
- 部分 OK → OK 分は OANDA、不可分は FRED 代替 / FX データ完結（realized_vol, usd_strength_synthetic）
- 全不可 → FRED + 自前計算で代替（既存 fred-ingest と組合せ）

## 2. 仮説

**H1 (主仮説)**: OANDA の通常 FX 口座では CFD instrument は権限制限により **403 Forbidden** が返る可能性が高い（特に米国向け規制対象である JP225/USB02Y/USB10Y）。一方 SPX500/XAU/WTICO はプリーミアム CFD account を別途開設しないと利用できない可能性。

**H2 (反証仮説)**: アカウント区分によっては全 instrument がアクセス可能で、追加開設なしで CFD candle データが取れる。実証してみないと分からない。

成功判定: 7 件すべてについて HTTP status / candles 件数 / エラーメッセージを観測でき、判定（OK / 403 / 404 / その他）が一意に決まる。

## 3. スコープ / 非スコープ

### スコープ
- 7 instrument それぞれに `/v3/instruments/{instrument}/candles?count=10&granularity=M1&price=BA` を 1 回ずつリクエスト
- HTTP status code, error message, candles 件数を記録
- 結果を JSON ファイルに出力
- 結果を Markdown レポートに整形して次アクション提案を提示

### 非スコープ
- DB への書き込み（試験のみ。CurrencyPair / price_bar_m1 は触らない）
- 他の granularity / count / from-to 指定での網羅試験
- アカウント開設手続き（試験結果を見てユーザー判断）
- 後続 ingest スクリプトの実装（別 TODO）

## 4. アプローチ

### 4.1 既存資産の再利用

**事前条件（verified by code-read）**: `src/api/oanda/client.py::_raise_for_status` の挙動を本設計の前提として固定する。

| HTTP Status | 既存 client の挙動 | probe での扱い |
|---|---|---|
| 401 | `OandaAuthError` を raise（リトライなし） | 即 abort |
| 403 | `httpx.HTTPStatusError`（`raise_for_status` 由来）を raise（リトライなし） | 捕捉して `verdict=FORBIDDEN` 記録 |
| 404 | `httpx.HTTPStatusError` を raise（リトライなし） | 捕捉して `verdict=NOT_FOUND` 記録 |
| 429 / 5xx | `OandaRateLimitError` / `OandaServerError` → tenacity 3 回リトライ後再 raise | 捕捉して `verdict=OTHER`、status_code 記録 |
| TransportError | tenacity 3 回リトライ | 捕捉して `verdict=OTHER` |
| 200 | 正常 return | `verdict=OK` |

この **「401 と 403 が異なる例外型として降ってくる」** という事前条件が成立しているため `OandaClient` をそのまま流用する。**もしこの条件が将来崩れた場合（例: 403 も `OandaAuthError` 化）は probe 専用の薄い HTTP 呼び出し層に切り替える**。テストでこの前提を担保する（403 シナリオで `OandaAuthError` が出ないことを確認）。

`OandaClient` 初期化時の `account_id` バリデーションは probe 用途でも問題なし（疎通には account_id 不要だが、token を渡すために既存 client 経由で初期化）。

### 4.2 スクリプト構成

`scripts/oanda_cfd_probe.py`（新設、`scripts/oanda_ping.py` を参考）:

1. `OandaClient` を `with` で open
2. 各 instrument について:
   - `client.get_candles(name, granularity="M1", price="BA", count=10)` を try で実行
   - 成功 → `verdict=OK`, status=200, candles 件数, 先頭 candle の time を記録
   - `httpx.HTTPStatusError` → status_code から verdict 派生（403→`FORBIDDEN`, 404→`NOT_FOUND`, それ以外→`OTHER`）、message 記録
   - `OandaAuthError` (401) → 全 probe を中断、token 設定誤りを stderr に出力、exit 1
   - その他例外 → `verdict=OTHER`, message=str(exc) 記録
3. 全件結果を JSON で `devnotes/20260422-1149-oanda-cfd-probe/probe-result.json` に保存
4. **同一スクリプトが続けて probe-report.md も生成する**（4.4 参照、separate formatter にしない）
5. 各 instrument の判定を stdout に出力
6. `--output-json` / `--output-md` オプションで保存先を上書き可能（テスト容易性向上）
7. `--instruments` オプションで対象 instrument を変更可能（デフォルトは設計記載の 7 件）

**verdict 定義（観測事実、解釈なし）**:

| verdict | 定義（観測事実） | 解釈の禁止事項 |
|---|---|---|
| OK | HTTP 200 + candles レスポンス取得（candle_count=0 の weekend ケースも含む） | - |
| FORBIDDEN | HTTP 403 を観測 | 「永久に使えない」と解釈しない。account 区分・契約状態に依存する可能性あり |
| NOT_FOUND | HTTP 404 を観測 | 「OANDA に存在しない」と断定しない。**現 live/account/environment で当該 instrument の candles を取得できなかった** という事実のみ |
| OTHER | 上記以外 (5xx 全 retry 失敗 / 429 / TransportError 等) | 一時的問題の可能性が高いので再試行を推奨 |

### 4.3 出力 JSON スキーマ（draft）

```json
{
  "probed_at": "2026-04-22T03:49:00+00:00",
  "base_url": "https://api-fxtrade.oanda.com",
  "results": [
    {
      "instrument": "SPX500_USD",
      "status_code": 200,
      "verdict": "OK",
      "candle_count": 10,
      "first_candle_time": "2026-04-22T02:50:00.000000000Z",
      "error_message": null
    },
    {
      "instrument": "USB02Y_USD",
      "status_code": 403,
      "verdict": "FORBIDDEN",
      "candle_count": null,
      "first_candle_time": null,
      "error_message": "..."
    }
  ],
  "summary": {
    "total": 7,
    "ok": 5,
    "forbidden": 2,
    "not_found": 0,
    "other": 0
  }
}
```

### 4.4 レポート構成

`devnotes/20260422-1149-oanda-cfd-probe/probe-report.md` を **同一スクリプトが JSON 書き出し直後に生成**する（separate formatter にしない理由: 7 件しか結果が無いので独立化のメリットなし、整合性管理コスト低減を優先）:

1. **試験条件**: 環境 (live/practice), base_url, 試験日時
2. **結果サマリー表**: instrument × verdict × status_code × candle_count × first_candle_time
3. **判定**: 全 OK / 部分 OK / 全不可
4. **次アクション提案**:
   - 全 OK → 「OANDA CFD ingest pipeline 拡張」TODO 起票
   - 部分 OK → OK 分の ingest TODO + 不可分の FRED/合成 primitive TODO の 2 本立て
   - 全不可 → FRED + 自前計算 primitive 強化 TODO
5. **観測 vs 解釈の分離**: verdict は観測事実のみ。403/404 を「永久に使えない」と読まない注記を入れる。

実 API 走行時はこのレポートを Claude が読んで「次アクション提案」セクションに具体的な後続 TODO 候補（ID, 概要）を追記する。

## 5. テスト設計（概念）

`tests/scripts/test_oanda_cfd_probe.py`:

- `respx` で OANDA candles エンドポイントを mock（既存 `tests/api/test_oanda_client.py` のパターンに倣う）
- シナリオ:
  1. 全 200 OK → verdict = OK
  2. 全 403 → verdict = FORBIDDEN
  3. 全 404 → verdict = NOT_FOUND
  4. 混在 (一部 OK / 一部 403 / 一部 404) → 各 instrument の verdict が独立に正しい
  5. 401 (auth error) → 即時 exit 1
- output JSON ファイル生成と内容を assert
- exit code: 401 以外は常に 0（probe 自体は失敗しない）

## 6. 想定リスク・mitigation

| リスク | mitigation |
|---|---|
| 401 (token 切れ) → 全件 fail | 1 件目で 401 検知したら abort + stderr エラー、scripts/oanda_ping.py 相当の手順を案内 |
| Rate limit (429) | tenacity が 3 回まで自動リトライ。7 件しか叩かないので実害なし |
| candles エンドポイントが weekend で空配列 | OK 判定に candle_count > 0 を要求しない（200 が返れば OK）。candle_count=0 は warning 表示のみ |
| 実 API 試験は token 必須 | テストは respx mock。実走行は手動で 1 回だけ実施し result を commit |

## 7. 受け入れ基準

- [ ] `scripts/oanda_cfd_probe.py` で 7 instrument を試験できる
- [ ] 結果が JSON / Markdown 両方に出力される
- [ ] respx mock テストが 4 シナリオ以上カバーする
- [ ] レポートに次アクション提案が明記される
- [ ] runbook.md に手順が追記される
- [ ] cross-pair.md の external data 戦略が実測結果で更新される

## 8. 関連ドキュメント

- `docs/alpha_factory/concepts/oanda-cfd-probe.md` (元コンセプト)
- `docs/alpha_factory/cross-pair.md`
- `docs/alpha_factory/runbook.md`
- `scripts/oanda_ping.py` (実装参考)
- `src/api/oanda/client.py` (再利用元)
- `tests/api/test_oanda_client.py` (テスト参考)
