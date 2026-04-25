**Verdict: NEEDS_REVISION**

Round 1 の **Must-fix の論点そのもの**は概ね潰せています。特に M3 の bps 正規化、M4 の `as_of` / known-at 前提、M5 の publication timestamp ベース化、safe default の warning + fail-fast 方針、EvaluationContext 注入経路の明記は妥当です。  
ただし、設計書内にまだ **実装を誤らせる不整合** が残っているため、この版のままは APPROVED にしません。

**Must-fix**
- `look-ahead bias 対策` 表の M5 がまだ `bar_time.date() - 1 以前` 参照になっています。L1/L3 では `publication_ts_utc < bar_time` に設計変更済みなので、ここは必ず統一が必要です。
- `Definition of Done` がまだ `_base.py::EvaluationContext` に `event_calendar=None` / `vix_daily=None` を追加する記述になっています。本文では `event_snapshot` / `vix_snapshot` に置き換わっており、ここがズレたままだと実装 API を誤ります。
- `テスト戦略` の後方互換確認も `event_calendar / vix_daily` の旧名称のままです。本文の snapshot 設計と一致させてください。

**Should-consider**
- `共通仕様` の `required_data` で M2 が `("ohlc", "calendar.session")` のままなのに、S3 では `("ohlc",)` に簡素化すると書かれており、ここも内部不整合です。どちらを正とするか 1 つに寄せた方が良いです。
- safe default の warning は十分ですが、`EvaluationResult.meta` を後続 TODO に送るなら、T012 では何をもって「伝搬漏れ検知が担保された」とみなすかを一文だけ補うと監査しやすくなります。

上の Must-fix を反映すれば、次版は **APPROVED 相当**です。