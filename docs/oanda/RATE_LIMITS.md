# OANDA API レートリミット（v20）

ローカルミラー [v20/best-practices/](./v20/best-practices/index.html) より抜粋。

## 公式の推奨値

| 区分 | 上限（推奨） | 出典原文 |
|---|---|---|
| 新規接続（TCP/SSL ハンドシェイク発生） | **2 req/sec** | "For new connections, we recommend you limit this to twice per second (2/s)." |
| 確立済み接続上のリクエスト（Keep-Alive 前提） | **100 req/sec** | "For an established connection, we recommend limiting this to one hundred per second (100/s)." |

「公式上限」ではなく「recommend（推奨）」という語だが、これを超えると **429** や接続強制切断のリスクがある。安全側で下回る運用が無難。

## Keep-Alive（HTTP Persistent Connection）

- HTTP/1.1 のクライアントはデフォルトで有効
- 公式計測: Keep-Alive 有効化でレイテンシ削減率

| アクション | Baseline (no KA) | Keep-Alive | 削減率 |
|---|---|---|---|
| Create Trade | 341.7ms | 117.8ms | 65.5% |
| Closing Trade | 340.3ms | 118.0ms | 65.3% |
| Get (100) Trades | 399.8ms | 236.9ms | 40.7% |

Python httpx は `httpx.Client` を使い回せば自動で Keep-Alive が効く。1 リクエストごとに `httpx.get` を呼び出す実装はこれを放棄することになる。

## zenigame-fx のコード側の設定

[src/api/oanda/rate_limit.py:10](../../src/api/oanda/rate_limit.py#L10):

```python
class TokenBucket:
    def __init__(self, rate_per_sec: float = 50.0, capacity: int = 50) -> None:
```

- デフォルト **50 req/sec**（established 100/s の半分、安全側）
- バースト容量 50（= 秒あたり上限と同じ）
- Phase1 の `fetch_historical.py` は 1 年分 M1 ≒ 74 リクエスト程度なので、この設定で余裕がある
- 複数通貨ペア並列取得を始める Phase4 以降、50 req/sec でも上限に近づく可能性がある。その時点で再評価

## v1（旧 API、日本語ドキュメント）側の補足制限

[jp-v1/v1/best-practices/](./jp-v1/v1/best-practices/index.html):

- `/transactions?count=500` は **1 req/min** 制限（v1 固有。v20 には該当なし、transactions は `/v3/accounts/{id}/transactions` でページング）
- HTTP レートストリームは同一トークンで複数コネクション可、**sessionId** で識別しないと古いコネクションが切断される

## 運用上のポイント

1. **Keep-Alive を保つ** — `httpx.Client` を使い捨てない
2. **429 / 5xx は tenacity で exponential backoff** — `src/api/oanda/client.py` で実装済み
3. **complete=false バーは永続キャッシュに入れない** — [Phase1 設計](../../devnotes/20260417-2200-phase1-detailed-design/detailed-design.md) 参照
4. **並列度を上げる場合は TokenBucket の rate/capacity を増やす前に公式値（100 req/s）を超えないかチェック**
5. **ストリーミング使用時は sessionId を設定** — Phase4 以降で WebSocket streaming に移行する場合の注意点
